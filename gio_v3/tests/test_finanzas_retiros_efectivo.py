"""Retiros de efectivo identificados por el usuario (retiros_efectivo.py)."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import retiros_efectivo
from modules.finanzas.budget import _calc_budget


def _mov(db, fecha, desc, monto):
    db.execute("INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, "
               "subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,?)",
               (fecha, fecha, desc, monto, 'BBVA_DEB', '', 'FINANZAS', 'Retiro efectivo', 'GASTO'))


def test_anillos_ale_pasan_a_familia_regalos_con_nota(test_db):
    with database.get_db() as db:
        _mov(db, '2026-07-11', 'RETIRO SIN TARJETA ******7852', 3400)
        _mov(db, '2026-07-18', 'RETIRO SIN TARJETA QR ******7852', 5500)
        _mov(db, '2026-07-30', 'RETIRO SIN TARJETA', 500)
        assert retiros_efectivo.aplicar(db) == (2, 0)
        assert retiros_efectivo.aplicar(db) == (2, 0)          # idempotente: la nota no se repite
        rows = db.execute("SELECT descripcion, categoria, subcategoria FROM est_movimientos ORDER BY fecha").fetchall()
        d = _calc_budget('2026-07', db)
    assert [tuple(r) for r in rows] == [
        ('RETIRO SIN TARJETA ******7852 · Anillos Ale', 'FAMILIA_REGALOS', 'Regalos'),
        ('RETIRO SIN TARJETA QR ******7852 · Anillos Ale', 'FAMILIA_REGALOS', 'Regalos'),
        ('RETIRO SIN TARJETA', 'FINANZAS', 'Retiro efectivo'),
    ]
    cats = {c['categoria']: c['gastado'] for c in d['buckets']['deseos']['cats']}
    assert cats == {'FAMILIA_REGALOS': 8900, 'FINANZAS': 500}


def test_sin_los_movimientos_cargados_no_hace_nada(test_db):
    with database.get_db() as db:
        assert retiros_efectivo.aplicar(db) == (0, 2)
