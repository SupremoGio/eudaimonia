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
    """Todo lo de Expense en un archivo, con ID para poder conciliar fuera de
    la app: facturas y depósitos de cada lote, facturas sin lote y los
    depósitos de la empresa que aún no están en ningún lote."""
    filas = []
    for l in listar(db):
        for g in l['gastos']:
            filas.append([g['id'], l['nombre'], l['estado'], 'Factura', g['fecha'], g['descripcion'], g['monto'],
                          'Pagado a compañero' if g['estatus_reembolso'] == ESTATUS_TERCERO else '', ''])
        for d in l['depositos']:
            filas.append([d['id'], l['nombre'], l['estado'], 'Depósito', d['fecha'], d['descripcion'], d['monto'], '', ''])
    for g in sin_lote(db):
        filas.append([g['id'], '', 'Sin lote', 'Factura', g['fecha'], g['descripcion'], g['monto'], g['estatus_reembolso'] or '', ''])
    for d in _depositos_sin_lote(db):
        filas.append([d['id'], '', 'Sin lote', 'Depósito', d['fecha'], d['descripcion'], d['monto'], '', ''])
    return filas


# ── Sugerencias automáticas ───────────────────────────────────────────────────
# El usuario (2026-09-28): los depósitos de la empresa (FIDEICOMISO F 1596,
# SITH2…, «EXPENSE … BMRCASH») pagan facturas de 1 a 3 meses antes. Para cada
# depósito sin lote se busca el grupo de facturas EXPENSE sin lote, de hasta
# VENTANA_DIAS antes, cuya suma dé el depósito (±TOLERANCIA). Solo sugiere:
# el usuario confirma y se crea el lote.
import re
from datetime import date, timedelta

VENTANA_DIAS = 100
_DEP_RE = re.compile(r'FIDEICOMISO|EXPENSE|SITH2|BMRCASH', re.IGNORECASE)


def _combinacion(montos: list[float], objetivo: float, tol: float = TOLERANCIA) -> list[int] | None:
    """Índices de montos cuya suma da el objetivo (±tol). Suma de
    subconjuntos en centavos con bitsets (así la combinación exacta al
    centavo gana a una que solo cuadra redondeando). Busca de la suma más
    cercana hacia afuera y, con varias soluciones, prefiere las facturas más
    antiguas (las primeras)."""
    cent = [int(round(m * 100)) for m in montos]
    obj = int(round(objetivo * 100))
    holgura = int(round(tol * 100))
    limite = obj + holgura
    mask = (1 << (limite + 1)) - 1
    alcanzables = [1]                          # alcanzables[i]: sumas con los primeros i montos
    for w in cent:
        alcanzables.append((alcanzables[-1] | (alcanzables[-1] << w)) & mask)
    total = alcanzables[-1]
    for delta in sorted(range(-holgura, holgura + 1), key=abs):
        s = obj + delta
        if s <= 0 or not (total >> s) & 1:
            continue
        idx = []
        for i in range(len(cent), 0, -1):      # de la más reciente a la más antigua
            if (alcanzables[i - 1] >> s) & 1:
                continue                       # alcanzable sin la i-ésima: no se usa
            idx.append(i - 1)
            s -= cent[i - 1]
        return sorted(idx)
    return None


def _bloque_seguido(montos: list[float], objetivo: float) -> list[int] | None:
    """Bloque de 2+ facturas consecutivas (ordenadas por fecha) que suma el
    objetivo (±TOLERANCIA): así sube el usuario sus facturas, por tanda. Si hay
    varios, el que empieza antes (los depósitos se atienden del más antiguo al
    más reciente, así cada uno toma las facturas más viejas que le cuadran)."""
    n = len(montos)
    for i in range(n):
        suma = 0.0
        for j in range(i, n):
            suma += montos[j]
            if j > i and abs(suma - objetivo) <= TOLERANCIA:
                return list(range(i, j + 1))
            if suma > objetivo + TOLERANCIA:
                break
    return None


# Pasadas de la más segura a la más amplia (el usuario: «amplía para emparejar
# facturas»): primero facturas de hasta ~3 meses antes, luego 6 y 12 para los
# depósitos que quedaron sin pareja; al final, dos depósitos seguidos (≤45
# días) que juntos pagan un grupo de facturas.
PASADAS = ((100, 'alta'), (185, 'media'), (370, 'baja'))
PAR_DIAS = 45
BLOQUE_DIAS = 400          # tanda de facturas seguidas: hasta ~13 meses antes
APROX_DIAS = 185           # aproximadas: la combinación más cercana en ~6 meses


def _tol_aprox(monto: float) -> float:
    return max(300.0, round(monto * 0.03, 2))


def _depositos_sin_lote(db) -> list[dict]:
    return [{**dict(r), 'monto': round(float(r['monto']), 2)} for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, banco FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ('FINANZAS', 'EXPENSE')
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY fecha, id
    """).fetchall() if _DEP_RE.search(r['descripcion'] or '')]


def sugerencias(db) -> list[dict]:
    deps = _depositos_sin_lote(db)
    libres = [g for g in sin_lote(db) if (g['estatus_reembolso'] or '') != ESTATUS_TERCERO]
    libres.sort(key=lambda g: (g['fecha'], g['id']))
    usados, emparejados, out = set(), set(), []

    def buscar(depositos, dias, confianza, modo='suma'):
        desde = (date.fromisoformat(depositos[0]['fecha']) - timedelta(days=dias)).isoformat()
        hasta = depositos[-1]['fecha']
        objetivo = round(sum(d['monto'] for d in depositos), 2)
        cand = [g for g in libres if g['id'] not in usados and desde <= g['fecha'][:10] <= hasta]
        if not cand:
            return False
        montos = [g['monto'] for g in cand]
        if modo == 'bloque':
            idx = _bloque_seguido(montos, objetivo)
        elif modo == 'aprox':
            idx = _combinacion(montos, objetivo, _tol_aprox(objetivo))
        else:
            idx = _combinacion(montos, objetivo)
        if idx is None:
            return False
        facturas = [cand[i] for i in idx]
        if modo == 'bloque':               # tanda reciente: alta; tanda vieja: media
            antig = (date.fromisoformat(hasta) - date.fromisoformat(facturas[0]['fecha'][:10])).days
            confianza = 'alta' if antig <= PASADAS[1][0] else 'media'
        usados.update(g['id'] for g in facturas)
        emparejados.update(d['id'] for d in depositos)
        total = round(sum(g['monto'] for g in facturas), 2)
        out.append({
            'deposito': depositos[0], 'depositos': depositos,
            'facturas': facturas, 'total': total,
            'diferencia': round(objetivo - total, 2),
            'confianza': confianza, 'ventana_dias': dias,
            'nombre': f"Expense {depositos[-1]['fecha']}",
        })
        return True

    for d in deps:                                   # tandas de facturas seguidas
        buscar([d], BLOQUE_DIAS, 'alta', 'bloque')
    for dias, confianza in PASADAS:
        for d in deps:
            if d['id'] not in emparejados:
                buscar([d], dias, confianza)
    sueltos = [d for d in deps if d['id'] not in emparejados]
    for a, b in zip(sueltos, sueltos[1:]):
        if a['id'] in emparejados or b['id'] in emparejados:
            continue
        if (date.fromisoformat(b['fecha']) - date.fromisoformat(a['fecha'])).days <= PAR_DIAS:
            buscar([a, b], PASADAS[1][0], 'media')
    for d in deps:                                   # lo más cercano, con diferencia
        if d['id'] not in emparejados:
            buscar([d], APROX_DIAS, 'aproximada', 'aprox')
    out.sort(key=lambda x: x['deposito']['fecha'])
    return out


def sueltos(db) -> dict:
    """Lo que ni está en un lote ni entra en ninguna sugerencia: depósitos de
    la empresa sin pareja y facturas EXPENSE pendientes sin pareja."""
    sug = sugerencias(db)
    con_dep = {d['id'] for s in sug for d in s['depositos']}
    con_fact = {f['id'] for s in sug for f in s['facturas']}
    deps = [d for d in _depositos_sin_lote(db) if d['id'] not in con_dep]
    facts = [g for g in sin_lote(db) if g['id'] not in con_fact
             and (g['estatus_reembolso'] or 'PENDIENTE') == 'PENDIENTE']
    return {
        'depositos': sorted(deps, key=lambda d: d['fecha'], reverse=True),
        'facturas': sorted(facts, key=lambda g: g['fecha'], reverse=True),
        'total_depositos': round(sum(d['monto'] for d in deps), 2),
        'total_facturas': round(sum(g['monto'] for g in facts), 2),
    }
