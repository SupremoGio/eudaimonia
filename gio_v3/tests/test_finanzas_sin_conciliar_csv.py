"""
test_finanzas_sin_conciliar_csv.py — abonos de «Sin conciliar» comentados por
el usuario: cada uno va a la categoría del gasto que le pagaron.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import correcciones_sin_conciliar as corr
from modules.finanzas.estados.config import SUBCATEGORIAS


def test_categorias_validas():
    for *_, cat, sub in corr.CORRECCIONES + [g[:5] for g in corr.GASTOS]:
        assert sub in SUBCATEGORIAS[cat], (cat, sub)


def test_aplica_por_id_y_por_texto(test_db):
    with database.get_db() as db:
        ins = lambda mid, f, d, m: db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                                                 VALUES (?,?,?,?, 'BBVA_DEB', 'FINANZAS', 'Transferencia', 'INGRESO')""", (mid, f, d, m))
        ins(4726, '2022-10-28', 'PAGO CUENTA DE TERCERO BNET TAXI', 150)
        ins(90001, '2022-12-01', 'PAGO CUENTA DE TERCERO BNET MISHELLE CT', 5300)
        db.commit()
        ok, faltan = corr.aplicar(db)
        cat = lambda i: tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert cat(4726) == ('TRANSPORTE', 'Taxi/apps')
        assert cat(90001) == ('VIVIENDA', 'Aportación renta')
        assert (ok, faltan) == (2, len(corr.CORRECCIONES) + len(corr.VIAJES) + len(corr.PERSONAS) + len(corr.GASTOS) + len(corr.ENTRADAS) + len(corr.REESCRITOS) + len(corr.AUDITORIA_2026) - 2)
        assert corr.aplicar(db)[0] == 0


def test_abono_en_fechas_de_viaje_se_liga(test_db):
    with database.get_db() as db:
        vid = db.execute("""INSERT INTO viajes (nombre, destino, fecha_inicio, fecha_fin, estado, created_at)
                            VALUES ('VILLAHERMOSA JUN 24', 'Villahermosa', '2024-05-30', '2024-06-03', 'completado', 'x')""").lastrowid
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES (3468, '2024-06-04', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 250, 'BBVA_DEB',
                              'FINANZAS', 'Transferencia', 'INGRESO')""")
        db.commit()
        corr.aplicar(db)
        r = db.execute("SELECT categoria, subcategoria, viaje_id FROM est_movimientos WHERE id=3468").fetchone()
        assert tuple(r) == ('VIAJES', 'Otros', vid)


def test_gastos_de_dinero_ajeno_regresado(test_db):
    with database.get_db() as db:
        i = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2023-01-04', 'PAGO CUENTA DE TERCERO BNET EXPENSE IVAN', 1171, 'BBVA_DEB', 'OTROS', '', 'GASTO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone()) \
            == ('FINANZAS', 'Reembolsable')


def test_pago_a_eli_solo_el_seguro_es_gasto(test_db):
    with database.get_db() as db:
        i = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-04-15', '059 180326OINVEX ABRIL PAGO CUENTA DE TERCERO BNET DEUDA', 3311,
                                  'BBVA_DEB', 'PAGO_TDC', '', 'PAGO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        assert tuple(db.execute("SELECT categoria, subcategoria, tipo, mi_parte FROM est_movimientos WHERE id=?",
                                (i,)).fetchone()) == ('TRANSPORTE', 'Seguro auto', 'GASTO', 1111.0)
        assert corr.aplicar(db)[0] == 0


def test_abonos_de_mommita_ya_no_se_vuelven_gasto(test_db):
    """La auditoría contra los PDF (2026-10-03) mostró que la «consulta» de
    $1,000 y «MENS GIO» $700 eran abonos de …3042 (su mamá) con texto del
    renglón vecino: ya no se fuerzan a gasto, quedan como reembolso."""
    with database.get_db() as db:
        c = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-06-22', 'PAGO CUENTA DE TERCERO', 1000, 'BBVA_DEB', 'SALUD', 'Consultas', 'INGRESO')""").lastrowid
        nueva = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                              VALUES ('2026-10-02', 'PAGO CUENTA DE TERCERO BNET …3042 P', 300, 'BBVA_DEB', 'FINANZAS',
                                      'Transferencia recibida', 'INGRESO')""").lastrowid
        viaje = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                              VALUES ('2025-12-25', 'PAGO CUENTA DE TERCERO BNET …3042 P', 604, 'BBVA_DEB', 'VIAJES',
                                      'Otros', 'INGRESO')""").lastrowid
        regalo = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                               VALUES ('2026-09-23', 'PAGO CUENTA DE TERCERO BNET …3042 REGALO A LAS LENIS', 33, 'BBVA_DEB',
                                       'FINANZAS', 'Transferencia', 'GASTO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        fila = lambda i: tuple(db.execute("SELECT tipo, categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert fila(c) == ('INGRESO', 'SALUD', 'Consultas')
        assert fila(nueva) == ('INGRESO', 'FINANZAS', 'Reembolso compartido')   # cuenta conocida: Mommita
        assert fila(viaje) == ('INGRESO', 'VIAJES', 'Otros')                     # categoría elegida: se respeta
        assert fila(regalo) == ('GASTO', 'FINANZAS', 'Transferencia')            # lo que él le manda no se toca


def test_nespresso_compartido(test_db):
    with database.get_db() as db:
        n = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-07-17', 'NESPRESSO MEXICO', 918.75, 'BBVA_TDC', 'CAFE/PAN', 'Café', 'GASTO')""").lastrowid
        c = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-07-17', 'PAGO CUENTA DE TERCERO BNET CAPSULAS CAFE', 410, 'BBVA_DEB', 'CAFE/PAN', 'Café', 'GASTO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        assert db.execute("SELECT mi_parte FROM est_movimientos WHERE id=?", (n,)).fetchone()[0] == 508.75
        assert tuple(db.execute("SELECT tipo, categoria, subcategoria FROM est_movimientos WHERE id=?", (c,)).fetchone()) \
            == ('INGRESO', 'FINANZAS', 'Reembolso compartido')


def test_deposito_propio_para_la_renta(test_db):
    with database.get_db() as db:
        i = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-04-07', 'A GIOVANY A DEPOSITO EFECTIVO PRACTIC ******1801', 7000, 'BBVA_DEB',
                                  'VIAJES', 'Otros', 'INGRESO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        assert tuple(db.execute("SELECT tipo, categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone()) \
            == ('INGRESO', 'FINANZAS', 'Entre cuentas propias')


def test_movimientos_con_fibra_hotelera_pegada(test_db):
    with database.get_db() as db:
        ins = lambda f, m, t: db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                                            VALUES (?, 'FIBRA HOTELERA SC PAGO CUENTA DE TERCERO BNET', ?, 'BBVA_DEB', 'VIAJES', 'Otros', ?)""",
                                         (f, m, t)).lastrowid
        a, b, c = ins('2026-03-12', 505, 'INGRESO'), ins('2026-03-29', 6000, 'GASTO'), ins('2026-04-27', 460.41, 'INGRESO')
        db.commit()
        corr.aplicar(db)
        row = lambda i: tuple(db.execute("SELECT descripcion, tipo, categoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert row(a) == ('PAGO CUENTA DE TERCERO BNET PLANTITA', 'GASTO', 'VIVIENDA')
        assert row(b) == ('PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 'INGRESO', 'FINANZAS')
        assert row(c) == ('PAGO CUENTA DE TERCERO BNET EXPENSE', 'GASTO', 'EXPENSE')
        assert corr.aplicar(db)[0] == 0


def test_reescrito_con_copia_buena_ya_guardada(test_db):
    """El mismo estado importado de dos PDFs: una copia con «FIBRA HOTELERA»
    pegado y otra ya con la descripción real. Antes el UNIQUE hacía fallar todo."""
    with database.get_db() as db:
        ins = lambda d, t: db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                                         VALUES ('2026-03-29', ?, 6000, 'BBVA_DEB', 'VIAJES', 'Otros', ?)""", (d, t)).lastrowid
        mala = ins('FIBRA HOTELERA SC PAGO CUENTA DE TERCERO BNET', 'GASTO')
        buena = ins('PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 'GASTO')
        db.commit()
        corr.aplicar(db)
        assert db.execute("SELECT 1 FROM est_movimientos WHERE id=?", (mala,)).fetchone() is None
        assert tuple(db.execute("SELECT tipo, categoria FROM est_movimientos WHERE id=?", (buena,)).fetchone()) == ('INGRESO', 'FINANZAS')
        assert next(r for r in corr.revisar_reescritos(db) if r['monto'] == 6000)['correcto']


def test_admin_correcciones(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = sess["fin_ok"] = True
        r = c.get('/finanzas/estados/admin/correcciones?aplicar=1').get_json()
        assert r['aplicado'] is not None and len(r['reescritos']) == len(corr.REESCRITOS)


def test_abonos_de_viajes_revisados_contra_pdf(test_db):
    with database.get_db() as db:
        ins = lambda f, d, m: db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                                            VALUES (?,?,?, 'BBVA_DEB', 'VIAJES', 'Otros', 'INGRESO')""", (f, d, m)).lastrowid
        fid = ins('2026-03-31', 'SIN DESCRIPCION', 2299)
        sp = ins('2026-04-07', '135 EGRESOS SPEI SVD PAGO CUENTA DE TERCERO BNET', 1500)
        liq = ins('2026-04-21', 'PAGO CUENTA DE TERCERO BNET', 738)
        stp = ins('2026-08-10', 'SPEI RECIBIDOSTP 646', 3000)
        db.commit()
        corr.aplicar(db)
        r = lambda i: tuple(db.execute("SELECT descripcion, categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert r(fid) == ('SITH26623774 FIDEICOMISO F/1596', 'FINANZAS', 'Reembolsable')
        assert r(sp)[1:] == ('OTROS', '')                      # de su papá: ingreso
        assert r(liq) == ('PAGO CUENTA DE TERCERO BNET LIQUIDOS', 'OTROS', '')
        assert r(stp)[1:] == ('FINANZAS', 'Transferencia recibida')


def test_comida_fuera_revisada_contra_pdf(test_db):
    with database.get_db() as db:
        ins = lambda f, d, m, t: db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                                               VALUES (?,?,?, 'BBVA_DEB', 'COMIDA_FUERA', 'Restaurante', ?)""", (f, d, m, t)).lastrowid
        mens = ins('2026-04-14', 'FIBRA HOTELERA SC SPEI ENVIADO SANTANDER', 750, 'GASTO')
        com = ins('2026-09-25', 'PAGO CUENTA DE TERCERO BNET COMIDA', 105, 'GASTO')
        val = ins('2026-07-02', 'SPEI RECIBIDOSTP 646 0061370VAL.ASEG. OP', 0.01, 'GASTO')
        db.commit()
        corr.aplicar(db)
        r = lambda i: tuple(db.execute("SELECT descripcion, tipo, categoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert r(mens) == ('SPEI ENVIADO SANTANDER MENS GIO', 'GASTO', 'SALSA')
        assert r(com)[1:] == ('INGRESO', 'COMIDA_FUERA')
        assert r(val)[1:] == ('INGRESO', 'FINANZAS')


def test_auditoria_2026_papa_colecta_y_cumple(test_db):
    with database.get_db() as db:
        ins = lambda f, d, m, t, c='FAMILIA_REGALOS', sub='Regalos': db.execute(
            """INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
               VALUES (?,?,?, 'BBVA_DEB', ?, ?, ?)""", (f, d, m, c, sub, t)).lastrowid
        tqm = ins('2026-07-16', 'PAGO CUENTA DE TERCERO BNET IGUAL TQM', 50000, 'INGRESO')
        col = ins('2026-03-03', 'PAGO CUENTA DE TERCERO', 600, 'INGRESO', 'FAMILIA_REGALOS', 'Colectas')
        seg = ins('2026-05-15', 'PAGO CUENTA DE TERCERO BNET SEGURO Y DEUDA', 5555, 'GASTO', 'FINANZAS', 'Transferencia')
        papa = ins('2026-08-20', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 500, 'INGRESO')
        dev = ins('2026-09-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 4500, 'INGRESO', 'VIAJES', 'Otros')
        db.commit()
        corr.aplicar(db)
        r = lambda i: tuple(db.execute("SELECT tipo, categoria, subcategoria, mi_parte FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert r(tqm) == ('INGRESO', 'OTROS', '', None)
        assert r(col) == ('INGRESO', 'FAMILIA_REGALOS', 'Colectas', None)
        assert r(seg) == ('GASTO', 'TRANSPORTE', 'Seguro auto', 555.0)
        assert r(papa)[:2] == ('INGRESO', 'OTROS')
        # regalito y el tercer regalo faltan en agosto: se registran (agosto ya está importado)
        assert db.execute("SELECT COUNT(*) FROM est_movimientos WHERE fecha='2026-08-20' AND monto=500").fetchone()[0] == 3
        # el cargo del préstamo del 11/09 falta: se registra y la devolución NO se toca
        assert r(dev)[:2] == ('INGRESO', 'VIAJES')
        assert db.execute("SELECT tipo, categoria FROM est_movimientos WHERE fecha='2026-09-11' AND monto=4500 AND tipo='GASTO'").fetchone()[:] == ('GASTO', 'PRESTAMOS')
        n = db.execute("SELECT COUNT(*) FROM est_movimientos").fetchone()[0]
        corr.aplicar(db)
        assert db.execute("SELECT COUNT(*) FROM est_movimientos").fetchone()[0] == n       # idempotente
        assert corr.aplicar(db)[0] == 0
