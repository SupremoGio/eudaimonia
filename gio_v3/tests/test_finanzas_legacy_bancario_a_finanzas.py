"""
test_finanzas_legacy_bancario_a_finanzas.py — cubre la migración que
reclasifica categorías legacy de "movimiento bancario, no gasto/ingreso
real" (DEPOSITO, FIDEICOMISO, SPEI_RECIBIDO, SPEI_ENVIADO, TRANSFERENCIA,
RETIRO, PAGO, PAGO_TDC) a categoria=FINANZAS con la subcategoria que más
calza. El usuario las vio mezcladas con la taxonomía nueva en el dropdown
("categorías viejas... quítalas") y confirmó mandarlas todas a FINANZAS,
pidiendo explícitamente asegurar que la reclasificación no sumara de más
ni dejara duplicados sin detectar.

Dos piezas:
  1. finanzas_legacy_bancario_a_finanzas_2026_09 (database.py) -- backfill
     de una sola vez, migration_log-guarded, con auditoría de duplicados
     (fecha+monto en toda la tabla) registrada en la descripción del log.
  2. budget.py: _INGRESO_EXCLUIR ahora incluye 'FINANZAS' -- sin esto, en
     cuanto DEPOSITO/SPEI_RECIBIDO/etc. (ya excluidos del ingreso real)
     cambiaran a categoria=FINANZAS habrían empezado a contarse de más
     como ingreso real -- el "sumando de más" que el usuario pidió evitar.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _insert(db, **kw):
    defaults = dict(fecha='2026-09-01', fecha_cargo=None, descripcion='X', monto=500.0,
                     banco='MANUAL', periodo='', categoria='DEPOSITO', subcategoria='',
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_legacy_bancario_a_finanzas_2026_09'")


# ── Migración: mapeo por categoria ──────────────────────────────────────────

def test_migration_maps_each_legacy_categoria_to_finanzas_subcategoria(test_db):
    import database
    mapeo_esperado = {
        'DEPOSITO':      'Transferencia',
        'FIDEICOMISO':   'Transferencia',
        'SPEI_RECIBIDO': 'Transferencia',
        'SPEI_ENVIADO':  'Transferencia',
        'TRANSFERENCIA': 'Transferencia',
        'RETIRO':        'Retiro efectivo',
        'PAGO':          'Pago servicios',
        'PAGO_TDC':      'Pago servicios',
    }
    with database.get_db() as db:
        _reset_migration(db)
        ids = {}
        for categoria_vieja in mapeo_esperado:
            ids[categoria_vieja] = _insert(db, descripcion=f'MOV {categoria_vieja}',
                                            categoria=categoria_vieja, subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for categoria_vieja, subcategoria_esperada in mapeo_esperado.items():
            row = db.execute(
                "SELECT categoria, subcategoria FROM est_movimientos WHERE id=?",
                (ids[categoria_vieja],),
            ).fetchone()
            assert row['categoria'] == 'FINANZAS', categoria_vieja
            assert row['subcategoria'] == subcategoria_esperada, categoria_vieja


def test_migration_does_not_touch_current_taxonomy_categorias(test_db):
    """No debe tocar categorías vigentes que no están en el mapeo legacy."""
    import database
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='NOMINA NORMAL', categoria='NOMINA',
                         subcategoria='Pago nominal', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_legacy_bancario_a_finanzas_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_migration_reports_duplicate_groups_in_log_description(test_db):
    """El usuario pidió explícitamente que se audite por duplicados al
    hacer esta reclasificación -- mismo día+monto en dos filas distintas
    debe quedar reportado en la descripción del migration_log."""
    import database
    with database.get_db() as db:
        _reset_migration(db)
        _insert(db, descripcion='PAGO A', fecha='2026-05-05', monto=777.0,
                categoria='PAGO', subcategoria='')
        _insert(db, descripcion='PAGO B', fecha='2026-05-05', monto=777.0,
                categoria='OTROS', subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT description FROM migration_log WHERE version='finanzas_legacy_bancario_a_finanzas_2026_09'"
        ).fetchone()
    assert row is not None
    assert '1 grupo' in row['description'] or 'grupo(s)' in row['description']


# ── budget.py: _INGRESO_EXCLUIR no debe sumar de más tras la migración ─────

def test_finanzas_ingreso_sigue_excluido_del_presupuesto_tras_migracion(test_db):
    """El caso concreto que el usuario pidió evitar: un ingreso que antes
    estaba excluido (categoria=DEPOSITO) no debe empezar a contarse como
    ingreso real solo porque ahora se llama FINANZAS."""
    import database
    from modules.finanzas.budget import _calc_budget

    with database.get_db() as db:
        _reset_migration(db)
        # Ingreso real legítimo (nómina) para que el mes tenga datos.
        _insert(db, descripcion='NOMINA', fecha='2026-06-05', monto=15000.0,
                categoria='NOMINA', subcategoria='Pago nominal', tipo='INGRESO')
        # Este es el que antes se excluía por ser DEPOSITO -- no debe sumar.
        _insert(db, descripcion='DEPOSITO GRANDE', fecha='2026-06-10', monto=50000.0,
                categoria='DEPOSITO', subcategoria='', tipo='INGRESO')
        db.commit()
    database.init_db()  # aplica la migración: DEPOSITO -> FINANZAS/Transferencia

    with database.get_db() as db:
        data = _calc_budget('2026-06', db)
    # Si FINANZAS no estuviera excluido, ingreso_real sería 65000.
    assert data['ingreso_real'] == 15000.0


def test_finanzas_reembolsable_tambien_excluido_del_ingreso_real(test_db):
    """Consistente con que EXPENSE (el gasto original) está excluido del
    gasto real -- el reembolso que regresa (FINANZAS/Reembolsable) debe
    estar igual de excluido del ingreso real, para que el viaje de ida y
    vuelta no afecte el presupuesto."""
    import database
    from modules.finanzas.budget import _calc_budget

    with database.get_db() as db:
        _insert(db, descripcion='NOMINA', fecha='2026-06-05', monto=15000.0,
                categoria='NOMINA', subcategoria='Pago nominal', tipo='INGRESO')
        _insert(db, descripcion='REEMBOLSO AMIGO', fecha='2026-06-12', monto=800.0,
                categoria='FINANZAS', subcategoria='Reembolsable', tipo='INGRESO')
        db.commit()
    with database.get_db() as db:
        data = _calc_budget('2026-06', db)
    assert data['ingreso_real'] == 15000.0
