import os, uuid
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import calendar
from database import get_db
from utils import today_str, today_date, uploads_base_dir, optimize_photo
from modules.plantas.care_data import suggest_care, seasonal_factor, ENTORNOS
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
LUCES = ('', 'baja', 'media', 'brillante', 'sol_directo')
_COL_CUIDADO = {'riego': 'last_riego', 'trasplante': 'last_trasplante'}


def _now():
    return datetime.now().isoformat()


def _parse_date(iso):
    try:
        return date.fromisoformat(str(iso)[:10]) if iso else None
    except ValueError:
        return None


def _add_months(d, n):
    """Mismo día n meses después; si ese mes es más corto, su último día
    (31-ene + 1 mes = 28/29-feb)."""
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _estado(dias, urgente, proximo):
    """Por días que faltan: vencido desde el día siguiente a la fecha; el
    mismo día es «urgente» (la UI lo muestra como «Hoy»)."""
    if dias < 0:        return 'vencido'
    if dias <= urgente: return 'urgente'
    if dias <= proximo: return 'proximo'
    return 'nominal'


def _pct(base, proxima, today):
    total = (proxima - base).days
    return round(min(max((today - base).days / total, 0), 2), 2) if total > 0 else 1.0


def _compute_planta(row, today, factores):
    """Cada planta tiene DOS calendarios independientes, cada uno con su fecha
    próxima real (no un porcentaje): riego y trasplante.

    Riego: cada dias_riego × factor de temporada de Guadalajara según el
    entorno (balcón recibe el ajuste completo, interior una fracción — ver
    care_data.seasonal_factor), sin tocar el dias_riego que configuró el
    usuario. «Aún húmeda» la pospone (riego_pospuesto_hasta).
    Trasplante: mismo día N meses después (_add_months).

    Esta es la ÚNICA fuente del estado: la página, la API y el Dashboard
    (agenda()) la usan, así que no pueden contradecirse."""
    created = _parse_date(row.get('created_at')) or today
    entorno = row.get('entorno') if row.get('entorno') in ENTORNOS else 'interior'

    intervalo = max(1, int(row['dias_riego'] * factores[entorno] + 0.5))
    base_r = _parse_date(row.get('last_riego')) or created
    prox_r = base_r + timedelta(days=intervalo)
    pospuesto = _parse_date(row.get('riego_pospuesto_hasta'))
    if pospuesto and pospuesto > prox_r:
        prox_r = pospuesto
    dias_r = (prox_r - today).days
    riego_status = _estado(dias_r, 0, max(1, min(2, intervalo // 4)))

    base_t = _parse_date(row.get('last_trasplante')) or created
    prox_t = _add_months(base_t, max(1, row['meses_trasplante']))
    dias_t = (prox_t - today).days
    trasplante_status = _estado(dias_t, 7, 30)

    peor = min(riego_status, trasplante_status, key=_STATUS_ORDER.get)
    return {
        **row,
        'entorno': entorno,
        'riego_interval_efectivo': intervalo,
        'riego_proxima': prox_r.isoformat(), 'riego_dias': dias_r,
        'riego_pct': _pct(base_r, prox_r, today), 'riego_status': riego_status,
        'riego_pospuesta': bool(pospuesto and pospuesto >= today and pospuesto == prox_r),
        'trasplante_proxima': prox_t.isoformat(), 'trasplante_dias': dias_t,
        'trasplante_pct': _pct(base_t, prox_t, today), 'trasplante_status': trasplante_status,
        'status': peor,
    }


def _factores(today):
    return {e: seasonal_factor(today.month, e)['factor'] for e in ENTORNOS}


def _serialize_plantas(db, today=None):
    today = today or today_date()
    f = _factores(today)
    rows = [dict(r) for r in db.execute("SELECT * FROM plantas ORDER BY id").fetchall()]
    plantas = [_compute_planta(r, today, f) for r in rows]
    plantas.sort(key=lambda p: (_STATUS_ORDER[p['status']], p['riego_dias']))
    return plantas


def _state():
    today = today_date()
    with get_db() as db:
        plantas = _serialize_plantas(db, today)
    counts = {'vencido': 0, 'urgente': 0, 'proximo': 0, 'nominal': 0}
    for p in plantas:
        counts[p['status']] += 1
    temporada = seasonal_factor(today.month, 'balcon')
    temporada['factor_interior'] = seasonal_factor(today.month, 'interior')['factor']
    return {'plantas': plantas, 'counts': counts, 'total': len(plantas), 'temporada': temporada}


def agenda(today=None, horizonte_dias=3):
    """Pendientes de plantas (riego y trasplante) que vencen dentro de
    `horizonte_dias` o ya vencieron, más urgentes primero. La consume el
    Dashboard: mismo cálculo que /plantas/, sin SQL propio."""
    today = today or today_date()
    with get_db() as db:
        plantas = _serialize_plantas(db, today)
    out = []
    for p in plantas:
        for tipo in ('riego', 'trasplante'):
            dias = p[f'{tipo}_dias']
            if dias <= horizonte_dias:
                out.append({'planta_id': p['id'], 'nombre': p['nombre'], 'foto': p.get('foto'),
                            'entorno': p['entorno'], 'tipo': tipo, 'fecha': p[f'{tipo}_proxima'],
                            'dias': dias, 'estado': p[f'{tipo}_status']})
    out.sort(key=lambda a: (a['dias'], a['tipo'] != 'riego'))
    return out


def _log_cuidado(planta_id, tipo, notas=''):
    """Registra riego/trasplante en la bitácora, resetea el calendario de
    esa planta y otorga XP/EC — mismo patrón que _log_servicio() de HARMA.
    Uno por planta y día: un segundo toque (o regar dos veces) no da XP.
    Guarda la fecha anterior (prev_fecha) para poder deshacerlo."""
    today = today_str()
    key = f"planta_{tipo}"
    xp, ec = (_RIEGO_XP, _RIEGO_EC) if tipo == 'riego' else (_TRASPLANTE_XP, _TRASPLANTE_EC)
    col = _COL_CUIDADO[tipo]

    with get_db() as db:
        if db.execute("SELECT 1 FROM plantas_bitacora WHERE planta_id=? AND tipo=? AND fecha=?",
                      (planta_id, tipo, today)).fetchone():
            return None, None
        row = db.execute(f"SELECT {col}, riego_pospuesto_hasta FROM plantas WHERE id=?", (planta_id,)).fetchone()
        log_id = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (key, today, xp)
        ).lastrowid
        bitacora_id = db.execute(
            "INSERT INTO plantas_bitacora (planta_id, tipo, fecha, notas, activity_log_id, prev_fecha, prev_pospuesto, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (planta_id, tipo, today, notas, log_id, row[col], row['riego_pospuesto_hasta'], _now())
        ).lastrowid
        extra = ", riego_pospuesto_hasta=NULL" if tipo == 'riego' else ''
        db.execute(f"UPDATE plantas SET {col}=?{extra} WHERE id=?", (today, planta_id))
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
    # Se guarda como JPEG ≤1600px (las de celular pesan varios MB y el HEIC no
    # se ve en Chrome/Android); si Pillow no la puede abrir, va el original.
    data = f.read()
    filename = uuid.uuid4().hex + '.jpg'
    if not optimize_photo(data, os.path.join(UPLOAD_DIR, filename)):
        filename = uuid.uuid4().hex + ext
        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as out:
            out.write(data)
    return filename, None


def _form_entorno(default='interior'):
    v = (request.form.get('entorno') or default).strip()
    return v if v in ENTORNOS else default


def _form_luz(default=''):
    v = (request.form.get('luz', default) or '').strip()
    return v if v in LUCES else default


def _form_fecha_pasada(name, default):
    """Fecha opcional del formulario (YYYY-MM-DD) que no puede ser futura."""
    d = _parse_date(request.form.get(name))
    if not d:
        return default
    return min(d, today_date()).isoformat()


# ── Rutas ─────────────────────────────────────────────────────────────────────

@plantas_bp.route('/')
def index():
    return render_template('plantas/index.html', today_iso=today_str(), **_state())


@plantas_bp.route('/api/state')
def api_state():
    return jsonify(_state())


@plantas_bp.route('/api/agenda')
def api_agenda():
    try:
        horizonte = max(0, min(int(request.args.get('dias', 3)), 60))
    except ValueError:
        horizonte = 3
    return jsonify({'agenda': agenda(horizonte_dias=horizonte)})


@plantas_bp.route('/api/sugerir')
def api_sugerir():
    """Sugerencia de riego/trasplante por especie — tabla local curada, sin
    API externa. Se consulta con lo que el usuario escriba en Nombre o
    Especie; el resultado es un punto de partida editable, no se aplica
    solo (el frontend lo ofrece como sugerencia con botón 'Usar')."""
    q = request.args.get('q', '')
    result = suggest_care(q)
    return jsonify(result or {})


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

    hoy = today_str()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO plantas (nombre, especie, ubicacion, foto, dias_riego, meses_trasplante, "
            "last_riego, last_trasplante, notas, entorno, luz, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                nombre,
                request.form.get('especie', '').strip()[:80],
                request.form.get('ubicacion', '').strip()[:80],
                filename,
                dias_riego, meses_trasplante,
                _form_fecha_pasada('last_riego', hoy), _form_fecha_pasada('last_trasplante', hoy),
                request.form.get('notas', '').strip()[:300],
                _form_entorno(), _form_luz(),
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

        try:
            dias_riego = max(1, int(request.form.get('dias_riego') or row['dias_riego']))
            meses_trasplante = max(1, int(request.form.get('meses_trasplante') or row['meses_trasplante']))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Intervalo inválido'}), 400

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

        db.execute(
            "UPDATE plantas SET nombre=?, especie=?, ubicacion=?, foto=?, dias_riego=?, "
            "meses_trasplante=?, notas=?, entorno=?, luz=? WHERE id=?",
            (
                request.form.get('nombre', row['nombre']).strip()[:80] or row['nombre'],
                request.form.get('especie', row['especie'] or '').strip()[:80],
                request.form.get('ubicacion', row['ubicacion'] or '').strip()[:80],
                filename,
                dias_riego, meses_trasplante,
                request.form.get('notas', row['notas'] or '').strip()[:300],
                _form_entorno(row.get('entorno') or 'interior'), _form_luz(row.get('luz') or ''),
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


def _cuidado(pid, tipo):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM plantas WHERE id=?", (pid,)).fetchone():
            return jsonify({'ok': False, 'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    bid, gam = _log_cuidado(pid, tipo, str(data.get('notas', ''))[:300])
    if bid is None:
        return jsonify({'ok': True, 'ya_registrado': True, 'gam': None, 'state': _state(),
                        'msg': 'Ya estaba registrado hoy'})
    return jsonify({'ok': True, 'gam': gam, 'bitacora_id': bid, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>/riego', methods=['POST'])
def api_planta_riego(pid):
    return _cuidado(pid, 'riego')


@plantas_bp.route('/api/plantas/<int:pid>/trasplante', methods=['POST'])
def api_planta_trasplante(pid):
    return _cuidado(pid, 'trasplante')


@plantas_bp.route('/api/plantas/<int:pid>/posponer', methods=['POST'])
def api_planta_posponer(pid):
    """«Revisé y aún está húmeda»: corre el próximo riego N días (1-7, por
    defecto 2) desde hoy. Sin XP — no es un riego. Revisar la tierra antes
    de regar es lo que evita el exceso de riego."""
    data = request.get_json(silent=True) or {}
    try:
        dias = max(1, min(int(data.get('dias') or 2), 7))
    except (TypeError, ValueError):
        dias = 2
    hoy = today_date()
    hasta = (hoy + timedelta(days=dias)).isoformat()
    with get_db() as db:
        row = db.execute("SELECT riego_pospuesto_hasta, last_riego FROM plantas WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        db.execute(
            "INSERT INTO plantas_bitacora (planta_id, tipo, fecha, notas, prev_pospuesto, created_at) VALUES (?,?,?,?,?,?)",
            (pid, 'revision', hoy.isoformat(), f'Aún húmeda — riego pospuesto {dias} d', row['riego_pospuesto_hasta'], _now()))
        db.execute("UPDATE plantas SET riego_pospuesto_hasta=? WHERE id=?", (hasta, pid))
        db.commit()
    return jsonify({'ok': True, 'gam': None, 'state': _state(),
                    'msg': f'Riego pospuesto {dias} día' + ('s' if dias != 1 else '')})


@plantas_bp.route('/api/plantas/<int:pid>/bitacora')
def api_planta_bitacora(pid):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM plantas WHERE id=?", (pid,)).fetchone():
            return jsonify({'ok': False, 'error': 'not found'}), 404
        rows = [dict(r) for r in db.execute(
            "SELECT id, tipo, fecha, notas FROM plantas_bitacora WHERE planta_id=? "
            "ORDER BY fecha DESC, id DESC LIMIT 60", (pid,)).fetchall()]
    for i, r in enumerate(rows):
        r['deshacer'] = i == 0   # solo el último registro se puede deshacer
    return jsonify({'ok': True, 'bitacora': rows})


@plantas_bp.route('/api/bitacora/<int:bid>', methods=['DELETE'])
def api_bitacora_deshacer(bid):
    """Deshace el ÚLTIMO registro de una planta: restaura la fecha anterior
    (riego/trasplante) o el pospuesto anterior (revisión) y retira el XP/EC."""
    with get_db() as db:
        r = db.execute("SELECT * FROM plantas_bitacora WHERE id=?", (bid,)).fetchone()
        if not r:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        ultimo = db.execute("SELECT id FROM plantas_bitacora WHERE planta_id=? ORDER BY fecha DESC, id DESC LIMIT 1",
                            (r['planta_id'],)).fetchone()
        if ultimo['id'] != bid:
            return jsonify({'ok': False, 'error': 'Solo se puede deshacer el último registro'}), 409
        if r['tipo'] in _COL_CUIDADO:
            db.execute(f"UPDATE plantas SET {_COL_CUIDADO[r['tipo']]}=? WHERE id=?", (r['prev_fecha'], r['planta_id']))
        if r['tipo'] in ('riego', 'revision'):
            db.execute("UPDATE plantas SET riego_pospuesto_hasta=? WHERE id=?", (r['prev_pospuesto'], r['planta_id']))
        if r['activity_log_id']:
            db.execute("DELETE FROM activity_logs WHERE id=?", (r['activity_log_id'],))
        db.execute("DELETE FROM plantas_bitacora WHERE id=?", (bid,))
        db.commit()
    if r['activity_log_id']:
        engine.remove_activity(r['activity_log_id'])
    return jsonify({'ok': True, 'state': _state()})


@plantas_bp.route('/foto/<filename>')
def serve_foto(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)
