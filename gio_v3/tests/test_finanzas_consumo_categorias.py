"""Consumo: el campo Categoría sugiere una base aunque no haya productos."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_sugerencias_base_con_lista_vacia(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = sess["fin_ok"] = True
        html = c.get('/finanzas/consumo/').get_data(as_text=True)
    assert '<option value="Despensa">' in html and '<option value="Mascotas">' in html
