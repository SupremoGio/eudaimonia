"""
test_ataraxia_v2.py — handoff Ataraxia v2 (/ataraxia/).

Sprint 1: encabezado con fecha · semana, pestañas compactas con su conteo,
Reset solo en el menú ⋯ (con confirmación), recompensas visibles desde el
inicio y vista previa de solo lectura entre semana.
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.ataraxia.routes as ar

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMINGO, MIERCOLES = datetime.date(2026, 11, 8), datetime.date(2026, 11, 4)


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _hoy(monkeypatch, d):
    monkeypatch.setattr(ar, 'today_date', lambda: d)
    monkeypatch.setattr(ar, 'today_str', lambda: d.isoformat())


def _src(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


def _get(client, q=''):
    return client.get('/ataraxia/' + q).get_data(as_text=True)


def _side(html):
    return html.split('<aside class="at-side"', 1)[1].split('</aside>', 1)[0]


def test_encabezado_fecha_semana_y_pestanas(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client)
    hd = html.split('<header class="at-hd">', 1)[1].split('</header>', 1)[0]
    assert 'Domingo 8 de noviembre · Semana 45' in hd
    assert 'class="eu-seg at-tabs"' in hd
    assert 'id="tab-sabado"' in hd and 'id="tab-domingo"' in hd
    assert hd.count('js-day-cnt') == 2
    assert 'aria-label="Más opciones"' in hd and 'id="reset-trigger"' in hd
    assert 'role="menu" hidden' in hd                  # el Reset solo vive en el menú ⋯
    for fuera in ('at-lead', 'at-week', 'finde-banner', 'at-note', 'Hoy no es fin de semana'):
        assert fuera not in html, fuera
    assert html.count('id="reset-trigger"') == 1 and "euModal.open('at-reset')" in _src('static/js/ataraxia.js')


def test_recompensas_visibles_antes_de_ganarlas(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    side = _side(_get(client))
    for rid, label, rw in [('sabado', 'Sábado completo', '+4 XP · +2 EC'), ('domingo', 'Domingo completo', '+5 XP · +3 EC'),
                           ('finde', 'Fin de semana perfecto', '+15 XP · +30 EC')]:
        assert f'id="rw-{rid}"' in side and label in side and rw in side
    assert 'is-ok' not in side and side.count('data-lucide="circle-dashed"') == 2


def test_recompensa_se_marca_al_completar_el_dia(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    with database.get_db() as db:
        req = [r['id'] for r in db.execute("SELECT id FROM rutina_bloques WHERE dia='sabado' AND opcional=0")]
        for tid in req:
            db.execute("INSERT INTO rutina_progreso (bloque_id, semana_id, completado) VALUES (?,?,1)", (tid, ar.get_semana_id()))
        db.commit()
    html = _get(client)
    assert '<div class="at-rw-row is-ok" id="rw-sabado"' in _side(html)
    assert '<div class="at-rw-row" id="rw-finde"' in _side(html)
    tab = html.split('id="tab-sabado"', 1)[1].split('</button>', 1)[0]
    assert '>✓</span>' in tab and 'data-complete="true"' in tab


def test_entre_semana_vista_previa_solo_lectura(client, monkeypatch):
    _hoy(monkeypatch, MIERCOLES)
    html = _get(client)
    assert 'Faltan 3 días para el sábado · vista previa' in html
    assert 'data-preview="1"' in html
    tareas = html.count('class="at-task js-task"')
    assert tareas and html.count('aria-disabled="true"') >= tareas
    assert 'root.dataset.preview' in _src('static/js/ataraxia.js')


def test_fin_de_semana_se_puede_marcar(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client)
    assert 'data-preview' not in html and 'aria-disabled="true"' not in html.split('class="at-main"', 1)[1]
