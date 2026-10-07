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
