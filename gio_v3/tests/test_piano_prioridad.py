"""
test_piano_prioridad.py — prioridad piano 2026-11-16 → 2027-02-16 (docs/piano_plan.md).

Migración piano_prioridad_2026_11: piano en Eurythmia (Flowkey touch 2 pts,
Pianoforall ancla lun/mié/vie con los pts/EC del ancla de CCNA, grabar pieza
ocasional con los pts del bonus Gol), ancla de baile jue/sáb que completa la
sesión de Eurythmia, Logoi en pausa sin perder historial y recordatorio de
reactivación. Los hábitos de piano se marcan a mano en Acta (no son baile).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.actividades.activity_defs as adefs
from utils import today_str

DIAS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')


def _def(key):
    with database.get_db() as db:
        r = db.execute("SELECT * FROM activity_defs WHERE key=?", (key,)).fetchone()
    return dict(r) if r else None


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def test_habitos_de_piano_y_baile(test_db):
    fk, pf, gp, bl = (_def(k) for k in ('piano_flowkey', 'piano_pianoforall', 'piano_grabar_libro', 'ancla_baile'))
    ccna, gol = _def('ancla_ccna_prog'), _def('gol')
    assert (fk['pillar'], fk['type'], fk['session'], fk['pts'], fk['days_of_week'], fk['active']) == ('eury', 'touch', 'night', 2, None, 1)
    assert (pf['pillar'], pf['type'], pf['session'], pf['days_of_week']) == ('eury', 'ancla', 'afternoon', 'mon,wed,fri')
    assert (pf['pts'], pf['ec']) == (ccna['pts'], ccna['ec'])                     # mismos pts/EC que CCNA
    assert (gp['type'], gp['pts'], gp['ec']) == ('ocasional', gol['pts'], gol['ec'])  # mismos que el bonus Gol
    assert (bl['pillar'], bl['type'], bl['days_of_week'], bl['pts'], bl['ec']) == ('eury', 'ancla', 'thu,sat', 0, 0)
    assert all(d['cat'] == 'Baile' for d in (fk, pf, gp, bl))


def test_logoi_en_pausa_sin_borrar(test_db):
    for k in ('ancla_ccna_prog', 'sololearn', 'leer_prog', 'python100', 'github'):
        d = _def(k)
        assert d is not None and d['active'] == 0, k                               # existe (historial) pero inactivo
    assert _def('resolver_codigo')['type'] == 'ocasional' and _def('resolver_codigo')['active'] == 1


def _recordatorios():
    with database.get_db() as db:
        return [tuple(x) for x in db.execute(
            "SELECT type, target_date, is_active, tema FROM reminders WHERE description LIKE 'Reactivar ancla CCNA%'")]


def test_recordatorio_de_reactivacion_solo_con_datos_del_usuario(test_db, monkeypatch):
    assert _recordatorios() == []                       # tests y ?demo=1 no lo siembran
    monkeypatch.setattr(database, 'SEMBRAR_DATOS_USUARIO', True)
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='piano_prioridad_2026_11'")
        db.commit()
    database.init_db()
    assert _recordatorios() == [('unico', '2027-02-16', 1, 'otros')]
    database.init_db()                                  # idempotente
    assert len(_recordatorios()) == 1


def test_calendario_de_anclas(test_db):
    # Una semana normal (sin fechas puntuales como el autodiagnóstico C1)
    from datetime import date, timedelta
    lunes = date(2026, 11, 16)
    act = [d for d in adefs.get_active_flat().values() if d['type'] == 'ancla' and d['key'] != 'gym']
    cal = {dia: sorted(d['key'] for d in act if adefs.eligible_today(d, dia, lunes + timedelta(days=i)))
           for i, dia in enumerate(DIAS)}
    # Plan C1 de idiomas (idiomas_c1_plan_2026_11): inglés y francés se parten
    # en sesión A/B (mismos días) y el sábado suma el repaso de idiomas.
    assert cal == {
        'mon': ['ancla_ingles', 'piano_pianoforall'],
        'tue': ['ancla_frances', 'ancla_leer_psico'],
        'wed': ['partido_futbol', 'piano_pianoforall'],
        'thu': ['ancla_baile', 'ancla_ingles_b'],
        'fri': ['ancla_frances_b', 'piano_pianoforall'],
        'sat': ['ancla_baile', 'ancla_repaso_idiomas'],
        'sun': ['ancla_leer_psico'],
    }


def test_migracion_idempotente(test_db):
    database.init_db()
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM activity_defs WHERE key LIKE 'piano_%'").fetchone()[0] == 3


def test_piano_se_marca_a_mano_y_no_es_baile():
    assert not adefs.es_proxy_eurythmia({'pillar': 'eury', 'key': 'piano_pianoforall'})
    assert not adefs.es_proxy_eurythmia({'pillar': 'eury', 'key': 'piano_flowkey'})
    assert not adefs.es_proxy_eurythmia({'pillar': 'eury', 'key': 'lenguaje_corporal'})
    assert adefs.es_proxy_eurythmia({'pillar': 'eury', 'key': 'ancla_baile'})
    assert not adefs.es_proxy_eurythmia({'pillar': 'hege', 'key': 'gym'})


def test_marcar_piano_en_acta_da_sus_pts(client):
    r = client.post('/actividades/api/activity/log', json={'key': 'piano_flowkey'}).get_json()
    assert r['action'] == 'added' and r['pts'] == 2


def test_sesion_de_baile_completa_el_ancla_con_0_pts(client):
    hoy = adefs.weekday_code()
    with database.get_db() as db:          # el ancla de baile toca hoy, sea el día que sea
        db.execute("UPDATE activity_defs SET days_of_week=? WHERE key='ancla_baile'", (hoy,))
        db.execute("UPDATE activity_defs SET days_of_week=? WHERE key='piano_pianoforall'", (hoy,))
        db.commit()
    import modules.gamification.engine as engine
    antes = engine.get_daily_classification()['anchors_done']
    assert client.post('/eurythmia/api/session', json={'min': 30, 'flow': 3}).status_code == 200
    with database.get_db() as db:
        logs = {r['activity_key']: r['pts'] for r in db.execute("SELECT activity_key, pts FROM activity_logs WHERE date=?", (today_str(),))}
    assert logs.get('ancla_baile') == 0                                   # sin XP doble: lo paga la sesión
    assert 'piano_pianoforall' not in logs and 'piano_flowkey' not in logs   # el baile no marca el piano
    assert engine.get_daily_classification()['anchors_done'] == antes + 1
    from modules.quick import badges
    with database.get_db() as db:
        assert badges(db)['acta'] == len([1 for d in adefs.get_active_flat().values()
                                           if d['type'] == 'ancla' and adefs.eligible_today(d) and d['key'] != 'ancla_baile'])
    # una 2ª sesión el mismo día no duplica el registro
    client.post('/eurythmia/api/session', json={'min': 20, 'flow': 3})
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM activity_logs WHERE activity_key='ancla_baile' AND date=?", (today_str(),)).fetchone()[0] == 1


def test_acta_pinta_piano_como_boton_y_baile_como_enlace(client):
    hoy = adefs.weekday_code()
    with database.get_db() as db:
        db.execute("UPDATE activity_defs SET days_of_week=? WHERE key IN ('ancla_baile','piano_pianoforall')", (hoy,))
        db.commit()
    html = client.get('/actividades/').get_data(as_text=True)
    i = html.index('data-key="piano_pianoforall"')
    assert 'js-act' in html[i:i + 1500] and 'Registrar en Eurythmia' not in html[i:i + 1500].split('acta-rm')[0]
    j = html.index('class="acta-item acta-anchor is-ancla" data-key="ancla_baile"')
    bloque = html[j:j + 1500]
    assert 'href="/eurythmia/?from=acta"' in bloque and 'XP de la sesión' in bloque
