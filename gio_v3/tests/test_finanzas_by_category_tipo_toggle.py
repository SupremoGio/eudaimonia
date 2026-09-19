"""
test_finanzas_by_category_tipo_toggle.py — el usuario reportó que el modal
de detalle de una categoría (clic en una fila de "Gastos por categoría")
mezclaba filas tipo=INGRESO con las de GASTO bajo la misma categoria (ej.
un +$50,000 verde de ingreso dentro de "Familia y regalos", categoría cuyo
total agregado de arriba solo cuenta GASTO): "aqui veo ingresos y gastos
en lo mismo entiendes?". Pidió un chip para cambiar entre ver Gastos e
Ingresos por categoría.

GET /api/summary/by-category ahora acepta tipo=GASTO|INGRESO (default
GASTO, sin cambio de comportamiento para quien no lo manda) para poder
alimentar el widget en ambos modos con el mismo query, reusando la misma
definición de "ingreso real" que ya usa /api/summary/stats
(_INGRESO_EXCLUIR_SQL excluye TRANSFERENCIA/RETIRO/DEPOSITO/SPEI_RECIBIDO/
APORTACION_RENTA/PAGO_TDC/PRESTAMOS/FINANZAS). El fix del propio modal de
detalle -- que ahora sí manda tipo al pedir /api/transactions -- es
puramente frontend (estados.js), api/transactions ya soportaba category+
tipo combinados sin cambios.
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


def _insert(db, **kw):
    defaults = dict(fecha='2026-02-05', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_TDC', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO', mi_parte=None)
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo,mi_parte)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo,:mi_parte)""",
        defaults,
    )


def test_default_sin_tipo_sigue_siendo_gasto(client):
    """No debe cambiar el comportamiento de nadie que no mande tipo=."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='WALMART', monto=300.0, categoria='ALIMENTACION', tipo='GASTO')
        _insert(db, descripcion='NOMINA SEP', monto=20000.0, categoria='NOMINA', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10'})
    cats = {r['categoria'] for r in resp.get_json()}
    assert 'ALIMENTACION' in cats
    assert 'NOMINA' not in cats


def test_tipo_ingreso_devuelve_solo_ingresos(client):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='WALMART', monto=300.0, categoria='ALIMENTACION', tipo='GASTO')
        _insert(db, descripcion='NOMINA SEP', monto=20000.0, categoria='NOMINA', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10', 'tipo': 'INGRESO'})
    assert resp.status_code == 200
    data = resp.get_json()
    cats = {r['categoria'] for r in data}
    assert 'NOMINA' in cats
    assert 'ALIMENTACION' not in cats
    row = next(r for r in data if r['categoria'] == 'NOMINA')
    assert row['total'] == 20000.0


def test_tipo_ingreso_excluye_movimientos_internos(client):
    """Mismos excluidos que ya usa /api/summary/stats para 'Total Ingreso'
    -- transferencias/retiros no son ingreso real."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='RETIRO CAJERO', monto=1000.0, categoria='RETIRO', tipo='INGRESO')
        _insert(db, descripcion='NOMINA SEP', monto=20000.0, categoria='NOMINA', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10', 'tipo': 'INGRESO'})
    cats = {r['categoria'] for r in resp.get_json()}
    assert 'RETIRO' not in cats
    assert 'NOMINA' in cats


def test_tipo_invalido_cae_a_gasto(client):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='WALMART', monto=300.0, categoria='ALIMENTACION', tipo='GASTO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10', 'tipo': 'ALGO_RARO'})
    cats = {r['categoria'] for r in resp.get_json()}
    assert 'ALIMENTACION' in cats


def test_tipo_ingreso_tambien_calcula_tendencia(client):
    import database
    with database.get_db() as db:
        # Periodo actual: 2026-02-01..2026-02-10 -> $20,000 NOMINA
        _insert(db, fecha='2026-02-05', descripcion='NOMINA SEP', monto=20000.0,
                categoria='NOMINA', tipo='INGRESO')
        # Periodo anterior de igual duración (10 días): 2026-01-22..2026-01-31 -> $18,000
        _insert(db, fecha='2026-01-25', descripcion='NOMINA AGO', monto=18000.0,
                categoria='NOMINA', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10', 'tipo': 'INGRESO'})
    row = next(r for r in resp.get_json() if r['categoria'] == 'NOMINA')
    assert row['total'] == 20000.0
    assert row['prev_total'] == 18000.0
    assert row['pct_change'] == round((20000 - 18000) / 18000 * 100, 1)


def test_tipo_gasto_no_cambia_tras_el_fix(client):
    """El comportamiento explícito tipo=GASTO debe ser idéntico al default
    de antes del cambio (mismos excluidos PAGO_TDC/PAGO/PRESTAMOS/FINANZAS,
    mismo mi_parte)."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='PAGO TARJETA', monto=1000.0, categoria='PAGO_TDC', tipo='GASTO')
        _insert(db, descripcion='WALMART COMPARTIDO', monto=1000.0, mi_parte=400.0,
                categoria='ALIMENTACION', tipo='GASTO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10', 'tipo': 'GASTO'})
    data = resp.get_json()
    cats = {r['categoria']: r['total'] for r in data}
    assert 'PAGO_TDC' not in cats
    assert cats['ALIMENTACION'] == 400.0


# ── /api/transactions ya soporta category+tipo combinados (sin cambios) ────

def test_transactions_filtra_por_category_y_tipo_juntos(client):
    """Confirma el mecanismo que el fix del modal de detalle usa en el
    front (yl({category,tipo})) -- ya funcionaba en el backend, el bug
    era que el front nunca mandaba tipo en ese caso."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='REGALO CUMPLE', monto=-500.0, categoria='FAMILIA_REGALOS', tipo='GASTO')
        _insert(db, descripcion='EFECTIVO RECIBIDO REGALO', monto=5000.0,
                categoria='FAMILIA_REGALOS', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/transactions',
                       query_string={'category': 'FAMILIA_REGALOS', 'tipo': 'GASTO'})
    data = resp.get_json()['data']
    assert len(data) == 1
    assert data[0]['tipo'] == 'GASTO'
