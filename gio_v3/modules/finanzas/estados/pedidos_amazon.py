"""
Pedidos de Amazon que el usuario pasa (captura de «Detalles del pedido») con la
categoría de lo que compró. El estado de cuenta solo dice «AMAZON», así que el
keyword los manda todos a DIGITAL; con el pedido se sabe qué fue.

Cada pedido se liga al cargo de Amazon con el mismo total, cargado entre el día
del pedido y 10 días después (el banco a veces lo cobra al enviar o entregar,
ej. el desodorante del 14/07 aparece el 19/07). Si hay varios, el más cercano.
Se aplica en «Aplicar reglas» y al cargar estados, así que un pedido de una
tarjeta aún no cargada se liga solo cuando llegue su estado.

Pedidos a meses: la línea de la compra se queda en FINANZAS/«Compra a meses»
(fuera del gasto); la categoría la llevan sus mensualidades, en
msi.MENSUALIDADES_AMAZON.

Devoluciones con reembolso a la tarjeta (DEVUELTOS): si aparecen el cargo y el
abono de Amazon por el mismo monto (hasta 60 días después), los dos pasan a
FINANZAS/Reembolsable: ni gasto ni ingreso. Si el abono no aparece, el cargo
se queda como estaba. /finanzas/estados/admin/pedidos-amazon dice qué se
encontró.
"""
from datetime import date, timedelta

VENTANA_DIAS = 10
VENTANA_REEMBOLSO_DIAS = 60

# (fecha del pedido, total, producto, categoria, subcategoria)
PEDIDOS = [
    ('2026-07-13', 246.25, 'Blanqueador Dr. Beckmann + Downy perlas', 'VIVIENDA', 'Artículos del hogar'),
    ('2026-07-13', 999.00, 'Maleta de mano rígida', 'VIVIENDA', 'Artículos del hogar'),
    ('2026-07-14', 45.45, 'Desodorante Dove Men Care', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2026-07-18', 298.00, 'Bolsas de vacío para ropa (Mastercard 4254)', 'VIVIENDA', 'Artículos del hogar'),
    # Oral B iO Series 6 $2,181.77 (13/07/2026) fue a 15 MSI: ver msi.MENSUALIDADES_AMAZON.
    # Pedido 13/07/2026 de $445.09 que el banco cobró en dos cargos; la creatina,
    # con la promoción de $29.90, fue $269.10.
    ('2026-07-13', 269.10, 'Creatina monohidratada 450 g', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2026-07-13', 175.99, 'Correa trenzada para Apple Watch', 'TECH/DIGITAL', 'Accesorios'),
    # Pedido 24/05/2026 de $711.84, tres cargos. El desodorante ($48 menos 10%
    # de Planea y Ahorra = $43.20) no es suscripción, aunque
    # _corregir_amazon_suscripciones mande los $43.20 de «AMAZON MEXICO» ahí.
    ('2026-05-24', 269.99, 'Funda para Kindle', 'VIVIENDA', 'Artículos del hogar'),
    ('2026-05-24', 398.65, 'Regleta multicontacto Tessan', 'VIVIENDA', 'Artículos del hogar'),
    ('2026-05-24', 43.20, 'Desodorante Dove Men Care', 'CUIDADO_PERSONAL', 'Higiene'),
    # Apple Watch Series 11 $7,186.75 (28/05/2026) fue a 15 MSI: ver msi.MENSUALIDADES_AMAZON.
    # Molinillo (regalo a Cornelius) y sartén del 07/05/2026 se pagaron con saldo
    # de Amazon: total $0, no hay cargo en ninguna tarjeta.
    ('2026-05-01', 111.18, 'Protector solar L\'Oréal + CeraVe PM', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2026-03-29', 488.08, 'Pants Nike Club', 'ROPA', 'Ropa deportiva'),
    ('2026-03-28', 936.80, 'Chaqueta Nike Park 20 Rain', 'ROPA', 'Ropa deportiva'),
    # Cartuchos Pilot, shampoo Ducray y espejo LED en un solo pedido: va a lo
    # que más pesa (el espejo).
    ('2026-03-28', 1057.00, 'Espejo LED + cartuchos Pilot + shampoo Ducray', 'VIVIENDA', 'Artículos del hogar'),
    # Audífonos Soundcore $999 devueltos: el reembolso quedó como saldo de
    # Amazon y con él salieron los pedidos en $0 (tenis y short Puma,
    # calcetines Under Armour, limpiador de lavadora). El cargo es esa ropa.
    ('2026-03-13', 999.00, 'Audífonos devueltos -> tenis/short Puma, calcetines UA', 'ROPA', 'Ropa deportiva'),
    ('2026-03-10', 260.10, 'Creatina monohidratada 450 g', 'CUIDADO_PERSONAL', 'Higiene'),
    # Cajón Nespresso (23/02) y Pato (18/02) salieron en $0: sin cargo.
    ('2026-01-25', 783.06, 'Sábanas Lacoste', 'VIVIENDA', 'Artículos del hogar'),
    # RAM Kingston x2 + power bank ($2,657) y cable HDMI ($114.89) del 24/01
    # fueron a 6 MSI: ver msi.MENSUALIDADES_AMAZON.
    ('2026-01-24', 448.99, 'Mouse UGREEN', 'TECH/DIGITAL', 'Accesorios'),
    ('2026-01-10', 182.00, 'Protector solar L\'Oréal UV Defender', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2026-01-10', 149.99, 'Pluma estilográfica Amazon Basics', 'APRENDIZAJE', 'Papelería'),
    ('2026-01-03', 520.00, 'Aspiradora inalámbrica para auto', 'TRANSPORTE', 'Mantenimiento auto'),
    ('2025-12-03', 196.00, 'Kit de sujeción de batería del coche', 'TRANSPORTE', 'Mantenimiento auto'),
    ('2025-12-03', 1680.49, 'Almohadas Luuna + vaporizador Taurus', 'VIVIENDA', 'Artículos del hogar'),
    ('2025-12-01', 238.00, 'Bolas magnéticas antiestrés (regalo)', 'FAMILIA_REGALOS', 'Regalos'),
    # Mejoras a la PC (sep 2025). El pedido del 25/09 ($1,065.17: hub USB, pasta
    # térmica, desarmadores, kits de limpieza y limpia lavadoras) llegó en cinco
    # cargos que suman justo el total.
    ('2025-09-24', 1779.00, 'SSD WD_Black SN7100 1 TB', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-25', 249.00, 'Mejoras PC (1/5 del pedido de $1,065.17)', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-25', 256.12, 'Mejoras PC (2/5 del pedido de $1,065.17)', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-25', 226.00, 'Mejoras PC (3/5 del pedido de $1,065.17)', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-25', 189.05, 'Mejoras PC (4/5 del pedido de $1,065.17)', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-25', 145.00, 'Mejoras PC (5/5 del pedido de $1,065.17)', 'TECH/DIGITAL', 'Accesorios'),
    # Bose QuietComfort $2,999 (20/07/2025) fue a 15 MSI: ver msi.MENSUALIDADES_AMAZON.
    ('2026-08-12', 279.63, 'Cetaphil crema limpiadora', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2026-09-03', 43.20, 'Desodorante Dove Men Care', 'CUIDADO_PERSONAL', 'Higiene'),
    # Más para la PC (sep 2025): monitor, teclado, y soporte + carcasa de disco
    # (pedido de $323.10 cobrado en dos cargos).
    ('2025-09-13', 1949.00, 'Monitor Xiaomi A27i 27"', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-13', 509.00, 'Teclado Free Wolf M96', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-14', 134.10, 'Soporte laptop / carcasa de disco (1/2 del pedido de $323.10)', 'TECH/DIGITAL', 'Accesorios'),
    ('2025-09-14', 189.00, 'Soporte laptop / carcasa de disco (2/2 del pedido de $323.10)', 'TECH/DIGITAL', 'Accesorios'),
    # Echo Dot $749 (30/09/2025) fue a 3 MSI: ver msi.MENSUALIDADES_AMAZON.
    # Pedido 07/10/2025 de $2,156.90 en cinco cargos; el de $88 fue la caja de
    # herramientas devuelta (DEVUELTOS) y el de $1,299 el microondas.
    ('2025-10-07', 1299.00, 'Microondas Xwave Mirage', 'VIVIENDA', 'Artículos del hogar'),
    ('2025-10-07', 355.00, 'Creatina monohidratada 450 g', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-10-07', 136.00, 'Detergente Persil 4.65 L', 'VIVIENDA', 'Artículos del hogar'),
    # Un solo cargo por Suavitel ($101) + protector solar ($143) + desodorante
    # ($50), menos la promoción: va a lo que más pesa (cuidado personal).
    ('2025-10-07', 278.90, 'Protector solar + desodorante + Suavitel', 'CUIDADO_PERSONAL', 'Higiene'),
    # Pedido 30/11/2025 de $1,422.17: un cargo por producto.
    ('2025-11-30', 389.27, 'Amortiguadores de cajuela Ibiza', 'TRANSPORTE', 'Mantenimiento auto'),
    ('2025-11-30', 259.00, 'Funda para volante', 'TRANSPORTE', 'Mantenimiento auto'),
    ('2025-11-30', 332.15, 'Contenedores herméticos Vtopmart', 'VIVIENDA', 'Artículos del hogar'),
    ('2025-11-30', 312.75, 'Lentes de sol Hawkers', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-11-30', 129.00, 'Cepillo de silicona para inodoro', 'VIVIENDA', 'Artículos del hogar'),
    # 2025 (BBVA crédito)
    ('2025-05-21', 459.00, 'Compresa caliente eléctrica', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-04-04', 668.33, 'Camiseta Lacoste cuello V', 'ROPA', 'Ropa'),
    # Pedido 04/04 de $634.88 en dos cargos: creatina Birdman ($498) y pintura
    # Angelus para cuero ($136.88, para tenis).
    ('2025-04-04', 498.00, 'Creatina Birdman 450 g', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-04-04', 136.88, 'Pintura Angelus para cuero', 'ROPA', 'Calzado'),
    ('2025-03-27', 299.00, 'Aromatizante Air Wick (7 repuestos)', 'VIVIENDA', 'Artículos del hogar'),
    # Pedido 27/03 de $331.99 en dos cargos: organizador de regadera ($199) y
    # atomizadores de perfume ($132.99), según el precio probable de cada uno.
    ('2025-03-27', 199.00, 'Organizador de regadera (2 pzas)', 'VIVIENDA', 'Artículos del hogar'),
    ('2025-03-27', 132.99, 'Atomizadores de perfume', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-02-15', 999.00, 'Perfume Lacoste L.12.12 Blanc', 'CUIDADO_PERSONAL', 'Higiene'),
    # Pedido 01/02 de $767.31 en dos cargos.
    ('2025-02-01', 599.99, 'Recipientes de vidrio EasyWare', 'VIVIENDA', 'Artículos del hogar'),
    ('2025-02-01', 167.32, 'Protector solar L\'Oréal UV Defender', 'CUIDADO_PERSONAL', 'Higiene'),
    # Cetaphil pedido el 29/01/2025 que el banco cobró hasta el 18/02 (fuera de
    # la ventana de 10 días): se registra con la fecha del cargo.
    ('2025-02-18', 278.10, 'Cetaphil crema limpiadora (pedido 29/01)', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-01-16', 751.28, 'Resveratrol + Omega 3 B Life', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2025-01-13', 3990.00, 'Llantas Mirage 185/60R15 (4)', 'TRANSPORTE', 'Mantenimiento auto'),
    # 2024 y 2023 (BBVA Oro)
    ('2024-05-24', 349.30, 'Creatina monohidratada 450 g', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2024-04-12', 99.00, 'Atomizador de perfume', 'CUIDADO_PERSONAL', 'Higiene'),
    # Lámpara + Roku + banco zapatero $1,737.99 (06/04/2024) fue a 6 MSI: ver
    # msi.MENSUALIDADES_AMAZON. La pintura Angelus de $228 del mismo día se
    # cargó a meses y se reversó (-$228 el 10/04): no hay gasto.
    ('2024-01-04', 357.00, 'Creatina Valara 450 g', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2023-12-04', 599.15, 'Agenda Clever Fox Weekly 2024-2025', 'APRENDIZAJE', 'Papelería'),
    ('2023-11-27', 399.00, 'Proteína Evolution WP60', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2023-10-17', 557.40, 'Cortinas opacas Amazon Basics', 'VIVIENDA', 'Artículos del hogar'),
    ('2023-10-13', 338.00, 'Soporte de TV para pared', 'VIVIENDA', 'Artículos del hogar'),
    ('2023-07-30', 284.99, 'Collar Clepsidra', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2023-07-30', 1577.24, 'Tenis Lacoste Hydez', 'ROPA', 'Calzado'),
    # Creatina Birdman $363 (15/05/2024) devuelta, pero el reembolso quedó como
    # saldo de Amazon: el cargo sigue siendo gasto.
    ('2024-05-15', 363.00, 'Creatina Birdman (devuelta a saldo Amazon)', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2023-07-25', 349.00, 'Soporte UGREEN para tablet', 'TECH/DIGITAL', 'Accesorios'),
    ('2023-07-02', 400.00, 'Creatina Pura Premium 500 g', 'CUIDADO_PERSONAL', 'Higiene'),
    # Audífonos Sennheiser HD 450SE $3,355.95 (11/03/2023) fueron a 6 MSI: ver
    # msi.MENSUALIDADES_AMAZON.
    ('2023-01-16', 469.00, 'Creatina Valara 450 g (débito)', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2023-01-08', 334.34, 'Maleta deportiva Puma Evercat', 'ROPA', 'Ropa deportiva'),
]

# (fecha del pedido, total, producto): devueltos con reembolso a la tarjeta.
DEVUELTOS = [
    ('2026-04-28', 970.00, 'Control Xbox Carbon Black'),
    ('2025-10-07', 88.00, 'Caja de herramientas Pretul'),
]

_AMAZON = "UPPER(descripcion) LIKE '%AMAZON%' AND ABS(ABS(monto) - ?) < 0.01"


def _hasta(fecha, dias):
    return (date.fromisoformat(fecha) + timedelta(days=dias)).isoformat()


def _cargo(db, fecha, monto):
    return db.execute(f"""
        SELECT id, fecha, descripcion, monto, banco, categoria, subcategoria FROM est_movimientos
        WHERE {_AMAZON} AND substr(fecha,1,10) BETWEEN ? AND ? AND tipo='GASTO' AND monto > 0
          AND parcialidad_num IS NULL AND COALESCE(subcategoria,'') != 'Compra a meses'
        ORDER BY julianday(substr(fecha,1,10)) - julianday(?), id LIMIT 1
    """, (monto, fecha, _hasta(fecha, VENTANA_DIAS), fecha)).fetchone()


def _reembolso(db, cargo, monto):
    """Abono de Amazon por el mismo monto después del cargo: negativo en la
    tarjeta de crédito o INGRESO en débito."""
    f = cargo['fecha'][:10]
    return db.execute(f"""
        SELECT id, fecha, descripcion, monto, banco, categoria, subcategoria FROM est_movimientos
        WHERE {_AMAZON} AND substr(fecha,1,10) BETWEEN ? AND ? AND id != ?
          AND (monto < 0 OR tipo='INGRESO')
        ORDER BY substr(fecha,1,10), id LIMIT 1
    """, (monto, f, _hasta(f, VENTANA_REEMBOLSO_DIAS), cargo['id'])).fetchone()


def _poner(db, row, cat, sub) -> int:
    if (row['categoria'], row['subcategoria'] or '') == (cat, sub):
        return 0
    db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
    return 1


def aplicar(db) -> tuple[int, int]:
    """(actualizados, no encontrados). Idempotente."""
    ok = faltan = 0
    for fecha, monto, _producto, cat, sub in PEDIDOS:
        row = _cargo(db, fecha, monto)
        if not row:
            faltan += 1
            continue
        ok += _poner(db, row, cat, sub)
    for fecha, monto, _producto in DEVUELTOS:
        cargo = _cargo(db, fecha, monto)
        abono = cargo and _reembolso(db, cargo, monto)
        if not abono:
            faltan += 1
            continue
        ok += _poner(db, cargo, 'FINANZAS', 'Reembolsable') + _poner(db, abono, 'FINANZAS', 'Reembolsable')
    return ok, faltan


_CAMPOS = ('id', 'fecha', 'descripcion', 'monto', 'banco', 'categoria', 'subcategoria')


def _mov(r):
    return r and {k: r[k] for k in _CAMPOS}


def _cercanos(db, fecha, usados, dias_despues=45):
    """Movimientos de Amazon (cargos y abonos, sin mensualidades) de 5 días
    antes a `dias_despues` del pedido que ningún pedido tomó: para ligar a
    mano un pedido que no cuadró al centavo o se cobró partido."""
    desde = (date.fromisoformat(fecha) - timedelta(days=5)).isoformat()
    rows = db.execute(f"""
        SELECT {', '.join(_CAMPOS)} FROM est_movimientos
        WHERE UPPER(descripcion) LIKE '%AMAZON%' AND substr(fecha,1,10) BETWEEN ? AND ?
          AND parcialidad_num IS NULL AND UPPER(descripcion) NOT LIKE '%MESES%'
        ORDER BY substr(fecha,1,10), id
    """, (desde, _hasta(fecha, dias_despues))).fetchall()
    return [_mov(r) for r in rows if r['id'] not in usados][:20]


def plan(db) -> list[dict]:
    """Solo lectura: cada pedido con el cargo (y, si se devolvió, el abono) que
    le tocó; los que no tienen, con los movimientos de Amazon cercanos libres."""
    out = []
    for fecha, monto, producto, cat, sub in PEDIDOS:
        out.append({'pedido': fecha, 'total': monto, 'producto': producto,
                    'categoria': f'{cat}/{sub}', 'cargo': _mov(_cargo(db, fecha, monto))})
    for fecha, monto, producto in DEVUELTOS:
        cargo = _cargo(db, fecha, monto)
        out.append({'pedido': fecha, 'total': monto, 'producto': producto, 'devuelto': True,
                    'cargo': _mov(cargo), 'reembolso': _mov(cargo and _reembolso(db, cargo, monto))})
    usados = {m['id'] for p in out for m in (p['cargo'], p.get('reembolso')) if m}
    for p in out:
        if not p['cargo'] or (p.get('devuelto') and not p['reembolso']):
            p['cercanos'] = _cercanos(db, p['pedido'], usados, 75 if p.get('devuelto') else 45)
    return out
