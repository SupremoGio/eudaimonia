"""
test_oikonomia_hub.py — Sprint 1 de Oikonomia v2: /finanzas/ entrega ya
calculado lo que pinta el resumen nuevo (por día, barra 50·30·20 con estado
por bucket, racha, mínimos a 30 días, categorías en riesgo, depósitos sin
clasificar con monto y «siguiente paso»). Las plantillas no cambian.
"""
import sys, os
from contextlib import contextmanager
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import template_rendered

import database
from modules.finanzas import routes as fr


# ── Helpers puros ────────────────────────────────────────────────────────────

def _bd(ingreso=10000, seg=(45, 25, 10), meta_minima=None, cats=()):
    nec, des, aho = seg
    return {
        'ingreso_real': ingreso,
        'seg': {'necesidades': nec, 'deseos': des, 'ahorro_deuda': aho},
        'buckets': {
            'necesidades': {'label': 'Necesidades', 'target_monto': ingreso * .5, 'total_gastado': ingreso * nec / 100, 'cats': list(cats)},
            'deseos': {'label': 'Deseos', 'target_monto': ingreso * .3, 'total_gastado': ingreso * des / 100, 'cats': []},
            'ahorro_deuda': {'label': 'Ahorro y Deudas', 'target_monto': ingreso * .2, 'total_gastado': ingreso * aho / 100,
                             'meta_minima': meta_minima, 'cats': []},
        },
    }


def test_seg_ahorro_bajo_la_meta():
    seg = {s['key']: s for s in fr._hub_seg(_bd(seg=(45, 25, 10)))}
    assert seg['necesidades']['ok'] and seg['necesidades']['kind'] == 'max' and seg['necesidades']['meta_pct'] == 50
    assert seg['deseos']['ok'] and seg['deseos']['meta_pct'] == 30
    aho = seg['ahorro_deuda']
    assert aho['kind'] == 'min' and not aho['ok'] and aho['falta'] == 1000     # meta 2,000 (20%), lleva 1,000


def test_seg_ahorro_sobre_la_meta_y_meta_minima():
    seg = {s['key']: s for s in fr._hub_seg(_bd(seg=(55, 35, 25)))}
    assert not seg['necesidades']['ok'] and not seg['deseos']['ok']            # sobre los topes
    assert seg['ahorro_deuda']['ok'] and seg['ahorro_deuda']['falta'] == 0
    # meta_minima manda sobre target_monto
    aho = {s['key']: s for s in fr._hub_seg(_bd(seg=(40, 20, 25), meta_minima=3000))}['ahorro_deuda']
    assert aho['meta'] == 3000 and not aho['ok'] and aho['falta'] == 500


def test_budget_rows_traen_restante_y_sin_limite():
    cats = [{'nombre': f'C{i}', 'gastado': g, 'limite': 1000, 'tiene_limite': True} for i, g in enumerate([950, 1200, 300, 860, 100, 50])]
    todas = fr._hub_budget_rows(_bd(cats=cats), limit=None)
    assert len(todas) == 6 and len(fr._hub_budget_rows(_bd(cats=cats))) == 5
    by = {r['nombre']: r for r in todas}
    assert by['C1']['restante'] == -200 and by['C0']['restante'] == 50


def _deuda(nombre, dias, minimo=500, pagado=False):
    return {'nombre': nombre, 'dias': dias, 'minimo': minimo, 'cuenta': nombre.lower(), 'pagado': pagado}


def test_next_step_prioridad():
    hoy, pronto, lejos = _deuda('BBVA', 0, 1250), _deuda('Invex', 2), _deuda('HSBC', 20)
    s = fr._hub_next_step([lejos, pronto, hoy], 14, 3210.0)
    assert s['kind'] == 'pago' and s['title'] == 'Pagar BBVA' and s['sub'] == 'vence hoy' and s['monto'] == 1250
    assert s['action'] == 'pago-ciclo' and s['tone'] == 'danger' and s['cuenta'] == 'bbva'
    s = fr._hub_next_step([lejos, pronto], 14, 3210.0)
    assert s['kind'] == 'clasificar' and s['title'] == 'Clasificar 14 depósitos' and s['monto'] == 3210.0 and s['href']
    s = fr._hub_next_step([lejos, pronto], 0, 0)
    assert s['kind'] == 'pago' and s['title'] == 'Pagar Invex' and s['sub'] == 'vence en 2 días'
    assert fr._hub_next_step([lejos], 0, 0) is None
    assert fr._hub_next_step([], 0, 0) is None                                   # sin deudas
    assert fr._hub_next_step([_deuda('BBVA', 0, pagado=True)], 0, 0) is None    # pagada (Sprint 2)


# ── /finanzas/ ───────────────────────────────────────────────────────────────

@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
            s['fin_ok'] = True
        yield app, c


@contextmanager
def _ctx(app):
    got = {}

    def rec(sender, template, context, **kw):
        if template.name == 'finanzas/hub.html':
            got.update(context)
    template_rendered.connect(rec, app)
    try:
        yield got
    finally:
        template_rendered.disconnect(rec, app)


def _mov(fecha, desc, monto, tipo='GASTO', cat='OTROS'):
    with database.get_db() as db:
        db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo) VALUES (?,?,?,?,?,?)",
                   (fecha, desc, monto, 'BBVA_DEB', cat, tipo))
        db.commit()


def test_mes_sin_movimientos_no_cae(client):
    app, c = client
    with _ctx(app) as ctx:
        assert c.get('/finanzas/').status_code == 200
    assert 'next_step' in ctx and 'minimos_30d' in ctx and ctx['minimos_30d'] == 0
    assert ctx['budget_risk'] == [] and ctx['estado_sin_clasificar'] == 0
    b = ctx['budget']
    assert b is None or 'seg' in b


def test_depositos_sin_clasificar_con_monto(client):
    app, c = client
    hoy = date.today().isoformat()
    _mov(hoy, 'SPEI RECIBIDO JUAN', 1200.0, 'INGRESO', 'SPEI_RECIBIDO')
    _mov(hoy, 'DEPOSITO EFECTIVO', 800.0, 'INGRESO', 'DEPOSITO')
    with _ctx(app) as ctx:
        c.get('/finanzas/')
    assert ctx['estado_sin_clasificar'] == 2 and ctx['estado_sin_clasificar_monto'] == 2000.0
    assert ctx['next_step']['kind'] == 'clasificar' and ctx['next_step']['monto'] == 2000.0


def test_mes_actual_con_datos_trae_por_dia_seg_y_racha(client, monkeypatch):
    app, c = client
    import modules.finanzas.budget as fb
    hoy = date(2026, 10, 10)
    for mod in (fr, fb):
        monkeypatch.setattr(mod, 'today_date', lambda: hoy)
    _mov('2026-10-01', 'PAGO DE NOMINA', 20000.0, 'INGRESO', 'NOMINA')
    for i in range(5):
        _mov(f'2026-10-0{i + 2}', f'OXXO {i}', 300.0, 'GASTO', 'ALIMENTACION')
    with _ctx(app) as ctx:
        c.get('/finanzas/')
    b = ctx['budget']
    assert b['mes'] == '2026-10' and [s['key'] for s in b['seg']] == ['necesidades', 'deseos', 'ahorro_deuda']
    assert b['dias_restantes_incl_hoy'] == 22
    assert b['por_dia'] == pytest.approx(b['disponible'] / 22, abs=0.01)
    assert ctx['racha_meses'] is not None and len(ctx['racha_historial']) == 6
    assert 'ahorro_pct' in b                      # se conserva por compatibilidad


def test_mes_cerrado_no_tiene_por_dia(client, monkeypatch):
    """Sin movimientos en el mes en curso el hub muestra el último mes con datos:
    ese mes ya cerró, así que no hay ritmo diario."""
    app, c = client
    import modules.finanzas.budget as fb
    hoy = date(2026, 11, 3)
    for mod in (fr, fb):
        monkeypatch.setattr(mod, 'today_date', lambda: hoy)
    _mov('2026-10-01', 'PAGO DE NOMINA', 20000.0, 'INGRESO', 'NOMINA')
    for i in range(5):                     # «último mes con datos» pide ≥ 5 movimientos
        _mov(f'2026-10-0{i + 2}', f'OXXO {i}', 300.0, 'GASTO', 'ALIMENTACION')
    with _ctx(app) as ctx:
        c.get('/finanzas/')
    b = ctx['budget']
    assert b['mes'] == '2026-10' and b['por_dia'] is None and b['dias_restantes_incl_hoy'] is None


# ── Sprint 3: encabezado y héroe ─────────────────────────────────────────────

def test_encabezado_una_accion_y_ojo_solo_en_topbar(client):
    app, c = client
    full = c.get('/finanzas/').get_data(as_text=True)
    html = full[full.index('<div class="oik" id="oik">'):]          # solo el hub (⌘K también dice «Registrar gasto»)
    html = html[:html.index('<script')]
    assert 'Subir estado de cuenta' in html and 'Registrar gasto' not in html
    html = full
    assert html.count('class="eu-iconbtn js-nw-toggle"') == 1 and 'js-nw-toggle" aria-pressed="false"><i data-lucide="eye-off"' not in html
    assert 'oik-alert' not in html
    assert '<h1 class="t-page">Oikonomia</h1>' in html            # h1 = nombre del menú (Navegación)
    for viejo in ('oik-stat', 'oik-wallet', 'oik-month'):
        assert viejo not in html


def test_heroe_con_datos_y_pago_hoy(client, monkeypatch):
    app, c = client
    import modules.finanzas.budget as fb
    hoy = date(2026, 10, 15)                                  # día de pago de BBVA e Invex
    for mod in (fr, fb):
        monkeypatch.setattr(mod, 'today_date', lambda: hoy)
    import modules.finanzas.pagos_ciclo as pc
    monkeypatch.setattr(pc, 'today_date', lambda: hoy)
    _mov('2026-10-01', 'PAGO DE NOMINA', 20000.0, 'INGRESO', 'NOMINA')
    for i in range(5):
        _mov(f'2026-10-0{i + 2}', f'OXXO {i}', 300.0, 'GASTO', 'ALIMENTACION')
    with database.get_db() as db:
        db.execute("INSERT INTO salud_cuentas (nombre,tipo,institucion,saldo,moneda,activa,created_at) "
                   "VALUES ('BBVA Oro','tarjeta_credito','BBVA',18000,'MXN',1,'x')")
        db.execute("INSERT INTO budget_deudas (nombre,saldo_inicial,saldo_actual,pago_minimo,activa,created_at) "
                   "VALUES ('BBVA Oro',1,1,1250,1,'x')")
        db.commit()
    html = c.get('/finanzas/').get_data(as_text=True)
    assert 'Disponible este mes' in html and 'por día' in html and 'quedan 17 días' in html
    assert 'class="oik-seg"' in html and html.count('class="oik-seg-mark"') == 2
    assert 'meta ≥ 20%' in html and 'faltan' in html                     # sin ahorro este mes
    assert 'Pagar BBVA Oro' in html and 'class="eu-btn eu-btn--primary eu-btn--sm js-pago" data-cuenta="bbva"' in html
    assert 'bajo presupuesto' in html and 'oik-racha-cells' in html
    # Marcar pagado → el siguiente paso ya no es ese pago
    assert c.post('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'}).get_json()['ok']
    assert 'Pagar BBVA Oro' not in c.get('/finanzas/').get_data(as_text=True)


# ── Sprint 4: Próximos pagos y Categorías en riesgo ──────────────────────────

def _hub_section(html, start, end):
    a = html.index(start)
    return html[a:html.index(end, a)]


def test_proximos_pagos_y_pagado(client, monkeypatch):
    app, c = client
    hoy = date(2026, 10, 9)
    import modules.finanzas.pagos_ciclo as pc
    for mod in (fr, pc):
        monkeypatch.setattr(mod, 'today_date', lambda: hoy)
    with database.get_db() as db:
        for n, inst, saldo, mn in [('BBVA Oro', 'BBVA', 18420, 1250), ('Invex', 'Invex', 6880, 520)]:
            db.execute("INSERT INTO salud_cuentas (nombre,tipo,institucion,saldo,moneda,activa,created_at) "
                       "VALUES (?,'tarjeta_credito',?,?,'MXN',1,'x')", (n, inst, saldo))
            db.execute("INSERT INTO budget_deudas (nombre,saldo_inicial,saldo_actual,pago_minimo,activa,created_at) "
                       "VALUES (?,1,1,?,1,'x')", (n, mn))
        db.commit()
    html = _hub_section(c.get('/finanzas/').get_data(as_text=True), 'id="oik-debts-t"', '</section>')
    assert 'Próximos pagos' in html and '<table' not in html
    assert '$1,770' in html                                   # 1,250 + 520 en mínimos a 30 días
    assert 'oct · 6 d' in html and 'saldo <span class="num">' in html
    c.post('/finanzas/api/pago-ciclo', json={'cuenta': 'bbva'})
    html = _hub_section(c.get('/finanzas/').get_data(as_text=True), 'id="oik-debts-t"', '</section>')
    assert 'data-tone="success"' in html and '>pagado<' in html
    assert '$520' in html.split('en mínimos')[0]               # BBVA pagada sale del total


def test_categorias_en_riesgo(client, monkeypatch):
    app, c = client
    monkeypatch.setattr(fr, '_hub_budget_rows', lambda bd, limit=5: [
        {'nombre': 'Restaurantes', 'gastado': 3450, 'meta': 3000, 'pct': 115, 'tone': 'danger', 'restante': -450},
        {'nombre': 'Súper', 'gastado': 5820, 'meta': 6000, 'pct': 97, 'tone': 'warning', 'restante': 180},
        {'nombre': 'Transporte', 'gastado': 1000, 'meta': 2500, 'pct': 40, 'tone': 'brand', 'restante': 1500}])
    _mov(date.today().isoformat(), 'SPEI RECIBIDO', 3210.0, 'INGRESO', 'SPEI_RECIBIDO')
    for i in range(5):
        _mov(date.today().isoformat(), f'OXXO {i}', 100.0, 'GASTO', 'ALIMENTACION')
    html = _hub_section(c.get('/finanzas/').get_data(as_text=True), 'id="oik-bud-t"', '</section>')
    assert 'Categorías en riesgo' in html and 'Ver las 3' in html
    assert '$450</span><span class="nw-mask">••••</span> excedido' in html and 'quedan' in html
    assert 'Transporte' not in html and '1 categoría más en rango' in html
    # El «Siguiente paso» del héroe ya es clasificar: el aviso no se repite aquí.
    assert 'Clasificar →' not in html
    monkeypatch.setattr(fr, '_hub_next_step', lambda *a: None)
    html = _hub_section(c.get('/finanzas/').get_data(as_text=True), 'id="oik-bud-t"', '</section>')
    assert '1 depósito</b>' in html and '$3,210' in html and 'Clasificar →' in html


def test_todo_en_rango(client, monkeypatch):
    app, c = client
    monkeypatch.setattr(fr, '_hub_budget_rows', lambda bd, limit=5: [
        {'nombre': 'Súper', 'gastado': 100, 'meta': 6000, 'pct': 2, 'tone': 'brand', 'restante': 5900}])
    for i in range(5):
        _mov(date.today().isoformat(), f'OXXO {i}', 100.0, 'GASTO', 'ALIMENTACION')
    html = _hub_section(c.get('/finanzas/').get_data(as_text=True), 'id="oik-bud-t"', '</section>')
    assert 'Todo en rango este mes' in html


def test_enlace_a_depositos_sin_clasificar_filtra(client):
    """El enlace «Clasificar» del hub abre Movimientos filtrado (hash que lee
    el SPA) y la API acepta varias categorías separadas por coma."""
    app, c = client
    assert fr.DEPOSITOS_SIN_CLASIFICAR_URL.endswith('#movimientos?tipo=INGRESO&category=DEPOSITO,SPEI_RECIBIDO')
    hoy = date.today().isoformat()
    _mov(hoy, 'SPEI RECIBIDO JUAN', 1200.0, 'INGRESO', 'SPEI_RECIBIDO')
    _mov(hoy, 'DEPOSITO EFECTIVO', 800.0, 'INGRESO', 'DEPOSITO')
    _mov(hoy, 'PAGO DE NOMINA', 20000.0, 'INGRESO', 'NOMINA')
    d = c.get('/finanzas/estados/api/transactions?tipo=INGRESO&category=DEPOSITO,SPEI_RECIBIDO').get_json()
    assert d['total'] == 2 and {r['categoria'] for r in d['data']} == {'DEPOSITO', 'SPEI_RECIBIDO'}
    assert c.get('/finanzas/estados/api/transactions?category=NOMINA').get_json()['total'] == 1
