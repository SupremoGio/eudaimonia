import os, uuid
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from database import get_db
from datetime import date, datetime, timedelta
from utils import uploads_base_dir, today_date

medico_bp = Blueprint('medico', __name__, template_folder='../../templates')

UPLOAD_DIR  = os.path.join(uploads_base_dir(), 'medico')
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.pdf'}
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _now():
    return datetime.now().isoformat()


def _today():
    return datetime.now().date().isoformat()


# ── Helpers compartidos con el hub de Hegemonikon (v2) ───────────────────────

RECURRENCIA_DIAS = 90


def recuperacion_por_tipo(db):
    """Días promedio de recuperación por tipo de episodio (solo resueltos)."""
    return [dict(r) for r in db.execute("""
        SELECT tipo,
               ROUND(AVG(julianday(fecha_fin) - julianday(fecha_inicio)), 1) AS avg_dias,
               COUNT(*) AS total
        FROM   medico_episodios
        WHERE  fecha_fin IS NOT NULL AND activo = 0
        GROUP  BY tipo
        ORDER  BY avg_dias DESC
    """).fetchall()]


def recurrencias(db):
    return [dict(r) for r in db.execute("""
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


def cada_dias(r):
    """Intervalo promedio entre episodios de una recurrencia."""
    if not r.get('dias_entre') or r['veces'] < 2:
        return None
    return r['dias_entre'] // (r['veces'] - 1)


def _alerta_key(titulo):
    return 'hg_alerta_oculta_hasta:' + (titulo or '').strip().lower()


def alerta_oculta(db, titulo, hoy=None):
    row = db.execute("SELECT value FROM app_settings WHERE key=?", (_alerta_key(titulo),)).fetchone()
    return bool(row and row['value'] >= (hoy or today_date()).isoformat())


def ocultar_alerta(db, titulo, dias=30, hoy=None):
    hasta = ((hoy or today_date()) + timedelta(days=dias)).isoformat()
    db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (_alerta_key(titulo), hasta))
    db.commit()
    return hasta


def recurrencia_alerta(db, hoy=None):
    """La primera recurrencia con intervalo promedio < 90 días que no esté
    oculta: {titulo, veces, cada_dias}. None si no hay."""
    for r in recurrencias(db):
        c = cada_dias(r)
        if c is not None and 0 < c < RECURRENCIA_DIAS and not alerta_oculta(db, r['titulo'], hoy):
            return {'titulo': r['titulo'], 'veces': r['veces'], 'cada_dias': c}
    return None


def _dias(desde, hoy):
    try:
        return (hoy - date.fromisoformat(str(desde)[:10])).days
    except (TypeError, ValueError):
        return None


def auto_terminar(db, hoy=None):
    """Fin automático: un medicamento con duracion_dias deja de tomarse al
    cumplir esos días desde la fecha de su receta. Los que no tienen duración
    («si hay dolor») nunca se apagan solos. Devuelve cuántos terminó."""
    hoy = hoy or today_date()
    n = 0
    for m in db.execute("""
        SELECT m.id, m.duracion_dias, r.fecha FROM medico_medicamentos m
        JOIN medico_recetas r ON r.id = m.receta_id
        WHERE m.tomando = 1 AND m.duracion_dias IS NOT NULL AND m.duracion_dias > 0
    """).fetchall():
        d = _dias(m['fecha'], hoy)
        if d is not None and d >= m['duracion_dias']:
            db.execute("UPDATE medico_medicamentos SET tomando=0, terminado_en=? WHERE id=?", (hoy.isoformat(), m['id']))
            n += 1
    if n:
        db.commit()
    return n


def medicamentos_de(db, episodio_id, hoy=None):
    """Medicamentos del episodio con dia_n contado desde la fecha de la receta."""
    hoy = hoy or today_date()
    out = []
    for m in db.execute("""
        SELECT m.*, r.fecha AS receta_fecha, r.medico, r.especialidad FROM medico_medicamentos m
        JOIN medico_recetas r ON r.id = m.receta_id
        WHERE r.episodio_id = ? ORDER BY m.tomando DESC, r.fecha DESC, m.id
    """, (episodio_id,)).fetchall():
        m = dict(m)
        dia = _dias(m['receta_fecha'], hoy) or 0
        dur = m.get('duracion_dias') or None
        out.append({
            'id': m['id'], 'nombre': m['nombre'], 'dosis': m.get('dosis') or '', 'frecuencia': m.get('frecuencia') or '',
            'medico': m.get('medico') or '', 'dia_n': dia, 'duracion_dias': dur, 'tomando': bool(m['tomando']),
            'pct': min(100, round(dia / dur * 100)) if dur else 0,
            'casi': bool(dur and m['tomando'] and dur - dia <= 2),
        })
    return out


def tratamiento(db, hoy=None):
    """El episodio activo más reciente con sus medicamentos, recetas,
    documentos y tu promedio de recuperación para su tipo. None si no hay."""
    hoy = hoy or today_date()
    e = db.execute("SELECT * FROM medico_episodios WHERE activo=1 ORDER BY fecha_inicio DESC, id DESC LIMIT 1").fetchone()
    if not e:
        return None
    e = dict(e)
    prom = next((r['avg_dias'] for r in recuperacion_por_tipo(db) if r['tipo'] == e['tipo']), None)
    recetas = db.execute("SELECT medico, especialidad FROM medico_recetas WHERE episodio_id=? ORDER BY fecha DESC", (e['id'],)).fetchall()
    docs = db.execute("SELECT COUNT(*) c FROM medico_documentos WHERE episodio_id=?", (e['id'],)).fetchone()['c']
    activos = db.execute("SELECT COUNT(*) c FROM medico_episodios WHERE activo=1").fetchone()['c']
    return {
        'id': e['id'], 'titulo': e['titulo'], 'tipo': e['tipo'], 'zona': e.get('zona_cuerpo') or '',
        'fecha_inicio': e['fecha_inicio'], 'dia_n': _dias(e['fecha_inicio'], hoy) or 0,
        'avg_recuperacion_tipo': prom, 'medicamentos': medicamentos_de(db, e['id'], hoy),
        'recetas': len(recetas), 'documentos': docs, 'episodios_activos': activos,
        'medico': (recetas[0]['medico'] + (' · ' + recetas[0]['especialidad'] if recetas[0]['especialidad'] else '')) if recetas and recetas[0]['medico'] else '',
    }


# ── Index ─────────────────────────────────────────────────────────────────────

@medico_bp.route('/')
def index():
    with get_db() as db:
        auto_terminar(db)
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
        recovery = recuperacion_por_tipo(db)

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

        recurrencia = recurrencias(db)
        for r in recurrencia:
            r['cada_dias'] = cada_dias(r)
        alerta = recurrencia_alerta(db)
        resueltos_6m = [e for e in episodios if e['fecha_inicio'] >= (today_date() - timedelta(days=183)).isoformat()]

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
            alerta=alerta,
            n_6m=len(resueltos_6m),
            recup_media=(round(sum(r['avg_dias'] * r['total'] for r in recovery) / sum(r['total'] for r in recovery), 1)
                         if recovery and sum(r['total'] for r in recovery) else None),
        ),
        ep_abrir=request.args.get('ep', type=int),
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
        out = {'ok': True}
        # Al resolver: cuántos días duró y contra tu promedio del tipo
        # (el promedio sin contar este episodio).
        if 'activo' in d and not d['activo']:
            e = db.execute("SELECT tipo, fecha_inicio, fecha_fin FROM medico_episodios WHERE id=?", (eid,)).fetchone()
            if e:
                try:
                    dias = (date.fromisoformat(e['fecha_fin'][:10]) - date.fromisoformat(e['fecha_inicio'][:10])).days
                except (TypeError, ValueError):
                    dias = None
                prom = db.execute("""SELECT AVG(julianday(fecha_fin) - julianday(fecha_inicio)) AS a FROM medico_episodios
                                     WHERE tipo=? AND activo=0 AND fecha_fin IS NOT NULL AND id != ?""", (e['tipo'], eid)).fetchone()['a']
                out.update(dias=dias, vs_promedio=(round(dias - prom, 1) if dias is not None and prom is not None else None))
    return jsonify(out)


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


@medico_bp.route('/api/episodios/<int:eid>/documentos')
def episodio_documentos(eid):
    with get_db() as db:
        docs = db.execute(
            "SELECT * FROM medico_documentos WHERE episodio_id=? ORDER BY fecha DESC, id DESC",
            (eid,),
        ).fetchall()
    return jsonify([dict(d) for d in docs])


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
            "UPDATE medico_medicamentos SET tomando=?, terminado_en=? WHERE id=?",
            (int(d['tomando']), None if int(d['tomando']) else today_date().isoformat(), mid),
        )
        db.commit()
    return jsonify({'ok': True})


@medico_bp.route('/api/medicamentos/<int:mid>', methods=['DELETE'])
def eliminar_medicamento(mid):
    with get_db() as db:
        db.execute("DELETE FROM medico_medicamentos WHERE id=?", (mid,))
        db.commit()
    return jsonify({'ok': True})


# ── Documentos (recetas/estudios escaneados) ──────────────────────────────────

@medico_bp.route('/api/episodios/<int:eid>/documentos', methods=['POST'])
def subir_documento(eid):
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if not ext or ext not in ALLOWED_EXT:
        _mime_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
                     'image/heic': '.heic', 'application/pdf': '.pdf'}
        ext = _mime_map.get((f.content_type or '').split(';')[0].strip(), '')
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido (solo imágenes o PDF)'}), 400
    filename = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, filename))
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO medico_documentos
                   (episodio_id, tipo, nombre_archivo, nombre_original, fecha, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                eid,
                request.form.get('tipo', 'receta'),
                filename,
                secure_filename(f.filename),
                request.form.get('fecha') or _today(),
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'filename': filename})


@medico_bp.route('/api/documentos/<int:did>', methods=['DELETE'])
def eliminar_documento(did):
    with get_db() as db:
        doc = db.execute("SELECT * FROM medico_documentos WHERE id=?", (did,)).fetchone()
        if doc:
            try:
                os.remove(os.path.join(UPLOAD_DIR, doc['nombre_archivo']))
            except OSError:
                pass
        db.execute("DELETE FROM medico_documentos WHERE id=?", (did,))
        db.commit()
    return jsonify({'ok': True})


@medico_bp.route('/documentos/<filename>')
def serve_documento(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)
