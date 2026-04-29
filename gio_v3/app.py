import os
from dotenv import load_dotenv
load_dotenv()  # carga gio_v3/.env en desarrollo local; en Railway no existe y no hace nada
from flask import Flask
from database import init_db

from modules.dashboard.routes      import dashboard_bp
from modules.actividades.routes    import actividades_bp
from modules.gtd.routes            import gtd_bp
from modules.finanzas.routes       import finanzas_bp
from modules.idiomas.routes        import idiomas_bp
from modules.nutricion.routes      import nutricion_bp
from modules.perfil.routes         import perfil_bp
from modules.sabado.routes         import sabado_bp
from modules.ataraxia.routes       import ataraxia_bp
from modules.gamification.routes   import gamification_bp
from modules.finanzas.consumo      import consumo_bp
from modules.finanzas.budget       import budget_bp
from modules.finanzas.prioridades  import prioridades_bp
from modules.finanzas.salud        import salud_bp
from modules.recetas.routes        import recetas_bp
from modules.tw.routes       import tw_bp
from modules.recompensas.routes import recompensas_bp
from modules.guardarropa.routes import guardarropa_bp
from modules.guardarropa.wishlist import wishlist_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'gio-pipeline-dev-only-2026')

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(actividades_bp,  url_prefix='/actividades')
    app.register_blueprint(gtd_bp,          url_prefix='/gtd')
    app.register_blueprint(finanzas_bp,     url_prefix='/finanzas')
    app.register_blueprint(idiomas_bp,      url_prefix='/idiomas')
    app.register_blueprint(nutricion_bp,    url_prefix='/nutricion')
    app.register_blueprint(perfil_bp,       url_prefix='/perfil')
    app.register_blueprint(sabado_bp,       url_prefix='/sabado')
    app.register_blueprint(ataraxia_bp,    url_prefix='/ataraxia')
    app.register_blueprint(gamification_bp)
    app.register_blueprint(consumo_bp,      url_prefix='/finanzas/consumo')
    app.register_blueprint(budget_bp,       url_prefix='/finanzas/budget')
    app.register_blueprint(prioridades_bp,  url_prefix='/finanzas/prioridades')
    app.register_blueprint(salud_bp,        url_prefix='/finanzas/salud')
    app.register_blueprint(recetas_bp,     url_prefix='/recetas')
    app.register_blueprint(tw_bp)
    app.register_blueprint(recompensas_bp, url_prefix='/recompensas')
    app.register_blueprint(guardarropa_bp, url_prefix='/guardarropa')
    app.register_blueprint(wishlist_bp,   url_prefix='/guardarropa/wishlist')

    @app.route('/api/health/v31')
    def health_v31():
        from ec_constants import EC_VALUE_MXN, GAMIFICATION_VERSION
        from data import ACTIVITIES
        sat_keys = {"sat_bloque1", "sat_bloque2", "sat_bloque3"}
        sun_keys = {"sun_reflexion", "sun_diseno", "sun_comidas", "sun_jugos", "sun_planchar"}
        checks = {
            "version":            GAMIFICATION_VERSION,
            "ec_value_mxn":       EC_VALUE_MXN,
            "ec_rate_ok":         EC_VALUE_MXN == 10,
            "sat_jugos_optional": ACTIVITIES.get("sat_jugos", {}).get("optional", False),
            "sat_keys_ok":        sat_keys.issubset(set(ACTIVITIES)),
            "sun_keys_ok":        sun_keys.issubset(set(ACTIVITIES)),
        }
        from database import get_db
        try:
            with get_db() as db:
                checks["ataraxia_seeded"]  = bool(db.execute(
                    "SELECT 1 FROM rutina_bloques LIMIT 1"
                ).fetchone())
                checks["migration_applied"] = bool(db.execute(
                    "SELECT 1 FROM migration_log WHERE version='3.1'"
                ).fetchone())
        except Exception as e:
            checks["db_error"] = str(e)
        ok = (checks["ec_rate_ok"] and checks["sat_keys_ok"] and
              checks["sun_keys_ok"] and "db_error" not in checks)
        return checks, 200 if ok else 500

    @app.route('/health')
    def health():
        from database import get_db_status, _USE_HYBRID
        status = get_db_status()
        ok = status.get('db_exists', False) and 'error' not in status
        return {
            'status': 'ok' if ok else 'degraded',
            'mode':   status.get('mode'),
            'turso':  'connected' if _USE_HYBRID else 'not_configured',
            'tables': status.get('tables', {}),
            'total_xp': status.get('total_xp', 0),
        }, 200 if ok else 503

    with app.app_context():
        init_db()

    return app
