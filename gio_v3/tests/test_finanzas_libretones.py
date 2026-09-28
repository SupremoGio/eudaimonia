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


@pytest.mark.parametrize('clave', libs.archivos('bbva_tdc_oro'))
def test_tdc_oro_cuadra_con_total_importes(clave):
    """En crédito los abonos (pagos, devoluciones) vienen con monto negativo."""
    d = libs.cargar(clave, 'bbva_tdc_oro')
    cargos = sum(m['monto'] for m in d['movimientos'] if m['monto'] > 0)
    abonos = -sum(m['monto'] for m in d['movimientos'] if m['monto'] < 0)
    assert round(cargos, 2) == d['totales']['cargos'] and round(abonos, 2) == d['totales']['abonos']


def test_tdc_oro_inserta_en_credito_sin_duplicar(test_db):
    d = libs.cargar('202405', 'bbva_tdc_oro')
    with database.get_db() as db:
        # Ya estaba el pago de $10,000 del 09/05/24 (de otro import)
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES ('2024-05-09', 'BMOVIL.PAGO TDC', -10000, 'BBVA_TDC', 'PAGO_TDC', '', 'PAGO')""")
        db.commit()
        assert libs.aplicar(db, '202405', 'bbva_tdc_oro') == (len(d['movimientos']) - 1, 1)
        db.commit()
        msi = db.execute("""SELECT * FROM est_movimientos WHERE banco='BBVA_TDC'
                            AND descripcion LIKE '%LIVERPOOL%' AND parcialidad_num=7""").fetchone()
        assert msi['parcialidad_total'] == 9 and msi['compra_msi_id']
        assert db.execute("SELECT COUNT(*) FROM est_movimientos WHERE banco='BBVA_DEB'").fetchone()[0] == 0


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


def test_cetes_por_spei_y_fondo_de_ahorro(test_db):
    with database.get_db() as db:
        libs.aplicar(db, '202401')
        libs.aplicar(db, '202402')
        db.commit()
        env = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE 'SPEI ENVIADO NAFIN%'").fetchall()
        dev = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE 'SPEI DEVUELTONAFIN%'").fetchall()
        assert env and all((r['categoria'], r['subcategoria']) == ('CETES', 'APORTACION') for r in env)
        assert dev and all((r['categoria'], r['subcategoria']) == ('CETES', 'RETIRO') for r in dev)
        fdo = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE '%FDO AHORRO%'").fetchone()
        assert (fdo['categoria'], fdo['subcategoria']) == ('NOMINA', 'Fondo de ahorro')


def test_ptu_y_spei_devuelto(test_db):
    with database.get_db() as db:
        libs.aplicar(db, '202301')
        libs.aplicar(db, '202302')   # el PTU (26/01/2023) viene en el corte de febrero
        db.commit()
        ptu = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE '%PTU%'").fetchone()
        assert (ptu['categoria'], ptu['subcategoria']) == ('NOMINA', 'PTU')
        dev = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE 'SPEI DEVUELTOBAJIO%'").fetchone()
        assert (dev['categoria'], dev['subcategoria']) == ('FINANZAS', 'Reembolsable')
        fdo = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE '%FONDO AHORRO%'").fetchone()
        assert fdo['subcategoria'] == 'Fondo de ahorro'



@pytest.mark.parametrize('clave', libs.archivos('bbva_tdc'))
def test_tdc_pdf_cuadra_con_total_cargos(clave):
    """Formato actual: TOTAL CARGOS no incluye penalizaciones/comisiones (van aparte)."""
    d = libs.cargar(clave, 'bbva_tdc')
    cargos = sum(m['monto'] for m in d['movimientos'] if m['monto'] > 0)
    abonos = -sum(m['monto'] for m in d['movimientos'] if m['monto'] < 0)
    t = d['totales']
    assert round(cargos, 2) == round(t['cargos'] + t.get('cargos_fuera_de_total', 0), 2)
    assert round(abonos, 2) == t['abonos']


def test_tdc_pdf_completa_la_mensualidad_de_una_fila_existente(test_db):
    """La mensualidad ya estaba (de un CSV) sin «5 de 6»: no se duplica y se le pone."""
    with database.get_db() as db:
        mid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                            VALUES ('2025-08-22', 'LIVERPOOL ZAPOPAN', 409, 'BBVA_TDC', 'ROPA', 'Calzado', 'GASTO')""").lastrowid
        db.commit()
        libs.aplicar(db, '202508', 'bbva_tdc')
        db.commit()
        r = db.execute("SELECT parcialidad_num, parcialidad_total FROM est_movimientos WHERE id=?", (mid,)).fetchone()
        assert tuple(r) == (5, 6)
        assert db.execute("SELECT COUNT(*) FROM est_movimientos WHERE descripcion LIKE 'LIVERPOOL ZAPOPAN%' AND monto=409").fetchone()[0] == 1


def test_tdc_pdf_no_empata_otro_comercio_por_fecha_de_liquidacion(test_db):
    """Corte 202607: la mensualidad Amazon $114 (22/07, liquida 23/07) no es el
    Little Caesars de $114 del 23/07 que ya estaba (del corte siguiente)."""
    with database.get_db() as db:
        lc = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                           VALUES ('2026-07-23', 'LITTLE CAESAR A CAMACH', 114.0, 'BBVA_TDC', 'COMIDA_FUERA', '', 'GASTO')""").lastrowid
        db.commit()
        libs.aplicar(db, '202607', 'bbva_tdc')
        db.commit()
        assert db.execute("SELECT parcialidad_num FROM est_movimientos WHERE id=?", (lc,)).fetchone()[0] is None
        am = db.execute("""SELECT parcialidad_num, parcialidad_total FROM est_movimientos
                           WHERE fecha='2026-07-22' AND descripcion LIKE 'AMAZON A MESES%' AND monto=114""").fetchone()
        assert tuple(am) == (6, 6)


def test_reparar_parcialidades_de_otro_comercio(test_db):
    """Lo que dejó el cargador viejo: la «6 de 6» en el Little Caesars y sin la mensualidad."""
    with database.get_db() as db:
        lc = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo,
                           parcialidad_num, parcialidad_total)
                           VALUES ('2026-07-23', 'LITTLE CAESAR A CAMACH', 114.0, 'BBVA_TDC', 'COMIDA_FUERA', '', 'GASTO', 6, 6)""").lastrowid
        db.commit()
        arr = libs.reparar_parcialidades(db)
        db.commit()
        assert len(arr) == 1 and 'LITTLE CAESAR' in arr[0]
        assert db.execute("SELECT parcialidad_num FROM est_movimientos WHERE id=?", (lc,)).fetchone()[0] is None
        assert db.execute("""SELECT COUNT(*) FROM est_movimientos WHERE fecha='2026-07-22'
                             AND descripcion LIKE 'AMAZON A MESES%' AND monto=114 AND parcialidad_num=6""").fetchone()[0] == 1
        assert libs.reparar_parcialidades(db) == []


def test_libretones_2021_2022_nomina_y_cancelados(test_db):
    """202201-202207: aguinaldo 2021, fondo de ahorro y quincena «PAGO Q8» a
    NOMINA; el $1,500 «ERR DEL HORROR» del 10/06/2022 regresó (no es ingreso)."""
    with database.get_db() as db:
        for k in ('202201', '202205', '202207'):
            libs.aplicar(db, k)
        db.commit()
        cat = lambda like: tuple(db.execute(
            "SELECT categoria, subcategoria FROM est_movimientos WHERE descripcion LIKE ? ORDER BY id LIMIT 1", (like,)).fetchone())
        assert cat('PAGO DE AGUINALDO%') == ('NOMINA', 'Aguinaldo')
        assert cat('DEPOSITO DE TERCERO FONDO DE AHORRO%') == ('NOMINA', 'Fondo de ahorro')
        assert cat('DEPOSITO DE TERCERO PAGO Q8%') == ('NOMINA', 'Pago nominal')
        assert cat('CORRECCION COMPRA TIEMPO%') == ('DIGITAL', 'Celular')
        assert cat('%ERR DEL HORROR') == ('FINANZAS', 'Reembolsable')
        assert cat('%BNET PABLO') != ('FINANZAS', 'Reembolsable')      # el usuario: fue renta
