from flask import Blueprint, render_template, jsonify
from database import get_db, get_gtd_stats, get_activity_streak, get_db_status
from data import get_quote_of_day, get_word_of_day, ACTIVITIES
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')

# Module → activity category mapping (mirrors eu-data.js EU.modules)
_MODULE_CATS = {
    'hegemonikon':    {'Salud Física', 'Salud Mental', 'Salud'},
    'oikonomia':      {'Finanzas'},
    'ataraxia':       {'Sistema', 'Orden', 'Enfoque'},
    'paideia':        {'Knowledge'},
    'cosmopolitismo': {'Idiomas'},
    'logoi':          {'Programación'},
    'eurythmia':      {'Baile'},
}

_EU_MODULES_BASE = [
    {'id': 'hegemonikon',    'name': 'HEGEMONIKON',    'concept': 'Bienestar',      'desc': 'Salud · Nutrición · Perfil',   'hue': 45},
    {'id': 'oikonomia',      'name': 'OIKONOMIA',      'concept': 'Finanzas',       'desc': 'Finanzas · Gastos · Deudas',   'hue': 80},
    {'id': 'ataraxia',       'name': 'ATARAXIA',       'concept': 'Productividad',  'desc': 'Automatización · Checklist',   'hue': 155},
    {'id': 'paideia',        'name': 'PAIDEIA',        'concept': 'Conocimiento',   'desc': 'Aprendizaje · Libros',         'hue': 265},
    {'id': 'cosmopolitismo', 'name': 'COSMOPOLITISMO', 'concept': 'Idiomas',        'desc': 'Idiomas · Culturas',           'hue': 215},
    {'id': 'logoi',          'name': 'LOGOI',          'concept': 'Programación',   'desc': 'Programación · Lógica',        'hue': 120},
    {'id': 'eurythmia',      'name': 'EURYTHMIA',      'concept': 'Baile',          'desc': 'Baile · Ritmo · Cuerpo',       'hue': 330},
]


@dashboard_bp.route('/')
def index():
    gtd   = get_gtd_stats()
    today = date.today().isoformat()
    week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()

    with get_db() as db:
        act_today = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date=?", (today,)).fetchone()["s"]
        act_week  = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date>=?", (week_start,)).fetchone()["s"]
        act_month = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date>=?", (month_start,)).fetchone()["s"]
        recent = db.execute("SELECT title, points, completed_at FROM gtd_tasks WHERE completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 8").fetchall()
        history = []
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            pts = db.execute("SELECT COALESCE(SUM(points_earned),0) as s FROM gtd_points_log WHERE date=?", (d,)).fetchone()["s"]
            history.append({"date": d, "pts": pts, "label": d[5:]})

    return render_template('dashboard/index.html',
        gtd=gtd, quote=get_quote_of_day(), word=get_word_of_day(),
        act_today=act_today, act_week=act_week, act_month=act_month,
        act_streak=get_activity_streak(), recent=recent, history=history, today=today,
    )


@dashboard_bp.route('/v2')
def eudaimonia_v2():
    from modules.gamification.engine import get_gamification_stats

    stats = get_gamification_stats()
    today = date.today().isoformat()

    with get_db() as db:
        logs = db.execute(
            "SELECT activity_key, date FROM activity_logs ORDER BY date DESC"
        ).fetchall()
        inbox_rows = db.execute(
            "SELECT id, title, context FROM gtd_tasks WHERE status='inbox' ORDER BY id DESC LIMIT 20"
        ).fetchall()

    # Build {date: set(categories)} map
    date_cats = {}
    for row in logs:
        cat = ACTIVITIES.get(row['activity_key'], {}).get('cat')
        if cat:
            date_cats.setdefault(row['date'], set()).add(cat)

    # Compute per-module streak and today-done flag
    modules = []
    for mod in _EU_MODULES_BASE:
        cats = _MODULE_CATS[mod['id']]
        streak, check = 0, date.today()
        while True:
            d = check.isoformat()
            if d in date_cats and date_cats[d] & cats:
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        done = bool(date_cats.get(today, set()) & cats)
        modules.append({**mod, 'streak': streak, 'done': done})

    gtd_inbox = [
        {
            'id':      r['id'],
            'text':    r['title'],
            'context': f"@{r['context']}" if r['context'] else '@inbox',
        }
        for r in inbox_rows
    ]

    eudaimonia_data = {
        'total_xp':   stats['total_xp'],
        'level':      stats['level'],
        'level_name': stats['level_name'],
        'level_pct':  stats['level_pct'],
        'xp_to_next': stats['xp_to_next'],
        'streak':     stats['streak'],
        'modules':    modules,
        'gtd_inbox':  gtd_inbox,
    }

    return render_template('base_eudaimonia.html', eudaimonia_data=eudaimonia_data)


@dashboard_bp.route('/api/xp')
def api_xp():
    from modules.gamification.engine import get_gamification_stats
    return jsonify(get_gamification_stats())


@dashboard_bp.route('/api/db-status')
def api_db_status():
    return jsonify(get_db_status())
