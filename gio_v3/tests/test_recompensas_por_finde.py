"""
test_recompensas_por_finde.py — tope de canjes por fin de semana (usuario,
2026-10-16: «hagamos que sean dos recompensas por fin de semana» para la
Cápsula Nespresso, que antes era una cada 7 días).
"""
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.recompensas import routes as rw


def _nespresso(db):
    return dict(db.execute("SELECT * FROM rewards WHERE LOWER(name)='cápsula nespresso'").fetchone())


def _canje(db, d, name='Cápsula Nespresso'):
    db.execute("INSERT INTO coins_ledger (amount, source, description, multiplier, date, created_at) "
               "VALUES (-8, 'reward', ?, 1.0, ?, ?)", (f"Recompensa: {name}", d.isoformat(), d.isoformat()))
    db.execute("UPDATE rewards SET last_redeemed=? WHERE LOWER(name)=?", (d.isoformat(), name.lower()))
    db.commit()


def test_migracion_nespresso_dos_por_finde(test_db):
    with database.get_db() as db:
        r = _nespresso(db)
    assert r['max_por_ventana'] == 2 and r['cooldown_days'] == 0 and r['weekend_only'] in (1, 2)


@pytest.mark.parametrize('modo,dias', [
    (2, [date(2026, 10, 16), date(2026, 10, 17), date(2026, 10, 18)]),   # vie–dom
    (1, [date(2026, 10, 17), date(2026, 10, 18)]),                       # sáb–dom
])
def test_dos_por_fin_de_semana_y_se_reabre_el_siguiente(test_db, monkeypatch, modo, dias):
    with database.get_db() as db:
        db.execute("UPDATE rewards SET weekend_only=? WHERE LOWER(name)='cápsula nespresso'", (modo,))
        db.commit()
    hoy = lambda d: monkeypatch.setattr(rw, 'today_date', lambda: d)
    primero, ultimo = dias[0], dias[-1]

    hoy(primero)
    with database.get_db() as db:
        assert rw._can_redeem(_nespresso(db), 10 ** 6, 10)[0]
        _canje(db, primero)
        assert rw._can_redeem(_nespresso(db), 10 ** 6, 10)[0]          # la 2ª sí, el mismo día
        _canje(db, primero)
    hoy(ultimo)
    with database.get_db() as db:
        ok, why = rw._can_redeem(_nespresso(db), 10 ** 6, 10)
    assert not ok and why.startswith('Ya van 2 este fin de semana')
    assert rw._fecha_corta(date(2026, 10, 23 if modo == 2 else 24)) in why

    hoy(date(2026, 10, 21))                                              # miércoles: fuera de ventana
    with database.get_db() as db:
        assert not rw._can_redeem(_nespresso(db), 10 ** 6, 10)[0]
    hoy(date(2026, 10, 24))                                              # sábado siguiente: se reabre
    with database.get_db() as db:
        assert rw._can_redeem(_nespresso(db), 10 ** 6, 10)[0]


def test_canje_del_finde_pasado_no_cuenta(test_db, monkeypatch):
    with database.get_db() as db:
        _canje(db, date(2026, 10, 11))                                   # domingo anterior
        _canje(db, date(2026, 10, 10))
    monkeypatch.setattr(rw, 'today_date', lambda: date(2026, 10, 17))
    with database.get_db() as db:
        assert rw._can_redeem(_nespresso(db), 10 ** 6, 10)[0]


def test_formulario_guarda_el_tope(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
    r = c.post('/recompensas/api/rewards', json={'name': 'Postre', 'ec_cost': 5, 'weekend_only': 1, 'max_por_ventana': 3})
    assert r.status_code == 201 and r.get_json()['max_por_ventana'] == 3
    rid = r.get_json()['id']
    assert c.put(f'/recompensas/api/rewards/{rid}', json={'max_por_ventana': 1}).get_json()['max_por_ventana'] == 1
    html = c.get('/recompensas/').get_data(as_text=True)
    assert '1 por fin de semana' in html and 'f-max' in html
