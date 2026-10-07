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

# Otros cuidados (Entrega 2): cada uno es opcional por planta y lleva su
# propio calendario en plantas_cuidados. tipo -> (etiqueta, días por defecto).
CUIDADOS_EXTRA = {
    'fertilizar': ('Fertilizar', 30),
    'rotar':      ('Rotar hacia la luz', 14),
    'limpiar':    ('Limpiar hojas', 30),
    'plagas':     ('Revisar plagas', 14),
}
_EXTRA_XP, _EXTRA_EC = 2, 1
# Noviembre-febrero: seco y fresco en Guadalajara, las plantas casi no crecen
# y fertilizar en reposo quema raíces. El calendario se pausa (no avisa).
FERTILIZAR_PAUSA = (11, 12, 1, 2)
TIPOS = ('riego', 'trasplante', *CUIDADOS_EXTRA)
_MAX_DIAS_ATRAS = 60   # «registrar en otra fecha»: hasta 2 meses atrás


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


def _compute_extra(c, created, today):
    """Estado de un cuidado extra (fertilizar, rotar, limpiar, plagas)."""
    label, _ = CUIDADOS_EXTRA[c['tipo']]
    cada = max(1, int(c['cada_dias'] or 1))
    base = _parse_date(c.get('last_fecha')) or created
    prox = base + timedelta(days=cada)
    dias = (prox - today).days
    pausado = c['tipo'] == 'fertilizar' and today.month in FERTILIZAR_PAUSA
    return {'tipo': c['tipo'], 'label': label, 'cada_dias': cada, 'last_fecha': c.get('last_fecha'),
            'proxima': prox.isoformat(), 'dias': dias, 'pct': _pct(base, prox, today),
            'pausado': pausado,
            'status': 'nominal' if pausado else _estado(dias, 0, max(1, min(2, cada // 4)))}


def _compute_planta(row, today, factores, cuidados=()):
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

    extras = [_compute_extra(c, created, today) for c in cuidados if c['tipo'] in CUIDADOS_EXTRA]
    extras.sort(key=lambda e: list(CUIDADOS_EXTRA).index(e['tipo']))
    peor = min([riego_status, trasplante_status, *(e['status'] for e in extras)], key=_STATUS_ORDER.get)
    return {
        **row,
        'cuidados': extras,
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
    cuidados = {}
    for c in db.execute("SELECT planta_id, tipo, cada_dias, last_fecha FROM plantas_cuidados").fetchall():
        cuidados.setdefault(c['planta_id'], []).append(dict(c))
    plantas = [_compute_planta(r, today, f, cuidados.get(r['id'], ())) for r in rows]
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
    return {'plantas': plantas, 'counts': counts, 'total': len(plantas), 'temporada': temporada,
            'cuidados_extra': {k: {'label': v[0], 'dias': v[1]} for k, v in CUIDADOS_EXTRA.items()},
            'fertilizar_pausado': today.month in FERTILIZAR_PAUSA}


def agenda(today=None, horizonte_dias=3):
    """Pendientes de plantas (riego, trasplante y otros cuidados) que vencen dentro de
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
        for e in p['cuidados']:
            if not e['pausado'] and e['dias'] <= horizonte_dias:
                out.append({'planta_id': p['id'], 'nombre': p['nombre'], 'foto': p.get('foto'),
                            'entorno': p['entorno'], 'tipo': e['tipo'], 'fecha': e['proxima'],
                            'dias': e['dias'], 'estado': e['status']})
    out.sort(key=lambda a: (a['dias'], TIPOS.index(a['tipo'])))
    return out


def _log_cuidado(planta_id, tipo, notas='', fecha=None):
    """Registra un cuidado en la bitácora, mueve su calendario y otorga XP/EC
    — mismo patrón que _log_servicio() de HARMA.

    - Uno por planta, tipo y fecha: un segundo toque no suma XP.
    - `fecha` permite registrar en otro día («la regué ayer»); si es anterior
      al último registro, queda en la bitácora sin mover el calendario.
    - Guarda la fecha anterior (prev_fecha) para poder deshacerlo.
    Devuelve (bitacora_id, gam); (None, None) si ya estaba registrado y
    (None, 'sin_config') si el cuidado extra no está activo en la planta."""
    fecha = fecha or today_str()
    key = f"planta_{tipo}"
    if tipo == 'riego':
        xp, ec = _RIEGO_XP, _RIEGO_EC
    elif tipo == 'trasplante':
        xp, ec = _TRASPLANTE_XP, _TRASPLANTE_EC
    else:
        xp, ec = _EXTRA_XP, _EXTRA_EC

    with get_db() as db:
        if db.execute("SELECT 1 FROM plantas_bitacora WHERE planta_id=? AND tipo=? AND fecha=?",
                      (planta_id, tipo, fecha)).fetchone():
            return None, None
        planta = db.execute("SELECT * FROM plantas WHERE id=?", (planta_id,)).fetchone()
        if tipo in _COL_CUIDADO:
            prev = planta[_COL_CUIDADO[tipo]]
        else:
            c = db.execute("SELECT last_fecha FROM plantas_cuidados WHERE planta_id=? AND tipo=?",
                           (planta_id, tipo)).fetchone()
            if not c:
                return None, 'sin_config'
            prev = c['last_fecha']
        log_id = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (key, today_str(), xp)
        ).lastrowid
        bitacora_id = db.execute(
            "INSERT INTO plantas_bitacora (planta_id, tipo, fecha, notas, activity_log_id, prev_fecha, prev_pospuesto, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (planta_id, tipo, fecha, notas, log_id, prev, planta['riego_pospuesto_hasta'], _now())
        ).lastrowid
        if not prev or fecha >= str(prev)[:10]:
            if tipo in _COL_CUIDADO:
                extra = ", riego_pospuesto_hasta=NULL" if tipo == 'riego' else ''
                db.execute(f"UPDATE plantas SET {_COL_CUIDADO[tipo]}=?{extra} WHERE id=?", (fecha, planta_id))
            else:
                db.execute("UPDATE plantas_cuidados SET last_fecha=? WHERE planta_id=? AND tipo=?",
                           (fecha, planta_id, tipo))
        db.commit()

    gam = engine.process_activity(key, xp, 'Plantas', log_id, ec=ec)
    return bitacora_id, gam


def _guardar_cuidados_extra(db, planta_id):
    """Del formulario: cuidado_<tipo> = días (activo) o vacío (desactivado).
    Activar uno nuevo arranca su calendario hoy; cambiar los días conserva la
    última fecha."""
    for tipo in CUIDADOS_EXTRA:
        campo = f'cuidado_{tipo}'
        if campo not in request.form:
            continue
        try:
            dias = int(request.form.get(campo) or 0)
        except ValueError:
            dias = 0
        if dias <= 0:
            db.execute("DELETE FROM plantas_cuidados WHERE planta_id=? AND tipo=?", (planta_id, tipo))
            continue
        dias = min(dias, 365)
        if db.execute("SELECT 1 FROM plantas_cuidados WHERE planta_id=? AND tipo=?", (planta_id, tipo)).fetchone():
            db.execute("UPDATE plantas_cuidados SET cada_dias=? WHERE planta_id=? AND tipo=?", (dias, planta_id, tipo))
        else:
            db.execute("INSERT INTO plantas_cuidados (planta_id, tipo, cada_dias, last_fecha, created_at) VALUES (?,?,?,?,?)",
                       (planta_id, tipo, dias, today_str(), _now()))


def _registrar_foto(db, planta_id, filename, nota=''):
    """Agrega la foto a la línea de tiempo y la vuelve la portada."""
    db.execute("INSERT INTO plantas_fotos (planta_id, foto, fecha, nota, created_at) VALUES (?,?,?,?,?)",
               (planta_id, filename, today_str(), nota[:200], _now()))
    db.execute("UPDATE plantas SET foto=? WHERE id=?", (filename, planta_id))


def _borrar_archivo(filename):
    if filename:
        try:
            os.remove(os.path.join(UPLOAD_DIR, filename))
        except OSError:
            pass


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
        pid = cur.lastrowid
        if filename:
            _registrar_foto(db, pid, filename)
        _guardar_cuidados_extra(db, pid)
        db.commit()
    return jsonify({'ok': True, 'id': pid, 'state': _state()}), 201


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

        # Una foto nueva se suma a la línea de tiempo (la anterior se conserva
        # ahí) y pasa a ser la portada.
        filename = row['foto']
        f = request.files.get('foto')
        if f and f.filename:
            new_filename, err = _save_upload(f)
            if not new_filename:
                return jsonify({'ok': False, 'error': err}), 400
            _registrar_foto(db, pid, new_filename)
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
        _guardar_cuidados_extra(db, pid)
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>', methods=['DELETE'])
def api_planta_delete(pid):
    with get_db() as db:
        row = db.execute("SELECT foto FROM plantas WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        fotos = {row['foto']} | {r['foto'] for r in db.execute(
            "SELECT foto FROM plantas_fotos WHERE planta_id=?", (pid,)).fetchall()}
        for fn in fotos:
            _borrar_archivo(fn)
        db.execute("DELETE FROM plantas_fotos WHERE planta_id=?", (pid,))
        db.execute("DELETE FROM plantas_cuidados WHERE planta_id=?", (pid,))
        db.execute("DELETE FROM plantas_bitacora WHERE planta_id=?", (pid,))
        db.execute("DELETE FROM plantas WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True, 'state': _state()})


def _fecha_cuidado(data):
    """Fecha opcional («la regué ayer»): ni futura ni de hace más de 60 días."""
    d = _parse_date(data.get('fecha'))
    hoy = today_date()
    if not d:
        return None, None
    if d > hoy or (hoy - d).days > _MAX_DIAS_ATRAS:
        return None, f'La fecha debe ser de hoy o de los últimos {_MAX_DIAS_ATRAS} días'
    return d.isoformat(), None


def _cuidado(pid, tipo):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM plantas WHERE id=?", (pid,)).fetchone():
            return jsonify({'ok': False, 'error': 'not found'}), 404
    data = request.get_json(silent=True) or {}
    fecha, err = _fecha_cuidado(data)
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    bid, gam = _log_cuidado(pid, tipo, str(data.get('notas', ''))[:300], fecha)
    if bid is None and gam == 'sin_config':
        return jsonify({'ok': False, 'error': 'Ese cuidado no está activo en esta planta'}), 400
    if bid is None:
        return jsonify({'ok': True, 'ya_registrado': True, 'gam': None, 'state': _state(),
                        'msg': 'Ya estaba registrado ese día'})
    return jsonify({'ok': True, 'gam': gam, 'bitacora_id': bid, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>/riego', methods=['POST'])
def api_planta_riego(pid):
    return _cuidado(pid, 'riego')


@plantas_bp.route('/api/plantas/<int:pid>/trasplante', methods=['POST'])
def api_planta_trasplante(pid):
    return _cuidado(pid, 'trasplante')


@plantas_bp.route('/api/plantas/<int:pid>/cuidado/<tipo>', methods=['POST'])
def api_planta_cuidado(pid, tipo):
    """Cualquier cuidado: riego, trasplante o uno extra (fertilizar…)."""
    if tipo not in TIPOS:
        return jsonify({'ok': False, 'error': 'Cuidado desconocido'}), 400
    return _cuidado(pid, tipo)


@plantas_bp.route('/api/riego-grupo', methods=['POST'])
def api_riego_grupo():
    """Regar de un jalón las pendientes (no «al día») de un entorno: todas las
    del balcón o todas las de interior. Cada una se registra como su propio
    riego (bitácora, XP, deshacer individual)."""
    data = request.get_json(silent=True) or {}
    entorno = data.get('entorno')
    if entorno not in ENTORNOS:
        return jsonify({'ok': False, 'error': 'Entorno inválido'}), 400
    with get_db() as db:
        pendientes = [p for p in _serialize_plantas(db)
                      if p['entorno'] == entorno and p['riego_status'] != 'nominal']
    n, xp, ec, gam = 0, 0, 0, None
    for p in pendientes:
        bid, g = _log_cuidado(p['id'], 'riego')
        if bid:
            n += 1
            xp += g['xp']; ec += g['ec']; gam = g
    if gam:
        gam = {**gam, 'xp': xp, 'ec': ec}
    return jsonify({'ok': True, 'regadas': n, 'gam': gam, 'state': _state(),
                    'msg': f"{n} planta{'s' if n != 1 else ''} regada{'s' if n != 1 else ''}"})


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
        ultimo = db.execute("SELECT MAX(id) m FROM plantas_bitacora WHERE planta_id=?", (pid,)).fetchone()['m']
    for r in rows:
        r['deshacer'] = r['id'] == ultimo   # solo el último registrado se puede deshacer
    return jsonify({'ok': True, 'bitacora': rows})


@plantas_bp.route('/api/bitacora/<int:bid>', methods=['DELETE'])
def api_bitacora_deshacer(bid):
    """Deshace el ÚLTIMO registro de una planta: restaura la fecha anterior
    (riego/trasplante) o el pospuesto anterior (revisión) y retira el XP/EC."""
    with get_db() as db:
        r = db.execute("SELECT * FROM plantas_bitacora WHERE id=?", (bid,)).fetchone()
        if not r:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        ultimo = db.execute("SELECT MAX(id) m FROM plantas_bitacora WHERE planta_id=?",
                            (r['planta_id'],)).fetchone()['m']
        if ultimo != bid:
            return jsonify({'ok': False, 'error': 'Solo se puede deshacer el último registro'}), 409
        if r['tipo'] in _COL_CUIDADO:
            db.execute(f"UPDATE plantas SET {_COL_CUIDADO[r['tipo']]}=? WHERE id=?", (r['prev_fecha'], r['planta_id']))
        elif r['tipo'] in CUIDADOS_EXTRA:
            db.execute("UPDATE plantas_cuidados SET last_fecha=? WHERE planta_id=? AND tipo=?",
                       (r['prev_fecha'], r['planta_id'], r['tipo']))
        if r['tipo'] in ('riego', 'revision'):
            db.execute("UPDATE plantas SET riego_pospuesto_hasta=? WHERE id=?", (r['prev_pospuesto'], r['planta_id']))
        if r['activity_log_id']:
            db.execute("DELETE FROM activity_logs WHERE id=?", (r['activity_log_id'],))
        db.execute("DELETE FROM plantas_bitacora WHERE id=?", (bid,))
        db.commit()
    if r['activity_log_id']:
        engine.remove_activity(r['activity_log_id'])
    return jsonify({'ok': True, 'state': _state()})


@plantas_bp.route('/api/plantas/<int:pid>/fotos')
def api_planta_fotos(pid):
    with get_db() as db:
        row = db.execute("SELECT foto FROM plantas WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        fotos = [dict(r) for r in db.execute(
            "SELECT id, foto, fecha, nota FROM plantas_fotos WHERE planta_id=? ORDER BY fecha, id", (pid,)).fetchall()]
    for f in fotos:
        f['portada'] = f['foto'] == row['foto']
    return jsonify({'ok': True, 'fotos': fotos})


@plantas_bp.route('/api/plantas/<int:pid>/fotos', methods=['POST'])
def api_planta_foto_nueva(pid):
    f = request.files.get('foto')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Falta la foto'}), 400
    with get_db() as db:
        if not db.execute("SELECT 1 FROM plantas WHERE id=?", (pid,)).fetchone():
            return jsonify({'ok': False, 'error': 'not found'}), 404
        filename, err = _save_upload(f)
        if not filename:
            return jsonify({'ok': False, 'error': err}), 400
        _registrar_foto(db, pid, filename, request.form.get('nota', '').strip())
        db.commit()
    return jsonify({'ok': True, 'state': _state()}), 201


@plantas_bp.route('/api/fotos/<int:fid>', methods=['DELETE'])
def api_foto_borrar(fid):
    """Borra una foto de la línea de tiempo; si era la portada, la portada
    pasa a la más reciente que quede (o ninguna)."""
    with get_db() as db:
        r = db.execute("SELECT * FROM plantas_fotos WHERE id=?", (fid,)).fetchone()
        if not r:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        db.execute("DELETE FROM plantas_fotos WHERE id=?", (fid,))
        planta = db.execute("SELECT foto FROM plantas WHERE id=?", (r['planta_id'],)).fetchone()
        if planta and planta['foto'] == r['foto']:
            nueva = db.execute("SELECT foto FROM plantas_fotos WHERE planta_id=? ORDER BY fecha DESC, id DESC LIMIT 1",
                               (r['planta_id'],)).fetchone()
            db.execute("UPDATE plantas SET foto=? WHERE id=?", (nueva['foto'] if nueva else None, r['planta_id']))
        db.commit()
    _borrar_archivo(r['foto'])
    return jsonify({'ok': True, 'state': _state()})


@plantas_bp.route('/foto/<filename>')
def serve_foto(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)
