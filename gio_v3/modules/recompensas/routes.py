import random
from flask import Blueprint, render_template, request, jsonify
from datetime import date, datetime, timedelta
from database import get_db
from modules.gamification.engine import get_gamification_stats
from utils import today_str, today_date
from ec_constants import EC_RATE

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


# Artículos que normalmente se compran una sola vez (gadgets, equipo). Solo
# se usa para la migración inicial y como sugerencia; el usuario lo cambia
# en el formulario («Única vez»).
_UNICA_WORDS = ("kindle", "watch", "ipad", "tablet", "iphone", "airpods", "laptop", "macbook", "consola",
                "playstation", "ps5", "nintendo", "xbox", "bicicleta", "monitor", "cámara", "camara",
                "audífonos", "audifonos", "silla", "escritorio", "teclado", "celular", "televisión", "pantalla")


def es_unica_por_nombre(name):
    n = (name or "").lower()
    return any(w in n for w in _UNICA_WORDS)


def _can_redeem(reward, ec_balance, current_level):
    if reward.get("unica") and reward.get("last_redeemed"):
        return False, "Ya la conseguiste"
    if ec_balance < reward["ec_cost"]:
        return False, "EC insuficientes"
    if current_level < reward["level_required"]:
        return False, f"Nivel {reward['level_required']} requerido"
    if reward.get("weekend_only") and today_date().weekday() < 5:
        return False, "Solo disponible en fin de semana"
    if reward["cooldown_days"] > 0 and reward["last_redeemed"]:
        cooldown_end = (
            datetime.fromisoformat(reward["last_redeemed"]) +
            timedelta(days=reward["cooldown_days"])
        ).date()
        if today_date() < cooldown_end:
            days_left = (cooldown_end - today_date()).days
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


# Ícono Lucide por palabras del nombre (la tabla rewards no guarda ícono)
_REWARD_ICONS = [
    (("libro", "book", "kindle", "lectura"), "book-open"), (("ropa", "nike", "tenis", "camisa"), "shirt"),
    (("viaje", "vuelo", "trip"), "plane"), (("watch", "reloj"), "watch"), (("tablet", "ipad"), "tablet"),
    (("salida", "cine", "experiencia", "concierto"), "ticket"), (("cena", "comida", "restaurante", "helado"), "utensils"),
    (("juego", "game", "steam"), "gamepad-2"), (("café", "cafe"), "coffee"), (("masaje", "spa"), "flower-2"),
]


def _reward_icon(name):
    n = (name or "").lower()
    for words, icon in _REWARD_ICONS:
        if any(w in n for w in words):
            return icon
    return "gift"


def _reward_status(r, ec_balance, current_level):
    """available · level (bloqueada por nivel) · wait (cooldown, fin de semana,
    badge) · ec (solo faltan EC) · done (única ya canjeada) — los filtros de la
    tienda V2."""
    if r.get("unica") and r.get("last_redeemed"):
        return "done"
    if r["can_redeem"]:
        return "available"
    if current_level < r["level_required"]:
        return "level"
    if ec_balance < r["ec_cost"]:
        can_otherwise, _ = _can_redeem(r, 10 ** 9, current_level)
        return "ec" if can_otherwise else "wait"
    return "wait"


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
        r["status"] = _reward_status(r, ec_balance, current_level)
        r["icon"] = _reward_icon(r["name"])
        r["ec_pct"] = min(100, round(ec_balance / r["ec_cost"] * 100)) if r["ec_cost"] else 100
    # Las conseguidas (únicas ya canjeadas) al final
    rewards.sort(key=lambda r: r["status"] == "done")

    today = today_date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month_ago = (today - timedelta(days=29)).isoformat()
    with get_db() as db:
        ec_week = db.execute("SELECT COALESCE(SUM(amount),0) s FROM coins_ledger WHERE amount>0 AND date>=?",
                             (week_start,)).fetchone()["s"]
        ec_30 = db.execute("SELECT COALESCE(SUM(amount),0) s FROM coins_ledger WHERE amount>0 AND date>=?",
                           (month_ago,)).fetchone()["s"]
        history = [dict(r) for r in db.execute(
            "SELECT id, ABS(amount) AS ec, description, date, source FROM coins_ledger "
            "WHERE amount < 0 ORDER BY id DESC LIMIT 60").fetchall()]

    return render_template('recompensas/index.html',
        rewards      = rewards,
        ec_balance   = ec_balance,
        level_info   = level_info,
        gam          = get_gamification_stats(),
        ec_rate      = EC_RATE,
        ec_week      = ec_week,
        ec_daily     = round(ec_30 / 30, 1),
        history      = history,
        counts       = {k: sum(1 for r in rewards if r["status"] == k) for k in ("available", "level", "wait", "ec", "done")},
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
            """INSERT INTO rewards (name, description, ec_cost, level_required, badge_required, cooldown_days, weekend_only, created_at, unica)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                name,
                data.get("description", ""),
                int(data.get("ec_cost", 0)),
                int(data.get("level_required", 1)),
                data.get("badge_required", ""),
                int(data.get("cooldown_days", 0)),
                int(bool(data.get("weekend_only", False))),
                now,
                int(bool(data.get("unica", es_unica_por_nombre(name)))),
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
               badge_required=?, cooldown_days=?, weekend_only=?, unica=? WHERE id=?""",
            (
                data.get("name", row["name"]),
                data.get("description", row["description"]),
                int(data.get("ec_cost", row["ec_cost"])),
                int(data.get("level_required", row["level_required"])),
                data.get("badge_required", row["badge_required"]),
                int(data.get("cooldown_days", row["cooldown_days"])),
                int(bool(data.get("weekend_only", row["weekend_only"]))),
                int(bool(data.get("unica", row["unica"]))),
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


@recompensas_bp.route('/api/gasto', methods=['POST'])
def registrar_gasto():
    data = request.json or {}
    ec   = int(data.get('ec', 0))
    desc = (data.get('descripcion') or '').strip()
    if ec <= 0:
        return jsonify({'error': 'EC inválido'}), 400
    if not desc:
        return jsonify({'error': 'Descripción requerida'}), 400
    balance = _get_ec_balance()
    if ec > balance:
        return jsonify({'error': f'EC insuficientes (tienes {balance} EC)'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (-ec, 'gasto', desc, 1.0, today_str(), now)
        )
        db.commit()
    return jsonify({'ok': True, 'ec_gastado': ec, 'ec_restante': balance - ec})


@recompensas_bp.route('/api/gastos', methods=['GET'])
def historial_gastos():
    with get_db() as db:
        rows = db.execute(
            """SELECT id, ABS(amount) as ec, description, date, source
               FROM coins_ledger
               WHERE amount < 0
               ORDER BY id DESC LIMIT 60"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])


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

    # Refuerzo variable (ratio impredecible, igual que ComboBonusSheet en el
    # home): ~15% de los canjes devuelven una parte del costo como "racha de
    # suerte" — el mismo canje se siente distinto cada vez, no es un
    # descuento fijo que el usuario aprenda a esperar.
    bonus_ec = 0
    if random.random() < 0.15:
        bonus_ec = max(1, round(cost * random.uniform(0.10, 0.20)))

    with get_db() as db:
        db.execute(
            "INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (-cost, "reward", f"Recompensa: {reward['name']}", 1.0, today_str(), now)
        )
        if bonus_ec:
            db.execute(
                "INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (bonus_ec, "bonus_variable", f"Racha de suerte al canjear: {reward['name']}", 1.0, today_str(), now)
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
        "bonus_ec": bonus_ec,
        "ec_remaining": ec_balance - cost + bonus_ec,
    })
