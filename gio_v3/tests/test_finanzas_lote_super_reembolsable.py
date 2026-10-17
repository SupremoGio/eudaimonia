"""
test_finanzas_lote_super_reembolsable.py — lote de correcciones puntuales
("MANDA A SUBCATEGORIA SUPER" y las instrucciones que siguieron en el mismo
mensaje) implementado en finanzas_lote_super_reembolsable_2026_09
(database.py).

Incluye la corrección de id 3228: el usuario había dicho antes "mandalo a
pago de prestamo ingreso" (categoria=PRESTAMOS), pero en este mensaje
corrigió: "esto es ingreso pago expense" -- se corrige a FINANZAS/
Reembolsable, la misma clasificación que ya usa el resto de reembolsos de
EXPENSE cobrados esta sesión.

También cubre "COBRADO Y REEMBOLSABLE ES LO MISMO UNIFICA": PRESTAMOS ya
no debe tener "Cobrado" como opción de subcategoria (ver
config.py::SUBCATEGORIAS) y cualquier fila existente con esa subcategoria
se unifica a FINANZAS/Reembolsable.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados.config import SUBCATEGORIAS


def _insert(db, **kw):
    defaults = dict(fecha='2026-03-13', fecha_cargo='2026-03-13',
                     descripcion='X', monto=100.0,
                     banco='BBVA_DEB', periodo='', categoria='OTROS', subcategoria='',
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_lote_super_reembolsable_2026_09'")


def _force_next_id(db, target_id):
    db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
    db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', ?)", (target_id - 1,))


def _row(db, tx_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()


def test_config_prestamos_ya_no_ofrece_cobrado():
    assert SUBCATEGORIAS['PRESTAMOS'] == ['Prestado']


def test_ztl_ids_van_a_super(test_db):
    ids = [1988, 1612]
    with database.get_db() as db:
        _reset_migration(db)
        for i, target_id in enumerate(sorted(ids)):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion=f'ZTL ZAIRAAXZAYMENDOZAM {i}', monto=99.02 + i,
                              categoria='ALIMENTACION', subcategoria='', tipo='GASTO')
            assert new_id == target_id
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in ids:
            row = _row(db, tx_id)
            assert row['categoria'] == 'ALIMENTACION'
            assert row['subcategoria'] == 'Súper'


def test_fideicomiso_10_ids_van_a_finanzas_reembolsable(test_db):
    ids = [2580, 2529, 2494, 2371, 2247, 2104, 2057, 2006, 1726, 1625]
    with database.get_db() as db:
        _reset_migration(db)
        for i, target_id in enumerate(sorted(ids)):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion='FIDEICOMISO F 1596', monto=100.0 + i,
                              categoria='FINANZAS', subcategoria='Fideicomiso', tipo='INGRESO')
            assert new_id == target_id
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in ids:
            row = _row(db, tx_id)
            assert row['categoria'] == 'FINANZAS'
            assert row['subcategoria'] == 'Reembolsable'


def test_id_3228_corregido_a_finanzas_reembolsable(test_db):
    """Corrección de la decisión anterior (categoria=PRESTAMOS) -- el
    usuario aclaró que es un reembolso de expense, no un cobro de
    préstamo."""
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 3228)
        tx_id = _insert(db, descripcion='PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A',
                        categoria='PRESTAMOS', subcategoria='', tipo='INGRESO', monto=1900.0)
        assert tx_id == 3228
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'


def test_id_2079_va_a_regalos(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2079)
        tx_id = _insert(db, descripcion='SU PAGO EN EFECTIVO EN COMERCIO', categoria='FAMILIA_REGALOS',
                        subcategoria='', tipo='INGRESO', monto=5000.0)
        assert tx_id == 2079
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'FAMILIA_REGALOS'
    assert row['subcategoria'] == 'Regalos'


def test_cetes_retiro_por_error_se_corrige_a_aportacion(test_db):
    ids = [1605, 1621, 1632, 1653, 1926, 2021, 2099, 2248]
    with database.get_db() as db:
        _reset_migration(db)
        for i, target_id in enumerate(sorted(ids)):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion=f'SPEI ENVIADO STP {i}', monto=4000.0 + i,
                              categoria='CETES', subcategoria='RETIRO', tipo='INVERSION')
            assert new_id == target_id
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in ids:
            row = _row(db, tx_id)
            assert row['subcategoria'] == 'APORTACION'


def test_cetes_retiro_real_no_se_toca_si_no_esta_en_la_lista(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 3220)
        tx_id = _insert(db, descripcion='SPEI RECIBIDONAFIN', categoria='CETES',
                        subcategoria='RETIRO', tipo='INVERSION', monto=4090.15)
        assert tx_id == 3220
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['subcategoria'] == 'RETIRO'


def test_id_1679_prestamo_a_hermana(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 1679)
        tx_id = _insert(db, descripcion='PAGO CUENTA DE TERCERO BNET COSITAS', categoria='FINANZAS',
                        subcategoria='Transferencia', tipo='GASTO', monto=4500.0)
        assert tx_id == 1679
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'PRESTAMOS'
    assert row['subcategoria'] == ''


def test_prestamos_cobrado_unificado_a_finanzas_reembolsable(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='ALGUIEN ME PAGO UN PRESTAMO', categoria='PRESTAMOS',
                        subcategoria='Cobrado', tipo='INGRESO', monto=800.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'


def test_prestamos_prestado_no_se_toca(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='LE PRESTE A ALGUIEN', categoria='PRESTAMOS',
                        subcategoria='Prestado', tipo='GASTO', monto=-800.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'PRESTAMOS'
    assert row['subcategoria'] == 'Prestado'


def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_lote_super_reembolsable_2026_09'"
        ).fetchall()
    assert len(rows) == 1
