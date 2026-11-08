"""
test_praxis_v2.py — handoff Praxis v2 (/gtd/).

Sprint 1: captura en una barra, sin el párrafo fijo, sin «Puntos y nivel»
y sin las 4 cifras (los conteos viven en cada sección).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _src(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


def _px(html):
    return html.split('<div class="px" id="px">', 1)[1].split('id="px-data"', 1)[0]


def test_captura_en_una_barra_y_sin_cifras(client):
    html = client.get('/gtd/').get_data(as_text=True)
    px = _px(html)
    cap = px.split('<form class="px-capture"', 1)[1].split('</form>', 1)[0]
    assert cap.count('class="px-cap-row"') == 1
    assert 'class="eu-seg px-cap-tipo"' in cap
    for tipo in ('tarea', 'idea', 'mantenimiento'):
        assert f'data-tipo="{tipo}"' in cap
    assert 'Capturar</button>' in cap
    for fuera in ('px-lead', 'Puntos y nivel', 'px-stats', 'id="st-'):
        assert fuera not in px, fuera
    assert '<span class="js-mt-inbox">0</span> en inbox</span>' in html


def test_js_y_css_sin_st():
    js, css = _src('static/js/praxis.js'), _src('static/css/praxis.css')
    assert 'st-inbox' not in js and 'st-hoy' not in js and 'st-done' not in js
    assert '#st-' not in css


def test_captura_tarea_va_al_inbox_e_idea_al_banco(client):
    t = client.post('/gtd/api/task', json={'texto': 'Renovar pasaporte', 'tipo': 'tarea'}).get_json()
    i = client.post('/gtd/api/task', json={'texto': 'Curso de SQL', 'tipo': 'idea'}).get_json()
    with database.get_db() as db:
        rows = {r['id']: dict(r) for r in db.execute('SELECT id, cuadrante, tipo FROM gtd_tasks')}
    assert rows[t['id']]['cuadrante'] is None
    assert rows[i['id']]['cuadrante'] == 'ideas'
    html = client.get('/gtd/').get_data(as_text=True)
    assert '<span class="js-mt-inbox">1</span> en inbox' in html
