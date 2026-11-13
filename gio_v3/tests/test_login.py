"""
test_login.py — Remates · Login S1.

- Alta: mínimo 8 caracteres en el endpoint (7 se rechaza) y en la plantilla
  (contador «0 de 8», data-min para login.js).
- Bloqueo: después de 5 intentos fallidos en un minuto, /login responde 429
  con retry_after (segundos) y Retry-After, que login.js usa para la cuenta
  regresiva con el botón deshabilitado.
- Una sola cita (sin au-q) y mostrar/ocultar con aria-pressed.
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from werkzeug.security import generate_password_hash
import database
from extensions import limiter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    limiter.reset()                       # almacenamiento en memoria compartido entre tests
    with app.test_client() as c:
        yield c
    limiter.reset()


def _con_pass(pw='correcta-123'):
    with database.get_db() as db:
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_pass_hash', ?)",
                   (generate_password_hash(pw),))
        db.commit()


# ── Mínimo de 8 en el alta ──────────────────────────────────────────────────
def test_alta_rechaza_7_caracteres(client):
    r = client.post('/login/setup', json={'password': '1234567'})
    assert r.status_code == 400
    assert r.get_json() == {'ok': False, 'error': 'Mínimo 8 caracteres'}
    with database.get_db() as db:
        assert db.execute("SELECT 1 FROM app_settings WHERE key='app_pass_hash'").fetchone() is None
    with client.session_transaction() as s:
        assert not s.get('app_ok')


def test_alta_acepta_8_caracteres(client):
    r = client.post('/login/setup', json={'password': '12345678'})
    assert r.status_code == 200 and r.get_json()['ok']
    with client.session_transaction() as s:
        assert s.get('app_ok')


def test_pantalla_de_alta_muestra_contador_y_minimo(client):
    html = client.get('/login').get_data(as_text=True)
    assert 'data-mode="setup"' in html
    assert re.search(r'id="au-pw-n"[^>]*data-min="8"', html)
    assert '0 de 8' in html and 'mínimo 8 caracteres' in html
    assert 'minlength="8"' in html
    assert 'id="au-err2"' in html          # error de coincidencia en el segundo campo


def test_login_js_usa_el_minimo_de_la_plantilla():
    js = open(os.path.join(BASE, 'static', 'js', 'login.js'), encoding='utf-8').read()
    assert 'length < 4' not in js
    assert 'p1.length < MIN' in js and 'dataset.min' in js


# ── Bloqueo por intentos ────────────────────────────────────────────────────
def _hasta_bloqueo(client):
    """Falla hasta el 429. La ventana del límite es fija por minuto: si los
    intentos cruzan el cambio de minuto el conteo se reinicia una vez, así
    que se permiten hasta 11 intentos (nunca cruza dos veces en < 1 min)."""
    fallos = 0
    for _ in range(11):
        r = client.post('/login', json={'password': 'mala'})
        if r.status_code == 429:
            return fallos, r
        assert r.status_code == 401
        fallos += 1
    raise AssertionError('nunca llegó el 429')


def test_sexto_intento_fallido_responde_bloqueo_con_espera(client):
    _con_pass()
    fallos, r = _hasta_bloqueo(client)
    assert fallos >= 5                     # el 429 nunca llega antes de 5 fallos
    d = r.get_json()
    assert d['ok'] is False
    assert isinstance(d['retry_after'], int) and 1 <= d['retry_after'] <= 60
    assert r.headers['Retry-After'] == str(d['retry_after'])
    assert f"Espera {d['retry_after']} s" in d['error']


def test_bloqueado_ni_la_correcta_entra(client):
    _con_pass('correcta-123')
    _hasta_bloqueo(client)
    r = client.post('/login', json={'password': 'correcta-123'})
    assert r.status_code == 429
    with client.session_transaction() as s:
        assert not s.get('app_ok')


def test_login_js_hace_cuenta_regresiva_con_el_429():
    js = open(os.path.join(BASE, 'static', 'js', 'login.js'), encoding='utf-8').read()
    assert 'r.status === 429' in js and 'retry_after' in js and 'Retry-After' in js
    assert "btn.disabled = true" in js and "'Espera ' + s + ' s'" in js


# ── Una sola cita y mostrar/ocultar ─────────────────────────────────────────
def test_una_sola_cita_y_boton_de_mostrar(client):
    _con_pass()
    html = client.get('/login').get_data(as_text=True)
    assert 'au-q"' not in html and 'Séneca' not in html
    assert html.count('Meditaciones V.16') == 2       # bloque móvil + hero (uno visible por tamaño)
    assert 'au-mob-q' in html and 'au-hero-q' in html
    m = re.search(r'<button[^>]*data-eye="au-pw"[^>]*>', html)
    assert m and 'aria-pressed="false"' in m.group(0) and 'aria-label="Mostrar contraseña"' in m.group(0)
    assert 'aria-busy' not in html                     # solo mientras espera la respuesta
