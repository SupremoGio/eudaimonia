"""
test_finanzas_export_csv_bom.py — el usuario reportó acentos rotos al abrir
el CSV exportado en Excel ("ArtÃ¬culos del hogar" en vez de "Artículos del
hogar"). Causa: export_csv() escribía UTF-8 sin BOM; Excel, sin una señal
explícita, asume ANSI/Windows-1252. Fix: anteponer el BOM UTF-8 ('﻿')
al cuerpo de la respuesta y declarar charset=utf-8 explícitamente.
"""
import sys, os

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


def _insert(db, **kw):
    defaults = dict(fecha='2026-03-13', fecha_cargo='2026-03-13',
                     descripcion='Artículos del hogar', monto=-378.0,
                     banco='BBVA_TDC', periodo='', categoria='VIVIENDA',
                     subcategoria='Artículos del hogar', tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


def test_csv_export_incluye_bom_utf8(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db)
        db.commit()

    resp = client.get('/finanzas/estados/api/transactions/export/csv')
    assert resp.status_code == 200
    body = resp.get_data()
    assert body.startswith('﻿'.encode('utf-8'))


def test_csv_export_declara_charset_utf8(client, test_db):
    resp = client.get('/finanzas/estados/api/transactions/export/csv')
    assert 'charset=utf-8' in resp.headers.get('Content-Type', '').lower()


def test_csv_export_acentos_se_preservan_al_decodificar_utf8(client, test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='Artículos del hogar')
        db.commit()

    resp = client.get('/finanzas/estados/api/transactions/export/csv')
    body = resp.get_data()
    text = body.decode('utf-8-sig')
    assert 'Artículos del hogar' in text
