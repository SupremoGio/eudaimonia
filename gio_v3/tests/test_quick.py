"""
test_quick.py — handoff Captura rápida (transversal).

Sprint 1: registro QUICK (endpoints existentes, permisos, sin solaparse con
ACTIONS), GET /api/quick/options con defaults, contador de uso.
Sprint 2: barra móvil con «+» y la hoja; contadores de Acta y Praxis.
Sprint 3: parser de ⌘K con una tabla de casos compartida (quick_parse_cases.json).
"""
import sys, os, json, re
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules import nav
from utils import today_str, today_date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def app(test_db):
    from app import create_app
    a = create_app()
    a.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return a


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


@pytest.fixture
def fin(client):
    with client.session_transaction() as s:
        s['fin_ok'] = True
    return client


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_quick_y_actions_no_se_solapan():
    ids = [q['id'] for q in nav.QUICK]
    assert ids == ['gasto', 'comida', 'tarea', 'actividad', 'peso', 'baile', 'km', 'medicamento', 'nota']
    assert not set(ids) & {a['id'] for a in nav.ACTIONS}
    labels = {a['label'].lower() for a in nav.ACTIONS}
    assert not any(k in l for q in nav.QUICK for k in (q['id'],) for l in labels if 'gasto' in l or 'tarea' in l)
    for q in nav.QUICK:
        assert q['url'] and q['keywords'] and q['icon']
        if q.get('post'):
            assert q['post']['url'].startswith('/') and q['post']['method'] in ('POST', 'PATCH')


def test_endpoints_existen(app):
    rutas = {(r.rule, m) for r in app.url_map.iter_rules() for m in r.methods}
    norm = lambda u: re.sub(r'\{id\}', '<int:x>', u)
    for q in nav.QUICK:
        for paso in [q.get('post')] + q.get('then', []) + [q.get('undo')]:
            if not paso:
                continue
            url = paso['url']
            ok = any(m == paso['method'] and re.fullmatch(re.sub(r'<[^>]+>', '[^/]+', rule), url.replace('{id}', '1'))
                     for rule, m in rutas)
            assert ok, (q['id'], paso)


def test_gasto_y_peso_piden_fin_ok(app, client, fin):
    assert 'gasto' not in [q['id'] for q in nav.quick_for({})]
    assert 'gasto' in [q['id'] for q in nav.quick_for({'fin_ok': True})]
    with app.test_request_context('/'):
        from flask import session
        assert 'gasto' not in [q['id'] for q in nav._quick_ctx()]
    c = client.application.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    assert c.get('/api/quick/options?id=gasto').status_code == 404
    assert 'data-quick="gasto"' not in c.get('/gtd/').get_data(as_text=True)


def test_options_devuelve_defaults(fin):
    with database.get_db() as db:
        for i, cat in enumerate(['TRANSPORTE', 'TRANSPORTE', 'SUPER']):
            db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo) VALUES (?,?,?,?,?,'GASTO')",
                       (today_str(), f'x{i}', 100 + i, 'MANUAL', cat))
        db.commit()
    g = fin.get('/api/quick/options?id=gasto').get_json()['fields']
    assert g['categoria']['default'] == 'TRANSPORTE' and g['categoria']['options'][1]['value'] == 'SUPER'
    assert g['cuenta']['default'] == 'MANUAL' and g['monto'] == {'default': None}
    fin.post('/api/quick/uso', json={'id': 'gasto', 'values': {'categoria': 'SUPER', 'cuenta': 'BBVA_DEB'}})
    g = fin.get('/api/quick/options?id=gasto').get_json()['fields']
    assert g['categoria']['default'] == 'SUPER' and g['cuenta']['default'] == 'BBVA_DEB'
    c = fin.get('/api/quick/options?id=comida').get_json()['fields']
    assert c['meal']['options'] and c['meal']['default'] in [o['value'] for o in c['meal']['options']]
    assert c['como']['default'] == 'limpia'
    t = fin.get('/api/quick/options?id=tarea').get_json()['fields']
    assert t['cuando']['default'] == 'inbox' and len(t['cuando']['options']) == 4
    b = fin.get('/api/quick/options?id=baile').get_json()['fields']
    assert b['min']['default'] == 30 and b['flow']['default'] == 3
    a = fin.get('/api/quick/options?id=actividad').get_json()['fields']['key']
    assert a['options'] and a['default'] == a['options'][0]['value']
    assert fin.get('/api/quick/options?id=nada').status_code == 404


def test_uso_ordena_la_hoja(fin):
    for _ in range(3):
        fin.post('/api/quick/uso', json={'id': 'km'})
    fin.post('/api/quick/uso', json={'id': 'nota'})
    from modules.quick import usos
    orden = [q['id'] for q in nav.quick_for({'fin_ok': True}, usos())]
    assert orden[:2] == ['km', 'nota'] and orden[2] == 'gasto'
    assert fin.post('/api/quick/uso', json={'id': 'nada'}).status_code == 400


# ── Sprint 3: parser de ⌘K (tabla de casos compartida) ───────────────────────

import shutil, subprocess

CASES = os.path.join(BASE, 'tests', 'quick_parse_cases.json')


@pytest.mark.skipif(not shutil.which('node'), reason='node no disponible')
def test_parser_tabla_de_casos():
    script = """
      const p = require(process.argv[1]); const fs = require('fs');
      const quick = JSON.parse(process.argv[2]); const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
      const out = cases.map(c => { const r = p.parse(c.in, quick); return r && {id: r.id, values: r.values, ready: r.ready, missing: r.missing}; });
      process.stdout.write(JSON.stringify(out));
    """
    r = subprocess.run(['node', '-e', script, os.path.join(BASE, 'static/js/eu-quick.js'), json.dumps(nav.QUICK), CASES],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    for case, res in zip(json.load(open(CASES, encoding='utf-8')), got):
        exp = case['out']
        if exp is None:
            assert res is None, case['in']
            continue
        assert res['id'] == exp['id'] and res['values'] == exp['values'] and res['ready'] == exp['ready'], (case['in'], res)
        if 'missing' in exp:
            assert res['missing'] == exp['missing'], case['in']


def test_keywords_no_chocan_con_paginas():
    """Un sinónimo de QUICK no debe tapar la búsqueda de una página («xyz» y
    los nombres del menú siguen como hoy)."""
    kws = {k for q in nav.QUICK for k in q['keywords']}
    paginas = {it['label'].lower() for g in nav.NAV for it in g['items']} | {ch['label'].lower() for g in nav.NAV for it in g['items'] for ch in it.get('children', [])}
    assert not kws & {p for p in paginas if ' ' not in p} - {'nutrición'}, kws & paginas


# ── Sprint 2: barra móvil con «+», hoja y contadores ─────────────────────────

def test_barra_con_mas_y_sin_tu():
    ids = [b['id'] for b in nav.BOTTOM_NAV]
    assert ids == ['inicio', 'acta', 'registrar', 'praxis', 'modulos']
    assert [b.get('badge') for b in nav.BOTTOM_NAV] == [None, 'acta', None, 'praxis', None]


def test_layout_hoja_y_contadores(fin):
    html = fin.get('/gtd/').get_data(as_text=True)
    assert 'id="eu-quick-btn"' in html and 'aria-haspopup="dialog" aria-controls="eu-quick"' in html and 'aria-label="Registrar"' in html
    assert 'id="eu-quick" hidden' in html and 'role="dialog" aria-modal="true" aria-labelledby="eu-quick-t"' in html
    assert html.count('class="eu-quick-cell"') == len(nav.QUICK) and 'data-quick="gasto"' in html
    assert 'data-badge-for="acta"' in html and 'data-badge-for="praxis"' in html and '/js/eu-quick.js' in html
    assert '<select' not in html.split('id="eu-quick"', 1)[1].split('id="eu-cmdk"', 1)[0]
    # «Tú» ya no está en la barra; Perfil vuelve al sheet de Módulos
    bnav = html.split('class="eu-bnav"', 1)[1].split('</nav>', 1)[0]
    assert '>Tú<' not in bnav
    sheet = html.split('id="eu-mod-sheet"', 1)[1].split('</nav>', 1)[0]
    assert 'href="/perfil/"' in sheet and 'href="/logros"' in sheet
    # Perfil activa «Módulos» en la barra
    p = fin.get('/perfil/').get_data(as_text=True).split('class="eu-bnav"', 1)[1].split('</nav>', 1)[0]
    assert 'id="eu-mod-btn" class="is-active"' in p


def test_badges(fin):
    with database.get_db() as db:
        ayer = (today_date() - timedelta(days=1)).isoformat()
        db.execute("INSERT INTO gtd_tasks (title, status, completado, fecha_limite, created_at) VALUES ('vencida', 'inbox', 0, ?, 'x')", (ayer,))
        db.execute("INSERT INTO gtd_tasks (title, status, completado, fecha_limite, created_at) VALUES ('hecha', 'done', 1, ?, 'x')", (ayer,))
        db.commit()
    b = fin.get('/api/quick/badges').get_json()
    assert b['praxis'] == 1 and b['acta'] >= 0
    from modules.quick import badges
    import modules.actividades.activity_defs as adefs
    anclas = [it['key'] for s, l in adefs.get_active_grouped().items() if s != 'ocasional' for it in l if it.get('effective_type') == 'ancla']
    if anclas:
        n0 = b['acta']
        fin.post('/actividades/api/activity/log', json={'key': anclas[0]})
        assert fin.get('/api/quick/badges').get_json()['acta'] == n0 - 1


def test_guardar_por_los_endpoints_existentes(fin):
    """El POST que arma eu-quick.js con QUICK funciona contra cada endpoint."""
    r = fin.post('/finanzas/estados/api/transactions', json={'fecha': today_str(), 'descripcion': 'tacos', 'monto': 180,
                                                             'categoria': 'COMIDA_FUERA', 'banco': 'MANUAL', 'tipo': 'GASTO'})
    assert r.status_code == 201 and r.get_json()['id']
    assert fin.delete(f"/finanzas/estados/api/transactions/{r.get_json()['id']}").status_code == 200
    t = fin.post('/gtd/api/task', json={'texto': 'Llamar al banco', 'tipo': 'tarea'}).get_json()
    assert fin.post(f"/gtd/api/task/{t['id']}/classify", json={'importante': 1, 'urgente': 1}).get_json()['ok']
    assert fin.post(f"/gtd/api/task/{t['id']}/update", json={'fecha_limite': today_str()}).get_json()['ok']
    m = fin.get('/api/quick/options?id=comida').get_json()['fields']['meal']
    assert fin.post('/nutricion/api/cumplir', json={'meal_id': m['default']}).status_code == 200
    assert fin.post('/nutricion/api/descumplir', json={'meal_id': m['default']}).get_json()['ok']
    assert fin.post('/perfil/api/update_measurement', json={'key': 'peso', 'value': 78.2}).get_json()['ok']
    assert fin.post('/eurythmia/api/session', json={'min': 30, 'flow': 3}).status_code == 200
    k = fin.get('/api/quick/options?id=actividad').get_json()['fields']['key']['default']
    log = fin.post('/actividades/api/activity/log', json={'key': k}).get_json()
    assert log['action'] == 'added' and fin.post(f"/actividades/api/activity/undo/{log['log_id']}").get_json()['ok']
