"""
test_finanzas_amazon_suscripciones.py — cargos de Amazon en DIGITAL que son
suscripción -> DIGITAL/Suscripciones entretenimiento: «AMAZON» solo, los de
$100 o más, «AMAZONCOM INC…» de $69 y «AMAZON MEXICO» de $43.20 — nunca los
que dicen «A MESES» ni los que el usuario ya mandó a otra categoría.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import routes as er

SUSCRIPCION = ('DIGITAL', 'Suscripciones entretenimiento', 'GASTO')
ACCESORIOS = ('DIGITAL', 'Accesorios tech', 'GASTO')


def _mov(desc, monto, fecha='2026-05-03', categoria='DIGITAL', subcategoria='Accesorios tech', tipo='GASTO'):
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


def test_capturas_del_usuario(test_db):
    sus = [
        _mov('AMAZON', -69.0, '2026-05-03'), _mov('AMAZON', -45.45, '2026-07-19'),
        _mov('AMAZON ', -43.20, '2026-09-09'), _mov('AMAZON', -182.0, '2026-01-10'),
        _mov('AMAZON', -149.99, '2026-01-19'), _mov('AMAZON', -239.0, '2026-03-02'),
        _mov('AMAZONCOM INC AMZN', -69.0, '2026-07-03'),
        _mov('AMAZON MEXICO', -43.20, '2026-05-24'),
        _mov('AMAZONCOM INC AMZN CIUDAD DE MEX', -310.0, '2026-06-11'),
    ]
    quedan = [
        _mov('AMAZON A MESES A 06 MESES S/I', -114.89, '2026-01-24'),
        _mov('AMAZON MX A MESES', -199.0, '2026-09-22'),
        _mov('AMAZON A MESES', -146.0, '2026-09-22'),
        _mov('AMAZONCOM INC AMZN CIUDAD DE MEX', -50.0, '2026-08-07'),
        _mov('AMAZONVALIDACION', -20.0, '2026-05-05'),
    ]
    otra_cat = _mov('AMAZON MEXICO', -899.0, '2026-06-24', 'VIVIENDA', 'Artículos del hogar')
    devolucion = _mov('AMAZON', 69.0, '2026-05-10', 'DIGITAL', 'Accesorios tech', 'INGRESO')
    with database.get_db() as db:
        assert er._corregir_amazon_suscripciones(db) == len(sus)
        db.commit()
    assert all(_cls(r) == SUSCRIPCION for r in sus)
    assert all(_cls(r) == ACCESORIOS for r in quedan)
    assert _cls(otra_cat) == ('VIVIENDA', 'Artículos del hogar', 'GASTO')
    assert _cls(devolucion) == ('DIGITAL', 'Accesorios tech', 'INGRESO')
    with database.get_db() as db:
        assert er._corregir_amazon_suscripciones(db) == 0          # idempotente


def test_la_migracion_los_mueve(test_db):
    rid = _mov('AMAZON', -239.0)
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_amazon_suscripciones'")
        db.commit()
    database.init_db()
    assert _cls(rid) == SUSCRIPCION
