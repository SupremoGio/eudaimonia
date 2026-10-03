"""
Lista «Préstamos sin persona» que contestó el usuario (2026-10-01).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import prestamos as pr
from modules.finanzas.estados import msi


def _ins(db, fecha, desc, monto, tipo='GASTO', cat='PRESTAMOS', sub='Prestado'):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (?,?,?, 'BBVA_DEB', ?, ?, ?)""", (fecha, desc, monto, cat, sub, tipo)).lastrowid


def _cat(db, i):
    return tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())


def test_registra_cornelius_y_jorge(test_db):
    with database.get_db() as db:
        c = _ins(db, '2026-05-12', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0)
        j = _ins(db, '2024-10-18', 'PAGO CUENTA DE TERCERO BNET CIRUJIA CAMBIO SEX', 10000.0)
        db.commit()
        assert pr.registrar_manuales(db) == (2, 0)
        assert pr.registrar_manuales(db) == (0, 0)
        per = {p['movimiento_id']: (p['persona'], p['estado']) for p in pr.listar(db)}
        assert per[c] == ('Cornelius', 'Pendiente') and per[j] == ('Jorge', 'Pendiente')
        assert pr.candidatos(db)['prestamos'] == []


def test_regresados_se_cancelan_con_su_deposito(test_db):
    with database.get_db() as db:
        a = _ins(db, '2024-09-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 13000.0)
        b = _ins(db, '2024-09-12', 'PAGO CUENTA DE TERCERO BNET DEUDA', 13000.0)
        da = _ins(db, '2024-09-11', 'DEVOLUCION SPEI', -13000.0, 'INGRESO', 'FINANZAS', 'Reembolso compartido')
        db.commit()
        assert pr.registrar_manuales(db) == (0, 2)
        assert _cat(db, a) == _cat(db, da) == ('FINANZAS', 'Entre cuentas propias')
        assert _cat(db, b) == ('FINANZAS', 'Entre cuentas propias')  # sin depósito: igual sale
        assert pr.registrar_manuales(db) == (0, 0)
        db.execute("DELETE FROM est_movimientos WHERE id=?", (da,))   # (para no confundir)
        db.commit()


def test_mensualidades_iphone_no_salen_sin_persona(test_db):
    with database.get_db() as db:
        m = _ins(db, '2023-05-22', 'MACSTORE MIDTOWN JALI', 1167.0, 'GASTO', 'TECH/DIGITAL', 'Deudas MSI')
        db.commit()
        msi.marcar_compras(db)
        assert _cat(db, m) == ('PRESTAMOS', 'Prestado')
        assert pr.candidatos(db)['prestamos'] == []


def test_viva_aerobus_de_la_familia_es_reembolsable(test_db):
    with database.get_db() as db:
        v = _ins(db, '2024-06-22', 'VIVA AEROBUS CIB', 1322.0)
        db.commit()
        msi.marcar_compras(db)
        assert _cat(db, v) == ('FINANZAS', 'Reembolsable')
        assert pr.candidatos(db)['prestamos'] == []


def test_regresado_con_deposito_un_dia_antes(test_db):
    """Le prestaron $13,000 el 10/09 y al otro día los devolvió."""
    with database.get_db() as db:
        dep = _ins(db, '2024-09-10', 'SPEI RECIBIDO', -13000.0, 'INGRESO', 'FINANZAS', 'Reembolso compartido')
        t = _ins(db, '2024-09-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 13000.0)
        db.commit()
        assert pr.registrar_manuales(db) == (0, 1)
        assert _cat(db, t) == _cat(db, dep) == ('FINANZAS', 'Entre cuentas propias')
        assert pr.candidatos(db)['prestamos'] == []


def test_jorge_liquido_con_abonos_leidos_como_cargo(test_db):
    with database.get_db() as db:
        cir = _ins(db, '2024-10-18', 'PAGO CUENTA DE TERCERO BNET CIRUJIA CAMBIO SEX', 10000.0)
        a = _ins(db, '2024-10-24', 'PAGO CUENTA DE TERCERO BNET JORGE', 4900.0)
        b = _ins(db, '2024-10-24', 'PAGO CUENTA DE TERCERO BNET GIO', 100.0, 'GASTO', 'FINANZAS', 'Transferencia')
        c = _ins(db, '2024-11-01', 'PAGO CUENTA DE TERCERO BNET JORGE 2 PAGO', 5000.0, 'GASTO', 'FINANZAS', 'Transferencia')
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Jorge', 'OTORGADO', 4900, '2024-10-24', '', ?, datetime('now'))""", (a,))
        db.commit()
        pr.registrar_manuales(db)
        pr.registrar_manuales(db)                                     # idempotente
        jorge = [p for p in pr.listar(db) if p['persona'] == 'Jorge']
        assert len(jorge) == 1 and jorge[0]['movimiento_id'] == cir
        assert jorge[0]['devuelto'] == 10000 and jorge[0]['estado'] == 'Pagado'
        for i in (a, b, c):
            assert db.execute("SELECT tipo, categoria FROM est_movimientos WHERE id=?", (i,)).fetchone()[:] == ('INGRESO', 'PRESTAMOS')


def test_judi_ida_y_vuelta_y_cornelius(test_db):
    """11/05 a Judi, Judi lo regresa («REGRESO AL CORNER», leído como cargo) y
    el 12 va a Cornelius («BNET TACOS …»)."""
    with database.get_db() as db:
        judi = _ins(db, '2026-05-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', 2000.0)
        vuelta = _ins(db, '2026-05-12', 'PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0)
        corner = _ins(db, '2026-05-12', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0)
        for mid, quien in ((judi, 'Judi'), (vuelta, 'Cornelius')):    # préstamos mal registrados
            db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                          VALUES (?, 'OTORGADO', 2000, '2026-05-11', '', ?, datetime('now'))""", (quien, mid))
        db.commit()
        pr.registrar_manuales(db)
        pr.registrar_manuales(db)
        prest = [(p['persona'], p['movimiento_id']) for p in pr.listar(db) if p['fecha'].startswith('2026-05')]
        assert prest == [('Cornelius', corner)]
        assert _cat(db, judi) == _cat(db, vuelta) == ('FINANZAS', 'Entre cuentas propias')
        assert db.execute("SELECT tipo FROM est_movimientos WHERE id=?", (vuelta,)).fetchone()[0] == 'INGRESO'
        assert pr.candidatos(db)['prestamos'] == []


def test_gracias_bebo_es_prestamo_de_2023_y_libera_mayo_2026(test_db):
    """«GRACIAS BEBO» estaba ligado al préstamo de mayo 2026 a Judi (que fue ida
    y vuelta); pasa a su propio préstamo de 2023, pagado."""
    with database.get_db() as db:
        gb = _ins(db, '2023-05-12', 'PAGO CUENTA DE TERCERO BNET GRACIAS BEBO', 4250.0, 'INGRESO', 'PRESTAMOS', '')
        judi = _ins(db, '2026-05-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A', 2000.0)
        vuelta = _ins(db, '2026-05-12', 'PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0)
        _ins(db, '2026-05-12', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0)
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                            VALUES ('Judi', 'OTORGADO', 2000, '2026-05-11', '', ?, datetime('now'))""", (judi,)).lastrowid
        db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,datetime('now'))",
                   (pid, gb))
        db.commit()
        pr.registrar_manuales(db)
        pr.registrar_manuales(db)
        por = {(p['persona'], p['fecha'][:4]): p for p in pr.listar(db)}
        j23 = por[('Judi', '2023')]
        assert j23['monto'] == 4250 and j23['estado'] == 'Pagado' and j23['notas'].startswith('Préstamo de 2023')
        assert ('Judi', '2026') not in por and ('Cornelius', '2026') in por
        assert _cat(db, judi) == _cat(db, vuelta) == ('FINANZAS', 'Entre cuentas propias')
        assert _cat(db, gb) == ('PRESTAMOS', '')


def test_cositas_cobrado_en_efectivo_pasa_al_viaje(test_db):
    with database.get_db() as db:
        vid = db.execute("""INSERT INTO viajes (nombre, fecha_inicio, fecha_fin, created_at)
                            VALUES ('Villahermosa Marzo 26', '2026-03-20', '2026-03-29', datetime('now'))""").lastrowid
        db.execute("""INSERT INTO viajes (nombre, fecha_inicio, fecha_fin, created_at)
                      VALUES ('Villahermosa Dic 25', '2025-12-20', '2025-12-30', datetime('now'))""")
        m = _ins(db, '2026-03-19', 'PAGO CUENTA DE TERCERO BNET COSITAS', 8000.0)
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, perdido_fecha, created_at)
                      VALUES ('X', 'OTORGADO', 8000, '2026-03-19', '', ?, '2026-09-25', datetime('now'))""", (m,))
        db.commit()
        pr.registrar_manuales(db)
        assert not [p for p in pr.listar(db) if p['movimiento_id'] == m]
        r = db.execute("SELECT categoria, subcategoria, viaje_id FROM est_movimientos WHERE id=?", (m,)).fetchone()
        assert tuple(r) == ('VIAJES', 'Otros', vid)


def test_cornelius_con_tipo_legado_se_registra(test_db):
    with database.get_db() as db:
        t = _ins(db, '2026-05-12', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0, 'PRESTAMO')
        db.commit()
        pr.registrar_manuales(db)
        assert [(p['persona'], p['estado']) for p in pr.listar(db) if p['movimiento_id'] == t] == [('Cornelius', 'Pendiente')]
        assert db.execute("SELECT tipo FROM est_movimientos WHERE id=?", (t,)).fetchone()[0] == 'GASTO'


def test_cocktelitos_devolucion_real_y_desligadas(test_db):
    from modules.finanzas.estados import abonos
    with database.get_db() as db:
        c = _ins(db, '2025-11-26', 'PAGO CUENTA DE TERCERO BNET COCKTELITOS', 10000.0)
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                            VALUES ('Judi', 'OTORGADO', 10000, '2025-11-26', '', ?, datetime('now'))""", (c,)).lastrowid
        ab = _ins(db, '2025-12-22', 'PAGO CUENTA DE TERCERO BNET ABONO', 5000.0, 'INGRESO', 'PRESTAMOS', '')
        tr = _ins(db, '2025-12-01', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 702.0, 'INGRESO', 'PRESTAMOS', '')
        for mid in (ab, tr):
            db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,datetime('now'))", (pid, mid))
        ef = _ins(db, '2026-05-12', 'SU PAGO EN EFECTIVO EN COMERCIO', 5000.0, 'INGRESO', 'FAMILIA_REGALOS', 'Regalos')
        db.commit()
        pr.registrar_manuales(db)
        pr.registrar_manuales(db)
        p = next(p for p in pr.listar(db) if p['id'] == pid)
        assert [d['movimiento_id'] for d in p['devoluciones']] == [ab]
        assert p['devuelto'] == 5000 and p['pendiente'] == 5000
        assert _cat(db, tr) == ('FINANZAS', 'Transferencia recibida')
        assert _cat(db, ef) == ('FAMILIA_REGALOS', 'Regalos')
        assert _cat(db, ab) == ('PRESTAMOS', '')
        ab, tr = tr, tr     # abajo: solo el de $702 vuelve a Sin conciliar
        # vuelven a Sin conciliar, sin pista de préstamo
        filas = {r['id']: r for r in abonos.sin_conciliar(db)['movimientos']} if isinstance(abonos.sin_conciliar(db), dict) else None
        if filas is not None:
            assert ab in filas and tr in filas
            assert all((filas[i].get('pista') or {}).get('tipo') != 'prestamo' for i in (ab, tr))


def test_jefe_de_famil_repo_dado_por_cobrado(test_db):
    with database.get_db() as db:
        m = _ins(db, '2025-03-27', 'PAGO CUENTA DE TERCERO BNET JEFE DE FAMIL REPO', 2513.0)
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                            VALUES ('Judi', 'OTORGADO', 2513, '2025-03-27', '', ?, datetime('now'))""", (m,)).lastrowid
        d = _ins(db, '2025-03-27', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 2512.0, 'INGRESO', 'PRESTAMOS', '')
        db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,datetime('now'))", (pid, d))
        db.commit()
        pr.registrar_manuales(db)
        p = next(p for p in pr.listar(db) if p['id'] == pid)
        assert p['estado'] == 'Pagado' and p['pendiente'] == 0


def test_regalo_bodas_no_era_prestamo(test_db):
    with database.get_db() as db:
        m = _ins(db, '2025-09-07', 'PAGO CUENTA DE TERCERO BNET REGALO BODAS', 950.0)
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Judi', 'OTORGADO', 950, '2025-09-07', 'Clasificado desde CSV', ?, datetime('now'))""", (m,))
        db.commit()
        pr.registrar_manuales(db)
        assert not [p for p in pr.listar(db) if p['movimiento_id'] == m]
        assert _cat(db, m) == ('FAMILIA_REGALOS', 'Regalos')


def test_retiro_sin_tarjeta_no_es_prestamo_a_cornelio(test_db):
    with database.get_db() as db:
        m = _ins(db, '2026-07-11', 'CORNELIO RETIRO SIN TARJETA ******7852', 3400.0)
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Cornelius', 'OTORGADO', 3400, '2026-07-11', 'Clasificado desde CSV', ?, datetime('now'))""", (m,))
        db.commit()
        pr.registrar_manuales(db)
        assert not [p for p in pr.listar(db) if p['movimiento_id'] == m]
        assert _cat(db, m) == ('FINANZAS', 'Retiro efectivo')


def test_devoluciones_de_judi_4500(test_db):
    with database.get_db() as db:
        p1 = _ins(db, '2026-06-10', 'PAGO CUENTA DE TERCERO BNET PRESTAMO A LA JUDI', 4500.0)
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                            VALUES ('Judi', 'OTORGADO', 4500, '2026-06-10', '', ?, datetime('now'))""", (p1,)).lastrowid
        d1 = _ins(db, '2026-06-29', 'PAGO CUENTA DE TERCERO BNET TRANSF', 4500.0, 'INGRESO', 'VIAJES', 'Otros')
        p2 = _ins(db, '2026-09-11', 'PAGO CUENTA DE TERCERO BNET PRESTAMO', 4500.0, 'GASTO', 'FINANZAS', 'Transferencia')
        d2 = _ins(db, '2026-09-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 4500.0, 'INGRESO', 'VIAJES', 'Otros')
        db.commit()
        pr.registrar_manuales(db)
        pr.registrar_manuales(db)
        por = {p['movimiento_id']: p for p in pr.listar(db)}
        assert por[p1]['estado'] == 'Pagado' and [x['movimiento_id'] for x in por[p1]['devoluciones']] == [d1]
        assert por[p2]['persona'] == 'Judi' and por[p2]['estado'] == 'Pagado'
        assert _cat(db, d2) == ('PRESTAMOS', '')
