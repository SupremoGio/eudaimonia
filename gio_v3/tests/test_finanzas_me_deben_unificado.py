"""«Me deben» unificado en Por cobrar (2026-10-18): los Compromisos «me deben»
de Salud se migran a est_prestamos, un gasto puede quedar «te deben parte»
(mi_parte = total − lo que te deben) y hay abonos sin movimiento del banco."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.finanzas.estados import prestamos as prest


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = sess["fin_ok"] = True
        yield c


def _mov(db, desc, monto, tipo, cat, fecha='2026-08-10', sub=''):
    return db.execute(
        "INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, "
        "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,?)",
        (fecha, fecha, desc, monto, 'BBVA_DEB', '', cat, sub, tipo)).lastrowid


def test_migra_compromisos_me_deben(test_db):
    with database.get_db() as db:
        dep = _mov(db, 'SPEI RECIBIDO ELI', 850, 'INGRESO', 'FINANZAS', fecha='2026-03-02', sub='Reembolso compartido')
        abierto = db.execute("""INSERT INTO debts (type, person, concept, amount, monto_total, monto_restante, settled, created_at)
                                VALUES ('owe_me', 'Eli', 'Viaje GDL', 3000, 3000, 1650, 0, '2026-02-01T10:00:00')""").lastrowid
        p1 = db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?, 850, 'spei', '2026-03-02T09:00:00')",
                        (abierto,)).lastrowid
        db.execute("INSERT INTO debt_payment_movs (payment_id, movimiento_id, created_at) VALUES (?, ?, '2026-03-02')", (p1, dep))
        db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?, 500, 'efectivo', '2026-04-01T09:00:00')",
                   (abierto,))
        db.execute("""INSERT INTO debts (type, person, concept, amount, monto_total, monto_restante, settled, created_at)
                      VALUES ('owe_me', 'Pops', 'Cena', 400, 400, 0, 1, '2025-11-01T10:00:00')""")
        db.execute("""INSERT INTO debts (type, person, concept, amount, monto_total, monto_restante, settled, created_at)
                      VALUES ('i_owe', 'Banco', 'Tarjeta', 1000, 1000, 1000, 0, '2026-01-01T10:00:00')""")
        # init_db ya corrió la migración con la tabla vacía; esta toma lo nuevo
        assert prest.migrar_compromisos(db) == 3
        assert prest.migrar_compromisos(db) == 0   # idempotente
        db.commit()
        por = {p['persona']: p for p in prest.listar(db)}
        assert set(por) == {'Eli', 'Pops'}
        assert [(p['persona'], p['pendiente']) for p in prest.listar(db, 'RECIBIDO')] == [('Banco', 1000)]   # «Debo»
        eli = por['Eli']
        assert (eli['monto'], eli['devuelto'], eli['pendiente'], eli['estado']) == (3000, 1350, 1650, 'Pagado parcial')
        assert [d['movimiento_id'] for d in eli['devoluciones']] == [dep]
        assert [(a['monto'], a['nota']) for a in eli['abonos']] == [(500, 'efectivo')]
        assert eli['concepto'] == 'Viaje GDL' and eli['fecha'] == '2026-02-01'
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (dep,)).fetchone()[0] == 'PRESTAMOS'
        assert por['Pops']['estado'] == 'Pagado'   # liquidado: el resto queda como abono «Liquidado»
        assert prest.total_por_cobrar(db) == 1650
        assert db.execute("SELECT COUNT(*) FROM debts").fetchone()[0] == 3   # debts queda de respaldo


def test_gasto_compartido_cuenta_solo_tu_parte(client):
    with database.get_db() as db:
        seguro = _mov(db, 'QUALITAS SEGURO AUTO', -9000, 'GASTO', 'TRANSPORTE', sub='Seguro')
        db.commit()
    r = client.post('/finanzas/estados/api/prestamos',
                    json={'movimiento_id': seguro, 'persona': 'Ale', 'monto': 4500, 'compartido': True})
    assert r.status_code == 201
    pid = r.get_json()['id']
    with database.get_db() as db:
        m = db.execute("SELECT categoria, subcategoria, mi_parte FROM est_movimientos WHERE id=?", (seguro,)).fetchone()
        assert (m['categoria'], m['subcategoria'], m['mi_parte']) == ('TRANSPORTE', 'Seguro', 4500)
        prest.reafirmar_categorias(db)   # no lo vuelve PRESTAMOS: el gasto sigue siendo tuyo en parte
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (seguro,)).fetchone()[0] == 'TRANSPORTE'
        p = prest.uno(db, pid)
        assert p['compartido'] and p['concepto'] == 'QUALITAS SEGURO AUTO' and p['mov_monto'] == 9000

    assert client.patch(f'/finanzas/estados/api/prestamos/{pid}', json={'monto': 3000}).status_code == 200
    assert client.patch(f'/finanzas/estados/api/prestamos/{pid}', json={'monto': 9500}).status_code == 400
    with database.get_db() as db:
        assert db.execute("SELECT mi_parte FROM est_movimientos WHERE id=?", (seguro,)).fetchone()[0] == 6000

    # Salud financiera lo muestra en «Me deben» con sus rutas de Por cobrar
    html = client.get('/finanzas/salud/').get_data(as_text=True)
    assert f'data-abonar="{pid}" data-kind="prestamo"' in html and 'Ale' in html

    # abono en efectivo desde Por cobrar, y se puede quitar
    r = client.post(f'/finanzas/estados/api/prestamos/{pid}/abonos', json={'monto': 1000, 'nota': 'efectivo'})
    assert r.status_code == 201
    assert client.post(f'/finanzas/estados/api/prestamos/{pid}/abonos', json={'monto': 5000}).status_code == 400
    with database.get_db() as db:
        assert prest.uno(db, pid)['pendiente'] == 2000
    client.delete(f"/finanzas/estados/api/prestamos/{pid}/abonos/{r.get_json()['id']}")

    # borrar lo que te deben: el gasto vuelve a ser 100 % tuyo
    assert client.delete(f'/finanzas/estados/api/prestamos/{pid}').status_code == 200
    with database.get_db() as db:
        assert db.execute("SELECT mi_parte FROM est_movimientos WHERE id=?", (seguro,)).fetchone()[0] is None


def test_prestamo_con_movimiento_sigue_igual(client):
    """Prestar con un movimiento (sin compartido) no cambió: todo el gasto es PRESTAMOS."""
    with database.get_db() as db:
        spei = _mov(db, 'SPEI ENVIADO JUAN', -3000, 'GASTO', 'FINANZAS', sub='Transferencia enviada')
        db.commit()
    r = client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': spei, 'persona': 'Juan'})
    assert r.status_code == 201
    assert client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': spei, 'persona': 'Juan'}).status_code == 409
    with database.get_db() as db:
        m = db.execute("SELECT categoria, mi_parte FROM est_movimientos WHERE id=?", (spei,)).fetchone()
        assert (m['categoria'], m['mi_parte']) == ('PRESTAMOS', None)
        assert prest.uno(db, r.get_json()['id'])['monto'] == 3000
    # sin movimiento ni monto no se puede
    assert client.post('/finanzas/estados/api/prestamos', json={'persona': 'Juan'}).status_code == 400


def test_me_prestaron_y_pagos_no_cuentan(client):
    """«Debo» por préstamo: el ingreso con el que te prestaron no es ingreso y
    tus transferencias para pagarle no son gasto."""
    with database.get_db() as db:
        ing = _mov(db, 'SPEI RECIBIDO POPS', 13000, 'INGRESO', 'FINANZAS', fecha='2026-09-01', sub='Transferencia recibida')
        pago = _mov(db, 'SPEI ENVIADO POPS', -5000, 'GASTO', 'FINANZAS', fecha='2026-10-01', sub='Transferencia enviada')
        db.commit()
    r = client.post('/finanzas/estados/api/prestamos', json={'direccion': 'RECIBIDO', 'movimiento_id': ing, 'persona': 'Pops'})
    assert r.status_code == 201
    pid = r.get_json()['id']
    info = client.get(f'/finanzas/estados/api/prestamos/movimiento/{pago}').get_json()
    assert [d['id'] for d in info['deudas']] == [pid] and info['pago_de'] is None
    cand = client.get(f'/finanzas/api/prestamo/{pid}/candidatos').get_json()['depositos']
    assert [m['id'] for m in cand] == [pago]   # el ingreso de origen no es candidato
    assert client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': ing}).status_code == 400
    assert client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': pago}).status_code == 201
    with database.get_db() as db:
        cats = dict(db.execute("SELECT id, categoria FROM est_movimientos WHERE id IN (?,?)", (ing, pago)).fetchall())
        assert cats == {ing: 'PRESTAMOS', pago: 'PRESTAMOS'}
        p = prest.uno(db, pid)
        assert (p['direccion'], p['monto'], p['pendiente']) == ('RECIBIDO', 13000, 8000)
        assert prest.total_por_cobrar(db, 'RECIBIDO') == 8000 and prest.total_por_cobrar(db) == 0
        from modules.finanzas.estados import abonos
        assert ing not in {m['id'] for m in abonos.sin_conciliar(db)['movimientos']}   # ya conciliado
    html = client.get('/finanzas/salud/').get_data(as_text=True)
    assert f'data-abonar="{pid}" data-kind="prestamo" data-dir="i_owe"' in html
    # quitar el pago: vuelve a Sin clasificar
    client.delete(f'/finanzas/estados/api/prestamos/{pid}/devoluciones/{pago}')
    with database.get_db() as db:
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (pago,)).fetchone()[0] == 'OTROS'


def test_pagaron_por_mi_el_pago_es_gasto_real(client):
    """«Debo» porque alguien pagó algo por ti: tu pago sí es gasto, de esa categoría."""
    client.post('/finanzas/api/debt', json={'type': 'i_owe', 'person': 'Ale', 'concept': 'Cena cumple',
                                            'amount': 800, 'pago_cat': 'COMIDA_FUERA'})
    with database.get_db() as db:
        pid = db.execute("SELECT id FROM est_prestamos WHERE direccion='RECIBIDO'").fetchone()[0]
        pago = _mov(db, 'SPEI ENVIADO ALE', -800, 'GASTO', 'OTROS', fecha='2026-10-02')
        db.commit()
    r = client.post(f'/finanzas/api/prestamo/{pid}/abonar', json={'movimiento_ids': [pago]})
    assert r.get_json()['settled'] is True
    with database.get_db() as db:
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (pago,)).fetchone()[0] == 'COMIDA_FUERA'
        prest.reafirmar_categorias(db)   # no lo vuelve PRESTAMOS
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (pago,)).fetchone()[0] == 'COMIDA_FUERA'
    h = client.get(f'/finanzas/api/prestamo/{pid}/historial').get_json()
    assert h['type'] == 'i_owe' and h['pago_cat'] == 'COMIDA_FUERA' and h['monto_restante'] == 0
