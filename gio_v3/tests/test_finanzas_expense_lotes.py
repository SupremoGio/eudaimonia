"""
test_finanzas_expense_lotes.py — conciliación de Expense por lotes: varias
facturas se suben juntas y la empresa paga un depósito (o varios) por el
lote. El estado se calcula, se refleja en estatus_reembolso de las facturas
(las «Pagado a compañero» conservan TERCERO) y el depósito ligado no cuenta
como ingreso.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database

API = '/finanzas/estados/api/expense'


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _mov(desc, monto, tipo='GASTO', categoria='EXPENSE', subcategoria='', fecha='2026-05-10', estatus=None):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos
                            (fecha, descripcion, monto, tipo, categoria, subcategoria, banco, estatus_reembolso)
                            VALUES (?, ?, ?, ?, ?, ?, 'BBVA_DEB', ?)""",
                         (fecha, desc, monto, tipo, categoria, subcategoria, estatus)).lastrowid
        db.commit()
        return rid


def _row(rid):
    with database.get_db() as db:
        return dict(db.execute("SELECT * FROM est_movimientos WHERE id=?", (rid,)).fetchone())


def _lote(client, lid):
    return next(l for l in client.get(f'{API}/lotes').get_json()['lotes'] if l['id'] == lid)


def test_ciclo_de_un_lote(client):
    f1 = _mov('HOTEL CLIENTE', -1000.0)
    f2 = _mov('TAXI CLIENTE', -250.0, fecha='2026-05-12')
    f3 = _mov('PAGO CUENTA DE TERCERO BNET EXPENSE MAYO', -394.5, estatus='TERCERO')
    dep1 = _mov('SPEI RECIBIDO FIBRA HOTELERA', 1000.0, 'INGRESO', 'OTROS')
    dep2 = _mov('SPEI RECIBIDO FIBRA HOTELERA 2', 644.5, 'INGRESO', 'FINANZAS', 'Transferencia recibida')

    cand = client.get(f'{API}/candidatos').get_json()
    assert {f1, f2, f3} <= {g['id'] for g in cand['gastos']}
    assert {dep1, dep2} <= {d['id'] for d in cand['depositos']}

    r = client.post(f'{API}/lotes', json={'nombre': 'Facturas mayo', 'gasto_ids': [f1, f2, f3], 'deposito_ids': [dep1]})
    assert r.status_code == 201
    lid = r.get_json()['id']
    l = _lote(client, lid)
    assert (l['total'], l['depositado'], l['pendiente'], l['estado']) == (1644.5, 1000.0, 644.5, 'Reembolsado parcial')
    assert l['terceros'] == 394.5 and l['desde'] == '2026-05-10' and l['hasta'] == '2026-05-12'
    assert _row(f1)['estatus_reembolso'] == 'PENDIENTE'
    assert (_row(dep1)['categoria'], _row(dep1)['subcategoria']) == ('FINANZAS', 'Reembolsable')

    assert client.post(f'{API}/lotes/{lid}/depositos', json={'movimiento_id': dep2}).status_code == 201
    l = _lote(client, lid)
    assert l['estado'] == 'Reembolsado' and l['pendiente'] == 0
    assert (_row(f1)['estatus_reembolso'], _row(f1)['fecha_reembolso']) == ('PAGADO', '2026-05-10')
    assert _row(f3)['estatus_reembolso'] == 'TERCERO'          # el compañero se queda como está

    # Quitar un depósito reabre el lote
    client.delete(f'{API}/lotes/{lid}/depositos/{dep2}')
    assert _lote(client, lid)['estado'] == 'Reembolsado parcial'
    assert _row(f2)['estatus_reembolso'] == 'PENDIENTE'

    # Ya no se ofrecen como candidatos
    cand = client.get(f'{API}/candidatos').get_json()
    assert not {f1, f2, f3} & {g['id'] for g in cand['gastos']}
    assert dep1 not in {d['id'] for d in cand['depositos']}

    client.delete(f'{API}/lotes/{lid}')
    assert client.get(f'{API}/lotes').get_json()['lotes'] == []
    assert _row(f1)['categoria'] == 'EXPENSE'                   # los movimientos no se tocan


def test_errores_no_dejan_un_lote_a_medias(client):
    f1 = _mov('HOTEL CLIENTE', -1000.0)
    no_expense = _mov('COMIDA', -100.0, categoria='COMIDA_FUERA')
    gasto = _mov('OTRO GASTO', -50.0, categoria='OTROS')
    r = client.post(f'{API}/lotes', json={'nombre': 'X', 'gasto_ids': [f1, no_expense]})
    assert r.status_code == 400
    r = client.post(f'{API}/lotes', json={'nombre': 'X', 'gasto_ids': [f1], 'deposito_ids': [gasto]})
    assert r.status_code == 400
    assert client.post(f'{API}/lotes', json={'nombre': '', 'gasto_ids': [f1]}).status_code == 400
    assert client.post(f'{API}/lotes', json={'nombre': 'X', 'gasto_ids': []}).status_code == 400
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM est_expense_lotes").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM est_expense_lote_gastos").fetchone()[0] == 0
    # Una factura no puede estar en dos lotes
    lid = client.post(f'{API}/lotes', json={'nombre': 'A', 'gasto_ids': [f1]}).get_json()['id']
    otro = client.post(f'{API}/lotes', json={'nombre': 'B', 'gasto_ids': [f1]})
    assert otro.status_code == 400 and 'otro lote' in otro.get_json()['error']
    assert client.post(f'{API}/lotes/{lid}/gastos', json={'movimiento_ids': [f1]}).status_code == 400


def test_resumen_y_aplicar_reglas(client):
    f1 = _mov('HOTEL CLIENTE', -1000.0)
    suelto = _mov('UBER CLIENTE', -120.0, estatus='PENDIENTE')
    _mov('CENA VIEJA', -300.0, estatus='PAGADO')
    dep = _mov('SPEI RECIBIDO EMPRESA', 400.0, 'INGRESO', 'OTROS', fecha='2026-06-01')
    lid = client.post(f'{API}/lotes', json={'nombre': 'Junio', 'gasto_ids': [f1], 'deposito_ids': [dep]}).get_json()['id']
    res = client.get(f'{API}/lotes').get_json()
    assert res['por_cobrar'] == 600.0 + 120.0            # pendiente del lote + suelto pendiente
    assert res['lotes_abiertos'] == 1
    assert suelto in {g['id'] for g in res['sin_lote']}

    # Una regla de keyword no saca la factura del lote ni vuelve ingreso el depósito
    with database.get_db() as db:
        db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES ('HOTEL', 'VIAJES', 'Hospedaje')")
        db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES ('SPEI RECIBIDO', 'OTROS', '')")
        db.commit()
    assert client.post('/finanzas/estados/api/keywords/apply-all').status_code == 200
    assert _row(f1)['categoria'] == 'EXPENSE'
    assert (_row(dep)['categoria'], _row(dep)['subcategoria']) == ('FINANZAS', 'Reembolsable')

    csv = client.get(f'{API}/export.csv').get_data(as_text=True)
    assert 'Junio' in csv and 'Depósito' in csv and 'Sin lote' in csv
