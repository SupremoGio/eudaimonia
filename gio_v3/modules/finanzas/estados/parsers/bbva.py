import re
from pathlib import Path
from ..config import PDF_PASSWORD, PDF_PASSWORD_BBVA, get_categoria_subcategoria
from ._base import (parse_text_statement, extract_periodo, open_pdf, clean_desc,
                    msi_group_id, _MSI_INSTALLMENT_RE)

PAYMENT_KW = ["BMOVIL", "PAGO TDC", "SPEI RECIBIDO", "ABONO RECIBIDO", "PAGO TARJETA"]

# Secciones que listan movimientos pero NO son movimientos del periodo: la de
# «CARGOS NO RECONOCIDOS» es el estatus de una aclaración (Sheraton $8,910,
# «Concluida, improcedente») y sale en varios cortes seguidos; leída como
# movimiento metía un abono falso de $8,910 en cada uno (ago-oct 2025).
_SECCIONES_INFO = re.compile(
    r"^CARGOS NO RECONOCIDOS.*?(?=^NOTAS ACLARATORIAS|^ATENCI[ÓO]N DE QUEJAS|^DESGLOSE DE MOVIMIENTOS|\Z)",
    re.DOTALL | re.MULTILINE)


def _sin_secciones_informativas(texto: str) -> str:
    return _SECCIONES_INFO.sub("", texto)


def parse(pdf_path: Path) -> list[dict]:
    movimientos = []
    try:
        with open_pdf(pdf_path, PDF_PASSWORD, PDF_PASSWORD_BBVA) as pdf:
            full_text = _sin_secciones_informativas("\n".join(p.extract_text() or "" for p in pdf.pages))
            inicio, fin = extract_periodo(full_text)
            periodo = f"{inicio} al {fin}" if inicio and fin else None
            movimientos = parse_text_statement(full_text, PAYMENT_KW, periodo)
            if not movimientos:
                movimientos = parse_tarjeta_oro(full_text)
    except Exception as e:
        print(f"  [ERROR BBVA] {e}")
    return movimientos


# ── Formato viejo «Tarjeta Oro BBVA» (cortes 2022-2024) ──────────────────────
# «23/04/24 23/04/24 SORIANA313 AMERICASGDL TSO 991022PB6 ******8256 $ 329.23»
# Fechas dd/mm/aa, RFC y referencia enmascarada en la línea, abonos con «-» al
# final del importe, una sección «Movimientos Efectuados Tarjeta Titular …»
# por tarjeta (titular y digitales/adicionales) con su «TOTAL IMPORTES».
# El parser de arriba no reconoce nada de esto (espera «Periodo: dd-mmm-aa»).
_ORO_LINE_RE = re.compile(r"^(\d{2}/\d{2}/\d{2})\s+(\d{2}/\d{2}/\d{2})\s+(.+?)\s+\$\s*([\d,]+\.\d{2})(-?)\s*$")
_ORO_REF_RE = re.compile(r"\s*\*{4,}\d+\s*$")
_ORO_RFC_RE = re.compile(r"\s+[A-ZÑ&]{3,4}\s?\d{6}[A-Z0-9]{3}\s*$")
_ORO_PERIODO_RE = re.compile(r"Del\s+(\d{2}/\d{2}/\d{2})\s+al\s+(\d{2}/\d{2}/\d{2})", re.IGNORECASE)


def _oro_fecha(s: str) -> str:
    d, m, a = s.split('/')
    return f"20{a}-{m}-{d}"


def oro_periodo(full_text: str) -> str | None:
    m = _ORO_PERIODO_RE.search(re.sub(r"\s+", " ", full_text))
    return f"{_oro_fecha(m.group(1))} al {_oro_fecha(m.group(2))}" if m else None


def parse_tarjeta_oro(full_text: str) -> list[dict]:
    periodo = oro_periodo(full_text)
    movimientos = []
    en_movs = False
    for linea in full_text.split("\n"):
        linea = linea.strip()
        lu = linea.upper()
        if lu.startswith("MOVIMIENTOS EFECTUADOS"):
            en_movs = True
            continue
        if lu.startswith("TOTAL IMPORTES") or lu.startswith("RESUMEN INFORMATIVO"):
            en_movs = False
            continue
        if not en_movs:
            continue
        m = _ORO_LINE_RE.match(linea)
        if not m:
            continue
        concepto = _ORO_RFC_RE.sub("", _ORO_REF_RE.sub("", m.group(3)))
        desc = clean_desc(concepto)
        # «01 DE 03 ANUALIDAD»: la anualidad diferida sale en la lista pero el
        # banco la cuenta en «Comisiones», no en TOTAL IMPORTES (corte dic 2022;
        # en el siguiente se bonificó con «FELICIDADES ABONO CUOTA ANUAL»).
        if _MSI_INSTALLMENT_RE.match(concepto) and desc.strip().upper() == "ANUALIDAD":
            continue
        monto = float(m.group(4).replace(",", ""))
        abono = m.group(5) == "-"
        msi_m = _MSI_INSTALLMENT_RE.match(concepto)
        if abono:
            monto, tipo, (cat, subcat) = -monto, "PAGO", ("PAGO", "")
        else:
            tipo, (cat, subcat) = "GASTO", get_categoria_subcategoria(desc)
        movimientos.append({
            "fecha": _oro_fecha(m.group(1)),
            "fecha_cargo": _oro_fecha(m.group(2)),
            "descripcion": desc[:80],
            "monto": monto,
            "categoria": cat,
            "subcategoria": subcat,
            "tipo": tipo,
            "periodo": periodo,
            "parcialidad_num": int(msi_m.group(1)) if msi_m else None,
            "parcialidad_total": int(msi_m.group(2)) if msi_m else None,
            "compra_msi_id": msi_group_id(desc, monto) if msi_m else None,
        })
    return movimientos


def oro_totales(full_text: str) -> tuple[float, float]:
    """Suma de «TOTAL IMPORTES: $ cargos [$ abonos-]» de todas las tarjetas."""
    c = a = 0.0
    for m in re.finditer(r"TOTAL IMPORTES:\s*\$\s*([\d,]+\.\d{2})(?:\s*\$\s*([\d,]+\.\d{2})-)?", full_text):
        c += float(m.group(1).replace(",", ""))
        a += float(m.group(2).replace(",", "")) if m.group(2) else 0.0
    return round(c, 2), round(a, 2)
