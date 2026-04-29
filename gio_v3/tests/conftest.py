"""
conftest.py — shared pytest fixtures for Eudaimonia OS test suite.

The test_db fixture:
  - Creates a temp SQLite file per test function
  - Patches database._DB_PATH and database._USE_HYBRID so all get_db() calls
    hit the isolated test file instead of pipeline.db
  - Calls init_db() to set up the full schema + seed data
  - Auto-cleans up after the test
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_eudaimonia.db")
    monkeypatch.setattr(database, "_DB_PATH", db_file)
    monkeypatch.setattr(database, "_USE_HYBRID", False)
    database.init_db()
    yield db_file
