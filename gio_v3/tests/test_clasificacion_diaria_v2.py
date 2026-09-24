"""
test_clasificacion_diaria_v2.py — tres ajustes a la clasificación diaria
(modules/gamification/engine.py, get_daily_classification):

  1. Ancla mínima: registrar la versión mínima de un ancla (`<key>__min`)
     da Hierro, pero no cuenta como ancla hecha para Oro ni Diamante.
  2. Diamante proporcional: basta el 75% de las anclas de hoy (redondeo
     arriba, piso de 2) en vez de todas.
  3. Oro exige touches de al menos 2 pilares distintos.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.actividades.activity_defs as adefs
import modules.gamification.engine as engine
from utils import today_str

LUNES = '2026-10-05'   # semana 1 del mes → no es semana de descarga, no es día de partido


def _solo(*defs):
    """Deja activas solo las actividades dadas: (label, pillar, type, session)."""
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


def _touches(pillars_sessions):
    return [(f"Touch {i}", p, "touch", s) for i, (p, s) in enumerate(pillars_sessions)]


# ── 1. Ancla mínima ──────────────────────────────────────────────────────────

def test_ancla_minima_da_hierro(test_db):
    ancla, = _solo(("CCNA", "logoi", "ancla", "morning"))
    assert engine.get_daily_classification(LUNES)["rank"] == "carbon"
    _log(LUNES, ancla + engine.ANCLA_MIN_SUFFIX)
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] in ("iron", "gold") and c["rank"] != "diamond"
    assert c["anchors_min"] == [ancla]
    assert c["anchors_done"] == 0


def test_ancla_minima_no_cuenta_para_diamante(test_db):
    ancla, = _solo(("CCNA", "logoi", "ancla", "morning"))
    _log(LUNES, ancla + engine.ANCLA_MIN_SUFFIX)
    # Sin touches definidos, Hierro → Oro directo; Diamante sigue pidiendo el ancla completa.
    assert engine.get_daily_classification(LUNES)["rank"] == "gold"
    _log(LUNES, ancla)
    assert engine.get_daily_classification(LUNES)["rank"] == "diamond"


def test_ancla_minima_no_descuenta_meta_de_oro(test_db):
    keys = _solo(("CCNA", "logoi", "ancla", "morning"), ("Inglés", "cosmo", "ancla", "night"),
                 *_touches([("hege", "morning"), ("atar", "afternoon"), ("oiko", "night"),
                            ("paideia", "morning"), ("philia", "afternoon")]))
    a1, a2, t = keys[0], keys[1], keys[2:]
    # Ancla completa + mínima de la otra: la mínima NO es ancla extra, sigue pidiendo 5 touches.
    _log(LUNES, a1, a2 + engine.ANCLA_MIN_SUFFIX, *t[:4])
    assert engine.get_daily_classification(LUNES)["rank"] == "iron"


def test_ancla_minima_de_otro_dia_no_cuenta(test_db):
    ancla = adefs.create("Francés", "cosmo", "ancla", "morning", days_of_week="fri")["key"]
    with database.get_db() as db:
        db.execute("UPDATE activity_defs SET active=0 WHERE key!=?", (ancla,))
        db.execute("DELETE FROM pillar_focus")
        db.commit()
    otra, = [adefs.create("CCNA", "logoi", "ancla", "morning")["key"]]
    _log(LUNES, ancla + engine.ANCLA_MIN_SUFFIX)   # Francés es de viernes, hoy es lunes
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "carbon" and c["anchors_min"] == []
    assert "versión mínima" in c["next_hint"]
    _log(LUNES, otra + engine.ANCLA_MIN_SUFFIX)
    assert engine.get_daily_classification(LUNES)["rank"] != "carbon"


# ── 2. Diamante proporcional ─────────────────────────────────────────────────

@pytest.mark.parametrize("n,needed", [(0, 0), (1, 1), (2, 2), (3, 3), (4, 3), (5, 4), (8, 6)])
def test_diamond_min_anchors(n, needed):
    assert engine._diamond_min_anchors(n) == needed


def test_tres_de_cuatro_anclas_da_diamante(test_db):
    keys = _solo(*[(f"Ancla {i}", p, "ancla", "morning")
                   for i, p in enumerate(("logoi", "cosmo", "paideia", "hege"))])
    _log(LUNES, *keys[:2])
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "gold" and c["diamond_min_anchors"] == 3
    assert c["next_hint"].startswith("Completa 1 ancla más (")
    assert c["next_pct"] == 67
    _log(LUNES, keys[2])
    assert engine.get_daily_classification(LUNES)["rank"] == "diamond"


def test_dos_anclas_siguen_pidiendo_ambas(test_db):
    keys = _solo(("CCNA", "logoi", "ancla", "morning"), ("Inglés", "cosmo", "ancla", "night"))
    _log(LUNES, keys[0])
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "gold"
    assert c["next_hint"] == "Completa Inglés → Diamante"


# ── 3. Oro con al menos 2 pilares ────────────────────────────────────────────

def test_oro_exige_dos_pilares(test_db):
    keys = _solo(("CCNA", "logoi", "ancla", "morning"),
                 *_touches([("hege", "morning"), ("hege", "afternoon"), ("hege", "night"),
                            ("hege", "any"), ("hege", "morning"), ("atar", "night")]))
    ancla, hege, atar = keys[0], keys[1:6], keys[6]
    _log(LUNES, ancla, *hege)       # 5 touches, 4 sesiones, pero todo de Hegemonikon
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "iron"
    assert c["pillars_covered"] == 1 and c["pillars_min"] == 2
    assert c["next_hint"] == "Suma un touch de otro pilar → Oro"
    assert c["next_pct"] == 50
    _log(LUNES, atar)
    assert engine.get_daily_classification(LUNES)["rank"] == "diamond"


def test_un_solo_pilar_disponible_no_bloquea_oro(test_db):
    keys = _solo(("CCNA", "logoi", "ancla", "morning"),
                 *_touches([("hege", "morning"), ("hege", "afternoon"), ("hege", "night"),
                            ("hege", "any"), ("hege", "morning")]))
    _log(LUNES, *keys)
    c = engine.get_daily_classification(LUNES)
    assert c["pillars_min"] == 1 and c["rank"] == "diamond"


def test_hint_combina_touches_sesiones_y_pilares(test_db):
    keys = _solo(("CCNA", "logoi", "ancla", "morning"),
                 *_touches([("hege", "morning"), ("atar", "afternoon"), ("oiko", "night"),
                            ("hege", "morning"), ("hege", "morning")]))
    _log(LUNES, keys[0], keys[1])
    c = engine.get_daily_classification(LUNES)
    assert c["rank"] == "iron"
    assert c["next_hint"] == "Registra 4 touches en 2+ pilares y toca Tarde y Noche → Oro"


# ── Endpoint: versión mínima desde Acta Diurna ───────────────────────────────

@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False   # el fetch del layout manda el token en el navegador
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
        yield c


def _keys_hoy():
    with database.get_db() as db:
        return [r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=?", (today_str(),)).fetchall()]


def _xp_hoy():
    # Solo XP de actividades: los logros que se desbloquean al registrar
    # (source='achievement') no se revierten al desmarcar, igual que siempre.
    with database.get_db() as db:
        return db.execute("SELECT COALESCE(SUM(amount),0) s FROM xp_ledger WHERE date=? AND source='activity'",
                          (today_str(),)).fetchone()["s"]


def test_endpoint_minima_registra_y_da_hierro(client):
    ancla, = _solo(("CCNA", "logoi", "ancla", "morning"))
    r = client.post("/actividades/api/activity/log", json={"key": ancla, "minimal": True}).get_json()
    assert r["action"] == "added" and r["minimal"] is True and r["ec"] == 0
    assert _keys_hoy() == [ancla + engine.ANCLA_MIN_SUFFIX]
    assert engine.get_daily_classification(today_str())["rank"] != "carbon"
    # Segundo click la quita
    r = client.post("/actividades/api/activity/log", json={"key": ancla, "minimal": True}).get_json()
    assert r["action"] == "removed" and _keys_hoy() == [] and _xp_hoy() == 0


def test_endpoint_ancla_completa_reemplaza_la_minima(client):
    ancla, = _solo(("CCNA", "logoi", "ancla", "morning"))
    client.post("/actividades/api/activity/log", json={"key": ancla, "minimal": True})
    xp_min = _xp_hoy()
    r = client.post("/actividades/api/activity/log", json={"key": ancla}).get_json()
    assert r["action"] == "added" and r["replaced_min"] is True
    assert _keys_hoy() == [ancla]
    assert _xp_hoy() == r["xp"] > xp_min          # no se suman los dos XP
    # Con el ancla completa ya registrada, la mínima se rechaza
    resp = client.post("/actividades/api/activity/log", json={"key": ancla, "minimal": True})
    assert resp.status_code == 400 and "completa" in resp.get_json()["error"]


def test_endpoint_minima_solo_para_anclas(client):
    touch, = _solo(("Agua", "hege", "touch", "morning"))
    resp = client.post("/actividades/api/activity/log", json={"key": touch, "minimal": True})
    assert resp.status_code == 400 and "anclas" in resp.get_json()["error"] and _keys_hoy() == []
