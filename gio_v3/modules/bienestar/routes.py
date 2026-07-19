from flask import Blueprint, redirect, jsonify
from database import get_db
from utils import today_str

bienestar_bp = Blueprint('bienestar', __name__, template_folder='../../templates')

@bienestar_bp.route('/')
def index():
    return redirect('/bienestar/salud')


@bienestar_bp.route('/api/hegemonikon-summary')
def hegemonikon_summary():
    from modules.nutricion.routes import get_week_start, get_today_key, get_streak, get_xp_today

    with get_db() as db:
        body = {r['key']: r['value'] for r in db.execute(
            "SELECT key, value FROM body_measurements"
        ).fetchall()}
        peso_hist = [dict(r) for r in db.execute(
            "SELECT value, recorded_at FROM body_measurements_history "
            "WHERE key='peso' ORDER BY recorded_at DESC LIMIT 8"
        ).fetchall()]

        week_str  = get_week_start().isoformat()
        today_key = get_today_key()
        meals = db.execute(
            "SELECT done FROM nutricion_semana WHERE week_start=? AND day_key=?",
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

    peso_spark = []
    for h in reversed(peso_hist):
        try:
            peso_spark.append(float(h['value']))
        except (TypeError, ValueError):
            pass
    peso_trend = round(peso_spark[-1] - peso_spark[-2], 1) if len(peso_spark) >= 2 else None

    return jsonify({
        'body':        body,
        'peso_trend':  peso_trend,
        'peso_spark':  peso_spark,
        'nutricion': {
            'comidas_done':  sum(1 for m in meals if m['done']),
            'comidas_total': len(meals),
            'streak':        nutri_streak,
            'xp_today':      nutri_xp_today,
        },
        'salud': {
            'episodios_activos': salud['activos'],
            'meds_activos':      salud['meds_activos'],
        },
        'guardarropa': {
            'items':   n_items,
            'outfits': n_outfits,
        },
        'recetas': {
            'total':     n_recetas,
            'favoritas': n_favoritas,
        },
    })
