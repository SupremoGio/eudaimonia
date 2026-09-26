"""
Estados de cuenta del Libretón BBVA Débito (cuenta 1520361804) que el usuario
mandó para llenar los huecos de la auditoría (2026-09-26, «te voy a pasar 5
por 5»). Cada archivo de data/bbva_deb_libreton/<AAAAMM>.json es la salida del
parser del Libretón (bbva_libreton._parse_text) sobre el PDF del banco, ya
cuadrada contra «Total importe cargos/abonos» del propio PDF (ver `totales`).
Cuando el saldo impreso no alcanza para decidir si una transferencia fue
cargo o abono, el tipo se fijó a mano y quedó anotado en `ajustes`.

Cada archivo se aplica una sola vez (migración finanzas_libreton_<AAAAMM>) y
pasa por lo mismo que un import: post-proceso de inversiones, pagos de TDC
como movimiento interno, nómina y «Aplicar reglas», más lo que el usuario ya
decidió en el CSV corregido (_decisiones_previas).

Nunca duplica: un movimiento del PDF se da por existente si BBVA_DEB ya tiene
una fila del mismo monto en su fecha de operación o de liquidación (las
descargas de la app pueden traer cualquiera de las dos). Se cuenta por
multiconjunto: dos transferencias de $500 el mismo día en el PDF contra una
en la base -> se inserta solo una.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'bbva_deb_libreton')


def archivos() -> list[str]:
    """Claves AAAAMM disponibles, en orden."""
    return sorted(f[:-5] for f in os.listdir(DATA_DIR) if f.endswith('.json'))


def cargar(clave: str) -> dict:
    with open(os.path.join(DATA_DIR, f'{clave}.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _decisiones_previas(db, ids: list) -> None:
    """Lo que el usuario ya decidió para movimientos iguales en el CSV
    corregido (correcciones_csv_2026_09_26): SPEI de NAFIN recibido es
    retiro de CETES; «expense» pagado es EXPENSE y el depósito de expense
    es su reembolso."""
    ph = ','.join('?' * len(ids))
    db.execute(f"""UPDATE est_movimientos SET categoria='CETES', subcategoria='RETIRO', tipo='INVERSION'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'SPEI RECIBIDONAFIN%'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='', tipo='GASTO'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE '%EXPENSE%' AND tipo='GASTO'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE '%EXPENSE%' AND tipo='INGRESO'""", ids)


def aplicar(db, clave: str) -> tuple[int, int]:
    """Inserta los movimientos faltantes de un Libretón; (insertados, ya existían)."""
    from .routes import (_auto_clasificar_nomina, _postproceso_inversiones,
                         _reaplicar_reglas, _unify_movimiento_interno)
    data = cargar(clave)
    movs = data['movimientos']
    fechas = sorted({m['fecha'] for m in movs} | {m['fecha_cargo'] for m in movs})
    existentes = [dict(r) for r in db.execute(
        f"""SELECT id, substr(fecha,1,10) AS fecha, ABS(monto) AS monto FROM est_movimientos
            WHERE banco='BBVA_DEB' AND substr(fecha,1,10) IN ({','.join('?' * len(fechas))})""",
        fechas).fetchall()]
    usados, nuevas, ya = set(), [], 0
    for m in movs:
        match = next((e for e in existentes if e['id'] not in usados
                      and e['fecha'] in (m['fecha'], m['fecha_cargo'])
                      and abs(e['monto'] - abs(m['monto'])) < 0.005), None)
        if match:
            usados.add(match['id'])
            ya += 1
            continue
        cur = db.execute("""INSERT OR IGNORE INTO est_movimientos
                            (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
                            VALUES (?,?,?,?, 'BBVA_DEB', ?,?,?,?)""",
                         (m['fecha'], m['fecha_cargo'], m['descripcion'], m['monto'], data['periodo'],
                          m['categoria'], m['subcategoria'], m['tipo']))
        if cur.rowcount:
            nuevas.append(cur.lastrowid)
        else:
            ya += 1
    if nuevas:
        _decisiones_previas(db, nuevas)
        _reaplicar_reglas(db)
        _postproceso_inversiones(db)
        _unify_movimiento_interno(db, nuevas)
        _auto_clasificar_nomina(db, nuevas)
    return len(nuevas), ya
