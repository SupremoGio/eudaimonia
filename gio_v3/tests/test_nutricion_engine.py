"""
test_nutricion_engine.py — handoff Nutrición v2 (/nutricion/).

Sprint 1: todo el XP por engine.process_activity (activity_logs con claves
nutri_*), día cerrado una sola vez, deshacer revierte el bono, racha calculada
(se rompe con un desliz), _hegemonikon_summary_data intacto.
Sprint 2–3: página sin pestañas, «¿Cómo cayó?», lateral (macros, disparadores).
Sprint 4: un solo recetario (fodmap/momento, banco migrado, «Agregar a hoy»).
"""
import sys, os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date, today_str
from modules.nutricion import routes as nr

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOY = today_date()


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


def _hoy(client):
    return client.get('/nutricion/api/estado').get_json()


def _meals(client):
    st = _hoy(client)
    return st['week'][st['today']]


def _logs(prefix):
    with database.get_db() as db:
        return [r['activity_key'] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE substr(activity_key,1,?)=?", (len(prefix), prefix)).fetchall()]


def _cumplir_todo(client):
    r = None
    for m in _meals(client):
        if not m['done']:
            r = client.post('/nutricion/api/cumplir', json={'meal_id': m['id']}).get_json()
    return r


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_comida_va_por_el_motor(client):
    m = _meals(client)[0]
    r = client.post('/nutricion/api/cumplir', json={'meal_id': m['id']}).get_json()
    assert _logs('nutri_comida_') == [f"nutri_comida_{m['id']}"]
    assert r['xp_earned'] >= m['xp'] and r['total_xp'] == r['xp_earned'] and r['bonus_xp'] == 0
    with database.get_db() as db:
        row = db.execute("SELECT * FROM activity_logs WHERE activity_key=?", (f"nutri_comida_{m['id']}",)).fetchone()
        assert row['pts'] == m['xp']
        assert db.execute("SELECT COUNT(*) FROM xp_ledger WHERE source='activity' AND reference_id=?", (row['id'],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM xp_ledger WHERE source='nutricion'").fetchone()[0] == 0
    assert client.post('/nutricion/api/cumplir', json={'meal_id': m['id']}).status_code == 400


def test_dia_cerrado_una_vez_y_deshacer_revierte_bono(client):
    r = _cumplir_todo(client)
    assert r['all_done'] and r['bonus_xp'] >= 30 and r['bonus_ec'] == 8 and r['streak'] == 1
    assert _logs('nutri_dia_') == [f'nutri_dia_{today_str()}']
    xp_cerrado = r['total_xp']
    ultima = _meals(client)[-1]
    d = client.post('/nutricion/api/descumplir', json={'meal_id': ultima['id']}).get_json()
    assert d['ok'] and d['bono_revertido'] and _logs('nutri_dia_') == [] and d['streak'] == 0
    assert d['total_xp'] < xp_cerrado - 30 and d['total_ec'] == 0
    r = client.post('/nutricion/api/cumplir', json={'meal_id': ultima['id']}).get_json()
    assert r['all_done'] and _logs('nutri_dia_') == [f'nutri_dia_{today_str()}']
    _cumplir_todo(client)                                          # nada más que cumplir: sin segundo bono
    assert len(_logs('nutri_dia_')) == 1


def test_sintoma_una_vez_por_comida(client):
    m = _meals(client)[0]
    client.post('/nutricion/api/cumplir', json={'meal_id': m['id']})
    a = client.post('/nutricion/api/sintoma', json={'meal_id': m['id'], 'feeling': 'Pesado'}).get_json()
    b = client.post('/nutricion/api/sintoma', json={'meal_id': m['id'], 'feeling': 'Bien'}).get_json()
    assert a['xp_earned'] >= 5 and b['xp_earned'] == 0 and a['feeling'] == 'regular' and b['feeling'] == 'bien'
    assert _logs('nutri_sintoma_') == [f"nutri_sintoma_{m['id']}"]


def test_desliz_penaliza_y_rompe_racha(client):
    _cumplir_todo(client)
    with database.get_db() as db:                                   # ayer también cerrado (motor ya activo)
        db.execute("UPDATE app_settings SET value=? WHERE key='nutri_engine_since'", ((HOY - timedelta(days=5)).isoformat(),))
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,30)",
                   (f'nutri_dia_{(HOY - timedelta(days=1)).isoformat()}', (HOY - timedelta(days=1)).isoformat()))
        db.commit()
        assert nr.get_streak(db) == 2
    xp = _hoy(client)['xp_today']
    r = client.post('/nutricion/api/desliz', json={'trig_id': 'pan', 'over': True}).get_json()
    assert r['pen'] == 18 and r['streak'] == 0 and r['total_xp'] == xp - 18
    assert _logs('nutri_desliz_') == [f"nutri_desliz_{r['slip']['id']}"]
    with database.get_db() as db:
        assert db.execute("SELECT pts FROM activity_logs WHERE activity_key=?", (f"nutri_desliz_{r['slip']['id']}",)).fetchone()[0] == -18


def test_racha_usa_fallback_antes_de_since(test_db):
    with database.get_db() as db:
        ayer = (HOY - timedelta(days=1)).isoformat()
        db.execute("UPDATE app_settings SET value=? WHERE key='nutri_engine_since'", (ayer,))
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('nutricion_streak', '4')")
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,30)", (f'nutri_dia_{ayer}', ayer))
        db.commit()
        assert nr.get_streak(db) == 5                                 # ayer cerrado + 4 heredados


def test_hegemonikon_summary_sigue(client):
    _cumplir_todo(client)
    from modules.bienestar.routes import _hegemonikon_summary_data
    with client.application.test_request_context():
        d = _hegemonikon_summary_data()
    assert d['nutricion'] is not None


def test_migracion_idempotente(test_db):
    database.init_db()
    database.init_db()
    with database.get_db() as db:
        cols = [r['name'] for r in db.execute("PRAGMA table_info(recetas)")]
        assert cols.count('fodmap') == 1 and cols.count('momento') == 1
        assert db.execute("SELECT COUNT(*) FROM recetas WHERE nombre='Kiwi + puñado de almendras'").fetchone()[0] == 1
        assert nr.migrar_banco(db) == 0
        assert db.execute("SELECT value FROM app_settings WHERE key='nutri_engine_since'").fetchone()[0] == today_str()


# ── Sprint 2–3: página ───────────────────────────────────────────────────────

def test_pagina_sin_pestanas(client):
    html = client.get('/nutricion/').get_data(as_text=True)
    for fuera in ('role="tablist" aria-label="Secciones', 'data-tab-set', 'tab-recetas', 'data-variant', 'Ritmo', 'hoy-ring', 'hoy-status',
                  'dt-lead', 'id="k-xp"', 'Caí en la tentación'):
        assert fuera not in html, fuera
    for dentro in ('d limpios</div>', '<h1 class="t-page">Nutrición</h1>', 'class="dt-tira"', 'id="hoy-list"', 'Agregar comida o colación · del recetario',
                   'El día', 'Bristol · hoy', 'Disparadores · 30 días', 'Registrar un desliz', '/recetas/?fodmap=seguro',
                   '?vista=semana', '?vista=sintomas', 'id="m-meal"', 'id="m-slip"', 'id="m-add"'):
        assert dentro in html, dentro
    js = open(os.path.join(BASE, 'static/js/nutricion.js'), encoding='utf-8').read()
    assert '¿Cómo cayó? · +5 XP' in js and "'Luego'" not in js and '>Luego<' in js and 'RECIPES' not in js and '/api/descumplir' in js


def test_vistas_semana_y_sintomas(client):
    m = _meals(client)[0]
    client.post('/nutricion/api/cumplir', json={'meal_id': m['id']})
    s = client.get('/nutricion/?vista=semana').get_data(as_text=True)
    assert 'id="sem-grid"' in s and 'id="hoy-list"' not in s
    h = client.get('/nutricion/?vista=sintomas').get_data(as_text=True)
    assert 'Pendiente' in h and f'data-meal="{m["id"]}"' in h and 'Deslices · 30 días' in h


def test_macros_solo_cumplidas_y_disparadores(client):
    _meals(client)                                                  # siembra la semana
    with database.get_db() as db:
        db.execute("UPDATE nutricion_semana SET kcal=400, protein=30")
        db.commit()
    ms = _meals(client)
    client.post('/nutricion/api/cumplir', json={'meal_id': ms[0]['id']})
    client.post('/nutricion/api/cumplir', json={'meal_id': ms[1]['id']})
    st = _hoy(client)
    assert st['macros'] == {'kcal': 800, 'prot': 60} and st['metas'] == {'kcal': 1850, 'prot': 130}
    client.post('/nutricion/api/desliz', json={'trig_id': 'lacteo'})
    client.post('/nutricion/api/desliz', json={'trig_id': 'lacteo'})
    r = client.post('/nutricion/api/desliz', json={'trig_id': 'cafe'}).get_json()
    assert r['estado']['disparadores'][0] == {'trig_id': 'lacteo', 'label': 'Lácteo', 'n': 2} and r['streak'] == 0
    with database.get_db() as db:
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('nutri_meta_kcal', '2100')")
        db.commit()
    assert _hoy(client)['metas']['kcal'] == 2100


def test_tira_semana(client):
    _cumplir_todo(client)
    tira = _hoy(client)['tira']
    hoy = [d for d in tira if d['hoy']][0]
    assert len(tira) == 7 and hoy['estado'] == 'cerrado' and hoy['fecha'] == today_str()


# ── Sprint 4: un solo recetario ──────────────────────────────────────────────

def test_receta_nueva_de_cena_aparece_en_agregar(client):
    r = client.post('/recetas/api/recipe', json={'nombre': 'Salmón con papa', 'categoria': 'Cena', 'calorias': 500, 'proteina': 35,
                                                 'fodmap': 'seguro', 'momento': ['cena'],
                                                 'ingredientes': [{'item': 'Salmón'}, {'item': 'Papa'}]}).get_json()
    assert r['fodmap'] == 'seguro' and r['momento'] == 'cena'
    cena = client.get('/nutricion/api/banco?slot=Cena').get_json()
    assert 'Salmón con papa' in [x['nombre'] for x in cena]
    assert cena[0]['fodmap'] == 'seguro' and all(x['fodmap'] != 'evitar' for x in cena)
    nombres_desayuno = [x['nombre'] for x in client.get('/nutricion/api/banco?slot=Desayuno').get_json() if x['match']]
    assert 'Salmón con papa' not in nombres_desayuno and 'Omelette de espinaca y papa' in nombres_desayuno
    orden = [x['fodmap'] for x in client.get('/nutricion/api/banco?slot=Desayuno').get_json() if x['match']]
    assert orden == sorted(orden, key=lambda f: {'seguro': 0, 'porcion': 1}.get(f, 2))
    m = client.post('/nutricion/api/comida', json={'receta_id': r['id'], 'slot': 'Cena'}).get_json()['meal']
    assert m['name'] == 'Salmón con papa' and m['kcal'] == 500 and m['protein'] == 35 and m['tag'] == 'safe' and m['time'] == '20:30'
    assert [i['t'] for i in m['items']] == ['Salmón', 'Papa']


def test_recetario_fodmap(client):
    html = client.get('/recetas/?fodmap=seguro').get_data(as_text=True)
    assert 'Apta FODMAP' in html and 'id="rc-fodmap" aria-pressed="true"' in html and 'id="rm-fodmap"' in html
    lista = client.get('/recetas/api/list?fodmap=seguro').get_json()
    assert lista and all(x['fodmap'] == 'seguro' for x in lista)
    st = _hoy(client)['recetario']
    assert st['total'] >= 9 and st['aptas'] == 7
    js = open(os.path.join(BASE, 'static/js/recetas.js'), encoding='utf-8').read()
    assert 'Agregar a hoy' in js and '/nutricion/api/comida' in js
