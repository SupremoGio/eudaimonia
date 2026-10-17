"""
Alta de las plantas del usuario (fotos que mandó por WhatsApp el 2026-10-06).
Especies identificadas por las fotos; «la Monstera es la chiquita» (esqueje).
Interior/balcón según dónde se tomó cada foto (barandal = balcón).

Se aplica una vez al arrancar (database.py, migration_log). Si ya existe una
planta con el mismo nombre, no la duplica: solo le suma la foto a su línea de
tiempo (y la especie científica si no tenía). Las fotos viven en
alta_2026_10_06/ junto a este archivo; una vez aplicada en producción, este
módulo y esa carpeta se pueden borrar (quedan en el historial de git).
"""
import os
import shutil
import uuid
from datetime import datetime

# «Pon que las regué hoy todas; no riego pata de oso, pata de elefante ni
# monstera aún» (el usuario, 2026-10-06 por la noche).
NO_REGADAS = ('Monstera', 'Pata de oso', 'Pata de elefante')

_DIR_FOTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alta_2026_10_06')
FECHA = '2026-10-06'

# (nombre, especie, especie_cientifica, entorno, dias_riego, meses_trasplante, foto, notas)
PLANTAS = [
    ('Monstera', 'Monstera (esqueje)', 'Monstera deliciosa', 'interior', 6, 12, 'monstera.jpg',
     'Esqueje recién plantado: tierra apenas húmeda, nunca encharcada, hasta que saque hojas nuevas.'),
    ('Oreja de elefante', 'Oreja de elefante', 'Alocasia', 'interior', 6, 12, 'oreja-elefante.jpg', ''),
    ('Pata de oso', 'Pata de oso', 'Cotyledon tomentosa', 'interior', 14, 24, 'pata-de-oso.jpg',
     'Suculenta: regar solo con la tierra seca; no mojar las hojas peludas.'),
    ('Palma areca', 'Palma areca', 'Dypsis lutescens', 'interior', 7, 18, 'palma-areca.jpg', ''),
    ('Pothos', 'Pothos', 'Epipremnum aureum', 'interior', 9, 18, 'pothos.jpg', ''),
    ('Lengua de suegra (interior)', 'Lengua de suegra', 'Dracaena trifasciata', 'interior', 21, 24,
     'lengua-suegra-interior.jpg', ''),
    ('Helecho espárrago', 'Helecho espárrago', 'Asparagus setaceus', 'interior', 5, 12, 'helecho-esparrago.jpg', ''),
    ('Lengua de suegra (balcón)', 'Lengua de suegra', 'Dracaena trifasciata', 'balcon', 18, 24,
     'lengua-suegra-balcon.jpg', ''),
    ('Árbol de la abundancia', 'Árbol de la abundancia', 'Portulacaria afra', 'balcon', 14, 24,
     'arbol-abundancia.jpg', ''),
    ('Pata de elefante', 'Pata de elefante', 'Beaucarnea recurvata', 'balcon', 18, 24, 'pata-elefante.jpg',
     'Guarda agua en la base: mejor de menos que de más.'),
]


def _norm(s):
    from modules.plantas.care_data import _norm as n
    return n(s)


def aplicar(db, upload_dir):
    """Crea las plantas que falten. Devuelve (creadas, existentes)."""
    os.makedirs(upload_dir, exist_ok=True)
    existentes = {_norm(r['nombre']): r for r in db.execute("SELECT id, nombre, especie_cientifica, last_riego FROM plantas")}
    creadas = ya = 0
    ahora = datetime.now().isoformat()
    for nombre, especie, cient, entorno, dias, meses, foto, notas in PLANTAS:
        src = os.path.join(_DIR_FOTOS, foto)
        filename = None
        if os.path.exists(src):
            filename = uuid.uuid4().hex + '.jpg'
            shutil.copyfile(src, os.path.join(upload_dir, filename))
        previa = existentes.get(_norm(nombre))
        if previa:
            pid = previa['id']
            if not previa['especie_cientifica']:
                db.execute("UPDATE plantas SET especie_cientifica=? WHERE id=?", (cient, pid))
            ya += 1
        else:
            pid = db.execute(
                "INSERT INTO plantas (nombre, especie, especie_cientifica, ubicacion, entorno, dias_riego, "
                "meses_trasplante, notas, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (nombre, especie, cient, '', entorno, dias, meses, notas,
                 f'{FECHA}T21:52:00')).lastrowid
            creadas += 1
        if nombre not in NO_REGADAS and not (previa and (previa['last_riego'] or '') >= FECHA):
            db.execute("INSERT INTO plantas_bitacora (planta_id, tipo, fecha, notas, prev_fecha, created_at) VALUES (?,?,?,?,?,?)",
                       (pid, 'riego', FECHA, 'Registrado al dar de alta', previa['last_riego'] if previa else None, ahora))
            db.execute("UPDATE plantas SET last_riego=?, riego_pospuesto_hasta=NULL WHERE id=?", (FECHA, pid))
        if filename:
            db.execute("INSERT INTO plantas_fotos (planta_id, foto, fecha, nota, created_at) VALUES (?,?,?,?,?)",
                       (pid, filename, FECHA, 'Foto del alta', ahora))
            db.execute("UPDATE plantas SET foto=? WHERE id=?", (filename, pid))
    return creadas, ya


def corregir_monstera(db):
    """La «Monstera» ya existía en producción con sus datos viejos (riego cada
    8 d) y el alta no la pisó. El usuario (2026-10-07): «cambia los datos que
    tú me dijiste de la monstera». Se le ponen los del alta; se conservan su
    ubicación, foto, historial y último riego. La nota se agrega sin borrar
    la suya. Devuelve cuántas filas cambió."""
    nombre, especie, cient, entorno, dias, meses, _foto, nota = PLANTAS[0]
    n = 0
    for r in db.execute("SELECT id, nombre, notas FROM plantas").fetchall():
        if _norm(r['nombre']) != _norm(nombre):
            continue
        notas = r['notas'] or ''
        if nota not in notas:
            notas = f"{notas}\n{nota}".strip() if notas else nota
        db.execute("UPDATE plantas SET especie=?, especie_cientifica=?, entorno=?, dias_riego=?, "
                   "meses_trasplante=?, notas=? WHERE id=?",
                   (especie, cient, entorno, dias, meses, notas[:300], r['id']))
        n += 1
    return n


# El usuario (2026-10-07): «oreja de elefante, palma areca y monstera están
# bajo tratamiento por cochinilla… cada 4 días con neem y jabón potásico»,
# última aplicación hace dos días. Ya lo llevaba como recordatorio
# («JABON POTASICO Y NEEM», cada 4 días): se pasa a Plantas y el recordatorio
# se desactiva para no duplicarlo en el Dashboard.
TRATAMIENTO = (('Oreja de elefante', 'Palma areca', 'Monstera'), 4, '2026-10-04',
               'Cochinilla · neem + jabón potásico')


def tratamiento_cochinilla(db):
    """Devuelve (plantas en tratamiento, recordatorios desactivados)."""
    nombres, cada, ultima, nota = TRATAMIENTO
    objetivo = {_norm(n) for n in nombres}
    ahora = datetime.now().isoformat()
    n = 0
    for r in db.execute("SELECT id, nombre FROM plantas").fetchall():
        if _norm(r['nombre']) not in objetivo:
            continue
        if db.execute("SELECT 1 FROM plantas_cuidados WHERE planta_id=? AND tipo='tratamiento'", (r['id'],)).fetchone():
            db.execute("UPDATE plantas_cuidados SET cada_dias=?, last_fecha=?, nota=? WHERE planta_id=? AND tipo='tratamiento'",
                       (cada, ultima, nota, r['id']))
        else:
            db.execute("INSERT INTO plantas_cuidados (planta_id, tipo, cada_dias, last_fecha, nota, created_at) VALUES (?,?,?,?,?,?)",
                       (r['id'], 'tratamiento', cada, ultima, nota, ahora))
        if not db.execute("SELECT 1 FROM plantas_bitacora WHERE planta_id=? AND tipo='tratamiento' AND fecha=?",
                          (r['id'], ultima)).fetchone():
            db.execute("INSERT INTO plantas_bitacora (planta_id, tipo, fecha, notas, created_at) VALUES (?,?,?,?,?)",
                       (r['id'], 'tratamiento', ultima, nota, ahora))
        n += 1
    rec = db.execute("UPDATE reminders SET is_active=0 WHERE is_active=1 AND UPPER(description) LIKE '%NEEM%'").rowcount
    return n, rec
