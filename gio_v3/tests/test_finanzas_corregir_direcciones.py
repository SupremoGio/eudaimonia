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
