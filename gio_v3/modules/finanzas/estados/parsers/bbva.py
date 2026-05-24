from pathlib import Path
from ..config import PDF_PASSWORD, PDF_PASSWORD_BBVA
from ._base import parse_text_statement, extract_periodo, open_pdf

PAYMENT_KW = ["BMOVIL", "PAGO TDC", "SPEI RECIBIDO", "ABONO RECIBIDO", "PAGO TARJETA"]


def parse(pdf_path: Path) -> list[dict]:
    movimientos = []
    try:
        with open_pdf(pdf_path, PDF_PASSWORD, PDF_PASSWORD_BBVA) as pdf:
            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            inicio, fin = extract_periodo(full_text)
            periodo = f"{inicio} al {fin}" if inicio and fin else None
            movimientos = parse_text_statement(full_text, PAYMENT_KW, periodo)
    except Exception as e:
        print(f"  [ERROR BBVA] {e}")
    return movimientos
