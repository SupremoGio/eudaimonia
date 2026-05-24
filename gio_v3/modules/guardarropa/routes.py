import os, uuid, urllib.request, json, ipaddress, logging
from datetime import datetime
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from database import get_db
from utils import clean_str, safe_float

_log = logging.getLogger(__name__)

guardarropa_bp = Blueprint('guardarropa', __name__, template_folder='../../templates')

UPLOAD_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'wardrobe')
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
os.makedirs(UPLOAD_DIR, exist_ok=True)

CATEGORIAS = [
    'Camisa', 'Camiseta', 'Polo', 'Sudadera', 'Suéter',
    'Pantalón', 'Jeans', 'Pants', 'Short', 'Traje / Conjunto',
    'Blazer / Saco', 'Chamarra / Abrigo',
    'Zapatos formales', 'Zapatos casuales', 'Sneakers', 'Botas', 'Sandalias',
    'Calcetas',
    'Accesorio',
]
OCASIONES  = ['Formal', 'Business', 'Casual', 'Social', 'Deportivo', 'Loungewear']
TEMPORADAS = ['todo', 'verano', 'invierno', 'entretiempo']
ESTADOS    = ['nuevo', 'bueno', 'regular', 'donar']


def _row(r):
    return dict(r)


# ── Pages ─────────────────────────────────────────────────────────────────────

@guardarropa_bp.route('/')
def index():
    with get_db() as db:
        items = [_row(r) for r in db.execute(
            "SELECT * FROM wardrobe_items WHERE activo=1 ORDER BY created_at DESC"
        ).fetchall()]
        outfits_raw = db.execute(
            "SELECT * FROM outfits ORDER BY created_at DESC"
        ).fetchall()
        outfit_items_raw = db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id"
        ).fetchall()

    # group outfit items
    oi_map = {}
    for r in outfit_items_raw:
        oi_map.setdefault(r['outfit_id'], []).append(_row(r))

    outfits = []
    for o in outfits_raw:
        od = _row(o)
        od['items'] = oi_map.get(o['id'], [])
        outfits.append(od)

    return render_template('guardarropa/index.html',
                           items=items, outfits=outfits,
                           categorias=CATEGORIAS, ocasiones=OCASIONES,
                           temporadas=TEMPORADAS, estados=ESTADOS)


# ── Wardrobe items API ────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/items')
def api_items():
    cat = request.args.get('categoria', '')
    oca = request.args.get('ocasion', '')
    q   = request.args.get('q', '').strip()
    sql = "SELECT * FROM wardrobe_items WHERE activo=1"
    params = []
    if cat:
        sql += " AND categoria=?"; params.append(cat)
    if oca:
        sql += " AND ocasion LIKE ?"; params.append(f'%{oca}%')
    if q:
        sql += " AND (nombre LIKE ? OR marca LIKE ? OR notas LIKE ?)"; params += [f'%{q}%']*3
    sql += " ORDER BY created_at DESC"
    with get_db() as db:
        rows = [_row(r) for r in db.execute(sql, params).fetchall()]
    return jsonify(rows)


@guardarropa_bp.route('/api/item', methods=['POST'])
def create_item():
    d   = request.get_json(force=True)
    now = datetime.now().isoformat()
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO wardrobe_items
               (nombre,categoria,subcategoria,color_hex,color_name,marca,
                ocasion,temporada,estado,precio,notas,url,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_s(d,'nombre'), _s(d,'categoria','Camisa'), _s(d,'subcategoria'),
             _s(d,'color_hex','#C9A84C'), _s(d,'color_name'), _s(d,'marca'),
             _s(d,'ocasion'), _s(d,'temporada','todo'), _s(d,'estado','bueno'),
             safe_float(d.get('precio'), min_val=0.0), _s(d,'notas'), _s(d,'url',max_len=1000), now)
        )
        db.commit()
        new_id = cur.lastrowid
        row = _row(db.execute("SELECT * FROM wardrobe_items WHERE id=?", (new_id,)).fetchone())
    return jsonify(row), 201


@guardarropa_bp.route('/api/item/<int:iid>', methods=['PUT'])
def update_item(iid):
    d = request.get_json(force=True)
    with get_db() as db:
        db.execute(
            """UPDATE wardrobe_items SET
               nombre=?,categoria=?,subcategoria=?,color_hex=?,color_name=?,marca=?,
               ocasion=?,temporada=?,estado=?,precio=?,notas=?,url=?
               WHERE id=?""",
            (_s(d,'nombre'), _s(d,'categoria','Camisa'), _s(d,'subcategoria'),
             _s(d,'color_hex','#C9A84C'), _s(d,'color_name'), _s(d,'marca'),
             _s(d,'ocasion'), _s(d,'temporada','todo'), _s(d,'estado','bueno'),
             safe_float(d.get('precio'), min_val=0.0), _s(d,'notas'), _s(d,'url',max_len=1000), iid)
        )
        db.commit()
        row = _row(db.execute("SELECT * FROM wardrobe_items WHERE id=?", (iid,)).fetchone())
    return jsonify(row)


@guardarropa_bp.route('/api/item/<int:iid>', methods=['DELETE'])
def delete_item(iid):
    with get_db() as db:
        db.execute("UPDATE wardrobe_items SET activo=0 WHERE id=?", (iid,))
        db.commit()
    return jsonify({'ok': True})


@guardarropa_bp.route('/api/item/<int:iid>/uso', methods=['POST'])
def register_uso(iid):
    with get_db() as db:
        db.execute("UPDATE wardrobe_items SET veces_usado=veces_usado+1 WHERE id=?", (iid,))
        db.commit()
        row = db.execute("SELECT veces_usado FROM wardrobe_items WHERE id=?", (iid,)).fetchone()
    return jsonify({'veces_usado': row['veces_usado']})


# ── Outfits API ───────────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/outfits')
def api_outfits():
    with get_db() as db:
        outfits_raw = db.execute("SELECT * FROM outfits ORDER BY created_at DESC").fetchall()
        oi_raw = db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id"
        ).fetchall()
    oi_map = {}
    for r in oi_raw:
        oi_map.setdefault(r['outfit_id'], []).append(_row(r))
    result = []
    for o in outfits_raw:
        od = _row(o); od['items'] = oi_map.get(o['id'], []); result.append(od)
    return jsonify(result)


@guardarropa_bp.route('/api/outfit', methods=['POST'])
def create_outfit():
    d    = request.get_json(force=True)
    now  = datetime.now().isoformat()
    ids  = [int(x) for x in (d.get('item_ids') or []) if x]
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO outfits (nombre,ocasion,rating,notas,created_at) VALUES (?,?,?,?,?)",
            (_s(d,'nombre'), _s(d,'ocasion'), int(d.get('rating') or 0), _s(d,'notas'), now)
        )
        db.commit()
        oid = cur.lastrowid
        for iid in ids:
            try: db.execute("INSERT INTO outfit_items (outfit_id,item_id) VALUES (?,?)", (oid, iid))
            except Exception: pass
        db.commit()
        row = _row(db.execute("SELECT * FROM outfits WHERE id=?", (oid,)).fetchone())
        row['items'] = [_row(r) for r in db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id WHERE oi.outfit_id=?", (oid,)
        ).fetchall()]
    return jsonify(row), 201


@guardarropa_bp.route('/api/outfit/<int:oid>', methods=['PUT'])
def update_outfit(oid):
    d   = request.get_json(force=True)
    ids = [int(x) for x in (d.get('item_ids') or []) if x]
    with get_db() as db:
        db.execute(
            "UPDATE outfits SET nombre=?,ocasion=?,rating=?,notas=? WHERE id=?",
            (_s(d,'nombre'), _s(d,'ocasion'), int(d.get('rating') or 0), _s(d,'notas'), oid)
        )
        db.execute("DELETE FROM outfit_items WHERE outfit_id=?", (oid,))
        for iid in ids:
            try: db.execute("INSERT INTO outfit_items (outfit_id,item_id) VALUES (?,?)", (oid, iid))
            except Exception: pass
        db.commit()
        row = _row(db.execute("SELECT * FROM outfits WHERE id=?", (oid,)).fetchone())
        row['items'] = [_row(r) for r in db.execute(
            "SELECT oi.outfit_id, wi.id, wi.nombre, wi.categoria, wi.color_hex, wi.foto "
            "FROM outfit_items oi JOIN wardrobe_items wi ON oi.item_id=wi.id WHERE oi.outfit_id=?", (oid,)
        ).fetchall()]
    return jsonify(row)


@guardarropa_bp.route('/api/outfit/<int:oid>', methods=['DELETE'])
def delete_outfit(oid):
    with get_db() as db:
        db.execute("DELETE FROM outfit_items WHERE outfit_id=?", (oid,))
        db.execute("DELETE FROM outfits WHERE id=?", (oid,))
        db.commit()
    return jsonify({'ok': True})


@guardarropa_bp.route('/api/outfit/<int:oid>/usar', methods=['POST'])
def usar_outfit(oid):
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db() as db:
        db.execute(
            "UPDATE outfits SET veces_usado=COALESCE(veces_usado,0)+1, ultimo_uso=? WHERE id=?",
            (today, oid)
        )
        item_ids = [r['item_id'] for r in db.execute(
            "SELECT item_id FROM outfit_items WHERE outfit_id=?", (oid,)
        ).fetchall()]
        for iid in item_ids:
            db.execute("UPDATE wardrobe_items SET veces_usado=veces_usado+1 WHERE id=?", (iid,))
        db.commit()
        row = _row(db.execute("SELECT * FROM outfits WHERE id=?", (oid,)).fetchone())
    return jsonify({'ok': True, 'veces_usado': row.get('veces_usado', 1), 'ultimo_uso': today})


# ── Photo upload ──────────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/upload/<int:iid>', methods=['POST'])
def upload_photo(iid):
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Sin archivo'}), 400
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if not ext or ext not in ALLOWED_EXT:
        # Dragged browser images arrive without extension — use MIME type
        _mime_map = {'image/jpeg': '.jpg', 'image/png': '.png',
                     'image/webp': '.webp', 'image/heic': '.heic'}
        ext = _mime_map.get((f.content_type or '').split(';')[0].strip(), '')
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'error': 'Tipo no permitido'}), 400
    filename = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, filename))
    with get_db() as db:
        # remove old photo file if exists
        old = db.execute("SELECT foto FROM wardrobe_items WHERE id=?", (iid,)).fetchone()
        if old and old['foto']:
            try: os.remove(os.path.join(UPLOAD_DIR, old['foto']))
            except OSError: pass
        db.execute("UPDATE wardrobe_items SET foto=? WHERE id=?", (filename, iid))
        db.commit()
    return jsonify({'ok': True, 'filename': filename})


_BLOCKED_HOSTS = {'localhost', ''}
_PRIVATE_PREFIXES = ('127.', '10.', '192.168.', '169.254.', '0.', '::1')


def _validate_url(url: str) -> None:
    """Bloquea URLs privadas/loopback para prevenir SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('Solo se permiten URLs http/https')
    host = (parsed.hostname or '').lower()
    if host in _BLOCKED_HOSTS:
        raise ValueError('Host no permitido')
    for prefix in _PRIVATE_PREFIXES:
        if host.startswith(prefix):
            raise ValueError('Host no permitido')
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError('IP privada no permitida')
    except ValueError as exc:
        if 'no permitid' in str(exc):
            raise


def _extract_image_url(page_url):
    """Extrae la URL de imagen principal de una página HTML (og:image, twitter:image, etc.)."""
    import re
    _validate_url(page_url)
    req = urllib.request.Request(page_url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        ct = resp.headers.get('Content-Type', '')
        if 'image' in ct:
            return page_url, ct, resp.read(5 * 1024 * 1024)
        html = resp.read(150_000).decode('utf-8', errors='ignore')

    # Buscar og:image, twitter:image, itemprop="image"
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        r'<meta[^>]+itemprop=["\']image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            img_url = m.group(1).strip()
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                from urllib.parse import urlparse
                p = urlparse(page_url)
                img_url = f'{p.scheme}://{p.netloc}{img_url}'
            return img_url, None, None

    raise ValueError('No se encontró imagen en la página')


@guardarropa_bp.route('/api/item/<int:iid>/fetch-url-photo', methods=['POST'])
def fetch_url_photo(iid):
    d   = request.get_json(force=True)
    url = d.get('url', '').strip()
    if not url:
        return jsonify({'ok': False, 'error': 'URL vacía'}), 400
    try:
        img_url, ct, data = _extract_image_url(url)

        # Si _extract_image_url devolvió solo la URL (página HTML), descargar la imagen
        if data is None:
            _validate_url(img_url)
            req2 = urllib.request.Request(img_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                ct = resp2.headers.get('Content-Type', '')
                data = resp2.read(5 * 1024 * 1024)

        if   'png'  in (ct or ''): ext = '.png'
        elif 'webp' in (ct or ''): ext = '.webp'
        else:                      ext = '.jpg'

        filename = uuid.uuid4().hex + ext
        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as f:
            f.write(data)
        with get_db() as db:
            old = db.execute("SELECT foto FROM wardrobe_items WHERE id=?", (iid,)).fetchone()
            if old and old['foto']:
                try: os.remove(os.path.join(UPLOAD_DIR, old['foto']))
                except OSError: pass
            db.execute("UPDATE wardrobe_items SET foto=? WHERE id=?", (filename, iid))
            db.commit()
        return jsonify({'ok': True, 'filename': filename})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        _log.error('fetch_url_photo id=%s: %s', iid, e)
        return jsonify({'ok': False, 'error': 'No se pudo obtener la imagen'}), 400


@guardarropa_bp.route('/photos/<filename>')
def serve_photo(filename):
    if '..' in filename or '/' in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename)


# ── AI helpers ───────────────────────────────────────────────────────────────

def _gemini(prompt, max_tokens=900):
    """Call Gemini 2.0 Flash via REST. Returns raw text."""
    import urllib.error
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY no configurada')
    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'gemini-2.0-flash:generateContent?key={api_key}'
    )
    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': 0.7},
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        try:
            msg = json.loads(err_body).get('error', {}).get('message', err_body[:200])
        except Exception:
            msg = err_body[:200]
        raise ValueError(f'Gemini HTTP {e.code}: {msg}')
    data = json.loads(resp.read().decode())
    return data['candidates'][0]['content']['parts'][0]['text'].strip()


def _strip_fences(raw):
    """Remove markdown code fences from IA response."""
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return raw.strip()


# ── AI Analysis ──────────────────────────────────────────────────────────────

@guardarropa_bp.route('/api/ai-outfit', methods=['POST'])
def ai_generate_outfit():
    if not os.environ.get('GEMINI_API_KEY'):
        return jsonify({'ok': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

    d = request.get_json(force=True)
    occasion = d.get('ocasion', 'Casual')

    with get_db() as db:
        items = [dict(r) for r in db.execute(
            "SELECT id, nombre, categoria, subcategoria, color_hex, color_name, marca, ocasion, temporada, estado "
            "FROM wardrobe_items WHERE activo=1 ORDER BY estado DESC"
        ).fetchall()]

    if not items:
        return jsonify({'ok': False, 'error': 'No hay prendas en el armario'}), 400

    items_list = '\n'.join([
        f"ID {i['id']}: {i['nombre']} | {i['categoria']}{(' · '+i['subcategoria']) if i.get('subcategoria') else ''} "
        f"| hex:{i['color_hex']} {i.get('color_name') or ''} | {i.get('marca') or ''} | estado:{i['estado']}"
        for i in items
    ])

    prompt = f"""Eres un coach de imagen personal masculino de élite con 20 años de experiencia vistiendo a ejecutivos y figuras públicas.

INVENTARIO DISPONIBLE ({len(items)} prendas):
{items_list}

OCASIÓN: {occasion}

Crea el outfit PERFECTO para esta ocasión usando SOLO las prendas del inventario. Aplica:
- Harmonía de color (análogos, monocromático, contraste tonal, complementarios)
- Equilibrio de proporciones visuales (proporción áurea en silhouette)
- Dress code apropiado para la ocasión
- Prioriza estado "nuevo" o "bueno"

Responde SOLO con JSON (sin markdown, sin ```, sin texto extra):
{{"nombre":"nombre elegante y descriptivo del look","ocasion":"{occasion}","item_ids":[IDs enteros de las prendas],"harmony":"tipo de harmonía de color específico","why_works":"por qué esta combinación funciona visualmente y psicológicamente — 2-3 líneas directas y concretas","tips":["tip concreto 1","tip concreto 2"],"rating":5}}

REGLAS: item_ids son enteros del inventario · incluye superior + inferior + calzado si disponibles · rating es entero 1-5"""

    try:
        raw = _strip_fences(_gemini(prompt, max_tokens=600))
        data = json.loads(raw)
        data['item_ids'] = [int(x) for x in data.get('item_ids', []) if x]
        data['ok'] = True
        return jsonify(data)
    except json.JSONDecodeError as e:
        return jsonify({'ok': False, 'error': f'JSON inválido: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@guardarropa_bp.route('/api/capsule/analyze', methods=['POST'])
def analyze_capsule():
    if not os.environ.get('GEMINI_API_KEY'):
        return jsonify({'ok': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

    with get_db() as db:
        items = [dict(r) for r in db.execute(
            "SELECT nombre, categoria, subcategoria, color_hex, color_name, marca, ocasion, estado, precio, veces_usado "
            "FROM wardrobe_items WHERE activo=1"
        ).fetchall()]

    if not items:
        return jsonify({'ok': False, 'error': 'No hay prendas'}), 400

    items_summary = '\n'.join([
        f"- {i['nombre']} | {i['categoria']}{(' · '+i['subcategoria']) if i.get('subcategoria') else ''} "
        f"| {i['color_hex']} {i.get('color_name') or ''} | {i.get('marca') or 'sin marca'} | estado:{i['estado']} | usos:{i.get('veces_usado', 0)}"
        for i in items
    ])

    prompt = f"""Eres el consultor de imagen personal masculina más riguroso del mundo. Tu metodología combina la ciencia del color de Faber Birren, los principios del armario cápsula de Susie Faux, y los estándares de Permanent Style y Die, Workwear!

ARMARIO A EVALUAR ({len(items)} prendas activas):
{items_summary}

Evalúa con rigor científico. Responde SOLO con JSON (sin markdown):
{{"score":85,"score_label":"Avanzado","strengths":["fortaleza específica 1","fortaleza 2","fortaleza 3"],"gaps":[{{"item":"prenda faltante específica","priority":"alta","reason":"por qué es una pieza ancla del armario masculino de élite","versatility_multiplier":8}},{{"item":"segunda prenda","priority":"media","reason":"..."}}],"color_harmony":"análisis de coherencia cromática del armario actual — ¿hay paleta definida?","versatility_index":72,"outfit_combinations_est":45,"elite_verdict":"veredicto directo como coach de élite — 2 líneas, sin filtros, qué falta para el siguiente nivel"}}

Niveles: 0-30=Iniciado | 31-50=Competente | 51-70=Sólido | 71-85=Avanzado | 86-95=Élite | 96-100=Maestro

Criterios científicos:
1. VERSATILIDAD: cada prenda → mínimo 5 outfits posibles
2. PALETA 70/20/10: 70% neutros, 20% colores base, 10% acento
3. DRESS CODES: casual, smart-casual, business casual, formal
4. PRENDAS ANCLA: blazer navy, camisa blanca, Oxford negro, pantalón gris
5. COHERENCIA: todas las prendas deben poder combinarse entre sí"""

    try:
        raw = _strip_fences(_gemini(prompt, max_tokens=900))
        data = json.loads(raw)
        data['ok'] = True
        return jsonify(data)
    except json.JSONDecodeError:
        return jsonify({'ok': False, 'error': 'Respuesta IA inválida'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@guardarropa_bp.route('/api/item/<int:iid>/analyze', methods=['POST'])
def analyze_item(iid):
    if not os.environ.get('GEMINI_API_KEY'):
        return jsonify({'ok': False, 'error': 'GEMINI_API_KEY no configurada'}), 503

    with get_db() as db:
        row = db.execute("SELECT * FROM wardrobe_items WHERE id=?", (iid,)).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': 'Item no encontrado'}), 404
    r = dict(row)

    prompt = f"""Eres un experto en psicología del color aplicada a la moda masculina.
Analiza esta prenda y responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional.

Prenda:
- Nombre: {r.get('nombre', '')}
- Categoría: {r.get('categoria', '')}
- Subcategoría: {r.get('subcategoria', '') or 'ninguna'}
- Color hex: {r.get('color_hex', '#888888')}
- Marca: {r.get('marca', '') or 'sin marca'}
- Ocasión registrada: {r.get('ocasion', '') or 'no especificada'}
- Temporada: {r.get('temporada', 'todo')}

Responde con este JSON exacto (sin markdown, sin ```):
{{
  "color_name": "nombre descriptivo del color en español",
  "psych": "análisis de la psicología del color de esta prenda en contexto de moda masculina (máx 20 palabras)",
  "rec": "en qué ocasiones específicas usar esta prenda (máx 12 palabras)",
  "is_sportswear": false,
  "sport_note": "si es deportiva explica brevemente por qué, si no déjalo vacío"
}}

Para is_sportswear=true: considera categoría deportiva, tejidos técnicos (dry-fit, lycra, spandex), ropa interior/pijama, calzado deportivo, o nombres como gym, running, yoga, etc."""

    try:
        raw = _strip_fences(_gemini(prompt, max_tokens=300))
        data = json.loads(raw)
        data['ok'] = True
        return jsonify(data)
    except json.JSONDecodeError:
        return jsonify({'ok': False, 'error': 'Respuesta IA inválida'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── helpers ───────────────────────────────────────────────────────────────────

def _s(d, key, default='', max_len=500):
    return clean_str(d.get(key, default), max_len=max_len)
