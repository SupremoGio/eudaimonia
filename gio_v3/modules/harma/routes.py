import os, re, uuid
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

# ── Categorías del plan de mantenimiento ──────────────────────────────────────
CAT = {
    'motor':      {'label': 'Motor',       'hue': 15},
    'frenos':     {'label': 'Frenos',      'hue': 0},
    'suspension': {'label': 'Suspensión',  'hue': 240},
    'trans':      {'label': 'Transmisión', 'hue': 280},
    'rodaje':     {'label': 'Rodaje',      'hue': 195},
    'fluidos':    {'label': 'Fluidos',     'hue': 175},
}
CAT_ORDER = ['motor', 'frenos', 'suspension', 'trans', 'rodaje', 'fluidos']

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
    {"id": "tarjeta_circulacion",  "label": "Tarjeta de circulación"},
    {"id": "verificacion",         "label": "Verificación"},
    {"id": "tenencia",             "label": "Tenencia"},
    {"id": "otro",                 "label": "Otro"},
]

TIPOS_SINIESTRO = [
    {"id": "choque",     "label": "Choque",              "icon": "💥"},
    {"id": "robo",       "label": "Robo",                 "icon": "🚨"},
    {"id": "cristal",    "label": "Cristal roto",          "icon": "🔺"},
    {"id": "inundacion", "label": "Inundación / clima",   "icon": "🌧️"},
    {"id": "otro",       "label": "Otro",                  "icon": "⚠️"},
]

ESTADOS_SINIESTRO = [
    {"id": "reportado",   "label": "Reportado"},
    {"id": "en_proceso",  "label": "En proceso"},
    {"id": "resuelto",    "label": "Resuelto"},
    {"id": "rechazado",   "label": "Rechazado"},
]

_PROXIMIDAD_DIAS = 14


def _now():
    return datetime.now().isoformat()


def _get_vehiculo(db):
    row = db.execute("SELECT * FROM harma_vehiculo ORDER BY id LIMIT 1").fetchone()
    return dict(row) if row else None


def _months_between(iso_date, today):
    if not iso_date:
        return 999
    try:
        d = datetime.fromisoformat(iso_date).date()
    except ValueError:
        return 999
    return (today.year - d.year) * 12 + (today.month - d.month)


def _compute_plan_item(item, km_actual, today):
    """Progreso doble (km vs. tiempo) — el que llegue primero manda, igual que el fabricante."""
    km_pct   = (km_actual - item['last_km']) / item['km_interval'] if item['km_interval'] else 0
    time_pct = _months_between(item['last_date'], today) / item['meses_interval'] if item['meses_interval'] else 0
    pct      = max(km_pct, time_pct)
    next_km  = item['last_km'] + item['km_interval']
    km_left  = next_km - km_actual

    if pct >= 1:      status = 'vencido'
    elif pct >= 0.85: status = 'urgente'
    elif pct >= 0.65: status = 'proximo'
    else:             status = 'nominal'

    return {
        **item, 'km_pct': km_pct, 'time_pct': time_pct, 'pct': pct,
        'next_km': next_km, 'km_left': km_left, 'status': status,
        'cat_label': CAT.get(item['cat'], {}).get('label', item['cat']),
        'cat_hue':   CAT.get(item['cat'], {}).get('hue', 0),
    }


def _serialize_plan(db, vehiculo):
    today = today_date()
    km_actual = vehiculo['km_actual'] if vehiculo else 0
    rows = [dict(r) for r in db.execute("SELECT * FROM harma_plan_items ORDER BY id").fetchall()]
    items = [_compute_plan_item(r, km_actual, today) for r in rows]
    order = {'vencido': 0, 'urgente': 1, 'proximo': 2, 'nominal': 3}
    items.sort(key=lambda it: (CAT_ORDER.index(it['cat']) if it['cat'] in CAT_ORDER else 99, order[it['status']]))
    return items


def _slugify(name, db):
    base = re.sub(r'[^a-z0-9]+', '_', name.strip().lower()).strip('_') or 'servicio'
    slug, n = base, 2
    while db.execute("SELECT 1 FROM harma_plan_items WHERE id=?", (slug,)).fetchone():
        slug = f"{base}_{n}"
        n += 1
    return slug


def _poliza_status(pol, today):
    if not pol['vigencia_fin']:
        return 'sin_fecha'
    try:
        dias = (datetime.fromisoformat(pol['vigencia_fin']).date() - today).days
    except ValueError:
        return 'sin_fecha'
    if dias < 0:
        return 'vencida'
    if dias <= _PROXIMIDAD_DIAS:
        return 'proximo'
    return 'vigente'


def _serialize_polizas(db):
    today = today_date()
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM harma_polizas ORDER BY id DESC"
    ).fetchall()]
    for p in rows:
        p['status'] = _poliza_status(p, today)
    order = {'vencida': 0, 'proximo': 1, 'vigente': 2, 'sin_fecha': 3}
    rows.sort(key=lambda p: order[p['status']])
    return rows


def _state():
    with get_db() as db:
        vehiculo = _get_vehiculo(db)
        servicios = [dict(r) for r in db.execute(
            "SELECT * FROM harma_servicios ORDER BY id DESC LIMIT 40"
        ).fetchall()]
        plan = _serialize_plan(db, vehiculo)
        documentos = [dict(r) for r in db.execute(
            "SELECT * FROM harma_documentos ORDER BY id DESC"
        ).fetchall()]
        polizas = _serialize_polizas(db)
        siniestros = [dict(r) for r in db.execute(
            "SELECT * FROM harma_siniestros ORDER BY fecha DESC, id DESC"
        ).fetchall()]
        total_costo = db.execute(
            "SELECT COALESCE(SUM(costo),0) as s FROM harma_servicios"
        ).fetchone()['s']

    counts = {'vencido': 0, 'urgente': 0, 'proximo': 0, 'nominal': 0}
    for it in plan:
        counts[it['status']] += 1

    return {
        'vehiculo': vehiculo,
        'servicios': servicios,
        'plan': plan,
        'plan_counts': counts,
        'documentos': documentos,
        'polizas': polizas,
        'siniestros': siniestros,
        'total_costo': total_costo,
        'cat_defs': [{'id': c, **CAT[c]} for c in CAT_ORDER],
        'tipos_servicio': TIPOS_SERVICIO,
        'tipos_documento': TIPOS_DOCUMENTO,
        'tipos_siniestro': TIPOS_SINIESTRO,
        'estados_siniestro': ESTADOS_SINIESTRO,
    }


def _log_servicio(tipo, titulo, descripcion, km, costo, taller, fecha, plan_item_id=None):
    """Inserta el servicio, actualiza odómetro y el plan (si aplica), y otorga XP/EC vía el engine."""
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
            "plan_item_id, activity_log_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tipo, titulo, descripcion, km, costo, taller, fecha, plan_item_id, log_id, now)
        )
        servicio_id = cur2.lastrowid

        vehiculo = _get_vehiculo(db)
        km_actual = vehiculo['km_actual'] if vehiculo else None
        if vehiculo and km is not None and km > (km_actual or 0):
            db.execute(
                "UPDATE harma_vehiculo SET km_actual=?, km_actualizado=? WHERE id=?",
                (km, today, vehiculo['id'])
            )
            km_actual = km

        if plan_item_id:
            db.execute(
                "UPDATE harma_plan_items SET last_km=?, last_date=? WHERE id=?",
                (km if km is not None else (km_actual or 0), fecha, plan_item_id)
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
            "UPDATE harma_vehiculo SET nombre=?, marca=?, modelo=?, anio=?, motor=?, color=?, placas=?, "
            "km_actual=?, km_actualizado=? WHERE id=?",
            (
                str(data.get('nombre', vehiculo['nombre']))[:80],
                str(data.get('marca', vehiculo['marca']))[:40],
                str(data.get('modelo', vehiculo['modelo']))[:40],
                data.get('anio', vehiculo['anio']),
                str(data.get('motor', vehiculo.get('motor', '')))[:40],
                str(data.get('color', vehiculo.get('color', '')))[:40],
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
    plan_item_id = data.get('plan_item_id') or None

    servicio_id, gam = _log_servicio(
        tipo, titulo, str(data.get('descripcion', ''))[:500], km, costo,
        str(data.get('taller', ''))[:80], fecha, plan_item_id,
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


@harma_bp.route('/api/plan', methods=['POST'])
def api_plan_create():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()[:120]
    if not name:
        return jsonify({'error': 'nombre requerido'}), 400
    cat = data.get('cat') if data.get('cat') in CAT else 'motor'
    try:
        km_interval = int(data.get('km_interval') or 0)
        meses_interval = int(data.get('meses_interval') or 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'intervalo inválido'}), 400
    if km_interval <= 0 and meses_interval <= 0:
        return jsonify({'error': 'define al menos un intervalo (km o meses)'}), 400

    with get_db() as db:
        vehiculo = _get_vehiculo(db)
        slug = _slugify(name, db)
        db.execute(
            "INSERT INTO harma_plan_items (id, cat, name, km_interval, meses_interval, last_km, "
            "last_date, critical, desc, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                slug, cat, name,
                km_interval or 999999, meses_interval or 999,
                vehiculo['km_actual'] if vehiculo else 0, today_str(),
                1 if data.get('critical') else 0,
                str(data.get('desc', ''))[:300],
                _now(),
            )
        )
        db.commit()

    return jsonify({'ok': True, 'id': slug, 'state': _state()})


@harma_bp.route('/api/plan/<item_id>/marcar', methods=['POST'])
def api_plan_marcar(item_id):
    """Registra el servicio real correspondiente a este ítem del plan (hoy) y recalcula su progreso."""
    data = request.get_json(silent=True) or {}
    with get_db() as db:
        item = db.execute("SELECT * FROM harma_plan_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({'error': 'not found'}), 404
        item = dict(item)
        vehiculo = _get_vehiculo(db)

    km = data.get('km')
    try:
        km = int(km) if km not in (None, '') else (vehiculo['km_actual'] if vehiculo else None)
    except (TypeError, ValueError):
        km = vehiculo['km_actual'] if vehiculo else None

    servicio_id, gam = _log_servicio(
        item['id'], item['name'], str(data.get('descripcion', ''))[:500], km,
        float(data.get('costo') or 0), str(data.get('taller', ''))[:80], today_str(),
        plan_item_id=item['id'],
    )
    return jsonify({'ok': True, 'servicio_id': servicio_id, 'gam': gam, 'state': _state()})


@harma_bp.route('/api/plan/<item_id>', methods=['PATCH'])
def api_plan_update(item_id):
    """Ajusta manualmente el último km/fecha de servicio de un ítem (para capturar historial conocido)."""
    data = request.get_json(silent=True) or {}
    with get_db() as db:
        item = db.execute("SELECT id FROM harma_plan_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({'error': 'not found'}), 404
        fields, vals = [], []
        if 'last_km' in data:
            try:
                fields.append('last_km=?'); vals.append(max(0, int(data['last_km'])))
            except (TypeError, ValueError):
                return jsonify({'error': 'km inválido'}), 400
        if 'last_date' in data:
            fields.append('last_date=?'); vals.append(data['last_date'] or None)
        if fields:
            vals.append(item_id)
            db.execute(f"UPDATE harma_plan_items SET {', '.join(fields)} WHERE id=?", vals)
            db.commit()
    return jsonify({'ok': True, 'state': _state()})


@harma_bp.route('/api/plan/<item_id>', methods=['DELETE'])
def api_plan_delete(item_id):
    with get_db() as db:
        db.execute("DELETE FROM harma_plan_items WHERE id=?", (item_id,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


def _save_upload(f):
    """Valida y guarda un archivo subido. Devuelve (filename, original) o (None, error_msg)."""
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if not ext or ext not in ALLOWED_EXT:
        _mime_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
                     'image/heic': '.heic', 'application/pdf': '.pdf'}
        ext = _mime_map.get((f.content_type or '').split(';')[0].strip(), '')
    if ext not in ALLOWED_EXT:
        return None, 'Tipo no permitido (solo imágenes o PDF)'
    filename = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, filename))
    return filename, secure_filename(f.filename)


# ── Documentos ────────────────────────────────────────────────────────────────

@harma_bp.route('/api/documentos', methods=['POST'])
def api_documento_upload():
    f = request.files.get('file')
    titulo = request.form.get('titulo', '').strip()[:120]
    if not titulo:
        return jsonify({'ok': False, 'error': 'Título requerido'}), 400
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    filename, original_or_err = _save_upload(f)
    if not filename:
        return jsonify({'ok': False, 'error': original_or_err}), 400

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO harma_documentos (tipo, titulo, nombre_archivo, nombre_original, "
            "fecha_vencimiento, notas, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                request.form.get('tipo', 'otro'), titulo, filename,
                original_or_err,
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


# ── Póliza de seguro ────────────────────────────────────────────────────────

@harma_bp.route('/api/poliza', methods=['POST'])
def api_poliza_create():
    aseguradora = request.form.get('aseguradora', '').strip()[:80]
    if not aseguradora:
        return jsonify({'ok': False, 'error': 'Aseguradora requerida'}), 400

    filename, original = '', ''
    f = request.files.get('file')
    if f and f.filename:
        filename, original_or_err = _save_upload(f)
        if not filename:
            return jsonify({'ok': False, 'error': original_or_err}), 400
        original = original_or_err

    try:
        prima = float(request.form.get('prima') or 0)
        deducible = float(request.form.get('deducible') or 0)
    except (TypeError, ValueError):
        prima, deducible = 0, 0

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO harma_polizas (aseguradora, numero_poliza, vigencia_inicio, vigencia_fin, "
            "prima, deducible, telefono_asistencia, notas, nombre_archivo, nombre_original, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                aseguradora,
                request.form.get('numero_poliza', '').strip()[:60],
                request.form.get('vigencia_inicio') or None,
                request.form.get('vigencia_fin') or None,
                prima, deducible,
                request.form.get('telefono_asistencia', '').strip()[:40],
                request.form.get('notas', '')[:300],
                filename, original,
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'state': _state()})


@harma_bp.route('/api/poliza/<int:pid>', methods=['DELETE'])
def api_poliza_delete(pid):
    with get_db() as db:
        pol = db.execute("SELECT * FROM harma_polizas WHERE id=?", (pid,)).fetchone()
        if pol and pol['nombre_archivo']:
            try:
                os.remove(os.path.join(UPLOAD_DIR, pol['nombre_archivo']))
            except OSError:
                pass
        db.execute("DELETE FROM harma_polizas WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


# ── Siniestros ────────────────────────────────────────────────────────────────

@harma_bp.route('/api/siniestro', methods=['POST'])
def api_siniestro_create():
    descripcion = request.form.get('descripcion', '').strip()[:500]
    fecha = request.form.get('fecha') or today_str()
    tipo = request.form.get('tipo') or 'otro'
    estado = request.form.get('estado') or 'reportado'
    if estado not in {e['id'] for e in ESTADOS_SINIESTRO}:
        estado = 'reportado'

    filename, original = '', ''
    f = request.files.get('file')
    if f and f.filename:
        filename, original_or_err = _save_upload(f)
        if not filename:
            return jsonify({'ok': False, 'error': original_or_err}), 400
        original = original_or_err

    def _num(key):
        try:
            return float(request.form.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    poliza_id = request.form.get('poliza_id')
    try:
        poliza_id = int(poliza_id) if poliza_id else None
    except (TypeError, ValueError):
        poliza_id = None

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO harma_siniestros (fecha, tipo, descripcion, costo_estimado, costo_cubierto, "
            "deducible_pagado, taller, estado, poliza_id, nombre_archivo, nombre_original, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                fecha, tipo, descripcion,
                _num('costo_estimado'), _num('costo_cubierto'), _num('deducible_pagado'),
                request.form.get('taller', '').strip()[:80],
                estado, poliza_id, filename, original,
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'state': _state()})


@harma_bp.route('/api/siniestro/<int:sid>', methods=['PATCH'])
def api_siniestro_update_estado(sid):
    data = request.get_json(silent=True) or {}
    estado = data.get('estado')
    if estado not in {e['id'] for e in ESTADOS_SINIESTRO}:
        return jsonify({'error': 'estado inválido'}), 400
    with get_db() as db:
        db.execute("UPDATE harma_siniestros SET estado=? WHERE id=?", (estado, sid))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@harma_bp.route('/api/siniestro/<int:sid>', methods=['DELETE'])
def api_siniestro_delete(sid):
    with get_db() as db:
        sin = db.execute("SELECT * FROM harma_siniestros WHERE id=?", (sid,)).fetchone()
        if sin and sin['nombre_archivo']:
            try:
                os.remove(os.path.join(UPLOAD_DIR, sin['nombre_archivo']))
            except OSError:
                pass
        db.execute("DELETE FROM harma_siniestros WHERE id=?", (sid,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@harma_bp.route('/documentos/<filename>')
def serve_documento(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)
