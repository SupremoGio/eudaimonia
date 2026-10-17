"""
Compromisos (tabla debts / debt_payments): abonos ligados a su depósito del banco.

Un abono de un compromiso puede ligarse a uno o varios movimientos bancarios
(un abono de $1,700 = dos depósitos de $850). El movimiento ligado queda como
FINANZAS/Reembolso compartido: es la persona pagándote lo que pagaste por
ella, no un ingreso. Cada movimiento se liga a un solo abono.

Sugerencias: cuando entra un depósito de la cuenta de alguien con un
compromiso abierto («me deben»), se propone como abono — no se aplica solo.
La persona del compromiso se reconoce por su contraparte (debts.contraparte o
el nombre/alias de estados/contrapartes.py).
"""
from datetime import datetime

from modules.finanzas.estados import contrapartes as _contra

SUB_COMPARTIDO = 'Reembolso compartido'
SUGERIR_DIAS_ANTES = 120   # el compromiso se suele registrar después de los primeros abonos


def asegurar(db) -> None:
    try:
        db.execute("ALTER TABLE debts ADD COLUMN contraparte TEXT DEFAULT NULL")
    except Exception:
        pass
    db.execute("""CREATE TABLE IF NOT EXISTS debt_payment_movs (
                      payment_id    INTEGER NOT NULL,
                      movimiento_id INTEGER NOT NULL UNIQUE,
                      created_at    TEXT    NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS debt_sugerencias_descartadas (
                      movimiento_id INTEGER PRIMARY KEY,
                      created_at    TEXT    NOT NULL)""")


def contraparte_de(db, d) -> str | None:
    return (d['contraparte'] if 'contraparte' in d.keys() else None) or _contra.de_persona(db, d['person'])


def movs_de_pago(db, pid: int) -> list[dict]:
    return [dict(r) for r in db.execute("""SELECT m.id, substr(m.fecha,1,10) AS fecha, m.descripcion, ABS(m.monto) AS monto
                                           FROM debt_payment_movs l JOIN est_movimientos m ON m.id = l.movimiento_id
                                           WHERE l.payment_id=? ORDER BY m.fecha, m.id""", (pid,)).fetchall()]


def ligar(db, payment_id: int, movimiento_id: int) -> None:
    """Liga un abono a un movimiento bancario (INGRESO). ValueError si no se puede."""
    m = db.execute("SELECT id, tipo FROM est_movimientos WHERE id=?", (movimiento_id,)).fetchone()
    if not m:
        raise ValueError(f'No existe el movimiento {movimiento_id}.')
    if m['tipo'] != 'INGRESO':
        raise ValueError(f'El movimiento {movimiento_id} no es un depósito.')
    otro = db.execute("SELECT payment_id FROM debt_payment_movs WHERE movimiento_id=?", (movimiento_id,)).fetchone()
    if otro and otro['payment_id'] != payment_id:
        raise ValueError(f'El movimiento {movimiento_id} ya está ligado a otro abono.')
    if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (movimiento_id,)).fetchone():
        raise ValueError(f'El movimiento {movimiento_id} es la devolución de un préstamo.')
    db.execute("INSERT OR IGNORE INTO debt_payment_movs (payment_id, movimiento_id, created_at) VALUES (?,?,?)",
               (payment_id, movimiento_id, datetime.now().isoformat(timespec='seconds')))
    db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=? WHERE id=?", (SUB_COMPARTIDO, movimiento_id))


def desligar(db, movimiento_id: int) -> None:
    """Quita el vínculo; el depósito vuelve a Sin conciliar."""
    if db.execute("DELETE FROM debt_payment_movs WHERE movimiento_id=?", (movimiento_id,)).rowcount:
        db.execute("""UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Transferencia recibida'
                      WHERE id=? AND categoria='FINANZAS' AND subcategoria=?""", (movimiento_id, SUB_COMPARTIDO))


def abiertos(db) -> list[dict]:
    """Compromisos «me deben» abiertos con su contraparte."""
    out = []
    for d in db.execute("SELECT * FROM debts WHERE type='owe_me' AND settled=0 ORDER BY created_at").fetchall():
        out.append({**dict(d), 'contraparte': contraparte_de(db, d)})
    return out


def sugerencias(db) -> list[dict]:
    """Depósitos de un deudor con compromiso abierto que todavía no son abono
    de nada (ni devolución de préstamo, ni depósito de Expense)."""
    out = []
    for d in abiertos(db):
        if not d['contraparte'] or (d['monto_restante'] or 0) <= 0:
            continue
        rows = db.execute("""
            SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, categoria, subcategoria
            FROM est_movimientos
            WHERE tipo='INGRESO' AND contraparte=? AND ABS(monto) <= ? + 0.01
              AND substr(fecha,1,10) >= date(substr(?,1,10), ?)
              AND id NOT IN (SELECT movimiento_id FROM debt_payment_movs)
              AND id NOT IN (SELECT movimiento_id FROM debt_sugerencias_descartadas)
              AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
              AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
              AND (categoria IN ('', 'OTROS') OR categoria IS NULL
                   OR (categoria='FINANZAS' AND COALESCE(subcategoria,'') IN ('', 'Transferencia', 'Transferencia recibida', ?)))
            ORDER BY fecha DESC, id DESC""",
            (d['contraparte'], d['monto_restante'], d['created_at'], f'-{SUGERIR_DIAS_ANTES} days', SUB_COMPARTIDO)).fetchall()
        for m in rows:
            out.append({'debt_id': d['id'], 'person': d['person'], 'concept': d['concept'],
                        'monto_restante': d['monto_restante'], 'movimiento': dict(m)})
    return out


def descartar(db, movimiento_id: int) -> None:
    """«No es abono»: no se vuelve a sugerir."""
    db.execute("INSERT OR IGNORE INTO debt_sugerencias_descartadas (movimiento_id, created_at) VALUES (?,?)",
               (movimiento_id, datetime.now().isoformat(timespec='seconds')))
