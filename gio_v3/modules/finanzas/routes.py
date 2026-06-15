from werkzeug.security import check_password_hash, generate_password_hash
from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from extensions import limiter
from datetime import date, datetime
from collections import defaultdict
from utils import today_str, today_date, clean_str, safe_float

finanzas_bp = Blueprint('finanzas', __name__, template_folder='../../templates')


def _get_pass_hash():
    with get_db() as db:
        row = db.execute(
            "SELECT value FROM app_settings WHERE key='finanzas_pass_hash'"
        ).fetchone()
        return row['value'] if row else None


def _set_pass_hash(new_hash: str):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('finanzas_pass_hash', ?)",
            (new_hash,)
        )
        db.commit()


def payment_alerts():
    d = today_date().day
    alerts = []
    if d == 15: alerts += [{"label":"BBVA","color":"#c5a36c"},{"label":"Invex","color":"#a78bfa"}]
    if d == 30: alerts.append({"label":"HSBC","color":"#60a5fa"})
    return alerts


@finanzas_bp.route('/')
def index():
    if not session.get('fin_ok'):
        return render_template('finanzas/lock.html', has_pass=bool(_get_pass_hash()))
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
    extra = {}

    try:  # Presupuesto: disponible + % del ingreso usado (reusa _calc_budget)
        from modules.finanzas.budget import _calc_budget, _last_month_with_data
        with get_db() as db:
            n_cur = db.execute("SELECT COUNT(*) n FROM est_movimientos "
                               "WHERE fecha>=? AND fecha<?", (mes_ini, mes_fin)).fetchone()['n']
            bmes  = cur_mes if n_cur >= 5 else (_last_month_with_data(db) or cur_mes)
            bd    = _calc_budget(bmes, db)
        extra['presupuesto_disponible'] = bd['disponible']
        if bd['ingreso_real']:
            extra['presupuesto_pct'] = round(bd['total_gastado'] / bd['ingreso_real'] * 100)
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

    return render_template('finanzas/hub.html',
        patrimonio_neto = patrimonio_neto_display,
        total_activos   = pat['total_activos'],
        total_pasivos   = pat['total_pasivos'],
        liquido         = pat['liquido'],
        total_bienes    = pat['total_bienes'],
        deudas_neto     = total_owe_me - total_i_owe,
        historial       = pat['historial'],
        pat_delta       = pat_delta,
        pat_delta_pct   = pat_delta_pct,
        alerts=payment_alerts(), today=today_str(),
        **extra,
    )


@finanzas_bp.route('/unlock', methods=['POST'])
@limiter.limit("5 per minute; 20 per hour")
def unlock():
    current_hash = _get_pass_hash()
    if current_hash is None:
        return jsonify({'ok': False, 'error': 'Sin contraseña configurada'}), 503
    pw = request.json.get('password', '')
    if pw and check_password_hash(current_hash, pw):
        session['fin_ok'] = True
        session.permanent = True
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Contraseña incorrecta'}), 401


@finanzas_bp.route('/setup-password', methods=['POST'])
@limiter.limit("3 per minute; 10 per hour")
def setup_password():
    d = request.get_json(force=True)
    new_pw = d.get('password', '')
    if not new_pw or len(new_pw) < 4:
        return jsonify({'ok': False, 'error': 'Mínimo 4 caracteres'}), 400
    current_hash = _get_pass_hash()
    if current_hash is not None and not session.get('fin_ok'):
        current_pw = d.get('current_password', '')
        if not current_pw or not check_password_hash(current_hash, current_pw):
            return jsonify({'ok': False, 'error': 'Contraseña actual incorrecta'}), 401
    _set_pass_hash(generate_password_hash(new_pw))
    session['fin_ok'] = True
    session.permanent = True
    return jsonify({'ok': True})


@finanzas_bp.route('/lock', methods=['POST'])
def lock():
    session.pop('fin_ok', None)
    return jsonify({'ok':True})


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
    budgets = [
        # ── NECESIDADES (50%) — total $14,385.25 ──────────────────────
        ('CASA/HOGAR',    'Vivienda',           6000.00),  # Alquiler
        ('SERVICIOS',     'Servicios',          1429.84),  # Agua+Luz+Internet+Gas+Garrafón
        ('GASOLINA/AUTO', 'Gasolina / Auto',    1955.41),  # Seguro+Gasolina
        ('VIVERES/SUPER', 'Víveres / Súper',    2500.00),  # Víveres+Carnes
        ('SALUD',         'Personal / Salud',    300.00),  # Saldo Cel+Corte cabello
        ('MENSUALIDAD',   'Mensualidad TDC',    2200.00),  # Mensualidad TDC
        # ── DESEOS (30%) — total $4,000.00 ───────────────────────────
        ('SALSA',          'Salsa / Baile',      700.00),
        ('COMIDA/REST',    'Comida / Restaurante',2000.00),
        ('ENTRETENIMIENTO','Gustos',              300.00),
        ('ROPA',           'Ropa',               500.00),
        ('GYM',            'Gym',                350.00),
        ('SUSCRIPCIONES',  'Apps / Suscripciones',150.00),
        # ── AHORRO Y DEUDAS (20%) — total $4,300.00 ──────────────────
        ('INVERSION',      'Ahorro',            4000.00),
        ('APRENDIZAJE',    'Educación',          300.00),
        # ── EXPENSE (informativo — se reembolsa, sin presupuesto) ─────
        ('EXPENSE',        'EXPENSE',              0.00),
    ]
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


@finanzas_bp.route('/admin/apply-migrations', methods=['POST'])
def apply_migrations():
    """Aplica migraciones de datos 2026 a la DB activa (local o Railway).
    Idempotente — se puede ejecutar varias veces sin duplicar ni corromper."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403

    log = []
    with get_db() as db:

        # ── 1. Presupuesto exacto Excel 2026 (50-30-20) ───────────────────────
        db.execute("DELETE FROM est_budgets")
        budgets = [
            ('CASA/HOGAR',    'Vivienda',           6000.00),
            ('SERVICIOS',     'Servicios',          1429.84),
            ('GASOLINA/AUTO', 'Gasolina / Auto',    1955.41),
            ('VIVERES/SUPER', 'Víveres / Súper',    2500.00),
            ('SALUD',         'Personal / Salud',    300.00),
            ('MENSUALIDAD',   'Mensualidad TDC',    2200.00),
            ('SALSA',         'Salsa / Baile',       700.00),
            ('COMIDA/REST',   'Comida / Restaurante',2000.00),
            ('ENTRETENIMIENTO','Gustos',              300.00),
            ('ROPA',          'Ropa',                500.00),
            ('GYM',           'Gym',                 350.00),
            ('SUSCRIPCIONES', 'Apps / Suscripciones',150.00),
            ('INVERSION',     'Ahorro',             4000.00),
            ('APRENDIZAJE',   'Educación',           300.00),
            ('EXPENSE',       'EXPENSE',               0.00),
        ]
        for cat, nombre, limite in budgets:
            db.execute(
                "INSERT INTO est_budgets (categoria, nombre, limite, periodo) VALUES (?,?,?,'mensual')",
                (cat, nombre, limite)
            )
        log.append(f'est_budgets: {len(budgets)} categorías cargadas')

        # ── 2. Keyword rules ──────────────────────────────────────────────────
        keywords = [
            ('NU MEXICO',               'APORTACION_RENTA', 'Parte renta Nu Mexico'),
            ('TARJETA DE TERCEROS MBAN','CASA/HOGAR',       'Renta depto 807'),
            ('5420150016315198',         'CASA/HOGAR',      'Renta depto 807'),
            ('TOTAL PLAY',               'CASA/HOGAR',      'Internet'),
            ('TOTALPLAY',                'CASA/HOGAR',      'Internet'),
            ('MI ATT A APP',             'SALUD',           'Saldo Celular'),
            ('ATTAPP',                   'SALUD',           'Saldo Celular'),
        ]
        for kw, cat, sub in keywords:
            db.execute(
                "INSERT OR REPLACE INTO est_keywords (keyword, categoria, subcategoria) VALUES (?,?,?)",
                (kw, cat, sub)
            )
        log.append(f'est_keywords: {len(keywords)} reglas aseguradas')

        # ── 3b. Reclasificar TOTAL PLAY → CASA/HOGAR ─────────────────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='CASA/HOGAR', subcategoria='Internet'
            WHERE (UPPER(descripcion) LIKE '%TOTAL PLAY%'
                OR UPPER(descripcion) LIKE '%TOTALPLAY%')
              AND tipo='GASTO'
        """)
        log.append(f'TOTAL PLAY → CASA/HOGAR: {r.rowcount} transacciones reclasificadas')

        # ── 3c. Reclasificar ATT saldo celular → SALUD ────────────────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='SALUD', subcategoria='Saldo Celular'
            WHERE (UPPER(descripcion) LIKE '%MI ATT A APP%'
                OR UPPER(descripcion) LIKE '%ATTAPP%')
              AND tipo='GASTO'
        """)
        log.append(f'ATT saldo celular → SALUD: {r.rowcount} transacciones reclasificadas')

        # ── 3a. Reclasificar aportación de renta Nu Mexico ────────────────────
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='APORTACION_RENTA', subcategoria='Parte renta Nu Mexico'
            WHERE tipo='INGRESO'
              AND UPPER(descripcion) LIKE '%NU MEXICO%'
              AND UPPER(descripcion) LIKE '%RECIBIDO%'
        """)
        log.append(f'APORTACION_RENTA: {r.rowcount} transacciones Nu Mexico reclasificadas')

        # ── 4. Reclasificar pagos de renta depto 807 ─────────────────────────
        # Patron: PAGO TARJETA DE TERCEROS a cuenta 5420150016315198 (MBAN)
        # Monto ~12,000-13,000, dias 1-12 de cada mes, BBVA_DEB
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='CASA/HOGAR',
                subcategoria='Renta depto 807',
                tipo='GASTO',
                mi_parte=6000.0
            WHERE banco='BBVA_DEB'
              AND UPPER(descripcion) LIKE '%TARJETA DE TERCEROS%'
              AND monto BETWEEN 11000 AND 14000
              AND CAST(substr(fecha,9,2) AS INTEGER) BETWEEN 1 AND 12
              AND subcategoria != 'Renta depto 807 + deposito'
        """)
        log.append(f'Renta depto 807: {r.rowcount} pagos mensuales reclasificados (mi_parte=6000)')

        # Nov-2025: depósito inicial — mi_parte = 7000
        r = db.execute("""
            UPDATE est_movimientos
            SET categoria='CASA/HOGAR',
                subcategoria='Renta depto 807 + deposito',
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
    """Corrige SPEI ENVIADO INVEX mal clasificados como INVERSION → PAGO_TDC."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        rows = db.execute('''
            SELECT id FROM est_movimientos
            WHERE tipo="INVERSION" AND categoria="INVEX"
              AND UPPER(descripcion) LIKE "%SPEI ENVIADO%"
        ''').fetchall()
        fixed = 0
        for r in rows:
            db.execute('''
                UPDATE est_movimientos
                SET tipo="PAGO", categoria="PAGO_TDC", subcategoria="Invex TDC"
                WHERE id=?
            ''', (r['id'],))
            fixed += 1
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
                        AND categoria NOT IN ('TRANSFERENCIA','PAGO_TDC','RETIRO','DEPOSITO','SPEI_RECIBIDO')
                       THEN monto ELSE 0 END) AS ingreso,
              SUM(CASE WHEN tipo='GASTO' AND categoria NOT IN ('PAGO_TDC','PAGO')
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


