"""
test_harma.py — handoff Harma v2 (/harma/).

Sprint 1: ritmo km/mes, edad del km, motivo/manda/fluido/ETA por ítem,
grupos, gasto de 12 meses, último taller y papeles unificados.
Sprint 2–3: odómetro que no baja, plan por urgencia y registro en la fila,
lateral con papeles y bitácora, vistas completas (?vista=).
Sprint 4: recordatorio de Perfil para verificación y póliza (upsert) y el
gasto de cada servicio en Oikonomia (solo con fin_ok).
"""
import sys, os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import pytest
import database
from utils import today_date
from modules.harma import plan as hp
from modules.harma import routes as hr

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOY = today_date()


def _client(fin_ok=True):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
        if fin_ok:
            s['fin_ok'] = True
    return c


@pytest.fixture
def client(test_db):
    return _client()


def _d(n):
    return (HOY - timedelta(days=n)).isoformat()


def _veh(km, hace=0):
    with database.get_db() as db:
        db.execute("UPDATE harma_vehiculo SET km_actual=?, km_actualizado=?", (km, _d(hace)))
        db.commit()


def _serv(km, hace, costo=0, taller=''):
    with database.get_db() as db:
        db.execute("INSERT INTO harma_servicios (tipo, titulo, km, costo, taller, fecha, created_at) VALUES ('otro','x',?,?,?,?,'x')",
                   (km, costo, taller, _d(hace)))
        db.commit()


def _item(id_, cat='motor', km_int=10000, meses=12, last_km=0, hace_meses=0, name=None):
    last = date(HOY.year, HOY.month, 1)
    m = last.month - 1 - hace_meses
    last = date(last.year + m // 12, m % 12 + 1, 1)
    with database.get_db() as db:
        db.execute("DELETE FROM harma_plan_items WHERE id=?", (id_,))
        db.execute("INSERT INTO harma_plan_items (id, cat, name, km_interval, meses_interval, last_km, last_date, critical, created_at) VALUES (?,?,?,?,?,?,?,0,'x')",
                   (id_, cat, name or id_, km_int, meses, last_km, last.isoformat()))
        db.commit()


def _solo(*ids):
    with database.get_db() as db:
        db.execute(f"DELETE FROM harma_plan_items WHERE id NOT IN ({','.join('?' * len(ids))})", ids)
        db.commit()


def _state():
    return hr._state()


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_ritmo_none_con_un_solo_servicio(test_db):
    _serv(80000, 0)
    _veh(80000, 0)
    with database.get_db() as db:
        assert hp.ritmo_km_mes(db, hr._get_vehiculo(db), HOY) is None


def test_ritmo_y_edad_del_km(test_db):
    _serv(72000, 300)
    _veh(84200, 23)
    s = _state()
    v = s['vehiculo']
    assert v['km_edad_dias'] == 23
    assert v['km_ritmo_mes'] == round(12200 / ((300 - 23) / 30.44))


def test_item_solo_por_tiempo(test_db):
    _veh(84200, 0)
    _item('frenos_liq', cat='fluidos', km_int=hp.SIN_KM, meses=24, last_km=0, hace_meses=25, name='Líquido de frenos')
    _solo('frenos_liq')
    it = _state()['plan'][0]
    assert it['manda'] == 'tiempo' and it['motivo'] == 'por tiempo · 25 de 24 meses'
    assert it['fluido'] and not it['con_km'] and it['eta_meses'] == 0 and it['status'] == 'vencido'


def test_item_por_km_con_eta_a_tu_ritmo(test_db):
    _serv(72000, 300)
    _veh(84200, 0)
    _item('aceite', km_int=10000, meses=12, last_km=75100, hace_meses=4, name='Aceite')
    _solo('aceite')
    s = _state()
    it = s['plan'][0]
    assert it['manda'] == 'km' and it['motivo'] == 'por km · 9,100 de 10,000'
    assert it['eta_meses'] == round(900 / s['vehiculo']['km_ritmo_mes'], 1) and it['status'] == 'urgente'


def test_eta_none_sin_ritmo(test_db):
    _veh(84200, 0)
    _item('aceite', km_int=10000, meses=60, last_km=80000, hace_meses=1)
    _solo('aceite')
    it = _state()['plan'][0]
    assert it['manda'] == 'km' and it['eta_meses'] is None and it['eta_txt'] == '—'


def test_grupos(test_db):
    _veh(84200, 0)
    _item('a', km_int=10000, meses=12, last_km=70000, hace_meses=1)    # 142 % vencido
    _item('b', km_int=10000, meses=12, last_km=75100, hace_meses=1)    # 91 % urgente
    _item('c', km_int=10000, meses=12, last_km=77000, hace_meses=1)    # 72 % próximo
    _item('d', km_int=10000, meses=12, last_km=84000, hace_meses=1)    # nominal
    _solo('a', 'b', 'c', 'd')
    g = _state()['grupos']
    assert [i['id'] for i in g['ahora']] == ['a', 'b']
    assert [i['id'] for i in g['siguiente']] == ['c'] and [i['id'] for i in g['al_dia']] == ['d']


def test_gasto_costo_km_y_taller(test_db):
    _serv(72000, 300, costo=3800, taller='Servicio Cholula')
    _serv(70000, 400, costo=999)                       # fuera de 12 meses
    _veh(84200, 0)
    s = _state()
    assert s['gasto_12m'] == 3800 and s['ultimo_taller'] == 'Servicio Cholula'
    assert s['costo_km'] == round(3800 / (s['vehiculo']['km_ritmo_mes'] * 12), 2)


def test_papeles_ordenados(test_db):
    with database.get_db() as db:
        db.execute("INSERT INTO harma_documentos (tipo, titulo, fecha_vencimiento, created_at) VALUES ('tarjeta_circulacion','Tarjeta',NULL,'x')")
        db.execute("INSERT INTO harma_documentos (tipo, titulo, fecha_vencimiento, created_at) VALUES ('tenencia','Tenencia',?,'x')", ((HOY + timedelta(days=120)).isoformat(),))
        db.execute("INSERT INTO harma_documentos (tipo, titulo, fecha_vencimiento, created_at) VALUES ('verificacion','Verificación',?,'x')", (_d(2),))
        db.execute("INSERT INTO harma_polizas (aseguradora, vigencia_fin, created_at) VALUES ('Qualitas',?,'x')", ((HOY + timedelta(days=18)).isoformat(),))
        db.commit()
    p = _state()['papeles']
    assert [x['titulo'] for x in p] == ['Verificación', 'Póliza · Qualitas', 'Tenencia', 'Tarjeta']
    assert [x['status'] for x in p] == ['vencida', 'proximo', 'vigente', 'sin_fecha']
    assert p[0]['dias'] == -2


def test_api_state_conserva_campos(client):
    s = client.get('/harma/api/state').get_json()
    for k in ('vehiculo', 'servicios', 'plan', 'plan_counts', 'documentos', 'polizas', 'siniestros', 'total_costo', 'cat_defs'):
        assert k in s
    for k in ('grupos', 'gasto_12m', 'costo_km', 'ultimo_taller', 'papeles'):
        assert k in s


# ── Sprint 2–3 ───────────────────────────────────────────────────────────────

def test_odometro_no_baja(client):
    _veh(84200, 5)
    r = client.post('/harma/api/vehiculo', json={'km_actual': 84000})
    assert r.status_code == 400 and 'no baja' in r.get_json()['error']
    r = client.post('/harma/api/vehiculo', json={'km_actual': 85000}).get_json()
    assert r['state']['vehiculo']['km_actual'] == 85000 and r['state']['vehiculo']['km_edad_dias'] == 0


def test_registrar_en_la_fila_mueve_a_al_dia(client):
    _veh(84200, 0)
    _item('aceite', km_int=10000, meses=12, last_km=70000, hace_meses=13)
    _solo('aceite')
    d = client.post('/harma/api/plan/aceite/marcar', json={'km': 84200, 'costo': 0, 'taller': 'Cholula'}).get_json()
    assert d['gam'] is not None
    g = d['state']['grupos']
    assert not g['ahora'] and [i['id'] for i in g['al_dia']] == ['aceite']


def test_pagina_sin_tabs_ni_modal_de_registrar(client):
    html = client.get('/harma/').get_data(as_text=True)
    for fuera in ('hm-tabs', 'role="tablist"', 'hm-status', 'Nota técnica', 'm-marcar', 'hm-lead', 'hm-filters'):
        assert fuera not in html, fuera
    for dentro in ('id="hm-odo"', 'Toca ahora', 'Lo siguiente', 'js-ok-toggle', 'Papeles', 'Bitácora', '/harma/?vista=papeles'):
        assert dentro in html, dentro
    assert not os.path.exists(os.path.join(BASE, 'templates/harma/_plan.html'))


def test_vistas_completas(client):
    pap = client.get('/harma/?vista=papeles').get_data(as_text=True)
    assert 'id="pane-papeles"' in pap and 'js-doc-new' in pap and 'js-sin-new' in pap and '← Plan' in pap
    assert 'id="hm-now"' not in pap
    bit = client.get('/harma/?vista=bitacora').get_data(as_text=True)
    assert 'id="pane-bitacora"' in bit and 'id="pane-papeles"' not in bit


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def _subir_doc(c, tipo, vence, titulo='Verificación 2026'):
    return c.post('/harma/api/documentos', data={'titulo': titulo, 'tipo': tipo, 'fecha_vencimiento': vence,
                                                  'file': (io.BytesIO(b'%PDF-1.4'), 'v.pdf')},
                  content_type='multipart/form-data').get_json()


def _rems(desc):
    with database.get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM reminders WHERE description=?", (desc,))]


def test_verificacion_upsert_recordatorio(client):
    v1 = (HOY + timedelta(days=60)).isoformat()
    d1 = _subir_doc(client, 'verificacion', v1)['id']
    r = _rems('Renovar verificación vehicular')
    assert len(r) == 1 and r[0]['origen'] == 'harma' and r[0]['origen_id'] == d1
    assert r[0]['next_date'] == (HOY + timedelta(days=46)).isoformat() and r[0]['tema'] == 'casa'
    v2 = (HOY + timedelta(days=240)).isoformat()
    d2 = _subir_doc(client, 'verificacion', v2)['id']
    r = _rems('Renovar verificación vehicular')
    assert len(r) == 1 and r[0]['origen_id'] == d2 and r[0]['next_date'] == (HOY + timedelta(days=226)).isoformat()
    _subir_doc(client, 'tenencia', v1, titulo='Tenencia')
    assert len(_rems('Renovar verificación vehicular')) == 1


def test_poliza_upsert_recordatorio(client):
    client.post('/harma/api/poliza', data={'aseguradora': 'Qualitas', 'vigencia_fin': (HOY + timedelta(days=30)).isoformat()})
    r = _rems('Renovar póliza · Qualitas')
    assert len(r) == 1 and r[0]['origen'] == 'harma'


def test_migracion_vincula_recordatorio_manual(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM reminders")
        db.execute("INSERT INTO reminders (description, type, is_active, created_at) VALUES ('Renovar verificación','unico',1,'x')")
        db.commit()
        assert hp.vincular_recordatorios(db) == 1
        assert hp.vincular_recordatorios(db) == 0
        rows = [dict(r) for r in db.execute("SELECT description, origen FROM reminders")]
    assert rows == [{'description': 'Renovar verificación vehicular', 'origen': 'harma'}]
    database.init_db()                                   # migración idempotente
    assert len(_rems('Renovar verificación vehicular')) == 1


def test_gasto_en_oikonomia_y_borrado(client):
    _veh(84200, 0)
    d = client.post('/harma/api/servicio', json={'titulo': 'Afinación', 'km': 84300, 'costo': 3800}).get_json()
    sid = d['servicio_id']
    with database.get_db() as db:
        s = db.execute("SELECT fin_mov_id FROM harma_servicios WHERE id=?", (sid,)).fetchone()
        m = db.execute("SELECT * FROM est_movimientos WHERE id=?", (s['fin_mov_id'],)).fetchone()
    assert m['monto'] == 3800 and m['categoria'] == 'TRANSPORTE' and m['subcategoria'] == 'Mantenimiento auto'
    assert m['tipo'] == 'GASTO' and m['descripcion'] == 'Harma · Afinación'
    client.delete(f'/harma/api/servicio/{sid}')
    with database.get_db() as db:
        assert db.execute("SELECT 1 FROM est_movimientos WHERE id=?", (s['fin_mov_id'],)).fetchone() is None


def test_sin_fin_ok_no_toca_oikonomia(test_db):
    c = _client(fin_ok=False)
    with database.get_db() as db:
        n0 = db.execute("SELECT COUNT(*) c FROM est_movimientos").fetchone()['c']
    d = c.post('/harma/api/servicio', json={'titulo': 'Afinación', 'costo': 3800}).get_json()
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) c FROM est_movimientos").fetchone()['c'] == n0
        assert db.execute("SELECT fin_mov_id FROM harma_servicios WHERE id=?", (d['servicio_id'],)).fetchone()[0] is None
    assert d['state']['fin_ok'] is False


def test_xp_y_ec_del_servicio_se_conservan(client):
    assert (hr._SERVICIO_XP, hr._SERVICIO_EC) == (5, 2)
