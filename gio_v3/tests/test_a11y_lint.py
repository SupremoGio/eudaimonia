"""
test_a11y_lint.py — handoff A11y + catálogo, Sprint 1: scripts/a11y_lint.py.

Cada regla con un fixture que la dispara y uno que no; la línea base por
huella (mover líneas no es nuevo, una copia sí) y la integración con
pre_deploy_check (falla solo con lo nuevo).
"""
import os, sys, json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import pytest
import a11y_lint as al


def _arbol(tmp_path, archivos):
    for rel, txt in archivos.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding='utf-8')
    return str(tmp_path)


def _reglas(tmp_path, archivos):
    return sorted(p['regla'] for p in al.lint(_arbol(tmp_path, archivos)))


def test_fg4_en_texto(tmp_path):
    assert _reglas(tmp_path, {'static/css/x.css': '.hint{color:var(--fg-4)}'}) == ['fg4-texto']
    ok = '.b:disabled{color:var(--fg-4)}\n.c[aria-hidden]{color:var(--fg-4)}\n.d::placeholder{color:var(--fg-4)}\n.e{border-color:var(--fg-4)}'
    assert _reglas(tmp_path / 'ok', {'static/css/x.css': ok}) == []
    assert _reglas(tmp_path / 'inline', {'templates/x.html': '<span style="color:var(--fg-4)">hola</span>'}) == ['fg4-texto']


def test_icono_sin_nombre(tmp_path):
    malo = '<button type="button" class="eu-iconbtn"><i data-lucide="x"></i></button><a href="/"><svg><path/></svg></a>'
    assert _reglas(tmp_path, {'templates/x.html': malo}) == ['icono-sin-nombre', 'icono-sin-nombre']
    bueno = ('<button type="button" aria-label="Cerrar"><i data-lucide="x"></i></button>'
             '<a href="/" title="Inicio"><i data-lucide="house"></i></a><button><i data-lucide="x"></i>Cerrar</button>')
    assert _reglas(tmp_path / 'ok', {'templates/x.html': bueno}) == []


def test_campo_sin_label(tmp_path):
    assert _reglas(tmp_path, {'templates/x.html': '<input class="eu-input" id="q">'}) == ['campo-sin-label']
    bueno = ('<label for="q">Q</label><input id="q"><input aria-label="B"><label>Nota <textarea></textarea></label>'
             '<input type="hidden" name="t"><select aria-labelledby="s-t"></select>')
    assert _reglas(tmp_path / 'ok', {'templates/x.html': bueno}) == []


def test_outline_sin_foco(tmp_path):
    assert _reglas(tmp_path, {'static/css/x.css': '.in{outline:none}'}) == ['outline-sin-foco']
    bueno = '.in{outline:none}\n.in:focus-visible{outline:2px solid var(--border-focus)}'
    assert _reglas(tmp_path / 'ok', {'static/css/x.css': bueno}) == []


def test_onclick_img_y_h1(tmp_path):
    assert _reglas(tmp_path, {'templates/x.html': '<div onclick="f()">x</div>'}) == ['onclick-sin-rol']
    assert _reglas(tmp_path / 'b', {'templates/x.html': '<div role="button" tabindex="0" onclick="f()">x</div>'}) == []
    assert _reglas(tmp_path / 'c', {'templates/x.html': '<img src="a.png">'}) == ['img-sin-alt']
    assert _reglas(tmp_path / 'd', {'templates/x.html': '<img src="a.png" alt="">'}) == []
    pagina = '{% extends "eu/layout_sub.html" %}{{ ui.page_head() }}{% include "p/_parte.html" %}'
    assert _reglas(tmp_path / 'e', {'templates/p/index.html': pagina, 'templates/p/_parte.html': '<h1>Otra</h1>'}) == ['h1-multiple']
    assert _reglas(tmp_path / 'f', {'templates/p/index.html': pagina, 'templates/p/_parte.html': '<h2>Sección</h2>'}) == []


def test_linea_base_por_huella(tmp_path):
    raiz = _arbol(tmp_path, {'templates/x.html': '<img src="a.png">\n'})
    base = tmp_path / 'base.json'
    al.guardar_baseline(al.lint(raiz), str(base))
    conocidos = al.cargar_baseline(str(base))
    _arbol(tmp_path, {'templates/x.html': '\n\n\n<img src="a.png">\n'})          # moverlo no es nuevo
    assert al.nuevos(al.lint(raiz), conocidos) == []
    _arbol(tmp_path, {'templates/x.html': '<img src="a.png">\n<img src="a.png">\n'})   # una copia sí
    assert len(al.nuevos(al.lint(raiz), conocidos)) == 1
    d = json.loads(base.read_text(encoding='utf-8'))
    assert d['total'] == 1 and d['por_modulo'] == {'x': 1}


def test_boton_nuevo_de_solo_icono_hace_fallar_pre_deploy(monkeypatch, tmp_path):
    raiz = _arbol(tmp_path, {'templates/x.html': '<button type="button"><i data-lucide="trash-2"></i></button>'})
    real = al.lint
    monkeypatch.setattr(al, 'lint', lambda raiz_=None: real(raiz))
    monkeypatch.setattr(al, 'cargar_baseline', lambda ruta=None: al.Counter())
    import pre_deploy_check as pdc
    errs = pdc._check_a11y()
    assert len(errs) == 1 and 'icono-sin-nombre' in errs[0] and 'templates/x.html:1' in errs[0]


def test_el_repo_no_tiene_problemas_nuevos():
    assert al.nuevos(al.lint()) == []
