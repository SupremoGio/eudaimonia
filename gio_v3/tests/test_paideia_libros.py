"""
test_paideia_libros.py — handoff Paideia v2 (/paideia/, Libros).

Sprint 1: ritmo de la meta anual, +10 XP · +5 EC al terminar un libro
(revertible) y registrar avance marca una vez al día la lectura en Acta.
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.paideia.routes as pr
import modules.actividades.activity_defs as adefs

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


def _libro(client, **kw):
    body = {'titulo': kw.pop('titulo', 'Meditaciones'), 'autor': 'Marco Aurelio', 'paginas_totales': 200, **kw}
    return client.post('/paideia/api/libros', json=body).get_json()['id']


def _logs(key):
    with database.get_db() as db:
        return db.execute("SELECT COUNT(*) FROM activity_logs WHERE activity_key=?", (key,)).fetchone()[0]


def _xp(desc_like):
    with database.get_db() as db:
        return db.execute("SELECT COALESCE(SUM(amount),0) FROM xp_ledger WHERE description LIKE ?", (desc_like,)).fetchone()[0]


# ── Ritmo ────────────────────────────────────────────────────────────────────

def test_ritmo_1_de_enero():
    r = pr.ritmo(12, 0, datetime.date(2026, 1, 1))
    assert r['ritmo_hoy'] == 0.0 and r['diff_ritmo'] == 0.0
    assert r['faltan'] == 12 and r['dias_restantes'] == 364 and r['cada_n_dias'] == 30


def test_ritmo_a_mitad_de_anio_detras():
    r = pr.ritmo(12, 4, datetime.date(2026, 7, 2))           # día 183 de 365
    assert r['ritmo_hoy'] == 6.0 and r['diff_ritmo'] == -2.0
    assert r['faltan'] == 8 and r['dias_restantes'] == 182 and r['cada_n_dias'] == 23
    assert r['ritmo_pct'] == 50.0


def test_ritmo_meta_cumplida():
    r = pr.ritmo(12, 13, datetime.date(2026, 11, 9))
    assert r['faltan'] == 0 and r['cada_n_dias'] is None and r['diff_ritmo'] > 0


def test_stats_trae_el_ritmo(client):
    s = client.get('/paideia/api/libros').get_json()['stats']
    for k in ('ritmo_hoy', 'diff_ritmo', 'faltan', 'dias_restantes', 'cada_n_dias'):
        assert k in s


# ── XP al terminar ───────────────────────────────────────────────────────────

def test_terminar_da_xp_una_vez_y_deshacer_lo_revierte(client):
    lid = _libro(client, estado='leyendo')
    r = client.patch(f'/paideia/api/libros/{lid}', json={'estado': 'leido'}).get_json()
    assert r['ok'] and r['gam'] and r['gam']['xp'] >= 10 and r['gam']['ec'] == 5
    assert _logs(f'paideia_libro_{lid}') == 1
    # volver a guardar como leído (ej. calificar) no paga otra vez
    client.patch(f'/paideia/api/libros/{lid}', json={'estado': 'leido', 'rating': 5})
    assert _logs(f'paideia_libro_{lid}') == 1
    # regresar a «leyendo» lo revierte
    r = client.patch(f'/paideia/api/libros/{lid}', json={'estado': 'leyendo'}).get_json()
    assert r['gam'] and _logs(f'paideia_libro_{lid}') == 0
    assert _xp(f'%paideia_libro_{lid}%') == 0


def test_borrar_un_libro_leido_revierte_el_xp(client):
    lid = _libro(client, estado='leyendo')
    client.patch(f'/paideia/api/libros/{lid}', json={'estado': 'leido'})
    assert _logs(f'paideia_libro_{lid}') == 1
    client.delete(f'/paideia/api/libros/{lid}')
    assert _logs(f'paideia_libro_{lid}') == 0


# ── Registrar avance marca la lectura en Acta ────────────────────────────────

def _hoy(monkeypatch, d):
    monkeypatch.setattr(pr, 'today_date', lambda: d)
    monkeypatch.setattr(pr, 'today_str', lambda: d.isoformat())


def test_progreso_por_pagina_y_ancla_una_vez(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 11, 10))           # martes: toca el ancla de Paideia
    act = pr.lectura_de_hoy()
    assert act and act['ancla'] and act['key'] == 'ancla_leer_psico'
    lid = _libro(client, estado='leyendo')
    r = client.post(f'/paideia/api/libros/{lid}/progreso', json={'pagina': 50}).get_json()
    assert r == {**r, 'ok': True, 'pct': 25, 'ancla_marcada': True, 'nueva': True}
    r = client.post(f'/paideia/api/libros/{lid}/progreso', json={'pagina': 80}).get_json()
    assert r['ancla_marcada'] and not r['nueva']              # idempotente por día
    with database.get_db() as db:
        n = db.execute("SELECT COUNT(*) FROM activity_logs WHERE activity_key='ancla_leer_psico' AND date='2026-11-10'").fetchone()[0]
        libro = db.execute("SELECT paginas_actuales, progreso_pct FROM paideia_libros WHERE id=?", (lid,)).fetchone()
    assert n == 1 and (libro['paginas_actuales'], libro['progreso_pct']) == (80, 40)


def test_sin_ancla_hoy_marca_leer_5_paginas(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 11, 9))            # lunes: no hay ancla de Paideia
    act = pr.lectura_de_hoy()
    assert act and not act['ancla'] and act['key'] == 'leer_general'
    lid = _libro(client, estado='leyendo')
    r = client.post(f'/paideia/api/libros/{lid}/progreso', json={'pct': 30}).get_json()
    assert r['ok'] and r['pct'] == 30 and r['ancla_marcada'] and r['actividad'] == 'Leer 5 páginas'


def test_progreso_sube_la_minima_a_completa(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 11, 10))
    with database.get_db() as db:
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('ancla_leer_psico__min', '2026-11-10', 1)")
        db.commit()
    lid = _libro(client, estado='leyendo')
    client.post(f'/paideia/api/libros/{lid}/progreso', json={'pagina': 10})
    assert _logs('ancla_leer_psico__min') == 0 and _logs('ancla_leer_psico') == 1


def test_progreso_valida_y_empieza_un_libro_por_leer(client):
    lid = _libro(client)                                     # por_leer
    assert client.post(f'/paideia/api/libros/{lid}/progreso', json={}).status_code == 400
    assert client.post('/paideia/api/libros/999/progreso', json={'pagina': 3}).status_code == 404
    client.post(f'/paideia/api/libros/{lid}/progreso', json={'pagina': 500})
    with database.get_db() as db:
        row = db.execute("SELECT estado, paginas_actuales, progreso_pct FROM paideia_libros WHERE id=?", (lid,)).fetchone()
    assert (row['estado'], row['paginas_actuales'], row['progreso_pct']) == ('leyendo', 200, 100)


# ── Sprint 2: encabezado y héroe ─────────────────────────────────────────────

def _src(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


def _hero(html):
    return html.split('id="pd-hero"', 1)[1].split('</section>', 1)[0]


def test_encabezado_en_una_fila_sin_tip_ni_plus_duplicado(client):
    html = client.get('/paideia/').get_data(as_text=True)
    hd = html.split('<header class="pd-hd">', 1)[1].split('</header>', 1)[0]
    assert 'class="eu-seg pd-tabs"' in hd and hd.count('js-new"') == 1
    for fuera in ('pd-lead', 'pd-tip', 'pd-stats', 'pd-now', 'js-bump', '+10 págs'):
        assert fuera not in html, fuera
    assert html.count('class="eu-btn eu-btn--primary js-new"') == 1


def test_heroe_meta_con_ritmo(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 7, 2))
    monkeypatch.setattr(pr, '_get_meta', lambda: 12)
    for i in range(4):
        lid = _libro(client, titulo=f'L{i}', estado='leyendo')
        client.patch(f'/paideia/api/libros/{lid}', json={'estado': 'leido', 'fecha_fin': '2026-03-01'})
    h = _hero(client.get('/paideia/').get_data(as_text=True))
    assert 'Meta 2026' in h and '<span class="pd-goal-n num">4</span>' in h and ' / 12 libros' in h
    assert 'ritmo hoy 6.0' in h and 'left:50.0%' in h
    assert 'Vas 2 libros detrás del ritmo' in h and 'Faltan 8 en 182 días: 1 cada 23 días.' in h


def test_heroe_meta_cumplida_y_adelantado(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 1, 10))
    monkeypatch.setattr(pr, '_get_meta', lambda: 1)
    lid = _libro(client, estado='leyendo')
    client.patch(f'/paideia/api/libros/{lid}', json={'estado': 'leido', 'fecha_fin': '2026-01-05'})
    assert 'Meta cumplida. Todo lo que leas suma.' in _hero(client.get('/paideia/').get_data(as_text=True))
    monkeypatch.setattr(pr, '_get_meta', lambda: 12)
    assert 'Vas adelantado · faltan 11' in _hero(client.get('/paideia/').get_data(as_text=True))


def test_heroe_todos_los_libros_en_lectura(client):
    a = _libro(client, titulo='Meditaciones', estado='leyendo', paginas_actuales=50)
    b = _libro(client, titulo='Sapiens', estado='leyendo', paginas_totales=None, progreso_pct=30)
    h = _hero(client.get('/paideia/').get_data(as_text=True))
    assert 'Leyendo ahora · 2' in h
    assert h.count('class="pd-rd"') == 2
    assert 'pág. 50 de 200 · 25%' in h and '≈ 6 sesiones de 30 min' in h        # 150 págs ÷ 25
    assert f'data-id="{a}" data-mode="pagina"' in h and f'data-id="{b}" data-mode="pct"' in h
    assert 'Registrar %' in h and h.count('Terminar +10 XP') == 2
    assert 'pd-nowrap js-prog' in h and 'pd-nowrap pd-finish js-finish' in h


def test_heroe_sin_lectura_y_pie_del_ancla(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 11, 10))
    h = _hero(client.get('/paideia/').get_data(as_text=True))
    assert 'No estás leyendo nada. Elige uno de «Por leer» abajo.' in h
    assert 'Registrar avance hoy marca «Leer psicología — sesión profunda» en Acta Diurna' in h
    lid = _libro(client, estado='leyendo')
    client.post(f'/paideia/api/libros/{lid}/progreso', json={'pagina': 20})
    h = _hero(client.get('/paideia/').get_data(as_text=True))
    assert 'class="pd-anchor is-ok js-anchor"' in h and 'marcada hoy en Acta Diurna' in h


def test_js_del_heroe():
    js = _src('static/js/paideia.js')
    assert "'/progreso'" in js and "{ estado: 'leido' }" in js and 'refreshLibros' in js
    assert "' terminado · +10 XP · +5 EC · meta '" in js.replace('»', "'").replace('«', "'") or 'terminado · +10 XP · +5 EC · meta' in js
    assert 'js-tip' not in js and 'js-bump' not in js
