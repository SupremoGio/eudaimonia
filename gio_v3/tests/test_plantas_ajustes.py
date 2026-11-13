"""
test_plantas_ajustes.py — handoff Plantas y Ajustes.

Plantas S1: «hoy» en el estado (vencidos/urgentes por atraso), tarjeta «Hoy»,
filtro por entorno y cuadrícula compacta; sin stats ni chips de estado.
Plantas S2: panel con pestañas (Cuidados · Fotos · Historial · Doctor),
m-planta corto con «Avanzado», sin el modal m-doctor.
Ajustes S1: grupos, POST /perfil/api/ajustes con lista blanca, exportar CSV.
"""
import sys, os, io, zipfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
            s['fin_ok'] = True
        yield c


def _planta(nombre, dias_riego=7, regada_hace=0, entorno='interior'):
    hoy = today_date()
    with database.get_db() as db:
        pid = db.execute("""INSERT INTO plantas (nombre, dias_riego, meses_trasplante, last_riego, last_trasplante, entorno, created_at)
                            VALUES (?,?,12,?,?,?,?)""",
                         (nombre, dias_riego, (hoy - timedelta(days=regada_hace)).isoformat(), hoy.isoformat(), entorno,
                          (hoy - timedelta(days=400)).isoformat())).lastrowid
        db.commit()
    return pid


def _hoy(client):
    return client.get('/plantas/api/state').get_json()['hoy']


# ── Plantas S1 ───────────────────────────────────────────────────────────────

def test_hoy_ordenado_por_atraso_y_riego_primero(client, monkeypatch):
    import modules.plantas.routes as pr
    monkeypatch.setattr(pr, 'seasonal_factor', lambda m, e: {'factor': 1.0, 'label': ''})
    a = _planta('Lavanda', 4, regada_hace=4, entorno='balcon')      # toca hoy
    b = _planta('Geranio', 3, regada_hace=5, entorno='balcon')      # tocaba hace 2 d
    _planta('Monstera', 8, regada_hace=1)                            # al día: no entra
    with database.get_db() as db:
        db.execute("INSERT INTO plantas_cuidados (planta_id, tipo, cada_dias, last_fecha, created_at) VALUES (?, 'rotar', 7, ?, 'x')",
                   (a, (today_date() - timedelta(days=7)).isoformat()))
        db.commit()
    hoy = _hoy(client)
    assert [(h['nombre'], h['tipo']) for h in hoy] == [('Geranio', 'riego'), ('Lavanda', 'riego'), ('Lavanda', 'rotar')]
    h = hoy[0]
    assert h['planta_id'] == b and h['status'] == 'vencido' and h['dias'] == -2 and h['pospuesto_ok'] is True
    assert h['regla'] == 'cada 3 d' and hoy[2]['pospuesto_ok'] is False


def test_marcar_en_hoy_lo_quita(client):
    pid = _planta('Pothos', 5, regada_hace=6)
    assert any(h['planta_id'] == pid for h in _hoy(client))
    d = client.post(f'/plantas/api/plantas/{pid}/cuidado/riego').get_json()
    assert d['ok'] and not any(h['planta_id'] == pid for h in d['state']['hoy'])   # el estado nuevo ya no la trae


def test_pagina_hoy_filtro_y_cuadricula(client):
    _planta('Pothos', 5, regada_hace=6)
    _planta('Romero', 5, regada_hace=1, entorno='balcon')
    html = client.get('/plantas/').get_data(as_text=True)
    assert 'id="pl-hoy"' in html and '<h2 class="pl-hoy-t" id="pl-hoy-t">Hoy</h2>' in html
    assert '2 plantas · 1 por atender hoy' in html                                 # eyebrow: pendientes de hoy
    assert 'data-env="todas"' in html and 'data-env="interior"' in html and 'data-env="balcon"' in html
    for fuera in ('pl-status', 'eu-stat', 'data-f="pendientes"', 'data-f="al_dia"', 'aside class="eu-card eu-card--inset pl-season"'):
        assert fuera not in html, fuera
    assert 'id="pl-hoy-data"' in html and 'id="pl-grid"' in html
    js = open(os.path.join(BASE, 'static/js/plantas.js'), encoding='utf-8').read()
    assert "n >= 2 ?" in js and "Regar las ' + n" in js                             # la barra solo con 2 o más
    assert "data-grupo=" in js and "/api/riego-grupo" in js                         # mismo endpoint
    css = open(os.path.join(BASE, 'static/css/plantas.css'), encoding='utf-8').read()
    assert '.pl-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))' in css
    assert 'grid-template-columns:repeat(4,minmax(0,1fr))' in css


def test_todas_al_dia(client):
    _planta('Monstera', 8, regada_hace=1)
    assert _hoy(client) == []
    js = open(os.path.join(BASE, 'static/js/plantas.js'), encoding='utf-8').read()
    assert 'Todas al día.' in js and 'Siguiente: ' in js


# ── Plantas S2 ───────────────────────────────────────────────────────────────

def test_panel_con_pestanas_y_sin_modal_doctor(client, monkeypatch):
    _planta('Monstera')
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    html = client.get('/plantas/').get_data(as_text=True)
    panel = html.split('id="pl-panel"', 1)[1].split('</aside>', 1)[0]
    for t in ('Cuidados', 'Fotos', 'Historial', 'Doctor'):
        assert f'>{t}</button>' in panel, t
    for movido in ('id="pl-fotos"', 'id="pl-hist"', 'id="pl-otra"', 'id="dr-texto"', 'js-dr-go', 'js-cx-go'):
        assert movido in panel, movido
    assert 'id="m-doctor"' not in html
    assert 'role="tablist"' in panel and 'js-pp-close' in panel and 'js-pp-edit' in panel
    monkeypatch.delenv('GEMINI_API_KEY')
    assert 'pl-tab-doctor' not in client.get('/plantas/').get_data(as_text=True)    # sin IA, sin pestaña


def test_modal_corto_con_avanzado(client):
    _planta('Monstera')
    html = client.get('/plantas/').get_data(as_text=True)
    modal = html.split('id="m-planta"', 1)[1]
    adv = modal.split('id="pl-avanzado"', 1)[1].split('</details>', 1)[0]
    for k in ('pl-dias-riego', 'pl-meses-trasplante', 'pl-extra', 'pl-sugerencia'):
        assert k in adv, k
    antes = modal.split('id="pl-avanzado"', 1)[0]
    for k in ('pl-photo-input', 'pl-nombre', 'pl-especie', 'pl-ubicacion', 'pl-entorno', 'pl-luz', 'pl-notas', 'pl-taxa'):
        assert k in antes, k
    assert 'pl-fotos-strip' not in modal.split('</form>', 1)[0] and 'pl-hist-list' not in modal.split('</form>', 1)[0]
    assert 'id="pl-delete-btn"' in modal
    js = open(os.path.join(BASE, 'static/js/plantas.js'), encoding='utf-8').read()
    assert "$('pl-avanzado').open = !p.id" in js                                    # abierto solo en el alta
    # Esc cierra y devuelve el foco: desde A11y S2 lo maneja euDialog (onClose enfoca la tarjeta)
    assert 'window.euDialog.open(pan' in js and 'onClose' in js and 'closePanel' in js
    assert 'if (t) t.focus()' in js


# ── Ajustes S1 ───────────────────────────────────────────────────────────────

def test_ajustes_por_grupos(client):
    html = client.get('/perfil/?sec=ajustes').get_data(as_text=True)
    sec = html.split('id="sec-ajustes"', 1)[1].split('</section>', 1)[0]
    for g in ('Apariencia', 'Avisos', 'Captura rápida', 'Inicio', 'Datos', 'Zona de peligro'):
        assert g in sec, g
    assert 'data-aj="avisos_off:harma"' in sec and 'data-aj="avisos_off:logros"' in sec
    assert 'data-aj="quick_orden_uso"' in sec and 'data-aj="quick_off:peso"' in sec
    assert 'data-aj="onb_oculto"' in sec and 'href="/perfil/api/exportar"' in sec
    assert 'id="reset-trigger"' in sec
    assert 'href="/perfil/?sec=ajustes#avisos">Preferencias' in html                 # enlace del panel de avisos


def test_lista_blanca(client):
    for clave in ('app_ok', 'avisos_off:nope', 'quick_off:nope', 'turso_token', ''):
        assert client.post('/perfil/api/ajustes', json={'clave': clave, 'valor': True}).status_code == 400, clave
    assert client.post('/perfil/api/ajustes', json={'clave': 'onb_oculto', 'valor': True}).get_json()['valor'] == '1'


def test_apagar_harma_lo_quita_de_la_campana(client):
    from modules import avisos as av
    with database.get_db() as db:
        db.execute("UPDATE harma_vehiculo SET marca='VW', km_actual=90000")
        db.execute("UPDATE harma_plan_items SET last_km=0, last_date='2020-01-01'")
        db.commit()
    assert any(a['fuente'] == 'harma' for a in client.get('/api/avisos').get_json()['hoy'])
    r = client.post('/perfil/api/ajustes', json={'clave': 'avisos_off:harma', 'valor': True}).get_json()
    assert r['ok'] and r['conteo_hoy'] is not None
    assert not any(a['fuente'] == 'harma' for a in client.get('/api/avisos').get_json()['hoy'])


def test_captura_oculta_y_orden(client):
    from modules import nav, quick
    client.post('/perfil/api/ajustes', json={'clave': 'quick_off:peso', 'valor': True})
    with database.get_db() as db:
        ocultos, por_uso = quick.preferencias(db)
    assert ocultos == {'peso'} and por_uso
    ids = [q['id'] for q in nav.quick_for({'fin_ok': True}, {'km': 9}, ocultos, por_uso)]
    assert 'peso' not in ids and ids[0] == 'km'
    ids = [q['id'] for q in nav.quick_for({'fin_ok': True}, {'km': 9}, ocultos, False)]
    assert ids[0] == nav.QUICK[0]['id']                                               # sin orden por uso
    assert 'data-quick="peso"' not in client.get('/').get_data(as_text=True)


def test_exportar_csv_zip(client):
    _planta('Monstera')
    r = client.get('/perfil/api/exportar')
    assert r.status_code == 200 and r.mimetype == 'application/zip'
    z = zipfile.ZipFile(io.BytesIO(r.data))
    nombres = set(z.namelist())
    assert {'plantas.csv', 'est_movimientos.csv', 'gtd_tasks.csv'} <= nombres
    assert 'app_settings.csv' not in nombres and not any('vault' in n for n in nombres)
    assert 'Monstera' in z.read('plantas.csv').decode('utf-8-sig')
    with client.session_transaction() as s:
        s['fin_ok'] = False
    assert client.get('/perfil/api/exportar').status_code == 403
