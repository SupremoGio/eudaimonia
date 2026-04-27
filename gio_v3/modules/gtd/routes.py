from flask import Blueprint, render_template, request, jsonify
from database import get_db, get_gtd_stats
from data import get_word_of_day, get_quote_of_day, get_random_word
from datetime import date, datetime, timedelta
import modules.gamification.engine as engine

gtd_bp = Blueprint('gtd', __name__, template_folder='../../templates')


@gtd_bp.route('/')
@gtd_bp.route('/dashboard')
def dashboard():
    stats    = get_gtd_stats()
    today    = date.today().isoformat()
    hour     = datetime.now().hour
    greeting = "Buenos días" if hour < 13 else ("Buenas tardes" if hour < 20 else "Buenas noches")
    with get_db() as db:
        next_tasks  = db.execute("""
            SELECT t.*, p.name as project_name FROM gtd_tasks t
            LEFT JOIN gtd_projects p ON t.project_id=p.id
            WHERE t.status='next'
            ORDER BY CASE t.priority WHEN 'critical' THEN 0 WHEN 'important' THEN 1 ELSE 2 END,
                     t.due_date ASC LIMIT 10""").fetchall()
        done_ids    = {r["id"] for r in db.execute("SELECT id FROM gtd_tasks WHERE completed_at=?", (today,)).fetchall()}
        inbox_tasks = db.execute("SELECT * FROM gtd_tasks WHERE status='inbox' ORDER BY id DESC LIMIT 6").fetchall()
    return render_template('gtd/dashboard.html',
        stats=stats, next_tasks=next_tasks, done_ids=done_ids,
        inbox_tasks=inbox_tasks, word=get_word_of_day(),
        quote=get_quote_of_day(), greeting=greeting, today=today,
    )


@gtd_bp.route('/inbox')
def inbox():
    with get_db() as db:
        tasks    = db.execute("SELECT * FROM gtd_tasks WHERE status='inbox' ORDER BY id DESC").fetchall()
        projects = db.execute("SELECT * FROM gtd_projects WHERE status='active' ORDER BY name").fetchall()
    return render_template('gtd/inbox.html', tasks=tasks, projects=projects, stats=get_gtd_stats())


@gtd_bp.route('/next')
def next_actions():
    with get_db() as db:
        tasks    = db.execute("""
            SELECT t.*, p.name as project_name FROM gtd_tasks t
            LEFT JOIN gtd_projects p ON t.project_id=p.id
            WHERE t.status='next'
            ORDER BY CASE t.priority WHEN 'critical' THEN 0 WHEN 'important' THEN 1 ELSE 2 END,
                     t.due_date ASC""").fetchall()
        projects = db.execute("SELECT * FROM gtd_projects WHERE status='active'").fetchall()
    return render_template('gtd/next.html', tasks=tasks, projects=projects, stats=get_gtd_stats())


@gtd_bp.route('/projects')
def projects():
    with get_db() as db:
        projs = db.execute("SELECT * FROM gtd_projects WHERE status='active' ORDER BY id DESC").fetchall()
        proj_tasks = {p["id"]: db.execute(
            "SELECT * FROM gtd_tasks WHERE project_id=? AND status!='done' ORDER BY id", (p["id"],)
        ).fetchall() for p in projs}
    return render_template('gtd/projects.html', projects=projs, proj_tasks=proj_tasks, stats=get_gtd_stats())


@gtd_bp.route('/someday')
def someday():
    with get_db() as db:
        tasks = db.execute("SELECT * FROM gtd_tasks WHERE status='someday' ORDER BY id DESC").fetchall()
    return render_template('gtd/someday.html', tasks=tasks, stats=get_gtd_stats())


@gtd_bp.route('/points')
def points():
    with get_db() as db:
        log   = db.execute("""SELECT l.*, t.title FROM gtd_points_log l
            LEFT JOIN gtd_tasks t ON l.task_id=t.id ORDER BY l.id DESC LIMIT 60""").fetchall()
        daily = db.execute("""SELECT date, SUM(points_earned) as total FROM gtd_points_log
            GROUP BY date ORDER BY date DESC LIMIT 30""").fetchall()
    return render_template('gtd/points.html', log=log, daily=daily, stats=get_gtd_stats())


# ── API ───────────────────────────────────────────────────────────────────────

@gtd_bp.route('/api/task', methods=['POST'])
def add_task():
    d   = request.json
    pts = 8 if d.get('priority')=='critical' else (6 if d.get('priority')=='important' else 4)
    with get_db() as db:
        db.execute("""INSERT INTO gtd_tasks
            (title,description,status,priority,due_date,category,points,project_id,
             context,estimated_mins,energy_level,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d['title'], d.get('description',''), d.get('status','inbox'),
             d.get('priority','normal'), d.get('due_date',''), d.get('category',''),
             pts, d.get('project_id') or None,
             d.get('context',''), int(d.get('estimated_mins') or 0),
             d.get('energy_level','medium'), datetime.now().isoformat()))
        db.commit()
        task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({'ok':True, 'id': task_id})


@gtd_bp.route('/api/task/<int:tid>/complete', methods=['POST'])
def complete_task(tid):
    today = date.today().isoformat()
    with get_db() as db:
        task = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (tid,)).fetchone()
        if not task: return jsonify({'error':'not found'}), 404
        if task['completed_at']: return jsonify({'error':'already done'}), 400
        db.execute("UPDATE gtd_tasks SET status='done', completed_at=? WHERE id=?", (today, tid))
        db.execute("INSERT INTO gtd_points_log (task_id,points_earned,reason,date) VALUES (?,?,?,?)",
                   (tid, task['points'], 'task_complete', today))
        done_count = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE completed_at=?", (today,)).fetchone()["c"]
        bonus = 0
        if done_count == 3:
            db.execute("INSERT INTO gtd_points_log (task_id,points_earned,reason,date) VALUES (?,?,?,?)",
                       (None, 15, 'daily_bonus_3tasks', today))
            bonus = 15
        db.commit()

    gam = engine.process_gtd_task(tid, task['priority'])
    if bonus:
        daily_gam = engine.process_gtd_daily_bonus()
        gam["daily_bonus_gam"] = daily_gam

    return jsonify({'ok':True,'pts':task['points'],'bonus':bonus,'stats':get_gtd_stats(),'gam':gam})


@gtd_bp.route('/api/task/<int:tid>/status', methods=['POST'])
def task_status(tid):
    new = request.json.get('status')
    if new not in ('inbox','next','someday','done'): return jsonify({'error':'invalid'}), 400
    with get_db() as db:
        db.execute("UPDATE gtd_tasks SET status=? WHERE id=?", (new, tid))
        db.commit()
    return jsonify({'ok':True})


@gtd_bp.route('/api/task/<int:tid>', methods=['DELETE'])
def delete_task(tid):
    with get_db() as db:
        db.execute("DELETE FROM gtd_tasks WHERE id=?", (tid,))
        db.commit()
    return jsonify({'ok':True})


@gtd_bp.route('/api/project', methods=['POST'])
def add_project():
    d = request.json
    with get_db() as db:
        db.execute("INSERT INTO gtd_projects (name,objective,color,created_at) VALUES (?,?,?,?)",
                   (d['name'],d.get('objective',''),d.get('color','#c5a36c'),datetime.now().isoformat()))
        db.commit()
    return jsonify({'ok':True})


@gtd_bp.route('/api/project/<int:pid>', methods=['DELETE'])
def delete_project(pid):
    with get_db() as db:
        db.execute("UPDATE gtd_projects SET status='archived' WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok':True})


@gtd_bp.route('/api/word/refresh')
def word_refresh():
    return jsonify(get_random_word())
