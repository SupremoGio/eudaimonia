"""
test_clasificacion_criterios.py — Sprint 1 de Inicio v2: get_daily_classification()
entrega `next_rank` y `criteria` [{key, label, hint, have, need, ok}] con lo que
falta para el siguiente rango (descuento por ancla extra y semana de descarga
incluidos). El héroe de Inicio los pinta tal cual.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.actividades.activity_defs as adefs
import modules.gamification.engine as engine

LUNES = '2026-10-05'     # semana 1 → no es semana de descarga
JUEVES_DESCARGA = '2026-10-22'   # semana 4 del mes → semana de descarga


def _solo(*defs):
    with database.get_db() as db:
        db.execute("UPDATE activity_defs SET active=0")
        db.execute("DELETE FROM pillar_focus")
        db.commit()
    return [adefs.create(label, pillar, type_, session, pts=3)["key"] for label, pillar, type_, session in defs]


def _log(fecha, *keys):
    with database.get_db() as db:
        for k in keys:
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,1)", (k, fecha))
        db.commit()


ANCLAS = [("CCNA", "logoi", "ancla", "morning"), ("Inglés", "cosmo", "ancla", "night"),
          ("Gym", "hege", "ancla", "afternoon"), ("Lectura", "paideia", "ancla", "night")]
TOUCHES = [("T mañana hege", "hege", "touch", "morning"), ("T mañana atar", "atar", "touch", "morning"),
           ("T tarde oiko", "oiko", "touch", "afternoon"), ("T tarde atar", "atar", "touch", "afternoon"),
           ("T noche philia", "philia", "touch", "night"), ("T noche hege", "hege", "touch", "night")]


def _dia(n_anclas=4):
    keys = _solo(*ANCLAS[:n_anclas], *TOUCHES)
    return keys[:n_anclas], keys[n_anclas:]


def _crit(c):
    return {x["key"]: (x["have"], x["need"], x["ok"]) for x in c["criteria"]}


def test_carbon_pide_una_ancla(test_db):
    _dia()
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "carbon" and c["next_rank"] == "iron"
    assert _crit(c) == {"anchor": (0, 1, False)}
    assert c["criteria"][0]["label"] == "Una ancla completa"
    assert "versión mínima" in c["criteria"][0]["hint"]
    assert c["next_hint"]   # se conserva por compatibilidad


def test_hierro_pide_touches_sesiones_y_pilares(test_db):
    anclas, t = _dia()
    _log(LUNES, anclas[0], t[0], t[1])          # 2 touches, solo mañana, 2 pilares
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "iron" and c["next_rank"] == "gold"
    assert _crit(c) == {"touches": (2, 5, False), "sessions": (1, 3, False), "pillars": (2, 2, True)}
    assert c["criteria"][0]["hint"] == "5 base − 1 por cada ancla extra"


@pytest.mark.parametrize("extra,touches_need,sessions_need", [(0, 5, 3), (1, 4, 2), (2, 3, 1), (3, 2, 1)])
def test_anclas_extra_descuentan(test_db, extra, touches_need, sessions_need):
    anclas, t = _dia()
    _log(LUNES, *anclas[:1 + extra], t[0])
    c = engine.get_daily_classification(LUNES)
    if c["rank"] != "iron":
        pytest.skip("con estas anclas el día ya no es Hierro")
    crit = _crit(c)
    assert crit["touches"][1] == touches_need
    assert crit["sessions"][1] == sessions_need
    if extra:
        assert f"− {extra} por tu" in c["criteria"][0]["hint"]


def test_oro_pide_75_por_ciento_de_anclas(test_db):
    anclas, t = _dia()
    _log(LUNES, anclas[0], *t)                   # todos los touches → Oro con 1/4 anclas
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "gold" and c["next_rank"] == "diamond"
    assert _crit(c) == {"anchors_pct": (1, 3, False)}
    assert c["criteria"][0]["hint"] == "75% de 4, redondeo arriba"


def test_oro_con_dos_anclas_pide_todas(test_db):
    anclas, t = _dia(2)
    _log(LUNES, anclas[0], *t)
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "gold"
    assert _crit(c) == {"anchors_pct": (1, 2, False)} and c["criteria"][0]["hint"] == "todas"


def test_diamante_sin_criterios(test_db):
    anclas, t = _dia()
    _log(LUNES, *anclas[:3], *t)
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "diamond" and c["next_rank"] is None and c["criteria"] == []


def test_semana_de_descarga_usa_sus_metas(test_db):
    anclas, t = _dia()
    c = engine.get_daily_classification(JUEVES_DESCARGA)
    assert c["rank"] == "carbon" and "semana de descarga" in c["criteria"][0]["hint"]
    _log(JUEVES_DESCARGA, anclas[0], t[0])
    c = engine.get_daily_classification(JUEVES_DESCARGA)
    assert c["rank"] == "iron"
    crit = _crit(c)
    assert crit["touches"] == (1, 3, False) and crit["sessions"] == (1, 2, False)
    assert "semana de descarga" in c["criteria"][0]["hint"]


def test_criterios_cumplidos_coinciden_con_el_rango(test_db):
    """Si todos los criterios de Hierro → Oro están ok, el rango ya es Oro."""
    anclas, t = _dia()
    for i in range(len(t)):
        _log(LUNES, *([anclas[0]] if i == 0 else []), t[i])
        c = engine.get_daily_classification(LUNES)
        if c["rank"] == "iron":
            assert not all(x["ok"] for x in c["criteria"])


def test_endpoint_expone_criterios(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    _dia()
    with app.test_client() as cl:
        with cl.session_transaction() as s:
            s['app_ok'] = True
        d = cl.get(f'/api/gamification/classification?date={LUNES}').get_json()
    assert d["next_rank"] == "iron" and d["criteria"][0]["key"] == "anchor"
