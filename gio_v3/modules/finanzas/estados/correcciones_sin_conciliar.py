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

# Tanda 5 (2026-10-04, comentarios a la lista de Sin conciliar):
CORRECCIONES += [
    (5328, '2022-06-10', 1500.0, 'PABLO', 'COMIDA_FUERA', 'Restaurante'),   # «mándalo a comida»
]

# Tanda 6 (2026-10-05): la renta de oct-2024 que se mandó a BANORTE y regresó
# («fue un depósito que hice a esa tarjeta Banorte, me lo regresaron y
# transferí a BBVA»): es tu propio dinero de vuelta, no ingreso.
CORRECCIONES += [
    (3061, '2024-10-08', 11000.0, 'BANORTE', 'FINANZAS', 'Entre cuentas propias'),
    # «cierralo de la mejor manera»: efectivo propio depositado a la cuenta, un
    # SPEI que regresó y un SPEI de STP (cuenta propia en otra app): ni
    # ingreso ni gasto.
    (2079, '2026-05-12', 5000.0, 'EFECTIVO EN COMERCIO', 'FINANZAS', 'Entre cuentas propias'),
    (2935, '2025-06-02', 3000.0, 'EFECTIVO EN COMERCIO', 'FINANZAS', 'Entre cuentas propias'),
    (3175, '2025-03-28', 192.5, 'SPEI DEVUELTO', 'FINANZAS', 'Entre cuentas propias'),
    (2431, '2026-08-10', 3000.0, 'STP', 'FINANZAS', 'Entre cuentas propias'),
]

# Sugerencias de la app que el usuario aceptó en bloque (2026-10-04: «aplica
# las sugerencias menos de gracias»): (id, fecha, monto, texto, categoria,
# subcategoria, viaje o None). «Reembolso compartido» = te regresaron lo que
# pagaste por otros en ese viaje.
SUGERENCIAS_ACEPTADAS = [
    (2590, '2024-11-12', 140.0, 'VIAJE MAZAMITLA', 'VIAJES', 'Otros', None),
    (2585, '2024-11-11', 100.0, 'TRANSF A GIOVANY', 'COMIDA_FUERA', 'Restaurante', None),     # Merpago Los Volcanes
    (2583, '2024-11-08', 63.0, 'DEUDAR MAR', 'COMIDA_FUERA', 'Restaurante', None),            # 1/2 de Merpago Dani
    (3062, '2024-10-09', 56.0, 'TRANSF A GIOVANY', 'SUPER', 'Súper', None),                   # Soriana
    (3130, '2024-09-20', 1000.0, 'TRANSF A GIOVANY', 'FINANZAS', 'Reembolso compartido', 'VIAJE 2024'),
    (3125, '2024-09-19', 89.0, 'TRANSF A GIOVANY', 'CAFE/PAN', 'Café', 'VIAJE 2024'),         # 1/2 de Starbucks
    (3116, '2024-09-13', 4000.0, 'TRANSF A UNDEFINED', 'FINANZAS', 'Reembolso compartido', 'VIAJE 2024'),
    (3110, '2024-09-11', 32.5, 'PIZZA', 'COMIDA_FUERA', 'Restaurante', None),
    (3347, '2024-01-07', 3814.0, 'PAGO 10 11 12', 'FINANZAS', 'Reembolso compartido', 'FIN DE AÑO 2023'),
    (3793, '2023-06-22', 360.0, 'TRANSF A GIOVANY', 'FINANZAS', 'Reembolso compartido', 'VILLA JUNIO 2023'),
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
    # 2026-10-04: «si yo pagué todo, es deuda»: pago de deuda a su papá, no seguro.
    ('2026-04-15', 3311.0, 'DEUDA', 'FINANZAS', 'Transferencia enviada'),
    # Nespresso compartido (2026-10-03): «compré una parte para mí y otra para
    # alguien más; me transfirieron su parte» ($410, «CAPSULAS CAFE», abajo).
    ('2026-07-17', 918.75, 'NESPRESSO', 'CAFE/PAN', 'Café', 508.75),
]

# Entradas de dinero (aunque se hayan guardado como salida): alguien pagándole
# su parte de un gasto que ya lleva mi_parte. (fecha, monto, texto, categoria,
# subcategoria). «Reembolso compartido» no es ingreso ni sale en Sin conciliar.
ENTRADAS = [
    ('2026-07-17', 410.0, 'CAPSULAS CAFE', 'FINANZAS', 'Reembolso compartido'),
    # «fue un depósito que yo mismo me hice para pagar la renta» (2026-10-03)
    ('2026-04-07', 7000.0, 'DEPOSITO EFECTIVO PRACTIC', 'FINANZAS', 'Entre cuentas propias'),
    ('2026-03-23', 1110.0, 'TRANSF', 'FINANZAS', 'Reembolso compartido'),     # Judi: devolución o reparto de gastos
    ('2026-08-10', 3000.0, 'SPEI RECIBIDO', 'FINANZAS', 'Transferencia recibida'),  # sin identificar: a Sin conciliar
    ('2026-02-15', 300.0, 'TRANSF A GIOVANY A', 'FINANZAS', 'Reembolso compartido'),  # de Judith
    ('2026-09-25', 105.0, 'BNET COMIDA', 'COMIDA_FUERA', 'Restaurante'),            # su parte de una comida: resta a Comida fuera
    ('2026-07-02', 0.01, 'VAL.ASEG', 'FINANZAS', 'Entre cuentas propias'),          # centavo de validación de Qualitas
]


# Salidas que quedaron guardadas como entrada («PAGO CUENTA DE TERCERO» es
# ambiguo en el PDF de BBVA): (fecha, monto, texto, categoria, subcategoria).
# Se busca por la categoría que ya tienen para no confundirlas con otro abono
# del mismo día. El usuario, 2026-10-03: «esto no es ingreso, yo lo pagué de consulta».
# (fecha, monto, texto, categoría que tiene hoy, categoría, subcategoría)
INGRESOS_QUE_ERAN_GASTO = [
    # Vacía desde la auditoría contra los PDF (2026-10-03): las que había aquí
    # (consulta $1,000, $57, $400, MENS GIO $700, Fresko) eran abonos con texto
    # del renglón vecino — devoluciones de su mamá (…3042) y del súper (…6197).
]


# Movimientos cuya descripción se mezcló con la del renglón vecino al leer el
# PDF (el usuario revisó sus estados BBVA de 2026, 2026-10-03: «FIBRA
# HOTELERA» venía del pago de nómina pegado). Se reescribe la descripción y
# se pone la dirección y categoría correctas.
# (fecha, monto, texto que hoy trae, descripción real, tipo, categoria, subcategoria)
REESCRITOS = [
    ('2026-03-12', 505.0, 'FIBRA HOTELERA', 'PAGO CUENTA DE TERCERO BNET PLANTITA',
     'GASTO', 'VIVIENDA', 'Plantas'),
    ('2026-03-29', 6000.0, 'FIBRA HOTELERA', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A',
     'INGRESO', 'FINANZAS', 'Reembolso compartido'),              # de Judith (auditoría 2026): no es ingreso
    ('2026-04-27', 460.41, 'FIBRA HOTELERA', 'PAGO CUENTA DE TERCERO BNET EXPENSE',
     'GASTO', 'EXPENSE', ''),                                     # le pasa a un compañero su parte (TERCERO)
    # Revisión contra los PDF (2026-10-03), abonos que estaban en Viajes/Otros:
    ('2026-03-31', 2299.0, 'SIN DESCRIPCION', 'SITH26623774 FIDEICOMISO F/1596',
     'INGRESO', 'FINANZAS', 'Reembolsable'),                      # «es un expense pagado»
    ('2026-04-07', 1500.0, 'EGRESOS SPEI SVD', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A',
     'INGRESO', 'OTROS', ''),                                     # de su papá (auditoría 2026): ingreso; el texto era del Cetes vecino
    ('2026-04-21', 738.0, 'PAGO CUENTA DE TERCERO', 'PAGO CUENTA DE TERCERO BNET LIQUIDOS',
     'INGRESO', 'OTROS', ''),                                     # le regresaron algo que pagó con vales: sí es ingreso
    # Revisión de «Comida fuera» contra los PDF (2026-10-03):
    ('2026-04-14', 750.0, 'FIBRA HOTELERA', 'SPEI ENVIADO SANTANDER MENS GIO',
     'GASTO', 'SALSA', 'Clases'),                                 # SPEI a Esteban Aceves «mens gio»: va a salsa
    ('2026-03-26', 227.0, 'HSBC MARZ GIO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A',
     'INGRESO', 'OTROS', ''),                                     # de su papá: ingreso; «HSBC MARZ GIO» era del SPEI del 28/03
]


_REFERENCIAS = (('est_prestamos', 'movimiento_id'), ('est_prestamo_devoluciones', 'movimiento_id'),
                ('est_expense_lote_gastos', 'movimiento_id'), ('est_expense_lote_depositos', 'movimiento_id'),
                ('debt_payment_movs', 'movimiento_id'))   # abono de un compromiso (modules/finanzas/compromisos.py)


def _referenciado(db, mid) -> bool:
    for tabla, col in _REFERENCIAS:
        try:
            if db.execute(f"SELECT 1 FROM {tabla} WHERE {col}=?", (mid,)).fetchone():
                return True
        except Exception:
            pass
    return False


def _reescribir(db, fecha, monto, texto, desc, tipo, cat, sub):
    """Corrige un movimiento de REESCRITOS. None si no está. Si ya existe otra
    copia con la descripción real (el mismo estado importado de dos PDFs), la
    de descripción mezclada es duplicada: se borra (si nada la usa) y se corrige
    la otra — antes el UNIQUE(fecha, descripcion, monto) hacía fallar todo."""
    filas = db.execute("""SELECT id, descripcion FROM est_movimientos WHERE substr(fecha,1,10)=?
                           AND ABS(ABS(monto) - ?) < 0.01 AND (UPPER(descripcion) LIKE ? OR descripcion=?)
                         ORDER BY id""", (fecha, monto, f"%{texto}%", desc)).fetchall()
    if not filas:
        return None
    buena = next((r for r in filas if r['descripcion'] == desc), None)
    n = 0
    for r in filas:
        if buena and r['id'] != buena['id'] and not _referenciado(db, r['id']):
            db.execute("DELETE FROM est_movimientos WHERE id=?", (r['id'],))
            n += 1
    objetivo = buena['id'] if buena else filas[0]['id']
    if not buena:
        # sin copia buena: si chocara con otra fila (otra fecha exacta/monto), no se renombra
        choque = db.execute("SELECT 1 FROM est_movimientos WHERE fecha=(SELECT fecha FROM est_movimientos WHERE id=?) "
                            "AND descripcion=? AND monto=(SELECT monto FROM est_movimientos WHERE id=?) AND id != ?",
                            (objetivo, desc, objetivo, objetivo)).fetchone()
        if choque:
            desc = None
    n += db.execute("""UPDATE est_movimientos SET descripcion=COALESCE(?, descripcion), tipo=?, categoria=?, subcategoria=?
                        WHERE id=? AND (descripcion != COALESCE(?, descripcion) OR tipo != ? OR categoria != ?
                                        OR COALESCE(subcategoria,'') != ?)""",
                    (desc, tipo, cat, sub, objetivo, desc, tipo, cat, sub)).rowcount
    return n


def revisar_reescritos(db) -> list[dict]:
    """Solo lectura: cómo están hoy los movimientos de REESCRITOS."""
    out = []
    for fecha, monto, texto, desc, tipo, cat, sub in REESCRITOS:
        filas = [dict(r) for r in db.execute("""SELECT id, fecha, descripcion, monto, tipo, categoria, subcategoria, banco
                                                FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01
                                                ORDER BY id""", (fecha, monto)).fetchall()]
        out.append({'fecha': fecha, 'monto': monto, 'esperado': {'descripcion': desc, 'tipo': tipo, 'categoria': cat,
                                                                 'subcategoria': sub},
                    'en_base': filas,
                    'correcto': any(f['descripcion'] == desc and f['tipo'] == tipo and f['categoria'] == cat for f in filas)})
    return out


# Auditoría de BBVA Débito 2026 contra los PDF (Cowork, 2026-10-03:
# correcciones_movimientos_2026.csv y movimientos_papa_2026.csv). Cada fila:
# (fecha, monto, palabra para encontrarlo, tipo, categoria, subcategoria,
#  mi_parte, crear) — crear: si no está en la base se registra (los «?» del CSV).
# Se busca por fecha + monto + palabra; si la palabra no aparece (descripción
# mezclada) y hay un solo movimiento con esa fecha y monto, se usa ese — salvo
# en las filas con «crear»: ahí solo cuenta la palabra (si no, se registra), para
# no confundir un cargo faltante con su devolución del mismo día. Las
# filas que ya están en REESCRITOS / ENTRADAS / GASTOS no se repiten aquí.
_PAPA = ('OTROS', '')                                    # «Familia > Papá (recibido)»: ingreso extraordinario
_REGALO = ('OTROS', '')                                  # «Ingreso > Regalo recibido»
_COLECTA = ('FAMILIA_REGALOS', 'Colectas')               # colecta de Martha: entra $1,550, sale $1,500
_SEGURO = ('TRANSPORTE', 'Seguro auto')                  # seguro del carro que le paga a su papá
AUDITORIA_2026 = [
    # Colecta de Martha (pasa por su cuenta: neto +$50)
    ('2026-02-27', 200.0, 'AYUDA', 'INGRESO', *_COLECTA, None, 'PAGO CUENTA DE TERCERO BNET AYUDA'),
    ('2026-02-27', 500.0, 'MARTHA', 'INGRESO', *_COLECTA, None, 'PAGO CUENTA DE TERCERO BNET MARTHA'),
    ('2026-03-03', 250.0, 'MARTHA', 'INGRESO', *_COLECTA, None, None),
    ('2026-03-03', 600.0, 'MARTHA', 'INGRESO', *_COLECTA, None, None),
    ('2026-03-04', 1500.0, 'RETIRO', 'GASTO', *_COLECTA, None, 'RETIRO SIN TARJETA ******7852'),
    # Papá → Gio (ingreso)
    ('2026-01-04', 251.0, 'ROSCA', 'INGRESO', *_PAPA, None, None),
    # 1/feb $1,610: abono de Eli al viaje a Guadalajara (contrapartes_viaje.py), no ingreso
    ('2026-02-01', 1610.0, 'TRANSF', 'INGRESO', 'FINANZAS', 'Reembolso compartido', None, None),
    ('2026-03-23', 500.0, 'TRANSF', 'INGRESO', *_PAPA, None, None),
    ('2026-05-08', 5000.0, 'PRE', 'INGRESO', *_REGALO, None, None),        # regalo de su papá
    ('2026-07-16', 50000.0, 'TQM', 'INGRESO', *_PAPA, None, None),
    # 3/feb le mandó $12,800 y el 4/feb se los regresó («deuda»): neto 0
    ('2026-02-03', 12800.0, 'TRANSF', 'INGRESO', 'FINANZAS', 'Entre cuentas propias', None, None),
    ('2026-02-04', 12800.0, 'DEUDA', 'GASTO', 'FINANZAS', 'Entre cuentas propias', None, None),
    # Gio → Papá: seguro del carro (y en mayo, seguro + deuda: solo el seguro es gasto)
    ('2026-01-15', 555.5, 'SEGURO', 'GASTO', *_SEGURO, None, None),
    ('2026-02-27', 555.5, 'SEGURO', 'GASTO', *_SEGURO, None, None),
    ('2026-05-15', 5555.0, 'SEGURO', 'GASTO', *_SEGURO, 555.0, None),
    ('2026-06-15', 555.0, 'SEGURO', 'GASTO', *_SEGURO, None, None),
    ('2026-07-06', 555.0, 'SEGURO', 'GASTO', *_SEGURO, None, None),
    ('2026-08-15', 555.0, 'SEGURO', 'GASTO', *_SEGURO, None, None),
    ('2026-09-17', 555.0, 'SEGURO', 'GASTO', *_SEGURO, None, None),
    # Cumpleaños (20/ago): Judith («regalito»), su papá y otra persona (los dos «Transf a GIOVANY A»)
    ('2026-08-20', 500.0, 'REGALITO', 'INGRESO', *_REGALO, None, 'PAGO CUENTA DE TERCERO BNET REGALITO'),
    ('2026-08-20', 500.0, 'TRANSF', 'INGRESO', *_REGALO, None, None),
    ('2026-08-20', 500.0, 'TRANSF', 'INGRESO', *_REGALO, None, 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A CUMPLE'),
    # 12/may: depósito en efectivo en OXXO que no hizo él (¿alguien pagándole?): a Sin conciliar
    ('2026-05-12', 5000.0, 'SU PAGO EN EFECTIVO', 'INGRESO', 'FINANZAS', 'Transferencia recibida', None, None),
    # Préstamos a Judi (cargos; sus devoluciones se ligan en prestamos.DEVOLUCIONES_DE_PRESTAMO)
    ('2026-06-10', 4500.0, 'PRESTAMO', 'GASTO', 'PRESTAMOS', 'Prestado', None, 'PAGO CUENTA DE TERCERO BNET PRESTAMO A LA JUDI'),
    ('2026-09-11', 4500.0, 'PRESTAMO', 'GASTO', 'PRESTAMOS', 'Prestado', None, 'PAGO CUENTA DE TERCERO BNET PRESTAMO'),
]


def _aplicar_auditoria(db) -> tuple[int, int]:
    ok = faltan = 0
    usados = set()
    for fecha, monto, palabra, tipo, cat, sub, parte, crear in AUDITORIA_2026:
        filas = [r for r in db.execute("""SELECT id, descripcion, tipo, categoria, subcategoria, mi_parte FROM est_movimientos
                                          WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005 ORDER BY id""",
                                       (fecha, monto)).fetchall() if r['id'] not in usados]
        con = [r for r in filas if palabra in (r['descripcion'] or '').upper()]
        row = con[0] if con else (filas[0] if len(filas) == 1 and not crear else None)
        if not row:
            # Solo se registra si ese mes de BBVA Débito ya está importado (en una
            # base vacía o de pruebas no se inventan movimientos).
            if crear and db.execute("SELECT 1 FROM est_movimientos WHERE banco='BBVA_DEB' AND substr(fecha,1,7)=?",
                                    (fecha[:7],)).fetchone():
                usados.add(db.execute("""INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo,
                                                                      categoria, subcategoria, tipo, mi_parte)
                                         VALUES (?,?,?,?, 'BBVA_DEB', '', ?,?,?,?)""",
                                      (fecha, fecha, crear, monto, cat, sub, tipo, parte)).lastrowid)
                ok += 1
            else:
                faltan += 1
            continue
        usados.add(row['id'])
        if _referenciado(db, row['id']) and cat != 'PRESTAMOS':
            continue   # ya ligado a un préstamo o lote: lo decide ese módulo
        if (row['tipo'], row['categoria'], row['subcategoria'] or '', row['mi_parte']) != (tipo, cat, sub, parte):
            db.execute("UPDATE est_movimientos SET tipo=?, categoria=?, subcategoria=?, mi_parte=?, mi_parte_auto=0 WHERE id=?",
                       (tipo, cat, sub, parte, row['id']))
            ok += 1
    return ok, faltan


def revisar_auditoria(db) -> list[dict]:
    """Solo lectura: cómo están hoy los movimientos de AUDITORIA_2026."""
    out = []
    for fecha, monto, palabra, tipo, cat, sub, parte, _ in AUDITORIA_2026:
        filas = [dict(r) for r in db.execute("""SELECT id, descripcion, tipo, categoria, subcategoria, mi_parte
                                                FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005""",
                                             (fecha, monto)).fetchall()]
        out.append({'fecha': fecha, 'monto': monto, 'esperado': f"{tipo} {cat}/{sub}", 'en_base': filas,
                    'correcto': any(f['tipo'] == tipo and f['categoria'] == cat for f in filas)})
    return out


def _fila(db, mid, fecha, monto, texto):
    row = db.execute("""SELECT id, categoria, subcategoria, viaje_id FROM est_movimientos
                        WHERE id=? AND substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'""",
                     (mid, fecha, monto)).fetchone()
    return row or db.execute("""SELECT id, categoria, subcategoria, viaje_id FROM est_movimientos
                                WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND tipo='INGRESO'
                                  AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""",
                             (fecha, monto, f"%{texto.upper()}%")).fetchone()


def _abonos_de_cuentas_conocidas(db) -> int:
    """Abonos de una cuenta que reembolsa (config.CUENTAS_CONOCIDAS, ej. …3042
    Mommita) que siguen con la categoría genérica del import -> Reembolso
    compartido. Una categoría que el usuario eligió se respeta."""
    from .config import CUENTAS_CONOCIDAS
    n = 0
    for cuenta, datos in CUENTAS_CONOCIDAS.items():
        if datos.get('reembolsa'):
            n += db.execute("""UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolso compartido'
                               WHERE tipo='INGRESO' AND descripcion LIKE ?
                                 AND (COALESCE(categoria, '') IN ('', 'OTROS')
                                      OR (categoria='FINANZAS' AND COALESCE(subcategoria, '') IN
                                          ('', 'Transferencia', 'Transferencia recibida')))""",
                            (f'%{cuenta}%',)).rowcount
    return n


def aplicar(db) -> tuple[int, int]:
    """(actualizadas, no encontradas). Idempotente."""
    ok = faltan = 0
    ok += _abonos_de_cuentas_conocidas(db)
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
    for mid, fecha, monto, texto, cat, sub, viaje in SUGERENCIAS_ACEPTADAS:
        row = _fila(db, mid, fecha, monto, texto)
        if not row:
            faltan += 1
            continue
        v = viaje and db.execute("SELECT id FROM viajes WHERE UPPER(TRIM(nombre))=UPPER(?) ORDER BY id LIMIT 1",
                                 (viaje,)).fetchone()
        vid = v['id'] if v else row['viaje_id']
        if (row['categoria'], row['subcategoria'] or '', row['viaje_id']) != (cat, sub, vid):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, viaje_id=? WHERE id=?",
                       (cat, sub, vid, row['id']))
            ok += 1
    for fecha, monto, texto, desc, tipo, cat, sub in REESCRITOS:
        n = _reescribir(db, fecha, monto, texto, desc, tipo, cat, sub)
        if n is None:
            faltan += 1
        else:
            ok += n
    a_ok, a_faltan = _aplicar_auditoria(db)
    ok, faltan = ok + a_ok, faltan + a_faltan
    for fecha, monto, texto, cat, sub in ENTRADAS:
        row = db.execute("""SELECT id, tipo, categoria, subcategoria FROM est_movimientos
                            WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01 AND UPPER(descripcion) LIKE ?
                            ORDER BY id LIMIT 1""", (fecha, monto, f"%{texto}%")).fetchone()
        if not row:
            faltan += 1
        elif (row['tipo'], row['categoria'], row['subcategoria'] or '') != ('INGRESO', cat, sub):
            db.execute("UPDATE est_movimientos SET tipo='INGRESO', categoria=?, subcategoria=? WHERE id=?",
                       (cat, sub, row['id']))
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
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, tipo='GASTO', mi_parte=?, mi_parte_auto=0 WHERE id=?",
                       (cat, sub, parte, row['id']))
            ok += 1
    return ok, faltan
