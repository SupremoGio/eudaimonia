from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify
from database import get_db

viajes_bp = Blueprint('viajes', __name__, template_folder='../../templates')

# ── Extras estándar que siempre se sugieren ───────────────────────────────────
EXTRAS_ESTANDAR = [
    ("Identificación / Pasaporte",    "Documentos",  1),
    ("Tarjetas bancarias",            "Documentos",  1),
    ("Efectivo",                      "Documentos",  1),
    ("Cepillo de dientes",            "Higiene",     1),
    ("Pasta dental",                  "Higiene",     1),
    ("Desodorante",                   "Higiene",     1),
    ("Shampoo",                       "Higiene",     1),
    ("Jabón corporal",                "Higiene",     1),
    ("Cargador de celular",           "Tecnología",  1),
    ("Auriculares",                   "Tecnología",  1),
    ("Power bank",                    "Tecnología",  1),
    ("Medicamentos personales",       "Salud",       1),
    ("Bolsa para ropa sucia",         "Varios",      1),
]


def _row(r):
    return dict(r)


def _gen_dias(viaje_id, fecha_inicio_str, fecha_fin_str, db):
    """Genera filas en viaje_dias para cada día del viaje."""
    inicio = date.fromisoformat(fecha_inicio_str)
    fin    = date.fromisoformat(fecha_fin_str)
    dias   = []
    cur    = inicio
    n      = 1
    while cur <= fin:
        dias.append((viaje_id, cur.isoformat(), f"Día {n}"))
        cur += timedelta(days=1)
        n   += 1
    db.executemany(
        "INSERT OR IGNORE INTO viaje_dias (viaje_id, fecha, descripcion) VALUES (?,?,?)",
        dias,
    )


# ── Página principal ──────────────────────────────────────────────────────────

@viajes_bp.route('/')
def index():
    return render_template('viajes/index.html')


# ── API Trips ─────────────────────────────────────────────────────────────────

@viajes_bp.route('/api/trips')
def api_trips():
    with get_db() as db:
        rows = db.execute("""
            SELECT v.*,
                   COUNT(m.id) AS items_packed,
                   (SELECT COUNT(*) FROM viaje_dias WHERE viaje_id=v.id) AS total_dias
            FROM viajes v
            LEFT JOIN viaje_maleta m ON m.viaje_id=v.id AND m.packed_ida=1
            GROUP BY v.id
            ORDER BY v.fecha_inicio DESC
        """).fetchall()
    return jsonify([_row(r) for r in rows])


@viajes_bp.route('/api/trips', methods=['POST'])
def api_create_trip():
    d = request.get_json(silent=True) or {}
    nombre  = (d.get('nombre') or '').strip()
    inicio  = (d.get('fecha_inicio') or '').strip()
    fin     = (d.get('fecha_fin') or '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre obligatorio'}), 400
    if not inicio or not fin:
        return jsonify({'ok': False, 'error': 'Fechas obligatorias'}), 400
    if fin < inicio:
        return jsonify({'ok': False, 'error': 'La fecha fin debe ser posterior al inicio'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO viajes (nombre, destino, fecha_inicio, fecha_fin, estado,
               tipo_clima, ocasion, notas, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (nombre,
             d.get('destino', ''),
             inicio, fin,
             d.get('estado', 'planificado'),
             d.get('tipo_clima', ''),
             d.get('ocasion', ''),
             d.get('notas', ''),
             now),
        )
        viaje_id = cur.lastrowid
        _gen_dias(viaje_id, inicio, fin, db)
    return jsonify({'ok': True, 'id': viaje_id})


@viajes_bp.route('/api/trips/<int:vid>')
def api_get_trip(vid):
    with get_db() as db:
        v = db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone()
        if not v:
            return jsonify({'error': 'No encontrado'}), 404
        total_dias = db.execute(
            "SELECT COUNT(*) as c FROM viaje_dias WHERE viaje_id=?", (vid,)
        ).fetchone()['c']
        packed_ida    = db.execute(
            "SELECT COUNT(*) as c FROM viaje_maleta WHERE viaje_id=? AND packed_ida=1", (vid,)
        ).fetchone()['c']
        packed_vuelta = db.execute(
            "SELECT COUNT(*) as c FROM viaje_maleta WHERE viaje_id=? AND packed_vuelta=1", (vid,)
        ).fetchone()['c']
        total_items = db.execute(
            "SELECT COUNT(*) as c FROM viaje_maleta WHERE viaje_id=?", (vid,)
        ).fetchone()['c']
    res = _row(v)
    res.update(total_dias=total_dias, packed_ida=packed_ida,
               packed_vuelta=packed_vuelta, total_items=total_items)
    return jsonify(res)


@viajes_bp.route('/api/trips/<int:vid>', methods=['PATCH'])
def api_update_trip(vid):
    d = request.get_json(silent=True) or {}
    nombre = (d.get('nombre') or '').strip()
    inicio = (d.get('fecha_inicio') or '').strip()
    fin    = (d.get('fecha_fin') or '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre obligatorio'}), 400
    if not inicio or not fin or fin < inicio:
        return jsonify({'ok': False, 'error': 'Fechas inválidas'}), 400
    with get_db() as db:
        old = db.execute(
            "SELECT fecha_inicio, fecha_fin FROM viajes WHERE id=?", (vid,)
        ).fetchone()
        if not old:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        db.execute(
            """UPDATE viajes SET nombre=?, destino=?, fecha_inicio=?, fecha_fin=?,
               estado=?, tipo_clima=?, ocasion=?, notas=? WHERE id=?""",
            (nombre, d.get('destino',''), inicio, fin,
             d.get('estado','planificado'), d.get('tipo_clima',''),
             d.get('ocasion',''), d.get('notas',''), vid),
        )
        # Si cambian las fechas, regenerar días (conserva outfits de días que sigan existiendo)
        if old['fecha_inicio'] != inicio or old['fecha_fin'] != fin:
            # Eliminar días fuera del nuevo rango
            db.execute(
                "DELETE FROM viaje_dias WHERE viaje_id=? AND (fecha < ? OR fecha > ?)",
                (vid, inicio, fin),
            )
            _gen_dias(vid, inicio, fin, db)
    return jsonify({'ok': True})


@viajes_bp.route('/api/trips/<int:vid>', methods=['DELETE'])
def api_delete_trip(vid):
    with get_db() as db:
        db.execute("DELETE FROM viaje_maleta    WHERE viaje_id=?", (vid,))
        db.execute("DELETE FROM viaje_dia_outfits WHERE dia_id IN "
                   "(SELECT id FROM viaje_dias WHERE viaje_id=?)", (vid,))
        db.execute("DELETE FROM viaje_dias      WHERE viaje_id=?", (vid,))
        db.execute("DELETE FROM viajes          WHERE id=?", (vid,))
    return jsonify({'ok': True})


# ── API Días ──────────────────────────────────────────────────────────────────

@viajes_bp.route('/api/trips/<int:vid>/dias')
def api_dias(vid):
    with get_db() as db:
        dias = [_row(r) for r in db.execute(
            "SELECT * FROM viaje_dias WHERE viaje_id=? ORDER BY fecha", (vid,)
        ).fetchall()]
        # Cargar outfits asignados por día
        outfits_raw = db.execute("""
            SELECT vdo.dia_id, o.id, o.nombre, o.foto, o.ocasion,
                   GROUP_CONCAT(wi.nombre, ' · ') AS prendas
            FROM viaje_dia_outfits vdo
            JOIN outfits o ON o.id=vdo.outfit_id
            LEFT JOIN outfit_items oi ON oi.outfit_id=o.id
            LEFT JOIN wardrobe_items wi ON wi.id=oi.item_id
            WHERE vdo.dia_id IN (SELECT id FROM viaje_dias WHERE viaje_id=?)
            GROUP BY vdo.dia_id, o.id
        """, (vid,)).fetchall()

    outfit_map = {}
    for r in outfits_raw:
        outfit_map.setdefault(r['dia_id'], []).append(_row(r))

    for d in dias:
        d['outfits'] = outfit_map.get(d['id'], [])

    return jsonify(dias)


@viajes_bp.route('/api/trips/<int:vid>/dias/<int:dia_id>/descripcion', methods=['PATCH'])
def api_dia_descripcion(vid, dia_id):
    d = request.get_json(silent=True) or {}
    desc = (d.get('descripcion') or '').strip()
    with get_db() as db:
        db.execute(
            "UPDATE viaje_dias SET descripcion=? WHERE id=? AND viaje_id=?",
            (desc, dia_id, vid),
        )
    return jsonify({'ok': True})


@viajes_bp.route('/api/trips/<int:vid>/dias/<int:dia_id>/outfit', methods=['POST'])
def api_set_outfit(vid, dia_id):
    d = request.get_json(silent=True) or {}
    outfit_id = d.get('outfit_id')
    if not outfit_id:
        return jsonify({'ok': False, 'error': 'outfit_id requerido'}), 400
    with get_db() as db:
        # Verificar que el día pertenece al viaje
        dia = db.execute(
            "SELECT id FROM viaje_dias WHERE id=? AND viaje_id=?", (dia_id, vid)
        ).fetchone()
        if not dia:
            return jsonify({'ok': False, 'error': 'Día no encontrado'}), 404
        # Un outfit por día (reemplaza si ya había)
        db.execute("DELETE FROM viaje_dia_outfits WHERE dia_id=?", (dia_id,))
        db.execute(
            "INSERT INTO viaje_dia_outfits (dia_id, outfit_id) VALUES (?,?)",
            (dia_id, outfit_id),
        )
    return jsonify({'ok': True})


@viajes_bp.route('/api/trips/<int:vid>/dias/<int:dia_id>/outfit', methods=['DELETE'])
def api_remove_outfit(vid, dia_id):
    with get_db() as db:
        db.execute("DELETE FROM viaje_dia_outfits WHERE dia_id=?", (dia_id,))
    return jsonify({'ok': True})


# ── API Outfits (para el picker) ──────────────────────────────────────────────

@viajes_bp.route('/api/outfits')
def api_outfits():
    with get_db() as db:
        outfits = [_row(r) for r in db.execute(
            "SELECT * FROM outfits ORDER BY nombre"
        ).fetchall()]
        items_raw = db.execute("""
            SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto
            FROM outfit_items oi
            JOIN wardrobe_items wi ON wi.id=oi.item_id
            WHERE wi.activo=1
        """).fetchall()

    items_map = {}
    for r in items_raw:
        items_map.setdefault(r['outfit_id'], []).append(_row(r))

    for o in outfits:
        o['items'] = items_map.get(o['id'], [])

    return jsonify(outfits)


# ── API Prendas del guardarropa (para agregar individualmente a la maleta) ────

@viajes_bp.route('/api/wardrobe-items')
def api_wardrobe_items():
    with get_db() as db:
        items = [_row(r) for r in db.execute(
            """SELECT id, nombre, categoria, color_hex, foto
               FROM wardrobe_items WHERE activo=1 ORDER BY categoria, nombre"""
        ).fetchall()]
    return jsonify(items)


# ── API Maleta ────────────────────────────────────────────────────────────────

@viajes_bp.route('/api/trips/<int:vid>/maleta')
def api_maleta(vid):
    with get_db() as db:
        items = [_row(r) for r in db.execute(
            """SELECT vm.*, wi.foto AS item_foto, wi.color_hex AS item_color
               FROM viaje_maleta vm
               LEFT JOIN wardrobe_items wi ON wi.id = vm.item_id
               WHERE vm.viaje_id=? ORDER BY vm.categoria, vm.nombre""",
            (vid,),
        ).fetchall()]
    return jsonify(items)


@viajes_bp.route('/api/trips/<int:vid>/maleta/generar', methods=['POST'])
def api_generar_maleta(vid):
    """Genera la lista de maleta basada en los outfits seleccionados por día."""
    with get_db() as db:
        viaje = db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone()
        if not viaje:
            return jsonify({'ok': False, 'error': 'Viaje no encontrado'}), 404

        # Recopilar todos los wardrobe_items de los outfits asignados en este viaje
        outfit_items = db.execute("""
            SELECT wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto,
                   COUNT(*) AS dias_uso
            FROM viaje_dia_outfits vdo
            JOIN viaje_dias vd ON vd.id=vdo.dia_id AND vd.viaje_id=?
            JOIN outfit_items oi ON oi.outfit_id=vdo.outfit_id
            JOIN wardrobe_items wi ON wi.id=oi.item_id AND wi.activo=1
            GROUP BY wi.id
        """, (vid,)).fetchall()

        # Calcular duración del viaje
        inicio = date.fromisoformat(viaje['fecha_inicio'])
        fin    = date.fromisoformat(viaje['fecha_fin'])
        noches = (fin - inicio).days

        # Conservar el check de empacado de las prendas que ya estaban (se regenera seguido,
        # cada vez que se asigna/quita un outfit, así que no debe resetear lo ya marcado)
        packed_by_item = {
            r['item_id']: (r['packed_ida'], r['packed_vuelta'])
            for r in db.execute(
                "SELECT item_id, packed_ida, packed_vuelta FROM viaje_maleta "
                "WHERE viaje_id=? AND es_extra=0 AND item_id IS NOT NULL", (vid,)
            ).fetchall()
        }

        # Eliminar maleta anterior (solo items de outfits; conservar manuales del usuario)
        db.execute(
            "DELETE FROM viaje_maleta WHERE viaje_id=? AND es_extra=0", (vid,)
        )

        # Insertar items de outfits
        now = datetime.now().isoformat()
        if outfit_items:
            db.executemany(
                """INSERT INTO viaje_maleta
                   (viaje_id, nombre, categoria, cantidad, packed_ida, packed_vuelta,
                    es_extra, item_id)
                   VALUES (?,?,?,?,?,?,0,?)""",
                [
                    (vid, r['nombre'],
                     _categorize(r['categoria']),
                     _smart_quantity(r['categoria'], r['dias_uso'], noches),
                     *packed_by_item.get(r['id'], (0, 0)),
                     r['id'])
                    for r in outfit_items
                ],
            )

        # Insertar extras estándar solo si aún no existen (por nombre)
        existing_nombres = {r['nombre'] for r in db.execute(
            "SELECT nombre FROM viaje_maleta WHERE viaje_id=?", (vid,)
        ).fetchall()}

        extras_to_insert = [
            (vid, nombre, cat, cant, 0, 0, 1, None)
            for nombre, cat, cant in EXTRAS_ESTANDAR
            if nombre not in existing_nombres
        ]
        if extras_to_insert:
            db.executemany(
                """INSERT INTO viaje_maleta
                   (viaje_id, nombre, categoria, cantidad, packed_ida, packed_vuelta,
                    es_extra, item_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                extras_to_insert,
            )

    return jsonify({'ok': True, 'outfit_items': len(outfit_items)})


def _categorize(categoria_guardarropa: str) -> str:
    """Mapea categorías de Guardarropa a categorías de maleta."""
    cat = categoria_guardarropa.lower()
    if any(x in cat for x in ['camisa', 'camiseta', 'polo', 'sudadera', 'suéter', 'sueter']):
        return 'Tops'
    if any(x in cat for x in ['pantalón', 'pantalon', 'jean', 'pants', 'short']):
        return 'Bottoms'
    if any(x in cat for x in ['traje', 'conjunto', 'blazer', 'saco']):
        return 'Formal'
    if any(x in cat for x in ['chamarra', 'abrigo']):
        return 'Abrigo'
    if any(x in cat for x in ['zapato', 'sneaker', 'bota', 'sandalia']):
        return 'Calzado'
    if 'calcet' in cat:
        return 'Ropa interior'
    if 'accesorio' in cat:
        return 'Accesorios'
    return 'Ropa'


def _smart_quantity(categoria: str, dias_uso: int, noches: int) -> int:
    """Determina cuántas unidades llevar de una prenda."""
    cat = categoria.lower()
    # Calcetas / ropa interior: una por día
    if any(x in cat for x in ['calcet', 'interior', 'ropa interior']):
        return min(dias_uso, noches + 1)
    # Calzado: siempre 1 par
    if any(x in cat for x in ['zapato', 'sneaker', 'bota', 'sandalia']):
        return 1
    # Accesorios: 1
    if 'accesorio' in cat:
        return 1
    # El resto: 1 (se puede reusar / lavar)
    return 1


@viajes_bp.route('/api/trips/<int:vid>/maleta/<int:item_id>', methods=['PATCH'])
def api_toggle_maleta(vid, item_id):
    d = request.get_json(silent=True) or {}
    field = d.get('field', 'packed_ida')
    if field not in ('packed_ida', 'packed_vuelta'):
        return jsonify({'ok': False, 'error': 'Campo inválido'}), 400
    with get_db() as db:
        cur_val = db.execute(
            f"SELECT {field} FROM viaje_maleta WHERE id=? AND viaje_id=?",
            (item_id, vid),
        ).fetchone()
        if not cur_val:
            return jsonify({'ok': False, 'error': 'Item no encontrado'}), 404
        new_val = 0 if cur_val[field] else 1
        db.execute(
            f"UPDATE viaje_maleta SET {field}=? WHERE id=? AND viaje_id=?",
            (new_val, item_id, vid),
        )
    return jsonify({'ok': True, 'value': new_val})


@viajes_bp.route('/api/trips/<int:vid>/maleta/item', methods=['POST'])
def api_add_maleta_item(vid):
    d = request.get_json(silent=True) or {}
    nombre = (d.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO viaje_maleta
               (viaje_id, nombre, categoria, cantidad, packed_ida, packed_vuelta, es_extra, item_id)
               VALUES (?,?,?,1,0,0,1,NULL)""",
            (vid, nombre, (d.get('categoria') or 'Varios').strip()),
        )
    return jsonify({'ok': True, 'id': cur.lastrowid})


@viajes_bp.route('/api/trips/<int:vid>/maleta/item-from-wardrobe', methods=['POST'])
def api_add_maleta_item_from_wardrobe(vid):
    """Agrega una prenda puntual del Guardarropa a la maleta, sin pasar por un outfit."""
    d = request.get_json(silent=True) or {}
    item_id = d.get('item_id')
    if not item_id:
        return jsonify({'ok': False, 'error': 'item_id requerido'}), 400
    with get_db() as db:
        wi = db.execute(
            "SELECT * FROM wardrobe_items WHERE id=? AND activo=1", (item_id,)
        ).fetchone()
        if not wi:
            return jsonify({'ok': False, 'error': 'Prenda no encontrada'}), 404
        existing = db.execute(
            "SELECT id FROM viaje_maleta WHERE viaje_id=? AND item_id=?", (vid, item_id)
        ).fetchone()
        if existing:
            return jsonify({'ok': False, 'error': 'Esa prenda ya está en tu maleta'}), 400
        cur = db.execute(
            """INSERT INTO viaje_maleta
               (viaje_id, nombre, categoria, cantidad, packed_ida, packed_vuelta, es_extra, item_id)
               VALUES (?,?,?,1,0,0,1,?)""",
            (vid, wi['nombre'], _categorize(wi['categoria']), item_id),
        )
    return jsonify({'ok': True, 'id': cur.lastrowid})


@viajes_bp.route('/api/trips/<int:vid>/maleta/<int:item_id>', methods=['DELETE'])
def api_delete_maleta_item(vid, item_id):
    with get_db() as db:
        db.execute(
            "DELETE FROM viaje_maleta WHERE id=? AND viaje_id=?", (item_id, vid)
        )
    return jsonify({'ok': True})
