import math
from flask import Blueprint, render_template, request, jsonify
from database import get_db
from datetime import datetime
from ec_constants import EC_RATE

wishlist_bp = Blueprint('wishlist', __name__, template_folder='../../templates')

CATEGORIAS = [
    'Tecnología', 'Ropa & Calzado', 'Hogar', 'Deporte & Fitness',
    'Entretenimiento', 'Salud & Bienestar', 'Educación & Libros',
    'Herramientas & Trabajo', 'Viajes', 'Otro',
]


@wishlist_bp.route('/')
def index():
    today = datetime.now().strftime('%d %b %Y')
    return render_template('guardarropa/wishlist.html', today=today, categorias=CATEGORIAS)


# ── API ────────────────────────────────────────────────────────────────────────

@wishlist_bp.route('/api/items')
def get_items():
    db = get_db()
    estado = request.args.get('estado', '')
    view = request.args.get('view', '')
    q = "SELECT * FROM wishlist_items"
    params = []
    if estado:
        q += " WHERE estado = ?"
        params.append(estado)
    elif view == 'activos':
        q += " WHERE estado IN ('evaluando','pendiente')"
    q += " ORDER BY created_at DESC"
    items = [dict(r) for r in db.execute(q, params).fetchall()]
    return jsonify(items)


@wishlist_bp.route('/api/item', methods=['POST'])
def add_item():
    db = get_db()
    d = request.json or {}
    now = datetime.now().isoformat()
    nombre = (d.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'nombre requerido'}), 400
    db.execute(
        """INSERT INTO wishlist_items
           (nombre, categoria, precio_estimado, descripcion, url, marca, estado, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            nombre,
            d.get('categoria', ''),
            float(d.get('precio_estimado') or 0),
            d.get('descripcion', ''),
            d.get('url', ''),
            d.get('marca', ''),
            'evaluando',
            now,
        ),
    )
    db.commit()
    item_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
    return jsonify({'ok': True, 'id': item_id})


@wishlist_bp.route('/api/item/<int:item_id>/quiz', methods=['POST'])
def submit_quiz(item_id):
    db = get_db()
    d = request.json or {}

    score, rec, reasons = _compute_protocol(d)

    now = datetime.now().isoformat()
    db.execute(
        """UPDATE wishlist_items SET
           dias_deseo=?, q1_persiste=?,
           q2_estado_financiero=?, q2_clasificacion=?,
           q3_es_util=?, q3_tiene_alternativa=?,
           q3_usos_mes=?, q3_cpu_ok=?,
           q3_mantenimiento_ok=?, q3_costo_oportunidad_ok=?,
           score=?, recomendacion=?, razon_recomendacion=?,
           estado='pendiente', updated_at=?
           WHERE id=?""",
        (
            d.get('dias_deseo'),
            1 if d.get('q1_persiste') else 0,
            d.get('q2_estado_financiero'),
            d.get('q2_clasificacion'),
            1 if d.get('q3_es_util') else 0,
            1 if d.get('q3_tiene_alternativa') else 0,
            d.get('q3_usos_mes'),
            1 if d.get('q3_cpu_ok') else 0,
            1 if d.get('q3_mantenimiento_ok') else 0,
            1 if d.get('q3_costo_oportunidad_ok') else 0,
            score,
            rec,
            ' | '.join(reasons),
            now,
            item_id,
        ),
    )
    db.commit()
    return jsonify({'ok': True, 'score': score, 'recomendacion': rec, 'razones': reasons})


@wishlist_bp.route('/api/item/<int:item_id>/decide', methods=['POST'])
def decide(item_id):
    db = get_db()
    d = request.json or {}
    decision = d.get('decision', 'pendiente')
    now = datetime.now().isoformat()
    purchased_at = now if decision == 'comprado' else None
    db.execute(
        """UPDATE wishlist_items
           SET estado=?, decision_override=?, notas_decision=?, purchased_at=?, updated_at=?
           WHERE id=?""",
        (decision, 1 if d.get('override') else 0, d.get('notas', ''), purchased_at, now, item_id),
    )
    db.commit()
    return jsonify({'ok': True})


@wishlist_bp.route('/api/item/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    db = get_db()
    db.execute("DELETE FROM wishlist_items WHERE id=?", (item_id,))
    db.commit()
    return jsonify({'ok': True})


# ── EC / Gamification ──────────────────────────────────────────────────────────

@wishlist_bp.route('/api/ec-status')
def ec_status():
    """Devuelve balance EC + cálculo sugerido para un precio dado."""
    db = get_db()
    balance = db.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger"
    ).fetchone()['s']
    balance = max(0, balance)

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


@wishlist_bp.route('/api/item/<int:item_id>/comprar-ec', methods=['POST'])
def comprar_ec(item_id):
    """Deduce EC del ledger y marca el artículo como comprado con EC."""
    db = get_db()
    item = db.execute(
        "SELECT nombre, precio_estimado, ec_sugerido FROM wishlist_items WHERE id=?",
        (item_id,)
    ).fetchone()
    if not item:
        return jsonify({'ok': False, 'error': 'Artículo no encontrado'}), 404

    d = request.json or {}
    ec_a_pagar = int(d.get('ec_cantidad', 0))
    if ec_a_pagar <= 0:
        return jsonify({'ok': False, 'error': 'Cantidad EC inválida'}), 400

    balance = db.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger"
    ).fetchone()['s']
    if balance < ec_a_pagar:
        return jsonify({'ok': False, 'error': f'EC insuficientes (tienes {balance}, necesitas {ec_a_pagar})'}), 400

    now = datetime.now().isoformat()
    # Registrar la deducción en el ledger de gamificación
    db.execute(
        """INSERT INTO coins_ledger (amount, source, reference_id, description, date, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            -ec_a_pagar,
            'reward',
            item_id,
            f'Wishlist: {item["nombre"]}',
            now[:10],
            now,
        ),
    )
    # Actualizar el artículo
    db.execute(
        """UPDATE wishlist_items
           SET comprar_con_ec=1, ec_sugerido=?, ec_pagado=?, estado='comprado',
               decision_override=0, purchased_at=?, updated_at=?
           WHERE id=?""",
        (ec_a_pagar, ec_a_pagar, now, now, item_id),
    )
    db.commit()
    nuevo_balance = max(0, balance - ec_a_pagar)
    return jsonify({'ok': True, 'nuevo_balance': nuevo_balance, 'ec_gastado': ec_a_pagar})


# ── Protocol engine ────────────────────────────────────────────────────────────

def _compute_protocol(d):
    score = 0
    reasons = []

    dias = int(d.get('dias_deseo') or 0)
    q1 = bool(d.get('q1_persiste'))
    q2_estado = d.get('q2_estado_financiero', '')
    q2_cls = d.get('q2_clasificacion', '')
    q3_util = bool(d.get('q3_es_util'))
    q3_dry = bool(d.get('q3_tiene_alternativa'))
    q3_usos = float(d.get('q3_usos_mes') or 1) or 1
    q3_cpu = bool(d.get('q3_cpu_ok'))
    q3_mant = bool(d.get('q3_mantenimiento_ok'))
    q3_cap = bool(d.get('q3_costo_oportunidad_ok'))

    # ── FASE 1: Dopamine firewall (20 pts) ────────────────────────────────────
    if dias >= 7:
        score += 15
        reasons.append(f'Deseo verificado por {dias} días — supera el filtro de 72h con solidez')
    elif dias >= 3:
        score += 10
        reasons.append(f'Deseo de {dias} días — supera el umbral mínimo de 72h')
    elif dias >= 1:
        score += 5
        reasons.append(f'Deseo de {dias} día(s) — todavía en zona de riesgo dopamínico')
    else:
        reasons.append('Deseo del mismo día — alta probabilidad de compra impulsiva')

    if not q1:
        reasons.append('El deseo desaparece en calma — patrón de glitch emocional detectado')
        return score, 'glitch_emocional', reasons

    score += 5
    reasons.append('El deseo persiste sin estímulos externos — señal de necesidad real')

    # ── FASE 2: Solvency audit (30 pts) ───────────────────────────────────────
    if q2_estado == 'estable':
        score += 30
        reasons.append('Estado financiero estable — capital disponible para la decisión')
    else:
        if q2_cls == 'capex':
            score += 15
            reasons.append('Estado inestable, pero es inversión productiva (CapEx) — compra estratégica limitada justificada')
            return score, 'compra_limitada', reasons
        else:
            reasons.append('Estado inestable + gasto de ocio (OpEx) — bloqueo por supervivencia financiera')
            return score, 'bloqueo_supervivencia', reasons

    # ── FASE 3: Logic algorithm (50 pts) ──────────────────────────────────────
    if not q3_util:
        reasons.append('Sin utilidad directa para tu diseño de vida o trabajo — rechazado por utilidad')
        return score, 'no_compres', reasons
    score += 15
    reasons.append('Útil para trabajo/vida — pasa el filtro de utilidad directa')

    if q3_dry:
        reasons.append('Ya tienes algo que cumple el 80% de la función — redundancia evitada (principio DRY)')
        return score, 'no_compres', reasons
    score += 10
    reasons.append('No tienes una alternativa equivalente — no es redundante')

    if not q3_cpu:
        reasons.append('Costo por uso elevado — retorno de inversión insuficiente')
        return score, 'no_compres', reasons
    score += 15
    reasons.append(f'Costo por uso favorable ({q3_usos:.0f} usos/mes) — buena relación valor/precio')

    if not q3_mant:
        reasons.append('Mantenimiento alto (>10 min/semana) — el costo de tiempo real es significativo')
        return score, 'reevaluar', reasons
    score += 5
    reasons.append('Bajo mantenimiento — no drena tu tiempo de forma relevante')

    if q3_cap:
        reasons.append('El capital rendiría más invertido compuesto — costo de oportunidad supera el valor')
        return score, 'no_compres', reasons
    score += 5
    reasons.append('El valor del artículo supera el rendimiento compuesto del capital — adquisición justificada')

    return score, 'compra_optima', reasons
