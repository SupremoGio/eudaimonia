from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from database import get_db
from utils import today_str
import modules.gamification.engine as engine

futbol_bp = Blueprint('futbol', __name__, template_folder='../../templates')

_GOL_KEY = 'gol'
_GOL_PTS = 2
_GOL_CAT = 'Salud Física'


def _now():
    return datetime.now().isoformat()


def _row_to_dict(r):
    return dict(r)


def _stats(partidos):
    total = len(partidos)
    goles_propios = sum(p['goles_propios'] or 0 for p in partidos)
    asistencias   = sum(p['asistencias'] or 0 for p in partidos)
    ratings = [p['rendimiento'] for p in partidos if p['rendimiento'] is not None]
    rating_prom = round(sum(ratings) / len(ratings), 1) if ratings else None

    ganados = empatados = perdidos = 0
    for p in partidos:
        gf, gc = p['goles_favor'] or 0, p['goles_contra'] or 0
        if gf > gc: ganados += 1
        elif gf < gc: perdidos += 1
        else: empatados += 1

    return {
        'total': total,
        'goles_propios': goles_propios,
        'asistencias': asistencias,
        'rating_prom': rating_prom,
        'ganados': ganados,
        'empatados': empatados,
        'perdidos': perdidos,
    }


def _credit_gol_bonus():
    """Credita el bonus 'Gol (bonus partido)' de Salud Física si no se ha dado hoy. Devuelve el log_id o None."""
    today = today_str()
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (_GOL_KEY, today)
        ).fetchone()
        if existing:
            return None
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (_GOL_KEY, today, _GOL_PTS)
        )
        log_id = cur.lastrowid
        db.commit()
    engine.process_activity(_GOL_KEY, _GOL_PTS, _GOL_CAT, log_id)
    return log_id


def _remove_gol_bonus(log_id):
    with get_db() as db:
        db.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
        db.commit()
    engine.remove_activity(log_id)


# ── Rutas ─────────────────────────────────────────────────────────────────────

@futbol_bp.route('/')
def index():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM futbol_partidos ORDER BY fecha DESC, id DESC"
        ).fetchall()
    partidos = [_row_to_dict(r) for r in rows]
    return render_template('bienestar/futbol.html', partidos=partidos, stats=_stats(partidos))


@futbol_bp.route('/api/partidos')
def list_partidos():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM futbol_partidos ORDER BY fecha DESC, id DESC"
        ).fetchall()
    partidos = [_row_to_dict(r) for r in rows]
    return jsonify({'partidos': partidos, 'stats': _stats(partidos)})


@futbol_bp.route('/api/partidos', methods=['POST'])
def crear_partido():
    d = request.json or {}
    if not d.get('fecha'):
        return jsonify({'ok': False, 'error': 'fecha requerida'}), 400

    goles_propios = int(d.get('goles_propios') or 0)
    gol_log_id = _credit_gol_bonus() if goles_propios > 0 else None

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO futbol_partidos
                   (fecha, hora, cancha, rival, goles_favor, goles_contra,
                    goles_propios, asistencias, minutos_jugados, rendimiento,
                    gol_log_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d['fecha'],
                d.get('hora', ''),
                d.get('cancha', '').strip(),
                d.get('rival', '').strip(),
                int(d.get('goles_favor') or 0),
                int(d.get('goles_contra') or 0),
                goles_propios,
                int(d.get('asistencias') or 0),
                int(d['minutos_jugados']) if d.get('minutos_jugados') not in (None, '') else None,
                float(d['rendimiento']) if d.get('rendimiento') not in (None, '') else None,
                gol_log_id,
                _now(),
            ),
        )
        db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'gol_credited': gol_log_id is not None})


@futbol_bp.route('/api/partidos/<int:pid>', methods=['PATCH'])
def actualizar_partido(pid):
    d = request.json or {}
    with get_db() as db:
        row = db.execute("SELECT * FROM futbol_partidos WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'no encontrado'}), 404
    partido = _row_to_dict(row)

    sets, vals = [], []
    for f in ('fecha', 'hora', 'cancha', 'rival'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(d[f])
    for f in ('goles_favor', 'goles_contra', 'asistencias', 'minutos_jugados'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(int(d[f]) if d[f] not in (None, '') else None)
    if 'rendimiento' in d:
        sets.append('rendimiento=?')
        vals.append(float(d['rendimiento']) if d['rendimiento'] not in (None, '') else None)

    gol_log_id = partido['gol_log_id']
    if 'goles_propios' in d:
        nuevos_goles = int(d['goles_propios'] or 0)
        if nuevos_goles > 0 and partido['goles_propios'] == 0:
            gol_log_id = _credit_gol_bonus()
        elif nuevos_goles == 0 and partido['goles_propios'] > 0 and gol_log_id:
            _remove_gol_bonus(gol_log_id)
            gol_log_id = None
        sets.append('goles_propios=?')
        vals.append(nuevos_goles)
        sets.append('gol_log_id=?')
        vals.append(gol_log_id)

    if not sets:
        return jsonify({'ok': False, 'error': 'nada que actualizar'}), 400

    vals.append(pid)
    with get_db() as db:
        db.execute(f"UPDATE futbol_partidos SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()
    return jsonify({'ok': True})


@futbol_bp.route('/api/partidos/<int:pid>', methods=['DELETE'])
def eliminar_partido(pid):
    with get_db() as db:
        row = db.execute("SELECT gol_log_id FROM futbol_partidos WHERE id=?", (pid,)).fetchone()
        if row and row['gol_log_id']:
            _remove_gol_bonus(row['gol_log_id'])
        db.execute("DELETE FROM futbol_partidos WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True})
