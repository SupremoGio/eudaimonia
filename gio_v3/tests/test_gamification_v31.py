"""
test_gamification_v31.py — Regression suite for Eudaimonia OS v3.1.

Covers:
  1. EC constants — EC_VALUE_MXN=10, GAMIFICATION_VERSION='3.1'
  2. ACTIVITIES — weekend keys exist (Sábado 7 bloques, Domingo 9), Jugos opcional
  3. Saturday combo — fires with the 6 required bloques, sat_jugos_bloque NOT required
  4. Sunday combo   — fires only when all 9 sun bloques are present
  5. Migration      — run_migration() is idempotent (second call = already_applied)
  6. Reward prices  — seeds use EC costs calibrated to $10 MXN/EC

Execution:
  cd gio_v3
  python -m pytest tests/test_gamification_v31.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# 1. EC constants
# ══════════════════════════════════════════════════════════════════════════════

class TestECConstants:

    def test_ec_value_mxn_is_10(self):
        from ec_constants import EC_VALUE_MXN
        assert EC_VALUE_MXN == 10, f"EC_VALUE_MXN={EC_VALUE_MXN}, should be 10 (v3.1 ajuste)"

    def test_ec_rate_alias_matches(self):
        from ec_constants import EC_RATE, EC_VALUE_MXN
        assert EC_RATE == EC_VALUE_MXN

    def test_gamification_version_is_3_1(self):
        from ec_constants import GAMIFICATION_VERSION
        assert GAMIFICATION_VERSION == "3.1"

    def test_changelog_mentions_10_mxn(self):
        from ec_constants import EC_VALUE_CHANGELOG
        assert "10" in EC_VALUE_CHANGELOG


# ══════════════════════════════════════════════════════════════════════════════
# 2. ACTIVITIES — weekend keys
#    Sábado: 7 bloques (6 requeridos + Jugos opcional); Domingo: 9 bloques.
#    Las claves salen de engine.SAT_COMBO_KEYS / SUN_COMBO_KEYS para que el
#    test no se desincronice del motor como pasó tras el refactor de ATARAXIA.
# ══════════════════════════════════════════════════════════════════════════════

class TestActivitiesWeekendKeys:

    def test_sat_combo_keys_exist(self):
        from data import ACTIVITIES
        from modules.gamification.engine import SAT_COMBO_KEYS, SAT_OPTIONAL_KEYS
        missing = (SAT_COMBO_KEYS | SAT_OPTIONAL_KEYS) - set(ACTIVITIES)
        assert not missing, f"Missing sat keys in ACTIVITIES: {missing}"

    def test_sun_combo_keys_exist(self):
        from data import ACTIVITIES
        from modules.gamification.engine import SUN_COMBO_KEYS
        missing = SUN_COMBO_KEYS - set(ACTIVITIES)
        assert not missing, f"Missing sun combo keys in ACTIVITIES: {missing}"

    def test_block_counts(self):
        from modules.gamification.engine import SAT_COMBO_KEYS, SAT_OPTIONAL_KEYS, SUN_COMBO_KEYS
        assert len(SAT_COMBO_KEYS | SAT_OPTIONAL_KEYS) == 7
        assert len(SUN_COMBO_KEYS) == 9

    def test_sat_jugos_is_not_required(self):
        from modules.gamification.engine import SAT_COMBO_KEYS, SAT_OPTIONAL_KEYS
        assert "sat_jugos_bloque" in SAT_OPTIONAL_KEYS
        assert "sat_jugos_bloque" not in SAT_COMBO_KEYS

    def test_sat_jugos_pts_and_ec(self):
        from data import ACTIVITIES
        act = ACTIVITIES["sat_jugos_bloque"]
        assert act["pts"] == 2
        assert act["ec"] == 1

    def test_sat_keys_have_weekend_marker(self):
        from data import ACTIVITIES
        from modules.gamification.engine import SAT_COMBO_KEYS, SAT_OPTIONAL_KEYS
        for key in SAT_COMBO_KEYS | SAT_OPTIONAL_KEYS:
            assert ACTIVITIES[key].get("weekend") == "sat", f"{key} missing weekend='sat'"
            assert ACTIVITIES[key]["tier"] in ("micro", "progreso", "alto"), f"{key} tier"

    def test_sun_keys_have_weekend_marker(self):
        from data import ACTIVITIES
        from modules.gamification.engine import SUN_COMBO_KEYS
        for key in SUN_COMBO_KEYS:
            assert ACTIVITIES[key].get("weekend") == "sun", f"{key} missing weekend='sun'"


# ══════════════════════════════════════════════════════════════════════════════
# 3/4. Weekend combos
# ══════════════════════════════════════════════════════════════════════════════

def _insert_keys(keys, today):
    import database
    with database.get_db() as db:
        for key in keys:
            db.execute(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                (key, today, 4),
            )
        db.commit()


def _combos(monkeypatch, today, keys):
    import datetime
    from modules.gamification import engine
    monkeypatch.setattr(engine, "today_str", lambda: today)
    monkeypatch.setattr(engine, "today_date", lambda: datetime.date.fromisoformat(today))
    _insert_keys(keys, today)
    return engine._check_combo_bonus(today, engine._get_today_keys(today))


def _ledger_sum(table, description, today):
    import database
    with database.get_db() as db:
        return db.execute(
            f"SELECT COALESCE(SUM(amount),0) as s FROM {table} "
            "WHERE source='bonus' AND description=? AND date=?",
            (description, today),
        ).fetchone()["s"]


class TestSaturdayCombo:
    TODAY = "2026-04-25"  # a Saturday

    def test_fires_with_all_required_bloques(self, test_db, monkeypatch):
        from modules.gamification.engine import SAT_COMBO_KEYS
        combos = _combos(monkeypatch, self.TODAY, sorted(SAT_COMBO_KEYS))
        assert any(c["type"] == "sat_complete" for c in combos), \
            "sat_complete combo should fire with the 6 required sat bloques"

    def test_fires_even_with_sat_jugos(self, test_db, monkeypatch):
        """Adding the optional Jugos bloque on top must not break the combo."""
        from modules.gamification.engine import SAT_COMBO_KEYS, SAT_OPTIONAL_KEYS
        combos = _combos(monkeypatch, self.TODAY, sorted(SAT_COMBO_KEYS | SAT_OPTIONAL_KEYS))
        assert any(c["type"] == "sat_complete" for c in combos)

    def test_sat_jugos_alone_does_not_fire(self, test_db, monkeypatch):
        combos = _combos(monkeypatch, self.TODAY, ["sat_jugos_bloque"])
        assert not any(c["type"] == "sat_complete" for c in combos)

    def test_missing_one_bloque_not_enough(self, test_db, monkeypatch):
        from modules.gamification.engine import SAT_COMBO_KEYS
        keys = sorted(SAT_COMBO_KEYS)[1:]
        combos = _combos(monkeypatch, self.TODAY, keys)
        assert not any(c["type"] == "sat_complete" for c in combos)

    def test_combo_is_idempotent(self, test_db, monkeypatch):
        """Calling combo check twice does not double-award XP."""
        from modules.gamification import engine
        from modules.gamification.engine import SAT_COMBO_KEYS
        _combos(monkeypatch, self.TODAY, sorted(SAT_COMBO_KEYS))
        engine._check_combo_bonus(self.TODAY, engine._get_today_keys(self.TODAY))  # second call
        import database
        with database.get_db() as db:
            count = db.execute(
                "SELECT COUNT(*) as c FROM xp_ledger "
                "WHERE source='bonus' AND description='Combo: Sábado Completo' AND date=?",
                (self.TODAY,),
            ).fetchone()["c"]
        assert count == 1, f"Sat combo XP must be awarded exactly once, got {count}"

    def test_sat_combo_awards_xp_and_coins(self, test_db, monkeypatch):
        from modules.gamification.engine import SAT_COMBO_KEYS
        _combos(monkeypatch, self.TODAY, sorted(SAT_COMBO_KEYS))
        assert _ledger_sum("xp_ledger", "Combo: Sábado Completo", self.TODAY) == 4
        assert _ledger_sum("coins_ledger", "Combo: Sábado Completo", self.TODAY) == 2


class TestSundayCombo:
    TODAY = "2026-04-26"  # a Sunday

    def test_fires_with_all_nine_bloques(self, test_db, monkeypatch):
        from modules.gamification.engine import SUN_COMBO_KEYS
        combos = _combos(monkeypatch, self.TODAY, sorted(SUN_COMBO_KEYS))
        assert any(c["type"] == "sun_complete" for c in combos), \
            "sun_complete must fire with all 9 sun bloques"

    def test_missing_cierre_blocks_combo(self, test_db, monkeypatch):
        """Every Sunday bloque is required — dropping one must prevent the bonus."""
        from modules.gamification.engine import SUN_COMBO_KEYS
        keys = sorted(SUN_COMBO_KEYS - {"sun_cierre_bloque"})
        combos = _combos(monkeypatch, self.TODAY, keys)
        assert not any(c["type"] == "sun_complete" for c in combos), \
            "sun_complete must NOT fire without sun_cierre_bloque"

    def test_sun_combo_awards_xp_and_coins(self, test_db, monkeypatch):
        from modules.gamification.engine import SUN_COMBO_KEYS
        _combos(monkeypatch, self.TODAY, sorted(SUN_COMBO_KEYS))
        xp = _ledger_sum("xp_ledger", "Combo: Domingo Completo", self.TODAY)
        ec = _ledger_sum("coins_ledger", "Combo: Domingo Completo", self.TODAY)
        assert xp == 5, f"Sun combo should award 5 XP, got {xp}"
        assert ec == 3, f"Sun combo should award 3 EC, got {ec}"


# ══════════════════════════════════════════════════════════════════════════════
# 5. Migration v3.1
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationV31:

    def test_migration_runs_successfully(self, test_db):
        from migrations.migrate_v31 import run_migration
        result = run_migration()
        assert result["status"] == "ok"
        assert result["version"] == "3.1"

    def test_migration_is_idempotent(self, test_db):
        from migrations.migrate_v31 import run_migration
        run_migration()
        result2 = run_migration()
        assert result2["status"] == "already_applied"

    def test_migration_records_bloque_count(self, test_db):
        import database
        from migrations.migrate_v31 import run_migration
        result = run_migration()
        with database.get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM rutina_bloques").fetchone()["c"]
        assert count > 0
        assert result.get("bloque_count") == count

    def test_migration_log_entry_persists(self, test_db):
        import database
        from migrations.migrate_v31 import run_migration
        run_migration()
        with database.get_db() as db:
            row = db.execute(
                "SELECT * FROM migration_log WHERE version='3.1'"
            ).fetchone()
        assert row is not None
        assert "3.1" in row["version"]

    def test_migration_verifies_ec_constant(self):
        from ec_constants import EC_VALUE_MXN
        assert EC_VALUE_MXN == 10

    def test_ataraxia_tables_exist_after_init(self, test_db):
        import database
        with database.get_db() as db:
            tables = {r["name"] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "rutina_bloques" in tables
        assert "rutina_progreso" in tables
        assert "migration_log" in tables

    def test_ataraxia_seeded_blocks_match_combos(self, test_db):
        """rutina_bloques siembra exactamente los bloques que usan los combos:
        Sábado 7 (Jugos opcional) y Domingo 9."""
        import database
        from modules.gamification.engine import SAT_COMBO_KEYS, SAT_OPTIONAL_KEYS, SUN_COMBO_KEYS
        with database.get_db() as db:
            rows = db.execute(
                "SELECT dia, bloque_id, MAX(opcional) AS opc FROM rutina_bloques GROUP BY dia, bloque_id"
            ).fetchall()
        sat = {r["bloque_id"] for r in rows if r["dia"] == "sabado"}
        sun = {r["bloque_id"] for r in rows if r["dia"] == "domingo"}
        optional = {r["bloque_id"] for r in rows if r["opc"]}
        assert sat == set(SAT_COMBO_KEYS | SAT_OPTIONAL_KEYS)
        assert sun == set(SUN_COMBO_KEYS)
        assert optional == set(SAT_OPTIONAL_KEYS)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Reward prices at $10 MXN / EC
# ══════════════════════════════════════════════════════════════════════════════

class TestRewardPrices:

    def test_rewards_are_seeded(self, test_db):
        import database
        with database.get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM rewards").fetchone()["c"]
        assert count >= 6, f"Expected ≥6 rewards, got {count}"

    def test_ropa_nike_costs_50_ec(self, test_db):
        import database
        with database.get_db() as db:
            row = db.execute(
                "SELECT ec_cost FROM rewards WHERE name='Ropa Nike'"
            ).fetchone()
        assert row is not None
        assert row["ec_cost"] == 50, \
            f"Ropa Nike should cost 50 EC ($500 MXN at $10/EC), got {row['ec_cost']}"

    def test_viaje_costs_500_ec(self, test_db):
        import database
        with database.get_db() as db:
            row = db.execute(
                "SELECT ec_cost FROM rewards WHERE name='Viaje'"
            ).fetchone()
        assert row is not None
        assert row["ec_cost"] == 500

    def test_ec_cost_to_mxn_calculation(self):
        from ec_constants import EC_VALUE_MXN
        nike_ec = 50
        assert nike_ec * EC_VALUE_MXN == 500, "50 EC × $10 = $500 MXN for Ropa Nike"

    def test_apple_watch_cost_makes_sense_at_10_mxn(self, test_db):
        """300 EC × $10 = $3,000 MXN — sensible price for Apple Watch."""
        import database
        from ec_constants import EC_VALUE_MXN
        with database.get_db() as db:
            row = db.execute(
                "SELECT ec_cost FROM rewards WHERE name='Apple Watch'"
            ).fetchone()
        assert row is not None
        mxn_value = row["ec_cost"] * EC_VALUE_MXN
        assert mxn_value == 3000, f"Apple Watch should map to $3000 MXN, got ${mxn_value}"
