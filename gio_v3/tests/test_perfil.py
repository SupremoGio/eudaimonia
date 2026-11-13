"""
test_perfil.py — handoff Perfil v2 (/perfil/).

Sprint 1: nav_counts, «Requiere atención», tiles y /posponer.
Sprint 2: lateral sin nivel/XP/EC y Resumen como portada (?sec=).
Sprint 3: datos en grupos, clic para copiar, privados en un solo fetch.
Sprint 4: medidas en tabla y lote (solo lo que cambió).
Sprint 5: recordatorios agrupados, pagos de tarjeta enlazados a Oikonomia
(solo con fin_ok) y ajustes.
"""
import sys, os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_str
from modules.perfil import resumen as rs

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ahora():
    """Reloj de la app (zona de la app) sin tz: así guarda la app sus fechas; datetime.now()
    del servidor (UTC) se desfasa un día cerca de la medianoche."""
    from utils import now_local
    return now_local().replace(tzinfo=None)
HOY = date.fromisoformat(today_str())


def _client(fin_ok=True):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
        if fin_ok:
            s['fin_ok'] = True
    return c


@pytest.fixture
def client(test_db):
    return _client()


def _rem(desc, dias, tipo='unico', **kw):
    f = (HOY + timedelta(days=dias)).isoformat()
    cols = {'description': desc, 'type': tipo, 'target_date': f, 'next_date': f, 'is_active': 1,
            'created_at': 'x', 'freq_unit': kw.pop('freq_unit', ''), 'freq_value': kw.pop('freq_value', 1), **kw}
    with database.get_db() as db:
        rid = db.execute(f"INSERT INTO reminders ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         list(cols.values())).lastrowid
        db.commit()
    return rid


def _sin_rems():
    with database.get_db() as db:
        db.execute("DELETE FROM reminders")
        db.commit()


def _info(**vals):
    with database.get_db() as db:
        for k, v in vals.items():
            db.execute("UPDATE personal_info SET value=? WHERE key=?", (v, k))
        db.commit()


def _todo_lleno():
    with database.get_db() as db:
        db.execute("UPDATE personal_info SET value='x'")
        db.commit()


def _medida(key, *vals, dias=0):
    with database.get_db() as db:
        for i, v in enumerate(vals):
            ts = (_ahora() - timedelta(days=dias + len(vals) - 1 - i)).isoformat()
            db.execute("INSERT INTO body_measurements_history (key, value, recorded_at) VALUES (?,?,?)", (key, str(v), ts))
        db.execute("UPDATE body_measurements SET value=? WHERE key=?", (str(vals[-1]), key))
        db.commit()


def _get(c, q=''):
    return c.get('/perfil/' + q).get_data(as_text=True)


def _ctx(test_db):
    from modules.perfil import recordatorios as rec
    with database.get_db() as db:
        info = db.execute("SELECT * FROM personal_info").fetchall()
        meas = db.execute("SELECT * FROM body_measurements ORDER BY rowid").fetchall()
        hist = db.execute("SELECT key, value, recorded_at FROM body_measurements_history ORDER BY recorded_at DESC").fetchall()
        rems = [dict(r) for r in db.execute("SELECT * FROM reminders WHERE is_active=1").fetchall()]
    med = rs.medidas(meas, hist, HOY)
    return info, med, rs.grupos_recordatorios(rems, HOY)


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_atencion_vacia_sin_vencidos(test_db):
    _sin_rems()
    _todo_lleno()
    _rem('Cumpleaños de Ana', 3)
    info, med, grupos = _ctx(test_db)
    assert rs.atencion(grupos, info, med) == []


def test_atencion_ordenada(test_db):
    _sin_rems()
    _todo_lleno()
    _info(rfc='— editar —')
    _rem('Verificación', -2)
    _rem('Pagar luz', 0)
    _medida('cintura', 86, 85, dias=70)
    _medida('estatura', 178, dias=400)
    info, med, grupos = _ctx(test_db)
    a = rs.atencion(grupos, info, med)
    assert [x['tipo'] for x in a] == ['rem', 'rem', 'dato', 'medidas']
    assert a[0]['vencido'] and a[0]['desc'] == 'Verificación' and not a[1]['vencido']
    assert a[2] == {'tipo': 'dato', 'campo': 'rfc', 'label': 'RFC', 'privado': True}
    assert a[3]['n'] == 1 and a[3]['labels'] == 'Cintura'            # la estatura no envejece


def test_nav_counts_y_tiles(test_db):
    _sin_rems()
    _todo_lleno()
    _info(direccion='— editar —')
    _rem('A', -1)
    _rem('B', 2)
    _medida('peso', 79.6, 79.0, 78.4, dias=6)
    info, med, grupos = _ctx(test_db)
    n = rs.nav_counts(info, med, grupos, 7, 14)
    assert n['datos']['txt'] == f'{len(info) - 1}/{len(info)}'
    assert n['recordatorios']['txt'] == '2' and n['recordatorios']['warn']
    assert n['resumen']['txt'] == '1 urgente' and n['documentos']['txt'] == '7' and n['vault']['txt'] == '14'
    t = {x['sec']: x for x in rs.tiles(grupos, info, med)}
    assert t['recordatorios']['sub'] == '1 urgente · 1 esta semana'
    assert t['medidas']['val'] == '78.4 kg' and t['medidas']['sub'] == 'peso · hace 6 d'


def test_posponer_no_toca_la_recurrencia(client):
    _sin_rems()
    rid = _rem('Pagar renta', -1, tipo='periodico', freq_unit='meses', freq_value=1)
    with database.get_db() as db:
        antes = dict(db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone())
    r = client.post(f'/perfil/api/recordatorios/{rid}/posponer').get_json()
    with database.get_db() as db:
        d = dict(db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone())
    assert r['fecha'] == (HOY + timedelta(days=1)).isoformat() == d['next_date']
    assert (d['type'], d['freq_unit'], d['freq_value'], d['target_date']) == \
           (antes['type'], antes['freq_unit'], antes['freq_value'], antes['target_date'])


def test_hecho_recurrente_da_xp(client):
    _sin_rems()
    rid = _rem('Pagar renta', 0, tipo='periodico', freq_unit='meses', freq_value=1)
    client.post(f'/perfil/api/reminder/{rid}/done')
    with database.get_db() as db:
        assert db.execute("SELECT pts FROM activity_logs WHERE activity_key=?", (f'recordatorio_{rid}',)).fetchone()['pts'] == 3


# ── Sprint 2 ─────────────────────────────────────────────────────────────────

def test_lateral_y_resumen(client):
    _sin_rems()
    _rem('Verificación', -2)
    html = _get(client)
    aside = html.split('<aside class="pf-aside">', 1)[1].split('</aside>', 1)[0]
    assert 'Tú · Αὐτός' in aside and aside.count('class="pf-nav-it"') == 7
    for fuera in ('Nivel ', 'xpbar', '/logros', '/recompensas', ' EC'):
        assert fuera not in aside, fuera
    assert 'data-ct="resumen">1 urgente' in aside and 'is-warn' in aside
    res = html.split('id="sec-resumen"', 1)[1].split('</section>\n</section>', 1)[0]
    assert 'Requiere atención' in res and 'js-attn-done' in res and 'Mañana' in res
    assert res.count('class="pf-tile"') == 3
    assert not os.path.exists(os.path.join(BASE, 'templates/perfil/_hub.html'))


def test_resumen_todo_al_dia(client):
    _sin_rems()
    _todo_lleno()
    html = _get(client)
    assert '<div class="pf-attn-ok js-attn-ok">' in html                # visible, sin hidden


def test_sec_en_la_url(client):
    html = _get(client, '?sec=medidas')
    assert 'data-sec="medidas"' in html
    assert 'data-sec-panel="medidas">' in html and 'data-sec-panel="resumen" hidden' in html


def test_tema_y_salir_solo_en_ajustes(client):
    html = _get(client)
    fuera = html.split('id="sec-ajustes"', 1)[0].split('<div class="pf" id="pf"', 1)[1]
    assert 'data-theme-set' not in fuera and 'logoutApp' not in fuera


# ── Sprint 3 ─────────────────────────────────────────────────────────────────

def test_datos_en_grupos_y_privado_fuera_del_html(client):
    _info(curp='RUSG940312HDFLLV08', telefono='+52 55 1234 5678')
    html = _get(client, '?sec=datos')
    assert 'RUSG940312HDFLLV08' not in html                             # ni en data-, ni en JSON
    sec = html.split('id="sec-datos"', 1)[1].split('</section>', 1)[0]
    for g in ('Identidad', 'Contacto', 'Privados · cifrados'):
        assert g in sec
    assert 'js-vis' not in sec and 'pf-priv' not in sec and 'eye-off' not in sec   # sin ojo por campo
    assert 'js-reveal' in sec and 'Mostrar privados' in sec
    assert 'pf-val js-val is-mono' in sec and '+52 55 1234 5678' in sec


def test_privados_en_un_solo_fetch(client):
    _info(curp='RUSG940312HDFLLV08', nss='12345678901')
    v = client.get('/perfil/api/privados').get_json()['valores']
    assert v['curp'] == 'RUSG940312HDFLLV08' and v['nss'] == '12345678901'
    assert 'nombre' not in v
    assert _client(fin_ok=False).get('/perfil/api/privados').status_code == 403


def test_js_auto_oculta_y_copia_del_backend():
    js = open(os.path.join(BASE, 'static/js/perfil.js'), encoding='utf-8').read()
    assert "setTimeout(hidePriv, 30000)" in js and "/perfil/api/privados" in js
    assert 'priv[k]' not in js


# ── Sprint 4 ─────────────────────────────────────────────────────────────────

def test_medidas_tabla_tendencia_y_edad(test_db):
    _medida('peso', 79.6, 79.0, 78.4, dias=6)
    _medida('biceps', 34.5, 34, dias=70)
    _medida('estatura', 178, dias=400)
    info, med, _ = _ctx(test_db)
    by = {m['key']: m for m in med}
    assert by['peso']['ultimas'] == [79.6, 79.0, 78.4] and by['peso']['tono'] == 'success' and by['peso']['delta'] == -0.6
    assert by['biceps']['tono'] == 'warning' and by['biceps']['vieja']
    assert not by['estatura']['vieja'] and by['estatura']['edad_txt'] == 'hace 1 año'


def test_lote_solo_lo_que_cambio(client):
    _medida('peso', 78.4)
    _medida('cintura', 84)
    with database.get_db() as db:
        n0 = db.execute("SELECT COUNT(*) c FROM body_measurements_history").fetchone()['c']
    r = client.post('/perfil/api/medidas/lote', json={'valores': {'peso': '78.0', 'cintura': '84', 'cuello': '', 'nope': '1'}}).get_json()
    assert r['guardadas'] == ['peso']
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) c FROM body_measurements_history").fetchone()['c'] == n0 + 1
        assert db.execute("SELECT value FROM body_measurements WHERE key='peso'").fetchone()['value'] == '78.0'


def test_medidas_html(client):
    html = _get(client, '?sec=medidas')
    sec = html.split('id="sec-medidas"', 1)[1]
    assert 'Actualizar todas' in sec and 'Guardar lectura de hoy' in sec and 'Últimas 3' in sec
    assert 'Tallas por marca · ' in sec and 'Grasa corporal · ' in sec
    assert 'pf-hist' not in sec and 'js-mcopy' not in sec


# ── Sprint 5 ─────────────────────────────────────────────────────────────────

def test_tarjeta_de():
    assert rs.tarjeta_de('Pagar HSBC') == 'hsbc' and rs.tarjeta_de('Pago tarjeta BBVA día 15') == 'bbva'
    assert rs.tarjeta_de('Cumpleaños de Ana') is None and rs.tarjeta_de('Revisar HSBC') is None


def test_vincular_idempotente(test_db):
    _sin_rems()
    a = _rem('Pagar HSBC', 0, tema='finanzas')
    b = _rem('Pagar renta', 0, tema='finanzas')
    with database.get_db() as db:
        assert rs.vincular_pagos(db) == 1
        assert rs.vincular_pagos(db) == 0
        rows = {r['id']: r['vinculado_oikonomia'] for r in db.execute("SELECT id, vinculado_oikonomia FROM reminders")}
    assert rows == {a: 1, b: 0}


def test_enlace_oikonomia_solo_con_fin_ok(test_db):
    _sin_rems()
    _rem('Pagar HSBC', 0, tema='finanzas')
    assert 'En Oikonomia →' not in _get(_client(fin_ok=False), '?sec=recordatorios')
    with database.get_db() as db:
        assert db.execute("SELECT vinculado_oikonomia FROM reminders").fetchone()[0] == 0
    html = _get(_client(), '?sec=recordatorios')
    assert 'En Oikonomia →' in html


def test_recordatorios_agrupados(client):
    _sin_rems()
    _rem('Vencido', -2)
    _rem('Hoy', 0)
    _rem('Semana', 4)
    _rem('Mes', 20)
    _rem('Renta', 40, tipo='periodico', freq_unit='meses', freq_value=1)
    sec = _get(client, '?sec=recordatorios').split('id="sec-recordatorios"', 1)[1]
    for g in ('Vencidos', 'Hoy', 'Esta semana', 'Después'):
        assert f'<span>{g}</span>' in sec
    assert 'Este mes' not in sec and 'Más adelante' not in sec
    assert '↻ Mensual · +3 XP' in sec


def test_ajustes(client):
    sec = _get(client, '?sec=ajustes').split('id="sec-ajustes"', 1)[1]
    assert 'data-theme-set="dark">Noche' in sec and 'Cerrar sesión' in sec
    assert sec.index('Cerrar sesión') < sec.index('Zona de peligro') and 'RESET' in sec
