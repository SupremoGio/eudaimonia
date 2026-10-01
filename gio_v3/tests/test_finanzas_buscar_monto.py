"""
test_finanzas_buscar_monto.py — el buscador de Movimientos también busca por monto.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _ids(client, q):
    d = client.get('/finanzas/estados/api/transactions', query_string={'search': q, 'per_page': 100}).get_json()
    rows = d.get('data', d) if isinstance(d, dict) else d
    return {r['descripcion'] for r in rows}


def test_busca_por_monto(client):
    with database.get_db() as db:
        for d, m, mp in (('PASTELERIA', -390.0, None), ('CENA', -390.5, None), ('HOTEL', -1500.0, None),
                         ('JOYERIA', -6882.28, None), ('COMPARTIDO', -3000.0, 1000.0), ('PAGO 390 X', -10.0, None)):
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, mi_parte, banco, categoria, tipo)
                          VALUES ('2026-09-10', ?, ?, ?, 'BBVA_TDC', 'OTROS', 'GASTO')""", (d, m, mp))
        db.commit()
    assert _ids(client, '390') == {'PASTELERIA', 'CENA', 'PAGO 390 X'}
    assert _ids(client, '390.50') == {'CENA'}
    assert _ids(client, '$1,500') == {'HOTEL'}
    assert _ids(client, '6882.28') == {'JOYERIA'}
    assert _ids(client, '1000') == {'COMPARTIDO'}          # su parte
    assert _ids(client, 'hotel') == {'HOTEL'}
