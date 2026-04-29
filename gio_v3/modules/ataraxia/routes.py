from flask import Blueprint, render_template, request, jsonify
from datetime import date, timedelta, datetime
import os
from database import get_db
from data import ACTIVITIES
from utils import today_str
import modules.gamification.engine as engine

ataraxia_bp = Blueprint('ataraxia', __name__, template_folder='../../templates')

# ── Bloque display labels (from ACTIVITIES dict) ──────────────────────────────
BLOQUE_LABELS = {k: v["label"] for k, v in ACTIVITIES.items() if v.get("weekend")}

# ── Reference horarios ────────────────────────────────────────────────────────
HORARIOS = {
    "sat_arranque":   "9:30 – 9:50",
    "sat_limpieza":   "9:50 – 10:55",
    "sat_transicion": "10:55 – 11:00",
    "sat_jugos_r":    "flexible",
    "sat_ensayo":     "11:00 – 1:00pm",
    "sat_gym":        "1:30 – 3:15pm",
    "sat_ropa":       "3:30 – 3:50pm",
    "sat_cierre":     "5:45 – 6:00pm",
    "sun_arranque":   "10:00 – 10:20",
    "sun_gym_r":      "10:20 – 12:20",
    "sun_comidas_r":  "12:20 – 1:00pm",
    "sun_planchar_r": "1:00 – 1:20pm",
    "sun_finanzas":   "3:30 – 4:10pm",
    "sun_planeacion": "4:10 – 5:00pm",
    "sun_prioridades": "dentro de planeación",
    "sun_jugos_r":    "dentro de mañana",
    "sun_cargas":     "5:00 – 5:15pm",
    "sun_cierre":     "5:45 – 6:00pm",
}

# ── Bloque icons ──────────────────────────────────────────────────────────────
BLOQUE_ICONS = {
    "sat_bloque1": "🧹", "sat_bloque2": "🎸", "sat_bloque3": "🏋️",
    "sun_reflexion": "🧠", "sun_comidas": "🥗", "sun_planchar": "👔",
    "sun_diseno": "💰", "sun_jugos": "🥤",
}


# ── Semana ID — starts Saturday ───────────────────────────────────────────────

def get_semana_id():
    hoy = date.today()
    dias_desde_sabado = (hoy.weekday() - 5) % 7
    sabado = hoy - timedelta(days=dias_desde_sabado)
    return sabado.isoformat()


# ── Data builder ──────────────────────────────────────────────────────────────

def _build_rutina(dia, semana_id):
    with get_db() as db:
        # Distinct bloques in order
        bloque_rows = db.execute("""
            SELECT bloque_id, MIN(orden) as min_orden
            FROM rutina_bloques WHERE dia=?
            GROUP BY bloque_id ORDER BY min_orden
        """, (dia,)).fetchall()

        bloques = []
        for br in bloque_rows:
            bid = br["bloque_id"]
            tareas = [dict(t) for t in db.execute(
                "SELECT * FROM rutina_bloques WHERE dia=? AND bloque_id=? ORDER BY orden",
                (dia, bid)
            ).fetchall()]

            task_ids = [t["id"] for t in tareas]
            done_ids = set()
            if task_ids:
                ph = ",".join("?" * len(task_ids))
                done_rows = db.execute(
                    f"SELECT bloque_id FROM rutina_progreso WHERE bloque_id IN ({ph}) AND semana_id=? AND completado=1",
                    task_ids + [semana_id]
                ).fetchall()
                done_ids = {r["bloque_id"] for r in done_rows}

            req_ids = {t["id"] for t in tareas if not t["opcional"]}
            bloque_done   = req_ids.issubset(done_ids) if req_ids else False
            total_duracion = sum(t["duracion_min"] for t in tareas if not t["opcional"])

            bloques.append({
                "bloque_id":      bid,
                "label":          BLOQUE_LABELS.get(bid, bid),
                "icon":           BLOQUE_ICONS.get(bid, "🔹"),
                "tareas":         tareas,
                "done_ids":       list(done_ids),
                "bloque_done":    bloque_done,
                "required_count": len(req_ids),
                "done_count":     len(done_ids & req_ids),
                "total_duracion": total_duracion,
                "xp_total":       sum(t["xp"] for t in tareas if not t["opcional"]),
                "ec_total":       sum(t["ec"] for t in tareas if not t["opcional"]),
            })

        # Global progress (required tasks only)
        all_req = db.execute(
            "SELECT id FROM rutina_bloques WHERE dia=? AND opcional=0", (dia,)
        ).fetchall()
        all_req_ids = [r["id"] for r in all_req]
        all_done = 0
        if all_req_ids:
            ph = ",".join("?" * len(all_req_ids))
            all_done = db.execute(
                f"SELECT COUNT(*) as c FROM rutina_progreso WHERE bloque_id IN ({ph}) AND semana_id=? AND completado=1",
                all_req_ids + [semana_id]
            ).fetchone()["c"]

    total = len(all_req_ids)
    return {
        "bloques": bloques,
        "total":   total,
        "done":    all_done,
        "pct":     int(all_done / total * 100) if total else 0,
        "complete": all_done >= total and total > 0,
    }


def _get_combo_status(semana_id):
    hoy = date.today()
    dias_desde_sabado = (hoy.weekday() - 5) % 7
    sat_date = (hoy - timedelta(days=dias_desde_sabado)).isoformat()
    sun_date = (hoy - timedelta(days=dias_desde_sabado - 1)).isoformat()
    with get_db() as db:
        sat_combo = bool(db.execute(
            "SELECT id FROM xp_ledger WHERE description='Combo: Sábado Completo' AND date=?", (sat_date,)
        ).fetchone())
        sun_combo = bool(db.execute(
            "SELECT id FROM xp_ledger WHERE description='Combo: Domingo Completo' AND date=?", (sun_date,)
        ).fetchone())
    return sat_combo, sun_combo


# ── Routes ────────────────────────────────────────────────────────────────────

@ataraxia_bp.route('/')
def index():
    semana_id = get_semana_id()
    dow = date.today().weekday()
    default_dia = "domingo" if dow == 6 else "sabado"
    dia = request.args.get('dia', default_dia)

    sabado_data  = _build_rutina("sabado",  semana_id)
    domingo_data = _build_rutina("domingo", semana_id)
    sat_combo, sun_combo = _get_combo_status(semana_id)

    return render_template('ataraxia/index.html',
        dia          = dia,
        semana_id    = semana_id,
        sabado       = sabado_data,
        domingo      = domingo_data,
        horarios     = HORARIOS,
        bloque_labels= BLOQUE_LABELS,
        sat_combo    = sat_combo,
        sun_combo    = sun_combo,
        is_weekend   = dow in (5, 6),
        today        = date.today().isoformat(),
    )


@ataraxia_bp.route('/api/rutina/<dia>')
def get_rutina(dia):
    if dia not in ('sabado', 'domingo'):
        return jsonify({"error": "invalid"}), 400
    semana_id = get_semana_id()
    return jsonify(_build_rutina(dia, semana_id))


@ataraxia_bp.route('/api/rutina/check', methods=['POST'])
def check_tarea():
    data      = request.json or {}
    sub_id    = data.get('bloque_id')
    tiempo_seg = int(data.get('tiempo_seg') or 0)
    semana_id = get_semana_id()
    now       = datetime.now().isoformat()

    with get_db() as db:
        tarea = db.execute("SELECT * FROM rutina_bloques WHERE id=?", (sub_id,)).fetchone()
    if not tarea:
        return jsonify({"error": "not found"}), 404
    tarea = dict(tarea)
    parent_bloque = tarea["bloque_id"]

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM rutina_progreso WHERE bloque_id=? AND semana_id=?", (sub_id, semana_id)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE rutina_progreso SET completado=1, completado_at=?, tiempo_real_seg=? WHERE bloque_id=? AND semana_id=?",
                (now, tiempo_seg, sub_id, semana_id)
            )
        else:
            db.execute(
                "INSERT INTO rutina_progreso (bloque_id, semana_id, completado, completado_at, tiempo_real_seg) VALUES (?,?,1,?,?)",
                (sub_id, semana_id, now, tiempo_seg)
            )
        db.commit()

        # Check if parent bloque is now complete
        req = db.execute(
            "SELECT id FROM rutina_bloques WHERE bloque_id=? AND opcional=0", (parent_bloque,)
        ).fetchall()
        req_ids = [r["id"] for r in req]
        done_ids = set()
        if req_ids:
            ph = ",".join("?" * len(req_ids))
            done_rows = db.execute(
                f"SELECT bloque_id FROM rutina_progreso WHERE bloque_id IN ({ph}) AND semana_id=? AND completado=1",
                req_ids + [semana_id]
            ).fetchall()
            done_ids = {r["bloque_id"] for r in done_rows}
        bloque_complete = set(req_ids).issubset(done_ids) if req_ids else False

    gam = None
    if tarea["tier"] != "micro" or bloque_complete:
        gam = engine.process_rutina_check(
            sub_key   = sub_id,
            xp        = tarea["xp"] if tarea["tier"] != "micro" else 0,
            ec        = tarea["ec"] if tarea["tier"] != "micro" else 0,
            cat       = tarea.get("categoria") or "",
            bloque_id = parent_bloque if bloque_complete else None,
        )

    rutina = _build_rutina(tarea["dia"], semana_id)
    return jsonify({"ok": True, "bloque_complete": bloque_complete, "gam": gam, "rutina": rutina})


@ataraxia_bp.route('/api/rutina/uncheck', methods=['POST'])
def uncheck_tarea():
    data   = request.json or {}
    sub_id = data.get('bloque_id')
    semana_id = get_semana_id()

    with get_db() as db:
        tarea = db.execute("SELECT * FROM rutina_bloques WHERE id=?", (sub_id,)).fetchone()
    if not tarea:
        return jsonify({"error": "not found"}), 404
    tarea = dict(tarea)

    with get_db() as db:
        db.execute(
            "UPDATE rutina_progreso SET completado=0, completado_at=NULL, tiempo_real_seg=NULL "
            "WHERE bloque_id=? AND semana_id=?",
            (sub_id, semana_id)
        )
        db.commit()

    gam = engine.process_rutina_uncheck(
        sub_key   = sub_id,
        bloque_id = tarea["bloque_id"],
    )
    rutina = _build_rutina(tarea["dia"], semana_id)
    return jsonify({"ok": True, "gam": gam, "rutina": rutina})


@ataraxia_bp.route('/api/rutina/finde/status')
def finde_status():
    semana_id = get_semana_id()
    sat_combo, sun_combo = _get_combo_status(semana_id)
    return jsonify({
        "semana_id":      semana_id,
        "sabado":         _build_rutina("sabado",  semana_id),
        "domingo":        _build_rutina("domingo", semana_id),
        "sat_combo":      sat_combo,
        "sun_combo":      sun_combo,
        "finde_perfecto": sat_combo and sun_combo,
    })


@ataraxia_bp.route('/api/rutina/reset', methods=['POST'])
def reset_rutina():
    token    = (request.json or {}).get('token')
    expected = os.environ.get('RESET_TOKEN', 'ataraxia-reset-2026')
    if token != expected:
        return jsonify({"error": "unauthorized"}), 401
    semana_id = get_semana_id()
    with get_db() as db:
        db.execute("DELETE FROM rutina_progreso WHERE semana_id=?", (semana_id,))
        db.commit()
    return jsonify({"ok": True, "semana_id": semana_id})
