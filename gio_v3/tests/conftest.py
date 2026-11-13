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
    monkeypatch.setattr(database, "SEMBRAR_DATOS_USUARIO", False)   # sin las plantas reales del usuario
    database.init_db()
    # Centro de avisos: las anclas de Acta pasan a «Hoy» después de las 20:00
    # de la hora REAL; sin esto, los tests que cuentan pendientes de hoy
    # (Inicio, campana) cambian según la hora a la que corre la suite.
    import modules.actividades.routes as _act
    monkeypatch.setattr(_act, "ANCLAS_AVISO_HORA", 99)
    import modules.ataraxia.routes as _ata          # idem: revisión del domingo 17:00
    monkeypatch.setattr(_ata, "REVISION_AVISO_HORA", 99)
    yield db_file
