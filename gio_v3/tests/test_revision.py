"""
test_revision.py — handoff Revisión semanal unificada (/ataraxia/revision).

Sprint 1: ruta con 4 pasos (?paso=), en VIEWS; guardado parcial que se
retoma; XP solo al cerrar y una sola vez; paso 1 (veredicto, 7 días, pregunta
del mejor día) y paso 2 (6 métricas automáticas, manuales con la semana
pasada, «A vigilar»).
Sprint 2: paso 3 (inbox, vencidas, avisos de la semana con acciones de un
toque), paso 4 (prioridades + calendario), cierre que marca Planeación y
las entradas (bloque Planeación, aviso del domingo, ⌘K).
"""
import sys, os, re, json, html as _html, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.ataraxia.routes as ar
from modules import nav

DOMINGO = datetime.date(2026, 11, 8)          # semana lun 2 – dom 8 nov (semana_id 2026-11-07)


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _hoy(monkeypatch, d=DOMINGO):
    monkeypatch.setattr(ar, 'today_date', lambda: d)
    monkeypatch.setattr(ar, 'today_str', lambda: d.isoformat())


def _get(client, q=''):
    return client.get('/ataraxia/revision' + q).get_data(as_text=True)


def _panel(html, n):
    return html.split(f'data-panel="{n}"', 1)[1].split('data-panel=', 1)[0]


def _row():
    return ar._get_revision_row(ar.get_semana_id()) or {}


def _xp_logs():
    with database.get_db() as db:
        return db.execute("SELECT COUNT(*) FROM activity_logs WHERE activity_key='revision_semanal'").fetchone()[0]


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_ruta_pasos_y_vista_en_la_barra(client, monkeypatch):
    _hoy(monkeypatch)
    html = _get(client)
    assert '<h1 class="t-page">Revisión</h1>' in html and 'Semana 45 · 2–8 nov' in html
    crumb = html.split('class="eu-crumb"', 1)[1].split('</nav>', 1)[0]
    assert 'href="/ataraxia/">Ataraxia</a>' in crumb and '<span aria-current="page">Revisión</span>' in crumb
    assert nav.view_of(nav.resolve('/ataraxia/revision')[1], None, {}, '/ataraxia/revision') == 'Revisión'
    for label in ('Cómo fue', 'Los números', 'Cerrar cabos', 'La que viene'):
        assert label in html
    assert 'href="?paso=1" data-go="1" aria-current="step"' in html
    assert 'data-panel="2" aria-labelledby="rv-h2" hidden' in html
    html = _get(client, '?paso=3')
    assert 'href="?paso=3" data-go="3" aria-current="step"' in html and 'data-panel="1" aria-labelledby="rv-h1" hidden' in html
    assert 'Al terminar: <b class="num">+7 XP · +3 EC</b>' in html


def test_guardado_parcial_se_retoma(client, monkeypatch):
    _hoy(monkeypatch)
    assert client.post('/ataraxia/api/revision', json={'notas': 'Dormí bien', 'paso': 2}).get_json()['first_save']
    client.post('/ataraxia/api/revision', json={'horas_sueno': 6.5})
    client.post('/ataraxia/api/revision', json={'pasos_promedio': ''})          # vaciar uno no toca los demás
    row = _row()
    assert row['notas'] == 'Dormí bien' and row['horas_sueno'] == 6.5 and row['paso'] == 2
    assert row['pasos_promedio'] is None and not row['cerrada_at'] and not row['xp_pagado']
    assert _xp_logs() == 0                                                       # el guardado parcial no paga
    html = _get(client)                                                          # sin ?paso= retoma donde quedó
    assert 'href="?paso=2" data-go="2" aria-current="step"' in html
    assert 'Dormí bien</textarea>' in html and 'data-save="horas_sueno" value="6.5"' in html


def test_cerrar_paga_una_sola_vez(client, monkeypatch):
    _hoy(monkeypatch)
    r = client.post('/ataraxia/api/revision', json={'cerrar': True}).get_json()
    assert r['pagada'] and r['cerrada'] and r['gam'] and _xp_logs() == 1
    r = client.post('/ataraxia/api/revision', json={'cerrar': True}).get_json()
    assert not r['pagada'] and r['gam'] is None and _xp_logs() == 1
    assert _row()['cerrada_at'] and _row()['xp_pagado'] == 1
    assert 'href="?paso=4" data-go="4"' in _get(client) and 'data-panel="5" aria-labelledby="rv-h5">' in _get(client)


def test_revision_vieja_ya_pagada_no_vuelve_a_pagar(client, monkeypatch):
    _hoy(monkeypatch)
    with database.get_db() as db:          # guardada con el formulario anterior (pagaba al primer guardado)
        db.execute("INSERT INTO revision_semanal (semana_id, horas_sueno, created_at, updated_at) VALUES (?, 7, 'x', 'x')",
                   (ar.get_semana_id(),))
        db.execute("DELETE FROM migration_log WHERE version='revision_semanal_v2'")
        db.commit()
    database.init_db()                     # la migración marca lo existente como pagado
    r = client.post('/ataraxia/api/revision', json={'cerrar': True}).get_json()
    assert r['cerrada'] and not r['pagada'] and _xp_logs() == 0
    database.init_db()                     # idempotente: no vuelve a correr
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM migration_log WHERE version='revision_semanal_v2'").fetchone()[0] == 1


def test_paso1_veredicto_dias_y_pregunta(client, monkeypatch):
    _hoy(monkeypatch)
    p1 = _panel(_get(client), 1)
    assert 'class="rv-verdict at-tier"' in p1 and 'class="rv-verdict-r"' in p1
    assert p1.count('class="rv-day ') == 7
    assert '¿Qué hizo que el ' in p1 and ' fuera tu mejor día?' in p1 or '¿Qué te funcionó esta semana?' in p1
    assert 'data-save="notas"' in p1


def test_paso2_metricas_auto_nuevas(client, monkeypatch):
    _hoy(monkeypatch)
    with database.get_db() as db:
        for f, m in (('2026-11-03', 45), ('2026-11-06', 80), ('2026-10-30', 999)):
            db.execute("INSERT INTO eury_sessions (date, min, split_diso, split_paso, split_improv, flow, xp, created_at) VALUES (?,?,0,0,0,3,0,'x')", (f, m))
        db.execute("INSERT OR REPLACE INTO body_measurements (key, label, value, unit) VALUES ('peso','Peso','78,4','kg')")
        for d in ('2026-11-02', '2026-11-03', '2026-11-04'):
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?, ?, 0)", ('nutri_dia_' + d, d))
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('x', ?, 1)", (d,))
        db.execute("INSERT INTO nutricion_deslices (date, trig_id, label, glyph, pen, over, note) VALUES ('2026-11-03','otro','x','x',1,0,'')")
        for d in ('2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08'):
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('x', ?, 1)", (d,))
        db.commit()
    auto = ar._auto_metrics(ar.get_semana_id())
    assert auto['min_baile'] == (125.0, 'Eurythmia')
    assert auto['peso'] == (78.4, 'Perfil')
    assert auto['dias_limpios'] == (2.0, 'Nutrición')
    assert auto['racha_anclas'] == (7.0, 'Acta')
    client.post('/ataraxia/api/revision', json={'peso': 1})                      # el cliente no pisa lo auto
    assert _row()['peso'] == 78.4 and _row()['min_baile'] == 125.0
    p2 = _panel(_get(client), 2)
    assert 'id="rv-m-min_baile">125 <span class="t-meta">min</span></output>' in p2
    assert p2.count('rv-src is-auto') == len(auto)
    for k in ('horas_sueno', 'pasos_promedio', 'screen_time_horas'):
        assert f'data-save="{k}"' in p2
    assert 'calorias_quemadas' not in p2


def test_metrica_auto_que_falla_pasa_a_manual(client, monkeypatch):
    _hoy(monkeypatch)
    def boom(semana_id):
        raise RuntimeError('db')
    monkeypatch.setitem(ar._AUTO_METRICS, 'racha_anclas', ('Acta', boom))
    assert 'racha_anclas' not in ar._auto_metrics(ar.get_semana_id())
    assert 'data-save="racha_anclas"' in _panel(_get(client), 2)


def test_manuales_con_semana_pasada_y_a_vigilar(client, monkeypatch):
    _hoy(monkeypatch)
    with database.get_db() as db:
        db.execute("INSERT INTO revision_semanal (semana_id, pasos_promedio, created_at, updated_at) VALUES ('2026-10-31', 7420, 'x', 'x')")
        db.commit()
    client.post('/ataraxia/api/revision', json={'horas_sueno': 6.6})
    p2 = _panel(_get(client), 2)
    assert 'sem. pasada 7420' in p2
    watch = p2.split('class="rv-watch"', 1)[1]
    assert 'A vigilar' in watch and 'Sueño promedio de 6.6h' in watch


# ── Sprint 2 ─────────────────────────────────────────────────────────────────

def _task(title, **kw):
    cols = {'title': title, 'tipo': 'tarea', 'completado': 0, 'status': 'inbox', 'points': 4, 'created_at': '2026-11-01T10:00:00', **kw}
    with database.get_db() as db:
        tid = db.execute(f"INSERT INTO gtd_tasks ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", list(cols.values())).lastrowid
        db.commit()
    return tid


def _acciones(html, key):
    li = html.split(f'data-key="{key}"', 1)[1].split('</li>', 1)[0]
    return {_html.unescape(m.group(2)): json.loads(_html.unescape(m.group(1)))
            for m in re.finditer(r'data-calls="([^"]*)" data-res="[^"]*"[^>]*>([^<]+)</button>', li)}


def _ejecutar(client, calls):
    for c in calls:
        r = client.open(c['url'], method=c['method'], json=c.get('body', {}))
        assert r.status_code == 200, (c, r.get_data(as_text=True))


def test_paso3_cerrar_cabos_se_refleja_en_praxis(client, monkeypatch):
    _hoy(monkeypatch)
    a, b, c = _task('Llamar al banco'), _task('Cotizar llantas'), _task('Regalo para Ana')
    v = _task('Pagar predial', cuadrante='semana', importante=1, urgente=0, fecha_limite='2026-11-05')
    html = _get(client, '?paso=3')
    p3 = _panel(html, 3)
    assert 'Inbox de Praxis' in p3 and 'Vencidas' in p3 and 'id="rv-pend">4<' in p3
    assert 'venció jue 5' in p3
    _ejecutar(client, _acciones(p3, f't{a}')['Esta semana'])
    _ejecutar(client, _acciones(p3, f't{b}')['Algún día'])
    _ejecutar(client, _acciones(p3, f't{c}')['Borrar'])
    _ejecutar(client, _acciones(p3, f't{v}')['Mover'])
    with database.get_db() as db:
        q = lambda i: db.execute("SELECT * FROM gtd_tasks WHERE id=?", (i,)).fetchone()
        assert q(a)['cuadrante'] == 'semana' and q(b)['cuadrante'] == 'ideas' and q(c) is None
        assert q(v)['fecha_limite'] == '2026-11-09'                                 # al lunes siguiente
    assert 'id="rv-pend">0<' in _get(client, '?paso=3')


def test_paso3_vencida_hoy_y_hecha(client, monkeypatch):
    _hoy(monkeypatch)
    v1 = _task('Mandar factura', cuadrante='semana', importante=1, urgente=0, fecha_limite='2026-11-06')
    v2 = _task('Renovar INE', cuadrante='semana', importante=1, urgente=0, fecha_limite='2026-11-06')
    p3 = _panel(_get(client, '?paso=3'), 3)
    _ejecutar(client, _acciones(p3, f't{v1}')['Hoy'])
    _ejecutar(client, _acciones(p3, f't{v2}')['Hecha'])
    with database.get_db() as db:
        r1 = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (v1,)).fetchone()
        assert r1['cuadrante'] == 'hoy' and r1['fecha_limite'] == '2026-11-08'
        assert db.execute("SELECT completado FROM gtd_tasks WHERE id=?", (v2,)).fetchone()[0] == 1


def test_paso3_avisos_de_la_semana(client, monkeypatch):
    _hoy(monkeypatch)
    f = (DOMINGO + datetime.timedelta(days=3)).isoformat()
    with database.get_db() as db:
        db.execute("INSERT INTO reminders (description, type, target_date, next_date, is_active, created_at) VALUES ('Saldo del celular','unico',?,?,1,'x')", (f, f))
        db.commit()
    p3 = _panel(_get(client, '?paso=3'), 3)
    assert 'Avisos de la semana' in p3 and 'Saldo del celular' in p3
    key = re.search(r'data-key="(per:rec:\d+:[\d-]+)"', p3).group(1)
    acts = _acciones(p3, key)
    assert set(acts) == {'Hecho', 'Posponer'}
    _ejecutar(client, acts['Posponer'])
    assert 'Saldo del celular' not in _panel(_get(client, '?paso=3'), 3)


def test_paso4_prioridades_y_calendario(client, monkeypatch):
    _hoy(monkeypatch)
    ids = [_task(f'Prioridad {i}', cuadrante='semana', importante=1, urgente=0) for i in range(4)]
    with database.get_db() as db:
        db.execute("INSERT INTO futbol_partidos (fecha, hora, rival, estado, created_at) VALUES ('2026-11-11', '20:00', 'Los Tigres', 'programado', 'x')")
        db.execute("INSERT INTO reminders (description, type, target_date, next_date, is_active, created_at) VALUES ('Pago predial','unico','2026-11-12','2026-11-12',1,'x')")
        db.commit()
    for t in ids[:3]:
        assert client.post(f'/ataraxia/api/prioridad-semana/{t}').get_json()['ok']
    assert client.post(f'/ataraxia/api/prioridad-semana/{ids[3]}').status_code == 409   # máx. 3
    p4 = _panel(_get(client, '?paso=4'), 4)
    assert p4.count('aria-pressed="true"') == 3 and 'data-full="true"' in p4 and '3/3' in p4
    cal = p4.split('Ya en el calendario', 1)[1]
    assert 'mié 11' in cal and 'Partido vs Los Tigres · 20:00' in cal and 'Pago predial' in cal
    assert 'sáb 14' in cal and 'Ataraxia · ' in cal and 'Revisión semana 46' in cal
    assert 'Pago BBVA TDC' not in cal                                            # sin fin_ok no hay Oikonomia
    with client.session_transaction() as s:
        s['fin_ok'] = True
    cal = _panel(_get(client, '?paso=4'), 4).split('Ya en el calendario', 1)[1]
    assert 'Pago BBVA TDC' in cal and 'Corte BBVA TDC' not in cal                # el 15 cae el dom 15; el corte (22), fuera


def test_cerrar_marca_planeacion(client, monkeypatch):
    _hoy(monkeypatch)
    sem = ar.get_semana_id()
    client.post('/ataraxia/api/revision', json={'cerrar': True})
    with database.get_db() as db:
        r = db.execute("SELECT completado FROM rutina_progreso WHERE bloque_id='sun_planeacion' AND semana_id=?", (sem,)).fetchone()
    assert r and r['completado'] == 1
    # cerrar de nuevo no vuelve a pagar la casilla
    assert ar._marcar_tarea('sun_planeacion', sem)['ya'] is True
    assert ar._marcar_tarea('sun_planeacion', sem)['gam'] is None


def test_ataraxia_sin_formulario_y_planeacion_abre_la_revision(client, monkeypatch):
    _hoy(monkeypatch)
    html = client.get('/ataraxia/?dia=domingo').get_data(as_text=True)
    assert 'id="rev-form"' not in html and 'data-metric=' not in html
    assert 'Revisión de la semana →' in html
    assert 'class="at-rev-link at-plan-link" href="/ataraxia/revision"' in html
    assert not os.path.exists(os.path.join(os.path.dirname(ar.__file__), '../../templates/ataraxia/_revision.html'))


def test_aviso_del_domingo_y_cmdk(client, monkeypatch):
    _hoy(monkeypatch)
    from modules import avisos as av
    with database.get_db() as db:
        assert ar.avisos(db, DOMINGO) == []                       # antes de las 17:00 (conftest)
        monkeypatch.setattr(ar, 'REVISION_AVISO_HORA', 0)
        a = ar.avisos(db, DOMINGO)
        assert a and a[0]['clave'] == 'ata:revision:2026-11-07' and a[0]['nivel'] == 'hoy'
        assert a[0]['accion']['url'] == '/ataraxia/revision'
        assert ar.avisos(db, DOMINGO - datetime.timedelta(days=1)) == []   # solo el domingo
    client.post('/ataraxia/api/revision', json={'cerrar': True})
    with database.get_db() as db:
        assert ar.avisos(db, DOMINGO) == []                       # cerrada: ya no avisa
    assert 'ataraxia' in {f[0] for f in av.FUENTES}
    act = next(x for x in nav.ACTIONS if x['id'] == 'revision')
    assert act['url'] == '/ataraxia/revision' and 'revision' in act['keywords']
