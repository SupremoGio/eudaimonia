"""
onboarding.py — «Primeros pasos» (handoff Estados vacíos, Sprint 2).

Cinco pasos que alimentan lo diario. Cada uno se marca solo cuando existe su
dato (no por pulsar el botón), paga +10 XP la primera vez (app_settings
onb_pagado:<paso>, para no volver a pagarlo aunque el dato desaparezca) y
la tarjeta de Inicio desaparece cuando están los cinco.

  anclas      ≥ 3 actividades activas con effective_type='ancla'
  ingreso     ingreso recurrente del mes (o el capturado a mano)
  estado      al menos un movimiento importado de un estado de cuenta
  peso        una medida de peso en Perfil
  recompensa  una recompensa creada por ti (las de ejemplo no cuentan)

Settings: onb_oculto (la tarjeta se ocultó), onb_visto (alguna vez se vio
con pasos pendientes; sin esto, una cuenta completa nunca ve la tarjeta),
onb_listo (ya se mostró el «Listo» final una vez).

POST /api/onboarding/oculto  {oculto}
"""
from flask import Blueprint, jsonify, request

from database import get_db
from utils import today_date

onboarding_bp = Blueprint('onboarding', __name__)

XP_PASO = 10
_PAGADO = 'onb_pagado:'

# Recompensas que siembra init_db(): no cuentan como «tu primera recompensa».
RECOMPENSAS_SEMILLA = {'Ropa Nike', 'Libro técnico', 'Kindle', 'Salida / Experiencia', 'Apple Watch',
                       'Viaje', 'Cápsula Nespresso', "Carl's Jr"}

# (id, título, detalle, acción, url, registro QUICK opcional)
PASOS = [
    ('anclas', 'Elige tus anclas del día', '3–5 hábitos que Acta te pide cada día', 'Elegir', '/actividades/', None),
    ('ingreso', 'Tu ingreso mensual', 'Oikonomia calcula lo disponible con esto', 'Capturar', '/finanzas/budget/', None),
    ('estado', 'Sube un estado de cuenta', 'categoriza solo; puedes corregir después', 'Subir', '/finanzas/estados/', None),
    ('peso', 'Tu peso y medidas', 'Hegemonikon y la revisión semanal los usan', 'Registrar', '/perfil/?sec=medidas', 'peso'),
    ('recompensa', 'Tu primera recompensa', 'en qué vas a gastar tus EC', 'Crear', '/recompensas/', None),
]


def _setting(db, key):
    r = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return r['value'] if r else None


def _set(db, key, value):
    db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)))


def _hecho(db, pid):
    """¿Existe el dato del paso? Defensivo: si la consulta falla, no está hecho."""
    try:
        if pid == 'anclas':
            import modules.actividades.activity_defs as adefs
            return sum(1 for a in adefs.get_active_flat().values() if a.get('effective_type') == 'ancla') >= 3
        if pid == 'ingreso':
            from modules.finanzas.budget import _ingresos_mes
            hoy = today_date()
            mes = hoy.strftime('%Y-%m')
            y, m = (hoy.year, hoy.month + 1) if hoy.month < 12 else (hoy.year + 1, 1)
            return (_ingresos_mes(db, mes, f"{mes}-01", f"{y}-{m:02d}-01") or {}).get('base', 0) > 0
        if pid == 'estado':
            return db.execute("SELECT 1 FROM est_movimientos LIMIT 1").fetchone() is not None
        if pid == 'peso':
            r = db.execute("SELECT value FROM body_measurements WHERE key='peso'").fetchone()
            try:
                if r and float(str(r['value']).replace(',', '.')) > 0:
                    return True
            except ValueError:
                pass                              # el marcador «— editar —» de Perfil
            return db.execute("SELECT 1 FROM body_measurements_history WHERE key='peso' LIMIT 1").fetchone() is not None
        if pid == 'recompensa':
            return any(r['name'] not in RECOMPENSAS_SEMILLA for r in db.execute("SELECT name FROM rewards").fetchall())
    except Exception as e:
        print(f'[onboarding] {pid}: {e}')
    return False


def pasos(db):
    """Los 5 pasos con {id, titulo, detalle, accion, url, quick, hecho, pagado}."""
    out = []
    for pid, titulo, detalle, accion, url, quick in PASOS:
        out.append({'id': pid, 'titulo': titulo, 'detalle': detalle, 'accion': accion, 'url': url, 'quick': quick,
                    'hecho': _hecho(db, pid), 'pagado': _setting(db, _PAGADO + pid) == '1'})
    return out


def pagar(db, lista):
    """+10 XP la primera vez que cada paso queda hecho. Devuelve los ids
    recién pagados. Nunca se descuenta: borrar el dato no quita lo pagado."""
    nuevos = [p for p in lista if p['hecho'] and not p['pagado']]
    if not nuevos:
        return []
    for p in nuevos:
        _set(db, _PAGADO + p['id'], 1)
        p['pagado'] = True
    db.commit()
    import modules.gamification.engine as engine
    for p in nuevos:
        engine._award_xp(XP_PASO, 'onboarding', f"Primeros pasos: {p['titulo']}")
    return [p['id'] for p in nuevos]


def estado(db, pagar_nuevos=True, inicio=True):
    """Lo que necesita la tarjeta de Inicio y la sección de Perfil. Solo
    Inicio (inicio=True) registra que la tarjeta se vio y consume el «Listo»."""
    lista = pasos(db)
    nuevos = pagar(db, lista) if pagar_nuevos else []
    n = sum(1 for p in lista if p['hecho'])
    total = len(lista)
    siguiente = next((p for p in lista if not p['hecho']), None)
    for p in lista:
        p['siguiente'] = siguiente is not None and p['id'] == siguiente['id']
    oculto = _setting(db, 'onb_oculto') == '1'
    visto = _setting(db, 'onb_visto') == '1'
    listo_visto = _setting(db, 'onb_listo') == '1'
    if n < total:
        modo = 'oculta' if oculto else 'abierta'
        if inicio and not visto and not oculto:
            _set(db, 'onb_visto', 1)
            db.commit()
    elif visto and not listo_visto:
        modo = 'listo'                    # se muestra una sola vez (en Inicio)
        if inicio:
            _set(db, 'onb_listo', 1)
            db.commit()
    else:
        modo = None                       # completa: nunca (o ya no) se muestra
    return {'pasos': lista, 'n': n, 'total': total, 'pct': round(n / total * 100),
            'siguiente': siguiente, 'modo': modo, 'nuevos': nuevos, 'xp': XP_PASO}


@onboarding_bp.route('/api/onboarding/oculto', methods=['POST'])
def api_oculto():
    oculto = bool((request.get_json(silent=True) or {}).get('oculto'))
    with get_db() as db:
        _set(db, 'onb_oculto', 1 if oculto else 0)
        db.commit()
    return jsonify({'ok': True, 'oculto': oculto})
