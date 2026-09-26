"""
test_finanzas_libretones.py — Libretones BBVA Débito mandados para llenar
huecos (data/bbva_deb_libreton): cada archivo cuadra con los totales del
PDF, no duplica lo que ya está (por fecha de operación o liquidación) y se
clasifica como un import normal.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados import libretones as libs


@pytest.mark.parametrize('clave', libs.archivos())
def test_cuadra_con_los_totales_del_pdf(clave):
    d = libs.cargar(clave)
    cargos = sum(m['monto'] for m in d['movimientos'] if m['tipo'] != 'INGRESO')
    abonos = sum(m['monto'] for m in d['movimientos'] if m['tipo'] == 'INGRESO')
    assert round(cargos, 2) == d['totales']['cargos'] and round(abonos, 2) == d['totales']['abonos']


def test_aplica_sin_duplicar_y_clasifica(test_db):
    d = libs.cargar('202408')
    with database.get_db() as db:
        # Ya existe (de una descarga de la app) una de las dos transferencias de $500 del 07/07
        # y el SPEI de renta con la fecha de liquidación.
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES ('2024-07-07', 'PAGO CUENTA DE TERCERO / 9246820029', 500, 'BBVA_DEB', 'FINANZAS', 'Transferencia', 'GASTO')""")
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES ('2024-07-08', 'SPEI RECIBIDOHSBC / 0100463588', 4850, 'BBVA_DEB', 'VIVIENDA', 'Aportación renta', 'INGRESO')""")
        db.commit()
        ins, ya = libs.aplicar(db, '202408')
        db.commit()
        assert (ins, ya) == (len(d['movimientos']) - 2, 2)
        assert libs.aplicar(db, '202408') == (0, len(d['movimientos']))
        n500 = db.execute("SELECT COUNT(*) FROM est_movimientos WHERE fecha='2024-07-07' AND monto=500").fetchone()[0]
        assert n500 == 2
        nafin = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE 'NAFIN%DOMICILIACION'").fetchall()
        assert nafin and all((r['categoria'], r['subcategoria'], r['tipo']) == ('CETES', 'APORTACION', 'INVERSION') for r in nafin)


def test_decisiones_previas(test_db):
    with database.get_db() as db:
        libs.aplicar(db, '202406')
        db.commit()
        spei = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE 'SPEI RECIBIDONAFIN%'").fetchall()
        assert spei and all((r['categoria'], r['subcategoria']) == ('CETES', 'RETIRO') for r in spei)
        exp = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE '%EXPENSE%'").fetchall()
        assert exp and all(r['categoria'] == ('EXPENSE' if r['tipo'] == 'GASTO' else 'FINANZAS') for r in exp)


def test_dos_retiros_identicos_el_mismo_dia_entran_los_dos(test_db):
    d = libs.cargar('202310')
    with database.get_db() as db:
        assert libs.aplicar(db, '202310') == (len(d['movimientos']), 0)
        db.commit()
        n = db.execute("""SELECT COUNT(*) FROM est_movimientos WHERE fecha='2023-10-04'
                          AND descripcion LIKE 'RETIRO SIN TARJETA QR%' AND monto=300""").fetchone()[0]
        assert n == 2
