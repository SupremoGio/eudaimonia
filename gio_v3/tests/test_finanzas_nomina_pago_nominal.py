"""
test_finanzas_nomina_pago_nominal.py — cubre la regla de auto-clasificación
de nómina, a petición explícita del usuario: un ingreso que menciona FIBRA
HOTELERA/NOMINA, cae en los días 1-3 o 29-31 del mes, y cuyo monto está
entre $10,000 y $12,000, se clasifica como categoria=NOMINA,
subcategoria='Pago nominal'.

Dos puntos de aplicación, igual que el resto de reglas de Sprint 3:
  1. _auto_clasificar_nomina (routes.py) -- corre en cada /api/upload,
     solo sobre las filas recién insertadas.
  2. finanzas_nomina_pago_nominal_2026_09 (database.py) -- backfill
     histórico de una sola vez, migration_log-guarded.
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


def test_does_not_match_day_outside_window(test_db):
    """El ejemplo real mostrado por el usuario: 02/13/2026 -- día 13, fuera
    de la ventana 1-3 / 29-31 -- no debe clasificarse con esta regla."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-02-13', descripcion='PAGO DE NOMINA FIBRA HOTELERA SC',
                         monto=10422.25, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [tx_id])
        db.commit()
        row = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['subcategoria'] == ''


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
        other_id = _insert(db, fecha='2026-03-01', descripcion='NOMINA', monto=10500.0, subcategoria='')
        db.commit()
        n = _auto_clasificar_nomina(db, [matching_id])
        db.commit()
        other = db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (other_id,)).fetchone()
    assert n == 1
    assert other['subcategoria'] == ''  # no estaba en la lista de ids -- no se toca


# ── Migración histórica ─────────────────────────────────────────────────────

def test_migration_backfills_existing_matching_rows(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'")
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


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'"
        ).fetchall()
    assert len(rows) == 1
