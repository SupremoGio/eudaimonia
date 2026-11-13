"""
test_recetas.py — Remates · Recetas S1 (encontrar y usar).

- Sin las 3 eu-stat; categorías en eu-seg, «Apta FODMAP» como chip aparte.
- «Para hoy»: lee el plan del día de Nutrición sin sembrarlo (sin plan → no
  aparece); momentos sin receta y sin comer → 3 aptas FODMAP del momento,
  favoritas primero y luego las menos usadas en 14 días. «Usar» = POST
  /nutricion/api/comida con receta_id → guarda receta_id y el momento sale.
- Detalle: franja de macros, porciones (1 → 3 triplica), pasos con casilla y
  «Cocinar» con ← → y Esc (euDialog) + wakeLock.
- Modal: lo opcional en «Avanzado».
"""
import sys, os, json, shutil, subprocess
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'static', 'js', 'recetas.js')


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with database.get_db() as db:
        db.execute("DELETE FROM recetas")          # el banco de Nutrición migrado no cuenta aquí
        db.commit()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _receta(nombre, momento='comida', fodmap='seguro', favorita=0, ingredientes=None, pasos=None, porciones=1):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO recetas (nombre, categoria, descripcion, ingredientes, instrucciones, calorias, proteina,
                            porciones, favorita, fodmap, momento, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                         (nombre, 'Almuerzo', '', json.dumps(ingredientes or []), json.dumps(pasos or []), 400, 30,
                          porciones, favorita, fodmap, momento)).lastrowid
        db.commit()
    return rid


def _sembrar_plan():
    from modules.nutricion.routes import get_or_seed_week, get_week_start
    with database.get_db() as db:
        get_or_seed_week(db, get_week_start().isoformat())


def _para_hoy():
    from modules.recetas.routes import para_hoy
    with database.get_db() as db:
        return para_hoy(db)


def _slot(ph, nombre):
    return next((m for m in ph if m['slot'] == nombre), None)


# ── Pantalla ─────────────────────────────────────────────────────────────────
def test_sin_stats_con_seg_chip_y_avanzado(client):
    html = client.get('/recetas/').get_data(as_text=True)
    assert 'eu-stat' not in html and 'st-total' not in html
    assert 'class="eu-seg rc-seg" role="group" aria-label="Categoría"' in html
    assert 'id="rc-fodmap"' in html and 'rc-chip-fodmap' in html
    assert '<details class="rc-adv" id="rc-avanzado">' in html
    # Siempre visibles: nombre, categoría, FODMAP, momento, ingredientes, pasos; antes de «Avanzado»
    adv = html.index('id="rc-avanzado"')
    for campo in ('id="rm-nombre"', 'id="rm-categoria"', 'id="rm-fodmap"', 'id="rm-momento"', 'id="ing-list"', 'id="step-list"'):
        assert html.index(campo) < adv, campo
    for campo in ('id="rm-cal"', 'id="rm-video"', 'id="rm-prep"', 'id="rm-coccion"'):
        assert html.index(campo) > adv, campo
    assert 'id="rc-cook"' in html


# ── «Para hoy» ───────────────────────────────────────────────────────────────
def test_sin_plan_no_hay_bloque_ni_se_siembra(client):
    _receta('Pollo')
    assert _para_hoy() == []
    assert 'id="rc-today"' not in client.get('/recetas/').get_data(as_text=True)
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) n FROM nutricion_semana").fetchone()['n'] == 0


def test_momentos_sin_receta_con_3_aptas_favoritas_primero(client):
    _sembrar_plan()
    a = _receta('A pollo')
    b = _receta('B pescado', favorita=1)
    _receta('C arroz')
    _receta('D pavo')
    _receta('E evitar', fodmap='evitar')           # no apta
    _receta('F desayuno', momento='desayuno')      # otro momento
    comida = _slot(_para_hoy(), 'Comida')
    assert comida is not None
    ids = [s['id'] for s in comida['sugerencias']]
    assert len(ids) == 3 and ids[0] == b                                  # favorita primero
    nombres = {s['nombre'] for s in comida['sugerencias']}
    assert 'E evitar' not in nombres and 'F desayuno' not in nombres
    html = client.get('/recetas/').get_data(as_text=True)
    assert 'id="rc-today"' in html and 'data-slot="Comida"' in html


def test_menos_usadas_en_14_dias_van_antes(client):
    _sembrar_plan()
    a = _receta('A pollo')
    b = _receta('B pescado')
    from modules.nutricion.routes import get_week_start
    hace = today_date() - timedelta(days=3)
    with database.get_db() as db:     # «A» se usó hace 3 días; «B» nunca
        db.execute("""INSERT INTO nutricion_semana (week_start, day_key, slot, name, custom, receta_id)
                      VALUES (?,?,?,?,1,?)""",
                   ((hace - timedelta(days=hace.weekday())).isoformat(), 'LMXJVSD'[hace.weekday()], 'Cena', 'A pollo', a))
        db.commit()
    comida = _slot(_para_hoy(), 'Comida')
    assert [s['id'] for s in comida['sugerencias']][:2] == [b, a]


def test_usar_asigna_al_plan_y_quita_el_momento(client):
    _sembrar_plan()
    rid = _receta('Pollo al limón', ingredientes=[{'item': 'pollo', 'cantidad': '200', 'unidad': 'g'}])
    assert _slot(_para_hoy(), 'Comida')
    r = client.post('/nutricion/api/comida', json={'receta_id': rid, 'slot': 'Comida'})
    assert r.status_code == 200 and r.get_json()['meal']['name'] == 'Pollo al limón'
    with database.get_db() as db:
        row = db.execute("SELECT receta_id FROM nutricion_semana WHERE name='Pollo al limón'").fetchone()
    assert row['receta_id'] == rid
    assert _slot(_para_hoy(), 'Comida') is None
    assert client.get('/recetas/api/para-hoy').get_json() == _para_hoy()


def test_comida_del_recetario_previa_a_receta_id_cuenta_por_nombre(client):
    _sembrar_plan()
    _receta('Pollo al limón')
    from modules.nutricion.routes import get_week_start
    hoy = today_date()
    with database.get_db() as db:
        db.execute("""INSERT INTO nutricion_semana (week_start, day_key, slot, name, custom)
                      VALUES (?,?,?,?,1)""", (get_week_start().isoformat(), 'LMXJVSD'[hoy.weekday()], 'Comida', 'Pollo al limón'))
        db.commit()
    assert _slot(_para_hoy(), 'Comida') is None


def test_momento_ya_comido_no_aparece(client):
    _sembrar_plan()
    _receta('Pollo')
    from modules.nutricion.routes import get_week_start
    with database.get_db() as db:
        db.execute("UPDATE nutricion_semana SET done=1 WHERE week_start=? AND day_key=? AND slot='Comida'",
                   (get_week_start().isoformat(), 'LMXJVSD'[today_date().weekday()]))
        db.commit()
    assert _slot(_para_hoy(), 'Comida') is None


# ── Detalle y Cocinar (cliente) ──────────────────────────────────────────────
def _js():
    return open(JS, encoding='utf-8').read()


def test_js_franja_porciones_casillas_y_cocinar():
    js = _js()
    assert 'rc-mstrip' in js and "cell('Kcal'" in js
    assert 'js-porc' in js and 'function setPorc' in js and 'porc / (r.porciones || 1)' in js
    assert 'rc-step-box' in js
    assert "'ArrowRight'" in js and "'ArrowLeft'" in js and 'euDialog.open($(\'rc-cook\')' in js
    assert "navigator.wakeLock.request('screen')" in js and "'wakeLock' in navigator" in js
    assert 'stats()' not in js
    assert "fetch('/nutricion/api/comida'" in js and 'function usar' in js


@pytest.mark.skipif(not shutil.which('node'), reason='node no está instalado')
def test_de_1_a_3_porciones_triplica_las_cantidades():
    js = _js()
    a, b = js.index('function parseQty'), js.index('function escalar')
    fin = js.index('\n  }\n', b) + 4
    prog = js[a:fin] + """
    var casos = [['200', 3], ['1.5', 3], ['1/2', 3], ['1 1/2', 3], ['2 tazas', 3], ['al gusto', 3], ['200', 1]];
    console.log(JSON.stringify(casos.map(function (c) { return escalar(c[0], c[1]); })));"""
    out = subprocess.run(['node', '-e', prog], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ['600', '4.5', '1.5', '4.5', '6 tazas', 'al gusto', '200']
