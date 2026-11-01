"""
Folio 37990 y el lote «Expense 2026-03-25» (el usuario, 2026-11-01, con el PDF
del reporte: «incluye esa flor; no sé por qué el retiro sin tarjeta está en
expense»).

El lote lo creó una sugerencia «aproximada»: depósito de $1,862 del 25/03/2026
contra Florería Florenci $580 (12/03) + Retiro sin tarjeta $1,500 (04/03) =
$2,080. Las tres piezas estaban mal:
  - El folio 37990 («ACTIVIDADES RH», 18/03/2026, $2,299 en una sola línea)
    incluye la florería y lo pagó el depósito de $2,299 del 31/03/2026
    (SITH26623774 FIDEICOMISO F/1596). Lote propio con los dos.
  - El retiro de $1,500 es la colecta de Martha (correcciones_sin_conciliar:
    FAMILIA_REGALOS/Colectas), no un gasto de trabajo: sale del lote y vuelve
    a su categoría (reafirmar_categorias lo había fijado en EXPENSE).
  - El depósito de $1,862 paga dulces de Halloween, papelería del altar,
    pastel de noviembre y dulces de la posada de 2025 (FIJOS de
    expense_plataforma): se suelta y se concilia con esos gastos.

Idempotente: todo se ubica por nombre de lote, fecha y monto.
"""
from . import expense_lotes as _lotes

LOTE_MAL = 'Expense 2026-03-25'
FLOR = ('2026-03-12', 580.00)
RETIRO = ('2026-03-04', 1500.00)
DEP_37990 = ('2026-03-31', 2299.00)
DEP_1862 = ('2026-03-25', 1862.00)
NOMBRE = 'Folio 37990 · Actividades RH'
NOTAS = 'Reporte de $2,299 (ACTIVIDADES RH, 18/03/2026); en el banco solo aparece la florería'


def _mov(db, fm, tipo):
    tipos = ('GASTO', 'PAGO') if tipo == 'GASTO' else ('INGRESO',)
    return db.execute(f"""SELECT id FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto)-?) < 0.01
                          AND tipo IN ({','.join('?' * len(tipos))}) ORDER BY id LIMIT 1""", (*fm, *tipos)).fetchone()


def aplicar(db) -> dict:
    res = {'lote_mal': 0, 'retiro': 0, 'folio_37990': 0, 'dep_1862': 0}
    flor, retiro = _mov(db, FLOR, 'GASTO'), _mov(db, RETIRO, 'GASTO')
    # Solo el de la sugerencia (el que arma conciliar() se llama igual).
    for l in db.execute("SELECT id FROM est_expense_lotes WHERE nombre=? AND COALESCE(notas,'') NOT LIKE 'Plataforma de Expense%'",
                        (LOTE_MAL,)).fetchall():
        lid = l['id']
        db.execute("DELETE FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lote_depositos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lotes WHERE id=?", (lid,))
        res['lote_mal'] += 1
    if retiro and not db.execute("SELECT 1 FROM est_expense_lote_gastos WHERE movimiento_id=?", (retiro['id'],)).fetchone():
        res['retiro'] = db.execute("""UPDATE est_movimientos SET categoria='FAMILIA_REGALOS', subcategoria='Colectas',
                                      estatus_reembolso=NULL, fecha_reembolso=NULL
                                      WHERE id=? AND categoria='EXPENSE'""", (retiro['id'],)).rowcount
    if flor and not db.execute("SELECT 1 FROM est_expense_lote_gastos WHERE movimiento_id=?", (flor['id'],)).fetchone():
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PENDIENTE', fecha_reembolso=NULL "
                   "WHERE id=? AND COALESCE(estatus_reembolso,'') != ?", (flor['id'], _lotes.ESTATUS_TERCERO))
    dep = _mov(db, DEP_37990, 'INGRESO')
    libre = lambda t, mid: not db.execute(f"SELECT 1 FROM {t} WHERE movimiento_id=?", (mid,)).fetchone()
    if not db.execute("SELECT 1 FROM est_expense_lotes WHERE nombre=?", (NOMBRE,)).fetchone() and (
            (flor and libre('est_expense_lote_gastos', flor['id'])) or (dep and libre('est_expense_lote_depositos', dep['id']))):
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (NOMBRE, NOTAS, _lotes.ahora())).lastrowid
        if flor and libre('est_expense_lote_gastos', flor['id']):
            db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='' WHERE id=?", (flor['id'],))
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, flor['id'], _lotes.ahora()))
        if dep and libre('est_expense_lote_depositos', dep['id']) and libre('est_prestamo_devoluciones', dep['id']):
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (dep['id'],))
            db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, dep['id'], _lotes.ahora()))
        _lotes.sincronizar(db, lid)
        res['folio_37990'] = 1
    from .expense_plataforma import conciliar
    res['dep_1862'] = len(conciliar(db, solo=DEP_1862))
    return res
