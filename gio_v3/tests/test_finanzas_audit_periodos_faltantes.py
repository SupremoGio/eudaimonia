"""
test_finanzas_audit_periodos_faltantes.py — el usuario sabe que hay huecos
en 2026 y pidió: "dine que periodos no estan contemplados o faltan del 01
de enero al 19 de septiembre para subirlos". No hay acceso a su DB de
producción desde este entorno, así que se construyó un diagnóstico de
solo lectura (/admin/audit-periodos-faltantes) que, banco por banco, dice
qué meses calendario dentro de un rango no tienen ninguna fila importada
-- para que él lo corra sobre su base real y sepa qué estados de cuenta
le faltan subir.
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
    defaults = dict(fecha='2026-05-05', fecha_cargo='2026-05-05', descripcion='X', monto=100.0,
                     banco='BBVA_DEB', periodo='', categoria='OTROS', subcategoria='', tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


def test_meses_sin_datos_se_reportan_como_faltantes(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, banco='BBVA_DEB', fecha='2026-01-15')
        _insert(db, banco='BBVA_DEB', fecha='2026-01-20', descripcion='Y', monto=200.0)
        _insert(db, banco='BBVA_DEB', fecha='2026-03-10', descripcion='Z', monto=300.0)
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-periodos-faltantes',
                       query_string={'desde': '2026-01-01', 'hasta': '2026-04-30'})
    assert resp.status_code == 200
    data = resp.get_json()
    deb = data['por_banco']['BBVA_DEB']
    assert deb['meses_con_datos'] == ['2026-01', '2026-03']
    assert deb['meses_faltantes'] == ['2026-02', '2026-04']


def test_banco_sin_ninguna_fila_reporta_todos_los_meses_como_faltantes(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, banco='BBVA_DEB', fecha='2026-01-15')
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-periodos-faltantes',
                       query_string={'desde': '2026-01-01', 'hasta': '2026-02-28'})
    data = resp.get_json()
    hsbc = data['por_banco']['HSBC']
    assert hsbc['total_filas'] == 0
    assert hsbc['meses_faltantes'] == ['2026-01', '2026-02']
    assert hsbc['primera_fecha'] is None
    assert hsbc['ultima_fecha'] is None


def test_banco_manual_no_se_incluye(client, test_db):
    resp = client.get('/finanzas/estados/admin/audit-periodos-faltantes')
    data = resp.get_json()
    assert 'MANUAL' not in data['por_banco']


def test_rango_por_default_cubre_hasta_hoy(client, test_db):
    resp = client.get('/finanzas/estados/admin/audit-periodos-faltantes')
    data = resp.get_json()
    assert data['desde'] == '2026-01-01'
    import utils
    assert data['hasta'] == utils.today_str()


def test_fuera_de_rango_no_cuenta(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, banco='BBVA_DEB', fecha='2025-12-31')
        _insert(db, banco='BBVA_DEB', fecha='2026-10-01', descripcion='Y', monto=200.0)
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-periodos-faltantes',
                       query_string={'desde': '2026-01-01', 'hasta': '2026-09-19'})
    data = resp.get_json()
    deb = data['por_banco']['BBVA_DEB']
    assert deb['total_filas'] == 0
    assert deb['meses_con_datos'] == []


def test_todos_los_meses_en_rango_incluye_septiembre_parcial(client, test_db):
    resp = client.get('/finanzas/estados/admin/audit-periodos-faltantes',
                       query_string={'desde': '2026-01-01', 'hasta': '2026-09-19'})
    data = resp.get_json()
    assert data['todos_los_meses_en_rango'] == [
        '2026-01', '2026-02', '2026-03', '2026-04', '2026-05',
        '2026-06', '2026-07', '2026-08', '2026-09',
    ]


def test_nunca_modifica_datos(client, test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, banco='BBVA_TDC', fecha='2026-04-04')
        db.commit()

    client.get('/finanzas/estados/admin/audit-periodos-faltantes')

    with database.get_db() as db:
        row = db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row is not None
