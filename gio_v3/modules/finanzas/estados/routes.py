"""
Flask blueprint for Estados de Cuenta — embedded React SPA + full REST API.
All data lives in Eudaimonia's existing database (Turso-backed → persistent on Railway).
Tables are prefixed with est_ to avoid conflicts.
"""
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

estados_bp = Blueprint(
    'estados',
    __name__,
    template_folder='../../../templates',
)

BANK_META = {
    "BBVA":     {"color": "#004B96", "type": "Tarjeta de crédito", "icon": "🔵"},
    "BBVA_DEB": {"color": "#004B96", "type": "Cuenta de débito",   "icon": "🏦"},
    "INVEX":    {"color": "#E30D13", "type": "Tarjeta de crédito", "icon": "🔴"},
    "HSBC":     {"color": "#DB0011", "type": "Tarjeta de crédito", "icon": "💳"},
    "MANUAL":   {"color": "#64748b", "type": "Entrada manual",     "icon": "✏️"},
}


# ── Auth helper ───────────────────────────────────────────────────────────────

def _locked():
    return jsonify({'error': 'locked'}), 403

def _ok():
    return session.get('fin_ok')


# ── Filter builder ────────────────────────────────────────────────────────────

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
        db.execute(
            """INSERT OR IGNORE INTO est_movimientos
               (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fecha, fecha, desc, float(d.get('monto', 0)),
             d.get('banco', 'MANUAL'), '',
             d.get('categoria', 'OTROS'), d.get('subcategoria', ''),
             d.get('tipo', 'GASTO')),
        )
        db.commit()
    return jsonify({'inserted': 1}), 201


@estados_bp.route('/api/transactions/<int:tx_id>', methods=['PATCH'])
def update_transaction(tx_id):
    if not _ok(): return _locked()
    d = request.json or {}
    with get_db() as db:
        if d.get('categoria') is not None:
            db.execute(
                "UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?",
                (d['categoria'], d.get('subcategoria', ''), tx_id),
            )
        if d.get('monto') is not None:
            db.execute("UPDATE est_movimientos SET monto=? WHERE id=?",
                       (float(d['monto']), tx_id))
        if d.get('tipo') is not None:
            db.execute("UPDATE est_movimientos SET tipo=? WHERE id=?",
                       (d['tipo'], tx_id))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("DELETE FROM est_movimientos WHERE id=?", (tx_id,))
        db.commit()
    return jsonify({'ok': True})


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
        row = db.execute("""
            SELECT
                SUM(CASE WHEN tipo='INGRESO'    THEN monto ELSE 0 END) AS income,
                SUM(CASE WHEN tipo='GASTO'      THEN monto ELSE 0 END) AS expense,
                SUM(CASE WHEN tipo='INVERSION'  THEN monto ELSE 0 END) AS inversion,
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
                SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE 0 END) AS income,
                SUM(CASE WHEN tipo='GASTO'   THEN monto ELSE 0 END) AS expense
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
    date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
    date_to   = request.args.get('date_to')
    bank      = request.args.get('bank')

    conds  = ["tipo='GASTO'", "fecha >= ?"]
    params = [date_from]
    if date_to:
        conds.append("fecha <= ?"); params.append(date_to)
    if bank:
        conds.append("banco = ?"); params.append(bank)

    with get_db() as db:
        rows = db.execute(f"""
            SELECT categoria, SUM(monto) AS total
            FROM est_movimientos
            WHERE {' AND '.join(conds)}
            GROUP BY categoria ORDER BY total DESC
        """, params).fetchall()

    return jsonify([{'categoria': r['categoria'], 'total': round(r['total'] or 0, 2)} for r in rows])


@estados_bp.route('/api/summary/stats')
def summary_stats():
    if not _ok(): return _locked()
    date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
    date_to   = request.args.get('date_to')
    bank      = request.args.get('bank')

    conds  = ["fecha >= ?"]
    params = [date_from]
    if date_to:
        conds.append("fecha <= ?"); params.append(date_to)
    if bank:
        conds.append("banco = ?"); params.append(bank)
    where = " AND ".join(conds)

    with get_db() as db:
        agg = db.execute(f"""
            SELECT
                SUM(CASE WHEN tipo='GASTO'   THEN monto ELSE 0 END) AS total_expense,
                SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE 0 END) AS total_income,
                COUNT(CASE WHEN tipo='GASTO' THEN 1 END)            AS tx_count,
                COUNT(CASE WHEN tipo='GASTO' AND categoria='OTROS' THEN 1 END) AS unclassified
            FROM est_movimientos WHERE {where}
        """, params).fetchone()

        max_row = db.execute(f"""
            SELECT descripcion, monto FROM est_movimientos
            WHERE tipo='GASTO' AND {where}
            ORDER BY monto DESC LIMIT 1
        """, params).fetchone()

    expense  = agg['total_expense'] or 0
    income   = agg['total_income']  or 0
    tx_count = agg['tx_count']      or 0

    d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    d_to   = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else datetime.now().date()
    days   = max((d_to - d_from).days + 1, 1)

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
        rows = db.execute("""
            SELECT banco,
                   SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE 0 END) AS income,
                   SUM(CASE WHEN tipo='GASTO'   THEN monto ELSE 0 END) AS expense,
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
            'icon':     meta.get('icon', '💳'),
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
        rows = db.execute("""
            SELECT categoria, SUM(monto) AS total
            FROM est_movimientos
            WHERE tipo='GASTO' AND fecha >= ?
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
        """, (d.get('categoria'), d.get('nombre') or d.get('categoria'), float(d.get('limite', 0))))
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
            db.execute("UPDATE est_budgets SET limite=? WHERE id=?", (float(d['limite']), bid))
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
                WHERE tipo='GASTO' AND UPPER(descripcion) LIKE ? AND categoria='OTROS'
            """, (cat, subcat, f'%{kw}%'))
            updated = result.rowcount if hasattr(result, 'rowcount') else 0
        else:
            updated = 0

        db.commit()

    return jsonify({'ok': True, 'updated_transactions': updated}), 201


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
    with get_db() as db:
        prestado = db.execute(
            "SELECT SUM(monto) FROM est_movimientos WHERE tipo='PRESTAMO'"
        ).fetchone()[0] or 0
        cobrado = db.execute(
            "SELECT SUM(monto) FROM est_movimientos WHERE tipo='COBRO_PRESTAMO'"
        ).fetchone()[0] or 0
        detalle = db.execute("""
            SELECT descripcion, tipo, SUM(monto) AS total, COUNT(*) AS n
            FROM est_movimientos
            WHERE tipo IN ('PRESTAMO','COBRO_PRESTAMO')
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
        inserted = 0
        skipped  = 0
        with get_db() as db:
            existing = set()
            for r in db.execute("SELECT fecha, descripcion FROM est_movimientos").fetchall():
                existing.add((r['fecha'], r['descripcion']))

            for m in movimientos:
                key = (m['fecha'], m['descripcion'])
                if key in existing:
                    skipped += 1
                    continue
                existing.add(key)
                db.execute("""
                    INSERT OR IGNORE INTO est_movimientos
                    (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    m['fecha'], m.get('fecha_cargo', m['fecha']),
                    m['descripcion'], m['monto'],
                    m.get('banco', bank), m.get('periodo', ''),
                    m['categoria'], m.get('subcategoria', ''), m['tipo'],
                ))
                inserted += 1
            db.commit()

        preview = [
            {k: v for k, v in m.items() if k != 'periodo'}
            for m in movimientos[:5]
        ]
        return jsonify({
            'ok': True, 'bank': bank,
            'parsed': len(movimientos), 'inserted': inserted,
            'skipped': skipped, 'preview': preview,
        })

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)
