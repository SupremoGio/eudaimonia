"""
test_finanzas_nomina_pago_nominal.py — cubre la regla de auto-clasificación
de nómina, a petición explícita del usuario: un ingreso que menciona FIBRA
HOTELERA/NOMINA y cuyo monto está entre $9,000 y $12,000 se clasifica
como categoria=NOMINA, subcategoria='Pago nominal'.

La v1 también exigía que la fecha cayera en los días 1-3/29-31 del mes,
pero un caso real (PAGO DE NOMINA FIBRA HOTELERA SC, $10,422.25,
02/13/2026) no calzaba con esa ventana -- el banco no siempre paga en
fechas fijas -- así que se quitó esa condición (v2): ahora solo importa
texto + monto.

La v2 usaba el rango $10,000-$12,000 (sueldo de 2026), pero el sueldo de
2025 (antes de un aumento) caía entre $9,000 y $11,000 -- fuera de ese
piso -- así que esos ingresos de nómina de 2025 nunca se reclasificaban
aunque el texto sí calzara. Se amplió el rango a $9,000-$12,000 (v3) para
cubrir ambos años con una sola regla.

Tres puntos de aplicación, igual que el resto de reglas de Sprint 3:
  1. _auto_clasificar_nomina (routes.py) -- corre en cada /api/upload,
     solo sobre las filas recién insertadas.
  2. finanzas_nomina_pago_nominal_2026_09 (v1, con filtro de fecha),
     finanzas_nomina_pago_nominal_v2_2026_09 (v2, sin filtro de fecha, rango
     $10,000-$12,000) y finanzas_nomina_pago_nominal_v3_2026_09 (v3, rango
     ampliado a $9,000-$12,000) en database.py -- backfills históricos de
     una sola vez, migration_log-guarded. Cada ajuste se agregó como
     migración nueva en vez de reescribir la anterior porque la anterior
     pudo haber corrido ya en producción antes del ajuste.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.routes import _auto_clasificar_nomina


def _insert(db, **kw):
    defaults = dict(fecha='2026-02-01', fecha_cargo=None, descripcion='X', monto=10500.0,
                     banco='BBVA_DEB', periodo='', categoria='NOMINA', subcategoria='',
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


# ── _auto_clasificar_nomina (regla en vivo al importar) ────────────────────

def test_matches_fibra_hotelera_day_1_amount_in_range(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-02-01', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                         monto=10422.25)
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_matches_mid_month_day_13_real_case(test_db):
    """El caso real que motivó el ajuste: día 13, fuera de la vieja
    ventana 1-3/29-31 -- ahora sí debe clasificarse."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-02-13', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                         monto=10422.25, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_matches_end_of_month_day_30(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-04-30', descripcion='SPEI RECIBIDO NOMINA EMPRESA',
                         monto=11000.0)
        db.commit()
        _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['subcategoria'] == 'Pago nominal'


def test_does_not_match_amount_outside_range(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-02-01', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                         monto=25000.0, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['subcategoria'] == ''


def test_matches_2025_lower_salary_within_widened_range(test_db):
    """El sueldo de 2025 (antes de un aumento) caía entre $9,000 y
    $11,000 -- fuera del piso original de $10,000 -- así que la v3
    amplió el rango a $9,000-$12,000."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2025-03-14', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                         monto=9500.0, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_does_not_match_below_widened_floor(test_db):
    """$8,999 sigue quedando fuera -- el piso ampliado es $9,000, no
    ilimitado hacia abajo."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2025-03-14', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                         monto=8999.0, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['subcategoria'] == ''


def test_does_not_match_gasto(test_db):
    """Nunca debe tocar un GASTO aunque el texto y el monto calcen."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-02-01', descripcion='PAGO NOMINA EMPLEADOS',
                         monto=10500.0, tipo='GASTO', categoria='OTROS', subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'OTROS'
    assert row['subcategoria'] == ''


def test_only_touches_given_ids(test_db):
    import database
    with database.get_db() as db:
        matching_id = _insert(db, fecha='2026-02-01', descripcion='NOMINA', monto=10500.0, subcategoria='')
        other_id = _insert(db, fecha='2026-03-15', descripcion='NOMINA', monto=10500.0, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [matching_id])
        db.commit()
        other = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (other_id,)).fetchone()
    assert n == 1
    assert other['subcategoria'] == ''  # no estaba en la lista de ids -- no se toca


# ── Migraciones históricas ──────────────────────────────────────────────────

def test_v1_migration_backfills_rows_within_old_date_window(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'")
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v2_2026_09'")
        _insert(db, fecha='2026-02-01', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                monto=10422.25, subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='PAGO DE NOMINA FIBRA HOTELERA SC'"
        ).fetchone()
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_v2_migration_backfills_rows_outside_old_date_window(test_db):
    """El caso real que motivó el ajuste: día 13, la v1 nunca lo hubiera
    tocado -- la v2 sí debe reclasificarlo."""
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'")
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v2_2026_09'")
        _insert(db, fecha='2026-02-13', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                monto=10422.25, subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion='PAGO DE NOMINA FIBRA HOTELERA SC'"
        ).fetchone()
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_v3_migration_backfills_2025_lower_salary_rows(test_db):
    """El sueldo de 2025 (antes de un aumento) caía entre $9,000 y
    $11,000 -- fuera del piso de $10,000 que usaban v1/v2 -- así que
    nunca se reclasificaba aunque el texto calzara. La v3 amplía el
    rango a $9,000-$12,000 y debe backfillearlo."""
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'")
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v2_2026_09'")
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v3_2026_09'")
        _insert(db, fecha='2025-03-14', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                monto=9500.0, subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE fecha='2025-03-14'"
        ).fetchone()
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


def test_all_three_migrations_are_logged_once(test_db):
    import database
    with database.get_db() as db:
        v1 = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'"
        ).fetchall()
        v2 = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v2_2026_09'"
        ).fetchall()
        v3 = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v3_2026_09'"
        ).fetchall()
    assert len(v1) == 1
    assert len(v2) == 1
    assert len(v3) == 1
