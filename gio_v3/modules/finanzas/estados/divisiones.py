"""
Movimientos divididos en varias categorías.

Un solo cargo del banco a veces es de varias cosas: un pedido de Amazon con
desodorante (CUIDADO_PERSONAL), una playera (ROPA) y un balón (DEPORTE), o
una transferencia que fue parte renta y parte préstamo. Antes se mandaba
todo «a lo que más pesa» (ver pedidos_amazon.py).

Modelo (mismo patrón que las compras a MSI):
  - El cargo original del banco NO se toca: conserva fecha, descripción y
    monto, así el dedup de la carga de estados (fecha, descripcion, monto) y
    la conciliación contra el PDF siguen viéndolo igual. Pasa a
    FINANZAS/Dividido, que no cuenta como gasto ni como ingreso.
  - Cada parte es una fila propia de est_movimientos con `dividido_de` = id
    del cargo original, mismo banco/fecha/tipo y su propia categoría. Como
    son filas normales, reportes, presupuestos, «mi parte», viajes, etc.
    funcionan sin cambios.
  - La categoría que manda es la de est_division_partes. Las reglas de
    keyword y las correcciones automáticas tocan filas por descripción (la
    parte de un «AMAZON» se iría a DIGITAL), así que reafirmar() se corre al
    final de «Aplicar reglas» y de cada carga de estados y vuelve a imponer
    padre e hijos. Editar la categoría de una parte desde el modal actualiza
    est_division_partes (ver sincronizar_edicion).
  - Las auditorías contra el PDF ignoran las partes (dividido_de IS NOT
    NULL): no son renglones del banco.
"""
from datetime import datetime

CAT_PADRE, SUB_PADRE = 'FINANZAS', 'Dividido'
TOLERANCIA = 0.01
MAX_PARTES = 20

# SQL para excluir filas de una división en consultas que comparan contra el
# banco (dedup, conciliación): las partes no son renglones del estado.
SOLO_BANCO = "dividido_de IS NULL"


class DivisionError(ValueError):
    pass


def _ahora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _signo(monto: float) -> float:
    return -1.0 if monto < 0 else 1.0


def es_padre(db, mov_id: int) -> bool:
    return db.execute("SELECT 1 FROM est_divisiones WHERE padre_id=?", (mov_id,)).fetchone() is not None


def padre_de(db, mov_id: int) -> int | None:
    """id del cargo original si `mov_id` es el cargo o una de sus partes."""
    if es_padre(db, mov_id):
        return mov_id
    r = db.execute("SELECT dividido_de FROM est_movimientos WHERE id=?", (mov_id,)).fetchone()
    return r['dividido_de'] if r and r['dividido_de'] else None


def obtener(db, mov_id: int) -> dict | None:
    """{padre, partes, cat_original} de la división a la que pertenece
    `mov_id` (cargo o parte), o None si no está dividido."""
    pid = padre_de(db, mov_id)
    if pid is None:
        return None
    padre = db.execute("SELECT * FROM est_movimientos WHERE id=?", (pid,)).fetchone()
    cab = db.execute("SELECT * FROM est_divisiones WHERE padre_id=?", (pid,)).fetchone()
    if not padre or not cab:
        return None
    partes = [dict(r) for r in db.execute(
        "SELECT id, hijo_id, orden, monto, categoria, subcategoria, nota FROM est_division_partes "
        "WHERE padre_id=? ORDER BY orden", (pid,)).fetchall()]
    return {'padre': dict(padre), 'partes': partes,
            'cat_original': cab['cat_original'], 'sub_original': cab['sub_original'] or ''}


def _descripcion(padre_desc: str, nota: str, i: int, n: int) -> str:
    # (i/n) siempre: dos partes con la misma nota y monto chocarían con el
    # índice UNIQUE(fecha, descripcion, monto).
    nota = (nota or '').strip()
    return f"{padre_desc} · {nota} ({i}/{n})" if nota else f"{padre_desc} · parte {i}/{n}"


def _validar(db, padre, partes: list[dict], normalizar_sub) -> list[dict]:
    if padre['dividido_de']:
        raise DivisionError('Esta fila ya es parte de una división: edita la división del movimiento original.')
    if padre['mi_parte'] is not None:
        raise DivisionError('Quita «Mi parte» antes de dividir: puedes ponerla después en cada parte.')
    if not isinstance(partes, list) or len(partes) < 2:
        raise DivisionError('Una división necesita al menos 2 partes.')
    if len(partes) > MAX_PARTES:
        raise DivisionError(f'Máximo {MAX_PARTES} partes.')
    limpias = []
    for i, p in enumerate(partes, 1):
        try:
            monto = round(abs(float(p.get('monto'))), 2)
        except (TypeError, ValueError):
            raise DivisionError(f'Parte {i}: monto inválido.')
        if monto <= 0:
            raise DivisionError(f'Parte {i}: el monto debe ser mayor a 0.')
        cat = (p.get('categoria') or '').strip()
        if not cat:
            raise DivisionError(f'Parte {i}: falta la categoría.')
        if cat == CAT_PADRE and (p.get('subcategoria') or '') == SUB_PADRE:
            raise DivisionError(f'Parte {i}: «Dividido» no es una categoría para una parte.')
        limpias.append({'monto': monto, 'categoria': cat,
                        'subcategoria': normalizar_sub(cat, p.get('subcategoria') or ''),
                        'nota': (p.get('nota') or '').strip()[:80]})
    total = round(abs(float(padre['monto'])), 2)
    suma = round(sum(p['monto'] for p in limpias), 2)
    if abs(suma - total) > TOLERANCIA:
        raise DivisionError(f'Las partes suman ${suma:,.2f} y el movimiento es de ${total:,.2f}.')
    return limpias


def _insertar_hijo(db, padre, parte: dict, i: int, n: int) -> int:
    cur = db.execute("""
        INSERT INTO est_movimientos
            (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo,
             viaje_id, dividido_de)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (padre['fecha'], padre['fecha_cargo'] or padre['fecha'],
          _descripcion(padre['descripcion'], parte['nota'], i, n),
          _signo(padre['monto']) * parte['monto'], padre['banco'], padre['periodo'],
          parte['categoria'], parte['subcategoria'], padre['tipo'], padre['viaje_id'], padre['id']))
    return cur.lastrowid


def _borrar_hijos(db, padre_id: int) -> None:
    hijos = [r['id'] for r in db.execute("SELECT id FROM est_movimientos WHERE dividido_de=?", (padre_id,)).fetchall()]
    for h in hijos:
        # Lo que se haya ligado a la parte (préstamo, «te deben parte»,
        # lote de Expense) se suelta con ella.
        db.execute("DELETE FROM est_prestamo_devoluciones WHERE movimiento_id=?", (h,))
        db.execute("UPDATE est_prestamos SET movimiento_id=NULL WHERE movimiento_id=?", (h,))
        db.execute("DELETE FROM est_expense_lote_gastos WHERE movimiento_id=?", (h,))
        db.execute("DELETE FROM est_expense_lote_depositos WHERE movimiento_id=?", (h,))
        db.execute("DELETE FROM est_movimientos WHERE id=?", (h,))
    db.execute("DELETE FROM est_division_partes WHERE padre_id=?", (padre_id,))


def guardar(db, mov_id: int, partes: list[dict], normalizar_sub=lambda c, s: s) -> dict:
    """Crea o reemplaza la división del movimiento `mov_id` (el cargo o una
    de sus partes). Las partes deben sumar el monto del cargo. El caller
    hace commit."""
    pid = padre_de(db, mov_id) or mov_id
    padre = db.execute("SELECT * FROM est_movimientos WHERE id=?", (pid,)).fetchone()
    if not padre:
        raise DivisionError('Movimiento no encontrado.')
    limpias = _validar(db, padre, partes, normalizar_sub)
    cab = db.execute("SELECT * FROM est_divisiones WHERE padre_id=?", (pid,)).fetchone()
    if cab:
        _borrar_hijos(db, pid)
    else:
        db.execute("INSERT INTO est_divisiones (padre_id, cat_original, sub_original, created_at) VALUES (?,?,?,?)",
                   (pid, padre['categoria'] or '', padre['subcategoria'] or '', _ahora()))
    n = len(limpias)
    for i, p in enumerate(limpias, 1):
        hijo = _insertar_hijo(db, padre, p, i, n)
        db.execute("""INSERT INTO est_division_partes (padre_id, hijo_id, orden, monto, categoria, subcategoria, nota)
                      VALUES (?,?,?,?,?,?,?)""", (pid, hijo, i, p['monto'], p['categoria'], p['subcategoria'], p['nota']))
    db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (CAT_PADRE, SUB_PADRE, pid))
    return obtener(db, pid)


def deshacer(db, mov_id: int) -> bool:
    """Borra las partes y regresa el cargo a la categoría que tenía antes de
    dividirlo. El caller hace commit."""
    pid = padre_de(db, mov_id)
    if pid is None:
        return False
    cab = db.execute("SELECT * FROM est_divisiones WHERE padre_id=?", (pid,)).fetchone()
    _borrar_hijos(db, pid)
    db.execute("DELETE FROM est_divisiones WHERE padre_id=?", (pid,))
    if cab:
        db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?",
                   (cab['cat_original'] or 'OTROS', cab['sub_original'] or '', pid))
    return True


def sincronizar_edicion(db, mov_id: int) -> None:
    """Tras editar una parte desde el modal: su categoría nueva pasa a ser la
    que manda (si no, reafirmar() la regresaría). Llamar después de aplicar
    el PATCH, antes de reafirmar_uno()."""
    r = db.execute("SELECT id, dividido_de, categoria, subcategoria FROM est_movimientos WHERE id=?",
                   (mov_id,)).fetchone()
    if not r or not r['dividido_de']:
        return
    if (r['categoria'], r['subcategoria'] or '') == (CAT_PADRE, SUB_PADRE):
        return
    db.execute("UPDATE est_division_partes SET categoria=?, subcategoria=? WHERE hijo_id=?",
               (r['categoria'], r['subcategoria'] or '', mov_id))


def _reafirmar_padre(db, pid: int) -> int:
    """Impone la división de un cargo. Devuelve cuántas filas cambió."""
    padre = db.execute("SELECT * FROM est_movimientos WHERE id=?", (pid,)).fetchone()
    if not padre:
        # El cargo se borró (auditoría, duplicado): las partes no pueden
        # quedar sueltas sumando gasto.
        n = db.execute("SELECT COUNT(*) FROM est_movimientos WHERE dividido_de=?", (pid,)).fetchone()[0]
        _borrar_hijos(db, pid)
        db.execute("DELETE FROM est_divisiones WHERE padre_id=?", (pid,))
        return n
    cambios = 0
    if (padre['categoria'], padre['subcategoria'] or '') != (CAT_PADRE, SUB_PADRE):
        db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (CAT_PADRE, SUB_PADRE, pid))
        cambios += 1
    partes = db.execute("SELECT * FROM est_division_partes WHERE padre_id=? ORDER BY orden", (pid,)).fetchall()
    n = len(partes)
    vivos = set()
    for p in partes:
        hijo = p['hijo_id'] and db.execute("SELECT * FROM est_movimientos WHERE id=? AND dividido_de=?",
                                           (p['hijo_id'], pid)).fetchone()
        if not hijo:
            nuevo = _insertar_hijo(db, padre, dict(p), p['orden'], n)
            db.execute("UPDATE est_division_partes SET hijo_id=? WHERE id=?", (nuevo, p['id']))
            vivos.add(nuevo)
            cambios += 1
            continue
        vivos.add(hijo['id'])
        monto = _signo(padre['monto']) * p['monto']
        # La parte sigue al cargo en todo lo que viene del banco.
        espejo = {'fecha': padre['fecha'], 'fecha_cargo': padre['fecha_cargo'] or padre['fecha'],
                  'banco': padre['banco'], 'periodo': padre['periodo'], 'tipo': padre['tipo']}
        if ((hijo['categoria'], hijo['subcategoria'] or '') != (p['categoria'], p['subcategoria'] or '')
                or abs(hijo['monto'] - monto) > 0.005 or any(hijo[k] != v for k, v in espejo.items())):
            db.execute("""UPDATE est_movimientos SET categoria=?, subcategoria=?, monto=?,
                              fecha=?, fecha_cargo=?, banco=?, periodo=?, tipo=? WHERE id=?""",
                       (p['categoria'], p['subcategoria'] or '', monto, *espejo.values(), hijo['id']))
            cambios += 1
    for r in db.execute("SELECT id FROM est_movimientos WHERE dividido_de=?", (pid,)).fetchall():
        if r['id'] not in vivos:
            db.execute("DELETE FROM est_movimientos WHERE id=?", (r['id'],))
            cambios += 1
    return cambios


def reafirmar(db) -> int:
    """Vuelve a imponer todas las divisiones (idempotente). Va al final de
    «Aplicar reglas» y de la carga de estados."""
    cambios = 0
    for r in db.execute("SELECT padre_id FROM est_divisiones").fetchall():
        cambios += _reafirmar_padre(db, r['padre_id'])
    # Partes cuyo cargo ya no tiene división registrada.
    for r in db.execute("""SELECT id FROM est_movimientos WHERE dividido_de IS NOT NULL
                           AND dividido_de NOT IN (SELECT padre_id FROM est_divisiones)""").fetchall():
        db.execute("DELETE FROM est_movimientos WHERE id=?", (r['id'],))
        cambios += 1
    return cambios


def reafirmar_uno(db, mov_id: int) -> int:
    pid = padre_de(db, mov_id)
    return _reafirmar_padre(db, pid) if pid is not None else 0
