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
  - gasto: si llegó en las fechas de un viaje (3 días antes a 30 después),
    tu parte de un gasto de ese viaje o, si ninguno cuadra, del viaje en
    general (VIAJES/Otros); al conciliar queda ligado al viaje. Si no,
    te pagaron (todo, 1/2, 1/3 o 1/4 de) un gasto tuyo de hasta 60
    días antes; o el concepto ya lo clasificaste antes; «RENTA» -> aportación
    de renta; «VIA/BOLETO/HOTEL…» -> VIAJES. Ver _pista_gasto.
  - propia: la misma cantidad salió de otra de tus cuentas ±3 días como
    transferencia, pago o inversión (no un gasto normal): es dinero tuyo que
    se movió entre cuentas, no entró de fuera.
  - sin pista.
"""
import re
from datetime import date, timedelta

CATEGORIAS = ('FINANZAS', 'PRESTAMOS', 'EXPENSE')
# Abonos que el usuario (o conciliar_pistas) marcó como dinero que vino de
# otra de sus cuentas: ya están conciliados, no salen en la lista.
SUB_PROPIA = 'Entre cuentas propias'


def sin_conciliar(db, anio: str | None = None) -> dict:
    ph = ','.join('?' * len(CATEGORIAS))
    params = list(CATEGORIAS)
    filtro_anio = ''
    if anio:
        filtro_anio = "AND substr(fecha, 1, 4) = ?"
        params.append(str(anio))
    try:   # parejas que se cancelan (routes.SE_CANCELAN): ya están conciliadas entre sí
        from .routes import SE_CANCELAN
    except Exception:
        SE_CANCELAN = ()
    cancelan = lambda r: any((r['fecha'] or '')[:10] == f and abs(abs(r['monto'] or 0) - m) < 0.005
                             and t in (r['descripcion'] or '').upper() for f, m, t in SE_CANCELAN)
    rows = [dict(r) for r in db.execute(f"""
        SELECT * FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph}) {filtro_anio}
          AND COALESCE(subcategoria, '') NOT IN ('{SUB_PROPIA}', '{SUB_COMPARTIDO}')
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
        ORDER BY fecha DESC, id DESC
    """, params).fetchall()]
    rows = [r for r in rows if not cancelan(r)]
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
    _patrones(rows)
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


def _concepto(desc: str) -> str:
    """Lo que escribió quien depositó: «PAGO CUENTA DE TERCERO BNET RENTA» -> «RENTA»,
    «SPEI RECIBIDONAFIN» -> «NAFIN»."""
    d = (desc or '').upper()
    for pref in ('BNET ', 'SPEI RECIBIDO', 'DEPOSITO EFECTIVO'):
        if pref in d:
            return d.split(pref, 1)[1].strip()[:25] or pref.strip()
    return d[:25]


def _frecuencia(fechas: list[str]) -> str:
    if len(fechas) < 3:
        return ''
    ds = sorted(date.fromisoformat(f) for f in fechas)
    gaps = sorted((b - a).days for a, b in zip(ds, ds[1:]))
    med = gaps[len(gaps) // 2]
    if 25 <= med <= 35:
        return 'cada mes'
    if 12 <= med <= 17:
        return 'cada quincena'
    if 5 <= med <= 9:
        return 'cada semana'
    return ''


def _patrones(rows) -> None:
    """r['patron']: el mismo monto que se repite (y cada cuánto) y el mismo
    concepto repetido, para recordar de qué eran (el usuario, 2026-09-29:
    «¿hay algún patrón… que se repita cada cierto tiempo o sea el mismo monto?»)."""
    por_monto, por_concepto = {}, {}
    for r in rows:
        por_monto.setdefault(round(abs(r['monto'] or 0), 2), []).append(r)
        por_concepto.setdefault(_concepto(r['descripcion']), []).append(r)
    for r in rows:
        partes = []
        mismos = por_monto[round(abs(r['monto'] or 0), 2)]
        if len(mismos) >= 2:
            fechas = [(m['fecha'] or '')[:10] for m in mismos if m['fecha']]
            frec = _frecuencia(fechas)
            partes.append(f"${abs(r['monto'] or 0):,.2f} ×{len(mismos)} ({min(fechas)} a {max(fechas)}"
                          + (f", {frec}" if frec else '') + ')')
        c = _concepto(r['descripcion'])
        if len(por_concepto[c]) >= 2:
            tot = sum(abs(m['monto'] or 0) for m in por_concepto[c])
            partes.append(f"«{c}» ×{len(por_concepto[c])} (${tot:,.2f})")
        r['patron'] = ' · '.join(partes)


def _estado(db) -> dict:
    """movimiento_id -> cómo quedó conciliado."""
    est = {}
    for r in db.execute("""SELECT d.movimiento_id, p.contraparte, p.fecha FROM est_prestamo_devoluciones d
                           JOIN est_prestamos p ON p.id = d.prestamo_id"""):
        est[r['movimiento_id']] = f"Devolución de préstamo: {r['contraparte']} ({(r['fecha'] or '')[:10]})"
    for r in db.execute("""SELECT d.movimiento_id, l.nombre FROM est_expense_lote_depositos d
                           JOIN est_expense_lotes l ON l.id = d.lote_id"""):
        est[r['movimiento_id']] = f"Depósito de Expense: lote «{r['nombre']}»"
    return est


def filas_csv(db, anio: str | None = None) -> list[list]:
    """Los sin conciliar y, como referencia, los que ya se conciliaron (columna
    Estado), con su pista y patrón. El patrón se calcula sobre todos juntos."""
    pend = sin_conciliar(db, anio)['movimientos']
    ids = {r['id'] for r in pend}
    ph = ','.join('?' * len(CATEGORIAS))
    params = list(CATEGORIAS) + ([str(anio)] if anio else [])
    otros = [dict(r) for r in db.execute(f"""
        SELECT * FROM est_movimientos WHERE tipo = 'INGRESO' AND categoria IN ({ph})
        {"AND substr(fecha, 1, 4) = ?" if anio else ""}
    """, params).fetchall() if r['id'] not in ids]
    est = _estado(db)
    for r in otros:
        r['pista'] = None
        r['estado'] = est.get(r['id']) or ('Entre cuentas propias' if r['subcategoria'] == SUB_PROPIA
                                           else 'Conciliado')
    for r in pend:
        r['estado'] = 'SIN CONCILIAR'
    todos = sorted(pend + otros, key=lambda r: (r['fecha'] or '', r['id']), reverse=True)
    _patrones(todos)
    return [[r['id'], (r['fecha'] or '')[:10], r['descripcion'], abs(r['monto'] or 0), r['banco'],
             r['categoria'], r['subcategoria'] or '', r['estado'],
             r['pista']['texto'] if r['pista'] else '', r['patron'], '']
            for r in todos]


PROPIA_DIAS = 3
_PALABRAS_COMUNES = {'PAGO', 'CUENTA', 'TERCERO', 'BNET', 'SPEI', 'RECIBIDO', 'ENVIADO', 'DEPOSITO',
                     'TRANSF', 'TRANSFERENCIA', 'PARA', 'DEL', 'LOS', 'LAS', 'GIO', 'GIOVANY', 'ALBERTO',
                     'SANCHEZ', 'BBVA', 'MEXICO'}


def _palabras(nombre: str) -> set:
    return {w for w in re.findall(r'[A-ZÑ]{3,}', (nombre or '').upper()) if w not in _PALABRAS_COMUNES}


PRESTAMO_DIAS = 365
COMPARTIDO_DIAS = 60
# Abono que te regresan lo que pagaste por otros en un gasto compartido (el
# gasto ya solo cuenta tu parte, mi_parte): ni ingreso ni resta al gasto.
SUB_COMPARTIDO = 'Reembolso compartido'


def _por_cobrar_compartido(db) -> list[dict]:
    """Gastos compartidos (con mi_parte): lo que pagaste por los demás."""
    out = []
    for g in db.execute("""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, ABS(mi_parte) AS mi_parte, viaje_id FROM est_movimientos
        WHERE tipo='GASTO' AND mi_parte IS NOT NULL AND ABS(monto) - ABS(mi_parte) > 1
    """).fetchall():
        out.append({**dict(g), 'otros': round(g['monto'] - g['mi_parte'], 2),
                    'resta': round(g['monto'] - g['mi_parte'], 2)})
    return out


def _compartido_de(compartidos, monto, fecha):
    """El usuario (2026-09-30): en los gastos compartidos «mi parte es lo que yo
    puse, lo demás yo lo pagué y luego me lo regresaron». El abono cuadra con lo
    que pagaste por los demás en un gasto de hasta 60 días antes: todo, o la
    parte de una persona (1/2, 1/3, 1/4 de lo de los demás)."""
    d = date.fromisoformat(fecha)
    cands = [g for g in compartidos if g['resta'] >= monto - 0.5
             and (g['fecha'] or '')[:10] <= (d + timedelta(days=1)).isoformat()
             and (g['fecha'] or '')[:10] >= (d - timedelta(days=COMPARTIDO_DIAS)).isoformat()]
    cands.sort(key=lambda g: abs((d - date.fromisoformat(g['fecha'][:10])).days))
    for k in PARTES:
        g = next((g for g in cands if abs(g['otros'] / k - monto) <= 0.5), None)
        if g:
            g['resta'] = round(g['resta'] - monto, 2)
            parte = 'todo lo de los demás' if k == 1 else f"la parte de una persona (1/{k} de lo de los demás)"
            return {'tipo': 'compartido', 'gasto_id': g['id'], 'viaje_id': g['viaje_id'],
                    'texto': f"Te regresaron {parte} de «{g['descripcion']}» ${g['monto']:,.2f} del {g['fecha'][:10]} "
                             f"(tu parte ${g['mi_parte']:,.2f})"}
    return None


def _pistas(db, rows) -> None:
    """Pone r['pista'] = {'tipo', 'texto'} o None en cada abono (ver docstring del módulo)."""
    try:
        from . import expense_lotes
        exp = {}
        for sug in expense_lotes.sugerencias(db):
            for d in sug['depositos']:
                exp[d['id']] = (f"Expense: cuadra con {len(sug['facturas'])} factura(s) por "
                                f"${sug['total']:,.2f} (confianza {sug['confianza']})", sug)
    except Exception:
        exp = {}
    try:
        from . import prestamos
        abiertos = [p for p in prestamos.listar(db) if p['pendiente'] > 0 and not p['perdido_fecha']]
    except Exception:
        abiertos = []
    aprendidos = _conceptos_aprendidos(db)
    pend = {p['id']: p['pendiente'] for p in abiertos}
    compartidos = _por_cobrar_compartido(db)
    # Del más antiguo al más reciente: cada devolución baja el pendiente de su
    # préstamo (o de su gasto compartido) antes de ver la siguiente.
    for r in sorted(rows, key=lambda x: (x['fecha'] or '', x['id'])):
        r['pista'] = None
        monto, fecha = abs(r['monto'] or 0), (r['fecha'] or '')[:10]
        if r['id'] in exp:
            texto, sug = exp[r['id']]
            r['pista'] = {'tipo': 'expense', 'texto': texto, 'confianza': sug['confianza'],
                          'facturas': [f['id'] for f in sug['facturas']],
                          'depositos': [d['id'] for d in sug['depositos']], 'nombre': sug['nombre']}
            continue
        if not fecha or 'RETIRO' in (r['descripcion'] or '').upper():
            continue
        c = _compartido_de(compartidos, monto, fecha)
        if c:
            r['pista'] = c
            continue
        desc = _palabras(r['descripcion'])
        antes = [p for p in abiertos if (p['fecha'] or '')[:10] <= fecha]
        p = next((p for p in antes if _palabras(p['persona']) & desc), None) \
            or next((p for p in antes if abs(pend[p['id']] - monto) < 0.01), None)
        if p:
            pend[p['id']] = round(pend[p['id']] - monto, 2)
            r['pista'] = {'tipo': 'prestamo', 'prestamo_id': p['id'],
                          'texto': f"Préstamo a {p['persona']} del {p['fecha'][:10]} (pendiente ${pend[p['id']] + monto:,.2f})"}
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
            continue
        r['pista'] = _pista_gasto(db, r, monto, d, aprendidos)
        if r['pista'] is None and _concepto(r['descripcion']).startswith('TRANSF'):
            # «TRANSF A GIOVANY A» no dice quién (el usuario: «me regresaron dinero
            # de algo, acomódalo a los préstamos»): el préstamo abierto más reciente
            # de hasta un año antes al que todavía le cabe el monto.
            lim = (d - timedelta(days=PRESTAMO_DIAS)).isoformat()
            p = max((p for p in abiertos if lim <= (p['fecha'] or '')[:10] <= fecha and pend[p['id']] >= monto - 0.01),
                    key=lambda p: p['fecha'], default=None)
            if p:
                pend[p['id']] = round(pend[p['id']] - monto, 2)
                r['pista'] = {'tipo': 'prestamo', 'prestamo_id': p['id'],
                              'texto': f"Préstamo a {p['persona']} del {p['fecha'][:10]} (pendiente "
                                       f"${pend[p['id']] + monto:,.2f}) · por fecha y monto: confírmalo"}




# ── Conciliación inteligente: abonos que regresan un gasto ─────────────────
# El usuario (2026-09-29): muchos depósitos son su parte de viajes, boletos,
# hoteles o cosas que compró por alguien. Conciliarlos = ponerles la
# categoría de ese gasto: un INGRESO en una categoría de gasto la resta
# (como ABONOS_A_GASTO), así el viaje cuenta solo lo que le tocó pagar.
GASTO_DIAS_ANTES, GASTO_DIAS_DESPUES = 60, 1
_SE_DIVIDE = ('VIAJES', 'COMIDA_FUERA', 'OCIO', 'SALSA', 'CAFE/PAN', 'TRANSPORTE')
_NO_GASTO = ('FINANZAS', 'PRESTAMOS', 'EXPENSE', 'INVERSION', 'NOMINA', 'OTROS', 'PAGO')
_VIAJE_RE = re.compile(r'\b(VIA|VIAJE|VIAJ|VACA|VACAS|BOLETO|BOLET|BOLETOS|HOTEL|HOSPEDAJE|VUELO|AVION|AIRBNB|CASA PLAYA)\b')
_RENTA_RE = re.compile(r'\bRENTA\b')
# Conceptos que no dicen nada: no se aprende de ellos.
# Depósitos de la empresa (Expense / viáticos): nunca son «te pagaron un gasto».
_EMPRESA_RE = re.compile(r'SITH2|SITH\d|FIDEICOMISO|BMRCASH|EXPENSE|SGLDAC')
_GENERICOS = {'CODI VALIDA', 'TRANSF A GIO', 'TRANSF A', 'TRANSFERENCI', 'TRANSFERENCIA', 'PAGO', 'GIO', 'GIOVANY', 'P', 'XX',
              'TRANSF A UND', 'NAFIN', 'HSBC', 'STP', 'BANORTE', 'SANTANDER', 'BANAMEX'}
PARTES = (1, 2, 3, 4)   # te pagaron todo, la mitad, un tercio o un cuarto del gasto


def _generico(c: str) -> bool:
    """«TRANSF A GIOVANY A» es el concepto que pone la app del banco por
    defecto: lo usan muchas personas distintas, no dice nada."""
    return (c in _GENERICOS or len(c) < 3 or c.startswith('TRANSF') or 'GIOVANY' in c or 'RETIRO' in c
            or _EMPRESA_RE.search(c) is not None)


def _conceptos_aprendidos(db) -> dict:
    """concepto -> (categoria, subcategoria) de abonos que el usuario ya puso en
    una categoría de gasto (el mismo «BNET BOLETO» de otra vez)."""
    ph = ','.join('?' * len(_NO_GASTO))
    cuenta = {}
    for r in db.execute(f"""SELECT descripcion, categoria, subcategoria FROM est_movimientos
                            WHERE tipo='INGRESO' AND categoria NOT IN ({ph})""", _NO_GASTO).fetchall():
        c = _concepto(r['descripcion'])
        if c and not _generico(c):
            k = (r['categoria'], r['subcategoria'] or '')
            cuenta.setdefault(c, {}).setdefault(k, 0)
            cuenta[c][k] += 1
    return {c: max(ks, key=ks.get) for c, ks in cuenta.items()}


VIAJE_DIAS_ANTES, VIAJE_DIAS_DESPUES = 3, 30


def _viaje_de(db, d):
    """El viaje (con gastos ligados) en cuyas fechas cae el depósito: de 3 días
    antes a 30 después (te pagan su parte al regresar). El más cercano."""
    return db.execute("""
        SELECT v.id, v.nombre, v.fecha_inicio, v.fecha_fin FROM viajes v
        WHERE ? BETWEEN date(v.fecha_inicio, ?) AND date(v.fecha_fin, ?)
          AND EXISTS (SELECT 1 FROM est_movimientos m WHERE m.viaje_id = v.id AND m.tipo = 'GASTO')
        ORDER BY ABS(julianday(?) - julianday(v.fecha_fin)) LIMIT 1
    """, (d.isoformat(), f'-{VIAJE_DIAS_ANTES} day', f'+{VIAJE_DIAS_DESPUES} day', d.isoformat())).fetchone()


def _pista_viaje(db, r, monto, d):
    """El usuario (2026-09-30): lo que le transfirieron en las fechas de un viaje
    seguramente fue su parte de algo que él pagó. Busca el gasto del viaje que
    cuadra (todo, 1/2, 1/3, 1/4); si ninguno, «tu parte del viaje»."""
    v = _viaje_de(db, d)
    if not v:
        return None
    # Solo gastos de verdad del viaje: no transferencias, retiros ni pagos
    # ligados a él (FINANZAS, PRESTAMOS…), que no son algo que «te pagaron».
    ph = ','.join('?' * len(_NO_GASTO))
    gastos = db.execute(f"""
        SELECT fecha, descripcion, ABS(monto) AS monto, categoria, subcategoria FROM est_movimientos
        WHERE viaje_id = ? AND tipo = 'GASTO' AND categoria NOT IN ({ph})
          AND COALESCE(subcategoria,'') != 'Compra a meses' AND mi_parte IS NULL AND substr(fecha,1,10) <= ?
        ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?))
    """, (v['id'], *_NO_GASTO, (d + timedelta(days=1)).isoformat(), d.isoformat())).fetchall()
    for partes in PARTES:
        g = next((g for g in gastos if abs(g['monto'] - monto * partes) <= 0.5 * partes), None)
        if g:
            parte = 'todo' if partes == 1 else f"1/{partes}"
            return {'tipo': 'gasto', 'categoria': g['categoria'], 'subcategoria': g['subcategoria'] or '',
                    'viaje_id': v['id'],
                    'texto': f"Viaje «{v['nombre']}»: te pagaron {parte} de «{g['descripcion']}» ${g['monto']:,.2f} "
                             f"→ {g['categoria']}/{g['subcategoria'] or ''}"}
    otros = db.execute("""SELECT COALESCE(SUM(ABS(monto) - ABS(mi_parte)), 0) FROM est_movimientos
                          WHERE viaje_id=? AND tipo='GASTO' AND mi_parte IS NOT NULL""", (v['id'],)).fetchone()[0] or 0
    if otros > 1:
        # En el viaje pagaste por otros (gastos con «mi parte»): lo más probable es
        # que te estén regresando eso, que ya no cuenta como tu gasto.
        return {'tipo': 'compartido', 'viaje_id': v['id'],
                'texto': f"Llegó en las fechas del viaje «{v['nombre']}», donde pagaste ${otros:,.2f} por otros: "
                         f"te regresaron parte de eso"}
    return {'tipo': 'gasto', 'categoria': 'VIAJES', 'subcategoria': 'Otros', 'viaje_id': v['id'],
            'texto': f"Llegó en las fechas del viaje «{v['nombre']}» ({v['fecha_inicio'][:10]} a "
                     f"{v['fecha_fin'][:10]}): tu parte de algo del viaje → VIAJES/Otros"}


def _pista_gasto(db, r, monto, d, aprendidos):
    if 'RETIRO' in (r['descripcion'] or '').upper():   # retiro de efectivo: no es que te pagaran algo
        return None
    if _EMPRESA_RE.search((r['descripcion'] or '').upper()):
        # Ni el algoritmo de Expense lo cuadró con facturas: se revisa a mano.
        return {'tipo': 'empresa', 'texto': 'Depósito de la empresa (Expense/viáticos) sin facturas que cuadren: '
                                            'crea o completa su lote en Expense'}
    concepto = _concepto(r['descripcion'])
    if concepto in aprendidos:
        cat, sub = aprendidos[concepto]
        return {'tipo': 'gasto', 'categoria': cat, 'subcategoria': sub,
                'texto': f"Como otros «{concepto}» que ya clasificaste: {cat}/{sub}"}
    if _RENTA_RE.search(concepto):
        return {'tipo': 'gasto', 'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta',
                'texto': "Parte de la renta que te depositaron (concepto «RENTA»)"}
    viaje = bool(_VIAJE_RE.search(concepto))
    if 'RETIRO' in (r['descripcion'] or '').upper():   # retiro de efectivo: no es que te pagaran algo
        return None
    pv = _pista_viaje(db, r, monto, d)
    if pv:
        return pv
    ph = ','.join('?' * len(_NO_GASTO))
    # El gasto va antes del depósito (pagaste y luego te pagaron), hasta el día siguiente.
    cands = db.execute(f"""
        SELECT fecha, descripcion, ABS(monto) AS monto, categoria, subcategoria FROM est_movimientos
        WHERE tipo='GASTO' AND categoria NOT IN ({ph}) AND COALESCE(subcategoria,'') NOT IN ('Compra a meses', 'Renta') AND mi_parte IS NULL
          AND substr(fecha,1,10) BETWEEN ? AND ? {"AND categoria='VIAJES'" if viaje else ""}
        ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?))
    """, (*_NO_GASTO, (d - timedelta(days=GASTO_DIAS_ANTES)).isoformat(),
          (d + timedelta(days=GASTO_DIAS_DESPUES)).isoformat(), d.isoformat())).fetchall()
    for partes in PARTES:
        # Mitades, tercios y cuartos solo en lo que se suele dividir entre varios.
        g = next((g for g in cands if abs(g['monto'] - monto * partes) <= 0.5 * partes
                  and (partes == 1 or g['categoria'] in _SE_DIVIDE)), None)
        if g:
            parte = 'todo' if partes == 1 else f"1/{partes}"
            return {'tipo': 'gasto', 'categoria': g['categoria'], 'subcategoria': g['subcategoria'] or '',
                    'texto': f"Te pagaron {parte} de «{g['descripcion']}» ${g['monto']:,.2f} del "
                             f"{g['fecha'][:10]} → {g['categoria']}/{g['subcategoria'] or ''}"}
    if viaje:
        return {'tipo': 'gasto', 'categoria': 'VIAJES', 'subcategoria': 'Otros',
                'texto': f"Tu parte de un viaje o boleto (concepto «{concepto}») → VIAJES/Otros"}
    return None


CONFIANZAS_EXPENSE = ('alta', 'media')   # «aproximada» no cuadra exacto: se revisa a mano


def conciliar_pistas(db, solo_seguras: bool = False) -> dict:
    """Aplica las pistas (el usuario, 2026-09-29: «manda esas sugerencias,
    concílialas»):
      - expense (confianza alta/media): crea el lote con sus facturas y
        depósito(s), como «Crear lote» en la pestaña Expense.
      - prestamo: liga la devolución, sin pasar del pendiente del préstamo.
      - propia: FINANZAS/«Entre cuentas propias».
      - gasto: la categoría del gasto que te pagaron (resta a ese gasto).
        solo_seguras=True (la migración de arranque) no aplica estas.
    Lo que no se aplica (Expense aproximada, devolución mayor al pendiente)
    se queda en la lista con su pista. Devuelve los conteos."""
    from datetime import datetime
    from . import expense_lotes, prestamos
    ahora = datetime.now().isoformat(timespec='seconds')
    out = {'expense_lotes': 0, 'expense_depositos': 0, 'prestamos': 0, 'propias': 0, 'gastos': 0, 'compartidos': 0, 'sin_aplicar': 0}
    rows = sorted(sin_conciliar(db)['movimientos'], key=lambda r: (r['fecha'] or '', r['id']))
    pendiente = {p['id']: p['pendiente'] for p in prestamos.listar(db)}
    hechos = set()
    for r in rows:
        pista = r['pista']
        if not pista or r['id'] in hechos:
            continue
        monto = abs(r['monto'] or 0)
        if pista['tipo'] == 'expense':
            if pista['confianza'] not in CONFIANZAS_EXPENSE:
                out['sin_aplicar'] += 1
                continue
            libres = lambda tabla, ids: not db.execute(
                f"SELECT 1 FROM {tabla} WHERE movimiento_id IN ({','.join('?' * len(ids))})", ids).fetchone()
            if not (libres('est_expense_lote_gastos', pista['facturas'])
                    and libres('est_expense_lote_depositos', pista['depositos'])):
                out['sin_aplicar'] += 1
                continue
            lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                             (pista['nombre'], 'Conciliado desde «Sin conciliar»', ahora)).lastrowid
            for mid in pista['facturas']:
                db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                           (lid, mid, ahora))
            for mid in pista['depositos']:
                db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (mid,))
                db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                           (lid, mid, ahora))
                hechos.add(mid)
            expense_lotes.sincronizar(db, lid)
            out['expense_lotes'] += 1
            out['expense_depositos'] += len(pista['depositos'])
        elif pista['tipo'] == 'prestamo':
            pid = pista['prestamo_id']
            if monto > pendiente.get(pid, 0) + 0.01:
                out['sin_aplicar'] += 1
                continue
            db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='' WHERE id=?", (r['id'],))
            db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (pid, r['id'], ahora))
            pendiente[pid] = round(pendiente[pid] - monto, 2)
            out['prestamos'] += 1
        elif pista['tipo'] == 'compartido':
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=?, viaje_id=COALESCE(?, viaje_id) WHERE id=?",
                       (SUB_COMPARTIDO, pista.get('viaje_id'), r['id']))
            out['compartidos'] += 1
        elif pista['tipo'] == 'empresa':
            out['sin_aplicar'] += 1
        elif pista['tipo'] == 'gasto':
            if not solo_seguras:
                db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, viaje_id=COALESCE(?, viaje_id) WHERE id=?",
                           (pista['categoria'], pista['subcategoria'], pista.get('viaje_id'), r['id']))
                out['gastos'] += 1
        elif pista['tipo'] == 'propia':
            db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=? WHERE id=?", (SUB_PROPIA, r['id']))
            out['propias'] += 1
    return out
