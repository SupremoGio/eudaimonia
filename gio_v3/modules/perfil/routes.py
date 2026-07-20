import os, uuid, base64, hashlib, mimetypes
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort, Response, session, current_app
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet, InvalidToken
from database import get_db

PLACEHOLDER = '— editar —'

perfil_bp = Blueprint('perfil', __name__, template_folder='../../templates')

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'docs')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _vault_fernet():
    """Deriva una clave Fernet estable a partir de SECRET_KEY.
    Si SECRET_KEY cambia, las entradas cifradas existentes dejan de poder
    descifrarse — por eso conviene fijar SECRET_KEY en .env desde el inicio."""
    key = hashlib.sha256(current_app.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _vault_encrypt(plaintext):
    return _vault_fernet().encrypt(plaintext.encode()).decode()


def _vault_decrypt(token):
    return _vault_fernet().decrypt(token.encode()).decode()

ALLOWED_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.xml', '.zip'}


@perfil_bp.route('/')
def index():
    with get_db() as db:
        info         = db.execute("SELECT * FROM personal_info ORDER BY rowid").fetchall()
        measurements = db.execute("SELECT * FROM body_measurements ORDER BY rowid").fetchall()
        all_docs     = db.execute("SELECT * FROM profile_docs ORDER BY uploaded_at DESC").fetchall()
        reminders    = db.execute(
            "SELECT * FROM reminders WHERE is_active=1 ORDER BY COALESCE(next_date, target_date, '9999-12-31'), created_at"
        ).fetchall()
        hist_rows = db.execute(
            "SELECT key, value, recorded_at FROM body_measurements_history ORDER BY recorded_at DESC"
        ).fetchall()
        vault_rows = db.execute(
            "SELECT id, servicio, usuario, url, notas FROM password_vault ORDER BY servicio COLLATE NOCASE"
        ).fetchall()

    # Passwords nunca se descifran aquí — solo id/servicio/usuario/url/notas.
    # El password real se pide bajo demanda vía /api/vault/reveal/<id>.
    vault = [dict(v) for v in vault_rows]

    # Group docs: general (field_key IS NULL) and per-field
    docs_general = []
    docs_by_field = {}
    for d in all_docs:
        fk = d["field_key"] if "field_key" in d.keys() else None
        if fk:
            docs_by_field.setdefault(fk, []).append(d)
        else:
            docs_general.append(d)

    # Build history dict: key → last 8 entries (newest first)
    meas_history = {}
    for r in hist_rows:
        k = r["key"]
        if k not in meas_history:
            meas_history[k] = []
        if len(meas_history[k]) < 8:
            meas_history[k].append({"value": r["value"], "date": r["recorded_at"][:10]})

    reminders = [dict(r) for r in reminders]

    # ── Stats para el hero ────────────────────────────────────────────────
    campos_completos  = sum(1 for i in info if i['value'] != PLACEHOLDER)
    medidas_completas = sum(1 for m in measurements if m['value'] != PLACEHOLDER)
    horizon = (date.today() + timedelta(days=3)).isoformat()
    rem_urgentes = sum(
        1 for r in reminders
        if (r.get('next_date') or r.get('target_date')) and (r.get('next_date') or r.get('target_date')) <= horizon
    )
    stats = {
        'campos_completos':  campos_completos,
        'campos_total':      len(info),
        'medidas_completas': medidas_completas,
        'medidas_total':     len(measurements),
        'docs_total':        len(all_docs),
        'rem_total':         len(reminders),
        'rem_urgentes':      rem_urgentes,
        'vault_total':       len(vault),
    }

    return render_template('perfil/index.html',
                           info=info,
                           measurements=measurements,
                           meas_history=meas_history,
                           docs=docs_general,
                           docs_by_field=docs_by_field,
                           reminders=reminders,
                           vault=vault,
                           stats=stats)


@perfil_bp.route('/api/update', methods=['POST'])
def update():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    key = d.get('key', '').strip()
    value = d.get('value')
    if not key or value is None:
        return jsonify({'ok': False, 'error': 'key and value required'}), 400
    with get_db() as db:
        db.execute("UPDATE personal_info SET value=? WHERE key=?", (str(value), key))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/update_measurement', methods=['POST'])
def update_measurement():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    key = d.get('key', '').strip()
    value = d.get('value')
    if not key or value is None:
        return jsonify({'ok': False, 'error': 'key and value required'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute("UPDATE body_measurements SET value=? WHERE key=?", (str(value), key))
        db.execute(
            "INSERT INTO body_measurements_history (key, value, recorded_at) VALUES (?,?,?)",
            (key, str(value), now)
        )
        db.commit()
        hist = db.execute(
            "SELECT value, recorded_at FROM body_measurements_history WHERE key=? ORDER BY recorded_at DESC LIMIT 8",
            (key,)
        ).fetchall()
    history = [{"value": r["value"], "date": r["recorded_at"][:10]} for r in hist]
    return jsonify({'ok': True, 'history': history})


@perfil_bp.route('/api/upload_doc', methods=['POST'])
def upload_doc():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    f         = request.files.get('file')
    field_key = request.form.get('field_key', '').strip() or None
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    safe_original = secure_filename(f.filename) or 'archivo'
    ext = os.path.splitext(safe_original)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido'}), 400
    safe_name    = uuid.uuid4().hex + ext
    file_content = f.read()
    # Also save to filesystem as fallback for local dev
    try:
        with open(os.path.join(UPLOAD_DIR, safe_name), 'wb') as fp:
            fp.write(file_content)
    except OSError:
        pass
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO profile_docs (filename, original, uploaded_at, field_key, content) VALUES (?,?,?,?,?)",
            (safe_name, safe_original, now, field_key, file_content)
        )
        doc_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        db.commit()
    return jsonify({'ok': True, 'id': doc_id, 'filename': safe_name,
                    'original': safe_original, 'uploaded_at': now, 'field_key': field_key})


@perfil_bp.route('/api/delete_doc', methods=['POST'])
def delete_doc():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.json
    with get_db() as db:
        row = db.execute("SELECT filename FROM profile_docs WHERE id=?", (d['id'],)).fetchone()
        if not row:
            return jsonify({'ok': False}), 404
        db.execute("DELETE FROM profile_docs WHERE id=?", (d['id'],))
        db.commit()
    try:
        os.remove(os.path.join(UPLOAD_DIR, row['filename']))
    except OSError:
        pass
    return jsonify({'ok': True})


@perfil_bp.route('/docs/<filename>')
def serve_doc(filename):
    if not session.get('fin_ok'): abort(403)
    if '..' in filename or '/' in filename:
        abort(400)
    with get_db() as db:
        row = db.execute(
            "SELECT content, original FROM profile_docs WHERE filename=?", (filename,)
        ).fetchone()
    if not row:
        abort(404)
    content = row['content'] if row else None
    if content is not None:
        # Turso puede restaurar BLOBs como string base64 (datos previos al fix de _to_arg)
        if isinstance(content, str):
            try:
                import base64
                content = base64.b64decode(content)
            except Exception:
                content = None
        if content:
            mime = mimetypes.guess_type(row['original'])[0] or 'application/octet-stream'
            return Response(
                bytes(content),
                mimetype=mime,
                headers={'Content-Disposition': f'inline; filename="{row["original"]}"'}
            )
    # Fallback: filesystem local (dev). En Railway el archivo puede no existir.
    fs_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(fs_path):
        return send_from_directory(UPLOAD_DIR, filename)
    abort(404)


# ── Reminders ─────────────────────────────────────────────────────────────────

@perfil_bp.route('/api/reminders')
def get_reminders():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM reminders WHERE is_active=1 ORDER BY COALESCE(next_date, target_date, '9999-12-31'), created_at"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@perfil_bp.route('/api/reminder/add', methods=['POST'])
def add_reminder():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    desc = (d.get('description') or '').strip()
    if not desc:
        return jsonify({'ok': False, 'error': 'Descripción requerida'}), 400
    typ = d.get('type', 'unico')
    target = d.get('target_date') or None
    next_d = d.get('next_date') or target
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO reminders (description, type, freq_unit, freq_value, target_date, next_date, is_active, created_at)
               VALUES (?,?,?,?,?,?,1,?)""",
            (desc, typ,
             d.get('freq_unit', ''),
             int(d.get('freq_value') or 1),
             target, next_d, now)
        )
        rid = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        db.commit()
    return jsonify({'ok': True, 'id': rid})


@perfil_bp.route('/api/reminder/<int:rid>/done', methods=['POST'])
def complete_reminder(rid):
    from datetime import date as _date, timedelta
    from utils import today_str as _today_str
    import calendar
    today = _today_str()
    with get_db() as db:
        row = db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if row['type'] == 'unico':
            db.execute("UPDATE reminders SET is_active=0, last_done=? WHERE id=?", (today, rid))
        else:
            fv = row['freq_value'] or 1
            fu = row['freq_unit'] or 'dias'
            base = _date.fromisoformat(today)
            if fu == 'semanas':
                next_d = (base + timedelta(weeks=fv)).isoformat()
            elif fu == 'meses':
                m = base.month + fv
                y = base.year + (m - 1) // 12
                m = (m - 1) % 12 + 1
                d_max = calendar.monthrange(y, m)[1]
                next_d = _date(y, m, min(base.day, d_max)).isoformat()
            else:
                next_d = (base + timedelta(days=fv)).isoformat()
            db.execute(
                "UPDATE reminders SET last_done=?, next_date=? WHERE id=?",
                (today, next_d, rid)
            )
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/reminder/<int:rid>/delete', methods=['POST'])
def delete_reminder(rid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        db.execute("DELETE FROM reminders WHERE id=?", (rid,))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/reminder/<int:rid>/edit', methods=['POST'])
def edit_reminder(rid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    desc = (d.get('description') or '').strip()
    if not desc:
        return jsonify({'ok': False, 'error': 'Descripción requerida'}), 400
    typ = d.get('type', 'unico')
    target = d.get('target_date') or None
    next_d = d.get('next_date') or target
    with get_db() as db:
        db.execute(
            """UPDATE reminders SET description=?, type=?, freq_unit=?, freq_value=?,
               target_date=?, next_date=? WHERE id=?""",
            (desc, typ,
             d.get('freq_unit', ''),
             int(d.get('freq_value') or 1),
             target, next_d, rid)
        )
        db.commit()
    return jsonify({'ok': True})


# ── Password Vault ──────────────────────────────────────────────────────────
# Los passwords se cifran (Fernet, clave derivada de SECRET_KEY) antes de
# guardarse y solo se descifran bajo demanda vía /reveal — nunca viajan en
# el HTML inicial ni en el listado.

@perfil_bp.route('/api/vault/add', methods=['POST'])
def vault_add():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    servicio = (d.get('servicio') or '').strip()
    password = d.get('password') or ''
    if not servicio or not password:
        return jsonify({'ok': False, 'error': 'Servicio y contraseña requeridos'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO password_vault (servicio, usuario, password_enc, url, notas, created_at)
               VALUES (?,?,?,?,?,?)""",
            (servicio, (d.get('usuario') or '').strip(), _vault_encrypt(password),
             (d.get('url') or '').strip(), (d.get('notas') or '').strip(), now)
        )
        vid = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        db.commit()
    return jsonify({'ok': True, 'id': vid, 'servicio': servicio,
                    'usuario': d.get('usuario') or '', 'url': d.get('url') or '',
                    'notas': d.get('notas') or ''})


@perfil_bp.route('/api/vault/<int:vid>/edit', methods=['POST'])
def vault_edit(vid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    servicio = (d.get('servicio') or '').strip()
    if not servicio:
        return jsonify({'ok': False, 'error': 'Servicio requerido'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        row = db.execute("SELECT id FROM password_vault WHERE id=?", (vid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        new_password = d.get('password')
        if new_password:
            db.execute(
                """UPDATE password_vault SET servicio=?, usuario=?, password_enc=?, url=?,
                   notas=?, updated_at=? WHERE id=?""",
                (servicio, (d.get('usuario') or '').strip(), _vault_encrypt(new_password),
                 (d.get('url') or '').strip(), (d.get('notas') or '').strip(), now, vid)
            )
        else:
            db.execute(
                """UPDATE password_vault SET servicio=?, usuario=?, url=?, notas=?, updated_at=?
                   WHERE id=?""",
                (servicio, (d.get('usuario') or '').strip(),
                 (d.get('url') or '').strip(), (d.get('notas') or '').strip(), now, vid)
            )
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/vault/<int:vid>/reveal', methods=['POST'])
def vault_reveal(vid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        row = db.execute("SELECT password_enc FROM password_vault WHERE id=?", (vid,)).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    try:
        password = _vault_decrypt(row['password_enc'])
    except InvalidToken:
        return jsonify({'ok': False, 'error': 'No se pudo descifrar (¿cambió SECRET_KEY?)'}), 500
    return jsonify({'ok': True, 'password': password})


@perfil_bp.route('/api/vault/<int:vid>/delete', methods=['POST'])
def vault_delete(vid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        db.execute("DELETE FROM password_vault WHERE id=?", (vid,))
        db.commit()
    return jsonify({'ok': True})
