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
    assert len(corr.CORRECCIONES) == 214 and len({c[0] for c in corr.CORRECCIONES}) == 214


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
