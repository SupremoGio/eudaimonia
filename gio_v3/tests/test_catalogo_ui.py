"""
test_catalogo_ui.py — handoff A11y + catálogo, Sprint 3: /_ui y COMPONENTES.md.
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import pytest
import gen_componentes_md as gm

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(test_db, monkeypatch):
    monkeypatch.delenv('FLASK_ENV', raising=False)
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _nombres():
    return re.findall(r'\{%-?\s*macro\s+(\w+)\s*\(', open(os.path.join(BASE, 'templates/_ui/macros.html'), encoding='utf-8').read())


def test_ui_es_404_en_produccion(client):
    assert client.get('/_ui').status_code == 404


def test_ui_con_un_ejemplo_por_macro(client, monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'development')
    r = client.get('/_ui')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    nombres = _nombres()
    assert len(nombres) >= 19
    for n in nombres:
        assert f'id="m-{n}"' in html, n                                     # una sección por macro
        assert f'<code class="ct-sig">ui.{n}(' in html, n                     # con su firma
    for parte in ('id="fundamentos"', 'data-cr="--fg-3"', 'data-ct-theme="light"', 'id="patrones"', 'data-cat="harma"'):
        assert parte in html, parte
    assert html.count('<h1') == 1                                             # el ejemplo de page_head no es otro h1


def test_ui_para_admin(client):
    with client.session_transaction() as s:
        s['is_admin'] = True
    assert client.get('/_ui').status_code == 200


def test_macro_sin_comentario_hace_fallar():
    texto = "{# Botón. #}\n{% macro button(a) -%}x{%- endmacro %}\n\n{% macro nueva(b) -%}y{%- endmacro %}"
    assert gm.macros_sin_comentario(texto) == ['nueva']
    assert gm.macros_sin_comentario() == []                                  # el repo: todas documentadas


def test_componentes_md_al_dia(tmp_path, monkeypatch):
    monkeypatch.setattr(gm, 'DOC', str(tmp_path / 'COMPONENTES.md'))
    gm.generar()
    nuevo = (tmp_path / 'COMPONENTES.md').read_text(encoding='utf-8')
    actual = open(os.path.join(os.path.dirname(BASE), 'docs', 'COMPONENTES.md'), encoding='utf-8').read()
    assert nuevo == actual, 'regenera docs/COMPONENTES.md con scripts/gen_componentes_md.py'
    for n in _nombres():
        assert f'## `{n}`' in nuevo
