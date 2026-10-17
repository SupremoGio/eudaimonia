"""
test_finanzas_duplicados.py — cubre la corrección al bug real confirmado
por el usuario: el mismo movimiento real (mismo día, mismo monto) se coló
dos veces en la DB con descripción y tipo distintos ("PAGO DE NOMINA HH"
vía BBVA_DEB tipo=INGRESO y "PAGO DE NOMINA / HH 4206466060 FIBRA
HOTELERA..." vía BBVA_TDC — probablemente mal detectado como GASTO al
importar y reclasificado a mano después). Ninguno de los guardarraíles
existentes lo atrapaba:
  - el índice UNIQUE(fecha,descripcion,monto) exige descripción idéntica.
  - el dedup de /api/upload por (fecha,monto,tipo) no aplica si el tipo
    también terminó distinto.

Tres piezas:
  1. create_transaction ahora bloquea (con aviso, no con adivinanza) un
     alta manual del mismo día+monto+tipo que uno ya existente, aunque la
     descripción sea distinta.
  2. El dedup de /api/upload ahora redondea el monto a centavos al armar
     la clave, para no dejar pasar un duplicado real por una diferencia
     de float entre dos formas de calcular el mismo monto.
  3. _detectar_posibles_duplicados (aviso no bloqueante en /api/upload) y
     /admin/audit-duplicados (reporte de solo lectura sobre toda la
     tabla) encuentran coincidencias de fecha+monto SIN importar el tipo
     -- el caso que de verdad se coló.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.finanzas.estados.routes import _detectar_posibles_duplicados


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
    defaults = dict(fecha='2026-07-30', fecha_cargo=None, descripcion='X', monto=10435.19,
                     banco='BBVA_DEB', periodo='', categoria='NOMINA', subcategoria='Pago nominal',
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


# ── create_transaction: bloquea mismo día+monto+tipo ────────────────────────

def test_create_transaction_blocks_same_day_amount_tipo_different_description(client):
    client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-07-30", "descripcion": "PAGO DE NOMINA HH", "monto": 10435.19,
        "tipo": "INGRESO", "categoria": "NOMINA",
    })
    resp = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-07-30",
        "descripcion": "PAGO DE NOMINA / HH 4206466060 FIBRA HOTELERA SC",
        "monto": 10435.19, "tipo": "INGRESO", "categoria": "NOMINA",
    })
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["inserted"] == 0
    assert data["possible_duplicate"] is True
    assert data["existing"]["descripcion"] == "PAGO DE NOMINA HH"

    import database
    with database.get_db() as db:
        n = db.execute(
            "SELECT COUNT(*) c FROM est_movimientos WHERE fecha='2026-07-30' AND ROUND(monto,2)=10435.19"
        ).fetchone()["c"]
    assert n == 1  # la segunda nunca se insertó


def test_create_transaction_force_bypasses_duplicate_guard(client):
    client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-07-30", "descripcion": "COMPRA A", "monto": 500.0, "tipo": "GASTO",
    })
    resp = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-07-30", "descripcion": "COMPRA B", "monto": 500.0, "tipo": "GASTO",
        "force": True,
    })
    assert resp.status_code == 201
    import database
    with database.get_db() as db:
        n = db.execute(
            "SELECT COUNT(*) c FROM est_movimientos WHERE fecha='2026-07-30' AND ROUND(monto,2)=500.0"
        ).fetchone()["c"]
    assert n == 2  # force=true sí las deja coexistir


def test_create_transaction_allows_different_tipo_same_day_amount(client):
    """Caso legítimo: un ingreso y un gasto real del mismo monto el mismo
    día no deben bloquearse entre sí."""
    r1 = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-07-30", "descripcion": "INGRESO REAL", "monto": 500.0, "tipo": "INGRESO",
    })
    r2 = client.post("/finanzas/estados/api/transactions", json={
        "fecha": "2026-07-30", "descripcion": "GASTO REAL", "monto": 500.0, "tipo": "GASTO",
    })
    assert r1.status_code == 201
    assert r2.status_code == 201


# ── _detectar_posibles_duplicados (aviso en /api/upload) ───────────────────

def test_detecta_duplicado_con_tipo_distinto(test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='PAGO DE NOMINA HH', tipo='INGRESO', banco='BBVA_DEB')
        nueva_id = _insert(db, descripcion='PAGO DE NOMINA / HH 4206466060 FIBRA HOTELERA SC',
                            tipo='GASTO', banco='BBVA_TDC', categoria='OTROS', subcategoria='')
        db.commit()
        avisos = _detectar_posibles_duplicados(db, [nueva_id])
    assert len(avisos) == 1
    assert avisos[0]['id'] == nueva_id
    assert avisos[0]['posible_duplicado_descripcion'] == 'PAGO DE NOMINA HH'


def test_no_aviso_para_fecha_o_monto_distintos(test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='PAGO DE NOMINA HH', fecha='2026-07-30', monto=10435.19)
        otra_fecha = _insert(db, descripcion='OTRA COSA', fecha='2026-08-01', monto=10435.19)
        otro_monto = _insert(db, descripcion='OTRA COSA 2', fecha='2026-07-30', monto=999.99)
        db.commit()
        avisos = _detectar_posibles_duplicados(db, [otra_fecha, otro_monto])
    assert avisos == []


def test_no_self_match(test_db):
    """Una fila recién insertada sin ninguna otra igual no debe avisar de
    sí misma."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='UNICA')
        db.commit()
        avisos = _detectar_posibles_duplicados(db, [tx_id])
    assert avisos == []


def test_only_checks_given_ids(test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='A', fecha='2026-07-30', monto=100.0)
        _insert(db, descripcion='B', fecha='2026-07-30', monto=100.0)
        otra_id = _insert(db, descripcion='C', fecha='2026-09-01', monto=200.0)
        db.commit()
        avisos = _detectar_posibles_duplicados(db, [otra_id])
    assert avisos == []  # ni A ni B estaban en la lista de ids a revisar


# ── /admin/audit-duplicados (reporte de solo lectura) ──────────────────────

def test_audit_duplicados_finds_group(client):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='PAGO DE NOMINA HH', tipo='INGRESO', banco='BBVA_DEB')
        _insert(db, descripcion='PAGO DE NOMINA / HH 4206466060 FIBRA HOTELERA SC',
                tipo='GASTO', banco='BBVA_TDC', categoria='OTROS', subcategoria='')
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-duplicados')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['grupos_duplicados'] == 1
    assert data['total_filas_involucradas'] == 2
    grupo = data['duplicados'][0]
    assert grupo['fecha'] == '2026-07-30'
    assert len(grupo['movimientos']) == 2


def test_audit_duplicados_ignores_singles(client):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='UNICA', fecha='2026-01-01', monto=50.0)
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-duplicados')
    data = resp.get_json()
    assert data['grupos_duplicados'] == 0
    assert data['duplicados'] == []


def test_audit_duplicados_never_modifies_data(client):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='A', fecha='2026-07-30', monto=100.0)
        _insert(db, descripcion='B', fecha='2026-07-30', monto=100.0)
        db.commit()

    client.get('/finanzas/estados/admin/audit-duplicados')

    with database.get_db() as db:
        n = db.execute("SELECT COUNT(*) c FROM est_movimientos").fetchone()['c']
    assert n == 2  # nada se borró ni se cambió
