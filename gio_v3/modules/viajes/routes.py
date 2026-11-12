from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, session, redirect, has_request_context
from database import get_db
from utils import today_str, today_date

viajes_bp = Blueprint('viajes', __name__, template_folder='../../templates')

# ── Extras estándar que siempre se sugieren ───────────────────────────────────
EXTRAS_ESTANDAR = [
    # (nombre, categoría, cantidad, no_regresa) — los consumibles se gastan en
    # el viaje y no cuentan en el checklist de regreso.
    ("Identificación / Pasaporte",    "Documentos",  1, 0),
    ("Tarjetas bancarias",            "Documentos",  1, 0),
    ("Efectivo",                      "Documentos",  1, 0),
    ("Cepillo de dientes",            "Higiene",     1, 0),
    ("Pasta dental",                  "Higiene",     1, 1),
    ("Desodorante",                   "Higiene",     1, 0),
    ("Shampoo",                       "Higiene",     1, 1),
    ("Jabón corporal",                "Higiene",     1, 1),
    ("Cargador de celular",           "Tecnología",  1, 0),
    ("Auriculares",                   "Tecnología",  1, 0),
    ("Power bank",                    "Tecnología",  1, 0),
    ("Medicamentos personales",       "Salud",       1, 0),
    ("Bolsa para ropa sucia",         "Varios",      1, 0),
]


def _row(r):
    return dict(r)


def _fin_ok():
    return bool(has_request_context() and session.get('fin_ok'))


def _presupuesto(d):
    try:
        return max(0.0, round(float(d.get('presupuesto') or 0), 2))
    except (TypeError, ValueError):
        return 0.0


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
    return render_template('viajes/index.html', today=today_str(), fin_ok=_fin_ok())


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
        res = []
        for r in rows:
            t = _row(r)
            t['regreso'] = resultado_regreso(db, r)
            if not _fin_ok():
                t.pop('presupuesto', None)
            res.append(t)
    return jsonify(res)


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
               tipo_clima, ocasion, notas, presupuesto, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (nombre,
             d.get('destino', ''),
             inicio, fin,
             d.get('estado', 'planificado'),
             d.get('tipo_clima', ''),
             d.get('ocasion', ''),
             d.get('notas', ''),
             _presupuesto(d) if _fin_ok() else 0,
             now),
        )
        viaje_id = cur.lastrowid
        _gen_dias(viaje_id, inicio, fin, db)
        _regenerar_maleta(viaje_id, db)      # arranca con los extras estándar
    return jsonify({'ok': True, 'id': viaje_id})


@viajes_bp.route('/api/trips/<int:vid>')
def api_get_trip(vid):
    with get_db() as db:
        v = db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone()
        if not v:
            return jsonify({'error': 'No encontrado'}), 404
        p = preparacion(db, v)
        res = _row(v)
        res.update(total_dias=p['outfits']['total'], packed_ida=p['ida']['hechos'],
                   packed_vuelta=p['vuelta']['hechos'], total_items=p['ida']['total'],
                   preparacion=p, regreso=resultado_regreso(db, v))
        if _fin_ok():
            res['dinero'] = dinero(db, v)
        else:
            res.pop('presupuesto', None)
    return jsonify(res)


def dinero(db, v):
    """Tarjeta «Dinero» (solo con fin_ok): lo gastado según los movimientos
    vinculados (misma suma que el desglose de Oikonomia) y los movimientos en
    las fechas del viaje aún sin vincular (la misma consulta de sugerencias)."""
    from modules.finanzas.estados.routes import _GASTO_FILTER, _MONTO
    gastado = db.execute(f"SELECT COALESCE(SUM({_MONTO}), 0) t FROM est_movimientos "
                         f"WHERE viaje_id=? AND {_GASTO_FILTER}", (v['id'],)).fetchone()['t'] or 0
    sug = db.execute(f"""SELECT id, monto, mi_parte FROM est_movimientos
                         WHERE viaje_id IS NULL AND fecha BETWEEN ? AND ? AND {_GASTO_FILTER}
                         ORDER BY fecha ASC, monto DESC LIMIT 100""",
                     (v['fecha_inicio'], v['fecha_fin'])).fetchall()
    pres = v['presupuesto'] or 0
    return {
        'presupuesto': round(pres, 2),
        'gastado': round(gastado, 2),
        'restan': round(pres - gastado, 2),
        'pct': round(gastado / pres * 100) if pres > 0 else None,
        'sugeridos': {'n': len(sug), 'ids': [r['id'] for r in sug],
                      'total': round(sum(abs(r['mi_parte'] if r['mi_parte'] is not None else r['monto']) for r in sug), 2)},
    }


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
            "SELECT fecha_inicio, fecha_fin, estado FROM viajes WHERE id=?", (vid,)
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
        if _fin_ok() and 'presupuesto' in d:
            db.execute("UPDATE viajes SET presupuesto=? WHERE id=?", (_presupuesto(d), vid))
        cerrar_viaje(db, vid, d.get('estado', 'planificado'), old['estado'])
        # Si cambian las fechas, regenerar días (conserva outfits de días que sigan existiendo)
        if old['fecha_inicio'] != inicio or old['fecha_fin'] != fin:
            # Eliminar días fuera del nuevo rango
            db.execute(
                "DELETE FROM viaje_dia_outfits WHERE dia_id IN (SELECT id FROM viaje_dias "
                "WHERE viaje_id=? AND (fecha < ? OR fecha > ?))", (vid, inicio, fin),
            )
            db.execute(
                "DELETE FROM viaje_dias WHERE viaje_id=? AND (fecha < ? OR fecha > ?)",
                (vid, inicio, fin),
            )
            _gen_dias(vid, inicio, fin, db)
            _regenerar_maleta(vid, db)
    return jsonify({'ok': True})


@viajes_bp.route('/api/trips/<int:vid>', methods=['DELETE'])
def api_delete_trip(vid):
    with get_db() as db:
        # `viajes` es la tabla compartida con el presupuesto de viaje
        # (modules/finanzas/estados/routes.py) — desvincular sus movimientos
        # tageados antes de borrar, igual que hace ese módulo.
        db.execute("UPDATE est_movimientos SET viaje_id=NULL WHERE viaje_id=?", (vid,))
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
        return jsonify(_tras_outfit(db, vid))


@viajes_bp.route('/api/trips/<int:vid>/dias/<int:dia_id>/outfit', methods=['DELETE'])
def api_remove_outfit(vid, dia_id):
    with get_db() as db:
        db.execute("DELETE FROM viaje_dia_outfits WHERE dia_id=? AND dia_id IN "
                   "(SELECT id FROM viaje_dias WHERE viaje_id=?)", (dia_id, vid))
        return jsonify(_tras_outfit(db, vid))


def _tras_outfit(db, vid):
    """Respuesta de asignar/quitar outfit: la maleta ya regenerada y los medidores."""
    _regenerar_maleta(vid, db)
    v = db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone()
    return {'ok': True, 'maleta': _maleta(db, vid), 'preparacion': preparacion(db, v)}


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
        items = _maleta(db, vid)
    return jsonify(items)


def _regenerar_maleta(vid, db, extras=False):
    """Recalcula las prendas de la maleta desde los outfits asignados por día.

    Conserva los checks (ida/vuelta) y `no_regresa` de las prendas que ya
    estaban, no toca los ítems manuales (es_extra=1) y siembra los extras
    estándar solo si el viaje aún no tiene ninguno (o si `extras=True`, el
    botón «Generar» de compatibilidad, que repone los que falten).
    Devuelve cuántas prendas salieron de los outfits, o None si no existe."""
    viaje = db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone()
    if not viaje:
        return None

    outfit_items = db.execute("""
        SELECT wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto,
               COUNT(DISTINCT vd.id) AS dias_uso
        FROM viaje_dia_outfits vdo
        JOIN viaje_dias vd ON vd.id=vdo.dia_id AND vd.viaje_id=?
        JOIN outfit_items oi ON oi.outfit_id=vdo.outfit_id
        JOIN wardrobe_items wi ON wi.id=oi.item_id AND wi.activo=1
        GROUP BY wi.id
    """, (vid,)).fetchall()

    inicio = date.fromisoformat(viaje['fecha_inicio'])
    fin    = date.fromisoformat(viaje['fecha_fin'])
    noches = (fin - inicio).days

    # Conservar el check de empacado de las prendas que ya estaban (se regenera
    # cada vez que se asigna/quita un outfit: no debe resetear lo ya marcado)
    prev = {
        r['item_id']: (r['packed_ida'], r['packed_vuelta'], r['no_regresa'] or 0)
        for r in db.execute(
            "SELECT item_id, packed_ida, packed_vuelta, no_regresa FROM viaje_maleta "
            "WHERE viaje_id=? AND es_extra=0 AND item_id IS NOT NULL", (vid,)
        ).fetchall()
    }
    # Prendas que el usuario ya agregó a mano: no se duplican
    manuales = {r['item_id'] for r in db.execute(
        "SELECT item_id FROM viaje_maleta WHERE viaje_id=? AND es_extra=1 AND item_id IS NOT NULL", (vid,)
    ).fetchall()}

    db.execute("DELETE FROM viaje_maleta WHERE viaje_id=? AND es_extra=0", (vid,))

    filas = [
        (vid, r['nombre'], _categorize(r['categoria']),
         _smart_quantity(r['categoria'], r['dias_uso'], noches),
         *prev.get(r['id'], (0, 0, 0)), r['id'])
        for r in outfit_items if r['id'] not in manuales
    ]
    if filas:
        db.executemany(
            """INSERT INTO viaje_maleta
               (viaje_id, nombre, categoria, cantidad, packed_ida, packed_vuelta,
                no_regresa, es_extra, item_id)
               VALUES (?,?,?,?,?,?,?,0,?)""", filas)

    existentes = {r['nombre'] for r in db.execute(
        "SELECT nombre FROM viaje_maleta WHERE viaje_id=?", (vid,)
    ).fetchall()}
    sembrados = any(n in existentes for n, *_ in EXTRAS_ESTANDAR)
    if extras or not sembrados:
        db.executemany(
            """INSERT INTO viaje_maleta
               (viaje_id, nombre, categoria, cantidad, packed_ida, packed_vuelta,
                no_regresa, es_extra, item_id)
               VALUES (?,?,?,?,0,0,?,1,NULL)""",
            [(vid, n, c, q, nr) for n, c, q, nr in EXTRAS_ESTANDAR if n not in existentes],
        )
    return len(outfit_items)


def _maleta(db, vid):
    """Maleta del viaje con `dias_uso`: en cuántos días aparece cada prenda."""
    usos = {r['item_id']: r['n'] for r in db.execute("""
        SELECT oi.item_id, COUNT(DISTINCT vd.id) AS n
        FROM viaje_dias vd
        JOIN viaje_dia_outfits vdo ON vdo.dia_id=vd.id
        JOIN outfit_items oi ON oi.outfit_id=vdo.outfit_id
        WHERE vd.viaje_id=? GROUP BY oi.item_id
    """, (vid,)).fetchall()}
    items = [_row(r) for r in db.execute(
        """SELECT vm.*, wi.foto AS item_foto, wi.color_hex AS item_color
           FROM viaje_maleta vm
           LEFT JOIN wardrobe_items wi ON wi.id = vm.item_id
           WHERE vm.viaje_id=? ORDER BY vm.categoria, vm.nombre""",
        (vid,),
    ).fetchall()]
    for m in items:
        m['no_regresa'] = m.get('no_regresa') or 0
        m['dias_uso'] = usos.get(m['item_id'], 0) if m['item_id'] else 0
    return items


def fase(v, hoy=None):
    """'cerrado' si está completado; 'regreso' desde el último día; si no 'antes'."""
    hoy = (hoy or today_date()).isoformat()
    if v['estado'] == 'completado':
        return 'cerrado'
    if hoy >= v['fecha_fin']:
        return 'regreso'
    return 'antes'


def preparacion(db, v, hoy=None):
    """Medidores del viaje: outfits por día, maleta de ida y de vuelta (sin
    consumibles), fase según la fecha y días que faltan para salir."""
    hoy = hoy or today_date()
    vid = v['id']
    dias_total = db.execute("SELECT COUNT(*) c FROM viaje_dias WHERE viaje_id=?", (vid,)).fetchone()['c']
    dias_con = db.execute("""SELECT COUNT(DISTINCT vd.id) c FROM viaje_dias vd
                             JOIN viaje_dia_outfits vdo ON vdo.dia_id=vd.id
                             WHERE vd.viaje_id=?""", (vid,)).fetchone()['c']
    m = db.execute("""SELECT COUNT(*) total,
                             COALESCE(SUM(packed_ida), 0) ida,
                             COALESCE(SUM(CASE WHEN COALESCE(no_regresa,0)=0 THEN 1 END), 0) vuelta_total,
                             COALESCE(SUM(CASE WHEN COALESCE(no_regresa,0)=0 AND packed_vuelta=1 THEN 1 END), 0) vuelta
                      FROM viaje_maleta WHERE viaje_id=?""", (vid,)).fetchone()
    return {
        'outfits': {'dias_con': dias_con, 'total': dias_total},
        'ida': {'hechos': m['ida'], 'total': m['total']},
        'vuelta': {'hechos': m['vuelta'], 'total_sin_consumibles': m['vuelta_total']},
        'fase': fase(v, hoy),
        'dias_para': (date.fromisoformat(v['fecha_inicio']) - hoy).days,
    }


def resultado_regreso(db, v, hoy=None):
    """Para viajes pasados: {olvidados, total}. Usa lo guardado al cerrar
    (viajes.olvidados) o, si aún no se cierra, lo calcula con la maleta."""
    hoy = (hoy or today_date()).isoformat()
    if v['estado'] != 'completado' and v['fecha_fin'] >= hoy:
        return None
    p = preparacion(db, v)
    total = p['vuelta']['total_sin_consumibles']
    if v['olvidados'] is not None and v['estado'] == 'completado':
        return {'olvidados': v['olvidados'], 'total': total}
    if not total:
        return None
    return {'olvidados': total - p['vuelta']['hechos'], 'total': total}


def cerrar_viaje(db, vid, estado_nuevo, estado_viejo):
    """Al pasar a «completado» guarda cuántos ítems no regresaron; si deja de
    estar completado, el resultado se borra (se recalcula al volver a cerrar)."""
    if estado_nuevo == 'completado' and estado_viejo != 'completado':
        p = preparacion(db, db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone())
        db.execute("UPDATE viajes SET olvidados=? WHERE id=?",
                   (p['vuelta']['total_sin_consumibles'] - p['vuelta']['hechos'], vid))
    elif estado_nuevo != 'completado' and estado_viejo == 'completado':
        db.execute("UPDATE viajes SET olvidados=NULL WHERE id=?", (vid,))


# ── Sugerencias de outfit por día ─────────────────────────────────────────────

# Tipo de viaje → ocasiones de Guardarropa compatibles
_OCASION_VIAJE = {
    'negocios': ('business', 'formal'),
    'formal':   ('formal', 'business', 'social'),
    'casual':   ('casual', 'social'),
    'playa':    ('casual', 'loungewear', 'social'),
    'aventura': ('deportivo', 'casual'),
}
_DIA_FORMAL = ('cena', 'formal', 'boda', 'gala', 'evento', 'junta', 'reunión', 'reunion')
_CLIMA = {'calor': 'calor', 'frio': 'frío', 'templado': 'templado', 'lluvia': 'lluvia'}


def sugerencias(db, vid, dia_id, n=3):
    """Hasta `n` outfits para un día: por ocasión compatible con el tipo de viaje
    y con la descripción del día («cena», «formal»… → formal), sin repetir el
    outfit del día anterior ni el actual, y ordenados por cuántas prendas
    comparten con la maleta (más compartidas = menos peso)."""
    v = db.execute("SELECT * FROM viajes WHERE id=?", (vid,)).fetchone()
    dia = db.execute("SELECT * FROM viaje_dias WHERE id=? AND viaje_id=?", (dia_id, vid)).fetchone()
    if not v or not dia:
        return None
    desc = (dia['descripcion'] or '').lower()
    formal = any(w in desc for w in _DIA_FORMAL)
    if formal:
        ocasiones = ('formal', 'business', 'social')
    else:
        ocasiones = _OCASION_VIAJE.get((v['ocasion'] or '').lower())

    excluir = {r['outfit_id'] for r in db.execute("""
        SELECT vdo.outfit_id FROM viaje_dia_outfits vdo JOIN viaje_dias vd ON vd.id=vdo.dia_id
        WHERE vd.viaje_id=? AND (vd.id=? OR vd.fecha=?)
    """, (vid, dia_id, (date.fromisoformat(dia['fecha']) - timedelta(days=1)).isoformat())).fetchall()}

    en_maleta = {r['item_id'] for r in db.execute(
        "SELECT item_id FROM viaje_maleta WHERE viaje_id=? AND item_id IS NOT NULL", (vid,)).fetchall()}
    prendas = {}
    for r in db.execute("""SELECT oi.outfit_id, oi.item_id FROM outfit_items oi
                           JOIN wardrobe_items wi ON wi.id=oi.item_id AND wi.activo=1""").fetchall():
        prendas.setdefault(r['outfit_id'], set()).add(r['item_id'])

    def compatible(o):
        oc = (o['ocasion'] or '').lower()
        return not ocasiones or not oc or any(x in oc for x in ocasiones)

    cand = [o for o in db.execute("SELECT * FROM outfits ORDER BY nombre").fetchall()
            if o['id'] not in excluir and prendas.get(o['id']) and compatible(o)]
    cand.sort(key=lambda o: (-len(prendas[o['id']] & en_maleta), -(o['veces_usado'] or 0), o['nombre'].lower()))

    clima = _CLIMA.get(v['tipo_clima'] or '')
    res = []
    for o in cand[:n]:
        comp = len(prendas[o['id']] & en_maleta)
        if formal:
            razon = 'para la ' + desc.split()[0] if desc.startswith('cena') else 'formal'
        else:
            razon = ' · '.join(x for x in ((o['ocasion'] or '').split(',')[0].strip().lower(), clima) if x) or 'tu guardarropa'
        if comp:
            razon += f" · comparte {comp} prenda{'s' if comp != 1 else ''}"
        res.append({'id': o['id'], 'nombre': o['nombre'], 'razon': razon})
    return res


@viajes_bp.route('/api/trips/<int:vid>/dias/<int:dia_id>/sugerencias')
def api_sugerencias(vid, dia_id):
    with get_db() as db:
        s = sugerencias(db, vid, dia_id)
        if s is None:
            return jsonify({'error': 'Día no encontrado'}), 404
        total = db.execute("""SELECT COUNT(DISTINCT o.id) c FROM outfits o
                              JOIN outfit_items oi ON oi.outfit_id=o.id""").fetchone()['c']
    return jsonify({'data': s, 'total': total})


@viajes_bp.route('/api/trips/<int:vid>/maleta/generar', methods=['POST'])
def api_generar_maleta(vid):
    """Compatibilidad: la maleta ya se regenera sola al asignar/quitar outfits."""
    with get_db() as db:
        n = _regenerar_maleta(vid, db, extras=True)
    if n is None:
        return jsonify({'ok': False, 'error': 'Viaje no encontrado'}), 404
    return jsonify({'ok': True, 'outfit_items': n})


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
    if 'no_regresa' in d:
        val = 1 if d.get('no_regresa') else 0
        with get_db() as db:
            cur = db.execute("UPDATE viaje_maleta SET no_regresa=? WHERE id=? AND viaje_id=?",
                             (val, item_id, vid))
            if not cur.rowcount:
                return jsonify({'ok': False, 'error': 'Item no encontrado'}), 404
        return jsonify({'ok': True, 'value': val})
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
