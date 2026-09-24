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


def test_csv_de_prestamos_para_clasificar(client, test_db):
    import csv, io
    with database.get_db() as db:
        prest, dev1, _ = _setup(db)
        suelto = _mov(db, 'RETIRO PRESTAMO SIN PERSONA', -700, 'GASTO', 'PRESTAMOS', fecha='2026-06-01')
        db.commit()
    pid = client.post('/finanzas/estados/api/prestamos', json={'movimiento_id': prest, 'persona': 'Judi'}).get_json()['id']
    client.post(f'/finanzas/estados/api/prestamos/{pid}/devoluciones', json={'movimiento_id': dev1})
    r = client.get('/finanzas/estados/api/prestamos/export.csv')
    assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
    body = r.get_data().decode('utf-8')
    assert body.startswith('﻿')
    rows = {int(x['ID']): x for x in csv.DictReader(io.StringIO(body[1:]))}
    assert (rows[prest]['Tipo'], rows[prest]['Persona'], rows[prest]['Estado'], rows[prest]['Pendiente']) == ('Préstamo', 'Judi', 'Pagado parcial', '2000.0')
    assert (rows[dev1]['Tipo'], rows[dev1]['Persona']) == ('Devolución', 'Judi')
    assert (rows[suelto]['Persona'], rows[suelto]['Estado'], rows[suelto]['Monto']) == ('', 'Sin registrar', '700.0')


# ── Clasificación del CSV corregido por el usuario (migración) ───────────────

_CSV = [  # id, fecha, tipo, descripción, monto (como en prestamos_2026-09-23_corregido.csv)
    (2571, '2026-09-11', 'GASTO', 'PAGO CUENTA DE TERCERO BNET PRESTAMO', -4500),
    (2306, '2026-07-11', 'GASTO', 'CORNELIO RETIRO SIN TARJETA ******7852', -3400),
    (2307, '2026-07-10', 'GASTO', 'PAGO CUENTA DE TERCERO BNET PRESTAMO JUDI', -1000),
    (2138, '2026-06-10', 'GASTO', 'PAGO CUENTA DE TERCERO BNET PRESTAMO A LA JUDI', -4500),
    (2088, '2026-05-15', 'GASTO', 'PAGO CUENTA DE TERCERO BNET PRESTAMO A JUDI', -1000),
    (2130, '2026-05-12', 'GASTO', 'PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', -2000),
    (2077, '2026-05-12', 'GASTO', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', -2000),
    (2073, '2026-05-11', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', -2000),
    (1836, '2026-03-08', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', -2000),
    (1772, '2026-02-23', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', -2000),
    (1679, '2026-01-25', 'GASTO', 'PAGO CUENTA DE TERCERO BNET COSITAS', -4500),
    (1560, '2025-12-22', 'INGRESO', 'PAGO CUENTA DE TERCERO BNET ABONO', 5000),
    (1534, '2025-12-15', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A AURORA EL', -150),
    (1469, '2025-11-26', 'GASTO', 'PAGO CUENTA DE TERCERO BNET COCKTELITOS', -10000),
    (1444, '2025-11-21', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', -2000),
    (2779, '2025-09-15', 'GASTO', 'PAGO CUENTA DE TERCERO BNET DEUDA EXTERNA', -7000),
    (2776, '2025-09-11', 'INGRESO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 7000),
    (2767, '2025-09-07', 'GASTO', 'PAGO CUENTA DE TERCERO BNET REGALO BODAS', -950),
    (2810, '2025-08-23', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', -500),
    (2903, '2025-07-04', 'GASTO', 'PAGO CUENTA DE TERCERO BNET JOVENES CONSTRUYEN', -1500),
    (2898, '2025-07-02', 'INGRESO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 1500),
    (2872, '2025-06-11', 'INGRESO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 600),
    (2870, '2025-06-11', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', -412),
    (2864, '2025-06-07', 'GASTO', 'PAGO CUENTA DE TERCERO BNET URGE', -600),
    (3004, '2025-03-27', 'GASTO', 'PAGO CUENTA DE TERCERO BNET JEFE DE FAMIL REPO', -2513),
    (3003, '2025-03-27', 'INGRESO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 2512),
    (2999, '2025-03-24', 'GASTO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', -1000),
    (3028, '2025-02-24', 'INGRESO', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 500),
    (3026, '2025-02-23', 'GASTO', 'PAGO CUENTA DE TERCERO BNET PRESTAMO CON INTER', -500),
    (3785, '2023-06-16', 'GASTO', 'PAGO CUENTA DE TERCERO BNET PRESTAMO GIO', -7000),
]


def _sembrar_csv(db, skip=()):
    db.execute("DELETE FROM migration_log WHERE version='finanzas_prestamos_clasificacion_csv_2026_09'")
    for mid, fecha, tipo, desc, monto in _CSV:
        if mid in skip:
            continue
        db.execute("INSERT INTO est_movimientos (id, fecha, fecha_cargo, descripcion, monto, banco, periodo, "
                   "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,'BBVA_DEB','','PRESTAMOS','',?)",
                   (mid, fecha, fecha, desc, monto, tipo))
    db.commit()


def test_migracion_csv_registra_personas_y_liga_devoluciones(test_db):
    from modules.finanzas.estados.prestamos import resumen
    with database.get_db() as db:
        _sembrar_csv(db)
    database.init_db()
    database.init_db()   # segunda corrida: no duplica
    with database.get_db() as db:
        r = resumen(db)
        by = {g['persona']: g for g in r['personas']}
        assert set(by) == {'Judi', 'Cornelius', 'Aurora'}
        assert (by['Judi']['prestado'], by['Judi']['devuelto'], by['Judi']['pendiente']) == (49975, 21612, 28363)
        assert (by['Cornelius']['prestado'], by['Cornelius']['pendiente']) == (5400, 5400)
        assert by['Aurora']['pendiente'] == 150
        assert r['total_pendiente'] == 33913
        est = {p['movimiento_id']: p['estado'] for g in r['personas'] for p in g['prestamos']}
        assert est[2138] == 'Pagado'          # 2571 convertido en devolución
        assert est[1469] == 'Pagado parcial'  # ABONO 1560 de 5,000
        assert est[3004] == 'Pagado parcial'  # 2,513 vs 2,512 devueltos
        assert est[2779] == est[2903] == est[2864] == est[3026] == 'Pagado'
        assert 2077 not in est and 2999 not in est
        assert db.execute("SELECT tipo FROM est_movimientos WHERE id=2571").fetchone()['tipo'] == 'INGRESO'
        assert db.execute("SELECT COUNT(*) c FROM est_prestamos").fetchone()['c'] == 21


def test_migracion_csv_respeta_lo_hecho_a_mano_y_omite_lo_que_no_coincide(test_db):
    with database.get_db() as db:
        _sembrar_csv(db, skip={3785})
        db.execute("UPDATE est_movimientos SET monto=-999 WHERE id=1534")          # no coincide: se omite
        db.execute("INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, movimiento_id, created_at) "
                   "VALUES ('Leni', 'OTORGADO', 1000, '2026-07-10', 2307, '2026-09-24')")  # ya registrado a mano
        db.commit()
    database.init_db()
    with database.get_db() as db:
        personas = dict(db.execute("SELECT movimiento_id, contraparte FROM est_prestamos").fetchall())
        log = db.execute("SELECT description FROM migration_log WHERE version='finanzas_prestamos_clasificacion_csv_2026_09'").fetchone()['description']
    assert personas[2307] == 'Leni'
    assert 1534 not in personas and 3785 not in personas
    assert 'préstamo 1534: no coincide' in log and 'préstamo 3785: no coincide' in log
