"""
test_finanzas_expense_en_ingreso.py — cubre la corrección a un uso
incorrecto que el usuario confirmó hacer por costumbre: EXPENSE es
exclusivamente para el lado del GASTO (algo que pagas y te van a
reembolsar -- ver estatus_reembolso/_sugerir_reembolsos), pero también le
ponía categoria=EXPENSE al depósito que le regresaba. Como EXPENSE nunca
lleva subcategoria (_normalize_subcategoria), ese ingreso le quedaba "sin
categoría".

_corregir_expense_en_ingreso reclasifica cualquier movimiento
tipo=INGRESO + categoria=EXPENSE a categoria=FINANZAS,
subcategoria='Reembolsable' -- la categoría real pensada para un
reembolso recibido. Se aplica en cuatro puntos de escritura:
  1. create_transaction (alta manual)
  2. update_transaction (PATCH -- categoria y tipo pueden llegar en
     requests separados, así que se revisa el estado ya actualizado)
  3. apply_all_keywords (reaplicar reglas a toda la tabla)
  4. upload_file (reglas de keyword al importar)
Y retroactivamente vía la migración
finanzas_expense_ingreso_reembolsable_2026_09 en database.py.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.finanzas.estados.routes import _corregir_expense_en_ingreso


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
    defaults = dict(fecha='2026-09-01', fecha_cargo=None, descripcion='X', monto=500.0,
                     banco='MANUAL', periodo='', categoria='EXPENSE', subcategoria='',
                     tipo='INGRESO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


# ── _corregir_expense_en_ingreso (unidad) ───────────────────────────────────

def test_corrige_expense_ingreso_a_finanzas_reembolsable():
    cat, sub = _corregir_expense_en_ingreso('EXPENSE', '', 'INGRESO')
    assert cat == 'FINANZAS'
    assert sub == 'Reembolsable'


def test_no_toca_expense_en_gasto():
    """El caso legítimo: EXPENSE sí pertenece a un GASTO."""
    cat, sub = _corregir_expense_en_ingreso('EXPENSE', '', 'GASTO')
    assert cat == 'EXPENSE'
    assert sub == ''


def test_no_toca_otras_categorias_en_ingreso():
    cat, sub = _corregir_expense_en_ingreso('NOMINA', 'Pago nominal', 'INGRESO')
    assert cat == 'NOMINA'
    assert sub == 'Pago nominal'


# ── create_transaction ───────────────────────────────────────────────────────

def test_create_transaction_corrige_expense_en_ingreso(client):
    resp = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-09-01", "descripcion": "ME REGRESARON EL DINERO", "monto": 500.0,
        "tipo": "INGRESO", "categoria": "EXPENSE",
    })
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='ME REGRESARON EL DINERO'"
        ).fetchone()
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'


def test_create_transaction_deja_expense_en_gasto(client):
    resp = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-09-01", "descripcion": "PAGUE ALGO QUE ME VAN A REGRESAR", "monto": 500.0,
        "tipo": "GASTO", "categoria": "EXPENSE",
    })
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='PAGUE ALGO QUE ME VAN A REGRESAR'"
        ).fetchone()
    assert row['categoria'] == 'EXPENSE'
    assert row['subcategoria'] == ''


# ── update_transaction (PATCH) ───────────────────────────────────────────────

def test_update_transaction_corrige_al_poner_categoria_expense_en_ingreso_existente(test_db, client):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, categoria='OTROS', subcategoria='', tipo='INGRESO')
        db.commit()
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"categoria": "EXPENSE"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'


def test_update_transaction_corrige_al_cambiar_tipo_a_ingreso_sobre_expense_existente(test_db, client):
    """Caso PATCH donde solo cambia el tipo (no la categoria) -- el
    movimiento ya era EXPENSE (de un GASTO legítimo) y lo pasan a
    INGRESO por error; debe corregirse igual."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, categoria='EXPENSE', subcategoria='', tipo='GASTO')
        db.commit()
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"tipo": "INGRESO"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'
    assert row['tipo'] == 'INGRESO'


def test_update_transaction_no_toca_expense_que_sigue_siendo_gasto(test_db, client):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, categoria='EXPENSE', subcategoria='', tipo='GASTO')
        db.commit()
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"descripcion": "ajuste"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'EXPENSE'
    assert row['subcategoria'] == ''


# ── apply_all_keywords ───────────────────────────────────────────────────────

def test_apply_all_keywords_corrige_expense_que_calzo_en_un_ingreso(test_db, client):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='REEMBOLSO VIAJE TABASCO', categoria='OTROS',
                         subcategoria='', tipo='INGRESO')
        db.execute(
            "INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES (?,?,?)",
            ('VIAJE TABASCO', 'EXPENSE', ''),
        )
        db.commit()
    resp = client.post("/finanzas/estados/api/keywords/apply-all")
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'


# ── Migración retroactiva ────────────────────────────────────────────────────

def test_migration_backfills_existing_expense_en_ingreso(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_expense_ingreso_reembolsable_2026_09'")
        _insert(db, descripcion='DEPOSITO REEMBOLSO VIEJO', categoria='EXPENSE',
                subcategoria='', tipo='INGRESO')
        _insert(db, descripcion='GASTO PENDIENTE DE REEMBOLSO', categoria='EXPENSE',
                subcategoria='', tipo='GASTO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        ingreso = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='DEPOSITO REEMBOLSO VIEJO'"
        ).fetchone()
        gasto = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='GASTO PENDIENTE DE REEMBOLSO'"
        ).fetchone()
    assert ingreso['categoria'] == 'FINANZAS'
    assert ingreso['subcategoria'] == 'Reembolsable'
    assert gasto['categoria'] == 'EXPENSE'  # el gasto legítimo no se toca
    assert gasto['subcategoria'] == ''


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_expense_ingreso_reembolsable_2026_09'"
        ).fetchall()
    assert len(rows) == 1
