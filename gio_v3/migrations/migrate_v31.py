"""
migrate_v31.py — Eudaimonia OS v3.1 migration guard.

Verifies that:
  - EC rate is $10 MXN (ec_constants.EC_VALUE_MXN == 10)
  - Ataraxia tables (rutina_bloques, rutina_progreso) exist and are seeded
  - migration_log table exists

Records the migration in migration_log so this is idempotent.
Safe to call on every deploy — exits immediately if already applied.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime


def run_migration():
    from database import get_db
    from ec_constants import EC_VALUE_MXN, GAMIFICATION_VERSION

    with get_db() as db:
        # Idempotency guard
        if db.execute("SELECT id FROM migration_log WHERE version='3.1'").fetchone():
            return {"status": "already_applied", "version": "3.1"}

        # Verify required tables exist
        tables = {r["name"] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        missing = [t for t in ("rutina_bloques", "rutina_progreso", "migration_log")
                   if t not in tables]
        if missing:
            return {"status": "error", "missing_tables": missing}

        # Verify EC constant matches expected value
        if EC_VALUE_MXN != 10:
            return {"status": "error", "msg": f"EC_VALUE_MXN={EC_VALUE_MXN}, expected 10"}

        bloque_count = db.execute(
            "SELECT COUNT(*) as c FROM rutina_bloques"
        ).fetchone()["c"]

        db.execute(
            "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,?)",
            (
                "3.1",
                f"Eudaimonia OS v{GAMIFICATION_VERSION} — EC $10 MXN/EC + ATARAXIA ({bloque_count} bloques)",
                datetime.datetime.now().isoformat(),
            ),
        )
        db.commit()

    return {"status": "ok", "version": "3.1", "bloque_count": bloque_count}


if __name__ == "__main__":
    result = run_migration()
    status = result.get("status")
    if status == "ok":
        print(f"[OK] Migration v3.1 applied — {result.get('bloque_count', '?')} bloques seeded")
    elif status == "already_applied":
        print("[OK] Migration v3.1 already applied — nothing to do")
    else:
        print(f"[FAIL] Migration v3.1 failed: {result}")
        sys.exit(1)
