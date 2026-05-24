"""
Parser for BBVA legacy CSV exports (multi-statement, multi-card format).
"""
import re
from pathlib import Path

import pandas as pd

from ..config import get_categoria_subcategoria

PAYMENT_KW = [
    "BMOVIL", "PAGO TDC", "SPEI RECIBIDO", "ABONO RECIBIDO",
    "PAGO TARJETA", "ABONO CUOTA", "FELICIDADES ABONO",
]

_S1_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{2})\s{2,}(\d{2}/\d{2}/\d{2})\s{2,}(.+?)\s+\$\s*([\d,]+\.\d{2})(-?)\s*$"
)
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2}$")


def _norm(s: str) -> str:
    return str(s).replace("\n", " ").strip().upper()


def _parse_fecha(s: str) -> str | None:
    m = re.match(r"(\d{2})/(\d{2})/(\d{2,4})", str(s).strip())
    if m:
        d, mo, y = m.groups()
        return f"20{y}-{mo}-{d}" if len(y) == 2 else f"{y}-{mo}-{d}"
    return None


def _clean_desc(s: str) -> str:
    s = re.sub(r"^\d{1,2}\s+DE\s+\d{1,2}\s+", "", str(s), flags=re.IGNORECASE)
    s = re.sub(r"MXP\s+\$[\d,.]+\s+TIPO\s+DE\s+CAMBIO\s+\$[\d,.]+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\*+\d*", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip().upper()


def _to_float(val) -> float | None:
    s = str(val).replace(",", "").replace("$", "").strip()
    negative = s.endswith("-")
    if negative:
        s = s[:-1].strip()
    if not s or s.lower() == "nan":
        return None
    try:
        result = float(s)
        return -result if negative else result
    except ValueError:
        return None


def _make_mov(fecha, fecha_cargo, desc, monto, is_payment):
    if not fecha or monto == 0:
        return None
    desc = _clean_desc(desc)
    if not desc:
        return None
    tipo = "PAGO" if (is_payment or any(k in desc for k in PAYMENT_KW)) else "GASTO"
    cat, subcat = ("PAGO", "") if tipo == "PAGO" else get_categoria_subcategoria(desc)
    return {
        "fecha":        fecha,
        "fecha_cargo":  fecha_cargo or fecha,
        "descripcion":  desc[:80],
        "monto":        monto,
        "categoria":    cat,
        "subcategoria": subcat,
        "tipo":         tipo,
        "periodo":      None,
    }


def _is_msi_summary_row(cells):
    return any(re.fullmatch(r"\d+\s+de\s+\d+", c, re.IGNORECASE) for c in cells if c)


def _extract_col_map(cells):
    joined = " ".join(cells)
    if "AUTORIZACION" not in joined:
        return None
    if "PARCIALIDAD" in joined or "SALDO ACTUAL" in joined or "NOMBRE DEL" in joined:
        return None
    for c in cells:
        if "AUTOR" in c and "APLIC" in c:
            return None

    col_map: dict = {}
    for i, c in enumerate(cells):
        if not c:
            continue
        if "FECHA" in c and "AUTOR" in c and "fecha_auth" not in col_map:
            col_map["fecha_auth"] = i
        elif "FECHA" in c and "APLIC" in c and "AUTOR" not in c:
            col_map["fecha_aplic"] = i
        elif "CONCEPTO" in c and "IMPORTE" not in c and "FECHA" not in c and "concepto" not in col_map:
            col_map["concepto"] = i
        elif "IMPORTE" in c and ("CARGO" in c or "CARGOS" in c) and "ABONO" not in c:
            col_map["cargo"] = i
        elif "IMPORTE" in c and ("ABONO" in c or "ABONOS" in c):
            col_map["abono"] = i

    if "fecha_auth" in col_map and "concepto" in col_map:
        return col_map
    return None


def _try_s1_lines(text, result):
    found = False
    for line in str(text).split("\n"):
        m = _S1_RE.match(line.strip())
        if m:
            fa, fap, desc, monto_str, neg = m.groups()
            mov = _make_mov(_parse_fecha(fa), _parse_fecha(fap), desc,
                            float(monto_str.replace(",", "")), bool(neg))
            if mov:
                result.append(mov)
                found = True
    return found


def _parse_multicolumn_row(row, n_cols, col_map):
    fa  = col_map.get("fecha_auth", 0)
    fap = col_map.get("fecha_aplic")
    dc  = col_map.get("concepto")
    cc  = col_map.get("cargo")
    ac  = col_map.get("abono")

    fecha_auth_raw = str(row.iloc[fa]).strip() if n_cols > fa else ""
    if not re.match(r"^\d{2}/\d{2}/\d{2}", fecha_auth_raw):
        return None

    if fap is not None:
        fecha_aplic_raw = str(row.iloc[fap]).strip() if n_cols > fap else ""
    else:
        fecha_aplic_raw = fecha_auth_raw
        for ci in range(1, min(6, n_cols)):
            v = str(row.iloc[ci]).strip()
            if re.match(r"^\d{2}/\d{2}/\d{2}", v):
                fecha_aplic_raw = v
                break

    if dc is not None:
        desc_raw = str(row.iloc[dc]).replace("\n", " ").strip() if n_cols > dc else ""
    else:
        desc_raw = ""
    if not desc_raw or desc_raw.lower() == "nan":
        return None

    cargo_raw = str(row.iloc[cc]).strip() if cc is not None and n_cols > cc else ""
    abono_raw = str(row.iloc[ac]).strip() if ac is not None and n_cols > ac else ""

    cargo = _to_float(cargo_raw)
    abono = _to_float(abono_raw)

    if cargo is None and abono is None:
        for ci in range(n_cols - 1, (dc or 2), -1):
            v = _to_float(str(row.iloc[ci]))
            if v is not None and v != 0:
                if v > 0:
                    cargo = v
                else:
                    abono = v
                break

    if cargo is not None and cargo > 0:
        return _make_mov(_parse_fecha(fecha_auth_raw), _parse_fecha(fecha_aplic_raw), desc_raw, cargo, False)
    if abono is not None and abono != 0:
        return _make_mov(_parse_fecha(fecha_auth_raw), _parse_fecha(fecha_aplic_raw), desc_raw, abs(abono), True)
    return None


def detect(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            sample = f.read(600).upper()
        return (
            "INFORME DE PUNTOS BBVA" in sample
            or ("MOVIMIENTOS EFECTUADOS" in sample and "AUTORIZACION" in sample)
        )
    except Exception:
        return False


def parse(path: Path) -> list[dict]:
    movimientos: list[dict] = []
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig", header=None, dtype=str, on_bad_lines="skip")
        raw = raw.fillna("")
        n_cols = len(raw.columns)
        in_movimientos = False
        col_map: dict = {}

        for _, row in raw.iterrows():
            cells = [_norm(str(v)) for v in row.values]
            cell0 = cells[0] if cells else ""

            if "MOVIMIENTOS EFECTUADOS" in cell0:
                in_movimientos = True
                col_map = {}
                continue
            if not in_movimientos:
                continue

            noise_kws = ["TOTAL IMPORTES", "IVA :", "IVA:", "INTERES:", "CAPITAL:",
                         "COMISIONES:", "PAGO EXCEDENTE"]
            if any(kw in cell0 for kw in noise_kws):
                _try_s1_lines(cell0, movimientos)
                continue
            if _is_msi_summary_row(cells):
                continue

            new_map = _extract_col_map(cells)
            if new_map is not None:
                col_map = new_map
                continue

            joined = " ".join(cells)
            if "AUTORIZACION" in joined and "APLICACION" in joined:
                col_map = {}
                continue

            if _try_s1_lines(cell0, movimientos):
                continue

            if col_map:
                mov = _parse_multicolumn_row(row, n_cols, col_map)
                if mov:
                    movimientos.append(mov)

    except Exception as e:
        print(f"  [ERROR BBVA LEGACY CSV] {e}")

    seen: set[tuple] = set()
    unique: list[dict] = []
    for m in movimientos:
        key = (m["fecha"], m["descripcion"], m["monto"])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique
