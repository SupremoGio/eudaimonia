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
from modules.gamification.routes   import gamification_bp
from modules.finanzas.consumo      import consumo_bp
from modules.finanzas.budget       import budget_bp
from modules.finanzas.prioridades  import prioridades_bp
from modules.tw.routes       import tw_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = 'gio-pipeline-secret-2026'

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(actividades_bp,  url_prefix='/actividades')
    app.register_blueprint(gtd_bp,          url_prefix='/gtd')
    app.register_blueprint(finanzas_bp,     url_prefix='/finanzas')
    app.register_blueprint(idiomas_bp,      url_prefix='/idiomas')
    app.register_blueprint(nutricion_bp,    url_prefix='/nutricion')
    app.register_blueprint(perfil_bp,       url_prefix='/perfil')
    app.register_blueprint(sabado_bp,       url_prefix='/sabado')
    app.register_blueprint(gamification_bp)
    app.register_blueprint(consumo_bp,      url_prefix='/finanzas/consumo')
    app.register_blueprint(budget_bp,       url_prefix='/finanzas/budget')
    app.register_blueprint(prioridades_bp,  url_prefix='/finanzas/prioridades')
    app.register_blueprint(tw_bp)

    with app.app_context():
        init_db()

    return app
