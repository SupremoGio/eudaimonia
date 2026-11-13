"""
test_vacios.py — handoff Estados vacíos y primer uso.

Sprint 1: ui.empty(kind=setup|period|filter|done) sin romper las llamadas de
siempre, cero vacíos armados a mano, kind=setup en los módulos sin su dato
base y ?demo=1 de solo lectura.
Sprint 2: «Primeros pasos» (modules/onboarding.py) en Inicio y en Perfil.
"""
import sys, os, re, glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from jinja2 import Environment, FileSystemLoader
import database

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


def _ui():
    return Environment(loader=FileSystemLoader(os.path.join(BASE, 'templates'))).get_template('_ui/macros.html').module


def _get(client, url):
    return client.get(url).get_data(as_text=True)


# ── Sprint 1: el macro ───────────────────────────────────────────────────────

def test_sin_kind_se_ve_igual_que_antes():
    html = str(_ui().empty('gift', 'Aún no hay', 'Crea la primera.', cta='Crear', cta_href='/x', compact=True))
    assert html.startswith('<div class="eu-empty eu-empty--sm">')
    assert '<div class="eu-empty-ic"><i data-lucide="gift"></i></div>' in html
    assert '<div class="t-card">Aún no hay</div>' in html and '<p>Crea la primera.</p>' in html
    assert '<a class="eu-btn eu-btn--primary" href="/x" >Crear</a>' in html
    assert 'data-kind' not in html


def test_los_cuatro_tipos():
    ui = _ui()
    setup = str(ui.empty('car', 'Registra tu vehículo', 'Texto', kind='setup', eyebrow='Harma · primer uso',
                         steps=['Uno', 'Dos'], cta='Agregar', cta_class='js-veh', example_href='?demo=1'))
    assert 'data-kind="setup"' in setup and 'Harma · primer uso' in setup and '<h2 class="eu-empty-t">' in setup
    assert setup.count('<li') == 2 and 'class="eu-btn eu-btn--primary js-veh"' in setup and 'href="?demo=1"' in setup
    period = str(ui.empty('wallet', 'Sin gasto.', 'Sube tu estado.', kind='period', ghost='bars', last='Octubre: $18,420 en 9 categorías.',
                          cta='Subir', cta_href='/finanzas/estados/'))
    assert 'eu-empty--period' in period and 'eu-ghost--bars' in period and 'Octubre: $18,420' in period
    assert 'style=' not in period                                        # el fantasma no usa estilos inline
    filt = str(ui.empty('filter', 'Ninguna prenda.', '', kind='filter', drop_filter={'label': 'Verde', 'count': 4, 'href': '?c=x'}))
    assert 'data-kind="filter"' in filt and 'Sin «Verde» hay 4.' in filt and 'Quitar «Verde»' in filt and 'href="?c=x"' in filt
    done = str(ui.empty('check', 'Inbox en cero', 'Procesaste 7 hoy.', kind='done', xp=5))
    assert 'data-kind="done"' in done and '+5 XP' in done and 'eu-empty-ok' in done


def test_no_quedan_vacios_a_mano():
    malos = []
    for f in glob.glob(os.path.join(BASE, 'templates/**/*.html'), recursive=True) + glob.glob(os.path.join(BASE, 'static/js/*.js')):
        rel = os.path.relpath(f, BASE)
        if rel in ('templates/_ui/macros.html', 'static/js/eu-motion.js') or rel.endswith('.min.js'):
            continue
        txt = open(f, encoding='utf-8').read()
        if 'class="eu-empty-ic"' in txt or "class=\\\"eu-empty-ic" in txt:
            malos.append(rel)
    assert malos == []
    for rel, viejo in (('templates/guardarropa/_hero.html', 'gr-today-n">Aún no hay outfits'),
                       ('templates/finanzas/salud/_bienes.html', '<div class="pt-empty"><p'),
                       ('templates/perfil/_recordatorios.html', 'js-rem-none" hidden>No hay')):
        assert viejo not in open(os.path.join(BASE, rel), encoding='utf-8').read(), rel


def test_kinds_asignados(client):
    assert 'eu-empty--period' in _get(client, '/finanzas/budget/')                 # bucket sin gasto → period
    assert 'data-kind="filter"' in _get(client, '/finanzas/consumo/')               # nomatch → filter
    # Wishlist de Oikonomia: Remates · Wishlist S1 quitó los chips de filtro (agrupa por mes),
    # así que ya no tiene vacío de filtro; con artículos pinta los grupos.
    assert 'data-kind="filter"' not in _get(client, '/finanzas/prioridades/')
    assert 'class="pr-group"' in _get(client, '/finanzas/prioridades/')
    assert 'data-kind="filter"' in _get(client, '/logros')
    assert 'data-kind="setup"' in _get(client, '/perfil/?sec=documentos')           # Documentos → setup
    assert 'data-kind="done"' in _get(client, '/')                                  # radar vacío → done


# ── Sprint 1: primer uso por módulo ──────────────────────────────────────────

@pytest.mark.parametrize('url,cta', [('/harma/', 'js-veh'), ('/guardarropa/', 'js-new-item'), ('/plantas/', 'js-new'),
                                     ('/eurythmia/', 'js-setup-reveal'), ('/idiomas/', 'js-setup-reveal')])
def test_setup_en_modulos_sin_dato_base(client, url, cta):
    html = _get(client, url)
    su = html.split('data-kind="setup"', 1)[1].split('</section>', 1)[0]
    assert 'primer uso' in su and cta in su and 'href="?demo=1"' in su
    assert re.search(r'(data-setup-body|class="(hm|gr|pl|ey)-body")[^>]*hidden', html)          # el contenido se oculta


def test_recompensas_setup_solo_sin_recompensas(client):
    assert 'data-kind="setup"' not in _get(client, '/recompensas/')               # trae las de ejemplo
    with database.get_db() as db:
        db.execute("DELETE FROM rewards")
        db.commit()
    assert 'Recompensas · primer uso' in _get(client, '/recompensas/')


def test_con_datos_no_hay_setup(client):
    with database.get_db() as db:
        db.execute("INSERT INTO plantas (nombre, dias_riego, created_at) VALUES ('Monstera', 7, 'x')")
        db.execute("UPDATE harma_vehiculo SET marca='VW', km_actual=1000")
        db.execute("INSERT INTO wardrobe_items (nombre, created_at) VALUES ('Camisa', 'x')")
        db.commit()
    for url in ('/plantas/', '/harma/', '/guardarropa/'):
        assert 'data-kind="setup"' not in _get(client, url), url


def _conteos():
    with database.get_db() as db:
        tablas = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}


def test_demo_no_escribe_en_la_base(client):
    antes = _conteos()
    for url in ('/harma/', '/guardarropa/', '/recompensas/', '/plantas/', '/eurythmia/', '/idiomas/', '/'):
        html = _get(client, url + '?demo=1')
        assert 'class="eu-demo-band"' in html and 'Ejemplo</b> · nada se guarda' in html and ' data-demo>' in html
    assert _conteos() == antes
    html = _get(client, '/harma/?demo=1')
    assert 'data-kind="setup"' not in html and 'Golf' in html                       # con datos de muestra
    assert 'Monstera' in _get(client, '/plantas/api/state?demo=1')                  # las lecturas del JS también
    assert 'Monstera' not in _get(client, '/plantas/api/state')                     # y la base real sigue vacía
    assert 'eu-demo-band' not in _get(client, '/harma/')


def test_demo_bloquea_escrituras_en_el_cliente():
    lay = open(os.path.join(BASE, 'templates/eu/layout_sub.html'), encoding='utf-8').read()
    assert "if(m!=='GET'&&m!=='HEAD'){" in lay and 'Ejemplo · nada se guarda' in lay and 'demo=1' in lay


# ── Sprint 2: Primeros pasos ─────────────────────────────────────────────────

from modules import onboarding as onb


def _completa():
    with database.get_db() as db:
        db.execute("INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, banco) VALUES ('2026-01-05','X',-10,'GASTO','OCIO','BBVA_DEB')")
        db.execute("INSERT OR REPLACE INTO body_measurements (key, label, value, unit) VALUES ('peso','Peso','78','kg')")
        db.execute("INSERT INTO rewards (name, ec_cost, created_at) VALUES ('Cena en Allium', 40, 'x')")
        db.commit()


def test_pasos_base_vacia_y_completa(test_db, monkeypatch):
    with database.get_db() as db:
        p = {x['id']: x['hecho'] for x in onb.pasos(db)}
    assert list(p) == ['anclas', 'ingreso', 'estado', 'peso', 'recompensa']
    assert p == {'anclas': True, 'ingreso': False, 'estado': False, 'peso': False, 'recompensa': False}   # las anclas vienen sembradas
    _completa()
    monkeypatch.setattr('modules.finanzas.budget._ingresos_mes', lambda *a, **k: {'base': 30000})
    with database.get_db() as db:
        assert all(x['hecho'] for x in onb.pasos(db))


def test_xp_una_vez_y_no_se_quita(test_db):
    with database.get_db() as db:
        e = onb.estado(db)
        assert e['nuevos'] == ['anclas']
        assert onb.estado(db)['nuevos'] == []
    _completa()
    with database.get_db() as db:
        assert set(onb.estado(db)['nuevos']) == {'estado', 'peso', 'recompensa'}
        db.execute("DELETE FROM rewards WHERE name='Cena en Allium'")      # borrar la única propia
        db.commit()
        e = onb.estado(db)
        assert e['nuevos'] == [] and not next(p for p in e['pasos'] if p['id'] == 'recompensa')['hecho']
        pagos = db.execute("SELECT COUNT(*), SUM(amount) FROM xp_ledger WHERE source='onboarding'").fetchone()
    assert tuple(pagos) == (4, 40)


def test_tarjeta_en_inicio_ocultar_y_mostrar(client):
    html = _get(client, '/')
    card = html.split('id="eu-onb"', 1)[1].split('</section>', 1)[0]
    assert 'Primeros pasos · 1/5' in card and 'Siguiente: tu ingreso mensual' in card
    assert card.count('class="eu-onb-row') == 5 and 'js-onb-ocultar' in card
    assert 'class="eu-btn eu-btn--sm eu-btn--primary" href="/finanzas/budget/"' in card       # el siguiente, primario
    assert 'data-onb-quick="peso"' in card                                                  # abre la captura rápida
    assert html.index('id="eu-onb"') < html.index('dash-hero') if 'dash-hero' in html else True
    client.post('/api/onboarding/oculto', json={'oculto': True})
    html = _get(client, '/')
    assert 'eu-onb-off' in html and 'Vuelven en Perfil › Primeros pasos' in html and 'js-onb-mostrar' in html
    client.post('/api/onboarding/oculto', json={'oculto': False})
    assert 'js-onb-ocultar' in _get(client, '/')
    assert 'id="sec-pasos"' in _get(client, '/perfil/?sec=pasos')


def test_cuenta_completa_nunca_ve_la_tarjeta(client, monkeypatch):
    _completa()
    monkeypatch.setattr('modules.finanzas.budget._ingresos_mes', lambda *a, **k: {'base': 30000})
    for _ in range(2):
        html = _get(client, '/')
        assert 'id="eu-onb"' not in html
    assert 'eu-onb-row' in _get(client, '/perfil/?sec=pasos')                      # en Perfil siempre está


def test_listo_se_muestra_una_vez(client, monkeypatch):
    assert 'Primeros pasos · 1/5' in _get(client, '/')                              # la vio con pendientes
    _completa()
    monkeypatch.setattr('modules.finanzas.budget._ingresos_mes', lambda *a, **k: {'base': 30000})
    html = _get(client, '/')
    assert 'Listo. Todo lo diario ya tiene con qué trabajar.' in html and 'Primeros pasos · 5/5' in html
    assert 'id="eu-onb"' not in _get(client, '/')
