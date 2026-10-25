"""
test_wishlist_ia.py — análisis IA (asesor de compra) desde la wishlist: se
guarda en el artículo y se puede re-analizar; el veredicto anterior queda
para mostrar cómo cambió. Gemini mockeado, sin red.
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.guardarropa import routes as gr

API = '/guardarropa/wishlist/api'
FAKE = {'veredicto': 'esperar', 'confianza': 70, 'titular': 'Espera al Buen Fin', 'resumen': '...',
        'precio': {'evaluacion': 'caro'}, 'factores': []}


@pytest.fixture
def client(test_db, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


def test_analizar_y_reanalizar(client, monkeypatch):
    prompts, respuestas = [], [FAKE, {**FAKE, 'veredicto': 'comprar'}]
    monkeypatch.setattr(gr, '_gemini_search', lambda p, max_tokens=4096: (prompts.append(p) or json.dumps(respuestas[len(prompts) - 1]), []))
    url = 'https://www.nike.com/mx/t/tenis-nike-free-metcon-7'
    iid = client.post(f'{API}/item', json={'nombre': url, 'categoria': 'Ropa & Calzado', 'precio_estimado': 1799}).get_json()['id']

    r = client.post(f'{API}/item/{iid}/ia', json={}).get_json()
    assert r['ok'] and r['analisis']['veredicto'] == 'esperar' and r['veredicto_anterior'] is None
    assert f'LINK: {url}' in prompts[0] and '$1799' in prompts[0] and 'SU ARMARIO' in prompts[0]

    r = client.post(f'{API}/item/{iid}/ia', json={'motivo': 'Bajó a $1,399'}).get_json()
    assert r['analisis']['veredicto'] == 'comprar' and r['veredicto_anterior'] == 'esperar'
    assert 'Bajó a $1,399' in prompts[1]
    it = [x for x in client.get(f'{API}/items').get_json() if x['id'] == iid][0]
    assert json.loads(it['ia_json'])['veredicto'] == 'comprar' and it['ia_veredicto_anterior'] == 'esperar'


def test_otra_categoria_no_usa_el_armario(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(gr, '_gemini_search', lambda p, max_tokens=4096: (seen.setdefault('p', p) and json.dumps(FAKE), []))
    iid = client.post(f'{API}/item', json={'nombre': 'Kindle Paperwhite', 'categoria': 'Tecnología', 'precio_estimado': 3299}).get_json()['id']
    assert client.post(f'{API}/item/{iid}/ia', json={}).get_json()['ok']
    assert 'SU ARMARIO' not in seen['p'] and 'categoría: Tecnología' in seen['p']


def test_ia_articulo_inexistente(client):
    assert client.post(f'{API}/item/999/ia', json={}).status_code == 404
