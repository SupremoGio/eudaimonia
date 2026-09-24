"""
test_perfil_recordatorios_grupos.py — Recordatorios agrupados por urgencia,
fecha relativa, frecuencia en palabras y Posponer sin mover el ciclo.
"""
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.perfil import recordatorios as rec

HOY = date(2026, 9, 24)


def _r(i, fecha, type='unico', fu='', fv=1):
    return {'id': i, 'description': f'r{i}', 'type': type, 'freq_unit': fu, 'freq_value': fv,
            'target_date': fecha, 'next_date': fecha, 'created_at': '2026-01-01'}


def test_agrupa_por_urgencia_con_vencidos_primero():
    gs = rec.agrupar([_r(1, '2026-10-05'), _r(2, '2026-06-10'), _r(3, '2026-09-24'),
                      _r(4, '2026-09-29'), _r(5, '2027-01-10'), _r(6, None)], HOY)
    assert [(g['key'], [r['id'] for r in g['items']]) for g in gs] == [
        ('vencidos', [2]), ('hoy', [3]), ('semana', [4]), ('mes', [1]), ('despues', [5]), ('sin_fecha', [6])]
    assert gs[0]['items'][0]['rel'] == 'Hace 3 meses'
    assert gs[1]['items'][0]['rel'] == 'Hoy'
    assert gs[2]['items'][0]['rel'] == 'Mar · en 5 días'
    assert gs[3]['items'][0]['rel'] == '5 oct · en 11 días'


@pytest.mark.parametrize('fu,fv,txt', [('meses', 1, 'Mensual'), ('dias', 7, 'Semanal'), ('semanas', 2, 'Cada 2 semanas'),
                                       ('dias', 1, 'Diario'), ('meses', 3, 'Trimestral'), ('dias', 10, 'Cada 10 días')])
def test_frecuencia_en_palabras(fu, fv, txt):
    assert rec.frecuencia(_r(1, None, 'periodico', fu, fv)) == txt


def test_siguiente_respeta_el_ancla_aunque_se_haya_pospuesto():
    r = _r(1, '2026-09-05', 'periodico', 'meses', 1)
    r['next_date'] = '2026-09-08'           # pospuesto del 5 al 8
    assert rec.siguiente(r, '2026-09-08') == '2026-10-05'
    # pago tardío: sigue el día 5
    assert rec.siguiente(_r(1, '2026-09-05', 'periodico', 'meses', 1), '2026-09-20') == '2026-10-05'
    # fin de mes: 31 ene → 28 feb → 31 mar, sin arrastrar el 28
    r = _r(1, '2026-01-31', 'periodico', 'meses', 1); r['next_date'] = '2026-02-28'
    assert rec.siguiente(r, '2026-02-28') == '2026-03-31'


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
        sess['fin_ok'] = True
    return c


def _add(fecha, type='unico', fu='', fv=1):
    with database.get_db() as db:
        cur = db.execute("INSERT INTO reminders (description, type, freq_unit, freq_value, target_date, next_date, is_active, created_at)"
                         " VALUES ('x',?,?,?,?,?,1,'2026-01-01')", (type, fu, fv, fecha, fecha))
        db.commit()
        return cur.lastrowid


def _row(rid):
    with database.get_db() as db:
        return dict(db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone())


def test_posponer_periodico_no_toca_el_ancla(client):
    rid = _add('2026-06-05', 'periodico', 'meses', 1)
    assert client.post(f'/perfil/api/reminder/{rid}/snooze', json={'fecha': '2026-10-09'}).get_json()['ok']
    r = _row(rid)
    assert r['next_date'] == '2026-10-09' and r['target_date'] == '2026-06-05'


def test_posponer_unico_mueve_su_fecha(client):
    rid = _add('2026-06-10')
    j = client.post(f'/perfil/api/reminder/{rid}/snooze', json={'dias': 7}).get_json()
    r = _row(rid)
    assert r['target_date'] == r['next_date'] == j['fecha']


def test_la_pagina_muestra_grupos(client):
    _add('2020-01-01')
    html = client.get('/perfil/').get_data(as_text=True)
    assert 'pf-remg--vencidos' in html and 'Posponer' in html
