"""
test_hegemonikon.py — handoff Hegemonikon v2 (/bienestar/).

Sprint 1: resumen del cuerpo, tratamiento con medicamentos («día N de M» y
fin automático), alerta de recurrencia ocultable, próximo partido y el
cierre de un episodio con {dias, vs_promedio}.
Sprint 2–3: hub (hoy en tu cuerpo, en tratamiento, cuerpo, partido,
también aquí). Sprint 4: Salud sin resumen repetido, análisis plegado, ?ep=.
"""
import sys, os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date
from modules.bienestar import salud as sl
from modules.bienestar import routes as br

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


def _ep(titulo='Esguince de tobillo', tipo='lesion', hace=9, activo=1, fin=None, zona='tobillo derecho'):
    with database.get_db() as db:
        eid = db.execute("INSERT INTO medico_episodios (tipo, titulo, zona_cuerpo, fecha_inicio, fecha_fin, activo, created_at) VALUES (?,?,?,?,?,?,'x')",
                         (tipo, titulo, zona, _d(hace), fin, activo)).lastrowid
        db.commit()
    return eid


def _receta(eid, hace=5, medico='Dr. Méndez'):
    with database.get_db() as db:
        rid = db.execute("INSERT INTO medico_recetas (episodio_id, medico, especialidad, fecha, created_at) VALUES (?,?,?,?,'x')",
                         (eid, medico, 'Traumatología', _d(hace))).lastrowid
        db.commit()
    return rid


def _med(rid, nombre, dur=None, tomando=1):
    with database.get_db() as db:
        mid = db.execute("INSERT INTO medico_medicamentos (receta_id, nombre, dosis, frecuencia, duracion_dias, tomando, created_at) VALUES (?,?,?,?,?,?,'x')",
                         (rid, nombre, '400 mg', 'cada 8 h', dur, tomando)).lastrowid
        db.commit()
    return mid


def _tomando(mid):
    with database.get_db() as db:
        return db.execute("SELECT tomando, terminado_en FROM medico_medicamentos WHERE id=?", (mid,)).fetchone()


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_fin_automatico_en_el_borde(test_db):
    eid = _ep()
    rid = _receta(eid, hace=7)
    borde = _med(rid, 'Ibuprofeno', dur=7)            # día 7 de 7 → se apaga
    antes = _med(rid, 'Diclofenaco', dur=8)           # día 7 de 8 → sigue
    sin = _med(rid, 'Paracetamol', dur=None)          # «si hay dolor» → nunca
    with database.get_db() as db:
        assert sl.auto_terminar(db) == 1
        assert sl.auto_terminar(db) == 0              # idempotente
    assert tuple(_tomando(borde)) == (0, HOY.isoformat())
    assert _tomando(antes)['tomando'] == 1 and _tomando(sin)['tomando'] == 1


def test_tratamiento_con_dia_n_desde_la_receta(test_db):
    viejo = _ep(titulo='Esguince viejo', hace=40, activo=0, fin=_d(26))   # 14 días
    eid = _ep(hace=9)
    rid = _receta(eid, hace=5)
    _med(rid, 'Ibuprofeno', dur=7)
    _med(rid, 'Paracetamol')
    with database.get_db() as db:
        t = sl.tratamiento(db)
    assert t['id'] == eid and t['dia_n'] == 9 and t['avg_recuperacion_tipo'] == 14.0
    assert t['recetas'] == 1 and t['documentos'] == 0 and t['medico'] == 'Dr. Méndez · Traumatología'
    ibu = next(m for m in t['medicamentos'] if m['nombre'] == 'Ibuprofeno')
    assert (ibu['dia_n'], ibu['duracion_dias'], ibu['pct'], ibu['casi']) == (5, 7, 71, True)
    para = next(m for m in t['medicamentos'] if m['nombre'] == 'Paracetamol')
    assert para['duracion_dias'] is None and para['pct'] == 0


def test_sin_tratamiento(test_db):
    with database.get_db() as db:
        assert sl.tratamiento(db) is None


def test_alerta_de_recurrencia_y_ocultar(client):
    for n in (120, 80, 40):
        _ep(titulo='Faringitis', tipo='enfermedad', hace=n, activo=0, fin=_d(n - 5))
    with database.get_db() as db:
        a = sl.recurrencia_alerta(db)
    assert a == {'titulo': 'Faringitis', 'veces': 3, 'cada_dias': 40}
    r = client.post('/bienestar/api/alerta/ocultar', json={'titulo': 'Faringitis'}).get_json()
    assert r['hasta'] == (HOY + timedelta(days=30)).isoformat()
    with database.get_db() as db:
        assert sl.recurrencia_alerta(db) is None
        assert sl.recurrencia_alerta(db, hoy=HOY + timedelta(days=31)) is not None   # vuelve a los 30 d
    assert 'hg-alert' not in client.get('/bienestar/').get_data(as_text=True)


def test_recurrencia_lenta_no_alerta(test_db):
    for n in (400, 200):
        _ep(titulo='Gripe', tipo='enfermedad', hace=n, activo=0, fin=_d(n - 4))
    with database.get_db() as db:
        assert sl.recurrencia_alerta(db) is None


def _partido(fecha, estado='programado', gf=0, gc=0, rival='Los Tigres', rend=None):
    with database.get_db() as db:
        db.execute("INSERT INTO futbol_partidos (fecha, hora, cancha, rival, goles_favor, goles_contra, rendimiento, estado, created_at) VALUES (?,?,?,?,?,?,?,?,'x')",
                   (fecha, '20:00', 'Cancha 2', rival, gf, gc, rend, estado))
        db.commit()


def _mie():
    d = HOY + timedelta(days=(2 - HOY.weekday()) % 7 or 7)
    return d


def test_partido_forma_y_lesion(test_db):
    _partido(_d(30), 'jugado', 3, 1, rend=7)
    _partido(_d(20), 'jugado', 1, 1, rend=8)
    _partido(_d(10), 'jugado', 0, 2, rend=6)
    _partido(_mie().isoformat())
    with database.get_db() as db:
        p = br._proximo_partido(db)
    assert p['hay'] and p['rival'] == 'Los Tigres' and p['reemplaza_gym'] and p['liga'] == 'SoccerGDL'
    assert p['forma'] == ['G', 'E', 'P'] and p['record'] == '1-1-1' and p['rating_prom'] == 7.0
    assert not p['lesion_activa']
    _ep()                                              # lesión activa
    _ep(titulo='Gripe', tipo='enfermedad')             # no cuenta
    with database.get_db() as db:
        p = br._proximo_partido(db)
    assert p['lesion_activa'] and p['lesion_zona'] == 'tobillo derecho'


def test_resolver_devuelve_dias_y_vs_promedio(client):
    _ep(titulo='Esguince viejo', hace=40, activo=0, fin=_d(26))   # 14 d
    eid = _ep(hace=9)
    r = client.patch(f'/bienestar/salud/api/episodios/{eid}', json={'activo': 0, 'fecha_fin': HOY.isoformat()}).get_json()
    assert r == {'ok': True, 'dias': 9, 'vs_promedio': -5.0}


def test_resumen_api_conserva_forma(client):
    d = client.get('/bienestar/api/hegemonikon-summary').get_json()
    for k in ('body', 'peso_trend', 'peso_spark', 'nutricion', 'salud', 'guardarropa', 'recetas', 'futbol', 'viajes'):
        assert k in d
    for k in ('peso', 'tratamiento', 'recurrencia_alerta', 'partido'):
        assert k in d


def test_terminado_en_al_marcar_termine(client):
    mid = _med(_receta(_ep()), 'Ibuprofeno', dur=7)
    client.patch(f'/bienestar/salud/api/medicamentos/{mid}', json={'tomando': 0})
    assert tuple(_tomando(mid)) == (0, HOY.isoformat())
    client.patch(f'/bienestar/salud/api/medicamentos/{mid}', json={'tomando': 1})
    assert tuple(_tomando(mid)) == (1, None)


# ── Sprint 2–3 ───────────────────────────────────────────────────────────────

def test_hub_con_tratamiento(client):
    eid = _ep()
    _med(_receta(eid), 'Ibuprofeno', dur=7)
    _partido(_mie().isoformat())
    html = client.get('/bienestar/').get_data(as_text=True)
    assert 'hg-lead' not in html and 'js-new-ep' in html and 'id="m-ep"' in html
    hoy = html.split('id="hg-hoy"', 1)[1].split('</section>', 1)[0]
    assert 'Sin lecturas' in hoy and '/perfil/?sec=medidas' in hoy
    assert '1 med.' in hoy and 'día 9' in hoy and 'reemplaza Gym' in hoy
    trat = html.split('id="hg-trat"', 1)[1].split('</section>', 1)[0]
    assert 'Marcar resuelto' in trat and 'día 5 de 7' in trat and 'Terminé' in trat
    assert f'/bienestar/salud/?ep={eid}' in trat
    side = html.split('<aside class="hg-side"', 1)[1]
    assert 'vs Los Tigres' in side and 'Ese día reemplaza a Gym y GymBook en Acta Diurna.' in side
    assert '¿Juegas?' in side and 'También aquí' in side and 'Guardarropa' in side and 'Viajes' in side
    body = html.split('id="hg-body"', 1)[1].split('</section>', 1)[0]
    assert body.count('<a class="hg-link') == 4 and 'is-warning' in body and '/guardarropa/' not in body


def test_hub_sin_nada(client):
    html = client.get('/bienestar/').get_data(as_text=True)
    assert 'Nada en tratamiento.' in html and 'hg-alert' not in html
    assert 'Sin partido programado' in html and '¿Juegas?' not in html


def test_hub_peso_con_spark(client):
    with database.get_db() as db:
        for i, v in enumerate([79.6, 79.0, 78.4]):
            db.execute("INSERT INTO body_measurements_history (key, value, recorded_at) VALUES ('peso',?,?)",
                       (str(v), (datetime.now() - timedelta(days=12 - i * 3)).isoformat()))
        db.commit()
    hoy = client.get('/bienestar/').get_data(as_text=True).split('id="hg-hoy"', 1)[1].split('</section>', 1)[0]
    assert '78.4 kg' in hoy and '-0.6 en 3 d · hace 6 d' in hoy and 'is-good' in hoy


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def test_salud_sin_resumen_y_analisis_plegado(client):
    eid = _ep()
    _ep(titulo='Esguince viejo', hace=40, activo=0, fin=_d(26))
    html = client.get(f'/bienestar/salud/?ep={eid}').get_data(as_text=True)
    assert 'sl-stats' not in html and f'data-ep="{eid}"' in html
    assert '<details class="eu-card eu-card--flush sl-an">' in html             # cerrado
    assert '2 episodios en 6 meses · recuperación media 14.0 d' in html
    js = open(os.path.join(BASE, 'static/js/salud.js'), encoding='utf-8').read()
    assert "root.dataset.ep" in js and "'día ' + n + ' de '" in js


def test_migracion_idempotente(test_db):
    database.init_db()
    database.init_db()
    with database.get_db() as db:
        cols = [r['name'] for r in db.execute("PRAGMA table_info(medico_medicamentos)")]
    assert cols.count('terminado_en') == 1
