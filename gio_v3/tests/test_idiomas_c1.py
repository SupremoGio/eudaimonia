"""
test_idiomas_c1.py — plan C1 de inglés y francés (docs/idiomas_c1_plan.md).

Migración idiomas_c1_plan_2026_11: las anclas de inglés y francés se parten
en sesión A (input) y B (output con corrección) SIN cambiar sus días; repaso
semanal el sábado; Anki y lectura opcionales; 15 hitos one_time; fuera el
test de certificación; checkpoints como recordatorios (solo con datos del
usuario). Acta pinta «Ocasionales y hitos» (antes los ocasionales no salían).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_str


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


def test_anclas_partidas_en_a_y_b_con_los_mismos_dias(test_db):
    en_a, en_b, fr_a, fr_b = (_def(k) for k in ('ancla_ingles', 'ancla_ingles_b', 'ancla_frances', 'ancla_frances_b'))
    assert (en_a['days_of_week'], en_b['days_of_week']) == ('mon', 'thu')     # los días de siempre: lun/jue
    assert (fr_a['days_of_week'], fr_b['days_of_week']) == ('tue', 'fri')     # mar/vie
    assert en_a['label'].startswith('Inglés · Sesión A') and en_b['label'].startswith('Inglés · Sesión B')
    assert fr_a['label'].startswith('Francés · Sesión A') and fr_b['label'].startswith('Francés · Sesión B')
    for a, b in ((en_a, en_b), (fr_a, fr_b)):
        assert (b['session'], b['type'], b['pillar'], b['ec']) == (a['session'], 'ancla', 'cosmo', a['ec'])
        assert b['pts'] == a['pts'] + 1          # ajuste v2: la sesión B vale 7 (absorbe conversación y writing)


def test_repaso_opcionales_y_certificacion(test_db):
    rep, en = _def('ancla_repaso_idiomas'), _def('ancla_ingles')
    assert (rep['type'], rep['days_of_week'], rep['session'], rep['pts'], rep['ec']) == ('ancla', 'sat', 'afternoon', en['pts'], en['ec'])
    # ajuste v2: Anki diario; escucha y lectura separadas por idioma (las mixtas, fuera)
    assert (_def('anki_idiomas')['days_of_week'], _def('anki_idiomas')['pts']) == (None, 2)
    assert _def('lectura_idiomas')['active'] == 0 and _def('podcast_idiomas')['active'] == 0
    assert _def('test_cert')['active'] == 0


def test_hitos_one_time(test_db):
    with database.get_db() as db:
        hitos = [dict(r) for r in db.execute("SELECT * FROM activity_defs WHERE key LIKE 'hito_%'")]
    assert len(hitos) == 15
    assert all(h['type'] == 'ocasional' and h['one_time'] == 1 and h['active'] == 1 and h['pillar'] == 'cosmo' for h in hitos)
    assert {h['key']: h['pts'] for h in hitos}['hito_en_c1'] == 100


def test_marcar_un_hito_da_su_xp_y_lo_retira(client):
    r = client.post('/actividades/api/activity/log', json={'key': 'hito_fr_litote'}).get_json()
    assert r['action'] == 'added' and r['pts'] == 20 and r['one_time'] is True
    assert _def('hito_fr_litote')['active'] == 0


def test_checkpoints_solo_con_datos_del_usuario(test_db, monkeypatch):
    def _n():
        with database.get_db() as db:
            return [r[0] for r in db.execute("SELECT target_date FROM reminders WHERE description LIKE '%checkpoint%' "
                                             "OR description LIKE 'Idiomas · línea base%' ORDER BY target_date")]
    assert _n() == []
    monkeypatch.setattr(database, 'SEMBRAR_DATOS_USUARIO', True)
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='idiomas_c1_plan_2026_11'")
        db.commit()
    database.init_db()
    fechas = _n()
    # El plan v1 los creó; el ajuste v2 ya corrió antes (su registro sigue), así
    # que en esta re-ejecución forzada quedan los 9 activos.
    assert fechas == ['2026-11-21', '2027-01-09', '2027-01-23', '2027-03-20', '2027-04-03',
                      '2027-05-29', '2027-06-26', '2027-07-24', '2027-09-18']
    from datetime import date
    assert all(date.fromisoformat(f).weekday() == 5 for f in fechas)       # todos en sábado (día del repaso)
    assert _def('ancla_ingles')['days_of_week'] == 'mon'                   # re-correr no vuelve a partir nada
    assert _def('ancla_ingles')['label'].startswith('Inglés · Sesión A')
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM activity_defs WHERE key LIKE 'ancla_ingles_b%'").fetchone()[0] == 1


def test_acta_pinta_ocasionales_y_hitos(client):
    html = client.get('/actividades/').get_data(as_text=True)
    i = html.index('id="acta-ocas"')
    bloque = html[i:]
    for k in ('gol', 'piano_grabar_libro', 'resolver_codigo', 'hito_en_c1', 'hito_fr_litote'):
        assert f'data-key="{k}"' in bloque, k
    assert bloque.index('data-key="gol"') < bloque.index('data-key="hito_en_c1"')      # bonus antes que hitos
    assert 'Hitos (una sola vez)' in bloque


def test_deshacer_un_hito_lo_reactiva(client):
    client.post('/actividades/api/activity/log', json={'key': 'hito_en_monologo'})
    assert _def('hito_en_monologo')['active'] == 0
    r = client.post('/actividades/api/activity/log', json={'key': 'hito_en_monologo'}).get_json()
    assert r['action'] == 'removed' and r['reactivated'] is True
    assert _def('hito_en_monologo')['active'] == 1
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM activity_logs WHERE activity_key='hito_en_monologo'").fetchone()[0] == 0
    # un hábito desactivado a mano (no one_time) sigue rechazándose
    assert client.post('/actividades/api/activity/log', json={'key': 'test_cert'}).status_code == 400
