from flask import Blueprint, render_template, request, jsonify
from datetime import date, timedelta
from database import get_db
from data import ACTIVITIES, ACTIVITY_CATEGORIES, get_quote_of_day, get_word_of_day, get_random_quote
import modules.gamification.engine as engine

actividades_bp = Blueprint('actividades', __name__, template_folder='../../templates')


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_dashboard_stats():
    today       = date.today().isoformat()
    week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()

    with get_db() as db:
        pts_today  = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date=?",      (today,)).fetchone()["s"]
        pts_week   = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date>=?",     (week_start,)).fetchone()["s"]
        pts_month  = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date>=?",     (month_start,)).fetchone()["s"]
        done_today = [r["activity_key"] for r in db.execute("SELECT activity_key FROM activity_logs WHERE date=?", (today,)).fetchall()]
        pipeline   = db.execute("SELECT * FROM pipeline_items ORDER BY id DESC").fetchall()
        priorities = db.execute("SELECT * FROM priorities WHERE date=? ORDER BY id", (today,)).fetchall()

        dates = [r["date"] for r in db.execute("SELECT DISTINCT date FROM activity_logs ORDER BY date DESC").fetchall()]
        streak, check = 0, date.today()
        for d in dates:
            if d == check.isoformat():
                streak += 1
                check -= timedelta(days=1)
            else:
                break

    return {
        "pts_today": pts_today, "pts_week": pts_week, "pts_month": pts_month,
        "streak": streak, "done_today": done_today,
        "pipeline":   [dict(r) for r in pipeline],
        "priorities": [dict(r) for r in priorities],
    }


def get_payment_alerts():
    d = date.today().day
    alerts = []
    if d == 15:
        alerts += [{"label": "BBVA", "color": "#c5a36c"}, {"label": "Invex", "color": "#a78bfa"}]
    if d == 30:
        alerts.append({"label": "HSBC", "color": "#60a5fa"})
    return alerts


# ── Routes ────────────────────────────────────────────────────────────────────

@actividades_bp.route('/')
def index():
    stats = get_dashboard_stats()
    return render_template('actividades/index.html',
        stats=stats,
        activities=ACTIVITIES,
        cats=ACTIVITY_CATEGORIES,
        quote=get_quote_of_day(),
        word=get_word_of_day(),
        payment_alerts=get_payment_alerts(),
        today=date.today().isoformat(),
        gam_stats=engine.get_gamification_stats(),
    )


@actividades_bp.route('/api/activity/log', methods=['POST'])
def log_activity():
    key   = request.json.get('key')
    today = date.today().isoformat()
    if key not in ACTIVITIES:
        return jsonify({'error': 'invalid'}), 400

    pts = ACTIVITIES[key]['pts']
    cat = ACTIVITIES[key]['cat']

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (key, today)
        ).fetchone()

        if existing:
            log_id = existing["id"]
            db.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
            db.commit()
            gam = engine.remove_activity(log_id)
            return jsonify({'action': 'removed', 'pts': -pts, 'stats': get_dashboard_stats(), 'gam': gam})

        cursor = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)", (key, today, pts)
        )
        log_id = cursor.lastrowid
        db.commit()

    gam = engine.process_activity(key, pts, cat, log_id)
    return jsonify({'action': 'added', 'pts': pts, 'stats': get_dashboard_stats(), 'gam': gam})


@actividades_bp.route('/api/pipeline', methods=['POST'])
def add_pipeline():
    text = request.json.get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty'}), 400
    from datetime import datetime
    with get_db() as db:
        db.execute("INSERT INTO pipeline_items (text, created_at) VALUES (?,?)", (text, datetime.now().isoformat()))
        db.commit()
        items = db.execute("SELECT * FROM pipeline_items ORDER BY id DESC").fetchall()
    return jsonify({'items': [dict(i) for i in items]})


@actividades_bp.route('/api/pipeline/<int:item_id>', methods=['DELETE'])
def delete_pipeline(item_id):
    with get_db() as db:
        db.execute("DELETE FROM pipeline_items WHERE id=?", (item_id,))
        db.commit()
    return jsonify({'ok': True})


@actividades_bp.route('/api/priority', methods=['POST'])
def add_priority():
    text  = request.json.get('text', '').strip()
    today = date.today().isoformat()
    if not text:
        return jsonify({'error': 'empty'}), 400
    with get_db() as db:
        if db.execute("SELECT COUNT(*) as c FROM priorities WHERE date=?", (today,)).fetchone()["c"] >= 3:
            return jsonify({'error': 'max 3'}), 400
        db.execute("INSERT INTO priorities (date, text) VALUES (?,?)", (today, text))
        db.commit()
        rows = db.execute("SELECT * FROM priorities WHERE date=? ORDER BY id", (today,)).fetchall()
    return jsonify({'priorities': [dict(r) for r in rows]})


@actividades_bp.route('/api/priority/<int:pid>/toggle', methods=['POST'])
def toggle_priority(pid):
    today = date.today().isoformat()
    with get_db() as db:
        row = db.execute("SELECT done FROM priorities WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute("UPDATE priorities SET done=? WHERE id=?", (0 if row["done"] else 1, pid))
        db.commit()

        rows  = db.execute("SELECT * FROM priorities WHERE date=? ORDER BY id", (today,)).fetchall()
        all3  = all(r["done"] for r in rows) and len(rows) == 3

        bonus_exists = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key='priority_bonus' AND date=?", (today,)
        ).fetchone()

        gam = None
        if all3 and not bonus_exists:
            db.execute(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                ('priority_bonus', today, 3)
            )
            db.commit()
            gam = engine.process_priority_bonus(today)

        elif not all3 and bonus_exists:
            db.execute("DELETE FROM activity_logs WHERE activity_key='priority_bonus' AND date=?", (today,))
            db.commit()
            gam = engine.remove_priority_bonus(today)

    return jsonify({'priorities': [dict(r) for r in rows], 'all3': all3,
                    'stats': get_dashboard_stats(), 'gam': gam})


@actividades_bp.route('/api/quote/refresh')
def refresh_quote():
    return jsonify(get_random_quote())


@actividades_bp.route('/api/word/refresh')
def refresh_word():
    from data import get_random_word
    return jsonify(get_random_word())
