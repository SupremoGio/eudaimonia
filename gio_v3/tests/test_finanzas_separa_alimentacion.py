"""
test_finanzas_separa_alimentacion.py — el usuario pidió separar ALIMENTACION
porque inflaba «Necesidades» del 50-30-20 con comida fuera: "manda en super
todo lo que sea conveniencia y super como categoria y deja comida afuera
como otra categoria y subcategoria fast food, restaurante y delivery".

  SUPER        (Necesidades) → Súper, Conveniencia
  COMIDA_FUERA (Deseos)      → Restaurante, Fast Food, Delivery
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _tx(db, cat, sub, desc='X', monto=100.0, fecha='2026-08-10'):
    return db.execute(
        "INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, "
        "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,'GASTO')",
        (fecha, fecha, desc, monto, 'BBVA', '', cat, sub)).lastrowid


def _row(db, tabla, rid):
    r = db.execute(f"SELECT categoria, subcategoria FROM {tabla} WHERE id=?", (rid,)).fetchone()
    return (r['categoria'], r['subcategoria'])


def test_migracion_separa_movimientos_reglas_y_limite(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_separa_alimentacion_2026_09'")
        ids = {sub: _tx(db, 'ALIMENTACION', sub, desc=f'X {sub}') for sub in
               ['Súper', 'Conveniencia', 'Restaurante', 'Fast Food', 'Delivery', 'Café', '', 'Supermercado']}
        walmart = _tx(db, 'ALIMENTACION', '', desc='WALMART SUC 123')
        kw = db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) "
                        "VALUES ('OXXO', 'ALIMENTACION', 'Conveniencia')").lastrowid
        db.execute("DELETE FROM est_budgets")
        db.execute("INSERT INTO est_budgets (categoria, nombre, limite) VALUES ('ALIMENTACION', 'Alimentación', 4500)")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        got = {sub: _row(db, 'est_movimientos', i) for sub, i in ids.items()}
        assert got['Súper'] == ('SUPER', 'Súper')
        assert got['Conveniencia'] == ('SUPER', 'Conveniencia')
        assert got['Restaurante'] == ('COMIDA_FUERA', 'Restaurante')
        assert got['Fast Food'] == ('COMIDA_FUERA', 'Fast Food')
        assert got['Delivery'] == ('COMIDA_FUERA', 'Delivery')
        assert got['Café'] == ('CAFE/PAN', 'Café')
        assert got[''] == ('COMIDA_FUERA', 'Restaurante')        # sin pista → comida fuera
        assert got['Supermercado'] == ('SUPER', 'Súper')          # subcategoría vieja
        assert _row(db, 'est_movimientos', walmart) == ('SUPER', 'Súper')  # por la descripción
        assert _row(db, 'est_keywords', kw) == ('SUPER', 'Conveniencia')
        lim = {r['categoria']: r['limite'] for r in db.execute("SELECT categoria, limite FROM est_budgets")}
        assert lim == {'SUPER': 2500, 'COMIDA_FUERA': 2000}
        assert db.execute("SELECT COUNT(*) c FROM est_categoria_naturaleza WHERE categoria='ALIMENTACION'").fetchone()['c'] == 0
        assert db.execute("SELECT naturaleza FROM est_categoria_naturaleza WHERE categoria='COMIDA_FUERA' "
                          "AND subcategoria='Delivery'").fetchone()['naturaleza'] == 'VARIABLE'


def test_limite_personalizado_se_reparte_en_proporcion(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_separa_alimentacion_2026_09'")
        db.execute("DELETE FROM est_budgets")
        db.execute("INSERT INTO est_budgets (categoria, nombre, limite) VALUES ('ALIMENTACION', 'Alimentación', 6000)")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        lim = {r['categoria']: r['limite'] for r in db.execute("SELECT categoria, limite FROM est_budgets")}
    assert lim == {'SUPER': 3350, 'COMIDA_FUERA': 2650}   # 6000 × 2500/4500 ≈ 3333 → múltiplo de 50


def test_blindaje_corrige_reglas_que_reviven_alimentacion(test_db):
    from modules.finanzas.estados.routes import _corregir_alimentacion_split
    with database.get_db() as db:
        kw = db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) "
                        "VALUES ('RAPPI', 'ALIMENTACION', 'Delivery')").lastrowid
        tx = _tx(db, 'ALIMENTACION', 'Súper')
        _corregir_alimentacion_split(db)
        assert _row(db, 'est_keywords', kw) == ('COMIDA_FUERA', 'Delivery')
        assert _row(db, 'est_movimientos', tx) == ('SUPER', 'Súper')


def test_reglas_de_config_usan_las_categorias_nuevas():
    from modules.finanzas.estados.config import SUBCATEGORIAS, get_categoria_subcategoria
    assert 'ALIMENTACION' not in SUBCATEGORIAS
    assert SUBCATEGORIAS['SUPER'] == ['Súper', 'Conveniencia']
    assert SUBCATEGORIAS['COMIDA_FUERA'] == ['Restaurante', 'Fast Food', 'Delivery']
    assert get_categoria_subcategoria('WALMART VENTA EN LINEA') == ('SUPER', 'Súper')
    assert get_categoria_subcategoria('RAPPI MEXICO') == ('COMIDA_FUERA', 'Delivery')


def test_presupuesto_50_30_20_manda_comida_fuera_a_deseos(test_db):
    from modules.finanzas.budget import _calc_budget
    with database.get_db() as db:
        _tx(db, 'SUPER', 'Súper', monto=1000, fecha='2026-09-05')
        _tx(db, 'COMIDA_FUERA', 'Restaurante', monto=800, fecha='2026-09-06')
        d = _calc_budget('2026-09', db)
    assert d['buckets']['necesidades']['total_gastado'] == 1000
    assert d['buckets']['deseos']['total_gastado'] == 800
    assert [c['nombre'] for c in d['buckets']['deseos']['cats']] == ['Comida fuera']


def test_migracion_carga_los_limites_del_plan_una_sola_vez(test_db):
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_limites_plan_2026_09'")
        db.execute("DELETE FROM est_budgets")
        db.execute("INSERT INTO est_budgets (categoria, nombre, limite) VALUES ('VIVIENDA', 'Vivienda', 7429.84)")
        db.execute("INSERT INTO est_budgets (categoria, nombre, limite) VALUES ('VIAJES', 'Viajes', 800)")
        db.execute("INSERT INTO est_budgets (categoria, nombre, limite) VALUES ('INVERSION', 'Ahorro', 4000)")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        lim = {r['categoria']: r['limite'] for r in db.execute("SELECT categoria, limite FROM est_budgets")}
        assert lim['VIVIENDA'] == 6950 and lim['SUPER'] == 2000 and lim['COMIDA_FUERA'] == 2200
        assert lim['CUIDADO_PERSONAL'] == 500 and lim['PROYECTOS'] == 200 and lim['DIGITAL'] == 1246
        assert 'VIAJES' not in lim
        assert lim['INVERSION'] == 4000          # fuera del plan: no se toca
        assert len([c for c in lim if c != 'INVERSION']) == 14
        db.execute("UPDATE est_budgets SET limite=2300 WHERE categoria='SUPER'")   # edición del usuario
        db.commit()
    database.init_db()
    with database.get_db() as db:
        assert db.execute("SELECT limite FROM est_budgets WHERE categoria='SUPER'").fetchone()['limite'] == 2300
