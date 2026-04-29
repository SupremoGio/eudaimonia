# Achievement definitions — pure data, no imports from this project.
#
# Filosofía de diseño (token economy + game design):
#   - XP de logros ≤ 4 días de actividad normal (~100 XP máximo)
#   - Total XP de todos los logros combinados ≈ 3 semanas de actividad
#   - Los logros son reconocimiento, no atajo a niveles
#   - semana_elite usa xp_week_acts (excluye XP de logros) para evitar cadenas
#
# stats keys:
#   streak, total_xp, total_coins, xp_week, xp_week_acts,
#   total_activity_count, cats_done_today (set), all_cats_ever (set),
#   prog_count, had_perfect_day, current_level

ACHIEVEMENT_DEFS = {
    # ── Tier 1: Inicio (semana 1) ─────────────────────────────────────────────
    "primer_paso": {
        "name":        "Primer Paso",
        "description": "Completa tu primera actividad",
        "icon":        "👣",
        "coins":       10,
        "xp":          5,
        "hidden":      False,
        "condition":   lambda s: s["total_activity_count"] >= 1,
    },

    # ── Tier 2: Patrones de comportamiento (semanas 1-4) ──────────────────────
    "disciplina_total": {
        "name":        "Disciplina Total",
        "description": "Completa actividades de 5 o más categorías en un solo día",
        "icon":        "🎯",
        "coins":       30,
        "xp":          15,
        "hidden":      True,
        "condition":   lambda s: len(s["cats_done_today"]) >= 5,
    },
    "perfeccionista": {
        "name":        "Perfeccionista",
        "description": "Completa un Día Perfecto (3 prioridades + 5+ pts de actividades)",
        "icon":        "✨",
        "coins":       30,
        "xp":          15,
        "hidden":      True,
        "condition":   lambda s: s["had_perfect_day"],
    },
    "semana_elite": {
        "name":        "Semana Elite",
        "description": "Superar 200 XP en actividades en una semana (sin contar logros)",
        "icon":        "🏆",
        "coins":       40,
        "xp":          20,
        "hidden":      True,
        # xp_week_acts excluye achievement XP — evita dispararse por cadena de logros
        "condition":   lambda s: s.get("xp_week_acts", s["xp_week"]) >= 200,
    },

    # ── Tier 3: Rachas (consistencia sostenida) ───────────────────────────────
    "racha_7": {
        "name":        "Semana de Fuego",
        "description": "7 días consecutivos de actividad",
        "icon":        "🔥",
        "coins":       50,
        "xp":          25,
        "hidden":      True,
        "condition":   lambda s: s["streak"] >= 7,
    },
    "racha_10": {
        "name":        "Imparable",
        "description": "10 días consecutivos de actividad",
        "icon":        "⚡",
        "coins":       80,
        "xp":          40,
        "hidden":      True,
        "condition":   lambda s: s["streak"] >= 10,
    },
    "racha_21": {
        "name":        "Hábito Forjado",
        "description": "21 días consecutivos — el hábito ya es tuyo",
        "icon":        "💎",
        "coins":       150,
        "xp":          70,
        "hidden":      True,
        "condition":   lambda s: s["streak"] >= 21,
    },
    "racha_30": {
        "name":        "Modo Bestia",
        "description": "30 días consecutivos — nivel de élite absoluto",
        "icon":        "💀",
        "coins":       250,
        "xp":          100,
        "hidden":      True,
        "condition":   lambda s: s["streak"] >= 30,
    },

    # ── Tier 4: Volumen / profundidad (meses de práctica) ─────────────────────
    "programador_nato": {
        "name":        "Programador Nato",
        "description": "Completa 50 actividades de Programación",
        "icon":        "💻",
        "coins":       100,
        "xp":          60,
        "hidden":      True,
        "condition":   lambda s: s["prog_count"] >= 50,
    },
    "polimata": {
        "name":        "Polímata",
        "description": "Completa actividades en las 10 categorías principales",
        "icon":        "🧠",
        "coins":       150,
        "xp":          80,
        "hidden":      True,
        # Fix: había 15 pero solo existen 10 categorías — nunca podía dispararse
        "condition":   lambda s: len(s["all_cats_ever"]) >= 10,
    },
    "millonario": {
        "name":        "El Gran Inicio",
        "description": "Acumula 1000 coins en total",
        "icon":        "💰",
        "coins":       30,
        "xp":          15,
        "hidden":      True,
        "condition":   lambda s: s["total_coins"] >= 1000,
    },

    # ── Tier 4b: Fin de semana perfecto ──────────────────────────────────────
    "fin_semana_perfecto": {
        "name":        "Fin de semana perfecto",
        "description": "Completar sábado y domingo completo en la misma semana",
        "icon":        "🏆",
        "coins":       30,
        "xp":          15,
        "hidden":      True,
        "condition":   lambda s: s.get("weekend_perfect_week", False),
    },

    # ── Tier 5: Hitos de nivel (solo coins, sin XP) ───────────────────────────
    "nivel_5": {
        "name":        "Disciplinado",
        "description": "Alcanza el nivel 5 — Autarkés",
        "icon":        "🎖️",
        "coins":       150,
        "xp":          0,
        "hidden":      True,
        "condition":   lambda s: s["current_level"] >= 5,
    },
    "nivel_10": {
        "name":        "Supremo",
        "description": "Alcanza el nivel 10 — Eudaimón",
        "icon":        "👑",
        "coins":       500,
        "xp":          0,
        "hidden":      True,
        "condition":   lambda s: s["current_level"] >= 10,
    },
}
