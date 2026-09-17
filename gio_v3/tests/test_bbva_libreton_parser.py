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

# ── "PAGO CUENTA DE TERCERO" cargo/abono verification ──────────────────────────
#
# BBVA doesn't indicate direction in the text for "PAGO CUENTA DE TERCERO"
# lines (unlike "SPEI ENVIADO"/"SPEI RECIBIDO", which are unambiguous by
# name) — the old parser guessed GASTO by default and was silently wrong
# whenever a transfer was actually incoming. Real statements confirmed this:
# a "Transf a X" line and a same-amount "expense" line both defaulted to
# GASTO, but the printed running balance showed one of each was actually an
# abono. The parser now verifies these against the balance printed after
# each transaction (SALDO OPERACION) instead of guessing, only applying a
# correction when exactly one sign-flip combination of the still-unresolved
# ambiguous lines explains the observed balance jump — never when the
# explanation is ambiguous between multiple candidates.
SAMPLE_TEXT_AMBIGUOUS_TIPOS = """Periodo DEL 07/01/2025 AL 06/02/2025
Fecha de Corte 06/02/2025
Comportamiento
Saldo Anterior 1,000.00
Detalle de Movimientos Realizados
FECHA SALDO
OPER LIQ DESCRIPCION REFERENCIA CARGOS ABONOS OPERACION LIQUIDACION
01/ENE 01/ENE PAGO CUENTA DE TERCERO 100.00 900.00 900.00
 BNET 1111111111 Transf a AMIGO A Referencia 1111111111
02/ENE 02/ENE PAGO CUENTA DE TERCERO 50.00 950.00 950.00
 BNET 2222222222 Transf a AMIGO B Referencia 2222222222
03/ENE 03/ENE PAGO CUENTA DE TERCERO 10.00
 BNET 3333333333 Transf a C1 Referencia 3333333333
03/ENE 03/ENE PAGO CUENTA DE TERCERO 20.00
 BNET 4444444444 Transf a C2 Referencia 4444444444
03/ENE 03/ENE PAGO CUENTA DE TERCERO 30.00 1,010.00 1,010.00
 BNET 5555555555 Transf a C3 Referencia 5555555555
04/ENE 04/ENE PAGO CUENTA DE TERCERO 15.00
 BNET 6666666666 Transf a E1 Referencia 6666666666
04/ENE 04/ENE PAGO CUENTA DE TERCERO 15.00 1,000.00 1,000.00
 BNET 7777777777 Transf a E2 Referencia 7777777777"""


def test_default_gasto_kept_when_it_already_matches_the_printed_balance():
    bounds = _extract_year_bounds(SAMPLE_TEXT_AMBIGUOUS_TIPOS)
    movs = _parse_text(SAMPLE_TEXT_AMBIGUOUS_TIPOS, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A AMIGO A"]["tipo"] == "GASTO"


def test_single_ambiguous_line_is_flipped_to_ingreso_when_balance_requires_it():
    bounds = _extract_year_bounds(SAMPLE_TEXT_AMBIGUOUS_TIPOS)
    movs = _parse_text(SAMPLE_TEXT_AMBIGUOUS_TIPOS, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A AMIGO B"]["tipo"] == "INGRESO"


def test_multiple_ambiguous_lines_all_flip_together_when_uniquely_explained():
    bounds = _extract_year_bounds(SAMPLE_TEXT_AMBIGUOUS_TIPOS)
    movs = _parse_text(SAMPLE_TEXT_AMBIGUOUS_TIPOS, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A C1"]["tipo"] == "INGRESO"
    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A C2"]["tipo"] == "INGRESO"
    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A C3"]["tipo"] == "INGRESO"


def test_ambiguous_lines_stay_at_default_when_the_flip_is_not_uniquely_attributable():
    # E1 and E2 have the same monto, so a balance jump matching "flip one of
    # them" can't tell which one — must not guess either way.
    bounds = _extract_year_bounds(SAMPLE_TEXT_AMBIGUOUS_TIPOS)
    movs = _parse_text(SAMPLE_TEXT_AMBIGUOUS_TIPOS, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A E1"]["tipo"] == "GASTO"
    assert by_desc["PAGO CUENTA DE TERCERO BNET TRANSF A E2"]["tipo"] == "GASTO"


SAMPLE_TEXT_RELIABLE_KEYWORDS = """Periodo DEL 07/01/2025 AL 06/02/2025
Fecha de Corte 06/02/2025
Detalle de Movimientos Realizados
FECHA SALDO
OPER LIQ DESCRIPCION REFERENCIA CARGOS ABONOS OPERACION LIQUIDACION
07/ENE 07/ENE DEPOSITO DE TERCERO 74,657.10
 FDO AHORRO 2024 BMRCASH Referencia REFBNTC00308757
03/FEB 04/FEB SPEI DEVUELTONAFIN 25,130.00
 1712240giovany ene 25 Referencia 0079616016 135"""


def test_deposito_de_tercero_and_devuelto_are_reliably_ingreso_by_keyword():
    bounds = _extract_year_bounds(SAMPLE_TEXT_RELIABLE_KEYWORDS)
    movs = _parse_text(SAMPLE_TEXT_RELIABLE_KEYWORDS, bounds, periodo=None)
    by_desc = {m["descripcion"]: m for m in movs}

    assert by_desc["DEPOSITO DE TERCERO FDO AHORRO 2024 BMRCASH"]["tipo"] == "INGRESO"
    assert by_desc["SPEI DEVUELTONAFIN"]["tipo"] == "INGRESO"

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
