"""
test_finanzas_celular_att_recargas.py — MI ATT y RECARGAS Y PAQUETES van
siempre a DIGITAL/Celular: keyword para imports nuevos, migración única y
blindaje en «Aplicar reglas».
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import routes as er
from modules.finanzas.estados.config import get_categoria_subcategoria

CELULAR = ('DIGITAL', 'Celular', 'GASTO')


def _mov(desc, fecha, categoria, subcategoria, monto=-150.0, tipo='GASTO'):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco)
                            VALUES (?, ?, ?, ?, ?, ?, 'BBVA_DEB')""",
                         (fecha, desc, monto, tipo, categoria, subcategoria)).lastrowid
        db.commit()
        return rid


def _cls(rid):
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (rid,)).fetchone()
        return (r['categoria'], r['subcategoria'], r['tipo'])


def test_keywords_para_imports_nuevos():
    assert get_categoria_subcategoria('MI ATT A APP TA') == ('DIGITAL', 'Celular')
    assert get_categoria_subcategoria('RECARGAS Y PAQUETES BMOV') == ('DIGITAL', 'Celular')


def test_corrige_y_no_toca_otras(test_db):
    cel = [
        _mov('RECARGAS Y PAQUETES BMOV', '2026-04-15', 'DIGITAL', 'Saldo telefono'),
        _mov('RECARGAS Y PAQUETES BMOV', '2026-02-15', 'OTROS', ''),
        _mov('MI ATT A APP TA', '2026-08-28', 'FINANZAS', 'Pago servicios'),
        _mov('MI ATT A APP TA', '2026-07-04', 'DIGITAL', 'Celular'),
    ]
    otro = _mov('ATTA TAXIS', '2026-07-04', 'TRANSPORTE', 'Taxi/apps')
    with database.get_db() as db:
        assert er._corregir_celular(db) == 3
        db.commit()
    assert all(_cls(r) == CELULAR for r in cel)
    assert _cls(otro) == ('TRANSPORTE', 'Taxi/apps', 'GASTO')
    with database.get_db() as db:
        assert er._corregir_celular(db) == 0          # idempotente


def test_la_migracion_los_mueve(test_db):
    rid = _mov('RECARGAS Y PAQUETES BMOV', '2026-01-20', 'DIGITAL', 'Saldo telefono')
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_celular_att_recargas'")
        db.commit()
    database.init_db()
    assert _cls(rid) == CELULAR
