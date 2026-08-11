"""
Definiciones editables de Acta Diurna (tabla activity_defs) — sesión, pilar y
tipo (ancla/touch/ocasional) por actividad, con soporte de "foco del mes"
(pillar_focus) que promueve dinámicamente un touch a ancla sin tocar el dato base.
"""
import re
import time
from database import get_db

SESSIONS = ("morning", "afternoon", "night", "any")
PILLARS  = ("logoi", "paideia", "cosmo", "hege", "eury", "atar", "oiko")
TYPES    = ("ancla", "touch", "ocasional")


def _slugify(label):
    base = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return base or "actividad"


def get_pillar_focus_map():
    with get_db() as db:
        rows = db.execute(
            "SELECT pillar, focus_key FROM pillar_focus WHERE focus_key IS NOT NULL"
        ).fetchall()
    return {r["pillar"]: r["focus_key"] for r in rows}


def set_pillar_focus(pillar, focus_key):
    if pillar not in PILLARS:
        raise ValueError(f"pilar inválido: {pillar}")
    with get_db() as db:
        if focus_key:
            row = db.execute(
                "SELECT key FROM activity_defs WHERE key=? AND pillar=? AND active=1",
                (focus_key, pillar)
            ).fetchone()
            if not row:
                raise ValueError("la actividad no pertenece a ese pilar o no está activa")
        db.execute(
            """INSERT INTO pillar_focus (pillar, focus_key, updated_at) VALUES (?,?,datetime('now'))
               ON CONFLICT(pillar) DO UPDATE SET focus_key=excluded.focus_key, updated_at=excluded.updated_at""",
            (pillar, focus_key)
        )
        db.commit()


def _effective_type(row, focus_map):
    if row["type"] == "ancla":
        return "ancla"
    if row["type"] == "touch" and focus_map.get(row["pillar"]) == row["key"]:
        return "ancla"
    return row["type"]


def _as_dict(row, focus_map):
    d = dict(row)
    d["effective_type"] = _effective_type(row, focus_map)
    return d


def get_active_grouped():
    """Actividades activas, visibles (no ocultas), agrupadas por sesión + ocasional."""
    focus_map = get_pillar_focus_map()
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM activity_defs WHERE active=1 AND hidden=0 ORDER BY sort_order, label"
        ).fetchall()
    grouped = {s: [] for s in SESSIONS}
    occasional = []
    for r in rows:
        item = _as_dict(r, focus_map)
        if item["type"] == "ocasional":
            occasional.append(item)
        elif item["session"] in grouped:
            grouped[item["session"]].append(item)
    grouped["ocasional"] = occasional
    return grouped


def get_active_flat():
    """key -> dict, todas las activas (incluye ocultas como gbm) — para validar logs."""
    focus_map = get_pillar_focus_map()
    with get_db() as db:
        rows = db.execute("SELECT * FROM activity_defs WHERE active=1").fetchall()
    return {r["key"]: _as_dict(r, focus_map) for r in rows}


def get_by_key(key):
    with get_db() as db:
        row = db.execute("SELECT * FROM activity_defs WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    return _as_dict(row, get_pillar_focus_map())


def create(label, pillar, type_="touch", session=None, pts=1, ec=0, cat="", tier="micro"):
    if pillar not in PILLARS:
        raise ValueError(f"pilar inválido: {pillar}")
    if type_ not in TYPES:
        raise ValueError(f"tipo inválido: {type_}")
    if type_ != "ocasional" and session not in SESSIONS:
        raise ValueError("sesión requerida para actividades touch/ancla")

    base_key = "custom_" + _slugify(label)
    key = base_key
    with get_db() as db:
        suffix = 1
        while db.execute("SELECT 1 FROM activity_defs WHERE key=?", (key,)).fetchone():
            suffix += 1
            key = f"{base_key}_{suffix}"

        max_sort = db.execute(
            "SELECT COALESCE(MAX(sort_order),0) as m FROM activity_defs WHERE session IS ?",
            (session,)
        ).fetchone()["m"]

        db.execute(
            """INSERT INTO activity_defs
               (key, label, cat, pts, ec, tier, session, pillar, type, active, hidden, custom, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,1,0,1,?)""",
            (key, label.strip(), cat, pts, ec, tier, session, pillar, type_, max_sort + 1)
        )
        db.commit()
    return get_by_key(key)


def update(key, **fields):
    allowed = {"label", "cat", "pts", "ec", "tier", "session", "pillar", "type"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return get_by_key(key)
    with get_db() as db:
        cols = ", ".join(f"{c}=?" for c in sets)
        db.execute(f"UPDATE activity_defs SET {cols} WHERE key=?", (*sets.values(), key))
        db.commit()
    return get_by_key(key)


def deactivate(key):
    """Soft delete: se quita del checklist pero el historial en activity_logs queda intacto."""
    with get_db() as db:
        db.execute("UPDATE activity_defs SET active=0 WHERE key=?", (key,))
        db.commit()
