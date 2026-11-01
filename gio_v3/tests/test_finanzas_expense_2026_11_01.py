"""
test_finanzas_expense_2026_11_01.py — folio 40524 completo con los cargos que
faltaban, el lote «Expense 2026-07-15» (sin depósito, facturas de otros
folios) deshecho, y ningún lote sin depósito deja facturas como Pagado.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import correcciones_expense_2026_11_01 as ce
from modules.finanzas.estados import expense_lotes as L


def _mov(fecha, desc, monto, tipo='GASTO', cat='EXPENSE', sub='', estatus=None):
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo, estatus_reembolso)
                            VALUES (?,?,?,'BBVA_DEB',?,?,?,?)""", (fecha, desc, monto, cat, sub, tipo, estatus)).lastrowid
        db.commit()
        return mid


def _lote(nombre, gastos, deps):
    with database.get_db() as db:
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?, '', 'x')", (nombre,)).lastrowid
        for g in gastos:
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, g))
        for d in deps:
            db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, d))
        db.commit()
        return lid


def _lotes():
    with database.get_db() as db:
        return {l['nombre']: l for l in L.listar(db)}


def test_correcciones(test_db):
    # Folio 40524 como quedó el 2026-09-26: 5 cargos y el depósito.
    g40524 = [_mov('2026-04-28', 'GLOBOS', -379.0), _mov('2026-04-30', 'DESPEDIDA', -420.0),
              _mov('2026-04-29', 'IMPRESIONES', -119.8), _mov('2026-04-28', 'DECORACION', -347.0),
              _mov('2026-05-17', 'PLAZA PANAMERICANA', -334.1)]
    dep = _mov('2026-05-20', 'SITH2 FIDEICOMISO F 1596', 10143.5, 'INGRESO', 'FINANZAS', 'Reembolsable')
    _lote('Folio 40524 · Día del niño y de las madres', g40524, [dep])
    regalos = _mov('2026-05-14', 'LIVERPOOL', -8067.68, cat='COMPRAS')
    pastel = _mov('2026-05-16', 'PASTELERIA', -480.0, cat='COMIDA_FUERA')
    _mov('2026-07-01', 'OTRO PASTEL', -480.0)  # fuera de la ventana: no se toma

    # Folios de destino y el lote mal armado (su depósito ya no existe).
    _lote('Folios 42644 + 42488 · Junio', [], [_mov('2026-07-22', 'FIDEICOMISO', 7163.62, 'INGRESO', 'FINANZAS', 'Reembolsable')])
    _lote('Folio 41143 · AAW', [], [_mov('2026-06-18', 'FIDEICOMISO', 709.0, 'INGRESO', 'FINANZAS', 'Reembolsable'), 888888])
    marisa = _mov('2026-07-08', 'PASTELES MARISA COLON', -235.0, estatus='PAGADO')
    office = _mov('2026-05-22', 'OFFICE DEPOT AMERICAS GUADALAJARA J', -98.9, estatus='PAGADO')
    neufeld = _mov('2026-06-05', 'NEUFELD', -460.0, estatus='PAGADO')
    flor = _mov('2026-04-12', 'FLORERIA MONICA', -250.0, estatus='PAGADO')
    _lote('Expense 2026-07-15', [marisa, office, neufeld, flor], [999999])  # liga huérfana

    with database.get_db() as db:
        r = ce.aplicar(db)
        db.commit()
        assert r == {'folio_40524': 2, 'movidas': 2, 'sueltas': 2, 'borrado': 1, 'ligas_huerfanas': 1}
        est = {m: db.execute("SELECT estatus_reembolso, categoria FROM est_movimientos WHERE id=?", (m,)).fetchone()
               for m in (marisa, office, neufeld, flor, regalos, pastel)}
        assert ce.aplicar(db) == {'folio_40524': 0, 'movidas': 0, 'sueltas': 0, 'borrado': 0, 'ligas_huerfanas': 0}

    lotes = _lotes()
    assert 'Expense 2026-07-15' not in lotes
    f = lotes['Folio 40524 · Día del niño y de las madres']
    assert {g['id'] for g in f['gastos']} == set(g40524) | {regalos, pastel}
    assert est[regalos]['categoria'] == 'EXPENSE' and est[regalos]['estatus_reembolso'] == 'PENDIENTE'  # $4.08 de diferencia (379 vs 374.92)
    assert {g['id'] for g in lotes['Folios 42644 + 42488 · Junio']['gastos']} == {marisa}
    assert {g['id'] for g in lotes['Folio 41143 · AAW']['gastos']} == {office}
    assert est[marisa]['estatus_reembolso'] == 'PAGADO' and est[office]['estatus_reembolso'] == 'PAGADO'
    assert est[neufeld]['estatus_reembolso'] == 'PENDIENTE' and est[flor]['estatus_reembolso'] == 'PENDIENTE'
