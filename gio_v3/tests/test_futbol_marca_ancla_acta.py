"""
test_futbol_marca_ancla_acta.py — al registrar el resultado de un partido
(estado 'jugado') en día de partido, el ancla «Partido de fútbol» del Acta
Diurna queda tachada sola, sin tener que marcarla a mano.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database

MIERCOLES, JUEVES = '2026-09-23', '2026-09-24'
BASE = '/bienestar/futbol/api/partidos'


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
        yield c


def _logs(fecha):
    with database.get_db() as db:
        return db.execute("SELECT id FROM activity_logs WHERE activity_key='partido_futbol' AND date=?",
                          (fecha,)).fetchall()


def _programar(client, fecha):
    r = client.post(BASE, json={'fecha': fecha, 'hora': '21:00', 'rival': 'Dany', 'estado': 'programado'})
    return r.get_json()['id']


def test_programado_no_tacha_el_ancla(client):
    _programar(client, MIERCOLES)
    assert _logs(MIERCOLES) == []


def test_registrar_resultado_tacha_el_ancla_una_sola_vez(client):
    pid = _programar(client, MIERCOLES)
    res = {'estado': 'jugado', 'goles_favor': 4, 'goles_contra': 4, 'rendimiento': 4}
    assert client.patch(f'{BASE}/{pid}', json=res).get_json()['ok']
    assert len(_logs(MIERCOLES)) == 1
    # Editar el partido ya jugado no vuelve a tachar ni duplica XP
    assert client.patch(f'{BASE}/{pid}', json={**res, 'minutos_jugados': 25}).get_json()['ok']
    assert len(_logs(MIERCOLES)) == 1
    with database.get_db() as db:
        n = db.execute("SELECT COUNT(*) c FROM xp_ledger WHERE description='Actividad: partido_futbol'").fetchone()['c']
    assert n == 1


def test_crear_partido_ya_jugado_tacha_el_ancla(client):
    client.post(BASE, json={'fecha': MIERCOLES, 'estado': 'jugado', 'goles_favor': 2, 'goles_contra': 1})
    assert len(_logs(MIERCOLES)) == 1


def test_partido_fuera_de_dia_de_partido_no_tacha_nada(client):
    client.post(BASE, json={'fecha': JUEVES, 'estado': 'jugado', 'goles_favor': 2, 'goles_contra': 1})
    assert _logs(JUEVES) == []
