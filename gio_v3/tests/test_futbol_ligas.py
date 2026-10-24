"""
test_futbol_ligas.py — cada partido pertenece a una liga (SoccerGDL mié,
Terranova jue, SoccerPark dom, u «otra»). Se guarda la que manda el
formulario; si no viene (o el partido es viejo) se deduce de la cancha y luego
del día de la semana. La página agrupa cifras y próximos por liga.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.bienestar import futbol as fb


def test_liga_por_dia_y_por_cancha():
    assert fb.liga_de('2026-10-21') == 'soccergdl'          # miércoles
    assert fb.liga_de('2026-10-22') == 'terranova'          # jueves
    assert fb.liga_de('2026-10-25') == 'soccerpark'         # domingo
    assert fb.liga_de('2026-10-24') == 'otra'               # sábado
    assert fb.liga_de('2026-10-24', 'Soccer Park') == 'soccerpark'   # la cancha manda
    assert fb.liga_de('2026-10-21', 'Terranova') == 'terranova'
    assert fb.liga_de('', '') == 'otra'


def test_fecha_corta_y_mes():
    assert fb.mes_label('2026-10') == 'Octubre 2026'
    assert fb.fecha_corta('2020-01-05') == 'dom 5 ene 2020'


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def test_crear_guarda_liga_elegida_o_deducida(client):
    r = client.post('/bienestar/futbol/api/partidos', json={'fecha': '2026-10-25', 'estado': 'programado', 'rival': 'Blue label'})
    assert r.get_json()['ok']
    r = client.post('/bienestar/futbol/api/partidos', json={'fecha': '2026-10-24', 'estado': 'programado', 'liga': 'terranova'})
    pid = r.get_json()['id']
    with database.get_db() as db:
        ligas = [x['liga'] for x in db.execute("SELECT liga FROM futbol_partidos ORDER BY id")]
    assert ligas == ['soccerpark', 'terranova']
    client.patch(f'/bienestar/futbol/api/partidos/{pid}', json={'liga': 'basura'})   # inválida -> se deduce (sábado)
    with database.get_db() as db:
        assert db.execute("SELECT liga FROM futbol_partidos WHERE id=?", (pid,)).fetchone()['liga'] == 'otra'


def test_pagina_agrupa_por_liga(client):
    with database.get_db() as db:
        # Partido viejo sin liga: miércoles -> SoccerGDL.
        db.execute("""INSERT INTO futbol_partidos (fecha, rival, goles_favor, goles_contra, goles_propios, estado, created_at)
                      VALUES ('2026-10-21', 'Olimpo', 13, 3, 2, 'jugado', '2026-10-21')""")
        db.commit()
    html = client.get('/bienestar/futbol/').get_data(as_text=True)
    assert 'id="fb-tab-soccergdl"' in html and 'id="fb-tab-terranova"' in html and 'id="fb-tab-soccerpark"' in html
    assert 'data-liga="soccergdl" data-mes="2026-10"' in html
    assert 'Octubre 2026' in html
    d = client.get('/bienestar/futbol/api/partidos').get_json()
    assert d['partidos'][0]['liga'] == 'soccergdl'
