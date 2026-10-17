"""Re-subir un estado ya importado corrige cargo/abono de lo guardado cuando
el parser lo verificó contra los totales del PDF (pagos de Jorge, 2026-10-03)."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados.routes import _corregir_direcciones


def _ins(db, desc, monto, tipo='GASTO', cat='FINANZAS', sub='Transferencia'):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES ('2024-10-24', ?, ?, 'BBVA_DEB', ?, ?, ?)""", (desc, monto, cat, sub, tipo)).lastrowid


def _m(desc, monto, tipo, ok=True):
    return {'fecha': '2024-10-24', 'descripcion': desc, 'monto': monto, 'tipo': tipo, 'banco': 'BBVA_DEB',
            'categoria': 'FINANZAS', 'subcategoria': 'Transferencia recibida', 'dir_verificada': ok}


def test_corrige_solo_lo_verificado_y_respeta_prestamos(test_db):
    with database.get_db() as db:
        a = _ins(db, 'PAGO CUENTA DE TERCERO BNET GIO', 100.0)
        b = _ins(db, 'PAGO CUENTA DE TERCERO BNET OTRO', 200.0)
        c = _ins(db, 'PAGO CUENTA DE TERCERO BNET JORGE', 4900.0, cat='PRESTAMOS', sub='Prestado')
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES ('Jorge', 'OTORGADO', 4900, '2024-10-24', '', ?, datetime('now'))""", (c,))
        res = _corregir_direcciones(db, [
            _m('PAGO CUENTA DE TERCERO BNET GIO', 100.0, 'INGRESO'),
            _m('PAGO CUENTA DE TERCERO BNET OTRO', 200.0, 'INGRESO', ok=False),   # sin verificar: no se toca
            _m('PAGO CUENTA DE TERCERO BNET JORGE', 4900.0, 'INGRESO'),
        ], 'BBVA_DEB')
        tipo = lambda i: db.execute("SELECT tipo, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone()[:]
        assert tipo(a) == ('INGRESO', 'Transferencia recibida')
        assert tipo(b) == ('GASTO', 'Transferencia')
        assert tipo(c) == ('GASTO', 'Prestado')
        assert [d['id'] for d in res['corregidas']] == [a] and [d['id'] for d in res['revisar']] == [c]


def test_pago_tdc_guardado_en_positivo_se_voltea(test_db):
    """Auditoría 2022-2026: los «BMOVIL.PAGO TDC» viejos estaban en positivo y
    la nueva subida (PAGO, monto negativo) los duplicaba."""
    with database.get_db() as db:
        a = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2023-10-24', 'BMOVIL.PAGO TDC', 300.0, 'BBVA_TDC', 'PAGO_TDC', '', 'MOVIMIENTO_INTERNO')""").lastrowid
        b = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                          VALUES ('2023-10-24', 'BMOVIL.PAGO TDC (2)', 1000.0, 'BBVA_TDC', 'PAGO_TDC', '', 'MOVIMIENTO_INTERNO')""").lastrowid
        compra = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                               VALUES ('2023-10-24', 'OXXO', 300.0, 'BBVA_TDC', 'SUPER', '', 'GASTO')""").lastrowid
        pago = lambda monto: {'fecha': '2023-10-24', 'descripcion': 'BMOVIL.PAGO TDC', 'monto': monto, 'tipo': 'PAGO',
                              'banco': 'BBVA_TDC', 'categoria': 'PAGO', 'subcategoria': ''}
        res = _corregir_direcciones(db, [pago(-300.0), pago(-1000.0)], 'BBVA_TDC')
        monto = lambda i: db.execute("SELECT monto FROM est_movimientos WHERE id=?", (i,)).fetchone()[0]
        assert (monto(a), monto(b), monto(compra)) == (-300.0, -1000.0, 300.0)
        assert len(res['corregidas']) == 2
