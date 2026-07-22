from flask import Blueprint, render_template, jsonify, redirect
from database import get_db, get_db_status
from data import get_word_of_day, get_quote_of_day, get_random_quote, ACTIVITIES, ACTIVITY_CATEGORIES
from datetime import date, timedelta
from utils import today_str, today_date, now_local
from ec_constants import CATEGORY_HUES

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')

# ── Module → activity category mapping ───────────────────────────────────────
_MODULE_CATS = {
    'hegemonikon':    {'Salud Física', 'Salud Mental', 'Salud Base'},
    'oikonomia':      {'Finanzas'},
    'ataraxia':       {'Orden', 'Sábado Reset', 'Domingo Strategy'},
    'paideia':        {'Paideia'},
    'cosmopolitismo': {'Idiomas'},
    'logoi':          {'Programación'},
    'eurythmia':      {'Baile'},
}

_EU_MODULES_BASE = [
    {'id': 'hegemonikon',    'name': 'HEGEMONIKON',    'concept': 'Bienestar',     'desc': 'Salud · Nutrición · Fútbol · Perfil',  'hue': 45 },
    {'id': 'oikonomia',      'name': 'OIKONOMIA',      'concept': 'Finanzas',      'desc': 'Finanzas · Gastos · Deudas',  'hue': 80,  'route': '/finanzas'},
    {'id': 'ataraxia',       'name': 'ATARAXIA',       'concept': 'Productividad', 'desc': 'Automatización · Checklist',  'hue': 155},
    {'id': 'paideia',        'name': 'PAIDEIA',        'concept': 'Conocimiento',  'desc': 'Aprendizaje · Libros',        'hue': 265},
    {'id': 'cosmopolitismo', 'name': 'COSMOPOLITISMO', 'concept': 'Idiomas',       'desc': 'Idiomas · Culturas',          'hue': 215},
    {'id': 'logoi',          'name': 'LOGOI',          'concept': 'Programación',  'desc': 'Programación · Lógica',       'hue': 120},
    {'id': 'eurythmia',      'name': 'EURYTHMIA',      'concept': 'Baile',         'desc': 'Baile · Ritmo · Cuerpo',      'hue': 330},
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
        ['eurythmia_session'],
        ['eurythmia_grabado'],
        [],
    ],
}


# ── Ventanas horarias para sugerencias "inteligentes" ─────────────────────────
# weekdays: None = todos los días, o set de now.weekday() (0=lunes .. 6=domingo)
# start/end: (hora, minuto), inclusive
_SUGGESTION_WINDOWS = {
    'gym':            {'weekdays': {0, 1, 2, 3, 4}, 'start': (6, 30),  'end': (23, 0)},
    'gymbook':        {'weekdays': {0, 1, 2, 3, 4}, 'start': (6, 30),  'end': (23, 0)},
    'dormir_8h':      {'weekdays': None,            'start': (9, 0),   'end': (11, 0)},
    'skincare_noche': {'weekdays': None,            'start': (20, 0),  'end': (23, 30)},
    'tender_cama':    {'weekdays': None,            'start': (9, 0),   'end': (11, 0)},
}


def _suggestion_in_window(key: str, now_dt) -> bool:
    """True si `key` no tiene ventana definida, o si `now_dt` cae dentro de ella."""
    win = _SUGGESTION_WINDOWS.get(key)
    if not win:
        return True
    if win['weekdays'] is not None and now_dt.weekday() not in win['weekdays']:
        return False
    now_min   = now_dt.hour * 60 + now_dt.minute
    start_min = win['start'][0] * 60 + win['start'][1]
    end_min   = win['end'][0] * 60 + win['end'][1]
    return start_min <= now_min <= end_min


def _build_suggestion(done_keys: set):
    from collections import defaultdict
    now_dt = now_local()
    by_cat = defaultdict(list)
    for k, v in ACTIVITIES.items():
        if 'weekend' not in v and not v.get('hidden'):
            by_cat[v['cat']].append(k)
    for cat, keys in by_cat.items():
        pending = [k for k in keys if k not in done_keys]
        if len(pending) == 1 and len(keys) > 1 and _suggestion_in_window(pending[0], now_dt):
            v = ACTIVITIES[pending[0]]
            return {'key': pending[0], 'label': v['label'], 'cat': cat, 'pts': v['pts']}
    return None


def _build_eudaimonia_data():
    """Construye el payload completo para window.__EUDAIMONIA_DATA__."""
    from modules.gamification.engine import get_gamification_stats

    stats = get_gamification_stats()
    today = today_str()
    _today = today_date()

    with get_db() as db:
        # Actividades de hoy y su historial para streaks
        all_logs = db.execute(
            "SELECT activity_key, date FROM activity_logs ORDER BY date DESC"
        ).fetchall()
        today_keys = {r['activity_key'] for r in all_logs if r['date'] == today}

        # GTD inbox (items sin clasificar en el nuevo modelo Praxis)
        inbox_rows = db.execute(
            "SELECT id, title FROM gtd_tasks WHERE cuadrante IS NULL AND completado=0 ORDER BY id DESC LIMIT 20"
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
        week_start  = (_today - timedelta(days=_today.weekday())).isoformat()
        month_start = _today.replace(day=1).isoformat()
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
        """, ((_today + timedelta(days=7)).isoformat(),)).fetchall()

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
        streak, check = 0, _today
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
            'context': '@inbox',
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
        for k, v in ACTIVITIES.items() if not v.get('hidden')
    ]

    # EURYTHMIA — resumen de práctica real de hoy (reemplaza el checklist manual)
    with get_db() as db:
        eury_row = db.execute(
            "SELECT COALESCE(SUM(min),0) as min, COALESCE(SUM(xp),0) as xp, COUNT(*) as sessions "
            "FROM eury_sessions WHERE date=?", (today,)
        ).fetchone()
        eury_last_step = db.execute(
            "SELECT step FROM eury_sessions WHERE date=? ORDER BY id DESC LIMIT 1", (today,)
        ).fetchone()
    eury_today = {
        'min':      eury_row['min'],
        'xp':       eury_row['xp'],
        'sessions': eury_row['sessions'],
        'step':     eury_last_step['step'] if eury_last_step else None,
    }

    # HARMA — resumen real del plan de mantenimiento (vencidos/urgentes, km actual)
    from modules.harma.routes import _serialize_plan as _harma_plan, _get_vehiculo as _harma_vehiculo
    with get_db() as db:
        _hv = _harma_vehiculo(db)
        _hplan = _harma_plan(db, _hv)
    harma_summary = {
        'vencidos':  sum(1 for it in _hplan if it['status'] == 'vencido'),
        'urgentes':  sum(1 for it in _hplan if it['status'] == 'urgente'),
        'km_actual': _hv['km_actual'] if _hv else 0,
    }

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
        'word_of_day':    get_word_of_day(),
        'reflexion':      get_quote_of_day(),
        'reminders':      [dict(r) for r in reminders_rows],
        'ec_balance':     ec_balance,
        'deadlines':      _build_deadlines(_today),
        'suggestion':     _build_suggestion(today_keys),
        'category_hues':  dict(CATEGORY_HUES),
        'eury_today':     eury_today,
        'harma_summary':  harma_summary,
    }


# ── EUDAIMONIA — ruta principal ───────────────────────────────────────────────
@dashboard_bp.route('/')
def index():
    return render_template('base_eudaimonia.html', eudaimonia_data=_build_eudaimonia_data())


def _build_deadlines(today_dt: date) -> list:
    """Recordatorios y tareas GTD con fecha en los próximos 6 días (o vencidos)."""
    horizon = (today_dt + timedelta(days=6)).isoformat()
    raw = []

    with get_db() as db:
        for r in db.execute("""
            SELECT id, description AS label, type AS rem_type,
                   COALESCE(next_date, target_date) AS fecha, 'reminder' AS kind
            FROM reminders
            WHERE is_active=1
              AND COALESCE(next_date, target_date) IS NOT NULL
              AND COALESCE(next_date, target_date) <= ?
            ORDER BY fecha LIMIT 8
        """, (horizon,)).fetchall():
            raw.append(dict(r))

        for r in db.execute("""
            SELECT id, title AS label, NULL AS rem_type,
                   fecha_limite AS fecha, 'task' AS kind
            FROM gtd_tasks
            WHERE (completado IS NULL OR completado=0)
              AND fecha_limite IS NOT NULL AND fecha_limite <> ''
              AND fecha_limite <= ?
            ORDER BY fecha_limite LIMIT 8
        """, (horizon,)).fetchall():
            raw.append(dict(r))

        for r in db.execute("""
            SELECT id,
                   ('vs ' || COALESCE(NULLIF(rival, ''), 'rival por confirmar')
                     || CASE WHEN hora <> '' THEN ' · ' || hora ELSE '' END
                     || CASE WHEN cancha <> '' THEN ' · ' || cancha ELSE '' END) AS label,
                   NULL AS rem_type,
                   fecha AS fecha, 'partido' AS kind
            FROM futbol_partidos
            WHERE estado='programado'
              AND fecha IS NOT NULL
              AND fecha <= ?
            ORDER BY fecha, hora LIMIT 8
        """, (horizon,)).fetchall():
            raw.append(dict(r))

    deadlines = []
    for d in raw:
        try:
            d['type'] = d.pop('kind')
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


@dashboard_bp.route('/api/data')
def api_data():
    return jsonify(_build_eudaimonia_data())


@dashboard_bp.route('/api/db-status')
def api_db_status():
    return jsonify(get_db_status())


@dashboard_bp.route('/api/word/refresh')
def api_word_refresh():
    from data import get_random_word
    return jsonify(get_random_word())


@dashboard_bp.route('/api/quote/refresh')
def api_quote_refresh():
    return jsonify(get_random_quote())
