"""
test_dashboard_siguiente_paso.py — el «Siguiente paso» de Inicio sugiere lo
que de verdad acerca al siguiente rango (clf.criteria), no solo «lo que cierra
una categoría vieja»: el ancla en Carbón, el touch que cubre la sesión o el
pilar que falta en Hierro, un ancla más en Oro.
"""
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.actividades.activity_defs as adefs
import modules.gamification.engine as engine
from modules.dashboard import routes as dr

LUNES = date(2026, 10, 5)


@pytest.fixture
def tarde(monkeypatch):
    monkeypatch.setattr(dr, 'today_date', lambda: LUNES)
    monkeypatch.setattr(dr, 'now_local', lambda: datetime(2026, 10, 5, 16, 0))
    monkeypatch.setattr(adefs, 'today_date', lambda: LUNES)
    return LUNES


def _solo(*defs):
    with database.get_db() as db:
        db.execute("UPDATE activity_defs SET active=0")
        db.execute("DELETE FROM pillar_focus")
        db.commit()
    return [adefs.create(label, pillar, type_, session, pts=2)["key"] for label, pillar, type_, session in defs]


def _clf(rank, **crit):
    return {'rank': rank, 'criteria': [{'key': k, 'have': h, 'need': n, 'ok': h >= n} for k, (h, n) in crit.items()]}


def test_carbon_sugiere_el_ancla(test_db, tarde):
    a, t = _solo(("CCNA", "logoi", "ancla", "afternoon"), ("Jugo verde", "hege", "touch", "morning"))
    s = dr._build_next_step(set(), _clf('carbon', anchor=(0, 1)))
    assert s['key'] == a and s['why'] == 'cierra Hierro' and s['cat_ui'] == 'logoi'


def test_hierro_prefiere_el_touch_que_cubre_lo_que_falta(test_db, tarde):
    keys = _solo(("Ancla", "logoi", "ancla", "morning"),
                 ("Mañana hege", "hege", "touch", "morning"),
                 ("Tarde hege", "hege", "touch", "afternoon"),
                 ("Tarde atar", "atar", "touch", "afternoon"),
                 ("Mañana atar", "atar", "touch", "morning"))
    ancla, m_hege, t_hege, t_atar, m_atar = keys
    hechos = {ancla, m_hege}
    # Falta sesión y pilar: «Tarde atar» cubre las dos cosas (y es de la tarde, ahora).
    s = dr._build_next_step(hechos, _clf('iron', touches=(1, 5), sessions=(1, 3), pillars=(1, 2)))
    assert s['key'] == t_atar and s['why'] == 'suma 1 touch, cubre la tarde y suma un pilar nuevo'
    # Solo falta volumen: cualquier touch de ahora sirve.
    s = dr._build_next_step(hechos, _clf('iron', touches=(4, 5), sessions=(3, 3), pillars=(2, 2)))
    assert s['why'] == 'suma 1 touch' and s['key'] in (t_hege, t_atar)


def test_oro_sugiere_otra_ancla_y_diamante_nada(test_db, tarde):
    a1, a2 = _solo(("CCNA", "logoi", "ancla", "morning"), ("Inglés", "cosmo", "ancla", "night"))
    s = dr._build_next_step({a1}, _clf('gold', anchors_pct=(1, 2)))
    assert s['key'] == a2 and s['why'] == 'suma 1 ancla para Diamante'
    assert dr._build_next_step({a1, a2}, _clf('diamond')) is None
    assert dr._build_next_step({a1, a2}, _clf('gold', anchors_pct=(2, 2))) is None   # nada pendiente


def test_inicio_muestra_el_porque(test_db, tarde, monkeypatch):
    a, = _solo(("CCNA", "logoi", "ancla", "afternoon"))
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        html = c.get('/').get_data(as_text=True)
    assert 'CCNA <span>· cierra Hierro</span>' in html and 'data-cat="logoi"' in html
