"""
test_finanzas_cafe_pan_categoria.py — cubre la migración
finanzas_cafe_pan_categoria_propia_2026_09 en database.py.

El Sprint 3 de taxonomía (finanzas_taxonomia_2026_09_sprint3) había
fusionado CAFE/PAN dentro de ALIMENTACION (subcategoria "Café"/"Pan"). A
petición explícita del usuario se revive CAFE/PAN como categoria propia:
las filas ALIMENTACION con subcategoria Café/Pan vuelven a categoria=
'CAFE/PAN' (conservando la subcategoria), se resiembra
est_categoria_naturaleza para los nuevos códigos, y config.py/budget.py se
actualizan para que las importaciones futuras y el presupuesto ya
clasifiquen ahí directamente.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _insert(db, **kw):
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_TDC', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO')
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )


def test_alimentacion_cafe_reclassified_to_cafe_pan(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_cafe_pan_categoria_propia_2026_09'")
        _insert(db, descripcion='STARBUCKS TORRE', monto=121.0,
                categoria='ALIMENTACION', subcategoria='Café')
        _insert(db, descripcion='PANADERIA EL BUEN PAN', monto=85.0,
                categoria='ALIMENTACION', subcategoria='Pan')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        rows = db.execute(
            "SELECT descripcion, categoria, subcategoria FROM est_movimientos ORDER BY descripcion"
        ).fetchall()
    by_desc = {r['descripcion']: r for r in rows}
    assert by_desc['STARBUCKS TORRE']['categoria'] == 'CAFE/PAN'
    assert by_desc['STARBUCKS TORRE']['subcategoria'] == 'Café'
    assert by_desc['PANADERIA EL BUEN PAN']['categoria'] == 'CAFE/PAN'
    assert by_desc['PANADERIA EL BUEN PAN']['subcategoria'] == 'Pan'


def test_other_alimentacion_subcategorias_untouched(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_cafe_pan_categoria_propia_2026_09'")
        _insert(db, descripcion='WALMART VENTA EN LINEA', monto=500.0,
                categoria='ALIMENTACION', subcategoria='Súper')
        _insert(db, descripcion='TAQUERIA EL BUEN SABOR', monto=200.0,
                categoria='ALIMENTACION', subcategoria='Restaurante')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        rows = db.execute(
            "SELECT descripcion, categoria FROM est_movimientos ORDER BY descripcion"
        ).fetchall()
    for r in rows:
        assert r['categoria'] == 'ALIMENTACION'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_cafe_pan_categoria_propia_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_naturaleza_seeded_for_cafe_pan(test_db):
    import database
    with database.get_db() as db:
        rows = {
            (r['categoria'], r['subcategoria']): r['naturaleza']
            for r in db.execute(
                "SELECT categoria, subcategoria, naturaleza FROM est_categoria_naturaleza "
                "WHERE categoria='CAFE/PAN'"
            ).fetchall()
        }
    assert rows[('CAFE/PAN', 'Café')] == 'VARIABLE'
    assert rows[('CAFE/PAN', 'Pan')] == 'VARIABLE'
    assert rows[('CAFE/PAN', '')] == 'VARIABLE'


def test_get_categoria_subcategoria_now_returns_cafe_pan():
    from modules.finanzas.estados.config import get_categoria_subcategoria
    assert get_categoria_subcategoria('STARBUCKS TORRE') == ('CAFE/PAN', 'Café')
    assert get_categoria_subcategoria('PANADERIA EL BUEN PAN') == ('CAFE/PAN', 'Pan')
    assert get_categoria_subcategoria('NESPRESSO BOUTIQUE') == ('CAFE/PAN', 'Café')
    # SUPER (antes ALIMENTACION) sigue funcionando normal para lo que no es café/pan
    assert get_categoria_subcategoria('WALMART VENTA EN LINEA') == ('SUPER', 'Súper')


def test_cafe_pan_no_longer_a_subcategoria_of_alimentacion():
    from modules.finanzas.estados.config import SUBCATEGORIAS
    assert 'Café' not in SUBCATEGORIAS['SUPER'] + SUBCATEGORIAS['COMIDA_FUERA']
    assert 'Pan' not in SUBCATEGORIAS['SUPER'] + SUBCATEGORIAS['COMIDA_FUERA']
    assert SUBCATEGORIAS['CAFE/PAN'] == ['Café', 'Pan']


def test_budget_has_cafe_pan_bucket_and_label():
    from modules.finanzas.budget import CATEGORIA_BUCKET, CAT_LABELS
    assert CATEGORIA_BUCKET['CAFE/PAN'] == 'deseos'
    assert CAT_LABELS['CAFE/PAN'] == 'Café & Pan'
