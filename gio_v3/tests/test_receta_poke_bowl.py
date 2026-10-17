"""Receta Poke Bowl agregada a petición del usuario: se inserta una sola vez."""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database

NOMBRE = "Poke Bowl de Quinoa, Atún Aleta Amarilla y Zanahoria"


def test_receta_poke_bowl_se_inserta_una_vez(test_db):
    database.init_db()
    with database.get_db() as db:
        rows = db.execute("SELECT * FROM recetas WHERE nombre=?", (NOMBRE,)).fetchall()
    assert len(rows) == 1
    r = rows[0]
    assert (r['categoria'], r['calorias'], r['proteina'], r['carbos'], r['grasa'], r['tiempo_prep'], r['porciones']) == \
        ('Post-Entrenamiento', 515, 38, 43, 18, 20, 1)
    ings = json.loads(r['ingredientes'])
    assert len(ings) == 9 and ings[1] == {"item": "Atún aleta amarilla en cubitos", "cantidad": "200", "unidad": "g"}
    assert len(json.loads(r['instrucciones'])) == 5
    assert 'PokeBowl' in r['tags']
