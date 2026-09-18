"""
test_finanzas_expense_sin_subcategoria.py — cubre la migración
finanzas_expense_sin_subcategoria_2026_09 y el enforcement en routes.py.

A petición explícita del usuario: EXPENSE es una categoria plana, "va todo
junto en uno solo" — nunca debe tener subcategoria, sin importar por dónde
se escriba (transacción manual, edición, reglas de keyword personalizadas,
o el aplicador de keywords al importar). Se habían acumulado subcategorias
inconsistentes ahí antes de este fix.

_normalize_subcategoria(categoria, subcategoria) en routes.py es el punto
único de la regla; se prueba directo y a través de cada endpoint que
escribe categoria+subcategoria juntos.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.finanzas.estados.routes import _normalize_subcategoria


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


def _insert(db, **kw):
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_TDC', periodo='', categoria='EXPENSE', subcategoria='',
                     tipo='GASTO')
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )


# ── _normalize_subcategoria directo ────────────────────────────────────────

def test_normalize_blanks_subcategoria_for_expense():
    assert _normalize_subcategoria('EXPENSE', 'Reembolsable') == ''
    assert _normalize_subcategoria('EXPENSE', '') == ''


def test_normalize_leaves_other_categorias_untouched():
    assert _normalize_subcategoria('ALIMENTACION', 'Súper') == 'Súper'
    assert _normalize_subcategoria('ROPA', '') == ''


# ── Migración: limpia datos ya existentes ──────────────────────────────────

def test_migration_blanks_existing_expense_subcategorias(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_expense_sin_subcategoria_2026_09'")
        _insert(db, descripcion='EXPENSE VUELO CLIENTE', subcategoria='Reembolsable')
        _insert(db, descripcion='EXPENSE OTRO', subcategoria='Viaje cliente X')
        db.execute("""INSERT INTO est_keywords (keyword, categoria, subcategoria)
                      VALUES ('CLIENTE X', 'EXPENSE', 'Viaje cliente X')""")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        rows = db.execute("SELECT subcategoria FROM est_movimientos WHERE categoria='EXPENSE'").fetchall()
        kw = db.execute("SELECT subcategoria FROM est_keywords WHERE categoria='EXPENSE'").fetchone()
    for r in rows:
        assert r['subcategoria'] == ''
    assert kw['subcategoria'] == ''


def test_migration_does_not_touch_other_categorias(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_expense_sin_subcategoria_2026_09'")
        _insert(db, descripcion='WALMART', categoria='ALIMENTACION', subcategoria='Súper')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE descripcion='WALMART'").fetchone()
    assert row['subcategoria'] == 'Súper'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_expense_sin_subcategoria_2026_09'"
        ).fetchall()
    assert len(rows) == 1


# ── Endpoints: create_transaction / update_transaction ─────────────────────

def test_create_transaction_forces_blank_subcategoria_for_expense(client):
    resp = client.post(
        "/finanzas/estados/api/transactions",
        json={"fecha": "2026-01-01", "descripcion": "EXPENSE NUEVO", "monto": 500.0,
              "categoria": "EXPENSE", "subcategoria": "Viaje cliente"},
    )
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE descripcion='EXPENSE NUEVO'").fetchone()
    assert row["subcategoria"] == ""


def test_update_transaction_forces_blank_subcategoria_for_expense(client):
    client.post("/finanzas/estados/api/transactions",
                json={"fecha": "2026-01-01", "descripcion": "EXPENSE A EDITAR", "monto": 100.0})
    import database
    with database.get_db() as db:
        tx_id = db.execute("SELECT id FROM est_movimientos WHERE descripcion='EXPENSE A EDITAR'").fetchone()["id"]

    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}",
                         json={"categoria": "EXPENSE", "subcategoria": "Algo que no debería quedar"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row["subcategoria"] == ""


def test_update_transaction_keeps_subcategoria_for_other_categorias(client):
    client.post("/finanzas/estados/api/transactions",
                json={"fecha": "2026-01-01", "descripcion": "COMPRA NORMAL", "monto": 100.0})
    import database
    with database.get_db() as db:
        tx_id = db.execute("SELECT id FROM est_movimientos WHERE descripcion='COMPRA NORMAL'").fetchone()["id"]

    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}",
                         json={"categoria": "ALIMENTACION", "subcategoria": "Súper"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row["subcategoria"] == "Súper"


# ── Endpoints: /api/keywords ────────────────────────────────────────────────

def test_create_keyword_forces_blank_subcategoria_for_expense(client):
    resp = client.post("/finanzas/estados/api/keywords",
                        json={"keyword": "VIAJE PROYECTO X", "categoria": "EXPENSE",
                              "subcategoria": "Proyecto X", "apply_to_existing": False})
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute("SELECT subcategoria FROM est_keywords WHERE keyword='VIAJE PROYECTO X'").fetchone()
    assert row["subcategoria"] == ""


def test_create_keyword_applies_blank_subcategoria_to_existing(client):
    client.post("/finanzas/estados/api/transactions",
                json={"fecha": "2026-01-01", "descripcion": "VIAJE PROYECTO Y CLIENTE", "monto": 200.0})
    resp = client.post("/finanzas/estados/api/keywords",
                        json={"keyword": "VIAJE PROYECTO Y", "categoria": "EXPENSE",
                              "subcategoria": "Proyecto Y", "apply_to_existing": True})
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='VIAJE PROYECTO Y CLIENTE'"
        ).fetchone()
    assert row["categoria"] == "EXPENSE"
    assert row["subcategoria"] == ""


def test_apply_all_keywords_forces_blank_subcategoria_for_expense(client):
    import database
    with database.get_db() as db:
        db.execute("""INSERT INTO est_keywords (keyword, categoria, subcategoria)
                      VALUES ('VIAJE PROYECTO Z', 'EXPENSE', 'Proyecto Z')""")
        db.commit()
    client.post("/finanzas/estados/api/transactions",
                json={"fecha": "2026-01-01", "descripcion": "VIAJE PROYECTO Z CLIENTE", "monto": 300.0})

    resp = client.post("/finanzas/estados/api/keywords/apply-all")
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='VIAJE PROYECTO Z CLIENTE'"
        ).fetchone()
    assert row["subcategoria"] == ""
