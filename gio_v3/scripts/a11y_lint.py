"""
a11y_lint.py — Auditoría estática de accesibilidad (handoff A11y + catálogo, S1).

Revisa templates/** y static/css/** sin navegador y reporta archivo:línea:

  fg4-texto      var(--fg-4) como `color` (2.9:1) fuera de lo deshabilitado,
                 placeholders o lo decorativo (aria-hidden)
  icono-sin-nombre  <button>/<a> cuyo único contenido es un ícono, sin
                 aria-label, aria-labelledby ni title
  campo-sin-label  <input>/<select>/<textarea> sin <label for>, aria-label,
                 aria-labelledby ni <label> que lo envuelva (salvo hidden)
  outline-sin-foco  outline:none/0 sin un :focus-visible para ese selector
                 en el mismo archivo
  onclick-sin-rol  onclick en <div>/<span> sin role y tabindex
  img-sin-alt    <img> sin alt
  h1-multiple    más de un <h1> por página (sumando sus include)

Uso:
  python scripts/a11y_lint.py                 # lista todo, por módulo
  python scripts/a11y_lint.py --nuevos        # solo lo que no está en la línea base
  python scripts/a11y_lint.py --baseline      # regenera scripts/a11y_baseline.json

La línea base guarda una huella por problema (regla + archivo + el código
normalizado), así que mover líneas no cuenta como problema nuevo.
pre_deploy_check falla solo con problemas nuevos. Ver docs/A11Y.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(AQUI)
BASELINE = os.path.join(AQUI, 'a11y_baseline.json')
CSS_FUERA = {'tailwind-built.css', 'tailwind-src.css'}     # generado / solo directivas

REGLAS = {
    'fg4-texto': 'var(--fg-4) como color de texto (2.9:1): usa --fg-3 o márcalo aria-hidden si es decorativo',
    'icono-sin-nombre': 'botón o enlace de solo ícono sin aria-label / aria-labelledby / title',
    'campo-sin-label': 'campo sin <label for>, aria-label, aria-labelledby ni <label> que lo envuelva',
    'outline-sin-foco': 'outline:none/0 sin :focus-visible alternativo para ese selector',
    'onclick-sin-rol': 'onclick en <div>/<span> sin role y tabindex: usa <button type="button">',
    'img-sin-alt': '<img> sin alt (alt="" si es decorativa)',
    'h1-multiple': 'más de un <h1> en la página (contando sus include)',
}


def _linea(texto, pos):
    return texto.count('\n', 0, pos) + 1


def _norm(s):
    return re.sub(r'\s+', ' ', s).strip()[:160]


class Problema(dict):
    @property
    def huella(self):
        base = f"{self['regla']}|{self['archivo']}|{_norm(self['codigo'])}"
        return hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]


def _p(regla, archivo, linea, codigo):
    return Problema(regla=regla, archivo=archivo, linea=linea, codigo=_norm(codigo))


# ── CSS ───────────────────────────────────────────────────────────────────────

_EXENTO_FG4 = (':disabled', 'aria-disabled', '.is-disabled', 'placeholder', 'aria-hidden', '[disabled]')


def _reglas_css(texto):
    """[(selector, cuerpo, pos)] de las reglas planas (también dentro de @media)."""
    limpio = re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m.group(0)), texto, flags=re.S)
    out = []
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', limpio):
        sel = m.group(1).strip()
        if sel.startswith('@') or not sel:
            continue
        out.append((sel, m.group(2), m.start(1) + (len(m.group(1)) - len(m.group(1).lstrip()))))
    return out


def lint_css(rel, texto):
    out = []
    reglas = _reglas_css(texto)
    con_foco = ' '.join(s for s, _c, _p2 in reglas if ':focus-visible' in s)
    for sel, cuerpo, pos in reglas:
        if re.search(r'(^|;)\s*color\s*:\s*var\(--fg-4\)', cuerpo):
            partes = [s.strip() for s in sel.split(',')]
            malos = [s for s in partes if not any(x in s for x in _EXENTO_FG4)]
            if malos:
                out.append(_p('fg4-texto', rel, _linea(texto, pos), ', '.join(malos) + '{color:var(--fg-4)}'))
        if re.search(r'(^|;)\s*outline\s*:\s*(none|0)\s*(;|$)', cuerpo):
            for s in (x.strip() for x in sel.split(',')):
                base = re.sub(r':(focus|focus-within|hover|active)\b', '', s).strip()
                if ':focus-visible' in s or (base and base + ':focus-visible' in con_foco) or base in ('*', ''):
                    continue
                if base and re.search(re.escape(base) + r'(\[[^\]]*\])?:focus-visible', con_foco):
                    continue
                out.append(_p('outline-sin-foco', rel, _linea(texto, pos), s + '{outline:none}'))
    return out


# ── Plantillas ────────────────────────────────────────────────────────────────

_ICONO = r'(?:\s*(?:<i\b[^>]*data-lucide[^>]*>\s*</i>|<svg\b.*?</svg>|\{\{\s*ic\([^}]*\)\s*\}\})\s*)'
_NOMBRE = re.compile(r'\b(aria-label|aria-labelledby|title)\s*=')


def _sin_comentarios(texto):
    """Quita <!-- --> y {# #} conservando los saltos de línea (archivo:línea)."""
    blanco = lambda m: re.sub(r'[^\n]', ' ', m.group(0))
    return re.sub(r'\{#.*?#\}', blanco, re.sub(r'<!--.*?-->', blanco, texto, flags=re.S), flags=re.S)


def lint_html(rel, texto):
    out = []
    texto = _sin_comentarios(texto)
    # 1) botones/enlaces de solo ícono
    for m in re.finditer(r'<(button|a)\b([^>]*)>(' + _ICONO + r')</\1>', texto, flags=re.S | re.I):
        if not _NOMBRE.search(m.group(2)) and '**' not in m.group(2):
            out.append(_p('icono-sin-nombre', rel, _linea(texto, m.start()), m.group(0)))
    # 2) campos sin etiqueta
    for m in re.finditer(r'<(input|select|textarea)\b([^>]*?)/?>', texto, flags=re.I | re.S):
        attrs = m.group(2)
        if re.search(r'type\s*=\s*["\']?(hidden|submit|button|reset)', attrs, re.I):
            continue
        if re.search(r'\baria-label(ledby)?\s*=', attrs) or '{{ kwargs' in attrs or '**' in attrs:
            continue
        idm = re.search(r'\bid\s*=\s*"([^"]+)"', attrs)
        if idm and re.search(r'<label\b[^>]*\bfor\s*=\s*"' + re.escape(idm.group(1)) + '"', texto):
            continue
        antes = texto[:m.start()]
        if antes.rfind('<label') > antes.rfind('</label>'):
            continue                                  # envuelto en <label>
        out.append(_p('campo-sin-label', rel, _linea(texto, m.start()), m.group(0)[:120]))
    # 3) onclick en div/span
    for m in re.finditer(r'<(div|span)\b([^>]*\bonclick\s*=[^>]*)>', texto, flags=re.I):
        if not (re.search(r'\brole\s*=', m.group(2)) and re.search(r'\btabindex\s*=', m.group(2))):
            out.append(_p('onclick-sin-rol', rel, _linea(texto, m.start()), m.group(0)[:120]))
    # 4) img sin alt
    for m in re.finditer(r'<img\b([^>]*)>', texto, flags=re.I):
        if not re.search(r'\balt\s*=', m.group(1)):
            out.append(_p('img-sin-alt', rel, _linea(texto, m.start()), m.group(0)[:120]))
    # 5) estilos en línea con --fg-4 como color
    for m in re.finditer(r'style\s*=\s*"([^"]*)"', texto):
        if re.search(r'(^|;)\s*color\s*:\s*var\(--fg-4\)', m.group(1)):
            pre = texto[max(0, m.start() - 200):m.start()]
            if 'aria-hidden' not in pre[pre.rfind('<'):]:
                out.append(_p('fg4-texto', rel, _linea(texto, m.start()), m.group(0)))
    return out


def _h1(texto):
    """<h1> literales + llamadas a ui.page_head (que pinta el h1)."""
    return len(re.findall(r'<h1\b', texto)) + len(re.findall(r'page_head\(', texto))


def lint_paginas(raiz, archivos):
    """h1-multiple: páginas (las que extienden un layout) sumando sus include."""
    out = []
    cache = {}

    def contar(rel, vistos):
        if rel in vistos or rel not in archivos:
            return 0
        vistos = vistos | {rel}
        t = _sin_comentarios(archivos[rel])
        n = _h1(re.sub(r'\{%\s*macro\b.*?\{%\s*endmacro\s*%\}', '', t, flags=re.S))
        for inc in re.findall(r'\{%-?\s*include\s+"([^"]+)"', t):
            n += contar('templates/' + inc, vistos)
        return n

    for rel, t in archivos.items():
        if '{% extends' not in t or not rel.startswith('templates/'):
            continue
        n = contar(rel, set())
        if n > 1:
            out.append(_p('h1-multiple', rel, 1, f'{n} h1'))
    return out


# ── Recorrido ─────────────────────────────────────────────────────────────────

def recolectar(raiz=APP):
    archivos = {}
    for carpeta, ext in (('templates', '.html'), ('static/css', '.css')):
        base = os.path.join(raiz, carpeta)
        for dirp, _d, fs in os.walk(base):
            for f in fs:
                if f.endswith(ext) and f not in CSS_FUERA:
                    p = os.path.join(dirp, f)
                    archivos[os.path.relpath(p, raiz).replace(os.sep, '/')] = open(p, encoding='utf-8').read()
    return archivos


def lint(raiz=APP):
    archivos = recolectar(raiz)
    out = []
    for rel, t in sorted(archivos.items()):
        out += lint_css(rel, t) if rel.endswith('.css') else lint_html(rel, t)
    out += lint_paginas(raiz, archivos)
    return out


def modulo(rel):
    partes = rel.split('/')
    if partes[0] == 'templates':
        return partes[1] if len(partes) > 2 else partes[1].rsplit('.', 1)[0]
    return partes[-1].rsplit('.', 1)[0]


def cargar_baseline(ruta=BASELINE):
    if not os.path.exists(ruta):
        return Counter()
    d = json.load(open(ruta, encoding='utf-8'))
    return Counter({k: v['n'] for k, v in d.get('problemas', {}).items()})


def nuevos(problemas, base=None):
    """Lo que excede la línea base (por huella, contando repeticiones)."""
    base = cargar_baseline() if base is None else base
    vistos, out = Counter(), []
    for p in problemas:
        vistos[p.huella] += 1
        if vistos[p.huella] > base.get(p.huella, 0):
            out.append(p)
    return out


def guardar_baseline(problemas, ruta=BASELINE):
    probs = {}
    for p in problemas:
        e = probs.setdefault(p.huella, {'regla': p['regla'], 'archivo': p['archivo'], 'codigo': p['codigo'], 'n': 0})
        e['n'] += 1
    por_mod = Counter(modulo(p['archivo']) for p in problemas)
    data = {'total': len(problemas), 'por_modulo': dict(por_mod.most_common()),
            'por_regla': dict(Counter(p['regla'] for p in problemas).most_common()),
            'problemas': dict(sorted(probs.items(), key=lambda kv: (kv[1]['archivo'], kv[1]['regla'])))}
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    return data


def imprimir(problemas, titulo):
    print(f'{titulo}: {len(problemas)}')
    for p in sorted(problemas, key=lambda x: (x['archivo'], x['linea'])):
        print(f"  {p['archivo']}:{p['linea']}  [{p['regla']}] {p['codigo'][:90]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--baseline', action='store_true', help='regenera scripts/a11y_baseline.json')
    ap.add_argument('--nuevos', action='store_true', help='solo lo que no está en la línea base')
    args = ap.parse_args(argv)
    probs = lint()
    if args.baseline:
        d = guardar_baseline(probs)
        print(f"Línea base: {d['total']} problemas")
        for m, n in d['por_modulo'].items():
            print(f'  {m:20} {n}')
        return 0
    if args.nuevos:
        nv = nuevos(probs)
        imprimir(nv, 'Problemas nuevos')
        return 1 if nv else 0
    imprimir(probs, 'Problemas')
    return 0


if __name__ == '__main__':
    sys.exit(main())
