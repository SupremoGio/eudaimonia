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
from utils import today_str, today_date

def combo(*parts):
    """Progreso de una condición compuesta: % promedio de sus partes (cada
    una tope en su meta) y la etiqueta con el detalle «racha 12/30 · nivel 4/7»."""
    # El nivel solo no cuenta como avance: sin progreso en lo demás, 0 %.
    if all(h <= 0 for h, _, lbl in parts if lbl != "nivel"):
        pct = 0
    else:
        pct = round(sum(min(h, n) / n for h, n, _ in parts) / len(parts) * 100)
    return (pct, 100, " · ".join(f"{lbl} {min(h, n)}/{n}" for h, n, lbl in parts))


def progress_of(defn, stats):
    """(have, need, label) de una definición medible con las mismas stats con
    que el motor decide el desbloqueo; None si no es medible."""
    fn = defn.get("progress")
    if not fn:
        return None
    try:
        h, n, lbl = fn(stats)
    except Exception:
        return None
    return (int(h or 0), int(n), lbl)


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
        "progress":    lambda s: (s.get("prog_count", 0), 5, "actividades de programación"),
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
        "progress":    lambda s: (s.get("salud_base_7d", 0), 7, "días con salud base · 7 d"),
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
        "progress":    lambda s: (s.get("redes_7", 0), 3, "días < 3.5 h de redes · 7 d"),
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
        "progress":    lambda s: combo((s.get("diamond_week", 0), 3, "Diamante semana"), (s.get("github_count", 0), 1, "GitHub")),
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
        "progress":    lambda s: (s.get("conv_month", 0), 3, "conversaciones este mes"),
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
        "progress":    lambda s: (s.get("gol_month", 0), 3, "goles este mes"),
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
        "progress":    lambda s: (s.get("diamond_week", 0), 3, "días Diamante esta semana"),
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
        "progress":    lambda s: (s.get("github_count", 0), 10, "proyectos en GitHub"),
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
        "progress":    lambda s: combo((s.get("streak", 0), 30, "racha"), (s.get("current_level", 0), 7, "nivel")),
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
        "progress":    lambda s: combo((s.get("conv_month", 0), 5, "conversaciones"), (s.get("current_level", 0), 8, "nivel")),
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
        "progress":    lambda s: combo((s.get("streak", 0), 21, "racha"), (s.get("github_count", 0), 3, "GitHub"), (s.get("current_level", 0), 6, "nivel")),
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
        "progress":    lambda s: (s.get("total_diamond_days", 0), 5, "días Diamante"),
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
        "progress":    lambda s: (s.get("weekend_complete", 0), 1, "fin de semana completo"),
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

    today      = today_str()
    _td        = today_date()
    month_start = _td.replace(day=1).isoformat()
    week_start  = (_td - timedelta(days=_td.weekday())).isoformat()

    with get_db() as db:
        # GitHub projects this total
        github_count = db.execute(
            "SELECT COUNT(*) as c FROM activity_logs WHERE activity_key='github'"
        ).fetchone()["c"]

        # Salud base activities in last 7 days
        salud_base_keys = ["colacion", "jugo_verde", "comer_fruta", "dormir_8h", "skincare_noche"]
        since_7 = (today_date() - timedelta(days=7)).isoformat()
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
            ((today_date() - timedelta(days=30)).isoformat(),)
        ).fetchone()["c"]

    # Días Diamante entre las últimas 90 fechas con actividad. La caché de
    # classification_history da el mismo rango que get_daily_classification.
    from modules.gamification.engine import classification_history
    fechas = all_dates_with_activity[:90]
    total_diamond_days = 0
    if fechas:
        ranks = classification_history(date.fromisoformat(min(fechas)), _td)
        total_diamond_days = sum(1 for d in fechas if ranks.get(d) == "diamond")

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
            expires = (today_date() + timedelta(days=defn["perk_days"])).isoformat()

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

    today = today_str()
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
    today = today_str()
    with get_db() as db:
        rows = db.execute(
            "SELECT key, tier, perks_active_until FROM badges WHERE unlocked_at IS NOT NULL AND perks_active_until >= ?",
            (today,)
        ).fetchall()
    return [dict(r) for r in rows]
