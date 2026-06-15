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
from utils import today_str, today_date

budget_bp = Blueprint('budget', __name__, template_folder='../../templates')

# ── Regla 50-30-20 ────────────────────────────────────────────────────────────
CATEGORIAS = ['necesidades', 'deseos', 'ahorro_deuda']
PCTS       = {'necesidades': 0.50, 'deseos': 0.30, 'ahorro_deuda': 0.20}

# Mapeo categoria → bucket (None = excluir del gasto visible)
CATEGORIA_BUCKET = {
    'COMIDA/REST':      'deseos',
    'VIVERES/SUPER':    'necesidades',
    'CASA/HOGAR':       'necesidades',
    'GASOLINA/AUTO':    'necesidades',
    'SERVICIOS':        'necesidades',   # Agua, Luz, Internet, Gas, Garrafón
    'MENSUALIDAD':      'necesidades',   # Mensualidad TDC
    'ROPA':             'deseos',
    'SALUD':            'necesidades',
    'TECH/DIGITAL':     'deseos',
    'SUSCRIPCIONES':    'deseos',
    'ENTRETENIMIENTO':  'deseos',
    'SALSA':            'deseos',
    'VIAJES/VUELOS':    'deseos',
    'TRANSPORTE':       'necesidades',
    'APRENDIZAJE':      'ahorro_deuda',
    'CAFE/PAN':         'deseos',
    'GYM':              'deseos',
    'DEPORTE':          'deseos',
    'REGALO':           'deseos',
    'OTROS':            'deseos',
    'EXPENSE':          None,            # Informativo – se reembolsa, no afecta buckets
    'APORTACION_RENTA': None,           # Parte de renta recibida de tercero – no es ingreso propio
    # Inversión → ahorro
    'INVERSION':        'ahorro_deuda',
    # Excluidos del gasto de consumo
    'PAGO_TDC':         None,
    'PAGO':             None,
    'TRANSFERENCIA':    None,
    'SPEI_ENVIADO':     None,
    'RETIRO':           None,
    'PUBLICIDAD':       None,
    'FINANZAS':         None,
    'NOMINA':           None,
}

# Categorías de ingreso que NO son ingreso real
_INGRESO_EXCLUIR = ('TRANSFERENCIA', 'PAGO_TDC', 'RETIRO', 'DEPOSITO', 'SPEI_RECIBIDO', 'APORTACION_RENTA')

CAT_LABELS = {
    'COMIDA/REST':     'Comida / Restaurante',
    'VIVERES/SUPER':   'Víveres / Súper',
    'CASA/HOGAR':      'Vivienda',
    'GASOLINA/AUTO':   'Gasolina / Auto',
    'SERVICIOS':       'Servicios',
    'MENSUALIDAD':     'Mensualidad TDC',
    'ROPA':            'Ropa',
    'SALUD':           'Personal / Salud',
    'TECH/DIGITAL':    'Tech / Digital',
    'SUSCRIPCIONES':   'Apps / Suscripciones',
    'ENTRETENIMIENTO': 'Gustos',
    'SALSA':           'Salsa / Baile',
    'VIAJES/VUELOS':   'Viajes / Vuelos',
    'TRANSPORTE':      'Transporte',
    'APRENDIZAJE':     'Educación',
    'INVERSION':       'Ahorro',
    'CAFE/PAN':        'Café / Pan',
    'GYM':             'Gym',
    'DEPORTE':         'Deporte',
    'REGALO':          'Regalo',
    'OTROS':           'Otros',
    'EXPENSE':         'EXPENSE',
    'APORTACION_RENTA':'Aportación renta',
    'FINANZAS':        'Cargos bancarios',
    'NOMINA':          'Nómina adelanto',
}

CAT_ICONS = {
    'COMIDA/REST': '🍔', 'VIVERES/SUPER': '🛒', 'CASA/HOGAR': '🏠',
    'GASOLINA/AUTO': '⛽', 'SERVICIOS': '💡', 'MENSUALIDAD': '💳',
    'ROPA': '👕', 'SALUD': '✂️',
    'TECH/DIGITAL': '💻', 'SUSCRIPCIONES': '📱', 'ENTRETENIMIENTO': '🎭',
    'SALSA': '💃', 'VIAJES/VUELOS': '✈️', 'TRANSPORTE': '🚗',
    'APRENDIZAJE': '📚', 'INVERSION': '📈', 'CAFE/PAN': '☕',
    'GYM': '🏋️', 'DEPORTE': '⚽', 'REGALO': '🎁',
    'OTROS': '📦', 'EXPENSE': '🧾',
}

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


def _calc_budget(mes, db):
    """Calcula toda la data del presupuesto para un mes dado."""
    y, m   = int(mes[:4]), int(mes[5:])
    next_m = m + 1 if m < 12 else 1
    next_y = y if m < 12 else y + 1
    next_mes  = f"{next_y}-{next_m:02d}"
    mes_inicio = f"{mes}-01"
    mes_fin    = f"{next_mes}-01"

    excl_ph = ','.join('?' * len(_INGRESO_EXCLUIR))

    # ── Ingreso real
    ingreso_row = db.execute(
        f"""SELECT SUM(monto) AS total
           FROM est_movimientos
           WHERE tipo='INGRESO'
             AND categoria NOT IN ({excl_ph})
             AND fecha >= ? AND fecha < ?""",
        list(_INGRESO_EXCLUIR) + [mes_inicio, mes_fin]
    ).fetchone()
    ingreso_real = float(ingreso_row['total'] or 0)
    ingreso_es_override = False

    if ingreso_real == 0:
        ov = db.execute(
            "SELECT ingreso_total FROM budget_meses WHERE mes=?", (mes,)
        ).fetchone()
        if ov and ov['ingreso_total']:
            ingreso_real = float(ov['ingreso_total'])
            ingreso_es_override = True

    # ── Gasto real por categoría
    spending_rows = db.execute(
        """SELECT categoria, SUM(COALESCE(mi_parte, monto)) AS total, COUNT(*) AS n
           FROM est_movimientos
           WHERE tipo='GASTO'
             AND categoria NOT IN ('PAGO_TDC','PAGO','TRANSFERENCIA',
                                   'SPEI_ENVIADO','RETIRO','PUBLICIDAD','NOMINA','FINANZAS')
             AND fecha >= ? AND fecha < ?
           GROUP BY categoria
           ORDER BY total DESC""",
        (mes_inicio, mes_fin)
    ).fetchall()

    # ── Límites opcionales (est_budgets)
    budgets_map = {r['categoria']: float(r['limite'] or 0)
                   for r in db.execute("SELECT categoria, limite FROM est_budgets").fetchall()}

    # ── Ingresos desglose (para mostrar de dónde viene el ingreso)
    ingresos_rows = db.execute(
        f"""SELECT categoria, SUM(monto) AS total
           FROM est_movimientos
           WHERE tipo='INGRESO'
             AND categoria NOT IN ({excl_ph})
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
        cat           = row['categoria']
        bucket        = CATEGORIA_BUCKET.get(cat) or 'deseos'
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
            'icono':        CAT_ICONS.get(cat, '📦'),
            'limite':       limite,
            'gastado':      gastado,
            'n':            int(row['n'] or 0),
            'pct':          pct,
            'pct_bucket':   pct_bucket,
            'tiene_limite': tiene_limite,
            'bucket':       bucket,
            'bucket_target': bucket_target,
            'status':       status,
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

    total_gastado = round(sum(c['gastado'] for c in cats_data), 2)
    disponible    = round(ingreso_real - total_gastado, 2)

    # Barra segmentada: % del ingreso gastado en cada bucket
    seg = {}
    for bk in CATEGORIAS:
        seg[bk] = round(buckets[bk]['total_gastado'] / ingreso_real * 100, 1) if ingreso_real > 0 else 0

    dias_mes      = calendar.monthrange(y, m)[1]
    today         = today_date()
    es_mes_actual = (today.strftime('%Y-%m') == mes)
    dia_actual    = today.day if es_mes_actual else dias_mes
    proyeccion    = round(total_gastado / dia_actual * dias_mes) if dia_actual > 0 and total_gastado > 0 else 0

    return {
        'ingreso_real':       ingreso_real,
        'ingreso_es_override':ingreso_es_override,
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

    return render_template(
        'finanzas/budget.html',
        mes=mes, prev_mes=prev_mes, next_mes=next_mes,
        **data,
    )


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
            db.execute("UPDATE est_movimientos SET categoria='TRANSFERENCIA' WHERE id=?", (mov_id,))
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
        rows = db.execute("""
            SELECT id, fecha, descripcion, monto, COALESCE(mi_parte, monto) AS mi_monto,
                   categoria, banco, tipo
            FROM est_movimientos
            WHERE categoria = ?
              AND tipo IN ('GASTO','INVERSION')
              AND fecha >= ? AND fecha < ?
            ORDER BY fecha DESC, id DESC
        """, (categoria, mes_ini, mes_fin)).fetchall()
    return jsonify({'movimientos': [dict(r) for r in rows]})


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
