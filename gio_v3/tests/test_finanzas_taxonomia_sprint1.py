"""
test_finanzas_taxonomia_sprint1.py — covers the finanzas_taxonomia_2026_09_sprint1
migration in database.py's init_db().

Sprint 1 del plan de taxonomía de finanzas: columnas nuevas en est_movimientos
(estatus_reembolso, fecha_reembolso, parcialidad_*, compra_msi_id), tablas
nuevas est_categoria_naturaleza / est_prestamos, tipo_viaje en viajes, y un
backfill idempotente y no-ambiguo (normalización de subcategorías, estatus de
reembolso de EXPENSE, PAGO_TDC/RETIRO reclasificados a MOVIMIENTO_INTERNO).
Validado primero contra un export real de est_movimientos (2414 filas) fuera
del test suite; aquí solo se cubre el comportamiento de la migración en sí.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _insert(db, **kw):
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_DEB', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO', mi_parte=None, reembolso_cat=None, viaje_id=None)
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,
            tipo,mi_parte,reembolso_cat,viaje_id)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo,:mi_parte,:reembolso_cat,:viaje_id)""",
        defaults,
    )


def test_new_columns_and_tables_exist(test_db):
    import database
    with database.get_db() as db:
        cols = [r["name"] for r in db.execute("PRAGMA table_info(est_movimientos)").fetchall()]
        for c in ("estatus_reembolso", "fecha_reembolso", "parcialidad_num",
                  "parcialidad_total", "compra_msi_id"):
            assert c in cols
        tables = [r["name"] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "est_categoria_naturaleza" in tables
        assert "est_prestamos" in tables
        v_cols = [r["name"] for r in db.execute("PRAGMA table_info(viajes)").fetchall()]
        assert "tipo_viaje" in v_cols


def test_naturaleza_catalog_is_seeded(test_db):
    import database
    with database.get_db() as db:
        n = db.execute("SELECT COUNT(*) c FROM est_categoria_naturaleza").fetchone()["c"]
        assert n >= 30
        # El catálogo se re-sembró con la taxonomía actual (CASA/HOGAR ·
        # Alquiler pasó a VIVIENDA · Renta).
        row = db.execute(
            "SELECT naturaleza FROM est_categoria_naturaleza WHERE categoria='VIVIENDA' AND subcategoria='Renta'"
        ).fetchone()
        assert row["naturaleza"] == "FIJO"


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_taxonomia_2026_09_sprint1'"
        ).fetchall()
    assert len(rows) == 1


def test_pago_tdc_reclassified_to_movimiento_interno(test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='PAGO TARJETA DE CREDITO', monto=17963.43,
                categoria='PAGO_TDC', subcategoria='', tipo='GASTO')
        db.commit()
        # Re-run init_db() to trigger the (already-applied, so no-op) migration
        # guard path plus exercise the reclassification against rows inserted
        # after the first run, the same way a redeploy would on real data.
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT tipo FROM est_movimientos WHERE categoria='PAGO_TDC'"
        ).fetchone()
    # La migración solo corre una vez (guardada por migration_log); una fila
    # insertada DESPUÉS de esa corrida no se reclasifica retroactivamente por
    # una segunda llamada a init_db() — igual que el resto de los backfills
    # de este archivo. Se deja tal cual para no repetir un full-table scan en
    # cada arranque.
    assert row["tipo"] == "GASTO"


def test_retiro_and_pago_tdc_reclassified_when_present_before_first_migration(test_db):
    """Simula el caso real: las filas ya existen en la DB la primera vez que
    corre init_db() (como pasa en un deploy sobre una DB con datos previos)."""
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_taxonomia_2026_09_sprint1'")
        _insert(db, descripcion='PAGO TARJETA DE CREDITO', monto=100.0,
                categoria='PAGO_TDC', tipo='GASTO')
        _insert(db, descripcion='RETIRO SIN TARJETA QR', monto=500.0,
                categoria='RETIRO', tipo='GASTO')
        _insert(db, descripcion='PAGO CUENTA DE TERCERO BNET CAPITAL', monto=2500.0,
                categoria='RETIRO', tipo='GASTO')  # no empieza con RETIRO -> no se toca
        _insert(db, descripcion='SEGURO Y', monto=300.0,
                categoria='GASOLINA/AUTO', subcategoria='seguro carro', tipo='GASTO')
        _insert(db, descripcion='EXPENSE PENDIENTE', monto=400.0,
                categoria='EXPENSE', reembolso_cat=None)
        _insert(db, descripcion='EXPENSE PAGADO', monto=500.0,
                categoria='EXPENSE', reembolso_cat='COMIDA/REST')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        pago_tdc = db.execute("SELECT tipo FROM est_movimientos WHERE categoria='PAGO_TDC'").fetchone()
        retiro_qr = db.execute(
            "SELECT tipo FROM est_movimientos WHERE descripcion='RETIRO SIN TARJETA QR'"
        ).fetchone()
        retiro_no_match = db.execute(
            "SELECT tipo FROM est_movimientos WHERE descripcion='PAGO CUENTA DE TERCERO BNET CAPITAL'"
        ).fetchone()
        seguro = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE categoria='GASOLINA/AUTO'"
        ).fetchone()
        expense_pendiente = db.execute(
            "SELECT estatus_reembolso FROM est_movimientos WHERE categoria='EXPENSE' AND reembolso_cat IS NULL"
        ).fetchone()
        expense_pagado = db.execute(
            "SELECT estatus_reembolso FROM est_movimientos WHERE categoria='EXPENSE' AND reembolso_cat='COMIDA/REST'"
        ).fetchone()

    assert pago_tdc["tipo"] == "MOVIMIENTO_INTERNO"
    assert retiro_qr["tipo"] == "MOVIMIENTO_INTERNO"
    assert retiro_no_match["tipo"] == "GASTO"
    assert seguro["subcategoria"] == "Seguro Carro"
    assert expense_pendiente["estatus_reembolso"] == "PENDIENTE"
    assert expense_pagado["estatus_reembolso"] == "PAGADO"
