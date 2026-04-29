from flask import Blueprint, render_template, request, jsonify, redirect
from database import get_db, get_gtd_stats
from datetime import date, datetime
import modules.gamification.engine as engine

gtd_bp = Blueprint('gtd', __name__, template_folder='../../templates')

_CUADRANTE = {
    (True,  True):  'hoy',
    (True,  False): 'semana',
    (False, True):  'delegar',
    (False, False): 'ideas',
}


def _calc_cuadrante(importante, urgente):
    if importante is None or urgente is None:
        return None
    return _CUADRANTE.get((bool(importante), bool(urgente)))


# ── Views ─────────────────────────────────────────────────────────────────────

@gtd_bp.route('/')
@gtd_bp.route('/dashboard')
def index():
    with get_db() as db:
        tasks = [dict(r) for r in db.execute(
            "SELECT * FROM gtd_tasks ORDER BY created_at DESC"
        ).fetchall()]
    return render_template('gtd/praxis.html', tasks=tasks, stats=get_gtd_stats())


@gtd_bp.route('/points')
def points():
    with get_db() as db:
        log = db.execute("""SELECT l.*, t.title FROM gtd_points_log l
            LEFT JOIN gtd_tasks t ON l.task_id=t.id
            ORDER BY l.id DESC LIMIT 60""").fetchall()
        daily = db.execute("""SELECT date, SUM(points_earned) as total
            FROM gtd_points_log GROUP BY date ORDER BY date DESC LIMIT 30""").fetchall()
    return render_template('gtd/points.html', log=log, daily=daily, stats=get_gtd_stats())


# Legacy routes redirect to new SPA
@gtd_bp.route('/inbox')
@gtd_bp.route('/next')
@gtd_bp.route('/someday')
@gtd_bp.route('/projects')
def _legacy():
    return redirect('/gtd/')


# ── API ───────────────────────────────────────────────────────────────────────

@gtd_bp.route('/api/tasks')
def api_tasks():
    with get_db() as db:
        tasks = [dict(r) for r in db.execute(
            "SELECT * FROM gtd_tasks ORDER BY created_at DESC"
        ).fetchall()]
    return jsonify(tasks)


@gtd_bp.route('/api/task', methods=['POST'])
def add_task():
    d = request.json or {}
    now = datetime.now().isoformat()
    texto = (d.get('texto') or d.get('title') or '').strip()
    if not texto:
        return jsonify({'ok': False, 'error': 'texto requerido'}), 400
    tipo = d.get('tipo', 'tarea')
    with get_db() as db:
        db.execute(
            """INSERT INTO gtd_tasks
               (title, tipo, completado, status, points, created_at, actualizado_en)
               VALUES (?,?,0,'inbox',4,?,?)""",
            (texto, tipo, now, now)
        )
        db.commit()
        task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({'ok': True, 'id': task_id})


@gtd_bp.route('/api/task/<int:tid>/classify', methods=['POST'])
def classify_task(tid):
    d = request.json or {}
    now = datetime.now().isoformat()
    # Accept null/None to move back to inbox
    imp = d.get('importante')
    urg = d.get('urgente')
    imp_val = None if imp is None else (1 if imp else 0)
    urg_val = None if urg is None else (1 if urg else 0)
    cuadrante = _calc_cuadrante(imp, urg)
    with get_db() as db:
        db.execute(
            "UPDATE gtd_tasks SET importante=?, urgente=?, cuadrante=?, actualizado_en=? WHERE id=?",
            (imp_val, urg_val, cuadrante, now, tid)
        )
        db.commit()
    return jsonify({'ok': True, 'cuadrante': cuadrante})


@gtd_bp.route('/api/task/<int:tid>/complete', methods=['POST'])
def complete_task(tid):
    today = date.today().isoformat()
    now = datetime.now().isoformat()
    with get_db() as db:
        task = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (tid,)).fetchone()
        if not task:
            return jsonify({'error': 'not found'}), 404
        if task['completado']:
            return jsonify({'error': 'already done'}), 400
        db.execute(
            """UPDATE gtd_tasks
               SET completado=1, fecha_completado=?, status='done', completed_at=?, actualizado_en=?
               WHERE id=?""",
            (today, today, now, tid)
        )
        priority = task['priority'] or 'normal'
        pts = task['points'] or 4
        db.execute(
            "INSERT INTO gtd_points_log (task_id,points_earned,reason,date) VALUES (?,?,?,?)",
            (tid, pts, 'task_complete', today)
        )
        done_count = db.execute(
            "SELECT COUNT(*) as c FROM gtd_tasks WHERE fecha_completado=?", (today,)
        ).fetchone()["c"]
        bonus = 0
        if done_count == 3:
            db.execute(
                "INSERT INTO gtd_points_log (task_id,points_earned,reason,date) VALUES (?,?,?,?)",
                (None, 15, 'daily_bonus_3tasks', today)
            )
            bonus = 15
        db.commit()

    gam = engine.process_gtd_task(tid, priority)
    if bonus:
        gam["daily_bonus_gam"] = engine.process_gtd_daily_bonus()

    return jsonify({'ok': True, 'pts': pts, 'bonus': bonus, 'stats': get_gtd_stats(), 'gam': gam})


@gtd_bp.route('/api/task/<int:tid>/update', methods=['POST'])
def update_task(tid):
    d = request.json or {}
    now = datetime.now().isoformat()
    with get_db() as db:
        task = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (tid,)).fetchone()
        if not task:
            return jsonify({'ok': False, 'error': 'not found'}), 404
        db.execute(
            """UPDATE gtd_tasks
               SET title=?, notas=?, fecha_limite=?, tipo=?, actualizado_en=?
               WHERE id=?""",
            (
                d.get('texto', task['title']),
                d.get('notas', task['notas']),
                d.get('fecha_limite', task['fecha_limite']),
                d.get('tipo', task['tipo'] or 'tarea'),
                now, tid
            )
        )
        db.commit()
    return jsonify({'ok': True})


@gtd_bp.route('/api/task/<int:tid>', methods=['DELETE'])
def delete_task(tid):
    with get_db() as db:
        db.execute("DELETE FROM gtd_tasks WHERE id=?", (tid,))
        db.commit()
    return jsonify({'ok': True})


# Legacy status endpoint (for backward compat)
@gtd_bp.route('/api/task/<int:tid>/status', methods=['POST'])
def task_status(tid):
    new = (request.json or {}).get('status', '')
    now = datetime.now().isoformat()
    if new == 'done':
        return complete_task(tid)
    cuadrante_map = {'someday': 'ideas', 'next': None, 'inbox': None}
    cuadrante = cuadrante_map.get(new)
    with get_db() as db:
        if new == 'someday':
            db.execute(
                "UPDATE gtd_tasks SET importante=0, urgente=0, cuadrante='ideas', status=?, actualizado_en=? WHERE id=?",
                (new, now, tid)
            )
        elif new in ('inbox', 'next'):
            db.execute(
                "UPDATE gtd_tasks SET status=?, actualizado_en=? WHERE id=?",
                (new, now, tid)
            )
        db.commit()
    return jsonify({'ok': True})


@gtd_bp.route('/api/word/refresh')
def word_refresh():
    from data import get_random_word
    return jsonify(get_random_word())
