"""
test_inversiones_saldo_corte.py — el usuario fijó sus saldos reales al
2026-09-24 (CETES 51,124.65 · Finsus 102,933.66 · GBM 65,965.58; «no hay
otro»). Desde ahí el saldo de cada plataforma = corte + movimientos
posteriores; el historial anterior ya está dentro del corte.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import database


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False   # el fetch del layout manda el token en el navegador
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _inv(db, plat, sub, monto, fecha, desc=None):
    db.execute("INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, "
               "subcategoria, tipo) VALUES (?,?,?,?,'BBVA_DEB','',?,?,'INVERSION')",
               (fecha, fecha, desc or f'{plat} {sub} {monto} {fecha}', monto, plat, sub))


def _reset(db):
    db.execute("DELETE FROM migration_log WHERE version='inversiones_saldo_corte_2026_09_24'")
    db.execute("DELETE FROM inv_saldo_base")


def test_corte_mas_movimientos_posteriores(client, test_db):
    with database.get_db() as db:
        _reset(db)
        _inv(db, 'CETES', 'APORTACION', 351675, '2025-06-01')      # histórico: ya dentro del corte
        _inv(db, 'CETES', 'RETIRO', 410080, '2026-08-01')
        _inv(db, 'OTRO', 'APORTACION', 256000, '2025-03-01')
        _inv(db, 'OTRO', 'APORTACION', 5000, '2025-04-01', desc='SPEI ENVIADO FINSUS')
        _inv(db, 'GBM', 'APORTACION', 1000, '2026-09-25')          # después del corte
        _inv(db, 'CETES', 'RETIRO', 124.65, '2026-09-30')
        db.commit()
    database.init_db()
    html = client.get('/finanzas/inversiones/').get_data(as_text=True)
    assert '$66,965.58' in html        # GBM 65,965.58 + 1,000
    assert '$51,000.00' in html        # CETES 51,124.65 − 124.65
    assert '$102,933.66' in html       # Finsus
    assert '$220,899.24' in html       # total
    assert 'Otro</span>' not in html   # «no hay otro»: en 0 y sin movimientos nuevos, no se muestra
    with database.get_db() as db:
        assert db.execute("SELECT categoria FROM est_movimientos WHERE descripcion='SPEI ENVIADO FINSUS'").fetchone()['categoria'] == 'FINSUS'


def test_ajustar_saldo_crea_nuevo_corte_y_la_migracion_no_lo_pisa(client, test_db):
    from utils import today_str
    with database.get_db() as db:
        _reset(db)
        db.commit()
    database.init_db()
    r = client.post('/finanzas/inversiones/api/saldo', json={'plataforma': 'GBM', 'saldo': 70000})
    assert r.get_json()['ok']
    assert client.post('/finanzas/inversiones/api/saldo', json={'plataforma': 'NADA', 'saldo': 1}).status_code == 400
    database.init_db()
    with database.get_db() as db:
        row = db.execute("SELECT saldo, fecha FROM inv_saldo_base WHERE plataforma='GBM'").fetchone()
    assert (row['saldo'], row['fecha']) == (70000, today_str())


def test_import_reconoce_finsus_antes_que_stp():
    from modules.finanzas.estados.config import get_categoria_subcategoria
    assert get_categoria_subcategoria('SPEI ENVIADO FINSUS STP')[0] == 'INVERSION'


def test_patrimonio_usa_el_saldo_en_vivo_de_inversiones(client, test_db):
    from modules.finanzas.salud import _compute_patrimonio
    with database.get_db() as db:
        _reset(db)
        for nombre, inst, saldo in [('CETES', 'CETES', 63415.05), ('FINSUS', 'FINSUS', 101829.00),
                                    ('GMB', 'GBM', 65499.00), ('Fondo retiro', 'Afore XXI', 90000.0)]:
            db.execute("INSERT INTO salud_cuentas (nombre, tipo, institucion, saldo, moneda, activa, created_at) "
                       "VALUES (?, 'inversion', ?, ?, 'MXN', 1, '2026-09-01')", (nombre, inst, saldo))
        _inv(db, 'GBM', 'APORTACION', 1000, '2026-09-25')
        db.commit()
    database.init_db()
    pat = _compute_patrimonio()
    inv = {c['nombre']: c['saldo'] for c in pat['cuentas'] if c['tipo'] == 'inversion'}
    assert inv == {'CETES Directo': 51124.65, 'Finsus': 102933.66, 'GBM Homebroker': 66965.58,
                   'Fondo retiro': 90000.0}            # la Afore no es plataforma: sigue manual
    html = client.get('/finanzas/salud/').get_data(as_text=True)
    assert 'Ajustar GBM Homebroker en Inversiones' in html
