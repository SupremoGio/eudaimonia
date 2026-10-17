"""Asesor de compra IA del guardarropa — Gemini mockeado, sin red."""
import json
import pytest

import database
from modules.guardarropa import routes


FAKE = {
    'veredicto': 'esperar', 'confianza': 78, 'titular': 'Espera al Buen Fin',
    'resumen': 'Ya tienes 2 playeras deportivas en buen estado.',
    'precio': {'evaluacion': 'caro', 'rango_mercado': '$450–$650 MXN', 'precio_objetivo': '$420'},
    'mejor_momento': 'Buen Fin (mediados de noviembre)', 'ahorro_esperando': '~$180',
    'factores': [{'nombre': 'Redundancia', 'impacto': 'negativo', 'detalle': 'Similar a Dry-fit negra'}],
    'similares_en_armario': ['Playera Dry-fit negra'], 'combina_con': ['Short negro'],
    'costo_por_uso_est': '$12 por uso', 'alternativas': [], 'consejo_final': 'Agrégala a la wishlist.',
}


@pytest.fixture
def client(test_db, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with database.get_db() as db:
        db.execute("INSERT INTO wardrobe_items (nombre,categoria,marca,veces_usado,created_at) "
                   "VALUES ('Playera Dry-fit negra','Camiseta','Nike',30,'2026-01-01')")
        db.commit()
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


def test_advisor_uses_grounded_search_and_wardrobe(client, monkeypatch):
    seen = {}

    def fake_search(prompt, max_tokens=4096):
        seen['prompt'] = prompt
        return 'Aquí va:\n' + json.dumps(FAKE), [{'title': 'Liverpool', 'url': 'https://liverpool.com.mx/x'}]

    monkeypatch.setattr(routes, '_gemini_search', fake_search)
    r = client.post('/guardarropa/api/purchase-advisor',
                    json={'prenda': 'Playera Under Armour Tech 2.0', 'precio': 599})
    d = r.get_json()
    assert r.status_code == 200 and d['ok']
    assert d['veredicto'] == 'esperar'
    assert d['sources'][0]['title'] == 'Liverpool'
    assert 'Playera Dry-fit negra' in seen['prompt']
    assert 'Under Armour' in seen['prompt'] and '$599' in seen['prompt']


def test_advisor_falls_back_without_search(client, monkeypatch):
    def boom(*a, **k):
        raise ValueError('Gemini HTTP 400')
    monkeypatch.setattr(routes, '_gemini_search', boom)
    monkeypatch.setattr(routes, '_gemini', lambda p, max_tokens=4096: json.dumps({**FAKE, 'veredicto': 'raro'}))
    d = client.post('/guardarropa/api/purchase-advisor', json={'prenda': 'Tenis'}).get_json()
    assert d['ok'] and d['sources'] == []
    assert d['veredicto'] == 'esperar'  # valor inválido normalizado


def test_advisor_requires_prenda(client):
    r = client.post('/guardarropa/api/purchase-advisor', json={'prenda': '  '})
    assert r.status_code == 400
