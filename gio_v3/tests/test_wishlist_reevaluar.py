"""
test_wishlist_reevaluar.py — un artículo de la wishlist se puede volver a
pasar por el protocolo: guarda el score anterior, cuenta las evaluaciones y
permite corregir los datos del artículo (p. ej. el precio).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database

API = '/guardarropa/wishlist/api'
NO_UTIL = {'dias_deseo': 1, 'q1_persiste': True, 'q2_estado_financiero': 'estable', 'q3_es_util': False}
OPTIMA = {'dias_deseo': 7, 'q1_persiste': True, 'q2_estado_financiero': 'estable', 'q3_es_util': True,
          'q3_tiene_alternativa': False, 'q3_usos_mes': 12, 'q3_cpu_ok': True, 'q3_mantenimiento_ok': True,
          'q3_costo_oportunidad_ok': False}


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _item(iid):
    with database.get_db() as db:
        return dict(db.execute("SELECT * FROM wishlist_items WHERE id=?", (iid,)).fetchone())


def test_reevaluar_guarda_score_anterior_y_corrige_datos(client):
    iid = client.post(f'{API}/item', json={'nombre': 'Nike Free Metcon 7', 'precio_estimado': 1799}).get_json()['id']

    r = client.post(f'{API}/item/{iid}/quiz', json=NO_UTIL).get_json()
    assert r['recomendacion'] == 'no_compres' and r['score_anterior'] is None
    primero = r['score']
    client.post(f'{API}/item/{iid}/decide', json={'decision': 'descartado'})

    # Re-evaluación: ya lleva más días, sí es útil, y bajó de precio.
    r = client.post(f'{API}/item/{iid}/quiz', json={**OPTIMA, 'nombre': 'Nike Free Metcon 7', 'precio_estimado': 1399}).get_json()
    assert r['recomendacion'] == 'compra_optima'
    assert r['score_anterior'] == primero and r['score'] > primero
    it = _item(iid)
    assert it['score_anterior'] == primero and it['evaluaciones'] == 2
    assert it['precio_estimado'] == 1399 and it['estado'] == 'pendiente'   # vuelve a la lista activa


def test_reevaluar_articulo_inexistente(client):
    assert client.post(f'{API}/item/999/quiz', json=OPTIMA).status_code == 404
