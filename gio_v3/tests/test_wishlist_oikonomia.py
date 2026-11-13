"""
test_wishlist_oikonomia.py — Remates · Wishlist de Oikonomia S1.

- h1 «Wishlist» y antetítulo «N pendientes · $X»; sin las 4 eu-stat.
- Franja: pendiente por prioridad, «Este mes» contra budget.libre_deseos
  (Deseos de la regla 50·30·20 menos lo gastado; sin ingreso no hay celda),
  comprado en el año.
- Grupos por mes_objetivo (Este mes incluye lo atrasado · Próximo · Más
  adelante · Sin fecha), por prioridad; Comprado y Descartado plegados.
- Fila: «Comprado» en línea, «Mover de mes» (los endpoints actuales), «o N EC»
  (POST /api/comprar-ec/<id>) y «también en Guardarropa».
- Sin fin_ok sigue redirigiendo a /finanzas/.
"""
import sys, os, re
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.finanzas.prioridades as pr
import modules.finanzas.budget as fb
from ec_constants import EC_RATE

HOY = date(2026, 11, 13)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _vaciar():
    with database.get_db() as db:          # la base de prueba trae artículos sembrados
        db.execute("DELETE FROM lista_prioridades")
        db.commit()


@pytest.fixture(autouse=True)
def _lista_vacia(test_db):
    _vaciar()


@pytest.fixture
def client(test_db, monkeypatch):
    monkeypatch.setattr(pr, 'today_date', lambda: HOY)
    monkeypatch.setattr(fb, 'today_date', lambda: HOY)
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    _vaciar()                              # init_db vuelve a sembrar la lista si la encuentra vacía
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
            s['fin_ok'] = True
        yield c


def _item(nombre, prioridad='Media', precio=1000, mes='', estado='Pendiente', **kw):
    with database.get_db() as db:
        iid = db.execute("""INSERT INTO lista_prioridades (nombre, categoria, prioridad, precio_estimado, mes_objetivo, tienda,
                            estado, precio_real, purchased_at, protocolo_rec, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                         (nombre, kw.get('categoria', 'Hogar'), prioridad, precio, mes, kw.get('tienda', 'Amazon'), estado,
                          kw.get('precio_real', 0), kw.get('purchased_at'), kw.get('protocolo_rec'))).lastrowid
        db.commit()
    return iid


def _ingreso(mes, total):
    with database.get_db() as db:
        db.execute("INSERT INTO budget_meses (mes, ingreso_total, created_at) VALUES (?,?,datetime('now'))", (mes, total))
        db.commit()


def _gasto(fecha, monto, cat):
    with database.get_db() as db:
        db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo) VALUES (?,?,?,?,?,?)",
                   (fecha, 'X', monto, 'BBVA_DEB', cat, 'GASTO'))
        db.commit()


def _vista():
    with database.get_db() as db:
        return pr.vista(db, HOY)


def _ec(n):
    with database.get_db() as db:
        db.execute("INSERT INTO coins_ledger (amount, source, description, date, created_at) VALUES (?,?,?,?,datetime('now'))",
                   (n, 'test', 'saldo', HOY.isoformat()))
        db.commit()


# ── libre_deseos ──────────────────────────────────────────────────────────────
def test_libre_deseos_es_la_meta_de_deseos_menos_lo_gastado(test_db, monkeypatch):
    monkeypatch.setattr(fb, 'today_date', lambda: HOY)
    _ingreso('2026-11', 20000)
    _gasto('2026-11-05', 1500, 'OCIO')         # deseo
    _gasto('2026-11-06', 4000, 'VIVIENDA')     # necesidad: no cuenta
    assert fb.CATEGORIA_BUCKET['OCIO'] == 'deseos' and fb.CATEGORIA_BUCKET['VIVIENDA'] == 'necesidades'
    with database.get_db() as db:
        r = fb.libre_deseos(db, '2026-11')
        bd = fb._calc_budget('2026-11', db)
    assert r == {'meta': 6000.0, 'gastado': 1500.0, 'libre': 4500.0}
    assert r['meta'] == bd['buckets']['deseos']['target_monto']      # el mismo cálculo del presupuesto


def test_sin_ingreso_no_hay_libre_ni_celda(client):
    _item('Silla', mes='2026-11')
    with database.get_db() as db:
        assert fb.libre_deseos(db, '2026-11') is None
    html = client.get('/finanzas/prioridades/').get_data(as_text=True)
    assert 'id="pr-este-cell"' not in html and 'id="pr-pend"' in html and 'id="pr-anio"' in html


# ── Pantalla ─────────────────────────────────────────────────────────────────
def test_titulo_antetitulo_y_sin_stats(client):
    _item('Silla', precio=1200)
    _item('Lámpara', precio=800)
    _item('Viejo', estado='Comprado', precio_real=500, purchased_at='2026-03-01T10:00:00')
    html = client.get('/finanzas/prioridades/').get_data(as_text=True)
    assert re.search(r'<h1[^>]*>\s*Wishlist\s*</h1>', html)
    assert '2 pendientes · $2,000' in html
    assert 'eu-stat' not in html and 'data-f=' not in html


def test_este_mes_suma_lo_mismo_que_su_grupo_y_va_contra_libre(client):
    _ingreso('2026-11', 20000)
    _gasto('2026-11-05', 1500, 'OCIO')
    a = _item('A', prioridad='Baja', precio=700, mes='2026-11')
    b = _item('B', prioridad='Alta', precio=300, mes='2026-10')        # atrasado → Este mes
    _item('C', precio=5000, mes='2026-12')
    _item('D', precio=9000, mes='2027-03')
    _item('E', precio=100)
    v = _vista()
    g = {x['key']: x for x in v['grupos']}
    assert [i['nombre'] for i in g['este']['items']] == ['B', 'A']    # por prioridad
    assert v['franja']['este_total'] == g['este']['total'] == 1000
    assert [i['nombre'] for i in g['prox']['items']] == ['C']
    assert [i['nombre'] for i in g['despues']['items']] == ['D']
    assert [i['nombre'] for i in g['sin']['items']] == ['E']
    assert v['franja']['libre']['libre'] == 4500
    html = client.get('/finanzas/prioridades/').get_data(as_text=True)
    assert 'id="pr-este-cell"' in html and '<span id="pr-este">$1,000</span>' in html and '$4,500' in html
    assert 'Desde Oct 2026' in html                                     # la fila atrasada lo dice


def test_pendiente_por_prioridad_y_comprado_en_el_anio(client):
    _item('A', prioridad='Alta', precio=1000)
    _item('M', prioridad='Media', precio=500)
    _item('B', prioridad='Baja', precio=250)
    _item('X', estado='Comprado', precio_real=800, purchased_at='2026-02-01T00:00:00')
    _item('Y', estado='Comprado', precio_real=300, purchased_at='2025-12-31T00:00:00')   # otro año
    _item('Z', estado='Descartado')
    f = _vista()['franja']
    assert f['por_prio'] == {'Alta': 1000, 'Media': 500, 'Baja': 250} and f['pend_total'] == 1750
    assert (f['anio_total'], f['anio_count']) == (800, 1)
    html = client.get('/finanzas/prioridades/').get_data(as_text=True)
    assert '<details class="pr-done" data-done="Comprado">' in html and '<details class="pr-done" data-done="Descartado">' in html


def test_fila_con_badges_ec_y_guardarropa(client):
    _ec(10_000)
    iid = _item('Apple Watch', prioridad='Alta', precio=EC_RATE * 10, protocolo_rec='compra_optima')
    caro = _item('Auto', precio=EC_RATE * 100_000)
    with database.get_db() as db:
        db.execute("INSERT INTO wishlist_items (nombre, created_at) VALUES ('apple  watch', datetime('now'))")
        db.commit()
    html = client.get('/finanzas/prioridades/').get_data(as_text=True)
    fila = html[html.index(f'id="pr-it-{iid}"'):html.index(f'id="pr-it-{caro}"')] if html.index(f'id="pr-it-{iid}"') < html.index(f'id="pr-it-{caro}"') \
        else html[html.index(f'id="pr-it-{iid}"'):]
    assert 'eu-badge eu-badge--danger pr-pri' in fila and 'eu-badge--success' in fila and 'Óptima' in fila
    assert 'data-ec="10"' in fila and 'también en Guardarropa' in fila
    assert 'aria-haspopup="menu"' in fila and 'js-comprar' in fila
    resto = html[html.index(f'id="pr-it-{caro}"'):]
    assert 'js-ec' not in resto[:resto.index('</li>')]                # no alcanza


# ── Acciones (endpoints) ─────────────────────────────────────────────────────
def test_mover_de_mes_con_los_endpoints_actuales(client):
    iid = _item('Silla', mes='2026-11', precio=1200)
    d = client.get(f'/finanzas/prioridades/api/get/{iid}').get_json()
    d['mes_objetivo'] = '2027-01'
    assert client.post(f'/finanzas/prioridades/api/update/{iid}', json=d).get_json()['ok']
    v = _vista()
    assert [i['id'] for i in {g['key']: g for g in v['grupos']}['despues']['items']] == [iid]
    assert v['franja']['este_total'] == 0
    assert v['meses_mover'][0]['mes'] == '2026-11' and [m['mes'] for m in v['meses_mover'][1:]] == ['2026-12', '2027-01', '2027-02']


def test_comprado_con_precio_real(client):
    iid = _item('Silla', precio=1200)
    client.post(f'/finanzas/prioridades/api/comprar/{iid}', json={'precio_real': 999})
    f = _vista()['franja']
    assert f['pend_count'] == 0 and f['anio_total'] == 999 and f['anio_count'] == 1


def test_comprar_con_ec_descuenta_y_marca_comprado(client):
    _ec(50)
    iid = _item('Taza', precio=EC_RATE * 20)
    r = client.post(f'/finanzas/prioridades/api/comprar-ec/{iid}').get_json()
    assert r == {'ok': True, 'ec': 20, 'balance': 30}
    with database.get_db() as db:
        it = db.execute("SELECT * FROM lista_prioridades WHERE id=?", (iid,)).fetchone()
        led = db.execute("SELECT amount, source, reference_id FROM coins_ledger WHERE reference_id=? AND amount<0", (iid,)).fetchone()
    assert (it['estado'], it['comprar_con_ec'], it['ec_pagado']) == ('Comprado', 1, 20)
    assert (led['amount'], led['source']) == (-20, 'reward')
    # ya comprado o sin saldo: no se cobra dos veces
    assert client.post(f'/finanzas/prioridades/api/comprar-ec/{iid}').status_code == 404
    caro = _item('Sofá', precio=EC_RATE * 31)
    assert client.post(f'/finanzas/prioridades/api/comprar-ec/{caro}').status_code == 400


def test_sin_fin_ok_redirige(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        for url in ('/finanzas/prioridades/', '/finanzas/prioridades/api/comprar-ec/1'):
            r = c.get(url) if url.endswith('/') else c.post(url)
            assert r.status_code == 302 and r.headers['Location'].endswith('/finanzas/')


def test_js_mueve_sin_recargar_y_recalcula():
    js = open(os.path.join(BASE, 'static', 'js', 'prioridades.js'), encoding='utf-8').read()
    mover = js[js.index("t.classList.contains('js-mover')"):js.index("t.classList.contains('js-edit')")]
    assert 'insertar(' in mover and 'recalc()' in mover and 'reload' not in mover
    assert "'/api/get/'" in mover and "'/api/update/'" in mover
    assert "'/api/comprar-ec/'" in js and 'function recalc' in js and "'ArrowDown'" in js
