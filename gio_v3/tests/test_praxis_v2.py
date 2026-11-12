"""
test_praxis_v2.py — handoff Praxis v2 (/gtd/).

Sprint 1: captura en una barra, sin el párrafo fijo, sin «Puntos y nivel»
y sin las 4 cifras (los conteos viven en cada sección).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _src(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


def _px(html):
    return html.split('<div class="px" id="px">', 1)[1].split('id="px-data"', 1)[0]


def test_captura_en_una_barra_y_sin_cifras(client):
    html = client.get('/gtd/').get_data(as_text=True)
    px = _px(html)
    cap = px.split('<form class="px-capture"', 1)[1].split('</form>', 1)[0]
    assert cap.count('class="px-cap-row"') == 1
    assert 'class="eu-seg px-cap-tipo"' in cap
    for tipo in ('tarea', 'idea', 'mantenimiento'):
        assert f'data-tipo="{tipo}"' in cap
    assert 'Capturar</button>' in cap
    for fuera in ('px-lead', 'Puntos y nivel', 'px-stats', 'id="st-'):
        assert fuera not in px, fuera
    assert '0 para hoy</div>' in html and '<h1 class="t-page">Praxis</h1>' in html   # antetítulo vivo (Navegación)


def test_js_y_css_sin_st():
    js, css = _src('static/js/praxis.js'), _src('static/css/praxis.css')
    assert 'st-inbox' not in js and 'st-hoy' not in js and 'st-done' not in js
    assert '#st-' not in css


def test_captura_tarea_va_al_inbox_e_idea_al_banco(client):
    t = client.post('/gtd/api/task', json={'texto': 'Renovar pasaporte', 'tipo': 'tarea'}).get_json()
    i = client.post('/gtd/api/task', json={'texto': 'Curso de SQL', 'tipo': 'idea'}).get_json()
    with database.get_db() as db:
        rows = {r['id']: dict(r) for r in db.execute('SELECT id, cuadrante, tipo FROM gtd_tasks')}
    assert rows[t['id']]['cuadrante'] is None
    assert rows[i['id']]['cuadrante'] == 'ideas'
    html = client.get('/gtd/').get_data(as_text=True)
    assert 'Renovar pasaporte' in html          # el Inbox se pinta en el cliente desde los datos de la página


# ── Sprint 2: Inbox de un clic y fechas relativas ────────────────────────────

import json, shutil, subprocess

DESTINOS = {'hoy': (1, 1), 'semana': (1, 0), 'delegar': (0, 1), 'ideas': (0, 0)}


def _node(expr):
    node = shutil.which('node')
    if not node:
        pytest.skip('node no está instalado')
    code = ("const D = require(%s); console.log(JSON.stringify(%s));"
            % (json.dumps(os.path.join(BASE, 'static/js/praxis-due.js')), expr))
    return json.loads(subprocess.run([node, '-e', code], capture_output=True, text=True, check=True).stdout)


@pytest.mark.parametrize('fecha,txt,tone', [
    ('2026-11-04', 'Vencida 1 d', 'danger'),     # fecha pasada
    ('2026-11-05', 'Hoy', 'danger'),             # hoy (jueves)
    ('2026-11-06', 'Mañana', 'warning'),
    ('2026-11-08', 'dom 8', 'warning'),          # 3 días
    ('2026-11-10', 'mar 10', ''),                # 5 días: < 7, sin tono
    ('2026-11-15', '15 nov', ''),                # 10 días
])
def test_reldue(fecha, txt, tone):
    r = _node(f"D.relDue('{fecha}', '2026-11-05')")
    assert r['txt'] == txt and r['tone'] == tone


def test_reldue_sin_fecha_y_orden():
    assert _node("D.relDue(null, '2026-11-05')") is None
    orden = _node("[{id:1,fecha_limite:null},{id:2,fecha_limite:'2026-11-09'},{id:3,fecha_limite:'2026-11-04'},{id:4,fecha_limite:null}]"
                  ".sort(D.byDue).map(t => t.id)")
    assert orden == [3, 2, 1, 4]


def test_js_inbox_de_un_clic_sin_fechas_iso():
    js = _src('static/js/praxis.js')
    assert 'segHTML' not in js and 'data-cls' not in js
    assert "esc(t.fecha_limite) + '</span>'" not in js           # la fecha cruda ya no se pinta
    for q, (imp, urg) in DESTINOS.items():
        assert f"q: '{q}'" in js and f"imp: {imp}, urg: {urg}" in js
    assert 'Hoy = urgente e importante · Semana = importante · Delegar = urgente · Idea = ninguno' in js


@pytest.mark.parametrize('q', list(DESTINOS))
def test_cada_destino_clasifica_en_su_cuadrante(client, q):
    tid = client.post('/gtd/api/task', json={'texto': 'X', 'tipo': 'tarea'}).get_json()['id']
    imp, urg = DESTINOS[q]
    r = client.post(f'/gtd/api/task/{tid}/classify', json={'importante': bool(imp), 'urgente': bool(urg)}).get_json()
    assert r['cuadrante'] == q


def test_praxis_carga_praxis_due(client):
    html = client.get('/gtd/').get_data(as_text=True)
    assert html.index('js/praxis-due.js') < html.index('js/praxis.js')


# ── Sprint 3: jerarquía de la matriz + bono visible ──────────────────────────

def test_js_estructura_hoy_semana_y_columna_derecha():
    js = _src('static/js/praxis.js')
    # columna principal y derecha, en el orden que pide el móvil
    assert js.index("'<div class=\"px-main\">'") < js.index('<aside class="px-side"')
    for s in ('px-sec--inbox', 'px-sec--hoy', 'px-sec--semana'):
        assert s in js
    assert js.index("px-sec--inbox") < js.index("px-sec--hoy") < js.index("px-sec--semana")
    assert js.index("side('delegar'") < js.index("side('ideas'") < js.index('<span>Completadas hoy</span>')
    assert 'if (g.inbox.length)' in js                         # Inbox solo si tiene tareas
    # bono de 3 visible antes de ganarlo
    assert "'/3 hechas</span>" in js and "'bono +5 XP'" in js and "'+5 XP ganados'" in js
    # «→ Hoy» = classify(importante=1, urgente=1)
    assert 'js-promote' in js and 'classify(id, true, true)' in js
    assert 'Historial completo en Logros →' in js and 'href="/logros?tab=historial&fuente=Praxis"' in js


def test_css_grid_y_columna_derecha():
    css = _src('static/css/praxis.css')
    assert 'grid-template-columns:minmax(0,1fr) 340px' in css
    assert '.px-side-sec{' in css and 'background:var(--bg-sunken)' in css
    assert '.px-bonus-pips i{flex:1;height:4px' in css
    assert '.px-bonus.is-won .px-bonus-t{color:var(--success-fg)}' in css


def test_promover_a_hoy_y_bono_con_el_conteo_de_complete(client):
    ids = [client.post('/gtd/api/task', json={'texto': f'T{i}', 'tipo': 'tarea'}).get_json()['id'] for i in range(3)]
    client.post(f'/gtd/api/task/{ids[0]}/classify', json={'importante': True, 'urgente': False})
    r = client.post(f'/gtd/api/task/{ids[0]}/classify', json={'importante': True, 'urgente': True}).get_json()
    assert r['cuadrante'] == 'hoy'
    html = client.get('/gtd/').get_data(as_text=True)
    assert 'data-done-today="0"' in html
    for n, tid in enumerate(ids, 1):
        r = client.post(f'/gtd/api/task/{tid}/complete').get_json()
        assert r['stats']['done_today'] == n
    assert 'data-done-today="3"' in client.get('/gtd/').get_data(as_text=True)


# ── Sprint 4: una sola moneda, XP (D1) ───────────────────────────────────────

def _ledger(where):
    with database.get_db() as db:
        return db.execute(f"SELECT COALESCE(SUM(amount),0) s, COUNT(*) c FROM xp_ledger WHERE {where}").fetchone()


def _nueva(client, texto='T'):
    return client.post('/gtd/api/task', json={'texto': texto, 'tipo': 'tarea'}).get_json()['id']


def test_completar_da_solo_xp_y_no_puntos(client):
    r = client.post(f'/gtd/api/task/{_nueva(client)}/complete').get_json()
    assert r['ok'] and r['xp'] > 0 and r['pts'] == 0 and r['bonus'] == 0 and r['bonus_xp'] == 0
    with database.get_db() as db:
        assert db.execute('SELECT COUNT(*) FROM gtd_points_log').fetchone()[0] == 0
    assert _ledger("source='task'")['s'] == r['xp']


def test_bono_de_tres_tareas_una_sola_vez(client):
    ids = [_nueva(client, f'T{i}') for i in range(5)]
    rs = [client.post(f'/gtd/api/task/{t}/complete').get_json() for t in ids[:3]]
    assert [r['bonus_xp'] for r in rs] == [0, 0, 5]
    assert 'daily_bonus_gam' in rs[2]['gam']
    # una 4.ª no repite el bono
    assert client.post(f'/gtd/api/task/{ids[3]}/complete').get_json()['bonus_xp'] == 0
    # ni borrar una completada y cerrar otra (el conteo vuelve a 3)
    client.delete(f'/gtd/api/task/{ids[0]}')
    client.delete(f'/gtd/api/task/{ids[1]}')
    assert client.post(f'/gtd/api/task/{ids[4]}/complete').get_json()['bonus_xp'] == 0
    assert _ledger("source='bonus' AND description LIKE 'Bonus diario GTD%'")['c'] == 1


def test_points_redirige_a_logros_y_sale_del_menu(client):
    r = client.get('/gtd/points')
    assert r.status_code == 302 and r.headers['Location'].endswith('/logros?tab=historial&fuente=Praxis')
    from modules.nav import NAV
    urls = [c['url'] for g in NAV for it in g['items'] for c in it.get('children', [])]
    assert '/gtd/points' not in urls
    js = _src('static/js/praxis.js')
    assert "' pts'" not in js and 'r.pts' not in js


# ── Sprint 5: Pipeline de Acta = Ideas de Praxis (D2) ────────────────────────

def _ideas():
    with database.get_db() as db:
        return [r['title'] for r in db.execute(
            "SELECT title FROM gtd_tasks WHERE cuadrante='ideas' AND completado=0 ORDER BY id")]


def test_migracion_pipeline_a_ideas_idempotente(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='praxis_v2_pipeline_a_ideas'")
        db.execute("INSERT INTO gtd_tasks (title,tipo,completado,status,importante,urgente,cuadrante,points,created_at,actualizado_en)"
                   " VALUES ('Curso de SQL','idea',0,'someday',0,0,'ideas',4,'x','x')")
        db.executemany("INSERT INTO pipeline_items (text, created_at) VALUES (?, '2026-11-01')",
                       [('Viaje a Oaxaca',), ('curso de sql',), ('  ',), ('Leer Meditaciones',)])
        assert database.migrar_pipeline_a_ideas(db) == 2          # sin duplicar «Curso de SQL»
        assert database.migrar_pipeline_a_ideas(db) == 0          # idempotente
        db.commit()
    assert _ideas() == ['Curso de SQL', 'Viaje a Oaxaca', 'Leer Meditaciones']
    database.init_db()                                           # re-arrancar no duplica
    assert len(_ideas()) == 3


def test_pipeline_de_acta_lee_y_escribe_ideas(client):
    r = client.post('/actividades/api/pipeline', json={'text': 'App de recetas'}).get_json()
    assert r['items'][0]['text'] == 'App de recetas'
    iid = r['items'][0]['id']
    assert 'App de recetas' in _ideas()
    # la misma idea se ve en Praxis y en Acta
    assert '"title": "App de recetas"' in client.get('/gtd/').get_data(as_text=True)
    acta = client.get('/actividades/').get_data(as_text=True)
    assert 'data-id="%d">App de recetas' % iid in acta and 'son las Ideas de Praxis' in acta
    with database.get_db() as db:
        assert db.execute('SELECT COUNT(*) FROM pipeline_items').fetchone()[0] == 0   # ya nadie escribe ahí
    # quitar desde Acta borra la idea; no toca tareas de otros cuadrantes
    tid = _nueva(client, 'Tarea normal')
    client.delete(f'/actividades/api/pipeline/{tid}')
    client.delete(f'/actividades/api/pipeline/{iid}')
    assert 'App de recetas' not in _ideas()
    with database.get_db() as db:
        assert db.execute('SELECT COUNT(*) FROM gtd_tasks WHERE id=?', (tid,)).fetchone()[0] == 1


# ── Sprint 6: prioridades = estrellas en Hoy (D3) ────────────────────────────

from utils import today_str


def _hoy_task(client, texto):
    tid = _nueva(client, texto)
    client.post(f'/gtd/api/task/{tid}/classify', json={'importante': True, 'urgente': True})
    return tid


def test_estrella_maximo_tres_y_solo_en_hoy(client):
    ids = [_hoy_task(client, f'H{i}') for i in range(4)]
    for n, tid in enumerate(ids[:3], 1):
        r = client.post(f'/gtd/api/task/{tid}/prioridad').get_json()
        assert r['ok'] and r['prioridad'] is True and r['n'] == n
    r = client.post(f'/gtd/api/task/{ids[3]}/prioridad')
    assert r.status_code == 409 and 'Ya tienes 3' in r.get_json()['error']
    # quitar una libera el lugar
    assert client.post(f'/gtd/api/task/{ids[0]}/prioridad').get_json()['prioridad'] is False
    assert client.post(f'/gtd/api/task/{ids[3]}/prioridad').get_json()['ok']
    # una tarea de Semana no puede ser prioridad
    sem = _nueva(client, 'S')
    client.post(f'/gtd/api/task/{sem}/classify', json={'importante': True, 'urgente': False})
    client.post(f'/gtd/api/task/{ids[3]}/prioridad')
    assert client.post(f'/gtd/api/task/{sem}/prioridad').status_code == 400


def test_acta_y_praxis_son_la_misma_tarea_y_bono_unico(client):
    ids = [_hoy_task(client, f'P{i}') for i in range(3)]
    for tid in ids:
        client.post(f'/gtd/api/task/{tid}/prioridad')
    acta = client.get('/actividades/').get_data(as_text=True)
    for i in range(3):
        assert f'<span class="eu-act-t">P{i}</span>' in acta
    # una se completa en Praxis, otra en Acta: ambas cuentan
    client.post(f'/gtd/api/task/{ids[0]}/complete')
    r = client.post(f'/actividades/api/priority/{ids[1]}/toggle').get_json()
    assert [p['done'] for p in r['priorities']] == [True, True, False] and not r['all3']
    with database.get_db() as db:
        assert db.execute('SELECT completado FROM gtd_tasks WHERE id=?', (ids[1],)).fetchone()[0] == 1
    r = client.post(f'/gtd/api/task/{ids[2]}/complete').get_json()
    assert r['all3'] and 'priority_bonus_gam' in r['gam']
    assert _ledger("description='Bonus: Prioridades x3'")['c'] == 1
    # volver a marcar en Acta no repite nada
    r = client.post(f'/actividades/api/priority/{ids[2]}/toggle').get_json()
    assert not r['all3']
    assert _ledger("description='Bonus: Prioridades x3'")['c'] == 1


def test_agregar_prioridad_desde_acta_crea_tarea_de_hoy(client):
    for i in range(3):
        assert client.post('/actividades/api/priority', json={'text': f'A{i}'}).status_code == 200
    assert client.post('/actividades/api/priority', json={'text': 'A3'}).status_code == 409
    with database.get_db() as db:
        rows = db.execute("SELECT cuadrante, prioridad_dia FROM gtd_tasks WHERE title LIKE 'A%'").fetchall()
    assert len(rows) == 3 and all(r['cuadrante'] == 'hoy' and r['prioridad_dia'] == today_str() for r in rows)


def test_migra_prioridades_manuales_de_hoy_sin_duplicar(client):
    hoy = today_str()
    tid = _hoy_task(client, 'Llamar al banco')            # ya existe como tarea abierta
    with database.get_db() as db:
        db.executemany("INSERT INTO priorities (date, text, done) VALUES (?,?,?)",
                       [(hoy, 'llamar al banco', 0), (hoy, 'Enviar declaración', 1), (hoy, 'Leer', 0), (hoy, 'Sobra', 0),
                        ('2026-01-01', 'Otro día', 0)])
        db.commit()
    for _ in range(2):                                     # cargar dos veces no duplica
        client.get('/gtd/')
        client.get('/actividades/')
    with database.get_db() as db:
        star = db.execute("SELECT id, title, completado FROM gtd_tasks WHERE prioridad_dia=? ORDER BY id", (hoy,)).fetchall()
        assert db.execute("SELECT COUNT(*) FROM gtd_tasks WHERE lower(title)='llamar al banco'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM priorities WHERE date=? AND gtd_task_id IS NULL", (hoy,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM gtd_tasks WHERE title='Otro día'").fetchone()[0] == 0
    assert [r['title'] for r in star] == ['Llamar al banco', 'Enviar declaración', 'Leer']   # máx. 3
    assert star[0]['id'] == tid and star[1]['completado'] == 1


def test_praxis_pinta_estrella_y_pie():
    js = _src('static/js/praxis.js')
    assert 'js-star' in js and "'/prioridad'" in js
    assert '/3 prioridades</b> · se muestran en Acta Diurna y dan su bono al completarse' in js
