"""
test_finanzas_otros_csv_2026_09_28.py — «Sin clasificar» comentado por el
usuario: cada fila de OTROS va a la categoría de su comentario.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import correcciones_otros_2026_09_28 as corr
from modules.finanzas.estados.config import SUBCATEGORIAS


def _ins(db, mid, fecha, desc, monto, cat='OTROS'):
    db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                  VALUES (?,?,?,?, 'BBVA_TDC', ?, '', 'GASTO')""", (mid, fecha, desc, monto, cat))


def test_categorias_validas():
    for *_, cat, sub in corr.CORRECCIONES:
        assert cat == 'EXPENSE' or sub in SUBCATEGORIAS[cat], (cat, sub)
    assert len(corr.CORRECCIONES) == 261 and len({c[0] for c in corr.CORRECCIONES}) == 261


def test_aplica_por_id_y_por_comercio(test_db):
    with database.get_db() as db:
        _ins(db, 4936, '2023-07-23', 'CERVECERIA CHAPULTEPEC', 1910.15)          # mismo id
        _ins(db, 90001, '2023-09-16', 'AQUAMATIC PABLO NERUDA (2)', 70.0)         # otro id: por comercio
        _ins(db, 5138, '2023-11-22', 'TRAINING INNOVATION', 359.0)
        _ins(db, 4588, '2024-01-01', 'OTRA COSA', 249.0)                          # id reusado: no se toca
        db.commit()
        ok, faltan = corr.aplicar(db)
        db.commit()
        cat = lambda i: tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert cat(4936) == ('COMIDA_FUERA', 'Restaurante')
        assert cat(90001) == ('VIVIENDA', 'Lavandería')
        assert cat(5138) == ('DEPORTE', 'Gym')
        assert cat(4588) == ('OTROS', '')
        assert ok == 3
        assert corr.aplicar(db)[0] == 0


def test_estacion_de_serv_col_es_gasolina(test_db):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES (4888, '2023-04-26', 'ESTACION DE SERV COL', 200, 'BBVA_TDC', 'TRANSPORTE', 'Estacionamiento', 'GASTO')""")
        db.commit()
        corr.aplicar(db)
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=4888").fetchone()) == ('TRANSPORTE', 'Gasolina')


def test_transferencias_de_5000_a_renta(test_db):
    from modules.finanzas.estados.routes import _corregir_pagos_renta, _reaplicar_reglas
    with database.get_db() as db:
        for f, d in (('2022-08-17', 'PAGO CUENTA DE TERCERO BNET RENTA GIO'),
                     ('2023-04-01', 'PAGO CUENTA DE TERCERO BNET PRIMERA PARTE'),
                     ('2023-05-12', 'PAGO CUENTA DE TERCERO BNET TRANSF A'),
                     ('2024-09-29', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A'),
                     ('2023-05-12', 'PAGO CUENTA DE TERCERO BNET TRANSF A (OTRO MONTO)')):
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES (?,?,?, 'BBVA_DEB', 'FINANZAS', 'Transferencia', 'GASTO')""",
                       (f, d, 800.0 if 'OTRO' in d else 5000.0))
        db.commit()
        assert _corregir_pagos_renta(db) == 4
        db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES ('BNET', 'FINANZAS', 'Transferencia')")
        _reaplicar_reglas(db)
        cats = db.execute("SELECT monto, categoria, subcategoria FROM est_movimientos ORDER BY id").fetchall()
        assert [tuple(r) for r in cats if r[0] == 5000] == [(5000.0, 'VIVIENDA', 'Renta')] * 4
        assert [tuple(r) for r in cats if r[0] == 800] == [(800.0, 'FINANZAS', 'Transferencia')]


def test_retiros_y_spei_2022_a_renta(test_db):
    from modules.finanzas.estados.routes import _corregir_pagos_renta
    with database.get_db() as db:
        filas = (('2022-11-19', 'RETIRO CAJERO AUTOMATICO NOV19 14:55 BBVA A605 FOLIO:1705', 9300.0, 'Retiro efectivo'),
                 ('2022-12-18', 'RETIRO SIN TARJETA', 8000.0, 'Retiro efectivo'),
                 ('2022-10-18', 'RETIRO SIN TARJETA', 5400.0, 'Retiro efectivo'),
                 ('2022-09-21', 'RETIRO CAJERO AUTOMATICO SEP21 21:41 BANCOMER A020 FOLIO:4075', 5000.0, 'Retiro efectivo'),
                 ('2022-07-20', 'SPEI ENVIADO BANAMEX', 9000.0, 'Transferencia enviada'),
                 ('2022-07-22', 'SPEI ENVIADO BAJIO', 5000.0, 'Transferencia enviada'),
                 ('2022-12-18', 'RETIRO SIN TARJETA', 200.0, 'Retiro efectivo'))          # otro monto: no
        for f, d, m, sub in filas:
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES (?,?,?, 'BBVA_DEB', 'FINANZAS', ?, 'GASTO')""", (f, d, m, sub))
        db.commit()
        assert _corregir_pagos_renta(db) == 6
        assert db.execute("SELECT categoria FROM est_movimientos WHERE monto=200").fetchone()[0] == 'FINANZAS'
