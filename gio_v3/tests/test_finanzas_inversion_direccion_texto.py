"""
test_finanzas_inversion_direccion_texto.py — el usuario reportó con datos
reales que varias aportaciones a CETES ("NAFIN 12206 CETESDIRECTO
DOMICILIACION", "SPEI ENVIADO STP") habían quedado como categoria=CETES/
subcategoria=RETIRO, cuando en realidad es dinero SALIENDO de su cuenta
para invertir (APORTACION): "SI DICE DOMICILIACION O ENVIADO QUIERE DECIR
QUE YO LO METI A INVERTIR... NO ES UN RETIRO... SALE DE MI CUENTA".

Causa raíz en el post-proceso de /api/upload (routes.py): la dirección
(APORTACION/RETIRO) se derivaba de `tipo` (INGRESO/GASTO), que no es
confiable para estos movimientos (puede venir mal según cómo el banco
emisor reportó el movimiento — el mismo problema de tipo inconsistente ya
visto en la auditoría de duplicados DEB/TDC). Además `_NOT_INVERSION`
("SPEI ENVIADO" entre sus patrones) se revisaba ANTES de detectar la
plataforma, así que cualquier aportación real a GBM/CETESDirecto/STP vía
SPEI ENVIADO se desviaba a PAGO_TDC en vez de reconocerse como inversión.

Fix: la plataforma se detecta primero; _NOT_INVERSION solo aplica si no
se reconoció ninguna plataforma; y la dirección se deriva del texto
("ENVIADO"/"DOMICILIACION" -> APORTACION, "RECIBIDO" -> RETIRO), con el
tipo como respaldo solo si el texto no trae ninguna de esas dos señales.
"""
import io
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


def _upload(client, monkeypatch, movimientos, bank="BBVA_DEB"):
    import modules.finanzas.estados.parsers as parsers_mod
    monkeypatch.setattr(parsers_mod, "parse_file", lambda path: movimientos)
    monkeypatch.setattr(parsers_mod, "detect_bank", lambda path: bank)
    data = {"file": (io.BytesIO(b"contenido irrelevante, parse_file esta mockeado"), "estado.pdf")}
    return client.post("/finanzas/estados/api/upload", data=data, content_type="multipart/form-data")


def _mov(**kw):
    defaults = dict(fecha="2026-01-09", fecha_cargo="2026-01-09",
                     descripcion="SPEI ENVIADO STP", monto=42200.0,
                     categoria="INVERSION", subcategoria="", tipo="INGRESO", periodo="")
    defaults.update(kw)
    return defaults


def _row_by_desc(db, descripcion):
    return db.execute(
        "SELECT * FROM est_movimientos WHERE descripcion=?", (descripcion,)
    ).fetchone()


def test_domiciliacion_es_aportacion_aunque_tipo_sea_ingreso(client, monkeypatch, test_db):
    """El caso real: tipo llegó como INGRESO (dinero "entrando" según el
    parser) pero el texto deja claro que es una domiciliación saliendo de
    la cuenta -- debe ser APORTACION, no RETIRO."""
    resp = _upload(client, monkeypatch, [_mov(
        descripcion="NAFIN 12206 CETESDIRECTO DOMICILIACION", monto=4000.0, tipo="INGRESO",
    )])
    assert resp.status_code == 200
    import database
    with database.get_db() as db:
        row = _row_by_desc(db, "NAFIN 12206 CETESDIRECTO DOMICILIACION")
    assert row['tipo'] == 'INVERSION'
    assert row['categoria'] == 'CETES'
    assert row['subcategoria'] == 'APORTACION'


def test_spei_enviado_stp_es_aportacion_a_cetes(client, monkeypatch, test_db):
    resp = _upload(client, monkeypatch, [_mov(descripcion="SPEI ENVIADO STP", monto=50000.0, tipo="INGRESO")])
    assert resp.status_code == 200
    import database
    with database.get_db() as db:
        row = _row_by_desc(db, "SPEI ENVIADO STP")
    assert row['tipo'] == 'INVERSION'
    assert row['categoria'] == 'CETES'
    assert row['subcategoria'] == 'APORTACION'


def test_spei_enviado_gbm_es_aportacion_a_gbm(client, monkeypatch, test_db):
    resp = _upload(client, monkeypatch, [_mov(
        descripcion="SPEI ENVIADO GBM 601 1404260INVERSION MAYO", monto=15300.0, tipo="INGRESO",
    )])
    assert resp.status_code == 200
    import database
    with database.get_db() as db:
        row = _row_by_desc(db, "SPEI ENVIADO GBM 601 1404260INVERSION MAYO")
    assert row['tipo'] == 'INVERSION'
    assert row['categoria'] == 'GBM'
    assert row['subcategoria'] == 'APORTACION'


def test_spei_recibido_sigue_siendo_retiro(client, monkeypatch, test_db):
    """El caso opuesto: dinero volviendo a la cuenta sí debe seguir como
    RETIRO."""
    resp = _upload(client, monkeypatch, [_mov(
        descripcion="SPEI RECIBIDONAFIN 135 EGRESOS SPEI SVD", monto=10000.0, tipo="INGRESO",
    )])
    assert resp.status_code == 200
    import database
    with database.get_db() as db:
        row = _row_by_desc(db, "SPEI RECIBIDONAFIN 135 EGRESOS SPEI SVD")
    assert row['tipo'] == 'INVERSION'
    assert row['categoria'] == 'CETES'
    assert row['subcategoria'] == 'RETIRO'


def test_spei_enviado_a_tdc_sin_plataforma_sigue_yendo_a_pago_tdc(client, monkeypatch, test_db):
    """Un SPEI ENVIADO genuino de pago de tarjeta (sin ninguna plataforma
    de inversión reconocida en la descripción) debe seguir excluyéndose
    como PAGO_TDC -- el fix no debe convertir todo SPEI ENVIADO en
    inversión. Termina como MOVIMIENTO_INTERNO (no PAGO) porque
    _es_movimiento_interno() -- ampliado en la auditoría de duplicados de
    esta misma sesión -- también reconoce "SPEI ENVIADO HSBC" y lo
    reclasifica un paso más adelante en el mismo /api/upload."""
    resp = _upload(client, monkeypatch, [_mov(
        descripcion="SPEI ENVIADO HSBC 021 0509260TDC HSBC", monto=502.0, tipo="GASTO",
    )])
    assert resp.status_code == 200
    import database
    with database.get_db() as db:
        row = _row_by_desc(db, "SPEI ENVIADO HSBC 021 0509260TDC HSBC")
    assert row['categoria'] == 'PAGO_TDC'
    assert row['tipo'] == 'MOVIMIENTO_INTERNO'
