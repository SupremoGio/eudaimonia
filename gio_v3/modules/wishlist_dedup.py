"""
Duplicados en las dos listas de deseos:
  - wishlist_items     → Wishlist de Guardarropa (/guardarropa/wishlist)
  - lista_prioridades  → Prioridades de Finanzas (/finanzas/prioridades)

Duplicado = mismo nombre normalizado (minúsculas, sin acentos ni espacios de
más): «Apple Watch» = «apple  watch ». Nombres distintos no se tocan
(«Apple Watch Ultra» ≠ «Apple Watch»).

Regla de fusión (la eligió el usuario): se queda el registro más completo
y, a igualdad, el más reciente. Los campos que el conservado tenga vacíos se
llenan con los de los otros (p. ej. el precio), una compra registrada en
cualquiera de ellos se conserva, y luego se borran los demás.
"""
import unicodedata

# tabla -> (campos que suman completitud, campos «comprado», valor de estado comprado)
TABLAS = {
    'wishlist_items': {
        'completos': ('precio_estimado', 'url', 'marca', 'descripcion', 'categoria', 'score',
                      'recomendacion', 'notas_decision', 'purchased_at'),
        'comprado': 'comprado',
        'etiqueta': 'Wishlist (Guardarropa)',
    },
    'lista_prioridades': {
        'completos': ('precio_estimado', 'precio_real', 'url', 'tienda', 'notas', 'categoria',
                      'mes_objetivo', 'protocolo_score', 'protocolo_rec', 'purchased_at'),
        'comprado': 'Comprado',
        'etiqueta': 'Prioridades (Finanzas)',
    },
}
# Nunca se copian de un duplicado al conservado
_NO_FUSIONAR = {'id', 'nombre', 'created_at', 'updated_at', 'estado', 'purchased_at'}


def normaliza(nombre: str) -> str:
    t = unicodedata.normalize('NFKD', (nombre or '').lower())
    return ' '.join(''.join(c for c in t if not unicodedata.combining(c)).split())


def _vacio(v) -> bool:
    return v is None or v == '' or v == 0


def completitud(row: dict, tabla: str) -> int:
    return sum(0 if _vacio(row.get(c)) else 1 for c in TABLAS[tabla]['completos'] if c in row)


def _conservar(rows: list[dict], tabla: str) -> dict:
    return max(rows, key=lambda r: (completitud(r, tabla), r.get('created_at') or '', r['id']))


def grupos(db, tabla: str) -> list[dict]:
    """Grupos de duplicados de una tabla, con el registro que se conservaría."""
    por_nombre = {}
    for r in db.execute(f"SELECT * FROM {tabla} ORDER BY id").fetchall():
        r = dict(r)
        k = normaliza(r['nombre'])
        if k:
            por_nombre.setdefault(k, []).append(r)
    out = []
    for k, rows in por_nombre.items():
        if len(rows) < 2:
            continue
        keep = _conservar(rows, tabla)
        out.append({
            'nombre': keep['nombre'], 'conservar_id': keep['id'],
            'items': [{'id': r['id'], 'nombre': r['nombre'], 'estado': r.get('estado'),
                       'precio_estimado': r.get('precio_estimado'), 'url': r.get('url') or '',
                       'created_at': r.get('created_at'), 'completitud': completitud(r, tabla)} for r in rows],
        })
    return sorted(out, key=lambda g: normaliza(g['nombre']))


def fusionar(db, tabla: str) -> dict:
    """Aplica la regla de fusión a todos los grupos. No hace commit."""
    cfg = TABLAS[tabla]
    borrados, fusionados = 0, []
    for g in grupos(db, tabla):
        rows = {r['id']: dict(r) for r in db.execute(
            f"SELECT * FROM {tabla} WHERE id IN ({','.join('?' * len(g['items']))})",
            [i['id'] for i in g['items']]).fetchall()}
        keep = rows[g['conservar_id']]
        otros = sorted((r for r in rows.values() if r['id'] != keep['id']),
                       key=lambda r: (completitud(r, tabla), r.get('created_at') or '', r['id']), reverse=True)
        cambios = {}
        for r in otros:
            for c, v in r.items():
                if c in _NO_FUSIONAR or c not in keep:
                    continue
                if _vacio(keep.get(c)) and _vacio(cambios.get(c)) and not _vacio(v):
                    cambios[c] = v
        # Una compra registrada en cualquier duplicado no se pierde
        if keep.get('estado') != cfg['comprado']:
            comprado = next((r for r in otros if r.get('estado') == cfg['comprado']), None)
            if comprado:
                cambios['estado'] = cfg['comprado']
                if comprado.get('purchased_at'):
                    cambios['purchased_at'] = comprado['purchased_at']
        if cambios:
            db.execute(f"UPDATE {tabla} SET {', '.join(c + '=?' for c in cambios)} WHERE id=?",
                       list(cambios.values()) + [keep['id']])
        db.execute(f"DELETE FROM {tabla} WHERE id IN ({','.join('?' * len(otros))})", [r['id'] for r in otros])
        borrados += len(otros)
        fusionados.append(keep['nombre'])
    return {'borrados': borrados, 'grupos': fusionados}


def existente(db, tabla: str, nombre: str, excluir_id: int | None = None) -> dict | None:
    """Para el aviso al crear: ¿ya hay un artículo con ese nombre?"""
    k = normaliza(nombre)
    if not k:
        return None
    for r in db.execute(f"SELECT id, nombre, estado FROM {tabla} ORDER BY id DESC").fetchall():
        if r['id'] != excluir_id and normaliza(r['nombre']) == k:
            return dict(r)
    return None
