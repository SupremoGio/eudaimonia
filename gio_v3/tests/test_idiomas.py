"""
test_idiomas.py — handoff Cosmopolitismo v2 (/idiomas/).

Sprint 1: XP por repaso (una vez por ronda) y journal (una vez al día) con el
touch de Acta sin duplicar, plan real (hecho/atraso/siguiente checkpoint),
vencidas, revisar y guardar (LanguageTool caído → score NULL), palabra del
día al repaso, prompt por fase. Sprint 2–4: página y lateral.
"""
import sys, os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from utils import today_date, today_str
from data import QUIZ_EN, QUIZ_FR
from modules.idiomas import routes as ir

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOY = today_date()


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as s:
        s['app_ok'] = True
    return c


def _logs(key):
    with database.get_db() as db:
        return db.execute("SELECT COUNT(*) c FROM activity_logs WHERE activity_key=? AND date=?", (key, today_str())).fetchone()['c']


def _xp_total():
    with database.get_db() as db:
        return db.execute("SELECT COALESCE(SUM(amount),0) s FROM xp_ledger").fetchone()['s']


def _ronda(client, aciertos, rid, lang='en'):
    pool = QUIZ_EN if lang == 'en' else QUIZ_FR
    qs = pool[:5]
    ans = [{'selected': q['answer'] if i < aciertos else (q['answer'] + 1) % 4} for i, q in enumerate(qs)]
    return client.post('/idiomas/api/quiz/check', json={'questions': qs, 'answers': ans, 'lang': lang, 'round_id': rid}).get_json()


@pytest.fixture
def lt_caido(monkeypatch):
    def _boom(*a, **k):
        raise OSError('sin red')
    monkeypatch.setattr(ir, '_call_languagetool', _boom)


@pytest.fixture
def lt_ok(monkeypatch):
    def _fake(text, language='en-US'):
        i = text.index('has became')
        return {'matches': [{'offset': i, 'length': 10, 'replacements': [{'value': 'has become'}],
                             'shortMessage': 'Participio', 'rule': {'issueType': 'grammar'}}]}
    monkeypatch.setattr(ir, '_call_languagetool', _fake)


# ── Sprint 1 ─────────────────────────────────────────────────────────────────

def test_repaso_da_xp_una_vez_por_ronda_y_marca_acta(client):
    r = _ronda(client, 3, 'r1')
    assert r['score'] == 3 and r['xp'] >= 6 and r['proximos'] == {'manana': 2, 'espaciadas': 3}
    assert {x['dias'] for x in r['results'] if not x['correct']} == {1}
    assert _logs('idiomas_repaso') == 1 and r['acta']['hechos'] == 1
    xp = _xp_total()
    d = _ronda(client, 3, 'r1')                                   # misma ronda: no duplica
    assert d['duplicada'] and d['xp'] == 0 and _xp_total() == xp and _logs('idiomas_repaso') == 1
    r2 = _ronda(client, 2, 'r2')                                  # otra ronda: su XP, sin otro touch
    assert r2['xp'] >= 4 and _logs('idiomas_repaso') == 1 and _logs('idiomas_repaso_ronda') == 1
    assert _xp_total() > xp


def test_journal_xp_una_vez_al_dia(client, lt_ok):
    t = 'Remote work has became more common than ever.'
    r = client.post('/idiomas/api/journal/revisar', json={'text': t, 'lang': 'en'}).get_json()
    assert r['ok'] and r['lt_ok'] and r['score'] == 93 and r['grade'] == 'C2' and r['xp'] >= 5
    assert r['entrada']['correcciones'][0]['suggestion'] == 'has become' and r['entrada']['score'] == 93
    assert r['entrada']['fase'] == 1 and r['entrada']['language'] == 'English'
    r2 = client.post('/idiomas/api/journal/revisar', json={'text': t, 'lang': 'en'}).get_json()
    assert r2['ok'] and r2['xp'] == 0 and _logs('idiomas_journal') == 1
    assert r2['journal']['tendencia'] == [93, 93] and r2['journal']['total'] == 2


def test_touch_marcado_a_mano_no_se_duplica(client, lt_ok):
    client.post('/actividades/api/activity/log', json={'key': 'idiomas_journal'})
    assert _logs('idiomas_journal') == 1
    r = client.post('/idiomas/api/journal/revisar', json={'text': 'It has became late.', 'lang': 'en'}).get_json()
    assert r['xp'] == 0 and _logs('idiomas_journal') == 1


def test_revisar_con_languagetool_caido_guarda_score_null(client, lt_caido):
    r = client.post('/idiomas/api/journal/revisar', json={'text': 'Bonjour à tous.', 'lang': 'fr'}).get_json()
    assert r['ok'] and not r['lt_ok'] and r['aviso'] and r['score'] is None
    with database.get_db() as db:
        row = db.execute("SELECT * FROM lang_journal WHERE id=?", (r['entrada']['id'],)).fetchone()
    assert row['score'] is None and row['language'] == 'Français' and row['feedback'] == ''
    # el endpoint viejo sigue igual
    assert client.post('/idiomas/api/language/feedback', json={'text': 'x'}).status_code == 503


def test_plan_hecho_atraso_y_siguiente(client):
    p = client.get('/idiomas/api/plan').get_json()
    assert p['hecho_pct'] == 0 and p['atraso_pts'] == p['progreso_pct']
    assert p['siguiente_cp']['semana_fin'] == 6 and p['siguiente_cp']['semanas_restantes'] == 5
    with database.get_db() as db:
        db.execute("UPDATE lang_plan_checkpoints SET completado=1 WHERE fase IN (1,2)")
        db.commit()
    p = client.get('/idiomas/api/plan').get_json()
    assert p['hecho_pct'] == 50 and p['atraso_pts'] == 0                # adelantado
    assert p['siguiente_cp']['titulo'] == 'Producción y automatización'


def test_due_y_palabra_al_repaso(client):
    assert client.get('/idiomas/api/quiz/due?lang=en').get_json() == {'vencidas': 0}
    w = client.get('/idiomas/api/word?lang=en').get_json()
    assert w['word'] and not w['en_repaso']
    r = client.post('/idiomas/api/word/srs', json={'lang': 'en'}).get_json()
    assert r['ok'] and r['next_review'] == (HOY + timedelta(days=1)).isoformat()
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM lang_vocab_srs WHERE word=? AND language='en'", (w['word'],)).fetchone()[0] == 1
        db.execute("UPDATE lang_vocab_srs SET next_review=?", (today_str(),))
        db.commit()
    assert client.get('/idiomas/api/quiz/due?lang=en').get_json() == {'vencidas': 1}
    q = client.get('/idiomas/api/quiz?lang=en').get_json()
    assert w['word'] in [x['word'] for x in q['questions']] and q['vencidas'] == 1
    assert client.get('/idiomas/api/word?lang=en').get_json()['en_repaso']
    both = client.get('/idiomas/api/word').get_json()
    assert set(both) == {'en', 'fr'} and both['fr']['word'] in [x['word'] for x in QUIZ_FR]


def test_quiz_etiquetas(client):
    _ronda(client, 0, 'x')                                          # 5 falladas → vencen mañana
    with database.get_db() as db:
        db.execute("UPDATE lang_vocab_srs SET next_review=?, last_seen=?", (today_str(), (HOY - timedelta(days=3)).isoformat()))
        db.commit()
    q = client.get('/idiomas/api/quiz?lang=en').get_json()
    tags = {x['word']: x['tag'] for x in q['questions']}
    assert q['vencidas'] == 5 and all(t == 'vencida · fallaste hace 3 d' for t in tags.values())


def test_prompt_por_fase(client):
    p = client.get('/idiomas/api/journal/prompt?lang=fr&fase=2').get_json()
    assert p['fase'] == 2 and p['prompt'] in ir._PROMPTS['fr'][2]
    assert client.get('/idiomas/api/journal/prompt?lang=en').get_json()['fase'] == 1


def test_migracion_idempotente(test_db):
    database.init_db()
    database.init_db()
    with database.get_db() as db:
        assert [r['name'] for r in db.execute("PRAGMA table_info(lang_journal)")].count('score') == 1
        assert db.execute("SELECT COUNT(*) FROM activity_defs WHERE key IN ('idiomas_repaso','idiomas_journal') AND pillar='cosmo'").fetchone()[0] == 2


# ── Sprint 4: tests por destreza y Acta ──────────────────────────────────────

def test_parse_score():
    assert ir.parse_score('7.5', 'en') == 7.5 and ir.parse_score('58/100', 'fr') == 14.5
    assert ir.parse_score('14/25', 'fr') == 14 and ir.parse_score('62', 'fr') == 15.5
    assert ir.parse_score('B2', 'en') is None and ir.parse_score('12', 'en') is None


def test_ultimo_por_destreza(client):
    for tipo, idioma, d, score, f in (('IELTS', 'English', 'Writing', '5.5', '2026-01-01'), ('IELTS', 'English', 'Writing', '6.0', '2026-03-01'),
                                      ('IELTS', 'English', 'Listening', '7.5', '2026-03-01'), ('IELTS', 'English', 'Reading', 'pendiente', '2026-04-01'),
                                      ('DALF C1', '', 'Writing', '44/100', '2026-02-01')):
        client.post('/idiomas/api/test', json={'test_type': tipo, 'idioma': idioma, 'destreza': d, 'score': score, 'test_date': f})
    en = client.get('/idiomas/api/tests/destrezas?lang=en').get_json()
    assert [(s['destreza'], s['valor'], s['ok']) for s in en['skills']] == [('Listening', 7.5, True), ('Writing', 6.0, False)]
    assert en['brecha'] == 'Writing' and en['meta'] == 7.0
    fr = client.get('/idiomas/api/tests/destrezas?lang=fr').get_json()
    assert fr['skills'][0]['nombre'] == 'Prod. écrite' and fr['skills'][0]['valor'] == 11 and fr['titulo'].startswith('DALF')


def test_acta_sube_con_repaso_y_journal(client, lt_ok):
    a0 = client.get('/idiomas/api/estado?lang=en').get_json()['acta']
    _ronda(client, 5, 'z')
    client.post('/idiomas/api/journal/revisar', json={'text': 'It has became late.', 'lang': 'en'})
    a = client.get('/idiomas/api/estado?lang=en').get_json()['acta']
    assert a['total'] == a0['total'] and a['hechos'] == a0['hechos'] + 2


# ── Sprint 2–4: página ───────────────────────────────────────────────────────

def test_pagina_principal(client):
    html = client.get('/idiomas/').get_data(as_text=True)
    for fuera in ('id-lead', 'js-word', 'id="j-lang"', 'id="j-fase"', 'id="j-destreza"', 'js-fb', 'Feedback real', 'Guardar entrada',
                  'Verificar respuestas', 'EN → FR', 'id-ring', 'id="tt-score" placeholder="7.5"></div>\n        <div'):
        assert fuera not in html, fuera
    for dentro in ('id="id-lang"', 'data-lang="en"', 'data-lang="fr"', 'Repaso de hoy', 'Revisar y guardar', 'Palabra del día',
                   'Añadir a repaso', 'Cosmopolitismo en Acta Diurna', 'href="/idiomas/?vista=plan"', 'href="/idiomas/?vista=tests"',
                   'id="m-test"', 'Writing journal'):
        assert dentro in html, dentro
    assert html.count('Revisar y guardar') == 1 and html.count('<select class="eu-select" id="tt-idioma">') == 1   # solo en el modal
    js = open(os.path.join(BASE, 'static/js/idiomas.js'), encoding='utf-8').read()
    assert "'id_lang'" in js and "'/quiz/check'" in js and "'/journal/revisar'" in js and '/word/refresh' not in js
    assert '/language/feedback' not in js and js.count("jpost(API + '/quiz/check'") == 1


def test_vistas(client, lt_ok):
    client.post('/idiomas/api/journal/revisar', json={'text': 'Remote work has became common.', 'lang': 'en'})
    client.post('/idiomas/api/test', json={'test_type': 'IELTS', 'idioma': 'English', 'destreza': 'Writing', 'score': '6.5'})
    assert 'id="plan-cps"' in client.get('/idiomas/?vista=plan').get_data(as_text=True)
    t = client.get('/idiomas/?vista=tests').get_data(as_text=True)
    assert 'js-del-test' in t and '6.5' in t and 'id="id-lang"' not in t
    j = client.get('/idiomas/?vista=journal').get_data(as_text=True)
    assert 'has become' in j and 'fase 1' in j and '<b class="fg-brand">93</b>' in j
