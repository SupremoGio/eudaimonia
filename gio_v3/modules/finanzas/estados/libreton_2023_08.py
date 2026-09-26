"""
Libretón BBVA Débito 07/08/2023 al 06/09/2023 (cuenta 1520361804), cargado a
mano (2026-09-26): la auditoría de huecos marcaba 2023-08-03 -> 2023-09-08 sin
movimientos en BBVA Débito y el PDF que mandó el usuario es una impresión
(solo imagen, sin texto), así que el parser no puede leerlo. Las 25 filas se
transcribieron del PDF y salen del parser del Libretón (bbva_libreton._parse_text
sobre el texto transcrito): mismas descripciones, tipo verificado contra el
saldo impreso y cuadran con el resumen del banco (17 cargos $36,045.62, 8
abonos $32,968.23; saldo 8,780.97 -> 5,703.58).

Encima del parser, lo que el import haría después o que el usuario ya había
decidido para movimientos iguales:
  - NAFIN cetesdirecto DOMICILIACION -> CETES/APORTACION (post-proceso de
    inversiones del import) y SPEI RECIBIDONAFIN -> CETES/RETIRO (CSV corregido:
    «saqué dinero de CETES»).
  - SPEI RECIBIDOHSBC «5401406Renta» -> VIVIENDA/Aportación renta.
  - «Expense botanas» -> EXPENSE.
Luego se corren las reglas de siempre (_reaplicar_reglas).

Idempotente: una fila se salta si ya hay en BBVA_DEB un movimiento del mismo
día, monto y tipo.
"""
PERIODO = '07/08/2023 al 06/09/2023'

# (fecha, fecha_cargo, descripcion, monto, categoria, subcategoria, tipo)
MOVIMIENTOS = (
    ('2023-08-08', '2023-08-08', 'PAGO CUENTA DE TERCERO BNET TRANSF A', 1200.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-08-11', '2023-08-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A', 800.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-08-11', '2023-08-11', 'SPEI RECIBIDONAFIN', 5000.00, 'CETES', 'RETIRO', 'INVERSION'),
    ('2023-08-11', '2023-08-11', 'PAGO TARJETA DE CREDITO', 9675.62, 'PAGO_TDC', '', 'GASTO'),
    ('2023-08-14', '2023-08-14', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 500.00, 'FINANZAS', 'Transferencia', 'INGRESO'),
    ('2023-08-14', '2023-08-14', 'PAGO CUENTA DE TERCERO BNET DEPOSITO DPTO', 2500.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-08-15', '2023-08-15', 'SPEI RECIBIDONAFIN', 5000.00, 'CETES', 'RETIRO', 'INVERSION'),
    ('2023-08-15', '2023-08-15', 'PAGO DE NOMINA FIBRA HOTELERA SC', 7604.56, 'NOMINA', 'Pago nominal', 'INGRESO'),
    ('2023-08-16', '2023-08-16', 'PAGO CUENTA DE TERCERO BNET TRANSF A', 500.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-08-16', '2023-08-16', 'NAFIN 12206 CETESDIRECTO DOMICILIACION', 4000.00, 'CETES', 'APORTACION', 'INVERSION'),
    ('2023-08-17', '2023-08-17', 'SPEI RECIBIDOHSBC 5401406RENTA', 800.00, 'VIVIENDA', 'Aportación renta', 'INGRESO'),
    ('2023-08-19', '2023-08-21', 'RETIRO SIN TARJETA QR', 8500.00, 'FINANZAS', 'Retiro efectivo', 'GASTO'),
    ('2023-08-21', '2023-08-19', 'DLOCAL*DIDI FOOD MX RFC: DME 180122DU4 10:04 AUT: 745508', 74.00, 'COMIDA_FUERA', 'Delivery', 'GASTO'),
    ('2023-08-23', '2023-08-23', 'PAGO CUENTA DE TERCERO BNET TRANSF A', 120.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-08-24', '2023-08-25', 'PAGO CUENTA DE TERCERO BNET TRANSF A', 30.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-08-28', '2023-08-28', 'RETIRO SIN TARJETA', 200.00, 'FINANZAS', 'Retiro efectivo', 'GASTO'),
    ('2023-08-31', '2023-08-31', 'PAGO CUENTA DE TERCERO BNET PAGO 8', 1378.00, 'FINANZAS', 'Transferencia', 'INGRESO'),
    ('2023-08-31', '2023-08-31', 'PAGO DE NOMINA FIBRA HOTELERA SC', 7574.68, 'NOMINA', 'Pago nominal', 'INGRESO'),
    ('2023-08-31', '2023-08-31', 'NAFIN 12206 CETESDIRECTO DOMICILIACION', 4000.00, 'CETES', 'APORTACION', 'INVERSION'),
    ('2023-09-02', '2023-09-04', 'RETIRO SIN TARJETA', 200.00, 'FINANZAS', 'Retiro efectivo', 'GASTO'),
    ('2023-09-03', '2023-09-04', 'PAGO CUENTA DE TERCERO BNET MENSU GIO', 800.00, 'FINANZAS', 'Transferencia', 'GASTO'),
    ('2023-09-04', '2023-09-04', 'RETIRO SIN TARJETA', 200.00, 'FINANZAS', 'Retiro efectivo', 'GASTO'),
    ('2023-09-05', '2023-09-05', 'SITH20000007452 FIBRA HOTELERA SC', 5110.99, 'FINANZAS', 'Fideicomiso', 'INGRESO'),
    ('2023-09-06', '2023-09-06', 'PAGO CUENTA DE TERCERO BNET EXPENSE BOTANAS', 462.00, 'EXPENSE', '', 'GASTO'),
    ('2023-09-06', '2023-09-06', 'PAGO CUENTA DE TERCERO BNET FINIQUITO', 2784.00, 'FINANZAS', 'Transferencia', 'GASTO'),
)


def aplicar(db) -> tuple[int, int]:
    """Inserta las filas que falten; devuelve (insertadas, ya existían)."""
    from .routes import _reaplicar_reglas, _unify_movimiento_interno
    nuevas, ya = [], 0
    for fecha, fecha_cargo, desc, monto, cat, sub, tipo in MOVIMIENTOS:
        if db.execute("""SELECT 1 FROM est_movimientos WHERE banco='BBVA_DEB' AND substr(fecha,1,10)=?
                         AND ABS(ABS(monto)-?) < 0.005 AND tipo=?""", (fecha, monto, tipo)).fetchone():
            ya += 1
            continue
        cur = db.execute("""INSERT OR IGNORE INTO est_movimientos
                            (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
                            VALUES (?,?,?,?, 'BBVA_DEB', ?,?,?,?)""",
                         (fecha, fecha_cargo, desc, monto, PERIODO, cat, sub, tipo))
        if cur.rowcount:
            nuevas.append(cur.lastrowid)
        else:
            ya += 1
    if nuevas:
        _unify_movimiento_interno(db, nuevas)
        _reaplicar_reglas(db)
    return len(nuevas), ya
