"""
test_finanzas_reportes_no_inflar_ingresos.py — el usuario reportó, con
screenshot de la tab Reportes: "cada ves veo que aumentas ingresos audita
rigurosamente no quiero fallas es critico". Causa raíz confirmada: la
migración finanzas_legacy_bancario_a_finanzas_2026_09 reclasificó
DEPOSITO/FIDEICOMISO/SPEI_RECIBIDO/SPEI_ENVIADO/TRANSFERENCIA/RETIRO/
PAGO/PAGO_TDC -> FINANZAS, pero existían VARIAS copias independientes,
en tres archivos distintos, de la lista de categorías "no es
ingreso/gasto real" -- solo se había corregido la de budget.py. Las de
estados/routes.py (que alimenta /api/summary/stats, el endpoint real
detrás de "Total Gastado"/"Total Ingreso"/"Promedio Diario" en Reportes)
y modules/finanzas/routes.py (el widget del Dashboard) seguían sin
'FINANZAS', así que en cuanto una fila cambiaba de DEPOSITO/SPEI_RECIBIDO/
etc. a FINANZAS, empezaba a contarse de más -- justo el bug reportado.

Este archivo prueba, con datos sembrados a mano que imitan movimientos
reales ya reclasificados a FINANZAS, que CADA endpoint que muestra un
total de ingreso/gasto sigue excluyendo esos movimientos correctamente.
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
    defaults = dict(fecha='2026-09-01', fecha_cargo=None, descripcion='X', monto=500.0,
                     banco='BBVA_DEB', periodo='', categoria='FINANZAS', subcategoria='Transferencia',
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


# ── /api/summary/stats -- Total Gastado / Total Ingreso / Promedio Diario ──

def test_summary_stats_no_cuenta_finanzas_como_ingreso(client, test_db):
    """Reproduce el screenshot: un ingreso real (nómina) más un movimiento
    ya reclasificado a FINANZAS (antes SPEI_RECIBIDO/DEPOSITO/etc.) --
    total_income debe ser SOLO el ingreso real."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='NOMINA', fecha='2026-09-05', monto=15000.0,
                categoria='NOMINA', subcategoria='Pago nominal', tipo='INGRESO')
        _insert(db, descripcion='SPEI RECIBIDONAFIN 135', fecha='2026-09-08', monto=10000.0,
                categoria='FINANZAS', subcategoria='Transferencia', tipo='INGRESO')
        _insert(db, descripcion='FIDEICOMISO F 1596', fecha='2026-09-10', monto=7163.62,
                categoria='FINANZAS', subcategoria='Transferencia', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/stats', query_string={
        'date_from': '2026-09-01', 'date_to': '2026-09-30',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_income'] == 15000.0


def test_summary_stats_no_cuenta_finanzas_como_gasto(client, test_db):
    """Simétrico del lado del gasto: un pago de tarjeta ya reclasificado a
    FINANZAS (antes PAGO/PAGO_TDC) no debe sumar a total_expense."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='WALMART', fecha='2026-09-05', monto=-1200.0,
                categoria='ALIMENTACION', subcategoria='Súper', tipo='GASTO')
        _insert(db, descripcion='PAGO CUENTA DE TERCERO BNET TRANSF', fecha='2026-09-06',
                monto=-4500.0, categoria='FINANZAS', subcategoria='Pago servicios', tipo='GASTO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/stats', query_string={
        'date_from': '2026-09-01', 'date_to': '2026-09-30',
    })
    data = resp.get_json()
    assert data['total_expense'] == -1200.0


def test_summary_stats_sigue_excluyendo_por_los_nombres_viejos(client, test_db):
    """Un movimiento que por alguna razón siga con el nombre legacy
    (ej. importado antes del deploy de la migración) también debe seguir
    excluido -- no se quitaron los nombres viejos, solo se agregó
    'FINANZAS'."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='NOMINA', fecha='2026-09-05', monto=15000.0,
                categoria='NOMINA', subcategoria='Pago nominal', tipo='INGRESO')
        _insert(db, descripcion='DEPOSITO VIEJO SIN MIGRAR', fecha='2026-09-08', monto=9999.0,
                categoria='DEPOSITO', subcategoria='', tipo='INGRESO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/stats', query_string={
        'date_from': '2026-09-01', 'date_to': '2026-09-30',
    })
    data = resp.get_json()
    assert data['total_income'] == 15000.0


# ── /api/summary/by-naturaleza (Sprint 4) ───────────────────────────────────

def test_by_naturaleza_no_cuenta_finanzas_como_gasto(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='RENTA', fecha='2026-09-01', monto=-8000.0,
                categoria='VIVIENDA', subcategoria='Renta', tipo='GASTO')
        _insert(db, descripcion='PAGO TDC', fecha='2026-09-03', monto=-4500.0,
                categoria='FINANZAS', subcategoria='Pago servicios', tipo='GASTO')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-naturaleza')
    assert resp.status_code == 200
    data = resp.get_json()
    total = sum(g['total'] for g in data)
    assert round(total, 2) == -8000.0


# ── /finanzas/api/oikonomia-summary (widget del Dashboard) ─────────────────

def test_oikonomia_summary_no_infla_ingreso_ni_gasto(test_db):
    import database
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True

        from utils import today_date
        mes_actual = today_date().replace(day=5).isoformat()
        with database.get_db() as db:
            _insert(db, descripcion='NOMINA', fecha=mes_actual, monto=15000.0,
                    categoria='NOMINA', subcategoria='Pago nominal', tipo='INGRESO')
            _insert(db, descripcion='SPEI RECIBIDO GRANDE', fecha=mes_actual, monto=50000.0,
                    categoria='FINANZAS', subcategoria='Transferencia', tipo='INGRESO')
            _insert(db, descripcion='PAGO TDC GRANDE', fecha=mes_actual, monto=-30000.0,
                    categoria='FINANZAS', subcategoria='Pago servicios', tipo='GASTO')
            db.commit()

        resp = c.get('/finanzas/api/oikonomia-summary')
        assert resp.status_code == 200
        data = resp.get_json()
    assert data['flujo_ingreso'] == 15000.0
    assert data['flujo_gasto'] == 0.0


# ── /finanzas/api/reclasificar -- ya no debe generar TRANSFERENCIA ─────────

def test_reclasificar_excluir_usa_finanzas_no_transferencia(test_db):
    import database
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True

        with database.get_db() as db:
            tx_id = _insert(db, descripcion='SPEI SIN CLASIFICAR', categoria='SPEI_RECIBIDO',
                             subcategoria='', tipo='INGRESO')
            db.commit()

        resp = c.post(f'/finanzas/budget/api/reclasificar/{tx_id}', json={'accion': 'excluir'})
        assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Transferencia'
