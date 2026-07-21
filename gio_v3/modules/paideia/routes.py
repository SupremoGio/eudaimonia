from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from database import get_db
from data import get_paideia_tip_of_day, get_random_paideia_tip

paideia_bp = Blueprint('paideia', __name__, template_folder='../../templates')

_META_KEY = 'paideia_meta_anual'
_DEFAULT_META = 12


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
                    rating, fecha_inicio, fecha_fin, notas, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
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
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@paideia_bp.route('/api/libros/<int:lid>', methods=['PATCH'])
def actualizar_libro(lid):
    d = request.json or {}
    sets, vals = [], []
    for f in ('titulo', 'autor', 'categoria', 'estado', 'fecha_inicio', 'fecha_fin', 'notas'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(d[f])
    for f in ('paginas_totales', 'paginas_actuales', 'rating'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(int(d[f]) if d[f] not in (None, '') else None)

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
