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
msi.CATEGORIA_MENSUALIDADES.

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
    # Oral B iO Series 6 $2,181.77 (13/07/2026) fue a 15 MSI: ver msi.CATEGORIA_MENSUALIDADES.
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
    # Apple Watch Series 11 $7,186.75 (28/05/2026) fue a 15 MSI: ver msi.CATEGORIA_MENSUALIDADES.
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
    # fueron a 6 MSI: ver msi.CATEGORIA_MENSUALIDADES.
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
    # Bose QuietComfort $2,999 (20/07/2025) fue a 15 MSI: ver msi.CATEGORIA_MENSUALIDADES.
    ('2026-08-12', 279.63, 'Cetaphil crema limpiadora', 'CUIDADO_PERSONAL', 'Higiene'),
    ('2026-09-03', 43.20, 'Desodorante Dove Men Care', 'CUIDADO_PERSONAL', 'Higiene'),
]

# (fecha del pedido, total, producto): devueltos con reembolso a la tarjeta.
DEVUELTOS = [
    ('2026-04-28', 970.00, 'Control Xbox Carbon Black'),
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
