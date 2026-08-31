"""
Tests for the AJUSTE (adjustment) direction in modules/finanzas/inversiones.py.

Ajuste lets the saldo estimado be reconciled against the real platform
balance (an untracked withdrawal, fees, market gain/loss) without
polluting the "aportado" total. Unlike the other three directions, its
monto can be negative.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_eudaimonia.db")
    monkeypatch.setattr(database, "_DB_PATH", db_file)
    monkeypatch.setattr(database, "_USE_HYBRID", False)
    database.init_db()

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def test_negative_ajuste_reduces_saldo_without_touching_aportado(client):
    r = client.post("/finanzas/inversiones/api/mov", json={
        "fecha": "2026-08-01", "plataforma": "GBM", "direccion": "APORTACION",
        "monto": 1000, "descripcion": "aportacion inicial",
    })
    assert r.status_code == 200 and r.json["ok"]

    # Retiro real no capturado por ningún parser: se corrige con un ajuste
    # negativo en vez de intentar reconstruir un movimiento que no existe.
    r = client.post("/finanzas/inversiones/api/mov", json={
        "fecha": "2026-08-15", "plataforma": "GBM", "direccion": "AJUSTE",
        "monto": -300, "descripcion": "retiro no capturado",
    })
    assert r.status_code == 200 and r.json["ok"]

    r = client.get("/finanzas/inversiones/")
    assert r.status_code == 200
    html = r.data.decode()

    # saldo = 1000 (aportado) - 0 (retirado) + 0 (rendimiento) - 300 (ajuste) = 700
    assert "$700" in html
    # aportado sigue siendo 1000 — el ajuste no lo contamina
    assert "$1,000" in html


def test_positive_ajuste_increases_saldo(client):
    client.post("/finanzas/inversiones/api/mov", json={
        "fecha": "2026-08-01", "plataforma": "CETES", "direccion": "APORTACION",
        "monto": 500, "descripcion": "aportacion",
    })
    r = client.post("/finanzas/inversiones/api/mov", json={
        "fecha": "2026-08-10", "plataforma": "CETES", "direccion": "AJUSTE",
        "monto": 50, "descripcion": "ganancia no reflejada",
    })
    assert r.status_code == 200 and r.json["ok"]

    r = client.get("/finanzas/inversiones/")
    assert "$550" in r.data.decode()


def test_zero_ajuste_is_rejected(client):
    r = client.post("/finanzas/inversiones/api/mov", json={
        "fecha": "2026-08-01", "plataforma": "GBM", "direccion": "AJUSTE",
        "monto": 0, "descripcion": "sin efecto",
    })
    assert r.status_code == 400
    assert "error" in r.json


def test_non_ajuste_direction_still_rejects_negative_monto(client):
    r = client.post("/finanzas/inversiones/api/mov", json={
        "fecha": "2026-08-01", "plataforma": "GBM", "direccion": "APORTACION",
        "monto": -100, "descripcion": "no deberia aceptarse",
    })
    assert r.status_code == 400
