"""
Parser for BBVA web CSV/Excel export.
"""
import re
from pathlib import Path

import pandas as pd

from ..config import get_categoria_subcategoria

PAYMENT_KW = ["BMOVIL", "PAGO TDC", "SPEI RECIBIDO", "ABONO RECIBIDO", "PAGO TARJETA"]


def _norm_col(c: str) -> str:
    c = str(c).strip().upper()
    for src, dst in [("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ñ","N")]:
        c = c.replace(src, dst)
    return re.sub(r"[^A-Z0-9]", "", c)


def _clean_desc(s: str) -> str:
    s = re.sub(r"\*+", " ", str(s))
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip().upper()


def _to_float(val) -> float | None:
    s = str(val).replace(",", "").replace("$", "").strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_fecha(s: str) -> str | None:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", str(s).strip())
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    return None


def _parse_df(raw: pd.DataFrame) -> list[dict]:
    raw = raw.fillna("").astype(str)

    header_idx = None
    for i, row in raw.iterrows():
        cells = [_norm_col(v) for v in row.values if str(v).strip()]
        if "FECHA" in cells and any("CARGO" in c for c in cells):
            header_idx = i
            break

    if header_idx is None:
        print("  [BBVA CSV] No se encontró fila de encabezados (FECHA / CARGO).")
        return []

    col_names = [_norm_col(c) for c in raw.iloc[header_idx].values]
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = col_names
    df = df.reset_index(drop=True)

    fecha_col = next((c for c in df.columns if c.startswith("FECHA")), None)
    desc_col  = next((c for c in df.columns if c.startswith("DESCRIP")), None)
    cargo_col = next((c for c in df.columns if "CARGO" in c), None)
    abono_col = next((c for c in df.columns if "ABONO" in c), None)

    if not fecha_col or not desc_col or not cargo_col:
        print(f"  [BBVA CSV] Columnas no encontradas: {col_names}")
        return []

    movimientos = []
    for _, row in df.iterrows():
        fecha_raw = str(row.get(fecha_col, "")).strip()
        desc_raw  = str(row.get(desc_col, "")).strip()
        cargo_raw = str(row.get(cargo_col, "")).strip()
        abono_raw = str(row.get(abono_col, "")).strip() if abono_col else ""

        if not re.match(r"\d{2}/\d{2}/\d{4}", fecha_raw):
            continue
        if not desc_raw or desc_raw.lower() == "nan":
            continue

        fecha = _parse_fecha(fecha_raw)
        if not fecha:
            continue

        desc  = _clean_desc(desc_raw)
        cargo = _to_float(cargo_raw) if cargo_raw not in ("", "nan") else None
        abono = _to_float(abono_raw) if abono_raw not in ("", "nan") else None

        if cargo is not None and cargo > 0:
            monto = cargo
            tipo  = "PAGO" if any(k in desc for k in PAYMENT_KW) else "GASTO"
        elif abono is not None:
            monto = abs(abono)
            tipo  = "PAGO"
        else:
            continue

        if tipo == "GASTO":
            cat, subcat = get_categoria_subcategoria(desc)
        else:
            cat, subcat = "PAGO", ""

        movimientos.append({
            "fecha":        fecha,
            "fecha_cargo":  fecha,
            "descripcion":  desc[:80],
            "monto":        monto,
            "categoria":    cat,
            "subcategoria": subcat,
            "tipo":         tipo,
            "periodo":      None,
        })

    return movimientos


def detect(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            sample = f.read(600).upper()
        return (
            "DETALLE DE MOVIMIENTOS" in sample
            or ("NUMERO DE TARJETA" in sample and "FECHA" in sample)
        )
    except Exception:
        return False


def parse(path: Path) -> list[dict]:
    try:
        raw = pd.read_csv(
            path, encoding="utf-8-sig",
            header=None, dtype=str, on_bad_lines="skip",
        )
        return _parse_df(raw)
    except Exception as e:
        print(f"  [ERROR BBVA CSV] {e}")
        return []


def detect_excel(path: Path) -> bool:
    try:
        df = pd.read_excel(path, header=None, nrows=15, dtype=str)
        sample = " ".join(str(v) for v in df.fillna("").values.flatten()).upper()
        return (
            "DETALLE DE MOVIMIENTOS" in sample
            or ("BBVA" in sample and "CARGO" in sample and "FECHA" in sample)
        )
    except Exception:
        return False


def parse_excel(path: Path) -> list[dict]:
    try:
        raw = pd.read_excel(path, header=None, dtype=str)
        return _parse_df(raw.fillna(""))
    except Exception as e:
        print(f"  [ERROR BBVA EXCEL] {e}")
        return []
