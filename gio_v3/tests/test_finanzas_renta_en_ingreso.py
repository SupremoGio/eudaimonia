"""
test_finanzas_renta_en_ingreso.py — el usuario confirmó, con screenshot:
"aportacion renta y parte renta Nu son lo mismo unificalo". Un depósito
de alguien aportando a la renta (ej. vía Nu) quedó con subcategoria=
'Renta' en vez de 'Aportación renta' en algún movimiento tipo=INGRESO --
probablemente de antes del fix que filtra el dropdown de subcategoria
por tipo (VIVIENDA/Renta es la subcategoria del lado GASTO,
VIVIENDA/Aportación renta la del lado INGRESO).

_corregir_renta_en_ingreso unifica: categoria=VIVIENDA, subcategoria=
'Renta', tipo=INGRESO -> subcategoria='Aportación renta'. Se aplica en
los mismos cuatro puntos de escritura que _corregir_expense_en_ingreso:
  1. create_transaction
  2. update_transaction (PATCH)
  3. apply_all_keywords
  4. upload_file
Y retroactivamente vía finanzas_renta_ingreso_unificada_2026_09 en
database.py.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.finanzas.estados.routes import _corregir_renta_en_ingreso


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
    defaults = dict(fecha='2026-09-04', fecha_cargo=None, descripcion='X', monto=5000.0,
                     banco='BBVA_DEB', periodo='', categoria='VIVIENDA', subcategoria='Renta',
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


# ── _corregir_renta_en_ingreso (unidad) ─────────────────────────────────────

def test_unifica_vivienda_renta_ingreso_a_aportacion_renta():
    cat, sub = _corregir_renta_en_ingreso('VIVIENDA', 'Renta', 'INGRESO')
    assert cat == 'VIVIENDA'
    assert sub == 'Aportación renta'


def test_no_toca_vivienda_renta_en_gasto():
    """El caso legítimo: VIVIENDA/Renta sí pertenece a un GASTO (tú
    pagando la renta)."""
    cat, sub = _corregir_renta_en_ingreso('VIVIENDA', 'Renta', 'GASTO')
    assert cat == 'VIVIENDA'
    assert sub == 'Renta'


def test_no_toca_otras_subcategorias_de_vivienda():
    cat, sub = _corregir_renta_en_ingreso('VIVIENDA', 'Luz', 'INGRESO')
    assert cat == 'VIVIENDA'
    assert sub == 'Luz'


def test_no_toca_renta_de_otra_categoria():
    cat, sub = _corregir_renta_en_ingreso('OTROS', 'Renta', 'INGRESO')
    assert cat == 'OTROS'
    assert sub == 'Renta'


# ── create_transaction ───────────────────────────────────────────────────────

def test_create_transaction_unifica_renta_en_ingreso(client):
    resp = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-09-04", "descripcion": "SPEI RECIBIDONU APORTE RENTA", "monto": 5000.0,
        "tipo": "INGRESO", "categoria": "VIVIENDA", "subcategoria": "Renta",
    })
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='SPEI RECIBIDONU APORTE RENTA'"
        ).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Aportación renta'


def test_create_transaction_deja_renta_en_gasto(client):
    resp = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-09-04", "descripcion": "PAGO RENTA DEPARTAMENTO", "monto": 8000.0,
        "tipo": "GASTO", "categoria": "VIVIENDA", "subcategoria": "Renta",
    })
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='PAGO RENTA DEPARTAMENTO'"
        ).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


# ── update_transaction (PATCH) ───────────────────────────────────────────────

def test_update_transaction_unifica_al_poner_subcategoria_renta_en_ingreso(test_db, client):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, categoria='VIVIENDA', subcategoria='Luz', tipo='INGRESO')
        db.commit()
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}",
                         json={"categoria": "VIVIENDA", "subcategoria": "Renta"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Aportación renta'


def test_update_transaction_unifica_al_cambiar_tipo_a_ingreso(test_db, client):
    """Caso PATCH donde solo cambia el tipo -- el movimiento ya era
    VIVIENDA/Renta (de un GASTO legítimo) y lo pasan a INGRESO por
    error; debe unificarse igual."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, categoria='VIVIENDA', subcategoria='Renta', tipo='GASTO')
        db.commit()
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"tipo": "INGRESO"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['subcategoria'] == 'Aportación renta'
    assert row['tipo'] == 'INGRESO'


def test_update_transaction_no_toca_renta_que_sigue_siendo_gasto(test_db, client):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, categoria='VIVIENDA', subcategoria='Renta', tipo='GASTO')
        db.commit()
    resp = client.patch(f"/finanzas/estados/api/transactions/{tx_id}", json={"descripcion": "ajuste"})
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['subcategoria'] == 'Renta'


# ── apply_all_keywords ───────────────────────────────────────────────────────

def test_apply_all_keywords_unifica_renta_que_calzo_en_un_ingreso(test_db, client):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='SPEI RECIBIDONU RENTA DEPTO', categoria='OTROS',
                         subcategoria='', tipo='INGRESO')
        db.execute(
            "INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES (?,?,?)",
            ('RECIBIDONU RENTA', 'VIVIENDA', 'Renta'),
        )
        db.commit()
    resp = client.post("/finanzas/estados/api/keywords/apply-all")
    assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Aportación renta'


# ── Migración retroactiva ────────────────────────────────────────────────────

def test_migration_backfills_existing_renta_en_ingreso(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_renta_ingreso_unificada_2026_09'")
        _insert(db, descripcion='SPEI RECIBIDONUBANK 638 APORTE RENTA VIEJO', categoria='VIVIENDA',
                subcategoria='Renta', tipo='INGRESO')
        _insert(db, descripcion='PAGO RENTA MENSUAL', categoria='VIVIENDA',
                subcategoria='Renta', tipo='GASTO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        ingreso = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='SPEI RECIBIDONUBANK 638 APORTE RENTA VIEJO'"
        ).fetchone()
        gasto = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='PAGO RENTA MENSUAL'"
        ).fetchone()
    assert ingreso['subcategoria'] == 'Aportación renta'
    assert gasto['subcategoria'] == 'Renta'  # el gasto legítimo no se toca


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_renta_ingreso_unificada_2026_09'"
        ).fetchall()
    assert len(rows) == 1
