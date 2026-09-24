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

Saldo de corte (inv_saldo_base): el usuario fija el saldo real de cada
plataforma en una fecha; desde ahí el saldo es ese corte + los movimientos
posteriores (la dirección la dan las reglas del import). Una plataforma sin
corte sigue calculándose con todo su historial.
"""
from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from utils import today_date, today_str, safe_float, clean_str
from datetime import datetime

inversiones_bp = Blueprint('inversiones', __name__, template_folder='../../templates')

PLATAFORMAS = ['GBM', 'INVEX', 'CETES', 'FINSUS', 'CRYPTO', 'FIBRA', 'OTRO']
DIRECCIONES = ['APORTACION', 'RETIRO', 'RENDIMIENTO']
# «Otro» no es una cuenta real del usuario («no hay otro, eso es todo»): ahí
# caen movimientos que el import marcó como inversión sin reconocer la
# plataforma (transferencias entre cuentas, etc.). Se siguen listando para
# poder revisarlos, pero no suman al saldo ni al Ahorro de la Radiografía.
SIN_SALDO = ('OTRO',)

PLAT_META = {
    'GBM':    {'label': 'GBM Homebroker', 'icon': 'trending-up',  'color': '#22c55e'},
    'INVEX':  {'label': 'Invex',           'icon': 'landmark',     'color': '#a78bfa'},
    'CETES':  {'label': 'CETES Directo',   'icon': 'shield-check', 'color': '#60a5fa'},
    'FINSUS': {'label': 'Finsus',          'icon': 'piggy-bank',   'color': '#34d399'},
    'CRYPTO': {'label': 'Crypto',          'icon': 'bitcoin',      'color': '#f59e0b'},
    'FIBRA':  {'label': 'FIBRA / Bienes R.','icon': 'building-2',  'color': '#fb923c'},
    'OTRO':   {'label': 'Otro',            'icon': 'briefcase',    'color': '#94a3b8'},
}

DIR_META = {
    'APORTACION':   {'label': 'Aportación',   'sign': +1, 'color': '#22c55e'},
    'RETIRO':       {'label': 'Retiro',        'sign': -1, 'color': '#f87171'},
    'RENDIMIENTO':  {'label': 'Rendimiento',   'sign': +1, 'color': '#fbbf24'},
}


def _ok():
    return session.get('fin_ok')


def _portafolio(db):
    """Saldo por plataforma (corte + movimientos posteriores). Lo usan esta
    vista y Patrimonio (salud.py), para que ambas muestren lo mismo."""
    base = {r['plataforma']: {'saldo': float(r['saldo']), 'fecha': r['fecha']}
            for r in db.execute("SELECT plataforma, saldo, fecha FROM inv_saldo_base")}
    # ── Por plataforma (solo lo posterior al corte de cada plataforma)
    plat_rows = db.execute("""
        SELECT m.categoria,
               m.subcategoria,
               SUM(ABS(m.monto)) AS total,
               COUNT(*)   AS n
        FROM est_movimientos m
        LEFT JOIN inv_saldo_base b ON b.plataforma = m.categoria
        WHERE m.tipo='INVERSION' AND (b.fecha IS NULL OR m.fecha > b.fecha)
        GROUP BY m.categoria, m.subcategoria
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
        if plat in SIN_SALDO:
            continue
        b = base.get(plat)
        if plat not in port and not (b and b['saldo']):
            continue  # sin corte con saldo ni movimientos: no se muestra (p. ej. «Otro» en 0)
        p = port.get(plat, {'aportado': 0, 'retirado': 0, 'rendimiento': 0})
        aportado    = round(p['aportado'], 2)
        retirado    = round(p['retirado'], 2)
        rendimiento = round(p['rendimiento'], 2)
        saldo       = round((b['saldo'] if b else 0) + aportado - retirado + rendimiento, 2)
        total_aportado    += aportado
        total_retirado    += retirado
        total_rendimiento += rendimiento
        plataformas_data.append({
            'id':          plat,
            'aportado':    aportado,
            'retirado':    retirado,
            'rendimiento': rendimiento,
            'saldo':       saldo,
            'base':        b,
            **PLAT_META.get(plat, PLAT_META['OTRO']),
        })

    total_aportado    = round(total_aportado, 2)
    total_retirado    = round(total_retirado, 2)
    total_rendimiento = round(total_rendimiento, 2)
    saldo_total       = round(sum(p['saldo'] for p in plataformas_data), 2)
    fechas_corte      = sorted({b['fecha'] for b in base.values()})

    # Distribución por saldo (antes era por aportado histórico).
    positivo = sum(max(p['saldo'], 0) for p in plataformas_data)
    for p in plataformas_data:
        p['pct'] = round(max(p['saldo'], 0) / positivo * 100, 1) if positivo > 0 else 0

    return {'plataformas': plataformas_data, 'total_aportado': total_aportado,
            'total_retirado': total_retirado, 'total_rendimiento': total_rendimiento,
            'saldo_total': saldo_total, 'fecha_corte': fechas_corte[-1] if fechas_corte else None}


# Alias con que el usuario nombró sus cuentas en Patrimonio (p. ej. «GMB»).
_ALIAS = {'GBM': ('GBM', 'GMB'), 'CETES': ('CETES',), 'FINSUS': ('FINSUS',), 'INVEX': ('INVEX',),
          'CRYPTO': ('CRYPTO', 'BITSO', 'COINBASE'), 'FIBRA': ('FIBRA',)}


def plataforma_de(texto):
    """Plataforma a la que se refiere el nombre de una cuenta de Patrimonio."""
    t = (texto or '').upper()
    return next((p for p, alias in _ALIAS.items() if any(a in t for a in alias)), None)


def cuentas_patrimonio(db):
    """Las inversiones como cuentas de Patrimonio, con el saldo en vivo."""
    return [{'id': f"inv-{p['id']}", 'nombre': p['label'], 'institucion': 'Desde Inversiones',
             'saldo': p['saldo'], 'moneda': 'MXN', 'tipo': 'inversion', 'auto': True, 'plataforma': p['id']}
            for p in _portafolio(db)['plataformas']]


@inversiones_bp.route('/')
def index():
    with get_db() as db:
        pf = _portafolio(db)
        # ── Historial completo (desc)
        movs = db.execute("""
            SELECT id, fecha, descripcion, monto, categoria, subcategoria, banco
            FROM est_movimientos
            WHERE tipo='INVERSION'
            ORDER BY fecha DESC
        """).fetchall()

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
        plataformas=pf['plataformas'],
        movs=movs_list,
        total_aportado=pf['total_aportado'],
        total_retirado=pf['total_retirado'],
        total_rendimiento=pf['total_rendimiento'],
        saldo_total=pf['saldo_total'],
        fecha_corte=pf['fecha_corte'],
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


# ── API: ajustar saldo (nuevo corte) ─────────────────────────────────────────

@inversiones_bp.route('/api/saldo', methods=['POST'])
def set_saldo():
    """Fija el saldo real de una plataforma hoy: desde aquí se suman los
    movimientos posteriores."""
    if not _ok():
        return jsonify({'error': 'locked'}), 403
    d = request.json or {}
    plataforma = clean_str(d.get('plataforma'), 20)
    try:
        saldo = round(float(d.get('saldo')), 2)
    except (TypeError, ValueError):
        return jsonify({'error': 'Saldo inválido'}), 400
    if plataforma not in PLATAFORMAS or saldo < 0:
        return jsonify({'error': 'Datos inválidos'}), 400
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO inv_saldo_base (plataforma, saldo, fecha, updated_at) "
                   "VALUES (?, ?, ?, datetime('now'))", (plataforma, saldo, today_str()))
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
