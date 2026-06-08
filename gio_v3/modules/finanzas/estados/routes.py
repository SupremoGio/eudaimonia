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
from utils import clean_str

estados_bp = Blueprint(
    'estados',
    __name__,
    template_folder='../../../templates',
)

# Categories that represent debt payments — never counted as real expenses
_PAGO_CATS = "categoria NOT IN ('PAGO_TDC', 'PAGO')"
# Use mi_parte when set (shared expense), otherwise full monto
_MONTO = "COALESCE(mi_parte, monto)"
# INGRESO categories that are NOT real income (transfers, cash mobilization)
_INGRESO_EXCLUIR = ('TRANSFERENCIA', 'PAGO_TDC', 'RETIRO', 'DEPOSITO', 'SPEI_RECIBIDO')
_INGRESO_EXCLUIR_SQL = "categoria NOT IN ({})".format(
    ','.join(f"'{c}'" for c in _INGRESO_EXCLUIR)
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
                       (float(d['monto']), tx_id))
        if d.get('tipo') is not None:
            db.execute("UPDATE est_movimientos SET tipo=? WHERE id=?",
                       (d['tipo'], tx_id))
        if 'mi_parte' in d:
            val = float(d['mi_parte']) if d['mi_parte'] not in (None, '') else None
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
    date_from = request.args.get('date_from') or datetime.now().replace(day=1).strftime("%Y-%m-%d")
    date_to   = request.args.get('date_to')
    bank      = request.args.get('bank')

    conds  = ["tipo='GASTO'", _PAGO_CATS, "fecha >= ?"]
    params = [date_from]
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
                SUM(CASE WHEN tipo='GASTO'   AND {_PAGO_CATS} THEN {_MONTO} ELSE 0 END) AS total_expense,
                SUM(CASE WHEN tipo='INGRESO'                   THEN monto ELSE 0 END) AS total_income,
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
        rows = db.execute(f"""
            SELECT banco,
                   SUM(CASE WHEN tipo='INGRESO'                  THEN monto    ELSE 0 END) AS income,
                   SUM(CASE WHEN tipo='GASTO' AND {_PAGO_CATS}   THEN {_MONTO} ELSE 0 END) AS expense,
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
        # Key = (fecha, monto, banco) — robusto ante diferencias de descripción
        # entre PDF y CSV del mismo banco para la misma transacción.
        inserted = 0
        skipped  = 0
        with get_db() as db:
            existing = set()
            for r in db.execute(
                "SELECT fecha, monto, banco FROM est_movimientos"
            ).fetchall():
                existing.add((r['fecha'], float(r['monto']), r['banco']))

            # También rastreamos depósitos/SPEIs nuevos para el response
            review_needed = []

            for m in movimientos:
                m_banco = m.get('banco', bank) or bank
                key = (m['fecha'], float(m['monto']), m_banco)
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
                    m_banco, m.get('periodo', ''),
                    m['categoria'], m.get('subcategoria', ''), m['tipo'],
                ))
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
            inv_candidates = db.execute("""
                SELECT id, descripcion, tipo
                FROM est_movimientos
                WHERE categoria='INVERSION' AND tipo IN ('INGRESO','GASTO')
            """).fetchall()

            for row in inv_candidates:
                desc_up = row['descripcion'].upper()
                plat = 'OTRO'
                for p, kw in _PLAT_KW:
                    if kw in desc_up:
                        plat = p
                        break
                # Dirección: GASTO = dinero sale → APORTACION; INGRESO = dinero entra → RETIRO
                direction = 'APORTACION' if row['tipo'] == 'GASTO' else 'RETIRO'
                db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INVERSION', categoria=?, subcategoria=?
                    WHERE id=?
                """, (plat, direction, row['id']))

            db.commit()

        preview = [
            {k: v for k, v in m.items() if k != 'periodo'}
            for m in movimientos[:5]
        ]
        return jsonify({
            'ok': True, 'bank': bank,
            'parsed': len(movimientos), 'inserted': inserted,
            'skipped': skipped, 'preview': preview,
            'review_needed': review_needed,  # DEPOSITO/SPEI pendientes de clasificar
        })

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Viajes ────────────────────────────────────────────────────────────────────

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
            FROM est_viajes v
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
            """INSERT INTO est_viajes
               (nombre, destino, fecha_inicio, fecha_fin, presupuesto, estado, notas, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                clean_str(nombre, 200),
                clean_str(d.get('destino', ''), 100),
                d.get('fecha_inicio', ''),
                d.get('fecha_fin', ''),
                float(d.get('presupuesto', 0)),
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
        params.append(float(d['presupuesto']))
    if not fields:
        return jsonify({'ok': True})
    params.append(trip_id)
    with get_db() as db:
        db.execute(f"UPDATE est_viajes SET {', '.join(fields)} WHERE id=?", params)
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/trips/<int:trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    if not _ok(): return _locked()
    with get_db() as db:
        db.execute("UPDATE est_movimientos SET viaje_id=NULL WHERE viaje_id=?", (trip_id,))
        db.execute("DELETE FROM est_viajes WHERE id=?", (trip_id,))
        db.commit()
    return jsonify({'ok': True})


@estados_bp.route('/api/trips/<int:trip_id>/summary')
def trip_summary(trip_id):
    if not _ok(): return _locked()
    with get_db() as db:
        trip = db.execute("SELECT * FROM est_viajes WHERE id=?", (trip_id,)).fetchone()
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
            "SELECT fecha_inicio, fecha_fin FROM est_viajes WHERE id=?", (trip_id,)
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
        if not db.execute("SELECT id FROM est_viajes WHERE id=?", (trip_id,)).fetchone():
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
