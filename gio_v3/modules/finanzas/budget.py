"""
Budget 50-30-20 — radiografía en vivo alimentada por est_movimientos.

Fuente de verdad única:
  - Gastos   → est_movimientos tipo='GASTO'   (excluye PAGO_TDC, PAGO, TRANSFERENCIA, SPEI_ENVIADO, RETIRO, PUBLICIDAD)
  - Ingresos → est_movimientos tipo='INGRESO' (excluye TRANSFERENCIA, PAGO_TDC, RETIRO, DEPOSITO, SPEI_RECIBIDO)
  - Targets  → ingreso × 50/30/20 (sin necesidad de est_budgets)
  - Límites opcionales por categoría → est_budgets
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
from datetime import datetime
import calendar
from utils import today_str, today_date, csv_response
from modules.finanzas.estados.prestamos import perdidos_en_rango, perdidos_detalle_en_rango

budget_bp = Blueprint('budget', __name__, template_folder='../../templates')

# ── Regla 50-30-20 ────────────────────────────────────────────────────────────
CATEGORIAS = ['necesidades', 'deseos', 'ahorro_deuda']
PCTS       = {'necesidades': 0.50, 'deseos': 0.30, 'ahorro_deuda': 0.20}

# Mapeo categoria → bucket (None = excluir del gasto visible)
#
# NOTA taxonomía 2026-09 (sprint de categorías): antes VIVERES/SUPER
# (necesidades) y COMIDA/REST + CAFE/PAN (deseos) eran categorías separadas.
# Se fusionaron en una sola categoria ALIMENTACION (Súper/Conveniencia/
# Restaurante/Fast Food/Delivery) -- este mapeo por bucket ya no puede
# distinguir "víveres" de "comer fuera" dentro de esa categoria. Se dejó en
# 'necesidades' (la comida en sí es una necesidad, se coma en casa o
# fuera) pero si se quiere recuperar el split completo de antes, hay que
# hacer CATEGORIA_BUCKET y _calc_budget conscientes de subcategoria, no
# solo categoria -- no se hizo aquí porque no se pidió, para no ampliar el
# alcance de lo confirmado.
#
# CAFE/PAN sí se revivió como categoria propia (2026-09, a petición
# explícita) -- café y pan son un "deseo" distinto de comprar despensa o
# comer en restaurante, así que se sacó de ALIMENTACION otra vez.
CATEGORIA_BUCKET = {
    # 2026-09: ALIMENTACION se separó en SUPER (necesidad) y COMIDA_FUERA
    # (deseo) -- ver _corregir_alimentacion_split en estados/routes.py.
    'SUPER':             'necesidades',
    'COMIDA_FUERA':      'deseos',
    'ALIMENTACION':      'necesidades',  # legado, ya no se genera
    'CAFE/PAN':          'deseos',  # revivida como categoria propia -- café/pan
                                     # siempre fue "deseo" aquí, no necesidad
    'VIVIENDA':          'necesidades',
    'TRANSPORTE':        'necesidades',
    'SALUD':             'necesidades',
    'CUIDADO_PERSONAL':  'deseos',
    'ROPA':              'deseos',
    'DIGITAL':           'deseos',
    'DEPORTE':           'deseos',
    'OCIO':              'deseos',
    'SALSA':             'deseos',
    'VIAJES':            'deseos',
    'FAMILIA_REGALOS':   'deseos',
    'OTROS':             'deseos',
    'APRENDIZAJE':       'ahorro_deuda',
    'INVERSION':         'ahorro_deuda',
    'COSTOS_FINANCIEROS':'ahorro_deuda',  # intereses/comisiones/penalizaciones -- gasto evitable real, sí debe verse
    'EXPENSE':           None,            # Informativo – se reembolsa, no afecta buckets
    'APORTACION_RENTA':  None,            # legado -- ya no se genera, ahora es VIVIENDA/Renta
    'PROYECTOS':         'deseos',        # Hosting/Software; Publicidad y Reclutamiento se excluyen (_GASTO_WHERE)
    'PUBLICIDAD':        None,            # legado, ver PROYECTOS
    # Excluidos del gasto de consumo (movimientos, no gasto real)
    'PAGO_TDC':          None,
    'PAGO':              None,
    'TRANSFERENCIA':     None,
    'SPEI_ENVIADO':      None,
    'RETIRO':            None,
    'FINANZAS':          'deseos',        # transferencias/retiros/cargos: se ven para reclasificar (ver _GASTO_WHERE)
    'NOMINA':            None,
    'PRESTAMOS':         None,            # por cobrar, no consumo (ver _GASTO_EXCLUIR)
}

# Categorías de ingreso que NO son ingreso real
#
# NOTA (2026-09, a petición del usuario): DEPOSITO, SPEI_RECIBIDO,
# TRANSFERENCIA, PAGO_TDC y RETIRO eran categorías legacy que ya no se
# generan -- la migración finanzas_legacy_bancario_a_finanzas_2026_09 las
# reclasifica todas a categoria='FINANZAS'. Se agrega 'FINANZAS' aquí para
# que sigan excluidas del ingreso real (igual que EXPENSE/FINANZAS ya
# están excluidas del lado de gasto arriba); sin este agregado, en cuanto
# cambiara su categoria habrían empezado a contarse de más como ingreso
# real -- el usuario pidió explícitamente evitar eso. Se dejan también los
# nombres viejos por si queda alguna fila sin migrar.
# PRESTAMOS: una devolución de préstamo no es ingreso, solo baja el pendiente
# en «Por cobrar» (Estados de cuenta ya lo excluía; aquí faltaba).
_INGRESO_EXCLUIR = ('TRANSFERENCIA', 'PAGO_TDC', 'RETIRO', 'DEPOSITO', 'SPEI_RECIBIDO',
                     'APORTACION_RENTA', 'FINANZAS', 'PRESTAMOS')

# Fila sintética de la Radiografía: aportaciones − retiros de tipo INVERSION.
INVERSIONES_NETAS = '__INVERSIONES__'

CAT_LABELS = {
    'SUPER':            'Súper',
    'COMIDA_FUERA':     'Comida fuera',
    'ALIMENTACION':     'Alimentación',
    'CAFE/PAN':         'Café & Pan',
    'VIVIENDA':         'Vivienda',
    'TRANSPORTE':       'Transporte',
    'SALUD':            'Salud',
    'CUIDADO_PERSONAL': 'Cuidado personal',
    'ROPA':             'Ropa',
    'DIGITAL':          'Digital',
    'DEPORTE':          'Deporte',
    'OCIO':             'Ocio',
    'SALSA':            'Salsa / Baile',
    'VIAJES':           'Viajes',
    'FAMILIA_REGALOS':  'Familia y regalos',
    'PROYECTOS':        'Proyectos',
    'COSTOS_FINANCIEROS':'Costos financieros',
    'APRENDIZAJE':      'Aprendizaje',
    'INVERSION':        'Ahorro',
    'OTROS':            'Otros',
    INVERSIONES_NETAS:  'Inversiones (neto)',
    'EXPENSE':          'EXPENSE',
    'APORTACION_RENTA': 'Aportación renta',
    'FINANZAS':         'Finanzas / Movimientos bancarios',
    'NOMINA':           'Nómina adelanto',
}


def _inversiones_mes(db, desde, hasta):
    r = db.execute("""
        SELECT COALESCE(SUM(CASE WHEN subcategoria='APORTACION' THEN ABS(monto) END), 0) AS aport,
               COALESCE(SUM(CASE WHEN subcategoria='RETIRO'     THEN ABS(monto) END), 0) AS ret,
               COUNT(*) AS n
        FROM est_movimientos
        WHERE tipo='INVERSION' AND subcategoria IN ('APORTACION', 'RETIRO')
          AND categoria != 'OTRO'   -- plataforma no reconocida: no es ahorro real (inversiones.SIN_SALDO)
          AND fecha >= ? AND fecha < ?""", (desde, hasta)).fetchone()
    aport, ret = round(float(r['aport']), 2), round(float(r['ret']), 2)
    return {'aportado': aport, 'retirado': ret, 'neto': round(aport - ret, 2), 'n': int(r['n'])}


# Ingreso recurrente: el sueldo = NOMINA / Pago nominal. También NOMINA sin
# subcategoría: la regla automática solo etiqueta «Pago nominal» a la nómina
# de $9k-12k, y las nóminas viejas o fuera de rango quedaron sin subcategoría;
# Bono / PTU / Fondo de ahorro siempre llevan la suya. Lo demás (bonos, PTU, fondo de ahorro,
# regalos, reembolsos de siniestro…) es extraordinario: se muestra aparte y no
# entra a Disponible ni a las metas, para que un mes con un extra grande no
# esconda el déficit del sueldo. Las devoluciones de préstamos no son ingreso
# (categoría PRESTAMOS, en _INGRESO_EXCLUIR).
_RECURRENTE_CAT, _RECURRENTE_SUBS = 'NOMINA', ('Pago nominal', '')
# La aportación del roomie a la renta no es ingreso: la renta ya cuenta solo
# tu parte (mi_parte). Misma regla que estados/routes.py::_INGRESO_EXCLUIR_SQL.
_NO_APORTACION_RENTA = "NOT (categoria='VIVIENDA' AND COALESCE(subcategoria,'')='Aportación renta')"


def _ingresos_mes(db, mes, desde, hasta):
    """{'total', 'recurrente', 'extraordinario', 'base', 'es_override'}. base
    es el recurrente; si en el mes no hay, el ingreso manual del mes
    (budget_meses) si lo hay, y si no, 0."""
    excl_ph = ','.join('?' * len(_INGRESO_EXCLUIR))
    r = db.execute(
        f"""SELECT COALESCE(SUM(monto), 0) AS total,
                  COALESCE(SUM(CASE WHEN categoria=? AND COALESCE(subcategoria, '') IN (?, ?)
                                    THEN monto END), 0) AS recurrente
           FROM est_movimientos
           WHERE tipo='INGRESO' AND categoria NOT IN ({excl_ph}) AND {_NO_APORTACION_RENTA}
             AND fecha >= ? AND fecha < ?""",
        [_RECURRENTE_CAT, *_RECURRENTE_SUBS, *_INGRESO_EXCLUIR, desde, hasta]).fetchone()
    total, recurrente = round(float(r['total']), 2), round(float(r['recurrente']), 2)
    base, es_override = recurrente, False
    if recurrente <= 0:
        ov = db.execute("SELECT ingreso_total FROM budget_meses WHERE mes=?", (mes,)).fetchone()
        if ov and ov['ingreso_total']:
            base, es_override = float(ov['ingreso_total']), True
    return {'total': total, 'recurrente': recurrente,
            'extraordinario': round(total - recurrente, 2), 'base': base, 'es_override': es_override}


# Meta mínima del grupo Ahorro y deudas: es un piso (verde al alcanzarla o
# superarla, rojo por debajo), a diferencia de Necesidades/Deseos cuya meta
# es un tope. El 20 % del ingreso recurrente se sigue mostrando de referencia.
META_AHORRO_KEY = 'presupuesto_meta_ahorro'
META_AHORRO_DEFAULT = 4000.0


def _meta_ahorro(db) -> float:
    r = db.execute("SELECT value FROM app_settings WHERE key=?", (META_AHORRO_KEY,)).fetchone()
    try:
        return float(r['value']) if r else META_AHORRO_DEFAULT
    except (TypeError, ValueError):
        return META_AHORRO_DEFAULT


# Categorías de GASTO que no son consumo y nunca entran a la Radiografía
# (misma lista para el cálculo del mes y para la racha). PRESTAMOS: dinero
# prestado no es gasto -- se sigue en «Por cobrar»; antes caía en Deseos por
# no tener bucket (CATEGORIA_BUCKET.get(cat, 'deseos')).
_GASTO_EXCLUIR = ('PAGO_TDC', 'PAGO', 'TRANSFERENCIA', 'SPEI_ENVIADO', 'RETIRO',
                  'PUBLICIDAD', 'NOMINA', 'EXPENSE',
                  'APORTACION_RENTA', 'PRESTAMOS')
# FINANZAS ya no se excluye entera (pedido del usuario 2026-09-26): sus
# transferencias enviadas, retiros de efectivo, cargos bancarios, etc. sí
# salen de tu bolsillo y su clasificación no es 100 % fiable, así que se ven
# en la Radiografía (bucket Deseos, como OTROS) para poder reclasificarlas.
# Solo quedan fuera las subcategorías que nunca son gasto (misma lista que
# estados/routes.py::_FINANZAS_NO_GASTO_SUBCATS).
_FINANZAS_NO_GASTO = ('Transferencia recibida', 'Depósito', 'Fideicomiso', 'Reembolsable')
# PROYECTOS ya no se excluye entero: Hosting y Software son gasto propio y
# cuentan en Deseos; Publicidad y Reclutamiento son gasto de trabajo y quedan
# fuera, igual que EXPENSE.
_PROYECTOS_EXCLUIR = ('Publicidad', 'Reclutamiento')
_GASTO_WHERE = ("categoria NOT IN (" + ",".join(f"'{c}'" for c in _GASTO_EXCLUIR) + ")"
                " AND NOT (categoria='PROYECTOS' AND COALESCE(subcategoria,'') IN ("
                + ",".join(f"'{s}'" for s in _PROYECTOS_EXCLUIR) + "))"
                " AND NOT (categoria='FINANZAS' AND COALESCE(subcategoria,'') IN ("
                + ",".join(f"'{s}'" for s in _FINANZAS_NO_GASTO) + "))")

BUCKET_META = {
    'necesidades': {'label': 'Necesidades',      'pct_target': 50, 'color': '#2a8a62', 'cls': 'bk-nec'},
    'deseos':      {'label': 'Deseos',            'pct_target': 30, 'color': '#467aa8', 'cls': 'bk-des'},
    'ahorro_deuda':{'label': 'Ahorro y Deudas',  'pct_target': 20, 'color': '#7d5c9c', 'cls': 'bk-aho'},
}


# ── Auth ──────────────────────────────────────────────────────────────────────

@budget_bp.before_request
def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_month_with_data(db):
    """Devuelve el mes (YYYY-MM) más reciente con ≥5 movimientos."""
    row = db.execute("""
        SELECT substr(fecha,1,7) mes, COUNT(*) n
        FROM est_movimientos
        GROUP BY mes
        HAVING n >= 5
        ORDER BY mes DESC
        LIMIT 1
    """).fetchone()
    return row['mes'] if row else None


def _racha_bajo_presupuesto(db, mes_hasta, max_meses=12):
    """
    Recorre hacia atrás desde `mes_hasta` (YYYY-MM) mes por mes, comparando
    ingreso real vs. gasto real (mismos filtros que _calc_budget). Un mes
    cuenta como "bajo presupuesto" si tuvo datos reales (>=5 movimientos) y
    gastó <= ingreso. La racha es la cadena de meses consecutivos así desde
    el mes más reciente con datos; se corta en el primer mes que la rompe o
    que no tiene datos suficientes.

    Devuelve (racha, meses) donde `meses` es la lista de los últimos
    `max_meses` (más antiguo primero) con status 'ok' | 'over' | 'sin_datos',
    para pintar una tira tipo heatmap.
    """
    y, m = int(mes_hasta[:4]), int(mes_hasta[5:])

    meses = []
    racha = 0
    racha_rota = False

    for _ in range(max_meses):
        mes = f"{y}-{m:02d}"
        mes_inicio = f"{mes}-01"
        next_m, next_y = (m + 1, y) if m < 12 else (1, y + 1)
        mes_fin = f"{next_y}-{next_m:02d}-01"

        n = db.execute(
            "SELECT COUNT(*) n FROM est_movimientos WHERE fecha >= ? AND fecha < ?",
            (mes_inicio, mes_fin)
        ).fetchone()['n']

        if n < 5:
            meses.append({'mes': mes, 'status': 'sin_datos'})
            racha_rota = True
        else:
            ingreso = _ingresos_mes(db, mes, mes_inicio, mes_fin)['base']
            gasto = db.execute(
                f"""SELECT COALESCE(SUM(COALESCE(mi_parte, monto)),0) t FROM est_movimientos
                   WHERE tipo='GASTO'
                     AND {_GASTO_WHERE}
                     AND fecha >= ? AND fecha < ?""",
                (mes_inicio, mes_fin)
            ).fetchone()['t'] + perdidos_en_rango(db, mes_inicio, mes_fin) \
              + _inversiones_mes(db, mes_inicio, mes_fin)['neto']

            if ingreso <= 0:
                meses.append({'mes': mes, 'status': 'sin_datos'})
                racha_rota = True
            else:
                ok = gasto <= ingreso
                meses.append({'mes': mes, 'status': 'ok' if ok else 'over'})
                if not ok:
                    racha_rota = True

        if not racha_rota:
            racha += 1

        m -= 1
        if m == 0:
            m, y = 12, y - 1

    meses.reverse()
    return racha, meses


def _calc_budget(mes, db):
    """Calcula toda la data del presupuesto para un mes dado."""
    y, m   = int(mes[:4]), int(mes[5:])
    next_m = m + 1 if m < 12 else 1
    next_y = y if m < 12 else y + 1
    next_mes  = f"{next_y}-{next_m:02d}"
    mes_inicio = f"{mes}-01"
    mes_fin    = f"{next_mes}-01"

    excl_ph = ','.join('?' * len(_INGRESO_EXCLUIR))

    # ── Ingreso: Disponible y metas 50-30-20 usan solo el recurrente (ver
    #    _ingresos_mes); el extraordinario se muestra aparte.
    ing = _ingresos_mes(db, mes, mes_inicio, mes_fin)
    ingreso_real = ing['base']
    ingreso_es_override = ing['es_override']

    # ── Gasto real por categoría
    spending_rows = db.execute(
        f"""SELECT categoria, SUM(COALESCE(mi_parte, monto)) AS total, COUNT(*) AS n
           FROM est_movimientos
           WHERE tipo='GASTO'
             AND {_GASTO_WHERE}
             AND fecha >= ? AND fecha < ?
           GROUP BY categoria
           ORDER BY total DESC""",
        (mes_inicio, mes_fin)
    ).fetchall()
    spending_rows = [dict(r) for r in spending_rows]

    # ── Préstamos perdidos que se prestaron este mes: su pendiente es gasto
    #    en Familia y regalos (registro interno, no hay movimiento bancario).
    perdido = perdidos_en_rango(db, mes_inicio, mes_fin)
    if perdido > 0:
        fam = next((r for r in spending_rows if r['categoria'] == 'FAMILIA_REGALOS'), None)
        if fam:
            fam['total'] = float(fam['total'] or 0) + perdido
            fam['perdido'] = perdido
        else:
            spending_rows.append({'categoria': 'FAMILIA_REGALOS', 'total': perdido, 'n': 0, 'perdido': perdido})

    # ── Límites opcionales (est_budgets)
    budgets_map = {r['categoria']: float(r['limite'] or 0)
                   for r in db.execute("SELECT categoria, limite FROM est_budgets").fetchall()}

    # ── Ingresos desglose (para mostrar de dónde viene el ingreso)
    ingresos_rows = db.execute(
        f"""SELECT categoria, SUM(monto) AS total
           FROM est_movimientos
           WHERE tipo='INGRESO'
             AND categoria NOT IN ({excl_ph}) AND {_NO_APORTACION_RENTA}
             AND fecha >= ? AND fecha < ?
           GROUP BY categoria ORDER BY total DESC""",
        list(_INGRESO_EXCLUIR) + [mes_inicio, mes_fin]
    ).fetchall()

    # ── Conteo total
    n_movimientos = db.execute(
        "SELECT COUNT(*) n FROM est_movimientos WHERE fecha >= ? AND fecha < ?",
        (mes_inicio, mes_fin)
    ).fetchone()['n']

    # ── Construir cats_data
    # Lógica de barra:
    #   - Con presupuesto configurado (limite > 0): pct = gastado/limite → métrica vs. presupuesto real
    #   - Sin presupuesto: pct = gastado/bucket_target → % del bucket como fallback informativo
    cats_data = []
    for row in spending_rows:
        cat    = row['categoria']
        bucket = CATEGORIA_BUCKET.get(cat, 'deseos')
        if bucket is None:
            continue
        gastado       = float(row['total'] or 0)
        limite        = budgets_map.get(cat, 0.0)
        bucket_target = round(ingreso_real * PCTS[bucket], 2)

        if limite > 0:
            # Presupuesto real configurado → barra mide gastado/limite
            pct         = round(gastado / limite * 100, 1)
            pct_bucket  = round(gastado / bucket_target * 100, 1) if bucket_target > 0 else 0
            tiene_limite = True
            if pct >= 100:
                status = 'over'
            elif pct >= 80:
                status = 'warn'
            else:
                status = 'ok'
        else:
            # Sin presupuesto → barra mide peso relativo en el bucket
            pct         = round(gastado / bucket_target * 100, 1) if bucket_target > 0 else 0
            pct_bucket  = pct
            tiene_limite = False
            if pct >= 60:
                status = 'over'
            elif pct >= 35:
                status = 'warn'
            else:
                status = 'ok'

        cats_data.append({
            'categoria':    cat,
            'nombre':       CAT_LABELS.get(cat, cat),
            'limite':       limite,
            'gastado':      gastado,
            'n':            int(row['n'] or 0),
            'perdido':      row.get('perdido', 0),
            'pct':          pct,
            'pct_bucket':   pct_bucket,
            'tiene_limite': tiene_limite,
            'bucket':       bucket,
            'bucket_target': bucket_target,
            'status':       status,
        })

    # ── Inversiones del mes (tipo INVERSION, categoría = plataforma GBM/CETES…):
    #    aportaciones − retiros, con la dirección tomada de la subcategoría
    #    (el signo del monto no es confiable). RENDIMIENTO no cuenta: no es
    #    dinero que el usuario aparta. No se cruza con los gastos de categoría
    #    INVERSION (tipo GASTO), que siguen como su propia fila: tipos distintos,
    #    así que nada se cuenta dos veces. El neto puede ser negativo.
    inv = _inversiones_mes(db, mes_inicio, mes_fin)
    if inv['n']:
        cats_data.append({
            'categoria':    INVERSIONES_NETAS,
            'nombre':       CAT_LABELS[INVERSIONES_NETAS],
            'limite':       0.0,
            'gastado':      inv['neto'],
            'n':            inv['n'],
            'pct':          round(inv['neto'] / (ingreso_real * PCTS['ahorro_deuda']) * 100, 1) if ingreso_real > 0 else 0,
            'pct_bucket':   0,
            'tiene_limite': False,
            'bucket':       'ahorro_deuda',
            'bucket_target': round(ingreso_real * PCTS['ahorro_deuda'], 2),
            'status':       'ok' if inv['neto'] >= 0 else 'over',
            'inversion':    inv,
        })

    # ── Agrupar por bucket
    buckets = {}
    for bk in CATEGORIAS:
        bk_cats       = [c for c in cats_data if c['bucket'] == bk]
        total_gastado = round(sum(c['gastado'] for c in bk_cats), 2)
        target_monto  = round(ingreso_real * PCTS[bk], 2)
        pct_of_income = round(total_gastado / ingreso_real * 100, 1) if ingreso_real > 0 else 0
        pct_of_target = min(round(total_gastado / target_monto * 100) if target_monto > 0 else 0, 999)
        buckets[bk] = {
            **BUCKET_META[bk],
            'cats':           sorted(bk_cats, key=lambda c: -c['gastado']),
            'total_gastado':  total_gastado,
            'target_monto':   target_monto,
            'pct_of_income':  pct_of_income,
            'pct_of_target':  pct_of_target,
            'over':           total_gastado > target_monto,
        }

    # Ahorro y deudas: la meta mínima decide el color (piso, no tope). 'over'
    # conserva su sentido de «en rojo» para el hero y el mini-resumen.
    ah = buckets['ahorro_deuda']
    meta = _meta_ahorro(db)
    ah['meta_minima'] = meta
    ah['cumple_meta'] = ah['total_gastado'] >= meta
    ah['over'] = not ah['cumple_meta']
    ah['pct_of_meta'] = max(min(round(ah['total_gastado'] / meta * 100) if meta > 0 else 100, 999), 0)

    total_gastado = round(sum(c['gastado'] for c in cats_data), 2)
    disponible    = round(ingreso_real - total_gastado, 2)

    # Barra segmentada: % del ingreso gastado en cada bucket
    seg = {}
    for bk in CATEGORIAS:
        seg[bk] = max(round(buckets[bk]['total_gastado'] / ingreso_real * 100, 1), 0) if ingreso_real > 0 else 0

    dias_mes      = calendar.monthrange(y, m)[1]
    today         = today_date()
    es_mes_actual = (today.strftime('%Y-%m') == mes)
    dia_actual    = today.day if es_mes_actual else dias_mes
    # La proyección extrapola solo el consumo; las inversiones son aportaciones
    # puntuales y se suman tal cual.
    consumo       = total_gastado - inv['neto']
    proyeccion    = round(consumo / dia_actual * dias_mes + inv['neto']) if dia_actual > 0 and total_gastado > 0 else 0

    return {
        'ingreso_real':       ingreso_real,          # base: recurrente (o manual)
        'ingreso_es_override':ingreso_es_override,
        'ingreso_recurrente': ing['recurrente'],
        'ingreso_extraordinario': ing['extraordinario'],
        'ingreso_total':      ing['total'],
        'ingresos_detalle':   [dict(r) for r in ingresos_rows],
        'n_movimientos':      n_movimientos,
        'total_gastado':      total_gastado,
        'disponible':         disponible,
        'proyeccion':         proyeccion,
        'dia_actual':         dia_actual,
        'dias_mes':           dias_mes,
        'es_mes_actual':      es_mes_actual,
        'buckets':            buckets,
        'seg':                seg,
        'mes_inicio':         mes_inicio,
    }


# ── Vista principal ───────────────────────────────────────────────────────────

@budget_bp.route('/')
@budget_bp.route('/<mes>')
def index(mes=None):
    today = today_date()

    with get_db() as db:
        if not mes:
            # Usa el mes actual si tiene ≥1 movimiento; si no, último con datos
            cur_mes = today.strftime('%Y-%m')
            n_cur   = db.execute(
                "SELECT COUNT(*) n FROM est_movimientos WHERE fecha >= ? AND fecha < ?",
                (f"{cur_mes}-01", f"{today.strftime('%Y')}-{today.month+1:02d}-01"
                 if today.month < 12 else f"{today.year+1}-01-01")
            ).fetchone()['n']
            mes = cur_mes if n_cur >= 1 else (_last_month_with_data(db) or cur_mes)

        y, m = int(mes[:4]), int(mes[5:])
        prev_mes = f"{y}-{m-1:02d}" if m > 1  else f"{y-1}-12"
        next_mes = f"{y}-{m+1:02d}" if m < 12 else f"{y+1}-01"

        data = _calc_budget(mes, db)

        # Racha siempre anclada al mes más reciente con datos, no al mes que
        # se está navegando — para que no "cambie" al ver meses pasados.
        cur_mes = today.strftime('%Y-%m')
        n_cur = db.execute(
            "SELECT COUNT(*) n FROM est_movimientos WHERE fecha >= ? AND fecha < ?",
            (f"{cur_mes}-01", f"{today.year}-{today.month+1:02d}-01"
             if today.month < 12 else f"{today.year+1}-01-01")
        ).fetchone()['n']
        mes_racha = cur_mes if n_cur >= 1 else (_last_month_with_data(db) or cur_mes)
        racha_meses, racha_historial = _racha_bajo_presupuesto(db, mes_racha)

    return render_template(
        'finanzas/budget.html',
        mes=mes, prev_mes=prev_mes, next_mes=next_mes,
        racha_meses=racha_meses, racha_historial=racha_historial,
        **data,
    )


# ── Exportar CSV ──────────────────────────────────────────────────────────────

@budget_bp.route('/api/export')
def export_csv():
    """Gasto por categoría de los últimos `n` meses (hasta `hasta`, incluido)
    con promedio y límite configurado, más ingreso/gasto/disponible por mes:
    la base para armar el presupuesto en una hoja de cálculo."""
    hasta = request.args.get('hasta') or today_date().strftime('%Y-%m')
    try:
        y, m = int(hasta[:4]), int(hasta[5:7])
        n = max(1, min(int(request.args.get('n', 6)), 24))
    except ValueError:
        return jsonify({'error': 'parámetros inválidos'}), 400
    meses = []
    for _ in range(n):
        meses.insert(0, f"{y}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)

    with get_db() as db:
        datos = {mes: _calc_budget(mes, db) for mes in meses}
        limites = {r['categoria']: float(r['limite'] or 0)
                   for r in db.execute("SELECT categoria, limite FROM est_budgets").fetchall()}

    # categoria → {mes: gastado}, agrupado por bucket en el orden 50/30/20
    gasto = {}
    for mes, d in datos.items():
        for bk in CATEGORIAS:
            for c in d['buckets'][bk]['cats']:
                gasto.setdefault((bk, c['categoria']), {})[mes] = c['gastado']

    def fila(label_bk, label_cat, vals, limite=''):
        prom = round(sum(vals) / len(vals), 2) if vals else 0
        return [label_bk, label_cat, *[round(v, 2) for v in vals], prom, limite]

    rows = []
    for bk in CATEGORIAS:
        cats = sorted((c for (b, c) in gasto if b == bk),
                      key=lambda c: -sum(gasto[(bk, c)].values()))
        for cat in cats:
            vals = [gasto[(bk, cat)].get(mes, 0) for mes in meses]
            rows.append(fila(BUCKET_META[bk]['label'], CAT_LABELS.get(cat, cat), vals, limites.get(cat) or ''))
        rows.append(fila(BUCKET_META[bk]['label'], f"Subtotal (meta {BUCKET_META[bk]['pct_target']} % del ingreso)",
                         [datos[mes]['buckets'][bk]['total_gastado'] for mes in meses]))
    rows.append([])
    rows.append(fila('Resumen', 'Ingreso recurrente', [datos[mes]['ingreso_real'] for mes in meses]))
    rows.append(fila('Resumen', 'Ingreso extraordinario', [datos[mes]['ingreso_extraordinario'] for mes in meses]))
    rows.append(fila('Resumen', 'Gasto total', [datos[mes]['total_gastado'] for mes in meses]))
    rows.append(fila('Resumen', 'Disponible', [datos[mes]['disponible'] for mes in meses]))

    return csv_response(['Grupo', 'Categoría', *meses, 'Promedio', 'Límite mensual'],
                        rows, f"presupuesto_{meses[0]}_a_{meses[-1]}.csv")


@budget_bp.route('/api/meta-ahorro', methods=['POST'])
def set_meta_ahorro():
    d = request.get_json(silent=True) or {}
    try:
        valor = round(float(d.get('valor')), 2)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Monto inválido'}), 400
    if valor <= 0 or valor > 10_000_000:
        return jsonify({'ok': False, 'error': 'La meta debe ser mayor a 0'}), 400
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (META_AHORRO_KEY, str(valor)))
        db.commit()
    return jsonify({'ok': True, 'valor': valor})


# ── API: Reclasificar DEPOSITO / SPEI ─────────────────────────────────────────

@budget_bp.route('/api/reclasificar/<int:mov_id>', methods=['POST'])
def reclasificar(mov_id):
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    d       = request.json or {}
    accion  = d.get('accion')
    cat_new = d.get('categoria', 'OTROS')

    with get_db() as db:
        row = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mov_id,)).fetchone()
        if not row:
            return jsonify({'error': 'no encontrado'}), 404
        if row['categoria'] not in ('DEPOSITO', 'SPEI_RECIBIDO'):
            return jsonify({'error': 'solo DEPOSITO / SPEI_RECIBIDO'}), 400
        if accion == 'ingreso':
            db.execute("UPDATE est_movimientos SET categoria=? WHERE id=?", (cat_new, mov_id))
        elif accion == 'excluir':
            # 'TRANSFERENCIA' era el marcador legacy -- se usa 'FINANZAS' /
            # 'Transferencia' ahora, igual que la migración
            # finanzas_legacy_bancario_a_finanzas_2026_09, para no volver a
            # generar la categoria vieja que ya se quitó del dropdown.
            db.execute(
                "UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Transferencia' WHERE id=?",
                (mov_id,),
            )
        else:
            return jsonify({'error': 'accion inválida'}), 400
        db.commit()
    return jsonify({'ok': True})


# ── API: Ingreso manual override ──────────────────────────────────────────────

@budget_bp.route('/api/ingreso', methods=['POST'])
def set_ingreso_override():
    d     = request.json or {}
    mes   = d.get('mes')
    monto = float(d.get('ingreso_total') or 0)
    if not mes:
        return jsonify({'error': 'mes requerido'}), 400
    with get_db() as db:
        db.execute("""
            INSERT INTO budget_meses (mes, ingreso_total, created_at)
            VALUES (?,?,?)
            ON CONFLICT(mes) DO UPDATE SET ingreso_total=excluded.ingreso_total
        """, (mes, monto, datetime.now().isoformat()))
        db.commit()
    return jsonify({'ok': True, 'mes': mes, 'ingreso_total': monto})


# ── API: Movimientos por categoría (drill-down) ───────────────────────────────

@budget_bp.route('/api/cat-movs/<mes>/<path:categoria>')
def cat_movimientos(mes, categoria):
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    y, m   = int(mes[:4]), int(mes[5:])
    next_m = m + 1 if m < 12 else 1
    next_y = y if m < 12 else y + 1
    mes_ini = f"{mes}-01"
    mes_fin = f"{next_y}-{next_m:02d}-01"
    with get_db() as db:
        # Mismo filtro que la fila de la Radiografía (p. ej. Proyectos sin Publicidad).
        rows = db.execute(f"""
            SELECT id, fecha, descripcion, monto, COALESCE(mi_parte, monto) AS mi_monto,
                   categoria, banco, tipo
            FROM est_movimientos
            WHERE categoria = ?
              AND tipo IN ('GASTO','INVERSION')
              AND fecha >= ? AND fecha < ?
              AND {_GASTO_WHERE}
            ORDER BY fecha DESC, id DESC
        """, (categoria, mes_ini, mes_fin)).fetchall()
        # Los préstamos perdidos que se prestaron este mes también suman a
        # Familia y regalos en la Radiografía (ver radiografia()); sin
        # listarlos aquí el detalle no cuadraba con la barra.
        perdidos = []
        if categoria == 'FAMILIA_REGALOS':
            perdidos = [{
                'prestamo_id': p['id'], 'persona': p['persona'], 'fecha': p['fecha'],
                'perdido_fecha': p['perdido_fecha'][:10], 'pendiente': p['pendiente'],
                'descripcion': p['descripcion'] or p['notas'],
            } for p in perdidos_detalle_en_rango(db, mes_ini, mes_fin)]
    return jsonify({'movimientos': [dict(r) for r in rows], 'perdidos': perdidos})


# ── API: Editar movimiento (categoría + monto mi_parte) ──────────────────────

@budget_bp.route('/api/mov/<int:mov_id>', methods=['PATCH'])
def editar_movimiento(mov_id):
    if not session.get('fin_ok'):
        return jsonify({'error': 'locked'}), 403
    d = request.json or {}
    with get_db() as db:
        row = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mov_id,)).fetchone()
        if not row:
            return jsonify({'error': 'no encontrado'}), 404

        fields, vals = [], []
        if 'categoria' in d:
            fields.append('categoria=?'); vals.append(d['categoria'].upper().strip())
        if 'descripcion' in d:
            fields.append('descripcion=?'); vals.append(str(d['descripcion'])[:300])
        if 'mi_parte' in d:
            mp = float(d['mi_parte'])
            fields.append('mi_parte=?'); vals.append(mp if mp > 0 else None)
        # Si cambia a tipo INVERSION, actualizar tipo también
        if 'tipo' in d and d['tipo'] in ('GASTO', 'INGRESO', 'PAGO', 'INVERSION'):
            fields.append('tipo=?'); vals.append(d['tipo'])

        if not fields:
            return jsonify({'error': 'nada que actualizar'}), 400

        vals.append(mov_id)
        db.execute(f"UPDATE est_movimientos SET {', '.join(fields)} WHERE id=?", vals)
        db.commit()
        updated = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mov_id,)).fetchone()
    return jsonify({'ok': True, 'mov': dict(updated)})


# ── API: Mini-resumen ─────────────────────────────────────────────────────────

@budget_bp.route('/api/mini-summary')
@budget_bp.route('/api/mini-summary/<mes>')
def mini_summary(mes=None):
    if not session.get('fin_ok'):
        return jsonify({'locked': True})
    today = today_date()
    if not mes:
        mes = today.strftime('%Y-%m')
    with get_db() as db:
        data = _calc_budget(mes, db)
    buckets_out = {}
    for bk, bd in data['buckets'].items():
        buckets_out[bk] = {
            'gastado': bd['total_gastado'],
            'target':  bd['target_monto'],
            'pct':     bd['pct_of_target'],
            'over':    bd['over'],
        }
    return jsonify({
        'mes':           mes,
        'ingreso':       data['ingreso_real'],
        'total_gastado': data['total_gastado'],
        'disponible':    data['disponible'],
        'buckets':       buckets_out,
    })
