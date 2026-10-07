"""
ia.py — acceso a Gemini 2.5 Flash compartido por los módulos con IA
(Guardarropa: coach de imagen; Plantas: doctor de plantas).

Sin GEMINI_API_KEY las funciones lanzan ValueError; cada módulo decide cómo
mostrarlo (los endpoints responden 503 y la UI oculta el botón).
"""
import io
import json
import logging
import os
import urllib.request

_log = logging.getLogger(__name__)


def disponible() -> bool:
    return bool(os.environ.get('GEMINI_API_KEY'))


def gemini(prompt, max_tokens=4096, thinking_budget=0, temperature=0.7, images=None):
    """Call Gemini 2.5 Flash via REST. Returns raw text (JSON mode).
    `thinking_budget` > 0 deja razonar al modelo antes de responder (los
    tokens de razonamiento cuentan dentro de `max_tokens`). `images` es una
    lista de (mime, bytes) que se adjuntan antes del texto."""
    import base64
    import urllib.error
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY no configurada')
    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'gemini-2.5-flash:generateContent?key={api_key}'
    )
    body = json.dumps({
        'contents': [{'parts': [
            {'inline_data': {'mime_type': mime, 'data': base64.b64encode(raw).decode()}}
            for mime, raw in (images or [])
        ] + [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': max_tokens,
            'temperature': temperature,
            'responseMimeType': 'application/json',
            'thinkingConfig': {'thinkingBudget': thinking_budget},
        },
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=90)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        try:
            msg = json.loads(err_body).get('error', {}).get('message', err_body[:200])
        except Exception:
            msg = err_body[:200]
        raise ValueError(f'Gemini HTTP {e.code}: {msg}')
    data = json.loads(resp.read().decode())
    candidate = data['candidates'][0]
    parts = candidate['content']['parts']
    # Filter out thought=True parts (internal reasoning tokens from Gemini 2.5)
    text_parts = [p.get('text', '') for p in parts if not p.get('thought', False)]
    return ''.join(text_parts).strip()


def extract_json(raw):
    """Extract first valid JSON object from IA response, ignoring surrounding text."""
    raw = raw.strip()
    # Strip markdown fences
    if '```' in raw:
        parts = raw.split('```')
        for part in parts:
            part = part.strip()
            if part.startswith('json'):
                part = part[4:].strip()
            if part.startswith('{'):
                raw = part
                break
    # Find outermost { ... }
    start = raw.find('{')
    if start == -1:
        raise ValueError(f'No JSON object in response: {raw[:200]}')
    depth, end = 0, -1
    for i, ch in enumerate(raw[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise ValueError(f'Unclosed JSON in response: {raw[:200]}')
    return raw[start:end + 1]


def photo_for_ai(path, max_dim=768):
    """Foto local reducida a JPEG chico para mandarla a la IA: ('image/jpeg',
    bytes), o None si no hay foto o no se puede leer (la IA sigue con texto)."""
    if not path:
        return None
    from PIL import Image, ImageOps
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, 'JPEG', quality=80)
            return ('image/jpeg', buf.getvalue())
    except Exception as e:
        _log.info('Foto no disponible para la IA (%s): %s', path, e)
        return None
