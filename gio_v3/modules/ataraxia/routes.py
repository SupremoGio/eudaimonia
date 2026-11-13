from flask import Blueprint, render_template, request, jsonify
from datetime import date, timedelta, datetime
import os
import re
from database import get_db
from data import ACTIVITIES
from utils import today_str, today_date, clean_str
import modules.gamification.engine as engine
import modules.gtd.prioridades as prio

ataraxia_bp = Blueprint('ataraxia', __name__, template_folder='../../templates')

# Algunas tareas de rutina_bloques traían un emoji sembrado al inicio del
# nombre (dato histórico en la tabla, no en código). migrations/migrate_
# strip_emoji_rutina.py limpia el dato de verdad; este strip se deja como
# red de seguridad idempotente (no-op sobre datos ya migrados) para
# instalaciones donde esa migración todavía no se haya corrido.
_EMOJI_PREFIX_RE = re.compile(r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF]️?\s*')


def _strip_emoji_prefix(nombre):
    return _EMOJI_PREFIX_RE.sub('', nombre)

# ── Bloque display labels (from ACTIVITIES dict) ──────────────────────────────
BLOQUE_LABELS = {k: v["label"] for k, v in ACTIVITIES.items() if v.get("weekend")}

# ── Reference horarios ────────────────────────────────────────────────────────
HORARIOS = {
    # ── SÁBADO ──────────────────────────────────────────────────────────────
    "sat_ventilacion":  "Mañana · 5 min",
    "sat_nespresso":    "Mañana · 10 min",
    "sat_cocina_r":     "Mañana · 10 min",
    "sat_despensa":     "Mañana · 20 min",
    "sat_carga1":       "Antes del gym",
    "sat_robot_sala":   "Mañana · 5 min",
    "sat_robot_cuarto": "Mañana · 5 min",
    "sat_basura":       "Mañana · 5 min",
    "sat_bano_vidrio":  "Tarde · 4 min",
    "sat_bano_espejo":  "Tarde · 3 min",
    "sat_bano_lavabo":  "Tarde · 4 min",
    "sat_bano_wc":      "Tarde · 5 min",
    "sat_bano_repisa":  "Tarde · 3 min",
    "sat_bano_trapear": "Tarde · 6 min",
    "sat_gym":          "12:30 – 2:00 PM",
    "sat_textiles_r":   "Tarde",
    "sat_limpieza_escritorio": "Tarde · 4 min",
    "sat_limpieza_buro":       "Tarde · 3 min",
    "sat_limpieza_mesa":       "Tarde · 3 min",
    "sat_limpieza_microondas": "Tarde · 4 min",
    "sat_limpieza_cocina":     "Tarde · 8 min",
    "sat_trapear_sala":   "Tarde · 7 min",
    "sat_trapear_cuarto": "Tarde · 7 min",
    "sat_trapear_bano":   "Tarde · 6 min",
    "sat_jugos_r":      "Tarde · 30 min (opcional)",
    # ── DOMINGO ─────────────────────────────────────────────────────────────
    "sun_cafe":              "8:00 AM",
    "sun_cafe_agua":         "Mañana · 2 min",
    "sun_cafe_carro":        "Mañana · 2 min",
    "sun_cafe_audifonos":    "Mañana · 1 min",
    "sun_cafe_aspiradora":   "Mañana · 2 min",
    "sun_cafe_pila":         "Mañana · 2 min",
    "sun_gym":          "9:30 – 11:00 AM",
    "sun_nevera":       "Tarde",
    "sun_comidas":      "Tarde · 1 hora",
    "sun_guardado":     "Tarde",
    "sun_planchar":     "Tarde · 20 min",
    "sun_planeacion":   "10:30 – 11:15 AM",
    "sun_prioridades":  "Dentro de planeación",
    "sun_cierre":       "5:30 – 6:00 PM",
}

# ── Bloque icons (nombres lucide, ver templates/ataraxia/index.html) ──────────
BLOQUE_ICONS = {
    # SÁBADO
    "sat_bloque1":           "house",
    "sat_gym_bloque":        "dumbbell",
    "sat_textiles_bloque":   "shirt",
    "sat_limpieza_bloque":   "spray-can",
    "sat_bano_bloque":       "shower-head",
    "sat_barrido_bloque":    "wind",
    "sat_jugos_bloque":      "cup-soda",
    # DOMINGO
    "sun_cafe_bloque":       "coffee",
    "sun_gym_bloque":        "dumbbell",
    "sun_nevera_bloque":     "refrigerator",
    "sun_comidas_bloque":    "utensils",
    "sun_guardado_bloque":   "shirt",
    "sun_planchar_bloque":   "shirt",
    "sun_planeacion_bloque": "calendar",
    "sun_prioridades_bloque":"target",
    "sun_cierre_bloque":     "check-circle",
}


# ── Semana ID — starts Saturday ───────────────────────────────────────────────

def get_semana_id():
    hoy = today_date()
    dias_desde_sabado = (hoy.weekday() - 5) % 7
    sabado = hoy - timedelta(days=dias_desde_sabado)
    return sabado.isoformat()


# ── Revisión Semanal Objetiva ─────────────────────────────────────────────────
# Métricas de entrada manual (sin integración automática con Apple Health,
# Kindle ni redes sociales) — cada una declara su dirección "mejor" para
# poder colorear el delta contra la semana anterior sin subjetividad.

REVISION_METRICS = [
    # Las 6 que la app sabe (handoff Revisión, nota 3) — si su consulta
    # falla, se capturan a mano como las demás.
    {"key": "presupuesto_pct",   "label": "Presupuesto usado",   "unit": "%",      "icon": "landmark",    "direction": "down", "step": "any", "min": "0", "max": "300",  "placeholder": "85"},
    {"key": "dias_lectura",      "label": "Días de lectura",     "unit": "de 7",   "icon": "book-open",   "direction": "up",   "step": "1",   "min": "0", "max": "7",    "placeholder": "0–7"},
    {"key": "min_baile",         "label": "Baile",               "unit": "min",    "icon": "music-2",     "direction": "up",   "step": "1",   "min": "0", "max": "3000", "placeholder": "120"},
    {"key": "dias_limpios",      "label": "Días limpios",        "unit": "de 7",   "icon": "salad",       "direction": "up",   "step": "1",   "min": "0", "max": "7",    "placeholder": "0–7"},
    {"key": "peso",              "label": "Peso",                "unit": "kg",     "icon": "scale",       "direction": "down", "step": "any", "min": "0", "max": "400",  "placeholder": "78.4"},
    {"key": "racha_anclas",      "label": "Racha de anclas",     "unit": "días",   "icon": "flame",       "direction": "up",   "step": "1",   "min": "0", "max": "3650", "placeholder": "0"},
    # Las que solo tú sabes.
    {"key": "horas_sueno",       "label": "Sueño promedio",      "unit": "h/noche","icon": "moon",        "direction": "up",   "step": "any", "min": "0", "max": "12",   "placeholder": "7.5"},
    {"key": "pasos_promedio",    "label": "Pasos promedio",      "unit": "pasos/d","icon": "footprints",  "direction": "up",   "step": "1",   "min": "0", "max": "30000","placeholder": "8000"},
    {"key": "screen_time_horas", "label": "Pantalla en redes",   "unit": "h/día",  "icon": "smartphone",  "direction": "down", "step": "any", "min": "0", "max": "12",   "placeholder": "1.5"},
]
# calorias_quemadas ya no se pide (handoff Revisión): la columna se queda con
# el histórico y Logros › Semanas la sigue mostrando.
_REVISION_KEYS = [m["key"] for m in REVISION_METRICS]


def _prev_semana_id(semana_id):
    d = date.fromisoformat(semana_id)
    return (d - timedelta(days=7)).isoformat()


def _get_revision_row(semana_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM revision_semanal WHERE semana_id=?", (semana_id,)).fetchone()
    return dict(row) if row else None


def _fmt_num(v):
    if v is None:
        return ""
    return str(int(v)) if v == int(v) else str(v)


# ── Análisis de Élite ──────────────────────────────────────────────────────────
# Lectura cuantitativa de la semana: combina el rango semanal ya calculado por
# el motor de gamificación (get_weekly_classification) con las métricas de
# bienestar de esta misma Revisión Semanal, y entrega un veredicto + plan de
# acción concreto para la siguiente — el mismo ritmo semana-a-semana del
# sistema de niveles (~52 semanas/año, ver engine.LEVEL_THRESHOLDS), pero
# aterrizado en "qué hago distinto la próxima semana" en vez de solo XP.
# Todo es determinista (sin IA) para que el "veredicto" sea 100% trazable a
# los datos — cuantitativo de verdad, no una narrativa inventada.
_RANK_ORDER = ["carbon", "iron", "gold", "diamond"]

_VERDICT_COPY = {
    "diamond": {
        "title": "Semana ÉLITE — Diamante",
        "body":  "La mayoría de tus días fueron Oro o Diamante: es exactamente el nivel de consistencia que compone. Sostenlo unas semanas más y deja de sentirse como esfuerzo — se vuelve identidad.",
    },
    "gold": {
        "title": "Semana sólida — Oro",
        "body":  "Cumpliste tus anclas con constancia y sumaste volumen real de touches. Lo que te separa de Diamante no es más esfuerzo, es cobertura: cerrar el 100% de tus anclas los días que ya estás en Oro.",
    },
    "iron": {
        "title": "Semana base — Hierro",
        "body":  "Completaste el mínimo casi todos los días, pero sin profundidad. Esto mantiene la racha viva — no construye margen. El salto a Oro está en repartir touches a lo largo del día, no en sumar más anclas.",
    },
    "carbon": {
        "title": "Semana de alerta — Carbón",
        "body":  "La mayoría de los días no llegaste ni a tu ancla mínima. Antes de pensar en Oro o Diamante, la única prioridad real es asegurar Hierro todos los días de la próxima semana.",
    },
}

_WELLNESS_ABS_FLAGS = [
    ("horas_sueno",       lambda v: v < 7,    lambda v: f"Sueño promedio de {v:g}h — bajo el mínimo de 7h. Es la palanca con más impacto directo en tu rendimiento diario."),
    ("screen_time_horas", lambda v: v >= 3.5, lambda v: f"Pantalla en redes en {v:g}h/día — por encima del umbral de tu propio sistema de badges (3.5h). Compite directo con tus touches."),
    ("presupuesto_pct",   lambda v: v > 100,  lambda v: f"Te pasaste del presupuesto semanal ({v:g}%). Revísalo en Finanzas antes de que se acumule."),
    ("dias_lectura",      lambda v: v == 0,   lambda v: "Cero días de lectura esta semana — la primera métrica que se cae cuando la semana se pone pesada."),
    ("pasos_promedio",    lambda v: v < 5000, lambda v: f"Pasos promedio de {v:,.0f}/día — por debajo del umbral sedentario (5,000). Súmalos con caminatas cortas repartidas, no una sola sesión larga."),
]


def _week_num_of(monday_id):
    return date.fromisoformat(monday_id).isocalendar()[1]


def _best_worst_day(days):
    evaluated = [d for d in days if not d["future"]]
    if not evaluated:
        return None, None
    scored = [(_RANK_ORDER.index(d["rank"]), d["xp"], d) for d in evaluated]
    best  = max(scored, key=lambda t: (t[0], t[1]))[2]
    worst = min(scored, key=lambda t: (t[0], t[1]))[2]
    return best, worst


def _wellness_flags(metrics):
    by_key = {m["key"]: m for m in metrics}
    flags = []
    for key, cond, msg in _WELLNESS_ABS_FLAGS:
        m = by_key.get(key)
        if m and m["value"] is not None and cond(m["value"]):
            flags.append({"key": key, "label": m["label"], "text": msg(m["value"])})
    # Cualquier métrica con tendencia negativa marcada que no haya entrado ya
    # por umbral absoluto — evita mostrar el mismo dato dos veces.
    flagged_keys = {f["key"] for f in flags}
    for m in metrics:
        if m["key"] in flagged_keys or m["trend"] != "worse" or m["delta"] is None:
            continue
        flags.append({
            "key": m["key"], "label": m["label"],
            "text": f"{m['label']} empeoró {abs(m['delta']):g}{m['unit']} vs la semana pasada.",
        })
    return flags[:3]


def _action_plan(weekly, worst_day, flags):
    plan = []
    if weekly["rank"] in ("carbon", "iron"):
        plan.append("Prioridad #1: completa tu ancla del día TODOS los días — sin eso, Oro no es matemáticamente posible.")
    if weekly["rank"] == "iron":
        plan.append("Reparte al menos 3 touches en 2 momentos distintos del día (no los dejes todos para la noche) — así es como Hierro se convierte en Oro.")
    if weekly["rank"] == "gold":
        plan.append("Ya tienes el volumen — enfócate en cerrar el 100% de tus anclas los días que sí llegas a Oro. Eso es lo único que falta para Diamante.")
    if weekly["rank"] == "diamond":
        plan.append("Sostén el mismo patrón — el riesgo en una semana de élite no es bajar el esfuerzo, es no anotar qué lo hizo funcionar para poder repetirlo.")
    if flags:
        plan.append(flags[0]["text"])
    if worst_day:
        plan.append(f"Tu día más flojo fue {worst_day['weekday']} ({worst_day['label']}) — identifica qué lo bloqueó y arma un plan mínimo específico para ese día.")
    return plan[:3]


def _analyze_week(weekly, prev_weekly, metrics):
    verdict = _VERDICT_COPY.get(weekly["rank"], _VERDICT_COPY["carbon"])
    best_day, worst_day = _best_worst_day(weekly["days"])

    vs_prev = {"trend": None, "delta_pts": None, "text": None, "prev_label": None}
    if prev_weekly and prev_weekly.get("days_evaluated"):
        vs_prev["prev_label"] = prev_weekly.get("label")
        delta = round(weekly["avg_points"] - prev_weekly["avg_points"], 2)
        vs_prev["delta_pts"] = delta
        if abs(delta) < 0.05:
            vs_prev["trend"] = "same"
            vs_prev["text"] = "Nivel casi idéntico al de la semana pasada."
        elif delta > 0:
            vs_prev["trend"] = "up"
            vs_prev["text"] = f"Subiste vs la semana pasada (fue {prev_weekly['label']})."
        else:
            vs_prev["trend"] = "down"
            vs_prev["text"] = f"Bajaste vs la semana pasada (fue {prev_weekly['label']})."

    flags = _wellness_flags(metrics)

    return {
        "verdict_title":  verdict["title"],
        "verdict_body":   verdict["body"],
        "best_day":       best_day,
        "worst_day":      worst_day,
        "vs_prev":        vs_prev,
        "wellness_flags": flags,
        "action_plan":    _action_plan(weekly, worst_day, flags),
    }


# ── Métricas automáticas (handoff Ataraxia v2, nota 7) ────────────────────────
# Lo que la app ya sabe no se pide a mano: presupuesto usado (Oikonomia) y
# días de lectura (anclas de Paideia en Acta). Si una consulta falla o no hay
# datos, esa métrica vuelve a ser manual.

def _semana_dias(semana_id):
    """Lunes..domingo (ISO) de la semana Lun-Dom que cierra este ciclo."""
    lunes = date.fromisoformat(semana_id) - timedelta(days=5)
    return [(lunes + timedelta(days=i)).isoformat() for i in range(7)]


def _auto_presupuesto_pct(semana_id):
    """consumo / ingreso_real del mes de la semana (misma definición que el
    héroe de Oikonomia, _calc_budget). None si no hay ingreso."""
    from modules.finanzas.budget import _calc_budget
    mes = _semana_dias(semana_id)[-1][:7]
    with get_db() as db:
        bd = _calc_budget(mes, db)
    ing = bd.get("ingreso_real") or 0
    if ing <= 0:
        return None
    return round(bd.get("consumo", 0) / ing * 100, 1)


def _auto_dias_lectura(semana_id):
    """Días de la semana con un ancla de Paideia completa en el Acta (la
    versión mínima no cuenta). None si no hay anclas de Paideia."""
    import modules.actividades.activity_defs as adefs
    keys = [k for k, a in adefs.get_active_flat().items()
            if a.get("pillar") == "paideia" and a.get("effective_type") == "ancla"]
    if not keys:
        return None
    dias = _semana_dias(semana_id)
    ph = ",".join("?" * len(keys))
    with get_db() as db:
        n = db.execute(
            f"SELECT COUNT(DISTINCT date) FROM activity_logs WHERE activity_key IN ({ph}) AND date>=? AND date<=?",
            keys + [dias[0], dias[-1]]).fetchone()[0]
    return float(n)


def _hasta_hoy(semana_id):
    """Días de la semana ya vividos (no cuenta lo que aún no pasa)."""
    hoy = today_date().isoformat()
    return [d for d in _semana_dias(semana_id) if d <= hoy]


def _auto_min_baile(semana_id):
    """Minutos de baile de la semana (sesiones de Eurythmia). None si
    Eurythmia nunca se ha usado."""
    dias = _semana_dias(semana_id)
    with get_db() as db:
        if not db.execute("SELECT 1 FROM eury_sessions LIMIT 1").fetchone():
            return None
        n = db.execute("SELECT COALESCE(SUM(min),0) FROM eury_sessions WHERE date>=? AND date<=?",
                       (dias[0], dias[-1])).fetchone()[0]
    return float(n)


def _auto_dias_limpios(semana_id):
    """Días de la semana con el día de Nutrición cerrado y sin desliz (la
    misma regla que la racha de Nutrición). None si Nutrición no se usa."""
    dias = _hasta_hoy(semana_id)
    with get_db() as db:
        if not db.execute("SELECT 1 FROM activity_logs WHERE substr(activity_key,1,10)='nutri_dia_' LIMIT 1").fetchone():
            return None
        cerrados = {r[0][len('nutri_dia_'):] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE activity_key IN ({})".format(",".join("?" * len(dias))),
            ["nutri_dia_" + d for d in dias]).fetchall()} if dias else set()
        deslices = {r[0] for r in db.execute(
            "SELECT DISTINCT date FROM nutricion_deslices WHERE date>=? AND date<=?", (dias[0], dias[-1])).fetchall()} if dias else set()
    return float(sum(1 for d in dias if d in cerrados and d not in deslices))


def _auto_peso(semana_id):
    """Última medida de peso de Perfil hasta el domingo de la semana."""
    domingo = _semana_dias(semana_id)[-1]
    with get_db() as db:
        r = db.execute("""SELECT value FROM body_measurements_history WHERE key='peso' AND substr(recorded_at,1,10)<=?
                          ORDER BY recorded_at DESC, id DESC LIMIT 1""", (domingo,)).fetchone()
        if not r:
            r = db.execute("SELECT value FROM body_measurements WHERE key='peso'").fetchone()
    try:
        return float(str(r["value"]).replace(",", ".")) if r else None
    except ValueError:                       # el marcador «— editar —» de Perfil
        return None


def _auto_racha_anclas(semana_id):
    """Racha de Acta (días seguidos con actividad, como Inicio) al cierre de
    la semana: al domingo, o a hoy si la semana sigue en curso."""
    corte = min(date.fromisoformat(_semana_dias(semana_id)[-1]), today_date())
    with get_db() as db:
        fechas = {r[0] for r in db.execute(
            "SELECT DISTINCT date FROM activity_logs WHERE date<=? UNION SELECT DISTINCT date FROM xp_ledger WHERE source!='penalty' AND date<=?",
            (corte.isoformat(), corte.isoformat())).fetchall()}
    n, d = 0, corte
    if d == today_date() and d.isoformat() not in fechas:   # hoy aún puede llegar
        d -= timedelta(days=1)
    while d.isoformat() in fechas:
        n += 1
        d -= timedelta(days=1)
    return float(n)


_AUTO_METRICS = {"presupuesto_pct": ("Oikonomia", _auto_presupuesto_pct),
                 "dias_lectura": ("Acta", _auto_dias_lectura),
                 "min_baile": ("Eurythmia", _auto_min_baile),
                 "dias_limpios": ("Nutrición", _auto_dias_limpios),
                 "peso": ("Perfil", _auto_peso),
                 "racha_anclas": ("Acta", _auto_racha_anclas)}


def _auto_metrics(semana_id):
    """{key: (valor, fuente)} de las métricas que la app pudo calcular."""
    out = {}
    for key, (fuente, fn) in _AUTO_METRICS.items():
        try:
            v = fn(semana_id)
        except Exception as e:  # la métrica vuelve a ser manual
            print(f"[ataraxia] métrica auto {key} falló: {e}")
            v = None
        if v is not None:
            out[key] = (v, fuente)
    return out


def _semana_rango(semana_id):
    dias = _semana_dias(semana_id)
    a, b = date.fromisoformat(dias[0]), date.fromisoformat(dias[-1])
    mes = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{a.day}–{b.day} {mes[b.month - 1]}" if a.month == b.month else f"{a.day} {mes[a.month - 1]} – {b.day} {mes[b.month - 1]}"


def _revision_view(semana_id):
    actual   = _get_revision_row(semana_id) or {}
    anterior = _get_revision_row(_prev_semana_id(semana_id)) or {}
    auto     = _auto_metrics(semana_id)

    metrics = []
    for m in REVISION_METRICS:
        v  = auto[m["key"]][0] if m["key"] in auto else actual.get(m["key"])
        pv = anterior.get(m["key"])
        delta = None
        delta_str = None
        trend = None
        if v is not None and pv is not None:
            delta = round(v - pv, 2)
            delta_str = f"{delta:+g}"
            if delta == 0:
                trend = "same"
            elif (m["direction"] == "up") == (delta > 0):
                trend = "better"
            else:
                trend = "worse"
        metrics.append({**m, "value": v, "value_str": _fmt_num(v), "prev_value": pv, "prev_str": _fmt_num(pv), "delta": delta, "delta_str": delta_str, "trend": trend,
                        "auto": m["key"] in auto, "fuente": auto.get(m["key"], (None, None))[1]})

    # semana_id es el sábado de este ciclo (ver get_semana_id) — el lunes de
    # esa misma semana Lun-Dom es 5 días antes.
    monday_id      = (date.fromisoformat(semana_id) - timedelta(days=5)).isoformat()
    prev_monday_id = (date.fromisoformat(monday_id) - timedelta(days=7)).isoformat()
    weekly         = engine.get_weekly_classification(monday_id)
    prev_weekly    = engine.get_weekly_classification(prev_monday_id)

    best = _best_worst_day(weekly["days"])[0]
    act = ACTIVITIES["revision_semanal"]
    return {
        "metrics":    metrics,
        "has_data":   bool(actual),
        "notas":      actual.get("notas") or "",
        "weekly":     weekly,
        "analysis":   _analyze_week(weekly, prev_weekly, metrics),
        "semana_num": _week_num_of(monday_id),
        "rango":      _semana_rango(semana_id),
        "semana_id":  semana_id,
        "auto_n":     sum(1 for m in metrics if m["auto"]),
        "paso":       actual.get("paso") or 1,
        "cerrada":    bool(actual.get("cerrada_at")),
        "xp_pagado":  bool(actual.get("xp_pagado")),
        "recompensa": {"xp": act["pts"], "ec": act["ec"]},
        "best_day":   best,
        "pregunta":   (f"¿Qué hizo que el {_DIA_LARGO.get(best['weekday'], best['weekday'])} fuera tu mejor día?" if best else
                       "¿Qué te funcionó esta semana?"),
    }


_DIA_LARGO = {"Lun": "lunes", "Mar": "martes", "Mié": "miércoles", "Jue": "jueves",
              "Vie": "viernes", "Sáb": "sábado", "Dom": "domingo"}


def historial_semanas(limit=52):
    """Revisiones guardadas, la más reciente arriba (vive en /logros/semanas;
    la semana en curso va marcada como «Esta semana»)."""
    semana_id = get_semana_id()
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM revision_semanal WHERE semana_id <= ? ORDER BY semana_id DESC LIMIT ?",
            (semana_id, limit)).fetchall()
    return [{**dict(r), "actual": r["semana_id"] == semana_id, "rango": _semana_rango(r["semana_id"])} for r in rows]


# ── Data builder ──────────────────────────────────────────────────────────────

def _build_rutina(dia, semana_id):
    with get_db() as db:
        # Distinct bloques in order
        bloque_rows = db.execute("""
            SELECT bloque_id, MIN(orden) as min_orden
            FROM rutina_bloques WHERE dia=?
            GROUP BY bloque_id ORDER BY min_orden
        """, (dia,)).fetchall()

        bloques = []
        for br in bloque_rows:
            bid = br["bloque_id"]
            tareas = [dict(t) for t in db.execute(
                "SELECT * FROM rutina_bloques WHERE dia=? AND bloque_id=? ORDER BY orden",
                (dia, bid)
            ).fetchall()]
            for t in tareas:
                t["nombre"] = _strip_emoji_prefix(t["nombre"])

            task_ids = [t["id"] for t in tareas]
            done_ids = set()
            if task_ids:
                ph = ",".join("?" * len(task_ids))
                done_rows = db.execute(
                    f"SELECT bloque_id FROM rutina_progreso WHERE bloque_id IN ({ph}) AND semana_id=? AND completado=1",
                    task_ids + [semana_id]
                ).fetchall()
                done_ids = {r["bloque_id"] for r in done_rows}

            req_ids = {t["id"] for t in tareas if not t["opcional"]}
            all_ids = set(task_ids)
            # Bloque sin tareas requeridas (todo opcional, ej. Jugos): "done" refleja
            # si la(s) tarea(s) opcional(es) se marcaron, en vez de quedar vacuamente falso
            bloque_done   = req_ids.issubset(done_ids) if req_ids else (all_ids.issubset(done_ids) if all_ids else False)
            total_duracion = sum(t["duracion_min"] for t in tareas if not t["opcional"])

            bloques.append({
                "bloque_id":      bid,
                "label":          BLOQUE_LABELS.get(bid, bid),
                "icon":           BLOQUE_ICONS.get(bid, "circle"),
                "tareas":         tareas,
                "done_ids":       list(done_ids),
                "bloque_done":    bloque_done,
                "required_count": len(req_ids),
                "done_count":     len(done_ids & req_ids),
                "total_duracion": total_duracion,
                "xp_total":       sum(t["xp"] for t in tareas if not t["opcional"]),
                "ec_total":       sum(t["ec"] for t in tareas if not t["opcional"]),
            })

    # Global progress: count completed BLOQUES (cada bloque = 1 tarea principal)
    # Bloques 100% opcionales (ej. Jugos) no cuentan para el total del día —
    # no deben bloquear el 100% / el combo "día completo"
    required_bloques = [bl for bl in bloques if bl["required_count"] > 0]
    total = len(required_bloques)
    done  = sum(1 for bl in required_bloques if bl["bloque_done"])
    # Bloque «Ahora» (handoff Ataraxia v2, nota 3): el primero del día con
    # requeridas pendientes. Es el único que se pinta abierto.
    ahora = next((bl["bloque_id"] for bl in bloques if bl["done_count"] < bl["required_count"]), None)
    return {
        "bloques":  bloques,
        "ahora":    ahora,
        "total":    total,
        "done":     done,
        "pct":      int(done / total * 100) if total else 0,
        "complete": done >= total and total > 0,
    }


# Lunes a miércoles: prórroga para cerrar el fin de semana anterior.
PRORROGA_DIAS = (0, 1, 2)


def _finde_rango(semana_id):
    sab = date.fromisoformat(semana_id)
    dom = sab + timedelta(days=1)
    mes = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{sab.day}–{dom.day} {mes[dom.month - 1]}" if sab.month == dom.month else f"{sab.day} {mes[sab.month - 1]} – {dom.day} {mes[dom.month - 1]}"


# ── Routes ────────────────────────────────────────────────────────────────────

@ataraxia_bp.route('/')
def index():
    semana_id = get_semana_id()
    dow = today_date().weekday()
    # Prórroga (usuario, 2026-11-09): lo que quedó pendiente del fin de
    # semana se puede terminar hasta el miércoles; jueves y viernes, vista previa.
    en_prorroga = dow in PRORROGA_DIAS
    puede_marcar = dow in (5, 6) or en_prorroga

    sabado_data  = _build_rutina("sabado",  semana_id)
    domingo_data = _build_rutina("domingo", semana_id)
    if dow == 6:
        default_dia = "domingo"
    elif en_prorroga and sabado_data["complete"] and not domingo_data["complete"]:
        default_dia = "domingo"
    else:
        default_dia = "sabado"
    dia = request.args.get('dia', default_dia)

    _td = today_date()
    fecha_larga = "{} {} de {}".format(
        ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][dow], _td.day,
        ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"][_td.month - 1])
    return render_template('ataraxia/index.html',
        fecha_larga  = fecha_larga,
        semana_num   = _td.isocalendar()[1],
        dias_para_sabado = (5 - dow) % 7,
        dia          = dia,
        semana_id    = semana_id,
        sabado       = sabado_data,
        domingo      = domingo_data,
        horarios     = HORARIOS,
        bloque_labels= BLOQUE_LABELS,
        is_weekend   = puede_marcar,
        en_prorroga  = en_prorroga,
        finde_rango  = _finde_rango(semana_id),
        today        = today_str(),
        prio_semana  = _prio_semana_view(semana_id),
    )


# ── Revisión de la semana en 4 pasos (handoff Revisión) ──────────────────────
# Una sola ruta para cerrar la semana: 1 Cómo fue · 2 Los números · 3 Cerrar
# cabos · 4 La que viene. Cada paso se guarda solo (/api/revision parcial) y
# el cierre (cerrar:true) paga una vez y marca «Planeación» del domingo.

REVISION_PASOS = [("como", "Cómo fue", "1 min"), ("numeros", "Los números", "2 min"),
                  ("cabos", "Cerrar cabos", "3 min"), ("viene", "La que viene", "2 min")]
REVISION_AVISO_HORA = 17     # el domingo desde las 17:00 la revisión entra a la campana
_DIA_CORTO = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _hace(fecha, hoy):
    try:
        n = (hoy - date.fromisoformat(str(fecha)[:10])).days
    except (TypeError, ValueError):
        return ""
    return "hoy" if n <= 0 else ("ayer" if n == 1 else f"hace {n} d")


def _cabos(hoy, sess):
    """Paso 3: inbox de Praxis, tareas vencidas y avisos de la semana. Cada
    fila trae las acciones de un toque contra los endpoints de su módulo."""
    with get_db() as db:
        inbox = [dict(r) for r in db.execute(
            """SELECT id, title, created_at FROM gtd_tasks WHERE completado=0 AND cuadrante IS NULL
               AND COALESCE(tipo,'tarea')!='idea' ORDER BY created_at""").fetchall()]
        vistos = {t["id"] for t in inbox}
        vencidas = [dict(r) for r in db.execute(
            """SELECT id, title, fecha_limite FROM gtd_tasks WHERE completado=0 AND COALESCE(fecha_limite,'')!=''
               AND fecha_limite < ? ORDER BY fecha_limite, id""", (hoy.isoformat(),)).fetchall() if r["id"] not in vistos]
        try:
            from modules import avisos as av
            semana = av.recolectar(db, hoy, sess)["semana"]
        except Exception as e:
            print(f"[ataraxia] avisos para la revisión: {e}")
            semana = []
    prox_lunes = hoy + timedelta(days=7 - hoy.weekday())
    grupos = [
        {"id": "inbox", "label": "Inbox de Praxis", "src": "Praxis", "items": [{
            "key": f"t{t['id']}", "t": t["title"], "s": _hace(t["created_at"], hoy),
            "acts": [{"l": "Esta semana", "res": "A esta semana", "calls": [
                         {"method": "POST", "url": f"/gtd/api/task/{t['id']}/classify", "body": {"importante": True, "urgente": False}}]},
                     {"l": "Algún día", "res": "A ideas", "calls": [
                         {"method": "POST", "url": f"/gtd/api/task/{t['id']}/classify", "body": {"importante": False, "urgente": False}}]},
                     {"l": "Borrar", "res": "Borrada", "tachar": True, "calls": [
                         {"method": "DELETE", "url": f"/gtd/api/task/{t['id']}"}]}]} for t in inbox]},
        {"id": "vencidas", "label": "Vencidas", "src": "Praxis", "items": [{
            "key": f"t{t['id']}", "t": t["title"],
            "s": "venció " + _DIA_CORTO[date.fromisoformat(t["fecha_limite"][:10]).weekday()] + " " + str(int(t["fecha_limite"][8:10])),
            "acts": [{"l": "Hoy", "res": "Para hoy", "calls": [
                         {"method": "POST", "url": f"/gtd/api/task/{t['id']}/update", "body": {"fecha_limite": hoy.isoformat()}},
                         {"method": "POST", "url": f"/gtd/api/task/{t['id']}/classify", "body": {"importante": True, "urgente": True}}]},
                     {"l": "Mover", "title": "A la próxima semana", "res": "Al lunes " + str(prox_lunes.day), "calls": [
                         {"method": "POST", "url": f"/gtd/api/task/{t['id']}/update", "body": {"fecha_limite": prox_lunes.isoformat()}}]},
                     {"l": "Hecha", "res": "Hecha", "tachar": True, "calls": [
                         {"method": "POST", "url": f"/gtd/api/task/{t['id']}/complete"}]}]} for t in vencidas]},
    ]
    avisos_items = []
    for a in semana:
        ac = a.get("accion") or {}
        acts = []
        if ac.get("method"):
            acts.append({"l": ac.get("label") or "Hecho", "res": ac.get("hecho") or "Hecho", "tachar": True,
                         "calls": [{"method": ac["method"], "url": ac["url"], "body": ac.get("body") or {}}]})
        elif ac.get("url"):
            acts.append({"l": ac.get("label") or "Ver", "href": ac["url"]})
        acts.append({"l": "Posponer", "res": "Pospuesto", "calls": [
            {"method": "POST", "url": f"/api/avisos/{a['clave']}/posponer", "body": {"nivel": "semana"}}]})
        avisos_items.append({"key": a["clave"], "t": a["titulo"], "s": a["modulo"] + (" · " + a["detalle"] if a.get("detalle") else ""), "acts": acts})
    grupos.append({"id": "avisos", "label": "Avisos de la semana", "src": "Avisos", "items": avisos_items})
    return grupos


def _proxima_semana(semana_id):
    """Lunes..domingo que siguen al fin de semana del ciclo (lo que gobiernan
    las prioridades elegidas ahora)."""
    lunes = date.fromisoformat(semana_id) + timedelta(days=2)
    return [lunes + timedelta(days=i) for i in range(7)]


def _calendario(semana_id, sess):
    """Paso 4 «Ya en el calendario»: lo que ya cae la semana que viene."""
    dias = _proxima_semana(semana_id)
    a, b = dias[0].isoformat(), dias[-1].isoformat()
    out = []

    def add(d, t, m):
        out.append({"fecha": d.isoformat() if isinstance(d, date) else d, "t": t, "m": m})

    with get_db() as db:
        try:
            for p in db.execute("""SELECT fecha, hora, rival FROM futbol_partidos WHERE estado='programado'
                                   AND fecha>=? AND fecha<=? ORDER BY fecha, hora""", (a, b)).fetchall():
                add(p["fecha"][:10], "Partido vs " + (p["rival"] or "rival por confirmar") + (f" · {p['hora']}" if p["hora"] else ""), "Fútbol")
        except Exception as e:
            print(f"[ataraxia] calendario fútbol: {e}")
        try:
            for r in db.execute("""SELECT description, COALESCE(next_date, target_date) AS f FROM reminders
                                   WHERE is_active=1 AND COALESCE(next_date, target_date)>=? AND COALESCE(next_date, target_date)<=?""",
                                (a, b)).fetchall():
                add(r["f"][:10], r["description"], "Perfil")
        except Exception as e:
            print(f"[ataraxia] calendario recordatorios: {e}")
        if sess.get("fin_ok"):
            try:
                from modules.finanzas.routes import PAY_DAYS, ESTADO_CORTE
                from modules.finanzas import pagos_ciclo
                for d in dias:
                    for p in PAY_DAYS:
                        if pagos_ciclo._due(d.year, d.month, p["day"]) == d:
                            add(d, f"Pago {p['label']}", "Oikonomia")
                    for _banco, (dia, label) in ESTADO_CORTE.items():
                        if pagos_ciclo._due(d.year, d.month, dia) == d:
                            add(d, f"Corte {label}", "Oikonomia")
            except Exception as e:
                print(f"[ataraxia] calendario Oikonomia: {e}")
        try:
            from modules.harma.routes import _get_vehiculo, _compute_plan_item, _months_between
            from modules.harma import plan as hp
            v = _get_vehiculo(db)
            if v:
                ritmo = hp.ritmo_km_mes(db, v, dias[0])
                for r in db.execute("SELECT * FROM harma_plan_items").fetchall():
                    it = hp.enriquecer(_compute_plan_item(dict(r), v["km_actual"] or 0, dias[0]), ritmo,
                                       _months_between(r["last_date"], dias[0]))
                    if it["eta_meses"] is not None and it["eta_meses"] <= 0.25:
                        add(a, it["name"] + (" · ya toca" if it["eta_meses"] <= 0 else " · esta semana"), "Harma")
        except Exception as e:
            print(f"[ataraxia] calendario Harma: {e}")
    sab = dias[5]
    try:
        with get_db() as db:
            n = db.execute("SELECT COUNT(DISTINCT bloque_id) FROM rutina_bloques WHERE dia IN ('sabado','domingo')").fetchone()[0]
        add(sab, f"Ataraxia · {n} bloques", "Ataraxia")
    except Exception as e:
        print(f"[ataraxia] calendario rutina: {e}")
    add(dias[6], f"Revisión semana {dias[0].isocalendar()[1]}", "aquí")
    out.sort(key=lambda x: x["fecha"])
    for x in out:
        d = date.fromisoformat(x["fecha"])
        x["d"] = f"{_DIA_CORTO[d.weekday()]} {d.day}"
    return out


@ataraxia_bp.route('/revision')
def revision():
    from flask import session
    semana_id = get_semana_id()
    rv = _revision_view(semana_id)
    try:
        paso = int(request.args.get('paso') or 0)
    except ValueError:
        paso = 0
    if not 1 <= paso <= 5:
        paso = 5 if rv["cerrada"] else rv["paso"]
    hoy = today_date()
    cabos = _cabos(hoy, session)
    return render_template('ataraxia/revision.html',
        rv=rv, paso=paso, pasos=REVISION_PASOS,
        cabos=cabos, cabos_n=sum(len(g["items"]) for g in cabos),
        prio_semana=_prio_semana_view(semana_id),
        calendario=_calendario(semana_id, session),
        proxima=_proxima_semana(semana_id),
    )


def avisos(db, hoy):
    """Aviso del centro (modules/avisos.py): el domingo desde las 17:00, si la
    semana no está cerrada, «Revisión de la semana» entra a Hoy."""
    from modules.avisos import aviso
    from utils import now_local
    if hoy.weekday() != 6 or hoy != today_date() or now_local().hour < REVISION_AVISO_HORA:
        return []
    semana_id = (hoy - timedelta(days=1)).isoformat()
    r = db.execute("SELECT cerrada_at FROM revision_semanal WHERE semana_id=?", (semana_id,)).fetchone()
    if r and r["cerrada_at"]:
        return []
    return [aviso(f"ata:revision:{semana_id}", 'Ataraxia', 'calendar-check', 'Revisión de la semana',
                  'cierra la semana en 4 pasos', hoy, 'hoy', {'label': 'Abrir', 'url': '/ataraxia/revision'})]


# ── Prioridades de la semana desde Praxis (handoff Ataraxia v2, Sprint 4) ────
# Se eligen con estrella entre las tareas de «Esta semana» de Praxis (máx. 3);
# gobiernan la semana Lun-Dom siguiente y Acta las muestra día a día.

def _prio_semana_view(semana_id):
    with get_db() as db:
        ops = prio.opciones_semana(db, semana_id)
    return {"opciones": ops, "n": sum(1 for o in ops if o["on"]), "max": prio.MAX_SEMANA}


@ataraxia_bp.route('/api/prioridad-semana/<int:tid>', methods=['POST'])
def toggle_prioridad_semana(tid):
    semana_id = get_semana_id()
    with get_db() as db:
        ok, val, code = prio.alternar_semana(db, tid, semana_id)
        db.commit()
    view = _prio_semana_view(semana_id)
    if not ok:
        return jsonify({'ok': False, 'error': val, **view}), code
    return jsonify({'ok': True, 'prioridad': val, **view})


@ataraxia_bp.route('/api/prioridad-semana', methods=['POST'])
def nueva_prioridad_semana():
    texto = clean_str((request.json or {}).get('texto', ''), max_len=300)
    if not texto:
        return jsonify({'ok': False, 'error': 'Escribe la prioridad'}), 400
    semana_id = get_semana_id()
    with get_db() as db:
        tid = prio.crear_prioridad_semana(db, texto, semana_id)
        db.commit()
    view = _prio_semana_view(semana_id)
    if tid is None:
        return jsonify({'ok': False, 'error': 'Ya elegiste 3 prioridades para la semana.', **view}), 409
    return jsonify({'ok': True, 'id': tid, **view})


@ataraxia_bp.route('/api/rutina/<dia>')
def get_rutina(dia):
    if dia not in ('sabado', 'domingo'):
        return jsonify({"error": "invalid"}), 400
    semana_id = get_semana_id()
    return jsonify(_build_rutina(dia, semana_id))


REVISION_TAREA = "sun_planeacion"      # «Planeación» del domingo: la cierra la revisión


def _marcar_tarea(sub_id, semana_id, tiempo_seg=0):
    """Marca una tarea de la rutina (lo que hace /api/rutina/check). None si
    la tarea no existe; si ya estaba marcada no vuelve a pagar."""
    now = datetime.now().isoformat()
    with get_db() as db:
        tarea = db.execute("SELECT * FROM rutina_bloques WHERE id=?", (sub_id,)).fetchone()
    if not tarea:
        return None
    tarea = dict(tarea)
    parent_bloque = tarea["bloque_id"]

    with get_db() as db:
        existing = db.execute(
            "SELECT id, completado FROM rutina_progreso WHERE bloque_id=? AND semana_id=?", (sub_id, semana_id)
        ).fetchone()
        ya = bool(existing and existing["completado"])
        if existing:
            db.execute(
                "UPDATE rutina_progreso SET completado=1, completado_at=?, tiempo_real_seg=? WHERE bloque_id=? AND semana_id=?",
                (now, tiempo_seg, sub_id, semana_id)
            )
        else:
            db.execute(
                "INSERT INTO rutina_progreso (bloque_id, semana_id, completado, completado_at, tiempo_real_seg) VALUES (?,?,1,?,?)",
                (sub_id, semana_id, now, tiempo_seg)
            )
        db.commit()

        # Check if parent bloque is now complete
        req = db.execute(
            "SELECT id FROM rutina_bloques WHERE bloque_id=? AND opcional=0", (parent_bloque,)
        ).fetchall()
        req_ids = [r["id"] for r in req]
        done_ids = set()
        if req_ids:
            ph = ",".join("?" * len(req_ids))
            done_rows = db.execute(
                f"SELECT bloque_id FROM rutina_progreso WHERE bloque_id IN ({ph}) AND semana_id=? AND completado=1",
                req_ids + [semana_id]
            ).fetchall()
            done_ids = {r["bloque_id"] for r in done_rows}
        bloque_complete = set(req_ids).issubset(done_ids) if req_ids else False

    gam = None
    if not ya and (tarea["tier"] != "micro" or bloque_complete):   # ya marcada: no paga otra vez
        gam = engine.process_rutina_check(
            sub_key   = sub_id,
            xp        = tarea["xp"] if tarea["tier"] != "micro" else 0,
            ec        = tarea["ec"] if tarea["tier"] != "micro" else 0,
            cat       = tarea.get("categoria") or "",
            bloque_id = parent_bloque if bloque_complete else None,
        )
    return {"ok": True, "ya": ya, "dia": tarea["dia"], "bloque_complete": bloque_complete, "gam": gam}


@ataraxia_bp.route('/api/rutina/check', methods=['POST'])
def check_tarea():
    data       = request.json or {}
    semana_id  = get_semana_id()
    r = _marcar_tarea(data.get('bloque_id'), semana_id, int(data.get('tiempo_seg') or 0))
    if not r:
        return jsonify({"error": "not found"}), 404
    rutina = _build_rutina(r["dia"], semana_id)
    return jsonify({"ok": True, "bloque_complete": r["bloque_complete"], "gam": r["gam"], "rutina": rutina})


@ataraxia_bp.route('/api/rutina/uncheck', methods=['POST'])
def uncheck_tarea():
    data   = request.json or {}
    sub_id = data.get('bloque_id')
    semana_id = get_semana_id()

    with get_db() as db:
        tarea = db.execute("SELECT * FROM rutina_bloques WHERE id=?", (sub_id,)).fetchone()
    if not tarea:
        return jsonify({"error": "not found"}), 404
    tarea = dict(tarea)

    with get_db() as db:
        db.execute(
            "UPDATE rutina_progreso SET completado=0, completado_at=NULL, tiempo_real_seg=NULL "
            "WHERE bloque_id=? AND semana_id=?",
            (sub_id, semana_id)
        )
        db.commit()

    gam = engine.process_rutina_uncheck(
        sub_key   = sub_id,
        bloque_id = tarea["bloque_id"],
    )
    rutina = _build_rutina(tarea["dia"], semana_id)
    return jsonify({"ok": True, "gam": gam, "rutina": rutina})


@ataraxia_bp.route('/api/revision', methods=['POST'])
def save_revision():
    """Guardado parcial de la revisión (handoff Revisión, S1): solo se tocan
    las llaves que vienen en el cuerpo, así cada paso se guarda solo y se
    puede retomar a medias. Las métricas automáticas siempre se guardan con
    el valor de la app, no con lo que mande el cliente.

    `cerrar: true` cierra la semana: XP/EC una sola vez por semana
    (xp_pagado) y marca la casilla «Planeación» del domingo en la rutina."""
    data = request.json or {}
    semana_id = get_semana_id()
    now = datetime.now().isoformat()

    cambios = {}
    for key in _REVISION_KEYS + ["calorias_quemadas"]:
        if key in data:
            raw = data.get(key)
            try:
                cambios[key] = float(raw) if raw not in (None, "") else None
            except (TypeError, ValueError):
                cambios[key] = None
    for key, (v, _f) in _auto_metrics(semana_id).items():
        cambios[key] = v
    if "notas" in data:
        cambios["notas"] = clean_str(data.get("notas") or "", max_len=4000)
    if "paso" in data:
        try:
            cambios["paso"] = max(1, min(int(data["paso"]), 4))
        except (TypeError, ValueError):
            pass
    cerrar = bool(data.get("cerrar"))

    with get_db() as db:
        row = db.execute("SELECT * FROM revision_semanal WHERE semana_id=?", (semana_id,)).fetchone()
        is_first_save = row is None
        if is_first_save:
            db.execute("INSERT INTO revision_semanal (semana_id, notas, created_at, updated_at, xp_pagado) VALUES (?, '', ?, ?, 0)",
                       (semana_id, now, now))
            row = {"xp_pagado": 0, "cerrada_at": None}
        if cerrar and not row["cerrada_at"]:
            cambios["cerrada_at"] = now
        pagar = cerrar and not row["xp_pagado"]
        if pagar:
            cambios["xp_pagado"] = 1
        cambios["updated_at"] = now
        cols = ", ".join(f"{k}=?" for k in cambios)
        db.execute(f"UPDATE revision_semanal SET {cols} WHERE semana_id=?", list(cambios.values()) + [semana_id])
        db.commit()

    gam = None
    if pagar:
        # Mismos valores calibrados de data.py (ACTIVITIES['revision_semanal']).
        act = ACTIVITIES["revision_semanal"]
        with get_db() as db:
            log_id = db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                                ("revision_semanal", today_str(), act["pts"])).lastrowid
            db.commit()
        gam = engine.process_activity("revision_semanal", act["pts"], act["cat"], log_id, ec=act["ec"])
    planeacion = None
    if cerrar:
        try:
            planeacion = _marcar_tarea(REVISION_TAREA, semana_id)
        except Exception as e:               # la revisión ya quedó cerrada
            print(f"[ataraxia] no se pudo marcar {REVISION_TAREA}: {e}")
        if planeacion and planeacion.get("gam") and not gam:
            gam = planeacion["gam"]

    return jsonify({"ok": True, "semana_id": semana_id, "first_save": is_first_save, "gam": gam,
                    "cerrada": cerrar or bool(row["cerrada_at"]), "pagada": pagar,
                    "planeacion": bool(planeacion and planeacion.get("ok"))})


@ataraxia_bp.route('/api/rutina/reset', methods=['POST'])
def reset_rutina():
    token    = (request.json or {}).get('token')
    expected = os.environ.get('RESET_TOKEN', 'ataraxia-reset-2026')
    if token != expected:
        return jsonify({"error": "unauthorized"}), 401
    semana_id = get_semana_id()
    with get_db() as db:
        db.execute("DELETE FROM rutina_progreso WHERE semana_id=?", (semana_id,))
        db.commit()
    return jsonify({"ok": True, "semana_id": semana_id})
