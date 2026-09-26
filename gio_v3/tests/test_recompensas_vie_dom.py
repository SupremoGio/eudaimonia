"""
test_recompensas_vie_dom.py — ventana viernes a domingo (weekend_only=2) con
cooldown: Carl's Jr se abre vie/sáb/dom y, tras canjearla, vuelve el siguiente
vie/sáb/dom después de 30 días.
"""
import sys, os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.recompensas import routes as rw


def _r(**kw):
    base = {'ec_cost': 10, 'level_required': 1, 'weekend_only': 2, 'cooldown_days': 30,
            'last_redeemed': None, 'badge_required': '', 'unica': 0}
    base.update(kw)
    return base


def _hoy(monkeypatch, d):
    monkeypatch.setattr(rw, 'today_date', lambda: d)


@pytest.mark.parametrize('d,ok', [
    (date(2026, 9, 24), False),  # jueves
    (date(2026, 9, 25), True),   # viernes
    (date(2026, 9, 26), True),   # sábado
    (date(2026, 9, 27), True),   # domingo
    (date(2026, 9, 28), False),  # lunes
])
def test_ventana_viernes_a_domingo(monkeypatch, d, ok):
    _hoy(monkeypatch, d)
    can, why = rw._can_redeem(_r(), 10 ** 6, 10)
    assert can is ok
    if not ok:
        assert why == 'Solo de viernes a domingo'


def test_fin_de_semana_clasico_sigue_sin_viernes(monkeypatch):
    _hoy(monkeypatch, date(2026, 9, 25))  # viernes
    assert not rw._can_redeem(_r(weekend_only=1), 10 ** 6, 10)[0]


def test_cooldown_30_dias_y_luego_proximo_vie_sab_dom(monkeypatch):
    # Canje el sábado 26 sep → 30 días = lunes 26 oct → próximo viernes 30 oct
    canje = datetime(2026, 9, 26, 14, 0).isoformat()
    _hoy(monkeypatch, date(2026, 10, 25))  # domingo, aún en cooldown
    can, why = rw._can_redeem(_r(last_redeemed=canje), 10 ** 6, 10)
    assert not can and why == 'Disponible el vie 30 oct'
    _hoy(monkeypatch, date(2026, 10, 27))  # martes: cooldown vencido, fuera de ventana
    assert not rw._can_redeem(_r(last_redeemed=canje), 10 ** 6, 10)[0]
    _hoy(monkeypatch, date(2026, 10, 30))  # viernes
    assert rw._can_redeem(_r(last_redeemed=canje), 10 ** 6, 10)[0]


@pytest.mark.parametrize('v,modo', [(True, 1), (False, 0), (0, 0), (1, 1), (2, 2), ('2', 2), (9, 0), (None, 0)])
def test_ventana_modo(v, modo):
    assert rw.ventana_modo(v) == modo


def test_migracion_crea_carls_jr(test_db):
    with database.get_db() as db:
        row = db.execute("SELECT * FROM rewards WHERE LOWER(name) LIKE '%carl%'").fetchone()
    assert row['weekend_only'] == 2 and row['cooldown_days'] == 30 and row['unica'] == 0
