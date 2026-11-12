"""
test_logros.py — handoff Logros v2 (/logros).

Sprint 1: ETA de nivel a tu ritmo, progreso por condición de insignias y
logros (el mismo que usa el motor para desbloquear), «Cerca de desbloquear»
y constancia por rango.
Sprint 2: encabezado con pestañas Colección / Historial y héroe de nivel.
Sprint 3: colección compacta, perks en 2 ranuras, constancia por rango.
Sprint 4: pestaña Historial (desglose por fuente + semanas) y /gtd/points.
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.gamification.routes as gr
import modules.gamification.engine as engine
from modules.gamification.badges import BADGE_DEFS, progress_of
from modules.gamification.achievements import ACHIEVEMENT_DEFS

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _xp(amount, days_ago=0, source='activity', desc='Actividad: gym'):
    d = (gr.today_date() - datetime.timedelta(days=days_ago)).isoformat()
    with database.get_db() as db:
        db.execute("INSERT INTO xp_ledger (amount,source,description,multiplier,date,created_at) VALUES (?,?,?,1,?,'x')",
                   (amount, source, desc, d))
        db.commit()


def _get(client, q=''):
    return client.get('/logros' + q).get_data(as_text=True)


def _src(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_eta_none_sin_datos(test_db):
    eta = gr.eta_nivel(0)
    assert eta == {'xp_dia_30': 0, 'dias_siguiente': None, 'dias_meta': None}


def test_eta_a_tu_ritmo(test_db):
    for i in range(30):
        _xp(20, days_ago=i)                       # 600 XP en 30 días → 20 XP/día
    _xp(500, days_ago=40)                         # fuera de la ventana: no cuenta para el ritmo
    eta = gr.eta_nivel(1100)                      # nivel 3 (900) → faltan 700 para 1,800
    assert eta['xp_dia_30'] == 20.0
    assert eta['dias_siguiente'] == 35            # ceil(700 / 20)
    assert eta['dias_meta'] == 270                # ceil((6500 - 1100) / 20)


def test_eta_nivel_maximo(test_db):
    _xp(30)
    assert gr.eta_nivel(7000)['dias_siguiente'] is None
    assert gr.eta_nivel(7000)['dias_meta'] is None


STATS = [
    {}, {'prog_count': 3, 'salud_base_7d': 7, 'redes_7': 1, 'diamond_week': 3, 'github_count': 0,
         'conv_month': 5, 'gol_month': 2, 'streak': 30, 'current_level': 6, 'total_diamond_days': 5,
         'weekend_complete': 1},
    {'prog_count': 9, 'diamond_week': 2, 'github_count': 10, 'conv_month': 4, 'current_level': 8,
     'streak': 21, 'gol_month': 3, 'redes_7': 3},
]


@pytest.mark.parametrize('st', STATS)
def test_progreso_de_insignias_coincide_con_el_motor(st):
    for key, defn in BADGE_DEFS.items():
        p = progress_of(defn, st)
        assert p is not None, key
        have, need, _ = p
        assert defn['condition'](st) == (have >= need), (key, st, p)


def test_progreso_de_logros_coincide_con_el_motor():
    base = {'total_activity_count': 0, 'xp_week': 0, 'xp_week_acts': 0, 'streak': 0, 'prog_count': 0,
            'all_cats_ever': set(), 'total_coins': 0, 'total_xp': 0, 'cats_done_today': set(),
            'had_perfect_day': False, 'current_level': 1}
    for st in (base, {**base, 'total_activity_count': 3, 'streak': 12, 'prog_count': 50, 'total_xp': 3000,
                      'all_cats_ever': set(range(10)), 'total_coins': 999, 'xp_week_acts': 200, 'current_level': 5}):
        for key, defn in ACHIEVEMENT_DEFS.items():
            p = progress_of(defn, st)
            if p is None:
                continue
            assert defn['condition'](st) == (p[0] >= p[1]), (key, p)


def test_combo_compuesto():
    p = progress_of(BADGE_DEFS['stoic_commander'], {'streak': 12, 'current_level': 4})
    assert p == (49, 100, 'racha 12/30 · nivel 4/7')            # (40% + 57%) / 2
    assert progress_of(BADGE_DEFS['stoic_commander'], {'current_level': 4})[0] == 0   # el nivel solo no es avance
    assert gr.prog_txt(p) == '49%' and gr.prog_txt((41, 50, 'sesiones')) == '41/50'


def _b(name, prog, tier='silver', unlocked=False):
    return {'name': name, 'rarity': gr.RARITY_OF[tier], 'tier_label': tier, 'icon_lucide': 'x',
            'perk': 'perk de ' + name, 'progress': prog, 'unlocked': unlocked}


def test_near_unlock_top3_por_avance():
    badges = [_b('A', (41, 50, 'sesiones')), _b('B', (1, 10, 'x')), _b('C', (0, 5, 'x')),
              _b('D', (4, 7, 'días')), _b('E', (2, 3, 'goles')), _b('F', None)]
    ach = [{'name': 'Oculto', 'progress': None, 'xp': 10, 'coins': 0, 'icon_lucide': 'x'},
           {'name': 'Primer Paso', 'progress': (0, 1, 'actividades'), 'xp': 5, 'coins': 10, 'icon_lucide': 'x'}]
    near = gr.near_unlock(badges, ach)
    assert [n['name'] for n in near] == ['A', 'E', 'D']          # 82 %, 67 %, 57 %
    assert near[0]['pct'] == 82 and near[0]['prog'] == '41/50' and near[0]['perk'] == 'perk de A'
    assert gr.near_unlock([_b('C', (0, 5, 'x'))], []) == []      # have = 0 no cuenta


def test_coleccion_progreso_real(test_db):
    with database.get_db() as db:
        for i in range(3):
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('conversacion', ?, 1)",
                       (gr.today_date().isoformat(),))
        db.commit()
    badges, ach = gr.coleccion_con_progreso()
    pol = next(b for b in badges if b['key'] == 'diplomatico')
    assert pol['progress'][2].startswith('conversaciones 3/5')
    oculto = next(a for a in ach if a['key'] == 'racha_30')
    assert oculto['oculto'] and oculto['progress'] is None        # lo oculto no revela su progreso


def test_constancia_por_rango(test_db, monkeypatch):
    hoy = gr.today_date()
    ranks = {(hoy - datetime.timedelta(days=1)).isoformat(): 'gold',
             (hoy - datetime.timedelta(days=2)).isoformat(): 'diamond',
             (hoy - datetime.timedelta(days=3)).isoformat(): 'carbon'}
    with database.get_db() as db:
        for d in ranks:
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('gym', ?, 3)", (d,))
        db.commit()
    monkeypatch.setattr(engine, 'get_daily_classification', lambda d=None: {'rank': ranks.get(d, 'carbon')})
    heat, counts = gr.constancia()
    assert len(heat) == 91
    assert counts == {'carbon': 1, 'hierro': 0, 'oro': 1, 'diamante': 1}
    by = {c['date']: c['rank'] for c in heat}
    assert by[(hoy - datetime.timedelta(days=2)).isoformat()] == 'diamante'
    assert by[(hoy - datetime.timedelta(days=5)).isoformat()] is None    # sin actividad


# ── Sprint 2 ─────────────────────────────────────────────────────────────────

def test_encabezado_y_heroe(client):
    for i in range(10):
        _xp(30, days_ago=i)                                         # 300 XP → Efebo; 30 XP/día... /30 = 10
    html = _get(client)
    hd = html.split('<header class="eu-page-hd lg-hd">', 1)[1].split('</header>', 1)[0]   # ui.page_head (Navegación)
    assert 'Nivel 2 · 600 XP para el 3' in hd and 'role="tablist"' in hd and '<h1 class="t-page">Logros</h1>' in hd
    assert 'href="/logros?tab=historial"' in hd and 'aria-selected="true">Colección' in hd
    for fuera in ('lg-stats', 'Días diamante', '>Los diez niveles<', 'lg-levels'):
        assert fuera not in html, fuera
    hero = html.split('<section class="lg-hero"', 1)[1].split('</section>', 1)[0]
    assert 'Nivel 2 de 10' in hero and 'Efebo' in hero and 'eu-tower' in hero
    assert '600 XP</b> para Asquetés' in hero                     # 900 - 300
    assert '≈ 60 días a tu ritmo' in hero and '10.0 XP/día (30 d)' in hero
    assert hero.count('class="lg-path-seg') == 10 and 'aria-current="step"' in hero
    assert 'Siguiente · 3' in hero and 'Meta · 10' in hero and '≈ 20.4 meses' in hero
    assert not os.path.exists(os.path.join(BASE, 'templates/gamification/_levels.html'))


def test_heroe_nivel_maximo(client):
    _xp(7000)
    hero = _get(client).split('<section class="lg-hero"', 1)[1].split('</section>', 1)[0]
    assert 'Nivel máximo' in hero and 'a tu ritmo' not in hero and 'Nivel 10 de 10' in hero


# ── Sprint 3 ─────────────────────────────────────────────────────────────────

def test_coleccion_compacta_y_perks(client):
    html = _get(client)
    assert 'Cerca de desbloquear' not in html                       # sin progreso, la sección no aparece
    coll = html.split('id="lg-coll-t"', 1)[1]
    assert 'data-status="earned"' in coll and 'data-sort' not in html   # sin segmentado Rareza/Reciente
    assert coll.count('class="lg-item lg-item--badge') == len(BADGE_DEFS)
    assert coll.count('class="lg-item lg-item--ach') == len(ACHIEVEMENT_DEFS)
    assert 'Se revela al conseguirlo' in coll
    perks = html.split('id="lg-perks-t"', 1)[1].split('</section>', 1)[0]
    assert '0 / 2 ranuras' in perks and perks.count('class="lg-slot"') == 2
    assert 'Si encadenas más de 3 perks sin pausa, pierdes 10% de XP durante 2 días.' in perks
    assert 'máx. 2' not in html
    heat = html.split('id="lg-heat-t"', 1)[1].split('</section>', 1)[0]
    assert 'Constancia · 13 semanas' in html and heat.count('class="lg-rank-c"') == 4
    assert 'Racha y clasificación de hoy viven en' in heat
    for fuera in ('lg-today', 'XP hoy', 'Clasificación</h2>'):
        assert fuera not in html, fuera
    assert not os.path.exists(os.path.join(BASE, 'templates/gamification/_today.html'))
    assert 'lg-today' not in _src('static/css/logros.css') and 'lg-today' not in _src('static/js/logros.js')


def test_cerca_de_desbloquear_en_pagina(client):
    with database.get_db() as db:
        for _ in range(2):
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('conversacion', ?, 1)",
                       (gr.today_date().isoformat(),))
        db.commit()
    near = _get(client).split('id="lg-near-t"', 1)[1].split('</section>', 1)[0]
    assert 'Políglota Activo' in near and '2/3' in near and '+3 EC en actividades de Idiomas' in near


def test_ganadas_primero_y_perk_activo(client):
    hoy = gr.today_date()
    with database.get_db() as db:
        db.execute("INSERT INTO badges (key, tier, unlocked_at, perks_active_until, notified, created_at) "
                   "VALUES ('poliglota_activo','silver',?,?,1,'x')", (hoy.isoformat(), (hoy + datetime.timedelta(days=3)).isoformat()))
        db.commit()
    html = _get(client)
    coll = html.split('id="lg-coll-t"', 1)[1]
    first = coll.split('class="lg-item lg-item--badge', 2)[1]
    assert 'Políglota Activo' in first and 'Perk activo' in first and '+3 EC en actividades de Idiomas' in first
    perks = html.split('id="lg-perks-t"', 1)[1].split('</section>', 1)[0]
    assert '1 / 2 ranuras' in perks and perks.count('class="lg-slot"') == 1
    assert 'lg-perk-d is-low">4 d' in perks


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def test_fuente_xp():
    assert gr.fuente_xp('task', 'Tarea GTD #3') == 'Praxis'
    assert gr.fuente_xp('bonus', 'Bonus diario GTD (3 tareas)') == 'Praxis'
    assert gr.fuente_xp('achievement', 'Logro: Primer Paso') == 'Logros'
    assert gr.fuente_xp('activity', 'Actividad: paideia_libro_4') == 'Paideia'
    assert gr.fuente_xp('activity', 'Actividad: revision_semanal') == 'Ataraxia'
    assert gr.fuente_xp('bonus', 'Combo: Domingo Completo') == 'Ataraxia'
    assert gr.fuente_xp('bonus', 'Bonus: Día Perfecto') == 'Acta'
    assert gr.fuente_xp('rutina', 'Rutina: x') == 'Acta'
    assert gr.fuente_xp('penalty', 'Perk encadenado') == 'Sistema'


def test_historial_por_fuente(client):
    _xp(6, desc='Actividad: gym')
    _xp(2, source='task', desc='Tarea GTD #1')
    _xp(-2, days_ago=1, source='penalty', desc='Perk encadenado (−10%)')
    _xp(10, days_ago=100)                                           # fuera de los 90 días
    html = _get(client, '?tab=historial&fuente=Praxis')
    assert 'aria-selected="true">Historial' in html and 'id="lg-coll-t"' not in html
    log = html.split('id="lg-log-t"', 1)[1]
    assert 'data-fuente="Praxis"' in html
    assert 'data-src="Praxis" aria-pressed="true">Praxis <span class="num fg-3">1' in log
    assert 'data-src="" aria-pressed="false">Todas <span class="num fg-3">3' in log
    assert 'data-src="Paideia"' not in log                          # solo fuentes con entradas
    assert 'class="num lg-amt neg">-2' in log and 'Hoy' in log and 'Ayer' in log
    assert 'Cargar más' in log
    assert 'href="/logros/semanas"' in html and 'Todas las semanas y métricas →' in html
    assert 'data-fuente=""' in _get(client, '?tab=historial&fuente=Nada')


def test_historial_sin_desglose_en_coleccion(client):
    html = _get(client)
    assert '<details' not in html and 'Historial de semanas' not in html
    assert not os.path.exists(os.path.join(BASE, 'templates/gamification/_xplog.html'))


def test_semanas_con_xp_total(client, monkeypatch):
    import modules.ataraxia.routes as ar
    client.post('/ataraxia/api/revision', json={'horas_sueno': 7})
    sem = ar._semana_dias(ar.get_semana_id())
    with database.get_db() as db:
        db.execute("INSERT INTO xp_ledger (amount,source,description,multiplier,date,created_at) VALUES (12,'activity','x',1,?,'x')", (sem[0],))
        db.commit()
    s = gr.semanas_recientes()
    assert s[0]['actual'] and s[0]['xp_total'] >= 12
    wk = _get(client, '?tab=historial').split('id="lg-wk-t"', 1)[1]
    assert 'lg-wk-row is-now' in wk and '· esta' in wk


def test_points_redirige_al_historial_de_praxis(client):
    r = client.get('/gtd/points')
    assert r.headers['Location'].endswith('/logros?tab=historial&fuente=Praxis')


def test_desglose_con_nombre_de_actividad(test_db):
    from modules.actividades import activity_defs as adefs
    a = adefs.create('Leer filosofía', 'paideia', session='night')
    _xp(1, desc='Actividad: ' + a['key'])
    _xp(1, desc='Actividad: no_existe')
    grupos, _, _ = gr.desglose_xp()
    descs = [r['desc'] for r in grupos[0]['rows']]
    assert 'Leer filosofía' in descs and 'Actividad: no_existe' in descs
