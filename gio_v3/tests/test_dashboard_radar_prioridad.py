"""
test_dashboard_radar_prioridad.py — «Pendiente» del Inicio ya no se satura:
antes cada fuente traía solo sus 8 fechas más viejas y la lista se cortaba a 8,
así que unos vencidos viejos sacaban lo de hoy. Ahora lo de hoy siempre sale,
lo importante va primero y lo que sobra queda plegado en «Ver N más».
"""
import sys, os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _rem(desc, dias, tema='otros'):
    f = (date.today() + timedelta(days=dias)).isoformat()
    with database.get_db() as db:
        db.execute("INSERT INTO reminders (description, type, target_date, tema, is_active, created_at) "
                   "VALUES (?, 'unico', ?, ?, 1, 'x')", (desc, f, tema))
        db.commit()


def _deadlines():
    from modules.dashboard.routes import _build_deadlines
    return _build_deadlines(date.today())


def test_lo_de_hoy_no_se_pierde_entre_vencidos_viejos(test_db):
    for i in range(12):
        _rem(f'Viejo {i}', -30 - i)
    _rem('Pagar tarjeta HOY', 0, 'finanzas')
    _rem('Llamar HOY', 0)
    dl = _deadlines()
    assert len(dl) == 14                      # nada se descarta
    assert [d['label'] for d in dl[:2]] == ['Pagar tarjeta HOY', 'Llamar HOY']
    assert not any(d['extra'] for d in dl[:8])
    assert sum(d['extra'] for d in dl) == 6


def test_todo_lo_de_hoy_queda_visible_aunque_pase_de_8(test_db):
    for i in range(11):
        _rem(f'Hoy {i}', 0)
    _rem('Próxima semana', 5)
    dl = _deadlines()
    assert all(not d['extra'] for d in dl if d['days'] == 0)
    assert [d['label'] for d in dl if d['extra']] == ['Próxima semana']


def test_importancia_ordena_dentro_del_dia(test_db):
    _rem('Comprar jabón', 0, 'casa')
    with database.get_db() as db:
        db.execute("INSERT INTO gtd_tasks (title, status, priority, created_at, importante, completado, fecha_limite) "
                   "VALUES ('Entregar reporte', 'next', 'normal', 'x', 1, 0, ?)", (date.today().isoformat(),))
        db.commit()
    _rem('Pagar renta', 0, 'finanzas')
    assert [d['label'] for d in _deadlines()] == ['Entregar reporte', 'Pagar renta', 'Comprar jabón']


def test_pagina_pliega_el_excedente(test_db):
    from app import create_app
    for i in range(10):
        _rem(f'Pendiente {i}', 3)
    app = create_app(); app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as s:
            s["app_ok"] = True
        html = c.get('/').get_data(as_text=True)
    assert 'Ver 2 más' in html
    assert 'Pendiente 9' in html
