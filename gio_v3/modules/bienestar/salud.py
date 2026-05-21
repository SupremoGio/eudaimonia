from flask import Blueprint, render_template, request, jsonify
from database import get_db
from datetime import datetime

medico_bp = Blueprint('medico', __name__, template_folder='../../templates')


def _now():
    return datetime.now().isoformat()


def _today():
    return datetime.now().date().isoformat()


# ── Index ─────────────────────────────────────────────────────────────────────

@medico_bp.route('/')
def index():
    with get_db() as db:
        rows = db.execute("""
            SELECT e.*,
                   COUNT(DISTINCT r.id)                              AS num_recetas,
                   COALESCE(SUM(CASE WHEN m.tomando=1 THEN 1 ELSE 0 END), 0) AS meds_activos
            FROM   medico_episodios e
            LEFT JOIN medico_recetas     r ON r.episodio_id = e.id
            LEFT JOIN medico_medicamentos m ON m.receta_id  = r.id
            GROUP  BY e.id
            ORDER  BY e.activo DESC, e.fecha_inicio DESC
        """).fetchall()

        episodios = [dict(r) for r in rows]

        activos       = sum(1 for e in episodios if e['activo'])
        meds_activos  = sum(e['meds_activos'] for e in episodios if e['activo'])
        ultimo_inicio = episodios[0]['fecha_inicio'] if episodios else None

        # ── Analytics ────────────────────────────────────────────────────────
        recovery = [dict(r) for r in db.execute("""
            SELECT tipo,
                   ROUND(AVG(julianday(fecha_fin) - julianday(fecha_inicio)), 1) AS avg_dias,
                   COUNT(*) AS total
            FROM   medico_episodios
            WHERE  fecha_fin IS NOT NULL AND activo = 0
            GROUP  BY tipo
            ORDER  BY avg_dias DESC
        """).fetchall()]

        monthly = [dict(r) for r in db.execute("""
            SELECT strftime('%Y-%m', fecha_inicio) AS mes,
                   COUNT(*) AS total
            FROM   medico_episodios
            WHERE  fecha_inicio >= date('now', '-6 months')
            GROUP  BY mes
            ORDER  BY mes
        """).fetchall()]

        zonas = [dict(r) for r in db.execute("""
            SELECT zona_cuerpo, COUNT(*) AS cnt
            FROM   medico_episodios
            WHERE  zona_cuerpo IS NOT NULL AND zona_cuerpo != ''
            GROUP  BY LOWER(zona_cuerpo)
            ORDER  BY cnt DESC
            LIMIT  5
        """).fetchall()]

        recurrencia = [dict(r) for r in db.execute("""
            SELECT titulo,
                   COUNT(*) AS veces,
                   MIN(fecha_inicio) AS primera,
                   MAX(fecha_inicio) AS ultima,
                   CAST(julianday(MAX(fecha_inicio)) - julianday(MIN(fecha_inicio)) AS INTEGER) AS dias_entre
            FROM   medico_episodios
            GROUP  BY LOWER(titulo)
            HAVING COUNT(*) > 1
            ORDER  BY veces DESC, dias_entre ASC
        """).fetchall()]

        top_meds = [dict(r) for r in db.execute("""
            SELECT m.nombre, COUNT(*) AS cnt
            FROM   medico_medicamentos m
            GROUP  BY LOWER(m.nombre)
            ORDER  BY cnt DESC
            LIMIT  4
        """).fetchall()]

    return render_template(
        'bienestar/salud.html',
        episodios=episodios,
        stats=dict(
            activos=activos,
            meds_activos=meds_activos,
            total=len(episodios),
            ultimo=ultimo_inicio,
        ),
        analytics=dict(
            recovery=recovery,
            monthly=monthly,
            zonas=zonas,
            recurrencia=recurrencia,
            top_meds=top_meds,
        ),
    )


# ── Episodios CRUD ────────────────────────────────────────────────────────────

@medico_bp.route('/api/episodios', methods=['POST'])
def crear_episodio():
    d = request.json or {}
    if not d.get('titulo'):
        return jsonify({'ok': False, 'error': 'titulo requerido'}), 400
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO medico_episodios
                   (tipo, titulo, descripcion, zona_cuerpo, fecha_inicio, activo, created_at)
               VALUES (?,?,?,?,?,1,?)""",
            (
                d.get('tipo', 'enfermedad'),
                d['titulo'].strip(),
                d.get('descripcion', '').strip(),
                d.get('zona_cuerpo', '').strip(),
                d.get('fecha_inicio') or _today(),
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@medico_bp.route('/api/episodios/<int:eid>', methods=['PATCH'])
def actualizar_episodio(eid):
    d = request.json or {}
    sets, vals = [], []
    for f in ('titulo', 'descripcion', 'zona_cuerpo', 'fecha_inicio', 'fecha_fin'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(d[f])
    if 'activo' in d:
        sets.append('activo=?')
        vals.append(int(d['activo']))
        if not d['activo'] and 'fecha_fin' not in d:
            sets.append('fecha_fin=?')
            vals.append(_today())
    if not sets:
        return jsonify({'ok': False, 'error': 'nada que actualizar'}), 400
    vals.append(eid)
    with get_db() as db:
        db.execute(f"UPDATE medico_episodios SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()
    return jsonify({'ok': True})


@medico_bp.route('/api/episodios/<int:eid>', methods=['DELETE'])
def eliminar_episodio(eid):
    with get_db() as db:
        db.execute("DELETE FROM medico_episodios WHERE id=?", (eid,))
        db.commit()
    return jsonify({'ok': True})


# ── Detalle: recetas + medicamentos de un episodio ────────────────────────────

@medico_bp.route('/api/episodios/<int:eid>/detail')
def episodio_detail(eid):
    with get_db() as db:
        recetas = db.execute(
            "SELECT * FROM medico_recetas WHERE episodio_id=? ORDER BY fecha DESC",
            (eid,),
        ).fetchall()
        result = []
        for r in recetas:
            meds = db.execute(
                "SELECT * FROM medico_medicamentos WHERE receta_id=? ORDER BY created_at",
                (r['id'],),
            ).fetchall()
            result.append({**dict(r), 'medicamentos': [dict(m) for m in meds]})
    return jsonify(result)


# ── Recetas CRUD ──────────────────────────────────────────────────────────────

@medico_bp.route('/api/recetas', methods=['POST'])
def crear_receta():
    d = request.json or {}
    if not d.get('episodio_id'):
        return jsonify({'ok': False, 'error': 'episodio_id requerido'}), 400
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO medico_recetas
                   (episodio_id, medico, especialidad, fecha, notas, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                d['episodio_id'],
                d.get('medico', '').strip(),
                d.get('especialidad', '').strip(),
                d.get('fecha') or _today(),
                d.get('notas', '').strip(),
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@medico_bp.route('/api/recetas/<int:rid>', methods=['DELETE'])
def eliminar_receta(rid):
    with get_db() as db:
        db.execute("DELETE FROM medico_recetas WHERE id=?", (rid,))
        db.commit()
    return jsonify({'ok': True})


# ── Medicamentos CRUD ─────────────────────────────────────────────────────────

@medico_bp.route('/api/medicamentos', methods=['POST'])
def crear_medicamento():
    d = request.json or {}
    if not d.get('receta_id') or not d.get('nombre'):
        return jsonify({'ok': False, 'error': 'receta_id y nombre requeridos'}), 400
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO medico_medicamentos
                   (receta_id, nombre, dosis, frecuencia, duracion_dias, tomando, created_at)
               VALUES (?,?,?,?,?,1,?)""",
            (
                d['receta_id'],
                d['nombre'].strip(),
                d.get('dosis', '').strip(),
                d.get('frecuencia', '').strip(),
                d.get('duracion_dias') or None,
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@medico_bp.route('/api/medicamentos/<int:mid>', methods=['PATCH'])
def actualizar_medicamento(mid):
    d = request.json or {}
    if 'tomando' not in d:
        return jsonify({'ok': False, 'error': 'campo tomando requerido'}), 400
    with get_db() as db:
        db.execute(
            "UPDATE medico_medicamentos SET tomando=? WHERE id=?",
            (int(d['tomando']), mid),
        )
        db.commit()
    return jsonify({'ok': True})


@medico_bp.route('/api/medicamentos/<int:mid>', methods=['DELETE'])
def eliminar_medicamento(mid):
    with get_db() as db:
        db.execute("DELETE FROM medico_medicamentos WHERE id=?", (mid,))
        db.commit()
    return jsonify({'ok': True})
