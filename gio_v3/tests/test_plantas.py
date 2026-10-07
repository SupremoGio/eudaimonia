"""
test_plantas.py — módulo Plantas, Entrega 1 (2026-10-06): fechas reales de
riego/trasplante, entorno interior/balcón, «aún húmeda», un registro por día,
deshacer y la agenda única que consume el Dashboard.
"""
import sys, os, io
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.plantas.routes as pr
from modules.plantas.care_data import suggest_care, seasonal_factor


# ── care_data ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('q,match', [
    ('Orquídea', 'orquidea'), ('Sábila', 'sabila'), ('Costilla de Adán', 'costilla de adan'),
    ('Bambú de la suerte', 'bambu de la suerte'), ('Ficus lyrata', 'ficus lyrata'),
    ('Monstera deliciosa', 'monstera'), ('Rosemary', 'rosemary'), ('Pizza', None),
])
def test_sugerencia_sin_acentos_y_por_palabra(q, match):
    assert (suggest_care(q) or {}).get('match') == match


def test_factor_de_temporada_por_entorno():
    assert seasonal_factor(7, 'balcon')['factor'] == 1.3
    assert seasonal_factor(7, 'interior')['factor'] == pytest.approx(1.105)
    assert seasonal_factor(4, 'interior')['factor'] == pytest.approx(0.93)


# ── Cálculo ──────────────────────────────────────────────────────────────────

F = {'interior': 1.0, 'balcon': 1.0}


def _row(**kw):
    r = {'id': 1, 'nombre': 'X', 'dias_riego': 7, 'meses_trasplante': 12, 'last_riego': '2026-10-01',
         'last_trasplante': '2026-01-01', 'created_at': '2025-01-01', 'entorno': 'interior',
         'riego_pospuesto_hasta': None}
    r.update(kw)
    return r


def test_trasplante_usa_el_dia_real_no_el_mes_de_calendario():
    """31-oct-2025 + 12 meses = 31-oct-2026; antes se marcaba vencido el 1-oct."""
    p = pr._compute_planta(_row(last_trasplante='2025-10-31'), date(2026, 10, 1), F)
    assert p['trasplante_proxima'] == '2026-10-31' and p['trasplante_status'] == 'proximo'
    assert pr._add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_el_dia_del_riego_es_hoy_no_vencido():
    hoy = date(2026, 10, 8)
    assert pr._compute_planta(_row(), hoy, F)['riego_status'] == 'urgente'      # la UI dice «Hoy»
    assert pr._compute_planta(_row(), date(2026, 10, 9), F)['riego_status'] == 'vencido'
    assert pr._compute_planta(_row(), date(2026, 10, 7), F)['riego_status'] == 'proximo'   # 7 d → aviso 1 día antes
    assert pr._compute_planta(_row(), date(2026, 10, 6), F)['riego_status'] == 'nominal'


def test_balcon_en_lluvias_espacia_mas_que_interior():
    f = {'interior': seasonal_factor(7, 'interior')['factor'], 'balcon': seasonal_factor(7, 'balcon')['factor']}
    hoy = date(2026, 7, 1)
    i = pr._compute_planta(_row(dias_riego=10, last_riego='2026-07-01'), hoy, f)
    b = pr._compute_planta(_row(dias_riego=10, last_riego='2026-07-01', entorno='balcon'), hoy, f)
    assert (i['riego_interval_efectivo'], b['riego_interval_efectivo']) == (11, 13)


def test_pospuesto_corre_la_fecha():
    p = pr._compute_planta(_row(riego_pospuesto_hasta='2026-10-10'), date(2026, 10, 8), F)
    assert p['riego_proxima'] == '2026-10-10' and p['riego_pospuesta'] and p['riego_dias'] == 2


# ── API ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(test_db, tmp_path, monkeypatch):
    from app import create_app
    monkeypatch.setattr(pr, 'UPLOAD_DIR', str(tmp_path))
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


def _crear(c, **kw):
    data = {'nombre': 'Monstera', 'dias_riego': '7', 'meses_trasplante': '12', **kw}
    return c.post('/plantas/api/plantas', data=data, content_type='multipart/form-data').get_json()['id']


def _xp():
    """XP de actividades (los bonos y logros que se desbloquean no se retiran
    al deshacer, igual que en /actividades)."""
    with database.get_db() as db:
        return db.execute("SELECT COALESCE(SUM(amount),0) s FROM xp_ledger WHERE source='activity'").fetchone()['s']


def test_alta_con_entorno_luz_y_ultimo_riego(client):
    pid = _crear(client, entorno='balcon', luz='sol_directo', last_riego='2026-01-02')
    with database.get_db() as db:
        r = dict(db.execute("SELECT entorno, luz, last_riego FROM plantas WHERE id=?", (pid,)).fetchone())
    assert r == {'entorno': 'balcon', 'luz': 'sol_directo', 'last_riego': '2026-01-02'}
    pid2 = _crear(client, entorno='jardin', luz='xx', last_riego='2999-01-01')   # inválidos
    with database.get_db() as db:
        r = dict(db.execute("SELECT entorno, luz, last_riego FROM plantas WHERE id=?", (pid2,)).fetchone())
    assert r['entorno'] == 'interior' and r['luz'] == '' and r['last_riego'] <= date.today().isoformat()


def test_un_riego_por_dia_y_deshacer_regresa_fecha_y_xp(client):
    pid = _crear(client, last_riego='2026-01-01')
    xp0 = _xp()
    d1 = client.post(f'/plantas/api/plantas/{pid}/riego').get_json()
    assert d1['gam']['xp'] > 0 and _xp() > xp0
    d2 = client.post(f'/plantas/api/plantas/{pid}/riego').get_json()
    assert d2['ya_registrado'] and d2['gam'] is None
    hist = client.get(f'/plantas/api/plantas/{pid}/bitacora').get_json()['bitacora']
    assert [h['tipo'] for h in hist] == ['riego'] and hist[0]['deshacer']
    assert client.delete(f'/plantas/api/bitacora/{hist[0]["id"]}').get_json()['ok']
    with database.get_db() as db:
        assert db.execute("SELECT last_riego FROM plantas WHERE id=?", (pid,)).fetchone()['last_riego'] == '2026-01-01'
    assert _xp() == xp0


def test_aun_humeda_pospone_sin_xp_y_se_puede_deshacer(client):
    pid = _crear(client, last_riego='2026-01-01')
    xp0 = _xp()
    d = client.post(f'/plantas/api/plantas/{pid}/posponer', json={'dias': 3}).get_json()
    p = next(x for x in d['state']['plantas'] if x['id'] == pid)
    assert p['riego_dias'] == 3 and p['riego_pospuesta'] and _xp() == xp0
    # Regar limpia el pospuesto
    client.post(f'/plantas/api/plantas/{pid}/riego')
    with database.get_db() as db:
        assert db.execute("SELECT riego_pospuesto_hasta FROM plantas WHERE id=?", (pid,)).fetchone()[0] is None
    hist = client.get(f'/plantas/api/plantas/{pid}/bitacora').get_json()['bitacora']
    assert [h['tipo'] for h in hist] == ['riego', 'revision']
    # Solo el último se deshace
    assert client.delete(f'/plantas/api/bitacora/{hist[1]["id"]}').status_code == 409
    client.delete(f'/plantas/api/bitacora/{hist[0]["id"]}')
    with database.get_db() as db:
        assert db.execute("SELECT riego_pospuesto_hasta FROM plantas WHERE id=?", (pid,)).fetchone()[0] is not None


def test_foto_se_guarda_como_jpeg_reducido(client, tmp_path):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4000, 3000), (10, 120, 40)).save(buf, 'PNG')
    buf.seek(0)
    r = client.post('/plantas/api/plantas', data={'nombre': 'Pothos', 'foto': (buf, 'foto.png')},
                    content_type='multipart/form-data').get_json()
    foto = next(p for p in r['state']['plantas'] if p['id'] == r['id'])['foto']
    assert foto.endswith('.jpg')
    assert max(Image.open(tmp_path / foto).size) == 1600


def test_dashboard_y_pagina_dan_el_mismo_estado(client):
    """La agenda del Dashboard sale del mismo cálculo que /plantas/."""
    from modules.dashboard.routes import _build_deadlines
    from utils import today_date
    hoy = today_date()
    pid = _crear(client, nombre='Helecho', dias_riego='3', last_riego=date.fromordinal(hoy.toordinal() - 3).isoformat())
    _crear(client, nombre='Cactus', dias_riego='30')
    st = client.get('/plantas/api/state').get_json()
    helecho = next(p for p in st['plantas'] if p['id'] == pid)
    ag = client.get('/plantas/api/agenda').get_json()['agenda']
    assert [(a['planta_id'], a['tipo'], a['fecha']) for a in ag] == [(pid, 'riego', helecho['riego_proxima'])]
    dl = [d for d in _build_deadlines(hoy) if d['type'].startswith('planta_')]
    assert [(d['id'], d['type'], d['fecha']) for d in dl] == [(pid, 'planta_riego', helecho['riego_proxima'])]


# ── Entrega 2: otros cuidados, fotos, regar en grupo, otra fecha ─────────────

def test_cuidado_extra_calendario_y_pausa_de_fertilizar():
    created = date(2026, 1, 1)
    c = {'tipo': 'rotar', 'cada_dias': 14, 'last_fecha': '2026-10-01'}
    assert pr._compute_extra(c, created, date(2026, 10, 15))['status'] == 'urgente'
    f = {'tipo': 'fertilizar', 'cada_dias': 30, 'last_fecha': '2026-09-01'}
    assert pr._compute_extra(f, created, date(2026, 10, 15))['status'] == 'vencido'
    pausa = pr._compute_extra(f, created, date(2026, 12, 15))
    assert pausa['pausado'] and pausa['status'] == 'nominal'
    p = pr._compute_planta(_row(), date(2026, 10, 2), F, [c])
    assert [e['tipo'] for e in p['cuidados']] == ['rotar']


def test_activar_registrar_y_desactivar_cuidado_extra(client):
    pid = _crear(client, cuidado_fertilizar='30', cuidado_rotar='')
    st = client.get('/plantas/api/state').get_json()
    p = next(x for x in st['plantas'] if x['id'] == pid)
    assert [(c['tipo'], c['cada_dias']) for c in p['cuidados']] == [('fertilizar', 30)]
    assert client.post(f'/plantas/api/plantas/{pid}/cuidado/rotar').status_code == 400     # no activo
    assert client.post(f'/plantas/api/plantas/{pid}/cuidado/xyz').status_code == 400
    d = client.post(f'/plantas/api/plantas/{pid}/cuidado/fertilizar').get_json()
    assert d['ok'] and d['gam']['xp'] > 0
    hist = client.get(f'/plantas/api/plantas/{pid}/bitacora').get_json()['bitacora']
    assert hist[0]['tipo'] == 'fertilizar' and hist[0]['deshacer']
    client.post(f'/plantas/api/plantas/{pid}', data={'cuidado_fertilizar': ''}, content_type='multipart/form-data')
    st = client.get('/plantas/api/state').get_json()
    assert next(x for x in st['plantas'] if x['id'] == pid)['cuidados'] == []


def test_registrar_en_otra_fecha(client):
    from utils import today_date
    hoy = today_date()
    pid = _crear(client, last_riego=(hoy - __import__('datetime').timedelta(days=10)).isoformat())
    ayer = (hoy - __import__('datetime').timedelta(days=1)).isoformat()
    d = client.post(f'/plantas/api/plantas/{pid}/riego', json={'fecha': ayer}).get_json()
    assert d['ok'] and next(x for x in d['state']['plantas'] if x['id'] == pid)['last_riego'] == ayer
    # Hoy también se puede (otro día), y uno anterior no mueve el calendario
    client.post(f'/plantas/api/plantas/{pid}/riego')
    hace5 = (hoy - __import__('datetime').timedelta(days=5)).isoformat()
    client.post(f'/plantas/api/plantas/{pid}/riego', json={'fecha': hace5})
    with database.get_db() as db:
        assert db.execute("SELECT last_riego FROM plantas WHERE id=?", (pid,)).fetchone()[0] == hoy.isoformat()
    # Futuro o muy viejo: error
    futuro = (hoy + __import__('datetime').timedelta(days=1)).isoformat()
    assert client.post(f'/plantas/api/plantas/{pid}/riego', json={'fecha': futuro}).status_code == 400
    viejo = (hoy - __import__('datetime').timedelta(days=90)).isoformat()
    assert client.post(f'/plantas/api/plantas/{pid}/riego', json={'fecha': viejo}).status_code == 400
    # Deshacer aplica al último REGISTRADO (el de hace 5 días), no al de fecha más reciente
    hist = client.get(f'/plantas/api/plantas/{pid}/bitacora').get_json()['bitacora']
    assert next(h for h in hist if h['deshacer'])['fecha'] == hace5


def test_regar_en_grupo_solo_pendientes_del_entorno(client):
    from utils import today_date
    viejo = (today_date() - __import__('datetime').timedelta(days=20)).isoformat()
    a = _crear(client, nombre='Lavanda', entorno='balcon', last_riego=viejo)
    b = _crear(client, nombre='Romero', entorno='balcon', last_riego=viejo)
    _crear(client, nombre='Cactus', entorno='balcon', dias_riego='60')            # al día
    i = _crear(client, nombre='Pothos', entorno='interior', last_riego=viejo)
    d = client.post('/plantas/api/riego-grupo', json={'entorno': 'balcon'}).get_json()
    assert d['regadas'] == 2 and d['gam']['xp'] >= 4
    hoy = today_date().isoformat()
    with database.get_db() as db:
        riego = {r['id']: r['last_riego'] for r in db.execute("SELECT id, last_riego FROM plantas")}
    assert riego[a] == riego[b] == hoy and riego[i] == viejo
    assert client.post('/plantas/api/riego-grupo', json={'entorno': 'jardin'}).status_code == 400


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (200, 200), (10, 120, 40)).save(buf, 'PNG')
    buf.seek(0)
    return buf


def test_fotos_de_evolucion_y_portada(client, tmp_path):
    r = client.post('/plantas/api/plantas', data={'nombre': 'Ficus', 'foto': (_png(), 'a.png')},
                    content_type='multipart/form-data').get_json()
    pid = r['id']
    client.post(f'/plantas/api/plantas/{pid}/fotos', data={'foto': (_png(), 'b.png')}, content_type='multipart/form-data')
    fotos = client.get(f'/plantas/api/plantas/{pid}/fotos').get_json()['fotos']
    assert len(fotos) == 2 and [f['portada'] for f in fotos] == [False, True]
    # Borrar la portada: pasa a la otra
    client.delete(f'/plantas/api/fotos/{fotos[1]["id"]}')
    fotos2 = client.get(f'/plantas/api/plantas/{pid}/fotos').get_json()['fotos']
    assert len(fotos2) == 1 and fotos2[0]['portada']
    assert not (tmp_path / fotos[1]['foto']).exists()
    # Cambiar la foto desde Editar la suma a la línea de tiempo sin borrar la anterior
    client.post(f'/plantas/api/plantas/{pid}', data={'foto': (_png(), 'c.png')}, content_type='multipart/form-data')
    fotos3 = client.get(f'/plantas/api/plantas/{pid}/fotos').get_json()['fotos']
    assert len(fotos3) == 2 and (tmp_path / fotos2[0]['foto']).exists()
    # Borrar la planta borra todos los archivos
    client.delete(f'/plantas/api/plantas/{pid}')
    assert not any((tmp_path / f['foto']).exists() for f in fotos3)


def test_portadas_existentes_entran_a_la_linea_de_tiempo(test_db):
    with database.get_db() as db:
        db.execute("INSERT INTO plantas (nombre, foto, created_at) VALUES ('Vieja', 'vieja.jpg', '2025-03-04T10:00:00')")
        db.commit()
    database.init_db()
    database.init_db()      # idempotente
    with database.get_db() as db:
        rows = db.execute("SELECT foto, fecha FROM plantas_fotos").fetchall()
    assert [tuple(r) for r in rows] == [('vieja.jpg', '2025-03-04')]


def test_dashboard_incluye_cuidados_extra(client):
    from modules.dashboard.routes import _build_deadlines
    from utils import today_date
    pid = _crear(client, nombre='Calathea', dias_riego='60', meses_trasplante='24', cuidado_limpiar='30')
    with database.get_db() as db:
        db.execute("UPDATE plantas_cuidados SET last_fecha='2026-01-01' WHERE planta_id=?", (pid,))
        db.commit()
    dl = [d for d in _build_deadlines(today_date()) if d['type'].startswith('planta_')]
    assert [(d['type'], d['label'], d['badge']) for d in dl] == [('planta_limpiar', 'Limpiar hojas de Calathea', 'VENCIDO')]
