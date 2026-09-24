"""
test_wishlist_duplicados.py — auditoría y fusión de duplicados en la Wishlist
de Guardarropa y en Prioridades de Finanzas: se queda el más completo (y a
igualdad el más reciente), hereda lo que le falte y la compra no se pierde.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database
from modules import wishlist_dedup as wd


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['app_ok'] = True
        sess['fin_ok'] = True
    return c


def _wl(nombre, created, **kw):
    cols = {'nombre': nombre, 'created_at': created, 'estado': 'evaluando', **kw}
    with database.get_db() as db:
        rid = db.execute(f"INSERT INTO wishlist_items ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         list(cols.values())).lastrowid
        db.commit()
        return rid


def _rows(tabla, nombre_like):
    with database.get_db() as db:
        return [dict(r) for r in db.execute(f"SELECT * FROM {tabla} WHERE LOWER(nombre) LIKE ?", (nombre_like,))]


def test_normaliza():
    assert wd.normaliza('  Apple   Watch ') == wd.normaliza('apple watch') == 'apple watch'
    assert wd.normaliza('Cámara') == 'camara'


def test_se_queda_el_mas_completo_y_hereda_el_precio(test_db):
    viejo = _wl('Apple Watch', '2026-01-01', precio_estimado=6000, url='https://apple.com')
    nuevo = _wl('apple watch ', '2026-09-01', marca='Apple', descripcion='Serie 10', score=80)
    _wl('Apple Watch Ultra', '2026-02-01')
    with database.get_db() as db:
        res = wd.fusionar(db, 'wishlist_items'); db.commit()
    assert res['borrados'] == 1
    rows = _rows('wishlist_items', 'apple watch%')
    assert len(rows) == 2                                    # Ultra no se toca
    aw = next(r for r in rows if r['id'] in (viejo, nuevo))
    assert aw['id'] == nuevo and aw['precio_estimado'] == 6000 and aw['url'] == 'https://apple.com'
    assert aw['score'] == 80


def test_a_igual_completitud_gana_el_mas_reciente(test_db):
    _wl('Sartenes', '2026-01-01', precio_estimado=900)
    nuevo = _wl('Sartenes', '2026-08-01', precio_estimado=1200)
    with database.get_db() as db:
        wd.fusionar(db, 'wishlist_items'); db.commit()
    rows = _rows('wishlist_items', 'sartenes')
    assert [r['id'] for r in rows] == [nuevo] and rows[0]['precio_estimado'] == 1200


def test_la_compra_no_se_pierde(test_db):
    _wl('Bocina', '2026-01-01', estado='comprado', purchased_at='2026-03-01')
    keep = _wl('Bocina', '2026-09-01', precio_estimado=800, marca='JBL')
    with database.get_db() as db:
        wd.fusionar(db, 'wishlist_items'); db.commit()
    r = _rows('wishlist_items', 'bocina')[0]
    assert r['id'] == keep and r['estado'] == 'comprado' and r['purchased_at'] == '2026-03-01'


def test_prioridades_apple_watch_duplicado(test_db):
    with database.get_db() as db:
        db.execute("INSERT INTO lista_prioridades (nombre, categoria, precio_estimado, created_at) VALUES ('Apple watch','Tecnología',0,'2026-09-20')")
        db.commit()
        assert len(wd.grupos(db, 'lista_prioridades')) == 1
        wd.fusionar(db, 'lista_prioridades'); db.commit()
    rows = _rows('lista_prioridades', 'apple watch')
    assert len(rows) == 1 and rows[0]['precio_estimado'] == 6000


def test_migracion_una_sola_vez(test_db):
    _wl('Kindle', '2026-01-01'); _wl('Kindle', '2026-02-01')
    database.init_db()                                          # ya registrada: no vuelve a fusionar
    assert len(_rows('wishlist_items', 'kindle')) == 2
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='wishlist_dedup_2026_09'"); db.commit()
    database.init_db()
    assert len(_rows('wishlist_items', 'kindle')) == 1


def test_aviso_y_auditoria(client):
    _wl('Apple Watch', '2026-01-01'); _wl('Apple Watch', '2026-02-01')
    assert client.get('/guardarropa/wishlist/api/existe?nombre=apple%20watch').get_json()['existe']['nombre'] == 'Apple Watch'
    assert client.get('/guardarropa/wishlist/api/existe?nombre=Pixel').get_json()['existe'] is None
    assert client.get('/finanzas/prioridades/api/existe?nombre=APPLE WATCH').get_json()['existe']
    audit = client.get('/guardarropa/wishlist/admin/duplicados').get_json()
    assert audit['wishlist_items']['grupos'][0]['nombre'] == 'Apple Watch'
    assert 'lista_prioridades' in audit
    # el aviso no bloquea: se puede agregar igual
    assert client.post('/guardarropa/wishlist/api/item', json={'nombre': 'Apple Watch'}).get_json()['ok']
