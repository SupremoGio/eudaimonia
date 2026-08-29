from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from database import get_db
from utils import today_str, today_date
import modules.gamification.engine as engine

eurythmia_bp = Blueprint('eurythmia', __name__, template_folder='../../templates')

# ── Fases fijas del bucle de práctica (reparto base 10/15/5 sobre 30 min) ────
PHASES = [
    {"id": "diso", "name": "Disociación corporal", "short": "Disociación", "hue": 330, "glyph": "∞",
     "principle": "Aislamiento motor",
     "desc": "Despierta y aísla cada segmento. Construyes los mapas motores que el casino necesita antes de moverte en conjunto."},
    {"id": "paso", "name": "Aprender paso o figura", "short": "Aprender paso", "hue": 45, "glyph": "♪",
     "principle": "Práctica deliberada",
     "desc": "Una sola figura. Repeticiones con foco y corrección — no volumen ciego. Fragmenta el paso y encadénalo."},
    {"id": "improv", "name": "Improvisación", "short": "Improvisación", "hue": 20, "glyph": "✦",
     "principle": "Práctica variable",
     "desc": "Recombina lo que sabes sin planear. Fuerzas el recuerdo y la transferencia — el paso deja de ser receta y se vuelve tuyo."},
]

# ── Niveles dancísticos por horas de práctica deliberada acumuladas ─────────
LEVELS = [
    {"n": 1, "name": "TIEMPO",     "sub": "Encuentra el uno",            "h": 5},
    {"n": 2, "name": "CASINERO",   "sub": "Base, guapea y dile que no",  "h": 20},
    {"n": 3, "name": "ENCHUFLERO", "sub": "Giros, enchuflas y vueltas",  "h": 50},
    {"n": 4, "name": "FIGUERO",    "sub": "Repertorio en pareja",        "h": 100},
    {"n": 5, "name": "SONERO",     "sub": "Musicalidad e improvisación", "h": 200},
    {"n": 6, "name": "RUMBERO",    "sub": "Cuerpo libre, despelote",     "h": 400},
]

FLOW_LABELS = ["—", "Trabado", "Mecánico", "Fluido", "En la música", "Despelote total"]

SCIENCE = [
    {"icon": "∞", "hue": 330, "tag": "Aprendizaje motor", "title": "Aislar antes de integrar",
     "body": "La disociación entrena control segmentario independiente. Los mapas motores de cada segmento (cadera, costillas, hombros) se construyen antes de que la coordinación compleja sea posible."},
    {"icon": "♪", "hue": 45, "tag": "Ericsson", "title": "Práctica deliberada",
     "body": "Repetir con foco estrecho, feedback inmediato y en el borde de tu capacidad produce mejora real. El volumen sin atención sólo automatiza errores."},
    {"icon": "✦", "hue": 20, "tag": "Shea & Morgan", "title": "Interferencia contextual",
     "body": "Improvisar y recuperar de memoria empeora el rendimiento de hoy pero dispara la retención y la transferencia a largo plazo frente a repetir en bloque."},
    {"icon": "◐", "hue": 200, "tag": "Efecto de espaciado", "title": "Consolidación y espaciado",
     "body": "El sueño y el espaciado convierten las repeticiones de hoy en automatismo mañana. Sesiones cortas y diarias superan a una sesión larga semanal."},
]

_GRABADO_KEY = "eurythmia_grabado"
_SESSION_KEY = "eurythmia_session"
_GRABADO_XP  = 3

# ── Música — 100 mejores álbumes ──────────────────────────────────────────────
_ALBUM_XP = 5
_ALBUM_EC = 2

RATING_DIMS = [
    {"key": "sonido",        "label": "Producción"},
    {"key": "letras",        "label": "Composición"},
    {"key": "consistencia",  "label": "Consistencia"},
    {"key": "replay",        "label": "Replay value"},
]


def _compute_mi_rating(row):
    vals = [row[f"rating_{d['key']}"] for d in RATING_DIMS if row[f"rating_{d['key']}"] is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def _musica_state():
    with get_db() as db:
        rows = db.execute("SELECT * FROM eury_albums ORDER BY rank").fetchall()
    albumes = [dict(r) for r in rows]
    escuchados = [a for a in albumes if a["escuchado"]]
    ranking = sorted(
        [a for a in escuchados if a["mi_rating"] is not None],
        key=lambda a: (-a["mi_rating"], a["rank"])
    )
    return {
        "albumes":       albumes,
        "total":         len(albumes),
        "escuchados_n":  len(escuchados),
        "ranking":       ranking,
    }


def _split_minutes(total):
    base, s = [10, 15, 5], 30
    mins = [max(1, round(b / s * total)) for b in base]
    diff = total - sum(mins)
    mins[1] = max(1, mins[1] + diff)
    return mins


def _level_from_minutes(total_min):
    hours = total_min / 60
    cur = LEVELS[-1]
    for lv in LEVELS:
        if hours < lv["h"]:
            cur = lv
            break
    idx = LEVELS.index(cur)
    prev_h = LEVELS[idx - 1]["h"] if idx > 0 else 0
    pct = (hours - prev_h) / (cur["h"] - prev_h) if cur["h"] > prev_h else 1
    return {
        "level": cur, "idx": idx,
        "pct": min(1, max(0, pct)),
        "hours_to_next": max(0, cur["h"] - hours),
    }


def _eury_streak():
    with get_db() as db:
        dates = {r["date"] for r in db.execute("SELECT DISTINCT date FROM eury_sessions").fetchall()}
    streak, check = 0, today_date()
    while check.isoformat() in dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


def _repertoire():
    with get_db() as db:
        rows = db.execute("SELECT * FROM eury_repertoire ORDER BY id").fetchall()
    libres = [dict(r) for r in rows if r["kind"] == "libres"]
    pareja = [dict(r) for r in rows if r["kind"] == "pareja"]
    return {"libres": libres, "pareja": pareja}


def _state():
    today = today_str()
    with get_db() as db:
        total_min = db.execute("SELECT COALESCE(SUM(min),0) as s FROM eury_sessions").fetchone()["s"]
        sessions_count = db.execute("SELECT COUNT(*) as c FROM eury_sessions").fetchone()["c"]
        log_rows = db.execute("SELECT * FROM eury_sessions ORDER BY id DESC LIMIT 30").fetchall()
        grabado_today = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (_GRABADO_KEY, today)
        ).fetchone() is not None

    log = [{
        "id": r["id"], "date": r["date"], "min": r["min"],
        "split": [r["split_diso"], r["split_paso"], r["split_improv"]],
        "step": r["step"], "flow": r["flow"], "improv": r["improv_note"],
        "xp": r["xp"], "grabado": bool(r["grabado"]),
    } for r in log_rows]

    days_practiced = len({r["date"] for r in log_rows}) if log_rows else 0
    avg_daily = round(total_min / max(1, days_practiced)) if days_practiced else 0

    return {
        "total_min": total_min,
        "sessions": sessions_count,
        "streak": _eury_streak(),
        "avg_daily": avg_daily,
        "level": _level_from_minutes(total_min),
        "repertoire": _repertoire(),
        "log": log,
        "grabado_today": grabado_today,
    }


# ── Rutas ─────────────────────────────────────────────────────────────────────

@eurythmia_bp.route('/')
def index():
    return render_template(
        'eurythmia/index.html',
        phases=PHASES, levels=LEVELS, flow_labels=FLOW_LABELS, science=SCIENCE,
        state=_state(),
        musica=_musica_state(),
        rating_dims=RATING_DIMS,
    )


@eurythmia_bp.route('/api/state')
def api_state():
    return jsonify(_state())


@eurythmia_bp.route('/api/split')
def api_split():
    try:
        total = int(request.args.get('min', 30))
    except (TypeError, ValueError):
        total = 30
    total = max(10, min(180, total))
    return jsonify({"split": _split_minutes(total)})


@eurythmia_bp.route('/api/session', methods=['POST'])
def api_session():
    data = request.get_json(silent=True) or {}
    try:
        minutes = int(data.get('min', 0))
        flow = int(data.get('flow', 3))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid'}), 400
    if minutes <= 0 or minutes > 300 or flow < 1 or flow > 5:
        return jsonify({'error': 'invalid'}), 400

    raw_split = data.get('split')
    if isinstance(raw_split, list) and len(raw_split) == 3 and all(isinstance(x, int) for x in raw_split):
        split = raw_split
    else:
        split = _split_minutes(minutes)

    step = str(data.get('step', ''))[:80]
    improv = str(data.get('improv', ''))[:500]
    grabado = bool(data.get('grabado'))

    xp = minutes + flow * 4
    today = today_str()
    now = datetime.now().isoformat()

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (_SESSION_KEY, today, xp)
        )
        log_id = cur.lastrowid
        cur2 = db.execute(
            "INSERT INTO eury_sessions (date, min, split_diso, split_paso, split_improv, step, flow, "
            "improv_note, xp, grabado, activity_log_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (today, minutes, split[0], split[1], split[2], step, flow, improv, xp, int(grabado), log_id, now)
        )
        session_id = cur2.lastrowid
        db.commit()

    gam = engine.process_activity(_SESSION_KEY, xp, 'Baile', log_id)

    grabado_gam = None
    if grabado:
        with get_db() as db:
            already = db.execute(
                "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (_GRABADO_KEY, today)
            ).fetchone()
            if not already:
                cur3 = db.execute(
                    "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                    (_GRABADO_KEY, today, _GRABADO_XP)
                )
                grabado_log_id = cur3.lastrowid
                db.commit()
                grabado_gam = engine.process_activity(_GRABADO_KEY, _GRABADO_XP, 'Baile', grabado_log_id)

    return jsonify({
        'ok': True, 'session_id': session_id, 'xp': xp,
        'gam': gam, 'grabado_gam': grabado_gam,
        'state': _state(),
    })


@eurythmia_bp.route('/api/grabado/toggle', methods=['POST'])
def api_grabado_toggle():
    today = today_str()
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (_GRABADO_KEY, today)
        ).fetchone()
        if existing:
            db.execute("DELETE FROM activity_logs WHERE id=?", (existing['id'],))
            db.commit()
            gam = engine.remove_activity(existing['id'])
            return jsonify({'action': 'removed', 'gam': gam, 'state': _state()})

        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (_GRABADO_KEY, today, _GRABADO_XP)
        )
        log_id = cur.lastrowid
        db.commit()

    gam = engine.process_activity(_GRABADO_KEY, _GRABADO_XP, 'Baile', log_id)
    return jsonify({'action': 'added', 'gam': gam, 'state': _state()})


@eurythmia_bp.route('/api/album/<int:album_id>', methods=['POST'])
def api_album_update(album_id):
    data = request.get_json(silent=True) or {}

    with get_db() as db:
        row = db.execute("SELECT * FROM eury_albums WHERE id=?", (album_id,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    row = dict(row)

    was_escuchado = bool(row['escuchado'])
    escuchado = bool(data.get('escuchado', was_escuchado))

    ratings = {}
    for d in RATING_DIMS:
        key = f"rating_{d['key']}"
        val = data.get(key, row[key])
        if val not in (None, ''):
            try:
                val = int(val)
            except (TypeError, ValueError):
                return jsonify({'error': f'invalid {key}'}), 400
            if val < 1 or val > 10:
                return jsonify({'error': f'invalid {key}'}), 400
        else:
            val = None
        ratings[key] = val

    mi_rating = _compute_mi_rating(ratings)
    notas = str(data.get('notas', row['notas']) or '')[:500]
    escuchado_at = row['escuchado_at']
    rating_cols = list(ratings.keys())
    rating_vals = [ratings[k] for k in rating_cols]

    gam = None
    with get_db() as db:
        if escuchado and not was_escuchado:
            escuchado_at = datetime.now().isoformat()
            today = today_str()
            cur = db.execute(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                (f"eury_album_{album_id}", today, _ALBUM_XP)
            )
            log_id = cur.lastrowid
            db.execute(
                f"UPDATE eury_albums SET escuchado=1, mi_rating=?, notas=?, escuchado_at=?, "
                f"{', '.join(f'{c}=?' for c in rating_cols)} WHERE id=?",
                (mi_rating, notas, escuchado_at, *rating_vals, album_id)
            )
            db.commit()
            gam = engine.process_activity(f"eury_album_{album_id}", _ALBUM_XP, 'Música', log_id, ec=_ALBUM_EC)
        elif not escuchado and was_escuchado:
            db.execute(
                f"UPDATE eury_albums SET escuchado=0, mi_rating=NULL, notas=?, escuchado_at=NULL, "
                f"{', '.join(f'{c}=NULL' for c in rating_cols)} WHERE id=?",
                (notas, album_id)
            )
            db.commit()
            log_row = db.execute(
                "SELECT id FROM activity_logs WHERE activity_key=? ORDER BY id DESC LIMIT 1",
                (f"eury_album_{album_id}",)
            ).fetchone()
            if log_row:
                db.execute("DELETE FROM activity_logs WHERE id=?", (log_row['id'],))
                db.commit()
                gam = engine.remove_activity(log_row['id'])
        else:
            db.execute(
                f"UPDATE eury_albums SET mi_rating=?, notas=?, "
                f"{', '.join(f'{c}=?' for c in rating_cols)} WHERE id=?",
                (mi_rating, notas, *rating_vals, album_id)
            )
            db.commit()

    return jsonify({'ok': True, 'gam': gam, 'musica': _musica_state()})


@eurythmia_bp.route('/api/drill', methods=['POST'])
def api_drill():
    data = request.get_json(silent=True) or {}
    step_key = data.get('step_key')
    with get_db() as db:
        row = db.execute("SELECT * FROM eury_repertoire WHERE step_key=?", (step_key,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        new_mastery = min(100, row['mastery'] + 3)
        new_reps = row['reps'] + 10
        db.execute(
            "UPDATE eury_repertoire SET mastery=?, reps=? WHERE step_key=?",
            (new_mastery, new_reps, step_key)
        )
        db.commit()
    return jsonify({'ok': True, 'step_key': step_key, 'mastery': new_mastery, 'reps': new_reps})
