"""
Folios de Expense que el usuario manda (PDF del reporte de la empresa) y que
se arman como lote aunque la empresa todavía no deposite.

Cada folio: nombre, notas, facturas (fecha, monto, texto en la descripción)
y el depósito que se espera (total del reporte). Corre en cada arranque y
al abrir la pestaña Expense, y es idempotente:
  - crea el lote si no existe y le agrega cada factura que encuentre sin
    lote (mismo monto ±$0.01, ±3 días, con el texto);
  - cuando llega un depósito de la empresa sin lote por el total del reporte
    (±$1, en los 90 días después de la aprobación), lo liga.
"""
from datetime import date, timedelta

from . import expense_lotes as _lotes

FOLIOS = (
    # Housekeeping week (aprobado 22/10/2026): $1,999.33. Actividad salud mental
    # ($315 + $60) no aparece en el banco.
    {'nombre': 'Folio 46940 · Housekeeping week',
     'notas': 'Reporte de $1,999.33 (aprobado 22/10/2026); sin cargo en el banco: actividad salud mental $315 + $60',
     'facturas': (('2026-09-28', 420.00, 'MARISA'), ('2026-10-05', 500.00, 'MARISA'), ('2026-09-25', 712.00, 'PLASTIGLOBOS')),
     'deposito': 1999.33, 'aprobado': '2026-10-22'},
)


def aplicar(db) -> dict:
    res = {'lotes': 0, 'facturas': 0, 'depositos': 0}
    for f in FOLIOS:
        fila = db.execute("SELECT id FROM est_expense_lotes WHERE nombre=?", (f['nombre'],)).fetchone()
        lid = fila['id'] if fila else None
        for fecha, monto, texto in f['facturas']:
            d = date.fromisoformat(fecha)
            g = db.execute("""
                SELECT id FROM est_movimientos
                WHERE tipo IN ('GASTO', 'PAGO') AND ABS(ABS(monto)-?) <= 0.01
                  AND substr(fecha,1,10) BETWEEN ? AND ? AND UPPER(descripcion) LIKE ?
                  AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_gastos)
                ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?)), id LIMIT 1""",
                (monto, (d - timedelta(days=3)).isoformat(), (d + timedelta(days=3)).isoformat(),
                 f'%{texto}%', fecha)).fetchone()
            if not g:
                continue
            if lid is None:
                lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                                 (f['nombre'], f['notas'], _lotes.ahora())).lastrowid
                res['lotes'] += 1
            db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='' WHERE id=?", (g['id'],))
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, g['id'], _lotes.ahora()))
            res['facturas'] += 1
        if lid is None:
            continue
        if not db.execute("SELECT 1 FROM est_expense_lote_depositos WHERE lote_id=?", (lid,)).fetchone():
            hasta = (date.fromisoformat(f['aprobado']) + timedelta(days=90)).isoformat()
            dep = next((x for x in _lotes._depositos_sin_lote(db)
                        if abs(x['monto'] - f['deposito']) <= 1 and f['aprobado'] <= x['fecha'] <= hasta), None)
            if dep:
                db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (dep['id'],))
                db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                           (lid, dep['id'], _lotes.ahora()))
                res['depositos'] += 1
        _lotes.sincronizar(db, lid)
    return res
