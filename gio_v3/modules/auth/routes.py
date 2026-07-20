from flask import Blueprint, render_template, request, jsonify, session, redirect
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db
from extensions import limiter

auth_bp = Blueprint('auth', __name__, template_folder='../../templates')


def _get_pass_hash():
    with get_db() as db:
        row = db.execute(
            "SELECT value FROM app_settings WHERE key='app_pass_hash'"
        ).fetchone()
        if row:
            return row['value']
        # Migración: si ya existía una contraseña de Finanzas (el candado por
        # módulo que reemplaza este login general), se reutiliza como la
        # contraseña general para que no se pierda el acceso ya configurado.
        legacy = db.execute(
            "SELECT value FROM app_settings WHERE key='finanzas_pass_hash'"
        ).fetchone()
        if not legacy:
            return None
        db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_pass_hash', ?)",
            (legacy['value'],),
        )
        db.commit()
        return legacy['value']


def _set_pass_hash(new_hash: str):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_pass_hash', ?)",
            (new_hash,),
        )
        db.commit()


@auth_bp.route('/login')
def login_page():
    if session.get('app_ok'):
        return redirect('/')
    return render_template('auth/login.html', has_pass=bool(_get_pass_hash()))


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute; 20 per hour")
def login():
    current_hash = _get_pass_hash()
    if current_hash is None:
        return jsonify({'ok': False, 'error': 'Sin contraseña configurada'}), 503
    pw = request.get_json(force=True).get('password', '')
    if pw and check_password_hash(current_hash, pw):
        session['app_ok'] = True
        session['fin_ok'] = True  # compat: submódulos de Finanzas siguen leyendo esta bandera
        session.permanent = True
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Contraseña incorrecta'}), 401


@auth_bp.route('/login/setup', methods=['POST'])
@limiter.limit("3 per minute; 10 per hour")
def setup():
    d = request.get_json(force=True)
    new_pw = d.get('password', '')
    if not new_pw or len(new_pw) < 4:
        return jsonify({'ok': False, 'error': 'Mínimo 4 caracteres'}), 400
    current_hash = _get_pass_hash()
    if current_hash is not None and not session.get('app_ok'):
        current_pw = d.get('current_password', '')
        if not current_pw or not check_password_hash(current_hash, current_pw):
            return jsonify({'ok': False, 'error': 'Contraseña actual incorrecta'}), 401
    _set_pass_hash(generate_password_hash(new_pw))
    session['app_ok'] = True
    session['fin_ok'] = True
    session.permanent = True
    return jsonify({'ok': True})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})
