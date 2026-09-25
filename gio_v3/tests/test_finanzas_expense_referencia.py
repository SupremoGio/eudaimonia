"""
test_finanzas_expense_referencia.py — EXPENSE (gasto de trabajo reembolsable)
queda fuera de «Total gastado» y se reporta aparte como referencia; los
«PAGO CUENTA DE TERCERO…» en EXPENSE (lo que el usuario le transfiere al
compañero que pagó el gasto) quedan con estatus TERCERO y el resto, que ya se
reembolsó, como PAGADO.
"""
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados import routes as er

HOY = datetime.now().strftime("%Y-%m-%d")


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _mov(desc, monto, categoria='EXPENSE', subcategoria='', tipo='GASTO', estatus=None, fecha=HOY):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos
                            (fecha, descripcion, monto, tipo, categoria, subcategoria, banco, estatus_reembolso)
                            VALUES (?, ?, ?, ?, ?, ?, 'BBVA_DEB', ?)""",
                         (fecha, desc, monto, tipo, categoria, subcategoria, estatus)).lastrowid
        db.commit()
        return rid


def _estatus(rid):
    with database.get_db() as db:
        return db.execute("SELECT estatus_reembolso FROM est_movimientos WHERE id=?", (rid,)).fetchone()[0]


def test_expense_no_suma_en_total_gastado(client):
    _mov('COMIDA', -300.0, 'COMIDA_FUERA', 'Restaurante')
    _mov('HOTEL CLIENTE', -2000.0)                                 # EXPENSE
    stats = client.get('/finanzas/estados/api/summary/stats').get_json()
    assert stats['total_expense'] == -300.0
    ov = client.get('/finanzas/estados/api/summary/overview').get_json()
    assert ov['expense'] == -300.0
    cats = {c['categoria'] for c in client.get('/finanzas/estados/api/summary/by-category?tipo=GASTO').get_json()}
    assert 'EXPENSE' not in cats
    # Sigue visible al filtrar Movimientos por la categoría
    lst = client.get('/finanzas/estados/api/transactions?category=EXPENSE').get_json()
    assert len(lst['data']) == 1


def test_terceros_y_pagados(test_db):
    terceros = [_mov('PAGO CUENTA DE TERCERO BNET PASTEL AC MARRIOTT', -3950.0),
                _mov('EXPENSE PAGO CUENTA DE TERCERO BNET', -560.0, estatus='PENDIENTE')]
    mios = [_mov('HOTEL CLIENTE', -2000.0), _mov('UBER AEROPUERTO', -350.0, estatus='PENDIENTE')]
    ya_pagado = _mov('CENA CLIENTE', -800.0, estatus='PAGADO')
    regalo = _mov('PAGO CUENTA DE TERCERO BNET REGALO', -500.0, 'FAMILIA_REGALOS', 'Regalos')
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_expense_terceros_pagados'")
        db.commit()
    database.init_db()
    assert [_estatus(r) for r in terceros] == ['TERCERO', 'TERCERO']
    assert [_estatus(r) for r in mios] == ['PAGADO', 'PAGADO']
    assert _estatus(ya_pagado) == 'PAGADO'
    assert _estatus(regalo) is None
    # Un EXPENSE nuevo pendiente no lo toca el blindaje (solo los de tercero)
    nuevo = _mov('TAXI CLIENTE', -120.0, estatus='PENDIENTE')
    nuevo_t = _mov('PAGO CUENTA DE TERCERO BNET EXPENSE OCT', -900.0, estatus='PENDIENTE')
    with database.get_db() as db:
        assert er._corregir_expense_terceros(db) == 1
        db.commit()
    assert _estatus(nuevo) == 'PENDIENTE' and _estatus(nuevo_t) == 'TERCERO'


def test_referencia_en_pendientes(client):
    _mov('PAGO CUENTA DE TERCERO BNET PASTEL', -632.0, estatus='TERCERO')
    _mov('HOTEL CLIENTE', -2000.0, estatus='PAGADO')
    _mov('TAXI CLIENTE', -150.0, estatus='PENDIENTE')
    _mov('REEMBOLSO EMPRESA', 2150.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
    _mov('HOTEL VIEJO', -999.0, estatus='PAGADO', fecha='2020-01-10')     # otro año
    ref = client.get('/finanzas/estados/api/summary/pendientes').get_json()['expense_ref']
    assert ref['n'] == 3
    assert ref['total'] == 2782.0
    assert ref['terceros'] == 632.0
    assert ref['mio'] == 2150.0
    assert ref['pendiente'] == 150.0
