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
    'eurythmia':      {'Baile', 'Música'},
}

_EU_MODULES_BASE = [
    {'id': 'hegemonikon',    'name': 'HEGEMONIKON',    'concept': 'Bienestar',     'desc': 'Salud · Nutrición · Fútbol · Perfil',  'hue': 45,  'route': '/bienestar/'},
    {'id': 'oikonomia',      'name': 'OIKONOMIA',      'concept': 'Finanzas',      'desc': 'Finanzas · Gastos · Deudas',  'hue': 80,  'route': '/finanzas/'},
    {'id': 'ataraxia',       'name': 'ATARAXIA',       'concept': 'Productividad', 'desc': 'Automatización · Checklist',  'hue': 155, 'route': '/ataraxia/'},
    {'id': 'paideia',        'name': 'PAIDEIA',        'concept': 'Conocimiento',  'desc': 'Aprendizaje · Libros',        'hue': 265, 'route': '/paideia/'},
    {'id': 'cosmopolitismo', 'name': 'COSMOPOLITISMO', 'concept': 'Idiomas',       'desc': 'Idiomas · Culturas',          'hue': 215, 'route': '/idiomas/'},
    {'id': 'logoi',          'name': 'LOGOI',          'concept': 'Programación',  'desc': 'Programación · Lógica',       'hue': 120, 'route': '/actividades/'},
    {'id': 'eurythmia',      'name': 'EURYTHMIA',      'concept': 'Baile',         'desc': 'Baile · Ritmo · Cuerpo',      'hue': 330, 'route': '/eurythmia/'},
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


def _build_next_step(done_keys: set, clf: dict):
    """«Siguiente paso» de Inicio: la actividad pendiente de hoy que más te
    acerca al siguiente rango (clf = engine.get_daily_classification).
      Carbón → el ancla del día («cierra Hierro»).
      Hierro → el touch que además cubre la sesión o el pilar que falta
               («suma 1 touch y cubre la tarde»).
      Oro    → un ancla más («suma 1 ancla para Diamante»).
    Solo actividades elegibles hoy, no hechas y dentro de su ventana horaria.
    None si no hay nada útil (Diamante o todo hecho): se usa _build_suggestion."""
    from modules.actividades import activity_defs as adefs
    from modules.gamification.engine import _sessions_of
    rank = (clf or {}).get('rank')
    if rank not in ('carbon', 'iron', 'gold'):
        return None
    d = today_date()
    now = now_local()
    wd = adefs.weekday_code(d)
    hoy = adefs.ajustar_por_partido(
        [x for x in adefs.get_active_flat().values() if adefs.eligible_today(x, wd, d) and not x.get('hidden')], d)
    pend = [x for x in hoy if x['key'] not in done_keys and _suggestion_in_window(x['key'], now)]
    ses_now = 'morning' if now.hour < 13 else 'afternoon' if now.hour < 19 else 'night'
    ses_lbl = {'morning': 'la mañana', 'afternoon': 'la tarde', 'night': 'la noche', 'any': 'cualquier momento'}

    def ahora(x):
        ss = _sessions_of(x)
        return ses_now in ss or 'any' in ss

    def out(x, why):
        ui = adefs.PILLAR_UI.get(x.get('pillar'), {})
        return {'key': x['key'], 'label': x['label'], 'cat': x.get('cat') or ui.get('name', ''), 'cat_ui': ui.get('cat'),
                'pts': x.get('pts') or 1, 'why': why}

    anclas = sorted((x for x in pend if x['effective_type'] == 'ancla'), key=lambda x: not ahora(x))
    if rank == 'carbon':
        return out(anclas[0], 'cierra Hierro') if anclas else None
    if rank == 'gold':
        return out(anclas[0], 'suma 1 ancla para Diamante') if anclas else None

    # Hierro → Oro: touches diarios; cuánto ayuda cada uno según lo que falta.
    es_touch = lambda x: x['effective_type'] == 'touch' and x.get('cadence', 'daily') == 'daily'
    hechos = [x for x in hoy if x['key'] in done_keys and es_touch(x)]
    ses_hechas = set().union(*(_sessions_of(x) for x in hechos)) if hechos else set()
    pil_hechos = {x['pillar'] for x in hechos}
    crit = {c['key']: c for c in (clf.get('criteria') or [])}
    falta_ses = 'sessions' in crit and not crit['sessions']['ok']
    falta_pil = 'pillars' in crit and not crit['pillars']['ok']
    best, best_score, best_why = None, -1, None
    for x in (t for t in pend if es_touch(t)):
        nuevas = _sessions_of(x) - ses_hechas
        pil_nuevo = x['pillar'] not in pil_hechos
        score = (2 if falta_ses and nuevas else 0) + (2 if falta_pil and pil_nuevo else 0) + (1 if ahora(x) else 0)
        if score > best_score:
            partes = ['suma 1 touch']
            if falta_ses and nuevas:
                ses = ses_now if ses_now in nuevas else sorted(nuevas, key=lambda s: ['morning', 'afternoon', 'night', 'any'].index(s))[0]
                partes.append(f'cubre {ses_lbl[ses]}')
            if falta_pil and pil_nuevo:
                partes.append('suma un pilar nuevo')
            best, best_score, best_why = x, score, ' y '.join(partes) if len(partes) < 3 else f"{partes[0]}, {partes[1]} y {partes[2]}"
    return out(best, best_why) if best else None


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
        'level_subtitle': stats['level_subtitle'],
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
        'suggestion':     _build_next_step(today_keys, stats.get('classification')) or _build_suggestion(today_keys),
        'category_hues':  dict(CATEGORY_HUES),
        'eury_today':     eury_today,
        'harma_summary':  harma_summary,
    }


# ── Dashboard V2 (Design System V2 · pantalla 02) ────────────────────────────
# Categoría de data.ACTIVITIES (la que usa la sugerencia) → data-cat del token
_ACT_CAT_TO_VIRTUE = {
    'Programación': 'logoi', 'Idiomas': 'cosmopolitismo', 'Salud Mental': 'hegemonikon',
    'Salud Física': 'hegemonikon', 'Salud Base': 'hegemonikon', 'Baile': 'eurythmia',
    'Paideia': 'paideia', 'Finanzas': 'oikonomia', 'Orden': 'ataraxia', 'Identidad': 'identidad',
}

# Tono del radar (nivel de urgencia de _build_deadlines → variante de badge)
_RADAR_TONE = {'red': 'danger', 'amber': 'warning', 'yellow': 'info', 'green': ''}


def _build_balance_week() -> dict:
    """«Equilibrio de la semana» (Inicio v2, marcador 5): XP de la semana y de
    hoy por virtud, umbral del 60% y bonus +20%. La regla vive en
    engine.balance_week (la misma que aplica el XP), aquí solo se presenta."""
    from modules.actividades import activity_defs as adefs
    from modules.gamification import engine
    b = engine.balance_week()
    top = max([b['threshold'], *b['week'].values(), 1])
    rows = []
    for pid in adefs.PILLAR_ORDER:
        ui = adefs.PILLAR_UI[pid]
        week, today = b['week'][pid], b['today'][pid]
        rows.append({'id': pid, 'cat': ui['cat'], 'label': ui['name'], 'fn': ui['fn'], 'icon': ui['icon'],
                     'url': ui['url'], 'xp_today': today, 'xp_week': week, 'bonus': pid in b['bonus'],
                     'pct': round(week / top * 100, 1)})
    return {'rows': rows, 'threshold': round(b['threshold'], 1), 'tick': round(b['threshold'] / top * 100, 1),
            'avg': round(b['avg'], 1), 'n_bonus': len(b['bonus']),
            'boost_pct': round((engine.BALANCE_BOOST - 1) * 100), 'ratio_pct': round(engine.BALANCE_RATIO * 100)}


_RANK_ES = {'carbon': 'Carbón', 'iron': 'Hierro', 'gold': 'Oro', 'diamond': 'Diamante'}


def _build_heat_16w() -> dict:
    """«Constancia» (Inicio v2, marcador 8): 16 semanas lunes→domingo hasta la
    semana actual (columna = semana, fila = día), coloreadas por la
    clasificación del día (no por XP) y conteo de días por rango."""
    from modules.gamification.engine import classification_history
    today = today_date()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=15)
    ranks = classification_history(start, today)
    cells, counts = [], {k: 0 for k in _RANK_ES}
    for i in range(16 * 7):
        d = start + timedelta(days=i)
        r = ranks.get(d.isoformat())
        if r:
            counts[r] += 1
        cells.append({'date': d.isoformat(), 'rank': r, 'label': _RANK_ES.get(r, ''),
                      'today': d == today, 'future': d > today})
    return {'cells': cells, 'counts': counts,
            'stats': [{'rank': k, 'label': _RANK_ES[k], 'n': counts[k]} for k in ('diamond', 'gold', 'iron', 'carbon')]}


def _streak_next(streak: int) -> dict:
    """Meta de la racha (Inicio v2, marcador 7): 7 días → +5% XP, 30 → +10%."""
    from modules.gamification.engine import _streak_xp_mult
    streak = max(0, int(streak or 0))
    if streak >= 30:
        return {'days_left': 0, 'next_bonus': None, 'max': True, 'filled': 30,
                'text': 'Bonus máximo · +10%'}
    goal, bonus = (7, 5) if streak < 7 else (30, 10)
    left = goal - streak
    return {'days_left': left, 'next_bonus': bonus, 'max': False, 'filled': streak,
            'bonus_now': round((_streak_xp_mult(streak) - 1) * 100),
            'text': f"{left} día{'s' if left != 1 else ''} más para +{bonus}% XP"}


def _build_dashboard_v2(data: dict) -> dict:
    """Extras de la pantalla V2 sobre _build_eudaimonia_data()."""
    from modules.gamification.engine import LEVEL_THRESHOLDS, get_gamification_stats
    from modules.gamification.badges import get_all_badges
    stats = get_gamification_stats()
    lvl = data['level']
    next_name = LEVEL_THRESHOLDS[lvl][2] if lvl < len(LEVEL_THRESHOLDS) else None
    try:
        perks = sum(1 for b in get_all_badges() if b['perk_active'])
    except Exception:
        perks = 0
    sugg = data.get('suggestion')
    hour = now_local().hour
    return {
        'greeting':    'Buenos días' if 5 <= hour < 12 else 'Buenas tardes' if hour < 19 else 'Buenas noches',
        'next_level':  next_name,
        'streak_bonus': round((stats.get('streak_mult', 1.0) - 1) * 100),
        'perks':       perks,
        'balance':     _build_balance_week(),
        'heat':        _build_heat_16w(),
        'streak_next': _streak_next(data.get('streak', 0)),
        'sugg_cat':    (sugg.get('cat_ui') or _ACT_CAT_TO_VIRTUE.get(sugg['cat'])) if sugg else None,
        'radar_tone':  _RADAR_TONE,
    }


_DIAS_ES = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
_MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio',
             'Agosto','Septiembre','Octubre','Noviembre','Diciembre']


# ── EUDAIMONIA — ruta principal ───────────────────────────────────────────────
@dashboard_bp.route('/')
def index():
    hoy = today_date()
    fecha_larga = f"{_DIAS_ES[hoy.weekday()]} {hoy.day} de {_MESES_ES[hoy.month - 1]}"
    data = _build_eudaimonia_data()
    return render_template(
        'dashboard/index.html',
        data=data,
        v2=_build_dashboard_v2(data),
        fecha_larga=fecha_larga,
        semana_iso=hoy.isocalendar()[1],
    )


_PLANTA_VERBO = {
    'riego': 'Regar {}', 'trasplante': 'Trasplantar {}', 'fertilizar': 'Fertilizar {}',
    'rotar': 'Rotar {}', 'limpiar': 'Limpiar hojas de {}', 'plagas': 'Revisar plagas de {}',
    'tratamiento': 'Tratamiento a {}',
}


def _build_deadlines(today_dt: date) -> list:
    """Recordatorios y tareas GTD con fecha en los próximos 6 días (o vencidos).
    Plantas usa un horizonte más corto (3 días) a propósito — el usuario lo
    pidió así para no ver el riego "venir" con tanta anticipación como el
    resto de los pendientes."""
    horizon = (today_dt + timedelta(days=6)).isoformat()
    plant_horizon = (today_dt + timedelta(days=3)).isoformat()
    raw = []

    with get_db() as db:
        for r in db.execute("""
            SELECT id, description AS label, type AS rem_type, tema,
                   COALESCE(next_date, target_date) AS fecha, 'reminder' AS kind
            FROM reminders
            WHERE is_active=1
              AND COALESCE(next_date, target_date) IS NOT NULL
              AND COALESCE(next_date, target_date) <= ?
            ORDER BY fecha
        """, (horizon,)).fetchall():
            raw.append(dict(r))

        for r in db.execute("""
            SELECT id, title AS label, NULL AS rem_type, importante, priority, cuadrante,
                   fecha_limite AS fecha, 'task' AS kind
            FROM gtd_tasks
            WHERE (completado IS NULL OR completado=0)
              AND fecha_limite IS NOT NULL AND fecha_limite <> ''
              AND fecha_limite <= ?
            ORDER BY fecha_limite
        """, (horizon,)).fetchall():
            raw.append(dict(r))

        for r in db.execute("""
            SELECT id,
                   ('vs ' || COALESCE(NULLIF(rival, ''), 'rival por confirmar')
                     || CASE WHEN hora <> '' THEN ' · ' || hora ELSE '' END) AS label,
                   NULL AS rem_type, cancha,
                   fecha AS fecha, 'partido' AS kind
            FROM futbol_partidos
            WHERE estado='programado'
              AND fecha IS NOT NULL
              AND fecha <= ?
            ORDER BY fecha, hora
        """, (horizon,)).fetchall():
            raw.append(dict(r))

    # Plantas — la agenda la calcula el propio módulo (modules/plantas/
    # routes.py:agenda): mismo estado que /plantas/ (temporada por entorno,
    # riegos pospuestos, fechas reales de trasplante), sin SQL duplicado.
    # Horizonte de 3 días a propósito (ver docstring). Si falla, el
    # Dashboard sigue sin la parte de plantas.
    try:
        from modules.plantas.routes import agenda as _plantas_agenda
        for a in _plantas_agenda(today_dt, 3):
            raw.append({'id': a['planta_id'],
                        'label': _PLANTA_VERBO.get(a['tipo'], '{}').format(a['nombre']),
                        'rem_type': None, 'fecha': a['fecha'], 'kind': f"planta_{a['tipo']}"})
    except Exception:
        pass

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

    # Sin tope por fuente ni total: antes cada consulta traía solo las 8 más
    # viejas y la lista se cortaba a 8 por días, así que unos cuantos vencidos
    # viejos sacaban lo de hoy. Ahora se ordena por urgencia e importancia y
    # la plantilla pliega lo que pase de RADAR_VISIBLES (nunca lo de hoy).
    for d in deadlines:
        d['importancia'] = _importancia(d)
    deadlines.sort(key=_radar_orden)
    visibles = max(RADAR_VISIBLES, sum(1 for d in deadlines if _radar_tramo(d['days']) == 0))
    for i, d in enumerate(deadlines):
        d['extra'] = i >= visibles
    return deadlines


# Filas a la vista en «Pendiente»; el resto queda en «Ver N más».
RADAR_VISIBLES = 8
_PRIORIDAD_ALTA = {'alta', 'high', 'urgente', 'urgent', 'critica', 'crítica'}


def _importancia(d: dict) -> int:
    """0 normal · 1 importante · 2 muy importante. Tareas: «importante» de la
    matriz o prioridad alta. Recordatorios de Finanzas (pagos, cortes): un
    olvido cuesta dinero. Partidos: tienen hora fija."""
    t = d.get('type')
    if t == 'task':
        if d.get('importante'):
            return 2
        return 1 if str(d.get('priority') or '').lower() in _PRIORIDAD_ALTA else 0
    if t == 'reminder':
        return 1 if d.get('tema') == 'finanzas' else 0
    if t == 'partido':
        return 1
    return 0


def _radar_tramo(days: int) -> int:
    """0 hoy o vencido en la última semana · 1 mañana/pasado ·
    2 vencido hace más de una semana · 3 el resto de la semana."""
    if -7 <= days <= 0:
        return 0
    if days < -7:
        return 2
    return 1 if days <= 2 else 3


def _radar_orden(d: dict):
    # Dentro del tramo: lo importante primero; luego lo más cercano a hoy
    # (hoy antes que ayer, ayer antes que hace 5 días).
    return (_radar_tramo(d['days']), -d['importancia'], abs(d['days']))


# ── Redirecciones de compatibilidad ──────────────────────────────────────────
@dashboard_bp.route('/classic')
@dashboard_bp.route('/v2')
@dashboard_bp.route('/tw')
@dashboard_bp.route('/logoi')
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
