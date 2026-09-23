"""
test_finanzas_ingreso_subcategorias.py — cubre la migración
finanzas_ingreso_subcategorias_2026_09 en database.py.

A petición explícita del usuario, tres cambios del lado de ingreso (nunca
tocan el lado de gasto de las mismas categoria/subcategoria):

  1. INGRESO de categoria=TRANSPORTE, subcategoria='Gasolina' (en realidad
     un pago de seguro, no gasolina real) -> subcategoria='Seguro auto'
     (la que ya existe en el sistema para esto).
  2. INGRESO de categoria=VIVIENDA, subcategoria='Renta' (alguien
     aportando para la renta) -> subcategoria='Aportación renta', para
     distinguirlo de la renta real que paga el usuario (GASTO).
  3. SUBCATEGORIAS gana NOMINA:[Pago nominal, Bono] y VIVIENDA gana
     'Aportación renta' como opción -- solo se agregan las opciones, no se
     reclasifica nada existente de nómina/bono.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _insert(db, **kw):
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_DEB', periodo='', categoria='OTROS', subcategoria='',
                     tipo='INGRESO')
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )


def test_ingreso_transporte_gasolina_reclassified_to_seguro_auto(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_ingreso_subcategorias_2026_09'")
        _insert(db, descripcion='SPEI RECIBIDO PAGO SEGURO AUTO', monto=9500.0,
                categoria='TRANSPORTE', subcategoria='Gasolina', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='SPEI RECIBIDO PAGO SEGURO AUTO'"
        ).fetchone()
    assert row['categoria'] == 'TRANSPORTE'
    assert row['subcategoria'] == 'Seguro auto'


def test_gasto_transporte_gasolina_untouched(test_db):
    """Las compras reales de gasolina (GASTO) nunca deben tocarse."""
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_ingreso_subcategorias_2026_09'")
        _insert(db, descripcion='PEMEX GASOLINERA', monto=800.0,
                categoria='TRANSPORTE', subcategoria='Gasolina', tipo='GASTO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='PEMEX GASOLINERA'"
        ).fetchone()
    assert row['subcategoria'] == 'Gasolina'


def test_ingreso_vivienda_renta_reclassified_to_aportacion(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_ingreso_subcategorias_2026_09'")
        _insert(db, descripcion='SPEI RECIBIDO ROOMMATE RENTA', monto=4000.0,
                categoria='VIVIENDA', subcategoria='Renta', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='SPEI RECIBIDO ROOMMATE RENTA'"
        ).fetchone()
    assert row['subcategoria'] == 'Aportación renta'


def test_gasto_vivienda_renta_untouched(test_db):
    """La renta real que paga el usuario (GASTO) nunca debe tocarse."""
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_ingreso_subcategorias_2026_09'")
        _insert(db, descripcion='PAGO RENTA DEPTO', monto=7000.0,
                categoria='VIVIENDA', subcategoria='Renta', tipo='GASTO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='PAGO RENTA DEPTO'"
        ).fetchone()
    assert row['subcategoria'] == 'Renta'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_ingreso_subcategorias_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_subcategorias_gained_nomina_and_aportacion_renta():
    from modules.finanzas.estados.config import SUBCATEGORIAS
    # PTU y Fondo de ahorro se agregaron después (commit 9d58fe7); lo que
    # garantiza esta migración es que existan Pago nominal y Bono.
    assert SUBCATEGORIAS['NOMINA'][:2] == ['Pago nominal', 'Bono']
    assert {'PTU', 'Fondo de ahorro'} <= set(SUBCATEGORIAS['NOMINA'])
    assert 'Renta' in SUBCATEGORIAS['VIVIENDA']
    assert 'Aportación renta' in SUBCATEGORIAS['VIVIENDA']
