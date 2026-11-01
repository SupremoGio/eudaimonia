"""
test_finanzas_expense_folios.py — un folio del usuario se arma como lote con
sus facturas aunque no haya depósito, y el depósito se liga solo al llegar.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import expense_folios as F
from modules.finanzas.estados import expense_lotes as L


def _mov(db, fecha, desc, monto, cat='EXPENSE', sub='', tipo='GASTO'):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (?,?,?,'BBVA_TDC',?,?,?)""", (fecha, desc, monto, cat, sub, tipo)).lastrowid


def test_folio_46940(test_db):
    with database.get_db() as db:
        a = _mov(db, '2026-09-28', 'PASTELES MARISA COLON', -420.0)
        b = _mov(db, '2026-10-05', 'PASTELES MARISA COLON', -500.0)
        c = _mov(db, '2026-09-25', 'PLASTIGLOBOS', -712.0, 'COMPRAS')
        _mov(db, '2026-10-27', 'MERPAGO FLORESSUSY', -580.0)          # no es del folio
        assert F.aplicar(db) == {'lotes': 1, 'facturas': 3, 'depositos': 0}
        lote = next(l for l in L.listar(db) if l['nombre'].startswith('Folio 46940'))
        assert {g['id'] for g in lote['gastos']} == {a, b, c} and lote['estado'] == L.PENDIENTE
        assert F.aplicar(db) == {'lotes': 0, 'facturas': 0, 'depositos': 0}
        dep = _mov(db, '2026-11-05', 'SITH2EXPENSERH FIBRA HOTELERA SC', 1999.33, 'FINANZAS', 'Reembolsable', 'INGRESO')
        assert F.aplicar(db)['depositos'] == 1
        lote = next(l for l in L.listar(db) if l['nombre'].startswith('Folio 46940'))
        assert [d['id'] for d in lote['depositos']] == [dep] and lote['estado'] == L.REEMBOLSADO
