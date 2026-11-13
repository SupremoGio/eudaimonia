import math
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
from ec_constants import EC_RATE
from modules import wishlist_dedup
import datetime
from utils import today_date

prioridades_bp = Blueprint('prioridades', __name__, template_folder='../../templates')


@prioridades_bp.before_request
def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')

MESES = {
    '01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun',
    '07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic'
}

def _fmt_mes(val):
    if not val or '-' not in val:
        return val or ''
    y, m = val.split('-', 1)
    return f"{MESES.get(m, m)} {y}"


# ── Remates · Wishlist S1: por mes y contra el presupuesto ───────────────────
# Grupos por mes_objetivo. «Este mes» incluye lo atrasado (mes_objetivo
# anterior al actual, marcado en la fila) para que la celda y el grupo sumen
# lo mismo. Comprado y Descartado van plegados al final.
GRUPOS = [('este', 'Este mes'), ('prox', 'Próximo'), ('despues', 'Más adelante'), ('sin', 'Sin fecha')]
PRIO_ORDEN = {'Alta': 0, 'Media': 1, 'Baja': 2}
REC = {   # protocolo_rec → (tono, etiqueta corta); las mismas de prioridades.js
    'compra_optima': ('success', 'Óptima'), 'compra_limitada': ('warning', 'Limitada'),
    'reevaluar': ('warning', 'Re-evaluar'), 'no_compres': ('danger', 'No compres'),
    'bloqueo_supervivencia': ('danger', 'Bloqueo'), 'glitch_emocional': ('danger', 'Glitch emocional'),
}


def _mes_mas(mes, n):
    y, m = int(mes[:4]), int(mes[5:7]) + n
    y += (m - 1) // 12
    return f"{y}-{(m - 1) % 12 + 1:02d}"


def grupo_de(mes_objetivo, mes_actual):
    mo = (mes_objetivo or '')[:7]
    if len(mo) != 7:
        return 'sin'
    if mo <= mes_actual:
        return 'este'
    return 'prox' if mo == _mes_mas(mes_actual, 1) else 'despues'


def _en_guardarropa(db):
    """Nombres normalizados de la wishlist de Guardarropa que siguen vivos."""
    try:
        rows = db.execute("SELECT nombre FROM wishlist_items "
                          "WHERE COALESCE(estado,'evaluando') NOT IN ('descartado')").fetchall()
    except Exception:
        return set()
    return {wishlist_dedup.normaliza(r['nombre']) for r in rows}


def _ec_balance(db):
    return max(0, int(db.execute("SELECT COALESCE(SUM(amount),0) AS s FROM coins_ledger").fetchone()['s'] or 0))


def vista(db, hoy=None):
    """Todo lo que pinta /finanzas/prioridades/: grupos, plegados y la franja."""
    from modules.finanzas.budget import libre_deseos
    hoy = hoy or today_date()
    mes = hoy.strftime('%Y-%m')
    rows = [dict(r) for r in db.execute("SELECT * FROM lista_prioridades").fetchall()]
    guarda = _en_guardarropa(db)
    balance = _ec_balance(db)
    for d in rows:
        d['mes_label'] = _fmt_mes(d.get('mes_objetivo', ''))
        d['grupo'] = grupo_de(d.get('mes_objetivo'), mes)
        d['atrasado'] = d['grupo'] == 'este' and (d.get('mes_objetivo') or '')[:7] < mes
        d['rec'] = REC.get(d.get('protocolo_rec') or '')
        d['en_guardarropa'] = wishlist_dedup.normaliza(d['nombre']) in guarda
        precio = d.get('precio_estimado') or 0
        d['ec'] = math.ceil(precio / EC_RATE) if precio > 0 else 0
        d['puede_ec'] = d['estado'] == 'Pendiente' and 0 < d['ec'] <= balance
    orden = lambda d: (PRIO_ORDEN.get(d['prioridad'], 3), (d['nombre'] or '').lower())
    pend = sorted([d for d in rows if d['estado'] == 'Pendiente'], key=orden)
    grupos = [{'key': k, 'label': l, 'items': [d for d in pend if d['grupo'] == k]} for k, l in GRUPOS]
    for g in grupos:
        g['total'] = round(sum(d['precio_estimado'] or 0 for d in g['items']), 2)
    comprados = sorted([d for d in rows if d['estado'] == 'Comprado'],
                       key=lambda d: d.get('purchased_at') or '', reverse=True)
    descartados = sorted([d for d in rows if d['estado'] == 'Descartado'], key=orden)
    anio = str(hoy.year)
    del_anio = [d for d in comprados if (d.get('purchased_at') or '')[:4] == anio]
    por_prio = {p: round(sum(d['precio_estimado'] or 0 for d in pend if d['prioridad'] == p), 2) for p in PRIO_ORDEN}
    este = grupos[0]
    return {
        'mes': mes,
        'meses_mover': [{'mes': _mes_mas(mes, n), 'label': _fmt_mes(_mes_mas(mes, n))} for n in range(0, 4)],
        'grupos': grupos, 'comprados': comprados, 'descartados': descartados,
        'franja': {
            'pend_total': round(sum(por_prio.values()), 2), 'pend_count': len(pend), 'por_prio': por_prio,
            'este_total': este['total'], 'este_count': len(este['items']),
            'libre': libre_deseos(db, mes),
            'anio': hoy.year, 'anio_total': round(sum(d['precio_real'] or 0 for d in del_anio), 2), 'anio_count': len(del_anio),
        },
        'ec_balance': balance, 'ec_rate': EC_RATE,
    }


@prioridades_bp.route('/')
def index():
    with get_db() as db:
        v = vista(db)
    return render_template('finanzas/prioridades.html', pg='prioridades', v=v, rec_map=REC)


@prioridades_bp.route('/api/existe')
def existe():
    """Aviso al crear: ¿ya hay un artículo con este nombre? (no bloquea)"""
    with get_db() as db:
        r = wishlist_dedup.existente(db, 'lista_prioridades', request.args.get('nombre', ''))
    return jsonify({'existe': r})


@prioridades_bp.route('/api/add', methods=['POST'])
def add():
    d = request.json or {}
    now = datetime.datetime.now().isoformat()
    with get_db() as db:
        db.execute("""
            INSERT INTO lista_prioridades
            (nombre, categoria, prioridad, precio_estimado, mes_objetivo, tienda, url, notas,
             protocolo_score, protocolo_rec, comprar_con_ec, ec_pagado, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get('nombre','').strip(), d.get('categoria',''), d.get('prioridad','Media'),
             float(d.get('precio_estimado') or 0), d.get('mes_objetivo',''),
             d.get('tienda',''), d.get('url',''), d.get('notas',''),
             d.get('protocolo_score'), d.get('protocolo_rec'),
             1 if d.get('comprar_con_ec') else 0,
             int(d.get('ec_pagado') or 0), now))
        iid = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        # If paid with EC, register deduction in gamification ledger
        if d.get('comprar_con_ec') and int(d.get('ec_pagado') or 0) > 0:
            nombre = d.get('nombre','').strip()
            ec = int(d.get('ec_pagado'))
            db.execute(
                """INSERT INTO coins_ledger (amount, source, reference_id, description, date, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (-ec, 'reward', iid, f'Wishlist: {nombre}', now[:10], now))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/update/<int:iid>', methods=['POST'])
def update(iid):
    d = request.json or {}
    with get_db() as db:
        db.execute("""
            UPDATE lista_prioridades
            SET nombre=?, categoria=?, prioridad=?, precio_estimado=?,
                mes_objetivo=?, tienda=?, url=?, notas=?, estado=?
            WHERE id=?""",
            (d.get('nombre','').strip(), d.get('categoria',''), d.get('prioridad','Media'),
             float(d.get('precio_estimado') or 0), d.get('mes_objetivo',''),
             d.get('tienda',''), d.get('url',''), d.get('notas',''),
             d.get('estado','Pendiente'), iid))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/comprar/<int:iid>', methods=['POST'])
def comprar(iid):
    d = request.json or {}
    now = datetime.datetime.now().isoformat()
    with get_db() as db:
        db.execute(
            "UPDATE lista_prioridades SET estado='Comprado', precio_real=?, purchased_at=? WHERE id=?",
            (float(d.get('precio_real') or 0), now, iid))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/descartar/<int:iid>', methods=['POST'])
def descartar(iid):
    with get_db() as db:
        db.execute("UPDATE lista_prioridades SET estado='Descartado' WHERE id=?", (iid,))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/get/<int:iid>')
def get_item(iid):
    with get_db() as db:
        row = db.execute("SELECT * FROM lista_prioridades WHERE id=?", (iid,)).fetchone()
    return jsonify(dict(row) if row else {})


@prioridades_bp.route('/api/delete/<int:iid>', methods=['POST'])
def delete(iid):
    with get_db() as db:
        db.execute("DELETE FROM lista_prioridades WHERE id=?", (iid,))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/comprar-ec/<int:iid>', methods=['POST'])
def comprar_ec(iid):
    """«o N EC» de la fila (Remates · Wishlist S1): el mismo registro que el
    alta con comprar_con_ec (coins_ledger, source 'reward') para un artículo
    que ya está en la lista; lo marca Comprado. El monto lo calcula el servidor."""
    now = datetime.datetime.now().isoformat()
    with get_db() as db:
        it = db.execute("SELECT * FROM lista_prioridades WHERE id=?", (iid,)).fetchone()
        if not it or it['estado'] != 'Pendiente':
            return jsonify({'ok': False, 'error': 'Artículo no disponible'}), 404
        ec = math.ceil((it['precio_estimado'] or 0) / EC_RATE) if (it['precio_estimado'] or 0) > 0 else 0
        if ec <= 0:
            return jsonify({'ok': False, 'error': 'El artículo no tiene precio'}), 400
        balance = _ec_balance(db)
        if balance < ec:
            return jsonify({'ok': False, 'error': f'EC insuficientes (tienes {balance}, necesitas {ec})'}), 400
        db.execute("""INSERT INTO coins_ledger (amount, source, reference_id, description, date, created_at)
                      VALUES (?,?,?,?,?,?)""", (-ec, 'reward', iid, f"Wishlist: {it['nombre']}", now[:10], now))
        db.execute("""UPDATE lista_prioridades SET estado='Comprado', comprar_con_ec=1, ec_pagado=?,
                      precio_real=0, purchased_at=? WHERE id=?""", (ec, now, iid))
        db.commit()
    return jsonify({'ok': True, 'ec': ec, 'balance': balance - ec})


@prioridades_bp.route('/api/ec-status')
def ec_status():
    """Devuelve balance EC + cálculo sugerido para un precio dado."""
    with get_db() as db:
        balance = db.execute(
            "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger"
        ).fetchone()['s']
    balance = max(0, int(balance or 0))
    precio = float(request.args.get('precio', 0) or 0)
    ec_sugerido = math.ceil(precio / EC_RATE) if precio > 0 else 0
    puede_pagar = balance >= ec_sugerido if ec_sugerido > 0 else False
    pct_balance = round((ec_sugerido / balance * 100), 1) if balance > 0 and ec_sugerido > 0 else None
    return jsonify({
        'balance': balance,
        'ec_rate': EC_RATE,
        'ec_sugerido': ec_sugerido,
        'puede_pagar': puede_pagar,
        'pct_balance': pct_balance,
    })
