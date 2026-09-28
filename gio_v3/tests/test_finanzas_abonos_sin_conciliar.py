"""
test_finanzas_abonos_sin_conciliar.py — pestaña «Sin conciliar»: abonos que no
cuentan como ingreso y no están ligados a un préstamo ni a un lote de Expense.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database

URL = '/finanzas/estados/api/abonos/sin-conciliar'


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


def _mov(fecha, desc, monto, cat, sub='', tipo='INGRESO'):
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                            VALUES (?,?,?, 'BBVA_DEB', ?,?,?)""", (fecha, desc, monto, cat, sub, tipo)).lastrowid
        db.commit()
    return mid


def test_solo_abonos_sueltos(client):
    suelto = _mov('2022-12-29', 'BNET TRANSF A GIOVANY A', 5300, 'FINANZAS', 'Transferencia')
    _mov('2022-12-15', 'PAGO DE NOMINA', 7000, 'NOMINA', 'Pago nominal')              # ingreso real: no
    _mov('2022-12-10', 'OXXO', 50, 'SUPER', 'Súper', tipo='GASTO')                     # gasto: no
    ligado = _mov('2022-11-01', 'BNET PAGO PRESTAMO', 1000, 'PRESTAMOS')
    dep = _mov('2022-10-01', 'FIDEICOMISO F 1596', 900, 'FINANZAS', 'Reembolsable')
    with database.get_db() as db:
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, monto, fecha, created_at)
                            VALUES ('Pops', 1000, '2022-10-01', '2022-10-01')""").lastrowid
        db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,'x')", (pid, ligado))
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, created_at) VALUES ('L', 'x')").lastrowid
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,'x')", (lid, dep))
        db.commit()
    d = client.get(URL).get_json()
    assert [m['id'] for m in d['movimientos']] == [suelto] and d['total'] == 5300
    assert d['grupos'] == [{'grupo': 'Transferencia', 'n': 1, 'total': 5300}]
    assert client.get(URL, query_string={'anio': '2021'}).get_json()['movimientos'] == []
    csv = client.get(URL + '.csv').get_data(as_text=True)
    assert 'COMENTARIOS' in csv and 'GIOVANY' in csv
