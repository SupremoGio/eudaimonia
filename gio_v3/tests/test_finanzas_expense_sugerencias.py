"""
test_finanzas_expense_sugerencias.py — sugerencias automáticas de lotes de
Expense: cada depósito de la empresa se cubre con facturas de hasta ~3 meses
antes cuya suma lo iguala (±$1).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import expense_lotes as E


def _mov(db, fecha, desc, monto, cat, sub='', tipo='GASTO', est=None):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo, estatus_reembolso)
                         VALUES (?,?,?, 'BBVA_TDC', ?,?,?,?)""", (fecha, desc, monto, cat, sub, tipo, est)).lastrowid


def test_sugiere_facturas_que_suman_el_deposito(test_db):
    with database.get_db() as db:
        a = _mov(db, '2024-03-10', 'COMIDA CLIENTE', 1200.50, 'EXPENSE')
        b = _mov(db, '2024-04-02', 'UBER', 214.00, 'EXPENSE')
        c = _mov(db, '2024-04-20', 'HOTEL', 1529.50, 'EXPENSE')
        viejo = _mov(db, '2023-10-01', 'MUY VIEJA', 500.0, 'EXPENSE')          # fuera de la ventana
        tercero = _mov(db, '2024-04-05', 'PAGO COMPAÑERO', 214.0, 'EXPENSE', est='TERCERO')
        dep = _mov(db, '2024-05-14', 'SITH20000000864 FIDEICOMISO F 1596', 2944.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        _mov(db, '2024-05-15', 'SPEI DEVUELTOSANTANDER', 2944.0, 'FINANZAS', 'Reembolsable', 'INGRESO')  # no es de la empresa
        d2 = _mov(db, '2024-06-04', 'SITH20000000932 FIDEICOMISO F 1596', 99999.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        s = E.sugerencias(db)
        assert len(s) == 1
        assert s[0]['deposito']['id'] == dep and s[0]['diferencia'] == 0.0
        assert {f['id'] for f in s[0]['facturas']} == {a, b, c}
        assert viejo not in {f['id'] for f in s[0]['facturas']} and tercero not in {f['id'] for f in s[0]['facturas']}


def test_cada_factura_se_usa_una_vez(test_db):
    with database.get_db() as db:
        f1 = _mov(db, '2025-01-05', 'TAXI', 300.0, 'EXPENSE')
        f2 = _mov(db, '2025-01-20', 'COMIDA', 300.0, 'EXPENSE')
        _mov(db, '2025-02-10', 'SITH20000001 FIDEICOMISO F 1596', 300.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        _mov(db, '2025-03-10', 'SITH20000002 FIDEICOMISO F 1596', 300.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        s = E.sugerencias(db)
        assert [x['facturas'][0]['id'] for x in s] == [f1, f2]


def test_ventana_amplia_y_dos_depositos(test_db):
    with database.get_db() as db:
        vieja = _mov(db, '2024-01-10', 'CONGRESO', 3000.0, 'EXPENSE')                   # 5 meses antes
        d1 = _mov(db, '2024-06-12', 'SITH2000001 FIDEICOMISO F 1596', 3000.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        g1 = _mov(db, '2024-07-01', 'VUELO', 5000.0, 'EXPENSE')
        g2 = _mov(db, '2024-07-03', 'HOTEL', 2500.0, 'EXPENSE')
        a = _mov(db, '2024-08-10', 'SITH2000002 FIDEICOMISO F 1596', 4000.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        b = _mov(db, '2024-08-30', 'SITH2000003 FIDEICOMISO F 1596', 3500.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        s = {x['deposito']['id']: x for x in E.sugerencias(db)}
        assert s[d1]['confianza'] == 'media' and [f['id'] for f in s[d1]['facturas']] == [vieja]
        assert [d['id'] for d in s[a]['depositos']] == [a, b]
        assert {f['id'] for f in s[a]['facturas']} == {g1, g2}


def test_sueltos(test_db):
    with database.get_db() as db:
        a = _mov(db, '2024-04-02', 'UBER', 214.0, 'EXPENSE')
        sola = _mov(db, '2024-04-03', 'CENA SIN REEMBOLSO', 999.0, 'EXPENSE')
        _mov(db, '2024-05-14', 'SITH2 FIDEICOMISO F 1596', 214.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        dep_solo = _mov(db, '2024-06-14', 'SITH3 FIDEICOMISO F 1596', 12345.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        s = E.sueltos(db)
        assert [d['id'] for d in s['depositos']] == [dep_solo] and [f['id'] for f in s['facturas']] == [sola]
        assert s['total_depositos'] == 12345.0 and s['total_facturas'] == 999.0


def test_tanda_de_facturas_seguidas_y_aproximada(test_db):
    """Un depósito grande paga una tanda de facturas seguidas (aunque haya
    otras combinaciones posibles); otro no cuadra exacto: sale aproximado."""
    with database.get_db() as db:
        tanda = [_mov(db, f'2024-0{m}-{d:02d}', f'FACT {m}{d}', monto, 'EXPENSE')
                 for m, d, monto in ((2, 1, 1500.0), (2, 10, 820.5), (2, 20, 2310.0), (3, 2, 999.0), (3, 15, 4100.0))]
        otra = _mov(db, '2024-04-01', 'FACT SUELTA', 1000.0, 'EXPENSE')
        dep = _mov(db, '2024-06-20', 'SITH2 FIDEICOMISO F 1596', 9729.5, 'FINANZAS', 'Reembolsable', 'INGRESO')
        casi = _mov(db, '2024-06-25', 'SITH3 FIDEICOMISO F 1596', 1100.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        s = {x['deposito']['id']: x for x in E.sugerencias(db)}
        assert [f['id'] for f in s[dep]['facturas']] == tanda and s[dep]['confianza'] == 'alta'
        assert s[casi]['confianza'] == 'aproximada' and [f['id'] for f in s[casi]['facturas']] == [otra]
        assert s[casi]['diferencia'] == 100.0
