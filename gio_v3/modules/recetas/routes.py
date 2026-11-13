import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from database import get_db

recetas_bp = Blueprint('recetas', __name__)

CATEGORIAS = ['Desayuno', 'Almuerzo', 'Cena', 'Snack', 'Meal Prep', 'Post-Entrenamiento']
# Un solo recetario (Nutrición v2): etiqueta FODMAP y momentos del plan
FODMAP = ['seguro', 'porcion', 'evitar']
MOMENTOS = [('desayuno', 'Desayuno'), ('colacion', 'Colación'), ('comida', 'Comida'), ('pregym', 'Pre-gym'), ('cena', 'Cena')]


def _fodmap(d):
    v = (d.get('fodmap') or '').strip().lower()
    return v if v in FODMAP else None


def _momento(d):
    m = d.get('momento') or []
    if isinstance(m, str):
        m = m.split(',')
    validos = {k for k, _ in MOMENTOS}
    return ','.join(x.strip() for x in m if x.strip() in validos)


# ── «Para hoy» (Remates · Recetas S1) ─────────────────────────────────────────
# Lee el plan del día de Nutrición (nutricion_semana de hoy) sin sembrarlo: si
# hoy no hay plan, no hay bloque. Por cada momento sin receta asignada y sin
# comer todavía, 3 recetas aptas FODMAP de ese momento: favoritas primero,
# luego las menos usadas en 14 días. «Usar» llama a POST /nutricion/api/comida
# con receta_id, que guarda nutricion_semana.receta_id.
SUGERENCIAS_POR_MOMENTO = 3
USO_DIAS = 14
_DIAS = 'LMXJVSD'


def _norm(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', (s or '').lower()) if unicodedata.category(c) != 'Mn').strip()


def para_hoy(db, hoy=None):
    """[{slot, time, momento, sugerencias: [{id, nombre, calorias, proteina, favorita, usos}]}];
    [] si Nutrición no tiene plan para hoy."""
    from datetime import timedelta
    from utils import today_date
    from modules.nutricion.routes import momento_de_slot
    hoy = hoy or today_date()
    week = (hoy - timedelta(days=hoy.weekday())).isoformat()
    dia = _DIAS[hoy.weekday()]
    try:
        plan = db.execute("SELECT * FROM nutricion_semana WHERE week_start=? AND day_key=? ORDER BY time_str, id",
                          (week, dia)).fetchall()
    except Exception:
        return []
    if not plan:
        return []
    recetas = db.execute("SELECT id, nombre, calorias, proteina, favorita, fodmap, momento FROM recetas").fetchall()
    por_nombre = {_norm(r['nombre']): r['id'] for r in recetas}

    def receta_de(m):
        rid = m['receta_id'] if 'receta_id' in m.keys() else None
        if rid:
            return rid
        # comidas del recetario anteriores a receta_id: mismo nombre y agregadas a mano
        return por_nombre.get(_norm(m['name'])) if m['custom'] else None

    # Usos en los últimos 14 días (hoy incluido)
    desde = hoy - timedelta(days=USO_DIAS - 1)
    usos = {}
    for m in db.execute("SELECT * FROM nutricion_semana WHERE week_start>=?",
                        ((desde - timedelta(days=desde.weekday())).isoformat(),)).fetchall():
        try:
            f = date_from(m['week_start'], m['day_key'])
        except Exception:
            continue
        rid = receta_de(m)
        if rid and desde <= f <= hoy:
            usos[rid] = usos.get(rid, 0) + 1

    slots, orden = {}, []
    for m in plan:
        s = slots.get(m['slot'])
        if s is None:
            s = slots[m['slot']] = {'slot': m['slot'], 'time': m['time_str'], 'con_receta': False, 'hecho': False}
            orden.append(m['slot'])
        s['con_receta'] = s['con_receta'] or bool(receta_de(m))
        s['hecho'] = s['hecho'] or bool(m['done'])

    out = []
    for nombre in orden:
        s = slots[nombre]
        if s['con_receta'] or s['hecho']:
            continue
        mom = momento_de_slot(nombre)
        aptas = [r for r in recetas if r['fodmap'] == 'seguro'
                 and mom in [x.strip() for x in (r['momento'] or '').split(',')]]
        aptas.sort(key=lambda r: (not r['favorita'], usos.get(r['id'], 0), r['nombre'].lower()))
        sug = [{'id': r['id'], 'nombre': r['nombre'], 'calorias': r['calorias'] or 0,
                'proteina': round(r['proteina'] or 0), 'favorita': bool(r['favorita']), 'usos': usos.get(r['id'], 0)}
               for r in aptas[:SUGERENCIAS_POR_MOMENTO]]
        if sug:
            out.append({'slot': nombre, 'time': s['time'], 'momento': mom, 'sugerencias': sug})
    return out


def date_from(week_start, day_key):
    from datetime import date, timedelta
    return date.fromisoformat(week_start) + timedelta(days=_DIAS.index(day_key))


def _row(r):
    d = dict(r)
    for f in ('ingredientes', 'instrucciones'):
        try:
            d[f] = json.loads(d[f]) if d[f] else []
        except Exception:
            d[f] = []
    return d


@recetas_bp.route('/')
def index():
    with get_db() as db:
        recetas = [_row(r) for r in db.execute(
            "SELECT * FROM recetas ORDER BY favorita DESC, created_at DESC"
        ).fetchall()]
        hoy_plan = para_hoy(db)
    return render_template('recetas/index.html',
                           recetas=recetas, para_hoy=hoy_plan,
                           categorias=CATEGORIAS, momentos=MOMENTOS,
                           fodmap_sel=request.args.get('fodmap') == 'seguro')


@recetas_bp.route('/api/para-hoy')
def api_para_hoy():
    with get_db() as db:
        return jsonify(para_hoy(db))


@recetas_bp.route('/api/list')
def api_list():
    cat = request.args.get('categoria', '')
    q   = request.args.get('q', '').strip()
    sql = "SELECT * FROM recetas WHERE 1=1"
    params = []
    if cat:
        sql += " AND categoria=?"
        params.append(cat)
    if request.args.get('fodmap') in FODMAP:
        sql += " AND fodmap=?"
        params.append(request.args.get('fodmap'))
    if q:
        sql += " AND (nombre LIKE ? OR tags LIKE ? OR ingredientes LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    sql += " ORDER BY favorita DESC, created_at DESC"
    with get_db() as db:
        rows = [_row(r) for r in db.execute(sql, params).fetchall()]
    return jsonify(rows)


@recetas_bp.route('/api/recipe', methods=['POST'])
def create():
    d = request.get_json(force=True)
    now = datetime.now().isoformat()
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO recetas
               (nombre, categoria, descripcion, ingredientes, instrucciones,
                calorias, proteina, carbos, grasa,
                tiempo_prep, tiempo_coccion, porciones,
                video_url, tags, favorita, fodmap, momento, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d.get('nombre', '').strip(),
                d.get('categoria', 'Almuerzo'),
                d.get('descripcion', ''),
                json.dumps(d.get('ingredientes', []), ensure_ascii=False),
                json.dumps(d.get('instrucciones', []), ensure_ascii=False),
                int(d.get('calorias', 0) or 0),
                float(d.get('proteina', 0) or 0),
                float(d.get('carbos', 0) or 0),
                float(d.get('grasa', 0) or 0),
                int(d.get('tiempo_prep', 0) or 0),
                int(d.get('tiempo_coccion', 0) or 0),
                int(d.get('porciones', 1) or 1),
                d.get('video_url', ''),
                d.get('tags', ''),
                1 if d.get('favorita') else 0,
                _fodmap(d), _momento(d),
                now,
            )
        )
        db.commit()
        new_id = cur.lastrowid
        row = _row(db.execute("SELECT * FROM recetas WHERE id=?", (new_id,)).fetchone())
    return jsonify(row), 201


@recetas_bp.route('/api/recipe/<int:rid>', methods=['PUT'])
def update(rid):
    d = request.get_json(force=True)
    with get_db() as db:
        db.execute(
            """UPDATE recetas SET
               nombre=?, categoria=?, descripcion=?, ingredientes=?, instrucciones=?,
               calorias=?, proteina=?, carbos=?, grasa=?,
               tiempo_prep=?, tiempo_coccion=?, porciones=?,
               video_url=?, tags=?, favorita=?, fodmap=?, momento=?
               WHERE id=?""",
            (
                d.get('nombre', '').strip(),
                d.get('categoria', 'Almuerzo'),
                d.get('descripcion', ''),
                json.dumps(d.get('ingredientes', []), ensure_ascii=False),
                json.dumps(d.get('instrucciones', []), ensure_ascii=False),
                int(d.get('calorias', 0) or 0),
                float(d.get('proteina', 0) or 0),
                float(d.get('carbos', 0) or 0),
                float(d.get('grasa', 0) or 0),
                int(d.get('tiempo_prep', 0) or 0),
                int(d.get('tiempo_coccion', 0) or 0),
                int(d.get('porciones', 1) or 1),
                d.get('video_url', ''),
                d.get('tags', ''),
                1 if d.get('favorita') else 0,
                _fodmap(d), _momento(d),
                rid,
            )
        )
        db.commit()
        row = _row(db.execute("SELECT * FROM recetas WHERE id=?", (rid,)).fetchone())
    return jsonify(row)


@recetas_bp.route('/api/recipe/<int:rid>', methods=['DELETE'])
def delete(rid):
    with get_db() as db:
        db.execute("DELETE FROM recetas WHERE id=?", (rid,))
        db.commit()
    return jsonify({'ok': True})


@recetas_bp.route('/api/recipe/<int:rid>/favorita', methods=['POST'])
def toggle_favorita(rid):
    with get_db() as db:
        cur = db.execute("SELECT favorita FROM recetas WHERE id=?", (rid,)).fetchone()
        if not cur:
            return jsonify({'error': 'not found'}), 404
        new_val = 0 if cur['favorita'] else 1
        db.execute("UPDATE recetas SET favorita=? WHERE id=?", (new_val, rid))
        db.commit()
    return jsonify({'favorita': bool(new_val)})
