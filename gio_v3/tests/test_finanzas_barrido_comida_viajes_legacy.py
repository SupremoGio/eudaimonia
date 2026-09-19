"""
test_finanzas_barrido_comida_viajes_legacy.py — el usuario reportó que las
categorías legacy siguen confundiéndolo en el selector: "hay comida y luego
alimentancion tambien esta el viejo de viajes/vuelos y el nuevo". La
migración finanzas_taxonomia_2026_09_sprint3 ya había "reemplazado"
COMIDA/REST y VIAJES/VUELOS, pero -- mismo patrón confirmado esta sesión
con CASA/HOGAR, VIVERES/SUPER y REGALO -- dejó filas sin migrar.

finanzas_barrido_comida_viajes_legacy_2026_09 (database.py) barre
cualquier fila restante sin reconstruir el mapeo exacto de sprint3 (_S3_M):
COMIDA/REST -> ALIMENTACION (Café se respeta, el resto a Restaurante, el
mismo default que usaba sprint3), VIAJES/VUELOS -> VIAJES (mismo mapeo de
subcategoria que sprint3, con catch-all a "Otros"). También se quitaron
"COMIDA/REST" y "VIAJES/VUELOS" del selector de categoría en estados.js.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-04-01', fecha_cargo=None, descripcion='X', monto=-100.0,
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_barrido_comida_viajes_legacy_2026_09'")


def _row(db, tx_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()


# ── COMIDA/REST ──────────────────────────────────────────────────────────────

def test_comida_rest_cafe_se_respeta(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='STARBUCKS', categoria='COMIDA/REST', subcategoria='Café')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Café'


def test_comida_rest_resto_va_a_restaurante(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='TACOS EL PASTOR', categoria='COMIDA/REST', subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Restaurante'


def test_comida_rest_con_subcategoria_rara_tambien_va_a_restaurante(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='ALGO', categoria='COMIDA/REST', subcategoria='Antojitos')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Restaurante'


# ── VIAJES/VUELOS ────────────────────────────────────────────────────────────

def test_viajes_vuelos_hotel_va_a_hospedaje(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='MARRIOTT', categoria='VIAJES/VUELOS', subcategoria='Hotel')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Hospedaje'


def test_viajes_vuelos_vuelos_va_a_transporte(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='AEROMEXICO', categoria='VIAJES/VUELOS', subcategoria='Vuelos')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Transporte'


def test_viajes_vuelos_restaurante_va_a_comida(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='RESTAURANTE LOCAL', categoria='VIAJES/VUELOS', subcategoria='Restaurante')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Comida'


def test_viajes_vuelos_blanco_va_a_otros(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='ALGO EN VIAJE', categoria='VIAJES/VUELOS', subcategoria='')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Otros'


def test_viajes_vuelos_subcategoria_no_contemplada_va_a_otros(test_db):
    """Catch-all: una subcategoria que sprint3 nunca enumeró tampoco debe
    quedarse atascada en la categoria vieja."""
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='RENTA DE AUTO', categoria='VIAJES/VUELOS', subcategoria='Auto rentado')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Otros'


# ── No debe tocar datos ya correctos ────────────────────────────────────────

def test_alimentacion_real_no_se_toca(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='WALMART', categoria='ALIMENTACION', subcategoria='Súper')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['subcategoria'] == 'Súper'


def test_viajes_real_no_se_toca(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='AIRBNB CDMX', categoria='VIAJES', subcategoria='Hospedaje')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Hospedaje'


def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_barrido_comida_viajes_legacy_2026_09'"
        ).fetchall()
    assert len(rows) == 1
