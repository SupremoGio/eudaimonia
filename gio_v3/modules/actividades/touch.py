"""Marcar un touch de Acta Diurna desde otro módulo (helper compartido).

Es la misma ruta que un check manual en /actividades/api/activity/log: una
fila en activity_logs (activity_key, date, pts) y engine.process_activity con
su XP/EC. Si el touch ya está marcado hoy no se duplica (devuelve None)."""
from database import get_db
from utils import today_str
import modules.gamification.engine as engine
import modules.actividades.activity_defs as adefs


def marcar_touch(key, pts=None, ec=None):
    """Marca `key` hoy si aún no lo está. `pts` reemplaza los del def (p. ej.
    XP variable por aciertos). Devuelve el resultado del engine (gam), o None
    si ya estaba marcado o el def no existe / no está activo."""
    act = adefs.get_by_key(key)
    if not act or not act['active']:
        return None
    today = today_str()
    pts = act['pts'] if pts is None else pts
    with get_db() as db:
        if db.execute("SELECT id FROM activity_logs WHERE activity_key=? AND date=?", (key, today)).fetchone():
            return None
        log_id = db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                            (key, today, pts)).lastrowid
        db.commit()
    if pts <= 0:
        return {'xp': 0, 'ec': 0, 'log_id': log_id}
    gam = engine.process_activity(key, pts, act['cat'], log_id, ec=ec)
    gam['log_id'] = log_id
    return gam


def touches_hoy(pillar):
    """{hechos, total} de los touches del pilar visibles en Acta hoy."""
    hoy = today_str()
    items = [it for sess, lst in adefs.get_active_grouped().items() if sess != 'ocasional' for it in lst
             if it.get('pillar') == pillar and it['type'] == 'touch']
    keys = sorted({it['key'] for it in items})
    if not keys:
        return {'hechos': 0, 'total': 0}
    with get_db() as db:
        n = db.execute(f"SELECT COUNT(DISTINCT activity_key) c FROM activity_logs WHERE date=? "
                       f"AND activity_key IN ({','.join('?' * len(keys))})", (hoy, *keys)).fetchone()['c']
    return {'hechos': n, 'total': len(keys)}
