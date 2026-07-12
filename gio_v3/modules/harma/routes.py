import os, uuid
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from database import get_db
from utils import today_str, today_date
import modules.gamification.engine as engine

harma_bp = Blueprint('harma', __name__, template_folder='../../templates')

UPLOAD_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'harma')
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.pdf'}
os.makedirs(UPLOAD_DIR, exist_ok=True)

_SERVICIO_KEY = "harma_servicio"
_SERVICIO_XP  = 5
_SERVICIO_EC  = 2

TIPOS_SERVICIO = [
    {"id": "aceite",       "label": "Cambio de aceite",     "icon": "🛢️"},
    {"id": "frenos",       "label": "Frenos / balatas",      "icon": "🛑"},
    {"id": "llantas",      "label": "Llantas",                "icon": "🛞"},
    {"id": "afinacion",    "label": "Afinación",              "icon": "🔧"},
    {"id": "bateria",      "label": "Batería",                "icon": "🔋"},
    {"id": "verificacion", "label": "Verificación",           "icon": "📋"},
    {"id": "lavado",       "label": "Lavado / detallado",     "icon": "🧼"},
    {"id": "otro",         "label": "Otro",                   "icon": "🔩"},
]

TIPOS_DOCUMENTO = [
    {"id": "seguro",               "label": "Póliza de seguro"},
    {"id": "tarjeta_circulacion",  "label": "Tarjeta de circulación"},
    {"id": "verificacion",         "label": "Verificación"},
    {"id": "tenencia",             "label": "Tenencia"},
    {"id": "otro",                 "label": "Otro"},
]

_PROXIMIDAD_KM   = 500
_PROXIMIDAD_DIAS = 14


def _now():
    return datetime.now().isoformat()


def _get_vehiculo(db):
    row = db.execute("SELECT * FROM harma_vehiculo ORDER BY id LIMIT 1").fetchone()
    return dict(row) if row else None


def _reminder_status(rec, km_actual, today):
    """'vencido' | 'proximo' | 'ok' — toma el peor de km/fecha si ambos aplican."""
    status = 'ok'
    if rec['proximo_km'] is not None and km_actual is not None:
        if km_actual >= rec['proximo_km']:
            status = 'vencido'
        elif km_actual >= rec['proximo_km'] - _PROXIMIDAD_KM and status == 'ok':
            status = 'proximo'
    if rec['proximo_fecha']:
        try:
            dias_restantes = (datetime.fromisoformat(rec['proximo_fecha']).date() - today).days
            if dias_restantes < 0:
                status = 'vencido'
            elif dias_restantes <= _PROXIMIDAD_DIAS and status != 'vencido':
                status = 'proximo'
        except ValueError:
            pass
    return status


def _compute_proximo(intervalo_km, intervalo_dias, base_km, base_fecha):
    proximo_km = (base_km + intervalo_km) if (intervalo_km and base_km is not None) else None
    proximo_fecha = None
    if intervalo_dias and base_fecha:
        try:
            proximo_fecha = (datetime.fromisoformat(base_fecha).date() + timedelta(days=intervalo_dias)).isoformat()
        except ValueError:
            proximo_fecha = None
    return proximo_km, proximo_fecha


def _serialize_recordatorios(db, vehiculo):
    today = today_date()
    km_actual = vehiculo['km_actual'] if vehiculo else None
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM harma_recordatorios WHERE activo=1 ORDER BY id DESC"
    ).fetchall()]
    for r in rows:
        r['status'] = _reminder_status(r, km_actual, today)
    order = {'vencido': 0, 'proximo': 1, 'ok': 2}
    rows.sort(key=lambda r: order[r['status']])
    return rows


def _state():
    with get_db() as db:
        vehiculo = _get_vehiculo(db)
        servicios = [dict(r) for r in db.execute(
            "SELECT * FROM harma_servicios ORDER BY id DESC LIMIT 40"
        ).fetchall()]
        recordatorios = _serialize_recordatorios(db, vehiculo)
        documentos = [dict(r) for r in db.execute(
            "SELECT * FROM harma_documentos ORDER BY id DESC"
        ).fetchall()]
        total_costo = db.execute(
            "SELECT COALESCE(SUM(costo),0) as s FROM harma_servicios"
        ).fetchone()['s']

    return {
        'vehiculo': vehiculo,
        'servicios': servicios,
        'recordatorios': recordatorios,
        'documentos': documentos,
        'total_costo': total_costo,
        'tipos_servicio': TIPOS_SERVICIO,
        'tipos_documento': TIPOS_DOCUMENTO,
    }


def _log_servicio(tipo, titulo, descripcion, km, costo, taller, fecha):
    """Inserta el servicio, actualiza odómetro si aplica, y otorga XP/EC vía el engine."""
    today = today_str()
    now = _now()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (_SERVICIO_KEY, today, _SERVICIO_XP)
        )
        log_id = cur.lastrowid
        cur2 = db.execute(
            "INSERT INTO harma_servicios (tipo, titulo, descripcion, km, costo, taller, fecha, "
            "activity_log_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (tipo, titulo, descripcion, km, costo, taller, fecha, log_id, now)
        )
        servicio_id = cur2.lastrowid

        vehiculo = _get_vehiculo(db)
        if vehiculo and km is not None and km > (vehiculo['km_actual'] or 0):
            db.execute(
                "UPDATE harma_vehiculo SET km_actual=?, km_actualizado=? WHERE id=?",
                (km, today, vehiculo['id'])
            )
        db.commit()

    gam = engine.process_activity(_SERVICIO_KEY, _SERVICIO_XP, 'Mecánica', log_id)
    return servicio_id, gam


# ── Rutas ─────────────────────────────────────────────────────────────────────

@harma_bp.route('/')
def index():
    return render_template('harma/index.html', **_state())


@harma_bp.route('/api/state')
def api_state():
    return jsonify(_state())


@harma_bp.route('/api/vehiculo', methods=['POST'])
def api_vehiculo_update():
    data = request.get_json(silent=True) or {}
    with get_db() as db:
        vehiculo = _get_vehiculo(db)
        if not vehiculo:
            return jsonify({'error': 'not found'}), 404
        km_actual = vehiculo['km_actual']
        if 'km_actual' in data:
            try:
                km_actual = max(0, int(data['km_actual']))
            except (TypeError, ValueError):
                return jsonify({'error': 'invalid km'}), 400
        db.execute(
            "UPDATE harma_vehiculo SET nombre=?, marca=?, modelo=?, anio=?, placas=?, "
            "km_actual=?, km_actualizado=? WHERE id=?",
            (
                str(data.get('nombre', vehiculo['nombre']))[:80],
                str(data.get('marca', vehiculo['marca']))[:40],
                str(data.get('modelo', vehiculo['modelo']))[:40],
                data.get('anio', vehiculo['anio']),
                str(data.get('placas', vehiculo['placas']))[:20],
                km_actual, today_str(), vehiculo['id'],
            )
        )
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@harma_bp.route('/api/servicio', methods=['POST'])
def api_servicio_create():
    data = request.get_json(silent=True) or {}
    titulo = str(data.get('titulo', '')).strip()[:120]
    if not titulo:
        return jsonify({'error': 'titulo requerido'}), 400
    tipo = data.get('tipo') or 'otro'
    km = data.get('km')
    try:
        km = int(km) if km not in (None, '') else None
    except (TypeError, ValueError):
        km = None
    try:
        costo = float(data.get('costo') or 0)
    except (TypeError, ValueError):
        costo = 0
    fecha = data.get('fecha') or today_str()

    servicio_id, gam = _log_servicio(
        tipo, titulo, str(data.get('descripcion', ''))[:500], km, costo,
        str(data.get('taller', ''))[:80], fecha,
    )
    return jsonify({'ok': True, 'servicio_id': servicio_id, 'gam': gam, 'state': _state()})


@harma_bp.route('/api/servicio/<int:sid>', methods=['DELETE'])
def api_servicio_delete(sid):
    with get_db() as db:
        row = db.execute("SELECT * FROM harma_servicios WHERE id=?", (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute("DELETE FROM harma_servicios WHERE id=?", (sid,))
        db.commit()
        log_id = row['activity_log_id']

    gam = None
    if log_id:
        with get_db() as db:
            db.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
            db.commit()
        gam = engine.remove_activity(log_id)
    return jsonify({'ok': True, 'gam': gam, 'state': _state()})


@harma_bp.route('/api/recordatorio', methods=['POST'])
def api_recordatorio_create():
    data = request.get_json(silent=True) or {}
    titulo = str(data.get('titulo', '')).strip()[:120]
    if not titulo:
        return jsonify({'error': 'titulo requerido'}), 400
    tipo = data.get('tipo') or 'otro'

    def _int_or_none(v):
        try:
            return int(v) if v not in (None, '') else None
        except (TypeError, ValueError):
            return None

    intervalo_km = _int_or_none(data.get('intervalo_km'))
    intervalo_dias = _int_or_none(data.get('intervalo_dias'))
    if not intervalo_km and not intervalo_dias:
        return jsonify({'error': 'define al menos un intervalo (km o días)'}), 400

    with get_db() as db:
        vehiculo = _get_vehiculo(db)
        base_km = _int_or_none(data.get('ultimo_km'))
        if base_km is None:
            base_km = vehiculo['km_actual'] if vehiculo else 0
        base_fecha = data.get('ultima_fecha') or today_str()

        proximo_km, proximo_fecha = _compute_proximo(intervalo_km, intervalo_dias, base_km, base_fecha)

        db.execute(
            "INSERT INTO harma_recordatorios (tipo, titulo, intervalo_km, intervalo_dias, "
            "ultimo_km, ultima_fecha, proximo_km, proximo_fecha, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (tipo, titulo, intervalo_km, intervalo_dias, base_km, base_fecha,
             proximo_km, proximo_fecha, _now())
        )
        db.commit()

    return jsonify({'ok': True, 'state': _state()})


@harma_bp.route('/api/recordatorio/<int:rid>/hecho', methods=['POST'])
def api_recordatorio_hecho(rid):
    """Marca el recordatorio como cumplido hoy: registra el servicio real y recalcula el próximo."""
    data = request.get_json(silent=True) or {}
    with get_db() as db:
        rec = db.execute("SELECT * FROM harma_recordatorios WHERE id=?", (rid,)).fetchone()
        if not rec:
            return jsonify({'error': 'not found'}), 404
        rec = dict(rec)
        vehiculo = _get_vehiculo(db)

    km = data.get('km')
    try:
        km = int(km) if km not in (None, '') else (vehiculo['km_actual'] if vehiculo else None)
    except (TypeError, ValueError):
        km = vehiculo['km_actual'] if vehiculo else None
    today = today_str()

    servicio_id, gam = _log_servicio(
        rec['tipo'], rec['titulo'], str(data.get('descripcion', ''))[:500], km,
        float(data.get('costo') or 0), str(data.get('taller', ''))[:80], today,
    )

    proximo_km, proximo_fecha = _compute_proximo(rec['intervalo_km'], rec['intervalo_dias'], km, today)
    with get_db() as db:
        db.execute(
            "UPDATE harma_recordatorios SET ultimo_km=?, ultima_fecha=?, proximo_km=?, proximo_fecha=? WHERE id=?",
            (km, today, proximo_km, proximo_fecha, rid)
        )
        db.commit()

    return jsonify({'ok': True, 'servicio_id': servicio_id, 'gam': gam, 'state': _state()})


@harma_bp.route('/api/recordatorio/<int:rid>', methods=['DELETE'])
def api_recordatorio_delete(rid):
    with get_db() as db:
        db.execute("DELETE FROM harma_recordatorios WHERE id=?", (rid,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


# ── Documentos ────────────────────────────────────────────────────────────────

@harma_bp.route('/api/documentos', methods=['POST'])
def api_documento_upload():
    f = request.files.get('file')
    titulo = request.form.get('titulo', '').strip()[:120]
    if not titulo:
        return jsonify({'ok': False, 'error': 'Título requerido'}), 400
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if not ext or ext not in ALLOWED_EXT:
        _mime_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
                     'image/heic': '.heic', 'application/pdf': '.pdf'}
        ext = _mime_map.get((f.content_type or '').split(';')[0].strip(), '')
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido (solo imágenes o PDF)'}), 400

    filename = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, filename))
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO harma_documentos (tipo, titulo, nombre_archivo, nombre_original, "
            "fecha_vencimiento, notas, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                request.form.get('tipo', 'otro'), titulo, filename,
                secure_filename(f.filename),
                request.form.get('fecha_vencimiento') or None,
                request.form.get('notas', '')[:300],
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'state': _state()})


@harma_bp.route('/api/documentos/<int:did>', methods=['DELETE'])
def api_documento_delete(did):
    with get_db() as db:
        doc = db.execute("SELECT * FROM harma_documentos WHERE id=?", (did,)).fetchone()
        if doc and doc['nombre_archivo']:
            try:
                os.remove(os.path.join(UPLOAD_DIR, doc['nombre_archivo']))
            except OSError:
                pass
        db.execute("DELETE FROM harma_documentos WHERE id=?", (did,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@harma_bp.route('/documentos/<filename>')
def serve_documento(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)
