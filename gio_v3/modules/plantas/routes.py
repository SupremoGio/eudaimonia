import os, uuid
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from datetime import datetime
from database import get_db
from utils import today_str, today_date, uploads_base_dir
import modules.gamification.engine as engine

plantas_bp = Blueprint('plantas', __name__, template_folder='../../templates')

UPLOAD_DIR  = os.path.join(uploads_base_dir(), 'plantas')
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Riego = acción rápida y frecuente (tier "progreso"); trasplante = mucho
# más esfuerzo y raro (tier "alto") — mismo criterio de escala que el resto
# de la app (álbumes/películas 5/2, resolver_codigo 6/2, etc.).
_RIEGO_XP,      _RIEGO_EC      = 2, 1
_TRASPLANTE_XP, _TRASPLANTE_EC = 6, 2

_STATUS_ORDER = {'vencido': 0, 'urgente': 1, 'proximo': 2, 'nominal': 3}


def _now():
    return datetime.now().isoformat()


def _days_since(iso_date, today):
    if not iso_date:
        return 9999
    try:
        d = datetime.fromisoformat(iso_date).date()
    except ValueError:
        return 9999
    return (today - d).days


def _months_since(iso_date, today):
    if not iso_date:
        return 9999
    try:
        d = datetime.fromisoformat(iso_date).date()
    except ValueError:
        return 9999
    return (today.year - d.year) * 12 + (today.month - d.month)


def _status_from_pct(pct):
    if pct >= 1:    return 'vencido'
    if pct >= 0.85: return 'urgente'
    if pct >= 0.65: return 'proximo'
    return 'nominal'


def _compute_planta(row, today):
    """Cada planta tiene DOS calendarios independientes (a diferencia del
    plan de HARMA, que usa una sola métrica doble km/tiempo por ítem) —
    riego y trasplante no comparten "el que llegue primero manda", cada
    uno se calcula y se marca por separado."""
    riego_pct = _days_since(row['last_riego'], today) / row['dias_riego'] if row['dias_riego'] else 0
    trasplante_pct = _months_since(row['last_trasplante'], today) / row['meses_trasplante'] if row['meses_trasplante'] else 0
    riego_status = _status_from_pct(riego_pct)
    trasplante_status = _status_from_pct(trasplante_pct)
    peor = riego_status if _STATUS_ORDER[riego_status] <= _STATUS_ORDER[trasplante_status] else trasplante_status
    return {
        **row,
        'riego_pct': round(min(riego_pct, 2), 2), 'riego_status': riego_status,
        'trasplante_pct': round(min(trasplante_pct, 2), 2), 'trasplante_status': trasplante_status,
        'status': peor,
    }


def _serialize_plantas(db):
    today = today_date()
    rows = [dict(r) for r in db.execute("SELECT * FROM plantas ORDER BY id").fetchall()]
    plantas = [_compute_planta(r, today) for r in rows]
    plantas.sort(key=lambda p: _STATUS_ORDER[p['status']])
    return plantas


def _state():
    with get_db() as db:
        plantas = _serialize_plantas(db)
    counts = {'vencido': 0, 'urgente': 0, 'proximo': 0, 'nominal': 0}
    for p in plantas:
        counts[p['status']] += 1
    return {'plantas': plantas, 'counts': counts, 'total': len(plantas)}


def _log_cuidado(planta_id, tipo, notas=''):
    """Registra riego/trasplante en la bitácora, resetea el calendario de
    esa planta y otorga XP/EC — mismo patrón que _log_servicio() de HARMA."""
    today = today_str()
    now = _now()
    key = f"planta_{tipo}"
    xp, ec = (_RIEGO_XP, _RIEGO_EC) if tipo == 'riego' else (_TRASPLANTE_XP, _TRASPLANTE_EC)
    col = 'last_riego' if tipo == 'riego' else 'last_trasplante'

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (key, today, xp)
        )
        log_id = cur.lastrowid
        cur2 = db.execute(
            "INSERT INTO plantas_bitacora (planta_id, tipo, fecha, notas, activity_log_id, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (planta_id, tipo, today, notas, log_id, now)
        )
        bitacora_id = cur2.lastrowid
        db.execute(f"UPDATE plantas SET {col}=? WHERE id=?", (today, planta_id))
        db.commit()

    gam = engine.process_activity(key, xp, 'Plantas', log_id, ec=ec)
    return bitacora_id, gam


def _save_upload(f):
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if not ext or ext not in ALLOWED_EXT:
        _mime_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/heic': '.heic'}
        ext = _mime_map.get((f.content_type or '').split(';')[0].strip(), '')
    if ext not in ALLOWED_EXT:
        return None, 'Tipo no permitido (solo imágenes)'
    filename = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, filename))
    return filename, None


# ── Rutas ─────────────────────────────────────────────────────────────────────

@plantas_bp.route('/')
def index():
    return render_template('plantas/index.html', **_state())


@plantas_bp.route('/api/state')
def api_state():
    return jsonify(_state())


@plantas_bp.route('/api/plantas', methods=['POST'])
def api_planta_create():
    nombre = request.form.get('nombre', '').strip()[:80]
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400

    try:
        dias_riego = max(1, int(request.form.get('dias_riego') or 7))
        meses_trasplante = max(1, int(request.form.get('meses_trasplante') or 12))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Intervalo inválido'}), 400

    filename = None
    f = request.files.get('foto')
    if f and f.filename:
        filename, err = _save_upload(f)
        if not filename:
            return jsonify({'ok': False, 'error': err}), 400

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO plantas (nombre, especie, ubicacion, foto, dias_riego, meses_trasplante, "
            "last_riego, last_trasplante, notas, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                nombre,
                request.form.get('especie', '').strip()[:80],
                request.form.get('ubicacion', '').strip()[:80],
                filename,
                dias_riego, meses_trasplante,
                today_str(), today_str(),
                request.form.get('notas', '').strip()[:300],
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'state': _state()}), 201


@plantas_bp.route('/api/plantas/<int:pid>', methods=['POST'])
def api_planta_update(pid):
    """POST (no PATCH) porque acepta multipart/form-data para reemplazar la foto."""
    with get_db() as db:
        row = db.execute("SELECT * FROM plantas WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        row = dict(row)

        filename = row['foto']
        f = request.files.get('foto')
        if f and f.filename:
            new_filename, err = _save_upload(f)
            if not new_filename:
                return jsonify({'ok': False, 'error': err}), 400
            if filename:
                try:
                    os.remove(os.path.join(UPLOAD_DIR, filename))
                except OSError:
                    pass
            filename = new_filename

        try:
            dias_riego = max(1, int(request.form.get('dias_riego') or row['dias_riego']))
            meses_trasplante = max(1, int(request.form.get('meses_trasplante') or row['meses_trasplante']))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Intervalo inválido'}), 400

        db.execute(
            "UPDATE plantas SET nombre=?, especie=?, ubicacion=?, foto=?, dias_riego=?, "
            "meses_trasplante=?, notas=? WHERE id=?",
            (
                request.form.get('nombre', row['nombre']).strip()[:80] or row['nombre'],
                request.form.get('especie', row['especie']).strip()[:80],
                request.form.get('ubicacion', row['ubicacion']).strip()[:80],
                filename,
                dias_riego, meses_trasplante,
                request.form.get('notas', row['notas']).strip()[:300],
                pid,
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>', methods=['DELETE'])
def api_planta_delete(pid):
    with get_db() as db:
        row = db.execute("SELECT foto FROM plantas WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        if row['foto']:
            try:
                os.remove(os.path.join(UPLOAD_DIR, row['foto']))
            except OSError:
                pass
        db.execute("DELETE FROM plantas_bitacora WHERE planta_id=?", (pid,))
        db.execute("DELETE FROM plantas WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>/riego', methods=['POST'])
def api_planta_riego(pid):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM plantas WHERE id=?", (pid,)).fetchone():
            return jsonify({'ok': False, 'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    _, gam = _log_cuidado(pid, 'riego', str(data.get('notas', ''))[:300])
    return jsonify({'ok': True, 'gam': gam, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>/trasplante', methods=['POST'])
def api_planta_trasplante(pid):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM plantas WHERE id=?", (pid,)).fetchone():
            return jsonify({'ok': False, 'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    _, gam = _log_cuidado(pid, 'trasplante', str(data.get('notas', ''))[:300])
    return jsonify({'ok': True, 'gam': gam, 'state': _state()})


@plantas_bp.route('/foto/<filename>')
def serve_foto(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)
