"""
Badge System v3.0 — Eudaimonia OS

Tiers: BRONCE → PLATA → ORO → ESPECIAL
Reglas:
  - Máx 2 perks activos simultáneamente
  - Perks de plata: temporales (máx 7 días)
  - Perks de oro: desbloqueos + temporales (hasta 14 días)
  - No permanentes en perks (excepto especiales)
  - Anti-abuso: >3 perks seguidos → -10% XP por 2 días
"""
from datetime import date, datetime, timedelta
from database import get_db

# ── Badge Definitions ─────────────────────────────────────────────────────────
#
# condition(stats) -> bool   (stats comes from engine._gather_achievement_stats())
# perk_days: 0 = one-shot reward, N = perk active for N days
#
BADGE_DEFS = {
    # ── BRONCE ────────────────────────────────────────────────────────────────
    "script_junior": {
        "name":        "Script Junior",
        "description": "5 días con actividad de Programación",
        "icon":        "💻",
        "tier":        "bronze",
        "perk":        "Desbloquea compra de libros técnicos (reward disponible)",
        "perk_days":   0,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("prog_count", 0) >= 5,
    },
    "chef_de_hierro": {
        "name":        "Chef de Hierro",
        "description": "7 días con colación saludable o jugos verdes",
        "icon":        "🍏",
        "tier":        "bronze",
        "perk":        "+10 EC único — disciplina nutricional",
        "perk_days":   0,
        "ec_bonus":    10,
        "condition":   lambda s: s.get("salud_base_7d", 0) >= 7,
    },
    "silencio_redes": {
        "name":        "Silencio de Redes",
        "description": "3 días con <3.5h redes sociales",
        "icon":        "📵",
        "tier":        "bronze",
        "perk":        "Próximo día Carbón no rompe racha",
        "perk_days":   1,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("redes_7", 0) >= 3,
    },

    # ── PLATA ─────────────────────────────────────────────────────────────────
    "fullstack_arete": {
        "name":        "Full-Stack Areté",
        "description": "3 días Diamante en una semana + 1 proyecto GitHub",
        "icon":        "⚔️",
        "tier":        "silver",
        "perk":        "Desbloquea Kindle en tienda de recompensas",
        "perk_days":   0,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("diamond_week", 0) >= 3 and s.get("github_count", 0) >= 1,
    },
    "poliglota_activo": {
        "name":        "Políglota Activo",
        "description": "3 conversaciones reales en el mes",
        "icon":        "🌍",
        "tier":        "silver",
        "perk":        "+3 EC en actividades de Idiomas (7 días)",
        "perk_days":   7,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("conv_month", 0) >= 3,
    },
    "pichichi_elite": {
        "name":        "Pichichi de Élite",
        "description": "3 goles en el mes",
        "icon":        "⚽",
        "tier":        "silver",
        "perk":        "+15% XP en Pliometría (5 días)",
        "perk_days":   5,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("gol_month", 0) >= 3,
    },
    "maestro_flow": {
        "name":        "Maestro del Flow",
        "description": "3 días Diamante en la misma semana",
        "icon":        "🔥",
        "tier":        "silver",
        "perk":        "Desbloquea día vacío controlado (no rompe racha)",
        "perk_days":   7,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("diamond_week", 0) >= 3,
    },

    # ── ORO ───────────────────────────────────────────────────────────────────
    "the_architect": {
        "name":        "The Architect",
        "description": "10 proyectos subidos a GitHub",
        "icon":        "🏛️",
        "tier":        "gold",
        "perk":        "+5 EC en actividades LOGOI (14 días)",
        "perk_days":   14,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("github_count", 0) >= 10,
    },
    "stoic_commander": {
        "name":        "Stoic Commander",
        "description": "30 días de racha + nivel 7+",
        "icon":        "🛡️",
        "tier":        "gold",
        "perk":        "Desbloquea Apple Watch en tienda de recompensas",
        "perk_days":   0,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("streak", 0) >= 30 and s.get("current_level", 0) >= 7,
    },
    "diplomatico": {
        "name":        "Diplomático",
        "description": "5 conversaciones reales + nivel 8+",
        "icon":        "✈️",
        "tier":        "gold",
        "perk":        "Desbloquea Viaje en tienda de recompensas",
        "perk_days":   0,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("conv_month", 0) >= 5 and s.get("current_level", 0) >= 8,
    },

    # ── ESPECIALES ────────────────────────────────────────────────────────────
    "the_mj_move": {
        "name":        "The MJ Move",
        "description": "Racha 21 días + 3 proyectos GitHub + nivel 6+",
        "icon":        "🐐",
        "tier":        "diamond",
        "perk":        "+50 EC único — nivel de élite",
        "perk_days":   0,
        "ec_bonus":    50,
        "condition":   lambda s: (
            s.get("streak", 0) >= 21 and
            s.get("github_count", 0) >= 3 and
            s.get("current_level", 0) >= 6
        ),
    },
    "clean_code_clean_wallet": {
        "name":        "Clean Code, Clean Wallet",
        "description": "5 días Diamante en total",
        "icon":        "💸",
        "tier":        "diamond",
        "perk":        "Un día Diamante automático (bonus +5 XP)",
        "perk_days":   0,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("total_diamond_days", 0) >= 5,
    },
    "eudaimonia_sync": {
        "name":        "Eudaimonia Sync",
        "description": "Completar Sábado Reset + Domingo Strategy en el mismo fin de semana",
        "icon":        "⚡",
        "tier":        "diamond",
        "perk":        "×1.3 XP durante 7 días",
        "perk_days":   7,
        "ec_bonus":    0,
        "condition":   lambda s: s.get("weekend_complete", 0) >= 1,
    },
}

# Tier display order
TIER_ORDER = {"bronze": 0, "silver": 1, "gold": 2, "diamond": 3}
TIER_LABELS = {
    "bronze":  {"label": "Bronce",   "color": "#cd7f32", "icon": "🟤"},
    "silver":  {"label": "Plata",    "color": "#94a3b8", "icon": "⚔️"},
    "gold":    {"label": "Oro",      "color": "#fbbf24", "icon": "🏆"},
    "diamond": {"label": "Diamante", "color": "#7dd3fc", "icon": "💎"},
}


def _gather_badge_stats():
    """Extended stats needed for badge conditions."""
    from modules.gamification.engine import _gather_achievement_stats, get_daily_classification
    stats = _gather_achievement_stats()

    today      = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    with get_db() as db:
        # GitHub projects this total
        github_count = db.execute(
            "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key='github'"
        ).fetchone()["c"]

        # Salud base activities in last 7 days
        salud_base_keys = ["colacion", "jugo_verde", "comer_fruta", "dormir_8h", "skincare_noche"]
        since_7 = (date.today() - timedelta(days=7)).isoformat()
        salud_base_7d = db.execute(
            "SELECT COUNT(DISTINCT date) as c FROM activity_logs WHERE activity_key IN ({}) AND date >= ?".format(
                ",".join("?" * len(salud_base_keys))
            ),
            salud_base_keys + [since_7]
        ).fetchone()["c"]

        # Total diamond days
        all_dates_with_activity = [r["date"] for r in db.execute(
            "SELECT DISTINCT date FROM activity_logs ORDER BY date DESC LIMIT 365"
        ).fetchall()]

        # Weekend complete (sat + sun both complete in same weekend)
        # Check last 30 days for any week where both sat_complete and sun_complete bonuses exist
        weekend_complete = db.execute(
            """SELECT COUNT(*) as c FROM (
                SELECT strftime('%W', date) as week
                FROM xp_ledger
                WHERE description IN ('Combo: Sábado Completo', 'Combo: Domingo Completo')
                  AND date >= ?
                GROUP BY strftime('%W', date)
                HAVING COUNT(DISTINCT description) = 2
            )""",
            ((date.today() - timedelta(days=30)).isoformat(),)
        ).fetchone()["c"]

    # Count total diamond days from last 90 days
    total_diamond_days = 0
    for d in all_dates_with_activity[:90]:
        if get_daily_classification(d)["rank"] == "diamond":
            total_diamond_days += 1

    stats.update({
        "github_count":      github_count,
        "salud_base_7d":     salud_base_7d,
        "total_diamond_days": total_diamond_days,
        "weekend_complete":  weekend_complete,
    })
    return stats


def check_and_unlock_badges():
    now = datetime.now().isoformat()
    with get_db() as db:
        already = {r["key"] for r in db.execute(
            "SELECT key FROM badges WHERE unlocked_at IS NOT NULL"
        ).fetchall()}

    try:
        stats = _gather_badge_stats()
    except Exception:
        return []

    newly_unlocked = []

    for key, defn in BADGE_DEFS.items():
        if key in already:
            continue
        try:
            met = defn["condition"](stats)
        except Exception:
            met = False
        if not met:
            continue

        expires = None
        if defn["perk_days"] > 0:
            expires = (date.today() + timedelta(days=defn["perk_days"])).isoformat()

        with get_db() as db:
            existing = db.execute("SELECT id FROM badges WHERE key=?", (key,)).fetchone()
            if existing:
                db.execute(
                    "UPDATE badges SET unlocked_at=?, perks_active_until=?, notified=0 WHERE key=?",
                    (now, expires, key)
                )
            else:
                db.execute(
                    "INSERT INTO badges (key, tier, unlocked_at, perks_active_until, notified, created_at)"
                    " VALUES (?,?,?,?,0,?)",
                    (key, defn["tier"], now, expires, now)
                )
            db.commit()

        # Award EC bonus if any
        if defn["ec_bonus"] > 0:
            from modules.gamification.engine import _award_coins
            _award_coins(defn["ec_bonus"], "badge", f"Badge: {defn['name']}")

        newly_unlocked.append({
            "key":         key,
            "name":        defn["name"],
            "description": defn["description"],
            "icon":        defn["icon"],
            "tier":        defn["tier"],
            "perk":        defn["perk"],
            "ec_bonus":    defn["ec_bonus"],
        })

    return newly_unlocked


def get_all_badges():
    """Returns all badge definitions with unlock status and tier info."""
    with get_db() as db:
        rows = {r["key"]: dict(r) for r in db.execute(
            "SELECT key, tier, unlocked_at, perks_active_until FROM badges"
        ).fetchall()}

    today = date.today().isoformat()
    result = []
    for key, defn in BADGE_DEFS.items():
        row      = rows.get(key, {})
        unlocked = bool(row.get("unlocked_at"))
        perk_active = (
            unlocked and
            defn["perk_days"] > 0 and
            row.get("perks_active_until", "") >= today
        ) if unlocked else False

        result.append({
            "key":              key,
            "name":             defn["name"],
            "description":      defn["description"],
            "icon":             defn["icon"],
            "tier":             defn["tier"],
            "tier_label":       TIER_LABELS[defn["tier"]]["label"],
            "tier_color":       TIER_LABELS[defn["tier"]]["color"],
            "tier_icon":        TIER_LABELS[defn["tier"]]["icon"],
            "perk":             defn["perk"],
            "perk_days":        defn["perk_days"],
            "ec_bonus":         defn["ec_bonus"],
            "unlocked":         unlocked,
            "unlocked_at":      row.get("unlocked_at"),
            "perks_active_until": row.get("perks_active_until"),
            "perk_active":      perk_active,
        })

    result.sort(key=lambda x: (TIER_ORDER.get(x["tier"], 0), not x["unlocked"]))
    return result


def get_active_perks():
    """Returns badges with currently active perks."""
    today = date.today().isoformat()
    with get_db() as db:
        rows = db.execute(
            "SELECT key, tier, perks_active_until FROM badges WHERE unlocked_at IS NOT NULL AND perks_active_until >= ?",
            (today,)
        ).fetchall()
    return [dict(r) for r in rows]
