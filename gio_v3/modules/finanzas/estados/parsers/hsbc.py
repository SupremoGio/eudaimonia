"""
HSBC Mexico — OCR-based parser (proprietary font encoding).
Requires: pymupdf, pytesseract, Pillow, Tesseract OCR binary.
"""
import os
import re
import io
from pathlib import Path

from ._base import parse_fecha, clean_desc, extract_periodo
from ..config import get_categoria_subcategoria

PAYMENT_KW = ["SU PAGO GRACIAS", "PAGO GRACIAS SPEI", "PAGO TDC", "SPEI", "ABONO"]

_OCR_DATE = r"[0-9Oo]{2}[-/][a-zA-Z]{3}[-/][0-9Oo]{2,4}"

# Regular transaction: two dates + description + amount
HSBC_LINE_RE = re.compile(
    rf"({_OCR_DATE})"
    r"[\s_|]+"
    rf"({_OCR_DATE})"
    r"[\s_|]+"
    r"(.+?)"
    r"\s+\$?\s*([\d,]+\.\d{2})"
    r"\s*$",
    re.IGNORECASE,
)

# MSI installment: one date + description + monto_original + saldo_pendiente + pago_requerido + "N de M" [+ tasa]
MSI_LINE_RE = re.compile(
    rf"^({_OCR_DATE})"
    r"\s+(.+?)"
    r"\s+[\[\|]?\$?\s*([\d,]+\.\d{2})"   # monto original
    r"\s+[\[\|]?\$?\s*([\d,]+\.\d{2})"   # saldo pendiente
    r"\s+[\[\|]?\$?\s*([\d,]+\.\d{2})"   # pago requerido  ← usamos este
    r"\s+\d{1,2}\s+de\s+\d{1,2}"
    r"(?:\s+[\d.]+%)?"
    r"\s*$",
    re.IGNORECASE,
)

REF_PREFIX_RE = re.compile(r"^\|?\s*[A-Z]{2,4}\s+[A-Z0-9]{6,12}\s+", re.IGNORECASE)


def _fix_ocr_date(s: str) -> str:
    parts = re.split(r"([-/])", s)
    if len(parts) >= 5:
        parts[0] = re.sub(r"[Oo]", "0", parts[0])
        parts[4] = re.sub(r"[Oo]", "0", parts[4])
    return "".join(parts)


def _clean_hsbc_desc(desc: str) -> str:
    desc = re.sub(r"^[\[\|_\s]+", "", desc)
    desc = REF_PREFIX_RE.sub("", desc)
    desc = re.sub(r"\[\s*[=\+\-]\s*\]", "", desc)
    desc = re.sub(r"A CTA CLABE\s+\S+", "", desc)
    return clean_desc(desc)


def _ocr_pages(pdf_path: Path) -> str:
    try:
        import fitz
    except ImportError:
        raise RuntimeError("Instala PyMuPDF: pip install pymupdf")
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "Instala pytesseract y Pillow: pip install pytesseract pillow\n"
            "Tambien necesitas Tesseract OCR instalado en el sistema."
        )

    cmd = os.getenv("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    available = pytesseract.get_languages()
    lang = "spa" if "spa" in available else "eng"

    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        mat = fitz.Matrix(3.0, 3.0)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        pages.append(pytesseract.image_to_string(img, lang=lang, config="--psm 4"))
    return "\n".join(pages)


def _parse_lines(full_text: str, periodo: str | None) -> list[dict]:
    movimientos = []

    for linea in full_text.split("\n"):
        linea = linea.strip()
        if not linea:
            continue

        # Regular transaction (two dates)
        m = HSBC_LINE_RE.match(linea)
        if m:
            try:
                monto = float(m.group(4).replace(",", ""))
            except ValueError:
                continue

            desc = _clean_hsbc_desc(m.group(3))
            fecha = parse_fecha(_fix_ocr_date(m.group(1)))
            fecha_cargo = parse_fecha(_fix_ocr_date(m.group(2)))
            tipo = "PAGO" if any(k in desc for k in PAYMENT_KW) else "GASTO"
            cat, subcat = ("PAGO", "") if tipo == "PAGO" else get_categoria_subcategoria(desc)

            movimientos.append({
                "fecha": fecha,
                "fecha_cargo": fecha_cargo,
                "descripcion": desc[:80],
                "monto": monto,
                "categoria": cat,
                "subcategoria": subcat,
                "tipo": tipo,
                "periodo": periodo,
            })
            continue

        # MSI installment — captura el "Pago Requerido" (cuota del periodo)
        m = MSI_LINE_RE.match(linea)
        if m:
            try:
                monto = float(m.group(5).replace(",", ""))  # pago_requerido
            except ValueError:
                continue

            desc = _clean_hsbc_desc(m.group(2))
            fecha = parse_fecha(_fix_ocr_date(m.group(1)))
            cat, subcat = get_categoria_subcategoria(desc)

            movimientos.append({
                "fecha": fecha,
                "fecha_cargo": fecha,
                "descripcion": desc[:80],
                "monto": monto,
                "categoria": cat,
                "subcategoria": subcat,
                "tipo": "GASTO",
                "periodo": periodo,
            })

    return movimientos


def parse(pdf_path: Path) -> list[dict]:
    print("  [HSBC] Aplicando OCR (puede tardar ~30 seg)...")
    try:
        full_text = _ocr_pages(pdf_path)
        inicio, fin = extract_periodo(full_text)
        periodo = f"{inicio} al {fin}" if inicio and fin else None
        movimientos = _parse_lines(full_text, periodo)
        if not movimientos:
            print("  [HSBC] OCR OK pero sin movimientos.")
        return movimientos
    except RuntimeError as e:
        print(f"\n  [HSBC - ACCION REQUERIDA]\n  {e}\n")
        return []
    except Exception as e:
        print(f"  [ERROR HSBC] {e}")
        return []
