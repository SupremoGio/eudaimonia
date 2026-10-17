"""
Respuestas del usuario a la auditoría de Expense (2026-09-26):

1. «Nada que ingrese va a crédito»: 18 movimientos de BBVA Crédito con
   formato «… / 00xxxxxxx …» (jun-ago 2026) son líneas del estado de DÉBITO
   importadas otra vez como crédito; cada una tiene su gemelo en BBVA Débito
   (mismo día y monto). Se borran. El de Qualitas ($9,998.10, 02/07) no tiene
   gemelo: se mueve a BBVA Débito en vez de borrarse.
2. Plaza Panamericana $334.10 (17/05, «Impresión y tinta») y Office Depot
   $213 (30/06, lote 43793) -> EXPENSE.
3. Lotes de la pestaña Expense con los folios del reporte de la empresa
   (expenses_20260925.csv), su depósito y las facturas ubicadas.

Todo se identifica por id + fecha + monto (y banco al borrar) y es
idempotente: una fila que no coincide no se toca.
"""
from . import expense_lotes as _lotes

DUPLICADOS_CREDITO = (  # (id, fecha, monto) en BBVA_TDC
    (2232, '2026-06-18', 709.00), (2264, '2026-06-29', 4500.00), (2265, '2026-06-27', 358.00),
    (2266, '2026-06-22', 1000.00), (2320, '2026-07-11', 1000.00), (2322, '2026-07-07', 4000.00),
    (2324, '2026-07-02', 0.01), (2325, '2026-07-01', 129.00), (2379, '2026-07-22', 7163.62),
    (2380, '2026-07-17', 410.00), (2440, '2026-08-14', 1000.00), (2442, '2026-08-12', 3799.40),
    (2443, '2026-08-10', 3000.00), (2444, '2026-08-07', 2000.00), (2445, '2026-08-07', 2500.00),
    (2493, '2026-08-05', 74.00), (2522, '2026-08-20', 500.00), (2523, '2026-08-18', 986.50),
)
A_DEBITO = ((2323, '2026-07-02', 9998.10),)
A_EXPENSE = ((2098, '2026-05-17', 334.10), (2337, '2026-06-30', 213.00))

# (nombre, notas, [facturas (id, fecha, monto)], [depósitos (id, fecha, monto)])
LOTES = (
    ('Folio 40524 · Día del niño y de las madres', 'Sin ubicar en tarjetas: regalos día de las madres $8,067.68 y pastel Sup Pau $480',
     [(2026, '2026-04-28', 379.00), (2039, '2026-04-30', 420.00), (2030, '2026-04-29', 119.80),
      (2025, '2026-04-28', 347.00), (2098, '2026-05-17', 334.10)],
     [(2104, '2026-05-20', 10143.50)]),
    ('Folio 41138 · Pastel aniversario PT1', 'Lo pagó un compañero; la empresa te lo depositó y tú se lo pasaste',
     [(2120, '2026-05-27', 3950.00), (2119, '2026-05-28', 632.00)], [(2121, '2026-05-27', 4582.00)]),
    ('Folio 41457 · Pastel aniversario PT2', 'Lo pagó un compañero; la empresa te lo depositó y tú se lo pasaste',
     [(2147, '2026-06-03', 3950.00), (2141, '2026-06-08', 632.00)], [(2146, '2026-06-04', 4582.00)]),
    ('Folio 41143 · AAW', 'Compra de $709 sin ubicar en tarjetas', [], [(2247, '2026-06-18', 709.00)]),
    ('Folios 42644 + 42488 · Junio', 'Un solo depósito pagó los dos folios ($965 + $6,198.62)',
     [(2284, '2026-06-19', 3316.00)], [(2371, '2026-07-22', 7163.62)]),
    ('Folio 43793 · 8 facturas', '', [(2337, '2026-06-30', 213.00)], [(2494, '2026-08-12', 3799.40)]),
    ('Folio 44449 · Farmacia y panificación', '', [], [(2529, '2026-08-18', 986.50)]),
    ('Folio 45332 · 10 facturas', '', [(2449, '2026-08-14', 279.95)], [(2580, '2026-09-15', 4174.94)]),
)


def _existe(db, mid, fecha, monto, banco=None):
    q = "SELECT * FROM est_movimientos WHERE id=? AND substr(fecha,1,10)=? AND ABS(ABS(monto)-?) < 0.01"
    args = [mid, fecha, abs(monto)]
    if banco:
        q += " AND banco=?"
        args.append(banco)
    return db.execute(q, args).fetchone()


def _ligado(db, mid) -> bool:
    return any(db.execute(f"SELECT 1 FROM {t} WHERE movimiento_id=?", (mid,)).fetchone() for t in (
        'est_expense_lote_gastos', 'est_expense_lote_depositos', 'est_prestamo_devoluciones'))


def aplicar(db) -> dict:
    res = {'borrados': 0, 'a_debito': 0, 'a_expense': 0, 'lotes': 0}
    for mid, f, m in DUPLICADOS_CREDITO:
        if _existe(db, mid, f, m, 'BBVA_TDC') and not _ligado(db, mid) \
                and not db.execute("SELECT 1 FROM est_prestamos WHERE movimiento_id=?", (mid,)).fetchone():
            db.execute("DELETE FROM est_movimientos WHERE id=?", (mid,))
            res['borrados'] += 1
    for mid, f, m in A_DEBITO:
        if _existe(db, mid, f, m, 'BBVA_TDC'):
            db.execute("UPDATE est_movimientos SET banco='BBVA_DEB' WHERE id=?", (mid,))
            res['a_debito'] += 1
    for mid, f, m in A_EXPENSE:
        r = _existe(db, mid, f, m)
        if r and r['categoria'] != 'EXPENSE':
            db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='', tipo='GASTO' WHERE id=?", (mid,))
            res['a_expense'] += 1
    for nombre, notas, gastos, deps in LOTES:
        if db.execute("SELECT 1 FROM est_expense_lotes WHERE nombre=?", (nombre,)).fetchone():
            continue
        g_ok = [mid for mid, f, m in gastos
                if (r := _existe(db, mid, f, m)) and r['categoria'] == 'EXPENSE' and r['tipo'] == 'GASTO'
                and not db.execute("SELECT 1 FROM est_expense_lote_gastos WHERE movimiento_id=?", (mid,)).fetchone()]
        d_ok = [mid for mid, f, m in deps
                if (r := _existe(db, mid, f, m)) and r['tipo'] == 'INGRESO' and not _ligado(db, mid)]
        if not d_ok and not g_ok:
            continue
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (nombre, notas, _lotes.ahora())).lastrowid
        for mid in g_ok:
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, mid, _lotes.ahora()))
        for mid in d_ok:
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (mid,))
            db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, mid, _lotes.ahora()))
        _lotes.sincronizar(db, lid)
        res['lotes'] += 1
    return res
