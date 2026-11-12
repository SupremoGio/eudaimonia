"""
test_eurythmia.py — handoff Eurythmia v2 (/eurythmia/).

Sprint 1: last_practiced (migración + backfill), sugerencias por espaciado,
dominio por sesión real, semana, ETA de nivel, próximo bono de racha y
duración habitual. Sprint 2–3: franja, «Sesión de hoy» con cierre en la
tarjeta, repertorio y lateral, vistas completas. Sprint 4: volver a Acta.
"""
import sys, os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date
from modules.eurythmia import routes as er

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOY = today_date()


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


def _d(n):
    return (HOY - timedelta(days=n)).isoformat()


def _rep(**pasos):
    """pasos: step_key=(nombre, kind, mastery, hace_dias|None)"""
    with database.get_db() as db:
        db.execute("DELETE FROM eury_repertoire")
        for k, (n, kind, m, d) in pasos.items():
            db.execute("INSERT INTO eury_repertoire (kind, step_key, name, mastery, reps, last_practiced, created_at) VALUES (?,?,?,?,0,?,'x')",
                       (kind, k, n, m, _d(d) if d is not None else None))
        db.commit()


def _ses(hace, minutes=30, step='', flow=3):
    with database.get_db() as db:
        db.execute("INSERT INTO eury_sessions (date, min, split_diso, split_paso, split_improv, step, flow, improv_note, xp, grabado, created_at) VALUES (?,?,10,15,5,?,?,'',0,0,'x')",
                   (_d(hace), minutes, step, flow))
        db.commit()


def _paso(k):
    with database.get_db() as db:
        return dict(db.execute("SELECT * FROM eury_repertoire WHERE step_key=?", (k,)).fetchone())


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_sugerencias_por_espaciado(test_db):
    _rep(enchufla_doble=('Enchufla doble', 'pareja', 42, 9),     # 9 × 58 = 522
         vacilala=('Vacílala', 'pareja', 58, 12),                 # 12 × 42 = 504
         sombrero=('Sombrero', 'pareja', 35, 4),                  # 4 × 65 = 260
         setenta=('Setenta', 'pareja', 20, 21),                   # 21 × 80 = 1680
         dile_que_no=('Dile que no', 'pareja', 92, 2),            # automatizado → fuera
         guapea=('Guapea', 'libres', 95, 1))
    s = er.sugerencias(er._repertoire())
    assert [x['step_key'] for x in s] == ['setenta', 'enchufla_doble', 'vacilala']
    assert s[0] == {'step_key': 'setenta', 'nombre': 'Setenta', 'kind': 'pareja', 'mastery': 20, 'dias': 21}


def test_paso_sin_last_practiced_cuenta_30_dias(test_db):
    _rep(a=('A', 'pareja', 50, 20),          # 20 × 50 = 1000
         b=('B', 'libres', 50, None))        # 30 × 50 = 1500
    s = er.sugerencias(er._repertoire())
    assert [x['step_key'] for x in s] == ['b', 'a'] and s[0]['dias'] is None


def test_dominio_sube_con_la_sesion_y_tope_100(client):
    _rep(enchufla=('Enchufla', 'pareja', 98, 6), sombrero=('Sombrero', 'pareja', 35, 4))
    d = client.post('/eurythmia/api/session', json={'min': 30, 'flow': 4, 'step': 'Sombrero', 'step_key': 'sombrero'}).get_json()
    assert d['step_mastery_nuevo'] == 39 and d['ec_total'] == 1
    p = _paso('sombrero')
    assert (p['mastery'], p['reps'], p['last_practiced']) == (39, 10, HOY.isoformat())
    d = client.post('/eurythmia/api/session', json={'min': 30, 'flow': 5, 'step': 'enchufla'}).get_json()
    assert d['step_mastery_nuevo'] == 100 and _paso('enchufla')['mastery'] == 100


def test_sesion_conserva_formulas(client):
    _rep()
    d = client.post('/eurythmia/api/session', json={'min': 45, 'flow': 5, 'step': 'libre', 'grabado': True}).get_json()
    assert d['xp'] == 45 + 5 * 4 and d['step_mastery_nuevo'] is None
    assert d['ec_total'] == er._session_ec(45, 5) + er._GRABADO_EC
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) c FROM activity_logs WHERE activity_key='eurythmia_session'").fetchone()['c'] == 1


def test_preview_coincide_con_backend(client):
    r = client.get('/eurythmia/api/preview-reward?min=45&flow=5&grabado=1').get_json()
    assert r == {'xp': 45 + 20 + er._GRABADO_XP, 'ec': er._session_ec(45, 5) + er._GRABADO_EC}
    js = open(os.path.join(BASE, 'static/js/eurythmia.js'), encoding='utf-8').read()
    assert 'min + flow * 4' in js and "(flow >= 5 ? 2 : flow >= 3 ? 1 : 0) + (min >= 45 ? 1 : 0)" in js


def test_racha_bono():
    assert er.racha_bono(0) == {'dias': 3, 'ec': 2}
    assert er.racha_bono(5) == {'dias': 7, 'ec': 3}
    assert er.racha_bono(29) == {'dias': 30, 'ec': 8}
    assert er.racha_bono(30) is None


def test_semana_eta_y_duracion_habitual(test_db):
    _rep()
    lunes = HOY - timedelta(days=HOY.weekday())
    for n, m in ((0, 30), (1, 45), (2, 30), (20, 60)):
        _ses(n, m)
    st = er._state()
    en_semana = [n for n in (0, 1, 2) if HOY - timedelta(days=n) >= lunes]
    assert st['semana']['sesiones'] == len(en_semana) and st['semana']['meta'] == 4
    assert st['duracion_habitual'] == 30
    horas_sem = (30 + 45 + 30 + 60) / 60 / 4
    assert st['nivel_eta_semanas'] == round(st['level']['hours_to_next'] / horas_sem, 1)


def test_sin_sesiones(test_db):
    st = er._state()
    assert st['duracion_habitual'] == 30 and st['nivel_eta_semanas'] is None and st['semana']['min'] == 0


def test_backfill_y_migracion_idempotente(test_db):
    _rep(sombrero=('Sombrero', 'pareja', 35, None), vacilala=('Vacílala', 'pareja', 58, None))
    _ses(5, step='Sombrero')
    _ses(3, step='sombrero')
    _ses(8, step='VACILALA')
    with database.get_db() as db:
        er.backfill_last_practiced(db)
        er.backfill_last_practiced(db)
    assert _paso('sombrero')['last_practiced'] == _d(3) and _paso('vacilala')['last_practiced'] == _d(8)
    database.init_db()
    database.init_db()
    with database.get_db() as db:
        cols = [r['name'] for r in db.execute("PRAGMA table_info(eury_repertoire)")]
    assert cols.count('last_practiced') == 1


# ── Sprint 2–3 ───────────────────────────────────────────────────────────────

def test_pagina_principal(client):
    html = client.get('/eurythmia/').get_data(as_text=True)
    for fuera in ('ey-subtabs', 'ey-lead', 'role="tablist"', 'id="m-close"', 'ey-grabado-chip', 'data-drill', 'ey-total-range'):
        assert fuera not in html, fuera
    for dentro in ('id="ey-strip"', 'Sesión de hoy', 'ey-durs', 'Disociación → un paso con foco → improvisa con lo que sabes.',
                   'Otro paso…', 'Empezar ·', 'id="f-close"', '¿Cómo se sintió?', 'Grabé esta práctica · +3 XP',
                   'Repertorio', 'Últimas sesiones', '?vista=bitacora', '?vista=musica', 'Por qué funciona · 4', 'id="m-run"'):
        assert dentro in html, dentro
    assert '<details class="ey-box ey-box--sunken ey-sci">' in html                 # plegado


def test_vistas_completas(client):
    mus = client.get('/eurythmia/?vista=musica').get_data(as_text=True)
    assert 'id="mu-list"' in mus and 'Sesión de hoy' not in mus and '← Sesión' in mus
    assert 'id="ey-log-list"' in client.get('/eurythmia/?vista=bitacora').get_data(as_text=True)
    assert 'ey-ladder' in client.get('/eurythmia/?vista=progreso').get_data(as_text=True)


def test_album_sigue_dando_xp(client):
    with database.get_db() as db:
        aid = db.execute("SELECT id FROM eury_albums ORDER BY rank LIMIT 1").fetchone()['id']
    d = client.post(f'/eurythmia/api/album/{aid}', json={'escuchado': True}).get_json()
    assert d['ok'] and d['gam'] is not None


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def test_volver_a_acta(client):
    html = client.get('/eurythmia/?from=acta').get_data(as_text=True)
    assert 'data-from="acta"' in html and '← Acta Diurna' in html and 'Volver a Acta' in html
    assert 'href="/actividades/" aria-label="Volver"' in html
    assert 'Volver a Acta' not in client.get('/eurythmia/').get_data(as_text=True)
    for f in ('templates/actividades/_item.html', 'templates/actividades/_anchors.html'):
        t = open(os.path.join(BASE, f), encoding='utf-8').read()
        assert '/eurythmia/?from=acta' in t and 'href="/eurythmia/"' not in t
