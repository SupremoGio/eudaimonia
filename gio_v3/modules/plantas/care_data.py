"""
Sugerencias de riego/trasplante por especie — tabla local curada, sin API
ni key. Match por substring case-insensitive contra lo que el usuario
escriba en "Nombre" o "Especie", mismo patrón que
modules/finanzas/estados/config.py:get_categoria_subcategoria() para
categorizar transacciones por palabra clave.

Los valores son un punto medio razonable dentro del rango típico que
recomiendan guías de cuidado de plantas de interior — un punto de partida
editable, no una receta exacta (la luz, la humedad y la maceta de cada
quien varían). El usuario siempre puede sobreescribirlos a mano.
"""

# keyword (minúsculas) -> (dias_riego, meses_trasplante)
PLANT_CARE: dict[str, tuple[int, int]] = {
    # Aráceas de interior muy comunes
    "pothos":       (9, 18),
    "potus":        (9, 18),
    "poto":         (9, 18),
    "epipremnum":   (9, 18),
    "monstera":     (8, 18),
    "costilla de adan": (7, 15),
    "adansonii":    (7, 15),
    "philodendron": (8, 15),
    "filodendro":   (8, 15),
    "anturio":      (6, 12),
    "anthurium":    (6, 12),
    "singonio":     (7, 15),
    "syngonium":    (7, 15),

    # Palmas y follaje grande
    "areca":        (7, 18),
    "palma bambu":  (7, 18),
    "ficus lyrata":     (7, 15),
    "lira":             (7, 15),
    "ficus elastica":   (9, 15),
    "hule":             (9, 15),
    "ficus":        (8, 15),
    "ave del paraiso":  (7, 18),
    "strelitzia":       (7, 18),

    # Suculentas y cactáceas
    "suculenta":    (12, 18),
    "cactus":       (18, 24),
    "cactacea":     (18, 24),
    "sabila":       (18, 15),
    "aloe":         (18, 15),
    "jade":         (18, 24),
    "crassula":     (18, 24),
    "echeveria":    (12, 18),
    "kalanchoe":    (12, 18),
    "sedum":        (12, 18),

    # Resistentes / bajo mantenimiento
    "sansevieria":  (18, 24),
    "lengua de suegra": (18, 24),
    "espada de san jorge": (18, 24),
    "zamioculcas":  (18, 24),
    "zz":           (18, 24),
    "dracaena":     (12, 18),
    "drago":        (12, 18),
    "yuca":         (14, 24),
    "yucca":        (14, 24),

    # Necesitan más humedad / riego frecuente
    "calathea":     (6, 12),
    "maranta":      (6, 12),
    "helecho":      (5, 12),
    "fern":         (5, 12),
    "nephrolepis":  (5, 12),
    "cinta":        (7, 12),
    "malamadre":    (7, 12),
    "clorofito":    (7, 12),
    "chlorophytum": (7, 12),
    "hiedra":       (6, 12),
    "ivy":          (6, 12),
    "hedera":       (6, 12),
    "croto":        (6, 12),
    "croton":       (6, 12),
    "bambu de la suerte": (7, 24),
    "lucky bamboo": (7, 24),

    # Flor
    "orquidea":     (7, 12),
    "orchid":       (7, 12),
    "phalaenopsis": (7, 12),
    "violeta africana": (6, 12),
    "african violet":   (6, 12),
    "cyclamen":     (6, 12),
    "ciclamen":     (6, 12),
    "begonia":      (6, 12),
    "espatifilo":   (6, 12),
    "spathiphyllum":(6, 12),
    "cuna de moises": (6, 12),
    "nochebuena":   (6, 12),
    "poinsettia":   (6, 12),

    # Jardín / exterior común
    "lavanda":      (8, 15),
    "lavender":     (8, 15),
    "rosal":        (4, 12),
    "rose":         (4, 12),
    "romero":       (10, 15),
    "albahaca":     (3, 6),
    "basil":        (3, 6),
    "menta":        (4, 6),
    "bonsai":       (3, 24),
}


def suggest_care(query: str):
    """Primer match por substring — case-insensitive, sin acentos exactos
    requeridos por parte del usuario (las claves ya están sin acento)."""
    if not query:
        return None
    q = query.strip().lower()
    if not q:
        return None
    for keyword, (dias_riego, meses_trasplante) in PLANT_CARE.items():
        if keyword in q:
            return {
                'match': keyword,
                'dias_riego': dias_riego,
                'meses_trasplante': meses_trasplante,
            }
    return None


# ── Ajuste estacional de riego para Guadalajara, Jalisco ─────────────────────
# Clima subtropical de altura (Köppen Cwa/Cwb): seco todo el año salvo
# junio-septiembre (temporada de lluvias, muy húmeda), con el pico de calor
# y evaporación justo ANTES de las lluvias (marzo-mayo) — no en pleno
# verano, al revés de climas templados. No es un API de clima en vivo: es
# un patrón anual estable de la ciudad, así que no hay nada que pueda
# fallar en producción como pasó con la búsqueda de iTunes.
#
# factor > 1  → intervalo efectivo MÁS LARGO (riega menos seguido)
# factor < 1  → intervalo efectivo MÁS CORTO (riega más seguido)
# El factor se aplica sobre dias_riego para calcular el "vencido/próximo/
# urgente", nunca sobreescribe el valor base que configuró el usuario.
SEASONAL_FACTOR_GDL: dict[int, tuple[float, str]] = {
    1:  (1.15, "Seca y fresca"),
    2:  (1.15, "Seca y fresca"),
    3:  (0.90, "Empieza el calor, aún seca"),
    4:  (0.80, "Calor fuerte y seco — pico de evaporación"),
    5:  (0.85, "Calor fuerte, previo a lluvias"),
    6:  (1.20, "Inicio de temporada de lluvias"),
    7:  (1.30, "Lluvias plenas — mucha humedad"),
    8:  (1.30, "Lluvias plenas — mucha humedad"),
    9:  (1.25, "Lluvias, aún húmedo"),
    10: (1.10, "Fin de lluvias, transición"),
    11: (1.15, "Seca y fresca"),
    12: (1.20, "Seca y fría"),
}


def seasonal_factor(month: int):
    factor, label = SEASONAL_FACTOR_GDL.get(month, (1.0, ""))
    return {'factor': factor, 'label': label}
