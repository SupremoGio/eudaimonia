"""
test_finanzas_viajes_restaurante_salidas.py — VIAJES gana las subcategorias
Restaurante y Salidas (config.py::SUBCATEGORIAS). Se ofrecen en el SPA vía
/api/categories, el validador de subcategoria las acepta y el desglose del
viaje las suma a Comida y Experiencias respectivamente.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados.config import SUBCATEGORIAS


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def test_viajes_tiene_restaurante_y_salidas():
    assert "Restaurante" in SUBCATEGORIAS["VIAJES"]
    assert "Salidas" in SUBCATEGORIAS["VIAJES"]
    assert SUBCATEGORIAS["VIAJES"][-1] == "Otros"


def test_api_categories_las_ofrece(client):
    cats = {c["categoria"]: c["subcategorias"] for c in client.get("/finanzas/estados/api/categories").get_json()}
    assert {"Restaurante", "Salidas"} <= set(cats["VIAJES"])


def test_desglose_de_viaje(client):
    with database.get_db() as db:
        cur = db.execute("INSERT INTO viajes (nombre, fecha_inicio, fecha_fin, created_at)"
                         " VALUES ('CDMX', '2026-09-01', '2026-09-03', '2026-09-01')")
        trip = cur.lastrowid
        for sub, monto in (("Restaurante", 300), ("Comida", 100), ("Salidas", 250)):
            db.execute(
                "INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco, viaje_id)"
                " VALUES ('2026-09-01', ?, ?, 'GASTO', 'VIAJES', ?, 'BBVA_TDC', ?)",
                (f"GASTO {sub}", monto, sub, trip))
        db.commit()
    r = client.get(f"/finanzas/estados/api/trips/{trip}/summary").get_json()
    por_concepto = {b["concepto"]: b["total"] for b in r["breakdown"]}
    assert por_concepto["Comida"] == 400
    assert por_concepto["Experiencias"] == 250
