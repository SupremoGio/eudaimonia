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
"""
from datetime import date, timedelta

VENTANA_DIAS = 10

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
]


def aplicar(db) -> tuple[int, int]:
    """(actualizados, no encontrados). Idempotente."""
    ok = faltan = 0
    for fecha, monto, _producto, cat, sub in PEDIDOS:
        hasta = (date.fromisoformat(fecha) + timedelta(days=VENTANA_DIAS)).isoformat()
        row = db.execute("""
            SELECT id, categoria, subcategoria FROM est_movimientos
            WHERE UPPER(descripcion) LIKE '%AMAZON%' AND ABS(ABS(monto) - ?) < 0.01
              AND substr(fecha,1,10) BETWEEN ? AND ? AND tipo='GASTO'
              AND parcialidad_num IS NULL AND COALESCE(subcategoria,'') != 'Compra a meses'
            ORDER BY julianday(substr(fecha,1,10)) - julianday(?), id LIMIT 1
        """, (monto, fecha, hasta, fecha)).fetchone()
        if not row:
            faltan += 1
            continue
        if (row['categoria'], row['subcategoria'] or '') != (cat, sub):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
            ok += 1
    return ok, faltan
