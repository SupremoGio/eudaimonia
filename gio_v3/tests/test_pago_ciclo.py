"""
test_pago_ciclo.py — Sprint 2 de Oikonomia v2: el pago del ciclo de una
tarjeta se puede marcar desde el hub (POST/DELETE /finanzas/api/pago-ciclo) o
se detecta solo cuando el estado de cuenta trae su PAGO_TDC. Lo pagado sale
de los avisos, de los mínimos a 30 días y del «siguiente paso».
"""
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas import pagos_ciclo as pc
from modules.finanzas import routes as fr

BBVA = {'match': 'bbva', 'day': 15, 'label': 'BBVA TDC'}
HSBC = {'match': 'hsbc', 'day': 30, 'label': 'HSBC'}


def test_ciclo_es_el_mes_del_proximo_pago():
    assert pc.ciclo(BBVA, date(2026, 10, 10))[:2] == ('2026-10', date(2026, 10, 15))
    assert pc.ciclo(BBVA, date(2026, 10, 15))[0] == '2026-10'          # hoy se paga: ciclo de este mes
    assert pc.ciclo(BBVA, date(2026, 10, 16))[:2] == ('2026-11', date(2026, 11, 15))
    assert pc.ciclo(BBVA, date(2026, 12, 20))[0] == '2027-01'
    assert pc.ciclo(HSBC, date(2027, 2, 10))[1] == date(2027, 2, 28)   # día 30 en febrero
    assert pc.ciclo(BBVA, date(2026, 10, 10))[2] == date(2026, 9, 15)  # pago anterior


@pytest.fixture
def hoy(monkeypatch):
    d = date(2026, 10, 15)
    monkeypatch.setattr(pc, 'today_date', lambda: d)
    monkeypatch.setattr(fr, 'today_date', lambda: d)
    import modules.actividades.routes as ar
    monkeypatch.setattr(ar, 'today_date', lambda: d)
    return d


@pytest.fixture
def client(test_db, hoy):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
            s['fin_ok'] = True
        yield c


def _filas():
    with database.get_db() as db:
        return [dict(r) for r in db.execute("SELECT cuenta, ciclo, origen, monto, movimiento_id FROM fin_pagos_ciclo")]


def test_marcar_y_deshacer(client):
    r = client.post('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva', 'monto': 1250})
    assert r.get_json()['ok'] and r.get_json()['pago']['ciclo'] == '2026-10'
    assert _filas() == [{'cuenta': 'bbva', 'ciclo': '2026-10', 'origen': 'manual', 'monto': 1250.0, 'movimiento_id': None}]
    # Marcar otra vez no duplica (UNIQUE)
    assert client.post('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'}).get_json()['ok']
    assert len(_filas()) == 1
    assert client.delete('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'}).get_json() == {'ok': True, 'quitado': True}
    assert _filas() == []


def test_cuenta_desconocida_y_sin_sesion(client):
    assert client.post('/finanzas/api/pago-ciclo', json={'cuenta': 'nu'}).status_code == 400
    with client.session_transaction() as s:
        s['fin_ok'] = False
    assert client.post('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'}).status_code == 403


def _pago_tdc(fecha, monto=5000.0, banco='BBVA_TDC', desc='PAGO TARJETA DE CREDITO'):
    with database.get_db() as db:
        mid = db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo) "
                         "VALUES (?,?,?,?, 'PAGO_TDC', 'MOVIMIENTO_INTERNO')", (fecha, desc, -monto, banco)).lastrowid
        db.commit()
    return mid


def test_detecta_pago_en_el_estado_de_cuenta(test_db, hoy):
    _pago_tdc('2026-09-10')                       # pago del ciclo anterior: no cuenta
    with database.get_db() as db:
        assert pc.detectar(db) == 0
    mid = _pago_tdc('2026-10-12', 4200.0)
    _pago_tdc('2026-10-13', 900.0, banco='BBVA_DEB', desc='SPEI ENVIADO INVEX')   # otra tarjeta
    with database.get_db() as db:
        assert pc.detectar(db) == 2
        db.commit()
        assert pc.detectar(db) == 0               # idempotente
    by = {f['cuenta']: f for f in _filas()}
    assert by['bbva']['origen'] == 'estado' and by['bbva']['movimiento_id'] == mid and by['bbva']['monto'] == 4200.0
    assert by['invex']['ciclo'] == '2026-10'


def test_pago_del_estado_no_se_desmarca(client):
    _pago_tdc('2026-10-12')
    with database.get_db() as db:
        pc.detectar(db)
        db.commit()
    r = client.delete('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'})
    assert r.status_code == 400 and 'estado de cuenta' in r.get_json()['error']


def test_lo_pagado_sale_de_avisos_minimos_y_siguiente_paso(client):
    assert {a['label'] for a in fr.payment_alerts()} == {'BBVA TDC', 'Invex'}   # hoy es 15
    client.post('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'})
    assert {a['label'] for a in fr.payment_alerts()} == {'Invex'}
    from modules.actividades.routes import get_payment_alerts
    assert [a['label'] for a in get_payment_alerts()] == ['Invex']

    debts = fr._hub_debts([{'nombre': 'BBVA Oro', 'institucion': 'BBVA', 'saldo': 18000.0, 'tipo': 'tarjeta_credito', 'moneda': 'MXN'},
                           {'nombre': 'Invex', 'institucion': 'INVEX', 'saldo': 6000.0, 'tipo': 'tarjeta_credito', 'moneda': 'MXN'}])
    by = {d['nombre']: d for d in debts}
    assert by['BBVA Oro']['pagado'] and by['BBVA Oro']['tone'] == 'success' and not by['Invex']['pagado']
    s = fr._hub_next_step(debts, 0, 0)
    assert s['title'] == 'Pagar Invex'
