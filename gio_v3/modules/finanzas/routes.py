from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from datetime import date, datetime, timedelta
from collections import defaultdict
from utils import today_str, today_date, clean_str, safe_float
from . import compromisos as _comp
from .estados import prestamos as _prest

finanzas_bp = Blueprint('finanzas', __name__, template_folder='../../templates')


# Días de pago de las tarjetas (no hay fecha de corte en la DB). `match` se
# busca en el nombre/institución de la cuenta de pasivo para el badge de
# vencimiento del hub; `label` es el aviso del día de pago.
PAY_DAYS = [
    {'match': 'bbva',  'day': 15, 'label': 'BBVA TDC'},
    {'match': 'invex', 'day': 15, 'label': 'Invex'},
    {'match': 'hsbc',  'day': 30, 'label': 'HSBC'},
]
_MESES_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _pagados():
    """{cuenta: fila} con el ciclo actual ya pagado (detecta antes los
    PAGO_TDC que ya entraron en un estado de cuenta). Defensivo: {} si falla."""
    from . import pagos_ciclo
    try:
        with get_db() as db:
            if pagos_ciclo.detectar(db):
                db.commit()
            return pagos_ciclo.pagados(db)
    except Exception:
        return {}


def payment_alerts():
    d = today_date().day
    hoy = [p for p in PAY_DAYS if p['day'] == d]
    if not hoy:
        return []
    pag = _pagados()
    return [{'label': p['label']} for p in hoy if p['match'] not in pag]


PAGO_AVISO_DIAS = 7          # un pago entra a «Esta semana» a 7 días
PRESUPUESTO_AVISO_PCT = 0.85  # mismo umbral que budgetAlerts() del bundle
ESTADO_CORTE = {'BBVA_TDC': (22, 'BBVA TDC')}   # tarjetas con día de corte conocido
ESTADO_GRACIA_DIAS = 3       # el banco tarda en publicar el estado


def avisos(db, hoy):
    """Avisos de Oikonomia para el centro (modules/avisos.py). Envuelve
    pagos_ciclo (lo mismo que payment_alerts y el hub), _detectar_avisos_msi,
    los presupuestos al 85 % y el estado de cuenta que falta subir."""
    from modules.avisos import aviso, relativo, fecha_corta, huella
    from . import pagos_ciclo
    from .estados.routes import _detectar_avisos_msi, presupuestos_mes
    out = []

    # Pagos de tarjeta: hoy → Hoy; ≤ 7 días → Esta semana. Marcar pagado en línea.
    if pagos_ciclo.detectar(db, hoy):
        db.commit()
    pagados = pagos_ciclo.pagados(db, hoy)
    for p in PAY_DAYS:
        if p['match'] in pagados:
            continue
        cic, due, _prev = pagos_ciclo.ciclo(p, hoy)
        dias = (due - hoy).days
        if dias > PAGO_AVISO_DIAS:
            continue
        body = {'cuenta': p['match']}
        out.append(aviso(
            f"oik:pago:{p['match']}:{cic}", 'Oikonomia', 'wallet', f"Pago de {p['label']}",
            'vence hoy' if dias <= 0 else f'vence {relativo(dias)} · {fecha_corta(due)}', due,
            'hoy' if dias <= 0 else 'semana',
            {'label': 'Marcar pagado', 'method': 'POST', 'url': '/finanzas/api/pago-ciclo', 'body': body,
             'hecho': 'Pago registrado',
             'deshacer': {'method': 'DELETE', 'url': '/finanzas/api/pago-ciclo', 'body': body}},
            perm='fin_ok'))

    # Compras a MSI con señales de doble conteo (solo avisa; se revisa a mano).
    msi = _detectar_avisos_msi(db)
    if msi:
        n = len(msi)
        out.append(aviso(
            f"oik:msi:{huella(m['compra_msi_id'] for m in msi)}", 'Oikonomia', 'wallet',
            f"{n} compra{'s' if n != 1 else ''} a MSI por revisar",
            msi[0]['descripcion'] if n == 1 else 'posible doble conteo de mensualidades', None, 'semana',
            {'label': 'Ver', 'url': '/finanzas/estados/#movimientos'}, perm='fin_ok'))

    # Presupuestos al 85 % o más este mes (las alertas del bundle, publicadas aquí).
    ym = hoy.strftime('%Y-%m')
    for b in presupuestos_mes(db, hoy.replace(day=1).isoformat()):
        if b['limite'] <= 0:
            continue
        pct = abs(b['gastado']) / b['limite']
        if pct < PRESUPUESTO_AVISO_PCT:
            continue
        pasado = pct > 1
        out.append(aviso(
            f"oik:presupuesto:{b['id']}:{ym}:{'excedido' if pasado else 'alerta'}", 'Oikonomia',
            'octagon-alert' if pasado else 'triangle-alert',
            f"Presupuesto de {b['nombre']} {'excedido' if pasado else 'al ' + str(round(pct * 100)) + ' %'}",
            f"${abs(b['gastado']):,.0f} de ${b['limite']:,.0f}", None, 'semana',
            {'label': 'Ver', 'url': '/finanzas/budget/'}, perm='fin_ok'))

    # Estado de cuenta por subir: pasó el corte (+ gracia) y no hay ningún
    # movimiento de esa tarjeta en el periodo que cerró.
    lim = hoy - timedelta(days=ESTADO_GRACIA_DIAS)
    for banco, (dia, label) in ESTADO_CORTE.items():
        corte = pagos_ciclo._due(lim.year, lim.month, dia)
        if corte > lim:
            y, m = (lim.year, lim.month - 1) if lim.month > 1 else (lim.year - 1, 12)
            corte = pagos_ciclo._due(y, m, dia)
        y, m = (corte.year, corte.month - 1) if corte.month > 1 else (corte.year - 1, 12)
        inicio = pagos_ciclo._due(y, m, dia)      # periodo (inicio, corte]
        if not db.execute("SELECT 1 FROM est_movimientos WHERE banco=? LIMIT 1", (banco,)).fetchone():
            continue                              # tarjeta que nunca se ha importado
        hay = db.execute("SELECT 1 FROM est_movimientos WHERE banco=? AND substr(fecha,1,10) > ? AND substr(fecha,1,10) <= ? LIMIT 1",
                         (banco, inicio.isoformat(), corte.isoformat())).fetchone()
        if not hay:
            out.append(aviso(
                f"oik:estado:{banco}:{corte.isoformat()}", 'Oikonomia', 'upload',
                f"Subir estado de cuenta {label}", f"cortó el {fecha_corta(corte)}", corte, 'semana',
                {'label': 'Subir', 'url': '/finanzas/estados/'}, perm='fin_ok'))
    return out


def _days_until(day):
    """Días hasta el próximo `day` del mes (un 30/31 en meses cortos cae en el último día)."""
    import calendar
    from datetime import timedelta
    t = today_date()
    for k in range(0, 2):
        y, m = (t.year, t.month + k) if t.month + k <= 12 else (t.year + 1, 1)
        last = calendar.monthrange(y, m)[1]
        due = t.replace(year=y, month=m, day=min(day, last))
        if due >= t:
            return (due - t).days
    return None


def _hub_debts(cuentas):
    """Tarjetas y préstamos activos (salud_cuentas) con su pago mínimo
    (budget_deudas, por nombre) y días al próximo pago (PAY_DAYS)."""
    from modules.finanzas.salud import TIPOS_PASIVO, TIPO_META, MONEDAS_EXTRANJERAS
    try:
        with get_db() as db:
            minimos = {(r['nombre'] or '').strip().lower(): r['pago_minimo'] or 0
                       for r in db.execute("SELECT nombre, pago_minimo FROM budget_deudas WHERE activa=1")}
    except Exception:
        minimos = {}
    # El saldo de las tarjetas sale de sus compras a MSI por pagar (la misma
    # cifra de «MSI activos» en Estados), no del capturado a mano en
    # Patrimonio. Banco del estado de cuenta (BBVA_TDC, HSBC…) → tarjeta cuyo
    # nombre/institución lo menciona; solo la primera, para no contarlo doble.
    # Tarjetas de bancos sin historial de MSI conservan el saldo manual.
    try:
        from modules.finanzas.estados.routes import msi_por_pagar
        activos, msi_bancos = msi_por_pagar()
    except Exception:
        activos, msi_bancos = [], set()
    msi_banco = defaultdict(float)
    for a in activos:
        msi_banco[a['banco']] += a['restante']
    asignados = set()
    pag = _pagados()
    out = []
    for c in cuentas:
        if c['tipo'] not in TIPOS_PASIVO or c['moneda'] in MONEDAS_EXTRANJERAS:
            continue
        hay = f"{c['nombre']} {c.get('institucion') or ''}".lower()
        saldo, de_msi = c['saldo'], False
        if c['tipo'] == 'tarjeta_credito':
            bancos = [b for b in msi_bancos - asignados if b and b.split('_')[0].lower() in hay]
            if bancos:
                asignados.update(bancos)
                saldo, de_msi = round(sum(msi_banco[b] for b in bancos), 2), True
        if not saldo:
            continue
        pay = next((p for p in PAY_DAYS if p['match'] in hay), None)
        dias = _days_until(pay['day']) if pay else None
        minimo = next((v for k, v in minimos.items() if k and (k in hay or c['nombre'].lower() in k)), None)
        out.append({
            'nombre': c['nombre'], 'cuenta': pay['match'] if pay else None,
            'sub': ' · '.join(filter(None, [TIPO_META.get(c['tipo'], {}).get('label'), c.get('institucion'),
                                            'MSI por pagar' if de_msi else None])),
            'saldo': saldo, 'minimo': minimo, 'dias': dias, 'tipo': c['tipo'],
            'vence': (today_date() + timedelta(days=dias)).isoformat() if dias is not None else None,
            'pagado': bool(pay and pay['match'] in pag),
            'tone': None if dias is None else 'danger' if dias == 0 else 'warning' if dias <= 7 else '',
        })
        if out[-1]['pagado']:
            out[-1]['tone'] = 'success'
    out.sort(key=lambda d: (d['dias'] is None, d['dias'] if d['dias'] is not None else 0, -d['saldo']))
    return out


def _hub_budget_rows(bd, limit=5):
    """Presupuesto por categoría para el hub: primero las categorías con límite
    configurado (gastado / límite); si no hay ninguna, los 3 buckets 50/30/20
    (gastado / meta del bucket). tone: ≥90% warning, >100% danger."""
    rows = []
    for bk in bd['buckets'].values():
        for c in bk['cats']:
            if c['tiene_limite']:
                rows.append({'nombre': c['nombre'], 'gastado': c['gastado'], 'meta': c['limite']})
    if not rows:
        rows = [{'nombre': bk['label'] if 'label' in bk else k, 'gastado': bk['total_gastado'], 'meta': bk['target_monto']}
                for k, bk in bd['buckets'].items()]
    if not any(r['gastado'] or r['meta'] for r in rows):
        return []
    for r in rows:
        r['pct'] = round(r['gastado'] / r['meta'] * 100) if r['meta'] else 0
        r['tone'] = 'danger' if r['pct'] > 100 else 'warning' if r['pct'] >= 90 else 'brand'
    rows.sort(key=lambda r: -r['pct'])
    for r in rows:
        r['restante'] = round((r['meta'] or 0) - (r['gastado'] or 0), 2)
    return rows[:limit] if limit else rows


# Oikonomia v2 (handoff, Sprint 1): metas 50·30·20 del resumen. Necesidades y
# Deseos son topes (kind 'max'); Ahorro y deudas es un piso (kind 'min').
_SEG_META = [('necesidades', 50, 'max'), ('deseos', 30, 'max'), ('ahorro_deuda', 20, 'min')]
BUDGET_RISK_PCT = 85      # «Categorías en riesgo»: ≥ 85% del límite
NEXT_STEP_DIAS = 3        # un pago que vence en ≤ 3 días también es «siguiente paso»
# Estados de cuenta → Movimientos filtrado a los depósitos sin clasificar (ver filterFromHash en el SPA).
DEPOSITOS_SIN_CLASIFICAR_URL = '/finanzas/estados/#movimientos?tipo=INGRESO&category=DEPOSITO,SPEI_RECIBIDO'


def _hub_seg(bd):
    """Los 3 buckets del ingreso para la barra 50·30·20 del héroe:
    {key, label, pct, meta_pct, kind, ok, monto, meta, falta}. pct sale de
    bd['seg'] (la misma barra que /finanzas/budget/); la meta de ahorro es
    meta_minima si existe, si no target_monto."""
    ing = bd['ingreso_real'] or 0
    out = []
    for key, meta_pct, kind in _SEG_META:
        bk = bd['buckets'][key]
        pct = bd['seg'].get(key, 0)
        monto = round(ing * pct / 100, 2)
        if kind == 'min':
            meta = bk.get('meta_minima') or bk['target_monto']
            ok = monto >= meta
            falta = round(max(meta - monto, 0), 2)
        else:
            meta = bk['target_monto']
            ok = pct <= meta_pct
            falta = 0
        out.append({'key': key, 'label': bk.get('label', key), 'pct': pct, 'meta_pct': meta_pct,
                    'kind': kind, 'ok': ok, 'monto': monto, 'meta': meta, 'falta': falta})
    return out


def _hub_next_step(debts, n_sin_clasificar, monto_sin_clasificar):
    """Lo que toca resolver primero en el hub: pago que vence hoy → depósitos
    sin clasificar → pago en ≤ 3 días → None. Las deudas ya pagadas en el
    ciclo (d['pagado'], Sprint 2) no cuentan. El dinero va aparte (monto)
    para que la plantilla lo pase por hide()."""
    pend = [d for d in debts if d.get('dias') is not None and not d.get('pagado')]
    hoy = next((d for d in pend if d['dias'] == 0), None)
    if hoy:
        return {'kind': 'pago', 'title': f"Pagar {hoy['nombre']}", 'sub': 'vence hoy', 'monto': hoy.get('minimo'),
                'cuenta': hoy.get('cuenta'), 'cta': 'Marcar pagado', 'action': 'pago-ciclo', 'tone': 'danger'}
    if n_sin_clasificar:
        return {'kind': 'clasificar', 'title': f"Clasificar {n_sin_clasificar} depósito{'s' if n_sin_clasificar != 1 else ''}",
                'sub': 'que podrían ser ingreso', 'monto': monto_sin_clasificar, 'cta': 'Clasificar',
                'href': DEPOSITOS_SIN_CLASIFICAR_URL, 'tone': 'warning'}
    pronto = next((d for d in pend if d['dias'] <= NEXT_STEP_DIAS), None)
    if pronto:
        return {'kind': 'pago', 'title': f"Pagar {pronto['nombre']}",
                'sub': f"vence en {pronto['dias']} día{'s' if pronto['dias'] != 1 else ''}", 'monto': pronto.get('minimo'),
                'cuenta': pronto.get('cuenta'), 'cta': 'Marcar pagado', 'action': 'pago-ciclo', 'tone': 'warning'}
    return None


@finanzas_bp.route('/')
def index():
    from modules.finanzas.salud import _compute_patrimonio
    pat = _compute_patrimonio()
    with get_db() as db:
        # «Me deben» y «Debo» viven en est_prestamos (OTORGADO / RECIBIDO).
        total_owe_me = _prest.total_por_cobrar(db)
        total_i_owe  = _prest.total_por_cobrar(db, 'RECIBIDO')
    patrimonio_neto_display = pat['patrimonio_neto'] + total_owe_me - total_i_owe

    # ── Trend: patrimonio vs snapshot anterior ──
    hist = pat['historial'] or []
    pat_delta = pat_delta_pct = None
    if len(hist) >= 2 and hist[-2]['patrimonio_neto']:
        pat_delta     = pat['patrimonio_neto'] - hist[-2]['patrimonio_neto']
        pat_delta_pct = round(pat_delta / abs(hist[-2]['patrimonio_neto']) * 100, 1)

    # ── Métricas por módulo (defensivo: si una tabla falla, esa métrica no aparece) ──
    today   = today_date()
    cur_mes = today.strftime('%Y-%m')
    _nm = 1 if today.month == 12 else today.month + 1
    _ny = today.year + 1 if today.month == 12 else today.year
    mes_ini, mes_fin = f"{cur_mes}-01", f"{_ny}-{_nm:02d}-01"
    extra = {'budget': None, 'budget_risk': [], 'budget_ok_count': 0,
             'racha_meses': None, 'racha_historial': [], 'estado_sin_clasificar': 0,
             'estado_sin_clasificar_monto': 0}

    try:  # Presupuesto del mes (o el último con movimientos): ingreso, gasto, ahorro, categorías
        from modules.finanzas.budget import _calc_budget, _last_month_with_data
        with get_db() as db:
            n_cur = db.execute("SELECT COUNT(*) n FROM est_movimientos "
                               "WHERE fecha>=? AND fecha<?", (mes_ini, mes_fin)).fetchone()['n']
            bmes  = cur_mes if n_cur >= 1 else (_last_month_with_data(db) or cur_mes)
            bd    = _calc_budget(bmes, db)
        ing, gas = bd['ingreso_real'], bd['consumo']   # invertir no es gasto; un retiro tampoco lo baja
        extra['budget'] = {
            'mes': bmes, 'mes_nombre': _MESES_ES[int(bmes[5:]) - 1], 'ingreso': ing, 'gastado': gas,
            # Lo que se aparta a inversiones sí ocupa ingreso; un retiro no lo libera.
            'disponible': bd['disponible'],   # = ing − consumo − invertido (mismo que la Radiografía)
            'pct': round(gas / ing * 100) if ing else None,
            # DEPRECADO (Oikonomia v2): «lo no gastado». La tasa de ahorro
            # oficial es el bucket ahorro_deuda (lo apartado) → budget.seg.
            'ahorro_pct': round((ing - gas) / ing * 100) if ing else None,
            'dias_restantes': bd['dias_mes'] - bd['dia_actual'] if bd['es_mes_actual'] else None,
            'fuentes': len(bd['ingresos_detalle']),
        }
        b = extra['budget']
        # Ritmo: lo disponible repartido en los días que quedan (contando hoy).
        quedan = (bd['dias_mes'] - bd['dia_actual'] + 1) if bd['es_mes_actual'] else 0
        b['dias_restantes_incl_hoy'] = quedan if bd['es_mes_actual'] else None
        b['por_dia'] = round(bd['disponible'] / quedan, 2) if quedan > 0 else None
        b['seg'] = _hub_seg(bd)
        todas = _hub_budget_rows(bd, limit=None)
        extra['budget_risk'] = [r for r in todas if r['pct'] >= BUDGET_RISK_PCT]
        extra['budget_ok_count'] = len(todas) - len(extra['budget_risk'])
    except Exception:
        pass

    try:  # Racha de meses bajo presupuesto (los últimos 6, como en /finanzas/budget/)
        from modules.finanzas.budget import _racha_bajo_presupuesto
        with get_db() as db:
            extra['racha_meses'], extra['racha_historial'] = _racha_bajo_presupuesto(db, bmes, max_meses=6)
    except Exception:
        pass

    try:  # Estado de cuenta: depósitos pendientes de clasificar (afectan el ingreso)
        with get_db() as db:
            r = db.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(ABS(monto)),0) s FROM est_movimientos "
                "WHERE tipo='INGRESO' AND categoria IN ('DEPOSITO','SPEI_RECIBIDO')").fetchone()
            extra['estado_sin_clasificar'] = r['n']
            extra['estado_sin_clasificar_monto'] = round(r['s'], 2)
    except Exception:
        pass

    from modules.finanzas.salud import MONEDAS_EXTRANJERAS
    inversiones = sum(c['saldo'] for c in pat['cuentas']
                      if c['tipo'] == 'inversion' and c['moneda'] not in MONEDAS_EXTRANJERAS)
    debts = _hub_debts(pat['cuentas'])
    minimos_30d = round(sum(d['minimo'] or 0 for d in debts
                            if d['dias'] is not None and d['dias'] <= 30 and not d.get('pagado')), 2)
    try:
        next_step = _hub_next_step(debts, extra.get('estado_sin_clasificar') or 0,
                                   extra.get('estado_sin_clasificar_monto') or 0)
    except Exception:
        next_step = None

    return render_template('finanzas/hub.html',
        patrimonio_neto = patrimonio_neto_display,
        total_activos   = pat['total_activos'],
        total_pasivos   = pat['total_pasivos'],
        liquido         = pat['liquido'],
        total_bienes    = pat['total_bienes'],
        inversiones     = inversiones,
        deudas_neto     = total_owe_me - total_i_owe,
        owe_me_total    = total_owe_me,
        i_owe_total     = total_i_owe,
        historial       = pat['historial'],
        pat_delta       = pat_delta,
        pat_delta_pct   = pat_delta_pct,
        debts           = debts,
        debts_total     = sum(d['saldo'] for d in debts),
        minimos_30d     = minimos_30d,
        mes_actual_nombre = _MESES_ES[today.month - 1],
        depositos_url   = DEPOSITOS_SIN_CLASIFICAR_URL,
        next_step       = next_step,
        alerts=payment_alerts(), today=today_str(),
        **extra,
    )


@finanzas_bp.route('/api/pago-ciclo', methods=['POST', 'DELETE'])
def pago_ciclo():
    """Marca (POST) o desmarca (DELETE) el ciclo actual de una tarjeta como
    pagado. Body: {cuenta, monto?}; cuenta = el `match` de PAY_DAYS."""
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    from . import pagos_ciclo
    d = request.get_json(silent=True) or {}
    cuenta = (d.get('cuenta') or '').strip().lower()
    try:
        with get_db() as db:
            if request.method == 'POST':
                monto = safe_float(d.get('monto')) if d.get('monto') not in (None, '') else None
                fila = pagos_ciclo.marcar(db, cuenta, monto)
                db.commit()
                return jsonify({'ok': True, 'pago': fila})
            quitado = pagos_ciclo.deshacer(db, cuenta)
            db.commit()
            return jsonify({'ok': True, 'quitado': quitado})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@finanzas_bp.route('/api/debt', methods=['POST'])
def add_debt():
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    d = request.json
    amount = safe_float(d.get('amount'), min_val=0.01)
    if not amount:
        return jsonify({'error': 'Monto inválido'}), 400
    person  = clean_str(d.get('person'), 100)
    concept = clean_str(d.get('concept'), 300)
    dtype   = clean_str(d.get('type'), 20)
    with get_db() as db:
        if dtype in ('owe_me', 'i_owe'):   # viven en est_prestamos
            try:
                _prest.crear(db, person, monto=amount, concepto=concept,
                             direccion='OTORGADO' if dtype == 'owe_me' else 'RECIBIDO',
                             pago_cat=clean_str(d.get('pago_cat'), 40) or None)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            db.commit()
            return jsonify({'ok': True})
        db.execute("""INSERT INTO debts
            (type, person, concept, amount, monto_total, monto_restante, created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (dtype, person, concept, amount, amount, amount, datetime.now().isoformat()))
        db.commit()
    return jsonify({'ok':True})


@finanzas_bp.route('/api/debt/<int:did>/abonar', methods=['POST'])
def abonar_debt(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    amount = safe_float(request.json.get('amount', 0), min_val=0.0)
    note   = clean_str(request.json.get('note', ''), 300)
    # Depósitos del banco que son este abono (opcional): ids de movimiento.
    try:
        mov_ids = [int(x) for x in (request.json.get('movimiento_ids') or []) if str(x).strip()]
    except (TypeError, ValueError):
        return jsonify({'error': 'Los ids de movimiento deben ser números'}), 400
    with get_db() as db:
        debt = db.execute("SELECT * FROM debts WHERE id=?", (did,)).fetchone()
        if not debt: return jsonify({'error':'not found'}), 404
        if amount <= 0:
            return jsonify({'error':'El monto debe ser mayor a 0'}), 400
        if amount > debt['monto_restante']:
            return jsonify({'error': f'El abono (${amount:.2f}) supera el restante (${debt["monto_restante"]:.2f})'}), 400

        nuevo_restante = round(debt['monto_restante'] - amount, 2)
        settled = 1 if nuevo_restante <= 0 else 0

        db.execute("UPDATE debts SET monto_restante=?, settled=? WHERE id=?",
                   (nuevo_restante, settled, did))
        pid = db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?,?,?,?)",
                         (did, amount, note, datetime.now().isoformat())).lastrowid
        try:
            for mid in mov_ids:
                _comp.ligar(db, pid, mid)
        except ValueError as e:
            db.rollback()
            return jsonify({'error': str(e)}), 400
        db.commit()

        updated = db.execute("SELECT * FROM debts WHERE id=?", (did,)).fetchone()
        payments = db.execute(
            "SELECT * FROM debt_payments WHERE debt_id=? ORDER BY paid_at DESC", (did,)
        ).fetchall()

    return jsonify({
        'ok': True,
        'settled': bool(settled),
        'monto_restante': nuevo_restante,
        'monto_total': debt['monto_total'],
        'pct': round((1 - nuevo_restante / debt['monto_total']) * 100, 1) if debt['monto_total'] > 0 else 100,
        'payments': [dict(p) for p in payments],
    })


@finanzas_bp.route('/api/debt/<int:did>/payments')
def debt_payments(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        payments = db.execute(
            "SELECT * FROM debt_payments WHERE debt_id=? ORDER BY paid_at DESC", (did,)
        ).fetchall()
    return jsonify({'payments': [dict(p) for p in payments]})


def _debt_hist(db, d) -> dict:
    """Una deuda con sus abonos/cobros en orden cronológico (historial)."""
    pagos = [{**dict(p), 'movimientos': _comp.movs_de_pago(db, p['id'])} for p in db.execute(
        "SELECT id, amount, note, paid_at FROM debt_payments WHERE debt_id=? ORDER BY paid_at, id", (d['id'],))]
    return {'id': d['id'], 'type': d['type'], 'person': d['person'], 'concept': d['concept'] or '',
            'monto_total': d['monto_total'], 'monto_restante': d['monto_restante'],
            'settled': bool(d['settled']), 'created_at': d['created_at'], 'payments': pagos,
            'pagado': round(sum(p['amount'] for p in pagos), 2)}


@finanzas_bp.route('/api/debt/<int:did>/historial')
def debt_historial(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        d = db.execute("SELECT * FROM debts WHERE id=?", (did,)).fetchone()
        if not d: return jsonify({'error': 'not found'}), 404
        return jsonify(_debt_hist(db, d))


@finanzas_bp.route('/api/debts/historial')
def debts_historial():
    """Deudas ya liquidadas, la más reciente primero, con sus pagos."""
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        # Los compromisos de debts ya se migraron a est_prestamos (debts queda de respaldo).
        debts = _prest.pagados_salud(db)
        debts.sort(key=lambda d: (d['ultimo'] or '')[:10], reverse=True)
        return jsonify({'debts': debts})


@finanzas_bp.route('/api/debt/<int:did>/settle', methods=['POST'])
def settle_debt(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        d = db.execute("SELECT monto_restante FROM debts WHERE id=?", (did,)).fetchone()
        # Lo que faltaba queda como último pago, para que el historial cuadre.
        if d and (d['monto_restante'] or 0) > 0:
            db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?,?,?,?)",
                       (did, d['monto_restante'], 'Liquidado', datetime.now().isoformat()))
        db.execute("UPDATE debts SET settled=1, monto_restante=0 WHERE id=?", (did,))
        db.commit()
    return jsonify({'ok':True})


@finanzas_bp.route('/api/debt-payment/<int:pid>/ligar', methods=['POST'])
def ligar_abono(pid):
    """Liga un abono ya registrado a su depósito del banco (id de movimiento)."""
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    try:
        mid = int((request.json or {}).get('movimiento_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Falta el id del movimiento'}), 400
    with get_db() as db:
        if not db.execute("SELECT 1 FROM debt_payments WHERE id=?", (pid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        try:
            _comp.ligar(db, pid, mid)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        db.commit()
        return jsonify({'ok': True, 'movimientos': _comp.movs_de_pago(db, pid)})


@finanzas_bp.route('/api/debt-payment/movimiento/<int:mid>', methods=['DELETE'])
def desligar_abono(mid):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        _comp.desligar(db, mid)
        db.commit()
    return jsonify({'ok': True})


@finanzas_bp.route('/api/debts/sugerencias')
def debts_sugerencias():
    """Depósitos de alguien con un compromiso abierto: posibles abonos (no se aplican solos)."""
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        return jsonify({'sugerencias': _prest.sugerencias(db)})


@finanzas_bp.route('/api/debts/sugerencias/<int:mid>/descartar', methods=['POST'])
def debts_sugerencia_descartar(mid):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        _prest.descartar_sugerencia(db, mid)
        db.commit()
    return jsonify({'ok': True})


# ── «Me deben» desde Salud financiera: viven en Por cobrar (est_prestamos) ──
# Misma forma que las rutas de debts de arriba para que Salud las use igual.

@finanzas_bp.route('/api/prestamo/<int:pid>/historial')
def prestamo_historial(pid):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        h = _prest.historial(db, pid)
    return jsonify(h) if h else (jsonify({'error': 'not found'}), 404)


@finanzas_bp.route('/api/prestamo/<int:pid>/candidatos')
def prestamo_candidatos(pid):
    """Depósitos que pueden ser abonos (primero los de la cuenta de la persona)."""
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        return jsonify({'depositos': _prest.candidatos_abono(db, pid)})


@finanzas_bp.route('/api/prestamo/<int:pid>/abonar', methods=['POST'])
def prestamo_abonar(pid):
    """Con depósitos elegidos se ligan como devolución (su monto es el abono);
    sin depósitos es un abono manual por `amount`."""
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    d = request.json or {}
    try:
        mov_ids = sorted({int(x) for x in (d.get('movimiento_ids') or []) if str(x).strip()})
    except (TypeError, ValueError):
        return jsonify({'error': 'Los depósitos elegidos no son válidos.'}), 400
    with get_db() as db:
        p = _prest.uno(db, pid)
        if not p:
            return jsonify({'error': 'not found'}), 404
        try:
            if mov_ids:
                # get_db() no tiene rollback: todo se valida antes de escribir.
                movs = [db.execute("SELECT id, tipo, ABS(monto) AS monto FROM est_movimientos WHERE id=?", (m,)).fetchone()
                        for m in mov_ids]
                total = sum(m['monto'] for m in movs if m)
                if total > p['pendiente'] + 0.01:
                    raise ValueError(f'Los depósitos suman ${total:,.2f} y solo quedan ${p["pendiente"]:,.2f} pendientes.')
                for m in mov_ids:
                    if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (m,)).fetchone():
                        raise ValueError(f'El depósito {m} ya está ligado a un préstamo.')
                for m in mov_ids:
                    _prest.ligar_devolucion(db, pid, m)
            else:
                _prest.abonar(db, pid, safe_float(d.get('amount'), min_val=0.0), clean_str(d.get('note', ''), 300))
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        db.commit()
        p = _prest.uno(db, pid)
    return jsonify({'ok': True, 'settled': p['estado'] == _prest.PAGADO, 'monto_restante': p['pendiente']})


@finanzas_bp.route('/api/prestamo/<int:pid>/settle', methods=['POST'])
def prestamo_settle(pid):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        try:
            _prest.liquidar(db, pid)
        except ValueError as e:
            return jsonify({'error': str(e)}), 404
        db.commit()
    return jsonify({'ok': True})


@finanzas_bp.route('/api/prestamo/<int:pid>', methods=['DELETE'])
def prestamo_delete(pid):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        _prest.borrar(db, pid)
        db.commit()
    return jsonify({'ok': True})


@finanzas_bp.route('/api/debt/<int:did>', methods=['DELETE'])
def delete_debt(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        for (pid,) in db.execute("SELECT id FROM debt_payments WHERE debt_id=?", (did,)).fetchall():
            for (mid,) in db.execute("SELECT movimiento_id FROM debt_payment_movs WHERE payment_id=?", (pid,)).fetchall():
                _comp.desligar(db, mid)
        db.execute("DELETE FROM debt_payments WHERE debt_id=?", (did,))
        db.execute("DELETE FROM debts WHERE id=?", (did,))
        db.commit()
    return jsonify({'ok':True})


@finanzas_bp.route('/admin/seed-budgets', methods=['POST'])
def seed_budgets():
    """Carga los presupuestos reales del Excel SG BUDGET 2026.
    Idempotente — se puede ejecutar múltiples veces sin duplicar."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    # Cifras exactas del Excel SG BUDGET 2026 (50-30-20)
    # Ingreso mensual: $22,796 | Excedente: $110.75
    # Límites del plan acordado (antes: cifras del Excel SG BUDGET 2026 con
    # categorías que ya no existen, p. ej. CASA/HOGAR o MENSUALIDAD).
    from modules.finanzas.presupuesto_plan import PLAN_LIMITES
    budgets = PLAN_LIMITES
    with get_db() as db:
        # Limpiar y recargar desde cero para garantizar cifras exactas
        db.execute("DELETE FROM est_budgets")
        for cat, nombre, limite in budgets:
            db.execute(
                "INSERT INTO est_budgets (categoria, nombre, limite, periodo) VALUES (?,?,?,'mensual')",
                (cat, nombre, limite)
            )
        db.commit()
        rows = db.execute("SELECT categoria, limite FROM est_budgets ORDER BY id").fetchall()
    return jsonify({'ok': True, 'loaded': len(budgets), 'budgets': [dict(r) for r in rows]})


@finanzas_bp.route('/admin/apply-migrations', methods=['GET', 'POST'])
def apply_migrations():
    """Aplica migraciones de datos 2026 a la DB activa (local o Railway).
    Idempotente — se puede ejecutar varias veces sin duplicar ni corromper."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403

    log = []
    with get_db() as db:

        # ── 1. Presupuesto exacto Excel 2026 (50-30-20) ───────────────────────
        db.execute("DELETE FROM est_budgets")
        from modules.finanzas.presupuesto_plan import PLAN_LIMITES
        budgets = PLAN_LIMITES
        for cat, nombre, limite in budgets:
            db.execute(
                "INSERT INTO est_budgets (categoria, nombre, limite, periodo) VALUES (?,?,?,'mensual')",
                (cat, nombre, limite)
            )
        log.append(f'est_budgets: {len(budgets)} categorías cargadas')

        # ── 2. Keyword rules ──────────────────────────────────────────────────
        keywords = [
            ('NU MEXICO',               'VIVIENDA', 'Renta'),
            ('TARJETA DE TERCEROS MBAN','VIVIENDA',  'Renta'),
            ('5420150016315198',         'VIVIENDA', 'Renta'),
            ('TOTAL PLAY CR MEX',        'VIVIENDA', 'Internet'),
            ('TOTAL PLAY',               'VIVIENDA', 'Internet'),
            ('TOTALPLAY',                'VIVIENDA', 'Internet'),
            ('CFE SUM SERV',             'VIVIENDA', 'Luz'),
            ('CFE',                      'VIVIENDA', 'Luz'),
            ('MI ATT A APP',             'DIGITAL',  'Celular'),
            ('ATTAPP',                   'DIGITAL',  'Celular'),
            ('ATTAPP MICROS',            'DIGITAL',  'Celular'),
        ]
        for kw, cat, sub in keywords:
            db.execute(
                "INSERT OR REPLACE INTO est_keywords (keyword, categoria, subcategoria) VALUES (?,?,?)",
                (kw, cat, sub)
            )
        log.append(f'est_keywords: {len(keywords)} reglas aseguradas')

        # ── 3b. Reclasificar TOTAL PLAY → VIVIENDA/Internet ─────────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='VIVIENDA', subcategoria='Internet'
            WHERE (UPPER(descripcion) LIKE '%TOTAL PLAY%'
                OR UPPER(descripcion) LIKE '%TOTALPLAY%')
        """)
        log.append(f'TOTAL PLAY → VIVIENDA/Internet: {r.rowcount} transacciones reclasificadas')

        # ── 3d. Reclasificar CFE → VIVIENDA/Luz ─────────────────────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='VIVIENDA', subcategoria='Luz'
            WHERE UPPER(descripcion) LIKE '%CFE%'
              AND tipo='GASTO'
        """)
        log.append(f'CFE → VIVIENDA/Luz: {r.rowcount} transacciones reclasificadas')

        # ── 3c. Reclasificar ATT saldo telefono → DIGITAL/Celular ────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='DIGITAL', subcategoria='Celular'
            WHERE (UPPER(descripcion) LIKE '%MI ATT A APP%'
                OR UPPER(descripcion) LIKE '%ATTAPP%')
              AND tipo='GASTO'
        """)
        log.append(f'ATT saldo telefono → DIGITAL/Celular: {r.rowcount} transacciones reclasificadas')

        # ── 3a. Reclasificar aportación de renta Nu Mexico ────────────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='VIVIENDA', subcategoria='Renta'
            WHERE tipo='INGRESO'
              AND UPPER(descripcion) LIKE '%NU MEXICO%'
              AND UPPER(descripcion) LIKE '%RECIBIDO%'
        """)
        log.append(f'Aportación renta Nu Mexico → VIVIENDA/Renta: {r.rowcount} transacciones reclasificadas')

        # ── 4. Reclasificar pagos de renta depto 807 ─────────────────────────
        # Patron: PAGO TARJETA DE TERCEROS a cuenta 5420150016315198 (MBAN)
        # Monto ~12,000-13,000, dias 1-12 de cada mes, BBVA_DEB
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='VIVIENDA',
                subcategoria='Renta',
                tipo='GASTO',
                mi_parte=6000.0
            WHERE banco='BBVA_DEB'
              AND UPPER(descripcion) LIKE '%TARJETA DE TERCEROS%'
              AND monto BETWEEN 11000 AND 14000
              AND CAST(substr(fecha,9,2) AS INTEGER) BETWEEN 1 AND 12
              AND NOT (monto = 13000 AND substr(fecha,1,7) = '2025-11')
        """)
        log.append(f'Renta depto 807: {r.rowcount} pagos mensuales reclasificados (mi_parte=6000)')

        # Nov-2025: depósito inicial — mi_parte = 7000. El depósito se
        # distingue por mi_parte (7000 vs 6000), no por su propia
        # subcategoria -- "Renta + deposito"/"Renta depto 807 + deposito"
        # eran variantes de lo mismo que el usuario pidió unificar
        # ("tambien renta depto 807"), igual que Aportación renta/Renta
        # del lado ingreso.
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='VIVIENDA',
                subcategoria='Renta',
                tipo='GASTO',
                mi_parte=7000.0
            WHERE banco='BBVA_DEB'
              AND UPPER(descripcion) LIKE '%TARJETA DE TERCEROS%'
              AND monto = 13000
              AND substr(fecha,1,7) = '2025-11'
        """)
        log.append(f'Renta nov-2025 deposito: {r.rowcount} fila(s) mi_parte=7000')

        db.commit()

    return jsonify({'ok': True, 'migrations': log})


@finanzas_bp.route('/admin/fix-invex-spei', methods=['POST'])
def fix_invex_spei():
    """Pasa todos los SPEI ENVIADO INVEX a PAGO_TDC / MOVIMIENTO_INTERNO (misma
    regla que el import y «Aplicar reglas»)."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    from modules.finanzas.estados.routes import _corregir_spei_invex
    with get_db() as db:
        fixed = _corregir_spei_invex(db)
        db.commit()
    return jsonify({'ok': True, 'fixed': fixed})


@finanzas_bp.route('/admin/limpiar-duplicados', methods=['POST'])
def limpiar_duplicados():
    """Elimina duplicados de est_movimientos usando clave (fecha, monto, banco, tipo).
    Corre sobre la DB activa — sirve tanto en local como en Railway."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        # 1) Duplicados exactos por (fecha, monto, banco, tipo) — monto > 0
        dups = db.execute('''
            SELECT MIN(id) keep_id, GROUP_CONCAT(id) all_ids
            FROM est_movimientos
            WHERE monto > 0
            GROUP BY fecha, monto, banco, tipo
            HAVING COUNT(*) > 1
        ''').fetchall()

        deleted = 0
        for row in dups:
            all_ids = [int(x) for x in row['all_ids'].split(',')]
            to_del  = [x for x in all_ids if x != row['keep_id']]
            for did in to_del:
                db.execute("DELETE FROM est_movimientos WHERE id=?", (did,))
                deleted += 1

        db.commit()

    return jsonify({'ok': True, 'deleted': deleted})


@finanzas_bp.route('/api/oikonomia-summary')
def oikonomia_summary():
    if not session.get('fin_ok'):
        return jsonify({'locked': True})
    from modules.finanzas.salud import _compute_patrimonio
    pat  = _compute_patrimonio()
    hist = pat['historial']
    if len(hist) >= 2 and hist[-2]['patrimonio_neto']:
        delta     = pat['patrimonio_neto'] - hist[-2]['patrimonio_neto']
        delta_pct = round(delta / abs(hist[-2]['patrimonio_neto']) * 100, 1)
    else:
        delta, delta_pct = 0, 0
    mes = today_date().replace(day=1).isoformat()
    # Gasto con la misma regla que Estados de cuenta (_PAGO_CATS): antes este
    # widget excluía FINANZAS entera y escondía transferencias que en
    # realidad eran gasto (pedido del usuario 2026-09-26).
    from modules.finanzas.estados.routes import _PAGO_CATS, _MONTO, _INGRESO_EXCLUIR_SQL
    with get_db() as db:
        flujo = db.execute(f"""
            SELECT
              SUM(CASE WHEN tipo='INGRESO' AND {_INGRESO_EXCLUIR_SQL}
                       THEN monto ELSE 0 END) AS ingreso,
              SUM(CASE WHEN tipo='GASTO' AND {_PAGO_CATS}
                       THEN {_MONTO} ELSE 0 END) AS gasto
            FROM est_movimientos WHERE fecha >= ?""", (mes,)).fetchone()
        n_cuentas = db.execute(
            "SELECT COUNT(*) c FROM salud_cuentas WHERE activa=1"
        ).fetchone()['c']
        n_bancos  = db.execute(
            "SELECT COUNT(DISTINCT banco) c FROM est_movimientos"
        ).fetchone()['c']
    return jsonify({
        'patrimonio_neto': pat['patrimonio_neto'],
        'activos':         pat['total_activos'],
        'pasivos':         pat['total_pasivos'],
        'liquido':         pat['liquido'],
        'trend_delta':     delta,
        'trend_pct':       delta_pct,
        'spark':           [h['patrimonio_neto'] for h in hist[-8:]],
        'flujo_ingreso':   flujo['ingreso'] or 0,
        'flujo_gasto':     flujo['gasto']   or 0,
        'n_cuentas':       n_cuentas,
        'n_bancos':        n_bancos,
        'pay_alerts':      payment_alerts(),
    })


