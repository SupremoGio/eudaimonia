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
        docs         = db.execute("SELECT * FROM profile_docs ORDER BY uploaded_at DESC").fetchall()
    return render_template('perfil/index.html', info=info, measurements=measurements, docs=docs)


@perfil_bp.route('/api/update', methods=['POST'])
def update():
    d = request.json
    with get_db() as db:
        db.execute("UPDATE personal_info SET value=? WHERE key=?", (d['value'], d['key']))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/update_measurement', methods=['POST'])
def update_measurement():
    d = request.json
    with get_db() as db:
        db.execute("UPDATE body_measurements SET value=? WHERE key=?", (d['value'], d['key']))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/upload_doc', methods=['POST'])
def upload_doc():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido'}), 400
    safe_name = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, safe_name))
    with get_db() as db:
        db.execute(
            "INSERT INTO profile_docs (filename, original, uploaded_at) VALUES (?,?,?)",
            (safe_name, f.filename, datetime.now().isoformat())
        )
        doc_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        db.commit()
    return jsonify({'ok': True, 'id': doc_id, 'filename': safe_name, 'original': f.filename,
                    'uploaded_at': datetime.now().isoformat()})


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
