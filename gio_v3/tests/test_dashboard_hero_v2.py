"""
test_dashboard_hero_v2.py — Sprint 2 de Inicio v2: el héroe de / muestra el
rango, lo que falta para el siguiente (clf.criteria) y el «Siguiente paso»
dentro del héroe. Se fuerza cada rango sobre la clasificación real.
"""
import sys, os

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


@pytest.mark.parametrize('rank,nombre,sub', [
    ('carbon', 'Carbón', 'Para Hierro te falta 1 cosa'),
    ('iron', 'Hierro', 'Para Oro te faltan 2 cosas'),
    ('gold', 'Oro', 'Para Diamante te falta 1 cosa'),
    ('diamond', 'Diamante', 'Máxima clasificación del día'),
])
def test_hero_por_rango(client, monkeypatch, rank, nombre, sub):
    _forzar(monkeypatch, rank)
    html = client.get('/').get_data(as_text=True)
    assert f'<div class="dash-hero-rname">{nombre}</div>' in html
    assert sub in html
    assert 'Hoy · clasificación' in html
    if rank == 'diamond':
        assert 'Día Diamante.' in html and 'class="dash-crit' not in html
    else:
        for c in CASOS[rank][1]:
            assert f'data-key="{c["key"]}"' in html and c['label'] in html
            assert f'{c["label"]}: {c["have"]} de {c["need"]}' in html   # aria-label
    if rank == 'iron':
        assert 'dash-crit is-ok' in html            # pilares ya cumplidos
        assert html.count('class="is-on"') >= 3 + 1 + 2


def test_encabezado_y_lo_que_se_quita(client):
    html = client.get('/').get_data(as_text=True)
    assert 'Marcar actividad' in html and 'href="/actividades/"' in html
    assert 'de tu racha</div>' not in html                  # la racha ya no va en el eyebrow
    assert '<div class="t-meta">EC</div>' not in html and 'Perks' not in html
    assert 'Siguiente paso' in html and html.count('Siguiente paso') == 1   # dentro del héroe, una sola vez
