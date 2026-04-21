from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
import datetime

prioridades_bp = Blueprint('prioridades', __name__, template_folder='../../templates')

MESES = {
    '01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun',
    '07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic'
}

def _auth():
    return session.get('fin_ok')

def _fmt_mes(val):
    if not val or '-' not in val:
        return val or ''
    y, m = val.split('-', 1)
    return f"{MESES.get(m, m)} {y}"


@prioridades_bp.route('/')
def index():
    if not _auth():
        return redirect('/finanzas')
    with get_db() as db:
        items = db.execute("""
            SELECT * FROM lista_prioridades
            ORDER BY
                CASE estado WHEN 'Pendiente' THEN 0 WHEN 'Comprado' THEN 1 ELSE 2 END,
                CASE prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 WHEN 'Baja' THEN 3 END,
                mes_objetivo, nombre
        """).fetchall()

        raw = db.execute("""
            SELECT prioridad, estado,
                   COALESCE(SUM(precio_estimado),0) as te,
                   COALESCE(SUM(precio_real),0)     as tr,
                   COUNT(*) as cnt
            FROM lista_prioridades
            GROUP BY prioridad, estado
        """).fetchall()

    # Build summary
    summary = {
        'alta_pend': 0, 'media_pend': 0, 'baja_pend': 0,
        'gastado': 0, 'pend_count': 0, 'comp_count': 0,
    }
    for r in raw:
        if r['estado'] == 'Pendiente':
            summary['pend_count'] += r['cnt']
            if r['prioridad'] == 'Alta':  summary['alta_pend']  += r['te']
            if r['prioridad'] == 'Media': summary['media_pend'] += r['te']
            if r['prioridad'] == 'Baja':  summary['baja_pend']  += r['te']
        elif r['estado'] == 'Comprado':
            summary['comp_count'] += r['cnt']
            summary['gastado']    += r['tr']

    items_dict = []
    for it in items:
        d = dict(it)
        d['mes_label'] = _fmt_mes(d.get('mes_objetivo', ''))
        items_dict.append(d)

    return render_template('finanzas/prioridades.html',
                           pg='prioridades', items=items_dict, summary=summary)


@prioridades_bp.route('/api/add', methods=['POST'])
def add():
    if not _auth():
        return jsonify({'ok': False}), 403
    d = request.json or {}
    now = datetime.datetime.now().isoformat()
    with get_db() as db:
        db.execute("""
            INSERT INTO lista_prioridades
            (nombre, categoria, prioridad, precio_estimado, mes_objetivo, tienda, url, notas, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (d.get('nombre','').strip(), d.get('categoria',''), d.get('prioridad','Media'),
             float(d.get('precio_estimado') or 0), d.get('mes_objetivo',''),
             d.get('tienda',''), d.get('url',''), d.get('notas',''), now))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/update/<int:iid>', methods=['POST'])
def update(iid):
    if not _auth():
        return jsonify({'ok': False}), 403
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
    if not _auth():
        return jsonify({'ok': False}), 403
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
    if not _auth():
        return jsonify({'ok': False}), 403
    with get_db() as db:
        db.execute("UPDATE lista_prioridades SET estado='Descartado' WHERE id=?", (iid,))
        db.commit()
    return jsonify({'ok': True})


@prioridades_bp.route('/api/get/<int:iid>')
def get_item(iid):
    if not _auth():
        return jsonify({'ok': False}), 403
    with get_db() as db:
        row = db.execute("SELECT * FROM lista_prioridades WHERE id=?", (iid,)).fetchone()
    return jsonify(dict(row) if row else {})


@prioridades_bp.route('/api/delete/<int:iid>', methods=['POST'])
def delete(iid):
    if not _auth():
        return jsonify({'ok': False}), 403
    with get_db() as db:
        db.execute("DELETE FROM lista_prioridades WHERE id=?", (iid,))
        db.commit()
    return jsonify({'ok': True})
