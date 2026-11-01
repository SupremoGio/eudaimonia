"""
test_finanzas_expense_folio_37990.py — el lote «Expense 2026-03-25» (sugerencia
aproximada) se deshace: la florería va al folio 37990 con el depósito de
$2,299, el retiro vuelve a la colecta y el depósito de $1,862 se concilia con
sus gastos de la plataforma.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import correcciones_expense_37990 as ce
from modules.finanzas.estados import expense_lotes as L


def _mov(fecha, desc, monto, tipo='GASTO', cat='EXPENSE', sub='', estatus=None):
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo, estatus_reembolso)
                            VALUES (?,?,?,'BBVA_DEB',?,?,?,?)""", (fecha, desc, monto, cat, sub, tipo, estatus)).lastrowid
        db.commit()
        return mid


def test_folio_37990(test_db):
    flor = _mov('2026-03-12', 'GASD700322H67 FLORERIA FLORENCI GPRS GUA', -580.0, estatus='PENDIENTE')
    retiro = _mov('2026-03-04', 'RETIRO SIN TARJETA', -1500.0, estatus='PENDIENTE')
    dep1862 = _mov('2026-03-25', 'SITH2EXPENSERH FIBRA HOTELERA SC', 1862.0, 'INGRESO', 'FINANZAS', 'Reembolsable')
    dep2299 = _mov('2026-03-31', 'SITH26623774 FIDEICOMISO F/1596', 2299.0, 'INGRESO', 'FINANZAS', 'Reembolsable')
    # Gastos del reporte que paga el de $1,862 (FIJOS de expense_plataforma).
    hall = _mov('2025-10-21', 'DULCERIA', -214.0, cat='COMIDA_FUERA')
    with database.get_db() as db:
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES ('Expense 2026-03-25', 'Sugerido automáticamente', 'x')").lastrowid
        for g in (flor, retiro):
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, g))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, dep1862))
        db.commit()

        r = ce.aplicar(db)
        db.commit()
        assert r == {'lote_mal': 1, 'retiro': 1, 'folio_37990': 1, 'dep_1862': 1}
        assert ce.aplicar(db) == {'lote_mal': 0, 'retiro': 0, 'folio_37990': 0, 'dep_1862': 0}
        lotes = {l['nombre']: l for l in L.listar(db)}
        ret = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (retiro,)).fetchone()
        st_flor = db.execute("SELECT estatus_reembolso FROM est_movimientos WHERE id=?", (flor,)).fetchone()[0]

    # El nombre se reusa para el lote bueno del depósito de $1,862 (sin florería ni retiro).
    assert lotes['Expense 2026-03-25']['notas'].startswith('Plataforma de Expense')
    assert not {flor, retiro} & {g['id'] for g in lotes['Expense 2026-03-25']['gastos']}
    f = lotes['Folio 37990 · Actividades RH']
    assert [g['id'] for g in f['gastos']] == [flor] and [d['id'] for d in f['depositos']] == [dep2299]
    assert f['estado'] == 'Reembolsado' and st_flor == 'PAGADO'
    assert tuple(ret) == ('FAMILIA_REGALOS', 'Colectas')
    nuevo = next(l for l in lotes.values() if [d['id'] for d in l['depositos']] == [dep1862])
    assert hall in [g['id'] for g in nuevo['gastos']]
