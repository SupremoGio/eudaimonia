"""
test_finanzas_borra_duplicados_confirmados.py — el usuario revisó el Excel
de duplicados que se le mandó (marcados, no borrados) y confirmó: "SI SON
DUPLICADOS SOLO DEJA EL QUE ESTA EN BBVA DEB LOS DEMAS ELIMINALOS Y BLINDA
QUE NO PASE EN EL FUTURO".

Esto cubre la parte de borrado: finanzas_borra_duplicados_confirmados_2026_09
(database.py) borra los 8 ids del lado BBVA_TDC confirmados, dejando vivo
el lado BBVA_DEB de cada par. La parte de "blindar a futuro" (el dedup
reforzado en upload_file() que ignora tipo para este patrón) se prueba en
test_finanzas_dedup_import_blindaje.py.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-06-02', fecha_cargo='2026-06-02',
                     descripcion='X', monto=100.0,
                     banco='BBVA_DEB', periodo='', categoria='FINANZAS', subcategoria='',
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
    db.execute("DELETE FROM migration_log WHERE version='finanzas_borra_duplicados_confirmados_2026_09'")


def _force_next_id(db, target_id):
    db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
    db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', ?)", (target_id - 1,))


def _row(db, tx_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()


IDS_A_BORRAR = (2387, 2321, 2234, 2237, 2239, 2236, 2235, 2238)
IDS_QUE_SOBREVIVEN = (2383, 2308, 2137, 2144, 2148, 2143, 2139, 2121)


def test_los_8_duplicados_confirmados_se_borran(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        for i, target_id in enumerate(sorted(IDS_A_BORRAR)):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion=f'SPEI RECIBIDONU MEXICO / REF{target_id} TRANSFERENCIA',
                              banco='BBVA_TDC', monto=100.0 + i, categoria='FINANZAS',
                              subcategoria='Posible duplicado (mismo día/monto en BBVA_DEB)')
            assert new_id == target_id
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in IDS_A_BORRAR:
            assert _row(db, tx_id) is None


def test_no_borra_ids_que_no_estan_en_la_lista(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 9999)
        tx_id = _insert(db, descripcion='ALGO NORMAL', monto=500.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row is not None


def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_borra_duplicados_confirmados_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_migration_idempotente_no_falla_si_ids_ya_no_existen(test_db):
    database.init_db()
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_borra_duplicados_confirmados_2026_09'"
        ).fetchall()
    assert len(rows) == 1
