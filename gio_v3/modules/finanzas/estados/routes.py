"""
Flask blueprint for Estados de Cuenta — embedded React SPA + full REST API.
All data lives in Eudaimonia's existing database (Turso-backed → persistent on Railway).
Tables are prefixed with est_ to avoid conflicts.
"""
import calendar
import csv
import io
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint, render_template, render_template_string, request,
    session, jsonify, Response, redirect, url_for,
)
from database import get_db
from utils import clean_str, today_str, safe_float, csv_response
import modules.gamification.engine as engine
from . import prestamos as _prest
from . import expense_lotes as _lotes
from . import correcciones_csv_2026_09_26 as _csv0926

estados_bp = Blueprint(
    'estados',
    __name__,
    template_folder='../../../templates',
)

# Categories that represent debt payments — never counted as real expenses.
# PRESTAMOS incluido: dinero que prestas y te regresan no es un gasto/ingreso
# real, solo un movimiento de efectivo — se excluye de ambos lados (ver
# también _INGRESO_EXCLUIR abajo) para que no infle Balance Neto ni Gastos
# por categoría. Se agrega/quita a mano en "Categoría" al editar el
# movimiento (el selector de Tipo del modal no expone Préstamo/Cobro).
#
# 'FINANZAS' agregado 2026-09: DEPOSITO/FIDEICOMISO/SPEI_RECIBIDO/
# SPEI_ENVIADO/TRANSFERENCIA/RETIRO/PAGO/PAGO_TDC se reclasificaron todos
# a categoria=FINANZAS (finanzas_legacy_bancario_a_finanzas_2026_09). Esta
# lista es una copia independiente de la de budget.py -- sin este cambio,
# los movimientos que antes se excluían aquí por su nombre viejo se
# hubieran empezado a contar de más en Reportes ("Total Gastado"/"Total
# Ingreso" en /api/summary/stats) en cuanto cambiara su categoria, aunque
# budget.py ya estuviera corregido. Bug real confirmado por el usuario.
#
# Corregido 2026-09-22: FINANZAS es una categoría paraguas con subcategorías
# muy distintas entre sí (ver config.py) -- Transferencia y Reembolsable son
# movimiento interno real (mover dinero entre tus propias cuentas, o dinero
# que ya vuelve) y con razón no cuentan como gasto/ingreso. Pero Retiro
# efectivo, Cargos bancarios, Pago servicios y Deudas MSI SÍ son gasto real
# -- el usuario reportó ver 51 movimientos "RETIRO SIN TARJETA" en
# Movimientos que no aparecían en absoluto en "Gastos por categoría" ni en
# ningún reporte, como si ese dinero hubiera desaparecido. Excluir la
# categoría FINANZAS completa escondía ese gasto real junto con las
# transferencias genuinas. Ahora la exclusión de FINANZAS es por
# subcategoría, no por categoría completa -- y esta es la ÚNICA copia de
# esta regla en todo el archivo (antes había 4 copias idénticas
# desincronizándose una de otra cada vez que se corregía solo una).
#
# Corregido otra vez el mismo día: la primera versión de esta lista solo
# tenía el string 'Transferencia' de config.py (el genérico por keyword
# "TRANSFERENCIA"), pero los parsers que de verdad generan la mayoría de
# estas filas (bbva_debit.py, bbva_libreton.py, un SPEI real en el estado
# de cuenta) escriben 'Transferencia enviada'/'Transferencia recibida' --
# strings DISTINTOS que no matcheaban, así que los SPEI reales (ej. "SPEI
# ENVIADO NAFIN"/"BANORTE" del reporte original del usuario) seguían
# contando como gasto real tras el fix anterior, sin que nadie lo pidiera.
# Se agregan todas las variantes que los parsers realmente escriben para
# FINANZAS (Depósito/Fideicomiso incluidos por completitud, aunque casi
# siempre llegan como INGRESO y no pasan por este filtro de GASTO).
#
# Corregido 2026-09-26, a petición del usuario: «Transferencia» y
# «Transferencia enviada» vuelven a contar como gasto. La clasificación de
# esas transferencias no es 100 % fiable (ej. un pago a un tercero que en
# realidad era de Salsa quedaba como FINANZAS/Transferencia y desaparecía de
# todos los reportes), así que es preferible verlas y reclasificarlas. Las
# que sí son movimiento interno tienen su propia categoría (PAGO_TDC,
# INVERSION, PRESTAMOS) y siguen fuera.
_FINANZAS_NO_GASTO_SUBCATS = (
    'Transferencia recibida',
    'Depósito', 'Fideicomiso', 'Reembolsable',
)


# EXPENSE (gasto de trabajo que la empresa reembolsa) tampoco es gasto real:
# el reembolso ya se excluye del ingreso (FINANZAS/Reembolsable), así que
# contar el cargo inflaba «Total gastado». El usuario pidió sacarlo del gasto
# y verlo aparte como referencia (/api/summary/pendientes -> expense_ref),
# igual que budget.py ya lo trataba como informativo.
def _pago_cats_sql(prefix: str = '') -> str:
    """Igual que _PAGO_CATS pero con un prefijo de tabla (ej. 'm.' en un JOIN)."""
    subcats = ",".join(f"'{s}'" for s in _FINANZAS_NO_GASTO_SUBCATS)
    return (f"{prefix}categoria NOT IN ('PAGO_TDC','PAGO','PRESTAMOS','EXPENSE') "
            f"AND NOT ({prefix}categoria='FINANZAS' AND {prefix}subcategoria IN ({subcats}))")


_PAGO_CATS = _pago_cats_sql()
# Use mi_parte when set (shared expense), otherwise full monto. mi_parte se
# captura y guarda como magnitud positiva ("pon aquí solo lo que te
# corresponde a ti", ver update_transaction) sin importar el signo de monto
# (negativo en GASTO, positivo en INGRESO) -- un COALESCE(mi_parte, monto)
# ingenuo sustituye un monto negativo por un mi_parte positivo, invirtiendo
# el signo de esa fila dentro de un SUM() y cancelando gasto real contra el
# resto (usuario lo confirmó en vivo: un solo gasto de $4,048 con mi_parte
# $1,349.33 hizo que "Total gastado" de 3 movimientos cayera a $149.33 en
# vez de ~$2,549). Se normaliza el signo de mi_parte al de monto antes de
# usarlo, para cualquier SUM que combine filas con y sin mi_parte.
_MONTO = "CASE WHEN mi_parte IS NOT NULL THEN (CASE WHEN monto < 0 THEN -ABS(mi_parte) ELSE ABS(mi_parte) END) ELSE monto END"


def _monto_expr(prefix: str = '') -> str:
    """Igual que _MONTO pero con un prefijo de tabla (ej. 'm.' en un JOIN)."""
    return (f"CASE WHEN {prefix}mi_parte IS NOT NULL THEN "
            f"(CASE WHEN {prefix}monto < 0 THEN -ABS({prefix}mi_parte) ELSE ABS({prefix}mi_parte) END) "
            f"ELSE {prefix}monto END")


# INGRESO categories that are NOT real income (transfers, cash mobilization)
_INGRESO_EXCLUIR = ('TRANSFERENCIA', 'PAGO_TDC', 'RETIRO', 'DEPOSITO', 'SPEI_RECIBIDO',
                     'APORTACION_RENTA', 'PRESTAMOS', 'FINANZAS')
# VIVIENDA/Aportación renta (lo que el roomie te deposita de su parte) no es
# ingreso: desde 2026-09-26 la renta cuenta solo tu parte (mi_parte), así que
# contar también su aportación duplicaba su mitad (pedido del usuario al
# corregir el CSV). Sigue visible en Movimientos.
_INGRESO_EXCLUIR_SQL = ("(categoria NOT IN ({}) AND NOT (categoria='VIVIENDA' "
                        "AND COALESCE(subcategoria,'')='Aportación renta'))").format(
    ','.join(f"'{c}'" for c in _INGRESO_EXCLUIR)
)

BANK_META = {
    "BBVA_TDC": {"color": "#004B96", "type": "Tarjeta de crédito", "icon": "credit-card"},
    "BBVA_DEB": {"color": "#004B96", "type": "Cuenta de débito",   "icon": "landmark"},
    "INVEX":    {"color": "#E30D13", "type": "Tarjeta de crédito", "icon": "credit-card"},
    "HSBC":     {"color": "#DB0011", "type": "Tarjeta de crédito", "icon": "credit-card"},
    "MANUAL":   {"color": "#64748b", "type": "Entrada manual",     "icon": "pencil"},
}


# ── Auth helper ───────────────────────────────────────────────────────────────

def _locked():
    return jsonify({'error': 'locked'}), 403

def _ok():
    return session.get('fin_ok')


# ── Filter builder ────────────────────────────────────────────────────────────

def _days_in_month(year_month: str) -> int:
    """Días calendario de un 'YYYY-MM' — el mes actual cuenta solo los días
    transcurridos hasta hoy (igual que un rango 'este mes' sin fecha final)."""
    year, month = (int(p) for p in year_month.split('-'))
    today = datetime.now().date()
    if (year, month) == (today.year, today.month):
        return today.day
    return calendar.monthrange(year, month)[1]


def _months_condition(args) -> tuple[str | None, list]:
    """Filtro por meses sueltos (no necesariamente consecutivos), ej.
    months=2026-01,2026-08 — usado por el selector "Personalizado" del
    front en vez de un rango continuo date_from/date_to."""
    months = [m.strip() for m in (args.get('months') or '').split(',') if m.strip()]
    if not months:
        return None, []
    placeholders = ','.join('?' for _ in months)
    return f"substr(fecha,1,7) IN ({placeholders})", months


def _build_filters(args) -> tuple[list[str], list]:
    conditions, params = [], []
    if args.get('bank'):
        conditions.append("banco = ?")
        params.append(args['bank'])
    if args.get('category'):
        conditions.append("categoria = ?")
        params.append(args['category'])
    if args.get('subcategoria'):
        conditions.append("subcategoria = ?")
        params.append(args['subcategoria'])
    if args.get('tipo'):
        conditions.append("tipo = ?")
        params.append(args['tipo'])
    if args.get('search'):
        conditions.append("UPPER(descripcion) LIKE ?")
        params.append(f"%{args['search'].upper()}%")
    months_cond, months_params = _months_condition(args)
    if months_cond:
        conditions.append(months_cond)
        params.extend(months_params)
    else:
        if args.get('date_from'):
            conditions.append("fecha >= ?")
            params.append(args['date_from'])
        if args.get('date_to'):
            conditions.append("fecha <= ?")
            params.append(args['date_to'])
    return conditions, params


# ── Page ──────────────────────────────────────────────────────────────────────

@estados_bp.route('/')
def index():
    if not _ok():
        return redirect(url_for('finanzas.index'))
    return render_template('finanzas/estados.html')


# ── Transactions ──────────────────────────────────────────────────────────────

_RENTA_VARIANTES = ('Renta + deposito', 'Renta depto 807 + deposito')


def _normalize_subcategoria(categoria: str, subcategoria: str) -> str:
    """EXPENSE es una categoria plana -- a petición explícita del usuario
    nunca lleva subcategoria ("va todo junto en uno solo"), sin importar
    qué venga en la request. Se aplica en cada punto de escritura
    (transacción manual, edición, reglas de keyword) para que no se pueda
    volver a acumular basura ahí.

    También unifica variantes de "Renta" bajo VIVIENDA: el script de
    /admin/apply-migrations (modules/finanzas/routes.py) generó "Renta +
    deposito" y "Renta depto 807 + deposito" para capturar que un pago
    puntual incluía el depósito inicial -- pero eso ya vive en mi_parte
    (6000 normal vs 7000 con depósito), no hace falta una subcategoria
    aparte. El usuario pidió explícitamente unificarlo, igual que
    Aportación renta/Renta del lado ingreso: "tambien renta depto 807".

    Y previene una combinación inválida: el modal "Editar movimiento" del
    SPA (estados.js, bundle sin fuente en este repo -- no se puede arreglar
    el <select> ahí) tiene un bug real reportado con capturas: al cambiar
    "Categoría" el <select> de "Subcategoría" no se resetea y se queda
    mostrando el valor de la categoría anterior (ej. cambiar de FINANZAS a
    VIVIENDA deja seleccionado "Transferencia enviada", que no es una
    subcategoría válida de VIVIENDA). Si esa combinación llega a guardarse
    tal cual, se limpia aquí a subcategoria='' en vez de persistir una
    subcategoría que no le corresponde a la categoría nueva -- más honesto
    que dejar basura mezclada, y evita que quede huérfana de cualquier
    filtro/exclusión que dependa de la combinación categoria+subcategoria."""
    if categoria == 'EXPENSE':
        return ''
    if categoria == 'VIVIENDA' and subcategoria in _RENTA_VARIANTES:
        return 'Renta'
    if subcategoria:
        from .config import SUBCATEGORIAS
        validas = SUBCATEGORIAS.get(categoria)
        if validas and subcategoria not in validas:
            return ''
    return subcategoria


def _corregir_fusion_gio(db) -> int:
    """El usuario reportó DOS VECES que "...FUSION GIO" (SPEI enviado a
    NU MEXICO para un congreso de salsa) seguía cayendo en APORTACION_
    RENTA/VIVIENDA: "esto por que sigue ahí ya habiamos dicho que es
    Salsa subcategoria congreso". Causa: una regla de keyword más amplia
    (custom_kw en est_keywords, ej. algo con "NU MEXICO") tiene prioridad
    sobre el keyword genérico "SALSA" de config.py (custom_kw se revisa
    primero en get_categoria_subcategoria) y la intercepta antes de que
    el texto "SALSA"/"FUSION GIO" pueda clasificarla bien. Se corrige por
    texto directamente, después de aplicar cualquier regla de keyword,
    para que ninguna la vuelva a pisar."""
    cur = db.execute("""
        UPDATE est_movimientos SET categoria='SALSA', subcategoria='Congreso'
        WHERE UPPER(descripcion) LIKE '%FUSION GIO%'
          AND (categoria != 'SALSA' OR subcategoria != 'Congreso')
    """)
    return cur.rowcount


_FAR_GUAD_UMBRAL = 200.0


def _corregir_far_guad(db) -> int:
    """FAR GUAD (Farmacias Guadalajara) vende tanto conveniencia/snacks
    como medicamentos bajo el mismo comercio, así que texto de descripción
    solo no alcanza para distinguirlos -- el usuario pidió blindar por
    monto: "todo lo que venga de FAR GUAD y es menor a 200 pesos es
    alimentacion subcategoria conveniencia todo lo que sea mayor a eso
    seguramente son medicamentos e iria en salud subcategoria farmacia".
    No toca categoria='EXPENSE' (reembolsable) -- eso es una decisión
    explícita del usuario en cada compra, no algo que se deba adivinar
    por monto."""
    cur1 = db.execute("""
        UPDATE est_movimientos SET categoria='SUPER', subcategoria='Conveniencia'
        WHERE UPPER(descripcion) LIKE '%FAR GUAD%'
          AND ABS(monto) < ?
          AND categoria != 'EXPENSE'
          AND (categoria != 'SUPER' OR subcategoria != 'Conveniencia')
    """, (_FAR_GUAD_UMBRAL,))
    cur2 = db.execute("""
        UPDATE est_movimientos SET categoria='SALUD', subcategoria='Farmacia'
        WHERE UPPER(descripcion) LIKE '%FAR GUAD%'
          AND ABS(monto) >= ?
          AND categoria != 'EXPENSE'
          AND (categoria != 'SALUD' OR subcategoria != 'Farmacia')
    """, (_FAR_GUAD_UMBRAL,))
    return cur1.rowcount + cur2.rowcount


_LEGACY_CATEGORIA_MAP = {
    'CASA/HOGAR':    ('VIVIENDA', 'Renta'),
    'VIVERES/SUPER': ('SUPER', 'Súper'),
    'COMIDA/REST':   ('COMIDA_FUERA', 'Restaurante'),
    'VIAJES/VUELOS': ('VIAJES', 'Otros'),
    # 'REGALO' (categoria plana legacy) es enteramente el pago a
    # CRISTAL VILLAHERMOSA a 12 meses (un anillo) -- el usuario confirmó
    # "ya tenemos familia regalo manda eso a familia y regalos a la
    # subcategoria Anillo Cornelius". Mismo patrón que los demás: una
    # regla vieja en est_keywords lo seguía reviviendo.
    'REGALO':        ('FAMILIA_REGALOS', 'Anillo Cornelius'),
}


def _corregir_categorias_legacy(db) -> int:
    """CASA/HOGAR, VIVERES/SUPER, COMIDA/REST y VIAJES/VUELOS fueron
    retiradas del selector (Fc en estados.js) y de config.py hace tiempo,
    con su propia migración de barrido -- pero el usuario reportó que
    CASA/HOGAR y VIVERES/SUPER seguían reapareciendo pese a eso: "esas
    categorias viejas no deben exisitir cuantas veces te lo debo
    repetir". Causa raíz (mismo patrón ya diagnosticado en
    _corregir_fusion_gio): reglas de keyword guardadas por el usuario en
    est_keywords ANTES del retiro todavía tenían categoria=<vieja>, y
    cada "Aplicar todas a lo existente" o import nuevo las revivía,
    deshaciendo cualquier barrido de datos hecho por migración. Se
    corrigen AMBAS tablas para blindarlo de verdad: est_keywords (para
    que ninguna regla guardada vuelva a producir la categoria vieja) y
    est_movimientos (por si alguna fila se cuela antes de que la regla
    se corrija)."""
    total = 0
    for legacy, (cat, sub) in _LEGACY_CATEGORIA_MAP.items():
        cur = db.execute(
            "UPDATE est_keywords SET categoria=?, subcategoria=? WHERE categoria=?",
            (cat, sub, legacy),
        )
        total += cur.rowcount
        cur = db.execute(
            "UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE categoria=?",
            (cat, sub, legacy),
        )
        total += cur.rowcount
    return total


def _corregir_alimentacion_split(db) -> int:
    """ALIMENTACION se separó (2026-09, a petición del usuario) en SUPER
    (Súper/Conveniencia → Necesidades) y COMIDA_FUERA (Restaurante/Fast
    Food/Delivery → Deseos): juntas inflaban Necesidades en el 50-30-20.
    Blindaje con el mismo patrón que _corregir_categorias_legacy: corrige
    est_keywords para que ninguna regla guardada la reviva y
    est_movimientos por si alguna fila se cuela. La regla de reparto vive en
    config.split_alimentacion (la misma que usa la migración)."""
    from .config import split_alimentacion
    total = 0
    for tabla, texto in (('est_keywords', 'keyword'), ('est_movimientos', 'descripcion')):
        for r in db.execute(f"SELECT id, subcategoria, {texto} AS t FROM {tabla} "
                            f"WHERE categoria='ALIMENTACION'").fetchall():
            cat, sub = split_alimentacion(r['subcategoria'], r['t'])
            db.execute(f"UPDATE {tabla} SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, r['id']))
            total += 1
    return total


_SERVICIOS_SUBCAT_MAP = {
    'Internet':       ('VIVIENDA', 'Internet'),
    'Luz':            ('VIVIENDA', 'Luz'),
    'Agua':           ('VIVIENDA', 'Agua'),
    'Gas':            ('VIVIENDA', 'Gas'),
    'Saldo telefono': ('DIGITAL',  'Celular'),
    '':               ('VIVIENDA', ''),
}


def _corregir_servicios_legacy(db) -> int:
    """"SERVICIOS" es una categoria plana legacy (de antes de que Vivienda
    tuviera subcategorías propias por servicio). El sprint de taxonomía
    en database.py solo migró sus filas con subcategoria Internet/Luz/
    Saldo telefono, dejando Agua/Gas/'' sin tocar, y sin blindaje contra
    recurrencia -- mismo patrón ya diagnosticado en
    _corregir_categorias_legacy: reglas guardadas en est_keywords ANTES
    de esa migración la seguían reviviendo en cada import o "Aplicar
    todas a lo existente". El usuario reportó ver el mismo gasto
    duplicado entre categoria=SERVICIOS y VIVIENDA con
    subcategoria='Servicios' (tampoco es una subcategoría real de
    Vivienda -- no existe en SUBCATEGORIAS de config.py). Se unifica todo
    bajo VIVIENDA con la subcategoría específica cuando se puede inferir
    de la subcategoria vieja; si no hay pista suficiente se deja
    subcategoria='' en vez de adivinar mal (el usuario la completa a
    mano una vez, igual que cualquier transacción nueva sin regla)."""
    from .config import SUBCATEGORIAS
    total = 0

    for sub_vieja, (cat, sub) in _SERVICIOS_SUBCAT_MAP.items():
        cur = db.execute(
            "UPDATE est_keywords SET categoria=?, subcategoria=? "
            "WHERE UPPER(categoria)='SERVICIOS' AND UPPER(COALESCE(subcategoria,''))=?",
            (cat, sub, sub_vieja.upper()),
        )
        total += cur.rowcount
        cur = db.execute(
            "UPDATE est_movimientos SET categoria=?, subcategoria=? "
            "WHERE UPPER(categoria)='SERVICIOS' AND UPPER(COALESCE(subcategoria,''))=?",
            (cat, sub, sub_vieja.upper()),
        )
        total += cur.rowcount

    # Catch-all: cualquier fila que siga en SERVICIOS con una subcategoria
    # no contemplada arriba (typo, variante no prevista) -- se sube a
    # VIVIENDA de todos modos; conserva la subcategoria solo si ya es
    # válida ahí, si no se blanquea en vez de adivinar.
    validas_vivienda = set(SUBCATEGORIAS.get('VIVIENDA', []))
    for row in db.execute(
        "SELECT rowid, subcategoria FROM est_keywords WHERE UPPER(categoria)='SERVICIOS'"
    ).fetchall():
        sub = (row['subcategoria'] or '').strip()
        db.execute(
            "UPDATE est_keywords SET categoria='VIVIENDA', subcategoria=? WHERE rowid=?",
            (sub if sub in validas_vivienda else '', row['rowid']),
        )
        total += 1
    for row in db.execute(
        "SELECT id, subcategoria FROM est_movimientos WHERE UPPER(categoria)='SERVICIOS'"
    ).fetchall():
        sub = (row['subcategoria'] or '').strip()
        db.execute(
            "UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria=? WHERE id=?",
            (sub if sub in validas_vivienda else '', row['id']),
        )
        total += 1

    # VIVIENDA/Servicios genérico: no es una subcategoría real y no hay
    # pista distinta a "Servicios" para inferir cuál sub específica le
    # toca -- se blanquea.
    cur = db.execute(
        "UPDATE est_keywords SET subcategoria='' "
        "WHERE UPPER(categoria)='VIVIENDA' AND UPPER(subcategoria)='SERVICIOS'"
    )
    total += cur.rowcount
    cur = db.execute(
        "UPDATE est_movimientos SET subcategoria='' "
        "WHERE UPPER(categoria)='VIVIENDA' AND UPPER(subcategoria)='SERVICIOS'"
    )
    total += cur.rowcount

    return total


_SUSCRIPCIONES_SUBCAT_MAP = {
    '':              ('DIGITAL',   ''),
    'Digital':       ('DIGITAL',   'Suscripciones entretenimiento'),
    'Diseño':        ('DIGITAL',   'Suscripciones IA/productividad'),
    'Gym':           ('DEPORTE',   'Gym'),
    'Internet/TV':   ('DIGITAL',   'Suscripciones entretenimiento'),
    'Música':        ('DIGITAL',   'Suscripciones entretenimiento'),
    'Productividad': ('DIGITAL',   'Suscripciones IA/productividad'),
    'Tech':          ('PROYECTOS', 'Hosting'),
    'Telefonía':     ('DIGITAL',   'Celular'),
}
_SUSCRIPCIONES_TELEFONO_KW = ('TELEFON', 'SALDO', 'CELULAR')


def _corregir_suscripciones_legacy(db) -> int:
    """"SUSCRIPCIONES" es otra categoria plana legacy, mismo patrón que
    CASA/HOGAR y SERVICIOS: el sprint de taxonomía en database.py ya la
    mapea (SUSCRIPCIONES/Telefonía -> DIGITAL/Celular, /Digital y
    /Internet/TV y /Música -> DIGITAL/Suscripciones entretenimiento,
    /Diseño y /Productividad -> DIGITAL/Suscripciones IA/productividad,
    /Gym -> DEPORTE/Gym, /Tech -> PROYECTOS/Hosting), pero nunca tuvo
    blindaje contra recurrencia -- el usuario reportó "saldo teléfono"
    partido entre SERVICIOS y SUSCRIPCIONES, mismo síntoma que ya se vio
    con _corregir_servicios_legacy: reglas guardadas en est_keywords
    ANTES de esa migración la seguían reviviendo en cada import o
    "Aplicar todas a lo existente". El destino elegido para saldo/plan de
    teléfono es DIGITAL/Celular en los dos casos (Servicios y
    Suscripciones), para que quede en un solo lugar."""
    from .config import SUBCATEGORIAS
    total = 0

    for sub_vieja, (cat, sub) in _SUSCRIPCIONES_SUBCAT_MAP.items():
        cur = db.execute(
            "UPDATE est_keywords SET categoria=?, subcategoria=? "
            "WHERE UPPER(categoria)='SUSCRIPCIONES' AND UPPER(COALESCE(subcategoria,''))=?",
            (cat, sub, sub_vieja.upper()),
        )
        total += cur.rowcount
        cur = db.execute(
            "UPDATE est_movimientos SET categoria=?, subcategoria=? "
            "WHERE UPPER(categoria)='SUSCRIPCIONES' AND UPPER(COALESCE(subcategoria,''))=?",
            (cat, sub, sub_vieja.upper()),
        )
        total += cur.rowcount

    # Variantes de "saldo teléfono" no cubiertas por el mapeo exacto
    # (typos, sin acento, etc.) -- cualquier subcategoria que mencione
    # teléfono/saldo/celular se va a DIGITAL/Celular, igual que en
    # _corregir_servicios_legacy.
    for row in db.execute(
        "SELECT rowid, subcategoria FROM est_keywords WHERE UPPER(categoria)='SUSCRIPCIONES'"
    ).fetchall():
        sub_u = (row['subcategoria'] or '').upper()
        if any(kw in sub_u for kw in _SUSCRIPCIONES_TELEFONO_KW):
            db.execute(
                "UPDATE est_keywords SET categoria='DIGITAL', subcategoria='Celular' WHERE rowid=?",
                (row['rowid'],),
            )
            total += 1
    for row in db.execute(
        "SELECT id, subcategoria FROM est_movimientos WHERE UPPER(categoria)='SUSCRIPCIONES'"
    ).fetchall():
        sub_u = (row['subcategoria'] or '').upper()
        if any(kw in sub_u for kw in _SUSCRIPCIONES_TELEFONO_KW):
            db.execute(
                "UPDATE est_movimientos SET categoria='DIGITAL', subcategoria='Celular' WHERE id=?",
                (row['id'],),
            )
            total += 1

    # Catch-all: cualquier fila que siga en SUSCRIPCIONES -- se sube a
    # DIGITAL de todos modos; conserva la subcategoria solo si ya es
    # válida ahí, si no se blanquea en vez de adivinar.
    validas_digital = set(SUBCATEGORIAS.get('DIGITAL', []))
    for row in db.execute(
        "SELECT rowid, subcategoria FROM est_keywords WHERE UPPER(categoria)='SUSCRIPCIONES'"
    ).fetchall():
        sub = (row['subcategoria'] or '').strip()
        db.execute(
            "UPDATE est_keywords SET categoria='DIGITAL', subcategoria=? WHERE rowid=?",
            (sub if sub in validas_digital else '', row['rowid']),
        )
        total += 1
    for row in db.execute(
        "SELECT id, subcategoria FROM est_movimientos WHERE UPPER(categoria)='SUSCRIPCIONES'"
    ).fetchall():
        sub = (row['subcategoria'] or '').strip()
        db.execute(
            "UPDATE est_movimientos SET categoria='DIGITAL', subcategoria=? WHERE id=?",
            (sub if sub in validas_digital else '', row['id']),
        )
        total += 1

    return total


def _corregir_steamgames(db) -> int:
    """El usuario pidió mover las compras de STEAMGAMES.COM que estaban
    cayendo en DIGITAL/Suscripciones IA/productividad a OCIO/Videojuegos
    ("manda estos a Entretenimiento y crea una subcategoria de
    videojuegos" -- OCIO ya existe con esa subcategoria, mostrada como
    "Ocio" en el selector). No hay keyword "STEAMGAMES" en config.py, así
    que además de esta corrección se agregó ahí para que futuras compras
    se clasifiquen bien desde el import; esta función es el blindaje para
    cualquier fila que ya se haya colado con otra categoria."""
    cur = db.execute("""
        UPDATE est_movimientos SET categoria='OCIO', subcategoria='Videojuegos'
        WHERE UPPER(descripcion) LIKE '%STEAMGAMES%'
          AND (categoria != 'OCIO' OR subcategoria != 'Videojuegos')
    """)
    return cur.rowcount


# Retiros sin tarjeta de 2023 que en realidad fueron el pago de la renta en
# efectivo. El usuario los señaló uno por uno (fecha + monto): no se toca
# ningún otro retiro, porque la mayoría sí son efectivo de uso diario.
RETIROS_RENTA_2023 = (
    ('2023-02-16', 8000.0), ('2023-03-17', 8000.0), ('2023-04-18', 8600.0),
    ('2023-05-18', 8500.0), ('2023-07-16', 7000.0), ('2023-09-16', 7600.0),
)


def _corregir_retiros_renta(db) -> int:
    """Esos retiros van a VIVIENDA/Renta. Blindaje: una regla de keyword
    «RETIRO» los regresaría a FINANZAS/Retiro efectivo al «Aplicar reglas»."""
    n = 0
    for fecha, monto in RETIROS_RENTA_2023:
        n += db.execute("""
            UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Renta', tipo='GASTO'
            WHERE substr(fecha, 1, 10)=? AND ABS(ABS(monto) - ?) < 0.005 AND tipo != 'INGRESO'
              AND UPPER(descripcion) LIKE 'RETIRO SIN TARJETA%'
              AND (categoria != 'VIVIENDA' OR subcategoria != 'Renta' OR tipo != 'GASTO')
        """, (fecha, monto)).rowcount
    return n


def _corregir_spei_invex(db) -> int:
    """Todo «SPEI ENVIADO … INVEX» es el pago de la TDC Invex (misma regla
    que _es_movimiento_interno en el import) -> PAGO_TDC / MOVIMIENTO_INTERNO.
    El import solo la aplica a las filas nuevas; una regla de keyword
    (ej. «INVEX» -> INVERSION, «SPEI ENVIADO» -> FINANZAS) las movía al
    «Aplicar reglas», y las históricas nunca pasaron por ella."""
    return db.execute("""
        UPDATE est_movimientos SET categoria='PAGO_TDC', subcategoria='', tipo='MOVIMIENTO_INTERNO'
        WHERE UPPER(descripcion) LIKE '%SPEI ENVIADO%' AND UPPER(descripcion) LIKE '%INVEX%'
          AND (categoria != 'PAGO_TDC' OR subcategoria != '' OR tipo != 'MOVIMIENTO_INTERNO')
    """).rowcount


def _corregir_zaira_restaurante(db) -> int:
    """ZTL ZAIRAAXZAYMENDOZAM va a COMIDA_FUERA/Restaurante (pedido del
    usuario). Antes 2 filas se habían mandado por id a ALIMENTACION/Súper;
    esto las alcanza a todas y evita que una regla de keyword las mueva."""
    return db.execute("""
        UPDATE est_movimientos SET categoria='COMIDA_FUERA', subcategoria='Restaurante', tipo='GASTO'
        WHERE UPPER(descripcion) LIKE '%ZAIRAAXZAYMENDOZAM%' AND tipo IN ('GASTO', 'PAGO')
          AND (categoria != 'COMIDA_FUERA' OR subcategoria != 'Restaurante' OR tipo != 'GASTO')
    """).rowcount


# Mensualidades de la lavadora comprada en walmart.com a 20 MSI: ~$509 cada
# una, descritas como «WALMART VENTA EN LIN…». El keyword genérico «WALMART»
# las mandaba a SUPER/Súper; el monto las separa de las compras de súper.
WALMART_LAVADORA_MONTO = (508.5, 510.0)


def _corregir_walmart_lavadora(db) -> int:
    """Mensualidades de la lavadora -> VIVIENDA/Artículos del hogar. El banco
    a veces corta la descripción («19 DE 20 WALMART VENTA EN L») y la última
    mensualidad fue de otro monto ($498), así que también cuenta cualquier
    «N DE 20 WALMART VENTA EN L…» (la lavadora es la compra a 20 meses)."""
    lo, hi = WALMART_LAVADORA_MONTO
    return db.execute("""
        UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Artículos del hogar', tipo='GASTO'
        WHERE UPPER(descripcion) LIKE '%WALMART%VENTA EN L%'
          AND ((ABS(monto) >= ? AND ABS(monto) < ?) OR UPPER(descripcion) LIKE '% DE 20 WALMART%')
          AND tipo IN ('GASTO', 'PAGO')
          AND (categoria != 'VIVIENDA' OR subcategoria != 'Artículos del hogar' OR tipo != 'GASTO')
    """, (lo, hi)).rowcount


# DiDi: si la descripción habla de un viaje (RIDE, VIAJE…) es transporte y
# se queda como lo clasificó el keyword «DIDI» (TRANSPORTE/Taxi/apps); todo
# lo demás de DiDi es comida a domicilio (pedido del usuario).
DIDI_VIAJE_KW = ('RIDE', 'VIAJE', 'TAXI', 'MOVILIDAD')


def _corregir_didi_delivery(db) -> int:
    """DIDI sin marca de viaje -> COMIDA_FUERA/Delivery. Los viajes no se tocan."""
    no_viaje = " ".join("AND UPPER(descripcion) NOT LIKE ?" for _ in DIDI_VIAJE_KW)
    return db.execute(f"""
        UPDATE est_movimientos SET categoria='COMIDA_FUERA', subcategoria='Delivery', tipo='GASTO'
        WHERE UPPER(descripcion) LIKE '%DIDI%' {no_viaje} AND tipo IN ('GASTO', 'PAGO')
          AND (categoria != 'COMIDA_FUERA' OR subcategoria != 'Delivery' OR tipo != 'GASTO')
    """, tuple(f"%{kw}%" for kw in DIDI_VIAJE_KW)).rowcount


# Amazon: el keyword genérico «AMAZON» manda todo a DIGITAL/Accesorios tech,
# pero estos cargos son suscripciones de entretenimiento (pedido del usuario,
# con capturas), siempre que la descripción NO diga «A MESES» (esas sí son
# compras a MSI):
#   - la descripción es solo «AMAZON» (cualquier monto),
#   - cualquier cargo de Amazon de $100 o más («los que son de cientos»),
#   - «AMAZONCOM INC…» de $69 (la mensualidad),
#   - «AMAZON MEXICO» de $43.20 (mismo cargo que el «AMAZON» de $43.20).
# Solo dentro de DIGITAL: no se jalan cargos de Amazon que el usuario ya
# mandó a otra categoría (ej. AMAZON MEXICO -> VIVIENDA/Artículos del hogar).
AMAZON_SUSCRIPCION_MIN_CIENTOS = 100.0
AMAZON_SUSCRIPCION_INC_MONTO = 69.0
AMAZON_SUSCRIPCION_MX_MONTO = 43.20


def _corregir_amazon_suscripciones(db) -> int:
    """Esos cargos de Amazon -> DIGITAL/Suscripciones entretenimiento."""
    return db.execute("""
        UPDATE est_movimientos SET subcategoria='Suscripciones entretenimiento', tipo='GASTO'
        WHERE categoria='DIGITAL' AND tipo IN ('GASTO', 'PAGO')
          AND UPPER(descripcion) LIKE 'AMAZON%' AND UPPER(descripcion) NOT LIKE '%MESES%'
          AND (TRIM(UPPER(descripcion)) = 'AMAZON'
               OR ABS(monto) >= ?
               OR (UPPER(descripcion) LIKE 'AMAZON%INC%' AND ABS(ABS(monto) - ?) < 0.005)
               OR (TRIM(UPPER(descripcion)) = 'AMAZON MEXICO' AND ABS(ABS(monto) - ?) < 0.005))
          AND (subcategoria != 'Suscripciones entretenimiento' OR tipo != 'GASTO')
    """, (AMAZON_SUSCRIPCION_MIN_CIENTOS, AMAZON_SUSCRIPCION_INC_MONTO, AMAZON_SUSCRIPCION_MX_MONTO)).rowcount


# MI ATT (app de AT&T) y RECARGAS Y PAQUETES (BBVA móvil) son siempre el
# celular (pedido del usuario: «que así sea siempre»). Una migración vieja
# había mandado 3 recargas a «Saldo telefono».
CELULAR_KW = ('MI ATT', 'RECARGAS Y PAQUETES')


def _corregir_celular(db) -> int:
    """MI ATT / RECARGAS Y PAQUETES -> DIGITAL/Celular."""
    kw = " OR ".join("UPPER(descripcion) LIKE ?" for _ in CELULAR_KW)
    return db.execute(f"""
        UPDATE est_movimientos SET categoria='DIGITAL', subcategoria='Celular', tipo='GASTO'
        WHERE ({kw}) AND tipo IN ('GASTO', 'PAGO')
          AND (categoria != 'DIGITAL' OR subcategoria != 'Celular' OR tipo != 'GASTO')
    """, tuple(f"%{k}%" for k in CELULAR_KW)).rowcount


# «PAGO CUENTA DE TERCERO…» en EXPENSE: un compañero pagó el gasto de
# trabajo, la empresa me lo reembolsó a mí y yo se lo transfiero a él. No es
# un reembolso pendiente ni gasto mío — estatus propio para distinguirlo en
# la referencia de Expense (pedido del usuario).
EXPENSE_ESTATUS_TERCERO = 'TERCERO'


def _corregir_expense_terceros(db) -> int:
    """EXPENSE «PAGO CUENTA DE TERCERO…» -> estatus_reembolso='TERCERO'."""
    # Algunos llegan del banco como tipo PAGO: son la misma salida de dinero
    # (y así no aparecían para armar lotes), se normalizan a GASTO.
    return db.execute("""
        UPDATE est_movimientos SET estatus_reembolso=?, tipo='GASTO'
        WHERE categoria='EXPENSE' AND tipo IN ('GASTO', 'PAGO')
          AND UPPER(descripcion) LIKE '%PAGO CUENTA DE TERCERO%'
          AND (estatus_reembolso IS NULL OR estatus_reembolso IN ('', 'PENDIENTE') OR tipo = 'PAGO')
    """, (EXPENSE_ESTATUS_TERCERO,)).rowcount


# Transferencias que el usuario señaló como gasto de Salsa (fecha, monto,
# texto de la descripción). Caían en FINANZAS/Transferencia; una regla de
# keyword («PAGO CUENTA DE TERCERO» -> Familia y regalos) también podría
# moverlas, así que se reafirman en el import y en «Aplicar reglas».
PAGOS_SALSA = (
    ('2024-10-15', 3500.0, 'SOLAR GIOVANY'),
)


def _corregir_pagos_salsa(db) -> int:
    n = 0
    for fecha, monto, texto in PAGOS_SALSA:
        n += db.execute("""
            UPDATE est_movimientos SET categoria='SALSA', subcategoria='', tipo='GASTO'
            WHERE substr(fecha, 1, 10)=? AND ABS(ABS(monto) - ?) < 0.005
              AND UPPER(descripcion) LIKE ? AND tipo IN ('GASTO', 'PAGO')
              AND (categoria != 'SALSA' OR tipo != 'GASTO')
        """, (fecha, monto, f"%{texto}%")).rowcount
    return n


def _corregir_expense_en_ingreso(categoria: str, subcategoria: str, tipo: str) -> tuple[str, str]:
    """EXPENSE es exclusivamente para el lado del GASTO (algo que pagas y
    te van a reembolsar -- ver estatus_reembolso/_sugerir_reembolsos). El
    usuario confirmó que por costumbre le pone EXPENSE también al
    depósito que le regresan, y como EXPENSE nunca lleva subcategoria
    (_normalize_subcategoria) ese ingreso le queda "sin categoría". Si
    alguien guarda categoria=EXPENSE en un movimiento tipo=INGRESO, se
    corrige solo a FINANZAS/Reembolsable -- que sí es una categoría real
    de ingreso pensada para esto -- en vez de dejarlo pasar."""
    if categoria == 'EXPENSE' and tipo == 'INGRESO':
        return 'FINANZAS', 'Reembolsable'
    return categoria, subcategoria


def _corregir_renta_en_ingreso(categoria: str, subcategoria: str, tipo: str) -> tuple[str, str]:
    """El usuario confirmó que "Aportación renta" y "Renta" en un ingreso
    son el mismo concepto real (alguien te deposita su parte de la renta,
    ej. vía Nu) y pidió unificarlos -- "aportacion renta y parte renta Nu
    son lo mismo unificalo". VIVIENDA/Renta es la subcategoria correcta
    del lado GASTO (tú pagando la renta); VIVIENDA/Aportación renta es la
    del lado INGRESO (alguien más aportando). Si categoria=VIVIENDA,
    subcategoria='Renta' y tipo=INGRESO, se corrige a 'Aportación renta'."""
    if categoria == 'VIVIENDA' and subcategoria == 'Renta' and tipo == 'INGRESO':
        return categoria, 'Aportación renta'
    return categoria, subcategoria


_SORT_COLUMNS = {
    'fecha_desc':  'fecha DESC',
    'fecha_asc':   'fecha ASC',
    'monto_desc':  'ABS(monto) DESC',
    'monto_asc':   'ABS(monto) ASC',
}


@estados_bp.route('/api/transactions')
def list_transactions():
    """El usuario reportó "veo Finanzas en Top gastos pero no aparece en
    ninguna otra parte" -- el tab Reportes de estados.js (bundle sin fuente
    en este repo, no se puede tocar ahí) pide aquí mismo
    tipo=GASTO&limit=2000&date_from=...&date_to=... para traerse TODO el
    período y calcular en el cliente tanto "Top N gastos" como el desglose
    por comercio. A diferencia de by-category/overview/monthly/summary_stats
    (que todos excluyen PAGO_TDC/PAGO/PRESTAMOS/FINANZAS vía _PAGO_CATS por
    ser transferencias/pagos internos, no gasto real), este endpoint genérico
    no aplicaba ese filtro -- así que una transferencia de $55,000 a NAFIN
    aparecía como el "gasto" más grande del período sin poder encontrarse en
    ningún desglose por categoría del resto del dashboard.

    Se aplica la misma exclusión aquí, pero SOLO cuando (a) no se pidió una
    categoría explícita y (b) el limit es grande (>=500) -- la firma real
    del fetch masivo de Reportes. El tab Movimientos pagina con limit=50 (ver
    sniff de red), así que nunca entra por esta rama; y si alguien sí filtra
    por category=FINANZAS a propósito (para revisar/reclasificar esas
    transferencias) tampoco se le oculta nada."""
    if not _ok(): return _locked()

    limit  = min(int(request.args.get('limit', 200)), 2000)
    offset = int(request.args.get('offset', 0))
    order_by = _SORT_COLUMNS.get(request.args.get('sort'), 'fecha DESC')
    conds, params = _build_filters(request.args)

    if limit >= 500 and not request.args.get('category'):
        tipo_arg = request.args.get('tipo', '').upper()
        if tipo_arg == 'GASTO':
            conds.append(_PAGO_CATS)
        elif tipo_arg == 'INGRESO':
            conds.append(_INGRESO_EXCLUIR_SQL)

    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    with get_db() as db:
        total = db.execute(
            f"SELECT COUNT(*) FROM est_movimientos {where}", params
        ).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM est_movimientos {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return jsonify({'data': [dict(r) for r in rows], 'total': total})


@estados_bp.route('/api/transactions', methods=['POST'])
def create_transaction():
    if not _ok(): return _locked()
    d = request.json or {}
    fecha = d.get('fecha', '')
    desc  = d.get('descripcion', '')
    categoria = d.get('categoria', 'OTROS')
    monto = safe_float(d.get('monto', 0))
    tipo = d.get('tipo', 'GASTO')
    categoria, subcategoria_in = _corregir_expense_en_ingreso(categoria, d.get('subcategoria', ''), tipo)
    categoria, subcategoria_in = _corregir_renta_en_ingreso(categoria, subcategoria_in, tipo)
    with get_db() as db:
        # Mismo día + mismo monto + mismo tipo, sin importar la descripción,
        # suele ser el mismo movimiento real capturado dos veces (ver
        # /admin/audit-duplicados) -- el índice UNIQUE(fecha,descripcion,monto)
        # de abajo no lo detecta cuando la descripción difiere. Se bloquea
        # por default; force=true lo permite (puede ser una coincidencia
        # legítima, ej. dos compras iguales el mismo día).
        if monto > 0 and not d.get('force'):
            dup = db.execute(
                "SELECT id, descripcion, banco FROM est_movimientos "
                "WHERE fecha=? AND ROUND(monto,2)=ROUND(?,2) AND tipo=?",
                (fecha, monto, tipo),
            ).fetchone()
            if dup:
                return jsonify({
                    'inserted': 0,
                    'possible_duplicate': True,
                    'existing': dict(dup),
                    'error': f'Ya existe un movimiento del mismo día, monto y tipo '
                             f'("{dup["descripcion"]}", {dup["banco"]}) — puede ser el mismo '
                             f'movimiento real capturado dos veces con otra descripción. '
                             f'Revísalo antes de guardar uno nuevo igual.',
                }), 409

        cur = db.execute(
            """INSERT OR IGNORE INTO est_movimientos
               (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fecha, fecha, desc, monto,
             d.get('banco', 'MANUAL'), d.get('periodo', ''),
             categoria, _normalize_subcategoria(categoria, subcategoria_in),
             tipo),
        )
        db.commit()
        inserted = cur.rowcount
        new_id = cur.lastrowid if inserted else None
    if not inserted:
        # Índice UNIQUE(fecha, descripcion): ya existe un movimiento con esa
        # misma fecha y descripción exacta — no se guardó. Devolvemos error
        # real en vez de fingir éxito, para que el cliente pueda avisar.
        return jsonify({
            'inserted': 0,
            'error': 'Ya existe un movimiento con esa fecha y descripción exacta. '
                     'Cambia la descripción si es una transacción distinta (ej. añade la hora o el monto).',
        }), 409
    return jsonify({'inserted': 1, 'id': new_id}), 201


@estados_bp.route('/api/transactions/<int:tx_id>', methods=['PATCH'])
def update_transaction(tx_id):
    if not _ok(): return _locked()
    d = request.json or {}
    with get_db() as db:
        if d.get('descripcion') is not None:
            db.execute("UPDATE est_movimientos SET descripcion=? WHERE id=?",
                       (clean_str(d['descripcion'], 300), tx_id))
        if d.get('categoria') is not None:
            db.execute(
                "UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?",
                (d['categoria'], _normalize_subcategoria(d['categoria'], d.get('subcategoria', '')), tx_id),
            )
        if d.get('monto') is not None:
            db.execute("UPDATE est_movimientos SET monto=? WHERE id=?",
                       (safe_float(d['monto']), tx_id))
        if d.get('tipo') is not None:
            db.execute("UPDATE est_movimientos SET tipo=? WHERE id=?",
                       (d['tipo'], tx_id))
        if d.get('fecha') is not None:
            db.execute("UPDATE est_movimientos SET fecha=?, fecha_cargo=? WHERE id=?",
                       (d['fecha'], d['fecha'], tx_id))
        if d.get('banco') is not None:
            db.execute("UPDATE est_movimientos SET banco=? WHERE id=?",
                       (d['banco'], tx_id))
        if d.get('periodo') is not None:
            db.execute("UPDATE est_movimientos SET periodo=? WHERE id=?",
                       (d['periodo'], tx_id))
        if 'mi_parte' in d:
            val = safe_float(d['mi_parte']) if d['mi_parte'] not in (None, '') else None
            db.execute("UPDATE est_movimientos SET mi_parte=? WHERE id=?", (val, tx_id))
        if 'reembolso_cat' in d:
            val = d['reembolso_cat'] or None
            db.execute("UPDATE est_movimientos SET reembolso_cat=? WHERE id=?", (val, tx_id))
        if 'viaje_id' in d:
            val = int(d['viaje_id']) if d['viaje_id'] not in (None, '') else None
            db.execute("UPDATE est_movimientos SET viaje_id=? WHERE id=?", (val, tx_id))
        if 'estatus_reembolso' in d:
            val = d['estatus_reembolso'] or None
            db.execute("UPDATE est_movimientos SET estatus_reembolso=? WHERE id=?", (val, tx_id))
        if 'fecha_reembolso' in d:
            val = d['fecha_reembolso'] or None
            db.execute("UPDATE est_movimientos SET fecha_reembolso=? WHERE id=?", (val, tx_id))
        # El PATCH aplica los campos por separado (categoria/subcategoria/
        # tipo pueden llegar en requests distintos), así que las
        # correcciones de _corregir_expense_en_ingreso y
        # _corregir_renta_en_ingreso se revisan aquí sobre el estado ya
        # actualizado, leyendo la fila completa en vez de solo lo que
        # llegó en este request.
        row = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
        if row:
            cat, sub = _corregir_expense_en_ingreso(row['categoria'], row['subcategoria'], row['tipo'])
            cat, sub = _corregir_renta_en_ingreso(cat, sub, row['tipo'])
            if cat != row['categoria'] or sub != row['subcategoria']:
                db.execute(
                    "UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?",
                    (cat, sub, tx_id),
                )
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_movimientos WHERE id=?", (tx_id,))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/transactions/reembolsos')
def list_reembolsos():
    """Return INGRESO transactions tagged as reimbursements for a given category."""
    if not _ok(): return _locked()
    cat = request.args.get('category')
    if not cat:
        return jsonify({'data': []})
    conds, params = ['reembolso_cat = ?'], [cat]
    if request.args.get('date_from'):
        conds.append("fecha >= ?"); params.append(request.args['date_from'])
    if request.args.get('date_to'):
        conds.append("fecha <= ?"); params.append(request.args['date_to'])
    if request.args.get('bank'):
        conds.append("banco = ?"); params.append(request.args['bank'])
    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM est_movimientos WHERE {' AND '.join(conds)} ORDER BY fecha DESC",
            params,
        ).fetchall()
    return jsonify({'data': [dict(r) for r in rows]})


@estados_bp.route('/api/transactions/export/csv')
def export_csv():
    if not _ok(): return _locked()
    conds, params = _build_filters(request.args)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM est_movimientos {where} ORDER BY fecha DESC", params
        ).fetchall()

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=dict(rows[0]).keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])

    # BOM UTF-8 al inicio: el usuario reportó acentos rotos ("ArtÃ¬culos
    # del hogar" en vez de "Artículos del hogar") al abrir el CSV en
    # Excel -- sin BOM, Excel asume ANSI/Windows-1252 en vez de UTF-8 y
    # descompone cada carácter acentuado en dos. El BOM le indica a Excel
    # explícitamente que el archivo es UTF-8.
    return Response(
        '﻿' + output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename=transacciones.csv',
        },
    )


# ── Summary / Analytics ───────────────────────────────────────────────────────

@estados_bp.route('/api/summary/overview')
def overview():
    if not _ok(): return _locked()
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")

    with get_db() as db:
        row = db.execute(f"""
            SELECT
                SUM(CASE WHEN tipo='INGRESO' AND {_INGRESO_EXCLUIR_SQL} THEN monto ELSE 0 END) AS income,
                SUM(CASE WHEN tipo='GASTO' AND {_PAGO_CATS}              THEN {_MONTO} ELSE 0 END) AS expense,
                SUM(CASE WHEN tipo='INVERSION'                           THEN monto ELSE 0 END) AS inversion,
                COUNT(*) AS tx_count
            FROM est_movimientos WHERE fecha >= ?
        """, (month_start,)).fetchone()

    income    = row['income']    or 0.0
    expense   = row['expense']   or 0.0
    inversion = row['inversion'] or 0.0
    savings   = round((income - expense) / income * 100, 1) if income > 0 else 0

    return jsonify({
        'income':      round(income, 2),
        'expense':     round(expense, 2),
        'balance':     round(income - expense, 2),
        'inversion':   round(inversion, 2),
        'savings_pct': savings,
        'tx_count':    row['tx_count'] or 0,
        'period':      month_start,
    })


@estados_bp.route('/api/summary/monthly')
def monthly_summary():
    if not _ok(): return _locked()
    months = min(int(request.args.get('months', 6)), 24)
    bank   = request.args.get('bank')

    bank_filter = "AND banco = ?" if bank else ""
    bank_params = [bank] if bank else []

    with get_db() as db:
        rows = db.execute(f"""
            SELECT
                substr(fecha,1,7) AS ym,
                SUM(CASE WHEN tipo='INGRESO' AND {_INGRESO_EXCLUIR_SQL} THEN monto ELSE 0 END) AS income,
                SUM(CASE WHEN tipo='GASTO' AND {_PAGO_CATS}              THEN {_MONTO} ELSE 0 END) AS expense
            FROM est_movimientos
            WHERE 1=1 {bank_filter}
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT ?
        """, bank_params + [months]).fetchall()

    month_names = ["Ene","Feb","Mar","Abr","May","Jun",
                   "Jul","Ago","Sep","Oct","Nov","Dic"]
    result = []
    for r in reversed(rows):
        _, mon = r['ym'].split("-")
        result.append({
            'month':      month_names[int(mon) - 1],
            'year_month': r['ym'],
            'income':     round(r['income'] or 0, 2),
            'expense':    round(r['expense'] or 0, 2),
        })
    return jsonify(result)


def _prev_period_range(date_from: str, date_to: str | None) -> tuple[str, str]:
    """Rango [prev_from, prev_to] de igual duración, inmediatamente anterior
    a [date_from, date_to] — usado para calcular tendencia (% de cambio) de
    un periodo contra el que le precede. `date_to` ausente se toma como hoy,
    igual que hace by-category para el rango en curso."""
    d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    d_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else datetime.now().date()
    span = (d_to - d_from).days + 1
    prev_to = d_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    return prev_from.isoformat(), prev_to.isoformat()


@estados_bp.route('/api/summary/by-category')
def by_category():
    """El usuario reportó que el modal de detalle de una categoría (clic
    en una fila de "Gastos por categoría") mezclaba filas tipo=INGRESO
    junto con las de GASTO bajo la misma categoria/subcategoria (ej.
    "Familia y regalos" con un +$50,000 verde de ingreso al lado de gastos
    reales), aunque el total agregado de arriba SOLO cuenta GASTO -- "aqui
    veo ingresos y gastos en lo mismo". Ese modal (api/transactions) ya
    soportaba filtrar por tipo, solo le faltaba que el front se lo pidiera
    (ver EuReports/$p en estados.js). Este endpoint ahora acepta
    tipo=GASTO|INGRESO (default GASTO) para poder alimentar tanto la vista
    de gastos como una de ingresos por categoría con el mismo query, cada
    una con su propia definición de "categoria real" (_PAGO_CATS excluye
    movimientos internos del lado gasto; _INGRESO_EXCLUIR_SQL excluye
    transferencias/retiros del lado ingreso, igual que /api/summary/stats)
    y su propio monto (mi_parte aplica solo a gasto compartido)."""
    if not _ok(): return _locked()
    bank = request.args.get('bank')
    tipo = request.args.get('tipo', 'GASTO').upper()
    if tipo not in ('GASTO', 'INGRESO'):
        tipo = 'GASTO'
    tipo_cond   = _PAGO_CATS if tipo == 'GASTO' else _INGRESO_EXCLUIR_SQL
    monto_expr  = _MONTO if tipo == 'GASTO' else 'monto'

    conds  = [f"tipo='{tipo}'", tipo_cond]
    params = []
    months_cond, months_params = _months_condition(request.args)
    prev_from = prev_to = None
    if months_cond:
        conds.append(months_cond)
        params.extend(months_params)
    else:
        date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
        date_to   = request.args.get('date_to')
        conds.append("fecha >= ?"); params.append(date_from)
        if date_to:
            conds.append("fecha <= ?"); params.append(date_to)
        # Sin months= (rango continuo) sí se puede calcular "el periodo
        # anterior de igual duración" — con months= (meses sueltos, no
        # necesariamente consecutivos) no hay un "anterior" bien definido,
        # así que ahí se deja sin tendencia en vez de inventar una comparación.
        prev_from, prev_to = _prev_period_range(date_from, date_to)
    if bank:
        conds.append("banco = ?"); params.append(bank)

    with get_db() as db:
        rows = db.execute(f"""
            SELECT categoria,
                   SUM({monto_expr}) AS total
            FROM est_movimientos
            WHERE {' AND '.join(conds)}
            GROUP BY categoria ORDER BY total DESC
        """, params).fetchall()

        prev_totals = {}
        if prev_from is not None:
            prev_conds = [f"tipo='{tipo}'", tipo_cond, "fecha >= ?", "fecha <= ?"]
            prev_params = [prev_from, prev_to]
            if bank:
                prev_conds.append("banco = ?"); prev_params.append(bank)
            prev_rows = db.execute(f"""
                SELECT categoria, SUM({monto_expr}) AS total
                FROM est_movimientos
                WHERE {' AND '.join(prev_conds)}
                GROUP BY categoria
            """, prev_params).fetchall()
            prev_totals = {r['categoria']: (r['total'] or 0) for r in prev_rows}

    result = []
    for r in rows:
        total = round(r['total'] or 0, 2)
        prev = prev_totals.get(r['categoria'])
        pct_change = round((total - prev) / prev * 100, 1) if prev else None
        result.append({
            'categoria': r['categoria'],
            'total': total,
            'prev_total': round(prev, 2) if prev is not None else None,
            'pct_change': pct_change,
        })
    return jsonify(result)


@estados_bp.route('/api/summary/by-naturaleza')
def by_naturaleza():
    """Desglose de gasto por naturaleza (FIJO/VARIABLE/IRREGULAR/EVITABLE),
    a partir de est_categoria_naturaleza (sembrada en la migración de
    Sprint 1, nunca antes consumida por ninguna vista). Una transacción sin
    match exacto (categoria, subcategoria) en esa tabla — p. ej. subcategoria
    en blanco para una categoría sin fila de fallback — cae en
    SIN_CLASIFICAR en vez de adivinar."""
    if not _ok(): return _locked()
    bank = request.args.get('bank')

    conds  = ["m.tipo='GASTO'", _pago_cats_sql('m.')]
    params = []
    months_cond, months_params = _months_condition(request.args)
    if months_cond:
        conds.append(months_cond.replace('fecha', 'm.fecha'))
        params.extend(months_params)
    else:
        date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
        date_to   = request.args.get('date_to')
        conds.append("m.fecha >= ?"); params.append(date_from)
        if date_to:
            conds.append("m.fecha <= ?"); params.append(date_to)
    if bank:
        conds.append("m.banco = ?"); params.append(bank)

    with get_db() as db:
        rows = db.execute(f"""
            SELECT COALESCE(n.naturaleza, 'SIN_CLASIFICAR') AS naturaleza,
                   SUM({_monto_expr('m.')}) AS total
            FROM est_movimientos m
            LEFT JOIN est_categoria_naturaleza n
              ON n.categoria = m.categoria AND n.subcategoria = m.subcategoria
            WHERE {' AND '.join(conds)}
            GROUP BY naturaleza ORDER BY total DESC
        """, params).fetchall()

    return jsonify([{'naturaleza': r['naturaleza'], 'total': round(r['total'] or 0, 2)} for r in rows])


@estados_bp.route('/api/summary/pendientes')
def summary_pendientes():
    """Reembolsos (EXPENSE) pendientes y deuda restante estimada en compras
    a MSI activas — datos de los Sprints 1/3 que hasta ahora no se
    resumían en ningún lado."""
    if not _ok(): return _locked()
    with get_db() as db:
        reembolsos = db.execute("""
            SELECT COUNT(*) AS n, COALESCE(SUM(ABS(monto)), 0) AS total
            FROM est_movimientos
            WHERE categoria='EXPENSE' AND estatus_reembolso='PENDIENTE'
        """).fetchone()

        # Referencia de Expense del año en curso: ya no suma en «Total
        # gastado» (ver _pago_cats_sql), pero el usuario quiere saber cuánto
        # se fue en gastos de trabajo, separado por quién lo pagó.
        year_start = datetime.now().strftime("%Y-01-01")
        exp = db.execute("""
            SELECT COUNT(*) AS n,
                   COALESCE(SUM(ABS(monto)), 0) AS total,
                   COALESCE(SUM(CASE WHEN estatus_reembolso='TERCERO' THEN ABS(monto) END), 0) AS terceros,
                   COALESCE(SUM(CASE WHEN estatus_reembolso='PENDIENTE' THEN ABS(monto) END), 0) AS pendiente
            FROM est_movimientos
            WHERE categoria='EXPENSE' AND tipo='GASTO' AND fecha >= ?
        """, (year_start,)).fetchone()

        # Por cada compra a MSI: cuotas restantes = total de mensualidades
        # de la compra menos las que ya se han visto en algún import: cada
        # una que falta por aparecer sigue siendo un cargo futuro real.
        msi_rows = db.execute("""
            SELECT compra_msi_id,
                   MAX(parcialidad_total) AS total_cuotas,
                   COUNT(DISTINCT parcialidad_num) AS cuotas_vistas,
                   AVG(monto) AS monto_cuota
            FROM est_movimientos
            WHERE compra_msi_id IS NOT NULL
            GROUP BY compra_msi_id
        """).fetchall()

    msi_restante = 0.0
    msi_compras_activas = 0
    for r in msi_rows:
        faltan = (r['total_cuotas'] or 0) - (r['cuotas_vistas'] or 0)
        if faltan > 0:
            msi_restante += faltan * (r['monto_cuota'] or 0)
            msi_compras_activas += 1

    return jsonify({
        'reembolsos_pendientes_count': reembolsos['n'] or 0,
        'reembolsos_pendientes_total': round(reembolsos['total'] or 0, 2),
        'expense_ref': {
            'desde': year_start,
            'n': exp['n'] or 0,
            'total': round(exp['total'] or 0, 2),
            'mio': round((exp['total'] or 0) - (exp['terceros'] or 0), 2),
            'terceros': round(exp['terceros'] or 0, 2),
            'pendiente': round(exp['pendiente'] or 0, 2),
        },
        'msi_compras_activas': msi_compras_activas,
        'msi_restante_total': round(msi_restante, 2),
    })


@estados_bp.route('/api/summary/by-subcategory')
def by_subcategory():
    if not _ok(): return _locked()
    category = request.args.get('category')
    if not category:
        return jsonify({'error': 'category requerida'}), 400
    bank = request.args.get('bank')

    conds  = ["tipo='GASTO'", _PAGO_CATS, "categoria = ?"]
    params = [category]
    months_cond, months_params = _months_condition(request.args)
    if months_cond:
        conds.append(months_cond)
        params.extend(months_params)
    else:
        date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
        date_to   = request.args.get('date_to')
        conds.append("fecha >= ?"); params.append(date_from)
        if date_to:
            conds.append("fecha <= ?"); params.append(date_to)
    if bank:
        conds.append("banco = ?"); params.append(bank)

    with get_db() as db:
        rows = db.execute(f"""
            SELECT COALESCE(NULLIF(subcategoria, ''), 'Sin subcategoría') AS subcategoria,
                   SUM({_MONTO}) AS total,
                   COUNT(*) AS n
            FROM est_movimientos
            WHERE {' AND '.join(conds)}
            GROUP BY subcategoria ORDER BY total DESC
        """, params).fetchall()

    return jsonify([
        {'subcategoria': r['subcategoria'], 'total': round(r['total'] or 0, 2), 'n': r['n']}
        for r in rows
    ])


@estados_bp.route('/api/summary/stats')
def summary_stats():
    if not _ok(): return _locked()
    bank = request.args.get('bank')

    months_cond, months_params = _months_condition(request.args)
    if months_cond:
        conds   = [months_cond]
        params  = list(months_params)
        days    = sum(_days_in_month(m) for m in months_params)
    else:
        date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
        date_to   = request.args.get('date_to')
        conds  = ["fecha >= ?"]
        params = [date_from]
        if date_to:
            conds.append("fecha <= ?"); params.append(date_to)
        d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        d_to   = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else datetime.now().date()
        days   = max((d_to - d_from).days + 1, 1)
    if bank:
        conds.append("banco = ?"); params.append(bank)
    where = " AND ".join(conds)
    days  = max(days, 1)

    with get_db() as db:
        agg = db.execute(f"""
            SELECT
                SUM(CASE WHEN tipo='GASTO'   AND {_PAGO_CATS} THEN {_MONTO} ELSE 0 END) AS total_expense,
                SUM(CASE WHEN tipo='INGRESO' AND {_INGRESO_EXCLUIR_SQL} THEN monto ELSE 0 END) AS total_income,
                COUNT(CASE WHEN tipo='GASTO' AND {_PAGO_CATS} THEN 1 END)              AS tx_count,
                COUNT(CASE WHEN tipo='GASTO' AND {_PAGO_CATS} AND categoria='OTROS' THEN 1 END) AS unclassified
            FROM est_movimientos WHERE {where}
        """, params).fetchone()

        max_row = db.execute(f"""
            SELECT descripcion, monto FROM est_movimientos
            WHERE tipo='GASTO' AND {_PAGO_CATS} AND {where}
            ORDER BY monto DESC LIMIT 1
        """, params).fetchone()

    expense  = agg['total_expense'] or 0
    income   = agg['total_income']  or 0
    tx_count = agg['tx_count']      or 0

    return jsonify({
        'total_expense':  round(expense, 2),
        'total_income':   round(income, 2),
        'balance':        round(income - expense, 2),
        'savings_pct':    round((income - expense) / income * 100, 1) if income > 0 else 0,
        'tx_count':       tx_count,
        'avg_daily':      round(expense / days, 2),
        'avg_per_tx':     round(expense / tx_count, 2) if tx_count > 0 else 0,
        'max_tx_amount':  round(max_row['monto'], 2) if max_row else 0,
        'max_tx_desc':    max_row['descripcion'][:50] if max_row else '',
        'unclassified':   agg['unclassified'] or 0,
        'days':           days,
    })


@estados_bp.route('/api/summary/banks')
def banks_list():
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT banco FROM est_movimientos WHERE banco IS NOT NULL ORDER BY banco"
        ).fetchall()
    return jsonify([r['banco'] for r in rows])


# ── Accounts ──────────────────────────────────────────────────────────────────

@estados_bp.route('/api/accounts')
def get_accounts():
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute(f"""
            SELECT banco,
                   SUM(CASE WHEN tipo='INGRESO' AND {_INGRESO_EXCLUIR_SQL} THEN monto ELSE 0 END) AS income,
                   SUM(CASE WHEN tipo='GASTO' AND {_PAGO_CATS}             THEN {_MONTO} ELSE 0 END) AS expense,
                   COUNT(*) AS tx_count
            FROM est_movimientos
            WHERE banco IS NOT NULL
            GROUP BY banco
            ORDER BY expense DESC
        """).fetchall()

    result = []
    for r in rows:
        meta = BANK_META.get(r['banco'], {"color": "#64748b", "type": "Cuenta"})
        income  = r['income']  or 0
        expense = r['expense'] or 0
        result.append({
            'id':       r['banco'],
            'name':     r['banco'].replace("_", " "),
            'color':    meta['color'],
            'type':     meta['type'],
            'icon':     meta.get('icon', 'credit-card'),
            'income':   round(income, 2),
            'expense':  round(expense, 2),
            'balance':  round(income - expense, 2),
            'tx_count': r['tx_count'],
        })
    return jsonify(result)


# ── Budgets ───────────────────────────────────────────────────────────────────

@estados_bp.route('/api/budgets')
def get_budgets():
    if not _ok(): return _locked()
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")

    with get_db() as db:
        budgets = db.execute(
            "SELECT * FROM est_budgets ORDER BY limite DESC"
        ).fetchall()

        spending = {}
        rows = db.execute(f"""
            SELECT categoria, SUM({_MONTO}) AS total
            FROM est_movimientos
            WHERE tipo='GASTO' AND {_PAGO_CATS} AND fecha >= ?
            GROUP BY categoria
        """, (month_start,)).fetchall()
        for r in rows:
            spending[r['categoria']] = r['total'] or 0

    result = []
    for b in budgets:
        spent = spending.get(b['categoria'], 0)
        result.append({
            'id':       b['id'],
            'categoria': b['categoria'],
            'nombre':   b['nombre'] or b['categoria'],
            'limite':   float(b['limite']),
            'gastado':  round(float(spent), 2),
        })
    return jsonify(result)


@estados_bp.route('/api/budgets', methods=['POST'])
def create_budget():
    if not _ok(): return _locked()
    d = request.json or {}
    with get_db() as db:
        db.execute("""
            INSERT INTO est_budgets (categoria, nombre, limite)
            VALUES (?,?,?)
            ON CONFLICT(categoria) DO UPDATE SET nombre=excluded.nombre, limite=excluded.limite
        """, (d.get('categoria'), d.get('nombre') or d.get('categoria'), safe_float(d.get('limite', 0), min_val=0)))
        db.commit()
    return jsonify({'ok': True}), 201


@estados_bp.route('/api/budgets/<int:bid>', methods=['PATCH'])
def update_budget(bid):
    if not _ok(): return _locked()
    d = request.json or {}
    with get_db() as db:
        if d.get('nombre') is not None:
            db.execute("UPDATE est_budgets SET nombre=? WHERE id=?", (d['nombre'], bid))
        if d.get('limite') is not None:
            db.execute("UPDATE est_budgets SET limite=? WHERE id=?", (safe_float(d['limite'], min_val=0), bid))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/budgets/<int:bid>', methods=['DELETE'])
def delete_budget(bid):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_budgets WHERE id=?", (bid,))
        db.commit()
    return jsonify({'ok': True})


# ── Categories & Keywords ─────────────────────────────────────────────────────

@estados_bp.route('/api/categories')
def list_categories():
    if not _ok(): return _locked()
    from .config import SUBCATEGORIAS
    return jsonify([
        {'categoria': cat, 'subcategorias': subs}
        for cat, subs in SUBCATEGORIAS.items()
    ])


@estados_bp.route('/api/keywords')
def list_keywords():
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute(
            "SELECT keyword, categoria, subcategoria FROM est_keywords ORDER BY keyword"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@estados_bp.route('/api/keywords', methods=['POST'])
def create_keyword():
    if not _ok(): return _locked()
    d = request.json or {}
    kw     = (d.get('keyword') or '').strip().upper()
    cat    = d.get('categoria', 'OTROS')
    subcat = _normalize_subcategoria(cat, d.get('subcategoria', ''))

    if not kw:
        return jsonify({'error': 'keyword requerido'}), 400

    with get_db() as db:
        db.execute("""
            INSERT INTO est_keywords (keyword, categoria, subcategoria)
            VALUES (?,?,?)
            ON CONFLICT(keyword) DO UPDATE SET categoria=excluded.categoria, subcategoria=excluded.subcategoria
        """, (kw, cat, subcat))

        if d.get('apply_to_existing', True):
            result = db.execute("""
                UPDATE est_movimientos
                SET categoria=?, subcategoria=?
                WHERE UPPER(descripcion) LIKE ?
            """, (cat, subcat, f'%{kw}%'))
            updated = result.rowcount if hasattr(result, 'rowcount') else 0
        else:
            updated = 0

        db.commit()

    return jsonify({'ok': True, 'updated_transactions': updated}), 201


@estados_bp.route('/api/keywords/apply-all', methods=['POST'])
def apply_all_keywords():
    """Re-apply every keyword rule to the entire transaction table."""
    if not _ok(): return _locked()
    total_updated = 0
    with get_db() as db:
        kw_rows = db.execute(
            "SELECT keyword, categoria, subcategoria FROM est_keywords"
        ).fetchall()
        for kw_row in kw_rows:
            result = db.execute("""
                UPDATE est_movimientos
                SET categoria=?, subcategoria=?
                WHERE UPPER(descripcion) LIKE ?
            """, (kw_row['categoria'], _normalize_subcategoria(kw_row['categoria'], kw_row['subcategoria']),
                  f'%{kw_row["keyword"]}%'))
            total_updated += result.rowcount if hasattr(result, 'rowcount') else 0
        # Una regla de keyword no distingue tipo -- si alguna quedó
        # aplicada a un ingreso con categoria=EXPENSE, o con VIVIENDA/
        # Renta (ver _corregir_expense_en_ingreso y
        # _corregir_renta_en_ingreso), se corrige aquí igual que en
        # create/update_transaction.
        db.execute("""
            UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
            WHERE categoria='EXPENSE' AND tipo='INGRESO'
        """)
        db.execute("""
            UPDATE est_movimientos SET subcategoria='Aportación renta'
            WHERE categoria='VIVIENDA' AND subcategoria='Renta' AND tipo='INGRESO'
        """)
        _corregir_fusion_gio(db)
        _corregir_far_guad(db)
        _corregir_categorias_legacy(db)
        _corregir_alimentacion_split(db)
        _prest.reafirmar_categorias(db)
        _corregir_servicios_legacy(db)
        _corregir_suscripciones_legacy(db)
        _corregir_steamgames(db)
        _corregir_retiros_renta(db)
        _corregir_spei_invex(db)
        _corregir_zaira_restaurante(db)
        _corregir_walmart_lavadora(db)
        _corregir_didi_delivery(db)
        _corregir_amazon_suscripciones(db)
        _corregir_celular(db)
        _corregir_expense_terceros(db)
        _corregir_pagos_salsa(db)
        _csv0926.aplicar(db)
        _lotes.reafirmar_categorias(db)   # al final: ninguna corrección saca facturas del lote
        db.commit()
    return jsonify({'ok': True, 'updated_transactions': total_updated})


@estados_bp.route('/api/keywords/<path:keyword>', methods=['DELETE'])
def remove_keyword(keyword):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_keywords WHERE keyword=?", (keyword.upper(),))
        db.commit()
    return jsonify({'ok': True})


# ── Loans ─────────────────────────────────────────────────────────────────────

@estados_bp.route('/api/loans')
def loans():
    if not _ok(): return _locked()
    # Dos formas de marcar un préstamo, por compatibilidad:
    #   1. tipo='PRESTAMO'/'COBRO_PRESTAMO' — nunca alcanzable desde el modal
    #      "Editar movimiento" (su selector de Tipo solo ofrece Gasto/Ingreso/
    #      Pago), se dejó por si algún día se expone ahí o se setea por API.
    #   2. categoria='PRESTAMOS' — sí seleccionable en "Categoría" del modal;
    #      la dirección (prestado/cobrado) la da el tipo real (GASTO/INGRESO)
    #      que ya trae el movimiento, sin necesidad de cambiarlo.
    with get_db() as db:
        prestado = db.execute("""
            SELECT SUM(monto) FROM est_movimientos
            WHERE tipo='PRESTAMO' OR (categoria='PRESTAMOS' AND tipo='GASTO')
        """).fetchone()[0] or 0
        cobrado = db.execute("""
            SELECT SUM(monto) FROM est_movimientos
            WHERE tipo='COBRO_PRESTAMO' OR (categoria='PRESTAMOS' AND tipo='INGRESO')
        """).fetchone()[0] or 0
        detalle = db.execute("""
            SELECT descripcion, tipo, SUM(monto) AS total, COUNT(*) AS n
            FROM est_movimientos
            WHERE tipo IN ('PRESTAMO','COBRO_PRESTAMO') OR categoria='PRESTAMOS'
            GROUP BY descripcion, tipo
            ORDER BY total DESC
        """).fetchall()

    return jsonify({
        'prestado':  round(float(prestado), 2),
        'cobrado':   round(float(cobrado), 2),
        'pendiente': round(float(prestado) - float(cobrado), 2),
        'detalle':   [dict(r) for r in detalle],
    })


# ── Préstamos por cobrar (seguimiento por persona) ────────────────────────────
# /api/loans (arriba) se queda igual: es el resumen agregado que usa Resumen.
# Esto es el seguimiento detallado de la pestaña «Por cobrar»; la lógica vive
# en prestamos.py porque la Radiografía (budget.py) también la usa.


def _mov(db, mov_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (mov_id,)).fetchone()


@estados_bp.route('/api/prestamos')
def prestamos_resumen():
    if not _ok(): return _locked()
    with get_db() as db:
        return jsonify(_prest.resumen(db))


@estados_bp.route('/api/prestamos/candidatos')
def prestamos_candidatos():
    if not _ok(): return _locked()
    with get_db() as db:
        return jsonify(_prest.candidatos(db))


@estados_bp.route('/api/prestamos/duplicados')
def prestamos_duplicados():
    """Solo lectura: grupos de movimientos de préstamo con mismo día y monto,
    para que el usuario confirme antes de borrar nada (desde Movimientos)."""
    if not _ok(): return _locked()
    with get_db() as db:
        return jsonify(_prest.duplicados(db))


@estados_bp.route('/api/prestamos/export.csv')
def prestamos_csv():
    """Movimientos de préstamo con persona/estado para clasificarlos fuera
    de la app; los que falta registrar llevan Persona vacía."""
    if not _ok(): return _locked()
    with get_db() as db:
        rows = _prest.filas_csv(db)
    return csv_response(['ID', 'Fecha', 'Tipo', 'Descripción', 'Monto', 'Banco',
                         'Persona', 'Estado', 'Pendiente'], rows, f"prestamos_{today_str()}.csv")


@estados_bp.route('/api/prestamos', methods=['POST'])
def prestamos_crear():
    """Crea un préstamo desde el movimiento con el que se prestó. El
    movimiento queda como PRESTAMOS/GASTO (fuera del gasto en todos lados)."""
    if not _ok(): return _locked()
    d = request.get_json(silent=True) or {}
    persona = clean_str(d.get('persona'), 80)
    if not persona:
        return jsonify({'error': 'Indica a quién le prestaste.'}), 400
    try:
        mov_id = int(d.get('movimiento_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Falta el movimiento del préstamo.'}), 400
    with get_db() as db:
        m = _mov(db, mov_id)
        if not m or m['tipo'] != 'GASTO':
            return jsonify({'error': 'El movimiento no existe o no es un gasto.'}), 400
        if db.execute("SELECT 1 FROM est_prestamos WHERE movimiento_id=?", (mov_id,)).fetchone():
            return jsonify({'error': 'Ese movimiento ya tiene un préstamo.'}), 409
        db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='Prestado' WHERE id=?", (mov_id,))
        pid = db.execute(
            "INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at) "
            "VALUES (?, 'OTORGADO', ?, ?, ?, ?, ?)",
            (persona, abs(float(m['monto'])), m['fecha'], clean_str(d.get('notas'), 300), mov_id, _prest.ahora())
        ).lastrowid
        db.commit()
    return jsonify({'ok': True, 'id': pid}), 201


@estados_bp.route('/api/prestamos/<int:pid>', methods=['PATCH'])
def prestamos_editar(pid):
    """Persona/notas, y marcar o desmarcar «Perdido» (guarda la fecha de hoy)."""
    if not _ok(): return _locked()
    d = request.get_json(silent=True) or {}
    with get_db() as db:
        if not db.execute("SELECT 1 FROM est_prestamos WHERE id=?", (pid,)).fetchone():
            return jsonify({'error': 'Préstamo no encontrado.'}), 404
        if 'persona' in d:
            persona = clean_str(d.get('persona'), 80)
            if not persona:
                return jsonify({'error': 'La persona no puede quedar vacía.'}), 400
            db.execute("UPDATE est_prestamos SET contraparte=? WHERE id=?", (persona, pid))
        if 'notas' in d:
            db.execute("UPDATE est_prestamos SET notas=? WHERE id=?", (clean_str(d.get('notas'), 300), pid))
        if 'perdido' in d:
            db.execute("UPDATE est_prestamos SET perdido_fecha=? WHERE id=?",
                       (today_str() if d.get('perdido') else None, pid))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/prestamos/<int:pid>', methods=['DELETE'])
def prestamos_borrar(pid):
    """Borra el registro del préstamo y sus ligas; los movimientos bancarios
    no se tocan."""
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_prestamo_devoluciones WHERE prestamo_id=?", (pid,))
        db.execute("DELETE FROM est_prestamos WHERE id=?", (pid,))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/prestamos/<int:pid>/devoluciones', methods=['POST'])
def prestamos_ligar(pid):
    """Liga un ingreso como devolución: queda como PRESTAMOS/INGRESO, así que
    deja de contar como ingreso y solo baja el pendiente."""
    if not _ok(): return _locked()
    d = request.get_json(silent=True) or {}
    try:
        mov_id = int(d.get('movimiento_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Falta el movimiento de la devolución.'}), 400
    with get_db() as db:
        if not db.execute("SELECT 1 FROM est_prestamos WHERE id=?", (pid,)).fetchone():
            return jsonify({'error': 'Préstamo no encontrado.'}), 404
        m = _mov(db, mov_id)
        if not m or m['tipo'] != 'INGRESO':
            return jsonify({'error': 'El movimiento no existe o no es un ingreso.'}), 400
        if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (mov_id,)).fetchone():
            return jsonify({'error': 'Ese ingreso ya está ligado a un préstamo.'}), 409
        db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='' WHERE id=?", (mov_id,))
        db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (pid, mov_id, _prest.ahora()))
        db.commit()
    return jsonify({'ok': True}), 201


@estados_bp.route('/api/prestamos/<int:pid>/devoluciones/<int:mov_id>', methods=['DELETE'])
def prestamos_desligar(pid, mov_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_prestamo_devoluciones WHERE prestamo_id=? AND movimiento_id=?", (pid, mov_id))
        db.commit()
    return jsonify({'ok': True})


# ── Expense: conciliación por lotes (pestaña «Expense») ──────────────────────
# Varias facturas se suben juntas y la empresa paga un depósito por el lote;
# la lógica vive en expense_lotes.py. get_db() hace commit al salir del
# `with` (y _HybridConn no tiene rollback), así que todo se valida ANTES de
# escribir: un error nunca deja un lote a medias.

def _ids(v) -> list:
    try:
        return sorted({int(x) for x in (v or [])})
    except (TypeError, ValueError):
        return []


def _lote_existe(db, lid) -> bool:
    return bool(db.execute("SELECT 1 FROM est_expense_lotes WHERE id=?", (lid,)).fetchone())


def _error_gastos(db, ids) -> str | None:
    for mid in ids:
        m = _mov(db, mid)
        if not m or m['tipo'] != 'GASTO' or m['categoria'] != 'EXPENSE':
            return f'El movimiento {mid} no es un gasto EXPENSE.'
        if db.execute("SELECT 1 FROM est_expense_lote_gastos WHERE movimiento_id=?", (mid,)).fetchone():
            return f'La factura «{m["descripcion"]}» ya está en otro lote.'
    return None


def _error_deposito(db, mid) -> str | None:
    m = _mov(db, mid)
    if not m or m['tipo'] != 'INGRESO':
        return 'El depósito no existe o no es un ingreso.'
    if db.execute("SELECT 1 FROM est_expense_lote_depositos WHERE movimiento_id=?", (mid,)).fetchone():
        return 'Ese depósito ya está ligado a un lote.'
    if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (mid,)).fetchone():
        return 'Ese ingreso está ligado como devolución de un préstamo.'
    return None


def _insertar_gastos(db, lid, ids):
    for mid in ids:
        db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, mid, _lotes.ahora()))


def _insertar_deposito(db, lid, mid):
    db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (mid,))
    db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
               (lid, mid, _lotes.ahora()))


@estados_bp.route('/api/expense/lotes')
def expense_lotes():
    if not _ok(): return _locked()
    with get_db() as db:
        return jsonify(_lotes.resumen(db))


@estados_bp.route('/api/expense/candidatos')
def expense_candidatos():
    if not _ok(): return _locked()
    with get_db() as db:
        return jsonify(_lotes.candidatos(db))


@estados_bp.route('/api/expense/export.csv')
def expense_csv():
    if not _ok(): return _locked()
    with get_db() as db:
        rows = _lotes.filas_csv(db)
    return csv_response(['Lote', 'Estado', 'Tipo', 'Fecha', 'Descripción', 'Monto', 'Nota'],
                        rows, f"expense_lotes_{today_str()}.csv")


@estados_bp.route('/api/expense/lotes', methods=['POST'])
def expense_lote_crear():
    """Crea un lote con sus facturas (gasto_ids) y, opcional, sus depósitos."""
    if not _ok(): return _locked()
    d = request.get_json(silent=True) or {}
    nombre = clean_str(d.get('nombre'), 80)
    gasto_ids, deposito_ids = _ids(d.get('gasto_ids')), _ids(d.get('deposito_ids'))
    if not nombre:
        return jsonify({'error': 'Ponle un nombre al lote (ej. «Facturas mayo»).'}), 400
    if not gasto_ids:
        return jsonify({'error': 'Elige al menos una factura.'}), 400
    with get_db() as db:
        err = _error_gastos(db, gasto_ids) or next(filter(None, (_error_deposito(db, m) for m in deposito_ids)), None)
        if err:
            return jsonify({'error': err}), 400
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (nombre, clean_str(d.get('notas'), 300), _lotes.ahora())).lastrowid
        _insertar_gastos(db, lid, gasto_ids)
        for mid in deposito_ids:
            _insertar_deposito(db, lid, mid)
        _lotes.sincronizar(db, lid)
        db.commit()
    return jsonify({'ok': True, 'id': lid}), 201


@estados_bp.route('/api/expense/lotes/<int:lid>', methods=['PATCH'])
def expense_lote_editar(lid):
    if not _ok(): return _locked()
    d = request.get_json(silent=True) or {}
    with get_db() as db:
        if not _lote_existe(db, lid):
            return jsonify({'error': 'Lote no encontrado.'}), 404
        if 'nombre' in d:
            nombre = clean_str(d.get('nombre'), 80)
            if not nombre:
                return jsonify({'error': 'El nombre no puede quedar vacío.'}), 400
            db.execute("UPDATE est_expense_lotes SET nombre=? WHERE id=?", (nombre, lid))
        if 'notas' in d:
            db.execute("UPDATE est_expense_lotes SET notas=? WHERE id=?", (clean_str(d.get('notas'), 300), lid))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/expense/lotes/<int:lid>', methods=['DELETE'])
def expense_lote_borrar(lid):
    """Borra el lote y sus ligas; los movimientos bancarios no se tocan."""
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lote_depositos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lotes WHERE id=?", (lid,))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/expense/lotes/<int:lid>/gastos', methods=['POST'])
def expense_lote_agregar_gastos(lid):
    if not _ok(): return _locked()
    ids = _ids((request.get_json(silent=True) or {}).get('movimiento_ids'))
    if not ids:
        return jsonify({'error': 'Elige al menos una factura.'}), 400
    with get_db() as db:
        if not _lote_existe(db, lid):
            return jsonify({'error': 'Lote no encontrado.'}), 404
        err = _error_gastos(db, ids)
        if err:
            return jsonify({'error': err}), 400
        _insertar_gastos(db, lid, ids)
        _lotes.sincronizar(db, lid)
        db.commit()
    return jsonify({'ok': True}), 201


@estados_bp.route('/api/expense/lotes/<int:lid>/gastos/<int:mov_id>', methods=['DELETE'])
def expense_lote_quitar_gasto(lid, mov_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_expense_lote_gastos WHERE lote_id=? AND movimiento_id=?", (lid, mov_id))
        _lotes.sincronizar(db, lid)
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/expense/lotes/<int:lid>/depositos', methods=['POST'])
def expense_lote_ligar_deposito(lid):
    """Liga el depósito de la empresa: queda como FINANZAS/Reembolsable (no
    cuenta como ingreso) y, si cubre el lote, sus facturas pasan a Pagado."""
    if not _ok(): return _locked()
    try:
        mid = int((request.get_json(silent=True) or {}).get('movimiento_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Falta el depósito.'}), 400
    with get_db() as db:
        if not _lote_existe(db, lid):
            return jsonify({'error': 'Lote no encontrado.'}), 404
        err = _error_deposito(db, mid)
        if err:
            return jsonify({'error': err}), 400
        _insertar_deposito(db, lid, mid)
        _lotes.sincronizar(db, lid)
        db.commit()
    return jsonify({'ok': True}), 201


@estados_bp.route('/api/expense/lotes/<int:lid>/depositos/<int:mov_id>', methods=['DELETE'])
def expense_lote_quitar_deposito(lid, mov_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_expense_lote_depositos WHERE lote_id=? AND movimiento_id=?", (lid, mov_id))
        _lotes.sincronizar(db, lid)
        db.commit()
    return jsonify({'ok': True})


# ── Reglas automáticas al importar (Sprint 3 original: "Reglas automáticas
#    al importar" — distinto de los sprints de taxonomía ya aplicados) ────────
#
# Antes, cada parser (parsers/*.py) decidía por su cuenta, con su propia
# lista payment_keywords, si una descripción era "MOVIMIENTO_INTERNO"
# (pago de tarjeta de crédito, no un gasto real) — lo que dejaba
# inconsistencias entre bancos/formatos (ver migración one-time
# finanzas_taxonomia_2026_09_sprint1, que tuvo que corregirlo
# retroactivamente). Esta regla corre en cada import, sobre las filas
# recién insertadas (`new_ids`), sin importar qué parser las produjo —
# nunca toca filas fuera de ese conjunto, para no reescribir clasificaciones
# manuales ni las de sprints anteriores.
_MOVIMIENTO_INTERNO_KW = (
    "PAGO TARJETA DE CREDITO", "PAGO INTERBANCARIO", "PAGOS INTERBANCARIOS",
    "PAGO TDC", "PAGO GRACIAS", "PAGO POR SPEI",
)


def _es_movimiento_interno(desc_upper: str) -> bool:
    """HSBC e INVEX en esta app son exclusivamente los bancos emisores de
    tarjeta de crédito (ver BANK_META) -- un "SPEI ENVIADO" hacia
    cualquiera de los dos SIEMPRE es un pago para abonar a esa TDC, nunca
    un gasto real (la compra real ya se contó cuando se importó el cargo
    en la TDC). Se agregó tras auditar filas históricas donde este patrón
    (y "PAGO TDC"/"PAGO GRACIAS"/"PAGO POR SPEI", las distintas formas en
    que BBVA/HSBC/INVEX describen el abono) seguía cayendo en
    FINANZAS/Pago servicios en vez de MOVIMIENTO_INTERNO/PAGO_TDC."""
    if any(kw in desc_upper for kw in _MOVIMIENTO_INTERNO_KW):
        return True
    if "SPEI" in desc_upper and "TDC" in desc_upper:
        return True
    return "SPEI ENVIADO" in desc_upper and ("HSBC" in desc_upper or "INVEX" in desc_upper)


def _descartar_ingresos_en_credito(db, ids: list) -> int:
    """«Nada que ingrese va a crédito» (regla del usuario): una entrada de
    dinero en BBVA_TDC que no es pago a la tarjeta y tiene gemela en BBVA_DEB
    (mismo día y monto) es una línea del estado de débito importada como
    crédito -- pasó con 18 movimientos jun-ago 2026. Se borra la de crédito,
    sin importar cuál de las dos se importó primero. Solo mira las filas
    recién importadas (`ids`) y nunca toca filas ligadas a lotes o préstamos."""
    if not ids:
        return 0
    ph = ','.join('?' * len(ids))
    ligadas = """SELECT movimiento_id FROM est_expense_lote_gastos UNION SELECT movimiento_id FROM est_expense_lote_depositos
                 UNION SELECT movimiento_id FROM est_prestamo_devoluciones
                 UNION SELECT movimiento_id FROM est_prestamos WHERE movimiento_id IS NOT NULL"""
    rows = db.execute(f"""
        SELECT DISTINCT c.id FROM est_movimientos c
        JOIN est_movimientos d ON d.banco='BBVA_DEB' AND d.tipo='INGRESO'
             AND substr(d.fecha,1,10)=substr(c.fecha,1,10) AND ABS(ABS(d.monto)-ABS(c.monto)) < 0.005
        WHERE c.banco='BBVA_TDC' AND c.tipo IN ('INGRESO','PAGO') AND c.monto != 0
          AND c.categoria != 'PAGO_TDC'
          AND (c.id IN ({ph}) OR d.id IN ({ph}))
          AND c.id NOT IN ({ligadas})
    """, ids + ids).fetchall()
    for r in rows:
        db.execute("DELETE FROM est_movimientos WHERE id=?", (r['id'],))
    return len(rows)


def _unify_movimiento_interno(db, ids: list) -> int:
    """Reclasifica, entre las filas recién insertadas (`ids`), las que en
    realidad son pago de tarjeta de crédito / SPEI hacia la TDC — dinero
    moviéndose entre mis propias cuentas, no un gasto real. Devuelve cuántas
    se reclasificaron."""
    if not ids:
        return 0
    placeholders = ','.join('?' * len(ids))
    rows = db.execute(
        f"SELECT id, descripcion FROM est_movimientos WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    updated = 0
    for r in rows:
        if _es_movimiento_interno((r['descripcion'] or '').upper()):
            db.execute(
                "UPDATE est_movimientos SET categoria='PAGO_TDC', subcategoria='', "
                "tipo='MOVIMIENTO_INTERNO' WHERE id=?",
                (r['id'],),
            )
            updated += 1
    if updated:
        db.commit()
    return updated


def _detectar_avisos_msi(db) -> list:
    """Revisa TODOS los grupos de compra_msi_id en la DB (no solo el import
    actual) en busca de señales de doble conteo de una compra a meses sin
    intereses: más mensualidades distintas de las que la compra debería
    tener (parcialidad_total), o el mismo número de mensualidad repetido
    dentro del mismo grupo. Solo avisa — nunca corrige ni borra nada solo,
    queda para revisión manual."""
    grupos = db.execute("""
        SELECT compra_msi_id, descripcion,
               COUNT(*) AS n_filas,
               COUNT(DISTINCT parcialidad_num) AS n_distintas,
               MAX(parcialidad_total) AS total_esperado
        FROM est_movimientos
        WHERE compra_msi_id IS NOT NULL
        GROUP BY compra_msi_id
    """).fetchall()
    avisos = []
    for g in grupos:
        if g['n_filas'] > g['n_distintas']:
            avisos.append({
                'compra_msi_id': g['compra_msi_id'],
                'descripcion': g['descripcion'],
                'tipo': 'PARCIALIDAD_REPETIDA',
                'detalle': (f"{g['n_filas']} filas pero solo {g['n_distintas']} número(s) de "
                            "mensualidad distintos — posible doble conteo."),
            })
        elif g['total_esperado'] and g['n_distintas'] > g['total_esperado']:
            avisos.append({
                'compra_msi_id': g['compra_msi_id'],
                'descripcion': g['descripcion'],
                'tipo': 'MAS_MENSUALIDADES_DE_LAS_ESPERADAS',
                'detalle': (f"{g['n_distintas']} mensualidades distintas registradas, pero la "
                            f"compra es a {g['total_esperado']} — revisar."),
            })
    return avisos


# Merchants/menciones de Tabasco — solo para SUGERIR (nunca asignar solo) un
# viaje "familia en Tabasco" por rango de fechas. "VSA " con espacio final
# evita falsos positivos con palabras que solo contienen "vsa" como substring.
_TABASCO_KW = ("VILLAHERMOSA", "VSA ", "TABASCO")


def _sugerir_viaje_tabasco(db, ids: list) -> list:
    """Para gastos recién importados que mencionan Villahermosa/VSA/Tabasco
    y que aún no tienen viaje asignado, sugiere (nunca asigna solo) un viaje
    existente marcado como FAMILIA_TABASCO (o cuyo destino/nombre lo
    mencione) cuyo rango de fechas cubra la transacción."""
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    rows = db.execute(
        f"""SELECT id, fecha, descripcion, monto FROM est_movimientos
            WHERE id IN ({placeholders}) AND tipo='GASTO' AND viaje_id IS NULL""",
        ids,
    ).fetchall()
    candidatos = [r for r in rows if any(kw in (r['descripcion'] or '').upper() for kw in _TABASCO_KW)]
    if not candidatos:
        return []
    viajes = db.execute("""
        SELECT id, nombre, fecha_inicio, fecha_fin FROM viajes
        WHERE tipo_viaje='FAMILIA_TABASCO'
           OR UPPER(destino) LIKE '%TABASCO%' OR UPPER(destino) LIKE '%VILLAHERMOSA%'
           OR UPPER(nombre) LIKE '%TABASCO%' OR UPPER(nombre) LIKE '%VILLAHERMOSA%'
    """).fetchall()
    if not viajes:
        return []
    sugerencias = []
    for tx in candidatos:
        for v in viajes:
            if v['fecha_inicio'] <= tx['fecha'] <= v['fecha_fin']:
                sugerencias.append({
                    'id': tx['id'], 'descripcion': tx['descripcion'],
                    'monto': tx['monto'], 'fecha': tx['fecha'],
                    'viaje_id': v['id'], 'viaje_nombre': v['nombre'],
                })
                break
    return sugerencias


def _sugerir_reembolsos(db, ids: list) -> list:
    """Para depósitos/ingresos recién importados, sugiere (nunca marca solo)
    conciliarlos contra gastos EXPENSE pendientes de reembolso
    (estatus_reembolso='PENDIENTE') cuyo monto coincida dentro de ±1%. La
    confirmación real la hace el usuario vía /api/expenses/<id>/conciliar."""
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    depositos = db.execute(
        f"""SELECT id, fecha, descripcion, monto FROM est_movimientos
            WHERE id IN ({placeholders}) AND tipo='INGRESO'""",
        ids,
    ).fetchall()
    if not depositos:
        return []
    pendientes = db.execute("""
        SELECT id, fecha, descripcion, monto FROM est_movimientos
        WHERE categoria='EXPENSE' AND estatus_reembolso='PENDIENTE'
    """).fetchall()
    if not pendientes:
        return []
    sugerencias = []
    for dep in depositos:
        for exp in pendientes:
            monto_exp = abs(exp['monto'])
            if monto_exp == 0:
                continue
            if abs(dep['monto'] - monto_exp) <= monto_exp * 0.01:
                sugerencias.append({
                    'deposito_id': dep['id'], 'deposito_descripcion': dep['descripcion'],
                    'deposito_monto': dep['monto'], 'deposito_fecha': dep['fecha'],
                    'expense_id': exp['id'], 'expense_descripcion': exp['descripcion'],
                    'expense_monto': exp['monto'],
                })
    return sugerencias


def _detectar_posibles_duplicados(db, ids: list) -> list:
    """Bug real confirmado por el usuario: el mismo movimiento real
    (mismo día, mismo monto) se coló dos veces con descripción Y tipo
    distintos (una vez tipo=GASTO por una mala detección de banco, luego
    reclasificado a mano a INGRESO) — el dedup de /api/upload por
    (fecha, monto, tipo) nunca lo iba a atrapar porque el tipo también
    difería en el momento del import.

    Esta función SOLO avisa -- nunca bloquea el import ni borra nada --
    buscando, para cada fila recién insertada, otras filas ya existentes
    con la misma fecha y el mismo monto (redondeado a centavos) SIN
    importar el tipo. Puede haber falsos positivos legítimos (dos compras
    reales de mismo monto el mismo día), así que queda para que el
    usuario decida con /admin/audit-duplicados o borrando la fila
    sobrante desde la UI."""
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    nuevas = db.execute(
        f"""SELECT id, fecha, descripcion, monto, tipo, banco FROM est_movimientos
            WHERE id IN ({placeholders}) AND monto != 0""",
        ids,
    ).fetchall()
    if not nuevas:
        return []
    avisos = []
    for tx in nuevas:
        otras = db.execute(
            """SELECT id, descripcion, tipo, banco FROM est_movimientos
               WHERE fecha=? AND ROUND(monto,2)=ROUND(?,2) AND id != ?""",
            (tx['fecha'], tx['monto'], tx['id']),
        ).fetchall()
        for otra in otras:
            avisos.append({
                'id': tx['id'], 'descripcion': tx['descripcion'], 'monto': tx['monto'],
                'fecha': tx['fecha'], 'banco': tx['banco'], 'tipo': tx['tipo'],
                'posible_duplicado_id': otra['id'], 'posible_duplicado_descripcion': otra['descripcion'],
                'posible_duplicado_tipo': otra['tipo'], 'posible_duplicado_banco': otra['banco'],
            })
    return avisos


def _auto_clasificar_nomina(db, ids: list) -> int:
    """A petición explícita del usuario: un ingreso que menciona FIBRA
    HOTELERA/NOMINA y cuyo monto está en el rango típico de la quincena/
    mensualidad se clasifica como categoria=NOMINA, subcategoria='Pago
    nominal'. (Ajustado: la primera versión también exigía que la fecha
    cayera en los días 1-3/29-31 del mes, pero un caso real de nómina
    confirmado llegó el día 13 -- el día de pago varía según cuándo
    procesa el banco, así que se quitó esa condición y se dejó solo
    texto+monto.) El rango de monto empezó siendo $10,000-$12,000, pero
    el sueldo de 2025 (antes de un aumento) caía entre $9,000 y $11,000
    -- se amplió a $9,000-$12,000 para cubrir ambos años con una sola
    regla. Solo corre sobre las filas recién insertadas (`ids`) -- para
    el histórico existente ver las migraciones finanzas_nomina_pago_
    nominal_v2_2026_09 (rango original) y finanzas_nomina_pago_nominal_
    v3_2026_09 (rango ampliado a 2025) en database.py."""
    if not ids:
        return 0
    placeholders = ','.join('?' * len(ids))
    cur = db.execute(f"""
        UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Pago nominal'
        WHERE id IN ({placeholders})
          AND tipo='INGRESO'
          AND (UPPER(descripcion) LIKE '%FIBRA HOTELERA%'
               OR UPPER(descripcion) LIKE '%NOMINA%'
               OR UPPER(descripcion) LIKE '%NÓMINA%')
          AND monto BETWEEN 9000 AND 12000
    """, ids)
    return cur.rowcount


@estados_bp.route('/api/expenses/<int:mov_id>/conciliar', methods=['POST'])
def conciliar_expense(mov_id):
    """Confirma una sugerencia de _sugerir_reembolsos: marca un EXPENSE
    pendiente como PAGADO. Nunca ocurre solo al importar — requiere esta
    confirmación explícita del usuario."""
    if not _ok(): return _locked()
    d = request.get_json(silent=True) or {}
    fecha_reembolso = d.get('fecha_reembolso') or today_str()
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM est_movimientos WHERE id=? AND categoria='EXPENSE'",
            (mov_id,),
        ).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Expense no encontrado'}), 404
        db.execute(
            "UPDATE est_movimientos SET estatus_reembolso='PAGADO', fecha_reembolso=? WHERE id=?",
            (fecha_reembolso, mov_id),
        )
        db.commit()
    return jsonify({'ok': True})


# ── Upload ────────────────────────────────────────────────────────────────────

@estados_bp.route('/api/upload', methods=['POST'])
def upload_file():
    if not _ok(): return _locked()

    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400

    suffix = Path(file.filename or 'file.pdf').suffix.lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        from .parsers import parse_file, detect_bank
        bank       = detect_bank(tmp_path)
        movimientos = parse_file(tmp_path)

        if not movimientos:
            return jsonify({'ok': False, 'error': 'No se encontraron transacciones', 'bank': bank})

        # Dedup and insert
        # Key = (fecha, monto, tipo) — NO incluye banco: el mismo movimiento
        # real puede importarse una vez desde un PDF (ej. banco=BBVA_DEB) y
        # otra desde un CSV/Excel de la misma cuenta que detect_bank() etiqueta
        # distinto (ej. BBVA_TDC), con descripciones ligeramente distintas
        # entre parsers (referencia numérica presente/ausente, etc.) — incluir
        # banco en la key dejaba pasar esos duplicados. Se mantiene tipo para
        # no confundir un ingreso y un gasto del mismo monto en el mismo día
        # (caso legítimo). Solo se aplica cuando monto > 0; montos en cero se
        # insertan siempre.
        inserted       = 0
        skipped        = 0
        dedup_conflict = 0  # chocó con idx_est_mov_dedup (fecha, descripcion) aunque
                             # el dedup por (fecha, monto, tipo) lo había dejado pasar
        with get_db() as db:
            existing = set()
            for r in db.execute(
                "SELECT fecha, monto, tipo FROM est_movimientos WHERE monto > 0"
            ).fetchall():
                # Redondeado a centavos: dos parsers pueden calcular el mismo
                # monto por caminos distintos (división vs. parseo directo
                # del string) y no siempre caen en el mismo float exacto —
                # comparar con round() evita que ese detalle deje pasar un
                # duplicado real.
                existing.add((r['fecha'], round(float(r['monto']), 2), r['tipo']))

            # Blindaje adicional (auditoría "AUDITA PORQUE HAY MONTOS Y DIAS
            # REPETIDOS..."): el mismo SPEI recibido / depósito de tercero
            # real, importado una vez como BBVA_DEB y otra como BBVA_TDC/
            # HSBC/INVEX, a veces llega con tipo distinto entre ambos lados
            # (uno como INGRESO, el otro como PAGO/GASTO según cómo lo lea
            # el parser del banco emisor) -- el dedup de arriba, que exige
            # tipo igual, no lo atrapa. Para este patrón específico (el
            # usuario confirmó: "estos ingresos nunca van a TDC, siempre son
            # depositos en debito") se ignora tipo: cualquier fila nueva que
            # NO sea BBVA_DEB, con "SPEI RECIBIDO" o "DEPOSITO DE TERCERO" en
            # la descripción, se descarta si ya existe una fila BBVA_DEB con
            # el mismo día y monto (sin importar su tipo).
            existing_deb_spei = set()
            for r in db.execute("""
                SELECT fecha, monto FROM est_movimientos
                WHERE banco='BBVA_DEB'
                  AND (UPPER(descripcion) LIKE '%SPEI RECIBIDO%'
                       OR UPPER(descripcion) LIKE '%DEPOSITO DE TERCERO%')
            """).fetchall():
                existing_deb_spei.add((r['fecha'], round(float(r['monto']), 2)))

            # También rastreamos depósitos/SPEIs nuevos para el response
            review_needed = []
            new_ids = []  # ids recién insertados — para las reglas automáticas de abajo

            for m in movimientos:
                m_banco = m.get('banco', bank) or bank
                m_monto = float(m['monto'])
                m_desc_upper = (m['descripcion'] or '').upper()
                # Dedup solo aplica a montos > 0
                key = (m['fecha'], round(m_monto, 2), m['tipo'])
                if m_monto > 0 and key in existing:
                    skipped += 1
                    continue
                if (m_monto > 0 and m_banco != 'BBVA_DEB'
                        and ('SPEI RECIBIDO' in m_desc_upper or 'DEPOSITO DE TERCERO' in m_desc_upper)
                        and (m['fecha'], round(m_monto, 2)) in existing_deb_spei):
                    skipped += 1
                    continue
                if m_monto > 0:
                    existing.add(key)
                    if m_banco == 'BBVA_DEB' and ('SPEI RECIBIDO' in m_desc_upper or 'DEPOSITO DE TERCERO' in m_desc_upper):
                        existing_deb_spei.add((m['fecha'], round(m_monto, 2)))
                cur = db.execute("""
                    INSERT OR IGNORE INTO est_movimientos
                    (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo,
                     parcialidad_num, parcialidad_total, compra_msi_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    m['fecha'], m.get('fecha_cargo', m['fecha']),
                    m['descripcion'], m['monto'],
                    m_banco, m.get('periodo', ''),
                    m['categoria'], m.get('subcategoria', ''), m['tipo'],
                    m.get('parcialidad_num'), m.get('parcialidad_total'), m.get('compra_msi_id'),
                ))
                if not cur.rowcount:
                    # Pasó el dedup de (fecha, monto, tipo) pero chocó con el índice
                    # UNIQUE(fecha, descripcion) — es una transacción real distinta
                    # (mismo día, misma descripción del banco, otro monto) que NO
                    # se guardó. No la contamos como "inserted".
                    dedup_conflict += 1
                    continue
                inserted += 1
                new_ids.append(cur.lastrowid)
                # Marcar DEPOSITO / SPEI_RECIBIDO como pendientes de clasificar
                if m['tipo'] == 'INGRESO' and m['categoria'] in ('DEPOSITO', 'SPEI_RECIBIDO'):
                    review_needed.append({
                        'fecha': m['fecha'],
                        'descripcion': m['descripcion'],
                        'monto': m['monto'],
                        'categoria': m['categoria'],
                    })

            # Apply all user-defined keywords to newly imported records
            kw_rows = db.execute(
                "SELECT keyword, categoria, subcategoria FROM est_keywords"
            ).fetchall()
            for kw_row in kw_rows:
                db.execute("""
                    UPDATE est_movimientos
                    SET categoria=?, subcategoria=?
                    WHERE UPPER(descripcion) LIKE ?
                """, (kw_row['categoria'], _normalize_subcategoria(kw_row['categoria'], kw_row['subcategoria']),
                      f'%{kw_row["keyword"]}%'))

            # Una regla de keyword no distingue tipo -- si alguna quedó
            # aplicada a un ingreso con categoria=EXPENSE, o con VIVIENDA/
            # Renta (ver _corregir_expense_en_ingreso y
            # _corregir_renta_en_ingreso), se corrige aquí igual que en
            # create/update_transaction y apply_all_keywords.
            db.execute("""
                UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                WHERE categoria='EXPENSE' AND tipo='INGRESO'
            """)
            db.execute("""
                UPDATE est_movimientos SET subcategoria='Aportación renta'
                WHERE categoria='VIVIENDA' AND subcategoria='Renta' AND tipo='INGRESO'
            """)
            _corregir_fusion_gio(db)
            _corregir_far_guad(db)
            _corregir_categorias_legacy(db)
            _corregir_alimentacion_split(db)
            _prest.reafirmar_categorias(db)
            _corregir_servicios_legacy(db)
            _corregir_suscripciones_legacy(db)
            _corregir_steamgames(db)
            _corregir_retiros_renta(db)
            _corregir_spei_invex(db)
            _corregir_zaira_restaurante(db)
            _corregir_walmart_lavadora(db)
            _corregir_didi_delivery(db)
            _corregir_amazon_suscripciones(db)
            _corregir_celular(db)
            _corregir_expense_terceros(db)
            _corregir_pagos_salsa(db)
            _csv0926.aplicar(db)
            _lotes.reafirmar_categorias(db)   # al final: ninguna corrección saca facturas del lote

            # ── Post-proceso inversiones ──────────────────────────────────────
            # Cuando categoria='INVERSION', elevar tipo y asignar plataforma+dirección.
            # Plataformas detectadas por keyword en descripción. "STP" se agregó
            # tras confirmar con datos reales que es el riel de pago que usa este
            # usuario para sus aportaciones a CETESDirecto ("SPEI ENVIADO STP").
            _PLAT_KW = [
                ('GBM',   'GBM'),
                ('FINSUS','FINSUS'),   # antes que CETES/STP: el nombre explícito gana
                ('INVEX', 'INVEX'),
                ('CETES', 'CETESDIRECTO'),
                ('CETES', 'NAFIN'),
                ('CETES', 'STP'),
                ('CRYPTO','BITSO'),
                ('CRYPTO','COINBASE'),
                ('FIBRA', 'FIBRA'),
            ]
            # Patrones que NUNCA son inversión aunque categoria='INVERSION':
            # son pagos/transferencias que contienen el nombre de la plataforma
            # en la descripción pero no son depósitos reales. Solo se aplica
            # cuando NO se detectó ninguna plataforma de inversión conocida --
            # antes esto se revisaba primero y excluía a ciegas cualquier "SPEI
            # ENVIADO" hacia GBM/CETESDirecto/STP (una aportación real, dinero
            # saliendo de la cuenta para invertir) como si fuera un pago de
            # TDC, aunque sí trajera una plataforma reconocida.
            _NOT_INVERSION = ('SPEI ENVIADO', 'PAGO TDC', 'PAGO TARJETA',
                               'PAGO CUENTA DE TERCERO', 'CARGO POR TRASPASO')

            inv_candidates = db.execute("""
                SELECT id, descripcion, tipo
                FROM est_movimientos
                WHERE categoria='INVERSION' AND tipo IN ('INGRESO','GASTO')
            """).fetchall()

            gbm_detected = False
            for row in inv_candidates:
                desc_up = row['descripcion'].upper()
                plat = 'OTRO'
                for p, kw in _PLAT_KW:
                    if kw in desc_up:
                        plat = p
                        break
                # Excluir transferencias/pagos que no son inversiones reales --
                # solo si no se reconoció ninguna plataforma de inversión.
                if plat == 'OTRO' and any(excl in desc_up for excl in _NOT_INVERSION):
                    db.execute("""
                        UPDATE est_movimientos
                        SET tipo='PAGO', categoria='PAGO_TDC', subcategoria='Pago TDC'
                        WHERE id=?
                    """, (row['id'],))
                    continue
                if plat == 'GBM':
                    gbm_detected = True
                # Dirección por texto, no por tipo: el usuario confirmó que
                # "DOMICILIACION"/"ENVIADO" es dinero saliendo de su cuenta
                # para invertir (APORTACION) y "RECIBIDO" es dinero volviendo
                # (RETIRO) -- tipo (INGRESO/GASTO) no es confiable aquí, puede
                # venir mal por cómo el banco emisor reportó el movimiento.
                if 'ENVIADO' in desc_up or 'DOMICILIACION' in desc_up:
                    direction = 'APORTACION'
                elif 'RECIBIDO' in desc_up:
                    direction = 'RETIRO'
                else:
                    direction = 'APORTACION' if row['tipo'] == 'GASTO' else 'RETIRO'
                db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INVERSION', categoria=?, subcategoria=?
                    WHERE id=?
                """, (plat, direction, row['id']))

            db.commit()

            # ── Reglas automáticas al importar (Sprint 3 original) ────────────
            n_duplicados_credito = _descartar_ingresos_en_credito(db, new_ids)
            n_movimiento_interno = _unify_movimiento_interno(db, new_ids)
            avisos_msi = _detectar_avisos_msi(db)
            sugerencias_viaje_tabasco = _sugerir_viaje_tabasco(db, new_ids)
            sugerencias_reembolso = _sugerir_reembolsos(db, new_ids)
            _auto_clasificar_nomina(db, new_ids)
            avisos_posible_duplicado = _detectar_posibles_duplicados(db, new_ids)
            db.commit()

            # Auto-log de "Investigar en GBM" (Acta Diurna) — actividad oculta,
            # se marca sola cuando el import trae un movimiento real de GBM.
            if gbm_detected:
                today = today_str()
                already = db.execute(
                    "SELECT id FROM activity_logs WHERE activity_key='gbm' AND date=?", (today,)
                ).fetchone()
                if not already:
                    import modules.actividades.activity_defs as adefs
                    gbm_def = adefs.get_by_key('gbm')
                    gbm_pts = gbm_def['pts'] if gbm_def else 2
                    cursor = db.execute(
                        "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                        ('gbm', today, gbm_pts)
                    )
                    db.commit()
                    engine.process_activity('gbm', gbm_pts, 'Finanzas', cursor.lastrowid)

        # XP + EC por importar un estado de cuenta — solo si trajo movimientos
        # NUEVOS de verdad (evita farmear re-subiendo el mismo archivo/duplicados).
        gam = engine.process_estado_import(inserted, bank) if inserted > 0 else None

        preview = [
            {k: v for k, v in m.items() if k != 'periodo'}
            for m in movimientos[:5]
        ]
        return jsonify({
            'ok': True, 'bank': bank,
            'parsed': len(movimientos), 'inserted': inserted,
            'skipped': skipped, 'dedup_conflict': dedup_conflict,
            'gamification': ({'xp': gam['xp'], 'ec': gam['ec']} if gam else None),
            'preview': preview,
            'review_needed': review_needed,  # DEPOSITO/SPEI pendientes de clasificar
            'movimiento_interno_reclasificados': n_movimiento_interno,
            'ingresos_duplicados_en_credito': n_duplicados_credito,   # «nada que ingrese va a crédito»
            'avisos_msi': avisos_msi,                         # posible doble conteo de MSI, revisar manual
            'sugerencias_viaje_tabasco': sugerencias_viaje_tabasco,  # nunca se asignan solas
            'sugerencias_reembolso': sugerencias_reembolso,          # confirmar en /api/expenses/<id>/conciliar
            'avisos_posible_duplicado': avisos_posible_duplicado,    # mismo día+monto, tipo distinto -- revisar manual
        })

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


def _comparar_pdf_vs_db(movimientos: list, db_rows: list) -> tuple:
    """Compara movimientos parseados del PDF contra filas ya guardadas en
    la DB para el mismo periodo, agrupando por (fecha, descripcion) y
    emparejando dentro de cada clave por monto EXACTO — nunca por
    orden/posición, porque una misma fecha+descripción puede tener más de
    una transacción real distinta el mismo día (ver migración
    idx_est_mov_dedup en database.py, que por eso amplió el índice único
    para incluir también el monto).

    Devuelve (faltan, monto_no_coincide, fantasmas):
      - faltan: movimientos completos del PDF (dict con todas sus claves,
        listos para insertarse) sin match en la DB.
      - monto_no_coincide: lista de {'pdf': movimiento, 'db': fila} donde,
        para una misma clave, sobra exactamente una fila de cada lado tras
        el emparejamiento exacto — inequívocamente el mismo movimiento con
        el monto guardado distinto.
      - fantasmas: filas de la DB (dict) sin match en el PDF.

    Si sobra más de una fila de un lado (o de ambos) para la misma clave,
    NUNCA se adivina cuál le corresponde a cuál — se reportan por separado
    como faltantes/fantasmas en vez de emparejarlas por posición."""
    pdf_por_clave: dict = {}
    for m in movimientos:
        pdf_por_clave.setdefault((m['fecha'], m['descripcion']), []).append(m)

    db_por_clave: dict = {}
    for r in db_rows:
        r = dict(r)
        db_por_clave.setdefault((r['fecha'], r['descripcion']), []).append(r)

    faltan, monto_no_coincide, fantasmas = [], [], []
    claves = set(pdf_por_clave) | set(db_por_clave)
    for clave in claves:
        pdf_movs = list(pdf_por_clave.get(clave, []))
        db_movs = list(db_por_clave.get(clave, []))
        pdf_restantes, db_restantes = [], list(db_movs)
        for pm in pdf_movs:
            match = next((dm for dm in db_restantes if abs(dm['monto'] - pm['monto']) < 0.01), None)
            if match:
                db_restantes.remove(match)
            else:
                pdf_restantes.append(pm)

        if len(pdf_restantes) == 1 and len(db_restantes) == 1:
            monto_no_coincide.append({'pdf': pdf_restantes[0], 'db': db_restantes[0]})
        else:
            faltan.extend(pdf_restantes)
            fantasmas.extend(db_restantes)

    return faltan, monto_no_coincide, fantasmas


@estados_bp.route('/admin/audit-buscar')
def audit_buscar():
    """Diagnóstico de solo lectura -- NUNCA borra ni modifica nada. El
    usuario reportó pagos de renta de depto 807 (~$12,000/mes, "PAGO
    TARJETA DE TERCEROS MBAN") que ve para may-sep 2026 pero no para
    ene-abr 2026, aunque confirma que sí los había importado antes
    ("ya los tenia ahi"). Investigando el código se encontró
    est_dedup_backfill_v1_done: un backfill automático (no protegido por
    migration_log como el resto, sino por app_settings) que ya corrió
    UNA VEZ en el pasado y borra duplicados usando una descripción
    normalizada (quita dígitos y símbolos) agrupada por (fecha, monto,
    tipo) -- si dos variantes de la misma transacción coincidían en esa
    clave normalizada, se borraba todo menos la de descripción más larga.

    Este endpoint da evidencia concreta en vez de más hipótesis:
      - si ese backfill llegó a correr en esta base (bandera en
        app_settings)
      - una búsqueda de texto libre (?q=) SIN ningún filtro de categoría/
        tipo/fecha, agrupada por mes, para ver en qué meses SÍ hay algo
        y en cuáles no hay absolutamente nada -- descarta que un filtro
        esté ocultando filas que siguen ahí."""
    if not _ok(): return _locked()
    q = request.args.get('q', 'TERCEROS').strip()
    with get_db() as db:
        dedup_corrio = db.execute(
            "SELECT value FROM app_settings WHERE key='est_dedup_backfill_v1_done'"
        ).fetchone()
        rows = db.execute("""
            SELECT id, fecha, fecha_cargo, descripcion, monto, banco, categoria, subcategoria, tipo
            FROM est_movimientos
            WHERE UPPER(descripcion) LIKE ?
            ORDER BY fecha
        """, (f'%{q.upper()}%',)).fetchall()

    por_mes: dict = {}
    for r in rows:
        mes = (r['fecha'] or '')[:7]
        por_mes.setdefault(mes, []).append(dict(r))

    return jsonify({
        'query': q,
        'dedup_backfill_v1_corrio_en_esta_db': bool(dedup_corrio),
        'total_filas_encontradas': len(rows),
        'meses_con_datos': sorted(por_mes.keys()),
        'por_mes': por_mes,
    })


def _meses_en_rango(desde: str, hasta: str) -> list:
    """Lista de 'YYYY-MM' desde el mes de `desde` hasta el mes de `hasta`,
    inclusive. `desde`/`hasta` son fechas 'YYYY-MM-DD'."""
    d = datetime.strptime(desde[:7], '%Y-%m')
    h = datetime.strptime(hasta[:7], '%Y-%m')
    meses = []
    while d <= h:
        meses.append(d.strftime('%Y-%m'))
        y, m = d.year, d.month + 1
        if m > 12:
            y, m = y + 1, 1
        d = d.replace(year=y, month=m)
    return meses


@estados_bp.route('/admin/audit-periodos-faltantes')
def audit_periodos_faltantes():
    """Diagnóstico de solo lectura -- NUNCA borra ni modifica nada. El
    usuario sabe que hay huecos en 2026 y quiere saber qué periodos
    (ene-sep) no se han subido, banco por banco, para ir a buscar esos
    estados de cuenta.

    Por cada banco que sube estado de cuenta (BBVA_DEB, BBVA_TDC, HSBC,
    INVEX -- se excluye MANUAL, que son altas sueltas, no estados de
    cuenta con periodo fijo), se listan los meses calendario dentro del
    rango que NO tienen ninguna fila importada. No es prueba definitiva
    de que falte el PDF completo (un mes puede tener pocas transacciones
    reales, o el corte de tarjeta de crédito no calza con el mes
    calendario), pero es la señal más directa disponible sin poder leer
    la DB de producción directamente."""
    if not _ok(): return _locked()
    desde = request.args.get('desde', '2026-01-01')
    hasta = request.args.get('hasta', today_str())
    bancos = ['BBVA_DEB', 'BBVA_TDC', 'HSBC', 'INVEX']
    todos_los_meses = _meses_en_rango(desde, hasta)

    resultado = {}
    with get_db() as db:
        for banco in bancos:
            rows = db.execute("""
                SELECT fecha FROM est_movimientos
                WHERE banco=? AND fecha BETWEEN ? AND ?
            """, (banco, desde, hasta)).fetchall()
            meses_con_datos = sorted({(r['fecha'] or '')[:7] for r in rows if r['fecha']})
            meses_faltantes = [m for m in todos_los_meses if m not in meses_con_datos]
            fechas = sorted(r['fecha'] for r in rows if r['fecha'])
            resultado[banco] = {
                'total_filas': len(rows),
                'primera_fecha': fechas[0] if fechas else None,
                'ultima_fecha': fechas[-1] if fechas else None,
                'meses_con_datos': meses_con_datos,
                'meses_faltantes': meses_faltantes,
            }

    return jsonify({
        'desde': desde,
        'hasta': hasta,
        'todos_los_meses_en_rango': todos_los_meses,
        'por_banco': resultado,
    })


AUDIT_BANCOS = {
    'BBVA_DEB': 'BBVA Débito',
    'BBVA_TDC': 'BBVA Crédito',
    'HSBC':     'HSBC',
    'INVEX':    'Invex Volaris',
}
_PERIODO_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s+al\s+(\d{4}-\d{2}-\d{2})")


def _auditar_banco(db, banco: str, hasta: str, umbral_dias: int) -> dict:
    """Huecos de un banco: (1) días sin cubrir entre periodos de estado de
    cuenta consecutivos (la señal más precisa: el `periodo` que guarda cada
    import), (2) tramos de más de `umbral_dias` sin ningún movimiento y
    (3) meses calendario sin filas, desde su primer movimiento hasta `hasta`."""
    rows = db.execute("""
        SELECT substr(fecha, 1, 10) AS fecha, COALESCE(periodo, '') AS periodo
        FROM est_movimientos
        WHERE banco=? AND fecha IS NOT NULL AND fecha != '' AND substr(fecha, 1, 10) <= ?
        ORDER BY fecha
    """, (banco, hasta)).fetchall()
    fechas = [r['fecha'] for r in rows]
    if not fechas:
        return {'filas': 0, 'primera_fecha': None, 'ultima_fecha': None, 'dias_sin_datos': None,
                'periodos': [], 'huecos_entre_periodos': [], 'huecos_sin_movimientos': [],
                'meses_sin_movimientos': []}

    # 1) Periodos de estado de cuenta
    periodos = {}
    for r in rows:
        m = _PERIODO_RE.search(r['periodo'])
        if m:
            p = periodos.setdefault((m.group(1), m.group(2)), 0)
            periodos[(m.group(1), m.group(2))] = p + 1
    lista = sorted(periodos.items())
    huecos_periodo = []
    for i in range(1, len(lista)):
        (_, fin_prev), _ = lista[i - 1]
        (ini_sig, _), _ = lista[i]
        d_fin = datetime.strptime(fin_prev, '%Y-%m-%d').date()
        d_ini = datetime.strptime(ini_sig, '%Y-%m-%d').date()
        # Tolerancia de 3 días: los cortes a veces brincan fines de semana.
        if (d_ini - d_fin).days > 3:
            huecos_periodo.append({
                'desde': (d_fin + timedelta(days=1)).isoformat(),
                'hasta': (d_ini - timedelta(days=1)).isoformat(),
                'dias': (d_ini - d_fin).days - 1,
            })

    # 2) Tramos sin movimientos
    huecos_mov = []
    prev = datetime.strptime(fechas[0], '%Y-%m-%d').date()
    for f in fechas[1:] + [hasta]:
        d = datetime.strptime(f, '%Y-%m-%d').date()
        if (d - prev).days > umbral_dias:
            huecos_mov.append({'desde': (prev + timedelta(days=1)).isoformat(),
                               'hasta': (d - timedelta(days=1)).isoformat() if f != hasta else hasta,
                               'dias': (d - prev).days - (1 if f != hasta else 0)})
        prev = max(prev, d)

    # 3) Meses sin movimientos
    con_datos = {f[:7] for f in fechas}
    meses_sin = [m for m in _meses_en_rango(fechas[0], hasta) if m not in con_datos]

    ultima = datetime.strptime(fechas[-1], '%Y-%m-%d').date()
    return {
        'filas': len(fechas),
        'primera_fecha': fechas[0],
        'ultima_fecha': fechas[-1],
        'dias_sin_datos': (datetime.strptime(hasta, '%Y-%m-%d').date() - ultima).days,
        'periodos': [{'inicio': a, 'fin': b, 'movimientos': n} for (a, b), n in lista],
        'huecos_entre_periodos': huecos_periodo,
        'huecos_sin_movimientos': huecos_mov,
        'meses_sin_movimientos': meses_sin,
    }


@estados_bp.route('/admin/audit-huecos')
def audit_huecos():
    """Auditoría de solo lectura -- NUNCA modifica nada -- de qué estados de
    cuenta faltan en BBVA Débito, BBVA Crédito, HSBC e Invex Volaris, desde
    el primer movimiento de cada banco hasta hoy (o ?hasta=YYYY-MM-DD).
    ?umbral=N ajusta cuántos días sin movimientos cuentan como hueco
    (default 25). ?formato=html la muestra como página legible."""
    if not _ok(): return _locked()
    hasta = request.args.get('hasta') or today_str()
    try:
        umbral = max(1, int(request.args.get('umbral', 25)))
    except ValueError:
        umbral = 25
    with get_db() as db:
        por_banco = {b: {'nombre': n, **_auditar_banco(db, b, hasta, umbral)}
                     for b, n in AUDIT_BANCOS.items()}
    data = {'hasta': hasta, 'umbral_dias': umbral, 'por_banco': por_banco}
    if request.args.get('formato') == 'html':
        return render_template_string(_AUDIT_HUECOS_HTML, **data)
    return jsonify(data)


_AUDIT_HUECOS_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Auditoría de estados de cuenta</title>
<style>
body{font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px;background:#0f0d14;color:#ece8f4}
h1{font-size:20px;margin:0 0 4px}.meta{color:#9d96ad;font-size:13px;margin-bottom:16px}
.card{background:#1a1622;border:1px solid #2c2638;border-radius:12px;padding:16px;margin-bottom:16px;max-width:760px}
h2{font-size:17px;margin:0 0 8px}.ok{color:#6ee7a8}.warn{color:#fbbf24}.bad{color:#f87171}
ul{margin:4px 0 8px;padding-left:20px}li{margin:2px 0}h3{font-size:14px;margin:12px 0 2px;color:#c9c2d8}
details summary{cursor:pointer;color:#9d96ad;font-size:13px;margin-top:8px}
</style></head><body>
<h1>Auditoría de estados de cuenta</h1>
<div class="meta">Hasta {{ hasta }} · hueco = más de {{ umbral_dias }} días sin movimientos · solo lectura</div>
{% for code, b in por_banco.items() %}
<div class="card"><h2>{{ b.nombre }}</h2>
{% if not b.filas %}<div class="bad">Sin ningún movimiento importado.</div>{% else %}
<div class="meta">{{ b.filas }} movimientos · {{ b.primera_fecha }} → {{ b.ultima_fecha }}
{% if b.dias_sin_datos > umbral_dias %}<span class="warn"> · {{ b.dias_sin_datos }} días sin datos al corte</span>{% endif %}</div>
{% if b.huecos_entre_periodos %}<h3 class="bad">Faltan estados de cuenta entre periodos</h3><ul>
{% for h in b.huecos_entre_periodos %}<li>{{ h.desde }} → {{ h.hasta }} ({{ h.dias }} días)</li>{% endfor %}</ul>{% endif %}
{% if b.huecos_sin_movimientos %}<h3 class="warn">Tramos sin movimientos</h3><ul>
{% for h in b.huecos_sin_movimientos %}<li>{{ h.desde }} → {{ h.hasta }} ({{ h.dias }} días)</li>{% endfor %}</ul>{% endif %}
{% if b.meses_sin_movimientos %}<h3 class="warn">Meses sin ningún movimiento</h3><div>{{ b.meses_sin_movimientos|join(', ') }}</div>{% endif %}
{% if not b.huecos_entre_periodos and not b.huecos_sin_movimientos and not b.meses_sin_movimientos %}<div class="ok">Sin huecos detectados.</div>{% endif %}
{% if b.periodos %}<details><summary>{{ b.periodos|length }} periodos importados</summary><ul>
{% for p in b.periodos %}<li>{{ p.inicio }} al {{ p.fin }} · {{ p.movimientos }} mov.</li>{% endfor %}</ul></details>{% endif %}
{% endif %}</div>
{% endfor %}
</body></html>"""


@estados_bp.route('/admin/audit-duplicados')
def audit_duplicados():
    """Bug real confirmado por el usuario: el mismo movimiento real se
    coló dos veces con descripción y/o tipo distintos (ej. "PAGO DE
    NOMINA HH" vía BBVA_DEB y "PAGO DE NOMINA / HH 4206466060 FIBRA
    HOTELERA..." vía BBVA_TDC, mismo día, mismo monto) — ninguno de los
    dos guardarraíles existentes lo atrapa: el índice UNIQUE(fecha,
    descripcion,monto) exige coincidencia exacta de descripción, y el
    dedup de /api/upload por (fecha,monto,tipo) no aplica si el tipo
    también terminó distinto (ej. una fila mal detectada como GASTO y
    luego reclasificada a mano a INGRESO).

    Reporte de solo lectura -- NUNCA borra ni modifica nada. Agrupa TODOS
    los movimientos por (fecha, monto redondeado a centavos), sin
    importar tipo/categoría/banco, y devuelve cada grupo con más de una
    fila para que el usuario decida cuál(es) borrar desde la UI (icono de
    basura en el modal de editar). Puede haber falsos positivos legítimos
    (dos compras reales del mismo monto el mismo día) -- no se adivina
    cuál es cuál."""
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute("""
            SELECT id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo
            FROM est_movimientos
            WHERE monto != 0
            ORDER BY fecha, ROUND(monto, 2)
        """).fetchall()

    grupos: dict = {}
    for r in rows:
        key = (r['fecha'], round(float(r['monto']), 2))
        grupos.setdefault(key, []).append(dict(r))

    duplicados = [
        {'fecha': fecha, 'monto': monto, 'movimientos': movs}
        for (fecha, monto), movs in grupos.items() if len(movs) > 1
    ]
    duplicados.sort(key=lambda g: g['fecha'])

    return jsonify({
        'grupos_duplicados': len(duplicados),
        'total_filas_involucradas': sum(len(g['movimientos']) for g in duplicados),
        'duplicados': duplicados,
    })


@estados_bp.route('/admin/audit-nomina-sospechosa')
def audit_nomina_sospechosa():
    """Bug real confirmado por el usuario con screenshot: un backfill legacy
    en database.py (ahora congelado -- ver
    finanzas_nomina_backfill_legacy_frozen_2026_09) corrió sin filtro de
    monto durante mucho tiempo, marcando como categoria=NOMINA,
    tipo=INGRESO cualquier movimiento que mencionara "FIBRA HOTELERA" --
    incluyendo retiros y SPEI enviados que claramente no eran sueldo (ej.
    "RETIRO SIN TARJETA... FIBRA HOTELERA SC" $500.00).

    Congelar el backfill detiene el problema hacia adelante, pero no
    corrige las filas que YA quedaron mal etiquetadas por corridas
    anteriores. No se adivina aquí cuál es el tipo/categoria correcto de
    cada una (podría ser FINANZAS/Retiro efectivo, FINANZAS/Transferencia,
    ALIMENTACION, etc. según el caso) -- reporte de solo lectura, NUNCA
    borra ni modifica nada, para que el usuario revise y corrija cada una
    desde el modal de editar en Movimientos."""
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute("""
            SELECT id, fecha, descripcion, monto, banco, subcategoria, tipo
            FROM est_movimientos
            WHERE categoria='NOMINA' AND monto NOT BETWEEN 9000 AND 12000
            ORDER BY ABS(monto) ASC
        """).fetchall()

    return jsonify({
        'total_sospechosas': len(rows),
        'movimientos': [dict(r) for r in rows],
    })


@estados_bp.route('/admin/audit-montos', methods=['POST'])
def audit_montos():
    """Audita que los MONTOS de un estado de cuenta YA importado cuadren
    contra lo que hay en la DB — no toca ni compara categoría/tipo (el
    usuario los reclasifica a mano y eso no se debe pisar). Es de solo
    lectura: nunca escribe nada, solo reporta.

    Vuelve a parsear el PDF (sin insertar nada, a diferencia de
    /api/upload) y compara, para el mismo periodo, contra las filas ya
    guardadas en la DB (banco='BBVA_DEB', mismo `periodo` textual que
    quedó grabado al importar):
      - movimientos del PDF que no aparecen en la DB (posible falta),
      - filas de la DB de este periodo que no corresponden a ningún
        movimiento del PDF (posible fantasma/duplicado),
      - pares que sí matchean por (fecha, descripcion) pero el monto no
        coincide,
      - los totales agregados (suma de cargos/abonos) del PDF, de la DB
        para este periodo, y los oficiales que el propio PDF reporta en
        su resumen ("Total Importe Cargos/Abonos", "Saldo Final") — para
        poder ver de un vistazo si todo cuadra en conjunto aunque no haya
        diferencias línea por línea."""
    if not _ok(): return _locked()

    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400

    suffix = Path(file.filename or 'file.pdf').suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        from .parsers import parse_file, detect_bank
        bank = detect_bank(tmp_path)
        movimientos = parse_file(tmp_path)
        if not movimientos:
            return jsonify({'ok': False, 'error': 'No se encontraron transacciones', 'bank': bank})

        periodo = movimientos[0].get('periodo')

        # Totales oficiales que el propio PDF reporta — solo disponibles
        # para el formato Libretón (bbva_libreton.py); en cualquier otro
        # formato se omiten y la auditoría se queda con la comparación
        # línea por línea contra la DB.
        oficiales = None
        try:
            from .parsers import bbva_libreton as _lib
            from .parsers._base import open_pdf as _open_pdf
            from .config import PDF_PASSWORD, PDF_PASSWORD_BBVA
            with _open_pdf(tmp_path, PDF_PASSWORD, PDF_PASSWORD_BBVA) as _pdf:
                _text = "\n".join(p.extract_text() or "" for p in _pdf.pages)
            _tc = _lib.TOTAL_CARGOS_RE.search(_text)
            _ta = _lib.TOTAL_ABONOS_RE.search(_text)
            _sf = _lib.SALDO_FINAL_RE.search(_text)
            _sa = _lib.SALDO_ANTERIOR_RE.search(_text)
            if _tc and _ta:
                oficiales = {
                    'total_cargos': float(_tc.group(1).replace(",", "")),
                    'n_cargos': int(_tc.group(2)),
                    'total_abonos': float(_ta.group(1).replace(",", "")),
                    'n_abonos': int(_ta.group(2)),
                    'saldo_anterior': float(_sa.group(1).replace(",", "")) if _sa else None,
                    'saldo_final': float(_sf.group(1).replace(",", "")) if _sf else None,
                }
        except Exception:
            pass

        with get_db() as db:
            db_rows = db.execute(
                "SELECT id, fecha, descripcion, monto, tipo FROM est_movimientos "
                "WHERE banco='BBVA_DEB' AND periodo=?",
                (periodo,),
            ).fetchall() if periodo else []

        faltan, pares_no_coinciden, fantasmas = _comparar_pdf_vs_db(movimientos, db_rows)
        faltan_en_db = [
            {'fecha': m['fecha'], 'descripcion': m['descripcion'], 'monto_pdf': m['monto']}
            for m in faltan
        ]
        monto_no_coincide = [
            {'id': p['db']['id'], 'fecha': p['pdf']['fecha'], 'descripcion': p['pdf']['descripcion'],
             'monto_pdf': p['pdf']['monto'], 'monto_guardado': p['db']['monto']}
            for p in pares_no_coinciden
        ]
        fantasmas_en_db = [
            {'id': r['id'], 'fecha': r['fecha'], 'descripcion': r['descripcion'],
             'monto': r['monto'], 'tipo': r['tipo']}
            for r in fantasmas
        ]

        total_pdf_cargos  = sum(m['monto'] for m in movimientos if m['tipo'] != 'INGRESO')
        total_pdf_abonos  = sum(m['monto'] for m in movimientos if m['tipo'] == 'INGRESO')
        total_db_cargos   = sum(r['monto'] for r in db_rows if r['tipo'] != 'INGRESO')
        total_db_abonos   = sum(r['monto'] for r in db_rows if r['tipo'] == 'INGRESO')

        return jsonify({
            'ok': True, 'bank': bank, 'periodo': periodo,
            'parseados_en_pdf': len(movimientos),
            'encontrados_en_db_este_periodo': len(db_rows),
            'oficiales_segun_pdf': oficiales,
            'totales': {
                'pdf_cargos': round(total_pdf_cargos, 2), 'pdf_abonos': round(total_pdf_abonos, 2),
                'db_cargos': round(total_db_cargos, 2), 'db_abonos': round(total_db_abonos, 2),
            },
            'faltan_en_db': faltan_en_db,
            'monto_no_coincide': monto_no_coincide,
            'fantasmas_en_db': fantasmas_en_db,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


@estados_bp.route('/admin/debug-pdf', methods=['GET', 'POST'])
def debug_pdf():
    """El usuario reportó "No se encontraron transacciones" al subir un
    estado de cuenta BBVA crédito -- el parser (bbva.py + LINE_RE en
    _base.py) exige que cada línea de movimiento tenga DOS fechas
    "DD-Mon-YY", una descripción, un signo +/- y un monto con "$" y 2
    decimales, todo en la MISMA línea de texto extraída por pdfplumber.
    Si BBVA cambió el formato de ese PDF en particular (una sola fecha,
    sin signo explícito, columnas en otro orden...) esa línea nunca
    matchea y se descarta en silencio -- sin poder ver el PDF real no hay
    forma de saber qué cambió.

    Diagnóstico de solo lectura, NUNCA guarda el archivo ni inserta nada
    en la DB: abre el PDF (con las mismas contraseñas que /api/upload),
    extrae el texto de las primeras páginas y devuelve las líneas
    REDACTADAS -- todos los dígitos se cambian por # y las palabras de
    4+ letras se acortan a su primera letra + "x" -- para ver la
    ESTRUCTURA real (cuántas fechas trae, dónde va el signo, cuántos
    espacios) sin exponer montos, fechas ni nombres de comercios reales."""
    if not _ok(): return _locked()

    if request.method == 'GET':
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<title>Debug PDF</title></head><body style="font-family:sans-serif;max-width:600px;margin:40px auto;">'
            '<h3>Diagnóstico de estado de cuenta (solo lectura)</h3>'
            '<p>Sube el mismo PDF que te dio "No se encontraron transacciones". '
            'No se guarda el archivo ni se inserta nada en la base de datos -- '
            'solo se muestra la estructura del texto con números y nombres tapados.</p>'
            '<form method="POST" enctype="multipart/form-data">'
            '<input type="file" name="file" accept=".pdf" required> '
            '<button type="submit">Analizar</button>'
            '</form></body></html>'
        )

    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400

    suffix = Path(file.filename or 'file.pdf').suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        import re as _re
        from .parsers import detect_bank
        from .parsers._base import open_pdf as _open_pdf
        from .config import PDF_PASSWORD, PDF_PASSWORD_BBVA

        bank = detect_bank(tmp_path)
        with _open_pdf(tmp_path, PDF_PASSWORD, PDF_PASSWORD_BBVA) as pdf:
            # Las primeras páginas de un estado de cuenta suelen ser solo
            # carátula (límite de crédito, fecha de corte, resumen) -- el
            # detalle de movimientos real puede empezar varias páginas
            # después. Se recorren TODAS las páginas en vez de solo las
            # primeras 2 (el primer intento de este diagnóstico solo vio
            # la carátula del usuario, cero líneas de movimientos reales).
            all_pages_text = [p.extract_text() or "" for p in pdf.pages]

        def _redact(line: str) -> str:
            line = _re.sub(r'\d', '#', line)
            line = _re.sub(
                r'[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}',
                lambda m: m.group(0)[0] + 'x' * (len(m.group(0)) - 1),
                line,
            )
            return line

        # Puntuar cada página por qué tan probable es que sea la tabla de
        # movimientos: cuenta líneas con "$" y al menos 2 dígitos seguidos
        # (fecha o monto) -- más confiable que buscar un encabezado literal
        # como "DETALLE", que varía entre formatos/años de BBVA.
        def _score(text: str) -> int:
            return sum(
                1 for line in text.split('\n')
                if '$' in line and _re.search(r'\d{2}', line)
            )

        paginas = []
        for i, t in enumerate(all_pages_text):
            nonempty = [l for l in t.split('\n') if l.strip()]
            paginas.append({'num': i + 1, 'lineas': len(nonempty), 'score': _score(t), 'texto': nonempty})

        resumen = '\n'.join(f"Página {p['num']}: {p['lineas']} líneas, score={p['score']}" for p in paginas)

        # Mostrar las 2 páginas con mayor score (más probables de ser la
        # tabla real) además de la página 1 (contexto/carátula) si no quedó
        # ya incluida.
        top = sorted(paginas, key=lambda p: -p['score'])[:2]
        top_nums = {p['num'] for p in top}
        mostrar = list(top)
        if paginas and paginas[0]['num'] not in top_nums:
            mostrar.insert(0, paginas[0])

        bloques = []
        for p in mostrar:
            redactadas = [_redact(l) for l in p['texto'][:30]]
            bloques.append(f"--- Página {p['num']} (score={p['score']}) ---\n" + '\n'.join(redactadas))

        html = (
            '<!doctype html><html><head><meta charset="utf-8"><title>Debug PDF</title></head>'
            '<body style="font-family:monospace;max-width:800px;margin:40px auto;white-space:pre-wrap;">'
            f'<p style="font-family:sans-serif;">Banco detectado: <b>{bank}</b> · {len(paginas)} páginas en total.</p>'
            f'<p style="font-family:sans-serif;">{resumen}</p>'
            '<hr>' + '\n\n'.join(bloques) + '</body></html>'
        )
        return html
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


@estados_bp.route('/admin/recover-montos', methods=['POST'])
def recover_montos():
    """Inserta las transacciones que audit-montos reporta como
    'faltan_en_db' para un estado de cuenta YA importado: movimientos
    reales del PDF que nunca se guardaron porque, antes de que
    idx_est_mov_dedup incluyera el monto (ver migración en database.py),
    colisionaban en (fecha, descripcion) con otra transacción distinta del
    mismo día y el INSERT OR IGNORE del importador las descartaba en
    silencio.

    Nunca toca una fila existente — no hay UPDATE ni DELETE, solo INSERT
    OR IGNORE de las filas que _comparar_pdf_vs_db confirma que genuinamente
    faltan (nunca las de 'monto_no_coincide' ni 'fantasmas_en_db', que son
    casos ambiguos y requieren revisión humana, no inserción automática).
    Por default es un dry-run — agrega ?apply=1 para insertar de verdad."""
    if not _ok(): return _locked()

    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400

    suffix = Path(file.filename or 'file.pdf').suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        from .parsers import parse_file, detect_bank
        bank = detect_bank(tmp_path)
        movimientos = parse_file(tmp_path)
        if not movimientos:
            return jsonify({'ok': False, 'error': 'No se encontraron transacciones', 'bank': bank})

        periodo = movimientos[0].get('periodo')
        apply_changes = request.args.get('apply') == '1'

        with get_db() as db:
            db_rows = db.execute(
                "SELECT id, fecha, descripcion, monto, tipo FROM est_movimientos "
                "WHERE banco='BBVA_DEB' AND periodo=?",
                (periodo,),
            ).fetchall() if periodo else []

            faltan, _pares, _fantasmas = _comparar_pdf_vs_db(movimientos, db_rows)

            insertados = []
            if apply_changes:
                for m in faltan:
                    cur = db.execute(
                        "INSERT OR IGNORE INTO est_movimientos "
                        "(fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (m['fecha'], m.get('fecha_cargo'), m['descripcion'], m['monto'],
                         m.get('banco') or bank, m.get('periodo') or periodo,
                         m.get('categoria', ''), m.get('subcategoria', ''), m.get('tipo', 'GASTO')),
                    )
                    if cur.rowcount == 1:
                        insertados.append({
                            'id': cur.lastrowid, 'fecha': m['fecha'], 'descripcion': m['descripcion'],
                            'monto': m['monto'], 'tipo': m.get('tipo'),
                        })
                db.commit()

        return jsonify({
            'ok': True, 'bank': bank, 'periodo': periodo, 'apply': apply_changes,
            'a_recuperar': [
                {'fecha': m['fecha'], 'descripcion': m['descripcion'], 'monto': m['monto'], 'tipo': m.get('tipo')}
                for m in faltan
            ],
            'insertados': insertados,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Viajes ────────────────────────────────────────────────────────────────────

@estados_bp.route('/admin/fix-libreton-years', methods=['GET', 'POST'])
def fix_libreton_years():
    """Corrige movimientos BBVA Libretón cuyo año quedó mal por el bug
    arreglado en parsers/bbva_libreton.py (estados de cuenta cuyo periodo
    cruza de año, ej. "07/12/2024 al 06/01/2025" — diciembre quedaba
    guardado con el año siguiente). Usa la misma lógica que
    scripts/fix_libreton_year_bug.py. GET = dry-run (no escribe nada),
    POST = corrige fechas; agrega ?delete_duplicates=1 para además borrar
    las filas viejas que sean duplicado confirmado (mismo monto y tipo) de
    una fila que ya quedó con la fecha correcta — pasa cuando el mismo
    estado de cuenta se subió dos veces, antes y después del fix."""
    if not _ok(): return _locked()

    from scripts.fix_libreton_year_bug import find_fixes

    with get_db() as db:
        rows, fixes, duplicates, review = find_fixes(db)

        fixes_preview = [
            {'id': _id, 'fecha_antes': r['fecha'], 'fecha_despues': nf,
             'fecha_cargo_antes': r['fecha_cargo'], 'fecha_cargo_despues': nfc,
             'monto': r['monto'], 'tipo': r['tipo'], 'descripcion': r['descripcion']}
            for _id, nf, nfc, r in fixes
        ]
        duplicates_preview = [
            {'id_viejo': r['id'], 'id_correcto': existing['id'],
             'fecha_vieja': r['fecha'], 'monto': r['monto'], 'tipo': r['tipo'],
             'descripcion': r['descripcion']}
            for r, existing in duplicates
        ]
        review_preview = [
            {'id': r['id'], 'fecha_antes': r['fecha'], 'fecha_a_corregir': nf,
             'choca_con_id': existing['id'], 'descripcion': r['descripcion']}
            for r, nf, existing in review
        ]

        if request.method == 'GET':
            return jsonify({
                'ok': True, 'dry_run': True,
                'revisadas': len(rows), 'a_corregir': len(fixes),
                'fixes': fixes_preview,
                'duplicados_confirmados': duplicates_preview,
                'revisar_a_mano': review_preview,
            })

        for _id, nf, nfc, _r in fixes:
            db.execute(
                "UPDATE est_movimientos SET fecha=?, fecha_cargo=? WHERE id=?",
                (nf, nfc, _id),
            )

        borrar_duplicados = request.args.get('delete_duplicates') == '1'
        if borrar_duplicados:
            for r, _existing in duplicates:
                db.execute("DELETE FROM est_movimientos WHERE id=?", (r['id'],))

        db.commit()

    return jsonify({
        'ok': True, 'dry_run': False,
        'corregidas': len(fixes), 'fixes': fixes_preview,
        'duplicados_confirmados': duplicates_preview,
        'duplicados_borrados': len(duplicates) if borrar_duplicados else 0,
        'revisar_a_mano': review_preview,
    })


# SQL expression that buckets a transaction into a travel concept.
# Taxonomía 2026-09: VIAJES ya trae sus propias subcategorias (Transporte,
# Hospedaje, Comida, Restaurante, Salidas, Otros) para lo que se etiquetó
# directamente como parte del viaje -- Restaurante suma a Comida y Salidas a
# Experiencias en el desglose del viaje; TRANSPORTE/SUPER/COMIDA_FUERA/OCIO/SALSA cubren transacciones de otras
# categorias que igual se asignaron a un viaje_id (ej. gasolina de carretera,
# clases de salsa del congreso).
_CONCEPTO_CASE = """
  CASE
    WHEN categoria='VIAJES' AND subcategoria='Hospedaje' THEN 'Hotel'
    WHEN categoria='VIAJES' AND subcategoria='Transporte' THEN 'Transporte'
    WHEN categoria='TRANSPORTE' THEN 'Transporte'
    WHEN categoria='VIAJES' AND subcategoria IN ('Comida','Restaurante') THEN 'Comida'
    WHEN categoria='VIAJES' AND subcategoria='Salidas' THEN 'Experiencias'
    WHEN categoria IN ('SUPER','COMIDA_FUERA','ALIMENTACION','CAFE/PAN') THEN 'Comida'
    WHEN categoria IN ('OCIO','SALSA') THEN 'Experiencias'
    ELSE 'Otros'
  END
"""

_GASTO_FILTER = f"tipo='GASTO' AND {_PAGO_CATS}"


@estados_bp.route('/viajes/')
def viajes_page():
    if not _ok():
        return redirect(url_for('finanzas.index'))
    return render_template('finanzas/viajes.html')


@estados_bp.route('/api/trips')
def list_trips():
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute(f"""
            SELECT v.*,
                   COUNT(m.id) AS tx_count,
                   COALESCE(SUM(
                       CASE WHEN {_GASTO_FILTER}
                            THEN {_monto_expr('m.')} ELSE 0 END
                   ), 0) AS total_gastado
            FROM viajes v
            LEFT JOIN est_movimientos m ON m.viaje_id = v.id
            GROUP BY v.id
            ORDER BY v.fecha_inicio DESC
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@estados_bp.route('/api/trips', methods=['POST'])
def create_trip():
    if not _ok(): return _locked()
    d = request.json or {}
    nombre = (d.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'error': 'nombre requerido'}), 400
    now = datetime.now().isoformat()
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO viajes
               (nombre, destino, fecha_inicio, fecha_fin, presupuesto, estado, notas, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                clean_str(nombre, 200),
                clean_str(d.get('destino', ''), 100),
                d.get('fecha_inicio', ''),
                d.get('fecha_fin', ''),
                safe_float(d.get('presupuesto', 0), min_val=0),
                d.get('estado', 'planificado'),
                clean_str(d.get('notas', ''), 500),
                now,
            ),
        )
        trip_id = cur.lastrowid
        db.commit()
    return jsonify({'ok': True, 'id': trip_id}), 201


@estados_bp.route('/api/trips/<int:trip_id>', methods=['PATCH'])
def update_trip(trip_id):
    if not _ok(): return _locked()
    d = request.json or {}
    fields, params = [], []
    for key in ('nombre', 'destino', 'fecha_inicio', 'fecha_fin', 'estado', 'notas'):
        if key in d:
            fields.append(f"{key}=?")
            params.append(clean_str(d[key], 500) if key in ('nombre', 'destino', 'notas') else d[key])
    if 'presupuesto' in d:
        fields.append("presupuesto=?")
        params.append(safe_float(d['presupuesto'], min_val=0))
    if not fields:
        return jsonify({'ok': True})
    params.append(trip_id)
    with get_db() as db:
        db.execute(f"UPDATE viajes SET {', '.join(fields)} WHERE id=?", params)
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/trips/<int:trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("UPDATE est_movimientos SET viaje_id=NULL WHERE viaje_id=?", (trip_id,))
        # `viajes` es la tabla compartida con el planner de maleta/outfits
        # (modules/viajes/routes.py) — borrar el viaje aquí debe limpiar
        # también su maleta y outfits asignados, igual que hace ese módulo.
        db.execute("DELETE FROM viaje_maleta      WHERE viaje_id=?", (trip_id,))
        db.execute("DELETE FROM viaje_dia_outfits WHERE dia_id IN "
                   "(SELECT id FROM viaje_dias WHERE viaje_id=?)", (trip_id,))
        db.execute("DELETE FROM viaje_dias        WHERE viaje_id=?", (trip_id,))
        db.execute("DELETE FROM viajes            WHERE id=?", (trip_id,))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/trips/<int:trip_id>/summary')
def trip_summary(trip_id):
    if not _ok(): return _locked()
    with get_db() as db:
        trip = db.execute("SELECT * FROM viajes WHERE id=?", (trip_id,)).fetchone()
        if not trip:
            return jsonify({'error': 'not found'}), 404
        breakdown = db.execute(f"""
            SELECT {_CONCEPTO_CASE} AS concepto,
                   SUM({_MONTO}) AS total,
                   COUNT(*) AS n
            FROM est_movimientos
            WHERE viaje_id=? AND {_GASTO_FILTER}
            GROUP BY concepto
            ORDER BY total DESC
        """, (trip_id,)).fetchall()
        total_gastado = sum(r['total'] or 0 for r in breakdown)
    return jsonify({
        'trip':          dict(trip),
        'total_gastado': round(total_gastado, 2),
        'breakdown': [
            {'concepto': r['concepto'], 'total': round(r['total'] or 0, 2), 'n': r['n']}
            for r in breakdown
        ],
    })


@estados_bp.route('/api/trips/<int:trip_id>/transactions')
def trip_transactions(trip_id):
    if not _ok(): return _locked()
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM est_movimientos WHERE viaje_id=? ORDER BY fecha ASC, monto DESC",
            (trip_id,),
        ).fetchall()
    return jsonify({'data': [dict(r) for r in rows]})


@estados_bp.route('/api/trips/<int:trip_id>/suggest')
def trip_suggest(trip_id):
    if not _ok(): return _locked()
    with get_db() as db:
        trip = db.execute(
            "SELECT fecha_inicio, fecha_fin FROM viajes WHERE id=?", (trip_id,)
        ).fetchone()
        if not trip:
            return jsonify({'data': []})
        rows = db.execute(f"""
            SELECT * FROM est_movimientos
            WHERE viaje_id IS NULL
              AND fecha BETWEEN ? AND ?
              AND {_GASTO_FILTER}
            ORDER BY fecha ASC, monto DESC
            LIMIT 100
        """, (trip['fecha_inicio'], trip['fecha_fin'])).fetchall()
    return jsonify({'data': [dict(r) for r in rows]})


@estados_bp.route('/api/trips/<int:trip_id>/tag', methods=['POST'])
def tag_transactions(trip_id):
    if not _ok(): return _locked()
    tx_ids = request.json.get('tx_ids', []) if request.json else []
    if not tx_ids:
        return jsonify({'ok': True, 'tagged': 0})
    with get_db() as db:
        if not db.execute("SELECT id FROM viajes WHERE id=?", (trip_id,)).fetchone():
            return jsonify({'error': 'trip not found'}), 404
        ph = ','.join('?' * len(tx_ids))
        db.execute(
            f"UPDATE est_movimientos SET viaje_id=? WHERE id IN ({ph})",
            [trip_id] + list(tx_ids),
        )
        db.commit()
    return jsonify({'ok': True, 'tagged': len(tx_ids)})


@estados_bp.route('/api/trips/<int:trip_id>/untag', methods=['POST'])
def untag_transactions(trip_id):
    if not _ok(): return _locked()
    tx_ids = request.json.get('tx_ids', []) if request.json else []
    if not tx_ids:
        return jsonify({'ok': True})
    with get_db() as db:
        ph = ','.join('?' * len(tx_ids))
        db.execute(
            f"UPDATE est_movimientos SET viaje_id=NULL WHERE id IN ({ph}) AND viaje_id=?",
            list(tx_ids) + [trip_id],
        )
        db.commit()
    return jsonify({'ok': True})
