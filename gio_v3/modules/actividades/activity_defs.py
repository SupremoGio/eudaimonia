"""
Definiciones editables de Acta Diurna (tabla activity_defs) — sesión, pilar y
tipo (ancla/touch/ocasional) por actividad, con soporte de "foco del mes"
(pillar_focus) que promueve dinámicamente un touch a ancla sin tocar el dato base.
"""
import calendar
import re
import time
from datetime import date, timedelta
from database import get_db
from utils import today_str, today_date

SESSIONS = ("morning", "afternoon", "night", "any")
PILLARS  = ("logoi", "paideia", "cosmo", "hege", "eury", "atar", "oiko", "philia")
TYPES    = ("ancla", "touch", "ocasional")

# Presentación de cada pilar en la UI V2 (Acta Diurna, Dashboard): categoría
# de tokens.css (data-cat), nombre, función, ícono Lucide y a dónde lleva.
PILLAR_UI = {
    "logoi":   {"cat": "logoi",          "name": "Logoi",          "fn": "Programación", "icon": "code-2",          "url": "/actividades/"},
    "hege":    {"cat": "hegemonikon",    "name": "Hegemonikon",    "fn": "Salud",        "icon": "heart-pulse",     "url": "/bienestar/"},
    "paideia": {"cat": "paideia",        "name": "Paideia",        "fn": "Conocimiento", "icon": "book-open",       "url": "/paideia/"},
    "cosmo":   {"cat": "cosmopolitismo", "name": "Cosmopolitismo", "fn": "Idiomas",      "icon": "languages",       "url": "/idiomas/"},
    "oiko":    {"cat": "oikonomia",      "name": "Oikonomia",      "fn": "Finanzas",     "icon": "landmark",        "url": "/finanzas/"},
    "atar":    {"cat": "ataraxia",       "name": "Ataraxia",       "fn": "Orden",        "icon": "sun-dim",         "url": "/ataraxia/"},
    "eury":    {"cat": "eurythmia",      "name": "Eurythmia",      "fn": "Baile",        "icon": "music-2",         "url": "/eurythmia/"},
    "philia":  {"cat": "philia",         "name": "Philia",         "fn": "Vínculos",     "icon": "heart-handshake", "url": "/actividades/"},
}
PILLAR_ORDER = ("logoi", "hege", "paideia", "cosmo", "oiko", "atar", "eury", "philia")
CADENCES = ("daily", "weekly")
DAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def weekday_code(d=None):
    """mon/tue/.../sun para hoy (o la fecha dada) — locale-independiente,
    a diferencia de strftime('%a')."""
    d = d or today_date()
    return DAY_CODES[d.weekday()]


def eligible_today(row, wd=None, d=None):
    """True si el item no tiene restricciones de fecha, o si hoy (o la fecha
    dada) cumple su days_of_week (anclas semanales rotativas, Fase 3), su
    days_of_month (touches ligados a fechas del calendario, ej. cierre de
    mes — 'last' significa el último día real del mes) y su interval_weeks
    (touches que no son ni diarios ni semanales fijos, ej. "cada 3 semanas
    en domingo" — interval_anchor es la fecha de la 1ª aparición; solo es
    elegible si el día coincide con days_of_week Y cayó un múltiplo exacto
    de interval_weeks semanas después del ancla)."""
    d  = d or today_date()
    wd = wd or weekday_code(d)
    dow = row["days_of_week"]
    if dow and wd not in dow.split(","):
        return False
    dom = row["days_of_month"]
    if dom:
        last_day = calendar.monthrange(d.year, d.month)[1]
        allowed_days = {last_day if tok == "last" else int(tok) for tok in dom.split(",")}
        if d.day not in allowed_days:
            return False
    weeks = row["interval_weeks"]
    if weeks:
        anchor = date.fromisoformat(row["interval_anchor"])
        if d < anchor or (d - anchor).days % (weeks * 7) != 0:
            return False
    return True


# ── Día de partido ────────────────────────────────────────────────────────────
# Los miércoles el usuario suele jugar fútbol en vez de ir al gym: si ese día
# hay un partido en futbol_partidos (programado o jugado), Ejercicio Gym y
# GymBook no se piden y el partido toma su lugar como ancla (mismo pilar y
# puntos que el gym). Sin partido, la actividad del partido no aparece.
PARTIDO_KEY = "partido_futbol"
REEMPLAZADAS_POR_PARTIDO = ("gym", "gymbook")
DIAS_PARTIDO = ("wed",)


def partido_del_dia(d=None):
    """El partido de hoy (o de la fecha dada) si es día de partido, si no None."""
    d = d or today_date()
    if weekday_code(d) not in DIAS_PARTIDO:
        return None
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM futbol_partidos WHERE fecha=? ORDER BY hora, id LIMIT 1", (d.isoformat(),)
        ).fetchone()
    return dict(row) if row else None


def _sesion_por_hora(hora):
    try:
        h = int((hora or "").split(":")[0])
    except ValueError:
        return "afternoon"
    return "morning" if h < 13 else ("afternoon" if h < 19 else "night")


def ajustar_por_partido(items, d=None):
    """Aplica la regla del día de partido a una lista de actividades (dicts):
    con partido quita Gym/GymBook y rotula el ancla del partido (rival, hora y
    sesión según la hora); sin partido quita el ancla del partido."""
    p = partido_del_dia(d)
    out = []
    for it in items:
        if p and it["key"] in REEMPLAZADAS_POR_PARTIDO:
            continue
        if it["key"] == PARTIDO_KEY:
            if not p:
                continue
            it = dict(it)
            extra = " · ".join(x for x in (f"vs {p['rival']}" if p.get("rival") else "", p.get("hora") or "") if x)
            it["label"] = "Partido de fútbol" + (f" · {extra}" if extra else "")
            it["session"] = _sesion_por_hora(p.get("hora"))
        out.append(it)
    return out


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
    """Actividades activas, visibles (no ocultas) y elegibles hoy (respeta
    days_of_week de las anclas semanales rotativas), agrupadas por sesión.

    `session` normalmente es un solo valor, pero admite CSV (igual que
    days_of_week) para actividades que viven en más de una tarjeta a la vez
    (ej. "morning,afternoon,night") sin dejar de ser una sola actividad/key:
    se marca una vez y aparece "done" en cada sesión donde aparece."""
    focus_map = get_pillar_focus_map()
    wd = weekday_code()
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM activity_defs WHERE active=1 AND hidden=0 ORDER BY sort_order, label"
        ).fetchall()
    grouped = {s: [] for s in SESSIONS}
    occasional = []
    items = ajustar_por_partido([_as_dict(r, focus_map) for r in rows if eligible_today(r, wd)])
    for item in items:
        if item["type"] == "ocasional":
            occasional.append(item)
        else:
            for sess in (item["session"] or "").split(","):
                if sess in grouped:
                    grouped[sess].append(item)
    # Anclas (ya sean fijas o promovidas por el foco del mes) van primero en
    # cada tarjeta de sesión: como ocupan la fila completa (grid-column:1/-1),
    # dejarlas al frente evita que corten el empaquetado de 2 columnas de los
    # touches y que quede un hueco impar. Orden estable: preserva sort_order
    # dentro de cada grupo (anclas / touches).
    for sess in grouped:
        grouped[sess].sort(key=lambda it: 0 if it["effective_type"] == "ancla" else 1)

    grouped["ocasional"] = occasional
    return grouped


def get_week_counts(keys):
    """Cuántas veces se registró cada key (lista) en la semana actual (lunes–hoy).
    Usado por items cadence='weekly' para mostrar progreso ("2/semana") sin
    cambiar la semántica del checkbox, que sigue siendo 'hoy'."""
    if not keys:
        return {}
    _today = today_date()
    week_start = (_today - timedelta(days=_today.weekday())).isoformat()
    with get_db() as db:
        rows = db.execute(
            f"""SELECT activity_key, COUNT(*) as c FROM activity_logs
                WHERE date>=? AND date<=? AND activity_key IN ({",".join("?"*len(keys))})
                GROUP BY activity_key""",
            (week_start, today_str(), *keys)
        ).fetchall()
    return {r["activity_key"]: r["c"] for r in rows}


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


def create(label, pillar, type_="touch", session=None, pts=1, ec=0, cat="", tier="micro",
           one_time=False, days_of_week=None):
    if pillar not in PILLARS:
        raise ValueError(f"pilar inválido: {pillar}")
    if type_ not in TYPES:
        raise ValueError(f"tipo inválido: {type_}")
    if type_ != "ocasional" and session not in SESSIONS:
        raise ValueError("sesión requerida para actividades touch/ancla")

    if isinstance(days_of_week, (list, tuple)):
        days_of_week = ",".join(days_of_week)
    days_of_week = days_of_week or None
    if days_of_week:
        codes = days_of_week.split(",")
        if any(c not in DAY_CODES for c in codes):
            raise ValueError("days_of_week inválido")
    one_time = bool(one_time)
    if one_time:
        days_of_week = None

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
               (key, label, cat, pts, ec, tier, session, pillar, type, active, hidden, custom, sort_order,
                one_time, days_of_week)
               VALUES (?,?,?,?,?,?,?,?,?,1,0,1,?,?,?)""",
            (key, label.strip(), cat, pts, ec, tier, session, pillar, type_, max_sort + 1,
             int(one_time), days_of_week)
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
