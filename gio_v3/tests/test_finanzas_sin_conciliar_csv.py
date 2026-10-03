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
        assert (ok, faltan) == (2, len(corr.CORRECCIONES) + len(corr.VIAJES) + len(corr.PERSONAS) + len(corr.GASTOS) + len(corr.ENTRADAS) + len(corr.REESCRITOS) - 2)
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


def test_consulta_guardada_como_ingreso_pasa_a_gasto(test_db):
    with database.get_db() as db:
        i = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-06-22', 'PAGO CUENTA DE TERCERO', 1000, 'BBVA_DEB', 'SALUD', 'Consultas', 'INGRESO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        assert tuple(db.execute("SELECT tipo, categoria FROM est_movimientos WHERE id=?", (i,)).fetchone()) == ('GASTO', 'SALUD')


def test_mens_gio_era_gasto_de_salsa(test_db):
    with database.get_db() as db:
        i = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2026-04-14', '014 180326OMENS GIO PAGO CUENTA DE TERCERO BNET', 700, 'BBVA_DEB',
                                  'TRANSPORTE', 'Gasolina', 'INGRESO')""").lastrowid
        db.commit()
        corr.aplicar(db)
        assert tuple(db.execute("SELECT tipo, categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone()) \
            == ('GASTO', 'SALSA', 'Clases')


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
