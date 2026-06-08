"""
Inversiones — vista dedicada para movimientos tipo='INVERSION'.

Modelo de datos (reutiliza est_movimientos):
  tipo        = 'INVERSION'
  categoria   = plataforma  (GBM | INVEX | CETES | CRYPTO | FIBRA | OTRO)
  subcategoria= dirección   (APORTACION | RETIRO | RENDIMIENTO)
  monto       = monto positivo

La net position por plataforma:
  aportado  = SUM(monto) WHERE subcategoria='APORTACION'
  retirado  = SUM(monto) WHERE subcategoria='RETIRO'
  rendimiento= SUM(monto) WHERE subcategoria='RENDIMIENTO'
  saldo_est = aportado - retirado + rendimiento
"""
from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from utils import today_date, today_str, safe_float, clean_str
from datetime import datetime

inversiones_bp = Blueprint('inversiones', __name__, template_folder='../../templates')

PLATAFORMAS = ['GBM', 'INVEX', 'CETES', 'CRYPTO', 'FIBRA', 'OTRO']
DIRECCIONES = ['APORTACION', 'RETIRO', 'RENDIMIENTO']

PLAT_META = {
    'GBM':    {'label': 'GBM Homebroker', 'icon': '📈', 'color': '#22c55e'},
    'INVEX':  {'label': 'Invex',           'icon': '🏦', 'color': '#a78bfa'},
    'CETES':  {'label': 'CETES Directo',   'icon': '🇲🇽', 'color': '#60a5fa'},
    'CRYPTO': {'label': 'Crypto',          'icon': '₿',  'color': '#f59e0b'},
    'FIBRA':  {'label': 'FIBRA / Bienes R.','icon': '🏢', 'color': '#fb923c'},
    'OTRO':   {'label': 'Otro',            'icon': '💼', 'color': '#94a3b8'},
}

DIR_META = {
    'APORTACION':   {'label': 'Aportación',   'sign': +1, 'color': '#22c55e'},
    'RETIRO':       {'label': 'Retiro',        'sign': -1, 'color': '#f87171'},
    'RENDIMIENTO':  {'label': 'Rendimiento',   'sign': +1, 'color': '#fbbf24'},
}


def _ok():
    return session.get('fin_ok')


@inversiones_bp.route('/')
def index():
    if not _ok():
        from modules.finanzas.routes import _get_pass_hash
        return render_template('finanzas/lock.html', has_pass=bool(_get_pass_hash()))

    with get_db() as db:
        # ── Por plataforma
        plat_rows = db.execute("""
            SELECT categoria,
                   subcategoria,
                   SUM(monto) AS total,
                   COUNT(*)   AS n
            FROM est_movimientos
            WHERE tipo='INVERSION'
            GROUP BY categoria, subcategoria
        """).fetchall()

        # ── Historial completo (desc)
        movs = db.execute("""
            SELECT id, fecha, descripcion, monto, categoria, subcategoria, banco
            FROM est_movimientos
            WHERE tipo='INVERSION'
            ORDER BY fecha DESC
        """).fetchall()

    # ── Construir portafolio por plataforma
    port = {}
    for r in plat_rows:
        cat = r['categoria'] if r['categoria'] in PLATAFORMAS else 'OTRO'
        sub = r['subcategoria'] if r['subcategoria'] in DIRECCIONES else 'APORTACION'
        if cat not in port:
            port[cat] = {'aportado': 0, 'retirado': 0, 'rendimiento': 0}
        if sub == 'APORTACION':
            port[cat]['aportado'] += float(r['total'] or 0)
        elif sub == 'RETIRO':
            port[cat]['retirado'] += float(r['total'] or 0)
        elif sub == 'RENDIMIENTO':
            port[cat]['rendimiento'] += float(r['total'] or 0)

    plataformas_data = []
    total_aportado = total_retirado = total_rendimiento = 0
    for plat in PLATAFORMAS:
        if plat not in port:
            continue
        p = port[plat]
        aportado    = round(p['aportado'], 2)
        retirado    = round(p['retirado'], 2)
        rendimiento = round(p['rendimiento'], 2)
        saldo       = round(aportado - retirado + rendimiento, 2)
        total_aportado    += aportado
        total_retirado    += retirado
        total_rendimiento += rendimiento
        plataformas_data.append({
            'id':          plat,
            'aportado':    aportado,
            'retirado':    retirado,
            'rendimiento': rendimiento,
            'saldo':       saldo,
            **PLAT_META.get(plat, PLAT_META['OTRO']),
        })

    total_aportado    = round(total_aportado, 2)
    total_retirado    = round(total_retirado, 2)
    total_rendimiento = round(total_rendimiento, 2)
    saldo_total       = round(total_aportado - total_retirado + total_rendimiento, 2)

    # Pct allocation para barra
    for p in plataformas_data:
        p['pct'] = round(p['aportado'] / total_aportado * 100, 1) if total_aportado > 0 else 0

    movs_list = []
    for m in movs:
        sub = m['subcategoria'] if m['subcategoria'] in DIRECCIONES else 'APORTACION'
        movs_list.append({
            'id':          m['id'],
            'fecha':       m['fecha'],
            'descripcion': m['descripcion'],
            'monto':       float(m['monto'] or 0),
            'categoria':   m['categoria'] if m['categoria'] in PLATAFORMAS else 'OTRO',
            'subcategoria': sub,
            'banco':       m['banco'],
            'dir_meta':    DIR_META[sub],
            'plat_meta':   PLAT_META.get(m['categoria'], PLAT_META['OTRO']),
        })

    return render_template(
        'finanzas/inversiones.html',
        plataformas=plataformas_data,
        movs=movs_list,
        total_aportado=total_aportado,
        total_retirado=total_retirado,
        total_rendimiento=total_rendimiento,
        saldo_total=saldo_total,
        plataformas_list=PLATAFORMAS,
        plat_meta=PLAT_META,
        dir_meta=DIR_META,
        today=today_str(),
    )


# ── API: registrar movimiento manual ────────────────────────────────────────

@inversiones_bp.route('/api/mov', methods=['POST'])
def add_mov():
    if not _ok():
        return jsonify({'error': 'locked'}), 403
    d = request.json or {}
    fecha       = d.get('fecha', today_str())
    monto       = safe_float(d.get('monto'), min_val=0.01)
    plataforma  = clean_str(d.get('plataforma'), 20)
    direccion   = clean_str(d.get('direccion'), 20)
    descripcion = clean_str(d.get('descripcion', ''), 200) or f'{direccion} {plataforma}'

    if not monto:
        return jsonify({'error': 'Monto inválido'}), 400
    if plataforma not in PLATAFORMAS:
        return jsonify({'error': 'Plataforma inválida'}), 400
    if direccion not in DIRECCIONES:
        return jsonify({'error': 'Dirección inválida'}), 400

    with get_db() as db:
        db.execute("""
            INSERT INTO est_movimientos
            (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (fecha, fecha, descripcion, monto, 'MANUAL', '', plataforma, direccion, 'INVERSION'))
        db.commit()

    return jsonify({'ok': True})


# ── API: eliminar movimiento ─────────────────────────────────────────────────

@inversiones_bp.route('/api/mov/<int:mid>', methods=['DELETE'])
def delete_mov(mid):
    if not _ok():
        return jsonify({'error': 'locked'}), 403
    with get_db() as db:
        row = db.execute(
            "SELECT tipo FROM est_movimientos WHERE id=?", (mid,)
        ).fetchone()
        if not row or row['tipo'] != 'INVERSION':
            return jsonify({'error': 'no encontrado'}), 404
        db.execute("DELETE FROM est_movimientos WHERE id=?", (mid,))
        db.commit()
    return jsonify({'ok': True})


# ── API: reclasificar plataforma / dirección ─────────────────────────────────

@inversiones_bp.route('/api/mov/<int:mid>', methods=['PATCH'])
def patch_mov(mid):
    if not _ok():
        return jsonify({'error': 'locked'}), 403
    d = request.json or {}
    plataforma = clean_str(d.get('plataforma', ''), 20)
    direccion  = clean_str(d.get('direccion',  ''), 20)

    updates = {}
    if plataforma and plataforma in PLATAFORMAS:
        updates['categoria'] = plataforma
    if direccion and direccion in DIRECCIONES:
        updates['subcategoria'] = direccion

    if not updates:
        return jsonify({'error': 'nada que actualizar'}), 400

    set_clause = ', '.join(f'{k}=?' for k in updates)
    with get_db() as db:
        db.execute(
            f"UPDATE est_movimientos SET {set_clause} WHERE id=? AND tipo='INVERSION'",
            list(updates.values()) + [mid]
        )
        db.commit()
    return jsonify({'ok': True})
