"""
Abonos sin conciliar: dinero que te entró (tipo INGRESO) que no cuenta como
ingreso -- FINANZAS (transferencias, depósitos, reembolsables), PRESTAMOS o
EXPENSE -- y que todavía no está ligado a nada: ni como devolución de un
préstamo (est_prestamo_devoluciones) ni como depósito de un lote de Expense
(est_expense_lote_depositos). El usuario (2026-09-28): «¿cómo veo los que no
están conciliados en Expense ni en Préstamos? debe haber aún algunos».

Solo lectura: para conciliarlos se ligan en Por cobrar / Expense o se les
cambia la categoría (p. ej. a ingreso real).

Cada abono trae una «pista» de qué es probablemente (el usuario, 2026-09-29:
«es mucho dinero que no sé dónde va… sé que mucho son regresos de préstamos,
expenses y así»), en este orden:
  - expense: el algoritmo de Expense (expense_lotes.sugerencias) lo cuadra
    con facturas EXPENSE sin lote.
  - prestamo: un préstamo con pendiente cuyo nombre aparece en la
    descripción, o cuyo pendiente es exactamente el monto (después de prestar).
  - propia: la misma cantidad salió de otra de tus cuentas ±3 días como
    transferencia, pago o inversión (no un gasto normal): es dinero tuyo que
    se movió entre cuentas, no entró de fuera.
  - sin pista.
"""
import re
from datetime import date, timedelta

CATEGORIAS = ('FINANZAS', 'PRESTAMOS', 'EXPENSE')


def sin_conciliar(db, anio: str | None = None) -> dict:
    ph = ','.join('?' * len(CATEGORIAS))
    params = list(CATEGORIAS)
    filtro_anio = ''
    if anio:
        filtro_anio = "AND substr(fecha, 1, 4) = ?"
        params.append(str(anio))
    rows = [dict(r) for r in db.execute(f"""
        SELECT * FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph}) {filtro_anio}
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
        ORDER BY fecha DESC, id DESC
    """, params).fetchall()]
    grupos = {}
    for r in rows:
        k = r['categoria'] if r['categoria'] != 'FINANZAS' else (r['subcategoria'] or 'Sin subcategoría')
        g = grupos.setdefault(k, {'grupo': k, 'n': 0, 'total': 0.0})
        g['n'] += 1
        g['total'] += abs(r['monto'] or 0)
    anios = [r[0] for r in db.execute(f"""
        SELECT DISTINCT substr(fecha, 1, 4) FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph}) ORDER BY 1 DESC
    """, list(CATEGORIAS)).fetchall()]
    _pistas(db, rows)
    por_pista = {}
    for r in rows:
        t = r['pista']['tipo'] if r['pista'] else 'ninguna'
        g = por_pista.setdefault(t, {'tipo': t, 'n': 0, 'total': 0.0})
        g['n'] += 1
        g['total'] += abs(r['monto'] or 0)
    return {
        'movimientos': rows,
        'por_pista': sorted(({**g, 'total': round(g['total'], 2)} for g in por_pista.values()),
                            key=lambda g: -g['total']),
        'total': round(sum(abs(r['monto'] or 0) for r in rows), 2),
        'grupos': sorted(({**g, 'total': round(g['total'], 2)} for g in grupos.values()),
                         key=lambda g: -g['total']),
        'anios': anios,
    }


def filas_csv(db, anio: str | None = None) -> list[list]:
    return [[r['id'], (r['fecha'] or '')[:10], r['descripcion'], abs(r['monto'] or 0), r['banco'],
             r['categoria'], r['subcategoria'] or '', r['pista']['texto'] if r['pista'] else '', '']
            for r in sin_conciliar(db, anio)['movimientos']]


PROPIA_DIAS = 3
_PALABRAS_COMUNES = {'PAGO', 'CUENTA', 'TERCERO', 'BNET', 'SPEI', 'RECIBIDO', 'ENVIADO', 'DEPOSITO',
                     'TRANSF', 'TRANSFERENCIA', 'PARA', 'DEL', 'LOS', 'LAS', 'GIO', 'GIOVANY', 'ALBERTO',
                     'SANCHEZ', 'BBVA', 'MEXICO'}


def _palabras(nombre: str) -> set:
    return {w for w in re.findall(r'[A-ZÑ]{3,}', (nombre or '').upper()) if w not in _PALABRAS_COMUNES}


def _pistas(db, rows) -> None:
    """Pone r['pista'] = {'tipo', 'texto'} o None en cada abono (ver docstring del módulo)."""
    try:
        from . import expense_lotes
        exp = {}
        for sug in expense_lotes.sugerencias(db):
            for d in sug['depositos']:
                exp[d['id']] = (f"Expense: cuadra con {len(sug['facturas'])} factura(s) por "
                                f"${sug['total']:,.2f} (confianza {sug['confianza']})")
    except Exception:
        exp = {}
    try:
        from . import prestamos
        abiertos = [p for p in prestamos.listar(db) if p['pendiente'] > 0 and not p['perdido_fecha']]
    except Exception:
        abiertos = []
    for r in rows:
        r['pista'] = None
        monto, fecha = abs(r['monto'] or 0), (r['fecha'] or '')[:10]
        if r['id'] in exp:
            r['pista'] = {'tipo': 'expense', 'texto': exp[r['id']]}
            continue
        desc = _palabras(r['descripcion'])
        p = next((p for p in abiertos if (p['fecha'] or '')[:10] <= fecha and _palabras(p['persona']) & desc), None) \
            or next((p for p in abiertos if (p['fecha'] or '')[:10] <= fecha and abs(p['pendiente'] - monto) < 0.01), None)
        if p:
            r['pista'] = {'tipo': 'prestamo', 'texto': f"Préstamo a {p['persona']} del {p['fecha'][:10]} "
                                                        f"(pendiente ${p['pendiente']:,.2f})"}
            continue
        if not fecha:
            continue
        d = date.fromisoformat(fecha)
        par = db.execute("""
            SELECT fecha, banco, descripcion FROM est_movimientos
            WHERE tipo IN ('GASTO', 'PAGO') AND banco != ? AND ABS(ABS(monto) - ?) < 0.01
              AND (tipo = 'PAGO' OR categoria IN ('FINANZAS', 'INVERSION', 'PAGO'))
              AND substr(fecha,1,10) BETWEEN ? AND ?
            ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?)) LIMIT 1
        """, (r['banco'], monto, (d - timedelta(days=PROPIA_DIAS)).isoformat(),
              (d + timedelta(days=PROPIA_DIAS)).isoformat(), fecha)).fetchone()
        if par:
            r['pista'] = {'tipo': 'propia', 'texto': f"Entre tus cuentas: salió de {par['banco']} el "
                                                     f"{par['fecha'][:10]} ({par['descripcion']})"}
