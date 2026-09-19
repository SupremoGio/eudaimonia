"""
test_finanzas_far_guad_por_monto.py — el usuario pidió blindar la
clasificación de FAR GUAD (Farmacias Guadalajara), que vende tanto
conveniencia/snacks como medicamentos bajo el mismo comercio: "todo lo que
venga de FAR GUAD y es menor a 200 pesos es alimentacion subcategoria
conveniencia todo lo que sea mayor a eso seguramente son medicamentos e
iria en salud subcategoria farmacia".

Como get_categoria_subcategoria() (config.py) solo recibe la descripción
(no el monto), esto se implementó como _corregir_far_guad(db) -- una
corrección a nivel DB, en el mismo patrón que _corregir_fusion_gio --
llamada desde apply_all_keywords() y upload_file() para blindar tanto la
aplicación manual de reglas como cada importación futura. El histórico ya
importado se corrige en la migración finanzas_far_guad_por_monto_2026_09.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.finanzas.estados.routes import _corregir_far_guad


def _insert(db, **kw):
    defaults = dict(fecha='2026-08-10', fecha_cargo=None, descripcion='FAR GUAD 1234',
                     monto=-150.0, banco='BBVA_TDC', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


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


# ── _corregir_far_guad (unidad) ─────────────────────────────────────────────

def test_menor_a_200_va_a_alimentacion_conveniencia(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, monto=-150.0)
        db.commit()
        n = _corregir_far_guad(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Conveniencia'


def test_mayor_o_igual_a_200_va_a_salud_farmacia(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, monto=-450.0)
        db.commit()
        n = _corregir_far_guad(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'SALUD'
    assert row['subcategoria'] == 'Farmacia'


def test_exactamente_200_va_a_salud_farmacia(test_db):
    """El umbral es 'menor a 200' para conveniencia -- 200 exacto ya cae
    del lado de farmacia."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, monto=-200.0)
        db.commit()
        n = _corregir_far_guad(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'SALUD'
    assert row['subcategoria'] == 'Farmacia'


def test_signo_negativo_no_afecta_el_umbral(test_db):
    """monto se guarda negativo para GASTO -- el umbral compara por
    magnitud (ABS), no por el signo guardado."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, monto=-199.99)
        db.commit()
        _corregir_far_guad(db)
        db.commit()
        row = db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'ALIMENTACION'


def test_no_toca_categoria_expense(test_db):
    """Un FAR GUAD marcado EXPENSE es una decisión explícita del usuario
    (algo que va a pedir reembolso) -- no se debe pisar por monto."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, monto=-500.0, categoria='EXPENSE', subcategoria='')
        db.commit()
        n = _corregir_far_guad(db)
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'EXPENSE'


def test_no_toca_descripciones_sin_far_guad(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='FARMACIA DEL AHORRO', monto=-150.0)
        db.commit()
        n = _corregir_far_guad(db)
        row = db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'OTROS'


def test_es_idempotente(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, monto=-150.0)
        db.commit()
        n1 = _corregir_far_guad(db)
        db.commit()
        n2 = _corregir_far_guad(db)
    assert n1 == 1
    assert n2 == 0


# ── Blindaje: apply_all_keywords y upload_file corren la corrección ────────

def test_apply_keywords_corrige_far_guad(client, test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='FAR GUAD 5678', monto=-80.0, categoria='OTROS')
        db.commit()

    resp = client.post('/finanzas/estados/api/keywords/apply-all')
    assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Conveniencia'


def test_upload_corrige_far_guad(client, monkeypatch, test_db):
    import io
    import modules.finanzas.estados.parsers as parsers_mod
    movimientos = [{
        'fecha': '2026-08-11', 'fecha_cargo': '2026-08-11',
        'descripcion': 'FAR GUAD 9999', 'monto': -650.0,
        'categoria': 'OTROS', 'subcategoria': '', 'tipo': 'GASTO', 'periodo': '',
    }]
    monkeypatch.setattr(parsers_mod, "parse_file", lambda path: movimientos)
    monkeypatch.setattr(parsers_mod, "detect_bank", lambda path: "BBVA_TDC")
    data = {"file": (io.BytesIO(b"contenido irrelevante"), "estado.pdf")}
    resp = client.post("/finanzas/estados/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion LIKE '%FAR GUAD 9999%'"
        ).fetchone()
    assert row['categoria'] == 'SALUD'
    assert row['subcategoria'] == 'Farmacia'
