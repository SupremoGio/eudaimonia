"""
BBVA Débito — Estado de cuenta de cheques/débito.
"""
import re
from pathlib import Path

from ..config import MESES, PDF_PASSWORD, PDF_PASSWORD_BBVA
from ._base import extract_periodo, open_pdf

DATE_LINE_RE = re.compile(
    r"^(\d{2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\s+(\d{4})"
    r"(?:\s+(.+?))?"
    r"\s+(\$-?[\d,]+)"
    r"\s+(\$-?[\d,]+)"
    r"\s*$",
    re.IGNORECASE,
)

DATE_ONLY_RE = re.compile(
    r"^(\d{2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\s+(\d{4})"
    r"(?:\s+(.*))?$",
    re.IGNORECASE,
)

CATS_DEBIT = {
    "NOMINA":           ["PAGO DE NOMINA", "NOMINA", "FIBRA HOTELERA"],
    "INVERSION":        ["FONDO", "CETES", "GBM", "BITSO"],
    "PAGO_TDC":         ["PAGO TARJETA DE CREDITO", "PAGO TARJETA DE TERCEROS"],
    "SPEI_ENVIADO":     ["SPEI ENVIADO"],
    "SPEI_RECIBIDO":    ["SPEI RECIBIDO"],
    "RETIRO":           ["RETIRO SIN TARJETA", "RETIRO"],
    "DEPOSITO":         ["DEPOSITO EFECTIVO"],
    "FIDEICOMISO":      ["FIDEICOMISO", "SITH"],
    "TRANSFERENCIA":    ["PAGO CUENTA DE TERCERO", "BNET"],
}

SKIP_KW = [
    "FECHA", "DESCRIPCI", "MONTO SALDO", "SALDO TOTAL",
    "DETALLES DE MOVIMIENTOS", "PERIODO:", "ALBERTO SANCHEZ",
    "MONTO DISPONIBLE", "CUENTA:", "EN CUMPLIMIENTO",
    "BBVA M", "CASO DE HABER", "GRUPO FINANCIERO",
]


def _should_skip(line: str) -> bool:
    if DATE_ONLY_RE.match(line):
        return False
    lu = line.upper()
    return any(k.upper() in lu for k in SKIP_KW)


def _parse_monto(raw: str) -> float:
    sign = -1.0 if "-" in raw else 1.0
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return 0.0
    if len(digits) <= 2:
        return sign * float(f"0.{digits.zfill(2)}")
    return sign * float(f"{digits[:-2]}.{digits[-2:]}")


def _categorize(desc: str) -> str:
    du = desc.upper()
    for cat, kws in CATS_DEBIT.items():
        if any(k in du for k in kws):
            return cat
    return "OTROS"


def _clean(desc: str) -> str:
    desc = re.sub(r"\b\d{7,}\b", "", desc)
    desc = re.sub(r"\b[A-Z]{2,5}\d{6,}\b", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\bCUENTA:\s*", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\s*/\s*", " ", desc)
    desc = re.sub(r"\s{2,}", " ", desc)
    return desc.strip().upper()[:80]


def _find_amount_in_block(block: list[str]) -> tuple[float | None, int | None]:
    dollar_idx = [i for i, l in enumerate(block) if l.strip() == "$"]
    if len(dollar_idx) >= 2:
        first_d = dollar_idx[0]
        if first_d >= 1:
            main = block[first_d - 1].strip()
            if re.match(r"^-?[\d,]+$", main):
                cents = "00"
                region_start = first_d - 1
                if first_d >= 2 and re.match(r"^\d{2}$", block[first_d - 2].strip()):
                    cents = block[first_d - 2].strip()
                    region_start = first_d - 2
                amount_str = main.replace(",", "") + cents
                sign = "-" if main.lstrip().startswith("-") else ""
                digits_only = re.sub(r"[^0-9]", "", amount_str)
                if len(digits_only) <= 2:
                    monto_float = float(f"{sign}0.{digits_only.zfill(2)}")
                else:
                    monto_float = float(f"{sign}{digits_only[:-2]}.{digits_only[-2:]}")
                return monto_float, region_start

    for i, line in enumerate(block):
        found = re.findall(r"\$\s*(-?[\d,]+)", line)
        if len(found) >= 2:
            return _parse_monto(found[0]), i

    return None, None


def _parse_text(full_text: str, periodo: str | None) -> list[dict]:
    lines = [l.strip() for l in full_text.split("\n")
             if l.strip() and not _should_skip(l.strip())]

    date_positions = []
    for i, line in enumerate(lines):
        if DATE_ONLY_RE.match(line):
            date_positions.append(i)

    if not date_positions:
        return []

    date_pos_set = set(date_positions)

    if periodo is None:
        fechas = []
        for pos in date_positions:
            m = DATE_ONLY_RE.match(lines[pos])
            d, mes, y = m.group(1), m.group(2).lower(), m.group(3)
            fechas.append(f"{y}-{MESES.get(mes, '00')}-{d.zfill(2)}")
        if fechas:
            periodo = f"{min(fechas)} al {max(fechas)}"

    movimientos = []
    for idx, pos in enumerate(date_positions):
        next_pos = date_positions[idx + 1] if idx + 1 < len(date_positions) else len(lines)
        m = DATE_ONLY_RE.match(lines[pos])
        d, mes, y = m.group(1), m.group(2).lower(), m.group(3)
        fecha = f"{y}-{MESES.get(mes, '00')}-{d.zfill(2)}"

        dm = DATE_LINE_RE.match(lines[pos])
        if dm:
            monto = _parse_monto(dm.group(5))
            inline_desc = (dm.group(4) or "").strip()
        else:
            block = lines[pos:next_pos]
            monto, region_start = _find_amount_in_block(block)
            if monto is None:
                continue
            inline_desc = (m.group(4) or "").strip()

        desc_parts = []
        if pos > 0 and (pos - 1) not in date_pos_set:
            desc_parts.append(lines[pos - 1])

        if inline_desc:
            desc_parts.append(inline_desc)

        is_last = (idx + 1 >= len(date_positions))
        if dm:
            post_end = next_pos if is_last else (next_pos - 1 if next_pos > pos + 1 else pos + 1)
            for bline in lines[pos + 1 : post_end]:
                if not DATE_ONLY_RE.match(bline):
                    desc_parts.append(bline)
        else:
            for bi, bline in enumerate(lines[pos + 1 : next_pos], 1):
                if bi >= region_start:
                    break
                if not DATE_ONLY_RE.match(bline):
                    desc_parts.append(bline)

        desc_raw = " ".join(p for p in desc_parts if p)
        categoria = _categorize(desc_raw)
        desc = _clean(desc_raw)
        tipo = "INGRESO" if monto >= 0 else "GASTO"

        movimientos.append({
            "fecha":        fecha,
            "fecha_cargo":  fecha,
            "descripcion":  desc or "SIN DESCRIPCION",
            "monto":        abs(monto),
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
            inicio, fin = extract_periodo(full_text)
            periodo = f"{inicio} al {fin}" if inicio and fin else None
            movimientos = _parse_text(full_text, periodo)
    except Exception as e:
        print(f"  [ERROR BBVA_DEB] {e}")
    return movimientos
