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
from datetime import datetime, timedelta
from database import get_db
from data import ACTIVITIES, ACTIVITY_CATEGORIES, VIRTUE_CATS
from modules.gamification.achievements import ACHIEVEMENT_DEFS
from utils import today_str, today_date

# ── Level System (10 Stoic Levels, 5 500 XP in 1 year) ───────────────────────
LEVEL_THRESHOLDS = [
    (0,     1,  "PROKOPTON"),
    (200,   2,  "EFEBO"),
    (500,   3,  "ASQUETÉS"),
    (1000,  4,  "ESTRATEGOS"),
    (1800,  5,  "AUTARKÉS"),
    (2700,  6,  "POLÍMATA"),
    (3600,  7,  "ARETÉ"),
    (4400,  8,  "HEGEMÓN"),
    (5000,  9,  "SOPHOS"),
    (5500,  10, "EUDAIMÓN"),
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
                "desc": "20+ XP · ≥1 acción alto impacto"},
    "gold":    {"label": "Oro",      "icon": "🥇", "color": "#fbbf24",
                "desc": "16+ XP · ≥3 categorías"},
    "iron":    {"label": "Hierro",   "icon": "⚔️",  "color": "#94a3b8",
                "desc": "8–15 XP · ≥2 categorías"},
    "carbon":  {"label": "Carbón",   "icon": "🪨",  "color": "#475569",
                "desc": "<7 XP o sin acciones de progreso"},
}


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
        combos.append({"type": "trio", "label": "LOGOI+HEGEMONIKON+PAIDEIA", "xp": 3})

    # 5 categorías en un día → +5 XP
    with get_db() as db:
        five_done = db.execute(
            "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: 5 categorías' AND date=?",
            (today,)
        ).fetchone()

    if len(cats) >= 5 and not five_done:
        _award_xp(5, "bonus", "Combo: 5 categorías")
        combos.append({"type": "5cats", "label": "5 Categorías", "xp": 5})

    # Weekend: sábado completo → +4 XP bonus
    sat_keys = {"sat_bloque1", "sat_bloque2", "sat_bloque3"}
    if sat_keys.issubset(set(keys_today)):
        with get_db() as db:
            sat_done = db.execute(
                "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: Sábado Completo' AND date=?",
                (today,)
            ).fetchone()
        if not sat_done:
            _award_xp(4, "bonus", "Combo: Sábado Completo")
            _award_coins(2, "bonus", "Combo: Sábado Completo")
            combos.append({"type": "sat_complete", "label": "Sábado Completo", "xp": 4})

    # Weekend: domingo completo → +5 XP bonus
    sun_keys = {"sun_reflexion", "sun_diseno", "sun_comidas", "sun_jugos", "sun_planchar"}
    if sun_keys.issubset(set(keys_today)):
        with get_db() as db:
            sun_done = db.execute(
                "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Combo: Domingo Completo' AND date=?",
                (today,)
            ).fetchone()
        if not sun_done:
            _award_xp(5, "bonus", "Combo: Domingo Completo")
            _award_coins(3, "bonus", "Combo: Domingo Completo")
            combos.append({"type": "sun_complete", "label": "Domingo Completo", "xp": 5})

    return combos


# ── Daily Classification ──────────────────────────────────────────────────────

def get_daily_classification(date_str=None):
    today = date_str or today_str()
    with get_db() as db:
        total_xp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=?", (today,)
        ).fetchone()["s"]
        keys = [r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=? AND activity_key != 'priority_bonus'",
            (today,)
        ).fetchall()]

    cats       = {ACTIVITIES[k]["cat"] for k in keys if k in ACTIVITIES}
    has_alto   = any(ACTIVITIES[k].get("tier") == "alto" for k in keys if k in ACTIVITIES)
    has_progreso = any(ACTIVITIES[k].get("tier") in ("progreso", "alto") for k in keys if k in ACTIVITIES)

    if total_xp >= 20 and has_alto:
        rank = "diamond"
    elif total_xp >= 16 and len(cats) >= 3:
        rank = "gold"
    elif total_xp >= 8 and len(cats) >= 2 and has_progreso:
        rank = "iron"
    else:
        rank = "carbon"

    info = CLASSIFICATION[rank].copy()
    info.update({"rank": rank, "xp": total_xp, "cats": len(cats), "has_alto": has_alto})
    return info


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

    streak     = get_gamification_streak()
    level_info = get_level_info(total_xp)

    return {
        "streak":               streak,
        "total_xp":             total_xp,
        "total_coins":          total_coins,
        "xp_week":              xp_week,
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

def process_activity(key, pts, cat, log_id):
    streak  = get_gamification_streak()
    ec      = ACTIVITIES.get(key, {}).get("ec", 0)

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
