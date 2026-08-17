import random
from flask import Blueprint, render_template, request, jsonify
from database import get_db
from data import get_word_of_day, get_random_word, get_quiz_questions, QUIZ_EN, QUIZ_FR
from datetime import date, datetime, timedelta
import urllib.request, urllib.parse, json
from utils import today_str, today_date

idiomas_bp = Blueprint('idiomas', __name__, template_folder='../../templates')

_LANG_MAP = {
    'English': 'en-US', 'Français': 'fr-FR',
    'Español': 'es',    'Deutsch':  'de-DE',
}

_PLAN_START_KEY = 'idiomas_plan_inicio'
_PLAN_TOTAL_SEMANAS = 26


@idiomas_bp.route('/')
def index():
    with get_db() as db:
        tests   = db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC").fetchall()
        journal = db.execute("SELECT * FROM lang_journal ORDER BY entry_date DESC LIMIT 20").fetchall()
    return render_template('idiomas/index.html',
        word=get_word_of_day(), tests=tests, journal=journal,
        today=today_str())


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
        result  = _call_languagetool(text, lt_lang)
        matches = result.get('matches', [])
    except Exception:
        return jsonify({
            'ok': False,
            'error': 'No se pudo conectar con LanguageTool. Intenta de nuevo.',
        }), 503

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

    word_count = len(text.split())
    score      = max(0, 100 - len(matches) * 7)
    grade      = ('C2' if score >= 93 else 'C1' if score >= 82
                  else 'B2' if score >= 70 else 'B1' if score >= 55 else 'A2')

    return jsonify({
        'ok':           True,
        'score':        score,
        'grade':        grade,
        'corrections':  corrections,
        'word_count':   word_count,
        'total_issues': len(matches),
        'source':       'LanguageTool',
    })


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


@idiomas_bp.route('/api/quiz')
def get_quiz():
    lang = request.args.get('lang', 'en')
    pool = QUIZ_EN if lang == 'en' else QUIZ_FR
    hoy = today_str()
    with get_db() as db:
        due_words = {
            r['word'] for r in db.execute(
                "SELECT word FROM lang_vocab_srs WHERE language=? AND next_review<=?", (lang, hoy)
            ).fetchall()
        }
    vencidas = [q for q in pool if q['word'] in due_words]
    resto    = [q for q in pool if q['word'] not in due_words]
    random.shuffle(vencidas)
    random.shuffle(resto)
    questions = (vencidas + resto)[:5]
    random.shuffle(questions)
    return jsonify({'ok': True, 'questions': questions, 'lang': lang, 'repasando': len(vencidas)})


@idiomas_bp.route('/api/quiz/check', methods=['POST'])
def check_quiz():
    body      = request.json or {}
    questions = body.get('questions', [])
    answers   = body.get('answers', [])
    lang      = body.get('lang', 'en')
    score     = 0
    results   = []
    hoy = today_date()
    with get_db() as db:
        for q, a in zip(questions, answers):
            correct = a.get('selected') == q.get('answer')
            if correct:
                score += 1
            _srs_actualizar(db, q['word'], lang, correct, hoy)
            results.append({
                'word':    q['word'],
                'correct': correct,
                'selected': a.get('selected'),
                'answer':  q['answer'],
                'options': q['options'],
                'example': q.get('example', ''),
            })
        db.commit()
    return jsonify({'ok': True, 'score': score, 'total': len(questions), 'results': results})


# ── Word of day ───────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/word/refresh')
def word_refresh():
    return jsonify(get_random_word())


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

    return jsonify({
        'inicio':         inicio,
        'semana_actual':  min(semana_actual, _PLAN_TOTAL_SEMANAS),
        'total_semanas':  _PLAN_TOTAL_SEMANAS,
        'fase_actual':    fase_actual,
        'progreso_pct':   min(100, round(semana_actual / _PLAN_TOTAL_SEMANAS * 100)),
        'checkpoints':    checkpoints,
    })


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
