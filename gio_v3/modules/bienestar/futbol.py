from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, date
from database import get_db
import modules.gamification.engine as engine
import modules.actividades.activity_defs as adefs

futbol_bp = Blueprint('futbol', __name__, template_folder='../../templates')

_RESULTADO_KEY = 'partido_resultado'
_RESULTADO_CAT = 'Salud Física'


def _now():
    return datetime.now().isoformat()


def _row_to_dict(r):
    return dict(r)


def _stats(partidos):
    jugados = [p for p in partidos if p.get('estado', 'jugado') == 'jugado']
    total = len(jugados)
    goles_propios = sum(p['goles_propios'] or 0 for p in jugados)
    asistencias   = sum(p['asistencias'] or 0 for p in jugados)
    ratings = [p['rendimiento'] for p in jugados if p['rendimiento'] is not None]
    rating_prom = round(sum(ratings) / len(ratings), 1) if ratings else None

    ganados = empatados = perdidos = 0
    for p in jugados:
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


def _calcular_liquidacion(p):
    """Tabulador de XP/EC de un partido jugado. Premia jugar, cada gol y cada
    asistencia sin tope (XP crece libre con el desempeño real), y reserva el EC
    (moneda canjeable) para señales de calidad — ganar y una buena calificación —
    en vez de repartirlo por cada gol, para no inflar la economía de recompensas."""
    goles = p.get('goles_propios') or 0
    asist = p.get('asistencias') or 0
    gf, gc = p.get('goles_favor') or 0, p.get('goles_contra') or 0
    rating = p.get('rendimiento')

    xp, ec = 3, 0          # por jugar el partido

    xp += goles * 2        # por cada gol propio
    xp += asist * 1        # por cada asistencia

    if gf > gc:
        xp += 2; ec += 1   # victoria
    elif gf == gc:
        xp += 1            # empate

    if rating is not None:
        if rating >= 9.0:
            xp += 4; ec += 2    # actuación de crack
        elif rating >= 7.5:
            xp += 2; ec += 1    # muy buena actuación
        elif rating >= 6.0:
            xp += 1              # actuación sólida

    return xp, ec


def _revertir_liquidacion(log_id):
    if not log_id:
        return
    with get_db() as db:
        db.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
        db.commit()
    engine.remove_activity(log_id)


def _liquidar_partido(partido, fecha):
    """Otorga el XP/EC de un partido jugado según _calcular_liquidacion.
    Devuelve el log_id a guardar en futbol_partidos.gol_log_id (reutilizada
    como referencia genérica de liquidación, ya no solo de goles) para poder
    revertir si el partido se edita o se borra."""
    xp, ec = _calcular_liquidacion(partido)
    if xp <= 0 and ec <= 0:
        return None
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (_RESULTADO_KEY, fecha, xp)
        )
        log_id = cur.lastrowid
        db.commit()
    engine.process_activity(_RESULTADO_KEY, xp, _RESULTADO_CAT, log_id, ec=ec)
    return log_id


def _marcar_ancla_partido(fecha):
    """Si ese día de partido ya hay un partido jugado, tacha en el Acta el
    ancla «Partido de fútbol» (activity_defs.PARTIDO_KEY) como si el usuario la
    hubiera marcado a mano: mismo log y mismo XP/EC que el check del Acta. Es
    idempotente — si ya estaba tachada no hace nada — y nunca la destacha."""
    try:
        d = date.fromisoformat(fecha)
    except (TypeError, ValueError):
        return None
    if adefs.weekday_code(d) not in adefs.DIAS_PARTIDO:
        return None
    act = adefs.get_by_key(adefs.PARTIDO_KEY)
    if not act or not act['active'] or act['hidden']:
        return None
    with get_db() as db:
        jugado = db.execute(
            "SELECT 1 FROM futbol_partidos WHERE fecha=? AND estado='jugado' LIMIT 1", (fecha,)
        ).fetchone()
        if not jugado or db.execute(
            "SELECT 1 FROM activity_logs WHERE activity_key=? AND date=?", (adefs.PARTIDO_KEY, fecha)
        ).fetchone():
            return None
        cur = db.execute(
            "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
            (adefs.PARTIDO_KEY, fecha, act['pts'])
        )
        log_id = cur.lastrowid
        db.commit()
    engine.process_activity(adefs.PARTIDO_KEY, act['pts'], act['cat'], log_id)
    return log_id


# ── Rutas ─────────────────────────────────────────────────────────────────────

@futbol_bp.route('/')
def index():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM futbol_partidos ORDER BY fecha DESC, id DESC"
        ).fetchall()
    todos = [_row_to_dict(r) for r in rows]
    jugados = [p for p in todos if p['estado'] == 'jugado']
    programados = sorted(
        (p for p in todos if p['estado'] == 'programado'),
        key=lambda p: (p['fecha'], p['hora'] or '')
    )
    return render_template(
        'bienestar/futbol.html',
        partidos=jugados,
        programados=programados,
        stats=_stats(todos),
    )


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

    estado = d.get('estado') or 'jugado'
    partido = {
        'goles_favor':   int(d.get('goles_favor') or 0),
        'goles_contra':  int(d.get('goles_contra') or 0),
        'goles_propios': int(d.get('goles_propios') or 0),
        'asistencias':   int(d.get('asistencias') or 0),
        'rendimiento':   float(d['rendimiento']) if d.get('rendimiento') not in (None, '') else None,
    }
    log_id = _liquidar_partido(partido, d['fecha']) if estado == 'jugado' else None

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO futbol_partidos
                   (fecha, hora, cancha, rival, goles_favor, goles_contra,
                    goles_propios, asistencias, minutos_jugados, rendimiento,
                    gol_log_id, estado, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d['fecha'],
                d.get('hora', ''),
                d.get('cancha', '').strip(),
                d.get('rival', '').strip(),
                partido['goles_favor'],
                partido['goles_contra'],
                partido['goles_propios'],
                partido['asistencias'],
                int(d['minutos_jugados']) if d.get('minutos_jugados') not in (None, '') else None,
                partido['rendimiento'],
                log_id,
                estado,
                _now(),
            ),
        )
        db.commit()
        pid = cur.lastrowid
    if estado == 'jugado':
        _marcar_ancla_partido(d['fecha'])
    return jsonify({'ok': True, 'id': pid, 'liquidado': log_id is not None})


@futbol_bp.route('/api/partidos/<int:pid>', methods=['PATCH'])
def actualizar_partido(pid):
    d = request.json or {}
    with get_db() as db:
        row = db.execute("SELECT * FROM futbol_partidos WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'no encontrado'}), 404
    partido = _row_to_dict(row)

    sets, vals = [], []
    for f in ('fecha', 'hora', 'cancha', 'rival', 'estado'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(d[f])
    for f in ('goles_favor', 'goles_contra', 'goles_propios', 'asistencias', 'minutos_jugados'):
        if f in d:
            sets.append(f'{f}=?')
            vals.append(int(d[f]) if d[f] not in (None, '') else None)
    if 'rendimiento' in d:
        sets.append('rendimiento=?')
        vals.append(float(d['rendimiento']) if d['rendimiento'] not in (None, '') else None)

    if not sets:
        return jsonify({'ok': False, 'error': 'nada que actualizar'}), 400

    # Si cambió algo que afecta el tabulador de XP/EC (o el estado del partido),
    # se revierte la liquidación anterior y se recalcula desde cero sobre los
    # valores ya actualizados — más simple y a prueba de errores que ajustar
    # la diferencia a mano.
    LIQUIDACION_FIELDS = ('goles_favor', 'goles_contra', 'goles_propios', 'asistencias', 'rendimiento', 'estado')
    if any(f in d for f in LIQUIDACION_FIELDS):
        nuevo = dict(partido)
        for f in ('goles_favor', 'goles_contra', 'goles_propios', 'asistencias'):
            if f in d:
                nuevo[f] = int(d[f]) if d[f] not in (None, '') else 0
        if 'rendimiento' in d:
            nuevo['rendimiento'] = float(d['rendimiento']) if d['rendimiento'] not in (None, '') else None
        nuevo_estado = d.get('estado', partido['estado'])

        if partido['gol_log_id']:
            _revertir_liquidacion(partido['gol_log_id'])
        log_id = _liquidar_partido(nuevo, d.get('fecha', partido['fecha'])) if nuevo_estado == 'jugado' else None

        sets.append('gol_log_id=?')
        vals.append(log_id)

    vals.append(pid)
    with get_db() as db:
        db.execute(f"UPDATE futbol_partidos SET {', '.join(sets)} WHERE id=?", vals)
        db.commit()
    if d.get('estado', partido['estado']) == 'jugado':
        _marcar_ancla_partido(d.get('fecha', partido['fecha']))
    return jsonify({'ok': True})


@futbol_bp.route('/api/partidos/<int:pid>', methods=['DELETE'])
def eliminar_partido(pid):
    with get_db() as db:
        row = db.execute("SELECT gol_log_id FROM futbol_partidos WHERE id=?", (pid,)).fetchone()
        if row and row['gol_log_id']:
            _revertir_liquidacion(row['gol_log_id'])
        db.execute("DELETE FROM futbol_partidos WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True})
