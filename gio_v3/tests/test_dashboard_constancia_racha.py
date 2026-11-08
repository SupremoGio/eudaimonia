"""
test_dashboard_constancia_racha.py — Sprint 5 de Inicio v2:
  - «Constancia» colorea cada día por su clasificación (no por XP), con el
    historial guardado en daily_classification (engine.classification_history)
    y recalculado solo si cambian los registros de ese día.
  - La racha dice qué sigue: «N días más para +5/10% XP» o «Bonus máximo».
"""
import sys, os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.gamification.engine as engine
from modules.dashboard import routes as dr

HOY = date(2026, 10, 8)     # jueves


@pytest.fixture
def hoy(monkeypatch):
    monkeypatch.setattr(engine, 'today_date', lambda: HOY)
    monkeypatch.setattr(engine, 'today_str', lambda: HOY.isoformat())
    monkeypatch.setattr(dr, 'today_date', lambda: HOY)
    return HOY


def _log(fecha, key='tender_cama'):
    with database.get_db() as db:
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,1)", (key, fecha))
        db.commit()


def _cached():
    with database.get_db() as db:
        return {r['date']: r['rank'] for r in db.execute("SELECT date, rank FROM daily_classification")}


def test_historial_usa_el_motor_y_lo_guarda(test_db, hoy, monkeypatch):
    real = engine.get_daily_classification
    calls = []

    def spy(d=None):
        calls.append(d)
        return {**real(d), 'rank': {'2026-10-05': 'gold', '2026-10-06': 'diamond'}.get(d, 'iron')}
    monkeypatch.setattr(engine, 'get_daily_classification', spy)
    _log('2026-10-05'); _log('2026-10-06'); _log('2026-10-08')
    h = engine.classification_history(date(2026, 10, 4), date(2026, 10, 10))
    assert h == {'2026-10-04': 'carbon', '2026-10-05': 'gold', '2026-10-06': 'diamond',
                 '2026-10-07': 'carbon', '2026-10-08': 'iron'}     # sin registros = Carbón; futuro fuera
    assert sorted(calls) == ['2026-10-05', '2026-10-06', '2026-10-08']
    assert _cached() == {'2026-10-05': 'gold', '2026-10-06': 'diamond'}   # hoy no se guarda

    calls.clear()
    engine.classification_history(date(2026, 10, 4), date(2026, 10, 10))
    assert calls == ['2026-10-08']                                  # pasado sale del caché

    calls.clear()
    _log('2026-10-05', 'jugo_verde')                                # se editó un día pasado
    engine.classification_history(date(2026, 10, 4), date(2026, 10, 10))
    assert sorted(calls) == ['2026-10-05', '2026-10-08']


def test_heatmap_por_rango_y_conteos(test_db, hoy, monkeypatch):
    monkeypatch.setattr(engine, 'classification_history',
                        lambda a, b: {'2026-10-06': 'gold', '2026-10-07': 'diamond', '2026-10-08': 'iron',
                                      '2026-10-05': 'carbon'})
    h = dr._build_heat_16w()
    assert len(h['cells']) == 112
    by = {c['date']: c for c in h['cells']}
    assert by['2026-10-06']['rank'] == 'gold' and by['2026-10-06']['label'] == 'Oro'
    assert by['2026-10-08']['today'] and by['2026-10-09']['future'] and by['2026-10-09']['rank'] is None
    assert h['counts'] == {'carbon': 1, 'iron': 1, 'gold': 1, 'diamond': 1}
    assert [s['rank'] for s in h['stats']] == ['diamond', 'gold', 'iron', 'carbon']


@pytest.mark.parametrize('streak,texto,filled,maximo', [
    (0, '7 días más para +5% XP', 0, False),
    (6, '1 día más para +5% XP', 6, False),
    (7, '23 días más para +10% XP', 7, False),
    (29, '1 día más para +10% XP', 29, False),
    (30, 'Bonus máximo · +10%', 30, True),
    (45, 'Bonus máximo · +10%', 30, True),
])
def test_texto_de_la_racha(streak, texto, filled, maximo):
    s = dr._streak_next(streak)
    assert s['text'] == texto and s['filled'] == filled and s['max'] is maximo


def test_inicio_pinta_constancia_y_racha(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        html = c.get('/').get_data(as_text=True)
    assert 'Días por clasificación, no por XP' in html
    assert 'class="dash-heat-stats"' in html and '<dt class="t-meta">Diamante</dt>' in html
    assert 'dash-streak-pips' in html and 'si se rompe, conservas tu XP' in html
    assert 'Racha · ' not in html                    # la racha ya no se repite en Constancia
