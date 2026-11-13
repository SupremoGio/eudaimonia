"""
test_avisos.py — handoff Avisos, un solo centro (transversal).

Sprint 1: forma común, adaptadores por módulo, recolectar() tolerante a
fallos, avisos_estado (posponer/descartar), permisos y claves estables.
Sprint 2: campana en la topbar con conteo_hoy desde nav_context.
Sprint 3: preferencias por fuente (avisos_off:<fuente>) e Inicio.
"""
import sys, os
from datetime import timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules import avisos as av
from utils import today_date


@pytest.fixture
def app(test_db):
    from app import create_app
    a = create_app()
    a.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return a


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


@pytest.fixture
def fin(client):
    with client.session_transaction() as s:
        s['fin_ok'] = True
    return client


def _recordatorio(texto, fecha):
    with database.get_db() as db:
        rid = db.execute("INSERT INTO reminders (description, type, target_date, next_date, is_active, created_at) "
                         "VALUES (?, 'unico', ?, ?, 1, '2026-01-01')", (texto, fecha, fecha)).lastrowid
        db.commit()
    return rid


def _recolectar(hoy=None, sess=None, **kw):
    with database.get_db() as db:
        return av.recolectar(db, hoy or today_date(), sess if sess is not None else {}, **kw)


def _claves(res):
    return [a['clave'] for n in av.NIVELES for a in res[n]]


# ── Sprint 1: contrato ──────────────────────────────────────────────────────

def test_todas_las_fuentes_exponen_avisos_y_no_fallan(test_db):
    res = _recolectar(sess={'fin_ok': True})
    assert res['errores'] == []
    for _fid, _n, ruta, _p in av.FUENTES:
        assert callable(av._cargar(ruta))


def test_forma_comun(test_db):
    hoy = today_date()
    _recordatorio('Pagar el agua', hoy.isoformat())
    a = _recolectar()['hoy'][0]
    for k in ('clave', 'modulo', 'icono', 'titulo', 'detalle', 'fecha', 'nivel', 'accion'):
        assert k in a
    assert a['nivel'] == 'hoy' and a['modulo'] == 'Perfil'
    assert a['accion']['method'] == 'POST' and a['accion']['url'].endswith('/done')
    with pytest.raises(ValueError):
        av.aviso('x:y', 'M', 'bell', 't', nivel='urgente')


def test_adaptador_roto_no_tumba_el_centro(test_db):
    def roto(db, hoy):
        raise RuntimeError('boom')

    def bueno(db, hoy):
        return [av.aviso('tst:ok', 'Test', 'bell', 'Sigo aquí', nivel='hoy')]

    res = _recolectar(fuentes=[('roto', 'Roto', roto, None), ('bueno', 'Bueno', bueno, None)])
    assert res['errores'] == ['roto']
    assert [a['clave'] for a in res['hoy']] == ['tst:ok'] and res['conteo_hoy'] == 1


def test_api_avisos_sobrevive_a_un_modulo_roto(client, monkeypatch):
    monkeypatch.setattr(av, 'FUENTES', [('perfil', 'Perfil', 'modules.no_existe', None)] + av.FUENTES)
    _recordatorio('Llamar al banco', today_date().isoformat())
    r = client.get('/api/avisos')
    assert r.status_code == 200
    d = r.get_json()
    assert set(d) >= {'hoy', 'semana', 'logro', 'conteo_hoy'}
    assert 'perfil' in d['errores'] and d['conteo_hoy'] >= 1


def test_pospuesto_no_aparece_hasta_su_fecha(client):
    hoy = today_date()
    _recordatorio('Renovar pasaporte', hoy.isoformat())
    clave = client.get('/api/avisos').get_json()['hoy'][0]['clave']
    r = client.post(f'/api/avisos/{clave}/posponer', json={'nivel': 'hoy'})
    assert r.get_json()['ok'] and r.get_json()['hasta'] == (hoy + timedelta(days=1)).isoformat()
    assert clave not in _claves(client.get('/api/avisos').get_json())
    assert r.get_json()['conteo_hoy'] == 0
    # mañana vuelve solo (el recordatorio sigue pendiente: misma clave)
    assert clave in _claves(_recolectar(hoy + timedelta(days=1)))
    # semana: 3 días por defecto
    r = client.post('/api/avisos/per:rec:999:2099-01-01/posponer', json={'nivel': 'semana'})
    assert r.get_json()['hasta'] == (hoy + timedelta(days=3)).isoformat()


def test_descartar_y_restaurar(client):
    _recordatorio('Cita dentista', today_date().isoformat())
    clave = client.get('/api/avisos').get_json()['hoy'][0]['clave']
    assert client.post(f'/api/avisos/{clave}/descartar').get_json()['conteo_hoy'] == 0
    assert clave not in _claves(_recolectar(today_date() + timedelta(days=30)))
    assert client.post(f'/api/avisos/{clave}/restaurar').get_json()['conteo_hoy'] == 1


def test_clave_invalida(client):
    assert client.post('/api/avisos/../etc/posponer').status_code in (400, 404)
    assert client.post('/api/avisos/sin espacios/descartar').status_code == 400


def _hoy_de_pago():
    """Un día de pago (15) para que BBVA e Invex venzan «hoy»."""
    return date(2026, 11, 15)


def test_sin_fin_ok_no_hay_nada_de_oikonomia(test_db):
    hoy = _hoy_de_pago()
    con = _recolectar(hoy, {'fin_ok': True})
    assert {'oik:pago:bbva:2026-11', 'oik:pago:invex:2026-11'} <= set(_claves(con))
    pago = next(a for a in con['hoy'] if a['clave'] == 'oik:pago:bbva:2026-11')
    assert pago['accion']['url'] == '/finanzas/api/pago-ciclo' and pago['accion']['body'] == {'cuenta': 'bbva'}
    assert pago['accion']['deshacer']['method'] == 'DELETE'
    sin = _recolectar(hoy, {})
    assert not [c for c in _claves(sin) if c.startswith('oik:')]
    # aunque una fuente sin permiso declarado devuelva avisos con perm
    fuente = [('x', 'X', lambda db, h: [av.aviso('oik:x', 'Oikonomia', 'wallet', 't', perm='fin_ok')], None)]
    assert _recolectar(hoy, {}, fuentes=fuente)['total'] == 0


def test_api_sin_fin_ok(client, monkeypatch):
    import modules.finanzas.pagos_ciclo as pc
    monkeypatch.setattr(av, 'today_date', _hoy_de_pago)
    d = client.get('/api/avisos').get_json()
    assert not [c for c in _claves(d) if c.startswith('oik:')]


def test_pago_semana_y_marcar_pagado(fin):
    hoy = date(2026, 11, 10)
    res = _recolectar(hoy, {'fin_ok': True})
    pago = next(a for a in res['semana'] if a['clave'] == 'oik:pago:bbva:2026-11')
    assert 'en 5 d' in pago['detalle']
    with database.get_db() as db:
        import modules.finanzas.pagos_ciclo as pc
        pc.marcar(db, 'bbva', hoy=hoy)
        db.commit()
    assert 'oik:pago:bbva:2026-11' not in _claves(_recolectar(hoy, {'fin_ok': True}))


def test_claves_estables(test_db):
    hoy = today_date()
    _recordatorio('Pagar luz', hoy.isoformat())
    _recordatorio('Cambiar filtro', (hoy + timedelta(days=4)).isoformat())
    with database.get_db() as db:
        db.execute("INSERT INTO harma_vehiculo (nombre, km_actual, created_at) VALUES ('Golf', 90000, 'x')")
        db.execute("""INSERT INTO harma_plan_items (id, cat, name, km_interval, meses_interval, last_km, last_date, created_at)
                      VALUES ('frenos_t', 'frenos', 'Líquido de frenos', 40000, 24, 80000, ?, 'x')""",
                   ((hoy - timedelta(days=800)).isoformat(),))
        db.execute("INSERT INTO harma_polizas (aseguradora, vigencia_fin, created_at) VALUES ('Qualitas', ?, 'x')",
                   ((hoy + timedelta(days=18)).isoformat(),))
        db.commit()
    a, b = _recolectar(sess={'fin_ok': True}), _recolectar(sess={'fin_ok': True})
    assert _claves(a) == _claves(b) and len(set(_claves(a))) == len(_claves(a))
    claves = _claves(a)
    assert any(c.startswith('har:plan:frenos_t:') for c in claves)
    assert any(c.startswith('har:papel:poliza:') for c in claves)
    plan = next(x for x in a['hoy'] if x['clave'].startswith('har:plan:frenos_t:'))
    assert plan['detalle'].startswith('por tiempo') and plan['accion']['method'] == 'POST'
    pol = next(x for x in a['semana'] if x['clave'].startswith('har:papel:poliza:'))
    assert 'en 18 d' in pol['detalle']
    for c in claves:
        assert av._clave_ok(c), c


def test_orden_por_nivel_y_fecha(test_db):
    hoy = today_date()
    _recordatorio('B tarde', (hoy + timedelta(days=5)).isoformat())
    _recordatorio('A pronto', (hoy + timedelta(days=2)).isoformat())
    _recordatorio('Vencido', (hoy - timedelta(days=3)).isoformat())
    res = _recolectar()
    assert [a['titulo'] for a in res['semana']] == ['A pronto', 'B tarde']
    assert res['hoy'][0]['titulo'] == 'Vencido' and 'hace 3' in res['hoy'][0]['detalle']


def test_logros_y_vistos(client):
    hoy = today_date().isoformat()
    with database.get_db() as db:
        db.execute("INSERT OR REPLACE INTO achievements (key, unlocked_at, xp_earned, coins_earned, notified) "
                   "VALUES ('primer_paso', ?, 5, 10, 0)", (hoy,))
        db.execute("INSERT OR REPLACE INTO achievements (key, unlocked_at, xp_earned, coins_earned, notified) "
                   "VALUES ('disciplina_total', '2020-01-01', 5, 10, 0)")
        db.commit()
    d = client.get('/api/avisos').get_json()
    assert [a['titulo'] for a in d['logro']] == ['Logro: Primer Paso']       # lo antiguo no
    assert d['logro'][0]['detalle'] == '+5 XP · +10 EC' and d['conteo_hoy'] == 0
    assert client.post('/api/avisos/logros/vistos', json={}).get_json()['marcados'] == 1
    with database.get_db() as db:
        assert db.execute("SELECT notified FROM achievements WHERE key='primer_paso'").fetchone()[0] == 1
    assert client.get('/api/avisos').get_json()['logro'] == []


def test_praxis_vencidas(test_db):
    hoy = today_date()
    with database.get_db() as db:
        db.execute("INSERT INTO gtd_tasks (title, status, fecha_limite, created_at) VALUES ('Declaración', 'next', ?, 'x')",
                   ((hoy - timedelta(days=2)).isoformat(),))
        db.execute("INSERT INTO gtd_tasks (title, status, fecha_limite, created_at) VALUES ('Futuro', 'next', ?, 'x')",
                   ((hoy + timedelta(days=2)).isoformat(),))
        db.commit()
    t = [a for a in _recolectar()['hoy'] if a['modulo'] == 'Praxis']
    assert [a['titulo'] for a in t] == ['Declaración'] and t[0]['accion']['url'].endswith('/complete')


def test_presupuesto_y_estado_por_subir(test_db):
    hoy = date(2026, 11, 13)
    with database.get_db() as db:
        db.execute("INSERT INTO est_budgets (categoria, nombre, limite) VALUES ('TEST_CAT', 'Prueba', 1000)")
        db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, banco) "
                   "VALUES ('2026-11-05', 'HEB', -950, 'GASTO', 'TEST_CAT', 'BBVA_DEB')")
        db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, banco) "
                   "VALUES ('2026-09-10', 'X', -10, 'GASTO', 'OCIO', 'BBVA_TDC')")
        db.commit()
    res = _recolectar(hoy, {'fin_ok': True})
    claves = _claves(res)
    assert any(c.startswith('oik:presupuesto:') and c.endswith(':2026-11:alerta') for c in claves)
    assert 'oik:estado:BBVA_TDC:2026-10-22' in claves


def test_acta_anclas_de_noche(test_db, monkeypatch):
    import modules.actividades.routes as act
    monkeypatch.setattr(act, 'ANCLAS_AVISO_HORA', 0)
    monkeypatch.setattr('modules.quick.badges', lambda db: {'acta': 2, 'praxis': 0})
    a = [x for x in _recolectar()['hoy'] if x['modulo'] == 'Acta Diurna']
    assert a and a[0]['titulo'] == '2 anclas sin registrar' and a[0]['accion']['url'] == '/actividades/'


# ── Sprint 2: campana ───────────────────────────────────────────────────────

def test_campana_en_topbar_con_conteo(client):
    _recordatorio('Pagar renta', today_date().isoformat())
    html = client.get('/').get_data(as_text=True)
    assert 'id="eu-avisos-btn"' in html and 'aria-label="Avisos, 1 para hoy"' in html
    assert 'class="eu-avisos-badge"' in html and 'eu-avisos.js' in html
    assert 'id="eu-avisos"' in html and 'role="dialog"' in html


def test_campana_sin_insignia_si_no_hay_nada(client):
    html = client.get('/').get_data(as_text=True)
    assert 'aria-label="Avisos, 0 para hoy"' in html
    assert 'class="eu-avisos-badge"' not in html


# ── Sprint 3: preferencias e Inicio ──────────────────────────────────────────────────

def test_apagar_fuente_la_quita_de_la_campana_y_el_conteo(client):
    _recordatorio('Pagar tenencia', today_date().isoformat())
    assert client.get('/api/avisos').get_json()['conteo_hoy'] == 1
    r = client.post('/api/avisos/preferencias', json={'fuente': 'perfil', 'activa': False})
    assert r.get_json()['conteo_hoy'] == 0
    assert 'aria-label="Avisos, 0 para hoy"' in client.get('/').get_data(as_text=True)
    client.post('/api/avisos/preferencias', json={'fuente': 'perfil', 'activa': True})
    assert client.get('/api/avisos').get_json()['conteo_hoy'] == 1
    assert client.post('/api/avisos/preferencias', json={'fuente': 'nope', 'activa': False}).status_code == 400


def test_preferencias_en_perfil(client):
    # Desde el handoff Plantas y Ajustes viven en Ajustes › Avisos.
    r = client.get('/perfil/?sec=avisos')
    assert r.status_code == 302 and r.headers['Location'].endswith('/perfil/?sec=ajustes#avisos')
    html = client.get('/perfil/?sec=ajustes').get_data(as_text=True)
    assert 'id="avisos-prefs"' in html
    for fid, nombre, _r, perm in av.FUENTES:
        if not perm:
            assert f'data-aj="avisos_off:{fid}"' in html


def test_inicio_y_campana_muestran_los_mismos_pendientes_de_hoy(fin):
    hoy = today_date()
    _recordatorio('Pagar predial', hoy.isoformat())
    _recordatorio('Pospuesto en la campana', hoy.isoformat())
    with database.get_db() as db:
        db.execute("INSERT INTO harma_vehiculo (nombre, km_actual, created_at) VALUES ('Golf', 90000, 'x')")
        db.execute("""INSERT INTO harma_plan_items (id, cat, name, km_interval, meses_interval, last_km, last_date, created_at)
                      VALUES ('aceite_t', 'motor', 'Cambio de aceite', 10000, 12, 0, '2020-01-01', 'x')""")
        db.commit()
    d = fin.get('/api/avisos').get_json()
    pos = next(a['clave'] for a in d['hoy'] if a['titulo'] == 'Pospuesto en la campana')
    fin.post(f'/api/avisos/{pos}/posponer', json={'nivel': 'hoy'})
    hoy_campana = {a['clave'] for a in fin.get('/api/avisos').get_json()['hoy']}
    from modules.dashboard.routes import _build_deadlines, _avisos_hoy
    with fin.application.test_request_context('/'):
        from flask import session
        session['fin_ok'] = True
        session['app_ok'] = True
        dl = _build_deadlines(hoy, _avisos_hoy(hoy))
    hoy_inicio = {d['clave'] for d in dl if d['days'] <= 0}
    assert hoy_inicio == hoy_campana
    assert any(c.startswith('har:plan:aceite_t') for c in hoy_inicio)      # el aviso de otro módulo entra
    html = fin.get('/').get_data(as_text=True)
    assert 'Pagar predial' in html and 'Pospuesto en la campana' not in html
    assert 'Cambio de aceite' in html and 'data-url="/harma/api/plan/aceite_t/marcar"' in html


def test_apagar_harma_lo_quita_de_inicio(client):
    with database.get_db() as db:
        db.execute("INSERT INTO harma_vehiculo (nombre, km_actual, created_at) VALUES ('Golf', 90000, 'x')")
        db.execute("""INSERT INTO harma_plan_items (id, cat, name, km_interval, meses_interval, last_km, last_date, created_at)
                      VALUES ('aceite_t', 'motor', 'Cambio de aceite', 10000, 12, 0, '2020-01-01', 'x')""")
        db.commit()
    assert 'Cambio de aceite' in client.get('/').get_data(as_text=True)
    client.post('/api/avisos/preferencias', json={'fuente': 'harma', 'activa': False})
    html = client.get('/').get_data(as_text=True)
    assert 'Cambio de aceite' not in html and 'aria-label="Avisos, 0 para hoy"' in html
