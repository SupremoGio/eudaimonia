from flask import Blueprint, render_template, request, jsonify
from datetime import date, timedelta
from database import get_db
from data import SATURDAY_TASKS

sabado_bp = Blueprint('sabado', __name__, template_folder='../../templates')


def week_start():
    today = date.today()
    days_since_sat = (today.weekday() + 2) % 7
    return (today - timedelta(days=days_since_sat)).isoformat()


@sabado_bp.route('/')
def index():
    ws = week_start()
    with get_db() as db:
        checks = {r["task_key"]: r["done"] for r in db.execute(
            "SELECT task_key, done FROM saturday_checks WHERE week_start=?", (ws,)
        ).fetchall()}
    tasks      = [{"key": t["key"], "label": t["label"], "done": checks.get(t["key"], 0)} for t in SATURDAY_TASKS]
    done_count = sum(1 for t in tasks if t["done"])
    return render_template('sabado/index.html',
        tasks=tasks, done_count=done_count, total=len(SATURDAY_TASKS),
        week_start=ws, is_saturday=(date.today().weekday() == 5),
    )


@sabado_bp.route('/api/toggle', methods=['POST'])
def toggle():
    key = request.json.get('key')
    ws  = week_start()
    with get_db() as db:
        row = db.execute("SELECT done FROM saturday_checks WHERE week_start=? AND task_key=?", (ws, key)).fetchone()
        if row:
            db.execute("UPDATE saturday_checks SET done=? WHERE week_start=? AND task_key=?",
                       (0 if row["done"] else 1, ws, key))
        else:
            db.execute("INSERT INTO saturday_checks (week_start, task_key, done) VALUES (?,?,1)", (ws, key))
        db.commit()
        checks = {r["task_key"]: r["done"] for r in db.execute(
            "SELECT task_key, done FROM saturday_checks WHERE week_start=?", (ws,)
        ).fetchall()}
    tasks      = [{"key": t["key"], "label": t["label"], "done": checks.get(t["key"], 0)} for t in SATURDAY_TASKS]
    done_count = sum(1 for t in tasks if t["done"])
    return jsonify({"tasks": tasks, "done_count": done_count, "total": len(SATURDAY_TASKS)})
