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
# «… A 20 MSI», «… A 03 MSI», «… A 03 MESES S/I»: la compra completa, no una
# mensualidad («AMAZON MX A MESES» sin número sí es mensualidad).
_COMPRA_RE = re.compile(r"^(.*?)\s+A\s+(\d{1,2})\s+(?:MSI|MESES)\b", re.IGNORECASE)
_PREFIJO = 12   # caracteres del comercio para ligar compra y mensualidades


# Compras que el banco pasó a meses por error y el usuario pagó como un gasto
# normal (fecha, texto, monto) -> (categoria, subcategoria): cuentan
# completas ese día y no entran a la conciliación.
NO_SON_MSI = {
    ('2025-03-15', 'POINTMP ARELLANO', 22.0): ('SUPER', 'Conveniencia'),   # «se confundieron… a 3 meses»
}


# La línea «… A NN MSI» que en realidad fue la 1ª mensualidad (el usuario:
# «04/10 fue la primera mensualidad»): cuenta como gasto y como mensualidad 1
# de una compra de cuota × NN.
PRIMERA_MENSUALIDAD = {
    ('2025-10-04', 'CRISTAL VILLAHERMOSA', 1037.5),
}

# Mensualidades de compras que el usuario pagó por alguien más y le fueron
# devolviendo (texto, cuota, desde, hasta) -> PRESTAMOS, fuera de su gasto.
MENSUALIDADES_PRESTADAS = (
    # Viva Aerobus A 09 (2) $11,895.45 del 20/02/2024: «fue para mi familia y me lo fueron pagando»
    ('VIVA AEROBUS', 1322.0, '2024-02-01', '2024-12-31'),
)

# Categoría de las mensualidades de compras que el usuario identificó
# (texto, cuota, plazo) -> (categoria, subcategoria). El keyword del comercio
# las mandaba a otro lado (Chedraui -> SUPER).
CATEGORIA_MENSUALIDADES = (
    ('CHEDRAUI TDA EN LINEA', 569.0, 13, 'VIVIENDA', 'Artículos del hogar'),   # refri
    ('OFFICE DEPOT INTERNET', 917.0, 12, 'TECH/DIGITAL', 'Deudas MSI'),       # laptop
    ('MACSTORE', 1167.0, 18, 'TECH/DIGITAL', 'Deudas MSI'),                   # iPhone
    ('MACSTORE', 211.0, 12, 'TECH/DIGITAL', 'Deudas MSI'),
)


def _coincide(r, fecha, texto, monto):
    return ((r['fecha'] or '')[:10] == fecha and texto in (r['descripcion'] or '').upper()
            and abs(abs(r['monto'] or 0) - monto) < 0.005)


def _excepcion(r):
    for (fecha, texto, monto), dest in NO_SON_MSI.items():
        if _coincide(r, fecha, texto, monto):
            return dest
    return None


def _es_primera(r) -> bool:
    return any(_coincide(r, *k) for k in PRIMERA_MENSUALIDAD)


def _categoria_de_mensualidades(db, r):
    """Para una línea que fue la 1ª mensualidad: la categoría de sus hermanas."""
    comercio = _COMPRA_RE.match(r['descripcion']).group(1).strip().upper()[:_PREFIJO]
    h = db.execute("""
        SELECT categoria, subcategoria, COUNT(*) n FROM est_movimientos
        WHERE id != ? AND UPPER(descripcion) LIKE ? AND tipo='GASTO'
          AND categoria NOT IN ('FINANZAS', 'OTROS') GROUP BY 1, 2 ORDER BY n DESC LIMIT 1
    """, (r['id'], f"%{comercio}%")).fetchone()
    if h:
        return h['categoria'], h['subcategoria'] or ''
    if r['categoria'] == 'FINANZAS' and r['subcategoria'] == SUBCAT:
        return 'OTROS', ''
    return r['categoria'], r['subcategoria'] or ''


def _reafirmar_mensualidades(db) -> int:
    n = 0
    for texto, cuota, desde, hasta in MENSUALIDADES_PRESTADAS:
        n += db.execute("""
            UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='Prestado'
            WHERE UPPER(descripcion) LIKE ? AND ABS(ABS(monto) - ?) <= 1 AND substr(fecha,1,10) BETWEEN ? AND ?
              AND tipo='GASTO' AND COALESCE(subcategoria,'') != ? AND categoria != 'PRESTAMOS'
        """, (f"%{texto}%", cuota, desde, hasta, SUBCAT)).rowcount
    for texto, cuota, plazo, cat, sub in CATEGORIA_MENSUALIDADES:
        n += db.execute("""
            UPDATE est_movimientos SET categoria=?, subcategoria=?
            WHERE UPPER(descripcion) LIKE ? AND ABS(ABS(monto) - ?) <= 1 AND parcialidad_total=?
              AND tipo='GASTO' AND (categoria != ? OR COALESCE(subcategoria,'') != ?)
        """, (cat, sub, f"%{texto}%", cuota, plazo, cat, sub)).rowcount
    return n


def marcar_compras(db) -> int:
    """Compra inicial a MSI -> FINANZAS/Compra a meses (fuera del gasto),
    salvo las de NO_SON_MSI (gasto normal) y PRIMERA_MENSUALIDAD (gasto, es
    la mensualidad 1). También reafirma la categoría de las mensualidades
    que el usuario identificó y las que pagó por alguien más."""
    rows = db.execute("""
        SELECT id, fecha, descripcion, monto, categoria, subcategoria, tipo FROM est_movimientos
        WHERE parcialidad_num IS NULL AND (UPPER(descripcion) LIKE '% MSI%' OR UPPER(descripcion) LIKE '% MESES%')
          AND tipo IN ('GASTO', 'PAGO')
    """).fetchall()
    n = 0
    for r in rows:
        if not _COMPRA_RE.match(r['descripcion'] or ''):
            continue
        if _es_primera(r):
            dest = _categoria_de_mensualidades(db, r)
        else:
            dest = _excepcion(r) or ('FINANZAS', SUBCAT)
        if (r['categoria'], r['subcategoria'] or '', r['tipo']) != (*dest, 'GASTO'):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, tipo='GASTO' WHERE id=?",
                       (*dest, r['id']))
            n += 1
    return n + _reafirmar_mensualidades(db)


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
    compras = [dict(r) for r in db.execute("""
        SELECT id, fecha, descripcion, monto, banco FROM est_movimientos
        WHERE categoria='FINANZAS' AND subcategoria=?
    """, (SUBCAT,)).fetchall()]
    for fecha, texto, monto in PRIMERA_MENSUALIDAD:
        compras += [dict(r) for r in db.execute("""
            SELECT id, fecha, descripcion, monto, banco FROM est_movimientos
            WHERE substr(fecha,1,10)=? AND UPPER(descripcion) LIKE ? AND ABS(ABS(monto) - ?) < 0.005
              AND COALESCE(subcategoria,'') != ?
        """, (fecha, f"%{texto}%", monto, SUBCAT)).fetchall()]
    compras.sort(key=lambda c: (c['fecha'], c['id']))
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
        # Compra devuelta en los días siguientes por el mismo monto (Palacio de
        # Hierro nov 2025: «A 09 MSI $2,345» y al otro día -$2,345): no procedió.
        devuelta = linea >= 0.005 and db.execute("""
            SELECT 1 FROM est_movimientos
            WHERE banco=? AND id != ? AND monto < 0 AND ABS(ABS(monto) - ?) < 0.005
              AND UPPER(descripcion) LIKE ?
              AND julianday(substr(fecha,1,10)) BETWEEN julianday(?) AND julianday(?) + 7
        """, (c['banco'], c['id'], linea, f"%{comercio[:_PREFIJO]}%", c['fecha'][:10], c['fecha'][:10])).fetchone()
        if linea < 0.005 or devuelta:
            # Compra que no procedió (el banco la dejó en $0 o la devolvió;
            # Palacio de Hierro nov 2025: «lo intenté dos veces y no me quiso»).
            out.append({**base, 'total': 0, 'cuota': 0, 'pagadas': 0, 'pagado': 0, 'restante': 0,
                        'meses_sin_mensualidad': [], 'por_venir': 0, 'pagos': [], 'posibles': [],
                        'estado': 'No procedió'})
            continue
        d_compra = c['fecha'][:10]
        inicio = _mes(d_compra) if int(d_compra[8:10]) <= DIA_CORTE else _sumar_meses(_mes(d_compra), 1)
        # Ventana: n meses + 7 de holgura (promociones «paga en enero»: la 1ª
        # mensualidad puede llegar varios meses después de la compra).
        fin = _sumar_meses(inicio, n + _DIFERIDO)
        hasta_mes = f"{fin[0]}-{fin[1]:02d}"

        def _buscar(like):
            return [dict(r) for r in db.execute("""
                SELECT id, substr(fecha,1,10) AS fecha, descripcion, monto, parcialidad_num, parcialidad_total
                FROM est_movimientos
                WHERE banco=? AND id != ? AND substr(fecha,1,10) >= ? AND substr(fecha,1,7) <= ? AND tipo='GASTO'
                  AND COALESCE(subcategoria,'') != ? AND UPPER(descripcion) LIKE ?
                ORDER BY fecha, id
            """, (c['banco'], c['id'], d_compra, hasta_mes, SUBCAT, like)).fetchall() if r['id'] not in usados]

        cand = _buscar(f"%{comercio[:_PREFIJO]}%")
        primera = _es_primera(c)
        if primera:                  # la línea misma es la mensualidad 1
            cand = [{'id': c['id'], 'fecha': d_compra, 'descripcion': c['descripcion'], 'monto': c['monto'],
                     'parcialidad_num': 1, 'parcialidad_total': n}] + cand
        # Las mensualidades pueden llegar con otro nombre («LIVERPOOL» sin la
        # sucursal, otra tienda de la cadena): sin ninguna de la cuota con el
        # nombre completo, se busca por la primera palabra del comercio, pero
        # solo cargos del monto de la cuota.
        palabra = comercio.split()[0] if comercio.split() else ''
        cuota0 = linea / n
        if len(palabra) >= 4 and palabra != comercio[:_PREFIJO] and not any(
                abs(abs(r['monto']) - cuota0) <= max(cuota0 * _TOL, 1.0) for r in cand):
            ids = {r['id'] for r in cand}
            cand += [r for r in _buscar(f"%{palabra}%")
                     if r['id'] not in ids and abs(abs(r['monto']) - cuota0) <= max(cuota0 * _TOL, 1.0)]
            cand.sort(key=lambda r: (r['fecha'], r['id']))
        # ¿La línea trae la cuota en vez del total? (p. ej. «CRISTAL … A 12 MSI
        # $1,037.50» con mensualidades «10 de 12» de $1,038.)
        cuota, total, linea_es_cuota = linea / n, linea, False
        if primera or n > 1 and any(r['parcialidad_total'] == n and r['id'] != c['id']
                                    and abs(abs(r['monto']) - linea) <= linea * _TOL for r in cand):
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
            # Con «k de n» el inicio se deduce de la mensualidad (la «4 de 9» en
            # mayo -> la 1 fue en febrero); sin número, inicio diferido: los
            # meses esperados arrancan en la 1ª mensualidad real.
            con_num = [_sumar_meses(_mes(r['fecha']), -(r['parcialidad_num'] - 1))
                       for r in rs if r.get('parcialidad_num')]
            if con_num:
                ini = min(con_num)
            else:
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
        # Pista para revisar a mano: cargos de CUALQUIER comercio con el monto
        # de la cuota en la ventana (así se ve con qué nombre llegaron).
        misma_cuota = [] if pagos else [dict(r) for r in db.execute("""
            SELECT id, substr(fecha,1,10) AS fecha, descripcion, monto FROM est_movimientos
            WHERE banco=? AND substr(fecha,1,10) >= ? AND substr(fecha,1,7) <= ? AND tipo='GASTO'
              AND ABS(ABS(monto) - ?) <= ? AND COALESCE(subcategoria,'') != ?
            ORDER BY fecha LIMIT 8
        """, (c['banco'], d_compra, hasta_mes, cuota, max(cuota * 0.01, 0.5), SUBCAT)).fetchall()]
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
            'misma_cuota': [{'id': r['id'], 'fecha': r['fecha'], 'descripcion': r['descripcion'],
                             'monto': round(abs(r['monto']), 2)} for r in misma_cuota],
        })
    out.sort(key=lambda x: x['fecha'], reverse=True)

    # Mensualidades sin compra inicial en la base (p. ej. la compra fue antes
    # del primer estado importado). Se agrupan por comercio y plazo, y dentro
    # de eso por mes de inicio (mes de la «k de n» - (k-1)) y cuota: así la
    # última mensualidad, que suele venir unos pesos menos ($287.99 vs $290),
    # no queda como otra compra, y dos compras iguales en meses distintos no
    # se mezclan.
    filas = [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, banco, ABS(monto) AS monto,
               parcialidad_num, parcialidad_total
        FROM est_movimientos
        WHERE compra_msi_id IS NOT NULL AND tipo='GASTO' AND parcialidad_num IS NOT NULL
        ORDER BY fecha, id
    """).fetchall() if r['id'] not in usados]
    grupos = []
    for r in filas:
        ini_r = _sumar_meses(_mes(r['fecha']), -(r['parcialidad_num'] - 1))
        desc = re.sub(r"^\d{1,2}\s+DE\s+\d{1,2}\s+", "", (r['descripcion'] or '').upper())   # «03 DE 06 …»
        clave = (desc[:_PREFIJO], r['banco'], r['parcialidad_total'])
        g = next((g for g in grupos if g['clave'] == clave and abs(_dif_meses(g['ini'], ini_r)) <= 1
                  and r['parcialidad_num'] not in g['nums']
                  and abs(r['monto'] - g['cuota']) <= max(g['cuota'] * _TOL, 1.0)), None)
        if g is None:
            g = {'clave': clave, 'ini': ini_r, 'cuota': r['monto'], 'nums': set(), 'filas': []}
            grupos.append(g)
        g['nums'].add(r['parcialidad_num'])
        g['filas'].append(r)
    for g in grupos:
        rs, n = g['filas'], g['clave'][2] or 0
        nums = sorted(g['nums'])
        cuota = round(max(r['monto'] for r in rs), 2)       # la última puede ser menor
        pagado = round(sum(r['monto'] for r in rs), 2)
        faltan_nums = [k for k in range(min(nums), max(nums) + 1) if k not in nums]
        out.append({
            'id': None, 'fecha': rs[0]['fecha'], 'descripcion': rs[0]['descripcion'], 'banco': rs[0]['banco'],
            'total': round(cuota * n, 2), 'mensualidades': n, 'cuota': cuota,
            'pagadas': len(nums), 'pagado': pagado,
            'restante': 0.0 if max(nums) >= n else round(cuota * (n - max(nums)), 2),
            'mensualidades_vistas': nums, 'mensualidades_faltantes': faltan_nums,
            'repetidas': False,
            'estado': 'Sin compra inicial',
        })
    return out
