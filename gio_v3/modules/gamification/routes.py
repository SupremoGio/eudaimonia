from flask import Blueprint, jsonify, request, render_template
from datetime import date, datetime, timedelta
from database import get_db
from modules.gamification.engine import (
    get_gamification_stats, get_level_info, apply_penalty, check_and_unlock,
    get_daily_classification,
)
from modules.gamification.achievements import ACHIEVEMENT_DEFS
from modules.gamification.badges import get_all_badges, check_and_unlock_badges, get_active_perks, BADGE_DEFS, TIER_LABELS

gamification_bp = Blueprint('gamification', __name__, template_folder='../../templates')


# ── Stats ─────────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/stats')
def stats():
    return jsonify(get_gamification_stats())


# ── Daily Classification ──────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/classification')
def classification():
    d = request.args.get('date', date.today().isoformat())
    return jsonify(get_daily_classification(d))


# ── Achievements ──────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/achievements')
def achievements():
    with get_db() as db:
        rows = {r["key"]: dict(r) for r in db.execute(
            "SELECT key, unlocked_at, coins_earned, xp_earned FROM achievements"
        ).fetchall()}

    result = []
    for key, defn in ACHIEVEMENT_DEFS.items():
        unlocked = key in rows and rows[key]["unlocked_at"] is not None
        entry = {
            "key":          key,
            "name":         defn["name"] if (not defn["hidden"] or unlocked) else "???",
            "description":  defn["description"] if (not defn["hidden"] or unlocked) else "Logro oculto — sigue progresando",
            "icon":         defn["icon"] if (not defn["hidden"] or unlocked) else "🔒",
            "coins":        defn["coins"],
            "xp":           defn["xp"],
            "hidden":       defn["hidden"],
            "unlocked":     unlocked,
            "unlocked_at":  rows[key]["unlocked_at"] if unlocked else None,
        }
        result.append(entry)

    unlocked_count = sum(1 for e in result if e["unlocked"])
    return jsonify({"achievements": result, "unlocked": unlocked_count, "total": len(result)})


# ── Badges ────────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/badges')
def badges():
    all_badges   = get_all_badges()
    active_perks = get_active_perks()
    unlocked     = [b for b in all_badges if b["unlocked"]]
    return jsonify({
        "badges":       all_badges,
        "unlocked":     len(unlocked),
        "total":        len(all_badges),
        "active_perks": active_perks,
    })


@gamification_bp.route('/api/gamification/badges/check', methods=['POST'])
def check_badges():
    newly = check_and_unlock_badges()
    return jsonify({"newly_unlocked": newly, "count": len(newly)})


# ── XP / Coins history ────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/history')
def history():
    limit = min(int(request.args.get('limit', 50)), 200)
    with get_db() as db:
        xp_log = db.execute(
            "SELECT amount,source,description,multiplier,date FROM xp_ledger ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        coin_log = db.execute(
            "SELECT amount,source,description,multiplier,date FROM coins_ledger ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return jsonify({
        "xp_log":   [dict(r) for r in xp_log],
        "ec_log":   [dict(r) for r in coin_log],
    })


# ── Multiplier log ────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/multipliers')
def multipliers():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM multiplier_log ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Penalties ─────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/penalty', methods=['POST'])
def penalty():
    data    = request.json or {}
    ptype   = data.get("type", "")
    context = data.get("context", "")
    result  = apply_penalty(ptype, context)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@gamification_bp.route('/api/gamification/penalties')
def penalty_log():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM penalty_log ORDER BY date DESC, id DESC LIMIT 30"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Special Events ────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/events')
def events():
    with get_db() as db:
        rows = db.execute("SELECT * FROM special_events ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@gamification_bp.route('/api/gamification/events/<key>/activate', methods=['POST'])
def activate_event(key):
    data       = request.json or {}
    start_date = data.get("start_date") or date.today().isoformat()
    end_date   = data.get("end_date")

    with get_db() as db:
        ev = db.execute("SELECT id FROM special_events WHERE key=?", (key,)).fetchone()
        if not ev:
            return jsonify({"error": "event not found"}), 404
        db.execute(
            "UPDATE special_events SET is_active=1, start_date=?, end_date=? WHERE key=?",
            (start_date, end_date, key)
        )
        db.commit()
        row = db.execute("SELECT * FROM special_events WHERE key=?", (key,)).fetchone()
    return jsonify(dict(row))


@gamification_bp.route('/api/gamification/events/<key>/deactivate', methods=['POST'])
def deactivate_event(key):
    with get_db() as db:
        db.execute("UPDATE special_events SET is_active=0 WHERE key=?", (key,))
        db.commit()
        row = db.execute("SELECT * FROM special_events WHERE key=?", (key,)).fetchone()
        if not row:
            return jsonify({"error": "event not found"}), 404
    return jsonify(dict(row))


# ── Manual achievement check ──────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/check-achievements', methods=['POST'])
def check_achievements():
    newly = check_and_unlock()
    return jsonify({"newly_unlocked": newly, "count": len(newly)})


# ── Logros Page ──────────────────────────────────────────────────────────────

@gamification_bp.route('/logros')
def logros():
    stats = get_gamification_stats()
    classification = get_daily_classification()

    # Achievements with ACHIEVEMENT_DEFS metadata merged
    with get_db() as db:
        ach_rows = {r["key"]: dict(r) for r in db.execute(
            "SELECT key, unlocked_at, coins_earned, xp_earned FROM achievements"
        ).fetchall()}
        xp_log = db.execute(
            "SELECT amount, source, description, date FROM xp_ledger ORDER BY id DESC LIMIT 30"
        ).fetchall()

    achievements = []
    for key, defn in ACHIEVEMENT_DEFS.items():
        row = ach_rows.get(key, {})
        unlocked = bool(row.get("unlocked_at"))
        achievements.append({
            "key":         key,
            "name":        defn["name"] if (not defn["hidden"] or unlocked) else "???",
            "description": defn["description"] if (not defn["hidden"] or unlocked) else "Logro oculto — sigue progresando",
            "icon":        defn["icon"] if (not defn["hidden"] or unlocked) else "🔒",
            "coins":       defn["coins"],
            "xp":          defn["xp"],
            "hidden":      defn["hidden"],
            "unlocked":    unlocked,
            "unlocked_at": row.get("unlocked_at", "")[:10] if unlocked else None,
        })

    badges = get_all_badges()

    # Last 7 days classification history
    history = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i))
        cl = get_daily_classification(d.isoformat())
        history.append({
            "date":  d.isoformat(),
            "label": d.strftime("%a %d"),
            "rank":  cl["rank"],
            "icon":  cl["icon"],
            "color": cl["color"],
            "xp":    cl["xp"],
        })

    return render_template('gamification/logros.html',
        stats=stats,
        classification=classification,
        achievements=achievements,
        badges=badges,
        tier_labels=TIER_LABELS,
        xp_log=[dict(r) for r in xp_log],
        history=history,
    )


# ── Full Reset ────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/reset', methods=['POST'])
def reset_gamification():
    """Wipe all XP, EC, streaks, achievements and badges. Keeps rewards config."""
    with get_db() as db:
        db.execute("DELETE FROM xp_ledger")
        db.execute("DELETE FROM coins_ledger")
        db.execute("DELETE FROM multiplier_log")
        db.execute("DELETE FROM penalty_log")
        db.execute("DELETE FROM activity_logs")
        # Achievements y badges se conservan como "ganados" para que no
        # se vuelvan a disparar (evita XP inesperado en la primera actividad post-reset)
        db.commit()
    return jsonify({"ok": True, "message": "Reset completo — empezando desde cero"})
