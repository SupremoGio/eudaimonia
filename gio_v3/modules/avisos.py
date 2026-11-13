"""
avisos.py — Avisos, un solo centro (handoff Avisos).

Cada módulo expone `avisos(db, hoy)` y devuelve una lista de avisos con la
forma común (ver `aviso()`); este módulo solo los junta. La lógica de cada
aviso sigue viviendo en su módulo y los avisos internos de cada página se
quedan donde están: el centro se suma a ellos.

Forma común:
    {clave, modulo, icono, titulo, detalle, fecha, nivel: 'hoy'|'semana'|'logro',
     accion: {label, url, method?, body?, deshacer?: {method, url, body?}},
     perm?: 'fin_ok'}
  · `clave` es estable entre recargas (p. ej. «oik:pago:bbva:2026-11»), para
    que posponer y descartar sobrevivan; cambia solo cuando el aviso es otro.
  · `accion` con `method` se resuelve en el panel (fetch + toast); sin
    `method`, navega a `url`. `deshacer` es el endpoint inverso, si existe.

Estado por clave en `avisos_estado` (pospuesto_hasta, descartado). Las
preferencias (Sprint 3) van en app_settings como `avisos_off:<fuente>`.

GET  /api/avisos                        {hoy, semana, logro, conteo_hoy, total}
POST /api/avisos/<clave>/posponer       {dias?, nivel?} (1 día en hoy, 3 en semana)
POST /api/avisos/<clave>/descartar
POST /api/avisos/<clave>/restaurar      deshace posponer/descartar
POST /api/avisos/logros/vistos          {claves?} marca notified=1
POST /api/avisos/preferencias           {fuente, activa} (Sprint 3)

`recolectar()` se cachea por petición (request.environ): la insignia de la
campana, el panel e Inicio comparten una sola pasada por las fuentes.
"""
import hashlib
import importlib
import re
import sys
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request, session, has_request_context
from database import get_db
from utils import today_date

avisos_bp = Blueprint('avisos', __name__)

NIVELES = ('hoy', 'semana', 'logro')
POSPONER_DIAS = {'hoy': 1, 'semana': 3, 'logro': 3}
_OFF = 'avisos_off:'
_CLAVE_RE = re.compile(r'^[a-z]{2,12}:[A-Za-z0-9_:.\-]{1,180}$')
_MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

# Fuentes: (id de preferencia, nombre visible, módulo con avisos(db, hoy), permiso).
# Una fuente con permiso ni se consulta si la sesión no lo tiene.
FUENTES = [
    ('oikonomia', 'Oikonomia', 'modules.finanzas.routes', 'fin_ok'),
    ('salud', 'Salud', 'modules.bienestar.salud', None),
    ('perfil', 'Recordatorios', 'modules.perfil.recordatorios', None),
    ('harma', 'Harma', 'modules.harma.routes', None),
    ('praxis', 'Praxis', 'modules.gtd.routes', None),
    ('plantas', 'Plantas', 'modules.plantas.routes', None),
    ('futbol', 'Fútbol', 'modules.bienestar.futbol', None),
    ('acta', 'Acta Diurna', 'modules.actividades.routes', None),
    ('logros', 'Logros', 'modules.gamification.routes', None),
]


# ── Forma común y ayudas de texto (las usan los adaptadores) ─────────────────

def aviso(clave, modulo, icono, titulo, detalle='', fecha=None, nivel='semana', accion=None, perm=None):
    if nivel not in NIVELES:
        raise ValueError(f'nivel inválido: {nivel}')
    a = {'clave': clave, 'modulo': modulo, 'icono': icono, 'titulo': titulo,
         'detalle': detalle or '', 'fecha': fecha.isoformat() if isinstance(fecha, date) else fecha,
         'nivel': nivel, 'accion': accion or None}
    if perm:
        a['perm'] = perm
    return a


def slug(txt):
    """Parte de clave estable a partir de texto libre (títulos)."""
    s = re.sub(r'[^a-z0-9]+', '-', (txt or '').strip().lower()).strip('-')
    return s[:40] or hashlib.md5((txt or '').encode()).hexdigest()[:8]


def huella(partes):
    """Clave corta de un conjunto (cambia si el conjunto cambia)."""
    return hashlib.md5('|'.join(sorted(str(p) for p in partes)).encode()).hexdigest()[:10]


def fecha_corta(d):
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f'{d.day} {_MESES[d.month - 1]}'


def relativo(dias):
    """«vence hoy», «mañana», «en 3 d», «hace 2 d»."""
    if dias == 0:
        return 'hoy'
    if dias == 1:
        return 'mañana'
    if dias == -1:
        return 'ayer'
    return f'hace {-dias} d' if dias < 0 else f'en {dias} d'


# ── Estado y preferencias ─────────────────────────────────────────────────────

def _setting(db, key):
    r = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return r['value'] if r else None


def fuentes_apagadas(db):
    n = len(_OFF)
    return {r['key'][n:] for r in db.execute(
        "SELECT key, value FROM app_settings WHERE substr(key,1,?)=?", (n, _OFF)).fetchall()
        if str(r['value']) == '1'}


def set_fuente(db, fuente, activa):
    if fuente not in {f[0] for f in FUENTES}:
        raise ValueError('fuente desconocida')
    if activa:
        db.execute("DELETE FROM app_settings WHERE key=?", (_OFF + fuente,))
    else:
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, '1')", (_OFF + fuente,))
    _invalidar()


_DESC = {
    'oikonomia': 'Pagos de tarjeta, presupuestos, MSI y estados por subir',
    'salud': 'Medicamentos que terminan y recurrencias',
    'perfil': 'Recordatorios vencidos o de esta semana',
    'harma': 'Plan de mantenimiento y papeles del vehículo',
    'praxis': 'Tareas con fecha límite vencida',
    'acta': 'Anclas sin registrar después de las 20:00',
    'plantas': 'Riegos y cuidados que tocan hoy',
    'futbol': 'Partido de hoy y resultados pendientes',
}


def preferencias(db, sess):
    """Interruptores de /perfil/?sec=avisos: una fila por fuente visible con
    los permisos de la sesión. Logros va aparte («Mostrar logros…»)."""
    off = fuentes_apagadas(db)
    return [{'id': fid, 'nombre': nombre, 'desc': _DESC.get(fid, ''), 'activa': fid not in off}
            for fid, nombre, _r, perm in FUENTES if not (perm and not sess.get(perm))]


def _estados(db, claves):
    if not claves:
        return {}
    out = {}
    claves = list(claves)
    for i in range(0, len(claves), 400):
        trozo = claves[i:i + 400]
        for r in db.execute(f"SELECT * FROM avisos_estado WHERE clave IN ({','.join('?' * len(trozo))})", trozo):
            out[r['clave']] = dict(r)
    return out


def _oculto(est, hoy):
    if not est:
        return False
    if est.get('descartado'):
        return True
    return bool(est.get('pospuesto_hasta') and est['pospuesto_hasta'] > hoy.isoformat())


# ── Recolección ───────────────────────────────────────────────────────────────

def _cargar(ruta):
    mod = importlib.import_module(ruta)
    fn = getattr(mod, 'avisos', None)
    if not callable(fn):
        raise AttributeError(f'{ruta} no expone avisos(db, hoy)')
    return fn


_CACHE = 'eu.avisos'


def _invalidar():
    if has_request_context():
        request.environ.pop(_CACHE, None)


def recolectar(db, hoy=None, sess=None, fuentes=None):
    """Junta los avisos de todas las fuentes activas. Un adaptador que falla
    se salta (queda en `errores`) sin tumbar al resto. Filtra por permisos,
    quita lo descartado y lo pospuesto vigente y ordena por nivel y fecha.
    Se cachea por petición: la insignia de la topbar y el panel comparten
    la misma llamada."""
    hoy = hoy or today_date()
    usar_cache = sess is None and fuentes is None and has_request_context()
    sess = session if usar_cache else (sess or {})
    if usar_cache:
        c = request.environ.get(_CACHE)
        if c and c['hoy'] == hoy and c['fin_ok'] == bool(sess.get('fin_ok')):
            return c['res']

    apagadas = fuentes_apagadas(db)
    todos, errores = [], []
    for fid, _nombre, ruta, perm in (fuentes or FUENTES):
        if fid in apagadas or (perm and not sess.get(perm)):
            continue
        try:
            fn = _cargar(ruta) if isinstance(ruta, str) else ruta
            for a in fn(db, hoy) or []:
                a = dict(a)
                a.setdefault('fuente', fid)
                todos.append(a)
        except Exception as e:                       # un módulo roto no tumba el centro
            errores.append(fid)
            print(f'[avisos] {fid}: {type(e).__name__}: {e}', file=sys.stderr)

    todos = [a for a in todos if a.get('nivel') in NIVELES and a.get('clave')
             and not (a.get('perm') and not sess.get(a['perm']))]
    vistos, unicos = set(), []
    for a in todos:                                  # una clave, un aviso
        if a['clave'] not in vistos:
            vistos.add(a['clave'])
            unicos.append(a)
    est = _estados(db, vistos)
    vivos = [a for a in unicos if not _oculto(est.get(a['clave']), hoy)]
    vivos.sort(key=lambda a: (NIVELES.index(a['nivel']), a.get('fecha') or '9999-12-31', a['titulo']))

    res = {n: [a for a in vivos if a['nivel'] == n] for n in NIVELES}
    res['conteo_hoy'] = len(res['hoy'])
    res['total'] = len(vivos)
    res['errores'] = errores
    if usar_cache:
        request.environ[_CACHE] = {'hoy': hoy, 'fin_ok': bool(sess.get('fin_ok')), 'res': res}
    return res


def conteo_hoy():
    """Para la insignia de la campana (nav_context). 0 si algo falla."""
    try:
        if not session.get('app_ok'):
            return 0
        with get_db() as db:
            return recolectar(db)['conteo_hoy']
    except Exception:
        return 0


# ── Endpoints ─────────────────────────────────────────────────────────────────

@avisos_bp.route('/api/avisos')
def api_avisos():
    with get_db() as db:
        return jsonify(recolectar(db))


def _guardar(db, clave, pospuesto_hasta=None, descartado=0):
    db.execute("""INSERT INTO avisos_estado (clave, pospuesto_hasta, descartado, actualizado) VALUES (?,?,?,?)
                  ON CONFLICT(clave) DO UPDATE SET pospuesto_hasta=excluded.pospuesto_hasta,
                  descartado=excluded.descartado, actualizado=excluded.actualizado""",
               (clave, pospuesto_hasta, descartado, datetime.now().isoformat(timespec='seconds')))
    db.commit()
    _invalidar()


def _clave_ok(clave):
    return bool(_CLAVE_RE.match(clave or ''))


@avisos_bp.route('/api/avisos/<path:clave>/posponer', methods=['POST'])
def api_posponer(clave):
    if not _clave_ok(clave):
        return jsonify({'ok': False, 'error': 'clave inválida'}), 400
    d = request.get_json(silent=True) or {}
    try:
        dias = int(d.get('dias') or POSPONER_DIAS.get(d.get('nivel'), 1))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'días inválidos'}), 400
    dias = max(1, min(dias, 365))
    hasta = (today_date() + timedelta(days=dias)).isoformat()
    with get_db() as db:
        _guardar(db, clave, pospuesto_hasta=hasta)
        conteo = recolectar(db)['conteo_hoy']
    return jsonify({'ok': True, 'hasta': hasta, 'conteo_hoy': conteo})


@avisos_bp.route('/api/avisos/<path:clave>/descartar', methods=['POST'])
def api_descartar(clave):
    if not _clave_ok(clave):
        return jsonify({'ok': False, 'error': 'clave inválida'}), 400
    with get_db() as db:
        _guardar(db, clave, descartado=1)
        conteo = recolectar(db)['conteo_hoy']
    return jsonify({'ok': True, 'conteo_hoy': conteo})


@avisos_bp.route('/api/avisos/<path:clave>/restaurar', methods=['POST'])
def api_restaurar(clave):
    if not _clave_ok(clave):
        return jsonify({'ok': False, 'error': 'clave inválida'}), 400
    with get_db() as db:
        db.execute("DELETE FROM avisos_estado WHERE clave=?", (clave,))
        db.commit()
        _invalidar()
        conteo = recolectar(db)['conteo_hoy']
    return jsonify({'ok': True, 'conteo_hoy': conteo})


@avisos_bp.route('/api/avisos/logros/vistos', methods=['POST'])
def api_logros_vistos():
    from modules.gamification.routes import marcar_vistos
    d = request.get_json(silent=True) or {}
    claves = d.get('claves')
    with get_db() as db:
        if not isinstance(claves, list):
            claves = [a['clave'] for a in recolectar(db)['logro']]
        n = marcar_vistos(db, [c for c in claves if isinstance(c, str)])
        db.commit()
    return jsonify({'ok': True, 'marcados': n})


@avisos_bp.route('/api/avisos/preferencias', methods=['POST'])
def api_preferencias():
    """{fuente, activa} — un interruptor por fuente (Sprint 3)."""
    d = request.get_json(silent=True) or {}
    try:
        with get_db() as db:
            set_fuente(db, d.get('fuente'), bool(d.get('activa')))
            db.commit()
            conteo = recolectar(db)['conteo_hoy']
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    return jsonify({'ok': True, 'conteo_hoy': conteo})
