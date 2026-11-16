"""
test_idiomas_ajuste_v2.py — eudaimonia_ajuste_v2.json (resumen en docs/idiomas_c1_plan.md).

Migración idiomas_ajuste_v2_2026_11 y reglas globales:
- versión mínima del ancla = 50 % del XP, 0 EC (conserva la racha: deja registro);
- vista del día: anclas + «Foco de hoy» (touches con foco, máx. 8) y el resto
  plegado en «Extras»;
- fusiones (Ritual nocturno, Meditar + visualizar, Nutrición del día), idiomas
  por día, autodiagnóstico C1 en 3 sábados en lugar del repaso.
"""
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.actividades.activity_defs as adefs
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


def test_fusiones_y_desactivados(test_db):
    for k in ('idiomas_repaso', 'VividVocab', 'idiomas_journal', 'podcast_idiomas', 'lectura_idiomas',
              'skincare_noche', 'correccion_diaria', 'gratitud_diaria', 'visualizacion', 'comer_fruta', 'colacion'):
        assert _def(k)['active'] == 0, k
    rit = _def('ritual_nocturno')
    assert (rit['pts'], rit['ec'], rit['checklist']) == (5, 0, 'Skin care|Corrección diaria|3 agradecimientos')
    assert (_def('meditar')['label'], _def('meditar')['pts']) == ('Meditar + visualizar', 3)
    nd = _def('nutricion_dia')
    assert (nd['pillar'], nd['type'], nd['pts'], nd['foco'], nd['days_of_week']) == ('hege', 'touch', 2, 0, None)
    conv = _def('conversacion')
    assert (conv['label'], conv['type'], conv['pts'], conv['ec']) == ('Conversación con humano 10 min+', 'ocasional', 5, 2)
    assert _def('partido')['label'] == 'Partido extra (fuera del miércoles)'


def test_idiomas_por_dia_tocan_los_dos_idiomas(test_db):
    assert (_def('anki_idiomas')['days_of_week'], _def('anki_idiomas')['session'], _def('anki_idiomas')['foco']) == (None, 'morning', 1)
    esperado = {'escucha_en': ('mon,wed,thu', 2, 0), 'escucha_fr': ('tue,fri,sun', 2, 0),
                'lectura_fr': ('mon,wed,thu', 3, 1), 'lectura_en': ('tue,fri,sun', 3, 1)}
    for k, (dias, pts, ec) in esperado.items():
        d = _def(k)
        assert (d['days_of_week'], d['pts'], d['ec'], d['foco'], d['pillar']) == (dias, pts, ec, 1, 'cosmo'), k
    # cada día de la semana menos el sábado: un idioma por escucha y el otro por lectura
    for dia in ('mon', 'tue', 'wed', 'thu', 'fri', 'sun'):
        hoy = [k for k, (dias, _, _) in esperado.items() if dia in dias.split(',')]
        assert sorted(k[-2:] for k in hoy) == ['en', 'fr'], dia
    assert (_def('ancla_ingles_b')['pts'], _def('ancla_frances_b')['pts']) == (7, 7)
    assert (_def('ancla_ingles')['duracion_min'], _def('ancla_ingles')['minima_min']) == (60, 20)
    assert (_def('ancla_repaso_idiomas')['minima_min']) == 25


def test_autodiagnostico_reemplaza_al_repaso_en_sus_sabados(test_db):
    ad, rep = _def('autodiagnostico_c1'), _def('ancla_repaso_idiomas')
    assert (ad['type'], ad['pts'], ad['ec'], ad['duracion_min']) == ('ancla', 30, 10, 90)
    for f in ('2027-01-23', '2027-04-03', '2027-06-12'):
        d = date.fromisoformat(f)
        assert adefs.eligible_today(ad, None, d) and not adefs.eligible_today(rep, None, d), f
    normal = date(2027, 1, 16)                                    # otro sábado
    assert adefs.eligible_today(rep, None, normal) and not adefs.eligible_today(ad, None, normal)


def test_version_minima_50_por_ciento_sin_ec(client):
    r = client.post('/actividades/api/activity/log', json={'key': 'ancla_ingles_b', 'minimal': True}).get_json()
    assert r['action'] == 'added' and r['pts'] == 4 and r['ec'] == 0        # 7 × 0.5 = 3.5 → 4
    r = client.post('/actividades/api/activity/log', json={'key': 'ancla_frances', 'minimal': True}).get_json()
    assert r['pts'] == 3                                                     # 6 × 0.5
    import modules.gamification.engine as engine
    assert engine.ANCLA_MIN_XP_RATIO == 0.5 and engine.get_gamification_streak() >= 1


def test_ritual_reflexion_no_lo_marca_solo(client):
    r = client.post('/actividades/api/reflexion', json={'key': 'ritual_nocturno', 'texto': 'Hoy agradezco…'}).get_json()
    assert r['ok'] and r['auto_checked'] is False
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM activity_logs WHERE activity_key='ritual_nocturno'").fetchone()[0] == 0
        assert db.execute("SELECT texto FROM reflexion_diaria WHERE activity_key='ritual_nocturno' AND date=?",
                          (today_str(),)).fetchone()[0] == 'Hoy agradezco…'


def test_vista_del_dia_foco_y_extras(client):
    html = client.get('/actividades/').get_data(as_text=True)
    i, j = html.index('class="eu-card acta-hoy"'), html.index('id="acta-extras"')
    hoy, extras = html[i:j], html[j:html.index('</details>', j)]
    assert 'data-key="anki_idiomas"' in hoy and 'data-key="anki_idiomas"' not in extras
    assert hoy.count('class="acta-item') <= 8
    assert 'data-key="ritual_nocturno"' in extras and 'Skin care · Corrección diaria · 3 agradecimientos' in extras
    assert 'data-key="nutricion_dia"' in extras                               # foco=false → Extras


def test_recordatorios_de_checkpoint_viejos_desactivados(test_db, monkeypatch):
    monkeypatch.setattr(database, 'SEMBRAR_DATOS_USUARIO', True)
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version IN ('idiomas_c1_plan_2026_11','idiomas_ajuste_v2_2026_11')")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        activos = [r[0] for r in db.execute("""SELECT target_date FROM reminders WHERE is_active=1 AND
                   (description LIKE '%checkpoint%' OR description LIKE 'Idiomas · línea base%')""")]
    assert activos == ['2026-11-21']                                         # queda solo la línea base
