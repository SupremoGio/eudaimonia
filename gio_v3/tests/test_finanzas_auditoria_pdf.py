"""Auditoría 2022-2026 contra los PDF de BBVA (modules/finanzas/estados/auditoria_pdf.py).

La base se arma con las mismas filas del CSV de auditoría, tal como las tenía
la app (id_app, descripción, tipo y categoría de la app), más los «gemelos» de
los posibles duplicados."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import auditoria_pdf as aud


def _sembrar(db, sin_gemelos=()):
    for f in aud.filas():
        if not f['id_app']:
            continue
        cat, _, sub = f['categoria_app'].partition('/')
        monto = float(f['monto'])
        if (mn := aud._monto_app_nota(f)):
            monto = mn[0]
        db.execute("""INSERT OR IGNORE INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria,
                      subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?)""",
                   (int(f['id_app']), f['fecha'], f['descripcion_app'], monto, f['banco'], cat, sub, f['tipo_app']))
    for f in aud.filas():
        dup = re.search(r'posible duplicado de id ([\d,\s]+)', f['nota'])
        for i in re.findall(r'\d+', dup.group(1) if dup else ''):
            if int(i) not in sin_gemelos:
                db.execute("""INSERT OR IGNORE INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria,
                              subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?)""",
                           (int(i), f['fecha'], f'GEMELO {i}', float(f['monto']), f['banco'], 'X', '', 'GASTO'))


def _fila(db, i):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (i,)).fetchone()


def test_simulacion_no_escribe_y_aplicar_es_idempotente(test_db):
    with database.get_db() as db:
        _sembrar(db)
        antes = db.execute("SELECT COUNT(*), SUM(monto) FROM est_movimientos").fetchone()[:]
        plan = aud.plan(db)
        assert db.execute("SELECT COUNT(*), SUM(monto) FROM est_movimientos").fetchone()[:] == antes
        assert len({(l['estado_auditoria'], l['fecha'], l['monto'], l['id_app']) for l in plan}) >= 280
        aud.aplicar(db, plan)
        db.commit()
        segunda = aud.plan(db)
        assert {l['accion'] for l in segunda} <= {'sin cambio', 'pendiente revisión'}
        assert db.execute("SELECT 1 FROM migration_log WHERE version=?", (aud.VERSION,)).fetchone()


def test_correcciones(test_db):
    with database.get_db() as db:
        _sembrar(db)
        dev = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                              VALUES ('2024-10-09', 'SPEI DEVUELTO BANORTE', 11000, 'BBVA_DEB', 'FINANZAS',
                                      'Transferencia recibida', 'INGRESO')""").lastrowid
        aud.aplicar(db)
        # Dirección en débito + categoría sugerida (antes era gasto en CAFE).
        r = _fila(db, 1616)
        assert (r['tipo'], r['categoria']) == ('INGRESO', 'OTROS')
        # Abono a la tarjeta: monto negativo, sigue siendo pago (no gasto ni ingreso).
        r = _fila(db, 40)
        assert (r['monto'], r['tipo'], r['categoria']) == (-11677.85, 'MOVIMIENTO_INTERNO', 'PAGO_TDC')
        # RFC -> nombre del comercio; la categoría que vino del RFC toma la sugerida.
        r = _fila(db, 115)
        assert (r['descripcion'], r['categoria'], r['subcategoria']) == ('OXXO PANAMERICANA', 'SUPER', 'Conveniencia')
        # Descripción mezclada -> la del PDF, en el formato del importador; la renta se queda como renta.
        r = _fila(db, 1838)
        assert r['descripcion'] == 'PAGO TARJETA DE TERCEROS MBAN'
        assert (r['categoria'], r['subcategoria']) == ('VIVIENDA', 'Renta')
        # Texto ajeno que lo había metido como inversión: es un retiro sin tarjeta.
        r = _fila(db, 2375)
        assert (r['descripcion'], r['tipo'], r['categoria'], r['subcategoria']) == \
            ('RETIRO SIN TARJETA QR', 'GASTO', 'FINANZAS', 'Retiro efectivo')
        # «me prestaron y regresé»: se voltea pero NO pasa a ingreso extraordinario.
        r = _fila(db, 3111)
        assert r['tipo'] == 'INGRESO'
        # Fresko: «alguien me pagó su parte del súper» (usuario, 2026-10-03).
        for i in (2272, 2276):
            r = _fila(db, i)
            assert (r['tipo'], r['categoria'], r['subcategoria']) == ('INGRESO', 'FINANZAS', 'Reembolso compartido')
        # …3042 es Mommita: sus abonos son reembolso; si ya estaban en VIAJES, restan del viaje.
        for i in (1816, 1888, 1975, 2242, 1615, 1440):
            r = _fila(db, i)
            assert (r['tipo'], r['categoria'], r['subcategoria']) == ('INGRESO', 'FINANZAS', 'Reembolso compartido'), i
        r = _fila(db, 1578)
        assert (r['tipo'], r['categoria']) == ('INGRESO', 'VIAJES')
        # Abono de Judi con concepto claro: se queda en su categoría (resta del viaje).
        r = _fila(db, 2958)
        assert (r['tipo'], r['categoria'], r['subcategoria']) == ('INGRESO', 'VIAJES', 'Otros')
        # Renta oct-2024: el SPEI a BANORTE regresó (ni gasto ni ingreso) y la renta es el pago a BBVA.
        assert (_fila(db, 3163)['categoria'], _fila(db, 3163)['subcategoria']) == ('FINANZAS', 'Entre cuentas propias')
        assert (_fila(db, dev)['categoria'], _fila(db, dev)['subcategoria']) == ('FINANZAS', 'Entre cuentas propias')
        r = db.execute("""SELECT * FROM est_movimientos WHERE fecha='2024-10-08' AND monto=11000
                          AND descripcion LIKE 'PAGO TARJETA DE TERCEROS%'""").fetchone()
        assert (r['tipo'], r['categoria'], r['subcategoria']) == ('GASTO', 'VIVIENDA', 'Renta')
        # Monto distinto.
        assert _fila(db, 2089)['monto'] == 5555.0


def test_borra_solo_lo_seguro(test_db):
    with database.get_db() as db:
        _sembrar(db, sin_gemelos={2117})
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Cornelius', 'OTORGADO', 2000, '2026-05-12', '', 2077, datetime('now'))""")
        db.execute("UPDATE est_movimientos SET viaje_id=3 WHERE id=1881")
        plan = {(l['id_app'], l['accion']) for l in aud.plan(db)}
        aud.aplicar(db)
        assert _fila(db, 1658) is None                  # monto 0.00
        assert _fila(db, 1810) is None                  # duplicado confirmado de 1816
        # Duplicado ligado (Cornelius): «lo que dice Cowork» -> el préstamo pasa al gemelo y la copia se borra.
        # El gemelo (2130) ya tiene lo suyo: el préstamo de Cornelius se queda sin movimiento y la copia se borra.
        assert _fila(db, 2077) is None and (2077, 'desligado') in plan
        assert db.execute("SELECT movimiento_id FROM est_prestamos WHERE contraparte='Cornelius'").fetchone()[0] is None
        assert _fila(db, 1881) is not None and (1881, 'pendiente revisión') in plan   # su gemelo no tiene el viaje
        assert _fila(db, 2003) is not None              # el «gemelo» no existe: no se borra
        assert _fila(db, 2031) is not None              # Steam: real, se queda
        assert _fila(db, 1306) is not None              # compra a MSI de los anillos
        assert _fila(db, 19) is not None                # no está en el PDF y nadie sabe qué es: se queda
        assert _fila(db, 1102) is None and _fila(db, 2053) is None   # garantía y validación: nunca se cobraron
        for i in aud.PENDIENTES_USUARIO:                # las que decidió el usuario no se tocan
            assert _fila(db, i)['tipo'] == 'GASTO'


def test_faltantes(test_db):
    with database.get_db() as db:
        _sembrar(db)
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES ('2024-05-05', 'PAGO CUENTA DE TERCERO BNET TRANSF A', 1500, 'BBVA_DEB', 'FINANZAS', '', 'GASTO')""")
        aud.aplicar(db)
        q = lambda f, m: [dict(r) for r in db.execute(
            "SELECT * FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01", (f, m))]
        # Envío y devolución el mismo día: los dos, sin contar como gasto ni ingreso.
        par = q('2026-01-08', 42200.0)
        assert len(par) == 2 and {r['tipo'] for r in par} == {'MOVIMIENTO_INTERNO'}
        # Pago a la tarjeta Invex desde débito: movimiento interno, como en el import.
        assert [(r['tipo'], r['categoria']) for r in q('2026-01-23', 3386.0)] == [('MOVIMIENTO_INTERNO', 'PAGO_TDC')]
        # Abono a la TDC creado con signo negativo.
        assert [(r['tipo'], r['monto'], r['banco']) for r in q('2022-02-08', 4813.06)] == [('PAGO', -4813.06, 'BBVA_TDC')]
        # Intereses del resumen como gasto financiero.
        assert [(r['categoria'], r['subcategoria']) for r in q('2025-08-22', 924.06)] == [('COSTOS_FINANCIEROS', 'Intereses')]
        # Mensualidad MSI.
        msi = q('2022-01-22', 292.0)
        assert [(r['descripcion'], r['parcialidad_num'], r['parcialidad_total']) for r in msi] == \
            [('TIENDAS CHEDRAUI S TA', 2, 12)]
        # La mensualidad de la anualidad no se crea (la anualidad ya va en comisiones).
        assert q('2022-12-22', 358.66) == []
        assert len(q('2022-11-23', 1076.0)) == 1
        # Otra operación del mismo monto ese día no cuenta como «ya existe».
        assert {r['descripcion'] for r in q('2024-05-05', 1500.0)} == \
            {'PAGO CUENTA DE TERCERO BNET TRANSF A', 'PAGO TARJETA DE CREDITO'}
        # Nada en 0.00.
        assert not db.execute("SELECT 1 FROM est_movimientos WHERE monto = 0").fetchone()


def test_endpoint_simula_y_aplica_con_respaldo(test_db):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with database.get_db() as db:
        _sembrar(db)
        db.commit()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['app_ok'] = True
            sess['fin_ok'] = True
        j = c.get('/finanzas/estados/admin/auditoria-pdf').get_json()
        assert j['respaldo'] is None and j['cambios']
        with database.get_db() as db:
            assert _fila(db, 1616)['tipo'] == 'GASTO'
        csv_txt = c.get('/finanzas/estados/admin/auditoria-pdf?formato=csv').get_data(as_text=True)
        assert csv_txt.startswith('id_app,banco,fecha,monto,estado_auditoria,accion')
        j = c.get('/finanzas/estados/admin/auditoria-pdf?aplicar=1&cuadre=1').get_json()
        assert j['respaldo'] and os.path.exists(j['respaldo'])
        assert isinstance(j['cuadre'], list)
        with database.get_db() as db:
            assert _fila(db, 1616)['tipo'] == 'INGRESO'


def _prestamo(db, persona, monto, fecha, mid, direccion='OTORGADO'):
    return db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                         VALUES (?, ?, ?, ?, '', ?, datetime('now'))""", (persona, direccion, monto, fecha, mid)).lastrowid


def _devolucion(db, pid, mid):
    db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,datetime('now'))",
               (pid, mid))


def test_ligados_confirmados_por_el_usuario(test_db):
    with database.get_db() as db:
        _sembrar(db)
        # 3351 ($7,000 a su papá) estaba como devolución de un préstamo que él dio.
        papa = _prestamo(db, 'Papá', 7000, '2023-12-01', None)
        _devolucion(db, papa, 3351)
        # 2999 ($1,000 de Judi) era el origen de un «préstamo» a Judi; Judi tiene otro abierto.
        falso = _prestamo(db, 'Judi', 1000, '2025-03-24', 2999)
        abierto = _prestamo(db, 'Judi', 3000, '2025-02-01', None)
        _prestamo(db, 'Judi', 10000, '2025-11-26', None)          # posterior al abono: no le toca
        # 3004 (jefe de famil repo) era el origen de un préstamo con una devolución de $2,512.
        repo = _prestamo(db, 'Judi', 2513, '2025-03-27', 3004)
        dev = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                            VALUES ('2025-04-02', 'PAGO CUENTA DE TERCERO BNET REPO', 2512, 'BBVA_DEB', 'PRESTAMOS', '', 'INGRESO')""").lastrowid
        _devolucion(db, repo, dev)
        # 2303 (expense que regresó) estaba como depósito de un lote.
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (1, 2303, datetime('now'))")
        # 1831 duplicado ligado como devolución -> pasa al gemelo 1847.
        _devolucion(db, abierto, 1831)
        aud.aplicar(db)
        fila = lambda i: tuple(db.execute("SELECT tipo, categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        liga = lambda i: db.execute("SELECT prestamo_id FROM est_prestamo_devoluciones WHERE movimiento_id=?", (i,)).fetchone()
        assert fila(3351) == ('GASTO', 'PRESTAMOS', '') and liga(3351) is None
        assert fila(2999)[0] == 'INGRESO' and liga(2999)[0] == abierto
        assert not db.execute("SELECT 1 FROM est_prestamos WHERE id IN (?, ?)", (falso, repo)).fetchone()
        assert fila(3004) == ('INGRESO', 'PRESTAMOS', '')
        assert liga(dev) is None and fila(dev) == ('INGRESO', 'FINANZAS', 'Transferencia recibida')
        assert fila(2124) == ('GASTO', 'FINANZAS', 'Retiro efectivo')
        assert fila(2303) == ('GASTO', 'FINANZAS', 'Reembolsable')
        assert not db.execute("SELECT 1 FROM est_expense_lote_depositos WHERE movimiento_id=2303").fetchone()
        assert _fila(db, 1831) is None and liga(1847)[0] == abierto
        assert {l['accion'] for l in aud.plan(db)} <= {'sin cambio', 'pendiente revisión'}


def test_periodo_y_cuadre_cuentan_la_devolucion_como_abono(test_db):
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with database.get_db() as db:
        for desc in ('SPEI ENVIADO STP 0080126AHORRO GIO', 'SPEI DEVUELTOSTP 0080126AHORRO GIO'):
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-01-08', ?, 42200, 'BBVA_DEB', 'FINANZAS', 'Entre cuentas propias',
                                  'MOVIMIENTO_INTERNO')""", (desc,))
        db.commit()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['app_ok'] = True
            sess['fin_ok'] = True
        j = c.get('/finanzas/estados/admin/auditoria-pdf/periodo?banco=BBVA_DEB&desde=2026-01-07&hasta=2026-02-06').get_json()
    assert (j['abonos'], j['cargos']) == (42200.0, 42200.0)


def test_sobran_por_cuadre_feb_2026(test_db):
    with database.get_db() as db:
        ins = lambda i, d, m, t, c: db.execute(
            """INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
               VALUES (?, ?, ?, ?, 'BBVA_DEB', ?, '', ?)""", (i, '2026-03-03', d, m, c, t))
        ins(1805, 'BNET MARTHA PAGO CUENTA DE TERCERO BNET', 600, 'INGRESO', 'FAMILIA_REGALOS')
        ins(1806, 'PAGO CUENTA DE TERCERO', 250, 'INGRESO', 'FAMILIA_REGALOS')
        ins(1807, 'PAGO CUENTA DE TERCERO BNET COLECTA MARTHA', 600, 'GASTO', 'FAMILIA_REGALOS')
        ins(1808, 'PAGO CUENTA DE TERCERO BNET MARTHA', 250, 'INGRESO', 'FAMILIA_REGALOS')
        ins(1812, 'BNET P RETIRO SIN TARJETA ******7852', 1500, 'GASTO', 'FAMILIA_REGALOS')
        ins(1817, 'RETIRO SIN TARJETA', 1500, 'GASTO', 'EXPENSE')
        db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (1, 1817, datetime('now'))")
        aud.aplicar(db)
        quedan = {r[0] for r in db.execute("SELECT id FROM est_movimientos WHERE id BETWEEN 1805 AND 1817")}
        assert quedan == {1805, 1808, 1812}
        assert db.execute("SELECT movimiento_id FROM est_expense_lote_gastos").fetchone()[0] == 1812


def test_correcciones_cuadre_feb_may_2026(test_db):
    with database.get_db() as db:
        ins = lambda i, f, d, m, t, c, s: db.execute(
            """INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
               VALUES (?, ?, ?, ?, 'BBVA_DEB', ?, ?, ?)""", (i, f, d, m, c, s, t))
        ins(1812, '2026-03-04', 'BNET P RETIRO SIN TARJETA ******7852', 1500, 'GASTO', 'FAMILIA_REGALOS', 'Colectas')
        ins(1817, '2026-03-04', 'RETIRO SIN TARJETA', 1500, 'GASTO', 'EXPENSE', '')     # se borra antes de renombrar 1812
        ins(1808, '2026-03-03', 'PAGO CUENTA DE TERCERO BNET MARTHA', 250, 'INGRESO', 'FAMILIA_REGALOS', 'Colectas')
        ins(1805, '2026-03-03', 'BNET MARTHA PAGO CUENTA DE TERCERO BNET', 600, 'INGRESO', 'FAMILIA_REGALOS', 'Colectas')
        ins(1807, '2026-03-03', 'PAGO CUENTA DE TERCERO BNET COLECTA MARTHA', 600, 'GASTO', 'FAMILIA_REGALOS', 'Colectas')
        ins(2059, '2026-05-06', 'SPEI ENVIADO BANAMEX 002 1404260CARNES GIO', 300, 'GASTO', 'COMIDA_FUERA', 'Restaurante')
        ins(1980, '2026-04-15', 'RETIRO SIN TARJETA', 200, 'GASTO', 'COMIDA_FUERA', 'Restaurante')
        ins(2006, '2026-04-23', 'GIOVANY SITH2PAGOGDLAC FIDEICOMISO F 1596', 3142.39, 'INGRESO', 'FINANZAS', 'Reembolsable')
        ins(2077, '2026-05-12', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000, 'GASTO', 'PRESTAMOS', 'Prestado')
        ins(2130, '2026-05-12', 'PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000, 'GASTO', 'PRESTAMOS', 'Prestado')
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Cornelius', 'OTORGADO', 2000, '2026-05-12', '', 2077, datetime('now'))""")
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Judi', 'OTORGADO', 2000, '2026-05-12', '', 2130, datetime('now'))""")
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES (2124, '2026-05-25', 'FIBRA HOTELERA SC RETIRO SIN TARJETA ******7852', 2000, 'BBVA_DEB',
                              'FINANZAS', 'Retiro efectivo', 'GASTO')""")
        aud.aplicar(db)
        fila = lambda i: db.execute("SELECT * FROM est_movimientos WHERE id=?", (i,)).fetchone()
        assert fila(1812)['descripcion'] == 'RETIRO SIN TARJETA' and fila(1817) is None
        assert fila(1805)['descripcion'] == 'PAGO CUENTA DE TERCERO BNET COLECTA MARTHA' and fila(1807) is None
        assert fila(2059)['fecha'][:10] == '2026-05-07'
        assert (fila(1980)['categoria'], fila(1980)['subcategoria']) == ('FINANZAS', 'Retiro efectivo')
        assert fila(2006)['descripcion'] == 'SITH2PAGOGDLAC FIDEICOMISO F 1596'
        assert fila(2124)['descripcion'] == 'RETIRO SIN TARJETA'
        assert fila(2077) is None
        assert db.execute("SELECT movimiento_id FROM est_prestamos WHERE contraparte='Cornelius'").fetchone()[0] is None
        assert {l['accion'] for l in aud.plan(db) if l['estado_auditoria'] == 'CUADRE'} <= {'sin cambio'}


def test_compras_canceladas_palacio(test_db):
    with database.get_db() as db:
        for i in (1, 2):
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2025-11-13', ?, -2345, 'BBVA_TDC', 'PAGO', '', 'PAGO')""",
                       (f'ELPALACIOHIERRO COM DEVOLUCION {i}',))
        aud.aplicar(db)
        rows = db.execute("""SELECT fecha, monto, tipo, subcategoria FROM est_movimientos
                             WHERE banco='BBVA_TDC' AND ABS(ABS(monto) - 2345) < 0.01 ORDER BY fecha, monto""").fetchall()
        assert [tuple(r) for r in rows] == [
            ('2025-11-10', 2345.0, 'MOVIMIENTO_INTERNO', 'Entre cuentas propias'),
            ('2025-11-12', 2345.0, 'MOVIMIENTO_INTERNO', 'Entre cuentas propias'),
            ('2025-11-13', -2345.0, 'MOVIMIENTO_INTERNO', 'Entre cuentas propias'),
            ('2025-11-13', -2345.0, 'MOVIMIENTO_INTERNO', 'Entre cuentas propias')]
        assert not [l for l in aud.plan(db) if l['fecha'].startswith('2025-11-1') and l['accion'] not in ('sin cambio',)
                    and abs(l['monto'] - 2345) < 0.01]


def test_burger_king_y_dinero_a_gbm(test_db):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES (2100, '2026-05-18', 'SPEI RECIBIDOSTP 646', 15305, 'BBVA_DEB', 'NOMINA', 'Bono', 'INGRESO')""")
        aud.aplicar(db)
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=2100").fetchone()) == \
            ('FINANZAS', 'Entre cuentas propias')
        bk = db.execute("SELECT * FROM est_movimientos WHERE descripcion='BURGER KING AVILA C'").fetchall()
        assert [(r['fecha'], r['monto'], r['subcategoria']) for r in bk] == [('2024-07-28', 99.0, 'Fast Food')]
        aud.aplicar(db)
        assert len(db.execute("SELECT 1 FROM est_movimientos WHERE descripcion='BURGER KING AVILA C'").fetchall()) == 1


def test_debito_cuadra_por_fecha_de_liquidacion(test_db):
    """2540: SPEI «corte gio» del sábado 5-sep liquidado el lunes 7. La fecha
    de operación se queda; por la de liquidación pasa al estado de septiembre."""
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, fecha_cargo, descripcion, monto, banco, categoria,
                      subcategoria, tipo) VALUES (2540, '2026-09-05', NULL, 'SPEI ENVIADO BANAMEX 002 1408260CORTE GIO',
                      150, 'BBVA_DEB', 'CUIDADO_PERSONAL', 'Barbería', 'GASTO')""")
        assert [m['id'] for m in aud.movimientos_periodo(db, 'BBVA_DEB', '2026-09-03', '2026-09-06')] == [2540]
        aud.aplicar(db)
        r = _fila(db, 2540)
        assert (r['fecha'], r['fecha_cargo']) == ('2026-09-05', '2026-09-07')
        assert aud.movimientos_periodo(db, 'BBVA_DEB', '2026-09-03', '2026-09-06') == []
        [m] = aud.movimientos_periodo(db, 'BBVA_DEB', '2026-09-07', '2026-09-10')
        assert (m['id'], m['fecha'], m['fecha_liq']) == (2540, '2026-09-05', '2026-09-07')
        sep = next(c for c in aud.cuadre(db) if c['periodo'].startswith('2026-09-07'))
        assert sep['cargos_app'] == 150.0
        assert {l['accion'] for l in aud.plan(db) if l['id_app'] == 2540} <= {'sin cambio'}


def test_2059_ya_movido_de_fecha_tambien_mueve_la_liquidacion(test_db):
    """Producción: la 1ª pasada le cambió la fecha al 7-may pero dejó la LIQ
    en el 6; al cuadrar por liquidación volvía a caer en abril (abr +$300)."""
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, fecha_cargo, descripcion, monto, banco, categoria,
                      subcategoria, tipo) VALUES (2059, '2026-05-07', '2026-05-06',
                      'SPEI ENVIADO BANAMEX 002 1404260CARNES GIO', 300, 'BBVA_DEB', 'COMIDA_FUERA', 'Restaurante', 'GASTO')""")
        aud.aplicar(db)
        r = _fila(db, 2059)
        assert (r['fecha'], r['fecha_cargo']) == ('2026-05-07', '2026-05-07')
        assert [m['id'] for m in aud.movimientos_periodo(db, 'BBVA_DEB', '2026-05-07', '2026-06-06')] == [2059]
