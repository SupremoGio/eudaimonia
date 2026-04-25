from flask import Blueprint, render_template, request, jsonify
from datetime import date, timedelta, datetime
from database import get_db
from data import ACTIVITIES, ACTIVITY_CATEGORIES, get_quote_of_day, get_word_of_day, get_random_quote, get_random_word
import modules.gamification.engine as engine

actividades_bp = Blueprint('actividades', __name__, template_folder='../../templates')


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_dashboard_stats():
    today       = date.today().isoformat()
    week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()

    with get_db() as db:
        xp_today   = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=?",
            (today,)
        ).fetchone()["s"]
        xp_week    = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=? AND date<=?",
            (week_start, today)
        ).fetchone()["s"]
        xp_month   = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=? AND date<=?",
            (month_start, today)
        ).fetchone()["s"]
        ec_total   = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger"
        ).fetchone()["s"]
        done_today = [r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=?", (today,)
        ).fetchall()]
        pipeline   = db.execute("SELECT * FROM pipeline_items ORDER BY id DESC").fetchall()
        priorities = db.execute("SELECT * FROM priorities WHERE date=? ORDER BY id", (today,)).fetchall()

    return {
        "xp_today":  xp_today,
        "xp_week":   xp_week,
        "xp_month":  xp_month,
        "ec_total":  max(0, ec_total),
        "streak":    engine.get_gamification_streak(),
        "done_today": done_today,
        "pipeline":  [dict(r) for r in pipeline],
        "priorities":[dict(r) for r in priorities],
        # Legacy aliases for template compatibility
        "pts_today": xp_today,
        "pts_week":  xp_week,
        "pts_month": xp_month,
    }


def get_payment_alerts():
    d = date.today().day
    alerts = []
    if d == 15:
        alerts += [{"label": "BBVA", "color": "#c5a36c"}, {"label": "Invex", "color": "#a78bfa"}]
    if d == 30:
        alerts.append({"label": "HSBC", "color": "#60a5fa"})
    return alerts


def get_weekend_mode():
    """Returns 'sat', 'sun', or None depending on today."""
    dow = date.today().weekday()   # 5 = Saturday, 6 = Sunday
    if dow == 5: return "sat"
    if dow == 6: return "sun"
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@actividades_bp.route('/')
def index():
    stats        = get_dashboard_stats()
    gam          = engine.get_gamification_stats()
    weekend_mode = get_weekend_mode()

    # Weekend activities separated
    sat_acts = {k: v for k, v in ACTIVITIES.items() if v.get("weekend") == "sat"}
    sun_acts = {k: v for k, v in ACTIVITIES.items() if v.get("weekend") == "sun"}
    # Regular activities (no weekend field)
    regular_acts = {k: v for k, v in ACTIVITIES.items() if "weekend" not in v}

    return render_template('actividades/index.html',
        stats         = stats,
        gam           = gam,
        activities    = regular_acts,
        sat_acts      = sat_acts,
        sun_acts      = sun_acts,
        cats          = ACTIVITY_CATEGORIES,
        quote         = get_quote_of_day(),
        word          = get_word_of_day(),
        payment_alerts= get_payment_alerts(),
        today         = date.today().isoformat(),
        today_name    = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][date.today().weekday()],
        weekend_mode  = weekend_mode,
        classification= gam["classification"],
    )


@actividades_bp.route('/api/today')
def today_status():
    today      = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()
    with get_db() as db:
        today_keys = {r['activity_key'] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=?", (today,)
        ).fetchall()}
        xp_today  = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date=?", (today,)
        ).fetchone()['s']
        xp_week   = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=? AND date<=?",
            (week_start, today)
        ).fetchone()['s']
        xp_month  = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE date>=? AND date<=?",
            (month_start, today)
        ).fetchone()['s']
    activities = [
        {'key': k, 'label': v['label'], 'cat': v['cat'], 'pts': v['pts'],
         'ec': v.get('ec', 0), 'tier': v.get('tier', 'micro'), 'done': k in today_keys}
        for k, v in ACTIVITIES.items()
    ]
    return jsonify({
        'activities': activities,
        'xp': {'today': xp_today, 'week': xp_week, 'month': xp_month},
        'streak': engine.get_gamification_streak(),
        'classification': engine.get_daily_classification(today),
        'date': today,
    })


@actividades_bp.route('/api/classification')
def classification():
    today = request.args.get('date', date.today().isoformat())
    return jsonify(engine.get_daily_classification(today))


@actividades_bp.route('/api/activity/log', methods=['POST'])
def log_activity():
    key   = request.json.get('key')
    today = date.today().isoformat()
    if key not in ACTIVITIES:
        return jsonify({'error': 'invalid'}), 400

    pts = ACTIVITIES[key]['pts']
    cat = ACTIVITIES[key]['cat']
    removed_id = None
    log_id     = None

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (key, today)
        ).fetchone()

        if existing:
            removed_id = existing["id"]
            db.execute("DELETE FROM activity_logs WHERE id=?", (removed_id,))
        else:
            cursor = db.execute(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)", (key, today, pts)
            )
            log_id = cursor.lastrowid
        db.commit()

    if removed_id:
        gam = engine.remove_activity(removed_id)
        return jsonify({'action': 'removed', 'pts': -pts, 'stats': get_dashboard_stats(), 'gam': gam})

    gam = engine.process_activity(key, pts, cat, log_id)
    return jsonify({'action': 'added', 'pts': pts, 'xp': gam['xp'], 'ec': gam['ec'],
                    'stats': get_dashboard_stats(), 'gam': gam})


@actividades_bp.route('/api/pipeline', methods=['POST'])
def add_pipeline():
    text = request.json.get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty'}), 400
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
    bonus_action = None

    with get_db() as db:
        row = db.execute("SELECT done FROM priorities WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute("UPDATE priorities SET done=? WHERE id=?", (0 if row["done"] else 1, pid))
        db.commit()

        rows  = [dict(r) for r in db.execute("SELECT * FROM priorities WHERE date=? ORDER BY id", (today,)).fetchall()]
        all3  = len(rows) == 3 and all(r["done"] for r in rows)

        bonus_exists = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key='priority_bonus' AND date=?", (today,)
        ).fetchone()

        if all3 and not bonus_exists:
            db.execute(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                ('priority_bonus', today, 5)
            )
            db.commit()
            bonus_action = 'add'
        elif not all3 and bonus_exists:
            db.execute("DELETE FROM activity_logs WHERE activity_key='priority_bonus' AND date=?", (today,))
            db.commit()
            bonus_action = 'remove'

    if bonus_action == 'add':
        gam = engine.process_priority_bonus(today)
    elif bonus_action == 'remove':
        gam = engine.remove_priority_bonus(today)
    else:
        gam = None

    return jsonify({'priorities': rows, 'all3': all3, 'stats': get_dashboard_stats(), 'gam': gam})


@actividades_bp.route('/api/quote/refresh')
def refresh_quote():
    return jsonify(get_random_quote())


@actividades_bp.route('/api/word/refresh')
def refresh_word():
    return jsonify(get_random_word())
