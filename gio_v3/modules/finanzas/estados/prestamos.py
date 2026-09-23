"""
Préstamos por cobrar — lógica compartida entre la API de Estados de cuenta
(routes.py) y la Radiografía del mes (budget.py).

Modelo:
  - est_prestamos: un préstamo otorgado (persona = contraparte, fecha, monto),
    normalmente creado desde el movimiento bancario con el que se prestó
    (movimiento_id, categoría PRESTAMOS / tipo GASTO).
  - est_prestamo_devoluciones: movimientos de ingreso ligados a un préstamo.
    Una devolución ligada queda con categoría PRESTAMOS, así que no cuenta
    como ingreso en ningún lado: solo baja el pendiente.
  - perdido_fecha: «Perdido» es manual; ese mes el pendiente cuenta como gasto
    en Familia y regalos, pero solo en la Radiografía (registro interno, no un
    movimiento bancario).

El estado se calcula (Pendiente / Pagado parcial / Pagado) para que nunca se
desincronice de las devoluciones; solo «Perdido» se marca a mano.
"""
from datetime import datetime

PENDIENTE, PARCIAL, PAGADO, PERDIDO = 'Pendiente', 'Pagado parcial', 'Pagado', 'Perdido'

# Categorías de ingreso que se ofrecen como posible devolución: las que ya son
# PRESTAMOS primero y luego transferencias recibidas / sin clasificar, que es
# como suele llegar alguien que te paga.
_CATS_DEVOLUCION = ('PRESTAMOS', 'FINANZAS', 'OTROS')


def estado(monto: float, devuelto: float, perdido_fecha) -> str:
    if perdido_fecha:
        return PERDIDO
    if devuelto >= monto - 0.005:
        return PAGADO
    return PARCIAL if devuelto > 0 else PENDIENTE


def _devoluciones(db) -> dict:
    """prestamo_id -> [devolución] con monto positivo."""
    out = {}
    for r in db.execute("""
        SELECT d.prestamo_id, m.id AS movimiento_id, m.fecha, m.descripcion, ABS(m.monto) AS monto
        FROM est_prestamo_devoluciones d
        JOIN est_movimientos m ON m.id = d.movimiento_id
        ORDER BY m.fecha
    """).fetchall():
        out.setdefault(r['prestamo_id'], []).append({
            'movimiento_id': r['movimiento_id'], 'fecha': r['fecha'],
            'descripcion': r['descripcion'], 'monto': round(float(r['monto']), 2),
        })
    return out


def listar(db) -> list[dict]:
    devs = _devoluciones(db)
    rows = db.execute("""
        SELECT p.*, m.descripcion AS mov_descripcion
        FROM est_prestamos p
        LEFT JOIN est_movimientos m ON m.id = p.movimiento_id
        WHERE p.direccion = 'OTORGADO'
        ORDER BY p.fecha DESC, p.id DESC
    """).fetchall()
    out = []
    for r in rows:
        monto = round(abs(float(r['monto'])), 2)
        d = devs.get(r['id'], [])
        devuelto = round(sum(x['monto'] for x in d), 2)
        pendiente = round(max(monto - devuelto, 0), 2)
        out.append({
            'id': r['id'], 'persona': r['contraparte'], 'fecha': r['fecha'],
            'monto': monto, 'devuelto': devuelto, 'pendiente': pendiente,
            'estado': estado(monto, devuelto, r['perdido_fecha']),
            'perdido_fecha': r['perdido_fecha'], 'notas': r['notas'] or '',
            'movimiento_id': r['movimiento_id'], 'descripcion': r['mov_descripcion'] or '',
            'devoluciones': d,
        })
    return out


def resumen(db) -> dict:
    """Total por cobrar y detalle por persona. Los perdidos no suman al
    pendiente (ya no se espera cobrarlos) pero se siguen listando."""
    prestamos = listar(db)
    personas = {}
    for p in prestamos:
        g = personas.setdefault(p['persona'], {'persona': p['persona'], 'prestado': 0.0,
                                               'devuelto': 0.0, 'pendiente': 0.0, 'prestamos': []})
        g['prestado'] += p['monto']
        g['devuelto'] += p['devuelto']
        if p['estado'] != PERDIDO:
            g['pendiente'] += p['pendiente']
        g['prestamos'].append(p)
    grupos = sorted(personas.values(), key=lambda g: (-g['pendiente'], g['persona'].lower()))
    for g in grupos:
        for k in ('prestado', 'devuelto', 'pendiente'):
            g[k] = round(g[k], 2)
    return {
        'total_pendiente': round(sum(g['pendiente'] for g in grupos), 2),
        'total_perdido': round(sum(p['pendiente'] for p in prestamos if p['estado'] == PERDIDO), 2),
        'personas': grupos,
    }


def perdidos_en_rango(db, desde: str, hasta: str) -> float:
    """Pendiente de los préstamos marcados como perdidos en [desde, hasta):
    es el gasto que la Radiografía suma a Familia y regalos ese mes."""
    return round(sum(p['pendiente'] for p in listar(db)
                     if p['perdido_fecha'] and desde <= p['perdido_fecha'][:10] < hasta), 2)


def candidatos(db) -> dict:
    """Movimientos para crear préstamos (gastos PRESTAMOS sin préstamo) y para
    ligar como devolución (ingresos no ligados), más las personas ya usadas."""
    nuevos = db.execute("""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, banco FROM est_movimientos
        WHERE categoria = 'PRESTAMOS' AND tipo = 'GASTO'
          AND id NOT IN (SELECT movimiento_id FROM est_prestamos WHERE movimiento_id IS NOT NULL)
        ORDER BY fecha DESC
    """).fetchall()
    ph = ','.join('?' * len(_CATS_DEVOLUCION))
    devs = db.execute(f"""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, banco, categoria FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph})
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY CASE WHEN categoria = 'PRESTAMOS' THEN 0 ELSE 1 END, fecha DESC
        LIMIT 200
    """, _CATS_DEVOLUCION).fetchall()
    personas = [r['contraparte'] for r in db.execute(
        "SELECT DISTINCT contraparte FROM est_prestamos ORDER BY contraparte COLLATE NOCASE")]
    return {'prestamos': [dict(r) for r in nuevos], 'devoluciones': [dict(r) for r in devs],
            'personas': personas}


def duplicados(db) -> list[dict]:
    """Posibles duplicados entre movimientos de préstamo: mismo día y mismo
    monto. Solo lectura: el usuario confirma y borra desde Movimientos."""
    grupos = db.execute("""
        SELECT fecha, ABS(monto) AS monto, COUNT(*) AS n FROM est_movimientos
        WHERE categoria = 'PRESTAMOS' OR tipo IN ('PRESTAMO', 'COBRO_PRESTAMO')
        GROUP BY fecha, ABS(monto) HAVING COUNT(*) > 1
        ORDER BY fecha DESC
    """).fetchall()
    out = []
    for g in grupos:
        movs = db.execute("""
            SELECT id, fecha, descripcion, monto, tipo, categoria, banco FROM est_movimientos
            WHERE fecha = ? AND ABS(monto) = ?
              AND (categoria = 'PRESTAMOS' OR tipo IN ('PRESTAMO', 'COBRO_PRESTAMO'))
            ORDER BY id
        """, (g['fecha'], g['monto'])).fetchall()
        out.append({'fecha': g['fecha'], 'monto': round(float(g['monto']), 2),
                    'movimientos': [dict(m) for m in movs]})
    return out


def ahora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def reafirmar_categorias(db) -> int:
    """Los movimientos ligados a un préstamo (el que lo originó y sus
    devoluciones) deben seguir siendo PRESTAMOS aunque una regla de keyword
    («Aplicar reglas» o un import) les ponga otra categoría; si no, volverían
    a contar como gasto o ingreso."""
    n = db.execute("""
        UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='Prestado'
        WHERE id IN (SELECT movimiento_id FROM est_prestamos WHERE movimiento_id IS NOT NULL)
          AND categoria != 'PRESTAMOS'
    """).rowcount
    n += db.execute("""
        UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria=''
        WHERE id IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
          AND categoria != 'PRESTAMOS'
    """).rowcount
    return n
