"""
test_finanzas_dedup_import_blindaje.py — "blinda que no pase en el futuro":
el usuario confirmó que los duplicados DEB/TDC de SPEI RECIBIDO/DEPOSITO DE
TERCERO son reales y pidió reforzar el import para que no vuelvan a colarse.

Causa por la que el dedup existente (clave fecha+monto+tipo) no los
atrapaba: el mismo movimiento real, visto desde el lado BBVA_DEB vs. desde
BBVA_TDC/HSBC/INVEX, a veces llega con tipo distinto (uno como INGRESO, el
otro como PAGO/GASTO/INVERSION según cómo lo interprete el parser del banco
emisor) -- confirmado con datos reales: el par 2143 (BBVA_DEB, INGRESO) /
2236 (BBVA_TDC, PAGO) y el par 2121 (BBVA_DEB, INVERSION) / 2238 (BBVA_TDC,
PAGO).

Fix en upload_file() (routes.py): para cualquier fila nueva que NO sea
BBVA_DEB, con "SPEI RECIBIDO" o "DEPOSITO DE TERCERO" en la descripción, se
descarta si ya existe una fila BBVA_DEB con el mismo día y monto -- sin
importar el tipo de ninguna de las dos.
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


def _upload(client, monkeypatch, movimientos, bank="BBVA_TDC"):
    import modules.finanzas.estados.parsers as parsers_mod
    monkeypatch.setattr(parsers_mod, "parse_file", lambda path: movimientos)
    monkeypatch.setattr(parsers_mod, "detect_bank", lambda path: bank)
    data = {"file": (io.BytesIO(b"contenido irrelevante, parse_file esta mockeado"), "estado.pdf")}
    return client.post("/finanzas/estados/api/upload", data=data, content_type="multipart/form-data")


def _mov(**kw):
    defaults = dict(fecha="2026-08-04", fecha_cargo="2026-08-04",
                     descripcion="SPEI RECIBIDONU MEXICO 638 0040826TRANSFERENCIA",
                     monto=3000.0, categoria="FINANZAS", subcategoria="Transferencia recibida",
                     tipo="INGRESO", periodo="")
    defaults.update(kw)
    return defaults


def _insert_existing(db, **kw):
    defaults = dict(fecha='2026-08-04', fecha_cargo='2026-08-04',
                     descripcion='SPEI RECIBIDONU MEXICO 638 0040826TRANSFERENCIA',
                     monto=3000.0, banco='BBVA_DEB', periodo='', categoria='VIVIENDA',
                     subcategoria='Aportación renta', tipo='INGRESO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


def test_spei_recibido_tdc_se_descarta_si_ya_existe_gemelo_deb(client, monkeypatch, test_db):
    """El caso real: el lado BBVA_DEB ya está en la DB (de una importación
    previa); ahora llega el mismo movimiento otra vez, esta vez detectado
    como BBVA_TDC y con tipo distinto (PAGO en vez de INGRESO) -- debe
    descartarse, no insertarse."""
    import database
    with database.get_db() as db:
        _insert_existing(db)
        db.commit()

    resp = _upload(client, monkeypatch, [_mov(
        descripcion='SPEI RECIBIDONU MEXICO / 0192086653 638 0040826TRANSFERENCIA',
        tipo='PAGO', categoria='FINANZAS', subcategoria='Pago servicios',
    )], bank="BBVA_TDC")
    data = resp.get_json()
    assert data['inserted'] == 0
    assert data['skipped'] == 1

    with database.get_db() as db:
        n = db.execute(
            "SELECT COUNT(*) c FROM est_movimientos WHERE fecha='2026-08-04' AND ROUND(monto,2)=3000.0"
        ).fetchone()['c']
    assert n == 1  # sigue habiendo solo la fila BBVA_DEB original


def test_deposito_de_tercero_tdc_se_descarta_si_ya_existe_gemelo_deb(client, monkeypatch, test_db):
    import database
    with database.get_db() as db:
        _insert_existing(db, descripcion='DEPOSITO DE TERCERO REFBNTC00305286 PREPAGO GDLAC BMRCASH',
                          monto=4582.0, categoria='FINANZAS', subcategoria='Reembolsable', tipo='INVERSION')
        db.commit()

    resp = _upload(client, monkeypatch, [_mov(
        descripcion='DEPOSITO DE TERCERO / REFBNTC00305286 PREPAGO GDLAC BMRCASH',
        monto=4582.0, tipo='PAGO', categoria='FINANZAS', subcategoria='Pago servicios',
    )], bank="BBVA_TDC")
    data = resp.get_json()
    assert data['inserted'] == 0
    assert data['skipped'] == 1


def test_spei_recibido_en_bbva_deb_no_se_bloquea_a_si_mismo(client, monkeypatch, test_db):
    """La primera vez que llega (sin gemelo previo en la DB) debe insertarse
    normal, sea cual sea el banco."""
    resp = _upload(client, monkeypatch, [_mov()], bank="BBVA_DEB")
    data = resp.get_json()
    assert data['inserted'] == 1
    assert data['skipped'] == 0


def test_no_descarta_spei_recibido_tdc_sin_gemelo_deb(client, monkeypatch, test_db):
    """Sin ninguna fila BBVA_DEB previa que haga match, un SPEI RECIBIDO en
    BBVA_TDC sí debe insertarse -- no se bloquea todo lo que venga de TDC,
    solo lo que sea gemelo confirmado de un BBVA_DEB existente."""
    resp = _upload(client, monkeypatch, [_mov(
        descripcion='SPEI RECIBIDONU MEXICO / 0999999999 638 UNICO',
        tipo='PAGO', categoria='FINANZAS', subcategoria='Pago servicios',
    )], bank="BBVA_TDC")
    data = resp.get_json()
    assert data['inserted'] == 1
    assert data['skipped'] == 0


def test_no_afecta_movimientos_sin_spei_recibido_ni_deposito_de_tercero(client, monkeypatch, test_db):
    """Una compra normal (WALMART) con la misma fecha+monto que algo en
    BBVA_DEB no debe descartarse por esta regla -- solo aplica al patrón
    SPEI RECIBIDO / DEPOSITO DE TERCERO. Se usa un tipo distinto al de la
    fila existente para aislar la regla nueva del dedup original
    (fecha,monto,tipo), que de otro modo también la bloquearía y no
    probaría lo que este test quiere confirmar."""
    import database
    with database.get_db() as db:
        _insert_existing(db, descripcion='WALMART VENTA EN LINEA', monto=509.0,
                          categoria='ALIMENTACION', subcategoria='Súper', tipo='GASTO')
        db.commit()

    resp = _upload(client, monkeypatch, [_mov(
        descripcion='WALMART VENTA EN LINEA OTRA SUCURSAL', monto=509.0,
        tipo='INGRESO', categoria='ALIMENTACION', subcategoria='Súper',
    )], bank="BBVA_TDC")
    data = resp.get_json()
    assert data['inserted'] == 1
    assert data['skipped'] == 0


def test_fecha_distinta_no_se_descarta(client, monkeypatch, test_db):
    import database
    with database.get_db() as db:
        _insert_existing(db, fecha='2026-08-04')
        db.commit()

    resp = _upload(client, monkeypatch, [_mov(fecha='2026-08-05')], bank="BBVA_TDC")
    data = resp.get_json()
    assert data['inserted'] == 1
    assert data['skipped'] == 0


def test_monto_distinto_no_se_descarta(client, monkeypatch, test_db):
    import database
    with database.get_db() as db:
        _insert_existing(db, monto=3000.0)
        db.commit()

    resp = _upload(client, monkeypatch, [_mov(monto=3001.0)], bank="BBVA_TDC")
    data = resp.get_json()
    assert data['inserted'] == 1
    assert data['skipped'] == 0
