"""
test_comparar_pdf_vs_db.py — covers _comparar_pdf_vs_db in
modules/finanzas/estados/routes.py, the matching logic shared by
/admin/audit-montos (read-only) and /admin/recover-montos (inserts
confirmed-missing rows).

A first version of this matching sorted each side by monto and zipped by
position — which mismatches whenever a (fecha, descripcion) key has more
than one real transaction (e.g. two separate "PAGO CUENTA DE TERCERO ...
TRANSF A X" transfers the same day for different amounts): it could pair
two amounts that belong to entirely different transactions and report a
false "monto_no_coincide", while an amount that actually matches exactly
goes unrecognized. The fix: match by EXACT monto first (removing matched
pairs from both sides regardless of order), and only report a
"monto_no_coincide" when exactly one row is left over on each side for
that key — otherwise it's genuinely ambiguous which leftover corresponds
to which, and it must never be guessed.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.routes import _comparar_pdf_vs_db


def _mov(fecha, desc, monto, tipo="GASTO"):
    return {"fecha": fecha, "descripcion": desc, "monto": monto, "tipo": tipo,
            "fecha_cargo": fecha, "banco": "BBVA_DEB", "periodo": "p",
            "categoria": "OTROS", "subcategoria": ""}


def _row(id_, fecha, desc, monto, tipo="GASTO"):
    return {"id": id_, "fecha": fecha, "descripcion": desc, "monto": monto, "tipo": tipo}


def test_exact_match_reports_nothing():
    pdf = [_mov("2025-01-01", "X", 100)]
    db = [_row(1, "2025-01-01", "X", 100)]
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert faltan == [] and mism == [] and fant == []


def test_single_row_key_with_different_monto_is_reported_as_mismatch():
    pdf = [_mov("2025-01-01", "X", 100)]
    db = [_row(1, "2025-01-01", "X", 250)]
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert faltan == [] and fant == []
    assert len(mism) == 1
    assert mism[0]["pdf"]["monto"] == 100
    assert mism[0]["db"]["monto"] == 250
    assert mism[0]["db"]["id"] == 1


def test_pdf_row_with_no_db_counterpart_is_missing():
    pdf = [_mov("2025-01-01", "X", 100)]
    db = []
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert mism == [] and fant == []
    assert len(faltan) == 1 and faltan[0]["monto"] == 100


def test_db_row_with_no_pdf_counterpart_is_a_ghost():
    pdf = []
    db = [_row(1, "2025-01-01", "X", 100)]
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert faltan == [] and mism == []
    assert len(fant) == 1 and fant[0]["id"] == 1


def test_two_real_transactions_same_day_same_description_both_match_exact():
    # The exact scenario that used to be silently dropped at import time
    # (idx_est_mov_dedup was UNIQUE(fecha, descripcion) only): two
    # different real transfers, same day, same description, different
    # amounts. Once both are actually present in the DB, matching them
    # must not depend on row order.
    pdf = [_mov("2025-01-01", "TRANSF A X", 100), _mov("2025-01-01", "TRANSF A X", 200)]
    db = [_row(2, "2025-01-01", "TRANSF A X", 200), _row(1, "2025-01-01", "TRANSF A X", 100)]
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert faltan == [] and mism == [] and fant == []


def test_more_pdf_rows_than_db_rows_for_a_key_never_guesses_a_pairing():
    # Real bug found auditing production data: PDF has amounts [3807.6,
    # 8978] for the same key, DB only has [8978]. The old sorted-zip
    # pairing falsely reported "8978 saved instead of 3807.6" (comparing
    # two DIFFERENT real transactions) while the row that actually matches
    # (8978) went unrecognized. The fix must recognize the exact match and
    # report only the genuinely absent amount as missing -- no mismatch.
    pdf = [_mov("2025-10-08", "PAGO TARJETA DE CREDITO", 8978),
           _mov("2025-10-08", "PAGO TARJETA DE CREDITO", 3807.6)]
    db = [_row(1, "2025-10-08", "PAGO TARJETA DE CREDITO", 8978)]
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert mism == [], "the exact match (8978) must not be reported as a mismatch"
    assert fant == []
    assert len(faltan) == 1 and faltan[0]["monto"] == 3807.6


def test_multiple_leftovers_on_both_sides_never_guesses_a_pairing():
    pdf = [_mov("2025-01-01", "X", 10), _mov("2025-01-01", "X", 20)]
    db = [_row(1, "2025-01-01", "X", 30), _row(2, "2025-01-01", "X", 40)]
    faltan, mism, fant = _comparar_pdf_vs_db(pdf, db)
    assert mism == [], "2 leftovers vs 2 leftovers is ambiguous -- must not pair them"
    assert {m["monto"] for m in faltan} == {10, 20}
    assert {r["id"] for r in fant} == {1, 2}


def test_faltan_entries_carry_full_movimiento_for_recovery_insert():
    # /admin/recover-montos inserts directly from the `faltan` entries, so
    # they must carry every column est_movimientos needs, not just a
    # display-friendly summary.
    pdf = [_mov("2025-01-01", "X", 100, tipo="INGRESO")]
    faltan, _, _ = _comparar_pdf_vs_db(pdf, [])
    assert faltan[0]["fecha_cargo"] == "2025-01-01"
    assert faltan[0]["banco"] == "BBVA_DEB"
    assert faltan[0]["periodo"] == "p"
    assert faltan[0]["categoria"] == "OTROS"
    assert faltan[0]["tipo"] == "INGRESO"
