"""
Regression test for modules/finanzas/estados/parsers/bbva_debit.py.

pdfplumber extracts BBVA débito statement text with the description split
across the line *before* and/or *after* the "DD mon YYYY ... $monto $saldo"
line — except when a movement fits entirely on one line, in which case the
neighbouring lines belong to *other* entries. The reconstruction logic used
to grab the line before a date unconditionally, which leaked a neighbouring
entry's description into a self-contained one-line entry (and dropped that
neighbour's own description in the process). This test uses fabricated
data (not any real statement) that reproduces the exact line-ordering
pattern that triggered the bug.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.parsers.bbva_debit import _parse_text

SAMPLE_TEXT = """NOMBRE APELLIDO EJEMPLO
Monto disponible
Cuenta: 1111111111 $5,00000
DETALLES DE MOVIMIENTOS
Periodo: Mes Actual, Todos los importes
FECHA DESCRIPCIÓN MONTO SALDO TOTAL
PAGO DE NOMINA / HH 1111111111
01 ene 2026 $1,00000 $5,00000
EMPRESA EJEMPLO SA
PAGO CUENTA DE TERCERO /
02 ene 2026 $-1000 $4,90000
0000000001 BNET 0000000002 prestamo
03 ene 2026 RETIRO SIN TARJETA QR / ******0000 $-20000 $4,70000
SPEI ENVIADO BANCO /
04 ene 2026 0000000003 001 0000000honorarios $-50000 $4,20000
medicos
En cumplimiento a la Ley Federal de Transparencia te presentamos el desglose de la comisión cobrada en
caso de haber utilizado cajeros automáticos de otras entidades financieras.
BBVA México, S.A. Institución de Banca Múltiple, Grupo Financiero BBVA México."""


def test_self_contained_entry_does_not_absorb_neighbour_description():
    movs = _parse_text(SAMPLE_TEXT, periodo=None)
    by_fecha = {m["fecha"]: m for m in movs}

    assert len(movs) == 4

    # Entry 2 (multi-line: before-line + empty inline + after-line) keeps
    # its own full description, including the "prestamo" continuation.
    assert "PRESTAMO" in by_fecha["2026-01-02"]["descripcion"]

    # Entry 3 is fully self-contained on one line — it must NOT pick up
    # entry 2's leftover continuation line ("0000000001 BNET ... prestamo").
    entry3_desc = by_fecha["2026-01-03"]["descripcion"]
    assert "PRESTAMO" not in entry3_desc
    assert "0000000001" not in entry3_desc
    assert "RETIRO SIN TARJETA" in entry3_desc

    # Entry 4 (3-line: before-line + partial inline + after-line) must
    # reconstruct all three fragments together.
    entry4_desc = by_fecha["2026-01-04"]["descripcion"]
    assert "SPEI ENVIADO BANCO" in entry4_desc
    assert "MEDICOS" in entry4_desc


def test_amounts_and_signs_unaffected_by_description_fix():
    movs = _parse_text(SAMPLE_TEXT, periodo=None)
    by_fecha = {m["fecha"]: m for m in movs}

    assert by_fecha["2026-01-01"]["monto"] == 1000.0
    assert by_fecha["2026-01-01"]["tipo"] == "INGRESO"

    assert by_fecha["2026-01-02"]["monto"] == 10.0
    assert by_fecha["2026-01-02"]["tipo"] == "GASTO"

    assert by_fecha["2026-01-03"]["monto"] == 200.0
    assert by_fecha["2026-01-03"]["tipo"] == "GASTO"

    assert by_fecha["2026-01-04"]["monto"] == 500.0
    assert by_fecha["2026-01-04"]["tipo"] == "GASTO"


# ── Blindaje de dirección (2026-10-03): cargos leídos como abonos ──────────────
# Datos de ejemplo inventados para probar la lógica (signo y saldo).
SAMPLE_SALDOS = """FECHA DESCRIPCIÓN MONTO SALDO TOTAL
01 mar 2026 PAGO DE NOMINA / HH 1111111111 $10,00000 $10,00000
04 mar 2026 PAGO CUENTA DE TERCERO / CONCEPTO A -$40000 $9,60000
14 abr 2026 PAGO CUENTA DE TERCERO / CONCEPTO B $−70000 $8,90000
27 jun 2026 PAGO CUENTA DE TERCERO / CONCEPTO C $35800 $8,54200
02 jul 2026 SPEI RECIBIDO STP / QUALITAS $1,00000 $9,54200"""


def test_signo_menos_antes_del_peso_o_tipografico_es_cargo():
    by = {m["fecha"]: m for m in _parse_text(SAMPLE_SALDOS, periodo=None)}
    assert by["2026-03-04"]["tipo"] == "GASTO" and by["2026-03-04"]["monto"] == 400.0
    assert by["2026-04-14"]["tipo"] == "GASTO" and by["2026-04-14"]["monto"] == 700.0


def test_el_saldo_corrige_un_cargo_sin_signo():
    # Viene sin signo pero el saldo bajó $358: es cargo (saldos inventados, no de un PDF real).
    by = {m["fecha"]: m for m in _parse_text(SAMPLE_SALDOS, periodo=None)}
    assert by["2026-06-27"]["tipo"] == "GASTO"
    assert by["2026-06-27"]["dir_verificada"] is True
    assert by["2026-07-02"]["tipo"] == "INGRESO" and by["2026-07-02"]["dir_verificada"] is True


def test_estado_del_mas_nuevo_al_mas_viejo():
    lineas = SAMPLE_SALDOS.split("\n")
    texto = "\n".join([lineas[0]] + lineas[1:][::-1])
    by = {m["fecha"]: m for m in _parse_text(texto, periodo=None)}
    assert by["2026-06-27"]["tipo"] == "GASTO" and by["2026-07-02"]["tipo"] == "INGRESO"



def test_excel_con_cero_en_abonos_es_cargo():
    import pandas as pd
    from modules.finanzas.estados.parsers.bbva_debit_xlsx import _parse_df
    raw = pd.DataFrame([["FECHA", "DESCRIPCIÓN", "CARGO", "ABONO", "SALDO"],
                        ["04/03/2026", "PAGO CUENTA DE TERCERO ARBITRAJE GIO", "400.00", "0", "9600"],
                        ["05/03/2026", "SPEI RECIBIDO", "0", "100.00", "9700"]])
    movs = _parse_df(raw)
    assert [(m["monto"], m["tipo"]) for m in movs] == [(400.0, "GASTO"), (100.0, "INGRESO")]
