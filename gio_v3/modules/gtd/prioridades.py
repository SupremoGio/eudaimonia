"""Prioridades del día = tareas de Hoy con estrella (handoff Praxis v2, D3).

Las 3 prioridades que Acta Diurna muestra y premia son tareas de Praxis con
`gtd_tasks.prioridad_dia = hoy`. Se escriben una vez y completarlas en Acta o
en Praxis es la misma acción (`completar_tarea`). El bono «Prioridades x3» se
paga una sola vez al día (fila `priority_bonus` en activity_logs).

La tabla `priorities` queda como entrada heredada: lo que haya ahí para hoy
(escrito a mano antes de esta versión, o sembrado por el ritual semanal de
Ataraxia) se convierte en tareas con estrella al abrir Acta o Praxis
(`materializar`), sin duplicar.
"""
from datetime import datetime, date, timedelta

from database import get_db, get_gtd_stats
from utils import today_str, today_date
import modules.gamification.engine as engine

MAX_PRIORIDADES = 3
MAX_SEMANA = 3


# ── Prioridades de la semana (handoff Ataraxia v2, Sprint 4) ──────────────────
# El domingo, en Ataraxia, se eligen con estrella hasta 3 tareas de «Esta
# semana» de Praxis (gtd_tasks.prioridad_semana = semana_id del ciclo, el
# sábado). Gobiernan la semana Lun-Dom siguiente: cada día de esa semana pasan
# solas a Hoy con estrella (materializar), así Acta las muestra y premia.

def semana_eleccion(d=None):
    """semana_id (sábado) del fin de semana en curso: donde se eligen."""
    d = d or today_date()
    return (d - timedelta(days=(d.weekday() - 5) % 7)).isoformat()


def semana_vigente(d=None):
    """semana_id cuyas prioridades gobiernan el día d: el sábado previo al
    lunes de la semana de d."""
    d = d or today_date()
    lunes = d - timedelta(days=d.weekday())
    return (lunes - timedelta(days=2)).isoformat()


def opciones_semana(db, semana_id):
    """Lo que se puede elegir: tareas abiertas de «Esta semana» más las ya
    elegidas para esa semana (aunque se hayan movido a Hoy)."""
    return [{"id": r["id"], "title": r["title"], "on": r["prioridad_semana"] == semana_id} for r in db.execute(
        """SELECT id, title, prioridad_semana FROM gtd_tasks
           WHERE completado=0 AND (cuadrante='semana' OR prioridad_semana=?)
           ORDER BY (prioridad_semana=?) DESC, fecha_limite IS NULL, fecha_limite, id""",
        (semana_id, semana_id))]


def _n_semana(db, semana_id):
    return db.execute("SELECT COUNT(*) FROM gtd_tasks WHERE prioridad_semana=?", (semana_id,)).fetchone()[0]


def alternar_semana(db, tid, semana_id):
    """Pone o quita la estrella de la semana. (ok, estado|mensaje, http)."""
    t = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (tid,)).fetchone()
    if not t:
        return False, "not found", 404
    if t["prioridad_semana"] == semana_id:
        db.execute("UPDATE gtd_tasks SET prioridad_semana=NULL WHERE id=?", (tid,))
        return True, False, 200
    if t["completado"]:
        return False, "Esa tarea ya está completada.", 400
    if _n_semana(db, semana_id) >= MAX_SEMANA:
        return False, "Ya elegiste 3 prioridades para la semana. Quita una estrella primero.", 409
    db.execute("UPDATE gtd_tasks SET prioridad_semana=? WHERE id=?", (semana_id, tid))
    return True, True, 200


def crear_prioridad_semana(db, texto, semana_id):
    """Nueva tarea en «Esta semana» ya elegida. None si ya hay 3."""
    if _n_semana(db, semana_id) >= MAX_SEMANA:
        return None
    now = datetime.now().isoformat()
    db.execute(
        """INSERT INTO gtd_tasks
           (title, tipo, completado, status, importante, urgente, cuadrante, points, created_at, actualizado_en, prioridad_semana)
           VALUES (?, 'tarea', 0, 'inbox', 1, 0, 'semana', 4, ?, ?, ?)""", (texto, now, now, semana_id))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def prioridades_hoy(db, today=None):
    """Tareas con estrella hoy, en el formato {id, text, done} que usa Acta."""
    today = today or today_str()
    return [{"id": r["id"], "text": r["title"], "done": bool(r["completado"])} for r in db.execute(
        "SELECT id, title, completado FROM gtd_tasks WHERE prioridad_dia=? ORDER BY id", (today,))]


def _n_estrellas(db, today):
    return db.execute("SELECT COUNT(*) FROM gtd_tasks WHERE prioridad_dia=?", (today,)).fetchone()[0]


def crear_prioridad(db, texto, today=None):
    """Nueva tarea en Hoy (urgente e importante) con estrella. None si ya hay 3."""
    today = today or today_str()
    if _n_estrellas(db, today) >= MAX_PRIORIDADES:
        return None
    now = datetime.now().isoformat()
    db.execute(
        """INSERT INTO gtd_tasks
           (title, tipo, completado, status, importante, urgente, cuadrante, points, created_at, actualizado_en, prioridad_dia)
           VALUES (?, 'tarea', 0, 'inbox', 1, 1, 'hoy', 4, ?, ?, ?)""", (texto, now, now, today))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def alternar_estrella(db, tid, today=None):
    """Pone o quita la estrella. Devuelve (ok, estado|mensaje, http)."""
    today = today or today_str()
    t = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (tid,)).fetchone()
    if not t:
        return False, "not found", 404
    if t["prioridad_dia"] == today:
        db.execute("UPDATE gtd_tasks SET prioridad_dia=NULL WHERE id=?", (tid,))
        return True, False, 200
    if t["completado"] or t["cuadrante"] != "hoy":
        return False, "Solo las tareas pendientes de Hoy pueden ser prioridad.", 400
    if _n_estrellas(db, today) >= MAX_PRIORIDADES:
        return False, "Ya tienes 3 prioridades hoy. Quita una estrella primero.", 409
    db.execute("UPDATE gtd_tasks SET prioridad_dia=? WHERE id=?", (today, tid))
    return True, True, 200


def materializar(db, today=None):
    """Convierte las filas de `priorities` de hoy aún sin tarea en tareas de
    Hoy con estrella. Si ya hay una tarea abierta con ese título, solo se le
    pone la estrella. Idempotente: cada fila guarda su gtd_task_id (-1 si no
    cupo porque ya había 3 estrellas)."""
    today = today or today_str()
    now = datetime.now().isoformat()
    n = _materializar_semana(db, today, now)
    rows = db.execute(
        "SELECT id, text, done FROM priorities WHERE date=? AND gtd_task_id IS NULL ORDER BY id", (today,)).fetchall()
    if not rows:
        return n
    for r in rows:
        txt = (r["text"] or "").strip()
        tid = -1
        if txt:
            ya = db.execute(
                "SELECT id, prioridad_dia FROM gtd_tasks WHERE completado=0 AND lower(trim(title))=lower(?) ORDER BY id DESC LIMIT 1",
                (txt,)).fetchone()
            if ya and ya["prioridad_dia"] == today:
                tid = ya["id"]
            elif _n_estrellas(db, today) < MAX_PRIORIDADES:
                if ya:
                    tid = ya["id"]
                    db.execute("UPDATE gtd_tasks SET prioridad_dia=?, importante=1, urgente=1, cuadrante='hoy', actualizado_en=? WHERE id=?",
                               (today, now, tid))
                else:
                    tid = crear_prioridad(db, txt, today)
                if r["done"]:
                    db.execute("UPDATE gtd_tasks SET completado=1, fecha_completado=?, completed_at=?, status='done' WHERE id=?",
                               (today, today, tid))
                n += 1
        db.execute("UPDATE priorities SET gtd_task_id=? WHERE id=?", (tid, r["id"]))
    db.commit()
    return n


def _materializar_semana(db, today, now):
    """Las prioridades de la semana vigente pasan a Hoy con estrella, una vez
    al día (prioridad_semana_dia): si se les quita la estrella ese día no
    vuelven hasta el siguiente. Respeta el máximo de 3 estrellas."""
    vig = semana_vigente(date.fromisoformat(today))
    rows = db.execute(
        """SELECT id FROM gtd_tasks WHERE prioridad_semana=? AND completado=0
           AND (prioridad_semana_dia IS NULL OR prioridad_semana_dia<>?) ORDER BY id""", (vig, today)).fetchall()
    n = 0
    for r in rows:
        if _n_estrellas(db, today) < MAX_PRIORIDADES:
            db.execute("""UPDATE gtd_tasks SET prioridad_dia=?, importante=1, urgente=1, cuadrante='hoy', actualizado_en=?
                          WHERE id=? AND (prioridad_dia IS NULL OR prioridad_dia<>?)""", (today, now, r["id"], today))
            n += 1
        db.execute("UPDATE gtd_tasks SET prioridad_semana_dia=? WHERE id=?", (today, r["id"]))
    if rows:
        db.commit()
    return n


def _pagar_bono_prioridades(today):
    """Bono «Prioridades x3» una sola vez: 3 estrellas hoy y las 3 hechas."""
    with get_db() as db:
        rows = db.execute("SELECT completado FROM gtd_tasks WHERE prioridad_dia=?", (today,)).fetchall()
        if len(rows) != MAX_PRIORIDADES or not all(r["completado"] for r in rows):
            return None
        if db.execute("SELECT 1 FROM activity_logs WHERE activity_key='priority_bonus' AND date=?", (today,)).fetchone():
            return None
        db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES ('priority_bonus', ?, 5)", (today,))
        db.commit()
    return engine.process_priority_bonus(today)


def completar_tarea(tid):
    """Completa una tarea de Praxis: XP de la tarea, bono de 3 tareas (una vez
    al día) y, si era prioridad, el bono «Prioridades x3» (una vez al día).
    Devuelve (dict, http)."""
    today = today_str()
    now = datetime.now().isoformat()
    with get_db() as db:
        task = db.execute("SELECT * FROM gtd_tasks WHERE id=?", (tid,)).fetchone()
        if not task:
            return {'error': 'not found'}, 404
        if task['completado']:
            return {'error': 'already done'}, 400
        db.execute(
            """UPDATE gtd_tasks
               SET completado=1, fecha_completado=?, status='done', completed_at=?, actualizado_en=?
               WHERE id=?""",
            (today, today, now, tid)
        )
        priority = task['priority'] or 'normal'
        done_count = db.execute(
            "SELECT COUNT(*) as c FROM gtd_tasks WHERE fecha_completado=?", (today,)
        ).fetchone()["c"]
        # Bono de 3 tareas una sola vez al día: borrar una completada y cerrar
        # otra vuelve a dar 3, así que se revisa el ledger antes de pagarlo.
        bonus_paid = db.execute(
            "SELECT 1 FROM xp_ledger WHERE source='bonus' AND date=? AND description LIKE 'Bonus diario GTD%'",
            (today,)
        ).fetchone() is not None
        db.commit()

    # Una sola moneda (D1): el premio es XP del engine; gtd_points_log ya no se escribe.
    gam = engine.process_gtd_task(tid, priority)
    bonus_xp = 0
    if done_count >= 3 and not bonus_paid:
        gam["daily_bonus_gam"] = engine.process_gtd_daily_bonus()
        bonus_xp = gam["daily_bonus_gam"]["xp"]
    prio_gam = _pagar_bono_prioridades(today) if task['prioridad_dia'] == today else None
    if prio_gam:
        gam["priority_bonus_gam"] = prio_gam

    # pts/bonus: deprecados (siempre 0), se mantienen por compatibilidad.
    return {'ok': True, 'xp': gam.get('xp', 0), 'bonus_xp': bonus_xp, 'pts': 0, 'bonus': 0,
            'all3': bool(prio_gam), 'stats': get_gtd_stats(), 'gam': gam}, 200
