"""
BBVA Libretón Básico Cuenta Digital — Estado de cuenta débito.
"""
import re
from pathlib import Path

from ..config import MESES, PDF_PASSWORD, PDF_PASSWORD_BBVA
from ._base import open_pdf

ABONO_KW = [
    "SPEI RECIBIDO", "PAGO DE NOMINA", "DEPOSITO EFECTIVO",
    "SU PAGO", "SITH", "ABONO",
]

CATS_LIBRETON = {
    "NOMINA":        ["PAGO DE NOMINA", "NOMINA", "FIBRA HOTELERA"],
    "INVERSION":     ["CETES", "GBM", "BITSO", "NAFIN", "FONDO"],
    "PAGO_TDC":      ["PAGO TARJETA DE CREDITO", "PAGO TARJETA DE TERCEROS",
                      "PAGO INTERBANCARIO"],
    "SPEI_ENVIADO":  ["SPEI ENVIADO"],
    "SPEI_RECIBIDO": ["SPEI RECIBIDO"],
    "RETIRO":        ["RETIRO SIN TARJETA", "RETIRO"],
    "DEPOSITO":      ["DEPOSITO EFECTIVO"],
    "FIDEICOMISO":   ["FIDEICOMISO", "SITH"],
    "TRANSFERENCIA": ["PAGO CUENTA DE TERCERO", "BNET"],
}

SKIP_KW = [
    "PAGINA ", "PERIODO DEL", "FECHA DE CORTE", "NO. DE CUENTA",
    "NO. DE CLIENTE", "R.F.C", "SUCURSAL:", "TELEFONO:", "PLAZA:",
    "INFORMACION FINANCIERA", "RENDIMIENTO", "SALDO PROMEDIO",
    "DIAS DEL PERIODO", "TASA BRUTA", "TASA DE", "INTERESES A FAVOR",
    "ISR RETENIDO", "COMISIONES", "CHEQUES PAGADOS", "MANEJO DE CUENTA",
    "TOTAL COMISIONES", "CARGOS OBJETADOS", "ABONOS OBJETADOS",
    "TOTAL DE APARTADOS", "SALDO GLOBAL", "DETALLE DE MOVIMIENTOS",
    "OPER LIQ DESCRIPCION", "GAT REAL", "BBVA MEXICO,", "AV. PASEO",
    "TOTAL DE MOVIMIENTOS", "TOTAL IMPORTE", "LE INFORMAMOS",
    "ESTADO DE CUENTA DE APARTADOS", "FOLIO NOMBRE APARTADO",
    "ANTES DE IMPUESTOS", "LA GAT REAL", "GIOVANNI", "GIOVANY ALBERTO",
    "DIRECCION:", "COL ", "CENTRO", "TAB MEXICO", "JOSE MARIA",
]

TXN_RE = re.compile(
    r"^(\d{2}/[A-Z]{3})\s+(\d{2}/[A-Z]{3})\s+(.+?)\s+([\d,]+\.\d{2})"
    r"(?:\s+[\d,]+\.\d{2}(?:\s+[\d,]+\.\d{2})?)?\s*$",
    re.IGNORECASE,
)

PERIODO_RE = re.compile(
    r"periodo\s+del\s+\d{2}/\d{2}/(\d{4})\s+al\s+\d{2}/\d{2}/(\d{4})",
    re.IGNORECASE,
)
CORTE_RE = re.compile(r"fecha\s+de\s+corte\s+\d{2}/\d{2}/(\d{4})", re.IGNORECASE)


def _extract_year(full_text: str) -> int:
    m = PERIODO_RE.search(full_text)
    if m:
        return int(m.group(2))
    m = CORTE_RE.search(full_text)
    if m:
        return int(m.group(1))
    return 2025


def _extract_periodo(full_text: str) -> str | None:
    m = PERIODO_RE.search(full_text)
    if m:
        dates = re.findall(r"\d{2}/\d{2}/\d{4}", m.group(0))
        if len(dates) == 2:
            return f"{dates[0]} al {dates[1]}"
    return None


def _parse_date(s: str, year: int) -> str:
    day, mon = s.split("/")
    mm = MESES.get(mon.lower(), "00")
    return f"{year}-{mm}-{day.zfill(2)}"


def _categorize(desc: str) -> str:
    du = desc.upper()
    for cat, kws in CATS_LIBRETON.items():
        if any(k in du for k in kws):
            return cat
    return "OTROS"


def _clean(desc: str) -> str:
    desc = re.sub(r"\bReferencia\b.*", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\b\d{7,}\b", "", desc)
    desc = re.sub(r"\bCUENTA:\s*\S+", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\s*/\s*", " ", desc)
    desc = re.sub(r"\s{2,}", " ", desc)
    return desc.strip().upper()[:80]


def _should_skip(line: str) -> bool:
    if TXN_RE.match(line):
        return False
    lu = line.upper()
    return any(k.upper() in lu for k in SKIP_KW)


def _parse_text(full_text: str, year: int, periodo: str | None) -> list[dict]:
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    txn_positions = []
    for i, line in enumerate(lines):
        if TXN_RE.match(line) and not _should_skip(line):
            txn_positions.append(i)

    if not txn_positions:
        return []

    movimientos = []
    for idx, pos in enumerate(txn_positions):
        next_pos = txn_positions[idx + 1] if idx + 1 < len(txn_positions) else len(lines)

        m = TXN_RE.match(lines[pos])
        fecha_oper  = _parse_date(m.group(1), year)
        fecha_cargo = _parse_date(m.group(2), year)
        desc_main   = m.group(3).strip()
        monto       = float(m.group(4).replace(",", ""))

        cont_extra = ""
        for bline in lines[pos + 1 : next_pos]:
            if _should_skip(bline) or TXN_RE.match(bline):
                break
            cleaned = re.sub(r"\s*Referencia\b.*", "", bline, flags=re.IGNORECASE).strip()
            if cleaned and re.match(r"^[A-Za-z]", cleaned):
                cont_extra = cleaned
            break

        full_desc = (desc_main + " " + cont_extra).strip() if cont_extra else desc_main
        du = full_desc.upper()
        tipo = "INGRESO" if any(k in du for k in ABONO_KW) else "GASTO"
        categoria = _categorize(full_desc)
        desc = _clean(full_desc)

        movimientos.append({
            "fecha":        fecha_oper,
            "fecha_cargo":  fecha_cargo,
            "descripcion":  desc or "SIN DESCRIPCION",
            "monto":        monto,
            "categoria":    categoria,
            "subcategoria": "",
            "tipo":         tipo,
            "periodo":      periodo,
        })

    return movimientos


def parse(pdf_path: Path) -> list[dict]:
    movimientos = []
    try:
        with open_pdf(pdf_path, PDF_PASSWORD, PDF_PASSWORD_BBVA) as pdf:
            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            year    = _extract_year(full_text)
            periodo = _extract_periodo(full_text)
            movimientos = _parse_text(full_text, year, periodo)
    except Exception as e:
        print(f"  [ERROR BBVA_LIB] {e}")
    return movimientos
