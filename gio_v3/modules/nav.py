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
         'icon': 'list-checks', 'url': '/gtd/', 'children': [
            {'id': 'praxis-puntos', 'label': 'Puntos y nivel', 'url': '/gtd/points'},
        ]},
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
            {'id': 'gastos-viaje', 'label': 'Gastos de viaje', 'url': '/finanzas/estados/viajes/', 'icon': 'plane'},
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
ACTIONS = [
    {'id': 'marcar', 'label': 'Marcar actividad', 'icon': 'check-circle-2', 'url': '/actividades/',
     'keywords': 'acta registrar habito xp'},
    {'id': 'gasto', 'label': 'Registrar gasto', 'icon': 'plus', 'url': '/finanzas/estados/',
     'keywords': 'movimiento gasto oikonomia finanzas'},
    {'id': 'estado', 'label': 'Subir estado de cuenta', 'icon': 'upload', 'url': '/finanzas/estados/',
     'keywords': 'pdf banco bbva hsbc invex importar'},
    {'id': 'tarea', 'label': 'Nueva tarea', 'icon': 'list-plus', 'url': '/gtd/',
     'keywords': 'praxis gtd inbox'},
    {'id': 'prenda', 'label': 'Nueva prenda', 'icon': 'shirt', 'url': '/guardarropa/?nueva=1',
     'keywords': 'ropa guardarropa'},
    # Los recordatorios son una sección de Perfil (no una página propia), así
    # que el ⌘K no los encontraba; /perfil/#recordatorios abre esa sección.
    {'id': 'recordatorios', 'label': 'Recordatorios', 'icon': 'bell', 'url': '/perfil/#recordatorios',
     'keywords': 'recordatorio nuevo pendiente aviso alarma vencido perfil'},
]

# Bottom nav (móvil): 5 destinos. 'modulos' no navega, abre el sheet.
BOTTOM_NAV = [
    {'id': 'inicio', 'label': 'Inicio', 'icon': 'house', 'url': '/'},
    {'id': 'acta', 'label': 'Acta', 'icon': 'scroll-text', 'url': '/actividades/'},
    {'id': 'praxis', 'label': 'Praxis', 'icon': 'list-checks', 'url': '/gtd/'},
    {'id': 'modulos', 'label': 'Módulos', 'icon': 'layout-grid', 'url': None},
    {'id': 'tu', 'label': 'Tú', 'icon': 'user-round', 'url': '/perfil/'},
]
_BOTTOM_DIRECT = {'inicio', 'acta', 'praxis'}
_TU_GROUP = 'Tú'

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


def nav_context():
    """Variables de navegación para layout_sub.html (context processor)."""
    try:
        path = request.path
    except RuntimeError:  # fuera de un request (p. ej. render en tests sin contexto)
        path = '/'
    group, item, child = resolve(path)

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

    if item and item['id'] in _BOTTOM_DIRECT:
        bottom_active = item['id']
    elif group and group['group'] == _TU_GROUP:
        bottom_active = 'tu'
    elif item:
        bottom_active = 'modulos'
    else:
        bottom_active = None

    # Sheet de Módulos: todo lo que no tiene pestaña propia en la bottom nav.
    sheet = [it for g in NAV for it in g['items']
             if it['id'] not in _BOTTOM_DIRECT and it['id'] != 'perfil']

    return {
        'NAV': NAV,
        'NAV_ACTIONS': ACTIONS,
        'NAV_BOTTOM': BOTTOM_NAV,
        'nav_here': here,
        'nav_crumbs': crumbs,
        'nav_title': title,
        'nav_sub': sub,
        'nav_back': back,
        'nav_bottom_active': bottom_active,
        'nav_sheet': sheet,
        'nav_sb_max': SIDEBAR_MAX_CHILDREN,
        'nav_cmdk': {'pages': _CMDK_PAGES, 'actions': _CMDK_ACTIONS},
        'XP_DAILY_GOAL': XP_DAILY_GOAL,
    }
