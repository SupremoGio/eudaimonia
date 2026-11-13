"""
gen_componentes_md.py — docs/COMPONENTES.md desde templates/_ui/macros.html
(handoff A11y + catálogo, S3).

Lee cada `{% macro nombre(args) %}` con el comentario `{# … #}` que lo
precede (entre ambos solo puede haber `{% set … %}`). La primera línea del
comentario es el resumen; el resto, la nota. pre_deploy_check falla si una
macro no tiene comentario (macros_sin_comentario).

    python scripts/gen_componentes_md.py           # regenera docs/COMPONENTES.md
    python scripts/gen_componentes_md.py --check   # 1 si falta algún comentario
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(AQUI)
MACROS = os.path.join(APP, 'templates', '_ui', 'macros.html')
DOC = os.path.join(os.path.dirname(APP), 'docs', 'COMPONENTES.md')

_MACRO = re.compile(r'\{%-?\s*macro\s+(\w+)\s*\((.*?)\)\s*-?%\}', re.S)
_COMENT = re.compile(r'\{#-?(.*?)-?#\}\s*((?:\{%-?\s*set\b.*?%\}\s*)*)$', re.S)


def macros(texto=None):
    """[{nombre, args, doc}] en orden; doc = '' si no tiene comentario."""
    texto = open(MACROS, encoding='utf-8').read() if texto is None else texto
    out, previo = [], 0
    for m in _MACRO.finditer(texto):
        antes = texto[previo:m.start()]
        k = antes.rfind('{#')                              # el comentario más cercano
        c = _COMENT.search(antes[k:]) if k >= 0 else None
        doc = ''
        if c:
            doc = '\n'.join(l.strip() for l in c.group(1).strip().splitlines())
            if doc.startswith('EUDAIMONIA OS'):          # cabecera del archivo, no de la macro
                doc = ''
        out.append({'nombre': m.group(1), 'args': re.sub(r'\s+', ' ', m.group(2)).strip(), 'doc': doc})
        fin = texto.find('endmacro', m.end())
        previo = texto.find('%}', fin) + 2 if fin >= 0 else m.end()
    return out


def resumen(doc):
    """Primera oración del comentario (sin los «──» decorativos)."""
    t = ' '.join(doc.replace('──', ' ').split())
    m = re.match(r'(.+?\.)(\s|$)', t)
    return (m.group(1) if m else t)[:160]


def macros_sin_comentario(texto=None):
    return [m['nombre'] for m in macros(texto) if not m['doc']]


def generar():
    ms = macros()
    lineas = [
        '# Componentes (macros de `_ui/macros.html`)',
        '',
        'Generado por `gio_v3/scripts/gen_componentes_md.py`. No se edita a mano: el comentario',
        '`{# … #}` sobre cada macro es la fuente. Antes de crear un componente, revisa `/_ui` (catálogo vivo,',
        'en desarrollo) y esta lista.',
        '',
        '```jinja',
        "{% import '_ui/macros.html' as ui %}",
        '```',
        '',
        '| Macro | Para qué |',
        '|---|---|',
    ]
    for m in ms:
        lineas.append(f"| [`{m['nombre']}`](#{m['nombre']}) | {resumen(m['doc']).replace('|', '/') or '—'} |")
    for m in ms:
        lineas += ['', f"## `{m['nombre']}`", '', '```jinja', f"ui.{m['nombre']}({m['args']})", '```']
        if m['doc']:
            lineas += ['', ' '.join(m['doc'].split())]
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    with open(DOC, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lineas) + '\n')
    return DOC


if __name__ == '__main__':
    if '--check' in sys.argv:
        faltan = macros_sin_comentario()
        print('Sin comentario: ' + ', '.join(faltan) if faltan else 'Todas las macros tienen comentario')
        sys.exit(1 if faltan else 0)
    print('Listo: ' + generar())
