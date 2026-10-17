"""
stylist.py — motor determinista del Coach de imagen (Guardarropa).

Antes, el generador mandaba a la IA el inventario crudo (nombre + hex) y le
pedía "el outfit perfecto". El resultado eran consejos burdos: la IA no sabe
leer un hex, no sabía qué prenda cumple qué función en el look (una sudadera
y una camisa eran lo mismo), ignoraba el nivel de formalidad y a veces
devolvía dos pantalones o ningún calzado.

Este módulo hace el trabajo que una persona estilista hace antes de pensar:
  1. Clasifica cada prenda por su función en el look (`slot_of`).
  2. Le asigna un nivel de formalidad 1–5 (`formality_of`).
  3. Traduce el hex a un color legible: familia, claridad, saturación,
     neutro o acento (`color_profile`).
  4. Puntúa la compatibilidad de cada candidata con la prenda ancla y con la
     ocasión (`score_candidate`) y arma una shortlist por función.
  5. Valida y completa lo que devuelve la IA (`sanitize_proposal`): IDs
     inexistentes fuera, una sola prenda por función, faltantes rellenados.

Todo es puro (sin DB ni red) para poder testearlo directo.
"""
import colorsys
import re
import unicodedata
from datetime import date

# ── Funciones de cada prenda en el look ──────────────────────────────────────

SLOTS = ('traje', 'superior', 'capa_media', 'capa_ext', 'inferior',
         'calzado', 'calcetas', 'accesorio', 'otro')

SLOT_LABEL = {
    'traje': 'Traje', 'superior': 'Prenda superior', 'capa_media': 'Capa media',
    'capa_ext': 'Capa exterior', 'inferior': 'Prenda inferior', 'calzado': 'Calzado',
    'calcetas': 'Calcetas', 'accesorio': 'Accesorio', 'otro': 'Otro',
}

# Orden importa: lo más específico primero ("pantalón de traje" es traje
# solo si la categoría lo dice; en el nombre manda la palabra de prenda).
_SLOT_KEYWORDS = [
    ('traje',      ('traje', 'conjunto', 'suit')),
    ('calcetas',   ('calceta', 'calcetin', 'sock')),
    ('calzado',    ('zapato', 'sneaker', 'tenis', 'bota', 'sandalia', 'mocasin',
                    'loafer', 'calzado', 'derby', 'chelsea', 'botin',
                    'alpargata', 'espadrille')),
    ('capa_ext',   ('blazer', 'saco', 'chamarra', 'abrigo', 'chaqueta', 'jacket',
                    'gabardina', 'parka', 'cazadora', 'trench', 'overshirt',
                    'sobrecamisa', 'veste', 'bomber', 'chaleco')),
    ('capa_media', ('sudadera', 'sueter', 'cardigan', 'hoodie', 'jersey', 'pullover',
                    'crewneck', 'quarter zip', 'medio cierre')),
    ('inferior',   ('pantalon', 'jean', 'pants', 'short', 'bermuda', 'chino',
                    'jogger', 'trouser', 'mezclilla')),
    ('superior',   ('camisa', 'camiseta', 'polo', 'playera', 't-shirt', 'tshirt',
                    'henley', 'guayabera')),
    ('accesorio',  ('accesorio', 'cinturon', 'reloj', 'gorra', 'sombrero', 'bufanda',
                    'corbata', 'panuelo', 'lentes', 'gafas', 'pulsera', 'collar',
                    'mochila', 'cartera', 'bolsa', 'gorro', 'belt', 'watch')),
]


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '').lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def _match(text, kws):
    return any(re.search(r'(?<![a-z])' + re.escape(k), text) for k in kws)


def slot_of(item):
    """Función de la prenda en el look. La categoría manda; si es ambigua
    (categorías legacy o libres), se usa subcategoría y luego el nombre."""
    for field in ('categoria', 'subcategoria', 'nombre'):
        text = _norm(item.get(field))
        if not text:
            continue
        for slot, kws in _SLOT_KEYWORDS:
            if _match(text, kws):
                return slot
    return 'otro'


# ── Formalidad 1 (deportivo/lounge) … 5 (formal) ─────────────────────────────

# Primera coincidencia gana: lo deportivo y el denim van antes que la prenda
# genérica para que "Pantalón de mezclilla" no cuente como pantalón de vestir.
_FORMALITY_BY_CAT = [
    (('traje', 'conjunto'), 5),
    (('zapatos formales', 'derby', 'mocasin', 'loafer'), 5),
    (('sudadera', 'hoodie', 'short', 'bermuda', 'pants', 'jogger', 'sandalia'), 1),
    (('jean', 'mezclilla', 'denim'), 2),
    (('blazer', 'saco'), 4),
    (('camisa',), 4),
    (('pantalon', 'chino', 'trouser'), 4),
    (('abrigo', 'gabardina', 'trench'), 4),
    (('polo', 'sueter', 'cardigan', 'zapatos casuales', 'botas', 'bota', 'chelsea'), 3),
    (('chamarra', 'chaqueta', 'jacket', 'overshirt', 'sobrecamisa', 'veste', 'bomber'), 3),
    (('camiseta', 'playera', 'henley', 'sneaker', 'tenis'), 2),
]
_SPORT_WORDS = ('gym', 'running', 'deportiv', 'dry-fit', 'dryfit', 'training',
                'yoga', 'pijama', 'lounge', 'futbol', 'basket', 'jogger')


def formality_of(item):
    text = _norm(' '.join(str(item.get(k) or '') for k in ('categoria', 'subcategoria', 'nombre')))
    level = 3
    for kws, lvl in _FORMALITY_BY_CAT:
        if _match(text, kws):
            level = lvl
            break
    occ = _norm(item.get('ocasion'))
    if occ in ('deportivo', 'loungewear') or _match(text, _SPORT_WORDS):
        level = 1
    elif occ == 'formal':
        level = max(level, 4)
    elif occ == 'business':
        level = max(level, 3)
    return level


# Rango de formalidad aceptable por ocasión: (mín, ideal, máx).
_OCCASION_RANGE = {
    'formal':             (4, 5, 5),
    'reunion importante': (4, 4, 5),
    'business':           (3, 4, 5),
    'cita':               (2, 3, 4),
    'social':             (2, 3, 4),
    'casual':             (2, 2, 3),
    'fin de semana':      (1, 2, 3),
    'deportivo':          (1, 1, 2),
}


def occasion_range(occasion):
    return _OCCASION_RANGE.get(_norm(occasion).strip(), (2, 3, 4))


# ── Color: del hex a algo que se pueda razonar ───────────────────────────────

def _hex_to_rgb(hx):
    hx = str(hx or '').strip().lstrip('#')
    if len(hx) == 3:
        hx = ''.join(c * 2 for c in hx)
    if not re.fullmatch(r'[0-9a-fA-F]{6}', hx):
        return None
    return tuple(int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hue_family(h):
    deg = h * 360
    for limit, name in ((15, 'rojo'), (40, 'naranja'), (65, 'amarillo'), (90, 'lima'),
                        (165, 'verde'), (195, 'turquesa'), (255, 'azul'),
                        (290, 'morado'), (335, 'rosa'), (361, 'rojo')):
        if deg < limit:
            return name
    return 'rojo'


def color_profile(item):
    """{'familia','claridad','saturacion','neutro','hue','l','s','desc'}.
    Los neutros de la sastrería masculina (negro, blanco, grises, navy,
    marrones, beige/camel, oliva apagado, denim) se marcan como neutros:
    combinan con casi todo y son la base 70% del look."""
    rgb = _hex_to_rgb(item.get('color_hex'))
    name = (item.get('color_name') or '').strip()
    if not rgb:
        return {'familia': name or 'desconocido', 'claridad': 'media', 'saturacion': 'media',
                'neutro': True, 'hue': None, 'l': 0.5, 's': 0.0,
                'desc': (name or 'color sin registrar')}
    h, l, s = colorsys.rgb_to_hls(*rgb)
    deg = h * 360
    if s < 0.12 or l < 0.10 or l > 0.93:
        familia = 'negro' if l < 0.18 else 'blanco' if l > 0.88 else 'gris'
        neutro = True
    elif 200 <= deg <= 250 and l < 0.35:
        familia, neutro = 'azul marino', True
    elif 195 <= deg <= 230 and s < 0.45 and l < 0.6:
        familia, neutro = 'denim / azul grisáceo', True
    elif 15 <= deg <= 50 and l < 0.40:
        familia, neutro = 'marrón', True
    elif 25 <= deg <= 55 and l >= 0.40 and s < 0.55:
        familia, neutro = 'beige / camel', True
    elif 55 <= deg <= 100 and s < 0.40 and l < 0.55:
        familia, neutro = 'oliva', True
    else:
        familia, neutro = _hue_family(h), False
    claridad = 'oscuro' if l < 0.33 else 'claro' if l > 0.66 else 'medio'
    saturacion = 'apagado' if s < 0.35 else 'vivo' if s > 0.65 else 'medio'
    desc = name or familia
    extra = [claridad] + ([] if familia in ('negro', 'blanco') else [saturacion])
    desc = f"{desc} ({familia}, {', '.join(extra)}{', neutro' if neutro else ', acento'})" \
        if name and _norm(name) != _norm(familia) else \
        f"{familia} ({', '.join(extra)}{', neutro' if neutro else ', acento'})"
    return {'familia': familia, 'claridad': claridad, 'saturacion': saturacion,
            'neutro': neutro, 'hue': deg, 'l': l, 's': s, 'desc': desc}


def color_compat(a, b):
    """0–100: qué tan bien conviven dos colores en un mismo look."""
    if a['hue'] is None or b['hue'] is None:
        return 70
    contrast = abs(a['l'] - b['l'])
    if a['neutro'] and b['neutro']:
        # Dos neutros siempre funcionan; mejor si hay contraste de valor.
        return 80 + min(15, int(contrast * 40))
    if a['neutro'] or b['neutro']:
        return 78 + min(12, int(contrast * 30))
    diff = abs(a['hue'] - b['hue']) % 360
    diff = min(diff, 360 - diff)
    both_vivid = a['s'] > 0.65 and b['s'] > 0.65
    if diff < 25:                       # tono sobre tono / análogo cercano
        base = 72 if contrast > 0.15 else 58
    elif diff < 60:                     # análogo
        base = 66
    elif diff > 150:                    # complementario: solo si uno es apagado
        base = 40 if both_vivid else 64
    else:                               # triádico / choque
        base = 30 if both_vivid else 48
    return base + min(10, int(contrast * 25))


# ── Puntuación de candidatas ─────────────────────────────────────────────────

def _days_since(iso):
    try:
        return (date.today() - date.fromisoformat(str(iso)[:10])).days
    except Exception:
        return None


def enrich(item):
    it = dict(item)
    it['slot'] = slot_of(it)
    it['formalidad'] = formality_of(it)
    it['color'] = color_profile(it)
    return it


def score_candidate(cand, occasion, anchor=None):
    """0–100. Ponderación: ocasión 35, color con la ancla 30, formalidad con
    la ancla 20, estado 10, rotación 5 (prendas olvidadas suben un poco)."""
    lo, ideal, hi = occasion_range(occasion)
    f = cand['formalidad']
    if lo <= f <= hi:
        occ = 100 - abs(f - ideal) * 12
    else:
        occ = max(0, 60 - (min(abs(f - lo), abs(f - hi))) * 35)

    if anchor is not None:
        col = color_compat(anchor['color'], cand['color'])
        frm = max(0, 100 - abs(anchor['formalidad'] - f) * 30)
    else:
        col, frm = 75, 75

    est = {'nuevo': 100, 'bueno': 90, 'regular': 45}.get(_norm(cand.get('estado')), 70)
    days = _days_since(cand.get('ultimo_uso'))
    usos = cand.get('veces_usado') or 0
    if days is None:
        rot = 100 if usos == 0 else 60
    else:
        rot = min(100, days * 3)

    return round(occ * .35 + col * .30 + frm * .20 + est * .10 + rot * .05)


def required_slots(anchor_slot=None):
    """Funciones que un look completo necesita, descontando la que ya cubre la
    ancla. Un traje cubre inferior + capa exterior, pero aún pide camisa."""
    if anchor_slot == 'traje':
        return ['superior', 'calzado']
    need = ['superior', 'inferior', 'calzado']
    if anchor_slot in need:
        need.remove(anchor_slot)
    elif anchor_slot == 'capa_media':
        # Sudadera/suéter puede ir solo arriba, así que la camisa es opcional.
        need.remove('superior')
    return need


def build_shortlist(items, occasion, anchor=None, per_slot=7):
    """Agrupa candidatas por función, filtra las que no tienen sentido para la
    ocasión (prendas a donar, deportivas en un look formal) y deja las
    `per_slot` mejores de cada función. Devuelve {slot: [items ordenados]}."""
    lo, _, _ = occasion_range(occasion)
    out = {}
    for it in items:
        if anchor is not None and it['id'] == anchor['id']:
            continue
        if _norm(it.get('estado')) == 'donar':
            continue
        if lo >= 3 and it['formalidad'] <= 1:
            continue
        if anchor is not None and anchor['slot'] == 'traje' and it['slot'] in ('traje', 'inferior'):
            continue
        if anchor is not None and it['slot'] == anchor['slot'] and anchor['slot'] not in ('accesorio', 'otro'):
            continue  # la ancla ya ocupa esa función
        it = dict(it)
        it['score'] = score_candidate(it, occasion, anchor)
        out.setdefault(it['slot'], []).append(it)
    for slot in out:
        out[slot].sort(key=lambda x: -x['score'])
        out[slot] = out[slot][:per_slot]
    return out


def item_line(it, with_score=True):
    bits = [f"ID {it['id']}: {it.get('nombre') or 'sin nombre'}",
            f"{it.get('categoria') or ''}{(' · ' + it['subcategoria']) if it.get('subcategoria') else ''}",
            f"color: {it['color']['desc']}",
            f"formalidad {it['formalidad']}/5"]
    if it.get('marca'):
        bits.append(f"marca {it['marca']}")
    if it.get('temporada') and it['temporada'] != 'todo':
        bits.append(f"temporada {it['temporada']}")
    if _norm(it.get('estado')) == 'regular':
        bits.append('estado regular (desgaste visible)')
    days = _days_since(it.get('ultimo_uso'))
    if days is not None and days > 45:
        bits.append(f'sin usar hace {days} días')
    elif not it.get('veces_usado'):
        bits.append('nunca usada')
    if it.get('notas'):
        bits.append(f"nota: {str(it['notas'])[:80]}")
    if with_score and 'score' in it:
        bits.append(f"afinidad {it['score']}/100")
    return ' | '.join(bits)


# ── Validación de lo que devuelve la IA ──────────────────────────────────────

def _to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def sanitize_proposal(prop, by_id, shortlist, anchor=None):
    """Deja la propuesta en un estado coherente:
    - descarta IDs que no existen o que no estaban en la shortlist;
    - una sola prenda por función (hasta 2 accesorios);
    - si falta una función obligatoria, la completa con la mejor candidata
      y lo marca en `autocompletado` para que la UI lo diga;
    - la ancla siempre va primera."""
    allowed = {it['id'] for lst in shortlist.values() for it in lst}
    seen_slots, ids = {}, []
    if anchor is not None:
        seen_slots[anchor['slot']] = 1
    for raw in prop.get('item_ids') or []:
        iid = _to_int(raw)
        if iid is None or iid not in allowed or iid in ids:
            continue
        slot = by_id[iid]['slot']
        cap = 2 if slot == 'accesorio' else 1
        if seen_slots.get(slot, 0) >= cap:
            continue
        if slot == 'traje' and ('inferior' in seen_slots):
            continue
        if slot == 'inferior' and 'traje' in seen_slots:
            continue
        seen_slots[slot] = seen_slots.get(slot, 0) + 1
        ids.append(iid)

    auto = []
    anchor_slot = anchor['slot'] if anchor is not None else None
    if anchor is None and 'traje' in seen_slots:
        anchor_slot = 'traje'
    for slot in required_slots(anchor_slot):
        if slot in seen_slots:
            continue
        if slot == 'inferior' and 'traje' in seen_slots:
            continue
        best = next((c for c in shortlist.get(slot, []) if c['id'] not in ids), None)
        if best:
            ids.append(best['id'])
            seen_slots[slot] = 1
            auto.append(best['id'])

    if anchor is not None:
        ids = [anchor['id']] + [i for i in ids if i != anchor['id']]

    roles = {}
    for r in prop.get('roles') or []:
        if isinstance(r, dict):
            iid = _to_int(r.get('id'))
            if iid in ids and r.get('rol'):
                roles[str(iid)] = str(r['rol'])[:240]

    def _strs(key, n, ln=240):
        v = prop.get(key) or []
        if isinstance(v, str):
            v = [v]
        return [str(x)[:ln] for x in v if x][:n]

    faltante = prop.get('pieza_faltante')
    if not isinstance(faltante, dict) or not faltante.get('nombre'):
        faltante = None
    else:
        faltante = {'nombre': str(faltante['nombre'])[:120],
                    'por_que': str(faltante.get('por_que') or '')[:240],
                    'categoria': str(faltante.get('categoria') or '')[:60]}

    rating = _to_int(prop.get('rating')) or 4
    return {
        'nombre': str(prop.get('nombre') or 'Look')[:120],
        'enfoque': str(prop.get('enfoque') or '')[:60],
        'item_ids': ids,
        'roles': roles,
        'harmony': str(prop.get('paleta') or prop.get('harmony') or '')[:240],
        'why_works': str(prop.get('why_works') or '')[:600],
        'tips': _strs('styling', 5) or _strs('tips', 5),
        'evitar': str(prop.get('evitar') or '')[:240],
        'pieza_faltante': faltante,
        'rating': max(1, min(5, rating)),
        'autocompletado': auto,
    }
