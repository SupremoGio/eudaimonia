"""
test_finanzas_steamgames_regalo_migracion.py — dos correcciones pedidas el
mismo día:

1. STEAMGAMES.COM caía en DIGITAL/Suscripciones IA/productividad --
   "manda estos a Entretenimiento y crea una subcategoria de videojuegos"
   (OCIO, mostrado como "Ocio" en el selector, ya tenía "Videojuegos" en
   config.py::SUBCATEGORIAS, no hacía falta crearla). _corregir_steamgames
   (routes.py) corrige por texto, wireada en apply_all_keywords()/
   upload_file() igual que _corregir_far_guad; también se agregó la
   keyword "STEAMGAMES" a config.py::CATEGORIAS para que futuras compras
   se clasifiquen bien desde el import.

2. REGALO (categoria legacy) -> FAMILIA_REGALOS/Anillo Cornelius, mismo
   patrón que CASA/HOGAR etc. (cubierto por separado en
   test_finanzas_categorias_legacy_blindaje.py, que ya extendí con casos
   REGALO). Este archivo cubre la migración histórica que backfillea
   ambas correcciones (finanzas_regalo_steamgames_2026_09).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados.routes import _corregir_steamgames
from modules.finanzas.estados.config import get_categoria_subcategoria


def _insert_tx(db, **kw):
    defaults = dict(fecha='2026-08-10', fecha_cargo=None, descripcion='X',
                     monto=-100.0, banco='BBVA_TDC', periodo='', categoria='DIGITAL',
                     subcategoria='Suscripciones IA/productividad', tipo='GASTO')
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


# ── _corregir_steamgames (unidad) ───────────────────────────────────────────

def test_steamgames_va_a_ocio_videojuegos(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, descripcion='STEAMGAMES.COM 42')
        db.commit()
        n = _corregir_steamgames(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'OCIO'
    assert row['subcategoria'] == 'Videojuegos'


def test_steamgames_con_folio_tambien_se_corrige(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, descripcion='STEAMGAMES.COM 4259522985')
        db.commit()
        _corregir_steamgames(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'OCIO'
    assert row['subcategoria'] == 'Videojuegos'


def test_no_toca_otras_descripciones(test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, descripcion='CLAUDE.AI SUBSCRIPTION SAN FRANCISCO CA')
        db.commit()
        n = _corregir_steamgames(db)
        row = db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'DIGITAL'


def test_es_idempotente(test_db):
    with database.get_db() as db:
        _insert_tx(db, descripcion='STEAMGAMES.COM 42')
        db.commit()
        n1 = _corregir_steamgames(db)
        db.commit()
        n2 = _corregir_steamgames(db)
    assert n1 == 1
    assert n2 == 0


# ── Blindaje: apply_all_keywords y upload_file corren la corrección ────────

def test_apply_keywords_corrige_steamgames(client, test_db):
    with database.get_db() as db:
        tx_id = _insert_tx(db, descripcion='STEAMGAMES.COM 99')
        db.commit()

    resp = client.post('/finanzas/estados/api/keywords/apply-all')
    assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'OCIO'
    assert row['subcategoria'] == 'Videojuegos'


def test_get_categoria_subcategoria_reconoce_steamgames(test_db):
    """Unit test directo de la keyword nueva en config.py -- lo que un
    parser real (bbva_csv.py, bbva_debit.py, etc.) llama para clasificar
    cada fila en el momento del import, antes de que llegue a
    upload_file()."""
    assert get_categoria_subcategoria('STEAMGAMES.COM 42') == ('OCIO', 'Videojuegos')
    assert get_categoria_subcategoria('STEAMGAMES.COM 4259522985') == ('OCIO', 'Videojuegos')


def test_upload_corrige_steamgames_via_blindaje(client, monkeypatch, test_db):
    """upload_file() no vuelve a correr get_categoria_subcategoria sobre
    lo que ya devolvió el parser (eso ya pasó dentro de parse_file, antes
    de llegar aquí) -- lo que sí hace es correr _corregir_steamgames como
    red de seguridad. Este test mockea parse_file devolviendo OTROS a
    propósito, para confirmar que esa red de seguridad funciona sola."""
    import io
    import modules.finanzas.estados.parsers as parsers_mod
    movimientos = [{
        'fecha': '2026-08-12', 'fecha_cargo': '2026-08-12',
        'descripcion': 'STEAMGAMES.COM 55', 'monto': -389.70,
        'categoria': 'OTROS', 'subcategoria': '', 'tipo': 'GASTO', 'periodo': '',
    }]
    monkeypatch.setattr(parsers_mod, "parse_file", lambda path: movimientos)
    monkeypatch.setattr(parsers_mod, "detect_bank", lambda path: "BBVA_TDC")
    data = {"file": (io.BytesIO(b"contenido irrelevante"), "estado.pdf")}
    resp = client.post("/finanzas/estados/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion LIKE '%STEAMGAMES.COM 55%'"
        ).fetchone()
    assert row['categoria'] == 'OCIO'
    assert row['subcategoria'] == 'Videojuegos'


# ── Migración histórica ─────────────────────────────────────────────────────

def _reset_migration(db):
    db.execute("DELETE FROM migration_log WHERE version='finanzas_regalo_steamgames_2026_09'")


def test_migracion_corrige_regalo_y_steamgames(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_regalo = _insert_tx(db, descripcion='07 DE 12 CRISTAL VILLAHERMOSA', monto=-1038.0,
                                categoria='REGALO', subcategoria='Anillo a cornelius')
        tx_steam = _insert_tx(db, descripcion='STEAMGAMES.COM 42', monto=-389.70)
        kw_id = db.execute(
            "INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES (?,?,?)",
            ('CRISTAL VILLAHERMOSA', 'REGALO', 'Anillo a cornelius'),
        ).lastrowid
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row_regalo = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_regalo,)).fetchone()
        row_steam = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_steam,)).fetchone()
        row_kw = db.execute("SELECT categoria, subcategoria FROM est_keywords WHERE id=?", (kw_id,)).fetchone()
    assert row_regalo['categoria'] == 'FAMILIA_REGALOS'
    assert row_regalo['subcategoria'] == 'Anillo Cornelius'
    assert row_steam['categoria'] == 'OCIO'
    assert row_steam['subcategoria'] == 'Videojuegos'
    assert row_kw['categoria'] == 'FAMILIA_REGALOS'
    assert row_kw['subcategoria'] == 'Anillo Cornelius'


def test_migracion_logueada_una_vez(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_regalo_steamgames_2026_09'"
        ).fetchall()
    assert len(rows) == 1
