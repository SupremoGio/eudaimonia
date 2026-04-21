from flask import Blueprint, render_template, request, jsonify
from database import get_db
from data import get_word_of_day, get_random_word, get_quiz_questions
from datetime import date, datetime
import urllib.request, urllib.parse, json

idiomas_bp = Blueprint('idiomas', __name__, template_folder='../../templates')

_LANG_MAP = {
    'English': 'en-US', 'Français': 'fr-FR',
    'Español': 'es',    'Deutsch':  'de-DE',
}


@idiomas_bp.route('/')
def index():
    with get_db() as db:
        tests   = db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC").fetchall()
        journal = db.execute("SELECT * FROM lang_journal ORDER BY entry_date DESC LIMIT 20").fetchall()
    return render_template('idiomas/index.html',
        word=get_word_of_day(), tests=tests, journal=journal,
        today=date.today().isoformat())


# ── Tests ──────────────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/test', methods=['POST'])
def add_test():
    d = request.json
    if not d.get('test_type') or not d.get('score'):
        return jsonify({'error': 'test_type and score required'}), 400
    with get_db() as db:
        db.execute("""INSERT INTO lang_test_results
            (test_type, score, notes, test_date, created_at) VALUES (?,?,?,?,?)""",
            (d['test_type'], str(d['score']), d.get('notes', ''),
             d.get('test_date', date.today().isoformat()), datetime.now().isoformat()))
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
            (language, entry_text, feedback, entry_date, created_at) VALUES (?,?,?,?,?)""",
            (d.get('language', 'English'), d['entry_text'], '',
             date.today().isoformat(), datetime.now().isoformat()))
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


# ── Quiz C1 ───────────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/quiz')
def get_quiz():
    lang = request.args.get('lang', 'en')
    questions = get_quiz_questions(lang, 5)
    return jsonify({'ok': True, 'questions': questions, 'lang': lang})


@idiomas_bp.route('/api/quiz/check', methods=['POST'])
def check_quiz():
    body      = request.json or {}
    questions = body.get('questions', [])
    answers   = body.get('answers', [])
    score     = 0
    results   = []
    for q, a in zip(questions, answers):
        correct = a.get('selected') == q.get('answer')
        if correct:
            score += 1
        results.append({
            'word':    q['word'],
            'correct': correct,
            'selected': a.get('selected'),
            'answer':  q['answer'],
            'options': q['options'],
            'example': q.get('example', ''),
        })
    return jsonify({'ok': True, 'score': score, 'total': len(questions), 'results': results})


# ── Word of day ───────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/word/refresh')
def word_refresh():
    return jsonify(get_random_word())
