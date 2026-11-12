from datetime import date
from flask import Blueprint, redirect, jsonify, render_template, request
from database import get_db
from utils import today_str, today_date
from modules.bienestar import salud as sl

bienestar_bp = Blueprint('bienestar', __name__, template_folder='../../templates')


def _hegemonikon_summary_data():
    from modules.nutricion.routes import get_week_start, get_today_key, get_streak, get_xp_today

    with get_db() as db:
        body = {r['key']: r['value'] for r in db.execute(
            "SELECT key, value FROM body_measurements"
        ).fetchall()}
        sl.auto_terminar(db)
        peso_hist = [dict(r) for r in db.execute(
            "SELECT value, recorded_at FROM body_measurements_history "
            "WHERE key='peso' ORDER BY recorded_at DESC LIMIT 8"
        ).fetchall()]

        week_str  = get_week_start().isoformat()
        today_key = get_today_key()
        meals = db.execute(
            "SELECT done, slot, name, time_str FROM nutricion_semana WHERE week_start=? AND day_key=? ORDER BY time_str",
            (week_str, today_key)
        ).fetchall()
        nutri_streak   = get_streak(db)
        nutri_xp_today = get_xp_today(db)

        salud = db.execute("""
            SELECT COALESCE(SUM(CASE WHEN e.activo=1 THEN 1 ELSE 0 END),0) AS activos,
                   COALESCE(SUM(CASE WHEN e.activo=1 AND m.tomando=1 THEN 1 ELSE 0 END),0) AS meds_activos
            FROM   medico_episodios e
            LEFT JOIN medico_recetas      r ON r.episodio_id = e.id
            LEFT JOIN medico_medicamentos m ON m.receta_id  = r.id
        """).fetchone()

        n_items    = db.execute("SELECT COUNT(*) c FROM wardrobe_items WHERE activo=1").fetchone()['c']
        n_outfits  = db.execute("SELECT COUNT(*) c FROM outfits").fetchone()['c']
        n_recetas  = db.execute("SELECT COUNT(*) c FROM recetas").fetchone()['c']
        n_favoritas = db.execute("SELECT COUNT(*) c FROM recetas WHERE favorita=1").fetchone()['c']

        n_partidos = db.execute("SELECT COUNT(*) c FROM futbol_partidos").fetchone()['c']
        rating_row = db.execute(
            "SELECT ROUND(AVG(rendimiento), 1) AS r FROM futbol_partidos WHERE rendimiento IS NOT NULL"
        ).fetchone()
        futbol_rating = rating_row['r']

        trat = sl.tratamiento(db)
        alerta = sl.recurrencia_alerta(db)
        n_episodios = db.execute("SELECT COUNT(*) c FROM medico_episodios").fetchone()['c']
        partido = _proximo_partido(db)
        viaje = db.execute(
            "SELECT destino, nombre, fecha_inicio FROM viajes WHERE estado != 'cancelado' AND fecha_inicio >= ? ORDER BY fecha_inicio LIMIT 1",
            (today_str(),)).fetchone()

        n_viajes = db.execute(
            "SELECT COUNT(*) c FROM viajes WHERE estado != 'cancelado'"
        ).fetchone()['c']
        n_viajes_proximos = db.execute(
            "SELECT COUNT(*) c FROM viajes WHERE estado != 'cancelado' AND fecha_fin >= ?",
            (today_str(),)
        ).fetchone()['c']

    peso_spark = []
    for h in reversed(peso_hist):
        try:
            peso_spark.append(float(h['value']))
        except (TypeError, ValueError):
            pass
    peso_trend = round(peso_spark[-1] - peso_spark[-2], 1) if len(peso_spark) >= 2 else None
    hoy = today_date()
    try:
        peso_edad = (hoy - date.fromisoformat(peso_hist[0]['recorded_at'][:10])).days if peso_hist else None
        peso_entre = (date.fromisoformat(peso_hist[0]['recorded_at'][:10]) -
                      date.fromisoformat(peso_hist[1]['recorded_at'][:10])).days if len(peso_hist) >= 2 else None
    except (TypeError, ValueError):
        peso_edad = peso_entre = None
    sig = next((m for m in meals if not m['done']), None)

    return {
        'body':        body,
        'peso_trend':  peso_trend,
        'peso_spark':  peso_spark,
        'peso': {
            'actual': peso_spark[-1] if peso_spark else None,
            'edad': peso_edad,
            'entre': peso_entre,
            'bueno': (peso_trend < 0) if peso_trend else None,
            'barras': _barras(peso_spark),
        },
        'tratamiento': trat,
        'recurrencia_alerta': alerta,
        'partido': partido,
        'nutricion': {
            'comidas_done':  sum(1 for m in meals if m['done']),
            'comidas_total': len(meals),
            'streak':        nutri_streak,
            'xp_today':      nutri_xp_today,
            'siguiente':     (sig['slot'] or sig['name']) if sig else None,
        },
        'salud': {
            'episodios_activos': salud['activos'],
            'meds_activos':      salud['meds_activos'],
            'historial':         n_episodios,
        },
        'guardarropa': {
            'items':   n_items,
            'outfits': n_outfits,
        },
        'recetas': {
            'total':     n_recetas,
            'favoritas': n_favoritas,
        },
        'futbol': {
            'partidos': n_partidos,
            'rating':   futbol_rating,
        },
        'viajes': {
            'total':    n_viajes,
            'proximos': n_viajes_proximos,
            'proximo':  ({'destino': viaje['destino'] or viaje['nombre'],
                          'en_dias': (date.fromisoformat(viaje['fecha_inicio'][:10]) - hoy).days} if viaje else None),
        },
    }


_DIAS = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')
_MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


def _barras(vals):
    """Alturas (px) de una sparkline de barras: 4 a 18 px."""
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    return [12 if hi == lo else round(4 + (v - lo) / (hi - lo) * 14) for v in vals]


def _resultado(p):
    gf, gc = p['goles_favor'] or 0, p['goles_contra'] or 0
    return 'G' if gf > gc else ('E' if gf == gc else 'P')


def _proximo_partido(db, hoy=None):
    """Próximo partido programado con liga y tono, forma (últimos 5),
    rating promedio, si reemplaza a Gym en Acta y si hay una lesión activa.
    El récord y el rating se devuelven aunque no haya partido próximo."""
    from modules.bienestar.futbol import LIGAS, OTRA, _liga_valida
    from modules.actividades.activity_defs import DIAS_PARTIDO, weekday_code
    hoy = hoy or today_date()
    jugados = [dict(r) for r in db.execute(
        "SELECT * FROM futbol_partidos WHERE COALESCE(estado,'jugado')='jugado' ORDER BY fecha DESC, id DESC").fetchall()]
    res = [_resultado(p) for p in jugados]
    rat = db.execute("SELECT ROUND(AVG(rendimiento),1) r FROM futbol_partidos WHERE rendimiento IS NOT NULL").fetchone()['r']
    lesion = db.execute("SELECT zona_cuerpo, titulo FROM medico_episodios WHERE activo=1 AND tipo='lesion' ORDER BY fecha_inicio DESC LIMIT 1").fetchone()
    p = db.execute("SELECT * FROM futbol_partidos WHERE estado='programado' AND fecha >= ? ORDER BY fecha, hora LIMIT 1",
                   (hoy.isoformat(),)).fetchone()
    base = {'forma': res[:5][::-1], 'rating_prom': rat, 'jugados': len(jugados),
            'record': f"{res.count('G')}-{res.count('E')}-{res.count('P')}",
            'lesion_activa': bool(lesion), 'lesion_zona': (lesion['zona_cuerpo'] or lesion['titulo']) if lesion else ''}
    if not p:
        return {**base, 'hay': False}
    p = dict(p)
    info = {l['key']: l for l in LIGAS + [OTRA]}.get(_liga_valida(p.get('liga'), p['fecha'], p.get('cancha')), OTRA)
    f = date.fromisoformat(p['fecha'][:10])
    return {**base, 'hay': True, 'id': p['id'], 'fecha': p['fecha'], 'hora': p.get('hora') or '', 'rival': p.get('rival') or '',
            'cancha': p.get('cancha') or '', 'liga': info['nombre'], 'tono': info['tono'],
            'fecha_txt': f"{_DIAS[f.weekday()]} {f.day}", 'en_dias': (f - hoy).days,
            'reemplaza_gym': weekday_code(f) in DIAS_PARTIDO}


@bienestar_bp.route('/api/alerta/ocultar', methods=['POST'])
def ocultar_alerta():
    titulo = ((request.json or {}).get('titulo') or '').strip()
    if not titulo:
        return jsonify({'ok': False, 'error': 'titulo requerido'}), 400
    with get_db() as db:
        hasta = sl.ocultar_alerta(db, titulo)
    return jsonify({'ok': True, 'hasta': hasta})


@bienestar_bp.route('/')
def index():
    # Antes redirigía directo a /bienestar/salud — pero Hegemonikon agrupa 6
    # páginas reales (Salud, Nutrición, Guardarropa, Recetas, Viajes, Fútbol)
    # y ese redirect las dejaba solo una de ellas alcanzable desde el
    # dashboard/sidebar. Ahora esto es el hub real del pilar.
    return render_template('bienestar/index.html', data=_hegemonikon_summary_data())


@bienestar_bp.route('/api/hegemonikon-summary')
def hegemonikon_summary():
    return jsonify(_hegemonikon_summary_data())
