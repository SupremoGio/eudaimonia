from flask import Blueprint, jsonify, request
from datetime import date, datetime
from database import get_db
from modules.gamification.engine import (
    get_gamification_stats, get_level_info, apply_penalty, check_and_unlock
)
from modules.gamification.achievements import ACHIEVEMENT_DEFS

gamification_bp = Blueprint('gamification', __name__)


# ── Stats ─────────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/stats')
def stats():
    return jsonify(get_gamification_stats())


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
        "coin_log": [dict(r) for r in coin_log],
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


# ── Manual achievement check (debug / admin) ──────────────────────────────────

@gamification_bp.route('/api/gamification/check-achievements', methods=['POST'])
def check_achievements():
    newly = check_and_unlock()
    return jsonify({"newly_unlocked": newly, "count": len(newly)})
