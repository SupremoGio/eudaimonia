#!/usr/bin/env python3
"""
pre_deploy_check.py — Smoke-checks Eudaimonia OS before a Railway deploy.

Exits 0 = all clear.
Exits 1 = at least one check failed (deploy should be blocked).

Run manually:
  cd gio_v3 && python scripts/pre_deploy_check.py
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _check_ec_constants():
    from ec_constants import EC_VALUE_MXN, GAMIFICATION_VERSION
    errors = []
    if EC_VALUE_MXN != 10:
        errors.append(f"EC_VALUE_MXN={EC_VALUE_MXN}, expected 10 (v3.1 ajuste)")
    if GAMIFICATION_VERSION != "3.1":
        errors.append(f"GAMIFICATION_VERSION={GAMIFICATION_VERSION!r}, expected '3.1'")
    if not errors:
        print(f"[OK] EC constants — {EC_VALUE_MXN} MXN/EC, v{GAMIFICATION_VERSION}")
    return errors


def _check_activities():
    from data import ACTIVITIES
    errors = []
    required = {
        "sat_bloque1", "sat_bloque2", "sat_bloque3", "sat_jugos",
        "sun_reflexion", "sun_diseno", "sun_comidas", "sun_jugos", "sun_planchar",
    }
    missing = required - set(ACTIVITIES)
    if missing:
        errors.append(f"ACTIVITIES missing weekend keys: {sorted(missing)}")
    if "sat_jugos" in ACTIVITIES and not ACTIVITIES["sat_jugos"].get("optional"):
        errors.append("sat_jugos must have optional=True")
    if not errors:
        print(f"[OK] ACTIVITIES — {len(required)} weekend keys verified, sat_jugos=optional")
    return errors


def _check_ataraxia_import():
    errors = []
    try:
        from modules.ataraxia.routes import ataraxia_bp
        print(f"[OK] ataraxia_bp importable ({ataraxia_bp.name})")
    except Exception as e:
        errors.append(f"ataraxia import failed: {e}")
    return errors


def _check_init_db():
    errors = []
    db_file = os.path.join(tempfile.gettempdir(), "eudaimonia_predeploy.db")
    try:
        import database
        orig_path = database._DB_PATH
        orig_hybrid = database._USE_HYBRID
        database._DB_PATH = db_file
        database._USE_HYBRID = False
        database.init_db()
        database._DB_PATH = orig_path
        database._USE_HYBRID = orig_hybrid

        # Quick schema sanity check
        import sqlite3
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for t in ("rutina_bloques", "rutina_progreso", "migration_log",
                  "xp_ledger", "coins_ledger", "rewards"):
            if t not in tables:
                errors.append(f"Table missing after init_db: {t}")
        bloque_count = conn.execute("SELECT COUNT(*) as c FROM rutina_bloques").fetchone()["c"]
        if bloque_count != 18:
            errors.append(f"rutina_bloques has {bloque_count} rows, expected 18")
        conn.close()

        if not errors:
            print(f"[OK] init_db() — schema + 18 rutina tasks seeded")
    except Exception as e:
        errors.append(f"init_db() raised: {e}")
    finally:
        try:
            os.unlink(db_file)
        except (FileNotFoundError, PermissionError, OSError):
            pass  # WAL files may stay locked briefly on Windows — temp dir cleans up eventually
    return errors


def _check_level_thresholds():
    errors = []
    from modules.gamification.engine import LEVEL_THRESHOLDS, get_level_info
    if len(LEVEL_THRESHOLDS) != 10:
        errors.append(f"Expected 10 level thresholds, got {len(LEVEL_THRESHOLDS)}")
    top = get_level_info(99999)
    if top["level"] != 10:
        errors.append(f"Max level should be 10, got {top['level']}")
    if not errors:
        print(f"[OK] Level system — 10 levels, max={top['level_name']}")
    return errors


def main():
    all_errors = []
    for fn in (_check_ec_constants, _check_activities, _check_ataraxia_import,
               _check_init_db, _check_level_thresholds):
        try:
            all_errors.extend(fn())
        except Exception as e:
            all_errors.append(f"Check {fn.__name__} crashed: {e}")

    if all_errors:
        print("\n[FAIL] Pre-deploy check failed:")
        for err in all_errors:
            print(f"  x {err}")
        sys.exit(1)
    else:
        print("\n[OK] All pre-deploy checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
