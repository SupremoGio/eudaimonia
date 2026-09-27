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
from itertools import combinations
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


DIA_CORTE = 22            # BBVA Crédito corta el 22: compra hasta el 22 -> 1ª mensualidad ese mes
_TOL = 0.05               # la última mensualidad suele variar unos pesos por redondeo
_DIFERIDO = 7             # meses que puede diferirse el inicio («MSI + paga en enero»)


def _dif_meses(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (a[0] - b[0]) * 12 + (a[1] - b[1])


def conciliar(db, hoy: str | None = None) -> list[dict]:
    hoy = hoy or date.today().isoformat()
    mes_hoy = _mes(hoy)
    compras = db.execute("""
        SELECT id, fecha, descripcion, monto, banco FROM est_movimientos
        WHERE categoria='FINANZAS' AND subcategoria=? ORDER BY fecha, id
    """, (SUBCAT,)).fetchall()
    usados = set()
    out = []
    for c in compras:
        m = _COMPRA_RE.match(c['descripcion'] or '')
        if not m:
            continue
        comercio, n = m.group(1).strip().upper(), int(m.group(2))
        linea = abs(c['monto'] or 0)
        base = {'id': c['id'], 'fecha': c['fecha'][:10], 'descripcion': c['descripcion'], 'banco': c['banco'],
                'mensualidades': n}
        if linea < 0.005:
            # Compra que no procedió (el banco la dejó en $0): nada que conciliar.
            out.append({**base, 'total': 0, 'cuota': 0, 'pagadas': 0, 'pagado': 0, 'restante': 0,
                        'meses_sin_mensualidad': [], 'por_venir': 0, 'pagos': [], 'posibles': [],
                        'estado': 'Sin monto'})
            continue
        d_compra = c['fecha'][:10]
        inicio = _mes(d_compra) if int(d_compra[8:10]) <= DIA_CORTE else _sumar_meses(_mes(d_compra), 1)
        # Ventana: n meses + 7 de holgura (promociones «paga en enero»: la 1ª
        # mensualidad puede llegar varios meses después de la compra).
        fin = _sumar_meses(inicio, n + _DIFERIDO)
        cand = [dict(r) for r in db.execute("""
            SELECT id, substr(fecha,1,10) AS fecha, descripcion, monto, parcialidad_num, parcialidad_total
            FROM est_movimientos
            WHERE banco=? AND id != ? AND substr(fecha,1,10) >= ? AND substr(fecha,1,7) <= ? AND tipo='GASTO'
              AND COALESCE(subcategoria,'') != ? AND UPPER(descripcion) LIKE ?
            ORDER BY fecha, id
        """, (c['banco'], c['id'], d_compra, f"{fin[0]}-{fin[1]:02d}", SUBCAT,
              f"%{comercio[:_PREFIJO]}%")).fetchall() if r['id'] not in usados]
        # ¿La línea trae la cuota en vez del total? (p. ej. «CRISTAL … A 12 MSI
        # $1,037.50» con mensualidades «10 de 12» de $1,038.)
        cuota, total, linea_es_cuota = linea / n, linea, False
        if n > 1 and any(r['parcialidad_total'] == n and abs(abs(r['monto']) - linea) <= linea * _TOL for r in cand):
            cuota, total, linea_es_cuota = linea, round(linea * n, 2), True

        def encaja(r):
            if abs(abs(r['monto']) - cuota) > max(cuota * _TOL, 1.0):
                return False
            if r['parcialidad_total'] and r['parcialidad_total'] != n:
                return False
            k = _dif_meses(_mes(r['fecha']), inicio)
            if r['parcialidad_num'] and k <= n:  # la «k de n» cae en el mes que le toca (±1)
                return abs(k - (r['parcialidad_num'] - 1)) <= 1
            return -1 <= k <= n + _DIFERIDO

        # Cada «serie» es un plan: (cuota, filas, mes de inicio). Normalmente
        # una sola serie con la cuota de la compra.
        series = []
        filas_1 = []
        for r in cand:
            if encaja(r) and _mes(r['fecha']) not in {_mes(x['fecha']) for x in filas_1}:
                filas_1.append(r)
        filas_1 = filas_1[:n]
        if len(filas_1) < n:
            # Compra de varios productos, cada uno con su plan (Palacio de
            # Hierro: 6 × $218.17 + 6 × $169.55 = $2,326.32), que pueden
            # empezar en meses distintos («MSI + paga en enero»): 2 o 3 montos
            # que se repiten en el comercio y cuyas cuotas suman la de la compra.
            por_monto = {}
            for r in cand:
                if r['id'] not in {x['id'] for x in filas_1} and abs(r['monto']) < cuota - max(cuota * _TOL, 1.0) \
                        and (not r['parcialidad_total'] or r['parcialidad_total'] == n):
                    por_monto.setdefault(round(abs(r['monto']), 2), []).append(r)
            montos = [mt for mt, rs in por_monto.items() if len(rs) >= 2]
            for tam in (2, 3):
                combo = next((cb for cb in combinations(sorted(montos), tam)
                              if abs(sum(cb) - cuota) <= max(cuota * _TOL, 1.0)), None)
                if combo:
                    for mt in combo:
                        rs, vistos = [], set()
                        for r in por_monto[mt]:
                            if _mes(r['fecha']) not in vistos:
                                rs.append(r)
                                vistos.add(_mes(r['fecha']))
                        series.append((mt, rs[:n]))
                    break
        if not series:
            series = [(cuota, filas_1)]
        pagos = sorted((r for _, rs in series for r in rs), key=lambda r: (r['fecha'], r['id']))
        usados.update(r['id'] for r in pagos)
        pagado = round(sum(abs(r['monto']) for r in pagos), 2)
        faltan, por_venir, completas = set(), 0, True
        for _, rs in series:
            meses_s = sorted({_mes(r['fecha']) for r in rs})
            # Inicio diferido: los meses esperados arrancan en la 1ª mensualidad real.
            ini = meses_s[0] if meses_s and meses_s[0] > inicio else inicio
            esperados = [_sumar_meses(ini, k) for k in range(n)]
            if len(meses_s) < n:
                completas = False
                faltan.update(f"{y}-{mm:02d}" for (y, mm) in esperados if (y, mm) < mes_hoy and (y, mm) not in meses_s)
            por_venir += sum(1 for ym in esperados if ym >= mes_hoy and ym not in meses_s)
        faltan = sorted(faltan)
        pagadas = min(len(rs) for _, rs in series)
        if completas and abs(total - pagado) <= max(1.0, n * 0.5):
            estado = 'Liquidada'
        elif faltan:
            estado = 'Faltan mensualidades'
        elif pagado - total > max(1.0, n * 0.5):
            estado = 'Pagado de más'
        else:
            estado = 'En curso'
        otros = [r for r in cand if r['id'] not in usados][:8]
        out.append({**base,
            'total': round(total, 2), 'cuota': round(cuota, 2), 'linea_es_cuota': linea_es_cuota,
            'pagadas': pagadas, 'pagado': pagado,
            'planes': [{'cuota': mt, 'mensualidades': len(rs)} for mt, rs in series] if len(series) > 1 else [], 'restante': round(max(total - pagado, 0), 2),
            'meses_sin_mensualidad': faltan, 'por_venir': por_venir, 'estado': estado,
            'pagos': [{'id': r['id'], 'fecha': r['fecha'], 'monto': round(abs(r['monto']), 2),
                       'parcialidad': r['parcialidad_num']} for r in pagos],
            # Cargos del mismo comercio en la ventana que NO se ligaron (otro
            # monto u otro plazo): para revisar a mano si falta algo.
            'posibles': [{'id': r['id'], 'fecha': r['fecha'], 'descripcion': r['descripcion'],
                          'monto': round(abs(r['monto']), 2), 'parcialidad': r['parcialidad_num'],
                          'de': r['parcialidad_total']} for r in otros],
        })
    out.sort(key=lambda x: x['fecha'], reverse=True)

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
