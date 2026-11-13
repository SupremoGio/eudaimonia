import os, uuid, base64, hashlib, mimetypes
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort, Response, session, current_app
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet, InvalidToken
from database import get_db
from utils import uploads_base_dir, today_str
import modules.gamification.engine as engine
from modules.perfil import recordatorios as rec
from modules.perfil import resumen as rs

PLACEHOLDER = '— editar —'

perfil_bp = Blueprint('perfil', __name__, template_folder='../../templates')

UPLOAD_DIR = os.path.join(uploads_base_dir(), 'docs')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Recordatorios — mismo tier "progreso" que registrar_gastos/riego de
# plantas (acción administrativa rápida). Se otorga cada vez que se marca
# cumplido, incluidos los recurrentes (pagar una tarjeta cada mes sí
# cuenta cada vez, no es un logro de una sola vez como un álbum/película).
_RECORDATORIO_XP = 3
_RECORDATORIO_EC = 1


def _vault_fernet():
    """Deriva una clave Fernet estable a partir de SECRET_KEY.
    Si SECRET_KEY cambia, las entradas cifradas existentes dejan de poder
    descifrarse — por eso conviene fijar SECRET_KEY en .env desde el inicio."""
    key = hashlib.sha256(current_app.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _vault_encrypt(plaintext):
    return _vault_fernet().encrypt(plaintext.encode()).decode()


def _vault_decrypt(token):
    return _vault_fernet().decrypt(token.encode()).decode()

ALLOWED_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.xml', '.zip'}


@perfil_bp.route('/')
def index():
    # Las preferencias de avisos viven en Ajustes (handoff Plantas y Ajustes).
    if request.args.get('sec') == 'avisos':
        from flask import redirect
        return redirect('/perfil/?sec=ajustes#avisos')
    with get_db() as db:
        info         = db.execute("SELECT * FROM personal_info ORDER BY rowid").fetchall()
        measurements = db.execute("SELECT * FROM body_measurements ORDER BY rowid").fetchall()
        all_docs     = db.execute("SELECT * FROM profile_docs ORDER BY uploaded_at DESC").fetchall()
        reminders    = db.execute(
            "SELECT * FROM reminders WHERE is_active=1 ORDER BY COALESCE(next_date, target_date, '9999-12-31'), created_at"
        ).fetchall()
        hist_rows = db.execute(
            "SELECT key, value, recorded_at FROM body_measurements_history ORDER BY recorded_at DESC"
        ).fetchall()
        vault_rows = db.execute(
            "SELECT id, servicio, usuario, url, notas FROM password_vault ORDER BY servicio COLLATE NOCASE"
        ).fetchall()
        pliegue_rows = db.execute(
            "SELECT * FROM pliegue_grasa_log ORDER BY fecha DESC, id DESC"
        ).fetchall()
        tallas_rows = db.execute(
            "SELECT * FROM tallas_marca ORDER BY prenda, marca COLLATE NOCASE"
        ).fetchall()

    # Passwords nunca se descifran aquí — solo id/servicio/usuario/url/notas.
    # El password real se pide bajo demanda vía /api/vault/reveal/<id>.
    vault = [dict(v) for v in vault_rows]

    # Group docs: general (field_key IS NULL) and per-field
    docs_general = []
    docs_by_field = {}
    for d in all_docs:
        fk = d["field_key"] if "field_key" in d.keys() else None
        if fk:
            docs_by_field.setdefault(fk, []).append(d)
        else:
            docs_general.append(d)

    reminders = [dict(r) for r in reminders]
    hoy = date.fromisoformat(today_str())

    # Pagos de tarjeta que ya lleva Oikonomia: se enlazan (solo con fin_ok)
    fin_ok = bool(session.get('fin_ok'))
    if fin_ok:
        try:
            with get_db() as db:
                if rs.vincular_pagos(db):
                    reminders = [dict(r) for r in db.execute(
                        "SELECT * FROM reminders WHERE is_active=1 ORDER BY COALESCE(next_date, target_date, '9999-12-31'), created_at"
                    ).fetchall()]
        except Exception:
            pass

    med_rows = rs.medidas(measurements, hist_rows, hoy)
    rem_grupos = rs.grupos_recordatorios(reminders, hoy)

    # ── Plicómetro (pliegues cutáneos): calcular deltas contra la lectura previa
    pliegue_log = [dict(p) for p in pliegue_rows]
    for i, p in enumerate(pliegue_log):
        prev = pliegue_log[i + 1] if i + 1 < len(pliegue_log) else None
        p['delta_pct'] = round(p['porcentaje'] - prev['porcentaje'], 1) if prev else None
        p['delta_mm']  = round(p['mm'] - prev['mm'], 1) if prev else None

    # ── Tallas por marca: agrupar por prenda (camisa / playera / pantalón) ──
    tallas_por_prenda = {}
    for t in tallas_rows:
        tallas_por_prenda.setdefault(t['prenda'], []).append(dict(t))

    nombre = next((i['value'] for i in info if i['key'] == 'nombre' and i['value'] != PLACEHOLDER), '')
    me = {'nombre': nombre, 'inicial': (nombre.strip()[:1] or 'Tú').upper() if nombre else 'Tú'}
    sec = request.args.get('sec', 'resumen')
    from modules import avisos as _av
    with get_db() as db:
        avisos_prefs = _av.preferencias(db, session)
        from modules import onboarding as _onb
        onb = _onb.estado(db, inicio=False)
        ajustes = _ajustes_view(db)

    return render_template('perfil/index.html',
                           onb=onb, ajustes=ajustes,
                           avisos_prefs=avisos_prefs,
                           me=me, sec=sec, fin_ok=fin_ok,
                           placeholder=PLACEHOLDER,
                           info=info,
                           grupos_datos=rs.grupos_datos(info, docs_by_field),
                           measurements=measurements,
                           med_rows=med_rows,
                           docs=docs_general,
                           docs_by_field=docs_by_field,
                           reminders=reminders,
                           rem_grupos=rem_grupos,
                           rem_temas=rec.conteo_temas(rem_grupos),
                           rem_tema_opts=rec.TEMAS,
                           vault=vault,
                           pliegue_log=pliegue_log,
                           tallas_por_prenda=tallas_por_prenda,
                           nav_counts=rs.nav_counts(info, med_rows, rem_grupos, len(all_docs), len(vault)),
                           atencion=rs.atencion(rem_grupos, info, med_rows, fin_ok),
                           tiles=rs.tiles(rem_grupos, info, med_rows))


@perfil_bp.route('/api/privados')
def privados():
    """Los valores privados en un solo fetch (Mostrar privados / copiar uno
    oculto). Nunca viajan en el HTML de la página."""
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        rows = db.execute("SELECT key, value FROM personal_info WHERE private=1").fetchall()
    return jsonify({'ok': True, 'valores': {r['key']: r['value'] for r in rows if rs.lleno(r['value'])}})


@perfil_bp.route('/api/medidas/lote', methods=['POST'])
def medidas_lote():
    """«Guardar lectura de hoy»: una lectura solo para las medidas que
    cambiaron (no infla el historial con valores repetidos)."""
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    valores = d.get('valores') or {}
    if not isinstance(valores, dict):
        return jsonify({'ok': False, 'error': 'valores inválidos'}), 400
    now = datetime.now().isoformat()
    guardadas = []
    with get_db() as db:
        actuales = {r['key']: r['value'] for r in db.execute("SELECT key, value FROM body_measurements").fetchall()}
        for k, v in valores.items():
            v = str(v if v is not None else '').strip().replace(',', '.')
            if k not in actuales or not v:
                continue
            a, b = rs._num(v), rs._num(actuales[k])
            if v == actuales[k] or (a is not None and b is not None and a == b):
                continue
            db.execute("UPDATE body_measurements SET value=? WHERE key=?", (v, k))
            db.execute("INSERT INTO body_measurements_history (key, value, recorded_at) VALUES (?,?,?)", (k, v, now))
            guardadas.append(k)
        db.commit()
    return jsonify({'ok': True, 'guardadas': guardadas})


@perfil_bp.route('/api/recordatorios/<int:rid>/posponer', methods=['POST'])
def posponer_recordatorio(rid):
    """«Mañana» del Resumen: mueve esta ocurrencia a mañana sin tocar la
    recurrencia (misma regla que /snooze)."""
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    manana = (date.fromisoformat(today_str()) + timedelta(days=1)).isoformat()
    with get_db() as db:
        row = db.execute("SELECT type FROM reminders WHERE id=?", (rid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if row['type'] == 'unico':
            db.execute("UPDATE reminders SET target_date=?, next_date=? WHERE id=?", (manana, manana, rid))
        else:
            db.execute("UPDATE reminders SET next_date=? WHERE id=?", (manana, rid))
        db.commit()
    return jsonify({'ok': True, 'fecha': manana})


@perfil_bp.route('/api/update', methods=['POST'])
def update():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    key = d.get('key', '').strip()
    value = d.get('value')
    if not key or value is None:
        return jsonify({'ok': False, 'error': 'key and value required'}), 400
    with get_db() as db:
        db.execute("UPDATE personal_info SET value=? WHERE key=?", (str(value), key))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/update_measurement', methods=['POST'])
def update_measurement():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    key = d.get('key', '').strip()
    value = d.get('value')
    if not key or value is None:
        return jsonify({'ok': False, 'error': 'key and value required'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute("UPDATE body_measurements SET value=? WHERE key=?", (str(value), key))
        db.execute(
            "INSERT INTO body_measurements_history (key, value, recorded_at) VALUES (?,?,?)",
            (key, str(value), now)
        )
        db.commit()
        hist = db.execute(
            "SELECT value, recorded_at FROM body_measurements_history WHERE key=? ORDER BY recorded_at DESC LIMIT 8",
            (key,)
        ).fetchall()
    history = [{"value": r["value"], "date": r["recorded_at"][:10]} for r in hist]
    return jsonify({'ok': True, 'history': history})


@perfil_bp.route('/api/pliegue/add', methods=['POST'])
def pliegue_add():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    try:
        mm = float(d.get('mm'))
        porcentaje = float(d.get('porcentaje'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'mm y porcentaje son requeridos y deben ser numéricos'}), 400
    fecha = (d.get('fecha') or '').strip() or date.today().isoformat()
    categoria = (d.get('categoria') or '').strip()
    notas = (d.get('notas') or '').strip()
    with get_db() as db:
        db.execute(
            "INSERT INTO pliegue_grasa_log (fecha, mm, porcentaje, categoria, notas, created_at) VALUES (?,?,?,?,?,?)",
            (fecha, mm, porcentaje, categoria, notas, datetime.now().isoformat())
        )
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/pliegue/<int:pid>/delete', methods=['POST'])
def pliegue_delete(pid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        db.execute("DELETE FROM pliegue_grasa_log WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True})


PRENDAS_VALIDAS = ('camisa', 'playera', 'pantalon')


@perfil_bp.route('/api/talla/add', methods=['POST'])
def talla_add():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    prenda = (d.get('prenda') or '').strip().lower()
    marca = (d.get('marca') or '').strip()
    talla = (d.get('talla') or '').strip()
    notas = (d.get('notas') or '').strip()
    if prenda not in PRENDAS_VALIDAS or not marca or not talla:
        return jsonify({'ok': False, 'error': 'prenda, marca y talla son requeridos'}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO tallas_marca (prenda, marca, talla, notas, created_at) VALUES (?,?,?,?,?)",
            (prenda, marca, talla, notas, datetime.now().isoformat())
        )
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/talla/<int:tid>/delete', methods=['POST'])
def talla_delete(tid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        db.execute("DELETE FROM tallas_marca WHERE id=?", (tid,))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/upload_doc', methods=['POST'])
def upload_doc():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    f         = request.files.get('file')
    field_key = request.form.get('field_key', '').strip() or None
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    safe_original = secure_filename(f.filename) or 'archivo'
    ext = os.path.splitext(safe_original)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido'}), 400
    safe_name    = uuid.uuid4().hex + ext
    file_content = f.read()
    # Also save to filesystem as fallback for local dev
    try:
        with open(os.path.join(UPLOAD_DIR, safe_name), 'wb') as fp:
            fp.write(file_content)
    except OSError:
        pass
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO profile_docs (filename, original, uploaded_at, field_key, content) VALUES (?,?,?,?,?)",
            (safe_name, safe_original, now, field_key, file_content)
        )
        doc_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        db.commit()
    return jsonify({'ok': True, 'id': doc_id, 'filename': safe_name,
                    'original': safe_original, 'uploaded_at': now, 'field_key': field_key})


@perfil_bp.route('/api/delete_doc', methods=['POST'])
def delete_doc():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.json
    with get_db() as db:
        row = db.execute("SELECT filename FROM profile_docs WHERE id=?", (d['id'],)).fetchone()
        if not row:
            return jsonify({'ok': False}), 404
        db.execute("DELETE FROM profile_docs WHERE id=?", (d['id'],))
        db.commit()
    try:
        os.remove(os.path.join(UPLOAD_DIR, row['filename']))
    except OSError:
        pass
    return jsonify({'ok': True})


@perfil_bp.route('/docs/<filename>')
def serve_doc(filename):
    if not session.get('fin_ok'): abort(403)
    if '..' in filename or '/' in filename:
        abort(400)
    with get_db() as db:
        row = db.execute(
            "SELECT content, original FROM profile_docs WHERE filename=?", (filename,)
        ).fetchone()
    if not row:
        abort(404)
    content = row['content'] if row else None
    if content is not None:
        # Turso puede restaurar BLOBs como string base64 (datos previos al fix de _to_arg)
        if isinstance(content, str):
            try:
                import base64
                content = base64.b64decode(content)
            except Exception:
                content = None
        if content:
            mime = mimetypes.guess_type(row['original'])[0] or 'application/octet-stream'
            return Response(
                bytes(content),
                mimetype=mime,
                headers={'Content-Disposition': f'inline; filename="{row["original"]}"'}
            )
    # Fallback: filesystem local (dev). En Railway el archivo puede no existir.
    fs_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(fs_path):
        return send_from_directory(UPLOAD_DIR, filename)
    abort(404)


# ── Reminders ─────────────────────────────────────────────────────────────────

@perfil_bp.route('/api/reminders')
def get_reminders():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM reminders WHERE is_active=1 ORDER BY COALESCE(next_date, target_date, '9999-12-31'), created_at"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


def _cuenta_desde(d):
    """'hecho' = la siguiente fecha cuenta desde que se marca; si no, 'ciclo'."""
    return 'hecho' if d.get('type') == 'periodico' and d.get('cuenta_desde') == 'hecho' else 'ciclo'


@perfil_bp.route('/api/reminder/add', methods=['POST'])
def add_reminder():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    desc = (d.get('description') or '').strip()
    if not desc:
        return jsonify({'ok': False, 'error': 'Descripción requerida'}), 400
    typ = d.get('type', 'unico')
    target = d.get('target_date') or None
    next_d = d.get('next_date') or target
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO reminders (description, type, freq_unit, freq_value, target_date, next_date, is_active, created_at, tema, cuenta_desde)
               VALUES (?,?,?,?,?,?,1,?,?,?)""",
            (desc, typ,
             d.get('freq_unit', ''),
             int(d.get('freq_value') or 1),
             target, next_d, now, rec.tema_valido(d.get('tema'), desc), _cuenta_desde(d))
        )
        rid = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        db.commit()
    return jsonify({'ok': True, 'id': rid})


@perfil_bp.route('/api/reminder/<int:rid>/done', methods=['POST'])
def complete_reminder(rid):
    from utils import today_str as _today_str
    today = _today_str()
    with get_db() as db:
        row = db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if row['type'] == 'unico':
            db.execute("UPDATE reminders SET is_active=0, last_done=? WHERE id=?", (today, rid))
        else:
            # Ancla en el ciclo del usuario (target_date), no en el día en que se
            # marca hecho: pagar tarde o posponer no «mueve» el recordatorio.
            next_d = rec.siguiente(dict(row), today)
            db.execute(
                "UPDATE reminders SET last_done=?, next_date=? WHERE id=?",
                (today, next_d, rid)
            )
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (f"recordatorio_{rid}", today, _RECORDATORIO_XP)
        )
        log_id = cur.lastrowid
        db.commit()

    gam = engine.process_activity(f"recordatorio_{rid}", _RECORDATORIO_XP, 'Recordatorios', log_id, ec=_RECORDATORIO_EC)
    return jsonify({'ok': True, 'gam': gam})


@perfil_bp.route('/api/reminder/<int:rid>/snooze', methods=['POST'])
def snooze_reminder(rid):
    """Posponer: mueve solo esta ocurrencia (`dias` desde hoy, o `fecha`).
    En los periódicos no toca target_date, que es el ancla del ciclo."""
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    try:
        if d.get('fecha'):
            nueva = date.fromisoformat(str(d['fecha'])[:10])
        else:
            nueva = date.fromisoformat(today_str()) + timedelta(days=max(1, min(int(d.get('dias') or 1), 365)))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Fecha inválida'}), 400
    with get_db() as db:
        row = db.execute("SELECT type FROM reminders WHERE id=?", (rid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if row['type'] == 'unico':
            db.execute("UPDATE reminders SET target_date=?, next_date=? WHERE id=?", (nueva.isoformat(),) * 2 + (rid,))
        else:
            db.execute("UPDATE reminders SET next_date=? WHERE id=?", (nueva.isoformat(), rid))
        db.commit()
    return jsonify({'ok': True, 'fecha': nueva.isoformat()})


@perfil_bp.route('/api/reminder/<int:rid>/delete', methods=['POST'])
def delete_reminder(rid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        db.execute("DELETE FROM reminders WHERE id=?", (rid,))
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/reminder/<int:rid>/edit', methods=['POST'])
def edit_reminder(rid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    desc = (d.get('description') or '').strip()
    if not desc:
        return jsonify({'ok': False, 'error': 'Descripción requerida'}), 400
    typ = d.get('type', 'unico')
    target = d.get('target_date') or None
    next_d = d.get('next_date') or target
    with get_db() as db:
        db.execute(
            """UPDATE reminders SET description=?, type=?, freq_unit=?, freq_value=?,
               target_date=?, next_date=?, tema=?, cuenta_desde=? WHERE id=?""",
            (desc, typ,
             d.get('freq_unit', ''),
             int(d.get('freq_value') or 1),
             target, next_d, rec.tema_valido(d.get('tema'), desc), _cuenta_desde(d), rid)
        )
        db.commit()
    return jsonify({'ok': True})


# ── Password Vault ──────────────────────────────────────────────────────────
# Los passwords se cifran (Fernet, clave derivada de SECRET_KEY) antes de
# guardarse y solo se descifran bajo demanda vía /reveal — nunca viajan en
# el HTML inicial ni en el listado.

@perfil_bp.route('/api/vault/add', methods=['POST'])
def vault_add():
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    servicio = (d.get('servicio') or '').strip()
    password = d.get('password') or ''
    if not servicio or not password:
        return jsonify({'ok': False, 'error': 'Servicio y contraseña requeridos'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO password_vault (servicio, usuario, password_enc, url, notas, created_at)
               VALUES (?,?,?,?,?,?)""",
            (servicio, (d.get('usuario') or '').strip(), _vault_encrypt(password),
             (d.get('url') or '').strip(), (d.get('notas') or '').strip(), now)
        )
        vid = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        db.commit()
    return jsonify({'ok': True, 'id': vid, 'servicio': servicio,
                    'usuario': d.get('usuario') or '', 'url': d.get('url') or '',
                    'notas': d.get('notas') or ''})


@perfil_bp.route('/api/vault/<int:vid>/edit', methods=['POST'])
def vault_edit(vid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    d = request.get_json(force=True, silent=True) or {}
    servicio = (d.get('servicio') or '').strip()
    if not servicio:
        return jsonify({'ok': False, 'error': 'Servicio requerido'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        row = db.execute("SELECT id FROM password_vault WHERE id=?", (vid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        new_password = d.get('password')
        if new_password:
            db.execute(
                """UPDATE password_vault SET servicio=?, usuario=?, password_enc=?, url=?,
                   notas=?, updated_at=? WHERE id=?""",
                (servicio, (d.get('usuario') or '').strip(), _vault_encrypt(new_password),
                 (d.get('url') or '').strip(), (d.get('notas') or '').strip(), now, vid)
            )
        else:
            db.execute(
                """UPDATE password_vault SET servicio=?, usuario=?, url=?, notas=?, updated_at=?
                   WHERE id=?""",
                (servicio, (d.get('usuario') or '').strip(),
                 (d.get('url') or '').strip(), (d.get('notas') or '').strip(), now, vid)
            )
        db.commit()
    return jsonify({'ok': True})


@perfil_bp.route('/api/vault/<int:vid>/reveal', methods=['POST'])
def vault_reveal(vid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        row = db.execute("SELECT password_enc FROM password_vault WHERE id=?", (vid,)).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    try:
        password = _vault_decrypt(row['password_enc'])
    except InvalidToken:
        return jsonify({'ok': False, 'error': 'No se pudo descifrar (¿cambió SECRET_KEY?)'}), 500
    return jsonify({'ok': True, 'password': password})


@perfil_bp.route('/api/vault/<int:vid>/delete', methods=['POST'])
def vault_delete(vid):
    if not session.get('fin_ok'): return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        db.execute("DELETE FROM password_vault WHERE id=?", (vid,))
        db.commit()
    return jsonify({'ok': True})



# ── Ajustes (handoff Plantas y Ajustes, nota 4) ──────────────────────────────
# Un solo lugar para lo configurable. POST /perfil/api/ajustes {clave, valor}
# solo acepta claves de la lista blanca; el valor se guarda como '1'/'0'.

def _ajustes_view(db):
    from modules import nav
    from modules.quick import preferencias
    ocultos, por_uso = preferencias(db)
    oculto = db.execute("SELECT value FROM app_settings WHERE key='onb_oculto'").fetchone()
    return {'quick': [{'id': q['id'], 'label': q['label'], 'on': q['id'] not in ocultos} for q in nav.QUICK],
            'por_uso': por_uso, 'onb_visible': not (oculto and oculto['value'] == '1')}


def clave_permitida(clave):
    """Lista blanca de Ajustes: avisos_off:<fuente>, quick_off:<id>,
    quick_orden_uso y onb_oculto."""
    from modules import nav
    from modules.avisos import FUENTES
    if clave in ('quick_orden_uso', 'onb_oculto'):
        return True
    if clave.startswith('avisos_off:'):
        return clave[len('avisos_off:'):] in {f[0] for f in FUENTES}
    if clave.startswith('quick_off:'):
        return clave[len('quick_off:'):] in {q['id'] for q in nav.QUICK}
    return False


@perfil_bp.route('/api/ajustes', methods=['POST'])
def api_ajustes():
    d = request.get_json(silent=True) or {}
    clave = str(d.get('clave') or '')
    if not clave_permitida(clave):
        return jsonify({'ok': False, 'error': 'Ajuste desconocido'}), 400
    valor = '1' if d.get('valor') in (True, 1, '1', 'true') else '0'
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (clave, valor))
        db.commit()
        conteo = None
        if clave.startswith('avisos_off:'):
            from modules import avisos as av
            conteo = av.recolectar(db)['conteo_hoy']
    return jsonify({'ok': True, 'clave': clave, 'valor': valor, 'conteo_hoy': conteo})


# Tablas que van en «Exportar todo». Sin la bóveda de contraseñas, sin
# app_settings (tokens y hashes de acceso) y sin archivos/fotos.
EXPORT_TABLAS = [
    'est_movimientos', 'est_budgets', 'est_prestamos', 'activity_logs', 'xp_ledger', 'coins_ledger',
    'gtd_tasks', 'reminders', 'personal_info', 'body_measurements', 'body_measurements_history',
    'plantas', 'plantas_bitacora', 'plantas_cuidados', 'medico_episodios', 'medico_recetas', 'medico_medicamentos',
    'harma_vehiculo', 'harma_servicios', 'harma_plan_items', 'harma_polizas', 'wardrobe_items', 'outfits',
    'rewards', 'lang_journal', 'lang_test_results', 'eury_sessions', 'revision_semanal', 'nutricion_deslices',
    'futbol_partidos', 'achievements', 'badges',
]


@perfil_bp.route('/api/exportar')
def api_exportar():
    """Zip con un CSV por tabla principal (solo lectura). Incluye finanzas,
    así que pide la misma llave que Oikonomia (fin_ok)."""
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    import csv, io, zipfile
    buf = io.BytesIO()
    with get_db() as db, zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        existentes = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in EXPORT_TABLAS:
            if t not in existentes:
                continue
            cur = db.execute(f'SELECT * FROM "{t}"')
            cols = [c[0] for c in cur.description]
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(cols)
            for row in cur.fetchall():
                w.writerow([row[c] for c in cols])
            zf.writestr(f'{t}.csv', '\ufeff' + out.getvalue())
    nombre = f"eudaimonia_{today_str()}.zip"
    return Response(buf.getvalue(), mimetype='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="{nombre}"'})
