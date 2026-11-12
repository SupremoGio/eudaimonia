"""
test_viajes_v2.py — handoff Viajes v2 (/viajes/).

Sprint 1: maleta automática al asignar/quitar outfit (conserva checks y
manuales), consumibles no_regresa, preparacion, dias_uso, sugerencias por
día, olvidados al completar. Sprint 2–3: encabezado, fases, filas de día y
maleta sin «Generar». Sprint 4: una sola página (Dinero con fin_ok, alta única).
"""
import sys, os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date
from modules.viajes import routes as vr

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOY = today_date()


def _d(n):
    return (HOY + timedelta(days=n)).isoformat()


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


@pytest.fixture
def fin(client):
    with client.session_transaction() as s:
        s['fin_ok'] = True
    return client


def _prenda(db, nombre, cat='Camisa'):
    return db.execute("INSERT INTO wardrobe_items (nombre, categoria, color_hex, activo, created_at) VALUES (?,?,'#333',1,'x')",
                      (nombre, cat)).lastrowid


def _outfit(db, nombre, prendas, ocasion='Casual'):
    oid = db.execute("INSERT INTO outfits (nombre, ocasion, created_at) VALUES (?,?,'x')", (nombre, ocasion)).lastrowid
    for p in prendas:
        db.execute("INSERT INTO outfit_items (outfit_id, item_id) VALUES (?,?)", (oid, p))
    return oid


@pytest.fixture
def armario(test_db):
    with database.get_db() as db:
        p = {n: _prenda(db, n, c) for n, c in (('Camisa oxford', 'Camisa'), ('Chino beige', 'Pantalón'), ('Tenis blancos', 'Tenis / Sneakers'),
                                               ('Playera negra', 'Camiseta'), ('Jean oscuro', 'Jeans'), ('Camisa blanca', 'Camisa'),
                                               ('Mocasines', 'Zapato'), ('Suéter gris', 'Suéter'))}
        o = {
            'casual': _outfit(db, 'Casual azul', [p['Camisa oxford'], p['Chino beige'], p['Tenis blancos']]),
            'turista': _outfit(db, 'Turista', [p['Playera negra'], p['Jean oscuro'], p['Tenis blancos']]),
            'noche': _outfit(db, 'Noche gris', [p['Suéter gris'], p['Jean oscuro'], p['Tenis blancos']]),
            'cena': _outfit(db, 'Cena', [p['Camisa blanca'], p['Chino beige'], p['Mocasines']], 'Formal'),
        }
        db.commit()
    return p, o


def _viaje(client, ini=5, fin=9, **kw):
    body = dict(nombre='CDMX', destino='Ciudad de México', fecha_inicio=_d(ini), fecha_fin=_d(fin),
                tipo_clima='templado', ocasion='casual', **kw)
    r = client.post('/viajes/api/trips', json=body).get_json()
    assert r['ok']
    dias = client.get(f"/viajes/api/trips/{r['id']}/dias").get_json()
    return r['id'], dias


def _por_nombre(maleta):
    return {m['nombre']: m for m in maleta}


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_viaje_nuevo_arranca_con_extras_y_consumibles(client):
    vid, _ = _viaje(client)
    m = _por_nombre(client.get(f'/viajes/api/trips/{vid}/maleta').get_json())
    assert len(m) == len(vr.EXTRAS_ESTANDAR)
    assert {n for n, x in m.items() if x['no_regresa']} == {'Pasta dental', 'Shampoo', 'Jabón corporal'}


def test_asignar_outfit_arma_la_maleta_y_conserva_checks(client, armario):
    p, o = armario
    vid, dias = _viaje(client)
    r = client.post(f"/viajes/api/trips/{vid}/dias/{dias[0]['id']}/outfit", json={'outfit_id': o['casual']}).get_json()
    m = _por_nombre(r['maleta'])
    assert r['ok'] and {'Camisa oxford', 'Chino beige', 'Tenis blancos'} <= set(m)
    assert r['preparacion']['outfits'] == {'dias_con': 1, 'total': 5}
    # Marcar empacado + un ítem manual; el siguiente outfit no los pisa
    client.patch(f"/viajes/api/trips/{vid}/maleta/{m['Tenis blancos']['id']}", json={'field': 'packed_ida'})
    manual = client.post(f'/viajes/api/trips/{vid}/maleta/item', json={'nombre': 'Gorra', 'categoria': 'Accesorios'}).get_json()['id']
    r = client.post(f"/viajes/api/trips/{vid}/dias/{dias[1]['id']}/outfit", json={'outfit_id': o['turista']}).get_json()
    m = _por_nombre(r['maleta'])
    assert m['Tenis blancos']['packed_ida'] == 1 and m['Tenis blancos']['dias_uso'] == 2
    assert m['Playera negra']['dias_uso'] == 1 and 'Gorra' in m and m['Gorra']['id'] == manual
    # Quitar outfit: sus prendas salen, lo demás se queda
    r = client.delete(f"/viajes/api/trips/{vid}/dias/{dias[1]['id']}/outfit").get_json()
    m = _por_nombre(r['maleta'])
    assert r['ok'] and 'Playera negra' not in m and m['Tenis blancos']['packed_ida'] == 1 and 'Gorra' in m
    # El GET de la maleta también trae dias_uso
    g = _por_nombre(client.get(f'/viajes/api/trips/{vid}/maleta').get_json())
    assert g['Tenis blancos']['dias_uso'] == 1 and g['Gorra']['dias_uso'] == 0


def test_extras_borrados_no_reaparecen(client, armario):
    _, o = armario
    vid, dias = _viaje(client)
    m = _por_nombre(client.get(f'/viajes/api/trips/{vid}/maleta').get_json())
    client.delete(f"/viajes/api/trips/{vid}/maleta/{m['Power bank']['id']}")
    r = client.post(f"/viajes/api/trips/{vid}/dias/{dias[0]['id']}/outfit", json={'outfit_id': o['casual']}).get_json()
    assert 'Power bank' not in _por_nombre(r['maleta'])
    # «Generar» (compatibilidad) sí repone los extras que falten
    assert client.post(f'/viajes/api/trips/{vid}/maleta/generar').get_json()['outfit_items'] == 3
    assert 'Power bank' in _por_nombre(client.get(f'/viajes/api/trips/{vid}/maleta').get_json())


def test_consumibles_no_cuentan_en_vuelta(client):
    vid, _ = _viaje(client)
    m = _por_nombre(client.get(f'/viajes/api/trips/{vid}/maleta').get_json())
    p = client.get(f'/viajes/api/trips/{vid}').get_json()['preparacion']
    assert p['ida'] == {'hechos': 0, 'total': 13} and p['vuelta'] == {'hechos': 0, 'total_sin_consumibles': 10}
    r = client.patch(f"/viajes/api/trips/{vid}/maleta/{m['Desodorante']['id']}", json={'no_regresa': True}).get_json()
    assert r == {'ok': True, 'value': 1}
    client.patch(f"/viajes/api/trips/{vid}/maleta/{m['Cargador de celular']['id']}", json={'field': 'packed_vuelta'})
    client.patch(f"/viajes/api/trips/{vid}/maleta/{m['Shampoo']['id']}", json={'field': 'packed_vuelta'})
    p = client.get(f'/viajes/api/trips/{vid}').get_json()['preparacion']
    assert p['vuelta'] == {'hechos': 1, 'total_sin_consumibles': 9}


def test_fase_y_dias_para(client):
    vid, _ = _viaje(client, 5, 9)
    p = client.get(f'/viajes/api/trips/{vid}').get_json()['preparacion']
    assert p['fase'] == 'antes' and p['dias_para'] == 5
    v = {'estado': 'activo', 'fecha_inicio': _d(-3), 'fecha_fin': _d(0)}
    assert vr.fase(v) == 'regreso'                                   # último día
    assert vr.fase(dict(v, fecha_fin=_d(1))) == 'antes'
    assert vr.fase(dict(v, fecha_fin=_d(-2), estado='planificado')) == 'regreso'
    assert vr.fase(dict(v, estado='completado')) == 'cerrado'


def test_sugerencias_por_ocasion_sin_repetir_ayer(client, armario):
    _, o = armario
    vid, dias = _viaje(client)
    client.post(f"/viajes/api/trips/{vid}/dias/{dias[0]['id']}/outfit", json={'outfit_id': o['turista']})
    r = client.get(f"/viajes/api/trips/{vid}/dias/{dias[1]['id']}/sugerencias").get_json()
    ids = [s['id'] for s in r['data']]
    assert o['turista'] not in ids and o['cena'] not in ids          # ayer + ocasión formal fuera
    assert set(ids) == {o['casual'], o['noche']} and r['total'] == 4
    # Noche gris comparte Jean + Tenis con la maleta → primero
    assert ids[0] == o['noche'] and 'comparte 2 prendas' in r['data'][0]['razon']
    assert set(r['data'][0]) == {'id', 'nombre', 'razon'}
    # Día de «Cena con Ana» → formal
    client.patch(f"/viajes/api/trips/{vid}/dias/{dias[3]['id']}/descripcion", json={'descripcion': 'Cena con Ana'})
    r = client.get(f"/viajes/api/trips/{vid}/dias/{dias[3]['id']}/sugerencias").get_json()
    assert [s['id'] for s in r['data']] == [o['cena']] and r['data'][0]['razon'].startswith('para la cena')
    assert client.get(f'/viajes/api/trips/{vid}/dias/999999/sugerencias').status_code == 404


def test_olvidados_al_completar(client):
    vid, _ = _viaje(client, -6, -1)
    m = _por_nombre(client.get(f'/viajes/api/trips/{vid}/maleta').get_json())
    for n in ('Cargador de celular', 'Auriculares'):
        client.patch(f"/viajes/api/trips/{vid}/maleta/{m[n]['id']}", json={'field': 'packed_vuelta'})
    t = client.get(f'/viajes/api/trips/{vid}').get_json()
    assert t['olvidados'] is None and t['regreso'] == {'olvidados': 8, 'total': 10}   # aún sin cerrar: en vivo
    body = dict(nombre='CDMX', fecha_inicio=t['fecha_inicio'], fecha_fin=t['fecha_fin'], estado='completado')
    client.patch(f'/viajes/api/trips/{vid}', json=body)
    t = client.get(f'/viajes/api/trips/{vid}').get_json()
    assert t['olvidados'] == 8 and t['preparacion']['fase'] == 'cerrado'
    lista = {x['id']: x for x in client.get('/viajes/api/trips').get_json()}
    assert lista[vid]['regreso'] == {'olvidados': 8, 'total': 10}
    client.patch(f'/viajes/api/trips/{vid}', json=dict(body, estado='activo'))
    assert client.get(f'/viajes/api/trips/{vid}').get_json()['olvidados'] is None


def test_completar_desde_finanzas_tambien_cierra(fin):
    vid, _ = _viaje(fin, -6, -1)
    fin.patch(f'/finanzas/estados/api/trips/{vid}', json={'estado': 'completado'})
    assert fin.get(f'/viajes/api/trips/{vid}').get_json()['olvidados'] == 10


def test_migracion_idempotente(test_db):
    with database.get_db() as db:
        vid = db.execute("INSERT INTO viajes (nombre, fecha_inicio, fecha_fin, created_at) VALUES ('X','2026-01-01','2026-01-02','x')").lastrowid
        db.execute("INSERT INTO viaje_maleta (viaje_id, nombre, categoria, es_extra) VALUES (?, 'Shampoo', 'Higiene', 1)", (vid,))
        db.execute("DELETE FROM migration_log WHERE version='viajes_v2_consumibles'")
        db.commit()
    database.init_db()
    database.init_db()
    with database.get_db() as db:
        assert [r['name'] for r in db.execute("PRAGMA table_info(viaje_maleta)")].count('no_regresa') == 1
        assert [r['name'] for r in db.execute("PRAGMA table_info(viajes)")].count('olvidados') == 1
        assert db.execute("SELECT no_regresa FROM viaje_maleta WHERE viaje_id=?", (vid,)).fetchone()[0] == 1


# ── Sprint 2–3 ───────────────────────────────────────────────────────────────

def test_detalle_sin_pestanas_ni_generar(client):
    html = client.get('/viajes/').get_data(as_text=True)
    for fuera in ('vj-tabs', 'pane-regreso', 'vj-banner', 'btn-generar', 'Generar desde outfits', 'vj-meta', 'detail-estado-badge',
                  'outfits-prog', 'maleta-prog', 'ui-stat', 'eu-stat'):
        assert fuera not in html, fuera
    for dentro in ('id="vj-prep"', 'data-fase="antes"', 'data-fase="regreso"', 'Outfits por día', 'Se actualiza sola con tus outfits',
                   'Agregar prenda o ítem…', 'id="vj-cierre"', 'id="m-picker"', 'Otros viajes', 'js-del'):
        assert dentro in html, dentro
    js = open(os.path.join(BASE, 'static/js/viajes.js'), encoding='utf-8').read()
    assert '/maleta/generar' not in js and '/sugerencias' in js and "'no regresa'" in js and 'Ver todos…' in js


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def test_sin_fin_ok_no_hay_dinero(client):
    html = client.get('/viajes/').get_data(as_text=True)
    assert 'f-presupuesto' not in html and 'id="vj-money"' not in html and 'data-fin="0"' in html
    vid, _ = _viaje(client, presupuesto=5000)
    t = client.get(f'/viajes/api/trips/{vid}').get_json()
    assert 'dinero' not in t and 'presupuesto' not in t
    assert all('presupuesto' not in x for x in client.get('/viajes/api/trips').get_json())
    with database.get_db() as db:
        assert db.execute("SELECT presupuesto FROM viajes WHERE id=?", (vid,)).fetchone()[0] == 0


def test_alta_unica_con_presupuesto_y_dinero(fin):
    html = fin.get('/viajes/').get_data(as_text=True)
    assert 'f-presupuesto' in html and 'id="vj-money"' in html and 'Desglose y movimientos' in html
    vid, _ = _viaje(fin, -2, 3, presupuesto=12000)
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo, viaje_id)
                      VALUES (?, 'HOTEL', 8400, 'BBVA_TDC', 'VIAJES', 'GASTO', ?)""", (_d(-2), vid))
        for i, monto in enumerate((500, 740)):
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo)
                          VALUES (?, ?, ?, 'BBVA_TDC', 'COMIDA_FUERA', 'GASTO')""", (_d(-1), f'REST {i}', monto))
        db.commit()
    din = fin.get(f'/viajes/api/trips/{vid}').get_json()['dinero']
    assert (din['presupuesto'], din['gastado'], din['restan'], din['pct']) == (12000, 8400, 3600, 70)
    assert din['sugeridos']['n'] == 2 and din['sugeridos']['total'] == 1240
    # Vincular con el endpoint existente de Oikonomia
    assert fin.post(f'/finanzas/estados/api/trips/{vid}/tag', json={'tx_ids': din['sugeridos']['ids']}).get_json()['tagged'] == 2
    din = fin.get(f'/viajes/api/trips/{vid}').get_json()['dinero']
    assert din['gastado'] == 9640 and din['sugeridos']['n'] == 0
    # Aparece en /finanzas con el mismo presupuesto (misma tabla, sin duplicar)
    lista = [t for t in fin.get('/finanzas/estados/api/trips').get_json() if t['nombre'] == 'CDMX']
    assert len(lista) == 1 and lista[0]['presupuesto'] == 12000
    # Editar desde /viajes cambia el presupuesto
    t = fin.get(f'/viajes/api/trips/{vid}').get_json()
    fin.patch(f'/viajes/api/trips/{vid}', json=dict(nombre='CDMX', fecha_inicio=t['fecha_inicio'], fecha_fin=t['fecha_fin'], presupuesto=15000))
    assert fin.get(f'/viajes/api/trips/{vid}').get_json()['dinero']['presupuesto'] == 15000


def test_finanzas_sin_alta_propia(fin):
    html = fin.get('/finanzas/estados/viajes/').get_data(as_text=True)
    assert 'id="m-trip"' not in html and 'js-new' not in html and 'js-del' not in html and 'Nuevo viaje' not in html
    js = open(os.path.join(BASE, 'static/js/fin-viajes.js'), encoding='utf-8').read()
    assert "'/viajes/?id='" in js and "/viajes/?nuevo=1" in js and "'POST'" in js     # el POST que queda es /tag
    assert "API + '/trips', 'POST'" not in js and "'DELETE'" not in js
    r = fin.get('/finanzas/estados/viajes/nuevo')
    assert r.status_code == 302 and r.headers['Location'].endswith('/viajes/?nuevo=1')


def test_borrar_desde_viajes_desvincula_movimientos(fin):
    vid, _ = _viaje(fin)
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo, viaje_id)
                            VALUES (?, 'UBER', 120, 'BBVA_TDC', 'TRANSPORTE', 'GASTO', ?)""", (_d(5), vid)).lastrowid
        db.commit()
    assert fin.delete(f'/viajes/api/trips/{vid}').get_json()['ok']
    with database.get_db() as db:
        assert db.execute("SELECT viaje_id FROM est_movimientos WHERE id=?", (mid,)).fetchone()[0] is None
        assert db.execute("SELECT COUNT(*) FROM viaje_maleta WHERE viaje_id=?", (vid,)).fetchone()[0] == 0
