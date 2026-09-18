"""
test_finanzas_fast_food_qin_tortas_gorditas.py — cubre la migración
finanzas_fast_food_qin_tortas_gorditas_2026_09 en database.py.

A petición explícita del usuario: Qin (comida china), tortas planchadas y
gorditas estaban en ALIMENTACION/Restaurante y pasan a ALIMENTACION/Fast
Food -- categoria NO cambia, solo subcategoria. config.py también se
actualizó (REST QIN, TOR PLANCHADAS, GORDITAS) para que las próximas
importaciones clasifiquen ahí directamente.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _insert(db, **kw):
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
                     banco='BBVA_TDC', periodo='', categoria='ALIMENTACION',
                     subcategoria='Restaurante', tipo='GASTO')
    defaults.update(kw)
    db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )


def test_qin_tortas_gorditas_reclassified_to_fast_food(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_fast_food_qin_tortas_gorditas_2026_09'")
        _insert(db, descripcion='REST QIN MIDTOWN')
        _insert(db, descripcion='TOR PLANCHADAS CENTRO')
        _insert(db, descripcion='GORDITAS DONA TOTA')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        rows = db.execute(
            "SELECT descripcion, categoria, subcategoria FROM est_movimientos ORDER BY descripcion"
        ).fetchall()
    for r in rows:
        assert r['categoria'] == 'ALIMENTACION'  # solo cambia subcategoria
        assert r['subcategoria'] == 'Fast Food'


def test_other_restaurante_rows_untouched(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_fast_food_qin_tortas_gorditas_2026_09'")
        _insert(db, descripcion='TAQUERIA EL BUEN SABOR')
        _insert(db, descripcion='CAFE LA CABANA GALERIA', categoria='ALIMENTACION', subcategoria='Café')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        rows = db.execute(
            "SELECT descripcion, subcategoria FROM est_movimientos ORDER BY descripcion"
        ).fetchall()
    by_desc = {r['descripcion']: r['subcategoria'] for r in rows}
    assert by_desc['TAQUERIA EL BUEN SABOR'] == 'Restaurante'
    assert by_desc['CAFE LA CABANA GALERIA'] == 'Café'


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_fast_food_qin_tortas_gorditas_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_get_categoria_subcategoria_now_returns_fast_food():
    from modules.finanzas.estados.config import get_categoria_subcategoria
    assert get_categoria_subcategoria('REST QIN MIDTOWN') == ('ALIMENTACION', 'Fast Food')
    assert get_categoria_subcategoria('TOR PLANCHADAS CENTRO') == ('ALIMENTACION', 'Fast Food')
    assert get_categoria_subcategoria('GORDITAS DONA TOTA') == ('ALIMENTACION', 'Fast Food')
    # No debe atrapar comercios no relacionados por substring accidental
    assert get_categoria_subcategoria('TAQUERIA EL BUEN SABOR') == ('ALIMENTACION', 'Restaurante')
