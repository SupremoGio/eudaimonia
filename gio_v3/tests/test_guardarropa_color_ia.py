"""
test_guardarropa_color_ia.py — el nombre de color que da la IA («Beige Claro»)
se guarda en la prenda si no tenía, para que la distribución de colores agrupe
por ese nombre y no cuente un beige pálido como Amarillo por su hex.
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.guardarropa.routes as gr


@pytest.fixture
def client(test_db, monkeypatch):
    from app import create_app
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    monkeypatch.setattr(gr, '_gemini', lambda *a, **k: json.dumps(
        {'color_name': 'Beige Claro', 'psych': 'p', 'rec': 'r', 'is_sportswear': False, 'sport_note': ''}))
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
    return c


def _prenda(color_name=''):
    with database.get_db() as db:
        cur = db.execute("INSERT INTO wardrobe_items (nombre, categoria, color_hex, color_name, created_at) VALUES (?,?,?,?,?)",
                         ('Veste-chemise Regular Fit', 'Chamarras', '#e6d8a8', color_name, '2026-09-24'))
        db.commit()
        return cur.lastrowid


def _nombre(iid):
    with database.get_db() as db:
        return db.execute("SELECT color_name FROM wardrobe_items WHERE id=?", (iid,)).fetchone()['color_name']


def test_guarda_el_nombre_de_la_ia_si_la_prenda_no_tenia(client):
    iid = _prenda()
    r = client.post(f'/guardarropa/api/item/{iid}/analyze')
    assert r.get_json()['color_name'] == 'Beige Claro'
    assert _nombre(iid) == 'Beige Claro'


def test_no_pisa_el_nombre_que_puso_el_usuario(client):
    iid = _prenda('Arena')
    client.post(f'/guardarropa/api/item/{iid}/analyze')
    assert _nombre(iid) == 'Arena'
