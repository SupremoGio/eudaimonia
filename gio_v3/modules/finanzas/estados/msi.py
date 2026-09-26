"""
Compras a meses sin intereses (MSI): se cuentan las MENSUALIDADES, no la
compra inicial (pedido del usuario, 2026-09-26).

El banco muestra la compra completa una vez («WALMART VENTA EN LIN3 A 20 MSI
$10,169», a veces con signo negativo) y luego cada mensualidad («01 DE 20
WALMART…» o solo «WALMART VENTA EN LIN3 $509»). Contar ambas duplicaba el
gasto (o, con el signo negativo, restaba la compra entera de un mes). La
línea inicial pasa a FINANZAS/«Compra a meses»: sigue visible en
Movimientos pero fuera de gasto e ingreso; el gasto lo llevan las
mensualidades, mes a mes, igual que el pago a la tarjeta.

conciliar() arma, por compra, lo que se esperaba (N mensualidades, el total)
contra lo que de verdad aparece en la base: cuánto va pagado, qué meses no
tienen mensualidad registrada y si la suma cuadra con el total.
"""
import re
from datetime import date

SUBCAT = 'Compra a meses'
# «… A 20 MSI», «… A 03 MSI»: la compra completa, no una mensualidad
_COMPRA_RE = re.compile(r"^(.*?)\s+A\s+(\d{1,2})\s+MSI\b", re.IGNORECASE)
_PREFIJO = 12   # caracteres del comercio para ligar compra y mensualidades


def marcar_compras(db) -> int:
    """Compra inicial a MSI -> FINANZAS/Compra a meses (fuera del gasto)."""
    rows = db.execute("""
        SELECT id, descripcion, categoria, subcategoria FROM est_movimientos
        WHERE parcialidad_num IS NULL AND UPPER(descripcion) LIKE '% MSI%'
          AND tipo IN ('GASTO', 'PAGO')
    """).fetchall()
    n = 0
    for r in rows:
        if _COMPRA_RE.match(r['descripcion'] or '') and (r['categoria'], r['subcategoria']) != ('FINANZAS', SUBCAT):
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=?, tipo='GASTO' WHERE id=?",
                       (SUBCAT, r['id']))
            n += 1
    return n


def _mes(d: str) -> tuple[int, int]:
    return int(d[:4]), int(d[5:7])


def _sumar_meses(ym: tuple[int, int], k: int) -> tuple[int, int]:
    y, m = ym
    m += k
    return y + (m - 1) // 12, (m - 1) % 12 + 1


def conciliar(db, hoy: str | None = None) -> list[dict]:
    hoy = hoy or date.today().isoformat()
    compras = db.execute("""
        SELECT id, fecha, descripcion, monto, banco FROM est_movimientos
        WHERE categoria='FINANZAS' AND subcategoria=? ORDER BY fecha DESC
    """, (SUBCAT,)).fetchall()
    usados = set()
    out = []
    for c in compras:
        m = _COMPRA_RE.match(c['descripcion'] or '')
        if not m:
            continue
        comercio, n = m.group(1).strip().upper(), int(m.group(2))
        total = abs(c['monto'] or 0)
        cuota = total / n if n else 0
        pref = comercio[:_PREFIJO]
        # Mensualidades: mismo banco, mismo comercio, después de la compra, y
        # o traen «NN de N» o su monto es la cuota (±3 %; la última a veces
        # es menor por redondeo, esa se liga por el «NN de N»).
        cand = db.execute("""
            SELECT id, substr(fecha,1,10) AS fecha, descripcion, monto, parcialidad_num, parcialidad_total
            FROM est_movimientos
            WHERE banco=? AND id != ? AND substr(fecha,1,10) >= ? AND tipo='GASTO'
              AND COALESCE(subcategoria,'') != ?
              AND UPPER(descripcion) LIKE ?
            ORDER BY fecha
        """, (c['banco'], c['id'], c['fecha'][:10], SUBCAT, f"%{pref}%")).fetchall()
        pagos = [r for r in cand if r['id'] not in usados and (
            (r['parcialidad_total'] == n) or (cuota and abs(abs(r['monto']) - cuota) <= cuota * 0.03))]
        pagos = pagos[:n]
        usados.update(r['id'] for r in pagos)
        pagado = round(sum(abs(r['monto']) for r in pagos), 2)
        # Meses esperados: la 1ª mensualidad cae en el corte siguiente a la
        # compra; se buscan en una ventana de N+2 meses.
        inicio = _sumar_meses(_mes(c['fecha']), 1)
        esperados = [_sumar_meses(inicio, k) for k in range(n)]
        con_pago = {_mes(r['fecha']) for r in pagos}
        mes_hoy = _mes(hoy)
        faltan = [f"{y}-{mm:02d}" for (y, mm) in esperados if (y, mm) not in con_pago and (y, mm) < mes_hoy]
        por_venir = sum(1 for ym in esperados if ym >= mes_hoy and ym not in con_pago)
        restante = round(max(total - pagado, 0), 2)
        if len(pagos) >= n and abs(total - pagado) <= max(1.0, n * 0.5):
            estado = 'Liquidada'
        elif faltan:
            estado = 'Faltan mensualidades'
        elif len(pagos) > n or pagado - total > max(1.0, n * 0.5):
            estado = 'Pagado de más'
        else:
            estado = 'En curso'
        out.append({
            'id': c['id'], 'fecha': c['fecha'][:10], 'descripcion': c['descripcion'], 'banco': c['banco'],
            'total': round(total, 2), 'mensualidades': n, 'cuota': round(cuota, 2),
            'pagadas': len(pagos), 'pagado': pagado, 'restante': restante,
            'meses_sin_mensualidad': faltan, 'por_venir': por_venir, 'estado': estado,
            'pagos': [{'id': r['id'], 'fecha': r['fecha'], 'monto': round(abs(r['monto']), 2),
                       'parcialidad': r['parcialidad_num']} for r in pagos],
        })

    # Mensualidades sin compra inicial en la base (p. ej. la compra fue antes
    # del primer estado importado): se agrupan por compra_msi_id.
    sueltas = db.execute("""
        SELECT compra_msi_id, MIN(descripcion) AS descripcion, MIN(banco) AS banco,
               MAX(parcialidad_total) AS n, COUNT(*) AS filas,
               GROUP_CONCAT(parcialidad_num) AS nums, ROUND(SUM(ABS(monto)), 2) AS pagado,
               ROUND(AVG(ABS(monto)), 2) AS cuota, MIN(substr(fecha,1,10)) AS desde, MAX(substr(fecha,1,10)) AS hasta
        FROM est_movimientos
        WHERE compra_msi_id IS NOT NULL AND tipo='GASTO'
        GROUP BY compra_msi_id
    """).fetchall()
    for g in sueltas:
        ids = [r['id'] for r in db.execute("SELECT id FROM est_movimientos WHERE compra_msi_id=?", (g['compra_msi_id'],))]
        if any(i in usados for i in ids):
            continue
        nums = sorted({int(x) for x in (g['nums'] or '').split(',') if x})
        n = g['n'] or 0
        faltan_nums = [k for k in range(min(nums) if nums else 1, (max(nums) if nums else 0) + 1) if k not in nums]
        out.append({
            'id': None, 'fecha': g['desde'], 'descripcion': g['descripcion'], 'banco': g['banco'],
            'total': round((g['cuota'] or 0) * n, 2), 'mensualidades': n, 'cuota': g['cuota'],
            'pagadas': len(nums), 'pagado': g['pagado'], 'restante': round((g['cuota'] or 0) * max(n - max(nums or [0]), 0), 2),
            'mensualidades_vistas': nums, 'mensualidades_faltantes': faltan_nums,
            'repetidas': g['filas'] > len(nums),
            'estado': 'Sin compra inicial',
        })
    return out
