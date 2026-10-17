"""
test_finanzas_spei_invex_pago_tdc.py — todo «SPEI ENVIADO … INVEX» es el pago
de la TDC Invex: pasa a PAGO_TDC / MOVIMIENTO_INTERNO sin importar cómo lo
haya dejado una regla de keyword, y «Aplicar reglas» no lo regresa.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados import routes as er

PAGO_TDC = ('PAGO_TDC', '', 'MOVIMIENTO_INTERNO')


def _mov(desc, categoria, subcategoria, tipo, monto=-5000):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco)
                            VALUES ('2026-08-10', ?, ?, ?, ?, ?, 'BBVA_DEB')""",
                         (desc, monto, tipo, categoria, subcategoria)).lastrowid
        db.commit()
        return rid


def _cls(rid):
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (rid,)).fetchone()
        return (r['categoria'], r['subcategoria'], r['tipo'])


def test_todas_las_variantes_van_a_pago_tdc(test_db):
    invex = [
        _mov('SPEI ENVIADO INVEX', 'INVERSION', 'APORTACION', 'INVERSION'),
        _mov('SPEI ENVIADO INVEX /0012345 PAGO', 'FINANZAS', 'Transferencia enviada', 'GASTO'),
        _mov('spei enviado invex', 'OTROS', '', 'GASTO'),
        _mov('SPEI ENVIADO INVEX', 'PAGO_TDC', 'Invex TDC', 'PAGO', monto=-3200),
    ]
    ya_bien = _mov('SPEI ENVIADO INVEX', *PAGO_TDC, monto=-1500)
    otros = [
        _mov('SPEI ENVIADO GIOVANY', 'FINANZAS', 'Transferencia enviada', 'GASTO'),
        _mov('INVEX RENDIMIENTOS', 'INVERSION', 'RETIRO', 'INVERSION', monto=200),
        _mov('SPEI RECIBIDO INVEX', 'FINANZAS', 'Transferencia recibida', 'INGRESO', monto=900),
    ]
    antes = [_cls(r) for r in otros]
    with database.get_db() as db:
        assert er._corregir_spei_invex(db) == 4
        db.commit()
    assert all(_cls(r) == PAGO_TDC for r in invex + [ya_bien])
    assert [_cls(r) for r in otros] == antes
    with database.get_db() as db:
        assert er._corregir_spei_invex(db) == 0          # idempotente


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def test_aplicar_reglas_no_los_regresa(client):
    rid = _mov('SPEI ENVIADO INVEX', *PAGO_TDC)
    with database.get_db() as db:
        db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES ('INVEX', 'INVERSION', '')")
        db.commit()
    assert client.post('/finanzas/estados/api/keywords/apply-all').status_code == 200
    assert _cls(rid) == PAGO_TDC


def test_la_migracion_los_mueve(test_db):
    rid = _mov('SPEI ENVIADO INVEX', 'INVERSION', 'APORTACION', 'INVERSION')
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_spei_invex_pago_tdc'")
        db.commit()
    database.init_db()
    assert _cls(rid) == PAGO_TDC
