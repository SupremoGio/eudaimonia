"""
test_finanzas_aportacion_renta_legacy.py — el usuario vio, en el filtro
"Sin subcategoría" de Ingresos, una fila "SPEI RECIBIDONUBANK 638
0040926TRANSFE... Aportación renta +$5,000.00" y reportó que aparecía
"sin subcategoria" pese a mostrar "Aportación renta".

Causa: APORTACION_RENTA es una categoria de NIVEL SUPERIOR legacy (con
ese mismo nombre de display "Aportación renta" en el mapa de íconos del
frontend) que quedó fuera de la migración finanzas_legacy_bancario_a_
finanzas_2026_09 -- colisiona de nombre con la subcategoria NUEVA
"Aportación renta" que vive bajo VIVIENDA (agregada en
finanzas_ingreso_subcategorias_2026_09). Como APORTACION_RENTA nunca
tuvo subcategorias propias, cualquier fila con esa categoria siempre
tenía subcategoria='' -- de ahí el filtro "Sin subcategoría".

finanzas_aportacion_renta_legacy_2026_09 reclasifica según tipo, igual
que el resto de VIVIENDA: INGRESO -> categoria=VIVIENDA,
subcategoria='Aportación renta'; GASTO -> categoria=VIVIENDA,
subcategoria='Renta'.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _insert(db, **kw):
    defaults = dict(fecha='2026-09-04', fecha_cargo=None, descripcion='X', monto=5000.0,
                     banco='BBVA_DEB', periodo='', categoria='APORTACION_RENTA', subcategoria='',
                     tipo='INGRESO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


def _reset_migration(db):
    db.execute("DELETE FROM migration_log WHERE version='finanzas_aportacion_renta_legacy_2026_09'")


def test_migration_reclasifica_ingreso_a_vivienda_aportacion_renta(test_db):
    import database
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SPEI RECIBIDONUBANK 638 0040926TRANSFE',
                         monto=5000.0, tipo='INGRESO', categoria='APORTACION_RENTA', subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Aportación renta'


def test_migration_reclasifica_gasto_a_vivienda_renta(test_db):
    import database
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='ALGO RARO', monto=-3000.0, tipo='GASTO',
                         categoria='APORTACION_RENTA', subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_migration_does_not_touch_new_vivienda_rows(test_db):
    """Una fila que ya está correctamente en VIVIENDA/Aportación renta
    (de la reclasificación anterior de ingresos) no debe tocarse de
    nuevo -- el filtro es por categoria='APORTACION_RENTA', no por
    subcategoria."""
    import database
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='YA CORRECTA', categoria='VIVIENDA',
                         subcategoria='Aportación renta', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Aportación renta'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_aportacion_renta_legacy_2026_09'"
        ).fetchall()
    assert len(rows) == 1
