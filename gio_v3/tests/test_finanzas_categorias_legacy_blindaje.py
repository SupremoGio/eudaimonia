"""
test_finanzas_categorias_legacy_blindaje.py — el usuario reportó que
CASA/HOGAR y VIVERES/SUPER seguían reapareciendo pese a migraciones de
barrido previas (finanzas_ejecuta_esto_batch_2026_09,
finanzas_barrido_comida_viajes_legacy_2026_09): "vivienda y casa/hogar es
lo mismo... misma cosa con viveres/super... esas categorias viejas no
deben exisitir cuantas veces te lo debo repetir".

Causa raíz (mismo patrón ya diagnosticado en _corregir_fusion_gio): barrer
solo est_movimientos no basta -- reglas guardadas en est_keywords ANTES
del retiro de estas categorías todavía tenían categoria=<vieja>, y cada
"Aplicar todas a lo existente" o import nuevo las revivía, deshaciendo el
barrido. _corregir_categorias_legacy(db) corrige AMBAS tablas y corre en
cada apply_all_keywords()/upload_file(); el histórico ya importado se
corrige en la migración finanzas_unifica_categorias_legacy_2026_09.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados.routes import _corregir_categorias_legacy


def _insert_tx(db, **kw):
    defaults = dict(fecha='2026-08-10', fecha_cargo=None, descripcion='X',
                     monto=-100.0, banco='BBVA_DEB', periodo='', categoria='CASA/HOGAR',
                     subcategoria='', tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


def _insert_kw(db, keyword, categoria, subcategoria=''):
    cur = db.execute(
        "INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES (?,?,?)",
        (keyword, categoria, subcategoria),
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


# ── _corregir_categorias_legacy (unidad) — est_movimientos ─────────────────

def test_casa_hogar_va_a_vivienda_renta(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, categoria='CASA/HOGAR', subcategoria='Alquiler')
        db.commit()
        _corregir_categorias_legacy(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_viveres_super_va_a_alimentacion_super(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, categoria='VIVERES/SUPER', subcategoria='Supermercado')
        db.commit()
        _corregir_categorias_legacy(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Súper'


def test_comida_rest_va_a_alimentacion_restaurante(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, categoria='COMIDA/REST', subcategoria='Antojitos')
        db.commit()
        _corregir_categorias_legacy(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Restaurante'


def test_viajes_vuelos_va_a_viajes_otros(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, categoria='VIAJES/VUELOS', subcategoria='Salidas')
        db.commit()
        _corregir_categorias_legacy(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'VIAJES'
    assert row['subcategoria'] == 'Otros'


def test_categorias_vigentes_no_se_tocan(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, categoria='VIVIENDA', subcategoria='Renta')
        db.commit()
        n = _corregir_categorias_legacy(db)
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_es_idempotente(test_db):
    with database.get_db() as db:
        _insert_tx(db, categoria='CASA/HOGAR')
        db.commit()
        n1 = _corregir_categorias_legacy(db)
        db.commit()
        n2 = _corregir_categorias_legacy(db)
    assert n1 == 1
    assert n2 == 0


# ── _corregir_categorias_legacy (unidad) — est_keywords (la causa raíz) ────

def test_regla_guardada_con_categoria_vieja_se_corrige(test_db):
    """Esta es la causa raíz real: una regla en est_keywords con
    categoria='CASA/HOGAR' guardada antes del retiro de esa categoria."""
    with database.get_db() as db:
        kw_id = _insert_kw(db, 'MI RENTA MENSUAL', 'CASA/HOGAR', 'Alquiler')
        db.commit()
        _corregir_categorias_legacy(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_keywords WHERE id=?", (kw_id,)).fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_regla_vigente_no_se_toca(test_db):
    with database.get_db() as db:
        kw_id = _insert_kw(db, 'ALGO', 'VIVIENDA', 'Renta')
        db.commit()
        n = _corregir_categorias_legacy(db)
        row = db.execute("SELECT categoria, subcategoria FROM est_keywords WHERE id=?", (kw_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'VIVIENDA'


# ── Blindaje: la regla vieja NO revive filas tras apply-all / upload ───────

def test_regla_vieja_ya_no_revive_casa_hogar_en_apply_all(client, test_db):
    """Antes del fix: una regla CASA/HOGAR guardada clasificaba nuevas
    transacciones a CASA/HOGAR en cada apply-all, deshaciendo cualquier
    barrido de datos. Ahora _corregir_categorias_legacy corre justo
    después y la corrige en el mismo request."""
    with database.get_db() as db:
        _insert_kw(db, 'RENTA DEPTO XYZ', 'CASA/HOGAR', 'Alquiler')
        tx_id = _insert_tx(db, descripcion='PAGO RENTA DEPTO XYZ', categoria='OTROS', subcategoria='')
        db.commit()

    resp = client.post('/finanzas/estados/api/keywords/apply-all')
    assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
        kw_row = db.execute("SELECT categoria FROM est_keywords WHERE keyword='RENTA DEPTO XYZ'").fetchone()
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'
    assert kw_row['categoria'] == 'VIVIENDA'


def test_upload_corrige_categoria_legacy(client, monkeypatch, test_db):
    import io
    import modules.finanzas.estados.parsers as parsers_mod
    movimientos = [{
        'fecha': '2026-08-11', 'fecha_cargo': '2026-08-11',
        'descripcion': 'SUPER ABC', 'monto': -350.0,
        'categoria': 'VIVERES/SUPER', 'subcategoria': 'Supermercado', 'tipo': 'GASTO', 'periodo': '',
    }]
    monkeypatch.setattr(parsers_mod, "parse_file", lambda path: movimientos)
    monkeypatch.setattr(parsers_mod, "detect_bank", lambda path: "BBVA_TDC")
    data = {"file": (io.BytesIO(b"contenido irrelevante"), "estado.pdf")}
    resp = client.post("/finanzas/estados/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion LIKE '%SUPER ABC%'"
        ).fetchone()
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Súper'


# ── Migración histórica ─────────────────────────────────────────────────────

def _reset_migration(db):
    db.execute("DELETE FROM migration_log WHERE version='finanzas_unifica_categorias_legacy_2026_09'")


def test_migracion_corrige_movimientos_y_keywords_historicos(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_casa = _insert_tx(db, descripcion='CASA X', categoria='CASA/HOGAR', subcategoria='Internet')
        tx_viveres = _insert_tx(db, descripcion='VIVERES X', categoria='VIVERES/SUPER', subcategoria='')
        kw_id = _insert_kw(db, 'OLD RULE', 'CASA/HOGAR', 'Alquiler')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row_casa = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_casa,)).fetchone()
        row_viveres = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_viveres,)).fetchone()
        row_kw = db.execute("SELECT categoria, subcategoria FROM est_keywords WHERE id=?", (kw_id,)).fetchone()
    assert row_casa['categoria'] == 'VIVIENDA'
    assert row_casa['subcategoria'] == 'Renta'
    assert row_viveres['categoria'] == 'ALIMENTACION'
    assert row_viveres['subcategoria'] == 'Súper'
    assert row_kw['categoria'] == 'VIVIENDA'
    assert row_kw['subcategoria'] == 'Renta'


def test_migracion_logueada_una_vez(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_unifica_categorias_legacy_2026_09'"
        ).fetchall()
    assert len(rows) == 1
