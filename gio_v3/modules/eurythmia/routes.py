from flask import Blueprint, render_template, request, jsonify, redirect
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
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
_GRABADO_EC  = 1

# ── Racha de días bailando — bono único al alcanzar el hito (no se repite
# hasta que la racha se rompe y se vuelve a formar otra vez) ────────────────
_STREAK_EC_BONUS = {3: 2, 7: 3, 14: 5, 30: 8}


def _session_ec(minutes, flow):
    """EC de una sesión de práctica: antes era 1 fijo sin importar duración o
    fluidez. Ahora premia la calidad del movimiento (flow, 1-5, ya capturado
    en cada sesión) y la dedicación (sesiones largas), en vez de dar lo mismo
    por 10 minutos trabados que por 45 en la música."""
    ec = 0
    if flow >= 5:
        ec += 2      # despelote total
    elif flow >= 3:
        ec += 1      # fluido / en la música
    if minutes >= 45:
        ec += 1      # sesión larga, dedicación real
    return ec


def _maybe_award_dance_streak(streak, today):
    """Bono de EC al alcanzar un hito de racha de días bailando seguidos.
    Se da una sola vez el día en que se alcanza cada hito (dedupe por fecha)."""
    bonus_ec = _STREAK_EC_BONUS.get(streak)
    if not bonus_ec:
        return None
    key = f"eurythmia_streak_{streak}"
    with get_db() as db:
        if db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (key, today)
        ).fetchone():
            return None
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (key, today, 0)
        )
        log_id = cur.lastrowid
        db.commit()
    return engine.process_activity(key, 0, 'Baile', log_id, ec=bonus_ec)


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


# ── Eurythmia v2: espaciado, dominio por sesión, semana y bonos ─────────────

SIN_PRACTICA_DIAS = 30        # un paso sin last_practiced cuenta como 30 días
META_SEMANA = 4


def _norm(t):
    t = unicodedata.normalize('NFKD', (t or '').lower())
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in t if not unicodedata.combining(c))).strip()


def _paso_de(db, step):
    """El paso del repertorio que corresponde al texto libre de una sesión
    (por clave o por nombre normalizado), o None."""
    n = _norm(step)
    if not n:
        return None
    for r in db.execute("SELECT * FROM eury_repertoire").fetchall():
        if n in (_norm(r['step_key']), _norm(r['name'])):
            return dict(r)
    return None


def backfill_last_practiced(db):
    """last_practiced = la última eury_sessions.date de cada paso."""
    n = 0
    ult = {}
    for r in db.execute("SELECT step, MAX(date) d FROM eury_sessions WHERE COALESCE(step,'') != '' GROUP BY step").fetchall():
        p = _paso_de(db, r['step'])
        if p and (p['step_key'] not in ult or r['d'] > ult[p['step_key']]):
            ult[p['step_key']] = r['d']
    for k, d in ult.items():
        db.execute("UPDATE eury_repertoire SET last_practiced=? WHERE step_key=? AND (last_practiced IS NULL OR last_practiced < ?)", (d, k, d))
        n += 1
    db.commit()
    return n


def _dias(lp, hoy):
    try:
        return (hoy - date.fromisoformat(str(lp)[:10])).days
    except (TypeError, ValueError):
        return None


def _estado(m):
    return 'Automatizado' if m >= 80 else ('Consolidando' if m >= 50 else 'Aprendiendo')


def _enriquecer(r, hoy):
    d = _dias(r.get('last_practiced'), hoy)
    dias = SIN_PRACTICA_DIAS if d is None else d
    return {**r, 'dias': d, 'score': dias * (100 - (r['mastery'] or 0)), 'estado': _estado(r['mastery'] or 0)}


def _repertoire():
    hoy = today_date()
    with get_db() as db:
        rows = db.execute("SELECT * FROM eury_repertoire ORDER BY id").fetchall()
    allr = [_enriquecer(dict(r), hoy) for r in rows]
    orden = lambda lst: sorted(lst, key=lambda r: -r['score'])
    return {"libres": orden([r for r in allr if r["kind"] == "libres"]),
            "pareja": orden([r for r in allr if r["kind"] == "pareja"])}


def sugerencias(repertoire, n=3):
    """Los n pasos no automatizados (dominio < 80) con más días sin practicar
    × (100 − dominio)."""
    todos = repertoire['pareja'] + repertoire['libres']
    cand = sorted((r for r in todos if (r['mastery'] or 0) < 80), key=lambda r: -r['score'])
    return [{'step_key': r['step_key'], 'nombre': r['name'], 'kind': r['kind'], 'mastery': r['mastery'] or 0,
             'dias': r['dias']} for r in cand[:n]]


def racha_bono(streak):
    hitos = sorted(k for k in _STREAK_EC_BONUS if k > streak)
    return {'dias': hitos[0], 'ec': _STREAK_EC_BONUS[hitos[0]]} if hitos else None


def _state():
    today = today_str()
    with get_db() as db:
        total_min = db.execute("SELECT COALESCE(SUM(min),0) as s FROM eury_sessions").fetchone()["s"]
        sessions_count = db.execute("SELECT COUNT(*) as c FROM eury_sessions").fetchone()["c"]
        log_rows = db.execute("SELECT * FROM eury_sessions ORDER BY id DESC LIMIT 30").fetchall()
        grabado_today = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (_GRABADO_KEY, today)
        ).fetchone() is not None
        hoy = today_date()
        lunes = (hoy - timedelta(days=hoy.weekday())).isoformat()
        sem = db.execute("SELECT COALESCE(SUM(min),0) m, COUNT(*) n FROM eury_sessions WHERE date>=? AND date<=?",
                         (lunes, today)).fetchone()
        min_4sem = db.execute("SELECT COALESCE(SUM(min),0) m FROM eury_sessions WHERE date>? AND date<=?",
                              ((hoy - timedelta(days=28)).isoformat(), today)).fetchone()['m']
        ult10 = [r['min'] for r in db.execute("SELECT min FROM eury_sessions ORDER BY id DESC LIMIT 10").fetchall()]

    log = [{
        "id": r["id"], "date": r["date"], "min": r["min"],
        "split": [r["split_diso"], r["split_paso"], r["split_improv"]],
        "step": r["step"], "flow": r["flow"], "improv": r["improv_note"],
        "xp": r["xp"], "grabado": bool(r["grabado"]),
    } for r in log_rows]

    days_practiced = len({r["date"] for r in log_rows}) if log_rows else 0
    avg_daily = round(total_min / max(1, days_practiced)) if days_practiced else 0
    level = _level_from_minutes(total_min)
    horas_semana = min_4sem / 60 / 4
    streak = _eury_streak()
    repertoire = _repertoire()
    if ult10:
        c = Counter(ult10)
        top = max(c.values())
        duracion = next(m for m in ult10 if c[m] == top)      # empate: la más reciente
    else:
        duracion = 30

    return {
        "total_min": total_min,
        "sessions": sessions_count,
        "streak": streak,
        "avg_daily": avg_daily,
        "level": level,
        "repertoire": repertoire,
        "log": log,
        "grabado_today": grabado_today,
        "sugerencias": sugerencias(repertoire),
        "semana": {"min": sem['m'], "sesiones": sem['n'], "meta": META_SEMANA},
        "nivel_eta_semanas": (round(level['hours_to_next'] / horas_semana, 1)
                              if horas_semana > 0 and level['hours_to_next'] > 0 else None),
        "racha_bono": racha_bono(streak),
        "duracion_habitual": duracion,
    }


# ── Rutas ─────────────────────────────────────────────────────────────────────

@eurythmia_bp.route('/')
def index():
    # Música es subpágina propia (/eurythmia/musica/, en el menú bajo Eurythmia);
    # el enlace viejo ?vista=musica sigue funcionando.
    if request.args.get('vista') == 'musica':
        from urllib.parse import urlencode
        resto = [(k, v) for k, v in request.args.items(multi=True) if k != 'vista']
        return redirect('/eurythmia/musica/' + ('?' + urlencode(resto) if resto else ''))
    vista = request.args.get('vista') if request.args.get('vista') in ('bitacora', 'progreso') else ''
    return _render(vista)


@eurythmia_bp.route('/musica/')
def musica_page():
    """Los 100 álbumes: subpágina de Eurythmia (antes ?vista=musica)."""
    return _render('musica')


def _render(vista):
    musica = _musica_state()
    siguiente = next((a for a in musica['albumes'] if not a['escuchado']), None)
    return render_template(
        'eurythmia/index.html',
        phases=PHASES, levels=LEVELS, flow_labels=FLOW_LABELS, science=SCIENCE,
        state=_state(),
        musica=musica, album_siguiente=siguiente,
        rating_dims=RATING_DIMS,
        vista=vista, from_acta=request.args.get('from') == 'acta',
        grabado_xp=_GRABADO_XP, grabado_ec=_GRABADO_EC,
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
        # Dominio por sesión real (nota 4): el paso drillado sube según la fluidez
        step_mastery = None
        paso = _paso_de(db, data.get('step_key') or step) or _paso_de(db, step)
        if paso:
            step_mastery = min(100, (paso['mastery'] or 0) + flow)
            db.execute("UPDATE eury_repertoire SET mastery=?, reps=reps+10, last_practiced=? WHERE id=?",
                       (step_mastery, today, paso['id']))
        db.commit()

    session_ec = _session_ec(minutes, flow)
    gam = engine.process_activity(_SESSION_KEY, xp, 'Baile', log_id, ec=session_ec)

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
                grabado_gam = engine.process_activity(_GRABADO_KEY, _GRABADO_XP, 'Baile', grabado_log_id, ec=_GRABADO_EC)

    streak_gam = _maybe_award_dance_streak(_eury_streak(), today)
    ec_total = session_ec + (_GRABADO_EC if grabado_gam else 0) + \
        (_STREAK_EC_BONUS.get(_eury_streak(), 0) if streak_gam else 0)

    return jsonify({
        'ok': True, 'session_id': session_id, 'xp': xp,
        'gam': gam, 'grabado_gam': grabado_gam, 'streak_gam': streak_gam,
        'step_mastery_nuevo': step_mastery, 'ec_total': ec_total,
        'state': _state(),
    })


@eurythmia_bp.route('/api/preview-reward')
def api_preview_reward():
    """La recompensa de una sesión antes de guardarla, con las mismas
    fórmulas que /api/session (para no duplicarlas en JS)."""
    try:
        minutes = max(1, min(300, int(request.args.get('min', 30))))
        flow = max(1, min(5, int(request.args.get('flow', 3))))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid'}), 400
    grabado = request.args.get('grabado') in ('1', 'true')
    with get_db() as db:
        ya = db.execute("SELECT 1 FROM activity_logs WHERE activity_key=? AND date=?", (_GRABADO_KEY, today_str())).fetchone()
    extra = grabado and not ya
    return jsonify({'xp': minutes + flow * 4 + (_GRABADO_XP if extra else 0),
                    'ec': _session_ec(minutes, flow) + (_GRABADO_EC if extra else 0)})


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

    gam = engine.process_activity(_GRABADO_KEY, _GRABADO_XP, 'Baile', log_id, ec=_GRABADO_EC)
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
