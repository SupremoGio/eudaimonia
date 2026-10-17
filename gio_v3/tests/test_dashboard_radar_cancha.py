"""
test_dashboard_radar_cancha.py — en «Pendiente» del Inicio, el partido muestra
la cancha en vez de «Partido · Fútbol».
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def test_partido_muestra_cancha(test_db):
    from app import create_app
    from utils import today_str
    app = create_app(); app.config["TESTING"] = True
    with database.get_db() as db:
        db.execute("""INSERT INTO futbol_partidos (fecha, hora, cancha, rival, estado, created_at)
                      VALUES (?, '22:40', 'Cancha Futpool Américas', 'Chicos del trueno', 'programado', 'x')""", (today_str(),))
        db.commit()
    with app.test_client() as c:
        with c.session_transaction() as s:
            s["app_ok"] = True
        html = c.get('/').get_data(as_text=True)
    assert 'vs Chicos del trueno · 22:40' in html
    assert 'Cancha Futpool Américas' in html
    assert 'Partido · Fútbol' not in html
