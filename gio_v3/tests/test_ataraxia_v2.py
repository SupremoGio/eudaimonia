"""
test_ataraxia_v2.py — handoff Ataraxia v2 (/ataraxia/).

Sprint 1: encabezado con fecha · semana, pestañas compactas con su conteo,
Reset solo en el menú ⋯ (con confirmación), recompensas visibles desde el
inicio y vista previa de solo lectura entre semana.
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
import modules.ataraxia.routes as ar

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMINGO, MIERCOLES, JUEVES = datetime.date(2026, 11, 8), datetime.date(2026, 11, 4), datetime.date(2026, 11, 5)


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _hoy(monkeypatch, d):
    monkeypatch.setattr(ar, 'today_date', lambda: d)
    monkeypatch.setattr(ar, 'today_str', lambda: d.isoformat())


def _src(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


def _get(client, q=''):
    return client.get('/ataraxia/' + q).get_data(as_text=True)


def _side(html):
    return html.split('<aside class="at-side"', 1)[1].split('</aside>', 1)[0]


def test_encabezado_fecha_semana_y_pestanas(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client)
    hd = html.split('<header class="at-hd">', 1)[1].split('</header>', 1)[0]
    assert 'Domingo 8 de noviembre · Semana 45' in hd
    assert 'class="eu-seg at-tabs"' in hd
    assert 'id="tab-sabado"' in hd and 'id="tab-domingo"' in hd
    assert hd.count('js-day-cnt') == 2
    assert 'aria-label="Más opciones"' in hd and 'id="reset-trigger"' in hd
    assert 'role="menu" hidden' in hd                  # el Reset solo vive en el menú ⋯
    for fuera in ('at-lead', 'at-week', 'finde-banner', 'at-note', 'Hoy no es fin de semana'):
        assert fuera not in html, fuera
    assert html.count('id="reset-trigger"') == 1 and "euModal.open('at-reset')" in _src('static/js/ataraxia.js')


def test_recompensas_visibles_antes_de_ganarlas(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    side = _side(_get(client))
    for rid, label, rw in [('sabado', 'Sábado completo', '+4 XP · +2 EC'), ('domingo', 'Domingo completo', '+5 XP · +3 EC'),
                           ('finde', 'Fin de semana perfecto', '+15 XP · +30 EC')]:
        assert f'id="rw-{rid}"' in side and label in side and rw in side
    assert 'is-ok' not in side and side.count('data-lucide="circle-dashed"') == 2


def test_recompensa_se_marca_al_completar_el_dia(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    with database.get_db() as db:
        req = [r['id'] for r in db.execute("SELECT id FROM rutina_bloques WHERE dia='sabado' AND opcional=0")]
        for tid in req:
            db.execute("INSERT INTO rutina_progreso (bloque_id, semana_id, completado) VALUES (?,?,1)", (tid, ar.get_semana_id()))
        db.commit()
    html = _get(client)
    assert '<div class="at-rw-row is-ok" id="rw-sabado"' in _side(html)
    assert '<div class="at-rw-row" id="rw-finde"' in _side(html)
    tab = html.split('id="tab-sabado"', 1)[1].split('</button>', 1)[0]
    assert '>✓</span>' in tab and 'data-complete="true"' in tab


def test_entre_semana_vista_previa_solo_lectura(client, monkeypatch):
    _hoy(monkeypatch, JUEVES)                         # lun–mié es prórroga; jue–vie, vista previa
    html = _get(client)
    assert 'Faltan 2 días para el sábado · vista previa' in html
    assert 'data-preview="1"' in html
    tareas = html.count('class="at-task js-task"')
    assert tareas and html.count('aria-disabled="true"') >= tareas
    assert 'root.dataset.preview' in _src('static/js/ataraxia.js')


def test_fin_de_semana_se_puede_marcar(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client)
    assert 'data-preview' not in html and 'aria-disabled="true"' not in html.split('class="at-main"', 1)[1]


# ── Sprint 2: un bloque abierto, el «Ahora» ──────────────────────────────────

def _bloques_abiertos(html, dia):
    panel = html.split(f'id="dia-{dia}"', 1)[1]
    if dia == 'sabado':
        panel = panel.split('id="dia-domingo"', 1)[0]
    return panel.count('aria-expanded="true"'), panel


def _marcar(bids):
    with database.get_db() as db:
        for tid in bids:
            db.execute("INSERT INTO rutina_progreso (bloque_id, semana_id, completado) VALUES (?,?,1)", (tid, ar.get_semana_id()))
        db.commit()


def test_un_solo_bloque_abierto_y_es_el_primero_pendiente(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    sab = ar._build_rutina('sabado', ar.get_semana_id())
    primero = sab['bloques'][0]
    assert sab['ahora'] == primero['bloque_id']
    # completar el primero mueve el «Ahora» al siguiente pendiente
    _marcar([t['id'] for t in primero['tareas'] if not t['opcional']])
    sab = ar._build_rutina('sabado', ar.get_semana_id())
    siguiente = next(b for b in sab['bloques'] if b['done_count'] < b['required_count'])
    assert sab['ahora'] == siguiente['bloque_id'] != primero['bloque_id']
    html = _get(client, '?dia=sabado')
    n, panel = _bloques_abiertos(html, 'sabado')
    assert n == 1
    assert f'class="eu-card eu-card--flush at-bl is-now" id="blcard-{siguiente["bloque_id"]}"' in panel
    assert f'id="blprog-{primero["bloque_id"]}">Listo</span>' in panel


def test_bloque_abierto_trae_temporizador_con_iniciar(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client, '?dia=domingo')
    assert '<span>Iniciar</span>' in html and 'eu-btn eu-btn--primary eu-btn--sm js-timer' in html
    for i in ('trow-', 'blbar-', 'blprog-', 'blpb-', 'timer-', 'js-day-cnt'):
        assert i in html, i                     # ids que usa ataraxia.js


def test_opcionales_con_regla_en_la_fila_y_sin_at_complete(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client)
    with database.get_db() as db:
        hay_opcional = db.execute("SELECT COUNT(*) FROM rutina_bloques WHERE opcional=1").fetchone()[0]
    if hay_opcional:
        assert '· opcional, no cuenta para el 100%' in html
    assert '<span class="eu-badge">opcional</span>' not in html
    assert 'at-complete' not in html and 'day-complete' not in _src('static/js/ataraxia.js')
    js = _src('static/js/ataraxia.js')
    assert 'markNow(dia)' in js and 'setOpen(justDone, false)' in js


# ── Sprint 3: revisión semanal con datos automáticos ─────────────────────────

import modules.actividades.activity_defs as adefs
import modules.finanzas.budget as fbudget


def _ancla_paideia():
    return adefs.create('Lectura profunda', 'paideia', 'ancla', 'night', pts=3)['key']


def _log(key, fecha):
    with database.get_db() as db:
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,1)", (key, fecha))
        db.commit()


def _budget(monkeypatch, ingreso, consumo):
    monkeypatch.setattr(fbudget, '_calc_budget', lambda mes, db: {'ingreso_real': ingreso, 'consumo': consumo})


def test_autocompleta_presupuesto_y_lectura(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)                       # semana lun 2 – dom 8 nov
    _budget(monkeypatch, 40000, 25600)
    k = _ancla_paideia()
    for f in ('2026-11-02', '2026-11-04', '2026-11-04', '2026-11-07', '2026-10-31'):
        _log(k, f)                                   # 3 días distintos dentro de la semana
    _log(k + '__min', '2026-11-05')                  # la versión mínima no cuenta
    auto = ar._auto_metrics(ar.get_semana_id())
    assert auto['presupuesto_pct'] == (64.0, 'Oikonomia')
    assert auto['dias_lectura'] == (3.0, 'Acta')
    html = _get(client, '?dia=domingo')
    rev = html.split('id="rs-card"', 1)[1]
    assert '<output class="at-metric-v num" id="rs-presupuesto_pct">64</output>' in rev
    assert '<output class="at-metric-v num" id="rs-dias_lectura">3</output>' in rev
    assert rev.count('class="at-auto"') == 2
    assert 'data-metric="presupuesto_pct"' not in rev and 'data-metric="dias_lectura"' not in rev
    assert 'data-metric="horas_sueno"' in rev       # las demás siguen a mano


def test_sin_datos_vuelve_a_manual(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    _budget(monkeypatch, 0, 0)                       # sin ingreso
    def boom(mes, db): raise RuntimeError('db')
    assert 'presupuesto_pct' not in ar._auto_metrics(ar.get_semana_id())
    monkeypatch.setattr(fbudget, '_calc_budget', boom)  # si falla la consulta
    with database.get_db() as db:
        db.execute("UPDATE activity_defs SET active=0 WHERE pillar='paideia'")
        db.commit()
    assert ar._auto_metrics(ar.get_semana_id()) == {}
    rev = _get(client, '?dia=domingo').split('id="rs-card"', 1)[1]
    assert 'data-metric="presupuesto_pct"' in rev and 'data-metric="dias_lectura"' in rev
    assert 'class="at-auto"' not in rev


def test_guardar_usa_los_valores_auto_y_muestra_delta(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    _budget(monkeypatch, 10000, 5000)
    sem = ar.get_semana_id()
    with database.get_db() as db:
        db.execute("INSERT INTO revision_semanal (semana_id, presupuesto_pct, horas_sueno, created_at, updated_at) VALUES (?,?,?,'x','x')",
                   (ar._prev_semana_id(sem), 58.0, 7.0))
        db.commit()
    r = client.post('/ataraxia/api/revision', json={'presupuesto_pct': 99, 'horas_sueno': 6.5}).get_json()
    assert r['ok']
    row = ar._get_revision_row(sem)
    assert row['presupuesto_pct'] == 50.0 and row['horas_sueno'] == 6.5     # el cliente no pisa lo auto
    rev = _get(client, '?dia=domingo').split('id="rs-card"', 1)[1]
    assert '↓ 8 vs anterior · de Oikonomia' in rev                            # presupuesto: bajar es mejor
    assert 'is-better' in rev and 'is-worse' in rev                            # sueño bajó: peor


def test_revision_visible_y_historial_en_logros(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    html = _get(client, '?dia=domingo')
    rev = html.split('id="rs-card"', 1)[1]
    assert '<section class="eu-card eu-vstack at-rev" id="rs-card"' in html     # ya no es <details>
    assert 'Revisión de la semana' in rev and '2–8 nov' in rev
    assert 'Historial de semanas en Logros →' in rev and 'href="/logros/semanas"' in rev
    assert '<details class="at-an">' in rev and 'Análisis' in rev
    assert 'eu-table' not in rev and 'Últimas semanas' not in rev
    client.post('/ataraxia/api/revision', json={'horas_sueno': 7})
    sem = client.get('/logros/semanas').get_data(as_text=True)
    assert 'Historial de semanas' in sem and '2–8 nov' in sem and 'Esta semana' in sem
    assert 'href="/logros/semanas"' in client.get('/logros').get_data(as_text=True)


# ── Sprint 4: prioridades de la semana desde Praxis ──────────────────────────

import modules.gtd.prioridades as prio

LUNES_SIG = datetime.date(2026, 11, 9)          # primer día que gobiernan las elegidas el 7–8 nov


def _semana_task(texto, cuadrante='semana'):
    with database.get_db() as db:
        db.execute("""INSERT INTO gtd_tasks (title,tipo,completado,status,importante,urgente,cuadrante,points,created_at,actualizado_en)
                      VALUES (?, 'tarea', 0, 'inbox', 1, 0, ?, 4, 'x', 'x')""", (texto, cuadrante))
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_semana_eleccion_y_vigente():
    assert prio.semana_eleccion(DOMINGO) == '2026-11-07'
    assert prio.semana_vigente(DOMINGO) == '2026-10-31'          # el domingo aún rige la semana anterior
    assert prio.semana_vigente(LUNES_SIG) == '2026-11-07'
    assert prio.semana_vigente(datetime.date(2026, 11, 15)) == '2026-11-07'


def test_elegir_con_estrella_maximo_tres(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    ids = [_semana_task(f'S{i}') for i in range(4)]
    _semana_task('De Hoy', 'hoy')                                   # no es opción
    html = _get(client, '?dia=domingo')
    box = html.split('id="prio-semana"', 1)[1].split('js-ps-empty', 1)[0]
    assert box.count('class="at-prio-it js-ps"') == 4 and 'De Hoy' not in box
    assert 'id="prio-1"' not in html                                # fuera los 3 inputs de texto
    for n, tid in enumerate(ids[:3], 1):
        r = client.post(f'/ataraxia/api/prioridad-semana/{tid}').get_json()
        assert r['ok'] and r['n'] == n
    r = client.post(f'/ataraxia/api/prioridad-semana/{ids[3]}')
    assert r.status_code == 409 and r.get_json()['n'] == 3
    assert client.post('/ataraxia/api/prioridad-semana', json={'texto': 'Otra'}).status_code == 409
    client.post(f'/ataraxia/api/prioridad-semana/{ids[0]}')        # quitar libera el lugar
    r = client.post('/ataraxia/api/prioridad-semana', json={'texto': 'Nueva'}).get_json()
    assert r['ok'] and r['n'] == 3 and any(o['title'] == 'Nueva' and o['on'] for o in r['opciones'])
    js = _src('static/js/ataraxia.js')
    assert "d.n >= d.max && row && row.getAttribute('aria-pressed') !== 'true'" in js   # 3 → completa la tarea


def test_acta_las_muestra_cada_dia_de_la_semana_siguiente(client, monkeypatch):
    _hoy(monkeypatch, DOMINGO)
    ids = [_semana_task(f'W{i}') for i in range(3)]
    for tid in ids:
        client.post(f'/ataraxia/api/prioridad-semana/{tid}')
    # el domingo de la elección todavía no pasan a Hoy
    with database.get_db() as db:
        assert prio.materializar(db, DOMINGO.isoformat()) == 0
        # el lunes siguiente: Hoy con estrella → Acta las muestra
        assert prio.materializar(db, LUNES_SIG.isoformat()) == 3
        rows = prio.prioridades_hoy(db, LUNES_SIG.isoformat())
        assert [r['text'] for r in rows] == ['W0', 'W1', 'W2']
        assert all(r['cuadrante'] == 'hoy' for r in db.execute(
            "SELECT cuadrante FROM gtd_tasks WHERE id IN (?,?,?)", ids))
        # quitar la estrella ese día la respeta; al día siguiente vuelve
        prio.alternar_estrella(db, ids[0], LUNES_SIG.isoformat())
        db.commit()
        assert prio.materializar(db, LUNES_SIG.isoformat()) == 0
        assert len(prio.prioridades_hoy(db, LUNES_SIG.isoformat())) == 2
        martes = (LUNES_SIG + datetime.timedelta(days=1)).isoformat()
        assert prio.materializar(db, martes) == 3
        # completada ya no vuelve
        db.execute("UPDATE gtd_tasks SET completado=1 WHERE id=?", (ids[1],))
        db.commit()
        assert prio.materializar(db, (LUNES_SIG + datetime.timedelta(days=2)).isoformat()) == 2


def test_migra_weekly_priorities_de_la_semana_actual(test_db):
    from utils import today_date
    hoy = today_date()
    actual = (hoy - datetime.timedelta(days=(hoy.weekday() - 5) % 7)).isoformat()
    vieja = (date_ := datetime.date.fromisoformat(actual) - datetime.timedelta(days=7)).isoformat()
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='ataraxia_v2_prioridades_semana'")
        db.execute("INSERT INTO weekly_priorities (semana_id, p1, p2, p3) VALUES (?, 'Cerrar sprint', 'revisar contrato', NULL)", (actual,))
        db.execute("INSERT INTO weekly_priorities (semana_id, p1) VALUES (?, 'Semana vieja')", (vieja,))
        db.execute("""INSERT INTO gtd_tasks (title,tipo,completado,status,importante,urgente,cuadrante,points,created_at,actualizado_en)
                      VALUES ('Revisar contrato', 'tarea', 0, 'inbox', 1, 0, 'semana', 4, 'x', 'x')""")
        assert database.migrar_prioridades_semana(db) == 2
        assert database.migrar_prioridades_semana(db) == 0
        db.commit()
        rows = db.execute("SELECT title, cuadrante FROM gtd_tasks WHERE prioridad_semana=? ORDER BY id", (actual,)).fetchall()
        assert [(r['title'], r['cuadrante']) for r in rows] == [('Revisar contrato', 'semana'), ('Cerrar sprint', 'semana')]
        assert db.execute("SELECT COUNT(*) FROM gtd_tasks WHERE title='Semana vieja'").fetchone()[0] == 0


def test_praxis_marca_las_prioridades_de_la_semana(client):
    html = client.get('/gtd/').get_data(as_text=True)
    assert f'data-semanas-prio="{prio.semana_eleccion()},{prio.semana_vigente()}"' in html
    assert 'px-sem' in _src('static/js/praxis.js')



# ── Prórroga: lunes a miércoles se termina el fin de semana anterior ─────────

import modules.gamification.engine as engine


@pytest.mark.parametrize('d', [datetime.date(2026, 11, 9), datetime.date(2026, 11, 10), datetime.date(2026, 11, 11)])
def test_prorroga_lunes_a_miercoles_se_puede_marcar(client, monkeypatch, d):
    _hoy(monkeypatch, d)
    html = _get(client)
    assert 'Prórroga: tienes hasta el miércoles para cerrar el fin de semana del 7–8 nov' in html
    assert 'data-preview' not in html and 'aria-disabled="true"' not in html.split('class="at-main"', 1)[1]
    assert ar.get_semana_id() == '2026-11-07'          # sigue siendo el fin de semana anterior


def test_prorroga_abre_domingo_si_el_sabado_ya_esta(client, monkeypatch):
    _hoy(monkeypatch, datetime.date(2026, 11, 9))
    with database.get_db() as db:
        for r in db.execute("SELECT id FROM rutina_bloques WHERE dia='sabado' AND opcional=0").fetchall():
            db.execute("INSERT INTO rutina_progreso (bloque_id, semana_id, completado) VALUES (?, '2026-11-07', 1)", (r['id'],))
        db.commit()
    html = _get(client)
    assert 'id="dia-domingo" role="tabpanel" aria-labelledby="tab-domingo" data-dia-panel="domingo">' in html


def _logs(fecha, keys):
    with database.get_db() as db:
        for k in keys:
            db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,0)", (k, fecha))
        db.commit()


def _combos(desc):
    with database.get_db() as db:
        return db.execute("SELECT COUNT(*) FROM xp_ledger WHERE description=?", (desc,)).fetchone()[0]


def test_combo_del_sabado_se_paga_aunque_se_cierre_el_lunes(test_db, monkeypatch):
    sat = sorted(engine.SAT_COMBO_KEYS)
    _logs('2026-11-07', sat[:4])                       # 4 bloques el sábado
    _logs('2026-11-09', sat[4:])                       # el resto el lunes
    # el motor anota el XP con today_str(): se fija al día simulado
    monkeypatch.setattr(engine, 'today_str', lambda: '2026-11-09')
    combos = engine._check_combo_bonus('2026-11-09', sat[4:])
    assert [c['type'] for c in combos] == ['sat_complete']
    monkeypatch.setattr(engine, 'today_str', lambda: '2026-11-10')
    assert engine._check_combo_bonus('2026-11-10', []) == []       # una sola vez por ciclo
    assert _combos('Combo: Sábado Completo') == 1


def test_fin_de_semana_perfecto_con_prorroga(test_db, monkeypatch):
    sat, sun = sorted(engine.SAT_COMBO_KEYS), sorted(engine.SUN_COMBO_KEYS)
    _logs('2026-11-07', sat)
    monkeypatch.setattr(engine, 'today_str', lambda: '2026-11-07')
    engine._check_combo_bonus('2026-11-07', sat)
    _logs('2026-11-10', sun)                           # domingo cerrado el martes
    monkeypatch.setattr(engine, 'today_str', lambda: '2026-11-10')
    engine._check_combo_bonus('2026-11-10', sun)
    assert _combos('Combo: Domingo Completo') == 1
    monkeypatch.setattr(engine, 'today_str', lambda: '2026-11-10')
    monkeypatch.setattr(engine, 'today_date', lambda: datetime.date(2026, 11, 10))
    assert engine._gather_achievement_stats()['weekend_perfect_week'] is True
    # el jueves siguiente ya es otro ciclo de lectura, pero sigue siendo el mismo
    # fin de semana: el sábado 14 abre uno nuevo y no hereda combos
    assert engine._sabado_ciclo('2026-11-14') == '2026-11-14'
    assert engine._sabado_ciclo('2026-11-13') == '2026-11-07'
