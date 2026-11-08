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
