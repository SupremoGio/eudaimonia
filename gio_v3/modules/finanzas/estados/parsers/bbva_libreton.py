"""
BBVA Libretón Básico Cuenta Digital — Estado de cuenta débito.
"""
import re
from itertools import combinations
from pathlib import Path

from ..config import MESES, PDF_PASSWORD, PDF_PASSWORD_BBVA
from ._base import open_pdf

ABONO_KW = [
    "SPEI RECIBIDO", "PAGO DE NOMINA", "DEPOSITO EFECTIVO", "DEPOSITO DE TERCERO",
    "SU PAGO", "SITH", "ABONO", "DEVUELTO",
]

# "PAGO CUENTA DE TERCERO" es la única descripción que de verdad puede ser
# cargo O abono según el caso — BBVA no lo distingue en el texto (a
# diferencia de "SPEI ENVIADO"/"SPEI RECIBIDO", que sí son inequívocos por
# nombre). Adivinar por palabra clave le atinaba la mayoría de las veces
# pero fallaba en silencio en el resto — ver commit "Verificar cargo/abono
# de PAGO CUENTA DE TERCERO contra el saldo del PDF". Para estas líneas se
# verifica el signo contra el saldo impreso en vez de adivinar.
AMBIGUOUS_KW = ["PAGO CUENTA DE TERCERO"]

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
    r"(?:\s+([\d,]+\.\d{2})(?:\s+[\d,]+\.\d{2})?)?\s*$",
    re.IGNORECASE,
)

PERIODO_RE = re.compile(
    r"periodo\s+del\s+\d{2}/(\d{2})/(\d{4})\s+al\s+\d{2}/(\d{2})/(\d{4})",
    re.IGNORECASE,
)
CORTE_RE = re.compile(r"fecha\s+de\s+corte\s+\d{2}/\d{2}/(\d{4})", re.IGNORECASE)
SALDO_ANTERIOR_RE = re.compile(r"saldo\s+anterior\s+([\d,]+\.\d{2})", re.IGNORECASE)
SALDO_FINAL_RE = re.compile(r"saldo\s+final\s+([\d,]+\.\d{2})", re.IGNORECASE)
TOTAL_CARGOS_RE = re.compile(
    r"total\s+importe\s+cargos\s+([\d,]+\.\d{2})\s+total\s+movimientos\s+cargos\s+(\d+)",
    re.IGNORECASE,
)
TOTAL_ABONOS_RE = re.compile(
    r"total\s+importe\s+abonos\s+([\d,]+\.\d{2})\s+total\s+movimientos\s+abonos\s+(\d+)",
    re.IGNORECASE,
)


def _extract_year_bounds(full_text: str) -> tuple[int, int, int, int]:
    """Devuelve (mes_inicio, anio_inicio, mes_fin, anio_fin) del periodo.

    El periodo de un Libretón siempre corta a mediados de mes (ej. "DEL
    07/12/2024 AL 06/01/2025"), así que en diciembre-enero el año de inicio
    y el de fin son distintos. Aplicar un solo año a todas las fechas del
    estado de cuenta (como hacía la versión anterior) desplazaba un año
    completo cada movimiento de diciembre — se colaban en el "2025-12" del
    año siguiente en vez de "2024-12", y por lo tanto desaparecían al
    filtrar por 2024 en la app.
    """
    m = PERIODO_RE.search(full_text)
    if m:
        mes_ini, anio_ini, mes_fin, anio_fin = m.groups()
        return int(mes_ini), int(anio_ini), int(mes_fin), int(anio_fin)
    m = CORTE_RE.search(full_text)
    if m:
        anio = int(m.group(1))
        return 1, anio, 12, anio
    return 1, 2025, 12, 2025


def _year_for_month(mon_abbr: str, bounds: tuple[int, int, int, int]) -> int:
    mes_ini, anio_ini, mes_fin, anio_fin = bounds
    if anio_ini == anio_fin:
        return anio_ini
    mes = int(MESES.get(mon_abbr.lower(), "0") or "0")
    if mes == mes_ini:
        return anio_ini
    if mes == mes_fin:
        return anio_fin
    # Mes fuera de lo esperado (no debería pasar en un periodo de ~1 mes):
    # nos quedamos con el año cuyo mes de borde está más cerca.
    return anio_fin if mes <= mes_fin else anio_ini


def _extract_periodo(full_text: str) -> str | None:
    m = PERIODO_RE.search(full_text)
    if m:
        dates = re.findall(r"\d{2}/\d{2}/\d{4}", m.group(0))
        if len(dates) == 2:
            return f"{dates[0]} al {dates[1]}"
    return None


def _parse_date(s: str, bounds: tuple[int, int, int, int]) -> str:
    day, mon = s.split("/")
    mm = MESES.get(mon.lower(), "00")
    year = _year_for_month(mon, bounds)
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


_MAX_PENDIENTES_COMBINATORIA = 14  # 2**14 = 16384 combinaciones, de sobra para una racha real


def _resolve_ambiguous_tipos(movimientos: list[dict], saldos: list[float | None],
                              ambiguos: list[bool], saldo_inicial: float | None) -> None:
    """Verifica contra el saldo impreso el tipo de las líneas ambiguas
    (AMBIGUOUS_KW), en vez de dejarlas en el default GASTO.

    Recorre los movimientos en orden acumulando un saldo esperado. Las
    líneas confiables (no ambiguas) aportan su monto con el signo ya
    determinado por palabra clave. Las líneas ambiguas se acumulan como
    "pendientes" (signo desconocido, sin aportar al saldo esperado)
    hasta la siguiente línea que trae saldo impreso (un "checkpoint").
    Ahí se compara, asumiendo GASTO por default para todas las pendientes,
    el saldo esperado contra el saldo real impreso. Si no cuadra, se
    prueban todos los subconjuntos de pendientes que — de voltearse a
    INGRESO — explican exactamente esa diferencia (cada uno vale 2×monto
    porque pasa de restar a sumar). Si hay una única combinación que
    cuadra, se aplica; si no hay ninguna o hay varias (ambiguo, no se
    puede saber cuál de las combinaciones es la real), no se adivina: se
    deja el default y esas líneas quedan sin verificar — ninguna peor que
    antes de este cambio, solo sin confirmar.

    Muta movimientos[i]["tipo"] in place cuando corrige.
    """
    if saldo_inicial is None:
        return  # no se pudo leer "Saldo Anterior" — no hay con qué verificar

    saldo_esperado = saldo_inicial
    pendientes: list[int] = []  # índices de movimientos ambiguos sin verificar aún

    for i, mov in enumerate(movimientos):
        signo = 1 if mov["tipo"] == "INGRESO" else -1
        if ambiguos[i]:
            pendientes.append(i)
        else:
            saldo_esperado += signo * mov["monto"]

        saldo_real = saldos[i]
        if saldo_real is None:
            continue  # esta línea no trae saldo impreso — no hay checkpoint aquí

        # saldo_esperado asume GASTO (signo -1) para cada pendiente sin resolver
        esperado_con_pendientes = saldo_esperado - sum(movimientos[j]["monto"] for j in pendientes)
        diff = round(saldo_real - esperado_con_pendientes, 2)

        if abs(diff) < 0.01:
            pass  # el default ya cuadra — nada que corregir
        elif pendientes and len(pendientes) <= _MAX_PENDIENTES_COMBINATORIA:
            montos = [movimientos[j]["monto"] for j in pendientes]
            matches = [
                combo
                for r in range(len(pendientes) + 1)
                for combo in combinations(range(len(pendientes)), r)
                if abs(sum(2 * montos[k] for k in combo) - diff) < 0.01
            ]
            if len(matches) == 1:
                for k in matches[0]:
                    movimientos[pendientes[k]]["tipo"] = "INGRESO"
            # 0 o >1 combinaciones cuadran: no se puede atribuir con
            # certeza — se deja tal cual (sin adivinar).

        saldo_esperado = saldo_real  # el saldo impreso es siempre la verdad
        pendientes = []


def _parse_text(full_text: str, bounds: tuple[int, int, int, int], periodo: str | None) -> list[dict]:
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    txn_positions = []
    for i, line in enumerate(lines):
        if TXN_RE.match(line) and not _should_skip(line):
            txn_positions.append(i)

    if not txn_positions:
        return []

    movimientos: list[dict] = []
    saldos: list[float | None] = []
    ambiguos: list[bool] = []

    for idx, pos in enumerate(txn_positions):
        next_pos = txn_positions[idx + 1] if idx + 1 < len(txn_positions) else len(lines)

        m = TXN_RE.match(lines[pos])
        fecha_oper  = _parse_date(m.group(1), bounds)
        fecha_cargo = _parse_date(m.group(2), bounds)
        desc_main   = m.group(3).strip()
        monto       = float(m.group(4).replace(",", ""))
        saldo_op    = float(m.group(5).replace(",", "")) if m.group(5) else None

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
        es_ambiguo = any(k in du for k in AMBIGUOUS_KW) and not any(k in du for k in ABONO_KW)
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
        saldos.append(saldo_op)
        ambiguos.append(es_ambiguo)

    saldo_inicial_m = SALDO_ANTERIOR_RE.search(full_text)
    saldo_inicial = float(saldo_inicial_m.group(1).replace(",", "")) if saldo_inicial_m else None
    _resolve_ambiguous_tipos(movimientos, saldos, ambiguos, saldo_inicial)

    return movimientos


def parse(pdf_path: Path) -> list[dict]:
    movimientos = []
    try:
        with open_pdf(pdf_path, PDF_PASSWORD, PDF_PASSWORD_BBVA) as pdf:
            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            bounds  = _extract_year_bounds(full_text)
            periodo = _extract_periodo(full_text)
            movimientos = _parse_text(full_text, bounds, periodo)
    except Exception as e:
        print(f"  [ERROR BBVA_LIB] {e}")
    return movimientos
