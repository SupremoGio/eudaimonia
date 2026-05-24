"""
Shared parsing utilities for text-based statements (BBVA, INVEX).
"""
import re
import pdfplumber
from pathlib import Path
from ..config import MESES, BLACKLIST, MSI_START, MSI_END, get_categoria_subcategoria


def open_pdf(path: Path, *passwords: str):
    candidates = [None, *passwords]
    for pwd in candidates:
        try:
            pdf = pdfplumber.open(path) if pwd is None else pdfplumber.open(path, password=pwd)
            text = "\n".join(p.extract_text() or "" for p in pdf.pages[:3])
            if text.strip():
                return pdf
            pdf.close()
        except Exception:
            pass
    for pwd in [None, *passwords]:
        try:
            return pdfplumber.open(path) if pwd is None else pdfplumber.open(path, password=pwd)
        except Exception:
            pass
    raise RuntimeError(f"No se pudo abrir el PDF: {path.name}")

LINE_RE = re.compile(
    r"^(\d{2}-[a-zA-Z]{3}-\d{2,4})"
    r"\s+(\d{2}-[a-zA-Z]{3}-\d{2,4})"
    r"\s+(.+?)"
    r"\s+([+\-])\s*\$?\s*([\d,]+\.\d{2})"
    r"\s*$",
    re.IGNORECASE,
)

_MSI_INSTALLMENT_RE = re.compile(r"^\d{1,2}\s+DE\s+\d{1,2}\b", re.IGNORECASE)

_DATE_LINE_RE = re.compile(
    r"^(\d{2}-[a-zA-Z]{3}-\d{2,4})\s+(\d{2}-[a-zA-Z]{3}-\d{2,4})\s+(.+)$",
    re.IGNORECASE,
)
_HAS_AMOUNT_RE = re.compile(r"[+\-]\s*\$?\s*[\d,]+\.\d{2}\s*$")
_TRAILING_AMOUNT_RE = re.compile(r"([+\-])\s*\$?\s*([\d,]+\.\d{2})\s*$")

_DATE_AMOUNT_ONLY_RE = re.compile(
    r"^(\d{2}-[a-zA-Z]{3}-\d{2,4})\s+(\d{2}-[a-zA-Z]{3}-\d{2,4})"
    r"\s+([+\-])\s*\$?\s*([\d,]+\.\d{2})\s*$",
    re.IGNORECASE,
)
_DATE_START_RE = re.compile(r"^\d{2}-[a-zA-Z]{3}-\d{2,4}", re.IGNORECASE)
_HEADER_PREFIXES = (
    "TOTAL ", "NOTAS", "VER NOTA", "NÚMERO", "PAGINA", "FECHA DE",
    "CARGOS,", "TARJETA", "TIPO DE CAMBIO", "DESCRIPCI",
)


def merge_split_transactions(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            da = _DATE_AMOUNT_ONLY_RE.match(nxt)
            if (
                da
                and stripped
                and not _DATE_START_RE.match(stripped)
                and not any(stripped.upper().startswith(p) for p in _HEADER_PREFIXES)
            ):
                out.append(
                    f"{da.group(1)}  {da.group(2)}  {stripped}  {da.group(3)} ${da.group(4)}"
                )
                i += 2
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def merge_continuations(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    skip_next = False
    for idx, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        stripped = line.strip()
        if idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            if (
                nxt.upper().startswith("TIPO DE CAMBIO")
                and _DATE_LINE_RE.match(stripped)
                and not _HAS_AMOUNT_RE.search(stripped)
            ):
                amt_m = _TRAILING_AMOUNT_RE.search(nxt)
                if amt_m:
                    out.append(f"{stripped}  {amt_m.group(1)} ${amt_m.group(2)}")
                    skip_next = True
                    continue
        out.append(line)
    return "\n".join(out)


def parse_fecha(s: str) -> str | None:
    if not s:
        return None
    s = s.strip().lower()
    for nombre, num in MESES.items():
        s = s.replace(nombre, num)
    partes = re.split(r"[-/]", s)
    if len(partes) == 3:
        d, m, y = partes
        y = f"20{y}" if len(y) == 2 else y
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return s


def clean_desc(desc: str) -> str:
    desc = re.sub(r";?\s*Tarjeta Digital\s*\*+\d*", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"^\d{1,2}\s+DE\s+\d{1,2}\s+", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\*", " ", desc)
    desc = re.sub(r"\s{2,}", " ", desc)
    return desc.strip().upper()


def is_blacklisted(line: str) -> bool:
    lu = line.upper()
    return any(b in lu for b in BLACKLIST)


def extract_periodo(full_text: str) -> tuple[str | None, str | None]:
    m = re.search(
        r"Periodo:\s*(\d{2}-[a-zA-Z]{3}-\d{2,4})\s+al\s+(\d{2}-[a-zA-Z]{3}-\d{2,4})",
        full_text,
        re.IGNORECASE,
    )
    if m:
        return parse_fecha(m.group(1)), parse_fecha(m.group(2))
    return None, None


def parse_text_statement(
    full_text: str,
    payment_keywords: list[str],
    periodo: str | None = None,
) -> list[dict]:
    movimientos = []
    in_msi = False

    for linea in full_text.split("\n"):
        linea = linea.strip()
        if not linea:
            continue
        lu = linea.upper()

        if any(h in lu for h in MSI_START):
            in_msi = True
            continue

        if in_msi:
            if any(e in lu for e in MSI_END):
                in_msi = False
                continue
            m = LINE_RE.match(linea)
            if not m:
                continue
            if _MSI_INSTALLMENT_RE.match(m.group(3).strip()):
                continue
            in_msi = False
        else:
            m = LINE_RE.match(linea)
            if not m:
                continue
            if _MSI_INSTALLMENT_RE.match(m.group(3).strip()):
                continue

        signo = m.group(4)
        monto = float(m.group(5).replace(",", ""))
        desc = clean_desc(m.group(3))
        fecha = parse_fecha(m.group(1))
        fecha_cargo = parse_fecha(m.group(2))

        tipo = "PAGO" if (signo == "-" or any(k in desc for k in payment_keywords)) else "GASTO"
        if signo == "-":
            monto = -monto

        if tipo == "GASTO":
            cat, subcat = get_categoria_subcategoria(desc)
        else:
            cat, subcat = "PAGO", ""

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

    return movimientos
