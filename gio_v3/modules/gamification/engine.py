"""
Gamification Engine v3.0 — Eudaimonia OS

Rule hierarchy:
  1. Activity XP = pts (direct, no multiplier table)
  2. EC = ec field per activity (tier-based: micro=0, progreso=1, alto=2-3)
  3. Streak bonus: +5% XP at 7d, +10% XP at 30d
  4. Balance rule: +20% XP if category <60% weekly avg
  5. Event multipliers (special_events table)
  6. Combo bonuses: LOGOI+HEGEMONIKON+PAIDEIA=+3 XP; 5 cats=+5 XP
  7. Daily classification: Carbón / Hierro / Oro / Diamante
  8. Hard cap: 3.0× on any multiplier
"""
from datetime import date, datetime, timedelta
from database import get_db
from data import ACTIVITIES, ACTIVITY_CATEGORIES, VIRTUE_CATS
from modules.gamification.achievements import ACHIEVEMENT_DEFS
from modules.gamification.icons import lucide_for
from utils import today_str, today_date
import modules.actividades.activity_defs as adefs

# ── Level System (10 Stoic Levels — 1 año dedicado = nivel 10) ───────────────
# Calibrado a 25 XP/día activo × 5 días/semana = nivel 10 en ~52 semanas
LEVEL_THRESHOLDS = [
    (0,     1,  "PROKOPTON"),   # inicio
    (300,   2,  "EFEBO"),        # ~2.5 semanas
    (900,   3,  "ASQUETÉS"),     # ~7 semanas
    (1800,  4,  "ESTRATEGOS"),   # ~3.5 meses
    (3000,  5,  "AUTARKÉS"),     # ~6 meses
    (4200,  6,  "POLÍMATA"),     # ~8.5 meses
    (5000,  7,  "ARETÉ"),        # ~10 meses
    (5600,  8,  "HEGEMÓN"),      # ~11 meses
    (6000,  9,  "SOPHOS"),       # ~12 meses
    (6500,  10, "EUDAIMÓN"),     # ~1 año exacto
]

LEVEL_SUBTITLES = {
    1:  "El que avanza — iniciaste el camino",
    2:  "El joven — forjando disciplina",
    3:  "El asceta — probando el esfuerzo",
    4:  "El estratega — ejecutando con intención",
    5:  "El autosuficiente — dueño de ti mismo",
    6:  "El polímata — crecimiento en todas las virtudes",
    7:  "La excelencia — viviendo con areté",
    8:  "El rector — guiando desde dentro",
    9:  "El sabio — equilibrio y maestría",
    10: "La eudaimonía — vida floreciente plena",
}

# Daily classification thresholds
CLASSIFICATION = {
    "diamond": {"label": "Diamante", "icon": "💎", "color": "#7dd3fc",
                "desc": "Oro + todas tus anclas de hoy completas"},
    "gold":    {"label": "Oro",      "icon": "🥇", "color": "#fbbf24",
                "desc": "Hierro + touches repartidos a lo largo del día"},
    "iron":    {"label": "Hierro",   "icon": "⚔️",  "color": "#94a3b8",
                "desc": "Completaste tu(s) ancla(s) del día"},
    "carbon":  {"label": "Carbón",   "icon": "🪨",  "color": "#475569",
                "desc": "Aún no completas tu ancla del día"},
}

# ── Meta de Oro: recalibrada con ciencia del comportamiento ──────────────────
# La versión original exigía el 50% de TODOS los touches activos definidos en
# Acta Diurna (ver historial de este archivo). Eso rompía por dos razones:
#   1. Ley de Goodhart: el umbral crecía cada vez que se agregaba un touch
#      nuevo (custom o de fase) — trackear más hábitos te alejaba de Oro en
#      vez de ayudarte, un incentivo perverso contra enriquecer el sistema.
#   2. Efecto de gradiente de meta (Kivetz, Urminsky & Zheng, 2006): una meta
#      que sigue lejos incluso tras esfuerzo real (ej. 4/38 → faltan 15) se
#      percibe como inalcanzable y mata la motivación en vez de acelerarla.
# La meta nueva usa dos números fijos y pequeños, independientes del tamaño
# de la librería de touches (a prueba de Goodhart):
#   - GOLD_MIN_TOUCHES:  un volumen absoluto alcanzable en un día ocupado.
#   - GOLD_MIN_SESSIONS: cobertura a lo largo del día (mañana/tarde/noche/
#     cualquier-momento), no un montón de touches fáciles en un solo bloque —
#     la práctica distribuida a lo largo del día construye el hábito mejor
#     que la práctica concentrada (distributed practice effect).
# El hint (_next_rank_hint) nombra el/los bloque(s) concretos que faltan en
# vez de un conteo abstracto — metas específicas y accionables superan a las
# vagas (goal-setting theory, Locke & Latham).
GOLD_MIN_TOUCHES           = 5
GOLD_MIN_SESSIONS          = 3
RECOVERY_GOLD_MIN_TOUCHES  = 3
RECOVERY_GOLD_MIN_SESSIONS = 2
RECOVERY_HIERRO_TOUCHES    = 2

# ── Meta de Diamante: ligada al sistema de anclas rotativas, no a pilares ────
# Dos intentos previos de Diamante fallaron por el mismo motivo de fondo —
# medían algo que no tiene relación con cómo está diseñado el resto de Acta
# Diurna:
#   v1: 8 de 8 pilares el mismo día (6 en descarga) — perfección total.
#   v2: se relajó a 6 de 8 — seguía siendo casi imposible, porque el sistema
#       de anclas semanales rotativas (Fase 3) REPARTE a propósito los focos
#       fuertes (CCNA, inglés, francés, lectura de psicología) en días
#       distintos — nunca coinciden los 8 pilares el mismo día por diseño,
#       así que exigirlos no medía disciplina, medía una coincidencia de
#       calendario que casi nunca ocurre.
# v3 mide lo que sí varía intencionalmente por día: completar TODAS las
# anclas elegibles hoy (2 en un día tranquilo como sábado, hasta 4 en lunes o
# viernes — ver eligible_today()/days_of_week). Esto respeta el diseño real
# del sistema de anclas en vez de competir con él, y sigue el principio de
# "cobertura de la señal correcta" en vez de una proxy ajena — la métrica
# que se recompensa (anclas completas) es la métrica que ya representa el
# esfuerzo fuerte del día, no una aproximación.
# Diamante = Oro + todas las anclas de hoy completas.
_SESSION_ORDER  = ("morning", "afternoon", "night", "any")
_SESSION_LABELS = {"morning": "Mañana", "afternoon": "Tarde", "night": "Noche", "any": "Cualquier momento"}


def _sessions_of(touch_def):
    return set((touch_def.get("session") or "").split(",")) & set(_SESSION_ORDER)


def get_level_info(total_xp):
    level, name, next_idx = 1, "PROKOPTON", 1
    for i, (threshold, lvl, nm) in enumerate(LEVEL_THRESHOLDS):
        if total_xp >= threshold:
            level, name, next_idx = lvl, nm, i + 1
        else:
            break
    current_threshold = LEVEL_THRESHOLDS[level - 1][0]
    next_threshold    = LEVEL_THRESHOLDS[next_idx][0] if next_idx < len(LEVEL_THRESHOLDS) else current_threshold
    span              = next_threshold - current_threshold
    pct               = min(100, int((total_xp - current_threshold) / span * 100)) if span > 0 else 100
    return {
        "level":        level,
        "level_name":   name,
        "level_subtitle": LEVEL_SUBTITLES.get(level, ""),
        "total_xp":     total_xp,
        "level_pct":    pct,
        "xp_to_next":   max(0, next_threshold - total_xp),
        "next_xp":      next_threshold,
        "max_level":    level >= 10,
    }


# ── Streak ────────────────────────────────────────────────────────────────────

def get_gamification_streak():
    with get_db() as db:
        xp_dates  = {r["date"] for r in db.execute(
            "SELECT DISTINCT date FROM xp_ledger WHERE source != 'penalty'"
        ).fetchall()}
        act_dates = {r["date"] for r in db.execute(
            "SELECT DISTINCT date FROM activity_logs"
        ).fetchall()}
    all_dates = xp_dates | act_dates
    streak, check = 0, today_date()
    while check.isoformat() in all_dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


def _streak_xp_mult(streak):
    if streak >= 30: return 1.10
    if streak >= 7:  return 1.05
    return 1.0


# ── Balance Rule ──────────────────────────────────────────────────────────────

def _get_balance_boost(category):
    """Return 1.20 if category is below 60% of weekly average, else 1.0."""
    _td = today_date()
    week_start = (_td - timedelta(days=_td.weekday())).isoformat()
    today_s = today_str()
    with get_db() as db:
        logs = db.execute(
            "SELECT activity_key FROM activity_logs WHERE date >= ? AND date <= ? AND activity_key != 'priority_bonus'",
            (week_start, today_s)
        ).fetchall()

    if not logs:
        return 1.0

    cat_counts = {}
    for log in logs:
        key = log["activity_key"]
        if key in ACTIVITIES:
            cat = ACTIVITIES[key]["cat"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    if len(cat_counts) < 2:
        return 1.0

    avg = sum(cat_counts.values()) / len(cat_counts)
    return 1.20 if cat_counts.get(category, 0) < 0.6 * avg else 1.0


# ── Active Special Events ─────────────────────────────────────────────────────

def _get_active_events():
    today = today_str()
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM special_events
            WHERE is_active=1
              AND (start_date IS NULL OR start_date <= ?)
              AND (end_date   IS NULL OR end_date   >= ?)
        """, (today, today)).fetchall()
    return [dict(r) for r in rows]


def _compute_xp_mult(category, streak):
    mult = 1.0
    mult *= _streak_xp_mult(streak)
    mult *= _get_balance_boost(category)
    for ev in _get_active_events():
        mult *= ev["xp_multiplier"]
        if category and ev.get("focus_category") == category:
            mult *= ev.get("focus_bonus", 1.0)
    return min(round(mult, 2), 3.0)


# ── Ledger writers ────────────────────────────────────────────────────────────

def _award_xp(amount, source, desc, ref_id=None, mult=1.0):
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO xp_ledger (amount,source,reference_id,description,multiplier,date,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (amount, source, ref_id, desc, mult, today_str(), now)
        )
        db.commit()


def _award_coins(amount, source, desc, ref_id=None, mult=1.0):
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO coins_ledger (amount,source,reference_id,description,multiplier,date,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (amount, source, ref_id, desc, mult, today_str(), now)
        )
        db.commit()


def _log_mult_event(type_, mult, triggered_by, applies_to, expires_at=None):
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO multiplier_log (type,multiplier,triggered_by,applies_to,date,expires_at,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (type_, mult, triggered_by, applies_to, today_str(), expires_at, now)
        )
        db.commit()


# ── Combo Bonuses ─────────────────────────────────────────────────────────────

def _get_today_keys(today):
    with get_db() as db:
        return [r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=? AND activity_key != 'priority_bonus'",
            (today,)
        ).fetchall()]


def _check_combo_bonus(today, keys_today):
    cats = {ACTIVITIES[k]["cat"] for k in keys_today if k in ACTIVITIES}
    combos = []

    # LOGOI + HEGEMONIKON + PAIDEIA → +3 XP
    has_logoi   = bool(cats & set(VIRTUE_CATS["LOGOI"]))
    has_hegemon = bool(cats & set(VIRTUE_CATS["HEGEMONIKON"]))
    has_paideia = bool(cats & set(VIRTUE_CATS["PAIDEIA"]))

    with get_db() as db:
        trio_done = db.execute(
            "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: LOGOI+HEGEMONIKON+PAIDEIA' AND date=?",
            (today,)
        ).fetchone()

    if has_logoi and has_hegemon and has_paideia and not trio_done:
        _award_xp(3, "bonus", "Combo: LOGOI+HEGEMONIKON+PAIDEIA")
        combos.append({"type": "trio", "icon": "⚡", "name": "Trío de virtudes", "description": "Mente, cuerpo y conocimiento en un día", "xp": 3, "ec": 0})

    # 5 categorías en un día → +5 XP
    with get_db() as db:
        five_done = db.execute(
            "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: 5 categorías' AND date=?",
            (today,)
        ).fetchone()

    if len(cats) >= 5 and not five_done:
        _award_xp(5, "bonus", "Combo: 5 categorías")
        combos.append({"type": "5cats", "icon": "🌟", "name": "5 Virtudes", "description": "Cinco categorías distintas en un día", "xp": 5, "ec": 0})

    # Weekend: sábado completo → +4 XP bonus (6 bloques requeridos; Jugos es opcional)
    sat_keys = {
        "sat_bloque1", "sat_gym_bloque", "sat_textiles_bloque",
        "sat_limpieza_bloque", "sat_bano_bloque", "sat_barrido_bloque",
    }
    if sat_keys.issubset(set(keys_today)):
        with get_db() as db:
            sat_done = db.execute(
                "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: Sábado Completo' AND date=?",
                (today,)
            ).fetchone()
        if not sat_done:
            _award_xp(4, "bonus", "Combo: Sábado Completo")
            _award_coins(2, "bonus", "Combo: Sábado Completo")
            combos.append({"type": "sat_complete", "icon": "🔥", "name": "Sábado Completo", "description": "Todos los bloques del sábado completados", "xp": 4, "ec": 2})

    # Weekend: domingo completo → +5 XP bonus (9 bloques)
    sun_keys = {
        "sun_cafe_bloque", "sun_gym_bloque", "sun_nevera_bloque", "sun_comidas_bloque",
        "sun_guardado_bloque", "sun_planchar_bloque", "sun_planeacion_bloque",
        "sun_prioridades_bloque", "sun_cierre_bloque",
    }
    if sun_keys.issubset(set(keys_today)):
        with get_db() as db:
            sun_done = db.execute(
                "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: Domingo Completo' AND date=?",
                (today,)
            ).fetchone()
        if not sun_done:
            _award_xp(5, "bonus", "Combo: Domingo Completo")
            _award_coins(3, "bonus", "Combo: Domingo Completo")
            combos.append({"type": "sun_complete", "icon": "✦", "name": "Domingo Completo", "description": "Ritual dominical cumplido en su totalidad", "xp": 5, "ec": 3})

    return combos


# ── Daily Classification ──────────────────────────────────────────────────────

# Semana del mes (bloques de 7 días, 1-indexed) en la que se relaja el estándar
# de Oro/Diamante a propósito — ciclo de descanso planeado a nivel sistema, no
# una decisión manual del usuario cada vez. Configurable.
RECOVERY_WEEK_OF_MONTH = 4


def _is_recovery_week(d):
    return ((d.day - 1) // 7) + 1 == RECOVERY_WEEK_OF_MONTH


def get_daily_classification(date_str=None):
    today    = date_str or today_str()
    d_obj    = date.fromisoformat(today)
    defs     = adefs.get_active_flat()
    recovery = _is_recovery_week(d_obj)
    # Anclas semanales rotativas (Fase 3): solo cuentan en el denominador del
    # día si están programadas para ese día de la semana — evita que una
    # ancla de otro día (ej. Francés en lunes) infle "cuántas anclas hay hoy".
    wd_today       = adefs.DAY_CODES[d_obj.weekday()]
    defs_today = {k: v for k, v in defs.items() if adefs.eligible_today(v, wd_today, d_obj)}

    with get_db() as db:
        total_xp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=?", (today,)
        ).fetchone()["s"]
        keys = [r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=? AND activity_key != 'priority_bonus'",
            (today,)
        ).fetchall()]
        eury_today = db.execute(
            "SELECT 1 FROM activity_logs WHERE activity_key='eurythmia_session' AND date=?", (today,)
        ).fetchone() is not None

    done_today = [defs[k] for k in keys if k in defs]

    pillars_today = {d["pillar"] for d in done_today if d["effective_type"] != "ocasional"}
    if eury_today:
        pillars_today.add("eury")
    # Harma queda fuera de la cobertura de Diamante a propósito (no es uno de los 8 pilares)
    pillars_today &= set(adefs.PILLARS)

    anchor_defs      = [d for d in defs_today.values() if d["effective_type"] == "ancla"]
    done_anchor_keys = {d["key"] for d in done_today if d["effective_type"] == "ancla"}
    anchors_done     = len(done_anchor_keys)
    # Los touches cadence='weekly' (ej. tiempo de calidad, networking) no se
    # exigen a diario — no cuentan en el conteo de touches del día, solo dan
    # XP/EC y cobertura de pilar cuando se registran.
    touch_defs   = [d for d in defs_today.values() if d["effective_type"] == "touch" and d.get("cadence", "daily") == "daily"]
    done_touch_keys = {d["key"] for d in done_today if d["effective_type"] == "touch" and d.get("cadence", "daily") == "daily"}
    touches_done = len(done_touch_keys)

    # Cobertura de sesiones (mañana/tarde/noche/cualquier-momento) entre los
    # touches ya registrados hoy — ver nota de GOLD_MIN_SESSIONS arriba.
    sessions_available = set()
    for d in touch_defs:
        sessions_available |= _sessions_of(d)
    sessions_covered = set()
    for d in touch_defs:
        if d["key"] in done_touch_keys:
            sessions_covered |= _sessions_of(d)

    gold_min_touches  = RECOVERY_GOLD_MIN_TOUCHES  if recovery else GOLD_MIN_TOUCHES
    gold_min_sessions = min(
        (RECOVERY_GOLD_MIN_SESSIONS if recovery else GOLD_MIN_SESSIONS),
        len(sessions_available)
    )
    # Anclas extra cuentan para Oro: la 1ª ancla del día ya la exige Hierro,
    # pero hasta ahora cualquier ancla adicional (días con 2-4 elegibles, ver
    # nota de Diamante arriba) no daba NINGÚN crédito hacia Oro pese a ser el
    # touch de mayor esfuerzo del sistema — un usuario podía completar TODAS
    # sus anclas del día y seguir en Hierro solo por no repartir touches, lo
    # cual castiga precisamente el esfuerzo que el propio diseño de Diamante
    # ya trata como la señal fuerte del día ("anclas completas"). Cada ancla
    # extra descuenta 1 touch y 1 sesión exigidos para Oro (piso de 1 en
    # ambos): sigue haciendo falta repartir esfuerzo en el día para llegar a
    # Oro, pero ya no se ignora lo que sí hiciste con tus anclas.
    extra_anchors = max(0, anchors_done - 1) if anchor_defs else 0
    if extra_anchors:
        gold_min_touches  = max(1, gold_min_touches - extra_anchors)
        if sessions_available:
            gold_min_sessions = max(1, gold_min_sessions - extra_anchors)
    # En semana de descarga, Hierro también se alcanza solo con touches —
    # "menos anclas exigidas" — sin necesidad de completar la sesión larga.
    hierro_ok = (not anchor_defs) or (anchors_done >= 1) or (
        recovery and touch_defs and touches_done >= RECOVERY_HIERRO_TOUCHES
    )

    rank = "carbon"
    if hierro_ok:
        rank = "iron"
        gold_ok = touches_done >= gold_min_touches and len(sessions_covered) >= gold_min_sessions
        if not touch_defs or gold_ok:
            rank = "gold"
            if not anchor_defs or anchors_done >= len(anchor_defs):
                rank = "diamond"

    info = CLASSIFICATION[rank].copy()
    info["icon_lucide"] = lucide_for(info["icon"])
    info.update({
        "rank": rank, "xp": total_xp,
        "cats": len(pillars_today), "pillars": sorted(pillars_today),
        "anchors_done": anchors_done, "anchors_total": len(anchor_defs),
        "touches_done": touches_done, "touches_total": len(touch_defs),
        "sessions_covered": len(sessions_covered), "sessions_available": len(sessions_available),
        "recovery_week": recovery,
        "next_hint": _next_rank_hint(
            rank, anchor_defs, done_anchor_keys, touch_defs, touches_done, gold_min_touches,
            sessions_covered, sessions_available, gold_min_sessions
        ),
        "next_pct": _next_rank_pct(
            rank, anchor_defs, done_anchor_keys, touch_defs, touches_done, gold_min_touches,
            sessions_covered, gold_min_sessions, recovery
        ),
    })
    return info


_WEEKDAY_LABELS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_RANK_POINTS        = {"carbon": 0, "iron": 1, "gold": 2, "diamond": 3}
_WEEKLY_DESC = {
    "diamond": "Semana de nivel máximo: la mayoría de tus días fueron Oro o Diamante.",
    "gold":    "Buena semana: cumpliste tus anclas y touches con constancia.",
    "iron":    "Semana sólida: completaste tu ancla casi todos los días, pero faltó volumen para Oro.",
    "carbon":  "Semana floja: la mayoría de los días no llegaste a completar tu ancla.",
}


def get_weekly_classification(monday_str):
    """Agrega get_daily_classification() sobre los 7 días lunes→domingo que
    empiezan en `monday_str` — mismo esquema Carbón/Hierro/Oro/Diamante que
    ya existe por día, aplicado a la semana completa, más el detalle día por
    día para poder mostrar "qué hiciste cada día de esta semana".
    Días futuros dentro del rango (semana en curso) se marcan future=True y
    no cuentan para el promedio."""
    monday = date.fromisoformat(monday_str)
    today  = today_date()

    days = []
    rank_counts  = {"carbon": 0, "iron": 0, "gold": 0, "diamond": 0}
    total_points = 0
    total_xp     = 0

    for i in range(7):
        d     = monday + timedelta(days=i)
        d_str = d.isoformat()
        if d > today:
            days.append({"date": d_str, "weekday": _WEEKDAY_LABELS_ES[i], "future": True, "rank": None})
            continue
        info = get_daily_classification(d_str)
        rank_counts[info["rank"]] += 1
        total_points += _RANK_POINTS[info["rank"]]
        total_xp     += info["xp"]
        days.append({
            "date": d_str, "weekday": _WEEKDAY_LABELS_ES[i], "future": False,
            "rank": info["rank"], "label": info["label"], "icon": info["icon"],
            "icon_lucide": info["icon_lucide"], "color": info["color"], "xp": info["xp"],
            "anchors_done": info["anchors_done"], "anchors_total": info["anchors_total"],
            "touches_done": info["touches_done"], "touches_total": info["touches_total"],
        })

    evaluated  = sum(1 for d in days if not d["future"])
    avg_points = (total_points / evaluated) if evaluated else 0.0

    if evaluated == 0:
        weekly_rank = "carbon"
    elif avg_points >= 2.5:
        weekly_rank = "diamond"
    elif avg_points >= 1.75:
        weekly_rank = "gold"
    elif avg_points >= 1.0:
        weekly_rank = "iron"
    else:
        weekly_rank = "carbon"

    info = CLASSIFICATION[weekly_rank].copy()
    info["icon_lucide"] = lucide_for(info["icon"])
    info.update({
        "rank": weekly_rank,
        "desc": _WEEKLY_DESC[weekly_rank],
        "pct": round(avg_points / 3 * 100) if evaluated else 0,
        "avg_points": round(avg_points, 2),
        "rank_counts": rank_counts,
        "days": days,
        "days_evaluated": evaluated,
        "total_xp": total_xp,
    })
    return info


# La clasificación diaria depende de anclas/touches/pilares cubiertos, no del
# XP acumulado — este hint se calcula aquí (no en el cliente) para que el
# widget de "Clasificación de hoy" nunca muestre una meta de XP inventada que
# no corresponde a la regla real de ascenso de rango.
def _next_rank_hint(rank, anchor_defs, done_anchor_keys, touch_defs, touches_done, gold_min_touches,
                     sessions_covered, sessions_available, gold_min_sessions):
    if rank == "diamond":
        return "✦ Diamante alcanzado"
    if rank == "gold":
        missing_anchors = [a for a in anchor_defs if a["key"] not in done_anchor_keys]
        if not missing_anchors:
            return "Diamante alcanzado"
        labels = " y ".join(a["label"] for a in missing_anchors)
        return f"Completa {labels} → Diamante"
    if rank == "iron":
        faltan_touches  = max(0, gold_min_touches - touches_done)
        faltan_sesiones = max(0, gold_min_sessions - len(sessions_covered))
        if not touch_defs or (faltan_touches <= 0 and faltan_sesiones <= 0):
            return "Oro alcanzado"
        if faltan_touches > 0 and faltan_sesiones <= 0:
            return f"Registra {faltan_touches} touch{'es' if faltan_touches != 1 else ''} más → Oro"
        missing = [s for s in _SESSION_ORDER if s in sessions_available and s not in sessions_covered]
        labels = " y ".join(_SESSION_LABELS[s] for s in missing[:faltan_sesiones])
        sesiones_txt = f"toca {labels}" if labels else f"cubre {faltan_sesiones} sesión{'es' if faltan_sesiones != 1 else ''} más"
        if faltan_touches > 0:
            return f"Registra {faltan_touches} touch{'es' if faltan_touches != 1 else ''} y {sesiones_txt} → Oro"
        return f"{sesiones_txt[0].upper()}{sesiones_txt[1:]} → Oro"
    # carbon
    if anchor_defs:
        return "Completa tu ancla del día → Hierro"
    return "Registra una actividad de hoy → Hierro"


# Progreso (0-100) hacia el SIGUIENTE rango — refleja el cuello de botella real
# (ej. en Hierro→Oro, el mínimo entre touches y sesiones cubiertas, porque
# ambos son requisitos y el que va más atrás es el que de verdad te frena).
# Esto es lo que llena la barra visual junto al hint: la tarjeta deja de
# mostrar solo "en qué rango estás" y muestra "qué tan cerca estás del que sigue".
def _next_rank_pct(rank, anchor_defs, done_anchor_keys, touch_defs, touches_done, gold_min_touches,
                    sessions_covered, gold_min_sessions, recovery):
    if rank == "diamond":
        return 100
    if rank == "gold":
        if not anchor_defs:
            return 100
        return round(100 * len(done_anchor_keys) / len(anchor_defs))
    if rank == "iron":
        if not touch_defs:
            return 100
        touch_frac = min(1.0, touches_done / gold_min_touches) if gold_min_touches else 1.0
        sess_frac  = min(1.0, len(sessions_covered) / gold_min_sessions) if gold_min_sessions else 1.0
        return round(100 * min(touch_frac, sess_frac))
    # carbon — el ancla es un evento binario (no hay "medio ancla"), así que
    # el % real es 0 hasta que se completa; el hint de arriba es lo accionable.
    if recovery and touch_defs:
        return round(100 * min(1.0, touches_done / RECOVERY_HIERRO_TOUCHES))
    return 0


# ── Achievement stats + unlock ────────────────────────────────────────────────

def _gather_achievement_stats():
    today      = today_str()
    _td        = today_date()
    week_start = (_td - timedelta(days=_td.weekday())).isoformat()

    with get_db() as db:
        total_act = db.execute(
            "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key != 'priority_bonus'"
        ).fetchone()["c"]

        keys_today = [r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=? AND activity_key != 'priority_bonus'", (today,)
        ).fetchall()]
        cats_today = {ACTIVITIES[k]["cat"] for k in keys_today if k in ACTIVITIES}

        all_keys = [r["activity_key"] for r in db.execute(
            "SELECT DISTINCT activity_key FROM activity_logs WHERE activity_key != 'priority_bonus'"
        ).fetchall()]
        all_cats = {ACTIVITIES[k]["cat"] for k in all_keys if k in ACTIVITIES}

        prog_keys = [k for k, v in ACTIVITIES.items() if v["cat"] == "Programación"]
        prog_count = 0
        if prog_keys:
            prog_count = db.execute(
                "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key IN ({})".format(
                    ",".join("?" * len(prog_keys))
                ), prog_keys
            ).fetchone()["c"]

        xp_week = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=? AND date<=?",
            (week_start, today)
        ).fetchone()["s"]

        # XP de actividades+bonos únicamente (excluye logros) — para condición semana_elite
        xp_week_acts = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger "
            "WHERE source != 'achievement' AND date>=? AND date<=?",
            (week_start, today)
        ).fetchone()["s"]

        total_coins = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger"
        ).fetchone()["s"]

        had_perfect_day = db.execute(
            "SELECT COUNT(*) as c FROM xp_ledger WHERE source='bonus' AND description='Bonus: Día Perfecto'"
        ).fetchone()["c"] > 0

        total_xp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger"
        ).fetchone()["s"]

        # Conversaciones this month
        month_start = today_date().replace(day=1).isoformat()
        conv_month = db.execute(
            "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key='conversacion' AND date>=?",
            (month_start,)
        ).fetchone()["c"]

        # Goles this month
        gol_month = db.execute(
            "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key='gol' AND date>=?",
            (month_start,)
        ).fetchone()["c"]

        # Days with <3.5h screen time (redes_control)
        redes_7 = db.execute(
            "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key='redes_control' AND date>=?",
            ((today_date() - timedelta(days=7)).isoformat(),)
        ).fetchone()["c"]

        # Diamond days this week
        diamond_week = 0
        for i in range(7):
            d = (today_date() - timedelta(days=i)).isoformat()
            cl = get_daily_classification(d)
            if cl["rank"] == "diamond":
                diamond_week += 1

        # Weekend perfect: both sat + sun combos awarded this ISO week
        sat_combo_week = db.execute(
            "SELECT COUNT(*) as c FROM xp_ledger WHERE description='Combo: Sábado Completo' AND date>=?",
            (week_start,)
        ).fetchone()["c"]
        sun_combo_week = db.execute(
            "SELECT COUNT(*) as c FROM xp_ledger WHERE description='Combo: Domingo Completo' AND date>=?",
            (week_start,)
        ).fetchone()["c"]

    streak     = get_gamification_streak()
    level_info = get_level_info(total_xp)

    return {
        "streak":               streak,
        "total_xp":             total_xp,
        "total_coins":          total_coins,
        "xp_week":              xp_week,
        "xp_week_acts":         xp_week_acts,
        "total_activity_count": total_act,
        "cats_done_today":      cats_today,
        "all_cats_ever":        all_cats,
        "prog_count":           prog_count,
        "had_perfect_day":      had_perfect_day,
        "current_level":        level_info["level"],
        "conv_month":           conv_month,
        "gol_month":            gol_month,
        "redes_7":              redes_7,
        "diamond_week":         diamond_week,
        "weekend_perfect_week": sat_combo_week > 0 and sun_combo_week > 0,
    }


def check_and_unlock():
    with get_db() as db:
        already = {r["key"] for r in db.execute(
            "SELECT key FROM achievements WHERE unlocked_at IS NOT NULL"
        ).fetchall()}

    stats          = _gather_achievement_stats()
    newly_unlocked = []
    now            = datetime.now().isoformat()

    for key, defn in ACHIEVEMENT_DEFS.items():
        if key in already:
            continue
        try:
            met = defn["condition"](stats)
        except Exception:
            met = False
        if not met:
            continue

        with get_db() as db:
            if db.execute("SELECT id FROM achievements WHERE key=?", (key,)).fetchone():
                db.execute(
                    "UPDATE achievements SET unlocked_at=?,coins_earned=?,xp_earned=?,notified=0 WHERE key=?",
                    (now, defn["coins"], defn["xp"], key)
                )
            else:
                db.execute(
                    "INSERT INTO achievements (key,unlocked_at,coins_earned,xp_earned,notified)"
                    " VALUES (?,?,?,?,0)",
                    (key, now, defn["coins"], defn["xp"])
                )
            db.commit()

        if defn["coins"] > 0:
            _award_coins(defn["coins"], "achievement", f"Logro: {defn['name']}")
        if defn["xp"] > 0:
            _award_xp(defn["xp"], "achievement", f"Logro: {defn['name']}")

        newly_unlocked.append({
            "key":         key,
            "name":        defn["name"],
            "description": defn["description"],
            "icon":        defn["icon"],
            "icon_lucide": lucide_for(defn["icon"]),
            "coins":       defn["coins"],
            "xp":          defn["xp"],
        })

    return newly_unlocked


# ── Badge checking (deferred import to avoid circular) ───────────────────────

def _check_badges_safe():
    try:
        from modules.gamification.badges import check_and_unlock_badges
        return check_and_unlock_badges()
    except Exception:
        return []


# ── Perfect Day ───────────────────────────────────────────────────────────────

def _is_perfect_day(today):
    with get_db() as db:
        priors = db.execute("SELECT done FROM priorities WHERE date=?", (today,)).fetchall()
        if len(priors) != 3 or not all(p["done"] for p in priors):
            return False
        xp_today = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=? AND source='activity'",
            (today,)
        ).fetchone()["s"]
    return xp_today >= 10


def _maybe_award_perfect_day(today):
    if not _is_perfect_day(today):
        return None
    with get_db() as db:
        if db.execute(
            "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Bonus: Día Perfecto' AND date=?",
            (today,)
        ).fetchone():
            return None

    _award_xp(5,    "bonus", "Bonus: Día Perfecto")
    _award_coins(10, "bonus", "Bonus: Día Perfecto")

    new_ach = check_and_unlock()
    return {"xp": 5, "ec": 10, "achievements": new_ach}


# ── Full stats snapshot ───────────────────────────────────────────────────────

def get_gamification_stats():
    today      = today_str()
    _td        = today_date()
    week_start = (_td - timedelta(days=_td.weekday())).isoformat()

    with get_db() as db:
        total_xp    = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger").fetchone()["s"]
        xp_today    = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=?",    (today,)).fetchone()["s"]
        xp_week     = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=? AND date<=?", (week_start, today)).fetchone()["s"]
        total_coins = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger").fetchone()["s"]
        coins_today = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger WHERE date=?", (today,)).fetchone()["s"]

        recent_ach = db.execute("""
            SELECT key, unlocked_at, coins_earned, xp_earned
            FROM achievements WHERE unlocked_at IS NOT NULL
            ORDER BY unlocked_at DESC LIMIT 5
        """).fetchall()

        active_events = db.execute("""
            SELECT name, description, end_date, xp_multiplier, coin_multiplier, focus_category, focus_bonus
            FROM special_events
            WHERE is_active=1
              AND (start_date IS NULL OR start_date <= ?)
              AND (end_date   IS NULL OR end_date   >= ?)
        """, (today, today)).fetchall()

        recent_penalties = db.execute(
            "SELECT type, coins_lost, description, date FROM penalty_log ORDER BY date DESC LIMIT 5"
        ).fetchall()

        recent_mults = db.execute(
            "SELECT type, multiplier, triggered_by, date FROM multiplier_log ORDER BY date DESC LIMIT 8"
        ).fetchall()

    streak     = get_gamification_streak()
    level_info = get_level_info(total_xp)
    classification = get_daily_classification(today)

    return {
        **level_info,
        "streak":            streak,
        "streak_mult":       _streak_xp_mult(streak),
        "xp_today":          xp_today,
        "xp_week":           xp_week,
        "total_coins":       total_coins,
        "coins_today":       coins_today,
        "active_events":     [dict(e) for e in active_events],
        "recent_ach":        [dict(a) for a in recent_ach],
        "recent_penalties":  [dict(p) for p in recent_penalties],
        "recent_mults":      [dict(m) for m in recent_mults],
        "classification":    classification,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def process_activity(key, pts, cat, log_id, ec=None):
    streak  = get_gamification_streak()
    if ec is None:
        act_def = adefs.get_by_key(key)
        ec      = act_def["ec"] if act_def else ACTIVITIES.get(key, {}).get("ec", 0)

    xp_mult  = _compute_xp_mult(cat, streak)
    final_xp = max(1, int(pts * xp_mult))

    _award_xp(final_xp, "activity", f"Actividad: {key}", log_id, xp_mult)
    if ec > 0:
        _award_coins(ec, "activity", f"EC: {key}", log_id, 1.0)

    if streak in (7, 30):
        _log_mult_event(f"streak_{streak}", xp_mult, f"Racha de {streak} días alcanzada", "xp")

    today       = today_str()
    keys_today  = _get_today_keys(today)
    combo_bonuses = _check_combo_bonus(today, keys_today)
    perfect_day   = _maybe_award_perfect_day(today)
    new_ach       = check_and_unlock()
    new_badges    = _check_badges_safe()

    return {
        "xp":           final_xp,
        "ec":           ec,
        "xp_mult":      xp_mult,
        "streak":       streak,
        "combo_bonuses":combo_bonuses,
        "perfect_day":  perfect_day,
        "achievements": new_ach,
        "badges":       new_badges,
        "stats":        get_gamification_stats(),
    }


def process_rutina_check(sub_key, xp, ec, cat, bloque_id=None):
    """
    Called by ataraxia module on sub-task completion.
    Awards XP/EC directly; inserts parent bloque_id into activity_logs when complete
    so the combo engine can fire sat/sun combo bonuses.
    """
    today   = today_str()
    now     = datetime.now().isoformat()
    final_xp = 0

    if xp > 0:
        streak   = get_gamification_streak()
        mult     = _compute_xp_mult(cat, streak) if cat else 1.0
        final_xp = max(1, int(xp * mult))
        _award_xp(final_xp, "rutina", f"Rutina: {sub_key}", None, mult)

    if ec > 0:
        _award_coins(ec, "rutina", f"EC Rutina: {sub_key}")

    if bloque_id:
        with get_db() as db:
            if not db.execute(
                "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (bloque_id, today)
            ).fetchone():
                db.execute(
                    "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                    (bloque_id, today, xp)
                )
                db.commit()

    keys_today    = _get_today_keys(today)
    combo_bonuses = _check_combo_bonus(today, keys_today)
    new_ach       = check_and_unlock()
    new_badges    = _check_badges_safe()

    return {
        "xp":           final_xp,
        "ec":           ec,
        "combo_bonuses": combo_bonuses,
        "achievements": new_ach,
        "badges":       new_badges,
        "stats":        get_gamification_stats(),
    }


def process_rutina_uncheck(sub_key, bloque_id=None):
    """Reverses XP/EC awarded for a rutina sub-task and removes bloque log if present."""
    today = today_str()
    with get_db() as db:
        db.execute(
            "DELETE FROM xp_ledger WHERE source='rutina' AND description=? AND date=?",
            (f"Rutina: {sub_key}", today)
        )
        db.execute(
            "DELETE FROM coins_ledger WHERE source='rutina' AND description=? AND date=?",
            (f"EC Rutina: {sub_key}", today)
        )
        if bloque_id:
            db.execute(
                "DELETE FROM activity_logs WHERE activity_key=? AND date=?",
                (bloque_id, today)
            )
        db.commit()
    return {"removed": True, "stats": get_gamification_stats()}


def remove_activity(log_id):
    with get_db() as db:
        db.execute("DELETE FROM xp_ledger    WHERE source='activity' AND reference_id=?", (log_id,))
        db.execute("DELETE FROM coins_ledger WHERE source='activity' AND reference_id=?", (log_id,))
        db.commit()
    return {"removed": True, "stats": get_gamification_stats()}


def process_priority_bonus(today):
    streak  = get_gamification_streak()
    xp_mult = _streak_xp_mult(streak)
    xp      = max(1, int(5 * xp_mult))

    _award_xp(xp,    "bonus", "Bonus: Prioridades x3", None, xp_mult)
    _award_coins(5,  "bonus", "Bonus: Prioridades x3", None, 1.0)

    perfect_day = _maybe_award_perfect_day(today)
    new_ach     = check_and_unlock()

    return {
        "xp":          xp,
        "ec":          5,
        "perfect_day": perfect_day,
        "achievements": new_ach,
        "stats":       get_gamification_stats(),
    }


def remove_priority_bonus(today):
    with get_db() as db:
        db.execute(
            "DELETE FROM xp_ledger    WHERE source='bonus' AND description='Bonus: Prioridades x3' AND date=?",
            (today,)
        )
        db.execute(
            "DELETE FROM coins_ledger WHERE source='bonus' AND description='Bonus: Prioridades x3' AND date=?",
            (today,)
        )
        db.commit()
    return {"removed": True, "stats": get_gamification_stats()}


def process_gtd_task(task_id, priority):
    _XP_GTD   = {"normal": 3, "important": 5, "critical": 8}
    _COIN_GTD = {"normal": 1, "important": 2, "critical": 3}

    streak  = get_gamification_streak()
    xp_mult = _streak_xp_mult(streak)
    base_xp = _XP_GTD.get(priority, 3)
    xp      = max(1, int(base_xp * xp_mult))
    coins   = _COIN_GTD.get(priority, 1)

    _award_xp(xp,     "task", f"Tarea GTD #{task_id}", task_id, xp_mult)
    _award_coins(coins, "task", f"Tarea GTD #{task_id}", task_id, 1.0)

    new_ach = check_and_unlock()
    return {
        "xp":          xp,
        "coins":       coins,
        "achievements": new_ach,
        "stats":       get_gamification_stats(),
    }


def process_gtd_daily_bonus():
    _award_xp(5,    "bonus", "Bonus diario GTD (3 tareas)")
    _award_coins(3, "bonus", "Bonus diario GTD (3 tareas)")
    new_ach = check_and_unlock()
    return {"xp": 5, "coins": 3, "achievements": new_ach}


def apply_penalty(penalty_type, context=""):
    PENALTIES = {
        "social_media_light":   (2,  "Exceso leve de redes sociales"),
        "social_media_heavy":   (10, "Exceso severo de redes sociales"),
        "missed_priorities_3d": (20, "3 días sin completar prioridades"),
        "streak_broken_minor":  (5,  "Racha rota (< 7 días)"),
        "streak_broken_major":  (15, "Racha rota (≥ 10 días)"),
    }
    if penalty_type not in PENALTIES:
        return {"error": "unknown penalty type"}

    amount, desc = PENALTIES[penalty_type]
    today = today_str()
    now   = datetime.now().isoformat()
    full_desc = desc + (f" | {context}" if context else "")

    with get_db() as db:
        already_today = abs(db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger WHERE source='penalty' AND date=?", (today,)
        ).fetchone()["s"])

        if already_today >= 50:
            return {"skipped": True, "reason": "daily penalty cap (50 EC) reached"}

        capped = min(amount, 50 - already_today)

        db.execute(
            "INSERT INTO coins_ledger (amount,source,description,multiplier,date,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (-capped, "penalty", full_desc, 1.0, today, now)
        )
        db.execute(
            "INSERT INTO penalty_log (type,coins_lost,description,date,created_at)"
            " VALUES (?,?,?,?,?)",
            (penalty_type, capped, full_desc, today, now)
        )
        db.commit()

    return {
        "applied":     True,
        "type":        penalty_type,
        "coins_lost":  capped,
        "description": full_desc,
        "stats":       get_gamification_stats(),
    }
