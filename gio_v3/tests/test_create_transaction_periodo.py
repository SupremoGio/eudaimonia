"""
test_create_transaction_periodo.py — covers the `periodo` field on
POST/PATCH /finanzas/estados/api/transactions in
modules/finanzas/estados/routes.py.

create_transaction() used to hardcode periodo='' regardless of what the
caller sent, silently dropping it. /admin/audit-montos and
/admin/recover-montos both scope their DB lookup to
WHERE banco='BBVA_DEB' AND periodo=<the exact periodo text stored on
import> — a manually-added transaction meant to fill a gap in an already-
imported statement (recovering a genuine same-day/same-description/
same-monto duplicate the unique index can't tell apart on its own) needs
that same periodo to actually be picked up by the audit, or it looks like
it's still missing even though it exists in the table.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


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


def test_create_transaction_stores_the_given_periodo(client):
    resp = client.post(
        "/finanzas/estados/api/transactions",
        json={
            "fecha": "2025-12-15",
            "descripcion": "PAGO CUENTA DE TERCERO BNET TRANSF A AURORA EL (2)",
            "monto": 150.0,
            "tipo": "GASTO",
            "categoria": "TRANSFERENCIA",
            "banco": "BBVA_DEB",
            "periodo": "07/12/2025 al 06/01/2026",
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["inserted"] == 1

    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT periodo FROM est_movimientos WHERE descripcion=?",
            ("PAGO CUENTA DE TERCERO BNET TRANSF A AURORA EL (2)",),
        ).fetchone()
    assert row["periodo"] == "07/12/2025 al 06/01/2026"


def test_create_transaction_without_periodo_still_defaults_to_empty(client):
    resp = client.post(
        "/finanzas/estados/api/transactions",
        json={"fecha": "2025-01-01", "descripcion": "MANUAL SIN PERIODO", "monto": 50.0},
    )
    assert resp.status_code == 201

    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT periodo FROM est_movimientos WHERE descripcion='MANUAL SIN PERIODO'"
        ).fetchone()
    assert row["periodo"] == ""


def test_patch_transaction_can_fix_a_wrong_periodo(client):
    client.post(
        "/finanzas/estados/api/transactions",
        json={"fecha": "2025-01-01", "descripcion": "FILA A CORREGIR", "monto": 10.0},
    )
    import database
    with database.get_db() as db:
        tx_id = db.execute(
            "SELECT id FROM est_movimientos WHERE descripcion='FILA A CORREGIR'"
        ).fetchone()["id"]

    resp = client.patch(
        f"/finanzas/estados/api/transactions/{tx_id}",
        json={"periodo": "07/01/2025 al 06/02/2025"},
    )
    assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute(
            "SELECT periodo FROM est_movimientos WHERE id=?", (tx_id,)
        ).fetchone()
    assert row["periodo"] == "07/01/2025 al 06/02/2025"
