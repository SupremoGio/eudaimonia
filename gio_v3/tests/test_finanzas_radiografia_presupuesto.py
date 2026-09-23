"""
test_finanzas_radiografia_presupuesto.py — ajustes al cálculo de la
Radiografía del mes (budget.py) pedidos por el usuario para que el 50-30-20
refleje la realidad. Un bloque por paso:

  1a. PRESTAMOS no es gasto: antes caía en Deseos por no tener bucket.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.budget import _calc_budget, _racha_bajo_presupuesto


def _mov(db, cat, monto, tipo='GASTO', sub='', fecha='2026-09-05', desc=None):
    return db.execute(
        "INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, "
        "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,?)",
        (fecha, fecha, desc or f'{cat} {sub} {monto} {fecha}', monto, 'BBVA', '', cat, sub, tipo)).lastrowid


# ── 1a. Préstamos fuera del gasto ────────────────────────────────────────────

def test_prestamos_no_cuentan_como_deseos_ni_gasto_total(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'OCIO', 500)
        _mov(db, 'PRESTAMOS', 3000)
        d = _calc_budget('2026-09', db)
    assert d['buckets']['deseos']['total_gastado'] == 500
    assert [c['categoria'] for c in d['buckets']['deseos']['cats']] == ['OCIO']
    assert d['total_gastado'] == 500


def test_prestamos_no_rompen_la_racha(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 1000, tipo='INGRESO', sub='Pago nominal')
        for i in range(4):
            _mov(db, 'OCIO', 100, fecha=f'2026-09-0{i + 2}')
        _mov(db, 'PRESTAMOS', 5000)   # sin exclusión: 5400 > 1000 → «over»
        _, meses = _racha_bajo_presupuesto(db, '2026-09', max_meses=1)
    assert meses[-1]['status'] == 'ok'


# ── 2. Inversiones netas dentro de Ahorro y deudas ───────────────────────────

def test_ahorro_suma_aportaciones_menos_retiros_por_subcategoria(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        # El signo no manda: la dirección sale de la subcategoría.
        _mov(db, 'GBM', -3000, tipo='INVERSION', sub='APORTACION')
        _mov(db, 'CETES', 1000, tipo='INVERSION', sub='APORTACION')
        _mov(db, 'GBM', 500, tipo='INVERSION', sub='RETIRO')
        _mov(db, 'GBM', 80, tipo='INVERSION', sub='RENDIMIENTO')      # no cuenta
        _mov(db, 'GBM', 9999, tipo='INVERSION', sub='APORTACION', fecha='2026-08-30')  # otro mes
        d = _calc_budget('2026-09', db)
    ahorro = d['buckets']['ahorro_deuda']
    inv = next(c for c in ahorro['cats'] if c.get('inversion'))
    assert inv['inversion'] == {'aportado': 4000, 'retirado': 500, 'neto': 3500, 'n': 3}
    assert ahorro['total_gastado'] == 3500
    assert d['total_gastado'] == 3500
    assert d['disponible'] == 16500


def test_gasto_con_categoria_inversion_no_se_cuenta_dos_veces(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'INVERSION', 700, sub='Ahorro')                        # tipo GASTO
        _mov(db, 'GBM', 1000, tipo='INVERSION', sub='APORTACION')
        d = _calc_budget('2026-09', db)
    ahorro = d['buckets']['ahorro_deuda']
    assert sorted(c['gastado'] for c in ahorro['cats']) == [700, 1000]
    assert ahorro['total_gastado'] == 1700


def test_neto_negativo_se_muestra_negativo(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'GBM', 5000, tipo='INVERSION', sub='RETIRO')
        _mov(db, 'GBM', 1000, tipo='INVERSION', sub='APORTACION')
        d = _calc_budget('2026-09', db)
    assert d['buckets']['ahorro_deuda']['total_gastado'] == -4000
    assert d['seg']['ahorro_deuda'] == 0          # la barra no pinta anchos negativos
