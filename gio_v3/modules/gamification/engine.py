"""
Gamification Engine — central rule processor.

Every point-earning or coin-earning action flows through here.
No route should write directly to xp_ledger or coins_ledger.
"""
from datetime import date, datetime, timedelta
from database import get_db
from data import ACTIVITIES, ACTIVITY_CATEGORIES
from modules.gamification.achievements import ACHIEVEMENT_DEFS

# ── Level System ──────────────────────────────────────────────────────────────

LEVEL_THRESHOLDS = [
    (0,       1,  "Novato"),
    (500,     2,  "Aprendiz"),
    (1_500,   3,  "Constante"),
    (3_500,   4,  "Enfocado"),
    (7_000,   5,  "Disciplinado"),
    (12_000,  6,  "Ejecutor"),
    (20_000,  7,  "Estratega"),
    (32_000,  8,  "Élite"),
    (50_000,  9,  "Maestro"),
    (75_000,  10, "Supremo"),
    (100_000, 11, "Leyenda"),
    (150_000, 12, "Bestia"),   # hidden until achievement unlocked
]


def get_level_info(total_xp):
    level, name, next_idx = 1, "Novato", 1
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
        "level":      level,
        "level_name": name,
        "total_xp":   total_xp,
        "level_pct":  pct,
        "xp_to_next": max(0, next_threshold - total_xp),
        "next_xp":    next_threshold,
    }


# ── XP / Coins formulas ───────────────────────────────────────────────────────

_XP_BY_PTS   = {1: 10, 2: 20, 3: 30, 4: 40, 5: 60}
_COIN_BY_PTS = {1: 2,  2: 4,  3: 6,  4: 8,  5: 12}
_XP_GTD      = {"normal": 50, "important": 75, "critical": 100}
_COIN_GTD    = {"normal": 5,  "important": 10, "critical": 15}


# ── Streak ────────────────────────────────────────────────────────────────────

def get_gamification_streak():
    """Combined streak: any day with xp_ledger OR activity_logs entries counts."""
    with get_db() as db:
        xp_dates  = {r["date"] for r in db.execute("SELECT DISTINCT date FROM xp_ledger").fetchall()}
        act_dates = {r["date"] for r in db.execute("SELECT DISTINCT date FROM activity_logs").fetchall()}
    all_dates = xp_dates | act_dates
    streak, check = 0, date.today()
    while check.isoformat() in all_dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


def _streak_coin_mult(streak):
    if streak >= 30: return 2.5
    if streak >= 21: return 2.0
    if streak >= 10: return 1.5
    if streak >= 7:  return 1.25
    return 1.0


# ── Active Special Events ─────────────────────────────────────────────────────

def _get_active_events():
    today = date.today().isoformat()
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM special_events
            WHERE is_active=1
              AND (start_date IS NULL OR start_date <= ?)
              AND (end_date   IS NULL OR end_date   >= ?)
        """, (today, today)).fetchall()
    return [dict(r) for r in rows]


def _compute_multipliers(base_xp, base_coins, category=None, streak=0):
    """Apply streak + active events. Returns final amounts and multiplier info."""
    xp_mult   = 1.0
    coin_mult = _streak_coin_mult(streak)   # streak only boosts coins
    active_event_names = []

    for ev in _get_active_events():
        xp_mult *= ev["xp_multiplier"]
        # If event focuses on a specific category and we match, apply extra focus bonus
        if category and ev["focus_category"] and ev["focus_category"] == category:
            coin_mult *= ev["coin_multiplier"] * ev["focus_bonus"]
        else:
            coin_mult *= ev["coin_multiplier"]
        active_event_names.append(ev["name"])

    # Hard cap at 3x to prevent abuse
    xp_mult   = min(round(xp_mult,   2), 3.0)
    coin_mult = min(round(coin_mult,  2), 3.0)

    return {
        "xp":     int(base_xp   * xp_mult),
        "coins":  int(base_coins * coin_mult),
        "xp_m":   xp_mult,
        "coin_m": coin_mult,
        "events": active_event_names,
    }


# ── Ledger writers ────────────────────────────────────────────────────────────

def _award_xp(amount, source, desc, ref_id=None, mult=1.0):
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO xp_ledger (amount,source,reference_id,description,multiplier,date,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (amount, source, ref_id, desc, mult, date.today().isoformat(), now)
        )
        db.commit()


def _award_coins(amount, source, desc, ref_id=None, mult=1.0):
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO coins_ledger (amount,source,reference_id,description,multiplier,date,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (amount, source, ref_id, desc, mult, date.today().isoformat(), now)
        )
        db.commit()


def _log_mult_event(type_, mult, triggered_by, applies_to, expires_at=None):
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO multiplier_log (type,multiplier,triggered_by,applies_to,date,expires_at,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (type_, mult, triggered_by, applies_to, date.today().isoformat(), expires_at, now)
        )
        db.commit()


# ── Achievement stats + unlock ────────────────────────────────────────────────

def _gather_achievement_stats():
    today      = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

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
        if prog_keys:
            prog_count = db.execute(
                "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key IN ({})".format(
                    ",".join("?" * len(prog_keys))
                ), prog_keys
            ).fetchone()["c"]
        else:
            prog_count = 0

        xp_week = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=?", (week_start,)
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
    }


def check_and_unlock():
    """Check all achievement conditions, unlock newly met ones, return list of newly unlocked."""
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


# ── Perfect Day ───────────────────────────────────────────────────────────────

def _is_perfect_day(today):
    with get_db() as db:
        priors = db.execute("SELECT done FROM priorities WHERE date=?", (today,)).fetchall()
        if len(priors) != 3 or not all(p["done"] for p in priors):
            return False
        pts = db.execute(
            "SELECT COALESCE(SUM(pts),0) as s FROM activity_logs"
            " WHERE date=? AND activity_key != 'priority_bonus'",
            (today,)
        ).fetchone()["s"]
    return pts >= 5


def _maybe_award_perfect_day(today):
    """Awards perfect day bonus once per day. Returns bonus dict or None."""
    if not _is_perfect_day(today):
        return None
    with get_db() as db:
        if db.execute(
            "SELECT id FROM xp_ledger WHERE source='bonus' AND description='Bonus: Día Perfecto' AND date=?",
            (today,)
        ).fetchone():
            return None

    _award_xp(150,   "bonus", "Bonus: Día Perfecto")
    _award_coins(50, "bonus", "Bonus: Día Perfecto")
    _log_mult_event("perfect_day", 1.0, "Día Perfecto completado", "both")

    new_ach = check_and_unlock()
    return {"xp": 150, "coins": 50, "achievements": new_ach}


# ── Full stats snapshot ───────────────────────────────────────────────────────

def get_gamification_stats():
    today      = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    with get_db() as db:
        total_xp    = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger").fetchone()["s"]
        xp_today    = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=?",    (today,)).fetchone()["s"]
        xp_week     = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=?",   (week_start,)).fetchone()["s"]
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

    return {
        **level_info,
        "streak":            streak,
        "streak_mult":       _streak_coin_mult(streak),
        "xp_today":          xp_today,
        "xp_week":           xp_week,
        "total_coins":       total_coins,
        "coins_today":       coins_today,
        "active_events":     [dict(e) for e in active_events],
        "recent_ach":        [dict(a) for a in recent_ach],
        "recent_penalties":  [dict(p) for p in recent_penalties],
        "recent_mults":      [dict(m) for m in recent_mults],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def process_activity(key, pts, cat, log_id):
    """Call this immediately after inserting a row into activity_logs."""
    streak = get_gamification_streak()
    m = _compute_multipliers(_XP_BY_PTS.get(pts, pts * 10), _COIN_BY_PTS.get(pts, pts * 2), cat, streak)

    _award_xp(m["xp"],    "activity", f"Actividad: {key}", log_id, m["xp_m"])
    _award_coins(m["coins"], "activity", f"Actividad: {key}", log_id, m["coin_m"])

    if streak in (7, 10, 21, 30):
        _log_mult_event(f"streak_{streak}", m["coin_m"], f"Racha de {streak} días alcanzada", "coins")

    today       = date.today().isoformat()
    perfect_day = _maybe_award_perfect_day(today)
    new_ach     = check_and_unlock()

    return {
        "xp":          m["xp"],
        "coins":       m["coins"],
        "xp_mult":     m["xp_m"],
        "coin_mult":   m["coin_m"],
        "streak":      streak,
        "events":      m["events"],
        "perfect_day": perfect_day,
        "achievements": new_ach,
        "stats":       get_gamification_stats(),
    }


def remove_activity(log_id):
    """Call this after deleting a row from activity_logs (toggle off)."""
    with get_db() as db:
        db.execute("DELETE FROM xp_ledger    WHERE source='activity' AND reference_id=?", (log_id,))
        db.execute("DELETE FROM coins_ledger WHERE source='activity' AND reference_id=?", (log_id,))
        db.commit()
    return {"removed": True, "stats": get_gamification_stats()}


def process_priority_bonus(today):
    """Call when all 3 priorities are newly completed."""
    streak = get_gamification_streak()
    m = _compute_multipliers(30, 10, None, streak)

    _award_xp(m["xp"],    "bonus", "Bonus: Prioridades x3", None, m["xp_m"])
    _award_coins(m["coins"], "bonus", "Bonus: Prioridades x3", None, m["coin_m"])

    perfect_day = _maybe_award_perfect_day(today)
    new_ach     = check_and_unlock()

    return {
        "xp":          m["xp"],
        "coins":       m["coins"],
        "perfect_day": perfect_day,
        "achievements": new_ach,
        "stats":       get_gamification_stats(),
    }


def remove_priority_bonus(today):
    """Call when a priority is un-completed and all-3 condition breaks."""
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
    """Call when a GTD task is marked complete."""
    streak = get_gamification_streak()
    m = _compute_multipliers(_XP_GTD.get(priority, 50), _COIN_GTD.get(priority, 5), None, streak)

    _award_xp(m["xp"],    "task", f"Tarea GTD #{task_id}", task_id, m["xp_m"])
    _award_coins(m["coins"], "task", f"Tarea GTD #{task_id}", task_id, m["coin_m"])

    new_ach = check_and_unlock()
    return {
        "xp":          m["xp"],
        "coins":       m["coins"],
        "achievements": new_ach,
        "stats":       get_gamification_stats(),
    }


def process_gtd_daily_bonus():
    """Call when a user completes their 3rd GTD task in a day (bonus event)."""
    m = _compute_multipliers(75, 20, None, 0)

    _award_xp(m["xp"],    "bonus", "Bonus diario GTD (3 tareas)", None, m["xp_m"])
    _award_coins(m["coins"], "bonus", "Bonus diario GTD (3 tareas)", None, m["coin_m"])

    new_ach = check_and_unlock()
    return {"xp": m["xp"], "coins": m["coins"], "achievements": new_ach}


def apply_penalty(penalty_type, context=""):
    """Deduct coins as penalty. Caps at -100 coins/day. Never reduces XP."""
    PENALTIES = {
        "social_media_light":   (5,  "Exceso leve de redes sociales"),
        "social_media_heavy":   (20, "Exceso severo de redes sociales"),
        "missed_priorities_3d": (50, "3 días sin completar prioridades"),
        "streak_broken_minor":  (10, "Racha rota (< 7 días)"),
        "streak_broken_major":  (30, "Racha rota (≥ 10 días)"),
    }
    if penalty_type not in PENALTIES:
        return {"error": "unknown penalty type"}

    amount, desc = PENALTIES[penalty_type]
    today = date.today().isoformat()
    now   = datetime.now().isoformat()
    full_desc = desc + (f" | {context}" if context else "")

    with get_db() as db:
        already_today = abs(db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger WHERE source='penalty' AND date=?", (today,)
        ).fetchone()["s"])

        if already_today >= 100:
            return {"skipped": True, "reason": "daily penalty cap (100 coins) reached"}

        capped = min(amount, 100 - already_today)

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
