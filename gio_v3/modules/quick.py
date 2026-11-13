"""
quick.py — Captura rápida (handoff Captura): lectura para la hoja «+» y ⌘K.

GET  /api/quick/options?id=<id>  opciones dinámicas y defaults de un registro
                                 de nav.QUICK (solo lectura).
GET  /api/quick/badges           contadores de la barra: anclas que faltan hoy
                                 en Acta y tareas vencidas en Praxis.
POST /api/quick/uso              suma un uso (orden de la hoja) y recuerda los
                                 últimos valores elegidos (defaults). Solo
                                 escribe en app_settings: los datos de cada
                                 módulo se guardan en el endpoint que ya usa.
"""
import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session
from database import get_db
from utils import today_str, today_date
from modules import nav

quick_bp = Blueprint('quick', __name__)

_USES = 'quick_uses:'
_LAST = 'quick_last:'

# Cuentas válidas para un gasto capturado a mano (BANK_META de Oikonomia)
CUENTAS = [('MANUAL', 'Efectivo'), ('BBVA_DEB', 'BBVA débito'), ('BBVA_TDC', 'BBVA crédito'),
           ('INVEX', 'Invex'), ('HSBC', 'HSBC')]
CATEGORIAS_BASE = ['COMIDA_FUERA', 'SUPER', 'TRANSPORTE', 'OCIO', 'CAFE/PAN', 'SALUD']


def _setting(db, key, default=None):
    r = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return r['value'] if r else default


def usos(db=None):
    """{id: n} de usos guardados (para ordenar la hoja)."""
    def _q(d):
        return {r['key'][len(_USES):]: int(r['value'] or 0) for r in d.execute(
            "SELECT key, value FROM app_settings WHERE substr(key,1,?)=?", (len(_USES), _USES)).fetchall()}
    if db is not None:
        return _q(db)
    with get_db() as d:
        return _q(d)


def _etiqueta_cat(c):
    return (c or '').replace('_', ' ').replace('/', ' / ').capitalize()


def _hhmm(t):
    try:
        h, m = (int(x) for x in (t or '0:0').split(':')[:2])
        return h * 60 + m
    except ValueError:
        return 0


def _opciones(db, qid):
    """{campo: {options: [...], default: v}} para los campos dinámicos."""
    last = {}
    raw = _setting(db, _LAST + qid)
    if raw:
        try:
            last = json.loads(raw)
        except ValueError:
            last = {}
    out = {}
    if qid == 'gasto':
        desde = (today_date() - timedelta(days=30)).isoformat()
        top = [r['categoria'] for r in db.execute(
            """SELECT categoria, COUNT(*) n FROM est_movimientos
               WHERE tipo='GASTO' AND fecha>=? AND COALESCE(categoria,'')!='' AND categoria NOT IN ('PAGO','TRANSFERENCIA')
               GROUP BY categoria ORDER BY n DESC LIMIT 6""", (desde,)).fetchall()]
        cats = top + [c for c in CATEGORIAS_BASE if c not in top]
        cats = cats[:6]
        out['categoria'] = {'options': [{'value': c, 'label': _etiqueta_cat(c)} for c in cats],
                            'default': last.get('categoria') if last.get('categoria') in cats else cats[0]}
        validas = [c for c, _ in CUENTAS]
        out['cuenta'] = {'options': [{'value': c, 'label': l} for c, l in CUENTAS],
                         'default': last.get('cuenta') if last.get('cuenta') in validas else 'MANUAL'}
    elif qid == 'comida':
        from modules.nutricion.routes import get_week_start, get_today_key, get_or_seed_week
        get_or_seed_week(db, get_week_start().isoformat())          # la semana se siembra al primer uso
        rows = db.execute("""SELECT id, slot, time_str, name FROM nutricion_semana
                             WHERE week_start=? AND day_key=? AND done=0 ORDER BY time_str""",
                          (get_week_start().isoformat(), get_today_key())).fetchall()
        ops = [{'value': r['id'], 'label': r['slot'], 'hint': r['name']} for r in rows]
        ahora = datetime.now().hour * 60 + datetime.now().minute
        due = [r for r in rows if _hhmm(r['time_str']) <= ahora + 60]
        pick = (due[-1] if due else (rows[0] if rows else None))
        out['meal'] = {'options': ops, 'default': pick['id'] if pick else None}
    elif qid == 'actividad':
        import modules.actividades.activity_defs as adefs
        hoy = today_str()
        hechas = {r['activity_key'] for r in db.execute(
            "SELECT activity_key FROM activity_logs WHERE date=?", (hoy,)).fetchall()}
        grupos = adefs.get_active_grouped()
        vistos, ops = set(), []
        for sess in ('morning', 'afternoon', 'night', 'any', 'ocasional'):
            for it in grupos.get(sess, []):
                k = it['key']
                if k in vistos or k in hechas or (k + '__min') in hechas:
                    continue
                vistos.add(k)
                ops.append({'value': k, 'label': it['label'], 'ancla': it.get('effective_type') == 'ancla'})
        ops.sort(key=lambda o: not o['ancla'])
        out['key'] = {'options': ops[:12], 'default': ops[0]['value'] if ops else None}
    elif qid == 'baile':
        mins = [r['min'] for r in db.execute("SELECT min FROM eury_sessions ORDER BY date DESC, id DESC LIMIT 10").fetchall()]
        habitual = max(set(mins), key=mins.count) if mins else 30
        base = sorted({20, 30, 45, 60, int(habitual)})
        out['min'] = {'options': [{'value': m, 'label': f'{m}′'} for m in base], 'default': int(habitual)}
    elif qid == 'km':
        v = db.execute("SELECT km_actual, nombre FROM harma_vehiculo ORDER BY id LIMIT 1").fetchone()
        out['km'] = {'default': None, 'actual': v['km_actual'] if v else None, 'vehiculo': v['nombre'] if v else None}
    elif qid == 'peso':
        r = db.execute("SELECT value FROM body_measurements WHERE key='peso'").fetchone()
        try:
            actual = float(str(r['value']).replace(',', '.')) if r else None
        except ValueError:
            actual = None                       # el marcador «— editar —» de Perfil no es una lectura
        out['kg'] = {'default': None, 'actual': actual}
    return out


@quick_bp.route('/api/quick/options')
def options():
    qid = request.args.get('id', '')
    q = nav._QUICK_BY_ID.get(qid)
    if not q or (q.get('perm') and not session.get(q['perm'])):
        return jsonify({'error': 'not found'}), 404
    with get_db() as db:
        dyn = _opciones(db, qid)
    campos = {}
    for f in q.get('fields', []):
        c = {'default': f.get('default')}
        if f.get('options'):
            c['options'] = f['options']
        c.update(dyn.get(f['name'], {}))
        campos[f['name']] = c
    return jsonify({'id': qid, 'fields': campos})


def badges(db):
    """Anclas de hoy que faltan (Acta) y tareas vencidas (Praxis)."""
    import modules.actividades.activity_defs as adefs
    hoy = today_str()
    hechas = {r['activity_key'] for r in db.execute(
        "SELECT activity_key FROM activity_logs WHERE date=?", (hoy,)).fetchall()}
    anclas = {it['key'] for sess, lst in adefs.get_active_grouped().items() if sess != 'ocasional'
              for it in lst if it.get('effective_type') == 'ancla'}
    faltan = sum(1 for k in anclas if k not in hechas and (k + '__min') not in hechas)
    vencidas = db.execute(
        """SELECT COUNT(*) c FROM gtd_tasks WHERE COALESCE(completado,0)=0
           AND COALESCE(fecha_limite,'')!='' AND fecha_limite < ?""", (hoy,)).fetchone()['c']
    return {'acta': faltan, 'praxis': vencidas}


@quick_bp.route('/api/quick/badges')
def api_badges():
    with get_db() as db:
        return jsonify(badges(db))


@quick_bp.route('/api/quick/uso', methods=['POST'])
def uso():
    d = request.get_json(silent=True) or {}
    qid = d.get('id')
    if qid not in nav._QUICK_BY_ID:
        return jsonify({'ok': False, 'error': 'registro desconocido'}), 400
    vals = {k: v for k, v in (d.get('values') or {}).items() if isinstance(v, (str, int, float)) and k in ('categoria', 'cuenta', 'como', 'cuando', 'flow', 'min')}
    with get_db() as db:
        n = int(_setting(db, _USES + qid, 0) or 0) + 1
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (_USES + qid, str(n)))
        if vals:
            db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (_LAST + qid, json.dumps(vals)))
        db.commit()
    return jsonify({'ok': True, 'usos': n})
