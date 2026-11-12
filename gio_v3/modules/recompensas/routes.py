import math
import random
from flask import Blueprint, render_template, request, jsonify, session
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


# Ventana de días por recompensa (columna weekend_only): 0 = cualquier día,
# 1 = fin de semana (sáb–dom), 2 = viernes a domingo (ej. Carl's Jr).
_VENTANAS = {1: (5, 6), 2: (4, 5, 6)}
_VENTANA_LABEL = {1: "Fin de semana", 2: "Vie–Dom"}
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def ventana_modo(value):
    """Normaliza weekend_only (bool del formulario viejo o 0/1/2) al modo 0/1/2."""
    if value is True:
        return 1
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return v if v in _VENTANAS else 0


def _proximo_dia_permitido(d, modo):
    dias = _VENTANAS.get(modo)
    if not dias:
        return d
    while d.weekday() not in dias:
        d += timedelta(days=1)
    return d


def _fecha_corta(d):
    return f"{_DIAS[d.weekday()]} {d.day} {_MESES[d.month - 1]}"


def _inicio_ventana(d, modo):
    """Primer día de la ventana (vie o sáb) que contiene a `d`."""
    primero = _VENTANAS[modo][0]
    return d - timedelta(days=(d.weekday() - primero) % 7)


def canjes_en_ventana(reward, d=None):
    """Canjes de la recompensa en la ventana (fin de semana) que contiene a `d`,
    contados en coins_ledger -- una sola fecha (last_redeemed) no alcanza para
    un tope de 2 o más."""
    modo = ventana_modo(reward.get("weekend_only"))
    if not modo:
        return 0
    d = d or today_date()
    if d.weekday() not in _VENTANAS[modo]:
        return 0
    with get_db() as db:
        return db.execute(
            "SELECT COUNT(*) c FROM coins_ledger WHERE source='reward' AND description=? AND amount<0 AND date BETWEEN ? AND ?",
            (f"Recompensa: {reward['name']}", _inicio_ventana(d, modo).isoformat(), d.isoformat())
        ).fetchone()["c"]


def _can_redeem(reward, ec_balance, current_level):
    if reward.get("unica") and reward.get("last_redeemed"):
        return False, "Ya la conseguiste"
    if ec_balance < reward["ec_cost"]:
        return False, "EC insuficientes"
    if current_level < reward["level_required"]:
        return False, f"Nivel {reward['level_required']} requerido"
    modo = ventana_modo(reward.get("weekend_only"))
    today = today_date()
    # Tope por ventana (ej. 2 cápsulas por fin de semana): reemplaza al
    # cooldown; al llenarse se abre de nuevo la siguiente ventana.
    tope = int(reward.get("max_por_ventana") or 0)
    if tope and modo and today.weekday() in _VENTANAS[modo] and canjes_en_ventana(reward, today) >= tope:
        siguiente = _inicio_ventana(today, modo) + timedelta(days=7)
        return False, f"Ya van {tope} este fin de semana · disponible el {_fecha_corta(siguiente)}"
    # Cooldown primero: al vencer, la recompensa se abre el siguiente día de su
    # ventana (Carl's Jr: 30 días y luego el próximo vie/sáb/dom).
    if reward["cooldown_days"] > 0 and reward["last_redeemed"] and not (tope and modo):
        cooldown_end = (
            datetime.fromisoformat(reward["last_redeemed"]) +
            timedelta(days=reward["cooldown_days"])
        ).date()
        if today < cooldown_end:
            if modo:
                return False, f"Disponible el {_fecha_corta(_proximo_dia_permitido(cooldown_end, modo))}"
            days_left = (cooldown_end - today).days
            return False, f"Cooldown: {days_left} días restantes"
    if modo and today.weekday() not in _VENTANAS[modo]:
        return False, ("Solo de viernes a domingo" if modo == 2 else "Solo disponible en fin de semana")
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
    (("salida", "cine", "experiencia", "concierto"), "ticket"), (("cena", "comida", "restaurante", "helado", "carl", "burger", "hamburguesa"), "utensils"),
    (("juego", "game", "steam"), "gamepad-2"), (("café", "cafe"), "coffee"), (("masaje", "spa"), "flower-2"),
]


def _reward_icon(name):
    n = (name or "").lower()
    for words, icon in _REWARD_ICONS:
        if any(w in n for w in words):
            return icon
    return "gift"


def _badge_ok(key):
    if not key:
        return True
    with get_db() as db:
        return db.execute("SELECT 1 FROM badges WHERE key=? AND unlocked_at IS NOT NULL", (key,)).fetchone() is not None


def _reward_status(r, ec_balance, current_level):
    """available · level (falta nivel) · badge (falta insignia) · ec (solo
    faltan EC) · wait (cooldown, ventana o tope del fin de semana) · done
    (única ya canjeada)."""
    if r.get("unica") and r.get("last_redeemed"):
        return "done"
    if r["can_redeem"]:
        return "available"
    if current_level < r["level_required"]:
        return "level"
    if not _badge_ok(r.get("badge_required")):
        return "badge"
    if ec_balance < r["ec_cost"]:
        can_otherwise, _ = _can_redeem(r, 10 ** 9, current_level)
        return "ec" if can_otherwise else "wait"
    return "wait"


# ── Recompensas v2: ritmo, ETA, requisitos con progreso y grupos ─────────────

def ec_ritmo(hoy=None):
    """EC ganados (solo positivos) en los últimos 30 días / 30, y los de la
    semana. Con el neto, cada canje alargaría las ETA."""
    hoy = hoy or today_date()
    with get_db() as db:
        ec_30 = db.execute("SELECT COALESCE(SUM(amount),0) s FROM coins_ledger WHERE amount>0 AND date>=? AND date<=?",
                           ((hoy - timedelta(days=29)).isoformat(), hoy.isoformat())).fetchone()["s"]
        ec_week = db.execute("SELECT COALESCE(SUM(amount),0) s FROM coins_ledger WHERE amount>0 AND date>=? AND date<=?",
                             ((hoy - timedelta(days=hoy.weekday())).isoformat(), hoy.isoformat())).fetchone()["s"]
    return round(ec_30 / 30, 1), int(ec_week)


def eta_dias(faltan, ritmo):
    if faltan <= 0:
        return 0
    if not ritmo or ritmo <= 0:
        return None
    return math.ceil(faltan / ritmo)


def eta_txt(dias):
    if dias is None:
        return None
    if dias <= 1:
        return "1 día"
    if dias < 30:
        return f"{dias} días"
    return f"{dias / 30:.1f} meses"


def _espera_corta(reason):
    """block_reason abreviado para el badge de requisito."""
    import re
    m = re.match(r"Ya van (\d+) este fin de semana · disponible el (\S+ \d+)", reason)
    if m:
        return f"{m.group(1)}/{m.group(1)} · {m.group(2)}"
    m = re.match(r"Disponible el (\S+ \d+)", reason)
    if m:
        return f"Disponible el {m.group(1)}"
    m = re.match(r"Cooldown: (\d+) días restantes", reason)
    if m:
        n = int(m.group(1))
        return "Mañana" if n == 1 else f"En {n} días"
    return {"Solo disponible en fin de semana": "Solo sáb–dom",
            "Solo de viernes a domingo": "Solo vie–dom"}.get(reason, reason)


class _Requisitos:
    """Calcula los requisitos con progreso, con las stats de insignias de
    Logros (una sola vez por página) y el ritmo de XP."""

    def __init__(self, level_info):
        from modules.gamification.routes import eta_nivel
        self.level_info = level_info
        self.xp_dia = eta_nivel(level_info["total_xp"])["xp_dia_30"]
        self._stats = None

    def stats(self):
        if self._stats is None:
            from modules.gamification.badges import _gather_badge_stats
            try:
                self._stats = _gather_badge_stats()
            except Exception:
                self._stats = {}
        return self._stats

    def nivel(self, n):
        from modules.gamification.engine import LEVEL_THRESHOLDS
        umbral = LEVEL_THRESHOLDS[min(max(n, 1), 10) - 1][0]
        faltan = max(0, umbral - self.level_info["total_xp"])
        dias = eta_dias(faltan, self.xp_dia)
        txt = eta_txt(dias)
        return {"tipo": "nivel", "texto": f"Nivel {n}" + (f" · ≈ {txt.replace(' días', ' d').replace(' día', ' d')}" if txt else ""),
                "have": self.level_info["total_xp"], "need": umbral, "eta_txt": txt, "eta_dias": dias,
                "cerca": dias is not None and dias <= 30}

    def insignia(self, key):
        from modules.gamification.badges import BADGE_DEFS, progress_of
        from modules.gamification.routes import prog_txt
        defn = BADGE_DEFS.get(key) or next((d for d in BADGE_DEFS.values() if d["name"].lower() == (key or "").lower()), None)
        if not defn:
            return {"tipo": "insignia", "texto": f"Insignia {key}", "have": None, "need": None, "eta_txt": None, "cerca": False}
        p = progress_of(defn, self.stats()) if self.stats() else None
        have, need = (p[0], p[1]) if p else (None, None)
        return {"tipo": "insignia", "texto": defn["name"] + (f" · {prog_txt(p)}" if p else ""), "have": have, "need": need,
                "eta_txt": None, "cerca": bool(p) and need and have / need >= 0.75}


def _requisito(r, reqs, current_level):
    if r["status"] == "level":
        return reqs.nivel(r["level_required"])
    if r["status"] == "badge":
        return reqs.insignia(r["badge_required"])
    if r["status"] == "wait":
        return {"tipo": "espera", "texto": _espera_corta(r["block_reason"]), "have": None, "need": None,
                "eta_txt": None, "cerca": False}
    return None


def _regla(r):
    """Una línea con la regla de la recompensa: «Cada 7 d», «2 por fin de semana»…"""
    if r.get("unica"):
        base = "Única vez"
    elif r.get("max_por_ventana"):
        base = f"{r['max_por_ventana']} por fin de semana"
    elif r.get("cooldown_days"):
        base = f"Cada {r['cooldown_days']} d"
    else:
        base = "Sin espera"
    v = {1: "sáb y dom", 2: "vie a dom"}.get(ventana_modo(r.get("weekend_only")))
    return base + (f" · {v}" if v and not r.get("max_por_ventana") else "")


def tienda():
    """Todo lo que pinta /recompensas/: recompensas con estado, regla, ETA y
    requisito; meta; grupos; ritmo e historial."""
    ec_balance = _get_ec_balance()
    level_info = _get_level()
    rewards = _get_all_rewards()
    lvl = level_info["level"]
    ritmo, ec_week = ec_ritmo()
    reqs = _Requisitos(level_info)
    for r in rewards:
        can, reason = _can_redeem(r, ec_balance, lvl)
        r["can_redeem"] = can
        r["block_reason"] = reason if not can else ""
        r["status"] = _reward_status(r, ec_balance, lvl)
        r["icon"] = _reward_icon(r["name"])
        r["ventana"] = _VENTANA_LABEL.get(ventana_modo(r.get("weekend_only")), "")
        r["max_por_ventana"] = int(r.get("max_por_ventana") or 0)
        r["usados_ventana"] = canjes_en_ventana(r) if r["max_por_ventana"] else 0
        r["ec_pct"] = min(100, round(ec_balance / r["ec_cost"] * 100)) if r["ec_cost"] else 100
        r["ec_left"] = max(0, r["ec_cost"] - ec_balance)
        r["eta_dias"] = eta_dias(r["ec_left"], ritmo)
        r["eta_txt"] = eta_txt(r["eta_dias"])
        r["regla"] = _regla(r)
        r["req"] = _requisito(r, reqs, lvl)

    available = [r for r in rewards if r["status"] == "available"]
    ec = sorted((r for r in rewards if r["status"] == "ec"), key=lambda r: (r["ec_left"], r["ec_cost"]))
    later = ([r for r in rewards if r["status"] == "wait"] +
             sorted((r for r in rewards if r["status"] in ("level", "badge")), key=lambda r: r["ec_cost"]))
    done = [r for r in rewards if r["status"] == "done"]

    with get_db() as db:
        history = [dict(r) for r in db.execute(
            "SELECT id, ABS(amount) AS ec, description, date, source FROM coins_ledger "
            "WHERE amount < 0 ORDER BY id DESC LIMIT 60").fetchall()]
    return {
        "rewards": rewards, "ec_balance": ec_balance, "level_info": level_info, "ec_rate": EC_RATE,
        "ec_week": ec_week, "ec_daily": ritmo, "history": history,
        "meta": ec[0] if ec else None,
        "grupos": {"available": available, "ec": ec, "later": later, "done": done},
    }


def wishlists_ec(ec_balance, ritmo, fin_ok, limite=5):
    """Lo pagable con EC de las dos wishlists, normalizado a {nombre, fuente,
    ec, url}. Finanzas solo con fin_ok (la misma regla que wishlist_dedup).
    La compra no se duplica: cada fila lleva a su propio flujo (comprar-ec)."""
    items = []
    with get_db() as db:
        for r in db.execute(
                "SELECT id, nombre, precio_estimado, ec_sugerido FROM wishlist_items "
                "WHERE COALESCE(estado,'evaluando') NOT IN ('comprado','descartado')").fetchall():
            ec = r["ec_sugerido"] or (math.ceil((r["precio_estimado"] or 0) / EC_RATE) if r["precio_estimado"] else 0)
            if ec > 0:
                items.append({"nombre": r["nombre"], "fuente": "Guardarropa", "ec": int(ec),
                              "url": "/guardarropa/wishlist/", "icon": "shirt"})
        if fin_ok:
            for r in db.execute(
                    "SELECT id, nombre, precio_estimado FROM lista_prioridades "
                    "WHERE estado='Pendiente' AND COALESCE(precio_estimado,0) > 0").fetchall():
                items.append({"nombre": r["nombre"], "fuente": "Finanzas", "ec": math.ceil(r["precio_estimado"] / EC_RATE),
                              "url": "/finanzas/prioridades/", "icon": "shopping-bag"})
    items.sort(key=lambda i: (i["ec"], i["nombre"]))
    for i in items:
        i["alcanzable"] = ec_balance >= i["ec"]
        i["faltan"] = max(0, i["ec"] - ec_balance)
        i["eta_txt"] = eta_txt(eta_dias(i["faltan"], ritmo))
    return items[:limite]


@recompensas_bp.route('/')
def index():
    ctx = tienda()
    ctx["wishlists"] = wishlists_ec(ctx["ec_balance"], ctx["ec_daily"], session.get("fin_ok"))
    return render_template('recompensas/index.html', **ctx)


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
            """INSERT INTO rewards (name, description, ec_cost, level_required, badge_required, cooldown_days, weekend_only, created_at, unica, max_por_ventana)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                name,
                data.get("description", ""),
                int(data.get("ec_cost", 0)),
                int(data.get("level_required", 1)),
                data.get("badge_required", ""),
                int(data.get("cooldown_days", 0)),
                ventana_modo(data.get("weekend_only", 0)),
                now,
                int(bool(data.get("unica", es_unica_por_nombre(name)))),
                max(0, int(data.get("max_por_ventana", 0) or 0)),
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
               badge_required=?, cooldown_days=?, weekend_only=?, unica=?, max_por_ventana=? WHERE id=?""",
            (
                data.get("name", row["name"]),
                data.get("description", row["description"]),
                int(data.get("ec_cost", row["ec_cost"])),
                int(data.get("level_required", row["level_required"])),
                data.get("badge_required", row["badge_required"]),
                int(data.get("cooldown_days", row["cooldown_days"])),
                ventana_modo(data.get("weekend_only", row["weekend_only"])),
                int(bool(data.get("unica", row["unica"]))),
                max(0, int(data.get("max_por_ventana", row["max_por_ventana"] or 0) or 0)),
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
        "saldo_antes": ec_balance,
        "saldo_despues": ec_balance - cost + bonus_ec,
    })


UNDO_MIN = 10


@recompensas_bp.route('/api/redeem/<int:reward_id>/undo', methods=['POST'])
def undo_redeem(reward_id):
    """Deshace el último canje si fue hace 10 minutos o menos: borra el cargo
    (y su racha de suerte), y restaura last_redeemed. usados_ventana se cuenta
    desde coins_ledger, así que el tope del fin de semana queda bien solo."""
    with get_db() as db:
        reward = db.execute("SELECT * FROM rewards WHERE id=?", (reward_id,)).fetchone()
        if not reward:
            return jsonify({"error": "not found"}), 404
        desc = f"Recompensa: {reward['name']}"
        cargo = db.execute(
            "SELECT id, amount, created_at FROM coins_ledger WHERE source='reward' AND description=? AND amount<0 "
            "ORDER BY id DESC LIMIT 1", (desc,)).fetchone()
        try:
            hace = datetime.now() - datetime.fromisoformat(cargo["created_at"]) if cargo else None
        except (TypeError, ValueError):
            hace = None
        if hace is None or hace > timedelta(minutes=UNDO_MIN) or hace < timedelta(0):
            return jsonify({"error": "Ya no se puede deshacer"}), 409
        db.execute("DELETE FROM coins_ledger WHERE id=?", (cargo["id"],))
        db.execute("DELETE FROM coins_ledger WHERE source='bonus_variable' AND description=? AND created_at=?",
                   (f"Racha de suerte al canjear: {reward['name']}", cargo["created_at"]))
        prev = db.execute(
            "SELECT created_at FROM coins_ledger WHERE source='reward' AND description=? AND amount<0 "
            "ORDER BY id DESC LIMIT 1", (desc,)).fetchone()
        db.execute("UPDATE rewards SET last_redeemed=?, status=? WHERE id=?",
                   (prev["created_at"] if prev else None, "redeemed" if prev else "available", reward_id))
        db.commit()
    return jsonify({"ok": True, "ec_balance": _get_ec_balance()})
