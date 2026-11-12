"""
Perfil v2 — datos de la portada y de las secciones.

· nav_counts: el contador de cada sección del lateral.
· atencion:   «Requiere atención» del Resumen (recordatorios vencidos o de
              hoy, datos sin capturar y un aviso de medidas viejas).
· tiles:      los tres accesos del Resumen (recordatorios, datos y peso).
· medidas:    tabla con las últimas 3 lecturas, tendencia y antigüedad.
· grupos_datos: Identidad / Contacto / Privados.
· vincular_pagos: recordatorios de pago de tarjeta que ya viven en Oikonomia.
"""
import re
import unicodedata
from datetime import date, datetime

from modules.perfil import recordatorios as rec

PLACEHOLDER = '— editar —'
MEDIDA_VIEJA_DIAS = 60
SIN_EDAD = ('estatura',)                 # la estatura no «envejece»
TENDENCIA = {'peso': 'down', 'cintura': 'down', 'biceps': 'up'}   # el resto, neutral
CONTACTO = ('telefono', 'email', 'direccion')
MONO = ('telefono',)                     # además de los privados


def lleno(v):
    return bool(v) and v != PLACEHOLDER


# ── Datos personales ─────────────────────────────────────────────────────────

def grupos_datos(info, docs_by_field):
    """Identidad, Contacto y Privados. El valor de un privado no se manda al
    HTML: se pide con /api/privados al mostrarlos o copiarlos."""
    filas = {'id': [], 'contacto': [], 'priv': []}
    for i in info:
        i = dict(i)
        g = 'priv' if i['private'] else ('contacto' if i['key'] in CONTACTO else 'id')
        filas[g].append({
            'key': i['key'], 'label': i['label'], 'private': bool(i['private']),
            'lleno': lleno(i['value']),
            'value': None if i['private'] else (i['value'] if lleno(i['value']) else ''),
            'mono': bool(i['private']) or i['key'] in MONO,
            'docs': len(docs_by_field.get(i['key'], [])),
            'adjuntos': i['key'] not in ('telefono', 'email'),
        })
    return [{'key': 'id', 'label': 'Identidad', 'rows': filas['id']},
            {'key': 'contacto', 'label': 'Contacto', 'rows': filas['contacto']},
            {'key': 'priv', 'label': 'Privados · cifrados', 'rows': filas['priv']}]


# ── Medidas ──────────────────────────────────────────────────────────────────

def _num(v):
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def medidas(measurements, hist_rows, hoy):
    """Una fila por medida: actual, últimas 3 lecturas (de la más vieja a la
    más nueva) con alturas para las mini barras, delta, tono de la última
    barra según la tendencia buena y antigüedad."""
    por_key = {}
    for r in hist_rows:                         # vienen de la más nueva a la más vieja
        por_key.setdefault(r['key'], []).append(r)
    out = []
    for m in measurements:
        m = dict(m)
        h = por_key.get(m['key'], [])
        ult = [x for x in (_num(r['value']) for r in h[:3]) if x is not None][::-1]
        edad = None
        if h:
            try:
                edad = (hoy - date.fromisoformat(h[0]['recorded_at'][:10])).days
            except ValueError:
                edad = None
        delta = round(ult[-1] - ult[-2], 1) if len(ult) >= 2 else None
        tend = TENDENCIA.get(m['key'])
        bueno = None
        if delta is not None and tend:
            bueno = delta < 0 if tend == 'down' else delta > 0
            if delta == 0:
                bueno = None
        lo, hi = (min(ult), max(ult)) if ult else (0, 0)
        barras = [{'h': 12 if hi == lo else round(6 + (v - lo) / (hi - lo) * 14), 'ultima': i == len(ult) - 1}
                  for i, v in enumerate(ult)]
        vieja = lleno(m['value']) and m['key'] not in SIN_EDAD and edad is not None and edad > MEDIDA_VIEJA_DIAS
        out.append({**m, 'lleno': lleno(m['value']), 'ultimas': ult, 'barras': barras, 'delta': delta,
                    'tono': 'success' if bueno is True else ('warning' if bueno is False else ''),
                    'edad': edad, 'edad_txt': _edad_txt(edad), 'vieja': vieja})
    return out


def _edad_txt(d):
    if d is None:
        return '—'
    if d <= 0:
        return 'hoy'
    if d == 1:
        return 'ayer'
    if d >= 365:
        n = d // 365
        return f'hace {n} año' + ('s' if n > 1 else '')
    return f'hace {d} d'


# ── Recordatorios ────────────────────────────────────────────────────────────

GRUPOS_V2 = (('vencidos', 'Vencidos'), ('hoy', 'Hoy'), ('semana', 'Esta semana'), ('despues', 'Después'))


def grupos_recordatorios(reminders, hoy):
    """Vencidos / Hoy / Esta semana / Después (este mes, más adelante y sin
    fecha van juntos en Después)."""
    base = rec.agrupar(reminders, hoy)
    items = {k: [] for k, _ in GRUPOS_V2}
    for g in base:
        k = g['key'] if g['key'] in items else 'despues'
        items[k].extend(g['items'])
    return [{'key': k, 'titulo': t, 'items': items[k]} for k, t in GRUPOS_V2 if items[k]]


def _norm(t):
    t = unicodedata.normalize('NFKD', (t or '').lower())
    return ' ' + re.sub(r'\s+', ' ', ''.join(c for c in t if not unicodedata.combining(c))) + ' '


def tarjeta_de(desc):
    """La tarjeta de PAY_DAYS que nombra un recordatorio de pago, o None."""
    from modules.finanzas.routes import PAY_DAYS
    t = _norm(desc)
    if not re.search(r'\b(pag|tarjeta|tdc|corte)', t):
        return None
    for p in PAY_DAYS:
        if re.search(r'\b' + re.escape(p['match']) + r'\b', t):
            return p['match']
    return None


def vincular_pagos(db):
    """Marca vinculado_oikonomia en los recordatorios de tema Finanzas que son
    el pago de una tarjeta de Oikonomia (PAY_DAYS). Solo enlaza, no borra.
    Idempotente: devuelve cuántos marcó esta vez."""
    n = 0
    for r in db.execute("SELECT id, description, tema FROM reminders WHERE is_active=1 AND COALESCE(vinculado_oikonomia,0)=0").fetchall():
        if rec.tema_valido(r['tema'], r['description']) == 'finanzas' and tarjeta_de(r['description']):
            db.execute("UPDATE reminders SET vinculado_oikonomia=1 WHERE id=?", (r['id'],))
            n += 1
    if n:
        db.commit()
    return n


# ── Portada ──────────────────────────────────────────────────────────────────

def nav_counts(info, med_rows, reminders_grupos, docs_total, vault_total):
    llenos = sum(1 for i in info if lleno(i['value']))
    viejas = sum(1 for m in med_rows if m['vieja'])
    total = sum(len(g['items']) for g in reminders_grupos)
    urg = sum(len(g['items']) for g in reminders_grupos if g['key'] in ('vencidos', 'hoy'))
    return {
        'resumen': {'txt': f"{urg} urgente{'s' if urg != 1 else ''}" if urg else '', 'warn': bool(urg)},
        'datos': {'txt': f'{llenos}/{len(info)}', 'warn': False},
        'medidas': {'txt': f"{viejas} vieja{'s' if viejas != 1 else ''}" if viejas else '', 'warn': False},
        'recordatorios': {'txt': str(total) if total else '', 'warn': bool(urg), 'total': total, 'urgentes': urg},
        'documentos': {'txt': str(docs_total) if docs_total else '', 'warn': False},
        'vault': {'txt': str(vault_total) if vault_total else '', 'warn': False},
        'ajustes': {'txt': '', 'warn': False},
    }


def atencion(reminders_grupos, info, med_rows, fin_ok=False):
    """Lista ordenada de lo que requiere atención: recordatorios vencidos y de
    hoy, datos sin capturar y un resumen de medidas viejas (sin estatura)."""
    out = []
    for g in reminders_grupos:
        if g['key'] not in ('vencidos', 'hoy'):
            continue
        for r in g['items']:
            out.append({'tipo': 'rem', 'id': r['id'], 'desc': r['description'], 'when_txt': r.get('rel') or '',
                        'vencido': g['key'] == 'vencidos', 'tema': rec.TEMA_LABEL.get(r['tema'], ''),
                        'freq': r.get('freq') or '', 'link': '/finanzas/' if (fin_ok and r.get('vinculado_oikonomia')) else ''})
    for i in info:
        if not lleno(i['value']):
            out.append({'tipo': 'dato', 'campo': i['key'], 'label': i['label'], 'privado': bool(i['private'])})
    viejas = [m for m in med_rows if m['vieja']]
    if viejas:
        out.append({'tipo': 'medidas', 'n': len(viejas), 'labels': ', '.join(m['label'] for m in viejas)})
    return out


def tiles(reminders_grupos, info, med_rows):
    total = sum(len(g['items']) for g in reminders_grupos)
    urg = sum(len(g['items']) for g in reminders_grupos if g['key'] in ('vencidos', 'hoy'))
    semana = sum(len(g['items']) for g in reminders_grupos if g['key'] == 'semana')
    llenos = sum(1 for i in info if lleno(i['value']))
    peso = next((m for m in med_rows if m['key'] == 'peso'), None)
    return [
        {'sec': 'recordatorios', 'label': 'Recordatorios', 'icon': 'bell', 'val': str(total),
         'sub': f'{urg} urgente{"s" if urg != 1 else ""} · {semana} esta semana' if urg else (f'{semana} esta semana' if semana else 'nada urgente')},
        {'sec': 'datos', 'label': 'Datos personales', 'icon': 'user-round', 'val': f'{llenos}/{len(info)}',
         'sub': f'{len(info) - llenos} sin capturar' if llenos < len(info) else 'completos'},
        {'sec': 'medidas', 'label': 'Medidas', 'icon': 'ruler',
         'val': f"{peso['value']} {peso['unit']}" if peso and peso['lleno'] else '—',
         'sub': f"peso · {peso['edad_txt']}" if peso and peso['lleno'] else 'peso sin capturar'},
    ]
