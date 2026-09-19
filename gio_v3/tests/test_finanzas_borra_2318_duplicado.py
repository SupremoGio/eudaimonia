"""
test_finanzas_borra_2318_duplicado.py — única excepción a "nunca borrar
automático" de esta sesión: el usuario, al ver la lista de duplicados
detectados en la auditoría, confirmó directamente sobre su propia base de
datos que la fila 2318 ($50,000, 16/07/2026, "PAGO CUENTA DE
TERCERO/...IGUAL TQM") es un duplicado real de algo que ya tiene como
INGRESO/REGALO, y pidió explícitamente borrarla: "2318 NO ES PAGO YA LO
TENEMOS EN INGRESO BORRA ESE DE PAGO".

A diferencia de los demás duplicados de esta sesión (marcados, nunca
borrados, porque eran una inferencia mía sobre datos que no podía ver en
vivo), aquí sí se borra porque es una instrucción explícita y puntual del
usuario tras verificar su propia DB -- no una migración adivinando.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-07-16', fecha_cargo='2026-07-16',
                     descripcion='PAGO CUENTA DE TERCERO / 0079857034 BNET 1101861239 IGUAL TQM',
                     monto=50000.0, banco='BBVA_TDC', periodo='', categoria='FINANZAS',
                     subcategoria='Pago servicios', tipo='PAGO')
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_borra_2318_duplicado_2026_09'")


def _force_next_id(db, target_id):
    db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
    db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', ?)", (target_id - 1,))


def test_id_2318_se_borra(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2318)
        tx_id = _insert(db)
        assert tx_id == 2318
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row is None


def test_no_borra_otra_fila_con_id_2318_si_descripcion_no_coincide(test_db):
    """Guarda de seguridad: si el id 2318 alguna vez apunta a algo distinto
    (otra fila, otro contexto), no se borra a ciegas por número de id."""
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2318)
        tx_id = _insert(db, descripcion='ALGO COMPLETAMENTE DISTINTO')
        assert tx_id == 2318
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row is not None


def test_no_borra_otras_filas(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2318)
        tx_id = _insert(db)
        _force_next_id(db, 9999)
        otra_id = _insert(db, descripcion='WALMART VENTA EN LINEA', monto=200.0, fecha='2026-01-01')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        otra = db.execute("SELECT * FROM est_movimientos WHERE id=?", (otra_id,)).fetchone()
    assert otra is not None


def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_borra_2318_duplicado_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_migration_idempotente_no_falla_si_ya_no_existe(test_db):
    """La fila ya se borró en la corrida normal de test_db (init_db se
    ejecuta al preparar la fixture) -- correr init_db() otra vez no debe
    fallar aunque el id ya no exista."""
    database.init_db()
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_borra_2318_duplicado_2026_09'"
        ).fetchall()
    assert len(rows) == 1
