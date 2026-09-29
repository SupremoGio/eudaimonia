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


def _mov_banco(fecha, desc, monto, cat, banco, sub='', tipo='INGRESO'):
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                            VALUES (?,?,?,?,?,?,?)""", (fecha, desc, monto, banco, cat, sub, tipo)).lastrowid
        db.commit()
    return mid


def test_pistas(client):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_prestamos (contraparte, monto, fecha, created_at)
                      VALUES ('Pablo Ruiz', 1500, '2023-01-05', 'x')""")
        db.execute("""INSERT INTO est_prestamos (contraparte, monto, fecha, created_at)
                      VALUES ('Judi', 740, '2023-01-05', 'x')""")
        db.commit()
    por_nombre = _mov('2023-02-01', 'PAGO CUENTA DE TERCERO BNET PABLO', 500, 'FINANZAS', 'Transferencia recibida')
    por_monto = _mov('2023-02-03', 'SPEI RECIBIDO BANORTE', 740, 'FINANZAS', 'Transferencia recibida')
    propia = _mov('2023-03-10', 'SPEI RECIBIDO NAFIN', 3000, 'FINANZAS', 'Transferencia recibida')
    _mov_banco('2023-03-09', 'TRASPASO A BBVA', 3000, 'FINANZAS', 'NU', 'Transferencia enviada', 'GASTO')
    gasto_igual = _mov('2023-04-10', 'SPEI RECIBIDO X', 250, 'FINANZAS', 'Transferencia recibida')
    _mov_banco('2023-04-10', 'RESTAURANTE', 250, 'COMIDA_FUERA', 'BBVA_TDC', 'Restaurante', 'GASTO')
    d = client.get(URL).get_json()
    pista = {m['id']: (m['pista'] or {}).get('tipo') for m in d['movimientos']}
    assert pista[por_nombre] == 'prestamo' and pista[por_monto] == 'prestamo'
    assert pista[propia] == 'propia'
    assert pista[gasto_igual] is None                                   # un gasto normal no es transferencia
    assert {g['tipo'] for g in d['por_pista']} == {'prestamo', 'propia', 'ninguna'}
    assert 'Pablo Ruiz' in client.get(URL + '.csv').get_data(as_text=True)


def test_conciliar_pistas(client):
    with database.get_db() as db:
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, monto, fecha, created_at)
                            VALUES ('Pablo Ruiz', 1000, '2023-01-05', 'x')""").lastrowid
        db.commit()
    dev1 = _mov('2023-02-01', 'PAGO CUENTA DE TERCERO BNET PABLO', 600, 'FINANZAS', 'Transferencia recibida')
    dev2 = _mov('2023-02-15', 'PAGO CUENTA DE TERCERO BNET PABLO', 600, 'FINANZAS', 'Transferencia recibida')  # pasa del pendiente
    propia = _mov('2023-03-10', 'SPEI RECIBIDO NAFIN', 3000, 'FINANZAS', 'Transferencia recibida')
    _mov_banco('2023-03-09', 'TRASPASO A BBVA', 3000, 'FINANZAS', 'NU', 'Transferencia enviada', 'GASTO')
    suelto = _mov('2023-04-10', 'SPEI RECIBIDO X', 250, 'FINANZAS', 'Transferencia recibida')
    r = client.post('/finanzas/estados/api/abonos/conciliar-pistas').get_json()
    assert (r['prestamos'], r['propias'], r['sin_aplicar']) == (1, 1, 1)
    ids = [m['id'] for m in client.get(URL).get_json()['movimientos']]
    assert dev1 not in ids and propia not in ids and dev2 in ids and suelto in ids
    with database.get_db() as db:
        assert db.execute("SELECT prestamo_id FROM est_prestamo_devoluciones WHERE movimiento_id=?", (dev1,)).fetchone()[0] == pid
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (propia,)).fetchone()) \
            == ('FINANZAS', 'Entre cuentas propias')
    assert client.post('/finanzas/estados/api/abonos/conciliar-pistas').get_json()['prestamos'] == 0   # idempotente


def test_conciliar_pistas_crea_lote_expense(client):
    f1 = _mov('2023-05-02', 'UBER', 300, 'EXPENSE', tipo='GASTO')
    f2 = _mov('2023-05-03', 'HOTEL', 700, 'EXPENSE', tipo='GASTO')
    dep = _mov('2023-05-20', 'FIDEICOMISO F 1596', 1000, 'FINANZAS', 'Reembolsable')
    assert client.get(URL).get_json()['movimientos'][0]['pista']['tipo'] == 'expense'
    r = client.post('/finanzas/estados/api/abonos/conciliar-pistas').get_json()
    assert (r['expense_lotes'], r['expense_depositos']) == (1, 1)
    assert client.get(URL).get_json()['movimientos'] == []
    with database.get_db() as db:
        lid = db.execute("SELECT lote_id FROM est_expense_lote_depositos WHERE movimiento_id=?", (dep,)).fetchone()[0]
        assert {x[0] for x in db.execute("SELECT movimiento_id FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))} == {f1, f2}
        assert {x[0] for x in db.execute("SELECT estatus_reembolso FROM est_movimientos WHERE id IN (?,?)", (f1, f2))} == {'PAGADO'}


def test_iphone_macstore_prestamo_y_devoluciones(client):
    from modules.finanzas.estados import prestamos
    pagos = [_mov(f, f'PAGO CUENTA DE TERCERO BNET {d}', m, 'FINANZAS', 'Transferencia')
             for f, d, m in (('2023-01-07', 'PAGO 2', 2756), ('2023-04-28', 'PAGO 4 Y 5', 2756),
                             ('2024-01-07', 'PAGO 10 11 12', 3814))]
    otro = _mov('2023-07-22', 'PAGO CUENTA DE TERCERO BNET PAGO', 1000, 'FINANZAS', 'Transferencia')
    with database.get_db() as db:
        assert prestamos.ligar_iphone_macstore(db) == (1, 3)
        assert prestamos.ligar_iphone_macstore(db) == (0, 0)
        db.commit()
        p = next(x for x in prestamos.listar(db) if x['persona'] == 'iPhone MacStore')
        assert p['devuelto'] == 9326 and p['pendiente'] == 20999 - 9326
    assert [m['id'] for m in client.get(URL).get_json()['movimientos']] == [otro]
