# Mapa emoji → nombre de icono lucide, para la pantalla de Logros.
#
# El campo "icon" de ACHIEVEMENT_DEFS/BADGE_DEFS/CLASSIFICATION sigue
# siendo un emoji (lo consume también la API JSON y el bundle React,
# fuera del alcance de este cambio). Este mapa solo se usa para derivar
# un "icon_lucide" adicional que /logros renderiza como SVG en vez de
# emoji, manteniendo el resto de consumidores intactos.
EMOJI_LUCIDE = {
    "👣": "footprints",
    "🎯": "target",
    "✨": "sparkles",
    "🏆": "trophy",
    "🔥": "flame",
    "⚡": "zap",
    "💎": "gem",
    "💀": "skull",
    "💻": "laptop",
    "🧠": "brain",
    "💰": "coins",
    "🎖️": "medal",
    "👑": "crown",
    "🍏": "apple",
    "📵": "phone-off",
    "⚔️": "swords",
    "🌍": "globe",
    "⚽": "circle-dot",
    "🏛️": "landmark",
    "🛡️": "shield",
    "✈️": "plane",
    "🐐": "award",
    "💸": "wallet",
    "🟤": "circle",
    "🥇": "medal",
    "🪨": "mountain",
    "🌟": "star",
    "✦": "sparkles",
    "🔒": "lock",
}


def lucide_for(emoji):
    return EMOJI_LUCIDE.get(emoji, "circle")
