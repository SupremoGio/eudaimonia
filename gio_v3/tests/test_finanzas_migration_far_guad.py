"""
test_finanzas_migration_far_guad.py — backfill del histórico ya importado
de FAR GUAD (finanzas_far_guad_por_monto_2026_09, database.py). La lógica
en sí (_corregir_far_guad) ya está probada en
test_finanzas_far_guad_por_monto.py; aquí solo se cubre que la migración
corre, es idempotente, y respeta el mismo umbral/exclusión de EXPENSE.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-03-01', fecha_cargo=None, descripcion='FAR GUAD 111',
                     monto=-100.0, banco='BBVA_TDC', periodo='', categoria='OTROS', subcategoria='',
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_far_guad_por_monto_2026_09'")


def _row(db, tx_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()


def test_migration_reclasifica_historico(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        chico = _insert(db, descripcion='FAR GUAD 111', monto=-99.0, categoria='OTROS')
        grande = _insert(db, descripcion='FAR GUAD 222', monto=-350.0, categoria='OTROS')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row_chico = _row(db, chico)
        row_grande = _row(db, grande)
    assert row_chico['categoria'] == 'ALIMENTACION'
    assert row_chico['subcategoria'] == 'Conveniencia'
    assert row_grande['categoria'] == 'SALUD'
    assert row_grande['subcategoria'] == 'Farmacia'


def test_migration_no_toca_expense(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='FAR GUAD 333', monto=-500.0, categoria='EXPENSE')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'EXPENSE'


def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_far_guad_por_monto_2026_09'"
        ).fetchall()
    assert len(rows) == 1
