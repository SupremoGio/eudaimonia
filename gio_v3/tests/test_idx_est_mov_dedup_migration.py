"""
test_idx_est_mov_dedup_migration.py — covers the idx_est_mov_dedup widening
in database.py's init_db().

Auditing real BBVA Libretón statements against their own official totals
(modules/finanzas/estados/routes.py's /admin/audit-montos) surfaced many
"faltan_en_db" entries: real transactions that share the same (fecha,
descripcion) with another transaction the same day (e.g. two separate
"PAGO CUENTA DE TERCERO ... TRANSF A X" transfers) but a different monto.
The root cause: idx_est_mov_dedup was UNIQUE(fecha, descripcion) only, and
imports use INSERT OR IGNORE — so the second transaction was silently
dropped at import time, with no error and no trace. The index now also
includes monto, so only a genuinely exact duplicate (same fecha,
descripcion AND monto) is deduplicated.
"""
import sys, os, sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_fresh_db_gets_the_three_column_index(test_db):
    import database
    with database.get_db() as db:
        idx = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_est_mov_dedup'"
        ).fetchone()
    assert idx is not None
    assert "monto" in idx["sql"]


def test_fresh_db_allows_same_day_same_description_different_monto(test_db):
    import database
    with database.get_db() as db:
        db.execute(
            "INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
            "VALUES ('2025-01-01','TRANSF A X',100,'BBVA_DEB','p','OTROS','','GASTO')"
        )
        db.execute(
            "INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
            "VALUES ('2025-01-01','TRANSF A X',200,'BBVA_DEB','p','OTROS','','GASTO')"
        )
        db.commit()
        n = db.execute(
            "SELECT COUNT(*) c FROM est_movimientos WHERE fecha='2025-01-01' AND descripcion='TRANSF A X'"
        ).fetchone()["c"]
    assert n == 2


def test_fresh_db_still_blocks_exact_duplicate(test_db):
    import database
    with database.get_db() as db:
        db.execute(
            "INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
            "VALUES ('2025-01-01','TRANSF A X',100,'BBVA_DEB','p','OTROS','','GASTO')"
        )
        db.commit()
        try:
            db.execute(
                "INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
                "VALUES ('2025-01-01','TRANSF A X',100,'BBVA_DEB','p','OTROS','','GASTO')"
            )
            db.commit()
            raised = False
        except sqlite3.IntegrityError:
            raised = True
    assert raised, "an exact (fecha, descripcion, monto) duplicate must still be rejected"


def test_existing_db_with_old_two_column_index_gets_migrated_in_place(tmp_path, monkeypatch):
    # Simulate a production database seeded before this fix: the table and
    # its UNIQUE(fecha, descripcion) index already exist, with real data in
    # it — the migration must widen the index without touching that data.
    db_file = str(tmp_path / "old_style.db")
    raw = sqlite3.connect(db_file)
    raw.execute("""CREATE TABLE est_movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, fecha_cargo TEXT,
        descripcion TEXT NOT NULL, monto REAL NOT NULL, banco TEXT NOT NULL DEFAULT '',
        periodo TEXT, categoria TEXT NOT NULL DEFAULT '', subcategoria TEXT DEFAULT '',
        tipo TEXT NOT NULL DEFAULT 'GASTO', mi_parte REAL, reembolso_cat TEXT, viaje_id INTEGER)""")
    raw.execute("CREATE UNIQUE INDEX idx_est_mov_dedup ON est_movimientos (fecha, descripcion)")
    raw.execute(
        "INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
        "VALUES ('2025-01-01','FILA VIEJA',500,'BBVA_DEB','p','OTROS','','GASTO')"
    )
    raw.commit()
    raw.close()

    import database
    monkeypatch.setattr(database, "_DB_PATH", db_file)
    monkeypatch.setattr(database, "_USE_HYBRID", False)
    database.init_db()

    with database.get_db() as db:
        idx = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_est_mov_dedup'"
        ).fetchone()
        assert "monto" in idx["sql"]

        rows = db.execute("SELECT * FROM est_movimientos").fetchall()
        assert len(rows) == 1
        assert rows[0]["descripcion"] == "FILA VIEJA"
        assert rows[0]["monto"] == 500

        # The exact scenario that used to lose data: now it's allowed.
        db.execute(
            "INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
            "VALUES ('2025-01-01','FILA VIEJA',999,'BBVA_DEB','p','OTROS','','GASTO')"
        )
        db.commit()
        n = db.execute(
            "SELECT COUNT(*) c FROM est_movimientos WHERE fecha='2025-01-01' AND descripcion='FILA VIEJA'"
        ).fetchone()["c"]
        assert n == 2


def test_migration_is_idempotent_across_repeated_init_db_calls(tmp_path, monkeypatch):
    db_file = str(tmp_path / "repeat_init.db")
    import database
    monkeypatch.setattr(database, "_DB_PATH", db_file)
    monkeypatch.setattr(database, "_USE_HYBRID", False)
    database.init_db()
    database.init_db()
    database.init_db()

    with database.get_db() as db:
        idx = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_est_mov_dedup'"
        ).fetchone()
    assert "monto" in idx["sql"]
