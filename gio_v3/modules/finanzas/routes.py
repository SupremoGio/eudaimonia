from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from datetime import date, datetime
from collections import defaultdict
from utils import today_str, today_date, clean_str, safe_float

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


def payment_alerts():
    d = today_date().day
    return [{'label': p['label']} for p in PAY_DAYS if p['day'] == d]


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
    out = []
    for c in cuentas:
        if c['tipo'] not in TIPOS_PASIVO or c['moneda'] in MONEDAS_EXTRANJERAS or not c['saldo']:
            continue
        hay = f"{c['nombre']} {c.get('institucion') or ''}".lower()
        pay = next((p for p in PAY_DAYS if p['match'] in hay), None)
        dias = _days_until(pay['day']) if pay else None
        minimo = next((v for k, v in minimos.items() if k and (k in hay or c['nombre'].lower() in k)), None)
        out.append({
            'nombre': c['nombre'],
            'sub': ' · '.join(filter(None, [TIPO_META.get(c['tipo'], {}).get('label'), c.get('institucion')])),
            'saldo': c['saldo'], 'minimo': minimo, 'dias': dias,
            'tone': None if dias is None else 'danger' if dias == 0 else 'warning' if dias <= 7 else '',
        })
    out.sort(key=lambda d: (d['dias'] is None, d['dias'] if d['dias'] is not None else 0, -d['saldo']))
    return out


def _hub_budget_rows(bd):
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
    return rows[:5]


@finanzas_bp.route('/')
def index():
    from modules.finanzas.salud import _compute_patrimonio
    pat = _compute_patrimonio()
    with get_db() as db:
        owe_me = db.execute("SELECT * FROM debts WHERE type='owe_me' AND settled=0").fetchall()
        i_owe  = db.execute("SELECT * FROM debts WHERE type='i_owe'  AND settled=0").fetchall()
    total_owe_me = sum(d['monto_restante'] for d in owe_me)
    total_i_owe  = sum(d['monto_restante'] for d in i_owe)
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
    extra = {'budget': None, 'budget_rows': []}

    try:  # Presupuesto del mes (o el último con movimientos): ingreso, gasto, ahorro, categorías
        from modules.finanzas.budget import _calc_budget, _last_month_with_data
        with get_db() as db:
            n_cur = db.execute("SELECT COUNT(*) n FROM est_movimientos "
                               "WHERE fecha>=? AND fecha<?", (mes_ini, mes_fin)).fetchone()['n']
            bmes  = cur_mes if n_cur >= 1 else (_last_month_with_data(db) or cur_mes)
            bd    = _calc_budget(bmes, db)
        ing, gas = bd['ingreso_real'], bd['total_gastado']
        extra['budget'] = {
            'mes': bmes, 'mes_nombre': _MESES_ES[int(bmes[5:]) - 1], 'ingreso': ing, 'gastado': gas,
            'disponible': bd['disponible'], 'pct': round(gas / ing * 100) if ing else None,
            'ahorro_pct': round((ing - gas) / ing * 100) if ing else None,
            'dias_restantes': bd['dias_mes'] - bd['dia_actual'] if bd['es_mes_actual'] else None,
            'fuentes': len(bd['ingresos_detalle']),
        }
        extra['budget_rows'] = _hub_budget_rows(bd)
    except Exception:
        pass

    try:  # Estado de cuenta: ingresos pendientes de clasificar + movs del mes
        with get_db() as db:
            extra['estado_sin_clasificar'] = db.execute(
                "SELECT COUNT(*) n FROM est_movimientos "
                "WHERE tipo='INGRESO' AND categoria IN ('DEPOSITO','SPEI_RECIBIDO')").fetchone()['n']
            extra['estado_total_movs'] = db.execute(
                "SELECT COUNT(*) n FROM est_movimientos WHERE fecha>=? AND fecha<?",
                (mes_ini, mes_fin)).fetchone()['n']
    except Exception:
        pass

    try:  # Consumo: gasto del mes (misma fuente que la página de Consumo)
        with get_db() as db:
            extra['consumo_mes'] = round(db.execute(
                "SELECT COALESCE(SUM(precio_total),0) s FROM consumo_compras "
                "WHERE fecha_compra >= ?", (mes_ini,)).fetchone()['s'], 2)
    except Exception:
        pass

    from modules.finanzas.salud import MONEDAS_EXTRANJERAS
    inversiones = sum(c['saldo'] for c in pat['cuentas']
                      if c['tipo'] == 'inversion' and c['moneda'] not in MONEDAS_EXTRANJERAS)
    debts = _hub_debts(pat['cuentas'])

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
        alerts=payment_alerts(), today=today_str(),
        **extra,
    )


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
        db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?,?,?,?)",
                   (did, amount, note, datetime.now().isoformat()))
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


@finanzas_bp.route('/api/debt/<int:did>/settle', methods=['POST'])
def settle_debt(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
        db.execute("UPDATE debts SET settled=1, monto_restante=0 WHERE id=?", (did,))
        db.commit()
    return jsonify({'ok':True})


@finanzas_bp.route('/api/debt/<int:did>', methods=['DELETE'])
def delete_debt(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    with get_db() as db:
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
    with get_db() as db:
        flujo = db.execute("""
            SELECT
              SUM(CASE WHEN tipo='INGRESO'
                        AND categoria NOT IN ('TRANSFERENCIA','PAGO_TDC','RETIRO','DEPOSITO','SPEI_RECIBIDO','FINANZAS')
                       THEN monto ELSE 0 END) AS ingreso,
              SUM(CASE WHEN tipo='GASTO' AND categoria NOT IN ('PAGO_TDC','PAGO','FINANZAS')
                       THEN COALESCE(mi_parte, monto) ELSE 0 END) AS gasto
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


