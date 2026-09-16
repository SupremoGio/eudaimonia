import requests
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from database import get_db
from data import get_paideia_tip_of_day, get_random_paideia_tip
import modules.gamification.engine as engine

paideia_bp = Blueprint('paideia', __name__, template_folder='../../templates')

_OPENLIBRARY_SEARCH_URL = 'https://openlibrary.org/search.json'
_ITUNES_SEARCH_URL = 'https://itunes.apple.com/search'

_META_KEY = 'paideia_meta_anual'
_DEFAULT_META = 12

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


def _stats(libros):
    this_year = datetime.now().year
    leidos_anio = [l for l in libros if l['estado'] == 'leido' and l['fecha_fin'] and l['fecha_fin'][:4] == str(this_year)]
    ratings = [l['rating'] for l in libros if l['rating'] is not None]
    return {
        'meta_anual': _get_meta(),
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
    return render_template(
        'paideia/index.html', libros=libros, stats=_stats(libros),
        tip=get_paideia_tip_of_day(), now_year=datetime.now().year,
        peliculas=_peliculas_state(), peli_rating_dims=PELI_RATING_DIMS,
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
        'tip': get_paideia_tip_of_day(),
    })


@paideia_bp.route('/api/tip/refresh')
def tip_refresh():
    cat = request.args.get('cat')
    return jsonify(get_random_paideia_tip(category=cat))


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


@paideia_bp.route('/api/buscar_pelicula')
def buscar_pelicula():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'resultados': []})
    try:
        r = requests.get(_ITUNES_SEARCH_URL, params={
            'term': q,
            'media': 'movie',
            'country': 'US',
            'limit': 6,
        }, timeout=6)
        r.raise_for_status()
        docs = r.json().get('results', [])
    except requests.RequestException:
        return jsonify({'resultados': []})

    resultados = []
    for d in docs:
        titulo = d.get('trackName')
        if not titulo:
            continue
        anio = None
        if d.get('releaseDate'):
            try:
                anio = int(d['releaseDate'][:4])
            except (TypeError, ValueError):
                anio = None
        # iTunes solo da miniaturas 100x100 — se pide la misma URL en
        # mayor resolución cambiando el segmento del tamaño (patrón
        # estable de Apple, no requiere otra llamada ni API key).
        portada = d.get('artworkUrl100')
        if portada:
            portada = portada.replace('100x100bb', '600x600bb')
        resultados.append({
            'titulo': titulo,
            'anio': anio,
            'genero': d.get('primaryGenreName'),
            'portada': portada,
        })
    return jsonify({'resultados': resultados})


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

    vals.append(lid)
    with get_db() as db:
        db.execute(f"UPDATE paideia_libros SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()
    return jsonify({'ok': True})


@paideia_bp.route('/api/libros/<int:lid>', methods=['DELETE'])
def eliminar_libro(lid):
    with get_db() as db:
        db.execute("DELETE FROM paideia_libros WHERE id=?", (lid,))
        db.commit()
    return jsonify({'ok': True})


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
