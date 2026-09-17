"""
Regression test for modules/finanzas/estados/parsers/bbva_libreton.py.

BBVA Libretón statement lines carry no year at all ("DD/MES DD/MES ..."),
so the year has to come from the statement's "Periodo DEL dd/mm/yyyy AL
dd/mm/yyyy" header. Libretón cycles always cut mid-month, so a December
statement's period is e.g. "DEL 07/12/2024 AL 06/01/2025" — start and end
years differ. The parser used to grab a single year (the period's end
year) and stamp every transaction with it, so December movements were
saved as "2025-12-DD" instead of "2024-12-DD": a year off. Filtering by
year in the app then made those December transactions look missing from
2024 (and, since there's a UNIQUE(fecha, descripcion) index, a real
December-2025 statement uploaded later could silently collide with these
mislabeled rows and get dropped as a false duplicate).

This test uses fabricated data (not any real statement) shaped like the
actual PDF text pdfplumber extracts, reproducing the year-crossing period.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.parsers.bbva_libreton import _extract_year_bounds, _parse_text

SAMPLE_TEXT_CROSS_YEAR = """Periodo DEL 07/12/2024 AL 06/01/2025
Fecha de Corte 06/01/2025
Detalle de Movimientos Realizados
FECHA SALDO
OPER LIQ DESCRIPCION REFERENCIA CARGOS ABONOS OPERACION LIQUIDACION
07/DIC 09/DIC PAGO CUENTA DE TERCERO 500.00 12,471.10 12,971.10
 BNET 1500866230 Transf a JUDITH A Referencia 2559027213
30/DIC 30/DIC PAGO DE NOMINA 12,224.89 26,560.88 26,560.88
 FIBRA HOTELERA SC Referencia HH 4206466060
03/ENE 03/ENE PAGO CUENTA DE TERCERO 789.00
 BNET 1539617589 ropita Referencia 4895769993
06/ENE 06/ENE RECARGAS Y PAQUETES BMOV 150.00 27,621.88 27,621.88
 06/ENE 12:49 AUT:489649 Referencia ******5725
TOTAL IMPORTE CARGOS 29,997.15 TOTAL MOVIMIENTOS CARGOS 3
TOTAL IMPORTE ABONOS 44,647.93 TOTAL MOVIMIENTOS ABONOS 1"""

SAMPLE_TEXT_SAME_YEAR = """Periodo DEL 07/01/2025 AL 06/02/2025
Fecha de Corte 06/02/2025
Detalle de Movimientos Realizados
FECHA SALDO
OPER LIQ DESCRIPCION REFERENCIA CARGOS ABONOS OPERACION LIQUIDACION
07/ENE 07/ENE DEPOSITO DE TERCERO 74,657.10
 FDO AHORRO 2024 BMRCASH Referencia REFBNTC00308757
04/FEB 04/FEB SPEI ENVIADO BANAMEX 1,750.00
 1712240Tamales marriott Referencia 0083471611 002"""


def test_december_transactions_keep_the_start_year():
    bounds = _extract_year_bounds(SAMPLE_TEXT_CROSS_YEAR)
    movs = _parse_text(SAMPLE_TEXT_CROSS_YEAR, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    dic_mov = by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A"]
    assert dic_mov["fecha"] == "2024-12-07"

    nomina_mov = by_desc["PAGO DE NOMINA FIBRA HOTELERA SC"]
    assert nomina_mov["fecha"] == "2024-12-30"


def test_january_transactions_get_the_end_year():
    bounds = _extract_year_bounds(SAMPLE_TEXT_CROSS_YEAR)
    movs = _parse_text(SAMPLE_TEXT_CROSS_YEAR, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    assert by_desc["PAGO CUENTA DE TERCERO BNET ROPITA"]["fecha"] == "2025-01-03"
    assert by_desc["RECARGAS Y PAQUETES BMOV"]["fecha"] == "2025-01-06"


def test_single_year_period_is_unaffected():
    bounds = _extract_year_bounds(SAMPLE_TEXT_SAME_YEAR)
    movs = _parse_text(SAMPLE_TEXT_SAME_YEAR, bounds, periodo=None)
    fechas = sorted(m["fecha"] for m in movs)

    assert fechas == ["2025-01-07", "2025-02-04"]


def test_all_movements_are_captured_no_count_regression():
    bounds = _extract_year_bounds(SAMPLE_TEXT_CROSS_YEAR)
    movs = _parse_text(SAMPLE_TEXT_CROSS_YEAR, bounds, periodo=None)
    assert len(movs) == 4
