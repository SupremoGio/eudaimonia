"""
test_gamification_v31.py — Regression suite for Eudaimonia OS v3.1.

Covers:
  1. EC constants — EC_VALUE_MXN=10, GAMIFICATION_VERSION='3.1'
  2. ACTIVITIES — weekend keys exist, sat_jugos is optional
  3. Saturday combo — fires on sat_bloque1+2+3, sat_jugos NOT required
  4. Sunday combo   — fires only when all 5 sun keys present (incl. sun_jugos)
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
# ══════════════════════════════════════════════════════════════════════════════

class TestActivitiesWeekendKeys:
    SAT_REQUIRED = {"sat_bloque1", "sat_bloque2", "sat_bloque3"}
    SUN_REQUIRED = {"sun_reflexion", "sun_diseno", "sun_comidas", "sun_jugos", "sun_planchar"}

    def test_sat_combo_keys_exist(self):
        from data import ACTIVITIES
        missing = self.SAT_REQUIRED - set(ACTIVITIES)
        assert not missing, f"Missing sat combo keys in ACTIVITIES: {missing}"

    def test_sun_combo_keys_exist(self):
        from data import ACTIVITIES
        missing = self.SUN_REQUIRED - set(ACTIVITIES)
        assert not missing, f"Missing sun combo keys in ACTIVITIES: {missing}"

    def test_sat_jugos_exists_and_is_optional(self):
        from data import ACTIVITIES
        assert "sat_jugos" in ACTIVITIES
        assert ACTIVITIES["sat_jugos"].get("optional") is True, \
            "sat_jugos must have optional=True — it must not gate the sat combo"

    def test_sat_jugos_pts_and_ec(self):
        from data import ACTIVITIES
        act = ACTIVITIES["sat_jugos"]
        assert act["pts"] == 2
        assert act["ec"] == 1

    def test_sat_bloque_tiers_are_progreso_or_alto(self):
        from data import ACTIVITIES
        for key in self.SAT_REQUIRED:
            tier = ACTIVITIES[key]["tier"]
            assert tier in ("progreso", "alto"), f"{key} tier={tier!r}"

    def test_sun_keys_have_weekend_marker(self):
        from data import ACTIVITIES
        for key in self.SUN_REQUIRED:
            assert ACTIVITIES[key].get("weekend") == "sun", \
                f"{key} missing weekend='sun'"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Saturday combo
# ══════════════════════════════════════════════════════════════════════════════

class TestSaturdayCombo:
    TODAY = "2026-04-25"  # a Saturday

    def _insert_keys(self, db_mod, keys, today):
        import database
        with database.get_db() as db:
            for key in keys:
                db.execute(
                    "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                    (key, today, 4),
                )
            db.commit()

    def test_fires_with_three_required_bloques(self, test_db, monkeypatch):
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 25))

        self._insert_keys(database, ["sat_bloque1", "sat_bloque2", "sat_bloque3"], self.TODAY)

        keys = engine._get_today_keys(self.TODAY)
        combos = engine._check_combo_bonus(self.TODAY, keys)
        assert any(c["type"] == "sat_complete" for c in combos), \
            "sat_complete combo should fire with sat_bloque1+2+3"

    def test_fires_even_with_sat_jugos(self, test_db, monkeypatch):
        """Adding sat_jugos on top of the 3 required bloques must not break the combo."""
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 25))

        self._insert_keys(database,
                          ["sat_bloque1", "sat_bloque2", "sat_bloque3", "sat_jugos"],
                          self.TODAY)

        keys = engine._get_today_keys(self.TODAY)
        combos = engine._check_combo_bonus(self.TODAY, keys)
        assert any(c["type"] == "sat_complete" for c in combos)

    def test_sat_jugos_alone_does_not_fire(self, test_db, monkeypatch):
        """sat_jugos alone — not enough, no sat combo."""
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 25))

        self._insert_keys(database, ["sat_jugos"], self.TODAY)

        keys = engine._get_today_keys(self.TODAY)
        combos = engine._check_combo_bonus(self.TODAY, keys)
        assert not any(c["type"] == "sat_complete" for c in combos)

    def test_two_bloques_not_enough(self, test_db, monkeypatch):
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 25))

        self._insert_keys(database, ["sat_bloque1", "sat_bloque2"], self.TODAY)

        keys = engine._get_today_keys(self.TODAY)
        combos = engine._check_combo_bonus(self.TODAY, keys)
        assert not any(c["type"] == "sat_complete" for c in combos)

    def test_combo_is_idempotent(self, test_db, monkeypatch):
        """Calling combo check twice does not double-award XP."""
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 25))

        self._insert_keys(database, ["sat_bloque1", "sat_bloque2", "sat_bloque3"], self.TODAY)

        keys = engine._get_today_keys(self.TODAY)
        engine._check_combo_bonus(self.TODAY, keys)
        engine._check_combo_bonus(self.TODAY, keys)  # second call

        with database.get_db() as db:
            count = db.execute(
                "SELECT COUNT(*) as c FROM xp_ledger "
                "WHERE source='bonus' AND description='Combo: Sábado Completo' AND date=?",
                (self.TODAY,),
            ).fetchone()["c"]
        assert count == 1, f"Sat combo XP must be awarded exactly once, got {count}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Sunday combo
# ══════════════════════════════════════════════════════════════════════════════

class TestSundayCombo:
    TODAY = "2026-04-26"  # a Sunday
    SUN_KEYS = ["sun_reflexion", "sun_diseno", "sun_comidas", "sun_jugos", "sun_planchar"]

    def _insert_keys(self, keys, today):
        import database
        with database.get_db() as db:
            for key in keys:
                db.execute(
                    "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                    (key, today, 4),
                )
            db.commit()

    def test_fires_with_all_five_keys(self, test_db, monkeypatch):
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 26))

        self._insert_keys(self.SUN_KEYS, self.TODAY)
        keys = engine._get_today_keys(self.TODAY)
        combos = engine._check_combo_bonus(self.TODAY, keys)
        assert any(c["type"] == "sun_complete" for c in combos), \
            "sun_complete must fire with all 5 sun keys"

    def test_missing_sun_jugos_blocks_combo(self, test_db, monkeypatch):
        """sun_jugos IS required for sun combo — removing it must prevent the bonus."""
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 26))

        keys_without_jugos = [k for k in self.SUN_KEYS if k != "sun_jugos"]
        self._insert_keys(keys_without_jugos, self.TODAY)

        keys = engine._get_today_keys(self.TODAY)
        combos = engine._check_combo_bonus(self.TODAY, keys)
        assert not any(c["type"] == "sun_complete" for c in combos), \
            "sun_complete must NOT fire without sun_jugos"

    def test_sun_combo_awards_xp_and_coins(self, test_db, monkeypatch):
        import database
        from modules.gamification import engine
        monkeypatch.setattr(engine, "today_str", lambda: self.TODAY)
        monkeypatch.setattr(engine, "today_date", lambda: __import__("datetime").date(2026, 4, 26))

        self._insert_keys(self.SUN_KEYS, self.TODAY)
        keys = engine._get_today_keys(self.TODAY)
        engine._check_combo_bonus(self.TODAY, keys)

        with database.get_db() as db:
            xp = db.execute(
                "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger "
                "WHERE source='bonus' AND description='Combo: Domingo Completo' AND date=?",
                (self.TODAY,),
            ).fetchone()["s"]
            ec = db.execute(
                "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger "
                "WHERE source='bonus' AND description='Combo: Domingo Completo' AND date=?",
                (self.TODAY,),
            ).fetchone()["s"]

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
        from migrations.migrate_v31 import run_migration
        result = run_migration()
        assert result.get("bloque_count", 0) == 18

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

    def test_ataraxia_seeded_18_tasks(self, test_db):
        import database
        with database.get_db() as db:
            count = db.execute(
                "SELECT COUNT(*) as c FROM rutina_bloques"
            ).fetchone()["c"]
        assert count == 18, f"Expected 18 seeded tasks, got {count}"


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
