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


# ── Fase 2: temas ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('desc,tema', [('Pagar Credito HSBC', 'finanzas'), ('EDO CUENTA BBVA DEBITO', 'finanzas'),
                                       ('Corte Invex', 'finanzas'), ('Candlelight MJ', 'eventos'),
                                       ('JABON POTASICO Y NEEM', 'casa'), ('Tomar vitaminas', 'casa'),
                                       ('Llamar a mamá', 'otros')])
def test_tema_por_palabras_clave(desc, tema):
    assert rec.tema_auto(desc) == tema


def test_alta_asigna_tema_automatico_o_el_elegido(client):
    client.post('/perfil/api/reminder/add', json={'description': 'Pagar Renta', 'type': 'unico'})
    client.post('/perfil/api/reminder/add', json={'description': 'Pagar Renta', 'type': 'unico', 'tema': 'casa'})
    with database.get_db() as db:
        assert [r['tema'] for r in db.execute("SELECT tema FROM reminders ORDER BY id")] == ['finanzas', 'casa']


def test_migracion_no_pisa_tema_existente(test_db):
    with database.get_db() as db:
        db.execute("INSERT INTO reminders (description, type, is_active, created_at, tema) VALUES ('Pagar luz','unico',1,'x','eventos')")
        db.execute("INSERT INTO reminders (description, type, is_active, created_at, tema) VALUES ('Corte Invex','unico',1,'x','')")
        db.execute("DELETE FROM migration_log WHERE version='recordatorios_tema_2026_09'")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        assert [r['tema'] for r in db.execute("SELECT tema FROM reminders ORDER BY id")] == ['eventos', 'finanzas']


def test_pagina_muestra_chips_por_tema(client):
    _add('2026-10-05'); _add('2026-10-06')
    with database.get_db() as db:
        db.execute("UPDATE reminders SET tema='finanzas' WHERE id=1"); db.execute("UPDATE reminders SET tema='eventos' WHERE id=2")
        db.commit()
    html = client.get('/perfil/').get_data(as_text=True)
    assert 'js-rem-tema' in html and 'data-tema="finanzas"' in html and 'data-tema="eventos"' in html


def test_pendiente_separa_vencidos_de_proximos(client):
    # Antes lo hacía la campanita de Inicio; desde Inicio v2 (Sprint 4) es la
    # tarjeta «Pendiente»: «Hoy y vencidos» / «Esta semana».
    from utils import today_str
    hoy = date.fromisoformat(today_str())
    _add('2020-01-01')
    _add(hoy.isoformat())
    from datetime import timedelta
    _add((hoy + timedelta(days=3)).isoformat())
    html = client.get('/').get_data(as_text=True)
    assert 'Hoy y vencidos <span class="num js-dl-sec-ct">2</span>' in html
    assert 'Esta semana <span class="num js-dl-sec-ct">1</span>' in html


# ── «Contar desde que lo marco» (Saldo cel: 25 días desde la última recarga) ──

def test_siguiente_desde_que_se_marca():
    r = _r(1, '2026-10-10', 'periodico', 'dias', 25)
    r['cuenta_desde'] = 'hecho'
    assert rec.siguiente(r, '2026-11-09') == '2026-12-04'     # vencido: cuenta desde hoy
    r['next_date'] = '2026-11-20'
    assert rec.siguiente(r, '2026-11-09') == '2026-12-04'     # antes de tiempo: también desde hoy
    assert rec.frecuencia(r) == 'Cada 25 días desde que lo marcas'
    r['cuenta_desde'] = 'ciclo'                               # el modo de siempre no cambia
    assert rec.siguiente(r, '2026-11-09') == '2026-11-29'


def test_marcar_hecho_reinicia_25_dias(client):
    from utils import today_str
    from datetime import date as _d, timedelta
    j = client.post('/perfil/api/reminder/add', json={'description': 'Recargar algo', 'type': 'periodico', 'freq_unit': 'dias',
                                                       'freq_value': 25, 'target_date': '2026-10-01', 'cuenta_desde': 'hecho'}).get_json()
    assert client.post(f"/perfil/api/reminder/{j['id']}/done").get_json()['ok']
    with database.get_db() as db:
        row = db.execute('SELECT next_date, cuenta_desde FROM reminders WHERE id=?', (j['id'],)).fetchone()
    assert row['cuenta_desde'] == 'hecho'
    assert row['next_date'] == (_d.fromisoformat(today_str()) + timedelta(days=25)).isoformat()
    # editar sin la opción vuelve al ciclo fijo
    client.post(f"/perfil/api/reminder/{j['id']}/edit", json={'description': 'Recargar algo', 'type': 'periodico', 'freq_unit': 'dias',
                                                               'freq_value': 25, 'target_date': '2026-10-01'})
    with database.get_db() as db:
        assert db.execute('SELECT cuenta_desde FROM reminders WHERE id=?', (j['id'],)).fetchone()[0] == 'ciclo'


def test_migracion_saldo_cel(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='recordatorio_saldo_cel_25d'")
        db.execute("INSERT INTO reminders (description, type, target_date, next_date, is_active, created_at) "
                   "VALUES ('Saldo cel', 'unico', '2026-11-01', '2026-11-01', 1, 'x')")
        db.execute("INSERT INTO reminders (description, type, target_date, next_date, is_active, created_at) "
                   "VALUES ('Pagar Renta', 'periodico', '2026-11-01', '2026-11-01', 1, 'x')")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        s = db.execute("SELECT * FROM reminders WHERE description='Saldo cel'").fetchone()
        r = db.execute("SELECT * FROM reminders WHERE description='Pagar Renta'").fetchone()
    assert (s['type'], s['freq_unit'], s['freq_value'], s['cuenta_desde']) == ('periodico', 'dias', 25, 'hecho')
    assert s['next_date'] == '2026-11-01'                     # sigue vencido hasta que lo marques
    assert r['cuenta_desde'] == 'ciclo'


def test_formulario_trae_contar_desde(client):
    html = client.get('/perfil/').get_data(as_text=True)
    assert 'id="remDesde"' in html and 'El día en que lo marco' in html
