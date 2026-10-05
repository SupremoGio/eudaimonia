"""
test_guardarropa_coach.py — Coach de imagen (outfit con IA desde una prenda o
por ocasión). La IA se simula: lo que se prueba es el motor determinista que
prepara la shortlist y valida/completa lo que la IA devuelve.
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
import modules.guardarropa.routes as gr
from modules.guardarropa import stylist


# ── Motor puro ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('item,slot', [
    ({'categoria': 'Camisa', 'nombre': 'Camisa Oxford blanca'}, 'superior'),
    ({'categoria': 'Jeans', 'nombre': 'Levi\'s 511'}, 'inferior'),
    ({'categoria': 'Chamarras', 'nombre': 'Veste-chemise Regular Fit'}, 'capa_ext'),
    ({'categoria': 'Blazer / Saco', 'nombre': 'Blazer navy'}, 'capa_ext'),
    ({'categoria': 'Sneakers', 'nombre': 'Common Projects'}, 'calzado'),
    ({'categoria': 'Traje / Conjunto', 'nombre': 'Traje gris'}, 'traje'),
    ({'categoria': 'Suéter', 'nombre': 'Merino'}, 'capa_media'),
    ({'categoria': '', 'nombre': 'Sobrecamisa de pana'}, 'capa_ext'),
    ({'categoria': 'Accesorio', 'nombre': 'Cinturón café'}, 'accesorio'),
])
def test_slot_of(item, slot):
    assert stylist.slot_of(item) == slot


def test_formalidad():
    assert stylist.formality_of({'categoria': 'Traje / Conjunto'}) == 5
    assert stylist.formality_of({'categoria': 'Pantalón', 'nombre': 'Pantalón de mezclilla'}) == 2
    assert stylist.formality_of({'categoria': 'Sudadera'}) == 1
    assert stylist.formality_of({'categoria': 'Camiseta', 'nombre': 'Dry-fit running'}) == 1


def test_color_profile_reconoce_neutros_de_sastreria():
    assert stylist.color_profile({'color_hex': '#1f2a44'})['familia'] == 'azul marino'
    assert stylist.color_profile({'color_hex': '#ffffff'})['familia'] == 'blanco'
    assert stylist.color_profile({'color_hex': '#c19a6b'})['neutro'] is True   # camel
    rojo = stylist.color_profile({'color_hex': '#e01010'})
    assert rojo['neutro'] is False and rojo['saturacion'] == 'vivo'


def test_dos_acentos_vivos_que_chocan_puntuan_bajo():
    rojo = stylist.color_profile({'color_hex': '#e01010'})
    verde = stylist.color_profile({'color_hex': '#10e010'})
    navy = stylist.color_profile({'color_hex': '#1f2a44'})
    assert stylist.color_compat(rojo, verde) < stylist.color_compat(rojo, navy)


def _it(iid, cat, nombre, hexc='#808080', **kw):
    return stylist.enrich({'id': iid, 'categoria': cat, 'nombre': nombre, 'color_hex': hexc,
                           'estado': kw.pop('estado', 'bueno'), **kw})


def test_shortlist_formal_excluye_deportivo_donar_y_la_funcion_de_la_ancla():
    anchor = _it(1, 'Blazer / Saco', 'Blazer navy', '#1f2a44')
    items = [anchor,
             _it(2, 'Camisa', 'Camisa blanca', '#ffffff'),
             _it(3, 'Sudadera', 'Hoodie gris'),
             _it(4, 'Pantalón', 'Pantalón gris', '#7a7a7a'),
             _it(5, 'Chamarra / Abrigo', 'Bomber'),
             _it(6, 'Zapatos formales', 'Derby café', '#4a2c1a'),
             _it(7, 'Camisa', 'Camisa rota', estado='donar')]
    sl = stylist.build_shortlist(items, 'Formal', anchor)
    ids = {it['id'] for lst in sl.values() for it in lst}
    assert ids == {2, 4, 6}


def test_sanitize_descarta_ids_inventados_duplica_funcion_y_completa_faltantes():
    anchor = _it(1, 'Jeans', 'Jeans oscuros', '#1c2333')
    items = [anchor,
             _it(2, 'Camisa', 'Camisa blanca', '#ffffff'),
             _it(3, 'Camiseta', 'Camiseta gris'),
             _it(4, 'Sneakers', 'Sneakers blancos', '#f5f5f5')]
    by_id = {i['id']: i for i in items}
    sl = stylist.build_shortlist(items, 'Casual', anchor)
    out = stylist.sanitize_proposal({'item_ids': [2, 3, 999, '1'], 'roles': [{'id': 2, 'rol': 'x'}, {'id': 3, 'rol': 'y'}]},
                                    by_id, sl, anchor)
    assert out['item_ids'][0] == 1                      # ancla primero
    assert 999 not in out['item_ids']                   # ID inventado fuera
    assert not ({2, 3} <= set(out['item_ids']))         # una sola prenda superior
    assert 4 in out['item_ids'] and out['autocompletado'] == [4]   # faltaba calzado
    assert '3' not in out['roles']


def test_required_slots():
    assert stylist.required_slots('traje') == ['superior', 'calzado']
    assert stylist.required_slots('inferior') == ['superior', 'calzado']
    assert stylist.required_slots('capa_media') == ['inferior', 'calzado']
    assert stylist.required_slots(None) == ['superior', 'inferior', 'calzado']


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def ai(test_db, monkeypatch):
    """Cliente con _gemini simulado; `ai.prompts` guarda los prompts enviados
    y `ai.reply` es lo que contesta la IA."""
    from app import create_app
    monkeypatch.setenv('GEMINI_API_KEY', 'x')

    class State:
        prompts = []
        reply = {}
    st = State()

    def fake(prompt, **kw):
        st.prompts.append(prompt)
        return json.dumps(st.reply)
    monkeypatch.setattr(gr, '_gemini', fake)
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
    st.client = c
    return st


def _prenda(nombre, categoria, hexc='#808080', estado='bueno'):
    with database.get_db() as db:
        cur = db.execute("INSERT INTO wardrobe_items (nombre, categoria, color_hex, estado, created_at) "
                         "VALUES (?,?,?,?,?)", (nombre, categoria, hexc, estado, '2026-09-01'))
        db.commit()
        return cur.lastrowid


def test_desde_prenda_devuelve_tres_propuestas_validas(ai):
    jeans = _prenda('Jeans oscuros', 'Jeans', '#1c2333')
    camisa = _prenda('Camisa blanca', 'Camisa', '#ffffff')
    polo = _prenda('Polo navy', 'Polo', '#1f2a44')
    tenis = _prenda('Sneakers blancos', 'Sneakers', '#f5f5f5')
    botas = _prenda('Botas café', 'Botas', '#5a3a22')
    hoodie = _prenda('Hoodie', 'Sudadera')
    ai.reply = {'propuestas': [
        {'enfoque': 'Clásico seguro', 'nombre': 'A', 'item_ids': [camisa, tenis], 'rating': 4,
         'styling': ['Camisa fajada'], 'pieza_faltante': None},
        {'enfoque': 'Elevado', 'nombre': 'B', 'item_ids': [camisa, botas, jeans], 'rating': 5},
        {'enfoque': 'Con carácter', 'nombre': 'C', 'item_ids': [polo, 12345], 'rating': 9,
         'pieza_faltante': {'nombre': 'Chore jacket', 'por_que': 'capa'}},
    ]}
    r = ai.client.post('/guardarropa/api/ai-outfit-from-item',
                       json={'item_id': jeans, 'ocasion': 'Cita', 'contexto': 'terraza, fresco'})
    d = r.get_json()
    assert r.status_code == 200 and d['ok']
    assert len(d['propuestas']) == 3
    for p in d['propuestas']:
        assert p['item_ids'][0] == jeans
        assert p['item_ids'].count(jeans) == 1
    assert d['propuestas'][2]['rating'] == 5               # acotado a 1–5
    assert 12345 not in d['propuestas'][2]['item_ids']
    assert d['propuestas'][2]['autocompletado']            # completó el calzado
    assert d['propuestas'][0]['tips'] == ['Camisa fajada']
    # Compatibilidad: campos planos de la primera propuesta
    assert d['item_ids'] == d['propuestas'][0]['item_ids']
    prompt = ai.prompts[-1]
    assert 'terraza, fresco' in prompt
    assert 'azul marino' in prompt or 'denim' in prompt   # color legible, no solo hex
    assert f'ID {hoodie}:' in prompt                      # cita casual: hoodie sí es candidata


def test_ocasion_formal_no_ofrece_deportivo_a_la_ia(ai):
    _prenda('Camisa blanca', 'Camisa', '#ffffff')
    _prenda('Pantalón gris', 'Pantalón')
    _prenda('Derby negro', 'Zapatos formales', '#111111')
    hoodie = _prenda('Hoodie', 'Sudadera')
    ai.reply = {'propuestas': [{'nombre': 'X', 'item_ids': [hoodie]}]}
    r = ai.client.post('/guardarropa/api/ai-outfit', json={'ocasion': 'Formal'})
    d = r.get_json()
    assert f'ID {hoodie}:' not in ai.prompts[-1]
    assert hoodie not in d['item_ids']
    assert len(d['item_ids']) == 3                        # completado con camisa+pantalón+derby


def test_historial_de_outfits_con_la_ancla_va_al_prompt(ai):
    jeans = _prenda('Jeans oscuros', 'Jeans', '#1c2333')
    camisa = _prenda('Camisa blanca', 'Camisa', '#ffffff')
    _prenda('Sneakers', 'Sneakers', '#f5f5f5')
    ai.client.post('/guardarropa/api/outfit', json={'nombre': 'Viernes', 'ocasion': 'Casual',
                                                     'rating': 5, 'item_ids': [jeans, camisa]})
    ai.reply = {'propuestas': [{'nombre': 'X', 'item_ids': [camisa]}]}
    ai.client.post('/guardarropa/api/ai-outfit-from-item', json={'item_id': jeans})
    assert '«Viernes»' in ai.prompts[-1]


def test_errores(ai):
    assert ai.client.post('/guardarropa/api/ai-outfit-from-item', json={}).status_code == 400
    solo = _prenda('Jeans', 'Jeans')
    assert ai.client.post('/guardarropa/api/ai-outfit-from-item', json={'item_id': 999}).status_code == 404
    r = ai.client.post('/guardarropa/api/ai-outfit-from-item', json={'item_id': solo})
    assert r.status_code == 400
    assert not ai.prompts                                  # no gasta llamada a la IA
