"""
Cierre del histórico de Expense hasta el 31/12/2025 (el usuario, 2026-11-01:
«los expense del 2025 para atrás ya no me quebraré la cabeza por conciliarlos
… lo marcamos como pagado; a partir de ahora llevaremos un mejor control»).

Sin borrar movimientos ni cambiar categorías (los reportes de gasto/ingreso
no se mueven):
  - Lotes abiertos (Pendiente / Pago parcial / sin gastos) cuyo movimiento
    más reciente es de 2025 o antes, y sin depósito de 2026 en adelante:
    quedan cerrados.
  - Facturas EXPENSE sin lote y depósitos de la empresa sin lote de 2025 o
    antes: un lote por año, «Histórico AAAA · cerrado sin conciliar».
Un lote cerrado cuenta como pagado: no suma a «Por cobrar», no sale en
sugerencias ni en «Sin pareja», y sus facturas quedan Pagado (las «Pagado a
compañero» conservan su estatus). Para revertir: cerrado=0 en
est_expense_lotes (y borrar los lotes «Histórico …»).
"""
from . import expense_lotes as _lotes

CORTE = '2026-01-01'
NOTA = 'Cierre del histórico: marcado como pagado sin conciliar (2026-11-01)'


def asegurar_columna(db) -> None:
    cols = [r['name'] for r in db.execute("PRAGMA table_info(est_expense_lotes)").fetchall()]
    if 'cerrado' not in cols:
        db.execute("ALTER TABLE est_expense_lotes ADD COLUMN cerrado INTEGER DEFAULT 0")


def aplicar(db) -> dict:
    asegurar_columna(db)
    res = {'lotes_cerrados': 0, 'lotes_historicos': 0, 'facturas': 0, 'depositos': 0}
    for l in _lotes.listar(db):
        if l['cerrado'] or l['estado'] == _lotes.REEMBOLSADO:
            continue
        fechas = [x['fecha'][:10] for x in l['gastos'] + l['depositos'] if x.get('fecha')]
        if not fechas or max(fechas) >= CORTE:
            continue
        db.execute("UPDATE est_expense_lotes SET cerrado=1 WHERE id=?", (l['id'],))
        _lotes.sincronizar(db, l['id'])
        res['lotes_cerrados'] += 1

    facturas = [g for g in _lotes.sin_lote(db) if g['fecha'][:10] < CORTE]
    depositos = [d for d in _lotes._depositos_sin_lote(db) if d['fecha'][:10] < CORTE]
    por_anio = {}
    for g in facturas:
        por_anio.setdefault(g['fecha'][:4], ([], []))[0].append(g['id'])
    for d in depositos:
        por_anio.setdefault(d['fecha'][:4], ([], []))[1].append(d['id'])
    for anio in sorted(por_anio):
        gastos, deps = por_anio[anio]
        nombre = f'Histórico {anio} · cerrado sin conciliar'
        fila = db.execute("SELECT id FROM est_expense_lotes WHERE nombre=?", (nombre,)).fetchone()
        lid = fila['id'] if fila else db.execute(
            "INSERT INTO est_expense_lotes (nombre, notas, created_at, cerrado) VALUES (?,?,?,1)",
            (nombre, NOTA, _lotes.ahora())).lastrowid
        res['lotes_historicos'] += 0 if fila else 1
        for mid in gastos:
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, mid, _lotes.ahora()))
        for mid in deps:
            db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, mid, _lotes.ahora()))
        res['facturas'] += len(gastos)
        res['depositos'] += len(deps)
        _lotes.sincronizar(db, lid)
    return res
