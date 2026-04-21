from flask import Blueprint, render_template
from database import get_db, get_gtd_stats, get_activity_streak
from data import get_quote_of_day, get_word_of_day
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')


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
