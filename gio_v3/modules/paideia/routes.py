import os
import requests
from flask import Blueprint, render_template, request, jsonify
import calendar
from datetime import datetime
from database import get_db
from utils import today_str, today_date
import modules.gamification.engine as engine
import modules.actividades.activity_defs as adefs

paideia_bp = Blueprint('paideia', __name__, template_folder='../../templates')

_OPENLIBRARY_SEARCH_URL = 'https://openlibrary.org/search.json'

# Búsqueda de películas — OMDb en vez de iTunes Search API: Apple suele
# bloquear/limitar peticiones servidor-a-servidor desde IPs de nube (Railway)
# a itunes.apple.com aunque funcione desde un navegador normal. OMDb está
# hecho justo para uso server-side y de paso trae Director (iTunes no lo
# daba). Requiere API key gratis (omdbapi.com/apikey.aspx, sin tarjeta) en
# la variable de entorno OMDB_API_KEY — sin ella la búsqueda degrada a
# "sin resultados" en vez de romper el modal de alta manual.
_OMDB_URL = 'https://www.omdbapi.com/'
_OMDB_API_KEY = os.environ.get('OMDB_API_KEY', '')

_META_KEY = 'paideia_meta_anual'
_DEFAULT_META = 12

# ── Libros — terminar uno da XP (handoff Paideia v2, nota 6), igual que una película
_LIBRO_XP = 10
_LIBRO_EC = 5
# Páginas por sesión de 30 min, para el «≈ N sesiones» del héroe
PAGINAS_POR_SESION = 25
# Si hoy no hay ancla de Paideia en Acta, registrar avance marca este touch
_LECTURA_TOUCH = 'leer_general'

# ── Películas — ranking personal (mismo patrón que Música dentro de EURYTHMIA) ─
_PELI_XP = 5
_PELI_EC = 2

PELI_RATING_DIMS = [
    {"key": "guion",      "label": "Guion"},
    {"key": "actuacion",  "label": "Actuación"},
    {"key": "direccion",  "label": "Dirección"},
    {"key": "rewatch",    "label": "Rewatch value"},
]


def _compute_mi_rating_peli(row):
    vals = [row[f"rating_{d['key']}"] for d in PELI_RATING_DIMS if row[f"rating_{d['key']}"] is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def _peliculas_state():
    with get_db() as db:
        rows = db.execute("SELECT * FROM paideia_peliculas ORDER BY created_at DESC, id DESC").fetchall()
    peliculas = [dict(r) for r in rows]
    vistas = [p for p in peliculas if p["vista"]]
    ranking = sorted(
        [p for p in vistas if p["mi_rating"] is not None],
        key=lambda p: -p["mi_rating"]
    )
    return {
        "peliculas": peliculas,
        "total":     len(peliculas),
        "vistas_n":  len(vistas),
        "ranking":   ranking,
    }


def _now():
    return datetime.now().isoformat()


def _get_meta():
    with get_db() as db:
        row = db.execute("SELECT value FROM app_settings WHERE key=?", (_META_KEY,)).fetchone()
    return int(row['value']) if row else _DEFAULT_META


def ritmo(meta, leidos, hoy=None):
    """¿Voy a cumplir la meta? (handoff Paideia v2, nota 2)
    ritmo_hoy: libros que «tocaría» llevar hoy para ir parejo; diff_ritmo > 0
    = adelantado; faltan y cada_n_dias: 1 libro cada N días para cerrar."""
    hoy = hoy or today_date()
    dias_anio = 366 if calendar.isleap(hoy.year) else 365
    dia = hoy.timetuple().tm_yday
    ritmo_hoy = round(meta * dia / dias_anio, 1)
    faltan = max(0, meta - leidos)
    dias_restantes = dias_anio - dia
    return {
        'ritmo_hoy':      ritmo_hoy,
        'diff_ritmo':     round(leidos - ritmo_hoy, 1),
        'faltan':         faltan,
        'dias_restantes': dias_restantes,
        'cada_n_dias':    (round(dias_restantes / faltan) if dias_restantes else 0) if faltan else None,
        'ritmo_pct':      round(min(100, ritmo_hoy / meta * 100), 1) if meta else 0,
    }


def _stats(libros):
    this_year = today_date().year
    leidos_anio = [l for l in libros if l['estado'] == 'leido' and l['fecha_fin'] and l['fecha_fin'][:4] == str(this_year)]
    ratings = [l['rating'] for l in libros if l['rating'] is not None]
    meta = _get_meta()
    return {
        **ritmo(meta, len(leidos_anio)),
        'meta_anual': meta,
        'leidos_este_anio': len(leidos_anio),
        'total_leidos': sum(1 for l in libros if l['estado'] == 'leido'),
        'leyendo': sum(1 for l in libros if l['estado'] == 'leyendo'),
        'por_leer': sum(1 for l in libros if l['estado'] == 'por_leer'),
        'rating_prom': round(sum(ratings) / len(ratings), 1) if ratings else None,
    }


def _row_to_dict(r):
    return dict(r)


def _clamp_pct(v):
    if v in (None, ''):
        return None
    return max(0, min(100, int(v)))


# ── Rutas ─────────────────────────────────────────────────────────────────────

@paideia_bp.route('/')
def index():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM paideia_libros ORDER BY "
            "CASE estado WHEN 'leyendo' THEN 0 WHEN 'por_leer' THEN 1 ELSE 2 END, "
            "COALESCE(fecha_fin, fecha_inicio) DESC, id DESC"
        ).fetchall()
    libros = [_row_to_dict(r) for r in rows]
    lectura = lectura_de_hoy()
    return render_template(
        'paideia/index.html', libros=libros, stats=_stats(libros),
        now_year=today_date().year,
        peliculas=_peliculas_state(), peli_rating_dims=PELI_RATING_DIMS,
        lectura=lectura, lectura_hecha=bool(lectura and _lectura_hecha_hoy(lectura)),
        paginas_sesion=PAGINAS_POR_SESION,
    )


@paideia_bp.route('/api/summary')
def summary():
    with get_db() as db:
        rows = db.execute("SELECT * FROM paideia_libros").fetchall()
    libros = [_row_to_dict(r) for r in rows]
    leyendo = next((l for l in libros if l['estado'] == 'leyendo'), None)
    return jsonify({
        'stats': _stats(libros),
        'leyendo': leyendo,
    })


@paideia_bp.route('/api/meta', methods=['POST'])
def set_meta():
    d = request.json or {}
    try:
        meta = max(1, int(d.get('meta', _DEFAULT_META)))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'meta inválida'}), 400
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (_META_KEY, str(meta)),
        )
        db.commit()
    return jsonify({'ok': True, 'meta': meta})


@paideia_bp.route('/api/buscar')
def buscar_libro():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'resultados': []})
    try:
        r = requests.get(_OPENLIBRARY_SEARCH_URL, params={
            'q': q,
            'fields': 'title,author_name,number_of_pages_median,cover_i,first_publish_year',
            'limit': 6,
        }, timeout=6)
        r.raise_for_status()
        docs = r.json().get('docs', [])
    except requests.RequestException:
        return jsonify({'resultados': []})
    resultados = [{
        'titulo': d.get('title'),
        'autor': (d.get('author_name') or [None])[0],
        'paginas': d.get('number_of_pages_median'),
        'anio': d.get('first_publish_year'),
        'portada': f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg" if d.get('cover_i') else None,
    } for d in docs if d.get('title')]
    return jsonify({'resultados': resultados})


def _omdb_year(y):
    if not y:
        return None
    digits = ''.join(c for c in y[:4] if c.isdigit())
    return int(digits) if len(digits) == 4 else None


def _omdb_clean(v):
    return None if v in (None, 'N/A', '') else v


@paideia_bp.route('/api/buscar_pelicula')
def buscar_pelicula():
    q = request.args.get('q', '').strip()
    if not q or not _OMDB_API_KEY:
        return jsonify({'resultados': []})
    try:
        r = requests.get(_OMDB_URL, params={
            'apikey': _OMDB_API_KEY, 's': q, 'type': 'movie',
        }, timeout=6)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return jsonify({'resultados': []})

    if data.get('Response') != 'True':
        return jsonify({'resultados': []})

    resultados = [{
        'imdb_id': d.get('imdbID'),
        'titulo':  d.get('Title'),
        'anio':    _omdb_year(d.get('Year')),
        'portada': _omdb_clean(d.get('Poster')),
    } for d in data.get('Search', [])[:6] if d.get('Title') and d.get('imdbID')]
    return jsonify({'resultados': resultados})


@paideia_bp.route('/api/pelicula_detalle')
def pelicula_detalle():
    """Detalle completo por imdbID — la búsqueda (s=) de OMDb no trae
    Director/Genre, solo título/año/póster; se pide aparte y solo cuando
    el usuario elige un resultado (no por cada item del dropdown)."""
    imdb_id = request.args.get('id', '').strip()
    if not imdb_id or not _OMDB_API_KEY:
        return jsonify({'error': 'no disponible'}), 400
    try:
        r = requests.get(_OMDB_URL, params={'apikey': _OMDB_API_KEY, 'i': imdb_id}, timeout=6)
        r.raise_for_status()
        d = r.json()
    except requests.RequestException:
        return jsonify({'error': 'sin conexión'}), 502
    if d.get('Response') != 'True':
        return jsonify({'error': d.get('Error', 'no encontrado')}), 404
    return jsonify({
        'titulo':   d.get('Title'),
        'anio':     _omdb_year(d.get('Year')),
        'director': _omdb_clean(d.get('Director')),
        'genero':   _omdb_clean(d.get('Genre')),
        'portada':  _omdb_clean(d.get('Poster')),
    })


@paideia_bp.route('/api/libros')
def list_libros():
    with get_db() as db:
        rows = db.execute("SELECT * FROM paideia_libros ORDER BY id DESC").fetchall()
    libros = [_row_to_dict(r) for r in rows]
    return jsonify({'libros': libros, 'stats': _stats(libros)})


@paideia_bp.route('/api/libros', methods=['POST'])
def crear_libro():
    d = request.json or {}
    if not d.get('titulo'):
        return jsonify({'ok': False, 'error': 'título requerido'}), 400
    estado = d.get('estado', 'por_leer')
    hoy = datetime.now().date().isoformat()
    fecha_inicio = d.get('fecha_inicio') or (hoy if estado in ('leyendo', 'leido') else None)
    fecha_fin = d.get('fecha_fin') or (hoy if estado == 'leido' else None)
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO paideia_libros
                   (titulo, autor, categoria, estado, paginas_totales, paginas_actuales,
                    rating, fecha_inicio, fecha_fin, notas, portada, progreso_pct, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d['titulo'].strip(),
                d.get('autor', '').strip(),
                d.get('categoria', 'Otro'),
                estado,
                int(d['paginas_totales']) if d.get('paginas_totales') not in (None, '') else None,
                int(d.get('paginas_actuales') or 0),
                int(d['rating']) if d.get('rating') not in (None, '') else None,
                fecha_inicio,
                fecha_fin,
                d.get('notas', '').strip(),
                d.get('portada') or None,
                _clamp_pct(d.get('progreso_pct')),
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@paideia_bp.route('/api/libros/<int:lid>', methods=['PATCH'])
def actualizar_libro(lid):
    d = request.json or {}
    sets, vals = [], []
    for f in ('titulo', 'autor', 'categoria', 'estado', 'fecha_inicio', 'fecha_fin', 'notas', 'portada'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(d[f])
    for f in ('paginas_totales', 'paginas_actuales', 'rating'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(int(d[f]) if d[f] not in (None, '') else None)
    if 'progreso_pct' in d:
        sets.append('progreso_pct=?')
        vals.append(_clamp_pct(d['progreso_pct']))

    # Transiciones automáticas de fecha al cambiar de estado
    if d.get('estado') == 'leyendo' and not d.get('fecha_inicio'):
        with get_db() as db:
            row = db.execute("SELECT fecha_inicio FROM paideia_libros WHERE id=?", (lid,)).fetchone()
        if row and not row['fecha_inicio']:
            sets.append('fecha_inicio=?')
            vals.append(datetime.now().date().isoformat())
    if d.get('estado') == 'leido' and not d.get('fecha_fin'):
        sets.append('fecha_fin=?')
        vals.append(datetime.now().date().isoformat())

    if not sets:
        return jsonify({'ok': False, 'error': 'nada que actualizar'}), 400

    with get_db() as db:
        prev = db.execute("SELECT estado FROM paideia_libros WHERE id=?", (lid,)).fetchone()
    if not prev:
        return jsonify({'ok': False, 'error': 'not found'}), 404
    vals.append(lid)
    with get_db() as db:
        db.execute(f"UPDATE paideia_libros SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()

    # Terminar un libro da +10 XP · +5 EC; salir de «leído» lo revierte
    gam = None
    nuevo = d.get('estado', prev['estado'])
    if nuevo == 'leido' and prev['estado'] != 'leido':
        gam = _premiar_libro(lid)
    elif prev['estado'] == 'leido' and nuevo != 'leido':
        gam = _revertir_libro(lid)
    return jsonify({'ok': True, 'gam': gam, 'stats': _stats(_todos_los_libros())})


@paideia_bp.route('/api/libros/<int:lid>', methods=['DELETE'])
def eliminar_libro(lid):
    with get_db() as db:
        row = db.execute("SELECT estado FROM paideia_libros WHERE id=?", (lid,)).fetchone()
        db.execute("DELETE FROM paideia_libros WHERE id=?", (lid,))
        db.commit()
    if row and row['estado'] == 'leido':
        _revertir_libro(lid)                      # igual que eliminar_pelicula
    return jsonify({'ok': True})


@paideia_bp.route('/api/libros/<int:lid>/progreso', methods=['POST'])
def progreso_libro(lid):
    """Registrar avance ({pagina} o {pct}): guarda el progreso y marca una vez
    al día la lectura de Paideia en Acta (handoff Paideia v2, nota 5)."""
    d = request.json or {}
    with get_db() as db:
        libro = db.execute("SELECT * FROM paideia_libros WHERE id=?", (lid,)).fetchone()
    if not libro:
        return jsonify({'ok': False, 'error': 'not found'}), 404
    total = libro['paginas_totales']
    try:
        if d.get('pagina') not in (None, ''):
            pagina = max(0, int(d['pagina']))
            if total:
                pagina = min(pagina, total)
            pct = round(pagina / total * 100) if total else libro['progreso_pct']
            sets, vals = ['paginas_actuales=?'], [pagina]
            if total:
                sets.append('progreso_pct=?'); vals.append(pct)
        elif d.get('pct') not in (None, ''):
            pct = _clamp_pct(d['pct'])
            sets, vals = ['progreso_pct=?'], [pct]
            if total:
                sets.append('paginas_actuales=?'); vals.append(round(total * pct / 100))
        else:
            return jsonify({'ok': False, 'error': 'pagina o pct requerido'}), 400
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'valor inválido'}), 400
    if libro['estado'] == 'por_leer':                 # registrar avance = empezar a leerlo
        sets += ['estado=?', 'fecha_inicio=COALESCE(fecha_inicio, ?)']
        vals += ['leyendo', today_str()]
    with get_db() as db:
        db.execute(f"UPDATE paideia_libros SET {', '.join(sets)} WHERE id=?", vals + [lid])
        db.commit()
    marca = _marcar_lectura_acta()
    return jsonify({'ok': True, 'pct': pct, 'ancla_marcada': bool(marca),
                    'actividad': marca and marca['label'], 'nueva': bool(marca and marca['nueva']),
                    'gam': marca and marca.get('gam')})


def _todos_los_libros():
    with get_db() as db:
        return [_row_to_dict(r) for r in db.execute("SELECT * FROM paideia_libros").fetchall()]


def _premiar_libro(lid):
    key = f"paideia_libro_{lid}"
    with get_db() as db:
        cur = db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                         (key, today_str(), _LIBRO_XP))
        log_id = cur.lastrowid
        db.commit()
    return engine.process_activity(key, _LIBRO_XP, 'Lectura', log_id, ec=_LIBRO_EC)


def _revertir_libro(lid):
    with get_db() as db:
        log_row = db.execute("SELECT id FROM activity_logs WHERE activity_key=? ORDER BY id DESC LIMIT 1",
                             (f"paideia_libro_{lid}",)).fetchone()
        if not log_row:
            return None
        db.execute("DELETE FROM activity_logs WHERE id=?", (log_row['id'],))
        db.commit()
    return engine.remove_activity(log_row['id'])


def lectura_de_hoy():
    """La actividad de Acta que registra la lectura hoy: el ancla de Paideia
    que toca hoy (con el Foco del mes aplicado) o, si no hay, el touch
    «Leer 5 páginas». {key, label, pts, cat, ancla} o None."""
    hoy = today_date()
    wd = adefs.DAY_CODES[hoy.weekday()]
    acts = [a for a in adefs.get_active_flat().values()
            if a.get('pillar') == 'paideia' and not a.get('hidden') and adefs.eligible_today(a, wd, hoy)]
    a = next((x for x in acts if x.get('effective_type') == 'ancla'), None) \
        or next((x for x in acts if x['key'] == _LECTURA_TOUCH), None)
    if not a:
        return None
    return {'key': a['key'], 'label': a['label'], 'pts': a['pts'], 'cat': a.get('cat') or 'Lectura',
            'ancla': a.get('effective_type') == 'ancla'}


def _lectura_hecha_hoy(act):
    with get_db() as db:
        return db.execute("SELECT 1 FROM activity_logs WHERE activity_key=? AND date=?",
                          (act['key'], today_str())).fetchone() is not None


def _marcar_lectura_acta():
    """Marca (una vez al día) la lectura de Paideia en Acta. Si ya estaba la
    versión mínima del ancla, la sube a completa sin sumar dos veces."""
    act = lectura_de_hoy()
    if not act:
        return None
    if _lectura_hecha_hoy(act):
        return {**act, 'nueva': False}
    today = today_str()
    min_id = None
    with get_db() as db:
        cur = db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)", (act['key'], today, act['pts']))
        log_id = cur.lastrowid
        prev_min = db.execute("SELECT id FROM activity_logs WHERE activity_key=? AND date=?",
                              (act['key'] + engine.ANCLA_MIN_SUFFIX, today)).fetchone()
        if prev_min:
            min_id = prev_min['id']
            db.execute("DELETE FROM activity_logs WHERE id=?", (min_id,))
        db.commit()
    if min_id:
        engine.remove_activity(min_id)
    gam = engine.process_activity(act['key'], act['pts'], act['cat'], log_id)
    return {**act, 'nueva': True, 'gam': gam}


# ── Películas ─────────────────────────────────────────────────────────────────

@paideia_bp.route('/api/peliculas')
def list_peliculas():
    return jsonify(_peliculas_state())


@paideia_bp.route('/api/peliculas', methods=['POST'])
def crear_pelicula():
    d = request.json or {}
    titulo = (d.get('titulo') or '').strip()
    if not titulo:
        return jsonify({'ok': False, 'error': 'título requerido'}), 400
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO paideia_peliculas (titulo, director, anio, genero, portada) VALUES (?,?,?,?,?)",
            (
                titulo,
                (d.get('director') or '').strip(),
                int(d['anio']) if d.get('anio') not in (None, '') else None,
                (d.get('genero') or '').strip(),
                d.get('portada') or None,
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'peliculas': _peliculas_state()}), 201


@paideia_bp.route('/api/peliculas/<int:pid>', methods=['POST'])
def actualizar_pelicula(pid):
    data = request.get_json(silent=True) or {}

    with get_db() as db:
        row = db.execute("SELECT * FROM paideia_peliculas WHERE id=?", (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    row = dict(row)

    was_vista = bool(row['vista'])
    vista = bool(data.get('vista', was_vista))

    ratings = {}
    for dim in PELI_RATING_DIMS:
        key = f"rating_{dim['key']}"
        val = data.get(key, row[key])
        if val not in (None, ''):
            try:
                val = int(val)
            except (TypeError, ValueError):
                return jsonify({'error': f'invalid {key}'}), 400
            if val < 1 or val > 10:
                return jsonify({'error': f'invalid {key}'}), 400
        else:
            val = None
        ratings[key] = val

    mi_rating = _compute_mi_rating_peli(ratings)
    notas = str(data.get('notas', row['notas']) or '')[:500]
    vista_at = row['vista_at']
    rating_cols = list(ratings.keys())
    rating_vals = [ratings[k] for k in rating_cols]

    gam = None
    with get_db() as db:
        if vista and not was_vista:
            vista_at = datetime.now().isoformat()
            today = datetime.now().date().isoformat()
            cur = db.execute(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                (f"paideia_pelicula_{pid}", today, _PELI_XP)
            )
            log_id = cur.lastrowid
            db.execute(
                f"UPDATE paideia_peliculas SET vista=1, mi_rating=?, notas=?, vista_at=?, "
                f"{', '.join(f'{c}=?' for c in rating_cols)} WHERE id=?",
                (mi_rating, notas, vista_at, *rating_vals, pid)
            )
            db.commit()
            gam = engine.process_activity(f"paideia_pelicula_{pid}", _PELI_XP, 'Cine', log_id, ec=_PELI_EC)
        elif not vista and was_vista:
            db.execute(
                f"UPDATE paideia_peliculas SET vista=0, mi_rating=NULL, notas=?, vista_at=NULL, "
                f"{', '.join(f'{c}=NULL' for c in rating_cols)} WHERE id=?",
                (notas, pid)
            )
            db.commit()
            log_row = db.execute(
                "SELECT id FROM activity_logs WHERE activity_key=? ORDER BY id DESC LIMIT 1",
                (f"paideia_pelicula_{pid}",)
            ).fetchone()
            if log_row:
                db.execute("DELETE FROM activity_logs WHERE id=?", (log_row['id'],))
                db.commit()
                gam = engine.remove_activity(log_row['id'])
        else:
            db.execute(
                f"UPDATE paideia_peliculas SET mi_rating=?, notas=?, "
                f"{', '.join(f'{c}=?' for c in rating_cols)} WHERE id=?",
                (mi_rating, notas, *rating_vals, pid)
            )
            db.commit()

    return jsonify({'ok': True, 'gam': gam, 'peliculas': _peliculas_state()})


@paideia_bp.route('/api/peliculas/<int:pid>', methods=['DELETE'])
def eliminar_pelicula(pid):
    with get_db() as db:
        row = db.execute("SELECT vista FROM paideia_peliculas WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        log_row = None
        if row['vista']:
            log_row = db.execute(
                "SELECT id FROM activity_logs WHERE activity_key=? ORDER BY id DESC LIMIT 1",
                (f"paideia_pelicula_{pid}",)
            ).fetchone()
            if log_row:
                db.execute("DELETE FROM activity_logs WHERE id=?", (log_row['id'],))
        db.execute("DELETE FROM paideia_peliculas WHERE id=?", (pid,))
        db.commit()
    if log_row:
        engine.remove_activity(log_row['id'])
    return jsonify({'ok': True, 'peliculas': _peliculas_state()})
