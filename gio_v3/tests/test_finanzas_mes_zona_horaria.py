"""
test_finanzas_mes_zona_horaria.py — «este mes» del Resumen se calcula en hora
de México: el 30 de septiembre a las 19:00 en CDMX (1 de octubre en UTC) sigue
siendo septiembre.
"""
import sys, os
from datetime import datetime
from zoneinfo import ZoneInfo

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


def test_mes_en_hora_de_mexico(client, monkeypatch):
    from modules.finanzas.estados import routes
    monkeypatch.setattr(routes, 'now_local',
                        lambda: datetime(2026, 9, 30, 19, 0, tzinfo=ZoneInfo('America/Mexico_City')))
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES ('2026-09-15', 'RENTA', -8000, 'BBVA_DEB', 'VIVIENDA', 'Renta', 'GASTO')""")
        db.commit()
    nat = client.get('/finanzas/estados/api/summary/by-naturaleza').get_json()
    assert round(sum(g['total'] for g in nat), 2) == -8000.0
