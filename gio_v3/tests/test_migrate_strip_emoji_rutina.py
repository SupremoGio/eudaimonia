"""
test_migrate_strip_emoji_rutina.py — covers migrations/migrate_strip_emoji_rutina.py.

The historical seed data in database.py used to bake an emoji into the
start of every rutina_bloques.nombre ("🪟 Ventilación Fast Track..."). The
seed literals are now clean, but existing databases seeded before that fix
still carry the emoji — this migration cleans them up for real.

Execution:
  cd gio_v3
  python -m pytest tests/test_migrate_strip_emoji_rutina.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re


def _seed_dirty_row(db):
    # Simulate a database seeded before the emoji fix: one row with an
    # emoji prefix baked into `nombre`, same shape as the historical data.
    db.execute(
        "UPDATE rutina_bloques SET nombre=? WHERE id='sat_ventilacion'",
        ("🪟 Ventilación Fast Track (abrir ventanas)",),
    )
    db.commit()


class TestMigrateStripEmojiRutina:

    def test_fresh_seed_is_already_clean(self, test_db):
        # database.py's seed literals no longer carry emoji — nothing for
        # the migration to do on a freshly-initialized database.
        import database
        EMOJI_RE = re.compile(r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF]️?\s*')
        with database.get_db() as db:
            rows = db.execute("SELECT nombre FROM rutina_bloques").fetchall()
        assert rows, "rutina_bloques should be seeded"
        assert not any(EMOJI_RE.match(r["nombre"]) for r in rows)

    def test_migration_cleans_dirty_row(self, test_db):
        import database
        with database.get_db() as db:
            _seed_dirty_row(db)

        from migrations.migrate_strip_emoji_rutina import run_migration
        result = run_migration()
        assert result["status"] == "ok"
        assert result["updated"] == 1

        with database.get_db() as db:
            row = db.execute(
                "SELECT nombre FROM rutina_bloques WHERE id='sat_ventilacion'"
            ).fetchone()
        assert row["nombre"] == "Ventilación Fast Track (abrir ventanas)"

    def test_migration_is_idempotent(self, test_db):
        import database
        with database.get_db() as db:
            _seed_dirty_row(db)

        from migrations.migrate_strip_emoji_rutina import run_migration
        run_migration()
        result2 = run_migration()
        assert result2["status"] == "already_applied"

    def test_migration_noop_on_already_clean_data(self, test_db):
        # A fresh DB is already clean (seed literals fixed) — the migration
        # should still succeed but touch 0 rows.
        from migrations.migrate_strip_emoji_rutina import run_migration
        result = run_migration()
        assert result["status"] == "ok"
        assert result["updated"] == 0

    def test_migration_log_entry_persists(self, test_db):
        import database
        from migrations.migrate_strip_emoji_rutina import run_migration
        run_migration()
        with database.get_db() as db:
            row = db.execute(
                "SELECT * FROM migration_log WHERE version='strip_emoji_rutina_bloques'"
            ).fetchone()
        assert row is not None
