"""
test_finanzas_descargas_presupuesto.py — botones «Descargar» de Consumo y
Presupuesto (el usuario los pidió para armar su presupuesto en una hoja de
cálculo). Ambos CSV llevan BOM UTF-8 como el de Estados de cuenta.
"""
import csv, io, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


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


def _rows(resp):
    body = resp.get_data().decode('utf-8')
    assert body.startswith('﻿')
    return list(csv.reader(io.StringIO(body[1:])))


def test_consumo_csv_estima_costo_mensual(client, test_db):
    import database
    with database.get_db() as db:
        db.execute("UPDATE consumo_productos SET activo=0")
        pid = db.execute("INSERT INTO consumo_productos (nombre, categoria, created_at) "
                         "VALUES ('Café en grano', 'Despensa', '2026-01-01')").lastrowid
        for f, p in [('2026-06-01', 300), ('2026-06-16', 300), ('2026-07-01', 300)]:
            db.execute("INSERT INTO consumo_compras (producto_id, fecha_compra, precio_total, created_at) "
                       "VALUES (?,?,?,?)", (pid, f, p, f))
        from modules.finanzas.consumo import _calcular_metricas
        _calcular_metricas(pid, db)
        db.commit()

    resp = client.get('/finanzas/consumo/export.csv')
    assert resp.status_code == 200
    assert 'attachment' in resp.headers['Content-Disposition']
    rows = _rows(resp)
    head, cafe = rows[0], rows[1]
    assert head[:2] == ['Categoría', 'Producto']
    r = dict(zip(head, cafe))
    assert r['Producto'] == 'Café en grano'
    assert float(r['Frecuencia (días)']) == 15.0
    assert float(r['Estimado mensual']) == 600.0      # 300 × 30 / 15
    assert float(r['Estimado anual']) == 7200.0
    assert rows[-1][0].startswith('TOTAL') and float(rows[-1][5]) == 600.0


def test_presupuesto_csv_gasto_por_categoria_y_mes(client, test_db):
    # Mismos números que la Radiografía del mes (sale de _calc_budget), que
    # suma el gasto tal como está guardado (positivo en los datos reales).
    import database
    with database.get_db() as db:
        for fecha, cat, tipo, monto in [
            ('2026-08-05', 'VIVIENDA', 'GASTO', 1000), ('2026-09-05', 'VIVIENDA', 'GASTO', 3000),
            ('2026-09-10', 'OCIO', 'GASTO', 500), ('2026-09-01', 'NOMINA_X', 'INGRESO', 10000),
        ]:
            db.execute("INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, "
                       "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,?)",
                       (fecha, fecha, 'x', monto, 'BBVA', '', cat, '', tipo))
        db.commit()

    resp = client.get('/finanzas/budget/api/export?hasta=2026-09&n=2')
    assert resp.status_code == 200
    assert 'presupuesto_2026-08_a_2026-09.csv' in resp.headers['Content-Disposition']
    rows = _rows(resp)
    assert rows[0] == ['Grupo', 'Categoría', '2026-08', '2026-09', 'Promedio', 'Límite mensual']
    by = {(r[0], r[1]): r for r in rows if len(r) > 1}
    viv = by[('Necesidades', 'Vivienda')]
    assert [float(v) for v in viv[2:5]] == [1000.0, 3000.0, 2000.0]
    assert float(by[('Deseos', 'Ocio')][3]) == 500.0
    assert float(by[('Resumen', 'Ingreso')][3]) == 10000.0


def test_presupuesto_csv_parametros_invalidos(client, test_db):
    assert client.get('/finanzas/budget/api/export?hasta=abc').status_code == 400
