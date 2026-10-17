"""
test_finanzas_expense_lotes_manuales.py — lote de Expense armado con el
reporte PDF de $8,029.20 (mayo 2023).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import expense_lotes_manuales as elm


def test_lote_8029(test_db):
    with database.get_db() as db:
        ins = lambda f, d, m, c, s, t: db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                                                     VALUES (?,?,?, 'BBVA_DEB', ?,?,?)""", (f, d, m, c, s, t)).lastrowid
        dep = ins('2023-05-25', 'DEPOSITO DE TERCERO SGLDAC EXPENSE GIOVANY', 8029.20, 'OTROS', '', 'INGRESO')
        g = [ins('2023-04-13', 'PAST MARISA ITALIA PRO', 390, 'COMIDA_FUERA', 'Restaurante', 'GASTO'),
             ins('2023-04-26', 'PAST MARISA ITALIA PRO', 365, 'COMIDA_FUERA', 'Restaurante', 'GASTO'),
             ins('2023-05-25', 'PAGO CUENTA DE TERCERO BNET BONO X NUESTR 1 CI', 6882.28, 'FINANZAS', 'Transferencia', 'GASTO'),
             ins('2023-05-30', 'PAGO CUENTA DE TERCERO BNET PAGO EXPENSE', 391.92, 'FINANZAS', 'Transferencia', 'GASTO')]
        db.commit()
        assert elm.aplicar(db) == (1, len(elm.LOTES) - 1)
        assert elm.aplicar(db)[0] == 0                              # idempotente
        lid = db.execute("SELECT lote_id FROM est_expense_lote_depositos WHERE movimiento_id=?", (dep,)).fetchone()[0]
        assert {r[0] for r in db.execute("SELECT movimiento_id FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))} == set(g)
        assert {r[0] for r in db.execute(f"SELECT categoria FROM est_movimientos WHERE id IN ({','.join('?'*4)})", g)} == {'EXPENSE'}
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (dep,)).fetchone()) == ('FINANZAS', 'Reembolsable')
