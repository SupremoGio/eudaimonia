"""
Lista «Préstamos sin persona» que contestó el usuario (2026-10-01).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import prestamos as pr
from modules.finanzas.estados import msi


def _ins(db, fecha, desc, monto, tipo='GASTO', cat='PRESTAMOS', sub='Prestado'):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (?,?,?, 'BBVA_DEB', ?, ?, ?)""", (fecha, desc, monto, cat, sub, tipo)).lastrowid


def _cat(db, i):
    return tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())


def test_registra_cornelius_y_jorge(test_db):
    with database.get_db() as db:
        c = _ins(db, '2026-05-12', 'BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER', 2000.0)
        j = _ins(db, '2024-10-18', 'PAGO CUENTA DE TERCERO BNET CIRUJIA CAMBIO SEX', 10000.0)
        db.commit()
        assert pr.registrar_manuales(db) == (2, 0)
        assert pr.registrar_manuales(db) == (0, 0)
        per = {p['movimiento_id']: (p['persona'], p['estado']) for p in pr.listar(db)}
        assert per[c] == ('Cornelius', 'Pendiente') and per[j] == ('Jorge', 'Pendiente')
        assert pr.candidatos(db)['prestamos'] == []


def test_regresados_se_cancelan_con_su_deposito(test_db):
    with database.get_db() as db:
        a = _ins(db, '2024-09-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 13000.0)
        b = _ins(db, '2024-09-12', 'PAGO CUENTA DE TERCERO BNET DEUDA', 13000.0)
        da = _ins(db, '2024-09-11', 'DEVOLUCION SPEI', -13000.0, 'INGRESO', 'FINANZAS', 'Reembolso compartido')
        db.commit()
        assert pr.registrar_manuales(db) == (0, 1)
        assert _cat(db, a) == _cat(db, da) == ('FINANZAS', 'Entre cuentas propias')
        assert _cat(db, b) == ('PRESTAMOS', 'Prestado')              # sin depósito: se queda
        db.execute("DELETE FROM est_movimientos WHERE id=?", (da,))   # (para no confundir)
        db.commit()


def test_mensualidades_iphone_no_salen_sin_persona(test_db):
    with database.get_db() as db:
        m = _ins(db, '2023-05-22', 'MACSTORE MIDTOWN JALI', 1167.0, 'GASTO', 'TECH/DIGITAL', 'Deudas MSI')
        db.commit()
        msi.marcar_compras(db)
        assert _cat(db, m) == ('PRESTAMOS', 'Prestado')
        assert pr.candidatos(db)['prestamos'] == []


def test_viva_aerobus_de_la_familia_es_reembolsable(test_db):
    with database.get_db() as db:
        v = _ins(db, '2024-06-22', 'VIVA AEROBUS CIB', 1322.0)
        db.commit()
        msi.marcar_compras(db)
        assert _cat(db, v) == ('FINANZAS', 'Reembolsable')
        assert pr.candidatos(db)['prestamos'] == []


def test_regresado_con_deposito_un_dia_antes(test_db):
    """Le prestaron $13,000 el 10/09 y al otro día los devolvió."""
    with database.get_db() as db:
        dep = _ins(db, '2024-09-10', 'SPEI RECIBIDO', -13000.0, 'INGRESO', 'FINANZAS', 'Reembolso compartido')
        t = _ins(db, '2024-09-11', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 13000.0)
        db.commit()
        assert pr.registrar_manuales(db) == (0, 1)
        assert _cat(db, t) == _cat(db, dep) == ('FINANZAS', 'Entre cuentas propias')
        assert pr.candidatos(db)['prestamos'] == []
