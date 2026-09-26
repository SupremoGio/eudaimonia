"""
test_finanzas_csv_corregido_2026_09_26.py — correcciones del CSV que el
usuario comentó: se aplican por id + fecha + monto (nunca a una fila que no
coincida), son idempotentes, y la aportación del roomie a la renta ya no
cuenta como ingreso (la renta cuenta solo su parte).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados import correcciones_csv_2026_09_26 as csv0926


def _ins(mid, fecha, desc, monto, cat, sub, tipo):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES (?, ?, ?, ?, 'BBVA_DEB', ?, ?, ?)""", (mid, fecha, desc, monto, cat, sub, tipo))
        db.commit()


def _row(mid):
    with database.get_db() as db:
        return dict(db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone())


def test_aplica_por_id_fecha_y_monto(test_db):
    _ins(2577, '2026-09-07', 'PAGO TARJETA DE TERCEROS MBAN', 12000, 'VIVIENDA', 'Renta', 'GASTO')
    _ins(3704, '2023-10-30', 'SPEI RECIBIDONAFIN', 22827.58, 'FINANZAS', 'Transferencia recibida', 'INGRESO')
    _ins(2384, '2026-08-03', 'SPEI ENVIADO GBM', 25000, 'FINANZAS', 'Pago servicios', 'PAGO')
    _ins(2613, '2024-12-06', 'SITH20000001490 FIDEICOMISO F 1596', 6138, 'FINANZAS', 'Transferencia', 'INGRESO')
    _ins(3031, '2025-02-27', 'SPEI RECIBIDOSANTANDER', 7158, 'FINANZAS', 'Transferencia', 'INGRESO')
    _ins(1872, '2099-01-01', 'OTRA FILA CON EL MISMO ID', 1133, 'COMIDA_FUERA', 'Restaurante', 'GASTO')  # fecha distinta
    with database.get_db() as db:
        ok, faltan = csv0926.aplicar(db)
        db.commit()
    assert ok == 5 and faltan == len(csv0926.CORRECCIONES) - 5
    assert _row(2577)['mi_parte'] == 6000
    assert (_row(3704)['categoria'], _row(3704)['subcategoria'], _row(3704)['tipo']) == ('CETES', 'RETIRO', 'INVERSION')
    assert (_row(2384)['categoria'], _row(2384)['tipo']) == ('GBM', 'INVERSION')
    assert _row(2613)['subcategoria'] == 'Reembolsable'
    assert _row(3031)['subcategoria'] == 'Aportación renta'
    assert _row(1872)['mi_parte'] is None                                  # no coincide: no se toca
    with database.get_db() as db:
        assert csv0926.aplicar(db)[0] == 0                                 # idempotente


def test_aportacion_renta_no_cuenta_como_ingreso(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    _ins(1, '2026-09-01', 'NOMINA', 20000, 'NOMINA', 'Pago nominal', 'INGRESO')
    _ins(2, '2026-09-02', 'SPEI RECIBIDOSANTANDER', 6000, 'VIVIENDA', 'Aportación renta', 'INGRESO')
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        stats = c.get('/finanzas/estados/api/summary/stats',
                      query_string={'date_from': '2026-09-01', 'date_to': '2026-09-30'}).get_json()
    assert stats['total_income'] == 20000
    from modules.finanzas.budget import _ingresos_mes
    with database.get_db() as db:
        assert _ingresos_mes(db, '2026-09', '2026-09-01', '2026-10-01')['total'] == 20000
