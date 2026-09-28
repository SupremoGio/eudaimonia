"""
Abonos sin conciliar: dinero que te entró (tipo INGRESO) que no cuenta como
ingreso -- FINANZAS (transferencias, depósitos, reembolsables), PRESTAMOS o
EXPENSE -- y que todavía no está ligado a nada: ni como devolución de un
préstamo (est_prestamo_devoluciones) ni como depósito de un lote de Expense
(est_expense_lote_depositos). El usuario (2026-09-28): «¿cómo veo los que no
están conciliados en Expense ni en Préstamos? debe haber aún algunos».

Solo lectura: para conciliarlos se ligan en Por cobrar / Expense o se les
cambia la categoría (p. ej. a ingreso real).
"""

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
    return {
        'movimientos': rows,
        'total': round(sum(abs(r['monto'] or 0) for r in rows), 2),
        'grupos': sorted(({**g, 'total': round(g['total'], 2)} for g in grupos.values()),
                         key=lambda g: -g['total']),
        'anios': anios,
    }


def filas_csv(db, anio: str | None = None) -> list[list]:
    return [[r['id'], (r['fecha'] or '')[:10], r['descripcion'], abs(r['monto'] or 0), r['banco'],
             r['categoria'], r['subcategoria'] or '', '']
            for r in sin_conciliar(db, anio)['movimientos']]
