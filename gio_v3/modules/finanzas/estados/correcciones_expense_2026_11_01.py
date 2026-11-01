"""
Correcciones de Expense del 2026-11-01 (el usuario pasó el reporte del folio
40524 y la captura del lote «Expense 2026-07-15», que estaba en «Esperando
pago» con sus 4 facturas como Pagado y $0 recibido).

1. Folio 40524 (Día del niño y de las madres, 7 gastos, $10,143.50 pagados con
   el depósito del 20/05/2026). Cuando se armó el lote (2026-09-26) faltaban
   los regalos del Día de las Madres ($8,067.68) y el pastel de cumpleañeros
   de mayo ($480) porque no aparecían en las tarjetas. Cada línea del reporte
   que el lote todavía no tiene se busca entre los cargos sin lote (mismo
   monto, de 7 días antes a 15 días después) y se agrega.

2. El lote «Expense 2026-07-15» se quedó sin depósito y mezclaba facturas de
   otros folios ya pagados: Pasteles Marisa $235 (08/07) es «Amenidad
   aniversarios» de los folios 42644 + 42488 y Office Depot $98.90 (22/05) es
   «Actividad AAW» del folio 41143. Se mueven a su lote; las demás quedan
   sueltas (Pendiente) para armarlas a mano, y el lote vacío se borra.

3. Ligas a movimientos que ya no existen (un depósito borrado como duplicado
   dejaba el lote con $0 recibido) se limpian, y todos los lotes vuelven a
   reflejar su estado en las facturas: un lote sin depósito ya no deja sus
   facturas como Pagado.

Todo se identifica por nombre de lote + fecha + monto y es idempotente.
"""
from datetime import date, timedelta

from . import expense_lotes as _lotes

FOLIO_40524 = 'Folio 40524'
DEPOSITO_40524 = ('2026-05-20', 10143.50)
REPORTE_40524 = (  # (fecha, título, monto MXN) del reporte
    ('2026-04-28', 'GLOBOS DECORACION DIA DEL NINO', 374.92),
    ('2026-04-30', 'DESPEDIDA PRACTICANTES', 420.00),
    ('2026-05-05', 'IMPRESIONES DIA DEL NIÑO', 119.80),
    ('2026-05-07', 'DECORACION DIA DEL NINO', 347.00),
    ('2026-05-13', 'REGALOS DIAS DE LAS MADRES', 8067.68),
    ('2026-05-15', 'ACTIVIDAD AAW', 334.10),
    ('2026-05-15', 'PASTEL CUMPLEANEROS MAYO', 480.00),
)
# Un cargo ya en el lote cuenta como esa línea si difiere hasta $5 (el de los
# globos se ligó con un cargo de $379 contra $374.92 del reporte).
TOL_LINEA = 5.0
DIAS_ANTES, DIAS_DESPUES = 7, 15

LOTE_MAL = 'Expense 2026-07-15'
# (fecha, monto, texto en la descripción) -> prefijo del lote al que pertenece
MOVER = (
    ('2026-07-08', 235.00, 'MARISA', 'Folios 42644'),
    ('2026-05-22', 98.90, 'OFFICE DEPOT', 'Folio 41143'),
)


def _lote(db, prefijo):
    return db.execute("SELECT id FROM est_expense_lotes WHERE nombre LIKE ? ORDER BY id LIMIT 1",
                      (prefijo + '%',)).fetchone()


def _ligar_gasto(db, lid, mid):
    db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='' WHERE id=?", (mid,))
    db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
               (lid, mid, _lotes.ahora()))


def completar_folio_40524(db) -> int:
    lote = _lote(db, FOLIO_40524)
    if lote:
        lid = lote['id']
    else:
        f, m = DEPOSITO_40524
        dep = db.execute("""SELECT id FROM est_movimientos WHERE tipo='INGRESO' AND substr(fecha,1,10)=?
                              AND ABS(ABS(monto)-?) < 0.01
                              AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)""",
                         (f, m)).fetchone()
        if not dep:
            return 0
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         ('Folio 40524 · Día del niño y de las madres', '', _lotes.ahora())).lastrowid
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (dep['id'],))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, dep['id'], _lotes.ahora()))
    # Qué líneas del reporte ya cubre el lote (cada cargo cubre a lo más una).
    libres = [abs(float(r['monto'])) for r in db.execute("""
        SELECT m.monto FROM est_expense_lote_gastos g JOIN est_movimientos m ON m.id = g.movimiento_id
        WHERE g.lote_id=?""", (lid,)).fetchall()]
    faltan = []
    for linea in sorted(REPORTE_40524, key=lambda x: -x[2]):
        hit = min((x for x in libres if abs(x - linea[2]) <= TOL_LINEA), key=lambda x: abs(x - linea[2]), default=None)
        if hit is None:
            faltan.append(linea)
        else:
            libres.remove(hit)
    n = 0
    for f, _, monto in faltan:
        d = date.fromisoformat(f)
        c = db.execute("""
            SELECT id FROM est_movimientos
            WHERE tipo IN ('GASTO', 'PAGO') AND ABS(ABS(monto)-?) <= 0.01
              AND substr(fecha,1,10) BETWEEN ? AND ?
              AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_gastos)
              AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
            ORDER BY CASE WHEN categoria='EXPENSE' THEN 0 ELSE 1 END,
                     ABS(julianday(substr(fecha,1,10)) - julianday(?)), id
            LIMIT 1""", (monto, (d - timedelta(days=DIAS_ANTES)).isoformat(),
                         (d + timedelta(days=DIAS_DESPUES)).isoformat(), f)).fetchone()
        if c:
            _ligar_gasto(db, lid, c['id'])
            n += 1
    return n


def deshacer_lote_mal(db) -> dict:
    res = {'movidas': 0, 'sueltas': 0, 'borrado': 0}
    for lote in db.execute("SELECT id FROM est_expense_lotes WHERE nombre=?", (LOTE_MAL,)).fetchall():
        lid = lote['id']
        if db.execute("""SELECT 1 FROM est_expense_lote_depositos d JOIN est_movimientos m ON m.id = d.movimiento_id
                         WHERE d.lote_id=?""", (lid,)).fetchone():
            continue  # tiene depósito: no es el lote de la captura
        for g in db.execute("""SELECT m.id, substr(m.fecha,1,10) AS fecha, ABS(m.monto) AS monto, m.descripcion
                               FROM est_expense_lote_gastos g JOIN est_movimientos m ON m.id = g.movimiento_id
                               WHERE g.lote_id=?""", (lid,)).fetchall():
            destino = next((p for f, m, txt, p in MOVER
                            if g['fecha'] == f and abs(g['monto'] - m) < 0.01 and txt in (g['descripcion'] or '').upper()),
                           None)
            dest = _lote(db, destino) if destino else None
            if dest:
                db.execute("UPDATE est_expense_lote_gastos SET lote_id=? WHERE movimiento_id=?", (dest['id'], g['id']))
                res['movidas'] += 1
            else:
                db.execute("DELETE FROM est_expense_lote_gastos WHERE movimiento_id=?", (g['id'],))
                db.execute("""UPDATE est_movimientos SET estatus_reembolso='PENDIENTE', fecha_reembolso=NULL
                              WHERE id=? AND COALESCE(estatus_reembolso,'') != ?""", (g['id'], _lotes.ESTATUS_TERCERO))
                res['sueltas'] += 1
        if not db.execute("SELECT 1 FROM est_expense_lote_gastos WHERE lote_id=?", (lid,)).fetchone():
            db.execute("DELETE FROM est_expense_lote_depositos WHERE lote_id=?", (lid,))
            db.execute("DELETE FROM est_expense_lotes WHERE id=?", (lid,))
            res['borrado'] += 1
    return res


def limpiar_y_sincronizar(db) -> int:
    n = 0
    for t in ('est_expense_lote_gastos', 'est_expense_lote_depositos'):
        n += db.execute(f"DELETE FROM {t} WHERE movimiento_id NOT IN (SELECT id FROM est_movimientos)").rowcount
    for r in db.execute("SELECT id FROM est_expense_lotes").fetchall():
        _lotes.sincronizar(db, r['id'])
    return n


def aplicar(db) -> dict:
    res = {'folio_40524': completar_folio_40524(db)}
    res.update(deshacer_lote_mal(db))
    res['ligas_huerfanas'] = limpiar_y_sincronizar(db)
    return res
