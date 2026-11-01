"""
test_finanzas_expense_cierre_2025.py — el histórico de Expense ≤2025 se cierra
como pagado sin conciliar: no suma a por cobrar, no sale en sugerencias ni
sueltos, no cambia categorías y 2026 sigue igual.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import expense_cierre_historico as C
from modules.finanzas.estados import expense_lotes as L


def _mov(db, fecha, desc, monto, cat='EXPENSE', sub='', tipo='GASTO', est=None):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo, estatus_reembolso)
                         VALUES (?,?,?,'BBVA_DEB',?,?,?,?)""", (fecha, desc, monto, cat, sub, tipo, est)).lastrowid


def _lote(db, nombre, gastos, deps):
    lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?, '', 'x')", (nombre,)).lastrowid
    for g in gastos:
        db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, g))
    for d in deps:
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, d))
    return lid


def test_cierre_historico(test_db):
    with database.get_db() as db:
        s24 = _mov(db, '2024-05-01', 'COMIDA 2024', -300.0)
        s25 = _mov(db, '2025-08-01', 'UBER 2025', -150.0)
        terc = _mov(db, '2025-09-01', 'PAGO COMPAÑERO', -80.0, est='TERCERO')
        d25 = _mov(db, '2025-10-01', 'SITH2 FIDEICOMISO F 1596', 999.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        s26 = _mov(db, '2026-02-01', 'TAXI 2026', -200.0)
        d26 = _mov(db, '2026-03-01', 'SITH2 FIDEICOMISO F 1596', 777.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        # Lote abierto viejo (se cierra) y uno con depósito de 2026 (no se toca).
        g_viejo = _mov(db, '2025-03-01', 'HOTEL', -1000.0, est='PENDIENTE')
        viejo = _lote(db, 'Viejo', [g_viejo], [])
        g_mixto = _mov(db, '2025-12-01', 'POSADA', -500.0)
        mixto = _lote(db, 'Mixto', [g_mixto], [_mov(db, '2026-01-07', 'SITH2 FIDEICOMISO', 400.0, 'FINANZAS', 'Reembolsable', 'INGRESO')])
        db.commit()
        cats_antes = db.execute("SELECT id, categoria, subcategoria FROM est_movimientos ORDER BY id").fetchall()

        r = C.aplicar(db)
        db.commit()
        assert r == {'lotes_cerrados': 1, 'lotes_historicos': 2, 'facturas': 3, 'depositos': 1}
        assert C.aplicar(db) == {'lotes_cerrados': 0, 'lotes_historicos': 0, 'facturas': 0, 'depositos': 0}
        assert [tuple(x) for x in db.execute("SELECT id, categoria, subcategoria FROM est_movimientos ORDER BY id")] \
            == [tuple(x) for x in cats_antes]

        lotes = {l['nombre']: l for l in L.listar(db)}
        st = lambda m: db.execute("SELECT estatus_reembolso FROM est_movimientos WHERE id=?", (m,)).fetchone()[0]
        assert lotes['Viejo']['estado'] == L.CERRADO and st(g_viejo) == 'PAGADO'
        assert lotes['Mixto']['estado'] == L.PARCIAL
        h25 = lotes['Histórico 2025 · cerrado sin conciliar']
        assert {g['id'] for g in h25['gastos']} == {s25, terc} and [d['id'] for d in h25['depositos']] == [d25]
        assert [g['id'] for g in lotes['Histórico 2024 · cerrado sin conciliar']['gastos']] == [s24]
        assert st(s24) == 'PAGADO' and st(s25) == 'PAGADO' and st(terc) == 'TERCERO'

        res = L.resumen(db)
        assert res['por_cobrar'] == 100.0 + 200.0          # pendiente del lote mixto + la factura de 2026
        assert [g['id'] for g in res['sin_lote']] == [s26]
        su = L.sueltos(db)
        assert [d['id'] for d in su['depositos']] == [d26] and [f['id'] for f in su['facturas']] == [s26]
