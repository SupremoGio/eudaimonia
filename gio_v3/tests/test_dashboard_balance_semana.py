"""
test_dashboard_balance_semana.py — Sprint 3 de Inicio v2: regla del 60% por
virtud. engine.balance_week calcula XP de la semana por pilar, umbral (60%
del promedio de las 8) y bonus; el motor da +20% XP a esas virtudes y la
tarjeta «Equilibrio de la semana» de Inicio pinta lo mismo.
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.actividades.activity_defs as adefs
import modules.gamification.engine as engine

JUEVES = datetime.date(2026, 10, 8)          # semana: lunes 5 → jueves 8


@pytest.fixture
def hoy(monkeypatch):
    monkeypatch.setattr(engine, 'today_date', lambda: JUEVES)
    monkeypatch.setattr(engine, 'today_str', lambda: JUEVES.isoformat())
    return JUEVES


def _log(fecha, key, pts):
    with database.get_db() as db:
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)", (key, fecha, pts))
        db.commit()


def _def(pillar):
    """Una actividad activa del pilar (de las sembradas)."""
    for k, d in adefs.get_active_flat().items():
        if d['pillar'] == pillar:
            return k
    return adefs.create(f'Test {pillar}', pillar, 'touch', 'any', pts=2)['key']


def test_semana_sin_datos_no_hay_bonus(test_db, hoy):
    b = engine.balance_week(hoy)
    assert set(b['week']) == set(adefs.PILLAR_ORDER) and 'philia' in b['week']
    assert all(v == 0 for v in b['week'].values()) and b['bonus'] == set() and b['threshold'] == 0


def test_umbral_y_bonus(test_db, hoy):
    # 8 virtudes: logoi 40, hege 40, resto 0 → promedio 10, umbral 6.
    _log('2026-10-05', _def('logoi'), 40)
    _log('2026-10-08', _def('hege'), 40)
    _log('2026-10-08', _def('paideia'), 7)          # 7 ≥ 6 → sin bonus
    _log('2026-10-07', _def('philia'), 5)           # 5 < 6.6 → bonus
    _log('2026-10-04', _def('oiko'), 50)            # domingo anterior: no cuenta
    b = engine.balance_week(hoy)
    assert b['week']['logoi'] == 40 and b['week']['oiko'] == 0
    assert b['today']['hege'] == 40 and b['today']['logoi'] == 0
    assert b['avg'] == pytest.approx(92 / 8) and b['threshold'] == pytest.approx(92 / 8 * 0.6)
    assert 'paideia' not in b['bonus'] and 'philia' in b['bonus'] and 'oiko' in b['bonus']
    assert 'logoi' not in b['bonus']


def test_una_sola_virtud_no_da_bonus(test_db, hoy):
    _log('2026-10-06', _def('logoi'), 30)
    assert engine.balance_week(hoy)['bonus'] == set()


def test_motor_aplica_el_bonus_de_la_virtud(test_db, hoy):
    _log('2026-10-05', _def('logoi'), 40)
    _log('2026-10-06', _def('hege'), 40)
    assert engine._compute_xp_mult(None, 0, key=_def('paideia')) == pytest.approx(1.2)
    assert engine._compute_xp_mult(None, 0, key=_def('logoi')) == pytest.approx(1.0)
    assert engine._compute_xp_mult('Finanzas', 0) == pytest.approx(1.2)    # por categoría vieja → oiko
    assert engine._compute_xp_mult('Identidad', 0) == pytest.approx(1.0)   # sin virtud


def test_tarjeta_en_inicio(test_db, hoy, monkeypatch):
    import modules.dashboard.routes as dr
    _log('2026-10-05', _def('logoi'), 40)
    _log('2026-10-08', _def('hege'), 40)
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        html = c.get('/').get_data(as_text=True)
    assert 'Equilibrio de la semana' in html and 'Virtudes de hoy' not in html
    assert '6 con bonus' in html                        # las 6 virtudes en 0
    assert 'Philia' in html and 'Umbral 60% del promedio (6 XP)' in html
    assert '+40 hoy' in html and '40 XP' in html
