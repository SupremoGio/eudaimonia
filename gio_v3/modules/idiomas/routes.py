import random, uuid
from flask import Blueprint, render_template, request, jsonify
from database import get_db
from data import get_word_of_day, get_random_word, QUIZ_EN, QUIZ_FR, WORDS
from datetime import date, datetime, timedelta
import urllib.request, urllib.parse, json
from utils import today_str, today_date
import modules.gamification.engine as engine
from modules.actividades.touch import marcar_touch, touches_hoy

idiomas_bp = Blueprint('idiomas', __name__, template_folder='../../templates')

_LANG_MAP = {
    'English': 'en-US', 'Français': 'fr-FR',
    'Español': 'es',    'Deutsch':  'de-DE',
}

_PLAN_START_KEY = 'idiomas_plan_inicio'
_PLAN_TOTAL_SEMANAS = 26

# Un solo selector de idioma para toda la página: 'en' | 'fr'
_LANG_NOMBRE = {'en': 'English', 'fr': 'Français'}
_REPASO_KEY, _REPASO_RONDA_KEY, _JOURNAL_KEY = 'idiomas_repaso', 'idiomas_repaso_ronda', 'idiomas_journal'
_XP_POR_ACIERTO = 2

# Destrezas de los tests: IELTS (banda 0–9, meta C1 7.0) y DALF (épreuves /25, meta 14)
_DESTREZAS = ['Listening', 'Reading', 'Writing', 'Speaking']
_TEST_CFG = {
    'en': {'titulo': 'IELTS · por destreza', 'max': 9, 'meta': 7.0,
           'nombres': {'Listening': 'Listening', 'Reading': 'Reading', 'Writing': 'Writing', 'Speaking': 'Speaking'}},
    'fr': {'titulo': 'DALF C1 · por épreuve', 'max': 25, 'meta': 14,
           'nombres': {'Listening': 'Compréh. orale', 'Reading': 'Compréh. écrite', 'Writing': 'Prod. écrite', 'Speaking': 'Prod. orale'}},
}

# Prompts del journal por fase del plan (uno por día, rota con la fecha)
_PROMPTS = {
    'en': {
        1: ['Describe your morning routine and one habit you want to change.',
            'Write about a mistake you made recently and what you learned.',
            'Explain your job to someone who has never heard of it.'],
        2: ['Argue for or against remote work in 150 words.',
            'Summarise an article you read this week and give your opinion.',
            'Compare two cities you know: which would you live in and why?'],
        3: ['Write a formal email complaining about a delayed order.',
            'Should governments tax sugary drinks? Defend your position.',
            'Discuss the advantages and drawbacks of social media for teenagers.'],
        4: ['IELTS Task 2: Some people believe university should be free. Discuss both views.',
            'Write a report on how people in your country spend their free time.',
            'To what extent is technology making us less creative?'],
    },
    'fr': {
        1: ['Décrivez votre routine du matin et une habitude que vous voulez changer.',
            'Racontez une erreur récente et ce que vous en avez appris.',
            'Expliquez votre métier à quelqu\'un qui ne le connaît pas.'],
        2: ['Donnez votre avis sur le télétravail en 150 mots.',
            'Résumez un article lu cette semaine et donnez votre opinion.',
            'Comparez deux villes que vous connaissez : où aimeriez-vous vivre ?'],
        3: ['Rédigez un courriel formel pour vous plaindre d\'une commande en retard.',
            'Faut-il taxer les boissons sucrées ? Défendez votre position.',
            'Les réseaux sociaux : avantages et inconvénients pour les adolescents.'],
        4: ['DALF C1 : synthèse — la gratuité de l\'université, pour ou contre ?',
            'Rédigez un rapport sur les loisirs dans votre pays.',
            'Dans quelle mesure la technologie nous rend-elle moins créatifs ?'],
    },
}


def _lang():
    l = (request.args.get('lang') or (request.get_json(silent=True) or {}).get('lang') or 'en').lower()
    if l in ('english', 'en-us'):
        return 'en'
    if l in ('français', 'francais', 'fr-fr'):
        return 'fr'
    return l if l in _LANG_NOMBRE else 'en'


@idiomas_bp.route('/')
def index():
    vista = request.args.get('vista', '')
    with get_db() as db:
        tests   = db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC, id DESC").fetchall()
        journal = db.execute("SELECT * FROM lang_journal ORDER BY entry_date DESC, id DESC LIMIT 200").fetchall()
    return render_template('idiomas/index.html',
        vista=vista if vista in ('plan', 'tests', 'journal') else '',
        tests=tests, journal=[_entrada(r) for r in journal], today=today_str())


# ── Tests ──────────────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/test', methods=['POST'])
def add_test():
    d = request.json
    if not d.get('test_type') or not d.get('score'):
        return jsonify({'error': 'test_type and score required'}), 400
    with get_db() as db:
        db.execute("""INSERT INTO lang_test_results
            (test_type, score, notes, test_date, created_at, idioma, destreza) VALUES (?,?,?,?,?,?,?)""",
            (d['test_type'], str(d['score']), d.get('notes', ''),
             d.get('test_date', today_str()), datetime.now().isoformat(),
             d.get('idioma', ''), d.get('destreza', '')))
        db.commit()
        rows = db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC").fetchall()
    return jsonify({'ok': True, 'tests': [dict(r) for r in rows]})


@idiomas_bp.route('/api/test/<int:tid>', methods=['DELETE'])
def delete_test(tid):
    with get_db() as db:
        db.execute("DELETE FROM lang_test_results WHERE id=?", (tid,))
        db.commit()
    return jsonify({'ok': True})


# ── Journal ────────────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/journal', methods=['POST'])
def add_journal():
    d = request.json
    if not d.get('entry_text'):
        return jsonify({'error': 'empty'}), 400
    with get_db() as db:
        db.execute("""INSERT INTO lang_journal
            (language, entry_text, feedback, entry_date, created_at, fase, destreza) VALUES (?,?,?,?,?,?,?)""",
            (d.get('language', 'English'), d['entry_text'], '',
             today_str(), datetime.now().isoformat(),
             d.get('fase') or None, d.get('destreza', '')))
        db.commit()
        rows = db.execute("SELECT * FROM lang_journal ORDER BY entry_date DESC LIMIT 20").fetchall()
    return jsonify({'ok': True, 'journal': [dict(r) for r in rows]})


@idiomas_bp.route('/api/journal/<int:jid>', methods=['DELETE'])
def delete_journal(jid):
    with get_db() as db:
        db.execute("DELETE FROM lang_journal WHERE id=?", (jid,))
        db.commit()
    return jsonify({'ok': True})


# ── Feedback real via LanguageTool API ────────────────────────────────────────

def _call_languagetool(text, language='en-US'):
    url  = 'https://api.languagetool.org/v2/check'
    data = urllib.parse.urlencode({'text': text, 'language': language}).encode('utf-8')
    req  = urllib.request.Request(url, data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('Accept', 'application/json')
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


@idiomas_bp.route('/api/language/feedback', methods=['POST'])
def language_feedback():
    body     = request.json or {}
    text     = body.get('text', '').strip()
    language = body.get('language', 'English')
    lt_lang  = _LANG_MAP.get(language, 'en-US')

    if not text:
        return jsonify({'error': 'empty'}), 400

    try:
        a = _analizar(text, lt_lang)
    except Exception:
        return jsonify({
            'ok': False,
            'error': 'No se pudo conectar con LanguageTool. Intenta de nuevo.',
        }), 503
    return jsonify({'ok': True, **a, 'source': 'LanguageTool'})


def _nivel(score):
    return ('C2' if score >= 93 else 'C1' if score >= 82
            else 'B2' if score >= 70 else 'B1' if score >= 55 else 'A2')


def _analizar(text, lt_lang):
    """LanguageTool → correcciones, score (100 − 7 por error) y nivel estimado.
    Lanza excepción si LanguageTool no responde."""
    matches = _call_languagetool(text, lt_lang).get('matches', [])
    corrections = []
    for m in matches[:12]:
        fragment     = text[m['offset']: m['offset'] + m['length']]
        replacements = [r['value'] for r in m.get('replacements', [])[:3]]
        issue_type   = m.get('rule', {}).get('issueType', 'other')
        corrections.append({
            'issue':       fragment,
            'suggestion':  replacements[0] if replacements else '',
            'all_suggestions': replacements,
            'message':     m.get('shortMessage') or m.get('message', ''),
            'type':        issue_type,
        })

    score = max(0, 100 - len(matches) * 7)
    return {
        'score':        score,
        'grade':        _nivel(score),
        'corrections':  corrections,
        'word_count':   len(text.split()),
        'total_issues': len(matches),
    }


def _entrada(r):
    """Entrada del journal con sus correcciones guardadas (feedback JSON)."""
    e = dict(r)
    try:
        e['correcciones'] = json.loads(e.get('feedback') or '[]')
        if not isinstance(e['correcciones'], list):
            e['correcciones'] = []
    except (ValueError, TypeError):
        e['correcciones'] = []
    e['nivel'] = _nivel(e['score']) if e.get('score') is not None else None
    return e


def _journal_estado(db, lang):
    nombre = _LANG_NOMBRE[lang]
    rows = db.execute("SELECT * FROM lang_journal WHERE language=? ORDER BY entry_date DESC, id DESC LIMIT 5",
                      (nombre,)).fetchall()
    tend = [r['score'] for r in db.execute(
        "SELECT score FROM lang_journal WHERE language=? AND score IS NOT NULL ORDER BY entry_date DESC, id DESC LIMIT 6",
        (nombre,)).fetchall()][::-1]
    total = db.execute("SELECT COUNT(*) c FROM lang_journal WHERE language=?", (nombre,)).fetchone()['c']
    return {'entradas': [_entrada(r) for r in rows], 'tendencia': tend, 'total': total}


@idiomas_bp.route('/api/journal/revisar', methods=['POST'])
def journal_revisar():
    """Un solo «Revisar y guardar»: LanguageTool + guarda la entrada con sus
    correcciones (feedback JSON) y su score. Si LanguageTool falla, se guarda
    igual con score NULL y se avisa. +5 XP una vez al día (touch de Acta)."""
    d = request.get_json(silent=True) or {}
    text = (d.get('text') or d.get('entry_text') or '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'Escribe algo primero'}), 400
    lang = _lang()
    try:
        fase = int(d.get('fase')) if d.get('fase') else _plan_estado()['fase_actual']
    except (TypeError, ValueError):
        fase = None
    try:
        a = _analizar(text, _LANG_MAP[_LANG_NOMBRE[lang]])
        lt_ok = True
    except Exception:
        a, lt_ok = None, False
    with get_db() as db:
        jid = db.execute("""INSERT INTO lang_journal
            (language, entry_text, feedback, entry_date, created_at, fase, destreza, score) VALUES (?,?,?,?,?,?,?,?)""",
            (_LANG_NOMBRE[lang], text, json.dumps(a['corrections'], ensure_ascii=False) if a else '',
             today_str(), datetime.now().isoformat(), fase, d.get('destreza') or 'Escritura',
             a['score'] if a else None)).lastrowid
        db.commit()
        entrada = _entrada(db.execute("SELECT * FROM lang_journal WHERE id=?", (jid,)).fetchone())
    gam = marcar_touch(_JOURNAL_KEY)
    with get_db() as db:
        estado = _journal_estado(db, lang)
    return jsonify({
        'ok': True, 'lt_ok': lt_ok,
        'aviso': None if lt_ok else 'LanguageTool no respondió: la entrada se guardó sin revisión.',
        'entrada': entrada, 'score': a['score'] if a else None, 'grade': a['grade'] if a else None,
        'corrections': a['corrections'] if a else [], 'total_issues': a['total_issues'] if a else None,
        'word_count': len(text.split()),
        'xp': gam['xp'] if gam else 0, 'gam': gam, 'acta': touches_hoy('cosmo'),
        'journal': estado,
    })


@idiomas_bp.route('/api/journal/prompt')
def journal_prompt():
    lang = _lang()
    try:
        fase = int(request.args.get('fase') or 0) or _plan_estado()['fase_actual']
    except ValueError:
        fase = _plan_estado()['fase_actual']
    lista = _PROMPTS[lang].get(fase) or _PROMPTS[lang][1]
    return jsonify({'fase': fase, 'prompt': lista[today_date().toordinal() % len(lista)]})


# ── Quiz C1 — con repetición espaciada (SM-2 simplificado) ────────────────────
#
# El quiz ya no muestra 5 palabras al azar: prioriza las que están "vencidas"
# en lang_vocab_srs (next_review <= hoy) y solo rellena con nuevas si sobra
# espacio. Una palabra fallada vuelve a aparecer pronto; una acertada varias
# veces se espacia cada vez más — así el tiempo de repaso no se desperdicia
# en lo que ya se sabe.

_SRS_EASE_INICIAL = 2.3
_SRS_EASE_MIN     = 1.3
_SRS_EASE_MAX     = 2.8


def _srs_actualizar(db, word, lang, correct, hoy):
    row = db.execute(
        "SELECT * FROM lang_vocab_srs WHERE word=? AND language=?", (word, lang)
    ).fetchone()
    if row:
        interval, ease = row['interval_days'], row['ease']
        correct_count, wrong_count = row['correct_count'], row['wrong_count']
    else:
        interval, ease, correct_count, wrong_count = 1, _SRS_EASE_INICIAL, 0, 0

    if correct:
        interval = max(1, round(interval * ease))
        ease = min(_SRS_EASE_MAX, ease + 0.1)
        correct_count += 1
    else:
        interval = 1
        ease = max(_SRS_EASE_MIN, ease - 0.2)
        wrong_count += 1

    next_review = (hoy + timedelta(days=interval)).isoformat()
    db.execute("""
        INSERT INTO lang_vocab_srs
            (word, language, interval_days, ease, next_review, correct_count, wrong_count, last_seen)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(word, language) DO UPDATE SET
            interval_days=excluded.interval_days, ease=excluded.ease, next_review=excluded.next_review,
            correct_count=excluded.correct_count, wrong_count=excluded.wrong_count, last_seen=excluded.last_seen
    """, (word, lang, interval, ease, next_review, correct_count, wrong_count, hoy.isoformat()))


def _pool(lang):
    """Preguntas del quiz. En inglés incluye también las palabras del día que
    se añadieron al repaso (WORDS), con su significado entre 4 opciones."""
    if lang == 'fr':
        return list(QUIZ_FR)
    pool = list(QUIZ_EN)
    vistos = {q['word'] for q in pool}
    for w in WORDS:
        if w['word'] in vistos:
            continue
        rnd = random.Random(w['word'])
        otros = rnd.sample([x['meaning'] for x in WORDS if x['word'] != w['word']], 3)
        ops = otros + [w['meaning']]
        rnd.shuffle(ops)
        pool.append({'word': w['word'], 'question': f"What does '{w['word'].lower()}' mean?",
                     'options': ops, 'answer': ops.index(w['meaning']), 'example': w['example']})
    return pool


def _vencidas(db, lang, hoy=None):
    hoy = hoy or today_str()
    pool = {q['word'] for q in _pool(lang)}
    return [r for r in db.execute(
        "SELECT * FROM lang_vocab_srs WHERE language=? AND next_review<=?", (lang, hoy)).fetchall()
        if r['word'] in pool]


@idiomas_bp.route('/api/quiz')
def get_quiz():
    lang = _lang()
    pool = _pool(lang)
    hoy = today_str()
    with get_db() as db:
        srs = {r['word']: r for r in db.execute("SELECT * FROM lang_vocab_srs WHERE language=?", (lang,)).fetchall()}
    due_words = {w for w, r in srs.items() if r['next_review'] <= hoy}
    vencidas = [q for q in pool if q['word'] in due_words]
    resto    = [q for q in pool if q['word'] not in due_words and q['word'] not in srs]
    espaciadas = [q for q in pool if q['word'] in srs and q['word'] not in due_words]
    random.shuffle(vencidas)
    random.shuffle(resto)
    random.shuffle(espaciadas)
    questions = (vencidas + resto + espaciadas)[:5]
    random.shuffle(questions)
    hoy_d = today_date()
    out = []
    for q in questions:
        q = dict(q)
        r = srs.get(q['word'])
        if r is None:
            q['tag'], q['vuelve_ok'] = 'nueva', max(1, round(1 * 2.3))
        else:
            tag = 'vencida'
            if r['interval_days'] == 1 and r['wrong_count'] and r['last_seen']:
                dias = (hoy_d - date.fromisoformat(r['last_seen'])).days
                tag += f' · fallaste hace {dias} d' if dias > 0 else ' · fallaste hoy'
            q['tag'], q['vuelve_ok'] = tag, max(1, round(r['interval_days'] * r['ease']))
        out.append(q)
    return jsonify({'ok': True, 'questions': out, 'lang': lang, 'repasando': len(vencidas),
                    'vencidas': len(due_words & {q['word'] for q in pool})})


@idiomas_bp.route('/api/quiz/due')
def quiz_due():
    lang = _lang()
    with get_db() as db:
        return jsonify({'vencidas': len(_vencidas(db, lang))})


@idiomas_bp.route('/api/quiz/check', methods=['POST'])
def check_quiz():
    """Califica la ronda (las 5 respuestas en un solo POST), actualiza SM-2 y da
    2 XP por acierto una vez por ronda (round_id). La primera ronda del día
    marca el touch de Cosmopolitismo en Acta; las siguientes suman su XP aparte."""
    body      = request.json or {}
    questions = body.get('questions', [])
    answers   = body.get('answers', [])
    lang      = _lang()
    round_id  = str(body.get('round_id') or uuid.uuid4())
    hoy = today_date()
    with get_db() as db:
        prev = db.execute("SELECT * FROM lang_quiz_rounds WHERE round_id=?", (round_id,)).fetchone()
    if prev:
        return jsonify({'ok': True, 'duplicada': True, 'score': prev['score'], 'total': prev['total'],
                        'xp': 0, 'results': [], 'proximos': None, 'acta': touches_hoy('cosmo')})
    score, results = 0, []
    with get_db() as db:
        for q, a in zip(questions, answers):
            correct = a.get('selected') == q.get('answer')
            if correct:
                score += 1
            _srs_actualizar(db, q['word'], lang, correct, hoy)
            dias = db.execute("SELECT interval_days FROM lang_vocab_srs WHERE word=? AND language=?",
                              (q['word'], lang)).fetchone()['interval_days']
            results.append({
                'word':    q['word'],
                'correct': correct,
                'selected': a.get('selected'),
                'answer':  q['answer'],
                'options': q['options'],
                'example': q.get('example', ''),
                'dias':    dias,
            })
        xp = score * _XP_POR_ACIERTO
        db.execute("INSERT INTO lang_quiz_rounds (round_id, language, score, total, xp, date, created_at) VALUES (?,?,?,?,?,?,?)",
                   (round_id, lang, score, len(questions), xp, hoy.isoformat(), datetime.now().isoformat()))
        db.commit()
    gam = marcar_touch(_REPASO_KEY, pts=xp)
    if gam is None and xp > 0:
        with get_db() as db:
            log_id = db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                                (_REPASO_RONDA_KEY, hoy.isoformat(), xp)).lastrowid
            db.commit()
        gam = engine.process_activity(_REPASO_RONDA_KEY, xp, 'Idiomas', log_id, ec=0)
    manana = sum(1 for r in results if r['dias'] <= 1)
    with get_db() as db:
        quedan = len(_vencidas(db, lang))
    return jsonify({'ok': True, 'score': score, 'total': len(questions), 'results': results,
                    'xp': gam['xp'] if gam else 0, 'gam': gam if gam and gam.get('stats') else None,
                    'proximos': {'manana': manana, 'espaciadas': len(results) - manana},
                    'vencidas': quedan, 'acta': touches_hoy('cosmo'), 'round_id': round_id})


# ── Word of day ───────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/word/refresh')
def word_refresh():
    """En desuso: la palabra del día queda fija (sin ↻). Se conserva por compatibilidad."""
    return jsonify(get_random_word())


def palabra_del_dia(lang, db=None):
    """EN: la palabra del día (get_word_of_day). FR: una del banco francés del
    quiz, fija por fecha, con su significado en francés."""
    if lang == 'fr':
        q = QUIZ_FR[today_date().toordinal() % len(QUIZ_FR)]
        w = {'word': q['word'], 'phonetic': '', 'meaning': q['options'][q['answer']], 'example': q['example']}
    else:
        g = get_word_of_day()
        w = {'word': g['word'], 'phonetic': g['phonetic'], 'meaning': g['meaning'], 'example': g['example']}
    def _en(db):
        return bool(db.execute("SELECT 1 FROM lang_vocab_srs WHERE word=? AND language=?", (w['word'], lang)).fetchone())
    if db is not None:
        w['en_repaso'] = _en(db)
    else:
        with get_db() as d:
            w['en_repaso'] = _en(d)
    w['lang'] = lang
    return w


@idiomas_bp.route('/api/word')
def word_get():
    lang = request.args.get('lang')
    if lang in _LANG_NOMBRE:
        return jsonify(palabra_del_dia(lang))
    return jsonify({'en': palabra_del_dia('en'), 'fr': palabra_del_dia('fr')})


@idiomas_bp.route('/api/word/srs', methods=['POST'])
def word_srs():
    """Añade la palabra del día al repaso (lang_vocab_srs, vuelve mañana)."""
    lang = _lang()
    w = palabra_del_dia(lang)
    manana = (today_date() + timedelta(days=1)).isoformat()
    with get_db() as db:
        db.execute("""INSERT OR IGNORE INTO lang_vocab_srs (word, language, interval_days, ease, next_review,
                      correct_count, wrong_count, last_seen) VALUES (?,?,1,?,?,0,0,NULL)""",
                   (w['word'], lang, _SRS_EASE_INICIAL, manana))
        db.commit()
    return jsonify({'ok': True, 'word': w['word'], 'next_review': manana, 'en_repaso': True})


# ── Plan C1 · 26 semanas — fases y checkpoints ─────────────────────────────────

def _plan_inicio():
    with get_db() as db:
        row = db.execute("SELECT value FROM app_settings WHERE key=?", (_PLAN_START_KEY,)).fetchone()
        if row:
            return row['value']
        inicio = today_str()
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (_PLAN_START_KEY, inicio))
        db.commit()
    return inicio


@idiomas_bp.route('/api/plan')
def get_plan():
    return jsonify(_plan_estado())


def _plan_estado():
    inicio = _plan_inicio()
    inicio_date = datetime.strptime(inicio, '%Y-%m-%d').date()
    dias_transcurridos = (today_date() - inicio_date).days
    semana_actual = max(1, dias_transcurridos // 7 + 1)

    with get_db() as db:
        rows = db.execute("SELECT * FROM lang_plan_checkpoints ORDER BY fase").fetchall()

    checkpoints, fase_actual = [], None
    for r in rows:
        cp = dict(r)
        cp['fecha_objetivo'] = (inicio_date + timedelta(weeks=cp['semana_fin'])).isoformat()
        cp['vencido'] = (not cp['completado']) and semana_actual > cp['semana_fin']
        checkpoints.append(cp)
        if fase_actual is None and semana_actual <= cp['semana_fin']:
            fase_actual = cp['fase']
    if fase_actual is None:
        fase_actual = checkpoints[-1]['fase'] if checkpoints else 1

    progreso = min(100, round(semana_actual / _PLAN_TOTAL_SEMANAS * 100))
    hechos = sum(1 for c in checkpoints if c['completado'])
    hecho_pct = round(hechos / len(checkpoints) * 100) if checkpoints else 0
    sig = next((c for c in checkpoints if not c['completado']), None)
    fase_cp = next((c for c in checkpoints if c['fase'] == fase_actual), None)
    return {
        'inicio':         inicio,
        'semana_actual':  min(semana_actual, _PLAN_TOTAL_SEMANAS),
        'total_semanas':  _PLAN_TOTAL_SEMANAS,
        'fase_actual':    fase_actual,
        'fase_nombre':    fase_cp['nombre'] if fase_cp else '',
        'progreso_pct':   progreso,
        'hechos':         hechos,
        'hecho_pct':      hecho_pct,
        'atraso_pts':     max(0, progreso - hecho_pct),
        'siguiente_cp':   {'titulo': sig['nombre'], 'criterio': sig['criterio'], 'fase': sig['fase'],
                           'semana_fin': sig['semana_fin'],
                           'semanas_restantes': max(0, sig['semana_fin'] - semana_actual)} if sig else None,
        'checkpoints':    checkpoints,
    }


@idiomas_bp.route('/api/plan/checkpoint/<int:cid>', methods=['POST'])
def toggle_checkpoint(cid):
    d = request.json or {}
    completado = 1 if d.get('completado') else 0
    with get_db() as db:
        db.execute(
            "UPDATE lang_plan_checkpoints SET completado=?, completado_at=? WHERE id=?",
            (completado, datetime.now().isoformat() if completado else None, cid)
        )
        db.commit()
    return jsonify({'ok': True})


@idiomas_bp.route('/api/plan/reiniciar', methods=['POST'])
def reiniciar_plan():
    d = request.json or {}
    nueva_fecha = d.get('inicio') or today_str()
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (_PLAN_START_KEY, nueva_fecha))
        db.execute("UPDATE lang_plan_checkpoints SET completado=0, completado_at=NULL")
        db.commit()
    return jsonify({'ok': True})


# ── Tests por destreza (frente a la marca de C1) ───────────────────────────────

_TIPO_LANG = {'ielts': 'en', 'toefl': 'en', 'cambridge': 'en', 'dalf': 'fr', 'delf': 'fr'}


def _idioma_test(r):
    i = (r['idioma'] or '').lower()
    if i.startswith('eng'):
        return 'en'
    if i.startswith('fr'):
        return 'fr'
    t = (r['test_type'] or '').lower()
    return next((v for k, v in _TIPO_LANG.items() if k in t), None)


def parse_score(score, lang):
    """«7.5» → 7.5 (IELTS); «58/100» → 14.5 (DALF /25); «14/25» → 14.
    Devuelve None si no se puede convertir o no cae en la escala."""
    s = str(score or '').strip().replace(',', '.')
    try:
        if '/' in s:
            a, b = (float(x) for x in s.split('/', 1))
            if b <= 0:
                return None
            v = a / b * _TEST_CFG[lang]['max']
        else:
            v = float(s)
            if lang == 'fr' and 25 < v <= 100:
                v = v / 100 * 25
    except ValueError:
        return None
    if v < 0 or v > _TEST_CFG[lang]['max']:
        return None
    return round(v, 1)


def ultimo_por_destreza(db, lang):
    cfg = _TEST_CFG[lang]
    ult = {}
    for r in db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC, id DESC").fetchall():
        if _idioma_test(r) != lang or r['destreza'] not in _DESTREZAS or r['destreza'] in ult:
            continue
        v = parse_score(r['score'], lang)
        if v is not None:
            ult[r['destreza']] = {'valor': v, 'fecha': r['test_date'], 'tipo': r['test_type']}
    skills = [{'destreza': d, 'nombre': cfg['nombres'][d], 'max': cfg['max'], 'meta': cfg['meta'],
               **ult[d], 'ok': ult[d]['valor'] >= cfg['meta']} for d in _DESTREZAS if d in ult]
    brecha = min(skills, key=lambda x: x['valor'])['nombre'] if skills else None
    return {'titulo': cfg['titulo'], 'max': cfg['max'], 'meta': cfg['meta'], 'skills': skills, 'brecha': brecha}


@idiomas_bp.route('/api/tests/destrezas')
def tests_destrezas():
    with get_db() as db:
        return jsonify(ultimo_por_destreza(db, _lang()))


# ── Estado de la página por idioma (un solo selector filtra todo) ─────────────

@idiomas_bp.route('/api/estado')
def estado():
    lang = _lang()
    plan = _plan_estado()
    lista = _PROMPTS[lang].get(plan['fase_actual']) or _PROMPTS[lang][1]
    with get_db() as db:
        return jsonify({
            'lang': lang, 'plan': plan,
            'vencidas': len(_vencidas(db, lang)),
            'palabra': palabra_del_dia(lang, db),
            'prompt': lista[today_date().toordinal() % len(lista)],
            'tests': ultimo_por_destreza(db, lang),
            'journal': _journal_estado(db, lang),
            'acta': touches_hoy('cosmo'),
        })
