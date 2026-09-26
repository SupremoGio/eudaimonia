"""
test_finanzas_auditoria_expense_2026_09_26.py — respuestas del usuario a la
auditoría de Expense: «nada que ingrese va a crédito» (se borran los
ingresos de BBVA Crédito con gemelo en Débito, también al importar), los dos
cargos que eran Expense y los lotes creados con los folios de la empresa.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import correcciones_expense_2026_09_26 as ce
from modules.finanzas.estados import expense_lotes as L
from modules.finanzas.estados.routes import _descartar_ingresos_en_credito


def _ins(mid, fecha, desc, monto, banco, cat, sub, tipo, estatus=None):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo, estatus_reembolso)
                      VALUES (?,?,?,?,?,?,?,?,?)""", (mid, fecha, desc, monto, banco, cat, sub, tipo, estatus))
        db.commit()


def _existe(mid):
    with database.get_db() as db:
        return db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone()


def test_borra_duplicados_de_credito_y_arma_lotes(test_db):
    _ins(2379, '2026-07-22', 'SITH27049535 / 441169685063080 FIDEICOMISO', 7163.62, 'BBVA_TDC', 'FINANZAS', 'Reembolsable', 'PAGO')
    _ins(2371, '2026-07-22', 'FIDEICOMISO F 1596', 7163.62, 'BBVA_DEB', 'FINANZAS', 'Reembolsable', 'INGRESO')
    _ins(2284, '2026-06-19', 'WAL MART AVILA CAMACHO', 3316.0, 'INVEX', 'EXPENSE', '', 'GASTO', 'PAGADO')
    _ins(2440, '2026-08-14', 'SPEI RECIBIDONUBANK / 0155', 1000.0, 'BBVA_DEB', 'VIVIENDA', 'Aportación renta', 'INGRESO')  # otro banco: no se borra
    _ins(2323, '2026-07-02', 'SPEI RECIBIDOSTP / QUALITAS', 9998.10, 'BBVA_TDC', 'TRANSPORTE', 'Seguro auto', 'INGRESO')
    _ins(2098, '2026-05-17', 'PLAZA PANAMERICANA', 334.10, 'BBVA_TDC', 'COMIDA_FUERA', 'Restaurante', 'GASTO')
    _ins(2104, '2026-05-20', 'SITH2PAGOGDLAC FIDEICOMISO F 1596', 10143.5, 'BBVA_DEB', 'FINANZAS', 'Reembolsable', 'INGRESO')
    with database.get_db() as db:
        r = ce.aplicar(db)
        db.commit()
    assert r['borrados'] == 1 and r['a_debito'] == 1 and r['a_expense'] == 1
    assert _existe(2379) is None and _existe(2371) is not None and _existe(2440) is not None
    assert _existe(2323)['banco'] == 'BBVA_DEB'
    assert _existe(2098)['categoria'] == 'EXPENSE'
    with database.get_db() as db:
        lotes = {l['nombre']: l for l in L.listar(db)}
    junio = lotes['Folios 42644 + 42488 · Junio']
    assert [g['id'] for g in junio['gastos']] == [2284] and [d['id'] for d in junio['depositos']] == [2371]
    assert junio['estado'] == 'Reembolsado'
    ninos = lotes['Folio 40524 · Día del niño y de las madres']
    assert [g['id'] for g in ninos['gastos']] == [2098] and ninos['depositado'] == 10143.5
    assert 'Folio 41138 · Pastel aniversario PT1' not in lotes      # sus movimientos no existen aquí
    with database.get_db() as db:
        assert ce.aplicar(db) == {'borrados': 0, 'a_debito': 0, 'a_expense': 0, 'lotes': 0}


def test_al_importar_nada_que_ingrese_va_a_credito(test_db):
    _ins(10, '2026-08-07', 'PAGO CUENTA DE TERCERO BNET TR', 2000.0, 'BBVA_DEB', 'FINANZAS', 'Transferencia', 'INGRESO')
    _ins(11, '2026-08-07', 'PAGO CUENTA DE TERCERO / 0046293827', 2000.0, 'BBVA_TDC', 'FINANZAS', 'Pago servicios', 'PAGO')
    _ins(12, '2026-08-07', 'BMOVIL.PAGO TDC', 2000.0, 'BBVA_TDC', 'PAGO_TDC', '', 'MOVIMIENTO_INTERNO')   # pago a la tarjeta: se queda
    _ins(13, '2026-08-09', 'SPEI RECIBIDO SIN GEMELO', 700.0, 'BBVA_TDC', 'OTROS', '', 'INGRESO')           # sin gemelo: se queda
    with database.get_db() as db:
        assert _descartar_ingresos_en_credito(db, [11, 12, 13]) == 1
        db.commit()
    assert _existe(11) is None and _existe(12) is not None and _existe(13) is not None and _existe(10) is not None
    # Al revés: se importa primero crédito y luego el débito
    _ins(21, '2026-08-20', 'PAGO CUENTA DE TERCERO / 0025151642', 500.0, 'BBVA_TDC', 'FINANZAS', 'Pago servicios', 'PAGO')
    _ins(20, '2026-08-20', 'PAGO CUENTA DE TERCERO BNET TR', 500.0, 'BBVA_DEB', 'FINANZAS', 'Transferencia', 'INGRESO')
    with database.get_db() as db:
        assert _descartar_ingresos_en_credito(db, [20]) == 1
        db.commit()
    assert _existe(21) is None and _existe(20) is not None
