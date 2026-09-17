"""
Flask blueprint for Estados de Cuenta — embedded React SPA + full REST API.
All data lives in Eudaimonia's existing database (Turso-backed → persistent on Railway).
Tables are prefixed with est_ to avoid conflicts.
"""
import calendar
import csv
import io
import tempfile
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, render_template, request,
    session, jsonify, Response, redirect, url_for,
)
from database import get_db
from utils import clean_str, today_str, safe_float
import modules.gamification.engine as engine

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
_PAGO_CATS = "categoria NOT IN ('PAGO_TDC', 'PAGO', 'PRESTAMOS')"
# Use mi_parte when set (shared expense), otherwise full monto
_MONTO = "COALESCE(mi_parte, monto)"
# INGRESO categories that are NOT real income (transfers, cash mobilization)
_INGRESO_EXCLUIR = ('TRANSFERENCIA', 'PAGO_TDC', 'RETIRO', 'DEPOSITO', 'SPEI_RECIBIDO', 'APORTACION_RENTA', 'PRESTAMOS')
_INGRESO_EXCLUIR_SQL = "categoria NOT IN ({})".format(
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

@estados_bp.route('/api/transactions')
def list_transactions():
    if not _ok(): return _locked()

    limit  = min(int(request.args.get('limit', 200)), 2000)
    offset = int(request.args.get('offset', 0))
    conds, params = _build_filters(request.args)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    with get_db() as db:
        total = db.execute(
            f"SELECT COUNT(*) FROM est_movimientos {where}", params
        ).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM est_movimientos {where} ORDER BY fecha DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return jsonify({'data': [dict(r) for r in rows], 'total': total})


@estados_bp.route('/api/transactions', methods=['POST'])
def create_transaction():
    if not _ok(): return _locked()
    d = request.json or {}
    fecha = d.get('fecha', '')
    desc  = d.get('descripcion', '')
    with get_db() as db:
        cur = db.execute(
            """INSERT OR IGNORE INTO est_movimientos
               (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fecha, fecha, desc, safe_float(d.get('monto', 0)),
             d.get('banco', 'MANUAL'), '',
             d.get('categoria', 'OTROS'), d.get('subcategoria', ''),
             d.get('tipo', 'GASTO')),
        )
        db.commit()
        inserted = cur.rowcount
    if not inserted:
        # Índice UNIQUE(fecha, descripcion): ya existe un movimiento con esa
        # misma fecha y descripción exacta — no se guardó. Devolvemos error
        # real en vez de fingir éxito, para que el cliente pueda avisar.
        return jsonify({
            'inserted': 0,
            'error': 'Ya existe un movimiento con esa fecha y descripción exacta. '
                     'Cambia la descripción si es una transacción distinta (ej. añade la hora o el monto).',
        }), 409
    return jsonify({'inserted': 1}), 201


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
                (d['categoria'], d.get('subcategoria', ''), tx_id),
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
        if 'mi_parte' in d:
            val = safe_float(d['mi_parte']) if d['mi_parte'] not in (None, '') else None
            db.execute("UPDATE est_movimientos SET mi_parte=? WHERE id=?", (val, tx_id))
        if 'reembolso_cat' in d:
            val = d['reembolso_cat'] or None
            db.execute("UPDATE est_movimientos SET reembolso_cat=? WHERE id=?", (val, tx_id))
        if 'viaje_id' in d:
            val = int(d['viaje_id']) if d['viaje_id'] not in (None, '') else None
            db.execute("UPDATE est_movimientos SET viaje_id=? WHERE id=?", (val, tx_id))
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

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=transacciones.csv'},
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


@estados_bp.route('/api/summary/by-category')
def by_category():
    if not _ok(): return _locked()
    bank = request.args.get('bank')

    conds  = ["tipo='GASTO'", _PAGO_CATS]
    params = []
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
            SELECT categoria,
                   SUM({_MONTO}) AS total
            FROM est_movimientos
            WHERE {' AND '.join(conds)}
            GROUP BY categoria ORDER BY total DESC
        """, params).fetchall()

    return jsonify([{'categoria': r['categoria'], 'total': round(r['total'] or 0, 2)} for r in rows])


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
    subcat = d.get('subcategoria', '')

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
            """, (kw_row['categoria'], kw_row['subcategoria'], f'%{kw_row["keyword"]}%'))
            total_updated += result.rowcount if hasattr(result, 'rowcount') else 0
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
                existing.add((r['fecha'], float(r['monto']), r['tipo']))

            # También rastreamos depósitos/SPEIs nuevos para el response
            review_needed = []

            for m in movimientos:
                m_banco = m.get('banco', bank) or bank
                m_monto = float(m['monto'])
                # Dedup solo aplica a montos > 0
                key = (m['fecha'], m_monto, m['tipo'])
                if m_monto > 0 and key in existing:
                    skipped += 1
                    continue
                if m_monto > 0:
                    existing.add(key)
                cur = db.execute("""
                    INSERT OR IGNORE INTO est_movimientos
                    (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    m['fecha'], m.get('fecha_cargo', m['fecha']),
                    m['descripcion'], m['monto'],
                    m_banco, m.get('periodo', ''),
                    m['categoria'], m.get('subcategoria', ''), m['tipo'],
                ))
                if not cur.rowcount:
                    # Pasó el dedup de (fecha, monto, tipo) pero chocó con el índice
                    # UNIQUE(fecha, descripcion) — es una transacción real distinta
                    # (mismo día, misma descripción del banco, otro monto) que NO
                    # se guardó. No la contamos como "inserted".
                    dedup_conflict += 1
                    continue
                inserted += 1
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
                """, (kw_row['categoria'], kw_row['subcategoria'], f'%{kw_row["keyword"]}%'))

            # ── Post-proceso inversiones ──────────────────────────────────────
            # Cuando categoria='INVERSION', elevar tipo y asignar plataforma+dirección.
            # Plataformas detectadas por keyword en descripción.
            _PLAT_KW = [
                ('GBM',   'GBM'),
                ('INVEX', 'INVEX'),
                ('CETES', 'CETESDIRECTO'),
                ('CETES', 'NAFIN'),
                ('CRYPTO','BITSO'),
                ('CRYPTO','COINBASE'),
                ('FIBRA', 'FIBRA'),
            ]
            # Patrones que NUNCA son inversión aunque categoria='INVERSION':
            # son pagos/transferencias que contienen el nombre de la plataforma
            # en la descripción pero no son depósitos reales.
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
                # Excluir transferencias/pagos que no son inversiones reales
                if any(excl in desc_up for excl in _NOT_INVERSION):
                    db.execute("""
                        UPDATE est_movimientos
                        SET tipo='PAGO', categoria='PAGO_TDC', subcategoria='Pago TDC'
                        WHERE id=?
                    """, (row['id'],))
                    continue
                plat = 'OTRO'
                for p, kw in _PLAT_KW:
                    if kw in desc_up:
                        plat = p
                        break
                if plat == 'GBM':
                    gbm_detected = True
                # Dirección: GASTO = dinero sale → APORTACION; INGRESO = dinero entra → RETIRO
                direction = 'APORTACION' if row['tipo'] == 'GASTO' else 'RETIRO'
                db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INVERSION', categoria=?, subcategoria=?
                    WHERE id=?
                """, (plat, direction, row['id']))

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
        })

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


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

        pdf_por_clave = {}
        for m in movimientos:
            pdf_por_clave.setdefault((m['fecha'], m['descripcion']), []).append(m)

        with get_db() as db:
            db_rows = db.execute(
                "SELECT id, fecha, descripcion, monto, tipo FROM est_movimientos "
                "WHERE banco='BBVA_DEB' AND periodo=?",
                (periodo,),
            ).fetchall() if periodo else []

        db_por_clave = {}
        for r in db_rows:
            db_por_clave.setdefault((r['fecha'], r['descripcion']), []).append(dict(r))

        faltan_en_db = []       # está en el PDF, no hay fila en la DB para esa clave
        monto_no_coincide = []  # misma clave, pero el monto guardado es distinto
        for clave, pdf_movs in pdf_por_clave.items():
            db_movs = db_por_clave.get(clave, [])
            if not db_movs:
                faltan_en_db.extend({
                    'fecha': m['fecha'], 'descripcion': m['descripcion'], 'monto_pdf': m['monto'],
                } for m in pdf_movs)
                continue
            # Compara ordenado por monto — cubre el caso normal (una fila
            # por clave) y el de varias filas iguales del mismo día.
            for pm, dm in zip(sorted(pdf_movs, key=lambda x: x['monto']),
                               sorted(db_movs, key=lambda x: x['monto'])):
                if abs(pm['monto'] - dm['monto']) >= 0.01:
                    monto_no_coincide.append({
                        'id': dm['id'], 'fecha': pm['fecha'], 'descripcion': pm['descripcion'],
                        'monto_pdf': pm['monto'], 'monto_guardado': dm['monto'],
                    })
            if len(pdf_movs) > len(db_movs):
                faltan_en_db.extend({
                    'fecha': m['fecha'], 'descripcion': m['descripcion'], 'monto_pdf': m['monto'],
                } for m in sorted(pdf_movs, key=lambda x: x['monto'])[len(db_movs):])

        fantasmas_en_db = []  # está en la DB con este periodo, no matchea ningún movimiento del PDF
        for clave, db_movs in db_por_clave.items():
            pdf_movs = pdf_por_clave.get(clave, [])
            if len(db_movs) > len(pdf_movs):
                fantasmas_en_db.extend({
                    'id': r['id'], 'fecha': r['fecha'], 'descripcion': r['descripcion'],
                    'monto': r['monto'], 'tipo': r['tipo'],
                } for r in sorted(db_movs, key=lambda x: x['monto'])[len(pdf_movs):])

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


# SQL expression that buckets a transaction into a travel concept
_CONCEPTO_CASE = """
  CASE
    WHEN categoria='VIAJES/VUELOS' AND subcategoria='Vuelos' THEN 'Vuelos'
    WHEN categoria='VIAJES/VUELOS' AND subcategoria='Hotel'  THEN 'Hotel'
    WHEN categoria='TRANSPORTE'
      OR (categoria='VIAJES/VUELOS' AND subcategoria='Transporte viaje') THEN 'Transporte'
    WHEN categoria IN ('COMIDA/REST','CAFE/PAN') THEN 'Comida'
    WHEN (categoria='VIAJES/VUELOS' AND subcategoria='Tours')
      OR categoria='ENTRETENIMIENTO' THEN 'Experiencias'
    ELSE 'Otros'
  END
"""

_GASTO_FILTER = "tipo='GASTO' AND categoria NOT IN ('PAGO_TDC','PAGO')"


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
                            THEN COALESCE(m.mi_parte, m.monto) ELSE 0 END
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
                   SUM(COALESCE(mi_parte, monto)) AS total,
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
