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
    y, m = 2024, 11          # compra antes del día 22: la 1ª mensualidad cae en ese corte
    for k in range(1, meses + 1):
        if k not in saltar:
            _ins(f'{y}-{m:02d}-22', 'WALMART VENTA EN LIN3', 498.0 if k == 20 else 509.0)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return cid


def test_compra_inicial_sale_del_gasto(test_db):
    cid = _lavadora()
    mens = _ins('2025-01-22', '03 DE 12 LIVERPOOL', 211.0, pn=3, pt=12, grupo='g1')   # mensualidad: no se toca
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
    _lavadora(saltar=(5,))          # la 5ª (marzo 2025) no se importó
    with database.get_db() as db:
        msi.marcar_compras(db)
        c = msi.conciliar(db, '2026-09-26')[0]
    assert c['estado'] == 'Faltan mensualidades' and c['meses_sin_mensualidad'] == ['2025-03']
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
    assert r.status_code == 200 and 'WALMART VENTA EN LIN3 A 20 MSI' in html and '2025-03' in html
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
    assert '2025-03' in txt and 'Sin compra inicial' in txt     # la lavadora y las mensualidades sueltas


def _conciliar():
    with database.get_db() as db:
        msi.marcar_compras(db)
        db.commit()
        return {c['id']: c for c in msi.conciliar(db, '2026-09-27')}


def test_casos_reales_de_produccion(test_db):
    """Casos del JSON del usuario (2026-09-27)."""
    # Dos Viva Aerobus A 09 el mismo día: cada mensualidad va a su compra por monto
    v1 = _ins('2024-02-20', 'VIVA AEROBUS CIB A 09 MSI', 5919.63, cat='VIAJES', sub='Transporte')
    v2 = _ins('2024-02-20', 'VIVA AEROBUS CIB A 09 MSI (2)', 11895.45, cat='VIAJES', sub='Transporte')
    _ins('2024-05-22', '04 DE 09 VIVA AEROBUS CIB', 658.0, cat='VIAJES', sub='Transporte', pn=4, pt=9, grupo='a')
    _ins('2024-05-22', '04 DE 09 VIVA AEROBUS CIB (2)', 1322.0, cat='VIAJES', sub='Transporte', pn=4, pt=9, grupo='b')
    _ins('2025-12-23', 'VIVA AEROBUS CIB', 1346.51, cat='VIAJES', sub='Transporte')      # otra compra: no se liga
    # Compra que no procedió ($0)
    p0 = _ins('2025-11-12', 'ELPALACIOHIERRO COM A 09 MSI', 0.0, cat='ROPA', sub='Ropa')
    # La línea trae la cuota, no el total
    cr = _ins('2025-10-04', 'CRISTAL VILLAHERMOSA A 12 MSI', 1037.5, cat='VIVIENDA', sub='Artículos del hogar')
    for k in (10, 11, 12):
        _ins(f'2026-{k - 3:02d}-22', f'{k} DE 12 CRISTAL VILLAHERMOSA', 1038.0, cat='VIVIENDA',
             sub='Artículos del hogar', pn=k, pt=12, grupo='cr')
    # Primera mensualidad en el mismo corte (compra el 10, corte el 22)
    va = _ins('2025-03-10', 'VIVA AEROBUS CIB A 06 MSI', 5808.01, cat='VIAJES', sub='Transporte')
    for k in range(6):
        _ins(f'2025-{3 + k:02d}-22', 'VIVA AEROBUS CIB', 968.01 if k == 5 else 968.0, cat='VIAJES', sub='Transporte')
    c = _conciliar()
    assert [p['monto'] for p in c[v1]['pagos']] == [658.0] and [p['monto'] for p in c[v2]['pagos']] == [1322.0]
    assert c[p0]['estado'] == 'No procedió'
    # el usuario confirmó que la línea del 04/10 fue la 1ª mensualidad: 1 + las 10, 11 y 12
    assert c[cr]['linea_es_cuota'] and c[cr]['total'] == 12450.0 and c[cr]['pagadas'] == 4
    assert c[va]['estado'] == 'Liquidada' and c[va]['meses_sin_mensualidad'] == []


def test_mensualidades_de_otra_compra_mismo_comercio(test_db):
    """Training Innovation 2022 (12 MSI) no se lleva las mensualidades de la de 2023."""
    t = _ins('2022-04-16', 'TRAINING INNOVATION A 12 MSI', 4290.0, cat='APRENDIZAJE', sub='Cursos')
    for k in range(1, 13):
        y, m = (2022, 3 + k) if 3 + k <= 12 else (2023, k - 9)
        _ins(f'{y}-{m:02d}-22', f'{k:02d} DE 12 TRAINING INNOVATION', 358.0, cat='APRENDIZAJE', sub='Cursos',
             pn=k, pt=12, grupo='t1')
    for k, mes in ((3, '2023-06'), (4, '2023-07')):
        _ins(f'{mes}-22', f'0{k} DE 12 TRAINING INNOVATION (B)', 359.0, cat='APRENDIZAJE', sub='Cursos',
             pn=k, pt=12, grupo='t2')
    c = _conciliar()[t]
    assert c['estado'] == 'Liquidada' and all(p['fecha'] < '2023-04' for p in c['pagos'])


def test_compra_de_varios_productos_y_pago_diferido(test_db):
    """Palacio de Hierro 01/06/2025: 6 × $218.17 + 6 × $169.55 = $2,326.32; el
    Lacoste era «MSI + paga en enero» -> dos cargos al mes, y empiezan tarde."""
    pal = _ins('2025-06-01', 'ELPALACIOHIERRO COM A 06 MSI', 2326.32, cat='ROPA', sub='Ropa')
    for k in range(6):
        y, m = (2025, 8 + k) if 8 + k <= 12 else (2026, k - 4)
        _ins(f'{y}-{m:02d}-22', 'ELPALACIOHIERRO COM', 218.17, cat='ROPA', sub='Ropa')
        _ins(f'{y}-{m:02d}-22', 'ELPALACIOHIERRO COM (B)', 169.55, cat='ROPA', sub='Ropa')
    c = _conciliar()[pal]
    assert (c['estado'], c['pagadas'], c['pagado']) == ('Liquidada', 6, 2326.32)
    assert c['meses_sin_mensualidad'] == []


def test_varios_productos_con_planes_que_no_se_enciman(test_db):
    """El primer producto de jul a dic 2025 y el Lacoste («paga en enero») de ene a jun 2026."""
    pal = _ins('2025-06-01', 'ELPALACIOHIERRO COM A 06 MSI', 2326.32, cat='ROPA', sub='Ropa')
    for k in range(6):
        _ins(f'2025-{7 + k:02d}-22', 'ELPALACIOHIERRO COM', 218.17, cat='ROPA', sub='Ropa')
    for k in range(5):                                   # falta la 6ª del Lacoste (jun 2026)
        _ins(f'2026-{1 + k:02d}-22', 'ELPALACIOHIERRO COM', 169.55, cat='ROPA', sub='Ropa')
    c = _conciliar()[pal]
    assert c['planes'] == [{'cuota': 169.55, 'mensualidades': 5}, {'cuota': 218.17, 'mensualidades': 6}]
    assert c['estado'] == 'Faltan mensualidades' and c['meses_sin_mensualidad'] == ['2026-06']
    assert c['restante'] == 169.55


def test_mensualidades_con_otro_nombre_del_comercio(test_db):
    """Liverpool Zapopan 10/04/2025, 6 × $408.17: las mensualidades llegan como «LIVERPOOL GDL»."""
    lv = _ins('2025-04-10', 'LIVERPOOL ZAPOPAN A 06 MSI', 2449.0, cat='ROPA', sub='Calzado')
    for k in range(6):
        _ins(f'2025-{4 + k:02d}-22', 'LIVERPOOL GDL', 408.17 if k < 5 else 408.15, cat='ROPA', sub='Calzado')
    _ins('2025-05-03', 'LIVERPOOL GDL', 1200.0, cat='ROPA', sub='Ropa')          # otra compra: no se liga
    c = _conciliar()[lv]
    assert (c['estado'], c['pagadas'], c['pagado']) == ('Liquidada', 6, 2449.0)


def test_pista_de_cargos_con_el_monto_de_la_cuota(test_db):
    lv = _ins('2025-04-10', 'LIVERPOOL ZAPOPAN A 06 MSI', 2449.0, cat='ROPA', sub='Calzado')
    _ins('2025-04-22', 'LPOOL 0123 ZAP', 408.17, cat='ROPA', sub='Calzado')
    c = _conciliar()[lv]
    assert c['pagadas'] == 0 and [p['descripcion'] for p in c['misma_cuota']] == ['LPOOL 0123 ZAP']


def test_compra_pasada_a_meses_por_error_es_gasto_normal(test_db):
    """Pointmp Arellano $22 (15/03/2025): conveniencia que el banco pasó a 3 meses por error."""
    pa = _ins('2025-03-15', 'POINTMP ARELLANO A 03 MSI', 22.0, cat='FINANZAS', sub='Compra a meses')
    c = _conciliar()
    assert pa not in c
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (pa,)).fetchone()
    assert tuple(r) == ('SUPER', 'Conveniencia', 'GASTO')


def test_respuestas_del_usuario_2026_09_27(test_db):
    # Cristal: la línea del 04/10 fue la 1ª mensualidad -> gasto y mensualidad 1
    _ins('2026-07-22', '10 DE 12 CRISTAL VILLAHERMOSA', 1038.0, cat='VIVIENDA', sub='Artículos del hogar',
         pn=10, pt=12, grupo='cr')
    cr = _ins('2025-10-04', 'CRISTAL VILLAHERMOSA A 12 MSI', 1037.5, cat='OTROS', sub='')
    # Viva (2): mensualidades de $1,322 fueron de la familia -> PRESTAMOS
    _ins('2024-02-20', 'VIVA AEROBUS CIB A 09 MSI (2)', 11895.45, cat='VIAJES', sub='Transporte')
    v2m = _ins('2024-05-22', '04 DE 09 VIVA AEROBUS CIB (2)', 1322.0, cat='VIAJES', sub='Transporte', pn=4, pt=9, grupo='b')
    mia = _ins('2024-05-22', '04 DE 09 VIVA AEROBUS CIB', 658.0, cat='VIAJES', sub='Transporte', pn=4, pt=9, grupo='a')
    # Refri a 13 meses en Chedraui (el keyword la mandaba a SUPER)
    ref = _ins('2024-05-22', 'CHEDRAUI TDA EN LINEA', 569.0, cat='SUPER', sub='Súper', pn=8, pt=13, grupo='ch')
    super_ = _ins('2024-05-10', 'CHEDRAUI TDA EN LINEA', 569.0, cat='SUPER', sub='Súper')     # sin plazo: súper normal
    c = _conciliar()
    row = lambda i: tuple(database.get_db().__enter__().execute(
        "SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
    assert row(cr) == ('VIVIENDA', 'Artículos del hogar')
    assert c[cr]['total'] == 12450.0 and c[cr]['pagos'][0]['id'] == cr
    assert row(v2m) == ('PRESTAMOS', 'Prestado') and row(mia) == ('VIAJES', 'Transporte')
    assert row(ref) == ('VIVIENDA', 'Artículos del hogar') and row(super_) == ('SUPER', 'Súper')
