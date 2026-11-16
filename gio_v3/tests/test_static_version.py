"""Versión en la URL de los estáticos (?v=<hash del contenido>).

Sin versión, el iPhone (sobre todo la app instalada en la pantalla de inicio)
podía seguir usando un app.css viejo tras un deploy: el modo noche «carbón
cálido» no aparecía en móvil. Si el archivo cambia, cambia la URL."""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def app(test_db):
    from app import create_app
    a = create_app()
    a.config.update(TESTING=True)
    return a


def test_head_versiona_css_js_iconos_y_manifest(app):
    html = app.test_client().get('/login').get_data(as_text=True)
    urls = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    assert urls and all(re.search(r'\?v=[0-9a-f]{10}$', u) for u in urls), urls
    for f in ('css/app.css', 'css/tailwind-built.css', 'manifest.json', 'icons/apple-touch-icon.png'):
        assert any(u.startswith('/static/' + f + '?v=') for u in urls), f
    assert 'href="/static/css/app.css"' not in html


def test_la_version_cambia_con_el_contenido(app, tmp_path, monkeypatch):
    from flask import url_for
    f = tmp_path / 'x.css'
    f.write_text('a{}')
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    with app.test_request_context():
        v1 = url_for('static', filename='x.css')
        f.write_text('a{color:red}')
        os.utime(f, (1, 1))                      # mtime distinto → recalcula
        v2 = url_for('static', filename='x.css')
        assert v1 != v2 and v1.startswith('/static/x.css?v=')
        assert url_for('static', filename='no-existe.css') == '/static/no-existe.css'


def test_la_url_versionada_sirve_el_archivo(app):
    c = app.test_client()
    html = c.get('/login').get_data(as_text=True)
    css = re.search(r'href="(/static/css/app.css\?v=[^"]+)"', html).group(1)
    r = c.get(css)
    assert r.status_code == 200 and b'--ink-950:#0C0B09' in r.data
