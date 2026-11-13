"""
capturas.py — Capturas antes/después de cada paquete (solo desarrollo).

    python scripts/capturas.py antes
    python scripts/capturas.py despues-plantas
    python scripts/capturas.py --comparar antes despues-plantas
    python scripts/capturas.py antes --db ruta/a/copia.db     # copia de TU base (nunca producción)
    python scripts/capturas.py antes --rutas / /plantas/       # solo algunas rutas

Arranca la app en un puerto libre con una base temporal: por defecto la base
de ejemplo (esquema completo + datos de muestra de modules/demo.py); con
--db, una COPIA del archivo indicado. Inicia sesión con la cookie de
sesión firmada (app_ok + fin_ok) y recorre RUTAS en escritorio (1440×900) y
móvil (390×844, deviceScaleFactor 2). Espera networkidle y oculta fechas y
horas (.js-now, [data-capture-hide]) y las animaciones para que las corridas
sean comparables.

Guarda en capturas/<etiqueta>/<tamaño>/<ruta>.png (capturas/ está en
.gitignore). Una ruta que responde 404 se anota como «no existe» y la
corrida sigue.

--comparar a b genera capturas/comparar-a-b.html: por ruta, las dos
imágenes y una tercera con la diferencia resaltada (Pillow ImageChops),
ordenadas de mayor a menor cambio; las que no cambiaron, al final y plegadas.

Requiere (solo desarrollo): pip install playwright pillow. Usa el Chromium
de Playwright; si no lo encuentra, CHROMIUM_PATH o /opt/pw-browsers/chromium.
No está conectado a pre_deploy_check.
"""
import argparse
import html
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(AQUI)
SALIDA = os.path.join(APP, 'capturas')

RUTAS = """
/  /actividades/  /gtd/  /ataraxia/  /ataraxia/revision
/finanzas/  /finanzas/presupuesto/  /finanzas/estados/  /finanzas/inversiones/  /finanzas/consumo/
/bienestar/  /bienestar/salud/  /bienestar/nutricion/  /bienestar/futbol/  /recetas/
/paideia/  /idiomas/  /eurythmia/  /guardarropa/  /guardarropa/wishlist/
/viajes/  /harma/  /plantas/  /logros/  /recompensas/  /perfil/  /perfil/?sec=ajustes
/_ui
""".split()

TAMANOS = {
    'escritorio': {'viewport': {'width': 1440, 'height': 900}},
    'movil': {'viewport': {'width': 390, 'height': 844}, 'device_scale_factor': 2, 'is_mobile': True, 'has_touch': True},
}

CSS_CAPTURA = """
.js-now,[data-capture-hide]{visibility:hidden!important}
*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}
#eu-toasts{display:none!important}
"""


def slug(ruta):
    s = re.sub(r'[^a-z0-9]+', '-', ruta.lower()).strip('-')
    return s or 'inicio'


# ── App con base temporal ─────────────────────────────────────────────────────

def preparar_base(origen):
    """Ruta a una base temporal: copia de `origen` o la base de ejemplo."""
    tmp = tempfile.mkdtemp(prefix='eu-capturas-')
    destino = os.path.join(tmp, 'pipeline.db')
    os.environ.pop('TURSO_DATABASE_URL', None)
    os.environ.pop('TURSO_AUTH_TOKEN', None)
    os.environ['DATABASE_PATH'] = destino
    os.environ.setdefault('SECRET_KEY', 'capturas-dev')
    os.environ['FLASK_ENV'] = 'development'           # /_ui solo existe en desarrollo
    if origen:
        prod = os.environ.get('RAILWAY_ENVIRONMENT') or '/data/' in os.path.abspath(origen)
        if prod:
            sys.exit('No se usa la base de producción: pasa una copia local.')
        shutil.copyfile(origen, destino)
    sys.path.insert(0, APP)
    os.chdir(APP)
    import database
    database.SEMBRAR_DATOS_USUARIO = False
    database.init_db()
    if not origen:
        from modules import demo
        from utils import today_date
        with database.get_db() as db:
            demo._seed(db, today_date())
            db.commit()
    return destino


def arrancar_app():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    from werkzeug.serving import make_server
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        puerto = s.getsockname()[1]
    srv = make_server('127.0.0.1', puerto, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from flask.sessions import SecureCookieSessionInterface
    cookie = SecureCookieSessionInterface().get_signing_serializer(app).dumps({'app_ok': True, 'fin_ok': True})
    return srv, f'http://127.0.0.1:{puerto}', cookie


def lanzar(pw):
    for ruta in (None, os.environ.get('CHROMIUM_PATH'), '/opt/pw-browsers/chromium'):
        try:
            return pw.chromium.launch(executable_path=ruta) if ruta else pw.chromium.launch()
        except Exception as e:                      # sin el Chromium de esta versión de Playwright
            ultimo = e
    raise ultimo


# ── Capturar ──────────────────────────────────────────────────────────────────

def capturar(etiqueta, origen=None, rutas=None):
    from playwright.sync_api import sync_playwright
    preparar_base(origen)
    srv, base, cookie = arrancar_app()
    rutas = rutas or RUTAS
    faltan = []
    try:
        with sync_playwright() as pw:
            nav = lanzar(pw)
            for tam, opts in TAMANOS.items():
                carpeta = os.path.join(SALIDA, etiqueta, tam)
                os.makedirs(carpeta, exist_ok=True)
                ctx = nav.new_context(**opts)
                ctx.add_cookies([{'name': 'session', 'value': cookie, 'url': base}])
                ctx.add_init_script("try{localStorage.setItem('eu-theme','dark')}catch(e){}")
                page = ctx.new_page()
                for r in rutas:
                    resp = page.goto(base + r, wait_until='networkidle')
                    if not resp or resp.status == 404:
                        if tam == 'escritorio':
                            faltan.append(r)
                        print(f'  {tam:10} {r:28} no existe')
                        continue
                    page.add_style_tag(content=CSS_CAPTURA)
                    page.wait_for_timeout(250)
                    page.screenshot(path=os.path.join(carpeta, slug(r) + '.png'), full_page=True)
                    print(f'  {tam:10} {r:28} {resp.status}')
                ctx.close()
            nav.close()
    finally:
        srv.shutdown()
    with open(os.path.join(SALIDA, etiqueta, 'no-existe.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(faltan))
    print(f'Listo: {os.path.join(SALIDA, etiqueta)}' + (f' · no existen: {", ".join(faltan)}' if faltan else ''))


# ── Comparar ──────────────────────────────────────────────────────────────────

def diferencia(pa, pb, salida):
    """(fracción de píxeles distintos, ruta de la imagen de diferencia)."""
    from PIL import Image, ImageChops
    a, b = Image.open(pa).convert('RGB'), Image.open(pb).convert('RGB')
    w, h = max(a.width, b.width), max(a.height, b.height)
    lienzo = lambda im: (lambda c: (c.paste(im, (0, 0)), c)[1])(Image.new('RGB', (w, h), (255, 0, 255)))
    a, b = lienzo(a), lienzo(b)
    d = ImageChops.difference(a, b).convert('L').point(lambda v: 255 if v > 24 else 0)
    cambio = sum(d.histogram()[255:]) / float(w * h)
    resaltada = Image.blend(b, Image.new('RGB', (w, h), (0, 0, 0)), 0.6)
    resaltada.paste(Image.new('RGB', (w, h), (255, 40, 80)), mask=d)
    resaltada.save(salida)
    return cambio, salida


def comparar(a, b):
    out_dir = os.path.join(SALIDA, f'comparar-{a}-{b}')
    filas = []
    for tam in TAMANOS:
        da, db_ = os.path.join(SALIDA, a, tam), os.path.join(SALIDA, b, tam)
        nombres = sorted(set(os.listdir(da) if os.path.isdir(da) else []) | set(os.listdir(db_) if os.path.isdir(db_) else []))
        os.makedirs(os.path.join(out_dir, tam), exist_ok=True)
        for n in nombres:
            pa, pb = os.path.join(da, n), os.path.join(db_, n)
            if os.path.exists(pa) and os.path.exists(pb):
                cambio, dif = diferencia(pa, pb, os.path.join(out_dir, tam, n))
            else:
                cambio, dif = 1.0, None
            filas.append({'tam': tam, 'n': n[:-4], 'cambio': cambio,
                          'a': pa if os.path.exists(pa) else None, 'b': pb if os.path.exists(pb) else None, 'dif': dif})
    filas.sort(key=lambda f: -f['cambio'])
    rel = lambda p: os.path.relpath(p, SALIDA) if p else None
    img = lambda p, alt: f'<img src="{html.escape(rel(p))}" alt="{html.escape(alt)}" loading="lazy">' if p else '<p class="na">no existe</p>'

    def bloque(f):
        return (f'<section><h2>{html.escape(f["n"])} <small>{f["tam"]} · {f["cambio"] * 100:.2f} % distinto</small></h2>'
                f'<div class="row"><figure>{img(f["a"], a)}<figcaption>{html.escape(a)}</figcaption></figure>'
                f'<figure>{img(f["b"], b)}<figcaption>{html.escape(b)}</figcaption></figure>'
                f'<figure>{img(f["dif"], "diferencia")}<figcaption>diferencia</figcaption></figure></div></section>')
    UMBRAL = 0.0001                     # menos de 1 px por cada 10 000: ruido de antialiasing
    cambiadas = [f for f in filas if f['cambio'] > UMBRAL]
    iguales = [f for f in filas if f['cambio'] <= UMBRAL]
    doc = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Comparar {html.escape(a)} · {html.escape(b)}</title>
<style>body{{margin:0;padding:24px;background:#09070F;color:#F2EDE0;font:14px system-ui}}h1{{font-weight:600}}
section{{margin:0 0 32px}}h2{{font-size:16px;margin:0 0 8px}}small{{color:#C2B69E;font-weight:400}}
.row{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}figure{{margin:0}}img{{width:100%;border:1px solid #333}}
figcaption{{color:#C2B69E;font-size:12px}}.na{{color:#C2B69E}}details{{margin-top:24px}}</style>
<h1>{html.escape(a)} → {html.escape(b)}</h1><p>{len(cambiadas)} con cambios · {len(iguales)} iguales</p>
{''.join(bloque(f) for f in cambiadas)}
<details><summary>Sin cambios ({len(iguales)})</summary>{''.join(bloque(f) for f in iguales)}</details></html>"""
    destino = os.path.join(SALIDA, f'comparar-{a}-{b}.html')
    with open(destino, 'w', encoding='utf-8') as fh:
        fh.write(doc)
    print(f'Listo: {destino}')
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description='Capturas antes/después')
    ap.add_argument('etiqueta', nargs='?', help='antes | despues-<paquete>')
    ap.add_argument('--comparar', nargs=2, metavar=('A', 'B'))
    ap.add_argument('--db', help='copia local de tu base (nunca la de producción)')
    ap.add_argument('--rutas', nargs='+')
    args = ap.parse_args(argv)
    if args.comparar:
        return comparar(*args.comparar)
    if not args.etiqueta or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', args.etiqueta):
        ap.error('etiqueta: antes o despues-<paquete> (minúsculas, números y guiones)')
    capturar(args.etiqueta, args.db, args.rutas)


if __name__ == '__main__':
    main()
