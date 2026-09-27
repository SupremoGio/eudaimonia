"""Parser del formato viejo «Tarjeta Oro BBVA» (cortes 2022-2024)."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.parsers import bbva as B

TEXTO = """Tasa Anual Tasa Anual Moratoria Tasa Mensual Días Transcurridos Periodo
0.00 % 0.00 % 0.00 % 30 Del 23/04/24
al 22/05/24
Movimientos Efectuados Tarjeta Titular 4772 1330 5409 7990
FECHA FECHA CONCEPTO R.F.C. REFERENCIA IMPORTE IMPORTE
23/04/24 23/04/24 SORIANA313 AMERICASGDL TSO 991022PB6 ******8256 $ 329.23
05/05/24 06/05/24 BMOVIL.PAGO TDC ******3615 $ 1,500.00-
Iva :$ 0.00 Interes: $ 0.00 Comisiones:$ 0.00 Capital:$ 1,500.00 Capital de promoción:$ 0.00 Pago excedente:$ 0.00
12/05/24 13/05/24 REST CUBIL LATINO PAAA771213QA0 ******8939 $ 161.00
22/05/24 23/05/24 07 DE 09 LIVERPOOL GUADALAJARA $ 249.00
TOTAL IMPORTES: $ 739.23 $ 1,500.00-
Resumen Informativo de sus Cargos sin Intereses
15/10/23 CHEDRAUI TDA EN LINEA $ 7,395.00 $ 569.00 05 de 13 $ 2,843.00
"""


def test_parsea_cargos_abonos_msi_y_periodo():
    ms = B.parse_tarjeta_oro(TEXTO)
    assert [m['descripcion'] for m in ms] == ['SORIANA313 AMERICASGDL', 'BMOVIL.PAGO TDC',
                                             'REST CUBIL LATINO', 'LIVERPOOL GUADALAJARA']
    assert ms[0]['fecha'] == '2024-04-23' and ms[0]['periodo'] == '2024-04-23 al 2024-05-22'
    assert (ms[1]['monto'], ms[1]['tipo']) == (-1500.0, 'PAGO')
    assert (ms[3]['parcialidad_num'], ms[3]['parcialidad_total']) == (7, 9)
    assert B.oro_totales(TEXTO) == (739.23, 1500.0)


def test_anualidad_diferida_no_es_movimiento():
    texto = """Movimientos Efectuados Tarjeta Titular 4772 1330 5409 7990
22/12/22 23/12/22 01 DE 06 MEN S FACTORY P PAT I $ 462.00
22/12/22 22/12/22 01 DE 03 ANUALIDAD $ 358.66
TOTAL IMPORTES: $ 462.00
"""
    assert [m['monto'] for m in B.parse_tarjeta_oro(texto)] == [462.0]


def test_cargos_no_reconocidos_no_son_movimientos():
    texto = """TOTAL ABONOS -$12,545.35
CARGOS NO RECONOCIDOS
Notas: Ver notas en la sección “NOTAS ACLARATORIAS” en este estado de cuenta.
06-jul-2025 05-ago-2025 SHERATON MEXICO C Concluida, 8054954410 - $8,910.00
improcedente 9066198060
NOTAS ACLARATORIAS
1. Tienes como límite"""
    assert 'SHERATON' not in B._sin_secciones_informativas(texto)
    assert 'NOTAS ACLARATORIAS\n1.' in B._sin_secciones_informativas(texto)
