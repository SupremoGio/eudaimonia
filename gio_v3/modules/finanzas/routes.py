from werkzeug.security import check_password_hash, generate_password_hash
from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from datetime import date, datetime
from utils import today_str, today_date

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
    mes_actual = today_date().strftime('%Y-%m')
    with get_db() as db:
        owe_me  = db.execute("SELECT * FROM debts WHERE type='owe_me' AND settled=0 ORDER BY id DESC").fetchall()
        i_owe   = db.execute("SELECT * FROM debts WHERE type='i_owe'  AND settled=0 ORDER BY id DESC").fetchall()
        settled = db.execute("SELECT * FROM debts WHERE settled=1 ORDER BY id DESC LIMIT 10").fetchall()
        pay_map = {}
        for row in db.execute("SELECT * FROM debt_payments ORDER BY paid_at DESC").fetchall():
            pay_map.setdefault(row["debt_id"], []).append(dict(row))

        # Budget del mes actual desde el módulo de planeación
        budget_mes_row = db.execute("SELECT * FROM budget_meses WHERE mes=?", (mes_actual,)).fetchone()
        budget_items = []
        if budget_mes_row:
            budget_items = [dict(r) for r in db.execute(
                "SELECT * FROM budget_items WHERE budget_id=? ORDER BY categoria, nombre",
                (budget_mes_row['id'],)
            ).fetchall()]

    total_budget = sum(i['monto_estimado'] or 0 for i in budget_items)
    total_spent  = sum(i['monto_real'] or 0 for i in budget_items)

    return render_template('finanzas/index.html',
        owe_me=list(owe_me), i_owe=list(i_owe), settled=list(settled),
        pay_map=pay_map,
        budget_items=budget_items,
        mes_actual=mes_actual,
        total_owe_me  = sum(d['monto_restante'] for d in owe_me),
        total_i_owe   = sum(d['monto_restante'] for d in i_owe),
        total_original_owe_me = sum(d['monto_total'] for d in owe_me),
        total_original_i_owe  = sum(d['monto_total'] for d in i_owe),
        total_budget  = total_budget,
        total_spent   = total_spent,
        alerts=payment_alerts(), today=today_str(),
    )


@finanzas_bp.route('/unlock', methods=['POST'])
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
    amount = float(d['amount'])
    with get_db() as db:
        db.execute("""INSERT INTO debts
            (type, person, concept, amount, monto_total, monto_restante, created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (d['type'], d['person'], d['concept'], amount, amount, amount, datetime.now().isoformat()))
        db.commit()
    return jsonify({'ok':True})


@finanzas_bp.route('/api/debt/<int:did>/abonar', methods=['POST'])
def abonar_debt(did):
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    amount = float(request.json.get('amount', 0))
    note   = request.json.get('note', '')
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


@finanzas_bp.route('/api/budget', methods=['POST'])
def update_budget():
    if not session.get('fin_ok'): return jsonify({'error':'locked'}), 403
    d = request.json
    with get_db() as db:
        db.execute("UPDATE budget_categories SET budgeted=?, spent=? WHERE id=?",
                   (float(d['budgeted']), float(d['spent']), int(d['id'])))
        db.commit()
    return jsonify({'ok':True})
