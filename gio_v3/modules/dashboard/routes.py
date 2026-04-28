from flask import Blueprint, render_template, jsonify, redirect
from database import get_db, get_db_status
from data import get_word_of_day, ACTIVITIES, ACTIVITY_CATEGORIES
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

        # PTS stats
        week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        month_start = date.today().replace(day=1).isoformat()
        pts_today_val  = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date=?",   (today,)).fetchone()['s']
        pts_week_val   = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date>=?",  (week_start,)).fetchone()['s']
        pts_month_val  = db.execute("SELECT COALESCE(SUM(pts),0) as s FROM activity_logs WHERE date>=?",  (month_start,)).fetchone()['s']

        # Max streak y semanas activo (para perfil)
        _all_dates = sorted({r['date'] for r in all_logs})
        max_streak, cur_streak, prev_d = 0, 0, None
        for d_str in _all_dates:
            dd = date.fromisoformat(d_str)
            cur_streak = (cur_streak + 1) if (prev_d and dd == prev_d + timedelta(days=1)) else 1
            max_streak = max(max_streak, cur_streak)
            prev_d = dd
        weeks_active = len({date.fromisoformat(r['date']).isocalendar()[:2] for r in all_logs if r['date']})

        # EC balance
        ec_balance = max(0, int(db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger"
        ).fetchone()['s'] or 0))

        # Recordatorios activos (próximos 7 días)
        reminders_rows = db.execute("""
            SELECT id, description, type, freq_unit, freq_value, target_date, next_date
            FROM reminders
            WHERE is_active=1
            AND COALESCE(next_date, target_date, '9999-12-31') <= ?
            ORDER BY COALESCE(next_date, target_date)
            LIMIT 5
        """, ((date.today() + timedelta(days=7)).isoformat(),)).fetchall()

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

    activities = [
        {'key': k, 'label': v['label'], 'cat': v['cat'], 'pts': v['pts'], 'done': k in today_keys}
        for k, v in ACTIVITIES.items()
    ]

    return {
        'total_xp':       stats['total_xp'],
        'xp_today':       stats['xp_today'],
        'level':          stats['level'],
        'level_name':     stats['level_name'],
        'level_pct':      stats['level_pct'],
        'xp_to_next':     stats['xp_to_next'],
        'streak':         stats['streak'],
        'classification': stats['classification'],
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
        'activities': activities,
        'act_cats':   list(ACTIVITY_CATEGORIES),
        'pts_today':    pts_today_val,
        'pts_week':     pts_week_val,
        'pts_month':    pts_month_val,
        'max_streak':   max_streak,
        'weeks_active': weeks_active,
        'word_of_day':  get_word_of_day(),
        'reminders':    [dict(r) for r in reminders_rows],
        'ec_balance':   ec_balance,
        'deadlines':    _build_deadlines(date.today()),
    }


# ── EUDAIMONIA — ruta principal ───────────────────────────────────────────────
@dashboard_bp.route('/')
def index():
    return render_template('base_eudaimonia.html', eudaimonia_data=_build_eudaimonia_data())


def _build_deadlines(today_dt: date) -> list:
    """Recordatorios activos con fecha en los próximos 6 días (o vencidos)."""
    horizon = (today_dt + timedelta(days=6)).isoformat()
    raw = []

    with get_db() as db:
        for r in db.execute("""
            SELECT id, description AS label, type AS rem_type,
                   COALESCE(next_date, target_date) AS fecha
            FROM reminders
            WHERE is_active=1
              AND COALESCE(next_date, target_date) IS NOT NULL
              AND COALESCE(next_date, target_date) <= ?
            ORDER BY fecha LIMIT 8
        """, (horizon,)).fetchall():
            raw.append(dict(r))

    deadlines = []
    for d in raw:
        try:
            d['type'] = 'reminder'
            days = (date.fromisoformat(d['fecha'][:10]) - today_dt).days
            d['days'] = days
            if days < 0:
                d['badge'] = 'VENCIDO'
                d['level'] = 'red'
            elif days == 0:
                d['badge'] = 'HOY'
                d['level'] = 'red'
            elif days <= 2:
                d['badge'] = str(days)
                d['level'] = 'amber'
            elif days == 3:
                d['badge'] = str(days)
                d['level'] = 'yellow'
            else:
                d['badge'] = str(days)
                d['level'] = 'green'
            deadlines.append(d)
        except Exception:
            pass

    deadlines.sort(key=lambda x: x['days'])
    return deadlines[:8]


# ── Redirecciones de compatibilidad ──────────────────────────────────────────
@dashboard_bp.route('/classic')
@dashboard_bp.route('/v2')
def legacy_redirect():
    return redirect('/', 301)


# ── API ───────────────────────────────────────────────────────────────────────
@dashboard_bp.route('/api/xp')
def api_xp():
    from modules.gamification.engine import get_gamification_stats
    return jsonify(get_gamification_stats())


@dashboard_bp.route('/api/db-status')
def api_db_status():
    return jsonify(get_db_status())
