"""
Budget 50-30-20 — radiografía en vivo de est_budgets + est_movimientos.

Fuente de verdad:
  - Gastos   → est_movimientos (tipo='GASTO')
  - Ingresos → est_movimientos (tipo='INGRESO', excluye TRANSFERENCIA y PAGO_TDC)
  - Límites  → est_budgets (editables desde budget.html y el SPA de Estados)
  - Override → budget_meses.ingreso_total (fallback si no hay movimientos de ingreso)
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
from datetime import datetime
import calendar
from utils import today_str, today_date

budget_bp = Blueprint('budget', __name__, template_folder='../../templates')

CATEGORIAS = ['necesidades', 'deseos', 'ahorro_deuda']
PCTS       = {'necesidades': 0.50, 'deseos': 0.30, 'ahorro_deuda': 0.20}

# Maps est_movimientos.categoria → 50-30-20 bucket  (None = excluir del cálculo)
CATEGORIA_BUCKET = {
    'COMIDA/REST':       'deseos',
    'VIVERES/SUPER':     'necesidades',
    'CASA/HOGAR':        'necesidades',
    'GASOLINA/AUTO':     'necesidades',
    'ROPA':              'deseos',
    'SALUD':             'necesidades',
    'TECH/DIGITAL':      'deseos',
    'SUSCRIPCIONES':     'deseos',
    'ENTRETENIMIENTO':   'deseos',
    'SALSA':             'deseos',
    'VIAJES/VUELOS':     'deseos',
    'TRANSPORTE':        'necesidades',
    'APRENDIZAJE':       'deseos',
    'INVERSION':         'ahorro_deuda',
    'CAFE/PAN':          'deseos',
    'GYM':               'necesidades',
    'DEPORTE':           'deseos',
    'REGALO':            'deseos',
    'OTROS':             'deseos',
    'EXPENSE':           'deseos',       # catch-all del parser
    # Excluidos — no son gasto de consumo real
    'PUBLICIDAD':        None,
    'FINANZAS':          None,           # comisiones bancarias / intereses TDC
    'NOMINA':            None,           # adelanto de nómina categorizado como gasto
    'PAGO_TDC':          None,
    'PAGO':              None,
    'TRANSFERENCIA':     None,
    'SPEI_ENVIADO':      None,
    'RETIRO':            None,
}

# Categorías de INGRESO que NO son ingreso real
_INGRESO_EXCLUIR = ('TRANSFERENCIA', 'PAGO_TDC', 'RETIRO')

# Etiquetas legibles
CAT_LABELS = {
    'COMIDA/REST':     'Comida / Restaurante',
    'VIVERES/SUPER':   'Víveres / Súper',
    'CASA/HOGAR':      'Casa / Hogar',
    'GASOLINA/AUTO':   'Gasolina / Auto',
    'ROPA':            'Ropa',
    'SALUD':           'Salud',
    'TECH/DIGITAL':    'Tech / Digital',
    'SUSCRIPCIONES':   'Suscripciones',
    'ENTRETENIMIENTO': 'Entretenimiento',
    'SALSA':           'Salsa',
    'VIAJES/VUELOS':   'Viajes / Vuelos',
    'TRANSPORTE':      'Transporte',
    'APRENDIZAJE':     'Aprendizaje',
    'INVERSION':       'Inversión',
    'CAFE/PAN':        'Café / Pan',
    'GYM':             'Gym',
    'DEPORTE':         'Deporte',
    'REGALO':          'Regalo',
    'OTROS':           'Otros',
    'EXPENSE':         'Gasto general',
    'FINANZAS':        'Cargos bancarios',
    'NOMINA':          'Nómina / adelanto',
}


# ── Auth ──────────────────────────────────────────────────────────────────────

@budget_bp.before_request
def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')


# ── Vista principal ───────────────────────────────────────────────────────────

@budget_bp.route('/')
@budget_bp.route('/<mes>')
def index(mes=None):
    today = today_date()
    if not mes:
        mes = today.strftime('%Y-%m')

    y, m = int(mes[:4]), int(mes[5:])
    prev_mes = f"{y}-{m-1:02d}" if m > 1  else f"{y-1}-12"
    next_mes = f"{y}-{m+1:02d}" if m < 12 else f"{y+1}-01"

    mes_inicio = f"{mes}-01"
    mes_fin    = f"{next_mes}-01"
    dias_mes   = calendar.monthrange(y, m)[1]
    es_mes_actual = (today.strftime('%Y-%m') == mes)
    dia_actual = today.day if es_mes_actual else dias_mes

    excl_ph = ','.join('?' * len(_INGRESO_EXCLUIR))

    with get_db() as db:
        # ── Límites por categoría (est_budgets)
        budgets_rows = db.execute(
            "SELECT * FROM est_budgets ORDER BY categoria"
        ).fetchall()
        budgets_map = {r['categoria']: dict(r) for r in budgets_rows}

        # ── Gasto real por categoría este mes
        spending_rows = db.execute(
            """SELECT categoria, SUM(COALESCE(mi_parte, monto)) AS total
               FROM est_movimientos
               WHERE tipo='GASTO'
                 AND categoria NOT IN ('PAGO_TDC','PAGO')
                 AND fecha >= ? AND fecha < ?
               GROUP BY categoria""",
            (mes_inicio, mes_fin)
        ).fetchall()
        spending_map = {r['categoria']: float(r['total'] or 0) for r in spending_rows}

        # ── Ingreso real del mes (excluye transferencias y pagos TDC)
        ingreso_row = db.execute(
            f"""SELECT SUM(monto) AS total
               FROM est_movimientos
               WHERE tipo='INGRESO'
                 AND categoria NOT IN ({excl_ph})
                 AND fecha >= ? AND fecha < ?""",
            list(_INGRESO_EXCLUIR) + [mes_inicio, mes_fin]
        ).fetchone()
        ingreso_real = float(ingreso_row['total'] or 0)

        # ── Fallback: si no hay movimientos de ingreso, usar override manual
        if ingreso_real == 0:
            override = db.execute(
                "SELECT ingreso_total FROM budget_meses WHERE mes=?", (mes,)
            ).fetchone()
            if override and override['ingreso_total']:
                ingreso_real = float(override['ingreso_total'])
                ingreso_es_override = True
            else:
                ingreso_es_override = False
        else:
            ingreso_es_override = False

        # ── Tiene movimientos importados?
        n_movimientos = db.execute(
            "SELECT COUNT(*) AS n FROM est_movimientos WHERE fecha >= ? AND fecha < ?",
            (mes_inicio, mes_fin)
        ).fetchone()['n']

    # ── Construir lista de categorías
    all_cats = (set(budgets_map.keys()) | set(spending_map.keys())) - {
        c for c, b in CATEGORIA_BUCKET.items() if b is None
    }
    all_cats = {c for c in all_cats if CATEGORIA_BUCKET.get(c) is not None}

    cats_data = []
    for cat in sorted(all_cats):
        b       = budgets_map.get(cat, {})
        limite  = float(b.get('limite', 0)) if b else 0.0
        gastado = spending_map.get(cat, 0.0)
        pct     = round(gastado / limite * 100) if limite > 0 else None
        if pct is None:
            status = 'nobudget'
        elif pct >= 100:
            status = 'over'
        elif pct >= 80:
            status = 'warn'
        else:
            status = 'ok'

        cats_data.append({
            'id':        b.get('id'),
            'categoria': cat,
            'nombre':    b.get('nombre') or CAT_LABELS.get(cat, cat),
            'limite':    limite,
            'gastado':   gastado,
            'pct':       pct,
            'bucket':    CATEGORIA_BUCKET[cat],
            'status':    status,
        })

    # ── Agrupar por bucket
    BUCKET_META = {
        'necesidades': {'label': 'Necesidades', 'pct_target': 50},
        'deseos':      {'label': 'Deseos',       'pct_target': 30},
        'ahorro_deuda':{'label': 'Ahorro y Deudas', 'pct_target': 20},
    }
    buckets = {}
    for bk in CATEGORIAS:
        bk_cats       = [c for c in cats_data if c['bucket'] == bk]
        total_gastado = round(sum(c['gastado'] for c in bk_cats), 2)
        total_limite  = round(sum(c['limite']  for c in bk_cats), 2)
        target_monto  = round(ingreso_real * PCTS[bk], 2)
        pct_vs_target = round(total_gastado / target_monto * 100) if target_monto > 0 else 0
        buckets[bk] = {
            **BUCKET_META[bk],
            'cats':          bk_cats,
            'total_gastado': total_gastado,
            'total_limite':  total_limite,
            'target_monto':  target_monto,
            'pct_vs_target': min(pct_vs_target, 100),
            'over':          total_gastado > target_monto,
        }

    total_gastado = round(sum(c['gastado'] for c in cats_data), 2)
    disponible    = round(ingreso_real - total_gastado, 2)
    proyeccion    = round(total_gastado / dia_actual * dias_mes) if dia_actual > 0 else 0

    # ── Barra segmentada (% del ingreso)
    seg = {}
    for bk in CATEGORIAS:
        seg[bk] = round(buckets[bk]['total_gastado'] / ingreso_real * 100, 1) if ingreso_real > 0 else 0

    return render_template(
        'finanzas/budget.html',
        mes=mes,
        prev_mes=prev_mes,
        next_mes=next_mes,
        ingreso_real=ingreso_real,
        ingreso_es_override=ingreso_es_override,
        n_movimientos=n_movimientos,
        total_gastado=total_gastado,
        disponible=disponible,
        proyeccion=proyeccion,
        dia_actual=dia_actual,
        dias_mes=dias_mes,
        es_mes_actual=es_mes_actual,
        buckets=buckets,
        seg=seg,
        mes_inicio=mes_inicio,
    )


# ── API: Override de ingreso manual ───────────────────────────────────────────

@budget_bp.route('/api/ingreso', methods=['POST'])
def set_ingreso_override():
    """Guarda un ingreso manual para el mes (usado cuando no hay movimientos INGRESO en Estados)."""
    data  = request.json or {}
    mes   = data.get('mes')
    monto = float(data.get('ingreso_total') or 0)
    now   = datetime.now().isoformat()
    if not mes:
        return jsonify({'error': 'mes requerido'}), 400
    with get_db() as db:
        db.execute("""
            INSERT INTO budget_meses (mes, ingreso_total, created_at)
            VALUES (?,?,?)
            ON CONFLICT(mes) DO UPDATE SET ingreso_total=excluded.ingreso_total
        """, (mes, monto, now))
        db.commit()
    return jsonify({'ok': True, 'mes': mes, 'ingreso_total': monto})


# ── API: Mini-resumen para embeber en otros módulos ───────────────────────────

@budget_bp.route('/api/mini-summary')
@budget_bp.route('/api/mini-summary/<mes>')
def mini_summary(mes=None):
    """Retorna el resumen 50-30-20 del mes en JSON — para el widget de Dashboard."""
    if not session.get('fin_ok'):
        return jsonify({'locked': True})
    today = today_date()
    if not mes:
        mes = today.strftime('%Y-%m')
    next_mes = f"{mes[:4]}-{int(mes[5:])+1:02d}" if int(mes[5:]) < 12 else f"{int(mes[:4])+1}-01"
    mes_inicio, mes_fin = f"{mes}-01", f"{next_mes}-01"
    excl_ph = ','.join('?' * len(_INGRESO_EXCLUIR))

    with get_db() as db:
        ingreso_row = db.execute(
            f"""SELECT SUM(monto) AS total FROM est_movimientos
               WHERE tipo='INGRESO' AND categoria NOT IN ({excl_ph})
               AND fecha >= ? AND fecha < ?""",
            list(_INGRESO_EXCLUIR) + [mes_inicio, mes_fin]
        ).fetchone()
        ingreso = float(ingreso_row['total'] or 0)
        if ingreso == 0:
            ov = db.execute("SELECT ingreso_total FROM budget_meses WHERE mes=?", (mes,)).fetchone()
            if ov:
                ingreso = float(ov['ingreso_total'] or 0)

        spending_rows = db.execute(
            """SELECT categoria, SUM(COALESCE(mi_parte, monto)) AS total
               FROM est_movimientos
               WHERE tipo='GASTO' AND categoria NOT IN ('PAGO_TDC','PAGO')
               AND fecha >= ? AND fecha < ?
               GROUP BY categoria""",
            (mes_inicio, mes_fin)
        ).fetchall()

    spending_map = {r['categoria']: float(r['total'] or 0) for r in spending_rows}
    buckets_out  = {}
    for bk in CATEGORIAS:
        gastado = sum(
            spending_map.get(c, 0)
            for c, b in CATEGORIA_BUCKET.items() if b == bk
        )
        target  = round(ingreso * PCTS[bk], 2)
        buckets_out[bk] = {
            'gastado': round(gastado, 2),
            'target':  target,
            'pct':     round(gastado / target * 100) if target > 0 else 0,
            'over':    gastado > target,
        }
    total_gastado = sum(b['gastado'] for b in buckets_out.values())
    return jsonify({
        'mes':          mes,
        'ingreso':      ingreso,
        'total_gastado': round(total_gastado, 2),
        'disponible':   round(ingreso - total_gastado, 2),
        'buckets':      buckets_out,
    })
