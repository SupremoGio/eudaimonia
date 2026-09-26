"""
test_finanzas_walmart_lavadora.py — las mensualidades de ~$509 de «WALMART
VENTA EN LIN…» (lavadora a 20 MSI) van a VIVIENDA/Artículos del hogar; las
demás compras de Walmart siguen en SUPER.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import routes as er

HOGAR = ('VIVIENDA', 'Artículos del hogar', 'GASTO')


def _mov(desc, monto, fecha='2026-08-10', categoria='SUPER', subcategoria='Súper', tipo='GASTO'):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco)
                            VALUES (?, ?, ?, ?, ?, ?, 'BBVA_TDC')""",
                         (fecha, desc, monto, tipo, categoria, subcategoria)).lastrowid
        db.commit()
        return rid


def _cls(rid):
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (rid,)).fetchone()
        return (r['categoria'], r['subcategoria'], r['tipo'])


def test_solo_las_mensualidades_de_509(test_db):
    lavadora = [
        _mov('WALMART VENTA EN LIN3', -509.0, '2026-06-10'),
        _mov('WALMART VENTA EN LIN3 03/20', -509.5, '2026-07-10', 'FINANZAS', 'Deudas MSI'),
        _mov('WALMART VENTA EN LINEA', 509.0, '2026-08-10'),
        _mov('19 DE 20 WALMART VENTA EN L', -509.0, '2026-05-22'),      # descripción cortada
        _mov('20 DE 20 WALMART VENTA EN L', -498.0, '2026-06-22'),      # última, otro monto
    ]
    super_linea = _mov('WALMART VENTA EN LIN3', -1250.0)
    super_tienda = _mov('WALMART SUPERCENTER', -509.0)
    devolucion = _mov('WALMART VENTA EN LIN3', 509.0, '2026-09-10', 'FINANZAS', 'Reembolsable', 'INGRESO')
    with database.get_db() as db:
        assert er._corregir_walmart_lavadora(db) == 5
        db.commit()
    assert all(_cls(r) == HOGAR for r in lavadora)
    assert _cls(super_linea) == _cls(super_tienda) == ('SUPER', 'Súper', 'GASTO')
    assert _cls(devolucion) == ('FINANZAS', 'Reembolsable', 'INGRESO')
    with database.get_db() as db:
        assert er._corregir_walmart_lavadora(db) == 0          # idempotente


def test_la_migracion_las_mueve(test_db):
    rid = _mov('WALMART VENTA EN LIN3', -509.0)
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_walmart_lavadora'")
        db.commit()
    database.init_db()
    assert _cls(rid) == HOGAR
