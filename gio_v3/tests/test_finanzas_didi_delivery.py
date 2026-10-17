"""
test_finanzas_didi_delivery.py — DIDI sin marca de viaje (RIDE, VIAJE, TAXI,
MOVILIDAD) va a COMIDA_FUERA/Delivery; los viajes de DiDi se quedan como
estaban (TRANSPORTE/Taxi/apps).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import routes as er

DELIVERY = ('COMIDA_FUERA', 'Delivery', 'GASTO')
TAXI = ('TRANSPORTE', 'Taxi/apps', 'GASTO')


def _mov(desc, monto=-150.0, categoria='TRANSPORTE', subcategoria='Taxi/apps', tipo='GASTO'):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco)
                            VALUES ('2026-08-10', ?, ?, ?, ?, ?, 'BBVA_TDC')""",
                         (desc, monto, tipo, categoria, subcategoria)).lastrowid
        db.commit()
        return rid


def _cls(rid):
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (rid,)).fetchone()
        return (r['categoria'], r['subcategoria'], r['tipo'])


def test_didi_sin_viaje_es_delivery_y_los_viajes_no_se_tocan(test_db):
    comida = [_mov('DIDI FOOD'), _mov('DL*DIDIFOOD MX', -210.0), _mov('DIDI', -99.0, 'OTROS', '')]
    viajes = [_mov('DIDI RIDES'), _mov('DL*DIDI*RIDE', -88.0), _mov('DIDI VIAJE CDMX', -120.0),
              _mov('DIDI TAXI', -75.0), _mov('DIDI MOVILIDAD', -64.0)]
    reembolso = _mov('DIDI FOOD', 150.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
    with database.get_db() as db:
        assert er._corregir_didi_delivery(db) == 3
        db.commit()
    assert all(_cls(r) == DELIVERY for r in comida)
    assert all(_cls(r) == TAXI for r in viajes)
    assert _cls(reembolso) == ('FINANZAS', 'Reembolsable', 'INGRESO')
    with database.get_db() as db:
        assert er._corregir_didi_delivery(db) == 0          # idempotente


def test_la_migracion_los_mueve(test_db):
    rid = _mov('DIDI FOOD')
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_didi_delivery'")
        db.commit()
    database.init_db()
    assert _cls(rid) == DELIVERY
