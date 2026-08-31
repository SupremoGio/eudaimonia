"""
BBVA Débito — Estado de cuenta de cheques/débito exportado como Excel
("Mis movimientos" desde la app/web de BBVA: columnas FECHA, DESCRIPCIÓN,
CARGO, ABONO, SALDO). A diferencia del PDF, aquí no hay que reconstruir
texto posicional — las columnas ya vienen limpias — así que reusamos
directamente la categorización de bbva_debit.py (el parser de PDF) en vez
de la de tarjeta de crédito (bbva_csv.py), que etiquetaría los abonos
(nómina, SPEI recibido, depósitos) como tipo "PAGO" y los perdería de
Ingresos.
"""
import re
from pathlib import Path

import pandas as pd

from .bbva_debit import _categorize, _clean

_DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_CUENTA_RE = re.compile(r"CUENTA:?\s*\d{8,}", re.IGNORECASE)


def _norm_col(c: str) -> str:
    c = str(c).strip().upper()
    for src, dst in [("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N")]:
        c = c.replace(src, dst)
    return re.sub(r"[^A-Z0-9]", "", c)


def _to_float(val) -> float | None:
    s = str(val).replace(",", "").replace("$", "").strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_header(raw: pd.DataFrame) -> int | None:
    for i, row in raw.iterrows():
        cells = [_norm_col(v) for v in row.values if str(v).strip()]
        if "FECHA" in cells and any("CARGO" in c for c in cells) and any("SALDO" in c for c in cells):
            return i
    return None


def _parse_df(raw: pd.DataFrame) -> list[dict]:
    raw = raw.fillna("").astype(str)

    header_idx = _find_header(raw)
    if header_idx is None:
        return []

    col_names = [_norm_col(c) for c in raw.iloc[header_idx].values]
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = col_names
    df = df.reset_index(drop=True)

    fecha_col = next((c for c in df.columns if c.startswith("FECHA")), None)
    desc_col  = next((c for c in df.columns if c.startswith("DESCRIP")), None)
    cargo_col = next((c for c in df.columns if "CARGO" in c), None)
    abono_col = next((c for c in df.columns if "ABONO" in c), None)

    if not fecha_col or not desc_col or not (cargo_col or abono_col):
        return []

    movimientos = []
    for _, row in df.iterrows():
        fecha_raw = str(row.get(fecha_col, "")).strip()
        desc_raw  = str(row.get(desc_col, "")).strip()
        cargo_raw = str(row.get(cargo_col, "")).strip() if cargo_col else ""
        abono_raw = str(row.get(abono_col, "")).strip() if abono_col else ""

        m = _DATE_RE.match(fecha_raw)
        if not m or not desc_raw or desc_raw.lower() == "nan":
            continue

        d, mo, y = m.groups()
        fecha = f"{y}-{mo}-{d}"

        cargo = _to_float(cargo_raw) if cargo_raw not in ("", "nan") else None
        abono = _to_float(abono_raw) if abono_raw not in ("", "nan") else None

        if abono is not None:
            monto, tipo = abs(abono), "INGRESO"
        elif cargo is not None:
            monto, tipo = abs(cargo), "GASTO"
        else:
            continue

        desc_flat = re.sub(r"\s*/\s*", " ", desc_raw)
        categoria = _categorize(desc_flat)
        desc = _clean(desc_flat)

        movimientos.append({
            "fecha":        fecha,
            "fecha_cargo":  fecha,
            "descripcion":  desc or "SIN DESCRIPCION",
            "monto":        monto,
            "categoria":    categoria,
            "subcategoria": "",
            "tipo":         tipo,
            "periodo":      None,
        })

    return movimientos


def detect_excel(path: Path) -> bool:
    """
    Distingue el Excel de una cuenta de débito/cheques del de una tarjeta
    de crédito (bbva_csv.py) buscando la línea "Cuenta: <numero>" que BBVA
    imprime solo en estados de cuenta de cheques — una tarjeta se
    identifica con "Tarjeta"/dígitos enmascarados, nunca con "Cuenta:".
    Se exige además que existan columnas FECHA/CARGO/SALDO para confirmar
    que es el formato tabular esperado.
    """
    try:
        df = pd.read_excel(path, header=None, nrows=8, dtype=str)
        header_sample = " ".join(
            str(v) for v in df.fillna("").values.flatten() if str(v).strip()
        ).upper()
        if not _CUENTA_RE.search(header_sample):
            return False

        full = pd.read_excel(path, header=None, nrows=15, dtype=str)
        return _find_header(full.fillna("").astype(str)) is not None
    except Exception:
        return False


def parse_excel(path: Path) -> list[dict]:
    try:
        raw = pd.read_excel(path, header=None, dtype=str)
        return _parse_df(raw.fillna(""))
    except Exception as e:
        print(f"  [ERROR BBVA DEB EXCEL] {e}")
        return []
