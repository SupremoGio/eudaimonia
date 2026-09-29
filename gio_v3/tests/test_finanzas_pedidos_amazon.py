"""
test_finanzas_pedidos_amazon.py — pedidos de Amazon que pasa el usuario:
cada uno se liga a su cargo «AMAZON» por total y fecha y toma su categoría.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import pedidos_amazon as amz
from modules.finanzas.estados import msi
from modules.finanzas.estados.config import SUBCATEGORIAS


def _ins(db, fecha, desc, monto, cat='DIGITAL', sub='Accesorios tech', pn=None, pt=None):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo,
                                                      parcialidad_num, parcialidad_total)
                         VALUES (?,?,?, 'BBVA_TDC', ?, ?, 'GASTO', ?, ?)""",
                      (fecha, desc, monto, cat, sub, pn, pt)).lastrowid


def _cat(db, i):
    return tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())


def test_categorias_validas():
    for *_, cat, sub in amz.PEDIDOS:
        assert sub in SUBCATEGORIAS[cat], (cat, sub)


def test_pedidos_se_ligan_a_su_cargo(test_db):
    with database.get_db() as db:
        maleta = _ins(db, '2026-07-13', 'AMAZON', 999.0, 'DIGITAL', 'Suscripciones entretenimiento')
        casa = _ins(db, '2026-07-13', 'AMAZON', 246.25)
        deso = _ins(db, '2026-07-19', 'AMAZON', 45.45)                 # cobrado 5 días después
        otro = _ins(db, '2026-09-01', 'AMAZON', 45.45)                 # fuera de la ventana
        db.commit()
        ok, faltan = amz.aplicar(db)
        assert _cat(db, maleta) == ('VIVIENDA', 'Artículos del hogar')
        assert _cat(db, casa) == ('VIVIENDA', 'Artículos del hogar')
        assert _cat(db, deso) == ('CUIDADO_PERSONAL', 'Higiene')
        assert _cat(db, otro) == ('DIGITAL', 'Accesorios tech')
        assert (ok, faltan) == (3, len(amz.PEDIDOS) - 3)   # el resto: sus cargos no están en esta base
        assert amz.aplicar(db)[0] == 0


def test_mensualidades_oral_b_a_cuidado_personal(test_db):
    with database.get_db() as db:
        oral = _ins(db, '2026-08-22', 'AMAZON A MESES', 146.0, pn=2, pt=15)
        otra = _ins(db, '2026-08-22', 'AMAZON A MESES', 480.0, pn=3, pt=15)
        db.commit()
        ajena = _ins(db, '2026-08-22', 'AMAZON MX A MESES', 200.0, pn=9, pt=12)
        db.commit()
        msi.marcar_compras(db)
        assert _cat(db, oral) == ('CUIDADO_PERSONAL', 'Higiene')
        assert _cat(db, otra) == ('TECH/DIGITAL', 'Accesorios')          # Apple Watch
        assert _cat(db, ajena) == ('DIGITAL', 'Accesorios tech')


def test_desodorante_de_43_20_no_es_suscripcion(test_db):
    from modules.finanzas.estados.routes import _corregir_amazon_suscripciones
    with database.get_db() as db:
        deso = _ins(db, '2026-05-24', 'AMAZON MEXICO', 43.20)
        db.commit()
        _corregir_amazon_suscripciones(db)                             # corre antes en «Aplicar reglas»
        amz.aplicar(db)
        assert _cat(db, deso) == ('CUIDADO_PERSONAL', 'Higiene')
