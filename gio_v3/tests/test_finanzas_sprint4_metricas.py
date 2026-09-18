"""
test_finanzas_sprint4_metricas.py — cubre el Sprint 4 ORIGINAL ("Métricas y
dashboard"), el que se había saltado entre el Sprint 3 (Reglas automáticas
al importar) y el Sprint 5 (Edición en la UI):

  1. GET /api/summary/by-naturaleza — desglosa el gasto por naturaleza
     (FIJO/VARIABLE/IRREGULAR/EVITABLE) usando est_categoria_naturaleza
     (sembrada desde el Sprint 1, nunca antes consumida por ninguna vista).
     Una transacción sin match exacto cae en SIN_CLASIFICAR, nunca se
     adivina.
  2. GET /api/summary/by-category ahora también trae prev_total/pct_change
     por categoría, comparando contra el periodo inmediatamente anterior de
     igual duración (solo cuando el filtro es un rango continuo
     date_from/date_to — con months= sueltos no hay "periodo anterior" bien
     definido y se deja sin tendencia).
  3. GET /api/summary/pendientes — total/conteo de EXPENSE con
     estatus_reembolso='PENDIENTE', y deuda restante estimada en compras a
     MSI activas (compra_msi_id con cuotas_vistas < parcialidad_total).
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
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_TDC', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO')
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )


# ── by-naturaleza ──────────────────────────────────────────────────────────

def test_by_naturaleza_groups_known_categories(client):
    import database
    with database.get_db() as db:
        _insert(db, fecha='2026-01-05', descripcion='RENTA', monto=7000.0,
                categoria='VIVIENDA', subcategoria='Renta')
        _insert(db, fecha='2026-01-06', descripcion='WALMART', monto=500.0,
                categoria='ALIMENTACION', subcategoria='Súper')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-naturaleza',
                       query_string={'date_from': '2026-01-01', 'date_to': '2026-01-31'})
    assert resp.status_code == 200
    data = {r['naturaleza']: r['total'] for r in resp.get_json()}
    assert data['FIJO'] == 7000.0
    assert data['VARIABLE'] == 500.0


def test_by_naturaleza_unmatched_falls_to_sin_clasificar(client):
    import database
    with database.get_db() as db:
        # ROPA no tiene fila de fallback ('ROPA','') en la semilla -- una
        # ROPA sin subcategoria debe caer en SIN_CLASIFICAR, no adivinarse.
        _insert(db, fecha='2026-01-05', descripcion='TIENDA', monto=300.0,
                categoria='ROPA', subcategoria='')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-naturaleza',
                       query_string={'date_from': '2026-01-01', 'date_to': '2026-01-31'})
    data = {r['naturaleza']: r['total'] for r in resp.get_json()}
    assert data.get('SIN_CLASIFICAR') == 300.0
    assert 'ROPA' not in data


def test_by_naturaleza_excludes_movement_categories(client):
    import database
    with database.get_db() as db:
        _insert(db, fecha='2026-01-05', descripcion='PAGO TARJETA', monto=1000.0,
                categoria='PAGO_TDC', subcategoria='', tipo='MOVIMIENTO_INTERNO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-naturaleza',
                       query_string={'date_from': '2026-01-01', 'date_to': '2026-01-31'})
    assert resp.get_json() == []


# ── by-category pct_change ─────────────────────────────────────────────────

def test_by_category_computes_pct_change_vs_previous_period(client):
    import database
    with database.get_db() as db:
        # Periodo actual: 2026-02-01..2026-02-10 (10 días) -> $300 en WALMART
        _insert(db, fecha='2026-02-05', descripcion='WALMART', monto=300.0,
                categoria='ALIMENTACION', subcategoria='Súper')
        # Periodo anterior de igual duración (10 días): 2026-01-22..2026-01-31 -> $200
        _insert(db, fecha='2026-01-25', descripcion='WALMART', monto=200.0,
                categoria='ALIMENTACION', subcategoria='Súper')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10'})
    assert resp.status_code == 200
    row = next(r for r in resp.get_json() if r['categoria'] == 'ALIMENTACION')
    assert row['total'] == 300.0
    assert row['prev_total'] == 200.0
    assert row['pct_change'] == 50.0


def test_by_category_pct_change_none_when_no_prior_spend(client):
    import database
    with database.get_db() as db:
        _insert(db, fecha='2026-02-05', descripcion='WALMART', monto=300.0,
                categoria='ALIMENTACION', subcategoria='Súper')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-02-01', 'date_to': '2026-02-10'})
    row = next(r for r in resp.get_json() if r['categoria'] == 'ALIMENTACION')
    assert row['prev_total'] is None
    assert row['pct_change'] is None


def test_by_category_no_trend_with_scattered_months_filter(client):
    import database
    with database.get_db() as db:
        _insert(db, fecha='2026-01-05', descripcion='WALMART', monto=300.0,
                categoria='ALIMENTACION', subcategoria='Súper')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'months': '2026-01'})
    row = next(r for r in resp.get_json() if r['categoria'] == 'ALIMENTACION')
    assert row['prev_total'] is None
    assert row['pct_change'] is None


# ── pendientes (reembolsos + MSI) ──────────────────────────────────────────

def test_pendientes_counts_only_expense_pendiente(client):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='EXPENSE PENDIENTE', monto=-1000.0, categoria='EXPENSE')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PENDIENTE' "
                   "WHERE descripcion='EXPENSE PENDIENTE'")
        _insert(db, descripcion='EXPENSE PAGADO', monto=-500.0, categoria='EXPENSE')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PAGADO' "
                   "WHERE descripcion='EXPENSE PAGADO'")
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/pendientes')
    data = resp.get_json()
    assert data['reembolsos_pendientes_count'] == 1
    assert data['reembolsos_pendientes_total'] == 1000.0


def test_pendientes_computes_remaining_msi_debt(client):
    import database
    with database.get_db() as db:
        # Compra a 12 meses, cuota $500 -- solo han llegado 3 de 12 -> faltan 9 * 500 = 4500
        for num in (1, 2, 3):
            db.execute("""INSERT INTO est_movimientos
                          (fecha,descripcion,monto,banco,categoria,tipo,
                           parcialidad_num,parcialidad_total,compra_msi_id)
                          VALUES (?,'LIVERPOOL',500.0,'BBVA_TDC','ROPA','GASTO',?,12,'msiA')""",
                       (f"2026-0{num}-01", num))
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/pendientes')
    data = resp.get_json()
    assert data['msi_compras_activas'] == 1
    assert data['msi_restante_total'] == 4500.0


def test_pendientes_excludes_msi_purchase_already_fully_seen(client):
    import database
    with database.get_db() as db:
        for num in (1, 2):
            db.execute("""INSERT INTO est_movimientos
                          (fecha,descripcion,monto,banco,categoria,tipo,
                           parcialidad_num,parcialidad_total,compra_msi_id)
                          VALUES (?,'AMAZON',300.0,'BBVA_TDC','DIGITAL','GASTO',?,2,'msiB')""",
                       (f"2026-0{num}-01", num))
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/pendientes')
    data = resp.get_json()
    assert data['msi_compras_activas'] == 0
    assert data['msi_restante_total'] == 0.0
