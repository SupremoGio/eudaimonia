"""
test_finanzas_sprint5_ui_edicion.py — cubre el Sprint 5 ORIGINAL ("Edición en
la UI"): el backend que el frontend (estados.js) ahora usa para exponer
reembolso_cat/estatus_reembolso/fecha_reembolso y viaje_id en el modal de
editar transacción.

viaje_id ya tenía soporte en PATCH /api/transactions/<id> (Sprint anterior);
lo que faltaba era estatus_reembolso/fecha_reembolso -- antes solo se podían
fijar indirectamente vía /api/expenses/<id>/conciliar (Sprint 3), nunca a
mano desde el modal de edición (p. ej. para revertir un PAGADO a PENDIENTE,
o marcarlo PAGADO sin haber pasado por una sugerencia de conciliación).

Verificado también de punta a punta en un navegador real (Playwright) contra
una DB de desarrollo local antes de este commit: modal de edición mostrando
Viaje/Reembolso, y el panel de import mostrando avisos_msi/
sugerencias_viaje_tabasco/sugerencias_reembolso con botones Asignar/
Conciliar funcionales -- no repetido aquí porque ese flujo ya lo cubren los
tests de _sugerir_viaje_tabasco/_sugerir_reembolsos en
test_finanzas_sprint3_reglas_importar.py; este archivo solo cubre el PATCH
directo que el modal ahora puede disparar.
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


def _create_expense(client):
    resp = client.post(
        "/finanzas/estados/api/transactions",
        json={
            "fecha": "2026-01-01",
            "descripcion": "EXPENSE VUELO CLIENTE",
            "monto": -1000.0,
            "tipo": "GASTO",
            "categoria": "EXPENSE",
        },
    )
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        return db.execute(
            "SELECT id FROM est_movimientos WHERE descripcion='EXPENSE VUELO CLIENTE'"
        ).fetchone()["id"]


def test_patch_sets_estatus_reembolso_and_fecha(client):
    tx_id = _create_expense(client)
    resp = client.patch(
        f"/finanzas/estados/api/transactions/{tx_id}",
        json={"estatus_reembolso": "PAGADO", "fecha_reembolso": "2026-01-20"},
    )
    assert resp.status_code == 200

    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT estatus_reembolso, fecha_reembolso FROM est_movimientos WHERE id=?", (tx_id,)
        ).fetchone()
    assert row["estatus_reembolso"] == "PAGADO"
    assert row["fecha_reembolso"] == "2026-01-20"


def test_patch_can_revert_estatus_reembolso_to_pendiente(client):
    tx_id = _create_expense(client)
    client.patch(f"/finanzas/estados/api/transactions/{tx_id}",
                 json={"estatus_reembolso": "PAGADO", "fecha_reembolso": "2026-01-20"})

    resp = client.patch(
        f"/finanzas/estados/api/transactions/{tx_id}",
        json={"estatus_reembolso": "PENDIENTE", "fecha_reembolso": ""},
    )
    assert resp.status_code == 200

    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT estatus_reembolso, fecha_reembolso FROM est_movimientos WHERE id=?", (tx_id,)
        ).fetchone()
    assert row["estatus_reembolso"] == "PENDIENTE"
    assert row["fecha_reembolso"] is None


def test_patch_without_estatus_reembolso_key_leaves_it_untouched(client):
    tx_id = _create_expense(client)
    client.patch(f"/finanzas/estados/api/transactions/{tx_id}",
                 json={"estatus_reembolso": "PAGADO", "fecha_reembolso": "2026-01-20"})

    resp = client.patch(
        f"/finanzas/estados/api/transactions/{tx_id}",
        json={"descripcion": "EXPENSE VUELO CLIENTE (editado)"},
    )
    assert resp.status_code == 200

    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT estatus_reembolso, descripcion FROM est_movimientos WHERE id=?", (tx_id,)
        ).fetchone()
    assert row["estatus_reembolso"] == "PAGADO"  # no tocado -- la clave no vino en el PATCH
    assert row["descripcion"] == "EXPENSE VUELO CLIENTE (editado)"


def test_patch_can_set_and_clear_viaje_id(client):
    client.post(
        "/finanzas/estados/api/trips",
        json={"nombre": "Viaje de prueba", "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-10"},
    )
    import database
    with database.get_db() as db:
        trip_id = db.execute("SELECT id FROM viajes WHERE nombre='Viaje de prueba'").fetchone()["id"]

    tx_id = _create_expense(client)
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"viaje_id": trip_id})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT viaje_id FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row["viaje_id"] == trip_id

    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"viaje_id": ""})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT viaje_id FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row["viaje_id"] is None
