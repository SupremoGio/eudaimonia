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
]


def aplicar(db) -> tuple[int, int]:
    """(actualizadas, no encontradas). Idempotente."""
    ok = faltan = 0
    for mid, fecha, monto, texto, cat, sub in CORRECCIONES:
        row = db.execute("""SELECT id, categoria, subcategoria FROM est_movimientos
                            WHERE id=? AND substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'""",
                         (mid, fecha, monto)).fetchone()
        if not row:
            row = db.execute("""SELECT id, categoria, subcategoria FROM est_movimientos
                                WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'
                                  AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""",
                             (fecha, monto, f"%{texto.upper()}%")).fetchone()
        if not row:
            faltan += 1
            continue
        if (row['categoria'], row['subcategoria'] or '') != (cat, sub):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
            ok += 1
    return ok, faltan
