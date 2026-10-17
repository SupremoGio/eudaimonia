"""
Lotes de Expense armados a mano con el reporte de gastos (PDF «Travel &
Expense Report») que el usuario pasa para depósitos de la empresa anteriores
al export de la plataforma (data/expense_plataforma.json empieza el 27/03/2024).

Cada lote: el depósito de la empresa y los movimientos del banco que pagaron
sus gastos (id, fecha, monto, texto; si el id no coincide se busca por fecha +
monto + texto). Se crea el lote como en la pestaña Expense: los gastos pasan a
EXPENSE, el depósito a FINANZAS/Reembolsable y el estado se sincroniza. Si el
depósito ya está en un lote o falta algún movimiento, no se toca nada.
"""
from datetime import datetime

from . import expense_lotes as _lotes

LOTES = [
    {
        # Reporte 66A9U410145054 (26/04 – 08/05/2023), $8,029.20: pasteles de
        # festejo (Pastelería Marisa), globos de bienvenida y regalos del Día de
        # las Madres (gargantillas, pagadas por transferencia).
        'nombre': 'Reporte 66A9U410145054 · Pasteles y Día de las Madres',
        'deposito': (3823, '2023-05-25', 8029.20, 'SGLDAC EXPENSE'),
        'gastos': [
            (None, '2023-04-13', 390.00, 'PAST MARISA'),
            (None, '2023-04-26', 365.00, 'PAST MARISA'),
            (None, '2023-05-25', 6882.28, 'BNET BONO X NUESTR'),
            (None, '2023-05-30', 391.92, 'BNET PAGO EXPENSE'),
        ],
    },
]


def _buscar(db, mid, fecha, monto, texto, tipo):
    q = """SELECT id FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01
           AND UPPER(descripcion) LIKE ? AND tipo IN ({})""".format(','.join('?' * len(tipo)))
    if mid:
        r = db.execute(q + " AND id=?", (fecha, monto, f"%{texto}%", *tipo, mid)).fetchone()
        if r:
            return r['id']
    r = db.execute(q + " ORDER BY id LIMIT 1", (fecha, monto, f"%{texto}%", *tipo)).fetchone()
    return r['id'] if r else None


def aplicar(db) -> tuple[int, int]:
    """(lotes creados, lotes que no se pudieron armar). Idempotente."""
    hechos = faltan = 0
    ahora = datetime.now().isoformat(timespec='seconds')
    for lote in LOTES:
        dep = _buscar(db, *lote['deposito'], ('INGRESO',))
        gastos = [_buscar(db, *g, ('GASTO', 'PAGO')) for g in lote['gastos']]
        if not dep or None in gastos:
            faltan += 1
            continue
        if db.execute("SELECT 1 FROM est_expense_lote_depositos WHERE movimiento_id=?", (dep,)).fetchone():
            continue
        if db.execute(f"SELECT 1 FROM est_expense_lote_gastos WHERE movimiento_id IN ({','.join('?' * len(gastos))})",
                      gastos).fetchone():
            faltan += 1
            continue
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (lote['nombre'], 'Armado con el reporte de gastos (PDF) que pasó el usuario', ahora)).lastrowid
        for g in gastos:
            db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='' WHERE id=?", (g,))
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, g, ahora))
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (dep,))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, dep, ahora))
        _lotes.sincronizar(db, lid)
        hechos += 1
    return hechos, faltan
