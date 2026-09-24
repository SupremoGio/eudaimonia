"""
Límites mensuales del plan de presupuesto acordado con el usuario (2026-09).
Única fuente para la migración que limpia est_budgets y para los endpoints de
administración que recargan presupuestos (antes recargaban el Excel viejo con
categorías que ya no existen: CASA/HOGAR, MENSUALIDAD, etc.).

El ahorro no va aquí: es la meta mínima del grupo Ahorro y deudas
(app_settings presupuesto_meta_ahorro). Viajes = 0 en el plan → sin límite.
"""
PLAN_LIMITES = [
    ('VIVIENDA',         'Vivienda',          6950.0),
    ('SUPER',            'Súper',             2000.0),
    ('SALUD',            'Salud',              300.0),
    ('TRANSPORTE',       'Transporte',        2105.0),
    ('CUIDADO_PERSONAL', 'Cuidado personal',   500.0),
    ('COMIDA_FUERA',     'Comida fuera',      2200.0),
    ('CAFE/PAN',         'Café & Pan',         300.0),
    ('DIGITAL',          'Digital',           1246.0),
    ('FAMILIA_REGALOS',  'Familia y regalos',  500.0),
    ('SALSA',            'Salsa / Baile',      300.0),
    ('DEPORTE',          'Deporte',            200.0),
    ('ROPA',             'Ropa',               400.0),
    ('OCIO',             'Ocio',               200.0),
    ('PROYECTOS',        'Proyectos',          200.0),
]
