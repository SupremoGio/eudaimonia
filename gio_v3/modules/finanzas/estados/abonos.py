"""
Abonos sin conciliar: dinero que te entró (tipo INGRESO) que no cuenta como
ingreso -- FINANZAS (transferencias, depósitos, reembolsables), PRESTAMOS o
EXPENSE -- y que todavía no está ligado a nada: ni como devolución de un
préstamo (est_prestamo_devoluciones) ni como depósito de un lote de Expense
(est_expense_lote_depositos). El usuario (2026-09-28): «¿cómo veo los que no
están conciliados en Expense ni en Préstamos? debe haber aún algunos».

Solo lectura: para conciliarlos se ligan en Por cobrar / Expense o se les
cambia la categoría (p. ej. a ingreso real).

Cada abono trae una «pista» de qué es probablemente (el usuario, 2026-09-29:
«es mucho dinero que no sé dónde va… sé que mucho son regresos de préstamos,
expenses y así»), en este orden:
  - expense: el algoritmo de Expense (expense_lotes.sugerencias) lo cuadra
    con facturas EXPENSE sin lote.
  - prestamo: un préstamo con pendiente cuyo nombre aparece en la
    descripción, o cuyo pendiente es exactamente el monto (después de prestar).
  - propia: la misma cantidad salió de otra de tus cuentas ±3 días como
    transferencia, pago o inversión (no un gasto normal): es dinero tuyo que
    se movió entre cuentas, no entró de fuera.
  - sin pista.
"""
import re
from datetime import date, timedelta

CATEGORIAS = ('FINANZAS', 'PRESTAMOS', 'EXPENSE')
# Abonos que el usuario (o conciliar_pistas) marcó como dinero que vino de
# otra de sus cuentas: ya están conciliados, no salen en la lista.
SUB_PROPIA = 'Entre cuentas propias'


def sin_conciliar(db, anio: str | None = None) -> dict:
    ph = ','.join('?' * len(CATEGORIAS))
    params = list(CATEGORIAS)
    filtro_anio = ''
    if anio:
        filtro_anio = "AND substr(fecha, 1, 4) = ?"
        params.append(str(anio))
    rows = [dict(r) for r in db.execute(f"""
        SELECT * FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph}) {filtro_anio}
          AND COALESCE(subcategoria, '') != '{SUB_PROPIA}'
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
        ORDER BY fecha DESC, id DESC
    """, params).fetchall()]
    grupos = {}
    for r in rows:
        k = r['categoria'] if r['categoria'] != 'FINANZAS' else (r['subcategoria'] or 'Sin subcategoría')
        g = grupos.setdefault(k, {'grupo': k, 'n': 0, 'total': 0.0})
        g['n'] += 1
        g['total'] += abs(r['monto'] or 0)
    anios = [r[0] for r in db.execute(f"""
        SELECT DISTINCT substr(fecha, 1, 4) FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph}) ORDER BY 1 DESC
    """, list(CATEGORIAS)).fetchall()]
    _pistas(db, rows)
    por_pista = {}
    for r in rows:
        t = r['pista']['tipo'] if r['pista'] else 'ninguna'
        g = por_pista.setdefault(t, {'tipo': t, 'n': 0, 'total': 0.0})
        g['n'] += 1
        g['total'] += abs(r['monto'] or 0)
    return {
        'movimientos': rows,
        'por_pista': sorted(({**g, 'total': round(g['total'], 2)} for g in por_pista.values()),
                            key=lambda g: -g['total']),
        'total': round(sum(abs(r['monto'] or 0) for r in rows), 2),
        'grupos': sorted(({**g, 'total': round(g['total'], 2)} for g in grupos.values()),
                         key=lambda g: -g['total']),
        'anios': anios,
    }


def filas_csv(db, anio: str | None = None) -> list[list]:
    return [[r['id'], (r['fecha'] or '')[:10], r['descripcion'], abs(r['monto'] or 0), r['banco'],
             r['categoria'], r['subcategoria'] or '', r['pista']['texto'] if r['pista'] else '', '']
            for r in sin_conciliar(db, anio)['movimientos']]


PROPIA_DIAS = 3
_PALABRAS_COMUNES = {'PAGO', 'CUENTA', 'TERCERO', 'BNET', 'SPEI', 'RECIBIDO', 'ENVIADO', 'DEPOSITO',
                     'TRANSF', 'TRANSFERENCIA', 'PARA', 'DEL', 'LOS', 'LAS', 'GIO', 'GIOVANY', 'ALBERTO',
                     'SANCHEZ', 'BBVA', 'MEXICO'}


def _palabras(nombre: str) -> set:
    return {w for w in re.findall(r'[A-ZÑ]{3,}', (nombre or '').upper()) if w not in _PALABRAS_COMUNES}


def _pistas(db, rows) -> None:
    """Pone r['pista'] = {'tipo', 'texto'} o None en cada abono (ver docstring del módulo)."""
    try:
        from . import expense_lotes
        exp = {}
        for sug in expense_lotes.sugerencias(db):
            for d in sug['depositos']:
                exp[d['id']] = (f"Expense: cuadra con {len(sug['facturas'])} factura(s) por "
                                f"${sug['total']:,.2f} (confianza {sug['confianza']})", sug)
    except Exception:
        exp = {}
    try:
        from . import prestamos
        abiertos = [p for p in prestamos.listar(db) if p['pendiente'] > 0 and not p['perdido_fecha']]
    except Exception:
        abiertos = []
    for r in rows:
        r['pista'] = None
        monto, fecha = abs(r['monto'] or 0), (r['fecha'] or '')[:10]
        if r['id'] in exp:
            texto, sug = exp[r['id']]
            r['pista'] = {'tipo': 'expense', 'texto': texto, 'confianza': sug['confianza'],
                          'facturas': [f['id'] for f in sug['facturas']],
                          'depositos': [d['id'] for d in sug['depositos']], 'nombre': sug['nombre']}
            continue
        desc = _palabras(r['descripcion'])
        p = next((p for p in abiertos if (p['fecha'] or '')[:10] <= fecha and _palabras(p['persona']) & desc), None) \
            or next((p for p in abiertos if (p['fecha'] or '')[:10] <= fecha and abs(p['pendiente'] - monto) < 0.01), None)
        if p:
            r['pista'] = {'tipo': 'prestamo', 'prestamo_id': p['id'],
                          'texto': f"Préstamo a {p['persona']} del {p['fecha'][:10]} (pendiente ${p['pendiente']:,.2f})"}
            continue
        if not fecha:
            continue
        d = date.fromisoformat(fecha)
        par = db.execute("""
            SELECT fecha, banco, descripcion FROM est_movimientos
            WHERE tipo IN ('GASTO', 'PAGO') AND banco != ? AND ABS(ABS(monto) - ?) < 0.01
              AND (tipo = 'PAGO' OR categoria IN ('FINANZAS', 'INVERSION', 'PAGO'))
              AND substr(fecha,1,10) BETWEEN ? AND ?
            ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?)) LIMIT 1
        """, (r['banco'], monto, (d - timedelta(days=PROPIA_DIAS)).isoformat(),
              (d + timedelta(days=PROPIA_DIAS)).isoformat(), fecha)).fetchone()
        if par:
            r['pista'] = {'tipo': 'propia', 'texto': f"Entre tus cuentas: salió de {par['banco']} el "
                                                     f"{par['fecha'][:10]} ({par['descripcion']})"}



CONFIANZAS_EXPENSE = ('alta', 'media')   # «aproximada» no cuadra exacto: se revisa a mano


def conciliar_pistas(db) -> dict:
    """Aplica las pistas (el usuario, 2026-09-29: «manda esas sugerencias,
    concílialas»):
      - expense (confianza alta/media): crea el lote con sus facturas y
        depósito(s), como «Crear lote» en la pestaña Expense.
      - prestamo: liga la devolución, sin pasar del pendiente del préstamo.
      - propia: FINANZAS/«Entre cuentas propias».
    Lo que no se aplica (Expense aproximada, devolución mayor al pendiente)
    se queda en la lista con su pista. Devuelve los conteos."""
    from datetime import datetime
    from . import expense_lotes, prestamos
    ahora = datetime.now().isoformat(timespec='seconds')
    out = {'expense_lotes': 0, 'expense_depositos': 0, 'prestamos': 0, 'propias': 0, 'sin_aplicar': 0}
    rows = sorted(sin_conciliar(db)['movimientos'], key=lambda r: (r['fecha'] or '', r['id']))
    pendiente = {p['id']: p['pendiente'] for p in prestamos.listar(db)}
    hechos = set()
    for r in rows:
        pista = r['pista']
        if not pista or r['id'] in hechos:
            continue
        monto = abs(r['monto'] or 0)
        if pista['tipo'] == 'expense':
            if pista['confianza'] not in CONFIANZAS_EXPENSE:
                out['sin_aplicar'] += 1
                continue
            libres = lambda tabla, ids: not db.execute(
                f"SELECT 1 FROM {tabla} WHERE movimiento_id IN ({','.join('?' * len(ids))})", ids).fetchone()
            if not (libres('est_expense_lote_gastos', pista['facturas'])
                    and libres('est_expense_lote_depositos', pista['depositos'])):
                out['sin_aplicar'] += 1
                continue
            lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                             (pista['nombre'], 'Conciliado desde «Sin conciliar»', ahora)).lastrowid
            for mid in pista['facturas']:
                db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                           (lid, mid, ahora))
            for mid in pista['depositos']:
                db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (mid,))
                db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                           (lid, mid, ahora))
                hechos.add(mid)
            expense_lotes.sincronizar(db, lid)
            out['expense_lotes'] += 1
            out['expense_depositos'] += len(pista['depositos'])
        elif pista['tipo'] == 'prestamo':
            pid = pista['prestamo_id']
            if monto > pendiente.get(pid, 0) + 0.01:
                out['sin_aplicar'] += 1
                continue
            db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='' WHERE id=?", (r['id'],))
            db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (pid, r['id'], ahora))
            pendiente[pid] = round(pendiente[pid] - monto, 2)
            out['prestamos'] += 1
        elif pista['tipo'] == 'propia':
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=? WHERE id=?", (SUB_PROPIA, r['id']))
            out['propias'] += 1
    return out
