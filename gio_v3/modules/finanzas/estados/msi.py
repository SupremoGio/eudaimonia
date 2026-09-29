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
# Pointmp Arellano $22 (15/03/2025, «se confundieron… a 3 meses») estuvo aquí,
# pero el banco sí la cobró en 3 mensualidades ($8 + $8 + $6): contaba doble.
# Ahora es una compra a meses normal y sus mensualidades van a SUPER/Conveniencia
# (CATEGORIA_MENSUALIDADES).
NO_SON_MSI: dict = {}


# La línea «… A NN MSI» que en realidad fue la 1ª mensualidad: cuenta como
# gasto y como mensualidad 1 de una compra de cuota × NN. Vacío desde que llegó
# el PDF de Cristal (oct 2025): la línea de $1,037.50 del 04/10 que la app
# descargó es la misma compra que el banco imprime como $12,450 ese día (la
# 1ª mensualidad real es la «1 de 12» del 22/10); ver _duplicadas.
PRIMERA_MENSUALIDAD: set = set()

# Mensualidades de compras que el usuario pagó por alguien más y le fueron
# devolviendo (texto, cuota, desde, hasta) -> PRESTAMOS, fuera de su gasto.
MENSUALIDADES_PRESTADAS = (
    # Viva Aerobus A 09 (2) $11,895.45 del 20/02/2024: «fue para mi familia y me lo fueron pagando»
    ('VIVA AEROBUS', 1322.0, '2024-02-01', '2024-12-31'),
    # MacStore A 18 $20,999 del 19/11/2022: «iphone no mío».
    ('MACSTORE', 1167.0, '2022-11-01', '2024-04-30'),
)

# Categoría de las mensualidades de compras que el usuario identificó
# (texto, cuota, plazo) -> (categoria, subcategoria). El keyword del comercio
# las mandaba a otro lado (Chedraui -> SUPER).
CATEGORIA_MENSUALIDADES = (
    ('CHEDRAUI TDA EN LINEA', 569.0, 13, 'VIVIENDA', 'Artículos del hogar'),   # refri
    ('OFFICE DEPOT INTERNET', 917.0, 12, 'TECH/DIGITAL', 'Deudas MSI'),       # laptop
    ('MACSTORE', 211.0, 12, 'TECH/DIGITAL', 'Deudas MSI'),
    ('POINTMP ARELLANO', 7.0, 3, 'SUPER', 'Conveniencia'),                    # $8, $8, $6
    # Comentarios del usuario a las compras iniciales (2026-09-28):
    ('WALMART VENTA EN LIN3', 567.0, 12, 'VIVIENDA', 'Artículos del hogar'),  # cama (abr 2022)
    ('TRAINING INNOVATION', 358.0, 12, 'DEPORTE', 'Gym'),                     # gym (abr 2022)
    ('TRAINING INNOVATION', 359.0, 12, 'DEPORTE', 'Gym'),                     # gym (abr 2023)
    ('MEN S FACTORY', 462.0, 6, 'ROPA', 'Ropa'),                             # ropa (dic 2022)
    ('MERCADO PAGO 1', 234.0, 6, 'VIVIENDA', 'Artículos del hogar'),         # artículo casa (nov 2022)
    ('MERCADO PAGO 1', 156.0, 3, 'VIVIENDA', 'Artículos del hogar'),         # artículo casa (sep 2022)
    # Pedidos de Amazon (ver pedidos_amazon.py):
    ('AMAZON A MESES', 146.0, 15, 'CUIDADO_PERSONAL', 'Higiene'),            # Oral B iO 6 $2,181.77 (jul 2026)
    ('AMAZON A MESES', 480.0, 15, 'TECH/DIGITAL', 'Accesorios'),             # Apple Watch S11 $7,186.75 (may 2026)
    ('AMAZON A MESES', 327.0, 6, 'TECH/DIGITAL', 'Accesorios'),              # RAM Kingston x2 $1,958 (ene 2026)
    ('AMAZON A MESES', 117.0, 6, 'TECH/DIGITAL', 'Accesorios'),              # power bank UGREEN $699 (ene 2026)
    ('AMAZON A MESES', 20.0, 6, 'TECH/DIGITAL', 'Accesorios'),               # cable HDMI $114.89 (ene 2026)
    ('AMAZON A MESES', 14.89, 6, 'TECH/DIGITAL', 'Accesorios'),              # su última mensualidad
    ('AMAZON MX A MESES', 200.0, 15, 'TECH/DIGITAL', 'Accesorios'),          # Bose QuietComfort $2,999 (jul 2025)
    ('AMAZON A MESES', 250.0, 3, 'VIVIENDA', 'Artículos del hogar'),        # Echo Dot $749 (sep 2025)
    ('AMAZON MX A MESES', 290.0, 6, 'VIVIENDA', 'Artículos del hogar'),     # lámpara + Roku + zapatero $1,737.99 (abr 2024)
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
            WHERE UPPER(descripcion) LIKE ? AND ABS(ABS(monto) - ?) <= ? AND parcialidad_total=?
              AND tipo='GASTO' AND (categoria != ? OR COALESCE(subcategoria,'') != ?)
        """, (cat, sub, f"%{texto}%", cuota, max(cuota * _TOL, 1.0), plazo, cat, sub)).rowcount
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


def _k_real(r, inicio: tuple[int, int]):
    """El renglón del banco recorta la «k» de dos dígitos: la «11 de 13» del
    refri Chedraui sale «1 DE 13» (su tabla de MSI sí dice «11 de 13»). Si
    k + 10 cae en el mes que le toca y k no, es k + 10."""
    pn, pt = r.get('parcialidad_num'), r.get('parcialidad_total')
    if not pn or not pt or pn + 10 > pt:
        return pn
    k = _dif_meses(_mes(r['fecha']), inicio) + 1
    return pn + 10 if abs(k - (pn + 10)) < abs(k - pn) else pn


def _rivales(db, compras) -> dict:
    """Por compra: banco, primera palabra del comercio, plazo, mes y cuota
    estimada (la línea / n, o la línea misma si hay mensualidades «k de n» de
    ese monto: la línea traía la cuota)."""
    out = {}
    for c in compras:
        m = _COMPRA_RE.match(c['descripcion'] or '')
        if not m:
            continue
        comercio, n = m.group(1).strip().upper(), int(m.group(2))
        linea = abs(c['monto'] or 0)
        if linea < 0.005:
            continue
        palabra = comercio.split()[0] if comercio.split() else ''
        out[c['id']] = {'id': c['id'], 'banco': c['banco'], 'palabra': palabra, 'n': n,
                        'mes': _mes(c['fecha'][:10]), 'cuota': linea / n, 'linea': linea,
                        'comercio': comercio}
    # Con la cuota «de la línea / n» de todas ya calculada: ¿alguna línea trae
    # la cuota? Solo si hay al menos 2 mensualidades «k de n» de ese monto que
    # no queden más cerca de la cuota de otra compra (Amazon A 06 $114.89 del
    # 24/01/2026 es la compra completa: la «k de 6» de $114 era la última de
    # la de $699 = 5 × $117 + $114).
    for c in compras:
        o = out.get(c['id'])
        if not o:
            continue
        if _es_primera(c):
            o['cuota'] = o['linea']
            continue
        if o['n'] < 2:
            continue
        filas = db.execute("""
            SELECT ABS(monto) AS monto FROM est_movimientos WHERE banco=? AND id != ? AND parcialidad_total=?
              AND ABS(ABS(monto) - ?) <= ? AND UPPER(descripcion) LIKE ?
        """, (c['banco'], c['id'], o['n'], o['linea'], o['linea'] * _TOL, f"%{o['comercio'][:_PREFIJO]}%")).fetchall()
        propias = [f for f in filas if not any(
            x['id'] != o['id'] and x['banco'] == o['banco'] and x['palabra'] == o['palabra'] and x['n'] == o['n']
            and abs(f['monto'] - x['cuota']) + 0.005 < abs(f['monto'] - o['linea']) for x in out.values())]
        if len(propias) >= 2:
            o['cuota'] = o['linea']
            o['es_cuota'] = True
    return out


def _duplicadas(compras) -> set:
    """La misma compra descargada dos veces: la app la trae con la cuota
    («CRISTAL VILLAHERMOSA A 12 MSI $1,037.50») y el PDF con el total ($12,450)
    el mismo día. La de la cuota sobra: no es otra compra ni una mensualidad."""
    info = []
    for c in compras:
        m = _COMPRA_RE.match(c['descripcion'] or '')
        if m and abs(c['monto'] or 0) >= 0.005:
            info.append((c, m.group(1).strip().upper()[:_PREFIJO], int(m.group(2)), abs(c['monto'])))
    dup = set()
    for c, com, n, linea in info:
        for o, com_o, n_o, linea_o in info:
            if o['id'] != c['id'] and o['banco'] == c['banco'] and o['fecha'][:10] == c['fecha'][:10] \
                    and com_o == com and n_o == n and n > 1 and abs(linea_o / n - linea) <= 0.02:   # la app da la cuota exacta al centavo
                dup.add(c['id'])
    return dup


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
    duplicadas = _duplicadas(compras)
    compras = sorted((c for c in compras if c['id'] not in duplicadas), key=lambda c: (c['fecha'], c['id']))
    rivales = _rivales(db, compras)
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
        for r in cand:
            r['parcialidad_num'] = _k_real(r, inicio)
        primera = _es_primera(c)
        if primera:                  # la línea misma es la mensualidad 1
            cand = [{'id': c['id'], 'fecha': d_compra, 'descripcion': c['descripcion'], 'monto': c['monto'],
                     'parcialidad_num': 1, 'parcialidad_total': n}] + cand
        # Las mensualidades pueden llegar con otro nombre («LIVERPOOL» sin la
        # sucursal, «AMAZON A MESES» / «AMAZON MX A MESES»): también se buscan
        # por la primera palabra del comercio, solo cargos del monto de la cuota.
        palabra = comercio.split()[0] if comercio.split() else ''
        cuota0 = rivales.get(c['id'], {}).get('cuota') or linea / n
        if len(palabra) >= 4 and palabra != comercio[:_PREFIJO]:
            ids = {r['id'] for r in cand}
            extra = [r for r in _buscar(f"%{palabra}%")
                     if r['id'] not in ids and abs(abs(r['monto']) - cuota0) <= max(cuota0 * _TOL, 1.0)]
            for r in extra:
                r['parcialidad_num'] = _k_real(r, inicio)
            cand += extra
            cand.sort(key=lambda r: (r['fecha'], r['id']))
        # ¿La línea trae la cuota en vez del total? (p. ej. «CRISTAL … A 12 MSI
        # $1,037.50» con mensualidades «10 de 12» de $1,038.)
        cuota, total, linea_es_cuota = linea / n, linea, False
        if primera or rivales.get(c['id'], {}).get('es_cuota'):
            cuota, total, linea_es_cuota = linea, round(linea * n, 2), True

        def encaja(r):
            if abs(abs(r['monto']) - cuota) > max(cuota * _TOL, 1.0):
                return False
            # Varias compras del mismo comercio y plazo en fechas cercanas (3
            # Amazon A 06 el 24/01/2026 de ~$114.89, ~$116.50 y ~$326.33): la
            # mensualidad va a la de cuota más parecida.
            dif = abs(abs(r['monto']) - cuota)
            for o in rivales.values():
                if o['id'] != c['id'] and o['banco'] == c['banco'] and o['palabra'] == palabra and o['n'] == n \
                        and abs(_dif_meses(o['mes'], _mes(d_compra))) <= 1 \
                        and abs(abs(r['monto']) - o['cuota']) + 0.005 < dif:
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
        # Una por mes, la mejor: con «k de n» antes que sin número, y luego la
        # de monto más parecido (Amazon A 03 $749: la 3ª es la «3 de 3» de
        # $249 del 22/12, no un cargo suelto de $259 del 01/12).
        por_mes = {}
        for r in cand:
            if encaja(r):
                clave = (0 if r['parcialidad_num'] else 1, abs(abs(r['monto']) - cuota), r['fecha'], r['id'])
                ym = _mes(r['fecha'])
                if ym not in por_mes or clave < por_mes[ym][0]:
                    por_mes[ym] = (clave, r)
        filas_1 = [r for _, (_, r) in sorted(por_mes.items())][:n]
        # La última mensualidad es lo que resta y puede quedar lejos de la
        # cuota en compras chicas (Amazon A 06 $114.89 = 5 × $20 + $14.89).
        if len(filas_1) == n - 1 and filas_1:
            resto = total - sum(abs(r['monto']) for r in filas_1)
            ult = _mes(filas_1[-1]['fecha'])
            fin_r = next((r for r in cand if r['id'] not in {x['id'] for x in filas_1}
                          and _dif_meses(_mes(r['fecha']), ult) >= 1 and abs(abs(r['monto']) - resto) <= 1.0
                          and abs(r['monto']) < cuota and (not r['parcialidad_total'] or r['parcialidad_total'] == n)), None)
            if fin_r:
                filas_1.append(fin_r)
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
