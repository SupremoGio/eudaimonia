"""
test_idiomas_temario.py — temario del plan C1 v2 (modules/idiomas/temario.py).

3 fases de 10 semanas desde 2026-11-16; por semana e idioma: tema, foco y
prompts fijos, material sugerido editable (lang_temario_material). «Hoy toca»
en Cosmopolitismo y una línea en las anclas de idioma de Acta.
"""
import sys, os, re
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import utils
from modules.idiomas import temario as tm


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def test_estructura_completa_y_sin_examenes():
    assert tm.SEMANAS == 30 and [f['semanas'] for f in tm.FASES] == [(1, 10), (11, 20), (21, 30)]
    for lang in ('en', 'fr'):
        assert len(tm.TEMARIO[lang]) == 30
        for e in tm.TEMARIO[lang]:
            assert all(e[k].strip() for k in ('tema', 'foco', 'material', 'conversacion', 'writing')), e
    texto = repr(tm.TEMARIO).lower()
    for prohibido in ('dalf', 'delf', 'ielts', 'toefl', 'cambridge exam', 'mock exam', 'examen oficial'):
        assert prohibido not in texto, prohibido
    assert [f['checkpoint'] for f in tm.FASES] == [date(2027, 1, 23), date(2027, 4, 3), date(2027, 6, 12)]
    assert all(tm.semana_de(f['checkpoint']) == f['semanas'][1] for f in tm.FASES)   # el checkpoint cae en su última semana


@pytest.mark.parametrize('d,titulo,escucha', [
    (date(2026, 11, 16), 'Inglés · Sesión A · input', 'Inglés'),
    (date(2026, 11, 17), 'Francés · Sesión A · input', 'Francés'),
    (date(2026, 11, 18), None, 'Inglés'),
    (date(2026, 11, 19), 'Inglés · Sesión B · output', 'Inglés'),
    (date(2026, 11, 20), 'Francés · Sesión B · output', 'Francés'),
    (date(2026, 11, 21), 'Repaso semanal EN+FR', None),
    (date(2026, 11, 22), None, 'Francés'),
    (date(2027, 1, 23), 'Autodiagnóstico C1 · checkpoint de la fase 1', None),
])
def test_hoy_toca(d, titulo, escucha):
    h = tm.hoy(d)
    assert (h.get('sesion') or {}).get('titulo') == titulo
    assert (h.get('escucha') or {}).get('idioma') == escucha
    if escucha:                                             # siempre los dos idiomas: escucha uno, lee el otro
        assert {h['escucha']['lang'], h['lectura']['lang']} == {'en', 'fr'}


def test_fuera_del_plan():
    assert tm.hoy(date(2026, 11, 15))['antes'] and tm.hoy(date(2027, 6, 14))['terminado']
    assert tm.para_ancla('ancla_ingles', date(2027, 7, 1)) is None


def test_plan_viejo_reemplazado(test_db):
    with database.get_db() as db:
        cps = [(r['fase'], r['semana_fin']) for r in db.execute("SELECT fase, semana_fin FROM lang_plan_checkpoints ORDER BY fase")]
        ini = db.execute("SELECT value FROM app_settings WHERE key='idiomas_plan_inicio'").fetchone()[0]
    assert cps == [(1, 10), (2, 20), (3, 30)] and ini == '2026-11-16'
    from modules.idiomas.routes import _plan_estado
    assert _plan_estado()['total_semanas'] == 30


def test_material_editable_y_vuelve_al_sugerido(client):
    r = client.post('/idiomas/api/temario/material', json={'lang': 'fr', 'semana': 2, 'material': 'Mi podcast'}).get_json()
    assert r['ok'] and r['semana']['material'] == 'Mi podcast' and r['semana']['material_propio']
    html = client.get('/idiomas/?vista=plan').get_data(as_text=True)
    assert 'Mi podcast' in html and 'Material (tuyo)' in html
    r = client.post('/idiomas/api/temario/material', json={'lang': 'fr', 'semana': 2, 'material': ''}).get_json()
    assert r['semana']['material'] == tm.TEMARIO['fr'][1]['material'] and not r['semana'].get('material_propio')
    assert client.post('/idiomas/api/temario/material', json={'lang': 'de', 'semana': 2, 'material': 'x'}).status_code == 400
    assert client.post('/idiomas/api/temario/material', json={'lang': 'en', 'semana': 31, 'material': 'x'}).status_code == 400


def test_pagina_muestra_hoy_toca_y_el_temario(client, monkeypatch):
    monkeypatch.setattr(utils, 'today_date', lambda: date(2026, 11, 19))     # jueves, semana 1
    html = client.get('/idiomas/').get_data(as_text=True)
    i = html.index('id="hoy"')
    hoy = html[i:i + 4000]
    assert 'Inglés · Sesión B · output' in hoy and tm.TEMARIO['en'][0]['conversacion'] in hoy
    assert tm.TEMARIO['en'][0]['writing'] in hoy and 'Escucha inglés' in hoy and 'Lectura francés' in hoy
    plan = client.get('/idiomas/?vista=plan').get_data(as_text=True)
    assert plan.count('class="id-tm') >= 60 and 'Cimientos C1' in plan and 'Precisión y registro' in plan
    assert 'mock exam' not in plan.lower()


def test_prompt_del_journal_es_el_de_la_semana(client, monkeypatch):
    monkeypatch.setattr(tm, 'semana_de', lambda d=None: 3)
    r = client.get('/idiomas/api/journal/prompt?lang=fr').get_json()
    assert r['prompt'] == tm.TEMARIO['fr'][2]['writing']
    assert client.get('/idiomas/api/estado?lang=en').get_json()['prompt'] == tm.TEMARIO['en'][2]['writing']


def test_ancla_de_acta_dice_lo_que_toca(client, monkeypatch):
    monkeypatch.setattr(tm, 'semana_de', lambda d=None: 1)
    import modules.actividades.activity_defs as adefs
    with database.get_db() as db:
        db.execute("UPDATE activity_defs SET days_of_week=? WHERE key='ancla_frances'", (adefs.weekday_code(),))
        db.commit()
    html = client.get('/actividades/').get_data(as_text=True)
    j = html.index('class="acta-item acta-anchor is-ancla" data-key="ancla_frances"')
    assert 'Semana 1 · Litote' in html[j:j + 1500] and 'href="/idiomas/#hoy"' in html[j:j + 1500]
