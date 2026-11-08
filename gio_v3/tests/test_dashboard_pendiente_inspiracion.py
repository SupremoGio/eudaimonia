"""
test_dashboard_pendiente_inspiracion.py — Sprint 4 de Inicio v2: la columna
lateral pone Pendiente primero, agrupado en «Hoy y vencidos» / «Esta semana»
con su contador, y la Reflexión y la Palabra comparten una tarjeta con
pestañas. La campanita y el modal m-notif ya no están en Inicio.
"""
import sys, os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from utils import today_date


def _rem(desc, dias):
    f = (today_date() + timedelta(days=dias)).isoformat()
    with database.get_db() as db:
        db.execute("INSERT INTO reminders (description, type, target_date, tema, is_active, created_at) "
                   "VALUES (?, 'unico', ?, 'otros', 1, 'x')", (desc, f))
        db.commit()


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _html(client):
    return client.get('/').get_data(as_text=True)


def test_pendiente_agrupado(client):
    _rem('Pago tarjeta BBVA Oro', 0)
    _rem('Pagar luz', -2)
    _rem('Declaración anual', 1)
    _rem('Verificación vehicular', 5)
    html = _html(client)
    assert 'Hoy y vencidos <span class="num js-dl-sec-ct">' in html
    assert 'Esta semana <span class="num js-dl-sec-ct">' in html
    hoy = html.index('Hoy y vencidos'); semana = html.index('Esta semana')
    assert hoy < html.index('Pago tarjeta BBVA Oro') < semana < html.index('Verificación vehicular')
    assert html.index('Pagar luz') < semana
    assert 'href="/perfil/#recordatorios"' in html and '>Nuevo<' in html.replace('</i>', '>')
    assert 'class="dash-radar-act js-dl-done"' in html and '/perfil/api/reminder/' in html


def test_solo_esta_semana(client):
    _rem('Algo en 3 días', 3)
    html = _html(client)
    assert 'Esta semana' in html and 'Hoy y vencidos' not in html


def test_pendiente_va_antes_que_inspiracion_y_sin_campanita(client):
    _rem('Algo', 0)
    html = _html(client)
    assert html.index('id="dash-radar-t"') < html.index('aria-label="Inspiración"')
    assert 'm-notif' not in html and 'dash-bell' not in html


def test_inspiracion_con_pestanas(client):
    html = _html(client)
    assert 'role="tablist" aria-label="Inspiración"' in html
    assert 'id="insp-tab-quote"' in html and 'aria-controls="insp-word"' in html
    assert 'id="insp-quote" role="tabpanel"' in html and 'id="insp-word" role="tabpanel"' in html
    assert 'id="insp-refresh"' in html
    assert 'quote-refresh' not in html and 'word-refresh' not in html
