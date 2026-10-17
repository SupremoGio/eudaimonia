"""
test_finanzas_deudas_msi.py — en la tarjeta «Deudas» del hub de Finanzas el
saldo de una tarjeta de crédito sale de sus compras a MSI por pagar (la misma
cifra de «MSI activos»), no del saldo capturado a mano en Patrimonio.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.routes import _hub_debts


def _cuota(fecha, desc, monto, pn, pt, grupo, banco='BBVA_TDC'):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo,
                      parcialidad_num, parcialidad_total, compra_msi_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (fecha, desc, monto, banco, 'VIVIENDA', 'Artículos del hogar', 'GASTO', pn, pt, grupo))
        db.commit()


def _tarjeta(nombre, inst, saldo, tipo='tarjeta_credito'):
    return {'nombre': nombre, 'institucion': inst, 'saldo': saldo, 'tipo': tipo, 'moneda': 'MXN'}


def test_saldo_de_tarjeta_sale_de_msi(test_db):
    _cuota('2026-09-22', '03 DE 06 LIVERPOOL', 500.0, 3, 6, 'a')      # faltan 3 → 1,500
    _cuota('2026-09-22', '02 DE 03 AMAZON', 200.0, 2, 3, 'b')         # falta 1 → 200
    _cuota('2026-09-22', '06 DE 06 COPPEL', 100.0, 6, 6, 'c')         # terminada
    debts = _hub_debts([_tarjeta('BBVA ORO', 'BBVA', 7834.0), _tarjeta('Invex', 'INVEX', 900.0),
                        _tarjeta('Auto', 'Banorte', 50000.0, tipo='prestamo')])
    by = {d['nombre']: d for d in debts}
    assert by['BBVA ORO']['saldo'] == 1700.0 and 'MSI por pagar' in by['BBVA ORO']['sub']
    assert by['Invex']['saldo'] == 900.0            # banco sin MSI: saldo manual
    assert by['Auto']['saldo'] == 50000.0           # préstamos no cambian


def test_tarjeta_con_msi_liquidados_desaparece(test_db):
    _cuota('2026-09-22', '06 DE 06 COPPEL', 100.0, 6, 6, 'c')
    assert _hub_debts([_tarjeta('BBVA ORO', 'BBVA', 7834.0)]) == []
