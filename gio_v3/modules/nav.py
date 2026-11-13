"""
nav.py — Fuente única de la navegación (Design System V2).

NAV alimenta, desde un solo lugar, el sidebar (desktop), la bottom nav y el
sheet de Módulos (móvil), el breadcrumb / título de la topbar y ⌘K. Antes
cada superficie tenía su propia lista (dict _pm, sidebar en duro, SUBMODULES
en el JS de ⌘K) y se desincronizaban.

Cada ítem:
  id        identificador estable (lo usan bottom nav y sheet)
  label     nombre visible
  greek     nombre griego de acento (opcional; se muestra en cursiva)
  fn        función en español («Finanzas») — va junto al nombre griego
  cat       categoría para el tinte (data-cat → tokens.css); opcional
  icon      ícono Lucide
  url       ruta (NO cambia: las etiquetas son solo presentación)
  match     prefijos extra que también activan este ítem (opcional)
  children  subpáginas (se muestran en el sidebar solo dentro del módulo activo)

Se inyecta en todas las plantillas con el context processor de app.py.
"""
from flask import request

NAV = [
    {'group': 'Hoy', 'items': [
        {'id': 'inicio', 'label': 'Inicio', 'greek': 'Ἀρχή', 'fn': 'Dashboard',
         'icon': 'house', 'url': '/'},
        {'id': 'acta', 'label': 'Acta Diurna', 'fn': 'Registro diario',
         'icon': 'scroll-text', 'url': '/actividades/'},
        {'id': 'praxis', 'label': 'Praxis', 'fn': 'Tareas',
         'icon': 'list-checks', 'url': '/gtd/'},
        {'id': 'ataraxia', 'label': 'Ataraxia', 'fn': 'Rutina', 'cat': 'ataraxia',
         'icon': 'sun-dim', 'url': '/ataraxia/'},
    ]},
    {'group': 'Virtudes', 'items': [
        {'id': 'oikonomia', 'label': 'Oikonomia', 'fn': 'Finanzas', 'cat': 'oikonomia',
         'icon': 'landmark', 'url': '/finanzas/', 'children': [
            {'id': 'movimientos', 'label': 'Movimientos', 'url': '/finanzas/estados/', 'icon': 'receipt'},
            {'id': 'presupuesto', 'label': 'Presupuesto', 'url': '/finanzas/budget/', 'icon': 'pie-chart'},
            {'id': 'inversiones', 'label': 'Inversiones', 'url': '/finanzas/inversiones/', 'icon': 'trending-up'},
            {'id': 'patrimonio', 'label': 'Patrimonio', 'url': '/finanzas/salud/', 'icon': 'scale'},
            {'id': 'consumo', 'label': 'Consumo', 'url': '/finanzas/consumo/', 'icon': 'shopping-cart'},
            {'id': 'fin-wishlist', 'label': 'Wishlist', 'url': '/finanzas/prioridades/', 'icon': 'star'},
            # «Gastos de viaje» salió del menú tras Viajes v2 S4: un viaje, una página
            # (/viajes/); su desglose sigue en /finanzas/estados/viajes/?id=.
            {'id': 'coach', 'label': 'Coach financiero', 'url': '/finanzas/coach/', 'icon': 'sparkles'},
        ]},
        {'id': 'hegemonikon', 'label': 'Hegemonikon', 'fn': 'Salud', 'cat': 'hegemonikon',
         'icon': 'heart-pulse', 'url': '/bienestar/', 'children': [
            {'id': 'salud', 'label': 'Salud', 'url': '/bienestar/salud/', 'icon': 'stethoscope'},
            {'id': 'futbol', 'label': 'Fútbol', 'url': '/bienestar/futbol/', 'icon': 'trophy'},
            {'id': 'nutricion', 'label': 'Nutrición', 'greek': 'Díaita', 'url': '/nutricion/', 'icon': 'salad'},
            {'id': 'recetas', 'label': 'Recetas', 'url': '/recetas/', 'icon': 'chef-hat'},
        ]},
        {'id': 'paideia', 'label': 'Paideia', 'fn': 'Aprendizaje', 'cat': 'paideia',
         'icon': 'book-open', 'url': '/paideia/'},
        {'id': 'cosmopolitismo', 'label': 'Cosmopolitismo', 'fn': 'Idiomas', 'cat': 'cosmopolitismo',
         'icon': 'languages', 'url': '/idiomas/'},
        {'id': 'eurythmia', 'label': 'Eurythmia', 'fn': 'Baile', 'cat': 'eurythmia',
         'icon': 'music-2', 'url': '/eurythmia/'},
    ]},
    {'group': 'Vida', 'items': [
        {'id': 'guardarropa', 'label': 'Guardarropa', 'fn': 'Ropa', 'cat': 'identidad',
         'icon': 'shirt', 'url': '/guardarropa/', 'children': [
            {'id': 'ropa-wishlist', 'label': 'Wishlist', 'url': '/guardarropa/wishlist/', 'icon': 'shopping-bag'},
        ]},
        {'id': 'viajes', 'label': 'Viajes', 'fn': 'Itinerarios', 'cat': 'cosmopolitismo',
         'icon': 'plane', 'url': '/viajes/'},
        {'id': 'harma', 'label': 'Harma', 'fn': 'Vehículo', 'cat': 'harma',
         'icon': 'car', 'url': '/harma/'},
        {'id': 'plantas', 'label': 'Plantas', 'fn': 'Riego', 'cat': 'ataraxia',
         'icon': 'sprout', 'url': '/plantas/'},
    ]},
    {'group': 'Tú', 'items': [
        {'id': 'logros', 'label': 'Logros', 'fn': 'XP · Nivel', 'icon': 'trophy', 'url': '/logros'},
        {'id': 'recompensas', 'label': 'Recompensas', 'fn': 'Tienda EC', 'icon': 'gift', 'url': '/recompensas/'},
        {'id': 'perfil', 'label': 'Perfil', 'greek': 'Αὐτός', 'fn': 'Tus datos',
         'icon': 'user-round', 'url': '/perfil/'},
    ]},
]

# Acciones de ⌘K. Por ahora navegan a la pantalla donde se hace cada cosa;
# cuando esas pantallas acepten un parámetro para abrir su formulario
# directo (Fase 3), basta con cambiar la url aquí.
# Lo que es un registro (gasto, tarea, actividad…) vive en QUICK; aquí queda lo
# que no se captura en una frase.
ACTIONS = [
    {'id': 'estado', 'label': 'Subir estado de cuenta', 'icon': 'upload', 'url': '/finanzas/estados/',
     'keywords': 'pdf banco bbva hsbc invex importar'},
    {'id': 'prenda', 'label': 'Nueva prenda', 'icon': 'shirt', 'url': '/guardarropa/?nueva=1',
     'keywords': 'ropa guardarropa'},
    # Los recordatorios son una sección de Perfil (no una página propia), así
    # que el ⌘K no los encontraba; /perfil/#recordatorios abre esa sección.
    {'id': 'recordatorios', 'label': 'Recordatorios', 'icon': 'bell', 'url': '/perfil/#recordatorios',
     'keywords': 'recordatorio nuevo pendiente aviso alarma vencido perfil'},
]

# Captura rápida (handoff Captura, nota 5): una sola fuente para la hoja «+»
# del móvil y para ⌘K. Cada registro postea al endpoint que YA usa su módulo
# (no hay endpoints de escritura nuevos para los datos del módulo):
#   post      {method, url, body}: en body, "{campo}" toma el valor del campo y
#             "{today}", "{tomorrow}", "{hora}" se resuelven en el cliente.
#   id_from   llave de la respuesta con el id creado (para then/undo: "{id}").
#   then      pasos extra condicionados a un campo (mismo formato que post).
#   undo      cómo deshacer (solo si el módulo ya tiene borrado/undo).
#   fields    name, label, kind (money|number|text|chips), options (fijas) o
#             options_from (las da GET /api/quick/options), default, fallback.
#   perm      permiso de sesión requerido ('fin_ok'); sin él no se envía.
#   url       respaldo: la pantalla con el formulario completo (⌘↵ / sin post).
# Endpoints verificados en cada routes.py:
#   gasto       POST /finanzas/estados/api/transactions · DELETE …/<id>
#   comida      POST /nutricion/api/cumplir (+ /api/desliz) · POST /api/descumplir
#   tarea/nota  POST /gtd/api/task (+ /classify, /update) · DELETE /gtd/api/task/<id>
#   actividad   POST /actividades/api/activity/log · POST …/activity/undo/<log_id>
#   peso        POST /perfil/api/update_measurement (pide fin_ok, como en Perfil)
#   baile       POST /eurythmia/api/session
#   km          POST /harma/api/vehiculo (solo km_actual; el odómetro no baja)
#   medicamento Salud no tiene «marcar toma» todavía → solo url de respaldo.
QUICK = [
    {'id': 'gasto', 'label': 'Gasto', 'icon': 'wallet', 'cat': 'oikonomia', 'perm': 'fin_ok',
     'keywords': ['gasto', 'pague', 'pagué', 'compre', 'compré'],
     'url': '/finanzas/estados/',
     'fields': [
         {'name': 'monto', 'label': 'Monto', 'kind': 'money', 'placeholder': '0'},
         {'name': 'concepto', 'label': 'Concepto', 'kind': 'text', 'placeholder': 'Tacos, gasolina…', 'fallback': 'Gasto {hora}'},
         {'name': 'categoria', 'label': 'Categoría', 'kind': 'chips', 'options_from': 'categorias'},
         {'name': 'cuenta', 'label': 'Cuenta', 'kind': 'chips', 'options_from': 'cuentas'},
     ],
     'post': {'method': 'POST', 'url': '/finanzas/estados/api/transactions',
              'body': {'fecha': '{today}', 'descripcion': '{concepto}', 'monto': '{monto}',
                       'categoria': '{categoria}', 'banco': '{cuenta}', 'tipo': 'GASTO'}},
     'id_from': 'id',
     'undo': {'method': 'DELETE', 'url': '/finanzas/estados/api/transactions/{id}'}},
    {'id': 'comida', 'label': 'Comida', 'icon': 'salad', 'cat': 'hegemonikon', 'reward': '+XP',
     'keywords': ['comida', 'comi', 'comí', 'desayuno', 'cena', 'colacion', 'colación', 'snack'],
     'url': '/nutricion/',
     'fields': [
         {'name': 'meal', 'label': 'Cuál', 'kind': 'chips', 'options_from': 'comidas'},
         {'name': 'como', 'label': 'Cómo fue', 'kind': 'chips', 'default': 'limpia',
          'options': [{'value': 'limpia', 'label': 'Limpia'}, {'value': 'desliz', 'label': 'Con desliz'}]},
     ],
     'post': {'method': 'POST', 'url': '/nutricion/api/cumplir', 'body': {'meal_id': '{meal}'}},
     'then': [{'if': {'como': 'desliz'}, 'method': 'POST', 'url': '/nutricion/api/desliz',
               'body': {'trig_id': 'otro', 'note': 'Captura rápida'}}],
     'undo': {'method': 'POST', 'url': '/nutricion/api/descumplir', 'body': {'meal_id': '{meal}'}}},
    {'id': 'tarea', 'label': 'Tarea', 'icon': 'list-checks', 'cat': None,
     'keywords': ['tarea', 'pendiente', 'todo'],
     'url': '/gtd/',
     'fields': [
         {'name': 'texto', 'label': 'Qué', 'kind': 'text', 'placeholder': 'Llamar al banco'},
         {'name': 'cuando', 'label': 'Cuándo', 'kind': 'chips', 'default': 'inbox',
          'options': [{'value': 'hoy', 'label': 'Hoy'}, {'value': 'manana', 'label': 'Mañana'},
                      {'value': 'semana', 'label': 'Esta semana'}, {'value': 'inbox', 'label': 'Inbox'}]},
     ],
     'post': {'method': 'POST', 'url': '/gtd/api/task', 'body': {'texto': '{texto}', 'tipo': 'tarea'}},
     'id_from': 'id',
     'then': [{'if': {'cuando': 'hoy'}, 'method': 'POST', 'url': '/gtd/api/task/{id}/classify', 'body': {'importante': 1, 'urgente': 1}},
              {'if': {'cuando': 'semana'}, 'method': 'POST', 'url': '/gtd/api/task/{id}/classify', 'body': {'importante': 1, 'urgente': 0}},
              {'if': {'cuando': 'manana'}, 'method': 'POST', 'url': '/gtd/api/task/{id}/update', 'body': {'fecha_limite': '{tomorrow}'}}],
     'undo': {'method': 'DELETE', 'url': '/gtd/api/task/{id}'}},
    {'id': 'actividad', 'label': 'Actividad', 'icon': 'circle-check', 'cat': None, 'reward': '+XP',
     'keywords': ['hice', 'marcar', 'actividad'],
     'url': '/actividades/',
     'fields': [{'name': 'key', 'label': 'Cuál', 'kind': 'chips', 'options_from': 'actividades'}],
     'post': {'method': 'POST', 'url': '/actividades/api/activity/log', 'body': {'key': '{key}'}},
     'id_from': 'log_id',
     'undo': {'method': 'POST', 'url': '/actividades/api/activity/undo/{id}'}},
    {'id': 'peso', 'label': 'Peso', 'icon': 'scale', 'cat': 'hegemonikon', 'perm': 'fin_ok',
     'keywords': ['peso', 'kg', 'pesé', 'pese'],
     'url': '/perfil/?sec=medidas',
     'fields': [{'name': 'kg', 'label': 'Kg', 'kind': 'number', 'placeholder': '78.4', 'step': 'any'}],
     'post': {'method': 'POST', 'url': '/perfil/api/update_measurement', 'body': {'key': 'peso', 'value': '{kg}'}}},
    {'id': 'baile', 'label': 'Sesión de baile', 'icon': 'music-2', 'cat': 'eurythmia', 'reward': '+XP',
     'keywords': ['baile', 'salsa', 'bailé', 'baile'],
     'url': '/eurythmia/',
     'fields': [
         {'name': 'min', 'label': 'Minutos', 'kind': 'chips', 'options_from': 'minutos'},
         {'name': 'flow', 'label': 'Cómo se sintió', 'kind': 'chips', 'default': 3,
          'options': [{'value': 1, 'label': '1 · trabado'}, {'value': 2, 'label': '2'}, {'value': 3, 'label': '3 · fluido'},
                      {'value': 4, 'label': '4'}, {'value': 5, 'label': '5 · en la música'}]},
     ],
     'post': {'method': 'POST', 'url': '/eurythmia/api/session', 'body': {'min': '{min}', 'flow': '{flow}'}}},
    {'id': 'km', 'label': 'Kilometraje', 'icon': 'gauge', 'cat': 'harma',
     'keywords': ['km', 'odometro', 'odómetro', 'kilometraje'],
     'url': '/harma/',
     'fields': [{'name': 'km', 'label': 'Km', 'kind': 'number', 'placeholder': '84200'}],
     'post': {'method': 'POST', 'url': '/harma/api/vehiculo', 'body': {'km_actual': '{km}'}}},
    {'id': 'medicamento', 'label': 'Tomé medicina', 'icon': 'pill', 'cat': 'hegemonikon',
     'keywords': ['medicina', 'pastilla', 'tome', 'tomé', 'med'],
     'url': '/bienestar/salud/', 'fields': []},
    {'id': 'nota', 'label': 'Nota', 'icon': 'notebook-pen', 'cat': None,
     'keywords': ['nota', 'idea', 'apunte'],
     'url': '/gtd/',
     'fields': [{'name': 'texto', 'label': 'Texto', 'kind': 'text', 'placeholder': 'Algo que no quieres olvidar'}],
     'post': {'method': 'POST', 'url': '/gtd/api/task', 'body': {'texto': '{texto}', 'tipo': 'idea'}},
     'id_from': 'id',
     'undo': {'method': 'DELETE', 'url': '/gtd/api/task/{id}'}},
]
_QUICK_BY_ID = {q['id']: q for q in QUICK}


def quick_for(session_obj, uses=None):
    """Registros que el usuario puede usar (sin los que piden un permiso que no
    tiene), ordenados por uso (desc) y luego por el orden de QUICK."""
    ok = [q for q in QUICK if not q.get('perm') or (session_obj or {}).get(q['perm'])]
    uses = uses or {}
    orden = {q['id']: i for i, q in enumerate(QUICK)}
    return sorted(ok, key=lambda q: (-uses.get(q['id'], 0), orden[q['id']]))


# Bottom nav (móvil): Inicio · Acta · + · Praxis · Módulos (handoff Captura,
# notas 2–4). 'registrar' abre la hoja de captura rápida y 'modulos' el sheet;
# «Tú» salió de la barra: Perfil, Logros y Recompensas viven en Módulos y en
# el avatar. Acta y Praxis llevan contador (GET /api/quick/badges).
BOTTOM_NAV = [
    {'id': 'inicio', 'label': 'Inicio', 'icon': 'house', 'url': '/'},
    {'id': 'acta', 'label': 'Acta', 'icon': 'scroll-text', 'url': '/actividades/', 'badge': 'acta'},
    {'id': 'registrar', 'label': 'Registrar', 'icon': 'plus', 'url': None},
    {'id': 'praxis', 'label': 'Praxis', 'icon': 'list-checks', 'url': '/gtd/', 'badge': 'praxis'},
    {'id': 'modulos', 'label': 'Módulos', 'icon': 'layout-grid', 'url': None},
]
_BOTTOM_DIRECT = {'inicio', 'acta', 'praxis'}

# Vistas internas de una pantalla (?vista=… o ?tab=…): la barra las conoce y
# muestra «Módulo › Vista» con volver al módulo (handoff Navegación, nota 5).
# Clave = id del ítem o subpágina de NAV; '_param' cambia el parámetro leído.
# Una vista que no está aquí se ignora.
VIEWS = {
    'harma':          {'bitacora': 'Bitácora', 'papeles': 'Papeles'},
    'eurythmia':      {'bitacora': 'Bitácora', 'musica': 'Música', 'progreso': 'Progreso'},
    'cosmopolitismo': {'plan': 'Plan', 'tests': 'Tests', 'journal': 'Journal'},
    'nutricion':      {'semana': 'Semana', 'sintomas': 'Síntomas'},
    'logros':         {'_param': 'tab', 'historial': 'Historial'},
}

# Sidebar: subpáginas visibles antes de «Más…»
SIDEBAR_MAX_CHILDREN = 4

# Meta diaria de XP (la misma que muestra el hero de Acta Diurna).
XP_DAILY_GOAL = 15


def _norm(url):
    return url.rstrip('/') + '/'


def _matches(path, url):
    """path cae dentro de url (prefijo por segmentos). '/' solo es exacto."""
    if url == '/':
        return path == '/'
    return _norm(path).startswith(_norm(url))


def resolve(path):
    """(grupo, ítem, hijo|None) de la ruta actual — el prefijo más largo gana."""
    best, best_len = (None, None, None), -1
    for g in NAV:
        for it in g['items']:
            for u in [it['url']] + it.get('match', []):
                if _matches(path, u) and len(u) > best_len:
                    best, best_len = (g, it, None), len(u)
            for ch in it.get('children', []):
                for u in [ch['url']] + ch.get('match', []):
                    if _matches(path, u) and len(u) > best_len:
                        best, best_len = (g, it, ch), len(u)
    return best


def _cmdk_pages():
    """Lista plana para ⌘K: cada ítem y subpágina, con texto de búsqueda."""
    out = []
    for g in NAV:
        for it in g['items']:
            out.append({
                'label': it['label'], 'url': it['url'], 'icon': it['icon'],
                'hint': it.get('greek') or it.get('fn') or g['group'],
                'q': ' '.join(filter(None, [it['label'], it.get('greek'), it.get('fn'), g['group']])),
            })
            for ch in it.get('children', []):
                out.append({
                    'label': ch['label'], 'url': ch['url'], 'icon': ch.get('icon', it['icon']),
                    'hint': it['label'],
                    'q': ' '.join(filter(None, [ch['label'], ch.get('greek'), it['label'], it.get('fn')])),
                })
    return out


_CMDK_PAGES = _cmdk_pages()
_CMDK_ACTIONS = [{'label': a['label'], 'url': a['url'], 'icon': a['icon'],
                  'q': a['label'] + ' ' + a.get('keywords', '')} for a in ACTIONS]


def view_of(item, child, args):
    """Nombre de la vista activa según VIEWS (o None)."""
    node = child or item
    if not node:
        return None
    m = VIEWS.get(node['id'])
    if not m:
        return None
    v = (args or {}).get(m.get('_param', 'vista'))
    return m.get(v) if v and not v.startswith('_') else None


def page_info():
    """Título y tinte de la pantalla actual para ui.page_head (global de Jinja:
    las macros importadas sin contexto no ven nav_title)."""
    c = nav_context()
    it = c['nav_here']['item']
    return {'title': c['nav_title'], 'cat': it.get('cat') if it else None}


def _quick_ctx():
    """QUICK filtrado por permisos y ordenado por uso, para la hoja y ⌘K."""
    try:
        from flask import session
        from modules.quick import usos
        return quick_for(session, usos())
    except Exception:
        return quick_for({}, {})


def nav_context():
    """Variables de navegación para layout_sub.html (context processor)."""
    try:
        path, args = request.path, request.args
    except RuntimeError:  # fuera de un request (p. ej. render en tests sin contexto)
        path, args = '/', {}
    group, item, child = resolve(path)
    view = view_of(item, child, args)

    here = {'group': group, 'item': item, 'child': child}
    crumbs, title, sub, back = [], None, None, '/'
    if item:
        if child:
            crumbs = [{'label': group['group']},
                      {'label': item['label'], 'url': item['url']},
                      {'label': child['label'], 'current': True}]
            title = child['label']
            sub = item['label'] + (' · ' + item['fn'] if item.get('fn') else '')
            back = item['url']
        elif item['id'] == 'inicio':
            crumbs = [{'label': item['label'], 'current': True}]
            title, sub = item['label'], None
        else:
            crumbs = [{'label': group['group']},
                      {'label': item['label'], 'fn': item.get('fn'), 'current': True}]
            title = item['label']
            sub = item.get('fn')
            back = '/'
        if view:
            # La vista es una página más: el módulo (o subpágina) pasa a ser enlace.
            node = child or item
            crumbs = [({'label': c['label'], 'url': node['url']} if c.get('current') else c) for c in crumbs]
            crumbs.append({'label': view, 'current': True})
            sub = node['label']
            title = view
            back = node['url']

    if item and item['id'] in _BOTTOM_DIRECT:
        bottom_active = item['id']
    elif item:
        bottom_active = 'modulos'
    else:
        bottom_active = None

    # Sheet de Módulos: todo lo que no tiene pestaña propia en la bottom nav.
    sheet = [it for g in NAV for it in g['items'] if it['id'] not in _BOTTOM_DIRECT]

    return {
        'NAV': NAV,
        'NAV_ACTIONS': ACTIONS,
        'NAV_BOTTOM': BOTTOM_NAV,
        'nav_here': here,
        'nav_crumbs': crumbs,
        'nav_title': title,
        'nav_sub': sub,
        'nav_back': back,
        'nav_view': view,
        'nav_bottom_active': bottom_active,
        'nav_sheet': sheet,
        'nav_sb_max': SIDEBAR_MAX_CHILDREN,
        'nav_cmdk': {'pages': _CMDK_PAGES, 'actions': _CMDK_ACTIONS},
        'nav_quick': _quick_ctx(),
        'XP_DAILY_GOAL': XP_DAILY_GOAL,
    }
