"""
test_finanzas_audit_huecos.py — /admin/audit-huecos: qué estados de cuenta
faltan en BBVA Débito, BBVA Crédito, HSBC e Invex Volaris (solo lectura).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database

URL = '/finanzas/estados/admin/audit-huecos'


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


def _mov(banco, fecha, periodo='', monto=-100.0):
    with database.get_db() as db:
        n = db.execute("SELECT COUNT(*) FROM est_movimientos").fetchone()[0]
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, banco, periodo)
                      VALUES (?, ?, ?, 'GASTO', 'OTROS', ?, ?)""", (fecha, f'MOV {n}', monto, banco, periodo))
        db.commit()


def test_hueco_entre_periodos_de_tarjeta(client):
    for f in ('2026-01-10', '2026-01-25'):
        _mov('BBVA_TDC', f, '2026-01-05 al 2026-02-04')
    _mov('BBVA_TDC', '2026-03-10', '2026-03-05 al 2026-04-04')     # falta feb 5 → mar 4
    _mov('BBVA_TDC', '2026-04-10', '2026-04-05 al 2026-05-04')     # contiguo: sin hueco
    b = client.get(URL, query_string={'hasta': '2026-05-04'}).get_json()['por_banco']['BBVA_TDC']
    assert b['nombre'] == 'BBVA Crédito'
    assert b['huecos_entre_periodos'] == [{'desde': '2026-02-05', 'hasta': '2026-03-04', 'dias': 28}]
    assert len(b['periodos']) == 3 and b['periodos'][0]['movimientos'] == 2
    assert b['meses_sin_movimientos'] == ['2026-02', '2026-05']      # mayo aún sin movimientos al corte


def test_tramos_sin_movimientos_y_dias_al_corte(client):
    _mov('BBVA_DEB', '2026-01-01')
    _mov('BBVA_DEB', '2026-01-10')
    _mov('BBVA_DEB', '2026-03-01')                                # 50 días sin nada
    b = client.get(URL, query_string={'hasta': '2026-04-15'}).get_json()['por_banco']['BBVA_DEB']
    assert b['huecos_sin_movimientos'][0] == {'desde': '2026-01-11', 'hasta': '2026-02-28', 'dias': 49}
    assert b['huecos_sin_movimientos'][-1]['hasta'] == '2026-04-15'   # desde el último hasta hoy
    assert b['dias_sin_datos'] == 45
    assert b['meses_sin_movimientos'] == ['2026-02', '2026-04']


def test_bancos_sin_datos_y_vista_html(client):
    _mov('INVEX', '2026-02-01', '2026-01-15 al 2026-02-14')
    r = client.get(URL, query_string={'hasta': '2026-02-14'}).get_json()
    assert set(r['por_banco']) == {'BBVA_DEB', 'BBVA_TDC', 'HSBC', 'INVEX'}
    assert r['por_banco']['HSBC']['filas'] == 0
    assert r['por_banco']['INVEX']['nombre'] == 'Invex Volaris'
    html = client.get(URL, query_string={'formato': 'html', 'hasta': '2026-02-14'}).get_data(as_text=True)
    assert 'Invex Volaris' in html and 'Sin ningún movimiento importado' in html


def test_no_modifica_nada(client):
    _mov('HSBC', '2026-01-05')
    with database.get_db() as db:
        antes = db.execute("SELECT COUNT(*) FROM est_movimientos").fetchone()[0]
    client.get(URL)
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM est_movimientos").fetchone()[0] == antes
