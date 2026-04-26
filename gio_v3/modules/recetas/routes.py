import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from database import get_db

recetas_bp = Blueprint('recetas', __name__)

CATEGORIAS = ['Desayuno', 'Almuerzo', 'Cena', 'Snack', 'Meal Prep', 'Post-Entrenamiento']


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
    return render_template('recetas/index.html',
                           recetas=recetas,
                           categorias=CATEGORIAS)


@recetas_bp.route('/api/list')
def api_list():
    cat = request.args.get('categoria', '')
    q   = request.args.get('q', '').strip()
    sql = "SELECT * FROM recetas WHERE 1=1"
    params = []
    if cat:
        sql += " AND categoria=?"
        params.append(cat)
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
                video_url, tags, favorita, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
               video_url=?, tags=?, favorita=?
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
