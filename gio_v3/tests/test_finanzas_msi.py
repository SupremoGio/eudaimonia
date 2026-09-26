"""
test_finanzas_msi.py — compras a meses: la compra inicial («… A 20 MSI») no
cuenta como gasto (cuentan las mensualidades) y la conciliación dice cuánto va
pagado, qué meses no tienen mensualidad y si cuadra.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados import msi


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _ins(fecha, desc, monto, cat='VIVIENDA', sub='Artículos del hogar', tipo='GASTO', banco='BBVA_TDC',
         pn=None, pt=None, grupo=None):
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo,
                            parcialidad_num, parcialidad_total, compra_msi_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                         (fecha, desc, monto, banco, cat, sub, tipo, pn, pt, grupo)).lastrowid
        db.commit()
    return mid


def _lavadora(meses=20, saltar=()):
    cid = _ins('2024-11-17', 'WALMART VENTA EN LIN3 A 20 MSI', -10169.0)
    y, m = 2024, 12
    for k in range(1, meses + 1):
        if k not in saltar:
            _ins(f'{y}-{m:02d}-22', 'WALMART VENTA EN LIN3', 498.0 if k == 20 else 509.0)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return cid


def test_compra_inicial_sale_del_gasto(test_db):
    cid = _lavadora()
    mens = _ins('2025-01-22', '03 DE 12 MACSTORE', 211.0, pn=3, pt=12, grupo='g1')   # mensualidad: no se toca
    with database.get_db() as db:
        assert msi.marcar_compras(db) == 1
        db.commit()
        r = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (cid,)).fetchone()
        assert tuple(r) == ('FINANZAS', 'Compra a meses')
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (mens,)).fetchone()[0] == 'VIVIENDA'
        assert msi.marcar_compras(db) == 0
    from modules.finanzas.estados.routes import _PAGO_CATS
    from modules.finanzas.budget import _GASTO_WHERE
    with database.get_db() as db:
        for where in (_PAGO_CATS, _GASTO_WHERE):
            n = db.execute(f"SELECT COUNT(*) FROM est_movimientos WHERE id=? AND {where}", (cid,)).fetchone()[0]
            assert n == 0


def test_conciliacion_liquidada_y_con_faltantes(test_db):
    _lavadora()
    with database.get_db() as db:
        msi.marcar_compras(db)
        c = msi.conciliar(db, '2026-09-26')[0]
    assert (c['estado'], c['pagadas'], c['pagado'], c['restante']) == ('Liquidada', 20, 10169.0, 0)


def test_conciliacion_detecta_mes_sin_mensualidad(test_db):
    _lavadora(saltar=(5,))          # la 5ª (abril 2025) no se importó
    with database.get_db() as db:
        msi.marcar_compras(db)
        c = msi.conciliar(db, '2026-09-26')[0]
    assert c['estado'] == 'Faltan mensualidades' and c['meses_sin_mensualidad'] == ['2025-04']
    assert c['pagadas'] == 19 and c['restante'] == 509.0


def test_mensualidades_sin_compra_inicial(test_db):
    for k in (1, 2, 4):
        _ins(f'2023-0{k}-22', f'0{k} DE 06 MEN S FACTORY', 462.0, cat='ROPA', sub='Ropa', pn=k, pt=6, grupo='mf')
    with database.get_db() as db:
        c = msi.conciliar(db, '2026-09-26')[0]
    assert c['estado'] == 'Sin compra inicial' and c['mensualidades_faltantes'] == [3]


def test_pagina_de_conciliacion(client):
    _lavadora(saltar=(5,))
    with database.get_db() as db:      # lo hacen la migración y cada import
        msi.marcar_compras(db)
        db.commit()
    r = client.get('/finanzas/estados/admin/msi', query_string={'formato': 'html'})
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'WALMART VENTA EN LIN3 A 20 MSI' in html and '2025-04' in html
    assert client.get('/finanzas/estados/admin/msi').get_json()['compras'][0]['estado'] == 'Faltan mensualidades'


def test_csv_de_pendientes(client):
    _lavadora(saltar=(5,))
    for k in (1, 2):
        _ins(f'2023-0{k}-22', f'0{k} DE 02 PRIVALIA', 100.0, cat='ROPA', sub='Ropa', pn=k, pt=2, grupo='pv')
    with database.get_db() as db:
        msi.marcar_compras(db)
        db.commit()
    r = client.get('/finanzas/estados/admin/msi', query_string={'formato': 'csv', 'solo': 'pendientes'})
    txt = r.get_data(as_text=True)
    assert r.status_code == 200 and 'COMENTARIOS' in txt and 'WALMART VENTA EN LIN3 A 20 MSI' in txt
    assert '2025-04' in txt and 'Sin compra inicial' in txt     # la lavadora y las mensualidades sueltas
