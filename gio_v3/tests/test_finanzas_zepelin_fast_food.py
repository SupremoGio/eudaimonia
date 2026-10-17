"""
test_finanzas_zepelin_fast_food.py — el usuario mandó varias filas reales
confirmando que ZEPELIN es una cadena de hot dogs/fast food, mal mapeada
como TRANSPORTE/Mantenimiento auto (keyword "CLIP MX MEC ZEPELIN" -- el
prefijo "MEC" del terminal de pago se leyó como "mecánico"). Pidió:
"estos clasificalos como fast food".

Dos piezas:
  1. config.py: keyword "ZEPELIN" (reemplaza "CLIP MX MEC ZEPELIN") ->
     ALIMENTACION/Fast Food. El keyword más amplio también cubre las
     variantes "PAYCLIP MEC ZEPELIN EN..." (BBVA_TDC/HSBC) que la
     entrada vieja, más estrecha, no atrapaba.
  2. finanzas_zepelin_fast_food_2026_09 (database.py) -- backfill de lo
     que ya estaba importado con la clasificación vieja.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.config import get_categoria_subcategoria


def _insert(db, **kw):
    defaults = dict(fecha='2026-03-08', fecha_cargo=None, descripcion='PAYCLIP MEC ZEPELIN EN',
                     monto=-105.0, banco='BBVA_TDC', periodo='', categoria='TRANSPORTE',
                     subcategoria='Mantenimiento auto', tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


# ── config.py keyword (unidad) ───────────────────────────────────────────────

def test_keyword_clip_mx_mec_zepelin_es_fast_food():
    cat, sub = get_categoria_subcategoria('CLIP MX MEC ZEPELIN EN GUADALAJARA')
    assert (cat, sub) == ('COMIDA_FUERA', 'Fast Food')


def test_keyword_payclip_mec_zepelin_es_fast_food():
    """Variante que la entrada vieja ('CLIP MX MEC ZEPELIN') no atrapaba."""
    cat, sub = get_categoria_subcategoria('PAYCLIP MEC ZEPELIN EN')
    assert (cat, sub) == ('COMIDA_FUERA', 'Fast Food')


def test_keyword_zepelin_variante_gua_es_fast_food():
    cat, sub = get_categoria_subcategoria('CLIP MX MEC ZEPELIN EN GUA')
    assert (cat, sub) == ('COMIDA_FUERA', 'Fast Food')


# ── Migración retroactiva ────────────────────────────────────────────────────

def test_migration_reclasifica_zepelin_existente(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_zepelin_fast_food_2026_09'")
        id1 = _insert(db, descripcion='CLIP MX MEC ZEPELIN EN GUADALAJARA', banco='INVEX')
        id2 = _insert(db, descripcion='PAYCLIP MEC ZEPELIN EN', banco='BBVA_TDC')
        id3 = _insert(db, descripcion='CLIP MX MEC ZEPELIN EN GUA', banco='HSBC')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in (id1, id2, id3):
            row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
            assert row['categoria'] == 'ALIMENTACION'
            assert row['subcategoria'] == 'Fast Food'


def test_migration_does_not_touch_unrelated_mantenimiento(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_zepelin_fast_food_2026_09'")
        tx_id = _insert(db, descripcion='AUTOZONE REFACCIONES', categoria='TRANSPORTE',
                         subcategoria='Mantenimiento auto')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row['categoria'] == 'TRANSPORTE'
    assert row['subcategoria'] == 'Mantenimiento auto'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_zepelin_fast_food_2026_09'"
        ).fetchall()
    assert len(rows) == 1
