"""
test_finanzas_ejecuta_esto_batch.py — el usuario mandó un solo mensaje
("EJECUTA ESTO") con 13 correcciones puntuales de datos reales (ids,
descripciones, montos, categorías actuales) y pidió ejecución directa sin
más preguntas. Cada corrección se implementó como parte de la migración
finanzas_ejecuta_esto_batch_2026_09 en database.py.

Estos tests verifican, uno por uno, que cada corrección hace exactamente
lo pedido y no toca filas que no debía tocar.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-03-13', fecha_cargo='2026-03-13',
                     descripcion='X', monto=-100.0,
                     banco='BBVA_TDC', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO')
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_ejecuta_esto_batch_2026_09'")


def _row(db, tx_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()


def test_amazon_mexico_expense_a_vivienda(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='AMAZON MEXICO COMPRA', categoria='EXPENSE',
                         subcategoria='', monto=-899.0)
        # una fila EXPENSE que no es Amazon no debe tocarse
        otra_id = _insert(db, descripcion='OFFICE DEPOT AMERICAS GUA 378', categoria='EXPENSE',
                           subcategoria='', monto=-378.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
        otra = _row(db, otra_id)
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Artículos del hogar'
    assert otra['categoria'] == 'EXPENSE'


def test_cristal_villahermoza_a_familia_regalos(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SPEI ENVIADO CRISTAL VILLAHERMOSA', categoria='VIVIENDA',
                         subcategoria='Renta', monto=-500.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'FAMILIA_REGALOS'
    assert row['subcategoria'] == 'Regalos'


def test_categoria_regalo_legacy_unificada(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='ALGUN REGALO', categoria='REGALO', subcategoria='',
                         monto=-300.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'FAMILIA_REGALOS'
    assert row['subcategoria'] == 'Regalos'


def test_prestamos_por_id_sin_subcategoria(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM est_movimientos")
        id1 = _insert(db, descripcion='PRESTAMO A', categoria='PRESTAMOS',
                      subcategoria='Prestado a alguien', monto=-1000.0)
        db.commit()
    # Forzamos que el próximo id insertado sea 2571 (ajustando sqlite_sequence)
    with database.get_db() as db:
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 2570)")
        db.commit()
        tx_id = _insert(db, descripcion='PRESTAMO REAL', categoria='PRESTAMOS',
                         subcategoria='Prestado a alguien', monto=-2000.0)
        db.commit()
    assert tx_id == 2571
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
        otra = _row(db, id1)
    assert row['subcategoria'] == ''
    assert row['categoria'] == 'PRESTAMOS'
    # la fila que no está en la lista de ids no se toca
    assert otra['subcategoria'] == 'Prestado a alguien'


def test_railway_a_proyectos_hosting(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='RAILWAY.APP SUSCRIPCION', categoria='OTROS',
                         subcategoria='', monto=-150.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'PROYECTOS'
    assert row['subcategoria'] == 'Hosting'


def test_ztl_zairaaxzaymendozam_por_id_a_alimentacion(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 1987)")
        db.commit()
        tx_id = _insert(db, descripcion='ZTL ZAIRAAXZAYMENDOZAM', categoria='TRANSPORTE',
                         subcategoria='Mantenimiento auto', monto=-200.0)
        db.commit()
    assert tx_id == 1988
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == ''


def test_spei_stp_por_id_a_inversion_gbm(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 3238)")
        db.commit()
        tx_id = _insert(db, descripcion='SPEI ENVIADO STP', categoria='OTROS',
                         subcategoria='', tipo='GASTO', monto=-5000.0)
        db.commit()
    assert tx_id == 3239
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'INVERSION'
    assert row['categoria'] == 'GBM'
    assert row['subcategoria'] == 'APORTACION'
    assert row['monto'] == 5000.0  # positivo, per el modelo de inversiones


def test_spei_invex_por_id_a_pago_tdc(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 3223)")
        db.commit()
        tx_id = _insert(db, descripcion='SPEI ENVIADO INVEX', categoria='OTROS',
                         subcategoria='', tipo='GASTO', monto=-3000.0)
        db.commit()
    assert tx_id == 3224
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'PAGO'
    assert row['categoria'] == 'PAGO_TDC'
    assert row['subcategoria'] == 'Invex TDC'


def test_recargas_bmov_por_id_a_digital_saldo_telefono(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 1662)")
        db.commit()
        tx_id = _insert(db, descripcion='RECARGAS Y PAQUETES BMOV', categoria='OTROS',
                         subcategoria='', monto=-100.0)
        db.commit()
    assert tx_id == 1663
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'DIGITAL'
    assert row['subcategoria'] == 'Saldo telefono'


def test_plantita_por_id_a_expense(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 3234)")
        db.commit()
        tx_id = _insert(db, descripcion='PLANTITA', categoria='OTROS',
                         subcategoria='algo', monto=-50.0)
        db.commit()
    assert tx_id == 3235
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'EXPENSE'
    assert row['subcategoria'] == ''


def test_giovany_por_id_a_ingreso_finanzas(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
        db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', 3224)")
        db.commit()
        tx_id = _insert(db, descripcion='GIOVANY', categoria='OTROS',
                         subcategoria='', tipo='GASTO', monto=-1500.0)
        db.commit()
    assert tx_id == 3225
    with database.get_db() as db:
        _reset_migration(db)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'INGRESO'
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Transferencia'
    assert row['monto'] == 1500.0


def test_viveres_super_legacy_a_alimentacion_super(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='MERPAGO LOSWEROS', categoria='VIVERES/SUPER',
                         subcategoria='', monto=-450.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Súper'


def test_casa_hogar_renta_mban_12000_a_vivienda_renta(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='766236 PAGO TARJETA DE TERCEROS MBAN', categoria='CASA/HOGAR',
                         subcategoria='', tipo='GASTO', monto=-12000.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_casa_hogar_resto_a_vivienda_articulos_hogar(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='HOME DEPOT MEXICO', categoria='CASA/HOGAR',
                         subcategoria='', monto=-800.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Artículos del hogar'


def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_ejecuta_esto_batch_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_migration_es_idempotente(test_db):
    """Correrla dos veces no debe fallar ni duplicar cambios (guardada por
    migration_log, la segunda llamada a init_db() no debe re-ejecutar el
    bloque)."""
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='AMAZON MEXICO OTRA COMPRA', categoria='EXPENSE',
                         subcategoria='', monto=-200.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row_antes = _row(db, tx_id)
    assert row_antes['categoria'] == 'EXPENSE'  # ya corrió antes de este insert, no se re-aplica
    database.init_db()
    with database.get_db() as db:
        row_despues = _row(db, tx_id)
    assert row_despues['categoria'] == 'EXPENSE'
