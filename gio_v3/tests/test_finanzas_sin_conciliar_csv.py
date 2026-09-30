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
    for *_, cat, sub in corr.CORRECCIONES:
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
        assert (ok, faltan) == (2, len(corr.CORRECCIONES) + len(corr.VIAJES) - 2)
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
