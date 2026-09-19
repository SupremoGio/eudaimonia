"""
test_finanzas_msi_group_id_prefijo.py — el usuario mandó un caso real de
MSI: una compra de Walmart a 20 meses ($509 c/u) que el banco no siempre
truncaba igual en la descripción ("WALMART VENTA EN L" vs "WALMART VENTA
EN LIN3"). msi_group_id agrupaba por hash de la descripción COMPLETA +
monto, así que estas dos variantes producían compra_msi_id distintos --
la secuencia de 20 cuotas se partía en dos grupos, cada uno reiniciando
su propia numeración ("18 de 20" y "19 de 20" aparecían repetidos en vez
de ser una sola secuencia 1..20).

Fix confirmado con el usuario (opción "Prefijo corto + monto"):
msi_group_id ahora usa solo los primeros 15 caracteres de la descripción
limpia + el monto de la cuota. Dos piezas:
  1. parsers/_base.py::msi_group_id -- nuevo algoritmo, usado por los
     tres parsers que generan compra_msi_id (bbva_debit vía
     parse_text_statement, bbva_legacy_csv, hsbc).
  2. finanzas_msi_group_id_prefijo_2026_09 (database.py) -- recalcula
     compra_msi_id para las filas de MSI ya importadas con la fórmula
     vieja.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.parsers._base import msi_group_id


def _insert(db, **kw):
    defaults = dict(fecha='2026-08-27', fecha_cargo='2026-08-28', descripcion='WALMART VENTA EN L',
                     monto=509.0, banco='INVEX', periodo='', categoria='ALIMENTACION',
                     subcategoria='Súper', tipo='GASTO', parcialidad_num=19, parcialidad_total=20,
                     compra_msi_id='old_id_1')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo,
            parcialidad_num,parcialidad_total,compra_msi_id)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo,:parcialidad_num,:parcialidad_total,:compra_msi_id)""",
        defaults,
    )
    return cur.lastrowid


# ── msi_group_id (unidad) ───────────────────────────────────────────────────

def test_agrupa_variantes_truncadas_del_mismo_comercio():
    """El caso real: mismo monto, descripción cortada distinto."""
    id1 = msi_group_id('WALMART VENTA EN L', 509.0)
    id2 = msi_group_id('WALMART VENTA EN LIN3', 509.0)
    assert id1 == id2
    assert id1 is not None


def test_distinto_monto_no_se_agrupa():
    """La última cuota real del caso ($498, distinta a las demás $509)
    no debe agruparse con las de $509 -- son compras distintas o al
    menos cuotas de montos distintos, no se fuerza la unión."""
    id_509 = msi_group_id('WALMART VENTA EN L', 509.0)
    id_498 = msi_group_id('WALMART VENTA EN L', 498.0)
    assert id_509 != id_498


def test_comercios_distintos_no_colisionan():
    id_walmart = msi_group_id('WALMART VENTA EN LIN3', 509.0)
    id_costco = msi_group_id('COSTCO VENTA EN LINEA', 509.0)
    assert id_walmart != id_costco


def test_none_desc_retorna_none():
    assert msi_group_id('', 509.0) is None
    assert msi_group_id(None, 509.0) is None


# ── Migración retroactiva ────────────────────────────────────────────────────

def test_migration_reagrupa_msi_existente(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_msi_group_id_prefijo_2026_09'")
        id1 = _insert(db, descripcion='WALMART VENTA EN L', monto=509.0,
                       parcialidad_num=19, compra_msi_id='hash_variante_1')
        id2 = _insert(db, descripcion='WALMART VENTA EN LIN3', monto=509.0,
                       parcialidad_num=18, compra_msi_id='hash_variante_2_distinto')
        id3 = _insert(db, descripcion='WALMART VENTA EN L', monto=498.0,
                       parcialidad_num=20, compra_msi_id='hash_variante_3')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row1 = db.execute("SELECT compra_msi_id FROM est_movimientos WHERE id=?", (id1,)).fetchone()
        row2 = db.execute("SELECT compra_msi_id FROM est_movimientos WHERE id=?", (id2,)).fetchone()
        row3 = db.execute("SELECT compra_msi_id FROM est_movimientos WHERE id=?", (id3,)).fetchone()
    # Las dos cuotas de $509 (antes en grupos distintos) ahora comparten compra_msi_id.
    assert row1['compra_msi_id'] == row2['compra_msi_id']
    # La cuota final de $498 sigue en su propio grupo (monto distinto).
    assert row3['compra_msi_id'] != row1['compra_msi_id']


def test_migration_does_not_touch_non_msi_rows(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_msi_group_id_prefijo_2026_09'")
        tx_id = _insert(db, descripcion='WALMART NORMAL', monto=1200.0,
                         parcialidad_num=None, parcialidad_total=None, compra_msi_id=None)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT compra_msi_id FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['compra_msi_id'] is None


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_msi_group_id_prefijo_2026_09'"
        ).fetchall()
    assert len(rows) == 1
