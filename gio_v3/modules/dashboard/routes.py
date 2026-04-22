from flask import Blueprint, render_template, jsonify, redirect, url_for
from database import get_db, get_gtd_stats, get_activity_streak, get_db_status
from data import get_quote_of_day, get_word_of_day, ACTIVITIES
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')

# ── Module → activity category mapping ───────────────────────────────────────
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
    {'id': 'hegemonikon',    'name': 'HEGEMONIKON',    'concept': 'Bienestar',     'desc': 'Salud · Nutrición · Perfil',  'hue': 45,  'route': '/actividades'},
    {'id': 'oikonomia',      'name': 'OIKONOMIA',      'concept': 'Finanzas',      'desc': 'Finanzas · Gastos · Deudas',  'hue': 80,  'route': '/finanzas'},
    {'id': 'ataraxia',       'name': 'ATARAXIA',       'concept': 'Productividad', 'desc': 'Automatización · Checklist',  'hue': 155, 'route': '/gtd'},
    {'id': 'paideia',        'name': 'PAIDEIA',        'concept': 'Conocimiento',  'desc': 'Aprendizaje · Libros',        'hue': 265, 'route': '/actividades'},
    {'id': 'cosmopolitismo', 'name': 'COSMOPOLITISMO', 'concept': 'Idiomas',       'desc': 'Idiomas · Culturas',          'hue': 215, 'route': '/idiomas'},
    {'id': 'logoi',          'name': 'LOGOI',          'concept': 'Programación',  'desc': 'Programación · Lógica',       'hue': 120, 'route': '/actividades'},
    {'id': 'eurythmia',      'name': 'EURYTHMIA',      'concept': 'Baile',         'desc': 'Baile · Ritmo · Cuerpo',      'hue': 330, 'route': '/actividades'},
]

# Habit → activity keys que la marcan como done si se loguearon hoy
_MODULE_HABIT_KEYS = {
    'hegemonikon': [
        ['colacion', 'jugo_verde'],
        [],
        ['gym', 'pliometria', 'gol'],
        ['meditar'],
    ],
    'oikonomia': [
        ['registrar_gastos'],
        ['finanzas_udemy'],
        [],
    ],
    'ataraxia': [
        ['tender_cama', 'limpieza', 'prep_comida', 'planchar'],
        ['revision_semanal'],
        ['revision_semanal'],
    ],
    'paideia': [
        ['leer_general', 'leer_psico', 'leer_365_dias'],
        ['brilliant'],
        [],
    ],
    'cosmopolitismo': [
        ['leccion_idiomas', 'VividVocab'],
        ['podcast_idiomas'],
        ['conversacion'],
    ],
    'logoi': [
        ['sololearn', 'python100', 'ccna', 'resolver_codigo'],
        ['github', 'python100'],
        ['leer_prog'],
    ],
    'eurythmia': [
        ['baile', 'grabar_baile'],
        ['grabar_baile'],
        [],
    ],
}


def _build_eudaimonia_data():
    """Construye el payload completo para window.__EUDAIMONIA_DATA__."""
    from modules.gamification.engine import get_gamification_stats

    stats = get_gamification_stats()
    today = date.today().isoformat()

    with get_db() as db:
        # Actividades de hoy y su historial para streaks
        all_logs = db.execute(
            "SELECT activity_key, date FROM activity_logs ORDER BY date DESC"
        ).fetchall()
        today_keys = {r['activity_key'] for r in all_logs if r['date'] == today}

        # GTD inbox
        inbox_rows = db.execute(
            "SELECT id, title, context FROM gtd_tasks WHERE status='inbox' ORDER BY id DESC LIMIT 20"
        ).fetchall()

        # Resumen financiero (mes actual)
        mes = today[:7]
        fin_row = db.execute(
            "SELECT id, ingreso_total FROM budget_meses WHERE mes=?", (mes,)
        ).fetchone()
        fin_gastos = 0
        if fin_row:
            fin_gastos = db.execute(
                "SELECT COALESCE(SUM(monto_real),0) as s FROM budget_items WHERE budget_id=?",
                (fin_row['id'],)
            ).fetchone()['s'] or 0
        fin_ingreso = fin_row['ingreso_total'] if fin_row else 0
        deudas_activas = db.execute(
            "SELECT COALESCE(SUM(saldo_actual),0) as s FROM budget_deudas WHERE activa=1"
        ).fetchone()['s'] or 0

        # Métricas corporales
        body = {r['key']: r['value'] for r in db.execute(
            "SELECT key, value FROM body_measurements"
        ).fetchall()}

        # Idiomas: test results más recientes por idioma
        lang_rows = db.execute(
            "SELECT test_type, score, test_date FROM lang_test_results ORDER BY test_date DESC LIMIT 10"
        ).fetchall()

        # Journal de idiomas (conteo por idioma para streak aproximado)
        lang_journal = db.execute(
            "SELECT language, COUNT(*) as cnt FROM lang_journal GROUP BY language"
        ).fetchall()
        lang_cnt = {r['language']: r['cnt'] for r in lang_journal}

    # ── {date: set(cats)} para streaks por módulo ────────────────────────────
    date_cats = {}
    for row in all_logs:
        cat = ACTIVITIES.get(row['activity_key'], {}).get('cat')
        if cat:
            date_cats.setdefault(row['date'], set()).add(cat)

    # ── Módulos con streak, done y route ────────────────────────────────────
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

    # ── Hábitos done basados en actividades de hoy ───────────────────────────
    habits_done = {}
    for mod_id, habit_keys_list in _MODULE_HABIT_KEYS.items():
        habits_done[mod_id] = [
            any(k in today_keys for k in keys) if keys else False
            for keys in habit_keys_list
        ]

    # ── GTD inbox ───────────────────────────────────────────────────────────
    gtd_inbox = [
        {
            'id':      r['id'],
            'text':    r['title'],
            'context': f"@{r['context']}" if r['context'] else '@inbox',
        }
        for r in inbox_rows
    ]

    # ── Lang stats aproximados ───────────────────────────────────────────────
    lang_scores = {}
    for r in lang_rows:
        if r['test_type'] not in lang_scores:
            lang_scores[r['test_type']] = r['score']

    lang_stats = [
        {'lang': 'Alemán',  'lvl': lang_scores.get('Alemán',  lang_scores.get('DALF', 'B1+')), 'entries': lang_cnt.get('Alemán',  0), 'pct': 0.72},
        {'lang': 'Inglés',  'lvl': lang_scores.get('Inglés',  lang_scores.get('IELTS','C1')),  'entries': lang_cnt.get('Inglés',  0), 'pct': 0.91},
        {'lang': 'Francés', 'lvl': lang_scores.get('Francés', 'A2'),                            'entries': lang_cnt.get('Francés', 0), 'pct': 0.25},
    ]

    return {
        'total_xp':   stats['total_xp'],
        'xp_today':   stats['xp_today'],
        'level':      stats['level'],
        'level_name': stats['level_name'],
        'level_pct':  stats['level_pct'],
        'xp_to_next': stats['xp_to_next'],
        'streak':     stats['streak'],
        'modules':    modules,
        'gtd_inbox':  gtd_inbox,
        'habits_done': habits_done,
        'financial': {
            'ingreso':  fin_ingreso,
            'gastos':   fin_gastos,
            'deudas':   deudas_activas,
        },
        'body': body,
        'lang_stats': lang_stats,
    }


# ── EUDAIMONIA — ruta principal ───────────────────────────────────────────────
@dashboard_bp.route('/')
def index():
    return render_template('base_eudaimonia.html', eudaimonia_data=_build_eudaimonia_data())


# ── Dashboard clásico ─────────────────────────────────────────────────────────
@dashboard_bp.route('/classic')
def index_classic():
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


# ── /v2 redirige a / ──────────────────────────────────────────────────────────
@dashboard_bp.route('/v2')
def eudaimonia_v2():
    return redirect(url_for('dashboard.index'))


# ── API ───────────────────────────────────────────────────────────────────────
@dashboard_bp.route('/api/xp')
def api_xp():
    from modules.gamification.engine import get_gamification_stats
    return jsonify(get_gamification_stats())


@dashboard_bp.route('/api/db-status')
def api_db_status():
    return jsonify(get_db_status())
