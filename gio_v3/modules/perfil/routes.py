import os, uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from database import get_db

perfil_bp = Blueprint('perfil', __name__, template_folder='../../templates')

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'docs')
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

    # Group docs: general (field_key IS NULL) and per-field
    docs_general = []
    docs_by_field = {}
    for d in all_docs:
        fk = d["field_key"] if "field_key" in d.keys() else None
        if fk:
            docs_by_field.setdefault(fk, []).append(d)
        else:
            docs_general.append(d)

    return render_template('perfil/index.html',
                           info=info,
                           measurements=measurements,
                           docs=docs_general,
                           docs_by_field=docs_by_field,
                           reminders=[dict(r) for r in reminders])


@perfil_bp.route('/api/update', methods=['POST'])
def update():
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
    d = request.get_json(force=True, silent=True) or {}
    key = d.get('key', '').strip()
    value = d.get('value')
    if not key or value is None:
        return jsonify({'ok': False, 'error': 'key and value required'}), 400
    with get_db() as db:
        db.execute("UPDATE body_measurements SET value=? WHERE key=?", (str(value), key))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/upload_doc', methods=['POST'])
def upload_doc():
    f         = request.files.get('file')
    field_key = request.form.get('field_key', '').strip() or None
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido'}), 400
    safe_name = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, safe_name))
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO profile_docs (filename, original, uploaded_at, field_key) VALUES (?,?,?,?)",
            (safe_name, f.filename, now, field_key)
        )
        doc_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        db.commit()
    return jsonify({'ok': True, 'id': doc_id, 'filename': safe_name,
                    'original': f.filename, 'uploaded_at': now, 'field_key': field_key})


@perfil_bp.route('/api/delete_doc', methods=['POST'])
def delete_doc():
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
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)


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
    import calendar
    today = _date.today().isoformat()
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
    with get_db() as db:
        db.execute("DELETE FROM reminders WHERE id=?", (rid,))
        db.commit()
    return jsonify({'ok': True})
