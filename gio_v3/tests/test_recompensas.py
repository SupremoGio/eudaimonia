"""
test_recompensas.py — handoff Recompensas v2 (/recompensas/).

Sprint 1: ritmo de EC (solo ganados), ETA por recompensa, requisitos con
progreso (nivel / insignia / espera), estado «badge» separado de «level»,
meta y grupos; redeem con saldo antes/después y undo de 10 minutos.
Sprint 2: encabezado + héroe (saldo una sola vez y siguiente meta).
Sprint 3: tres grupos, canje con confirmación, editar/borrar en el modal,
gasto libre plegado y canjes recientes.
Sprint 4: «Desde tus wishlists» (Finanzas solo con fin_ok).
"""
import sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.recompensas import routes as rw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ahora():
    """Reloj de la app (zona de la app) sin tz: así guarda la app sus fechas; datetime.now()
    del servidor (UTC) se desfasa un día cerca de la medianoche."""
    from utils import now_local
    return now_local().replace(tzinfo=None)


def _client(fin_ok=False):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
        if fin_ok:
            sess['fin_ok'] = True
    return c


@pytest.fixture
def client(test_db):
    return _client()


@pytest.fixture(autouse=True)
def sin_suerte(monkeypatch):
    monkeypatch.setattr(rw.random, 'random', lambda: 0.99)     # sin racha de suerte


def _limpia():
    with database.get_db() as db:
        db.execute("DELETE FROM rewards")
        db.commit()


def _ec(amount, days_ago=0, source='t', desc='t', created=None):
    d = (rw.today_date() - timedelta(days=days_ago)).isoformat()
    with database.get_db() as db:
        db.execute("INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at) VALUES (?,?,?,1,?,?)",
                   (amount, source, desc, d, created or datetime.now().isoformat()))
        db.commit()


def _reward(name, cost, **kw):
    cols = {'name': name, 'ec_cost': cost, 'level_required': 1, 'cooldown_days': 0, 'created_at': 'x', **kw}
    with database.get_db() as db:
        rid = db.execute(f"INSERT INTO rewards ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         list(cols.values())).lastrowid
        db.commit()
    return rid


def _get(c):
    return c.get('/recompensas/').get_data(as_text=True)


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_eta_sin_ritmo_y_textos():
    assert rw.eta_dias(30, 0) is None and rw.eta_txt(None) is None
    assert rw.eta_dias(0, 0) == 0
    assert rw.eta_dias(66, 7) == 10
    assert rw.eta_txt(1) == '1 día' and rw.eta_txt(19) == '19 días' and rw.eta_txt(138) == '4.6 meses'


def test_ritmo_solo_ec_ganados(test_db):
    _ec(300)
    _ec(-200)                          # un canje no alarga las ETA
    _ec(90, days_ago=40)               # fuera de los 30 días
    ritmo, semana = rw.ec_ritmo()
    assert ritmo == 10.0 and semana == 300


def test_estado_badge_separado_de_level(test_db):
    _limpia()
    _ec(1000)
    _reward('Kindle', 100, badge_required='fullstack_arete')
    _reward('Viaje', 100, level_required=9)
    t = rw.tienda()
    by = {r['name']: r for r in t['rewards']}
    assert by['Kindle']['status'] == 'badge' and by['Viaje']['status'] == 'level'
    assert by['Kindle']['req']['tipo'] == 'insignia' and by['Kindle']['req']['texto'].startswith('Full-Stack Areté')
    assert by['Viaje']['req']['tipo'] == 'nivel' and by['Viaje']['req']['texto'].startswith('Nivel 9')
    assert [r['name'] for r in t['grupos']['later']] == ['Kindle', 'Viaje']


def test_requisito_nivel_con_eta(test_db):
    _limpia()
    with database.get_db() as db:
        for i in range(30):
            db.execute("INSERT INTO xp_ledger (amount,source,description,multiplier,date,created_at) VALUES (10,'activity','x',1,?,'x')",
                       ((rw.today_date() - timedelta(days=i)).isoformat(),))
        db.commit()
    _reward('Audífonos', 10, level_required=3)          # 300 XP, ritmo 10/día → faltan 600 → 60 d
    r = rw.tienda()['rewards'][0]
    assert r['status'] == 'level' and r['req']['texto'] == 'Nivel 3 · ≈ 2.0 meses' and not r['req']['cerca']


def test_requisito_espera_abreviado(test_db, monkeypatch):
    _limpia()
    _ec(1000)
    _reward('Cine', 15, cooldown_days=7, last_redeemed=(_ahora() - timedelta(days=2)).isoformat())
    r = rw.tienda()['rewards'][0]
    assert r['status'] == 'wait' and r['req'] == {**r['req'], 'tipo': 'espera', 'texto': 'En 5 días'}
    assert rw._espera_corta('Ya van 2 este fin de semana · disponible el sáb 15 nov') == '2/2 · sáb 15'


def test_meta_y_grupos(test_db):
    _limpia()
    _ec(84)
    for i in range(29):
        _ec(7, days_ago=i + 1)         # ritmo ≈ (84 + 203)/30
    _ec(-203)                          # saldo 84; el ritmo solo cuenta lo ganado
    _reward('Café', 5)
    _reward('Masaje', 90)
    _reward('Videojuego', 120)
    _reward('Ropa', 150)
    t = rw.tienda()
    assert [r['name'] for r in t['grupos']['available']] == ['Café']
    assert t['ec_balance'] == 84 and t['ec_daily'] == 9.6
    assert [r['name'] for r in t['grupos']['ec']] == ['Masaje', 'Videojuego', 'Ropa']
    assert t['meta']['name'] == 'Masaje' and t['meta']['ec_left'] == 90 - t['ec_balance']
    assert t['meta']['eta_txt'] == '1 día'                            # faltan 6 a 9.6 EC/día


def test_redeem_saldos_y_undo(client):
    _limpia()
    _ec(100)
    rid = _reward('Cine', 15, cooldown_days=7, weekend_only=0)
    d = client.post(f'/recompensas/api/rewards/{rid}/redeem').get_json()
    assert d['saldo_antes'] == 100 and d['saldo_despues'] == 85
    assert rw._get_ec_balance() == 85
    u = client.post(f'/recompensas/api/redeem/{rid}/undo')
    assert u.status_code == 200 and u.get_json()['ec_balance'] == 100
    with database.get_db() as db:
        row = db.execute("SELECT last_redeemed FROM rewards WHERE id=?", (rid,)).fetchone()
    assert row['last_redeemed'] is None
    assert rw.tienda()['grupos']['available'][0]['name'] == 'Cine'
    assert client.post(f'/recompensas/api/redeem/{rid}/undo').status_code == 409     # nada que deshacer


def test_undo_fuera_de_ventana_409(client):
    _limpia()
    _ec(100)
    rid = _reward('Cine', 15)
    _ec(-15, source='reward', desc='Recompensa: Cine', created=(datetime.now() - timedelta(minutes=11)).isoformat())
    assert client.post(f'/recompensas/api/redeem/{rid}/undo').status_code == 409
    assert rw._get_ec_balance() == 85


def test_undo_revierte_ventana_y_last_redeemed_previo(client, monkeypatch):
    _limpia()
    _ec(100)
    sab = rw.today_date()
    sab = sab + timedelta(days=(5 - sab.weekday()) % 7)
    monkeypatch.setattr(rw, 'today_date', lambda: sab)
    monkeypatch.setattr(rw, 'today_str', lambda: sab.isoformat())
    rid = _reward('Cápsula', 8, weekend_only=1, max_por_ventana=2)
    viejo = (datetime.now() - timedelta(hours=2)).isoformat()
    _ec(-8, source='reward', desc='Recompensa: Cápsula', created=viejo)
    with database.get_db() as db:
        db.execute("UPDATE rewards SET last_redeemed=? WHERE id=?", (viejo, rid))
        db.execute("UPDATE coins_ledger SET date=? WHERE description='Recompensa: Cápsula'", (sab.isoformat(),))
        db.commit()
    assert client.post(f'/recompensas/api/rewards/{rid}/redeem').status_code == 200
    r = {x['id']: x for x in rw.tienda()['rewards']}[rid]
    assert r['usados_ventana'] == 2 and r['status'] == 'wait'
    assert client.post(f'/recompensas/api/redeem/{rid}/undo').status_code == 200
    r = {x['id']: x for x in rw.tienda()['rewards']}[rid]
    assert r['usados_ventana'] == 1 and r['status'] == 'available'
    with database.get_db() as db:
        assert db.execute("SELECT last_redeemed FROM rewards WHERE id=?", (rid,)).fetchone()['last_redeemed'] == viejo


# ── Sprint 2 ─────────────────────────────────────────────────────────────────

def test_encabezado_y_heroe(client):
    _limpia()
    _ec(84)
    _reward('Masaje', 90, cooldown_days=30)
    html = _get(client)
    hd = html.split('<header class="eu-page-hd rw-hd">', 1)[1].split('</header>', 1)[0]   # ui.page_head (Navegación)
    assert '84 EC' in hd and 'Tú ·' not in hd and '<h1 class="t-page">Recompensas</h1>' in hd and 'eu-btn eu-btn--ghost js-new' in hd and 'Recompensa</button>' in hd
    assert 'rw-lead' not in html and 'rw-level' not in html
    assert html.count('class="num fg-ec js-ec"') == 1                     # saldo en un solo bloque
    hero = html.split('id="rw-hero"', 1)[1].split('</section>', 1)[0]
    assert '≈ $<span class="js-ec-mxn">840</span> MXN · 1 EC = $10' in hero
    assert 'Siguiente meta' in hero and 'Masaje' in hero and 'Faltan <b class="num">6 EC</b>' in hero
    assert 'Cada 30 d' in hero
    for f in ('_level.html', '_filters.html'):
        assert not os.path.exists(os.path.join(BASE, 'templates/recompensas', f))


def test_heroe_sin_meta(client):
    _limpia()
    _ec(100)
    _reward('Café', 5)
    assert 'Todo lo periódico está a tu alcance.' in _get(client)


# ── Sprint 3 ─────────────────────────────────────────────────────────────────

def test_tres_grupos_sin_botones_en_tarjetas(client):
    _limpia()
    _ec(50)
    _reward('Café', 5)
    _reward('Masaje', 90)
    _reward('Viaje', 10, level_required=9)
    html = _get(client)
    main = html.split('id="rw-main"', 1)[1].split('<aside', 1)[0]
    assert 'Puedes canjear ahora' in main and 'Reuniendo EC' in main and 'Se abren más adelante' in main
    assert 'Saldo 50 → 45 EC' in main and 'js-confirm' in main and 'js-cancel' in main
    assert 'faltan 40' in main and 'eu-badge rw-req' in main
    assert 'trash-2' not in main and 'pencil' not in main and 'data-filter' not in html
    assert 'Editar o borrar: abre cualquier recompensa.' in main
    modal = html.split('id="rw-modal"', 1)[1]
    assert 'js-del' in modal and 'Eliminar' in modal


def test_nada_disponible(client):
    _limpia()
    _reward('Masaje', 90)
    assert 'Nada disponible por ahora. Tu siguiente meta está arriba.' in _get(client)


def test_gasto_libre_plegado_e_historial(client):
    _limpia()
    for i in range(6):
        _ec(-1, source='gasto', desc=f'Gasto {i}')
    html = _get(client)
    assert '<details class="eu-card rw-spend">' in html and 'Registrar gasto libre' in html
    hist = html.split('id="rw-hist"', 1)[1].split('</section>', 1)[0]
    assert 'Canjes recientes' in hist and hist.count('class="rw-hrow"') == 6
    assert hist.count(' hidden>') == 2 and 'js-hist-all' in hist


def test_js_refresca_sin_recargar():
    js = open(os.path.join(BASE, 'static/js/recompensas.js'), encoding='utf-8').read()
    assert '/undo' in js and 'refresh()' in js and 'location.reload(); }, ' not in js


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def _wish():
    with database.get_db() as db:
        db.execute("INSERT INTO wishlist_items (nombre, precio_estimado, ec_sugerido, estado, created_at) VALUES ('Chamarra de piel', 1800, 175, 'evaluando', 'x')")
        db.execute("INSERT INTO wishlist_items (nombre, precio_estimado, estado, created_at) VALUES ('Ya comprada', 500, 'comprado', 'x')")
        db.execute("DELETE FROM lista_prioridades")
        db.execute("INSERT INTO lista_prioridades (nombre, precio_estimado, estado, created_at) VALUES ('Curso de SQL', 600, 'Pendiente', 'x')")
        db.commit()


def test_wishlists_sin_fin_ok(client):
    _wish()
    _ec(100)
    html = _get(client)
    w = html.split('id="rw-wish-t"', 1)[1].split('</section>', 1)[0]
    assert 'Chamarra de piel' in w and '175 EC' in w and 'href="/guardarropa/wishlist/"' in w
    assert 'Curso de SQL' not in w and 'Ya comprada' not in w
    assert 'faltan 75' in w


def test_wishlists_con_fin_ok(test_db):
    _wish()
    _ec(100)
    w = _get(_client(fin_ok=True)).split('id="rw-wish-t"', 1)[1].split('</section>', 1)[0]
    assert 'Curso de SQL' in w and '60 EC' in w and 'alcanzable' in w and 'href="/finanzas/prioridades/"' in w
    assert w.index('Curso de SQL') < w.index('Chamarra de piel')          # ordenadas por EC


def test_sin_wishlists_no_aparece(client):
    with database.get_db() as db:
        db.execute("DELETE FROM wishlist_items")
        db.commit()
    assert 'Desde tus wishlists' not in _get(client)
