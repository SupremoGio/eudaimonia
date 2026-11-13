"""
demo.py — «Ver un ejemplo» (handoff Estados vacíos, Sprint 1).

Un módulo sin su dato base muestra ui.empty(kind='setup') con «Ver un
ejemplo», que abre la misma página con ?demo=1. En ese modo:

  · get_db() apunta (database.DEMO_PATH) a una COPIA TEMPORAL de una base de
    ejemplo: el esquema completo de init_db() más datos fijos de muestra.
    La copia se borra al terminar la petición, así que nada de lo que
    ocurra al pintar la página (siembras, migraciones perezosas) llega a la
    base real ni a Turso.
  · El layout pinta la banda «Ejemplo · nada se guarda» y el fetch global
    no deja salir escrituras (POST/PATCH/DELETE) y agrega demo=1 a las
    lecturas, para que el JS de la página siga viendo los datos de muestra.

La base de ejemplo se construye una vez por proceso (perezosa).
"""
import os
import shutil
import tempfile
import threading
from datetime import timedelta, datetime

from flask import request, g

import database

_LOCK = threading.Lock()
_BASE = None
VERSION = 1


def _seed(db, hoy):
    """Datos fijos de muestra para los módulos con kind='setup'."""
    now = datetime.now().isoformat()
    d = lambda n: (hoy - timedelta(days=n)).isoformat()

    # Harma: un vehículo configurado, kilometraje y servicios recientes
    v = db.execute("SELECT id FROM harma_vehiculo ORDER BY id LIMIT 1").fetchone()
    if v:
        db.execute("""UPDATE harma_vehiculo SET nombre='Golf', marca='Volkswagen', modelo='Golf', anio=2019,
                      km_actual=58200, km_actualizado=? WHERE id=?""", (d(9), v['id']))
    else:
        db.execute("""INSERT INTO harma_vehiculo (nombre, marca, modelo, anio, km_actual, km_actualizado, created_at)
                      VALUES ('Golf','Volkswagen','Golf',2019,58200,?,?)""", (d(9), now))
    for tipo, titulo, km, costo, taller, dias in (
            ('aceite', 'Cambio de aceite y filtro', 52000, 1450, 'Taller Hernández', 150),
            ('llantas', 'Rotación y balanceo', 52000, 600, 'Taller Hernández', 150),
            ('frenos', 'Balatas delanteras', 47800, 2300, 'Agencia VW', 320)):
        db.execute("""INSERT INTO harma_servicios (tipo, titulo, km, costo, taller, fecha, created_at)
                      VALUES (?,?,?,?,?,?,?)""", (tipo, titulo, km, costo, taller, d(dias), now))
    db.execute("UPDATE harma_plan_items SET last_km=52000, last_date=? WHERE cat IN ('motor','fluidos')", (d(150),))
    db.execute("UPDATE harma_plan_items SET last_km=47800, last_date=? WHERE cat NOT IN ('motor','fluidos')", (d(320),))

    # Guardarropa: un armario chico y un outfit
    prendas = [('Camisa Oxford blanca', 'Camisa', '#F2EDE0', 'Blanco', 'Formal'),
               ('Camisa de lino azul', 'Camisa', '#4A6FA5', 'Azul', 'Casual'),
               ('Playera negra', 'Playera', '#1A1627', 'Negro', 'Casual'),
               ('Pantalón chino beige', 'Pantalón', '#C8B38A', 'Beige', 'Casual'),
               ('Jeans índigo', 'Pantalón', '#2E3B55', 'Azul', 'Casual'),
               ('Blazer gris', 'Saco', '#6B6B70', 'Gris', 'Formal'),
               ('Tenis blancos', 'Calzado', '#FFFFFF', 'Blanco', 'Casual'),
               ('Mocasines café', 'Calzado', '#6B4A2B', 'Café', 'Formal')]
    ids = []
    for i, (nombre, cat, hexc, color, oc) in enumerate(prendas):
        ids.append(db.execute("""INSERT INTO wardrobe_items (nombre, categoria, color_hex, color_name, ocasion, veces_usado, ultimo_uso, created_at)
                                 VALUES (?,?,?,?,?,?,?,?)""", (nombre, cat, hexc, color, oc, 3 + i, d(2 + i * 3), now)).lastrowid)
    oid = db.execute("INSERT INTO outfits (nombre, ocasion, rating, veces_usado, created_at) VALUES ('Oficina relajada','Casual',4,2,?)",
                     (now,)).lastrowid
    for pid in (ids[1], ids[3], ids[7]):
        try:
            db.execute("INSERT INTO outfit_items (outfit_id, item_id) VALUES (?,?)", (oid, pid))
        except Exception:
            pass

    # Plantas
    for nombre, especie, ubi, cada, ult in (('Monstera', 'Monstera deliciosa', 'Sala', 7, 3),
                                           ('Pothos', 'Epipremnum aureum', 'Cocina', 6, 6),
                                           ('Lengua de suegra', 'Sansevieria', 'Recámara', 14, 10)):
        db.execute("""INSERT INTO plantas (nombre, especie, ubicacion, dias_riego, last_riego, created_at)
                      VALUES (?,?,?,?,?,?)""", (nombre, especie, ubi, cada, d(ult), now))

    # Eurythmia: sesiones de práctica de las últimas semanas
    for dias, mins, flow in ((1, 45, 4), (3, 30, 3), (6, 60, 5), (9, 30, 3), (13, 45, 4)):
        db.execute("""INSERT INTO eury_sessions (date, min, split_diso, split_paso, split_improv, step, flow, xp, created_at)
                      VALUES (?,?,?,?,?,'',?,0,?)""", (d(dias), mins, mins // 3, mins // 3, mins - 2 * (mins // 3), flow, now))
    db.execute("UPDATE eury_repertoire SET mastery=2, reps=12, last_practiced=? WHERE id IN (SELECT id FROM eury_repertoire ORDER BY id LIMIT 4)", (d(1),))

    # Idiomas: entradas del journal
    for dias, lang, txt in ((1, 'en', 'Today I practiced listening with a podcast about history.'),
                            (2, 'fr', "Aujourd'hui j'ai lu un article sur la cuisine."),
                            (4, 'en', 'I wrote a short summary of the book I am reading.')):
        db.execute("INSERT INTO lang_journal (language, entry_text, entry_date, created_at) VALUES (?,?,?,?)",
                   (lang, txt, d(dias), now))


def base_path():
    """Ruta de la base de ejemplo (la construye la primera vez)."""
    global _BASE
    with _LOCK:
        if _BASE and os.path.exists(_BASE):
            return _BASE
        ruta = os.path.join(tempfile.gettempdir(), f'eu-demo-{os.getpid()}-v{VERSION}.db')
        if os.path.exists(ruta):
            os.remove(ruta)
        tok = database.DEMO_PATH.set(ruta)
        sembrar = database.SEMBRAR_DATOS_USUARIO
        database.SEMBRAR_DATOS_USUARIO = False          # nada de los datos reales del usuario
        try:
            database.init_db()
            from utils import today_date
            with database.get_db() as db:
                _seed(db, today_date())
                db.commit()
        finally:
            database.SEMBRAR_DATOS_USUARIO = sembrar
            database.DEMO_PATH.reset(tok)
        _BASE = ruta
        return ruta


def activo():
    try:
        return bool(g.get('eu_demo'))
    except RuntimeError:
        return False


def init_app(app):
    @app.before_request
    def _demo_on():
        if request.args.get('demo') != '1' or request.method not in ('GET', 'HEAD'):
            return
        fd, copia = tempfile.mkstemp(prefix='eu-demo-req-', suffix='.db')
        os.close(fd)
        shutil.copyfile(base_path(), copia)
        g.eu_demo = True
        g.eu_demo_copia = copia
        g.eu_demo_tok = database.DEMO_PATH.set(copia)

    @app.teardown_request
    def _demo_off(_exc=None):
        tok = g.pop('eu_demo_tok', None)
        if tok is not None:
            database.DEMO_PATH.reset(tok)
        copia = g.pop('eu_demo_copia', None)
        if copia:
            try:
                os.remove(copia)
            except OSError:
                pass

    @app.context_processor
    def _demo_ctx():
        return {'eu_demo': activo()}
