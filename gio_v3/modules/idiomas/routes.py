from flask import Blueprint, render_template, request, jsonify
from database import get_db
from data import get_word_of_day, get_random_word
from datetime import date, datetime

idiomas_bp = Blueprint('idiomas', __name__, template_folder='../../templates')


@idiomas_bp.route('/')
def index():
    with get_db() as db:
        tests   = db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC").fetchall()
        journal = db.execute("SELECT * FROM lang_journal ORDER BY entry_date DESC LIMIT 20").fetchall()
    return render_template('idiomas/index.html',
        word=get_word_of_day(), tests=tests, journal=journal,
        today=date.today().isoformat(),
    )


# ── Tests ──────────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/test', methods=['POST'])
def add_test():
    d = request.json
    if not d.get('test_type') or not d.get('score'):
        return jsonify({'error': 'test_type and score required'}), 400
    with get_db() as db:
        db.execute("""INSERT INTO lang_test_results
            (test_type, score, notes, test_date, created_at) VALUES (?,?,?,?,?)""",
            (d['test_type'], str(d['score']), d.get('notes',''),
             d.get('test_date', date.today().isoformat()), datetime.now().isoformat()))
        db.commit()
        rows = db.execute("SELECT * FROM lang_test_results ORDER BY test_date DESC").fetchall()
    return jsonify({'ok':True, 'tests':[dict(r) for r in rows]})


@idiomas_bp.route('/api/test/<int:tid>', methods=['DELETE'])
def delete_test(tid):
    with get_db() as db:
        db.execute("DELETE FROM lang_test_results WHERE id=?", (tid,))
        db.commit()
    return jsonify({'ok':True})


# ── Journal ────────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/journal', methods=['POST'])
def add_journal():
    d = request.json
    if not d.get('entry_text'): return jsonify({'error':'empty'}), 400
    with get_db() as db:
        db.execute("""INSERT INTO lang_journal
            (language, entry_text, feedback, entry_date, created_at) VALUES (?,?,?,?,?)""",
            (d.get('language','English'), d['entry_text'], '',
             date.today().isoformat(), datetime.now().isoformat()))
        db.commit()
        rows = db.execute("SELECT * FROM lang_journal ORDER BY entry_date DESC LIMIT 20").fetchall()
    return jsonify({'ok':True, 'journal':[dict(r) for r in rows]})


@idiomas_bp.route('/api/journal/<int:jid>', methods=['DELETE'])
def delete_journal(jid):
    with get_db() as db:
        db.execute("DELETE FROM lang_journal WHERE id=?", (jid,))
        db.commit()
    return jsonify({'ok':True})


# ── Feedback (mock — ready for LanguageTool/Grammarly integration) ─────────

@idiomas_bp.route('/api/language/feedback', methods=['POST'])
def language_feedback():
    """
    Mock feedback endpoint.
    Future: integrate with LanguageTool API (https://languagetool.org/http-api/)
    POST { text: "...", language: "en-US" }
    Returns simulated corrections for now.
    """
    text     = request.json.get('text','')
    language = request.json.get('language','en-US')

    # Simulated feedback rules (replace with real API call)
    corrections = []
    checks = [
        ("i ", "I ",       "Always capitalize the pronoun 'I'."),
        ("dont",  "don't", "Missing apostrophe in contraction."),
        ("cant",  "can't", "Missing apostrophe in contraction."),
        ("wont",  "won't", "Missing apostrophe in contraction."),
        ("its a", "it's a","Possible contraction needed: it's = it is."),
    ]
    for wrong, right, msg in checks:
        if wrong in text.lower():
            corrections.append({"issue": wrong, "suggestion": right, "message": msg})

    # Score simulation
    score = max(0, 100 - len(corrections) * 15)
    grade = "C1" if score >= 85 else ("B2" if score >= 70 else ("B1" if score >= 55 else "A2"))

    return jsonify({
        "ok": True,
        "score": score,
        "grade": grade,
        "corrections": corrections,
        "word_count": len(text.split()),
        "note": "Simulated feedback — LanguageTool API integration ready.",
    })


# ── Word of day ────────────────────────────────────────────────────────────

@idiomas_bp.route('/api/word/refresh')
def word_refresh():
    return jsonify(get_random_word())
