"""
test_finanzas_prestamos_por_cobrar.py — seguimiento de préstamos (paso 1b):
persona, monto, devoluciones ligadas (varias), pendiente, estado calculado,
«Perdido» manual que se vuelve gasto de Familia y regalos en la Radiografía,
reporte de duplicados de solo lectura y normalización de tipo PRESTAMO.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database


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


def _mov(db, desc, monto, tipo, cat, fecha='2026-08-10', sub=''):
    return db.execute(
        "INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, "
        "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,?)",
        (fecha, fecha, desc, monto, 'BBVA', '', cat, sub, tipo)).lastrowid


def _setup(db):
    prest = _mov(db, 'SPEI ENVIADO JUAN', -3000, 'GASTO', 'FINANZAS', sub='Transferencia enviada')
    dev1 = _mov(db, 'SPEI RECIBIDO JUAN 1', 1000, 'INGRESO', 'FINANZAS', fecha='2026-08-20')
    dev2 = _mov(db, 'SPEI RECIBIDO JUAN 2', 500, 'INGRESO', 'OTROS', fecha='2026-09-01')
    db.commit()
    return prest, dev1, dev2


def test_ciclo_completo_de_un_prestamo(client, test_db):
    with database.get_db() as db:
        prest, dev1, dev2 = _setup(db)

    cand = client.get('/finanzas/estados/api/prestamos/candidatos').get_json()
    assert dev1 in [m['id'] for m in cand['devoluciones']]

    r = client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': prest, 'persona': 'Juan'})
    assert r.status_code == 201
    pid = r.get_json()['id']
    # El movimiento queda como PRESTAMOS: ya no es gasto
    with database.get_db() as db:
        m = db.execute("SELECT categoria, tipo FROM est_movimientos WHERE id=?", (prest,)).fetchone()
    assert (m['categoria'], m['tipo']) == ('PRESTAMOS', 'GASTO')
    assert client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': prest, 'persona': 'X'}).status_code == 409

    res = client.get('/finanzas/estados/api/prestamos').get_json()
    assert res['total_pendiente'] == 3000
    assert res['personas'][0]['prestamos'][0]['estado'] == 'Pendiente'

    for dev in (dev1, dev2):
        assert client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': dev}).status_code == 201
    p = client.get('/finanzas/estados/api/prestamos').get_json()['personas'][0]
    assert (p['persona'], p['devuelto'], p['pendiente']) == ('Juan', 1500, 1500)
    assert p['prestamos'][0]['estado'] == 'Pagado parcial'
    assert len(p['prestamos'][0]['devoluciones']) == 2
    # La devolución ligada ya no es ingreso: queda como PRESTAMOS
    with database.get_db() as db:
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (dev2,)).fetchone()['categoria'] == 'PRESTAMOS'
    # Un ingreso no se liga dos veces
    assert client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': dev1}).status_code == 409


def test_estado_pagado_y_desligar():
    from modules.finanzas.estados.prestamos import estado
    assert estado(1000, 0, None) == 'Pendiente'
    assert estado(1000, 400, None) == 'Pagado parcial'
    assert estado(1000, 1000, None) == 'Pagado'
    assert estado(1000, 400, '2026-09-01') == 'Perdido'


def test_perdido_suma_a_familia_y_regalos_en_el_mes_que_se_marca(client, test_db):
    from modules.finanzas.budget import _calc_budget
    from utils import today_str
    with database.get_db() as db:
        prest, dev1, _ = _setup(db)
    pid = client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': prest, 'persona': 'Juan'}).get_json()['id']
    client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': dev1})
    client.patch(f'/finanzas/estados/api/prestamos/{pid}', json={'perdido': True})

    res = client.get('/finanzas/estados/api/prestamos').get_json()
    assert res['total_pendiente'] == 0 and res['total_perdido'] == 2000
    assert res['personas'][0]['prestamos'][0]['perdido_fecha'] == today_str()

    mes = today_str()[:7]
    with database.get_db() as db:
        d = _calc_budget(mes, db)
    fam = [c for c in d['buckets']['deseos']['cats'] if c['categoria'] == 'FAMILIA_REGALOS']
    assert fam and fam[0]['gastado'] == 2000

    client.patch(f'/finanzas/estados/api/prestamos/{pid}', json={'perdido': False})
    with database.get_db() as db:
        d = _calc_budget(mes, db)
    assert not [c for c in d['buckets']['deseos']['cats'] if c['categoria'] == 'FAMILIA_REGALOS']


def test_aplicar_reglas_no_saca_de_prestamos_a_los_movimientos_ligados(client, test_db):
    with database.get_db() as db:
        prest, dev1, _ = _setup(db)
        db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES ('SPEI', 'FINANZAS', 'Transferencia')")
        db.commit()
    pid = client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': prest, 'persona': 'Juan'}).get_json()['id']
    client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': dev1})
    assert client.post('/finanzas/estados/api/keywords/apply-all').status_code in (200, 201)
    with database.get_db() as db:
        cats = {r['id']: r['categoria'] for r in db.execute(
            "SELECT id, categoria FROM est_movimientos WHERE id IN (?,?)", (prest, dev1))}
    assert cats == {prest: 'PRESTAMOS', dev1: 'PRESTAMOS'}


def test_duplicados_es_solo_lectura(client, test_db):
    with database.get_db() as db:
        _mov(db, 'PRESTAMO ANA EFECTIVO', -800, 'GASTO', 'PRESTAMOS', fecha='2026-07-02')
        _mov(db, 'SPEI ENVIADO ANA', -800, 'GASTO', 'PRESTAMOS', fecha='2026-07-02')
        _mov(db, 'OTRO', -800, 'GASTO', 'OCIO', fecha='2026-07-02')
        db.commit()
        n0 = db.execute("SELECT COUNT(*) c FROM est_movimientos").fetchone()['c']
    dup = client.get('/finanzas/estados/api/prestamos/duplicados').get_json()
    assert len(dup) == 1 and dup[0]['monto'] == 800 and len(dup[0]['movimientos']) == 2
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) c FROM est_movimientos").fetchone()['c'] == n0


def test_migracion_normaliza_tipo_prestamo(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_prestamos_tipo_real_2026_09'")
        a = _mov(db, 'PRESTAMO VIEJO', 500, 'PRESTAMO', 'OTROS')
        b = _mov(db, 'COBRO VIEJO', 500, 'COBRO_PRESTAMO', 'OTROS')
        db.commit()
    database.init_db()
    database.init_db()   # segunda corrida: no rompe ni duplica
    with database.get_db() as db:
        rows = {r['id']: (r['tipo'], r['categoria']) for r in db.execute(
            "SELECT id, tipo, categoria FROM est_movimientos WHERE id IN (?,?)", (a, b))}
    assert rows == {a: ('GASTO', 'PRESTAMOS'), b: ('INGRESO', 'PRESTAMOS')}
