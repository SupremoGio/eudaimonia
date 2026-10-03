"""
Abonos de «Sin conciliar» que el usuario comentó en el CSV (columna
COMENTARIOS). Casi todos son gente pagándole su parte de algo que él pagó:
el abono va a la categoría de ese gasto y lo resta (como ABONOS_A_GASTO).
Cada fila se identifica por id + fecha + monto; si el id no coincide (otra
base), por fecha + monto + texto de la descripción. Solo toca INGRESOS,
salvo la lista GASTOS.
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

# Tanda 4 (2026-09-30, comentarios del usuario a la lista de pendientes):
CORRECCIONES += [
    (4754, '2022-11-23', 1000.0, 'MISHELLE', 'VIVIENDA', 'Aportación renta'),     # «Mishelle sí es roomie»
    (5383, '2022-01-22', 350.0, 'BNET AURO', 'VIVIENDA', 'Artículos del hogar'),  # «me pagó la tele, fue mom»
    (3792, '2023-06-21', 180.0, 'BNET CENA', 'COMIDA_FUERA', 'Restaurante'),      # «me regresó dinero de una cena que pagué yo»
    # Validaciones del banco y un SPEI que regresó: no es dinero de nadie más.
    (4717, '2022-10-24', 1.0, 'SPEI DEVUELTO', 'FINANZAS', 'Entre cuentas propias'),
    (4655, '2022-09-11', 0.01, 'CODI VALIDA', 'FINANZAS', 'Entre cuentas propias'),
    (4645, '2022-09-01', 0.01, 'CODI VALIDA', 'FINANZAS', 'Entre cuentas propias'),
]

# Devoluciones de una persona (id, fecha, monto, texto, persona): se ligan a su
# préstamo con pendiente (el más cercano antes del abono, si no el más antiguo
# con saldo); si no tiene, quedan como «Reembolso compartido» (te regresó algo
# que pagaste por ella).
PERSONAS = [
    (3811, '2023-05-12', 4250.0, 'GRACIAS BEBO', 'Judi'),   # «Gracias bebo: me regresó dinero Judi»
]

# Abonos que además se ligan a un viaje (id, fecha, monto, texto, nombre del viaje):
# llegaron en sus fechas, así que son tu parte de algo de ese viaje (VIAJES/Otros).
VIAJES = [
    (3468, '2024-06-04', 250.0, 'TRANSF A GIOVANY', 'VILLAHERMOSA JUN 24'),
    (4084, '2023-04-25', 500.0, 'TRANSF A GIOVANY', 'VILLA MARZO 2023'),
]

# Gastos que el usuario reclasificó (fecha, monto, texto, categoria, subcategoria
# [, mi_parte]): dinero ajeno que regresó (sale de su gasto) y pagos que
# identificó. mi_parte: solo esa parte es gasto (el resto no lo es).
GASTOS = [
    # «regresé dinero de un expense que me pagaron pero no era mío» (2026-10-01)
    ('2023-01-04', 1171.0, 'EXPENSE IVAN', 'FINANZAS', 'Reembolsable'),
    ('2023-06-30', 999.0, 'EXPENSE IVAN', 'FINANZAS', 'Reembolsable'),
    # «es un depósito de un roomie que devolví» (2026-10-01)
    ('2023-08-14', 2500.0, 'DEPOSITO DPTO', 'FINANZAS', 'Reembolsable'),
    # «manda todo esto a salsa, clases» (2026-10-01): mensualidades de 2023
    ('2023-01-06', 400.0, 'PAGO SUPREMO GIO', 'SALSA', 'Clases'),
    ('2023-01-14', 420.0, 'MENS BOLETO GIO', 'SALSA', 'Clases'),
    ('2023-02-17', 400.0, 'TRANSF A DIEGO ALB', 'SALSA', 'Clases'),
    ('2023-03-26', 400.0, 'MENS GIO', 'SALSA', 'Clases'),
    ('2023-04-17', 400.0, 'MENSUALIDAD GIO', 'SALSA', 'Clases'),
    ('2023-06-06', 400.0, 'MAYO GIO', 'SALSA', 'Clases'),
    ('2023-10-30', 400.0, 'MENSUALIDAD GIOVAN', 'SALSA', 'Clases'),
    ('2023-12-29', 400.0, 'PAGO BOLETO GIO', 'SALSA', 'Clases'),
    # «aquí le pagué a Eli, mi papá» (2026-10-03): seguro de marzo y abril
    # ($555.50 c/u) + préstamos que él le hizo ($1,500 + $700, no son gasto).
    # «INVEX ABRIL» en el concepto lo mandaba a Pago TDC.
    ('2026-04-15', 3311.0, 'INVEX ABRIL PAGO CUENTA DE TERCERO BNET DEUDA', 'TRANSPORTE', 'Seguro auto', 1111.0),
]


# Salidas que quedaron guardadas como entrada («PAGO CUENTA DE TERCERO» es
# ambiguo en el PDF de BBVA): (fecha, monto, texto, categoria, subcategoria).
# Se busca por la categoría que ya tienen para no confundirlas con otro abono
# del mismo día. El usuario, 2026-10-03: «esto no es ingreso, yo lo pagué de consulta».
# (fecha, monto, texto, categoría que tiene hoy, categoría, subcategoría)
INGRESOS_QUE_ERAN_GASTO = [
    ('2026-06-22', 1000.0, 'PAGO CUENTA DE TERCERO', 'SALUD', 'SALUD', 'Consultas'),
    # «esto tampoco es ingreso, es gasto» (2026-10-03)
    ('2026-07-01', 129.0, 'FRESKO', 'SUPER', 'SUPER', 'Súper'),
    ('2026-06-27', 358.0, 'FRESKO', 'SUPER', 'SUPER', 'Súper'),
    ('2026-03-22', 57.0, 'TRANSF', 'SUPER', 'SUPER', 'Súper'),
    ('2026-03-04', 400.0, 'ARBITRAJE GIO', 'DEPORTE', 'DEPORTE', 'Fútbol'),
    # «MENS GIO va a salsa»: estaba como Gasolina
    ('2026-04-14', 700.0, 'MENS GIO', 'TRANSPORTE', 'SALSA', 'Clases'),
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
    for mid, fecha, monto, texto, persona in PERSONAS:
        row = _fila(db, mid, fecha, monto, texto)
        if not row:
            faltan += 1
            continue
        if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (row['id'],)).fetchone():
            continue
        from . import prestamos
        abiertos = [p for p in prestamos.listar(db) if p['persona'].strip().lower() == persona.lower()
                    and p['pendiente'] >= monto - 0.01 and not p['perdido_fecha']]
        antes = [p for p in abiertos if (p['fecha'] or '')[:10] <= fecha]
        p = max(antes, key=lambda p: p['fecha']) if antes else (min(abiertos, key=lambda p: p['fecha']) if abiertos else None)
        if p:
            db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='' WHERE id=?", (row['id'],))
            db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,datetime('now'))",
                       (p['id'], row['id']))
            ok += 1
        elif (row['categoria'], row['subcategoria'] or '') != ('FINANZAS', 'Reembolso compartido'):
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolso compartido' WHERE id=?", (row['id'],))
            ok += 1
    for mid, fecha, monto, texto, cat, sub in CORRECCIONES:
        row = _fila(db, mid, fecha, monto, texto)
        if not row:
            faltan += 1
            continue
        if (row['categoria'], row['subcategoria'] or '') != (cat, sub):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
            ok += 1
    for fecha, monto, texto, cat_hoy, cat, sub in INGRESOS_QUE_ERAN_GASTO:
        row = db.execute("""SELECT id FROM est_movimientos
                            WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'
                              AND categoria IN (?, ?) AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""",
                         (fecha, monto, cat_hoy, cat, f"%{texto}%")).fetchone()
        if row:
            db.execute("UPDATE est_movimientos SET tipo='GASTO', categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
            ok += 1
        elif db.execute("""SELECT 1 FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01
                              AND tipo='GASTO' AND categoria=? AND UPPER(descripcion) LIKE ?""",
                        (fecha, monto, cat_hoy, f"%{texto}%")).fetchone() and cat != cat_hoy:
            db.execute("""UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE substr(fecha,1,10)=?
                            AND ABS(ABS(monto) - ?) < 0.01 AND tipo='GASTO' AND categoria=? AND UPPER(descripcion) LIKE ?""",
                       (cat, sub, fecha, monto, cat_hoy, f"%{texto}%"))
    for fecha, monto, texto, cat, sub, *resto in GASTOS:
        parte = resto[0] if resto else None
        row = db.execute("""SELECT id, categoria, subcategoria, tipo, mi_parte FROM est_movimientos
                            WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo IN ('GASTO', 'PAGO')
                              AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""",
                         (fecha, monto, f"%{texto}%")).fetchone()
        if not row:
            faltan += 1
        elif (row['categoria'], row['subcategoria'] or '', row['tipo'], row['mi_parte']) != (cat, sub, 'GASTO', parte):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, tipo='GASTO', mi_parte=? WHERE id=?",
                       (cat, sub, parte, row['id']))
            ok += 1
    return ok, faltan
