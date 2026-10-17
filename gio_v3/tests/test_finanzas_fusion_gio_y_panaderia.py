"""
test_finanzas_fusion_gio_y_panaderia.py — dos correcciones puntuales
pedidas por el usuario en la misma sesión, con filas reales:

1. FUSION GIO -> SALSA/Congreso. Reportado DOS VECES: "esto por que
   sigue ahí ya habiamos dicho que es Salsa subcategoria congreso".
   SPEI ENVIADO NU MEXICO ...FUSION GIO (un congreso de salsa) seguía
   cayendo en APORTACION_RENTA/VIVIENDA porque una regla de keyword más
   amplia (custom_kw en est_keywords, prioritaria sobre el keyword
   genérico "SALSA" de config.py -- ver get_categoria_subcategoria) la
   interceptaba antes de que el texto pudiera clasificarse bien.
   _corregir_fusion_gio corrige por texto directamente, después de
   aplicar cualquier regla de keyword, para que ninguna la pise.

2. MERPAGO PANADERIA -> CAFE/PAN/Pan. "esto mandalo a cafe y pan
   subcategoria pan" -- filas de antes de que existiera el keyword
   "PANADERIA" en config.py (o de antes de revivir CAFE/PAN como
   categoria propia) se quedaron en ALIMENTACION.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.routes import _corregir_fusion_gio
from modules.finanzas.estados.config import get_categoria_subcategoria


def _insert(db, **kw):
    defaults = dict(fecha='2026-05-25', fecha_cargo=None, descripcion='X', monto=2150.0,
                     banco='BBVA_DEB', periodo='', categoria='APORTACION_RENTA', subcategoria='',
                     tipo='PAGO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


# ── _corregir_fusion_gio (unidad) ───────────────────────────────────────────

def test_corregir_fusion_gio_reclasifica_sin_importar_tipo(test_db):
    """El caso real: tipo='PAGO' (ni GASTO ni INGRESO), por eso la
    migración de APORTACION_RENTA (que solo mira GASTO/INGRESO) nunca lo
    tocaba."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='SPEI ENVIADO NU MEXICO 638 0805260SALSA FUSION GIO',
                         categoria='APORTACION_RENTA', tipo='PAGO')
        db.commit()
        n = _corregir_fusion_gio(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'SALSA'
    assert row['subcategoria'] == 'Congreso'


def test_corregir_fusion_gio_matches_variante_sin_salsa_en_texto(test_db):
    """El segundo caso real: descripción sin la palabra "SALSA", solo
    "FUSION GIO" -- el keyword genérico "SALSA" no la hubiera atrapado
    de todos modos."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='SPEI ENVIADO NU MEXICO 638 1404260FUSION GIO',
                         categoria='APORTACION_RENTA', tipo='PAGO')
        db.commit()
        n = _corregir_fusion_gio(db)
        db.commit()
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 1
    assert row['categoria'] == 'SALSA'
    assert row['subcategoria'] == 'Congreso'


def test_corregir_fusion_gio_no_toca_otras_filas(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='SPEI RECIBIDO OTRA COSA', categoria='FINANZAS',
                         subcategoria='Transferencia', tipo='INGRESO')
        db.commit()
        n = _corregir_fusion_gio(db)
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert n == 0
    assert row['categoria'] == 'FINANZAS'


# ── apply_all_keywords aplica la corrección ─────────────────────────────────

def test_apply_all_keywords_corrige_fusion_gio(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        import database
        with database.get_db() as db:
            tx_id = _insert(db, descripcion='SPEI ENVIADO NU MEXICO 638 0805260SALSA FUSION GIO',
                             categoria='APORTACION_RENTA', tipo='PAGO')
            db.commit()
        resp = c.post("/finanzas/estados/api/keywords/apply-all")
        assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'SALSA'
    assert row['subcategoria'] == 'Congreso'


# ── config.py: PANADERIA ─────────────────────────────────────────────────────

def test_keyword_merpago_panaderia_es_cafe_pan():
    cat, sub = get_categoria_subcategoria('MERPAGO PANADERIA')
    assert (cat, sub) == ('CAFE/PAN', 'Pan')


# ── Migraciones retroactivas ─────────────────────────────────────────────────

def test_migration_fusion_gio_backfill(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_fusion_gio_salsa_2026_09'")
        id1 = _insert(db, descripcion='SPEI ENVIADO NU MEXICO 638 0805260SALSA FUSION GIO',
                       categoria='APORTACION_RENTA')
        id2 = _insert(db, descripcion='SPEI ENVIADO NU MEXICO 638 1404260FUSION GIO',
                       categoria='APORTACION_RENTA')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in (id1, id2):
            row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
            assert row['categoria'] == 'SALSA'
            assert row['subcategoria'] == 'Congreso'


def test_migration_fusion_gio_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_fusion_gio_salsa_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_migration_panaderia_backfill(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_merpago_panaderia_2026_09'")
        tx_id = _insert(db, descripcion='MERPAGO PANADERIA', categoria='ALIMENTACION',
                         subcategoria='Restaurante', tipo='GASTO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'CAFE/PAN'
    assert row['subcategoria'] == 'Pan'


def test_migration_panaderia_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_merpago_panaderia_2026_09'"
        ).fetchall()
    assert len(rows) == 1
