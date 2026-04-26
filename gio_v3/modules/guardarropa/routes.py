import os, uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from database import get_db

guardarropa_bp = Blueprint('guardarropa', __name__, template_folder='../../templates')

UPLOAD_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'wardrobe')
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
os.makedirs(UPLOAD_DIR, exist_ok=True)

CATEGORIAS = [
    'Camisa', 'Camiseta', 'Polo', 'Sudadera', 'Suéter',
    'Pantalón', 'Jeans', 'Short', 'Traje / Conjunto',
    'Blazer / Saco', 'Chamarra / Abrigo',
    'Zapatos formales', 'Zapatos casuales', 'Sneakers', 'Botas', 'Sandalias',
    'Accesorio', 'Ropa deportiva', 'Ropa interior / Pijama',
]
OCASIONES  = ['Formal', 'Business', 'Casual', 'Social', 'Deportivo', 'Loungewear']
TEMPORADAS = ['todo', 'verano', 'invierno', 'entretiempo']
ESTADOS    = ['nuevo', 'bueno', 'regular', 'donar']


def _row(r):
    return dict(r)


# ── Pages ─────────────────────────────────────────────────────────────────────

@guardarropa_bp.route('/')
def index():
    with get_db() as db:
        items = [_row(r) for r in db.execute(
            "SELECT * FROM wardrobe_items WHERE activo=1 ORDER BY created_at DESC"
        ).fetchall()]
        outfits_raw = db.execute(
            "SELECT * FROM outfits ORDER BY created_at DESC"
        ).fetchall()
        outfit_items_raw = db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id"
        ).fetchall()

    # group outfit items
    oi_map = {}
    for r in outfit_items_raw:
        oi_map.setdefault(r['outfit_id'], []).append(_row(r))

    outfits = []
    for o in outfits_raw:
        od = _row(o)
        od['items'] = oi_map.get(o['id'], [])
        outfits.append(od)

    return render_template('guardarropa/index.html',
                           items=items, outfits=outfits,
                           categorias=CATEGORIAS, ocasiones=OCASIONES,
                           temporadas=TEMPORADAS, estados=ESTADOS)


# ── Wardrobe items API ────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/items')
def api_items():
    cat = request.args.get('categoria', '')
    oca = request.args.get('ocasion', '')
    q   = request.args.get('q', '').strip()
    sql = "SELECT * FROM wardrobe_items WHERE activo=1"
    params = []
    if cat:
        sql += " AND categoria=?"; params.append(cat)
    if oca:
        sql += " AND ocasion LIKE ?"; params.append(f'%{oca}%')
    if q:
        sql += " AND (nombre LIKE ? OR marca LIKE ? OR notas LIKE ?)"; params += [f'%{q}%']*3
    sql += " ORDER BY created_at DESC"
    with get_db() as db:
        rows = [_row(r) for r in db.execute(sql, params).fetchall()]
    return jsonify(rows)


@guardarropa_bp.route('/api/item', methods=['POST'])
def create_item():
    d   = request.get_json(force=True)
    now = datetime.now().isoformat()
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO wardrobe_items
               (nombre,categoria,subcategoria,color_hex,color_name,marca,
                ocasion,temporada,estado,precio,notas,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_s(d,'nombre'), _s(d,'categoria','Camisa'), _s(d,'subcategoria'),
             _s(d,'color_hex','#C9A84C'), _s(d,'color_name'), _s(d,'marca'),
             _s(d,'ocasion'), _s(d,'temporada','todo'), _s(d,'estado','bueno'),
             float(d.get('precio') or 0), _s(d,'notas'), now)
        )
        db.commit()
        new_id = cur.lastrowid
        row = _row(db.execute("SELECT * FROM wardrobe_items WHERE id=?", (new_id,)).fetchone())
    return jsonify(row), 201


@guardarropa_bp.route('/api/item/<int:iid>', methods=['PUT'])
def update_item(iid):
    d = request.get_json(force=True)
    with get_db() as db:
        db.execute(
            """UPDATE wardrobe_items SET
               nombre=?,categoria=?,subcategoria=?,color_hex=?,color_name=?,marca=?,
               ocasion=?,temporada=?,estado=?,precio=?,notas=?
               WHERE id=?""",
            (_s(d,'nombre'), _s(d,'categoria','Camisa'), _s(d,'subcategoria'),
             _s(d,'color_hex','#C9A84C'), _s(d,'color_name'), _s(d,'marca'),
             _s(d,'ocasion'), _s(d,'temporada','todo'), _s(d,'estado','bueno'),
             float(d.get('precio') or 0), _s(d,'notas'), iid)
        )
        db.commit()
        row = _row(db.execute("SELECT * FROM wardrobe_items WHERE id=?", (iid,)).fetchone())
    return jsonify(row)


@guardarropa_bp.route('/api/item/<int:iid>', methods=['DELETE'])
def delete_item(iid):
    with get_db() as db:
        db.execute("UPDATE wardrobe_items SET activo=0 WHERE id=?", (iid,))
        db.commit()
    return jsonify({'ok': True})


@guardarropa_bp.route('/api/item/<int:iid>/uso', methods=['POST'])
def register_uso(iid):
    with get_db() as db:
        db.execute("UPDATE wardrobe_items SET veces_usado=veces_usado+1 WHERE id=?", (iid,))
        db.commit()
        row = db.execute("SELECT veces_usado FROM wardrobe_items WHERE id=?", (iid,)).fetchone()
    return jsonify({'veces_usado': row['veces_usado']})


# ── Outfits API ───────────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/outfits')
def api_outfits():
    with get_db() as db:
        outfits_raw = db.execute("SELECT * FROM outfits ORDER BY created_at DESC").fetchall()
        oi_raw = db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id"
        ).fetchall()
    oi_map = {}
    for r in oi_raw:
        oi_map.setdefault(r['outfit_id'], []).append(_row(r))
    result = []
    for o in outfits_raw:
        od = _row(o); od['items'] = oi_map.get(o['id'], []); result.append(od)
    return jsonify(result)


@guardarropa_bp.route('/api/outfit', methods=['POST'])
def create_outfit():
    d    = request.get_json(force=True)
    now  = datetime.now().isoformat()
    ids  = [int(x) for x in (d.get('item_ids') or []) if x]
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO outfits (nombre,ocasion,rating,notas,created_at) VALUES (?,?,?,?,?)",
            (_s(d,'nombre'), _s(d,'ocasion'), int(d.get('rating') or 0), _s(d,'notas'), now)
        )
        db.commit()
        oid = cur.lastrowid
        for iid in ids:
            try: db.execute("INSERT INTO outfit_items (outfit_id,item_id) VALUES (?,?)", (oid, iid))
            except Exception: pass
        db.commit()
        row = _row(db.execute("SELECT * FROM outfits WHERE id=?", (oid,)).fetchone())
        row['items'] = [_row(r) for r in db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id WHERE oi.outfit_id=?", (oid,)
        ).fetchall()]
    return jsonify(row), 201


@guardarropa_bp.route('/api/outfit/<int:oid>', methods=['PUT'])
def update_outfit(oid):
    d   = request.get_json(force=True)
    ids = [int(x) for x in (d.get('item_ids') or []) if x]
    with get_db() as db:
        db.execute(
            "UPDATE outfits SET nombre=?,ocasion=?,rating=?,notas=? WHERE id=?",
            (_s(d,'nombre'), _s(d,'ocasion'), int(d.get('rating') or 0), _s(d,'notas'), oid)
        )
        db.execute("DELETE FROM outfit_items WHERE outfit_id=?", (oid,))
        for iid in ids:
            try: db.execute("INSERT INTO outfit_items (outfit_id,item_id) VALUES (?,?)", (oid, iid))
            except Exception: pass
        db.commit()
        row = _row(db.execute("SELECT * FROM outfits WHERE id=?", (oid,)).fetchone())
        row['items'] = [_row(r) for r in db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id WHERE oi.outfit_id=?", (oid,)
        ).fetchall()]
    return jsonify(row)


@guardarropa_bp.route('/api/outfit/<int:oid>', methods=['DELETE'])
def delete_outfit(oid):
    with get_db() as db:
        db.execute("DELETE FROM outfit_items WHERE outfit_id=?", (oid,))
        db.execute("DELETE FROM outfits WHERE id=?", (oid,))
        db.commit()
    return jsonify({'ok': True})


# ── Photo upload ──────────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/upload/<int:iid>', methods=['POST'])
def upload_photo(iid):
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido'}), 400
    filename = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, filename))
    with get_db() as db:
        # remove old photo file if exists
        old = db.execute("SELECT foto FROM wardrobe_items WHERE id=?", (iid,)).fetchone()
        if old and old['foto']:
            try: os.remove(os.path.join(UPLOAD_DIR, old['foto']))
            except OSError: pass
        db.execute("UPDATE wardrobe_items SET foto=? WHERE id=?", (filename, iid))
        db.commit()
    return jsonify({'ok': True, 'filename': filename})


@guardarropa_bp.route('/photos/<filename>')
def serve_photo(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)


# ── helpers ───────────────────────────────────────────────────────────────────

def _s(d, key, default=''):
    v = d.get(key, default)
    return str(v).strip() if v is not None else default
