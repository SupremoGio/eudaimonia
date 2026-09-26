"""
Conciliación de Expense por lotes — lógica de la pestaña «Expense» de
Estados de cuenta (routes.py).

El usuario sube varias facturas de gastos de trabajo juntas (un lote) y la
empresa le paga un depósito, o varios, por todo el lote. Modelo:
  - est_expense_lotes: el lote (nombre, notas).
  - est_expense_lote_gastos: gastos EXPENSE del lote (cada gasto, a lo más
    en un lote). Incluye los «PAGO CUENTA DE TERCERO» (lo que se le pasa al
    compañero que pagó una factura del lote).
  - est_expense_lote_depositos: depósitos de la empresa ligados al lote.
    Quedan como FINANZAS/Reembolsable, así que no cuentan como ingreso.

El estado del lote se calcula (Pendiente / Reembolsado parcial /
Reembolsado) y se refleja en estatus_reembolso de sus gastos (los
«Pagado a compañero» conservan su estatus TERCERO).
"""
from datetime import datetime

PENDIENTE, PARCIAL, REEMBOLSADO, VACIO = 'Pendiente', 'Reembolsado parcial', 'Reembolsado', 'Sin gastos'
ESTATUS_TERCERO = 'TERCERO'
# Redondeos del depósito vs. la suma de facturas: hasta $1 de diferencia se
# da por reembolsado completo.
TOLERANCIA = 1.0
# Ingresos que se ofrecen como depósito del lote: los ya marcados como
# reembolso primero, luego transferencias recibidas / sin clasificar.
_CATS_DEPOSITO = ('FINANZAS', 'OTROS', 'EXPENSE')


def ahora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def estado(total: float, depositado: float) -> str:
    if total <= 0:
        return VACIO
    if depositado >= total - TOLERANCIA:
        return REEMBOLSADO
    return PARCIAL if depositado > 0 else PENDIENTE


def _movs(db, tabla: str) -> dict:
    """lote_id -> [movimiento] de la tabla de ligas dada."""
    out = {}
    for r in db.execute(f"""
        SELECT l.lote_id, m.id, m.fecha, m.descripcion, ABS(m.monto) AS monto, m.banco,
               m.estatus_reembolso, m.fecha_reembolso
        FROM {tabla} l JOIN est_movimientos m ON m.id = l.movimiento_id
        ORDER BY m.fecha DESC, m.id DESC
    """).fetchall():
        d = dict(r)
        d['monto'] = round(float(d['monto']), 2)
        out.setdefault(d.pop('lote_id'), []).append(d)
    return out


def listar(db) -> list[dict]:
    gastos, deps = _movs(db, 'est_expense_lote_gastos'), _movs(db, 'est_expense_lote_depositos')
    out = []
    for r in db.execute("SELECT * FROM est_expense_lotes ORDER BY id DESC").fetchall():
        g, d = gastos.get(r['id'], []), deps.get(r['id'], [])
        total = round(sum(x['monto'] for x in g), 2)
        depositado = round(sum(x['monto'] for x in d), 2)
        fechas = sorted(x['fecha'] for x in g)
        out.append({
            'id': r['id'], 'nombre': r['nombre'], 'notas': r['notas'] or '',
            'desde': fechas[0] if fechas else None, 'hasta': fechas[-1] if fechas else None,
            'gastos': g, 'depositos': d,
            'total': total, 'depositado': depositado,
            'pendiente': round(max(total - depositado, 0), 2),
            'diferencia': round(depositado - total, 2),
            'terceros': round(sum(x['monto'] for x in g if x['estatus_reembolso'] == ESTATUS_TERCERO), 2),
            'estado': estado(total, depositado),
        })
    # Abiertos primero, luego por la factura más reciente.
    orden = {PENDIENTE: 0, PARCIAL: 0, VACIO: 1, REEMBOLSADO: 2}
    out.sort(key=lambda l: (orden[l['estado']], -(int((l['hasta'] or '0000-00-00').replace('-', '')))))
    return out


def sin_lote(db) -> list[dict]:
    rows = db.execute("""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, banco, estatus_reembolso FROM est_movimientos
        WHERE categoria = 'EXPENSE' AND tipo = 'GASTO'
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_gastos)
        ORDER BY fecha DESC, id DESC
    """).fetchall()
    return [{**dict(r), 'monto': round(float(r['monto']), 2)} for r in rows]


def resumen(db) -> dict:
    lotes = listar(db)
    sueltos = sin_lote(db)
    pendientes_sueltos = [g for g in sueltos if (g['estatus_reembolso'] or 'PENDIENTE') == 'PENDIENTE']
    year = datetime.now().strftime('%Y')
    return {
        'por_cobrar': round(sum(l['pendiente'] for l in lotes)
                            + sum(g['monto'] for g in pendientes_sueltos), 2),
        'lotes_abiertos': sum(1 for l in lotes if l['estado'] in (PENDIENTE, PARCIAL)),
        'reembolsado_anio': round(sum(d['monto'] for l in lotes for d in l['depositos']
                                      if (d['fecha'] or '')[:4] == year), 2),
        'lotes': lotes,
        'sin_lote': sueltos,
    }


def candidatos(db) -> dict:
    ph = ','.join('?' * len(_CATS_DEPOSITO))
    deps = db.execute(f"""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, banco, categoria, subcategoria FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph})
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY CASE WHEN subcategoria = 'Reembolsable' THEN 0 ELSE 1 END, fecha DESC
        LIMIT 200
    """, _CATS_DEPOSITO).fetchall()
    return {'gastos': sin_lote(db), 'depositos': [{**dict(r), 'monto': round(float(r['monto']), 2)} for r in deps]}


def sincronizar(db, lote_id: int) -> None:
    """Refleja el estado del lote en estatus_reembolso/fecha_reembolso de sus
    gastos (los TERCERO se quedan como están)."""
    lote = next((l for l in listar(db) if l['id'] == lote_id), None)
    if not lote or not lote['gastos']:
        return
    ok = lote['estado'] == REEMBOLSADO
    fecha = max((d['fecha'] for d in lote['depositos']), default=None) if ok else None
    ids = [g['id'] for g in lote['gastos']]
    ph = ','.join('?' * len(ids))
    db.execute(f"""
        UPDATE est_movimientos SET estatus_reembolso=?, fecha_reembolso=?
        WHERE id IN ({ph}) AND COALESCE(estatus_reembolso, '') != ?
    """, ('PAGADO' if ok else 'PENDIENTE', fecha, *ids, ESTATUS_TERCERO))


def reafirmar_categorias(db) -> int:
    """Una regla de keyword no debe sacar a un gasto del lote de EXPENSE ni
    volver ingreso a un depósito ya ligado."""
    n = db.execute("""
        UPDATE est_movimientos SET categoria='EXPENSE', subcategoria=''
        WHERE id IN (SELECT movimiento_id FROM est_expense_lote_gastos) AND categoria != 'EXPENSE'
    """).rowcount
    n += db.execute("""
        UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
        WHERE id IN (SELECT movimiento_id FROM est_expense_lote_depositos)
          AND (categoria != 'FINANZAS' OR subcategoria != 'Reembolsable')
    """).rowcount
    return n


def filas_csv(db) -> list[list]:
    filas = []
    for l in listar(db):
        for g in l['gastos']:
            filas.append([l['nombre'], l['estado'], 'Factura', g['fecha'], g['descripcion'], g['monto'],
                          'Pagado a compañero' if g['estatus_reembolso'] == ESTATUS_TERCERO else ''])
        for d in l['depositos']:
            filas.append([l['nombre'], l['estado'], 'Depósito', d['fecha'], d['descripcion'], d['monto'], ''])
    for g in sin_lote(db):
        filas.append(['', 'Sin lote', 'Factura', g['fecha'], g['descripcion'], g['monto'], g['estatus_reembolso'] or ''])
    return filas
