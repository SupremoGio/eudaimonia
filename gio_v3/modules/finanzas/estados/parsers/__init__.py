"""
Detects which bank a file belongs to and routes it to the right parser.
"""
from pathlib import Path
import pdfplumber

from ..config import PDF_PASSWORD, PDF_PASSWORD_BBVA
from ._base import open_pdf

SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}


def _open_pdf(pdf_path: Path):
    return open_pdf(pdf_path, PDF_PASSWORD, PDF_PASSWORD_BBVA)


def _detect_bank_pdf(pdf_path: Path) -> str:
    text = ""
    pdf = _open_pdf(pdf_path)
    if pdf:
        try:
            for page in pdf.pages[:2]:
                text += (page.extract_text() or "").upper()
                if text.strip():
                    break
        except Exception:
            pass
        finally:
            pdf.close()

    if "BBVA" in text:
        if "DETALLE DE MOVIMIENTOS REALIZADOS" in text or "OPER LIQ DESCRIPCION" in text:
            return "BBVA_LIB"
        if "DETALLES DE MOVIMIENTOS" in text and "SALDO TOTAL" in text:
            return "BBVA_DEB"
        return "BBVA"
    if "INVEX" in text:
        return "INVEX"
    if "HSBC" in text:
        return "HSBC"

    cid_count = text.count("(CID:") + text.count("(cid:")
    clean = text.replace("?", "").replace("@", "").replace("`", "").strip()
    if cid_count > 10 or not clean or len(clean) < 30:
        return "HSBC"

    name = pdf_path.stem.upper()
    if "BBVA" in name and ("DEB" in name or "DEBITO" in name or "CHEQUE" in name):
        return "BBVA_DEB"
    for banco in ("HSBC", "INVEX", "BBVA"):
        if banco in name:
            return banco

    return "DESCONOCIDO"


def detect_bank(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".csv":
        from .bbva_csv import detect as bbva_detect
        from .bbva_legacy_csv import detect as legacy_detect
        if bbva_detect(path) or legacy_detect(path):
            return "BBVA"
        return "DESCONOCIDO"
    if ext in (".xlsx", ".xls"):
        from .bbva_csv import detect_excel as bbva_excel_detect
        if bbva_excel_detect(path):
            return "BBVA"
        return "DESCONOCIDO"
    return _detect_bank_pdf(path)


def parse_pdf(pdf_path: Path) -> list[dict]:
    banco = _detect_bank_pdf(pdf_path)

    if banco == "BBVA":
        from .bbva import parse
    elif banco == "BBVA_DEB":
        from .bbva_debit import parse
    elif banco == "BBVA_LIB":
        from .bbva_libreton import parse
    elif banco == "INVEX":
        from .invex import parse
    elif banco == "HSBC":
        from .hsbc import parse
    else:
        print(f"  [!] Banco no reconocido en: {pdf_path.name}")
        return []

    print(f"  -> Banco detectado: {banco}")
    movimientos = parse(pdf_path)
    for m in movimientos:
        m["banco"] = banco
    return movimientos


def parse_csv(path: Path) -> list[dict]:
    from .bbva_csv import detect as bbva_detect, parse as bbva_parse
    from .bbva_legacy_csv import detect as legacy_detect, parse as legacy_parse
    if bbva_detect(path):
        print("  -> Banco detectado: BBVA (CSV)")
        movimientos = bbva_parse(path)
    elif legacy_detect(path):
        print("  -> Banco detectado: BBVA (CSV legacy)")
        movimientos = legacy_parse(path)
    else:
        print(f"  [!] Formato CSV no reconocido: {path.name}")
        return []
    for m in movimientos:
        m["banco"] = "BBVA"
    return movimientos


def parse_excel(path: Path) -> list[dict]:
    from .bbva_csv import detect_excel as bbva_detect, parse_excel as bbva_parse
    if bbva_detect(path):
        print(f"  -> Banco detectado: BBVA (Excel)")
        movimientos = bbva_parse(path)
        for m in movimientos:
            m["banco"] = "BBVA"
        return movimientos
    print(f"  [!] Formato Excel no reconocido: {path.name}")
    return []


def parse_file(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".csv":
        return parse_csv(path)
    if ext in (".xlsx", ".xls"):
        return parse_excel(path)
    print(f"  [!] Extensión no soportada: {path.suffix}")
    return []
