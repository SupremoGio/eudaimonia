"""
test_acta_dia_de_partido.py — los miércoles el usuario suele jugar fútbol en
vez de ir al gym: si hay partido agendado ese día, Ejercicio Gym y GymBook no
se piden y el partido es el ancla (mismo pilar y puntos que el gym).
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import modules.actividades.activity_defs as adefs
import modules.gamification.engine as engine

MIERCOLES, JUEVES = '2026-09-30', '2026-10-01'


def _hoy(monkeypatch, fecha):
    d = datetime.date.fromisoformat(fecha)
    monkeypatch.setattr(adefs, 'today_date', lambda: d)
    monkeypatch.setattr(adefs, 'today_str', lambda: fecha)


def _partido(fecha, hora='21:00', rival='Dany', estado='programado'):
    with database.get_db() as db:
        db.execute("INSERT INTO futbol_partidos (fecha, hora, rival, estado, created_at) VALUES (?,?,?,?,?)",
                   (fecha, hora, rival, estado, fecha))
        db.commit()


def _keys(grouped):
    return {it['key']: it for s in ('morning', 'afternoon', 'night', 'any') for it in grouped[s]}


def test_miercoles_con_partido_quita_gym_y_el_partido_es_ancla(test_db, monkeypatch):
    _hoy(monkeypatch, MIERCOLES)
    _partido(MIERCOLES)
    acts = _keys(adefs.get_active_grouped())
    assert 'gym' not in acts and 'gymbook' not in acts
    p = acts['partido_futbol']
    assert p['effective_type'] == 'ancla' and p['pillar'] == 'hege'
    assert p['label'] == 'Partido de fútbol · vs Dany · 21:00'
    assert p['session'] == 'night'                      # 21:00 → noche
    assert p in adefs.get_active_grouped()['night']


def test_miercoles_sin_partido_queda_el_gym(test_db, monkeypatch):
    _hoy(monkeypatch, MIERCOLES)
    acts = _keys(adefs.get_active_grouped())
    assert 'gym' in acts and 'gymbook' in acts and 'partido_futbol' not in acts


def test_partido_otro_dia_no_cambia_nada(test_db, monkeypatch):
    _hoy(monkeypatch, JUEVES)
    _partido(JUEVES)
    acts = _keys(adefs.get_active_grouped())
    assert 'gym' in acts and 'partido_futbol' not in acts


def test_clasificacion_cuenta_el_partido_como_ancla_y_no_pide_gym(test_db):
    _partido(MIERCOLES, hora='18:30')
    with database.get_db() as db:
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('partido_futbol', ?, 4)", (MIERCOLES,))
        db.commit()
    c = engine.get_daily_classification(MIERCOLES)
    anchors = {d['key'] for d in adefs.ajustar_por_partido(
        [v for v in adefs.get_active_flat().values() if adefs.eligible_today(v, 'wed', datetime.date.fromisoformat(MIERCOLES))],
        datetime.date.fromisoformat(MIERCOLES)) if d['effective_type'] == 'ancla'}
    assert 'partido_futbol' in anchors and 'gym' not in anchors
    assert c['rank'] != 'carbon'                         # el partido cuenta como ancla hecha → al menos Hierro
