"""
Retiros de efectivo («RETIRO SIN TARJETA») que el usuario identificó: el banco
solo dice que sacó efectivo, no en qué se fue. Cada uno pasa a su categoría y
lleva una nota al final de la descripción (se conserva el texto del banco).

Cambiar la descripción no duplica nada al volver a cargar el estado: el
importador deduplica por fecha + monto + tipo + banco (estados/routes.py).
"""

# (fecha, monto, texto del banco, categoria, subcategoria, nota)
RETIROS = (
    # 2026-10-06: «los 5,500 y los 3,400 fue un regalo, unos anillos que le
    # hice a Ale». El de $3,400 ya se había desligado de un préstamo a
    # Cornelio (prestamos.NO_ERAN_PRESTAMO).
    ('2026-07-11', 3400.0, 'RETIRO SIN TARJETA', 'FAMILIA_REGALOS', 'Regalos', 'Anillos Ale'),
    ('2026-07-18', 5500.0, 'RETIRO SIN TARJETA', 'FAMILIA_REGALOS', 'Regalos', 'Anillos Ale'),
)


def aplicar(db) -> tuple[int, int]:
    """(aplicados, no encontrados). Idempotente: la nota no se repite."""
    ok = falta = 0
    for fecha, monto, texto, cat, sub, nota in RETIROS:
        m = db.execute("""SELECT id, descripcion FROM est_movimientos
                          WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005
                            AND UPPER(descripcion) LIKE ? AND tipo='GASTO'
                          ORDER BY id LIMIT 1""", (fecha, monto, f"%{texto}%")).fetchone()
        if not m:
            falta += 1
            continue
        desc = m['descripcion'] or ''
        if nota.upper() not in desc.upper():
            desc = f"{desc} · {nota}"
        db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, descripcion=? WHERE id=?",
                   (cat, sub, desc, m['id']))
        ok += 1
    return ok, falta
