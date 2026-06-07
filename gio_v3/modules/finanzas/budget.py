"""
Budget 50-30-20 — radiografía en vivo de est_budgets + est_movimientos.
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
from datetime import date, datetime
import calendar
from utils import today_str, today_date

budget_bp = Blueprint('budget', __name__, template_folder='../../templates')

CATEGORIAS = ['necesidades', 'deseos', 'ahorro_deuda']
PCTS       = {'necesidades': 0.50, 'deseos': 0.30, 'ahorro_deuda': 0.20}

# Maps Estados top-level categories → 50-30-20 bucket (None = exclude)
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
    'PUBLICIDAD':        None,
    'FINANZAS':          None,
    'INVERSION':         'ahorro_deuda',
    'CAFE/PAN':          'deseos',
    'GYM':               'necesidades',
    'DEPORTE':           'deseos',
    'REGALO':            'deseos',
    'OTROS':             'deseos',
    'EXPENSE':           'deseos',       # catch-all fallback from parsers
    'PAGO_TDC':          None,
    'PAGO':              None,
    'TRANSFERENCIA':     None,           # inter-account transfer
    'SPEI_ENVIADO':      None,           # outgoing SPEI
    'RETIRO':            None,           # ATM withdrawal
}

# Human-readable labels for est_budgets categories
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
}


# ── Auth ──────────────────────────────────────────────────────────────────────

@budget_bp.before_request
def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_mes(mes, db):
    row = db.execute("SELECT * FROM budget_meses WHERE mes=?", (mes,)).fetchone()
    if not row:
        now = datetime.now().isoformat()
        db.execute("INSERT INTO budget_meses (mes, ingreso_total, created_at) VALUES (?,0,?)", (mes, now))
        db.commit()
        row = db.execute("SELECT * FROM budget_meses WHERE mes=?", (mes,)).fetchone()
    return dict(row)


def _resumen(budget, items):
    ingreso = budget['ingreso_total'] or 0
    totales = {c: 0.0 for c in CATEGORIAS}
    for it in items:
        val = it['monto_real'] if it['monto_real'] is not None else it['monto_estimado']
        totales[it['categoria']] = totales.get(it['categoria'], 0) + (val or 0)

    targets = {c: round(ingreso * PCTS[c], 2) for c in CATEGORIAS}
    gastado = sum(totales.values())
    disponible = round(ingreso - gastado, 2)

    pcts_real = {}
    for c in CATEGORIAS:
        pcts_real[c] = round((totales[c] / ingreso * 100), 1) if ingreso else 0

    return {
        'ingreso':     ingreso,
        'totales':     totales,
        'targets':     targets,
        'gastado':     gastado,
        'disponible':  disponible,
        'pcts_real':   pcts_real,
        'pcts_target': {c: int(PCTS[c] * 100) for c in CATEGORIAS},
    }


def _simular_deuda(saldo, pago_minimo, tasa_mensual, pago_propuesto):
    """
    Calculates months and total interest for three scenarios.
    tasa_mensual: decimal monthly rate (e.g. 0.05 = 5%/month)
    """
    def _calc(saldo, pago, tasa):
        if pago <= 0:
            return {'meses': None, 'intereses': None, 'total': None}
        s, meses, intereses = float(saldo), 0, 0.0
        while s > 0.01 and meses < 600:
            i = s * tasa
            intereses += i
            s = s + i - pago
            meses += 1
        return {
            'meses':     meses,
            'intereses': round(intereses, 2),
            'total':     round(float(saldo) + intereses, 2),
        }

    return {
        'minimo':     _calc(saldo, pago_minimo,         tasa_mensual),
        'propuesto':  _calc(saldo, pago_propuesto,      tasa_mensual),
        'agresivo':   _calc(saldo, pago_minimo * 2,     tasa_mensual),
        'liquidar':   _calc(saldo, pago_minimo * 3,     tasa_mensual),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

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

    with get_db() as db:
        # Category limits from est_budgets
        budgets_rows = db.execute(
            "SELECT * FROM est_budgets ORDER BY categoria"
        ).fetchall()
        budgets_map = {r['categoria']: dict(r) for r in budgets_rows}

        # Real spending per category this month
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

        # Income this month
        ingreso_row = db.execute(
            """SELECT SUM(monto) AS total
               FROM est_movimientos
               WHERE tipo='INGRESO' AND fecha >= ? AND fecha < ?""",
            (mes_inicio, mes_fin)
        ).fetchone()

        # Debt tracker (keep)
        deudas = [dict(r) for r in db.execute(
            "SELECT * FROM budget_deudas WHERE activa=1 ORDER BY nombre"
        ).fetchall()]
        pagos_mes = {r['deuda_id']: r['total'] for r in db.execute(
            "SELECT deuda_id, COALESCE(SUM(monto_pagado),0) as total "
            "FROM budget_pagos WHERE mes=? GROUP BY deuda_id",
            (mes,)
        ).fetchall()}

    ingreso_real = float(ingreso_row['total'] or 0)

    # Build per-category list — union of est_budgets + categories with spending
    all_cats = (set(budgets_map.keys()) | set(spending_map.keys())) - {
        c for c, b in CATEGORIA_BUCKET.items() if b is None
    }
    # Only categories with a known bucket
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

    # Group by bucket
    BUCKET_META = {
        'necesidades': {'label': 'Necesidades', 'pct_target': 50, 'color': 'var(--emerald)'},
        'deseos':      {'label': 'Deseos',       'pct_target': 30, 'color': 'var(--blue)'},
        'ahorro_deuda':{'label': 'Ahorro y Deudas', 'pct_target': 20, 'color': 'var(--violet-l)'},
    }
    buckets = {}
    for bk in CATEGORIAS:
        bk_cats         = [c for c in cats_data if c['bucket'] == bk]
        total_gastado   = round(sum(c['gastado'] for c in bk_cats), 2)
        total_limite    = round(sum(c['limite']  for c in bk_cats), 2)
        target_monto    = round(ingreso_real * PCTS[bk], 2)
        pct_vs_target   = round(total_gastado / target_monto * 100) if target_monto > 0 else 0
        buckets[bk] = {
            **BUCKET_META[bk],
            'cats':           bk_cats,
            'total_gastado':  total_gastado,
            'total_limite':   total_limite,
            'target_monto':   target_monto,
            'pct_vs_target':  min(pct_vs_target, 100),
            'over':           total_gastado > target_monto,
        }

    total_gastado = round(sum(c['gastado'] for c in cats_data), 2)
    disponible    = round(ingreso_real - total_gastado, 2)
    proyeccion    = round(total_gastado / dia_actual * dias_mes) if dia_actual > 0 else 0

    # Segmented bar widths (% of ingreso)
    seg = {}
    for bk in CATEGORIAS:
        seg[bk] = round(buckets[bk]['total_gastado'] / ingreso_real * 100, 1) if ingreso_real > 0 else 0

    return render_template(
        'finanzas/budget.html',
        mes=mes,
        prev_mes=prev_mes,
        next_mes=next_mes,
        ingreso_real=ingreso_real,
        total_gastado=total_gastado,
        disponible=disponible,
        proyeccion=proyeccion,
        dia_actual=dia_actual,
        dias_mes=dias_mes,
        es_mes_actual=es_mes_actual,
        buckets=buckets,
        seg=seg,
        deudas=deudas,
        pagos_mes=pagos_mes,
        mes_inicio=mes_inicio,
    )


# ── API ───────────────────────────────────────────────────────────────────────

@budget_bp.route('/api/ingreso', methods=['POST'])
def set_ingreso():
    data   = request.json or {}
    mes    = data.get('mes')
    monto  = float(data.get('ingreso_total') or 0)
    now    = datetime.now().isoformat()
    if not mes:
        return jsonify({'error': 'mes requerido'}), 400
    with get_db() as db:
        existing = db.execute("SELECT id FROM budget_meses WHERE mes=?", (mes,)).fetchone()
        if existing:
            db.execute("UPDATE budget_meses SET ingreso_total=? WHERE mes=?", (monto, mes))
        else:
            db.execute("INSERT INTO budget_meses (mes, ingreso_total, created_at) VALUES (?,?,?)", (mes, monto, now))
        db.commit()
        budget = dict(db.execute("SELECT * FROM budget_meses WHERE mes=?", (mes,)).fetchone())
        items  = [dict(r) for r in db.execute(
            "SELECT * FROM budget_items WHERE budget_id=?", (budget['id'],)).fetchall()]
    return jsonify({'ok': True, 'resumen': _resumen(budget, items)})


@budget_bp.route('/api/item', methods=['POST'])
def add_item():
    data       = request.json or {}
    mes        = data.get('mes')
    nombre     = (data.get('nombre') or '').strip()
    categoria  = data.get('categoria', 'necesidades')
    tipo       = data.get('tipo', 'fijo')
    estimado   = float(data.get('monto_estimado') or 0)
    deuda_id   = data.get('deuda_id') or None
    if not nombre or not mes:
        return jsonify({'error': 'nombre y mes requeridos'}), 400
    with get_db() as db:
        budget = _get_or_create_mes(mes, db)
        db.execute(
            "INSERT INTO budget_items (budget_id,nombre,categoria,tipo,monto_estimado,deuda_id)"
            " VALUES (?,?,?,?,?,?)",
            (budget['id'], nombre, categoria, tipo, estimado, deuda_id)
        )
        db.commit()
        items = [dict(r) for r in db.execute(
            "SELECT * FROM budget_items WHERE budget_id=?", (budget['id'],)).fetchall()]
    return jsonify({'ok': True, 'resumen': _resumen(budget, items),
                    'items': items})


@budget_bp.route('/api/item/<int:iid>', methods=['PATCH'])
def update_item(iid):
    data = request.json or {}
    with get_db() as db:
        row = db.execute("SELECT * FROM budget_items WHERE id=?", (iid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        monto_real     = data.get('monto_real')
        monto_estimado = data.get('monto_estimado')
        if monto_real is not None:
            db.execute("UPDATE budget_items SET monto_real=? WHERE id=?", (float(monto_real), iid))
        if monto_estimado is not None:
            db.execute("UPDATE budget_items SET monto_estimado=? WHERE id=?", (float(monto_estimado), iid))
        db.commit()
        budget = dict(db.execute("SELECT * FROM budget_meses WHERE id=?", (row['budget_id'],)).fetchone())
        items  = [dict(r) for r in db.execute(
            "SELECT * FROM budget_items WHERE budget_id=?", (budget['id'],)).fetchall()]
    return jsonify({'ok': True, 'resumen': _resumen(budget, items)})


@budget_bp.route('/api/item/<int:iid>', methods=['DELETE'])
def delete_item(iid):
    with get_db() as db:
        row = db.execute("SELECT budget_id FROM budget_items WHERE id=?", (iid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        bid = row['budget_id']
        db.execute("DELETE FROM budget_items WHERE id=?", (iid,))
        db.commit()
        budget = dict(db.execute("SELECT * FROM budget_meses WHERE id=?", (bid,)).fetchone())
        items  = [dict(r) for r in db.execute(
            "SELECT * FROM budget_items WHERE budget_id=?", (bid,)).fetchall()]
    return jsonify({'ok': True, 'resumen': _resumen(budget, items)})


@budget_bp.route('/api/copiar/<mes_origen>/<mes_destino>', methods=['POST'])
def copiar_mes(mes_origen, mes_destino):
    """Copy estimated items from one month to another (without monto_real)."""
    with get_db() as db:
        origen  = db.execute("SELECT * FROM budget_meses WHERE mes=?", (mes_origen,)).fetchone()
        if not origen:
            return jsonify({'error': 'Mes origen no existe'}), 404
        destino = _get_or_create_mes(mes_destino, db)
        # Only copy if destination is empty
        existing = db.execute("SELECT COUNT(*) as c FROM budget_items WHERE budget_id=?",
                               (destino['id'],)).fetchone()['c']
        if existing:
            return jsonify({'error': 'El mes destino ya tiene ítems'}), 400
        # Copy ingreso too
        db.execute("UPDATE budget_meses SET ingreso_total=? WHERE id=?",
                   (origen['ingreso_total'], destino['id']))
        items_origen = db.execute("SELECT * FROM budget_items WHERE budget_id=?",
                                   (origen['id'],)).fetchall()
        for it in items_origen:
            db.execute(
                "INSERT INTO budget_items (budget_id,nombre,categoria,tipo,monto_estimado,deuda_id)"
                " VALUES (?,?,?,?,?,?)",
                (destino['id'], it['nombre'], it['categoria'], it['tipo'],
                 it['monto_estimado'], it['deuda_id'])
            )
        db.commit()
    return jsonify({'ok': True, 'copiados': len(items_origen)})


@budget_bp.route('/api/deuda', methods=['POST'])
def add_deuda():
    data    = request.json or {}
    nombre  = (data.get('nombre') or '').strip()
    saldo   = float(data.get('saldo_inicial') or 0)
    minimo  = float(data.get('pago_minimo') or 0)
    tasa    = float(data.get('tasa_interes') or 0)
    now     = datetime.now().isoformat()
    if not nombre or saldo <= 0:
        return jsonify({'error': 'nombre y saldo_inicial requeridos'}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO budget_deudas (nombre,saldo_inicial,saldo_actual,pago_minimo,tasa_interes,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (nombre, saldo, saldo, minimo, tasa, now)
        )
        db.commit()
        deuda = dict(db.execute("SELECT * FROM budget_deudas ORDER BY id DESC LIMIT 1").fetchone())
    return jsonify({'ok': True, 'deuda': deuda})


@budget_bp.route('/api/deuda/<int:did>/pago', methods=['POST'])
def pago_deuda(did):
    data   = request.json or {}
    mes    = data.get('mes') or today_date().strftime('%Y-%m')
    monto  = float(data.get('monto_pagado') or 0)
    fecha  = data.get('fecha') or today_str()
    nota   = data.get('nota', '')
    now    = datetime.now().isoformat()
    if monto <= 0:
        return jsonify({'error': 'monto debe ser > 0'}), 400
    with get_db() as db:
        deuda = db.execute("SELECT * FROM budget_deudas WHERE id=?", (did,)).fetchone()
        if not deuda:
            return jsonify({'error': 'Deuda no encontrada'}), 404
        # Reduce balance (floor at 0)
        nuevo_saldo = max(0, round(deuda['saldo_actual'] - monto, 2))
        db.execute("UPDATE budget_deudas SET saldo_actual=? WHERE id=?", (nuevo_saldo, did))
        db.execute(
            "INSERT INTO budget_pagos (deuda_id,mes,monto_pagado,fecha_pago,nota,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (did, mes, monto, fecha, nota, now)
        )
        db.commit()
        deuda = dict(db.execute("SELECT * FROM budget_deudas WHERE id=?", (did,)).fetchone())
        pagos = [dict(r) for r in db.execute(
            "SELECT * FROM budget_pagos WHERE deuda_id=? ORDER BY fecha_pago DESC LIMIT 12",
            (did,)).fetchall()]
    return jsonify({'ok': True, 'deuda': deuda, 'pagos': pagos,
                    'nuevo_saldo': nuevo_saldo})


@budget_bp.route('/api/deuda/<int:did>/simulacion')
def simulacion(did):
    pago = float(request.args.get('pago', 0))
    with get_db() as db:
        deuda = db.execute("SELECT * FROM budget_deudas WHERE id=?", (did,)).fetchone()
    if not deuda:
        return jsonify({'error': 'not found'}), 404
    tasa = (deuda['tasa_interes'] or 0) / 100
    result = _simular_deuda(deuda['saldo_actual'], deuda['pago_minimo'], tasa, pago)
    return jsonify({'ok': True, 'simulacion': result, 'saldo': deuda['saldo_actual']})


@budget_bp.route('/api/deuda/<int:did>', methods=['DELETE'])
def desactivar_deuda(did):
    with get_db() as db:
        db.execute("UPDATE budget_deudas SET activa=0 WHERE id=?", (did,))
        db.commit()
    return jsonify({'ok': True})
