"""
test_nav.py — handoff Navegación y encabezados (transversal).

Sprint 1: VIEWS + nav_view (crumb de la vista, título y volver al módulo) y la
macro ui.page_head. Sprint 2: cada ruta de NAV renderiza un solo <h1> igual a
nav_title, sin antetítulos de grupo ni lemas.
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from modules import nav

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        s['fin_ok'] = True
    return c


def _ctx(app, url):
    with app.test_request_context(url):
        return nav.nav_context()


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_vista_suma_crumb_y_vuelve_al_modulo(app):
    c = _ctx(app, '/harma/?vista=bitacora')
    assert c['nav_view'] == 'Bitácora' and c['nav_title'] == 'Bitácora' and c['nav_sub'] == 'Harma'
    assert c['nav_back'] == '/harma/'
    assert c['nav_crumbs'] == [{'label': 'Vida'}, {'label': 'Harma', 'url': '/harma/'}, {'label': 'Bitácora', 'current': True}]


def test_vista_en_subpagina(app):
    c = _ctx(app, '/nutricion/?vista=semana')
    assert c['nav_title'] == 'Semana' and c['nav_sub'] == 'Nutrición' and c['nav_back'] == '/nutricion/'
    assert [x['label'] for x in c['nav_crumbs']] == ['Virtudes', 'Hegemonikon', 'Nutrición', 'Semana']
    assert c['nav_crumbs'][2] == {'label': 'Nutrición', 'url': '/nutricion/'}
    assert _ctx(app, '/logros?tab=historial')['nav_title'] == 'Historial'


def test_vista_desconocida_se_ignora(app):
    c = _ctx(app, '/harma/?vista=nada')
    assert c['nav_view'] is None and c['nav_title'] == 'Harma' and c['nav_back'] == '/'
    assert _ctx(app, '/viajes/?vista=bitacora')['nav_view'] is None
    assert _ctx(app, '/harma/?vista=_param')['nav_view'] is None


def test_page_head(app):
    tpl = "{% import '_ui/macros.html' as ui %}"
    with app.test_request_context('/harma/'):
        sin = app.jinja_env.from_string(tpl + "{{ ui.page_head() }}").render()
        con = app.jinja_env.from_string(tpl + "{% call ui.page_head(eyebrow='Golf · 84,200 km') %}<button>x</button>{% endcall %}").render()
    assert '<h1 class="t-page">Harma</h1>' in sin and 'eu-page-eb' not in sin and 'eu-page-hd-a' not in sin
    assert 'data-cat="harma"' in sin
    assert 'Golf · 84,200 km' in con and '<div class="eu-page-hd-a"><button>x</button></div>' in con
    with app.test_request_context('/logros'):
        assert 'data-cat' not in app.jinja_env.from_string(tpl + "{{ ui.page_head() }}").render()
    css = open(os.path.join(BASE, 'static/css/components.css'), encoding='utf-8').read()
    assert '.eu-page-hd[data-cat] .eu-page-eb{color:var(--cat-fg)}' in css


# ── Sprint 2: todas las pantallas ────────────────────────────────────────────

# Rutas que no siguen la regla del h1 (ninguna por ahora; aquí irían los
# detalles de entidad que estén en NAV).
EXCLUIR = set()
GRUPOS = ('Virtudes ·', 'Vida ·', 'Tú ·', 'Hoy ·')


def _rutas():
    for g in nav.NAV:
        for it in g['items']:
            yield it['url'], it['label']
            for ch in it.get('children', []):
                yield ch['url'], ch['label']


def _h1s(html):
    return [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.S)]


def _eyebrows(html):
    return [re.sub(r'<[^>]+>', '', e).strip() for e in re.findall(r'<div class="t-eyebrow eu-page-eb">(.*?)</div>', html, re.S)]


@pytest.mark.parametrize('url,label', list(_rutas()))
def test_un_h1_igual_al_menu(client, url, label):
    if url in EXCLUIR:
        pytest.skip('detalle de entidad')
    r = client.get(url, follow_redirects=True)
    assert r.status_code == 200, url
    html = r.get_data(as_text=True)
    assert _h1s(html) == [label], (url, _h1s(html))
    assert f'<title>{label} — Eudaimonia</title>' in html, url
    for eb in _eyebrows(html):
        assert not eb.startswith(GRUPOS), (url, eb)
        assert eb.count('·') <= 1, (url, eb)          # máximo dos piezas


@pytest.mark.parametrize('url,vista', [('/harma/?vista=bitacora', 'Bitácora'), ('/eurythmia/?vista=musica', 'Música'),
                                       ('/idiomas/?vista=plan', 'Plan'), ('/nutricion/?vista=semana', 'Semana'),
                                       ('/logros?tab=historial', 'Historial')])
def test_vistas_titulan_con_su_nombre(client, url, vista):
    html = client.get(url).get_data(as_text=True)
    assert _h1s(html) == [vista] and f'<title>{vista} — Eudaimonia</title>' in html
    assert f'<span aria-current="page">{vista}</span>' in html


def test_sin_lemas_ni_eyebrows_de_modulo():
    import glob
    for f in glob.glob(os.path.join(BASE, 'templates/**/*.html'), recursive=True) + glob.glob(os.path.join(BASE, 'static/css/*.css')):
        txt = open(f, encoding='utf-8').read()
        assert not re.search(r'\b(hg|id|dt|ey|hm|vj|gr|wl|pl|rc|fb|iv|ci|pr|gv|co|pf)-(lead|eyebrow)\b', txt), f
    assert not any(it['id'] == 'gastos-viaje' for g in nav.NAV for it in g['items'] for it in it.get('children', []))
