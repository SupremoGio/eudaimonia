from flask import Blueprint, render_template, request, jsonify
from datetime import timedelta, datetime
import time
from database import get_db
from data import ACTIVITIES, ACTIVITY_CATEGORIES, get_stoic_of_day, get_motivational_of_day, get_random_quote
from utils import today_str, today_date, now_local
from ec_constants import CATEGORY_HUES
import modules.gamification.engine as engine
import modules.actividades.activity_defs as adefs

actividades_bp = Blueprint('actividades', __name__, template_folder='../../templates')

PILLAR_META = {
    # Hues alineados con window.EU.modules (eu-data.js) — mismo pilar, mismo
    # color en el Home y en Acta Diurna.
    "logoi":   {"name": "Logoi",          "hue": 120},
    "paideia": {"name": "Paideia",        "hue": 265},
    "cosmo":   {"name": "Cosmopolitismo", "hue": 215},
    "hege":    {"name": "Hegemonikon",    "hue": 45},
    "eury":    {"name": "Eurythmia",      "hue": 330},
    "atar":    {"name": "Ataraxia",       "hue": 155},
    "oiko":    {"name": "Oikonomia",      "hue": 80},
    "philia":  {"name": "Philia",         "hue": 10},
}
SESSION_META = {
    "morning":   {"label": "Mañana", "window": "6:00 – 13:00"},
    "afternoon": {"label": "Tarde",  "window": "13:00 – 19:00"},
    "night":     {"label": "Noche",  "window": "19:00 – 23:00"},
    "any":       {"label": "Cualquier momento", "window": ""},
}


# Días en que Baile es la ancla semanal (sesión profunda) — ver calendario
# de Fase 3. No es una fila de activity_defs: el card pasivo de Eurythmia
# solo cambia de copy según esto, sigue leyendo eurythmia_session tal cual.
EURYTHMIA_ANCLA_DAYS = {"tue", "sat"}


def get_eurythmia_today():
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key='eurythmia_session' AND date=?",
            (today_str(),)
        ).fetchone()
    return row is not None


def get_eurythmia_card():
    done      = get_eurythmia_today()
    ancla_day = adefs.weekday_code() in EURYTHMIA_ANCLA_DAYS
    if ancla_day and not done:
        return {"title": "Hoy toca Baile — tu ancla semanal", "subtitle": "Se llena solo desde Eurythmia", "badge": "Pendiente", "done": False}
    if ancla_day and done:
        return {"title": "Baile completado hoy", "subtitle": "Ancla semanal cumplida", "badge": "Hecho", "done": True}
    if not ancla_day and not done:
        return {"title": "¿Bailaste hoy?", "subtitle": "No era tu día ancla, pero cuenta si lo hiciste", "badge": "Opcional", "done": False}
    return {"title": "Bailaste hoy", "subtitle": "Extra — no era tu ancla", "badge": "Extra", "done": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_dashboard_stats():
    today       = today_str()
    _today      = today_date()
    week_start  = (_today - timedelta(days=_today.weekday())).isoformat()
    month_start = _today.replace(day=1).isoformat()

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
    d = today_date().day
    alerts = []
    if d == 15:
        alerts += [{"label": "BBVA", "color": "#c5a36c"}, {"label": "Invex", "color": "#a78bfa"}]
    if d == 30:
        alerts.append({"label": "HSBC", "color": "#60a5fa"})
    return alerts


def get_weekend_mode():
    """Returns 'sat', 'sun', or None depending on today."""
    dow = today_date().weekday()   # 5 = Saturday, 6 = Sunday
    if dow == 5: return "sat"
    if dow == 6: return "sun"
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

def _now_session():
    """Sesión que coincide con la hora real (zona horaria de la app, no la
    del servidor — Railway corre en UTC), para expandir esa tarjeta arriba."""
    hour = now_local().hour
    if 6 <= hour < 13:  return "morning"
    if 13 <= hour < 19: return "afternoon"
    if 19 <= hour < 23: return "night"
    return "afternoon"  # madrugada: se ancla a la sesión más reciente por defecto


def build_acta_diurna_context():
    """Agrupación de actividades por sesión + foco del mes + Eurythmia pasivo.

    Compartido por la página Jinja (/actividades) y el endpoint JSON que
    consume la pantalla React (/actividades/api/today) — una sola fuente
    de verdad para no duplicar (y desincronizar) esta lógica entre las dos.
    """
    grouped    = adefs.get_active_grouped()
    with get_db() as db:
        done_today = {r["activity_key"] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=?", (today_str(),)
        ).fetchall()}

    weekly_keys  = [i["key"] for items in grouped.values() for i in items if i.get("cadence") == "weekly"]
    week_counts  = adefs.get_week_counts(weekly_keys)

    by_pillar = {}
    for items in grouped.values():
        for item in items:
            item["done"] = item["key"] in done_today
            if item.get("cadence") == "weekly":
                item["week_count"] = week_counts.get(item["key"], 0)
            if item["type"] != "ocasional":
                by_pillar.setdefault(item["pillar"], []).append(item)

    # Pilares con >1 item elegible = candidatos a "foco del mes" (ancla configurable)
    foco_candidates = {p: items for p, items in by_pillar.items() if len(items) > 1}

    return {
        "grouped":         grouped,
        "now_session":     _now_session(),
        "session_meta":    SESSION_META,
        "pillar_meta":     PILLAR_META,
        "pillar_focus":    adefs.get_pillar_focus_map(),
        "foco_candidates": foco_candidates,
        "eurythmia_done":  get_eurythmia_today(),
        "eurythmia_card":  get_eurythmia_card(),
    }


@actividades_bp.route('/')
def index():
    stats        = get_dashboard_stats()
    gam          = engine.get_gamification_stats()
    weekend_mode = get_weekend_mode()

    # Weekend activities separated (bloques Sábado/Domingo, sistema aparte)
    sat_acts = {k: v for k, v in ACTIVITIES.items() if v.get("weekend") == "sat"}
    sun_acts = {k: v for k, v in ACTIVITIES.items() if v.get("weekend") == "sun"}

    ctx = build_acta_diurna_context()

    _td = today_date()
    return render_template('actividades/index.html',
        stats         = stats,
        gam           = gam,
        grouped       = ctx["grouped"],
        now_session   = ctx["now_session"],
        session_meta  = ctx["session_meta"],
        pillar_meta   = ctx["pillar_meta"],
        pillar_focus  = ctx["pillar_focus"],
        foco_candidates = ctx["foco_candidates"],
        eurythmia_done= ctx["eurythmia_done"],
        eurythmia_card= ctx["eurythmia_card"],
        sat_acts      = sat_acts,
        sun_acts      = sun_acts,
        cats          = ACTIVITY_CATEGORIES,
        category_hues = CATEGORY_HUES,
        quote_stoic   = get_stoic_of_day(),
        quote_motiv   = get_motivational_of_day(),
        payment_alerts= get_payment_alerts(),
        today         = _td.isoformat(),
        today_name    = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][_td.weekday()],
        weekend_mode  = weekend_mode,
        classification= gam["classification"],
    )


@actividades_bp.route('/api/today')
def today_status():
    today       = today_str()
    _today      = today_date()
    week_start  = (_today - timedelta(days=_today.weekday())).isoformat()
    month_start = _today.replace(day=1).isoformat()
    with get_db() as db:
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

    ctx = build_acta_diurna_context()
    return jsonify({
        'grouped':         ctx["grouped"],
        'now_session':     ctx["now_session"],
        'session_meta':    ctx["session_meta"],
        'pillar_meta':     ctx["pillar_meta"],
        'pillar_focus':    ctx["pillar_focus"],
        'foco_candidates': ctx["foco_candidates"],
        'eurythmia_done':  ctx["eurythmia_done"],
        'eurythmia_card':  ctx["eurythmia_card"],
        'xp': {'today': xp_today, 'week': xp_week, 'month': xp_month},
        'streak': engine.get_gamification_streak(),
        'classification': engine.get_daily_classification(today),
        'date': today,
    })


@actividades_bp.route('/api/classification')
def classification():
    today = request.args.get('date', today_str())
    return jsonify(engine.get_daily_classification(today))


@actividades_bp.route('/api/activity/log', methods=['POST'])
def log_activity():
    _t0 = time.perf_counter()
    key   = request.json.get('key')
    today = today_str()
    act = adefs.get_by_key(key)
    if not act or not act['active'] or act['hidden']:
        return jsonify({'error': 'invalid'}), 400

    pts = act['pts']
    cat = act['cat']
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
    _t1 = time.perf_counter()

    if removed_id:
        gam = engine.remove_activity(removed_id)
        _t2 = time.perf_counter()
        stats = get_dashboard_stats()
        _t3 = time.perf_counter()
        print(f"[logAct] sqlite={(_t1-_t0)*1000:.1f}ms engine={(_t2-_t1)*1000:.1f}ms stats={(_t3-_t2)*1000:.1f}ms TOTAL={(_t3-_t0)*1000:.1f}ms")
        return jsonify({'action': 'removed', 'pts': -pts, 'stats': stats, 'gam': gam})

    gam = engine.process_activity(key, pts, cat, log_id)
    _t2 = time.perf_counter()
    stats = get_dashboard_stats()
    _t3 = time.perf_counter()
    print(f"[logAct] sqlite={(_t1-_t0)*1000:.1f}ms engine={(_t2-_t1)*1000:.1f}ms stats={(_t3-_t2)*1000:.1f}ms TOTAL={(_t3-_t0)*1000:.1f}ms")
    return jsonify({'action': 'added', 'pts': pts, 'xp': gam['xp'], 'ec': gam['ec'],
                    'log_id': log_id, 'stats': stats, 'gam': gam})


# ── CRUD de actividades (Acta Diurna) ───────────────────────────────────────

@actividades_bp.route('/api/activity/create', methods=['POST'])
def create_activity():
    data = request.json or {}
    label = (data.get('label') or '').strip()
    pillar = data.get('pillar')
    type_  = data.get('type', 'touch')
    session = data.get('session')
    if type_ == 'ocasional':
        session = None
    try:
        pts = int(data.get('pts', 1))
        ec  = int(data.get('ec', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'pts/ec inválidos'}), 400
    if not label or pillar not in adefs.PILLARS or type_ not in adefs.TYPES:
        return jsonify({'error': 'datos incompletos o inválidos'}), 400
    try:
        act = adefs.create(label=label, pillar=pillar, type_=type_, session=session, pts=pts, ec=ec)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True, 'activity': act})


@actividades_bp.route('/api/activity/update/<key>', methods=['POST'])
def update_activity(key):
    if not adefs.get_by_key(key):
        return jsonify({'error': 'not found'}), 404
    data = request.json or {}
    fields = {k: v for k, v in data.items() if k in
              {'label', 'cat', 'pts', 'ec', 'tier', 'session', 'pillar', 'type'}}
    act = adefs.update(key, **fields)
    return jsonify({'ok': True, 'activity': act})


@actividades_bp.route('/api/activity/<key>', methods=['DELETE'])
def delete_activity(key):
    act = adefs.get_by_key(key)
    if not act:
        return jsonify({'error': 'not found'}), 404
    adefs.deactivate(key)
    return jsonify({'ok': True})


@actividades_bp.route('/api/pillar-focus', methods=['GET'])
def get_pillar_focus():
    return jsonify(adefs.get_pillar_focus_map())


@actividades_bp.route('/api/pillar-focus', methods=['POST'])
def post_pillar_focus():
    data = request.json or {}
    pillar = data.get('pillar')
    focus_key = data.get('focus_key')
    try:
        adefs.set_pillar_focus(pillar, focus_key)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True, 'pillar_focus': adefs.get_pillar_focus_map()})


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
    today = today_str()
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
    today = today_str()
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


@actividades_bp.route('/api/activity/undo/<int:log_id>', methods=['POST'])
def undo_activity(log_id):
    today = today_str()
    with get_db() as db:
        row = db.execute(
            "SELECT id, activity_key, pts FROM activity_logs WHERE id=? AND date=?",
            (log_id, today)
        ).fetchone()
        if not row:
            return jsonify({'error': 'not found or not today'}), 404
        db.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
        db.commit()
    gam   = engine.remove_activity(log_id)
    stats = get_dashboard_stats()
    return jsonify({'ok': True, 'stats': stats, 'gam': gam})


@actividades_bp.route('/api/quote/refresh')
def refresh_quote():
    cat = request.args.get('cat')  # 'stoic' | 'motivational' | None
    return jsonify(get_random_quote(category=cat))


