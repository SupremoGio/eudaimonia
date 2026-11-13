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


# Días de pago de prueba. Los tests de Oikonomia, Avisos y Perfil arman sus
# escenarios sobre estos días («el 15 vencen BBVA e Invex»). PAY_DAYS real es
# configuración del usuario (BBVA pasó del 15 al 11 en 2026-11) y no debe
# romper la suite cuando cambia. Todos los consumidores leen
# modules.finanzas.routes.PAY_DAYS al momento de usarlo.
PAY_DAYS_TEST = [
    {'match': 'bbva',  'day': 15, 'label': 'BBVA TDC'},
    {'match': 'invex', 'day': 15, 'label': 'Invex'},
    {'match': 'hsbc',  'day': 30, 'label': 'HSBC'},
]


@pytest.fixture(autouse=True)
def _pay_days_de_prueba(monkeypatch):
    import modules.finanzas.routes as _fr
    monkeypatch.setattr(_fr, 'PAY_DAYS', [dict(p) for p in PAY_DAYS_TEST])
