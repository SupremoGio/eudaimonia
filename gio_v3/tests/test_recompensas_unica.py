"""
test_recompensas_unica.py — recompensas de una sola vez (Kindle, Apple Watch):
una vez canjeadas quedan como «Conseguida» y no vuelven a estar disponibles
cuando vence el cooldown; las periódicas siguen con su cooldown.
"""
import sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.recompensas import routes as rw


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
    return c


def _r(**kw):
    base = {'ec_cost': 10, 'level_required': 1, 'weekend_only': 0, 'cooldown_days': 90,
            'last_redeemed': None, 'badge_required': '', 'unica': 0}
    base.update(kw)
    return base


def test_unica_canjeada_ya_no_vuelve_aunque_pase_el_cooldown():
    hace_un_anio = (datetime.now() - timedelta(days=365)).isoformat()
    ok, why = rw._can_redeem(_r(unica=1, last_redeemed=hace_un_anio), 10 ** 6, 10)
    assert not ok and why == 'Ya la conseguiste'
    r = _r(unica=1, last_redeemed=hace_un_anio, can_redeem=False)
    assert rw._reward_status(r, 10 ** 6, 10) == 'done'


def test_periodica_vuelve_al_vencer_el_cooldown():
    hace_un_anio = (datetime.now() - timedelta(days=365)).isoformat()
    assert rw._can_redeem(_r(last_redeemed=hace_un_anio), 10 ** 6, 10)[0]


@pytest.mark.parametrize('nombre,unica', [('Kindle', True), ('Apple Watch', True), ('Ropa Nike', False),
                                          ('Viaje', False), ('Cápsula Nespresso', False), ('Libro técnico', False)])
def test_sugerencia_por_nombre(nombre, unica):
    assert rw.es_unica_por_nombre(nombre) is unica


def test_migracion_marca_kindle_y_watch_como_unicas(test_db):
    with database.get_db() as db:
        got = {r['name']: r['unica'] for r in db.execute("SELECT name, unica FROM rewards")}
    assert got['Kindle'] == 1 and got['Apple Watch'] == 1 and got['Ropa Nike'] == 0


def test_migracion_no_pisa_lo_que_el_usuario_cambio(test_db):
    with database.get_db() as db:
        db.execute("UPDATE rewards SET unica=0 WHERE name='Kindle'")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        assert db.execute("SELECT unica FROM rewards WHERE name='Kindle'").fetchone()['unica'] == 0


def test_canje_de_unica_la_mueve_a_conseguidas(client):
    with database.get_db() as db:
        db.execute("INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at) VALUES (1000,'t','t',1,'2026-09-01','x')")
        rid = db.execute("INSERT INTO rewards (name, ec_cost, level_required, cooldown_days, unica, created_at) VALUES ('Kindle Paperwhite',10,1,0,1,'x')").lastrowid
        db.commit()
    assert client.post(f'/recompensas/api/rewards/{rid}/redeem').get_json()['redeemed']
    assert client.post(f'/recompensas/api/rewards/{rid}/redeem').status_code == 400
    html = client.get('/recompensas/').get_data(as_text=True)
    assert 'data-filter="done">Conseguidas' in html and 'Conseguida el' in html


def test_editar_permite_cambiar_unica(client):
    with database.get_db() as db:
        rid = db.execute("SELECT id FROM rewards WHERE name='Kindle'").fetchone()['id']
    assert client.put(f'/recompensas/api/rewards/{rid}', json={'unica': False}).get_json()['unica'] == 0


def test_apple_watch_desbloqueado(test_db):
    with database.get_db() as db:
        r = db.execute("SELECT level_required, badge_required, ec_cost FROM rewards WHERE name='Apple Watch'").fetchone()
    assert r['level_required'] == 1 and r['badge_required'] == '' and r['ec_cost'] == 300
