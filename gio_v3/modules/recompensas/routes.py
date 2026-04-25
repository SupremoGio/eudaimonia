from flask import Blueprint, render_template, request, jsonify
from datetime import date, datetime, timedelta
from database import get_db
from modules.gamification.engine import get_gamification_stats

recompensas_bp = Blueprint('recompensas', __name__, template_folder='../../templates')


def _get_ec_balance():
    with get_db() as db:
        total = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger").fetchone()["s"]
    return max(0, total)


def _get_level():
    from modules.gamification.engine import get_level_info
    with get_db() as db:
        total_xp = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger").fetchone()["s"]
    return get_level_info(total_xp)


def _get_all_rewards():
    with get_db() as db:
        rows = db.execute("SELECT * FROM rewards ORDER BY ec_cost ASC").fetchall()
    return [dict(r) for r in rows]


def _can_redeem(reward, ec_balance, current_level):
    if ec_balance < reward["ec_cost"]:
        return False, "EC insuficientes"
    if current_level < reward["level_required"]:
        return False, f"Nivel {reward['level_required']} requerido"
    if reward["cooldown_days"] > 0 and reward["last_redeemed"]:
        cooldown_end = (
            datetime.fromisoformat(reward["last_redeemed"]) +
            timedelta(days=reward["cooldown_days"])
        ).date()
        if date.today() < cooldown_end:
            days_left = (cooldown_end - date.today()).days
            return False, f"Cooldown: {days_left} días restantes"
    if reward["badge_required"]:
        with get_db() as db:
            badge = db.execute(
                "SELECT unlocked_at FROM badges WHERE key=? AND unlocked_at IS NOT NULL",
                (reward["badge_required"],)
            ).fetchone()
        if not badge:
            return False, f"Badge requerido: {reward['badge_required']}"
    return True, "ok"


@recompensas_bp.route('/')
def index():
    ec_balance    = _get_ec_balance()
    level_info    = _get_level()
    rewards       = _get_all_rewards()
    current_level = level_info["level"]

    for r in rewards:
        can, reason = _can_redeem(r, ec_balance, current_level)
        r["can_redeem"] = can
        r["block_reason"] = reason if not can else ""

    return render_template('recompensas/index.html',
        rewards      = rewards,
        ec_balance   = ec_balance,
        level_info   = level_info,
        gam          = get_gamification_stats(),
    )


@recompensas_bp.route('/api/rewards', methods=['GET'])
def list_rewards():
    ec_balance    = _get_ec_balance()
    level_info    = _get_level()
    rewards       = _get_all_rewards()
    current_level = level_info["level"]
    for r in rewards:
        can, reason = _can_redeem(r, ec_balance, current_level)
        r["can_redeem"] = can
        r["block_reason"] = reason if not can else ""
    return jsonify({"rewards": rewards, "ec_balance": ec_balance, "level": current_level})


@recompensas_bp.route('/api/rewards', methods=['POST'])
def create_reward():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO rewards (name, description, ec_cost, level_required, badge_required, cooldown_days, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                name,
                data.get("description", ""),
                int(data.get("ec_cost", 0)),
                int(data.get("level_required", 1)),
                data.get("badge_required", ""),
                int(data.get("cooldown_days", 0)),
                now,
            )
        )
        db.commit()
        row = db.execute("SELECT * FROM rewards ORDER BY id DESC LIMIT 1").fetchone()
    return jsonify(dict(row)), 201


@recompensas_bp.route('/api/rewards/<int:reward_id>', methods=['PUT'])
def update_reward(reward_id):
    data = request.json or {}
    with get_db() as db:
        row = db.execute("SELECT * FROM rewards WHERE id=?", (reward_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        db.execute(
            """UPDATE rewards SET name=?, description=?, ec_cost=?, level_required=?,
               badge_required=?, cooldown_days=? WHERE id=?""",
            (
                data.get("name", row["name"]),
                data.get("description", row["description"]),
                int(data.get("ec_cost", row["ec_cost"])),
                int(data.get("level_required", row["level_required"])),
                data.get("badge_required", row["badge_required"]),
                int(data.get("cooldown_days", row["cooldown_days"])),
                reward_id,
            )
        )
        db.commit()
        updated = db.execute("SELECT * FROM rewards WHERE id=?", (reward_id,)).fetchone()
    return jsonify(dict(updated))


@recompensas_bp.route('/api/rewards/<int:reward_id>', methods=['DELETE'])
def delete_reward(reward_id):
    with get_db() as db:
        db.execute("DELETE FROM rewards WHERE id=?", (reward_id,))
        db.commit()
    return jsonify({"ok": True})


@recompensas_bp.route('/api/rewards/<int:reward_id>/redeem', methods=['POST'])
def redeem_reward(reward_id):
    ec_balance  = _get_ec_balance()
    level_info  = _get_level()

    with get_db() as db:
        reward = db.execute("SELECT * FROM rewards WHERE id=?", (reward_id,)).fetchone()
        if not reward:
            return jsonify({"error": "not found"}), 404
        reward = dict(reward)

    can, reason = _can_redeem(reward, ec_balance, level_info["level"])
    if not can:
        return jsonify({"error": reason}), 400

    now = datetime.now().isoformat()
    cost = reward["ec_cost"]

    with get_db() as db:
        db.execute(
            "INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (-cost, "reward", f"Recompensa: {reward['name']}", 1.0, date.today().isoformat(), now)
        )
        db.execute(
            "UPDATE rewards SET last_redeemed=?, status='redeemed' WHERE id=?",
            (now, reward_id)
        )
        db.commit()

    return jsonify({
        "redeemed": True,
        "reward": reward["name"],
        "ec_spent": cost,
        "ec_remaining": ec_balance - cost,
    })
