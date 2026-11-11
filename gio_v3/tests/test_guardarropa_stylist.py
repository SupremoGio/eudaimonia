"""
test_guardarropa_stylist.py — handoff Guardarropa v2 (/guardarropa/).

Sprint 1: la sugerencia del día sale del servidor con su razón y las piezas
olvidadas; cada pieza trae su último uso; rotación con meta del 70 %.
"""
import sys, os, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.guardarropa import stylist

HOY = datetime.date(2026, 11, 11)


def _it(i, nombre='Prenda', ultimo=None, usos=0, creada='2026-01-01', cat='Camisa'):
    return {'id': i, 'nombre': nombre, 'categoria': cat, 'ultimo_uso': ultimo, 'veces_usado': usos,
            'created_at': creada, 'color_hex': '#112233', 'foto': ''}


def _of(i, items, ocasion='Casual', ultimo=None, usos=0, rating=0):
    return {'id': i, 'nombre': f'Outfit {i}', 'ocasion': ocasion, 'ultimo_uso': ultimo,
            'veces_usado': usos, 'rating': rating, 'items': items}


# ── Piezas ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('it,txt,dias,olv', [
    (_it(1, ultimo='2026-11-11', usos=3), 'hoy', 0, False),
    (_it(1, ultimo='2026-11-10', usos=3), 'ayer', 1, False),
    (_it(1, ultimo='2026-08-01', usos=3), 'hace 102 d', 102, True),
    (_it(1, usos=0, creada='2026-01-01'), 'nunca usada', None, True),          # >90 d en el armario
    (_it(1, usos=0, creada='2026-11-01'), 'nunca usada', None, False),         # recién agregada
])
def test_pieza_ultimo_uso_y_olvidada(it, txt, dias, olv):
    p = stylist._pieza(it, HOY)
    assert (p['ultimo_uso_txt'], p['dias_sin_uso'], p['olvidada']) == (txt, dias, olv)


# ── Razón ────────────────────────────────────────────────────────────────────

def test_razon_con_olvidadas():
    items = [_it(1, 'Camisa lino', ultimo='2026-07-01', usos=2), _it(2, 'Pantalón gris', ultimo='2026-06-01', usos=3),
             _it(3, 'Mocasines', ultimo='2026-11-01', usos=9)]
    s = stylist.sugerencia_del_dia([_of(1, items, usos=1, ultimo='2026-05-01')], HOY)
    assert s['razon'].startswith('Reúne 2 prendas sin usar en más de 90 días')
    assert s['piezas_olvidadas'] == [1, 2]


def test_razon_con_clima_y_combinacion_mas_usada():
    blazer = _it(4, 'Blazer azul', ultimo='2026-11-01', usos=4, cat='Blazer / Saco')
    a = _of(1, [blazer, _it(5, ultimo='2026-11-02', usos=5)], ocasion='Business', usos=7, ultimo='2026-10-01')
    b = _of(2, [_it(6, ultimo='2026-11-03', usos=1)], ocasion='Business', usos=2, ultimo='2026-11-05')
    s = stylist.sugerencia_del_dia([a, b], HOY, clima={'temp': 19})
    assert s['outfit']['id'] == 1
    assert s['razon'] == 'El clima de hoy (19 °C) permite blazer azul; es tu combinación más usada de Business.'


def test_razon_nunca_vacia():
    nuevo = _of(1, [_it(1, ultimo='2026-11-09', usos=1)])
    assert stylist.sugerencia_del_dia([nuevo], HOY)['razon'] == 'Nunca lo has usado: buen día para estrenarlo.'
    viejo = _of(1, [_it(1, ultimo='2026-11-09', usos=1)], usos=3, ultimo='2026-10-30')
    assert stylist.sugerencia_del_dia([viejo], HOY)['razon'] == 'Es el que más tiempo lleva sin usarse (12 d).'


def test_sin_clima_se_omite():
    blazer = _it(4, 'Blazer', ultimo='2026-11-01', usos=4, cat='Blazer / Saco')
    s = stylist.sugerencia_del_dia([_of(1, [blazer], usos=1, ultimo='2026-11-02')], HOY)
    assert '°C' not in s['razon']


# ── Elección y «Otro» ────────────────────────────────────────────────────────

def test_elige_el_mas_olvidado_y_otro_no_repite():
    i = [_it(1, ultimo='2026-11-01', usos=1)]
    a = _of(1, i, ultimo='2026-10-01', usos=1)
    b = _of(2, i, ultimo='2026-09-01', usos=1)
    c = _of(3, i, ultimo=None)
    vacio = _of(4, [])                                            # sin prendas: no cuenta
    lista = [a, b, c, vacio]
    assert stylist.sugerencia_del_dia(lista, HOY)['outfit']['id'] == 3
    assert stylist.sugerencia_del_dia(lista, HOY, skip=['3'])['outfit']['id'] == 2
    assert stylist.sugerencia_del_dia(lista, HOY, skip=['3', '2'])['outfit']['id'] == 1
    assert stylist.sugerencia_del_dia(lista, HOY, skip=['3', '2', '1'])['outfit']['id'] == 3   # vuelve a empezar


def test_si_ya_se_uso_hoy_se_muestra_ese():
    i = [_it(1, ultimo='2026-11-11', usos=2)]
    lista = [_of(1, i, ultimo='2026-11-11', usos=2), _of(2, i, ultimo=None)]
    s = stylist.sugerencia_del_dia(lista, HOY)
    assert s['outfit']['id'] == 1 and s['usado_hoy']
    assert s['razon'] == 'Ya lo usaste hoy. Mañana te sugerimos otro.'
    assert stylist.sugerencia_del_dia(lista, HOY, skip=['1'])['outfit']['id'] == 2


def test_sin_outfits_no_falla():
    assert stylist.sugerencia_del_dia([], HOY) is None
    assert stylist.sugerencia_del_dia([_of(1, [])], HOY) is None


# ── Rotación ─────────────────────────────────────────────────────────────────

def test_rotacion_y_faltan_para_meta():
    usadas = [_it(i, ultimo='2026-11-01', usos=2) for i in range(1, 7)]           # 6 en uso
    olv = [_it(i, ultimo=f'2026-0{i - 6}-01', usos=1) for i in range(7, 11)]      # 4 olvidadas
    r = stylist.rotacion(usadas + olv, HOY)
    assert r['rotacion_pct'] == 60 and r['rotacion_meta'] == 70
    assert r['faltan_para_meta'] == 1                                              # ceil(10·0.7)=7 − 6
    assert r['olvidadas_n'] == 4 and [o['id'] for o in r['olvidadas']] == [7, 8, 9, 10]


def test_rotacion_en_meta_y_vacia():
    assert stylist.rotacion([_it(1, ultimo='2026-11-01', usos=1)], HOY)['faltan_para_meta'] == 0
    r = stylist.rotacion([], HOY)
    assert r == {**r, 'rotacion_pct': 0, 'faltan_para_meta': 0, 'olvidadas_n': 0, 'olvidadas': []}


def test_olvidadas_maximo_cinco():
    r = stylist.rotacion([_it(i, ultimo='2026-01-01', usos=1) for i in range(9)], HOY)
    assert r['olvidadas_n'] == 9 and len(r['olvidadas']) == 5


# ── Endpoint ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True
        yield c


def _seed():
    with database.get_db() as db:
        for i in (1, 2):
            db.execute("INSERT INTO wardrobe_items (id, nombre, categoria, color_hex, activo, veces_usado, created_at) "
                       "VALUES (?, ?, 'Camisa', '#123456', 1, 0, '2026-01-01')", (i, f'P{i}'))
        for o in (1, 2):
            db.execute("INSERT INTO outfits (id, nombre, ocasion, created_at) VALUES (?, ?, 'Casual', ?)",
                       (o, f'O{o}', f'2026-01-0{o}'))
            db.execute("INSERT INTO outfit_items (outfit_id, item_id) VALUES (?, ?)", (o, o))
        db.commit()


def test_api_sugerencia_skip(client):
    _seed()
    a = client.get('/guardarropa/api/sugerencia').get_json()['sugerencia']
    b = client.get(f"/guardarropa/api/sugerencia?skip={a['outfit']['id']}").get_json()['sugerencia']
    assert a['outfit']['id'] != b['outfit']['id']
    assert b['razon'] and b['piezas'][0]['ultimo_uso_txt'] == 'nunca usada'
    assert client.get('/guardarropa/').status_code == 200


# ── Sprint 2: encabezado + héroe ─────────────────────────────────────────────

def _hero(html):
    return html.split('id="gr-hero"', 1)[1].split('</section>', 1)[0]


def test_encabezado_un_solo_boton_y_wishlist(client):
    html = client.get('/guardarropa/').get_data(as_text=True)
    hd = html.split('<header class="gr-hd">', 1)[1].split('</header>', 1)[0]
    assert 'Vida · Estilo · 0 prendas' in hd
    assert 'class="eu-seg gr-tablist" role="tablist"' in hd
    root = html.split('id="gr"', 1)[1].split('id="gr-data"', 1)[0]
    assert hd.count('href="/guardarropa/wishlist/"') == 1 and root.count('href="/guardarropa/wishlist/"') == 1
    assert 'data-view-set' not in html and 'gr-viewseg' not in html
    for fuera in ('gr-side', 'gr-today-mini', 'Uso · 90 días', '<details class="eu-card gr-ai"'):
        assert fuera not in html, fuera
    assert 'value="vista:list"' in html                             # la vista pasa al menú de orden


def test_heroe_outfit_de_hoy_con_razon(client):
    _seed()
    html = client.get('/guardarropa/').get_data(as_text=True)
    h = _hero(html)
    assert html.index('id="gr-hero"') < html.index('id="gr-prendas"')   # lo primero que se ve
    assert 'Outfit de hoy · Casual' in h and 'class="gr-today-n">O1<' in h
    assert '<span>· nunca usada</span>' in h and 'gr-today-why' in h
    assert 'class="gr-today-idle num">0 usos<' in h                      # olvidada (0 usos, >90 d en el armario)
    assert 'js-today-use' in h and 'js-today-next' in h and 'js-coach' in h
    assert 'Rotación · 90 días' in h and 'meta ≥ 70%' in h and 'left:70%' in h
    assert '2 olvidadas · sin usar 90 d' in h and 'js-idle-filter' in h


def test_otro_no_repite_y_usado_hoy(client):
    _seed()
    a = client.get('/guardarropa/').get_data(as_text=True)
    oa = _hero(a).split('class="gr-today-n">', 1)[1].split('<', 1)[0]
    b = client.get('/guardarropa/?skip=' + ('1' if oa == 'O1' else '2')).get_data(as_text=True)
    assert _hero(b).split('class="gr-today-n">', 1)[1].split('<', 1)[0] != oa
    assert client.post('/guardarropa/api/outfit/2/usar').get_json()['ok']
    h = _hero(client.get('/guardarropa/').get_data(as_text=True))
    assert 'class="gr-today-n">O2<' in h and 'Usado hoy' in h and 'js-today-use' not in h
    assert '<span>· usada hoy</span>' in h


def test_usar_hoy_da_xp_una_vez(client):
    _seed()
    h = _hero(client.get('/guardarropa/').get_data(as_text=True))
    import modules.actividades.activity_defs as adefs
    act = adefs.get_by_key('outfit')
    if act and act['active'] and not act['hidden']:
        assert f"Usar hoy · +{act['pts']} XP" in h
        client.post('/actividades/api/activity/log', json={'key': 'outfit'})
        h = _hero(client.get('/guardarropa/').get_data(as_text=True))
        assert 'Usar hoy</button>' in h.replace('\n', '') or '· +' not in h.split('js-today-use', 1)[1].split('</button>', 1)[0]


def test_coach_es_un_modal_reutilizable(client):
    html = client.get('/guardarropa/').get_data(as_text=True)
    modal = html.split('id="gr-coach"', 1)[1]
    assert 'id="ai-go"' in modal and 'id="ai-occs"' in modal
    assert html.count('js-coach') >= 2                                  # héroe + pestaña Outfits
