"""Salud Financiera — patrimonio neto: cuentas, inversiones y bienes."""
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
from datetime import datetime, date
from collections import defaultdict

salud_bp = Blueprint('salud', __name__, template_folder='../../templates')

TIPOS_ACTIVO = ('efectivo', 'cuenta_banco', 'inversion')
TIPOS_PASIVO = ('tarjeta_credito', 'prestamo')

TIPO_META = {
    'efectivo':       {'label': 'Efectivo',             'color': '#C9A84C', 'icon': 'wallet'},
    'cuenta_banco':   {'label': 'Cuenta Bancaria',      'color': '#60a5fa', 'icon': 'building-2'},
    'inversion':      {'label': 'Inversión',             'color': '#10b981', 'icon': 'trending-up'},
    'tarjeta_credito':{'label': 'Tarjeta de Crédito',   'color': '#f43f5e', 'icon': 'credit-card'},
    'prestamo':       {'label': 'Préstamo / Crédito',   'color': '#f97316', 'icon': 'landmark'},
}

BIEN_META = {
    'vehiculo':       {'label': 'Vehículo',          'color': '#60a5fa', 'icon': 'car'},
    'electrodomestico':{'label': 'Electrodoméstico', 'color': '#a78bfa', 'icon': 'zap'},
    'mueble':         {'label': 'Mueble',             'color': '#fb923c', 'icon': 'sofa'},
    'electronico':    {'label': 'Electrónico',        'color': '#34d399', 'icon': 'monitor'},
    'otro':           {'label': 'Otro',               'color': '#94a3b8', 'icon': 'package'},
}


@salud_bp.before_request
def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')


def _totales(cuentas, bienes):
    activos_cuentas = sum(c['saldo'] for c in cuentas if c['tipo'] in TIPOS_ACTIVO)
    total_bienes    = sum(b['valor_actual'] for b in bienes)
    total_activos   = activos_cuentas + total_bienes
    total_pasivos   = sum(c['saldo'] for c in cuentas if c['tipo'] in TIPOS_PASIVO)
    return total_activos, activos_cuentas, total_bienes, total_pasivos, total_activos - total_pasivos


# ── Vistas ─────────────────────────────────────────────────────────────────────

@salud_bp.route('/')
def index():
    with get_db() as db:
        cuentas   = [dict(r) for r in db.execute(
            "SELECT * FROM salud_cuentas WHERE activa=1 ORDER BY tipo, nombre"
        ).fetchall()]
        bienes    = [dict(r) for r in db.execute(
            "SELECT * FROM salud_bienes WHERE activo=1 ORDER BY categoria, nombre"
        ).fetchall()]
        historial = [dict(r) for r in db.execute(
            "SELECT * FROM salud_patrimonio_log ORDER BY fecha ASC LIMIT 12"
        ).fetchall()]

    total_activos, activos_cuentas, total_bienes, total_pasivos, patrimonio_neto = _totales(cuentas, bienes)

    bienes_por_cat = defaultdict(list)
    for b in bienes:
        bienes_por_cat[b['categoria']].append(b)

    return render_template(
        'finanzas/salud.html',
        cuentas_liquido   = [c for c in cuentas if c['tipo'] in ('efectivo', 'cuenta_banco')],
        cuentas_inversion = [c for c in cuentas if c['tipo'] == 'inversion'],
        cuentas_pasivo    = [c for c in cuentas if c['tipo'] in TIPOS_PASIVO],
        bienes            = bienes,
        bienes_por_cat    = dict(bienes_por_cat),
        historial         = historial,
        total_activos     = total_activos,
        activos_cuentas   = activos_cuentas,
        total_bienes      = total_bienes,
        total_pasivos     = total_pasivos,
        patrimonio_neto   = patrimonio_neto,
        tipo_meta         = TIPO_META,
        bien_meta         = BIEN_META,
        today             = date.today().strftime('%d %b %Y').upper(),
    )


# ── API Cuentas ────────────────────────────────────────────────────────────────

@salud_bp.route('/api/cuenta', methods=['POST'])
def add_cuenta():
    d = request.json or {}
    nombre = (d.get('nombre') or '').strip()
    if not nombre:
        return jsonify(ok=False, error='Nombre requerido'), 400
    now = datetime.now().isoformat()
    tipo = d.get('tipo', 'cuenta_banco')
    color = TIPO_META.get(tipo, {}).get('color', '#C9A84C')
    with get_db() as db:
        db.execute(
            """INSERT INTO salud_cuentas
               (nombre, tipo, institucion, saldo, moneda, color, activa, ultima_actualizacion, notas, created_at)
               VALUES (?,?,?,?,?,?,1,?,?,?)""",
            (nombre, tipo, d.get('institucion', ''), float(d.get('saldo', 0)),
             d.get('moneda', 'MXN'), color, now, d.get('notas', ''), now)
        )
        db.commit()
        row = db.execute("SELECT * FROM salud_cuentas WHERE rowid=last_insert_rowid()").fetchone()
    return jsonify(ok=True, cuenta=dict(row))


@salud_bp.route('/api/cuenta/<int:cid>', methods=['PATCH'])
def update_cuenta(cid):
    d = request.json or {}
    now = datetime.now().isoformat()
    with get_db() as db:
        row = db.execute("SELECT * FROM salud_cuentas WHERE id=?", (cid,)).fetchone()
        if not row:
            return jsonify(ok=False, error='No encontrada'), 404
        old_saldo = float(row['saldo'])
        new_saldo = float(d.get('saldo', old_saldo))
        if 'saldo' in d and new_saldo != old_saldo:
            db.execute(
                "INSERT INTO salud_saldos_historial (cuenta_id, saldo, fecha, nota, created_at) VALUES (?,?,?,?,?)",
                (cid, new_saldo, now[:10], d.get('nota', ''), now)
            )
        tipo  = d.get('tipo', row['tipo'])
        color = TIPO_META.get(tipo, {}).get('color', row['color'])
        db.execute(
            """UPDATE salud_cuentas
               SET nombre=?, tipo=?, institucion=?, saldo=?, moneda=?, color=?, notas=?, ultima_actualizacion=?
               WHERE id=?""",
            (d.get('nombre', row['nombre']), tipo,
             d.get('institucion', row['institucion']), new_saldo,
             d.get('moneda', row['moneda']), color,
             d.get('notas', row['notas']), now, cid)
        )
        db.commit()
    return jsonify(ok=True)


@salud_bp.route('/api/cuenta/<int:cid>', methods=['DELETE'])
def delete_cuenta(cid):
    with get_db() as db:
        db.execute("UPDATE salud_cuentas SET activa=0 WHERE id=?", (cid,))
        db.commit()
    return jsonify(ok=True)


# ── API Bienes ─────────────────────────────────────────────────────────────────

@salud_bp.route('/api/bien', methods=['POST'])
def add_bien():
    d = request.json or {}
    nombre = (d.get('nombre') or '').strip()
    if not nombre:
        return jsonify(ok=False, error='Nombre requerido'), 400
    now    = datetime.now().isoformat()
    precio = float(d.get('precio_compra', 0))
    valor  = float(d.get('valor_actual', precio))
    with get_db() as db:
        db.execute(
            """INSERT INTO salud_bienes
               (nombre, categoria, descripcion, precio_compra, valor_actual,
                fecha_compra, lugar_compra, garantia_hasta, notas, activo, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,1,?)""",
            (nombre, d.get('categoria', 'otro'), d.get('descripcion', ''),
             precio, valor, d.get('fecha_compra', ''), d.get('lugar_compra', ''),
             d.get('garantia_hasta', ''), d.get('notas', ''), now)
        )
        db.commit()
        row = db.execute("SELECT * FROM salud_bienes WHERE rowid=last_insert_rowid()").fetchone()
    return jsonify(ok=True, bien=dict(row))


@salud_bp.route('/api/bien/<int:bid>', methods=['PATCH'])
def update_bien(bid):
    d = request.json or {}
    with get_db() as db:
        row = db.execute("SELECT * FROM salud_bienes WHERE id=?", (bid,)).fetchone()
        if not row:
            return jsonify(ok=False, error='No encontrado'), 404
        db.execute(
            """UPDATE salud_bienes
               SET nombre=?, categoria=?, descripcion=?, precio_compra=?, valor_actual=?,
                   fecha_compra=?, lugar_compra=?, garantia_hasta=?, notas=?
               WHERE id=?""",
            (d.get('nombre', row['nombre']), d.get('categoria', row['categoria']),
             d.get('descripcion', row['descripcion']),
             float(d.get('precio_compra', row['precio_compra'])),
             float(d.get('valor_actual',  row['valor_actual'])),
             d.get('fecha_compra',   row['fecha_compra']),
             d.get('lugar_compra',   row['lugar_compra']),
             d.get('garantia_hasta', row['garantia_hasta']),
             d.get('notas', row['notas']), bid)
        )
        db.commit()
        updated = db.execute("SELECT * FROM salud_bienes WHERE id=?", (bid,)).fetchone()
    return jsonify(ok=True, bien=dict(updated))


@salud_bp.route('/api/bien/<int:bid>', methods=['DELETE'])
def delete_bien(bid):
    with get_db() as db:
        db.execute("UPDATE salud_bienes SET activo=0 WHERE id=?", (bid,))
        db.commit()
    return jsonify(ok=True)


# ── Snapshot de patrimonio ─────────────────────────────────────────────────────

@salud_bp.route('/api/snapshot', methods=['POST'])
def take_snapshot():
    now   = datetime.now().isoformat()
    today = now[:10]
    with get_db() as db:
        if db.execute("SELECT id FROM salud_patrimonio_log WHERE fecha=?", (today,)).fetchone():
            return jsonify(ok=False, error='Ya existe un snapshot de hoy'), 409
        cuentas = [dict(r) for r in db.execute("SELECT * FROM salud_cuentas WHERE activa=1").fetchall()]
        bienes  = [dict(r) for r in db.execute("SELECT * FROM salud_bienes WHERE activo=1").fetchall()]
        total_activos, _, _, total_pasivos, patrimonio = _totales(cuentas, bienes)
        db.execute(
            "INSERT INTO salud_patrimonio_log (total_activos, total_pasivos, patrimonio_neto, fecha, created_at) VALUES (?,?,?,?,?)",
            (total_activos, total_pasivos, patrimonio, today, now)
        )
        db.commit()
    return jsonify(ok=True, patrimonio_neto=patrimonio, fecha=today)
