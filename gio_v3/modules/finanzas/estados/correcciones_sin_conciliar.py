"""
Abonos de «Sin conciliar» que el usuario comentó en el CSV (columna
COMENTARIOS). Casi todos son gente pagándole su parte de algo que él pagó:
el abono va a la categoría de ese gasto y lo resta (como ABONOS_A_GASTO).
Cada fila se identifica por id + fecha + monto; si el id no coincide (otra
base), por fecha + monto + texto de la descripción. Solo toca INGRESOS.
Se aplica en «Aplicar reglas», al cargar estados y al arrancar (la versión de
la migración lleva el tamaño de la lista: cada tanda nueva se aplica sola).
"""

# (id, fecha, monto, texto, categoria, subcategoria)  # comentario
CORRECCIONES = [
    # Tanda 1 (2026-09-29)
    (3786, '2023-06-17', 75.0, 'JUDITH MICHE', 'COMIDA_FUERA', 'Restaurante'),       # me regresaron de una cerveza
    (4760, '2022-12-01', 5300.0, 'MISHELLE CT', 'VIVIENDA', 'Aportación renta'),     # pago de renta de roomie
    (4726, '2022-10-28', 150.0, 'BNET TAXI', 'TRANSPORTE', 'Taxi/apps'),             # me pagaron un taxi
    (4659, '2022-09-15', 74.0, 'CROASANT', 'CAFE/PAN', 'Pan'),                       # me pagaron un pan
    # «compré una tele y mom me pagaba esa mensualidad»: resta a lo de la casa.
    (5430, '2022-03-04', 450.0, 'BNET TELE', 'VIVIENDA', 'Artículos del hogar'),
    (5363, '2022-01-07', 300.0, 'BNET TELE', 'VIVIENDA', 'Artículos del hogar'),
    (5423, '2022-02-28', 1500.0, 'BNET SERGIO', 'VIVIENDA', 'Aportación renta'),   # Sergio pagaba su parte de la renta
    # Tanda 2 (2026-09-30): «estos son dinero efectivo que metí a mi cuenta»:
    # su propio dinero, ni ingreso ni gasto.
    (2063, '2026-05-08', 2500.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (1728, '2026-02-11', 7000.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (1437, '2025-11-19', 6000.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (2742, '2025-10-08', 4300.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (2834, '2025-07-14', 4700.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (2878, '2025-06-15', 5600.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (4091, '2023-11-07', 4000.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    (5277, '2022-04-29', 1380.0, 'DEPOSITO EFECTIVO', 'FINANZAS', 'Entre cuentas propias'),
    # Tanda 3 (2026-09-30, «todo lo que dices tiene lógica, aplícalos»):
    (3817, '2023-05-17', 5150.0, 'TRANSF A GIOVANY', 'VIVIENDA', 'Aportación renta'),   # mismo monto que la renta de los roomies (mar–jul 2023)
    (3441, '2024-05-11', 3000.0, 'BNET VAC', 'VIAJES', 'Otros'),                       # «VAC»: vacaciones / vaca
]

# Abonos que además se ligan a un viaje (id, fecha, monto, texto, nombre del viaje):
# llegaron en sus fechas, así que son tu parte de algo de ese viaje (VIAJES/Otros).
VIAJES = [
    (3468, '2024-06-04', 250.0, 'TRANSF A GIOVANY', 'VILLAHERMOSA JUN 24'),
    (4084, '2023-04-25', 500.0, 'TRANSF A GIOVANY', 'VILLA MARZO 2023'),
]


def _fila(db, mid, fecha, monto, texto):
    row = db.execute("""SELECT id, categoria, subcategoria, viaje_id FROM est_movimientos
                        WHERE id=? AND substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'""",
                     (mid, fecha, monto)).fetchone()
    return row or db.execute("""SELECT id, categoria, subcategoria, viaje_id FROM est_movimientos
                                WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'
                                  AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""",
                             (fecha, monto, f"%{texto.upper()}%")).fetchone()


def aplicar(db) -> tuple[int, int]:
    """(actualizadas, no encontradas). Idempotente."""
    ok = faltan = 0
    for mid, fecha, monto, texto, nombre in VIAJES:
        row = _fila(db, mid, fecha, monto, texto)
        v = db.execute("SELECT id FROM viajes WHERE UPPER(TRIM(nombre))=? ORDER BY id LIMIT 1", (nombre,)).fetchone()
        if not row or not v:
            faltan += 1
            continue
        if (row['categoria'], row['subcategoria'] or '', row['viaje_id']) != ('VIAJES', 'Otros', v['id']):
            db.execute("UPDATE est_movimientos SET categoria='VIAJES', subcategoria='Otros', viaje_id=? WHERE id=?",
                       (v['id'], row['id']))
            ok += 1
    for mid, fecha, monto, texto, cat, sub in CORRECCIONES:
        row = _fila(db, mid, fecha, monto, texto)
        if not row:
            faltan += 1
            continue
        if (row['categoria'], row['subcategoria'] or '') != (cat, sub):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
            ok += 1
    return ok, faltan
