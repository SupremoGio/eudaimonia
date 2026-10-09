"""
test_finanzas_abonos_tdc_devolucion.py — el usuario (2026-10-09): «cuando es
en tarjeta de crédito número negativo quiere decir que me regresaron algo»,
con «ABONO BBVA AMAZON» -209 / -379 / -356.99 (aclaración de cargos de
Amazon). Los parsers mandaban toda la columna de abonos a PAGO: salía del
gasto pero no le restaba nada a la compra.

_corregir_abonos_tdc: un abono en BBVA_TDC/INVEX que no es pago a la tarjeta
pasa a GASTO con monto negativo en la categoría del cargo original.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados.routes import _corregir_abonos_tdc


def _insert(db, **kw):
    d = dict(fecha='2026-10-09', descripcion='X', monto=100.0, banco='BBVA_TDC',
             categoria='PAGO', subcategoria='', tipo='PAGO')
    d.update(kw)
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (:fecha,:descripcion,:monto,:banco,:categoria,:subcategoria,:tipo)""", d).lastrowid


def _row(db, i):
    return tuple(db.execute("SELECT tipo, monto, categoria, subcategoria FROM est_movimientos WHERE id=?",
                            (i,)).fetchone())


def test_abono_amazon_resta_en_la_categoria_del_cargo(test_db):
    with database.get_db() as db:
        _insert(db, fecha='2026-10-07', descripcion='AMAZON', monto=356.99, tipo='GASTO',
                categoria='VIVIENDA', subcategoria='Artículos del hogar')
        _insert(db, fecha='2026-09-23', descripcion='AMAZON', monto=209.0, tipo='GASTO',
                categoria='CUIDADO_PERSONAL', subcategoria='Higiene')
        a = _insert(db, descripcion='ABONO BBVA AMAZON', monto=-356.99)
        b = _insert(db, descripcion='ABONO BBVA AMAZON', monto=209.0)            # CSV lo guarda positivo
        c = _insert(db, descripcion='ABONO BBVA AMAZON', monto=-379.0)           # sin cargo exacto
        assert _corregir_abonos_tdc(db) == 3
        assert _corregir_abonos_tdc(db) == 0                                       # idempotente
        assert _row(db, a) == ('GASTO', -356.99, 'VIVIENDA', 'Artículos del hogar')
        assert _row(db, b) == ('GASTO', -209.0, 'CUIDADO_PERSONAL', 'Higiene')
        assert _row(db, c) == ('GASTO', -379.0, 'VIVIENDA', 'Artículos del hogar')  # último cargo de Amazon


def test_pagos_a_la_tarjeta_no_se_tocan(test_db):
    with database.get_db() as db:
        ids = [_insert(db, descripcion=d, monto=-1500.0) for d in
               ('BMOVIL.PAGO TDC', 'PAGO TARJETA DE CREDITO', 'SPEI RECIBIDO BANORTE', 'ABONO RECIBIDO')]
        manual = _insert(db, descripcion='ABONO BBVA AMAZON', monto=-50.0, categoria='FINANZAS',
                         subcategoria='Reembolsable')
        debito = _insert(db, descripcion='ABONO BBVA AMAZON', monto=-51.0, banco='BBVA_DEB')
        assert _corregir_abonos_tdc(db) == 0
        assert all(_row(db, i)[0] == 'PAGO' for i in ids)
        assert _row(db, manual)[2] == 'FINANZAS' and _row(db, debito)[0] == 'PAGO'


def test_gemela_en_debito_no_se_convierte(test_db):
    with database.get_db() as db:
        _insert(db, descripcion='DEPOSITO X', monto=800.0, banco='BBVA_DEB', tipo='INGRESO', categoria='FINANZAS')
        tdc = _insert(db, descripcion='ABONO RARO', monto=-800.0)
        assert _corregir_abonos_tdc(db) == 0 and _row(db, tdc)[0] == 'PAGO'


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


def test_import_tdc_abono_resta_del_gasto(client, monkeypatch, test_db):
    import modules.finanzas.estados.parsers as parsers_mod
    movs = [
        dict(fecha='2026-10-07', fecha_cargo='2026-10-07', descripcion='AMAZON', monto=356.99,
             categoria='DIGITAL', subcategoria='', tipo='GASTO', periodo=None),
        dict(fecha='2026-10-09', fecha_cargo='2026-10-09', descripcion='ABONO BBVA AMAZON', monto=356.99,
             categoria='PAGO', subcategoria='', tipo='PAGO', periodo=None),
    ]
    monkeypatch.setattr(parsers_mod, "parse_file", lambda path: movs)
    monkeypatch.setattr(parsers_mod, "detect_bank", lambda path: "BBVA_TDC")
    resp = client.post("/finanzas/estados/api/upload",
                       data={"file": (io.BytesIO(b"x"), "tdc.xlsx")}, content_type="multipart/form-data")
    assert resp.status_code == 200
    r = client.get('/finanzas/estados/api/summary/by-category',
                   query_string={'date_from': '2026-10-01', 'date_to': '2026-10-31'}).get_json()
    assert not any(x['categoria'] == 'DIGITAL' and abs(x['total']) > 0.005 for x in r)
