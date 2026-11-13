"""SALUD/Psicólogo (2026-11): terapia como necesidad, no como Cuidado personal."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules.finanzas.estados.config import SUBCATEGORIAS, get_categoria_subcategoria


def test_psicologo_es_subcategoria_de_salud():
    assert 'Psicólogo' in SUBCATEGORIAS['SALUD']
    assert 'Psicólogo' not in SUBCATEGORIAS.get('CUIDADO_PERSONAL', [])


@pytest.mark.parametrize('desc', ['PAGO PSICOLOGA ANA', 'CONSULTA PSICOLOGO', 'CLINICA DE PSICOLOGIA',
                                  'PSICOTERAPIA INTEGRAL'])
def test_importador_lo_clasifica_en_psicologo(desc):
    assert get_categoria_subcategoria(desc) == ('SALUD', 'Psicólogo')


def test_consultas_y_farmacia_no_cambian():
    assert get_categoria_subcategoria('DOCTOR SIMI') == ('SALUD', 'Consultas')
    assert get_categoria_subcategoria('FARMACIA ARROCHA') == ('SALUD', 'Farmacia')


def test_naturaleza_sembrada(test_db):
    with database.get_db() as db:
        r = db.execute("SELECT naturaleza FROM est_categoria_naturaleza "
                       "WHERE categoria='SALUD' AND subcategoria='Psicólogo'").fetchone()
    assert r and r['naturaleza'] == 'VARIABLE'


def test_api_categories_la_expone(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
            s['fin_ok'] = True
        cats = {x['categoria']: x['subcategorias'] for x in c.get('/finanzas/estados/api/categories').get_json()}
    assert 'Psicólogo' in cats['SALUD']
