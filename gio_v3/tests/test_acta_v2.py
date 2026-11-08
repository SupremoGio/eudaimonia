"""
test_acta_v2.py — handoff Acta Diurna v2 (/actividades/).

Sprint 1: el panel lateral muestra la «Clasificación» con el mismo checklist
que Inicio (clf.criteria); el XP del día aparece una sola vez y la tarjeta
de Progreso ya no existe.
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import modules.gamification.engine as engine

CASOS = {
    'carbon': ('iron', [{'key': 'anchor', 'label': 'Una ancla completa', 'hint': 'o su versión mínima (⅓ del XP)',
                         'have': 0, 'need': 1, 'ok': False}]),
    'iron': ('gold', [{'key': 'touches', 'label': 'Touches', 'hint': '5 base − 1 por tu ancla extra', 'have': 3, 'need': 4, 'ok': False},
                      {'key': 'sessions', 'label': 'Sesiones del día', 'hint': '3 base − 1 por tu ancla extra', 'have': 1, 'need': 2, 'ok': False},
                      {'key': 'pillars', 'label': 'Pilares distintos', 'hint': 'al menos 2', 'have': 4, 'need': 2, 'ok': True}]),
    'gold': ('diamond', [{'key': 'anchors_pct', 'label': 'Anclas de hoy', 'hint': '75% de 4, redondeo arriba',
                          'have': 2, 'need': 3, 'ok': False}]),
    'diamond': (None, []),
}


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _forzar(monkeypatch, rank):
    real = engine.get_daily_classification
    nxt, crit = CASOS[rank]

    def fake(date_str=None):
        return {**real(date_str), 'rank': rank, 'next_rank': nxt, 'criteria': crit}
    monkeypatch.setattr(engine, 'get_daily_classification', fake)


def _clf_card(html):
    m = re.search(r'<section class="eu-card eu-vstack acta-clf".*?</section>', html, re.S)
    assert m, 'falta la tarjeta Clasificación'
    return m.group(0)


@pytest.mark.parametrize('rank,nombre,sub', [
    ('carbon', 'Carbón', 'Para Hierro te falta 1 cosa'),
    ('iron', 'Hierro', 'Para Oro te faltan 2 cosas'),
    ('gold', 'Oro', 'Para Diamante te falta 1 cosa'),
    ('diamond', 'Diamante', 'Día Diamante. Lo que marques suma XP sin presión.'),
])
def test_clasificacion_por_rango(client, monkeypatch, rank, nombre, sub):
    _forzar(monkeypatch, rank)
    card = _clf_card(client.get('/actividades/').get_data(as_text=True))
    assert f'<div class="acta-clf-name js-clf-label">{nombre}</div>' in card
    assert sub in card
    assert 'Racha, nivel y semana en Inicio →' in card
    n = len(CASOS[rank][1])
    assert card.count('<li class="dash-crit') == n
    if rank == 'diamond':
        assert 'js-clf-crit" aria-label="Lo que falta para el siguiente rango" hidden' in card
    if rank == 'iron':
        assert 'data-key="pillars"' in card and 'Pilares distintos: 4 de 2, cumplido' in card


def test_xp_del_dia_una_sola_vez_y_sin_progreso(client):
    html = client.get('/actividades/').get_data(as_text=True)
    assert html.count('js-xp-today') == 1
    assert 'eu-tb-xp' not in html          # sin pastilla de XP en la topbar
    for fuera in ('acta-mbar', 'acta-prog', 'js-xp-week', 'js-xp-month', 'js-streak',
                  'js-lvl-', 'Resumen del día', 'js-clf-desc', 'js-clf-hint', 'js-done-n', 'js-pillars-n'):
        assert fuera not in html, fuera
    assert 'eu-ranks' not in _clf_card(html)


def test_marcar_devuelve_criterios_para_repintar(client):
    """acta.js repinta el checklist con gam.stats.classification de la respuesta."""
    import modules.actividades.activity_defs as adefs
    key = next(k for k, a in adefs.get_active_flat().items() if a.get('effective_type') == 'touch' and not a.get('hidden'))
    r = client.post('/actividades/api/activity/log', json={'key': key}).get_json()
    assert r['action'] == 'added'
    clf = r['gam']['stats']['classification']
    assert 'criteria' in clf and 'next_rank' in clf
    for c in clf['criteria']:
        assert set(c) >= {'key', 'label', 'hint', 'have', 'need', 'ok'}


# ── Sprint 2: Anclas de hoy + virtudes compactas ─────────────────────────────

def _ctx(client, monkeypatch=None):
    from flask import template_rendered
    caps = []
    app = client.application

    def rec(sender, template, context, **kw):
        if template.name == 'actividades/index.html':
            caps.append(context)
    template_rendered.connect(rec, app)
    try:
        html = client.get('/actividades/').get_data(as_text=True)
    finally:
        template_rendered.disconnect(rec, app)
    return html, caps[0]


def test_anclas_en_su_bloque_y_sin_duplicados(client):
    html, ctx = _ctx(client)
    anclas = ctx['acta_anchors']
    assert anclas and all(a['effective_type'] == 'ancla' for a in anclas)
    assert ctx['anchors_need'] == ctx['classification']['diamond_min_anchors']
    assert 'Anclas de hoy' in html and f'· Diamante pide {ctx["anchors_need"]}' in html
    vista = html.split('acta-view acta-virtues', 1)[1].split('acta-view acta-sessions', 1)[0]
    bloque = html.split('class="eu-card acta-anchors"', 1)[1].split('acta-view acta-virtues', 1)[0]
    for a in anclas:
        assert f'data-key="{a["key"]}"' not in vista            # no se repite en las virtudes
        if not a.get('eury_proxy'):
            assert f'class="acta-anchor-min js-min" data-key="{a["key"]}"' in bloque
    keys = [k for p in ctx['acta_pillars'] for k in (i['key'] for i in p['items'])]
    assert len(keys) == len(set(keys))
    # «Por sesión» conserva las anclas en su horario
    sesiones = html.split('acta-view acta-sessions', 1)[1]
    assert f'data-key="{anclas[0]["key"]}"' in sesiones


def test_icono_de_virtud_se_enciende_al_tocarla(client):
    html, ctx = _ctx(client)
    assert 'Cobertura de pilares' not in html and 'acta-cover' not in html
    p = ctx['acta_pillars'][0]
    assert f'class="eu-card acta-pillar" data-cat="{p["cat"]}" data-pillar="{p["id"]}"' in html
    client.post('/actividades/api/activity/log', json={'key': p['items'][0]['key']})
    html = client.get('/actividades/').get_data(as_text=True)
    assert f'class="eu-card acta-pillar is-on" data-cat="{p["cat"]}" data-pillar="{p["id"]}"' in html


def test_version_minima_desde_el_bloque_da_hierro(client):
    _, ctx = _ctx(client)
    a = next(a for a in ctx['acta_anchors'] if not a.get('eury_proxy'))
    r = client.post('/actividades/api/activity/log', json={'key': a['key'], 'minimal': True}).get_json()
    assert r['gam']['stats']['classification']['rank'] == 'iron'


# ── Sprint 3: encabezado y filtros ───────────────────────────────────────────

def test_encabezado_tres_controles_y_sin_filtros(client):
    import modules.actividades.routes as ar
    html, ctx = _ctx(client)
    hd = html.split('<header class="acta-hd">', 1)[1].split('</header>', 1)[0]
    assert f'{ctx["fecha_larga"]} · {ar.SESSION_META[ctx["now_session"]]["label"]}' in hd
    assert 'js-hide-done' in hd and 'Ocultar hechas' in hd and 'eye-off' in hd
    assert 'data-view="virtue"' in hd and 'data-view="session"' in hd
    assert 'aria-label="Editar checklist y foco del mes"' in hd
    for fuera in ('acta-lead', 'data-filter', 'acta-filters', 'js-ct-', 'acta-alerts', 'Hoy: pagar'):
        assert fuera not in html, fuera
    assert 'payment_alerts' not in ctx


def test_foco_del_mes_vive_en_la_barra_de_edicion(client):
    html, ctx = _ctx(client)
    bar = html.split('<div class="acta-editbar" hidden>', 1)[1].split('acta-view acta-virtues', 1)[0]
    if ctx['foco_candidates']:
        assert 'Foco del mes' in bar
    assert html.count('Foco del mes</span>') <= 1
    assert 'class="eu-card acta-foco"' not in html


def test_todo_hecho_por_virtud(client):
    html, ctx = _ctx(client)
    for p in ctx['acta_pillars']:
        assert f'Todo hecho en {p["name"]}.' in html


def test_css_y_js_sin_data_filter():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for f in ('static/css/acta.css', 'static/js/acta.js'):
        src = open(os.path.join(base, f), encoding='utf-8').read()
        assert 'data-filter' not in src and 'dataset.filter' not in src
    js = open(os.path.join(base, 'static/js/acta.js'), encoding='utf-8').read()
    assert "'acta.hideDone'" in js
