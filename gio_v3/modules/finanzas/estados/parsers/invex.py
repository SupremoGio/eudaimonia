from pathlib import Path
from ..config import PDF_PASSWORD
from ._base import (
    parse_text_statement,
    extract_periodo,
    open_pdf,
    merge_split_transactions,
    merge_continuations,
)

PAYMENT_KW = ["SU PAGO POR SPEI", "PAGO TDC", "SPEI RECIBIDO", "ABONO RECIBIDO", "PAGO TARJETA"]


def parse(pdf_path: Path) -> list[dict]:
    movimientos = []
    try:
        with open_pdf(pdf_path, PDF_PASSWORD) as pdf:
            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

        full_text = merge_split_transactions(full_text)
        full_text = merge_continuations(full_text)

        inicio, fin = extract_periodo(full_text)
        periodo = f"{inicio} al {fin}" if inicio and fin else None
        movimientos = parse_text_statement(full_text, PAYMENT_KW, periodo)
    except Exception as e:
        print(f"  [ERROR INVEX] {e}")
    return movimientos
