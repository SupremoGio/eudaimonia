from flask import Blueprint, jsonify, request, render_template
from datetime import date, datetime, timedelta
from database import get_db
from utils import today_str, today_date
from modules.gamification.engine import (
    get_gamification_stats, get_level_info, apply_penalty, check_and_unlock,
    get_daily_classification,
)
from modules.gamification.achievements import ACHIEVEMENT_DEFS
from modules.gamification.badges import get_all_badges, check_and_unlock_badges, get_active_perks, BADGE_DEFS
from modules.gamification.icons import lucide_for

gamification_bp = Blueprint('gamification', __name__, template_folder='../../templates')


# ── Stats ─────────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/stats')
def stats():
    return jsonify(get_gamification_stats())


# ── Daily Classification ──────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/classification')
def classification():
    d = request.args.get('date', today_str())
    return jsonify(get_daily_classification(d))


# ── Achievements ──────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/achievements')
def achievements():
    with get_db() as db:
        rows = {r["key"]: dict(r) for r in db.execute(
            "SELECT key, unlocked_at, coins_earned, xp_earned FROM achievements"
        ).fetchall()}

    result = []
    for key, defn in ACHIEVEMENT_DEFS.items():
        unlocked = key in rows and rows[key]["unlocked_at"] is not None
        _icon = defn["icon"] if (not defn["hidden"] or unlocked) else "🔒"
        entry = {
            "key":          key,
            "name":         defn["name"] if (not defn["hidden"] or unlocked) else "???",
            "description":  defn["description"] if (not defn["hidden"] or unlocked) else "Logro oculto — sigue progresando",
            "icon":         _icon,
            "icon_lucide":  lucide_for(_icon),
            "coins":        defn["coins"],
            "xp":           defn["xp"],
            "hidden":       defn["hidden"],
            "unlocked":     unlocked,
            "unlocked_at":  rows[key]["unlocked_at"] if unlocked else None,
        }
        result.append(entry)

    unlocked_count = sum(1 for e in result if e["unlocked"])
    return jsonify({"achievements": result, "unlocked": unlocked_count, "total": len(result)})


# ── Badges ────────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/badges')
def badges():
    all_badges   = get_all_badges()
    for b in all_badges:
        b["icon_lucide"] = lucide_for(b["icon"])
    active_perks = get_active_perks()
    unlocked     = [b for b in all_badges if b["unlocked"]]
    return jsonify({
        "badges":       all_badges,
        "unlocked":     len(unlocked),
        "total":        len(all_badges),
        "active_perks": active_perks,
    })


@gamification_bp.route('/api/gamification/badges/check', methods=['POST'])
def check_badges():
    newly = check_and_unlock_badges()
    return jsonify({"newly_unlocked": newly, "count": len(newly)})


# ── XP / Coins history ────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/history')
def history():
    limit = min(int(request.args.get('limit', 50)), 200)
    with get_db() as db:
        xp_log = db.execute(
            "SELECT amount,source,description,multiplier,date FROM xp_ledger ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        coin_log = db.execute(
            "SELECT amount,source,description,multiplier,date FROM coins_ledger ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return jsonify({
        "xp_log":   [dict(r) for r in xp_log],
        "ec_log":   [dict(r) for r in coin_log],
    })


# ── Multiplier log ────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/multipliers')
def multipliers():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM multiplier_log ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Penalties ─────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/penalty', methods=['POST'])
def penalty():
    data    = request.json or {}
    ptype   = data.get("type", "")
    context = data.get("context", "")
    result  = apply_penalty(ptype, context)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@gamification_bp.route('/api/gamification/penalties')
def penalty_log():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM penalty_log ORDER BY date DESC, id DESC LIMIT 30"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Special Events ────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/events')
def events():
    with get_db() as db:
        rows = db.execute("SELECT * FROM special_events ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@gamification_bp.route('/api/gamification/events/<key>/activate', methods=['POST'])
def activate_event(key):
    data       = request.json or {}
    start_date = data.get("start_date") or today_str()
    end_date   = data.get("end_date")

    with get_db() as db:
        ev = db.execute("SELECT id FROM special_events WHERE key=?", (key,)).fetchone()
        if not ev:
            return jsonify({"error": "event not found"}), 404
        db.execute(
            "UPDATE special_events SET is_active=1, start_date=?, end_date=? WHERE key=?",
            (start_date, end_date, key)
        )
        db.commit()
        row = db.execute("SELECT * FROM special_events WHERE key=?", (key,)).fetchone()
    return jsonify(dict(row))


@gamification_bp.route('/api/gamification/events/<key>/deactivate', methods=['POST'])
def deactivate_event(key):
    with get_db() as db:
        db.execute("UPDATE special_events SET is_active=0 WHERE key=?", (key,))
        db.commit()
        row = db.execute("SELECT * FROM special_events WHERE key=?", (key,)).fetchone()
        if not row:
            return jsonify({"error": "event not found"}), 404
    return jsonify(dict(row))


# ── Manual achievement check ──────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/check-achievements', methods=['POST'])
def check_achievements():
    newly = check_and_unlock()
    return jsonify({"newly_unlocked": newly, "count": len(newly)})


# ── Streak heatmap ───────────────────────────────────────────────────────────

@gamification_bp.route('/api/streak/heatmap')
def streak_heatmap():
    """XP por día de los últimos N días (máx 90)."""
    days = int(request.args.get('days', 21))
    days = max(7, min(days, 90))
    end   = today_date()
    start = end - timedelta(days=days - 1)
    with get_db() as db:
        rows = db.execute(
            "SELECT date, SUM(pts) as xp FROM activity_logs "
            "WHERE date>=? AND date<=? GROUP BY date",
            (start.isoformat(), end.isoformat())
        ).fetchall()
    by_date = {r['date']: r['xp'] for r in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        out.append({'date': d, 'xp': by_date.get(d, 0)})
    return jsonify({'days': out, 'max_xp': max((r['xp'] for r in out), default=0)})


# ── Historial de semanas (handoff Ataraxia v2, nota 8) ───────────────────────

@gamification_bp.route('/logros/semanas')
def logros_semanas():
    from modules.ataraxia.routes import historial_semanas
    return render_template('gamification/semanas.html', semanas=historial_semanas())


# ── Logros Page (handoff Logros v2) ─────────────────────────────────────────

RANK_ES = {"carbon": "carbon", "iron": "hierro", "gold": "oro", "diamond": "diamante"}
RARITY_OF = {"bronze": "bronce", "silver": "plata", "gold": "oro", "diamond": "especial"}
FUENTES = ("Acta", "Praxis", "Ataraxia", "Paideia", "Logros", "Sistema")
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def eta_nivel(total_xp, hoy=None):
    """Ritmo de los últimos 30 días y días estimados al siguiente nivel y a
    Eudaimón (6,500 XP). None sin XP en 30 días o en el nivel máximo."""
    import math
    from modules.gamification.engine import LEVEL_THRESHOLDS
    hoy = hoy or today_date()
    with get_db() as db:
        xp30 = db.execute("SELECT COALESCE(SUM(amount),0) AS s FROM xp_ledger WHERE date>=? AND date<=?",
                          ((hoy - timedelta(days=29)).isoformat(), hoy.isoformat())).fetchone()["s"]
    ritmo = round(max(xp30, 0) / 30, 1)
    info = get_level_info(total_xp)
    meta = LEVEL_THRESHOLDS[-1][0]

    def dias(falta):
        if info["max_level"] or ritmo <= 0 or falta <= 0:
            return None
        return math.ceil(falta / ritmo)
    return {"xp_dia_30": ritmo, "dias_siguiente": dias(info["xp_to_next"]),
            "dias_meta": dias(meta - total_xp)}


def coleccion_con_progreso():
    """Insignias y logros con su progreso (have, need, label), calculado con las
    mismas stats con que el motor decide el desbloqueo."""
    from modules.gamification.badges import _gather_badge_stats, progress_of
    try:
        st = _gather_badge_stats()
    except Exception:
        st = None

    badges = get_all_badges()
    for b in badges:
        b["icon_lucide"] = lucide_for(b["icon"])
        b["rarity"] = RARITY_OF.get(b["tier"], "bronce")
        b["progress"] = None if b["unlocked"] or st is None else progress_of(BADGE_DEFS[b["key"]], st)
        b["days_left"] = None
        if b["perk_active"] and b.get("perks_active_until"):
            try:
                b["days_left"] = (datetime.fromisoformat(b["perks_active_until"][:10]).date() - today_date()).days + 1
            except ValueError:
                pass
    # Orden fijo (nota 5): ganadas primero, luego por rareza de mayor a menor
    tier_rank = {"diamond": 0, "gold": 1, "silver": 2, "bronze": 3}
    badges.sort(key=lambda b: (not b["unlocked"], tier_rank.get(b["tier"], 9)))
    for b in badges:
        b["prog_txt"] = prog_txt(b["progress"])

    with get_db() as db:
        rows = {r["key"]: dict(r) for r in db.execute(
            "SELECT key, unlocked_at FROM achievements").fetchall()}
    achievements = []
    for key, defn in ACHIEVEMENT_DEFS.items():
        unlocked = bool(rows.get(key, {}).get("unlocked_at"))
        oculto = defn["hidden"] and not unlocked
        achievements.append({
            "key": key, "name": defn["name"], "description": defn["description"],
            "icon_lucide": lucide_for(defn["icon"]), "coins": defn["coins"], "xp": defn["xp"],
            "hidden": defn["hidden"], "oculto": oculto, "unlocked": unlocked,
            "unlocked_at": (rows[key]["unlocked_at"] or "")[:10] if unlocked else None,
            "progress": None if unlocked or oculto or st is None else progress_of(defn, st),
        })
    for a in achievements:
        a["prog_txt"] = prog_txt(a["progress"])
    achievements.sort(key=lambda a: not a["unlocked"])
    return badges, achievements


def prog_txt(progress):
    """«41/50», o «35%» en condiciones compuestas (su etiqueta ya trae el detalle)."""
    if not progress:
        return None
    have, need, label = progress
    return f"{have}%" if "/" in label else f"{have:,}/{need:,}"


def _recompensa_logro(a):
    partes = ([f'+{a["xp"]} XP'] if a["xp"] else []) + ([f'+{a["coins"]} EC'] if a["coins"] else [])
    return " · ".join(partes)


def near_unlock(badges, achievements, n=3):
    """Las n insignias o logros bloqueados más avanzados (have/need, con have > 0).
    Los logros ocultos no aparecen: se revelan al conseguirlos."""
    cand = []
    for b in badges:
        if b["progress"] and b["progress"][0] > 0:
            cand.append({"name": b["name"], "tier": b["rarity"], "tier_label": b["tier_label"],
                         "icon": b["icon_lucide"], "perk": b["perk"], "progress": b["progress"]})
    for a in achievements:
        if a["progress"] and a["progress"][0] > 0:
            cand.append({"name": a["name"], "tier": "logro", "tier_label": "Logro",
                         "icon": a["icon_lucide"], "perk": _recompensa_logro(a), "progress": a["progress"]})
    out = []
    for c in cand:
        have, need, label = c["progress"]
        if have >= need:
            continue
        out.append({**c, "have": have, "need": need, "label": label,
                    "pct": int(have / need * 100), "prog": prog_txt(c["progress"])})
    out.sort(key=lambda c: -c["have"] / c["need"])
    return out[:n]


def constancia(hoy=None):
    """13 semanas lunes→domingo con el rango de cada día (de las clasificaciones
    guardadas, igual que Inicio) y el conteo por rango."""
    from modules.gamification.engine import classification_history
    end = hoy or today_date()
    start = end - timedelta(days=end.weekday()) - timedelta(weeks=12)
    ranks = classification_history(start, end)
    with get_db() as db:
        by = {r["date"]: r["xp"] or 0 for r in db.execute(
            "SELECT date, SUM(pts) AS xp FROM activity_logs WHERE date>=? AND date<=? GROUP BY date",
            (start.isoformat(), end.isoformat())).fetchall()}
    heat, counts = [], {"carbon": 0, "hierro": 0, "oro": 0, "diamante": 0}
    for i in range(13 * 7):
        d = start + timedelta(days=i)
        ds = d.isoformat()
        activo = ds in by
        rank = RANK_ES.get(ranks.get(ds), "carbon") if (activo and d <= end) else None
        if rank:
            counts[rank] += 1
        heat.append({"date": ds, "xp": by.get(ds, 0), "today": d == end, "future": d > end, "rank": rank})
    return heat, counts


def fuente_xp(source, description, _cache=None):
    """Módulo de origen de una entrada de xp_ledger (la columna source no está
    normalizada: «activity» puede venir de Acta, Paideia o Ataraxia)."""
    desc = description or ""
    if source == "achievement":
        return "Logros"
    if source == "task" or desc.startswith("Bonus diario GTD"):
        return "Praxis"
    if desc in ("Combo: Sábado Completo", "Combo: Domingo Completo"):
        return "Ataraxia"
    if source == "activity":
        key = desc.split(": ", 1)[1] if desc.startswith("Actividad: ") else ""
        if key.startswith("paideia_"):
            return "Paideia"
        if key == "revision_semanal":
            return "Ataraxia"
        if _cache is None:
            _cache = {}
        if key not in _cache:
            from modules.gamification.engine import pillar_of
            try:
                _cache[key] = pillar_of(key)
            except Exception:
                _cache[key] = None
        return "Ataraxia" if _cache[key] == "atar" else "Acta"
    if source in ("rutina", "bonus"):
        return "Acta"
    return "Sistema"


def _fecha_corta(ds, hoy):
    d = date.fromisoformat(ds)
    if d == hoy:
        return "Hoy"
    if d == hoy - timedelta(days=1):
        return "Ayer"
    return f"{_DIAS[d.weekday()]} {d.day} {_MESES[d.month - 1]}"


def _desc_legible(desc, _cache):
    """«Actividad: leer_general» → el nombre de la actividad, si existe."""
    if not desc.startswith("Actividad: "):
        return desc
    key = desc[len("Actividad: "):]
    if key not in _cache:
        try:
            from modules.actividades.activity_defs import get_by_key
            d = get_by_key(key)
            _cache[key] = d.get("label") if d else None
        except Exception:
            _cache[key] = None
    return _cache[key] or desc


def desglose_xp(dias=90, hoy=None):
    """Entradas de XP de los últimos `dias`, agrupadas por día (más reciente
    arriba), cada una con su fuente; y el conteo por fuente."""
    hoy = hoy or today_date()
    with get_db() as db:
        rows = db.execute(
            "SELECT amount, source, description, date FROM xp_ledger WHERE date>=? AND date<=? "
            "ORDER BY date DESC, id DESC", ((hoy - timedelta(days=dias - 1)).isoformat(), hoy.isoformat())).fetchall()
    grupos, idx, conteo, pil, lbl = [], {}, {}, {}, {}
    for r in rows:
        f = fuente_xp(r["source"], r["description"], pil)
        conteo[f] = conteo.get(f, 0) + 1
        if r["date"] not in idx:
            idx[r["date"]] = len(grupos)
            grupos.append({"date": r["date"], "label": _fecha_corta(r["date"], hoy), "rows": []})
        grupos[idx[r["date"]]]["rows"].append({"amount": r["amount"], "desc": _desc_legible(r["description"] or r["source"], lbl), "fuente": f})
    orden = list(FUENTES) + sorted(set(conteo) - set(FUENTES))
    fuentes = [{"k": f, "n": conteo[f]} for f in orden if conteo.get(f)]
    return grupos, fuentes, len(rows)


def semanas_recientes(n=5):
    """Últimas n revisiones de Ataraxia con el XP total de cada semana (lun–dom)."""
    from modules.ataraxia.routes import historial_semanas, _semana_dias
    out = []
    for h in historial_semanas(limit=n):
        dias = _semana_dias(h["semana_id"])
        with get_db() as db:
            xp = db.execute("SELECT COALESCE(SUM(amount),0) AS s FROM xp_ledger WHERE date>=? AND date<=?",
                            (dias[0], dias[-1])).fetchone()["s"]
        out.append({**h, "xp_total": int(xp)})
    return out


@gamification_bp.route('/logros')
def logros():
    from modules.gamification.engine import LEVEL_THRESHOLDS, LEVEL_SUBTITLES
    tab = 'historial' if request.args.get('tab') == 'historial' else 'coleccion'
    stats = get_gamification_stats()
    lvl, total = stats["level"], stats["total_xp"]

    levels = []
    for threshold, n, name in LEVEL_THRESHOLDS:
        state = "past" if n < lvl else ("now" if n == lvl else "next")
        fill = 100 if n < lvl else (stats["level_pct"] if n == lvl else 0)
        levels.append({"n": n, "name": name, "xp": threshold, "state": state, "fill": fill})
    max_xp = LEVEL_THRESHOLDS[-1][0]

    ctx = dict(stats=stats, levels=levels, max_xp=max_xp, level_quote=LEVEL_SUBTITLES.get(lvl, ""),
               eta=eta_nivel(total), tab=tab)
    if tab == 'historial':
        grupos, fuentes, n_total = desglose_xp()
        fuente = request.args.get('fuente', '')
        ctx.update(grupos=grupos, fuentes=fuentes, n_total=n_total,
                   fuente=fuente if any(f["k"] == fuente for f in fuentes) else '',
                   semanas=semanas_recientes())
    else:
        badges, achievements = coleccion_con_progreso()
        heat, rank_counts = constancia()
        ctx.update(badges=badges, achievements=achievements, near=near_unlock(badges, achievements),
                   perks=[b for b in badges if b["perk_active"]], heat=heat, rank_counts=rank_counts)
    return render_template('gamification/logros.html', **ctx)


# ── Full Reset ────────────────────────────────────────────────────────────────

@gamification_bp.route('/api/gamification/reset', methods=['POST'])
def reset_gamification():
    """Wipe all XP, EC, streaks, achievements and badges. Keeps rewards config."""
    with get_db() as db:
        db.execute("DELETE FROM xp_ledger")
        db.execute("DELETE FROM coins_ledger")
        db.execute("DELETE FROM multiplier_log")
        db.execute("DELETE FROM penalty_log")
        db.execute("DELETE FROM activity_logs")
        # Achievements y badges se conservan como "ganados" para que no
        # se vuelvan a disparar (evita XP inesperado en la primera actividad post-reset)
        db.commit()
    return jsonify({"ok": True, "message": "Reset completo — empezando desde cero"})


LOGRO_AVISO_DIAS = 14   # solo lo desbloqueado hace poco: lo antiguo nunca se marcó notified


def avisos(db, hoy):
    """Avisos de Logros para el centro (modules/avisos.py): insignias y
    logros desbloqueados con notified=0. Se marcan vistos al abrir el panel."""
    from modules.avisos import aviso
    desde = (hoy - timedelta(days=LOGRO_AVISO_DIAS)).isoformat()
    out = []
    for r in db.execute("""SELECT key, tier, unlocked_at FROM badges
                           WHERE unlocked_at IS NOT NULL AND COALESCE(notified,0)=0 AND substr(unlocked_at,1,10) >= ?""",
                        (desde,)).fetchall():
        d = BADGE_DEFS.get(r['key'])
        if not d:
            continue
        tier = {'bronze': 'bronce', 'silver': 'plata', 'gold': 'oro'}.get(r['tier'] or d.get('tier'), r['tier'] or '')
        out.append(aviso(f"log:badge:{r['key']}:{r['unlocked_at'][:10]}", 'Logros', (lucide_for(d.get('icon')).replace('circle', 'award')),
                         f"Insignia: {d['name']}" + (f' · {tier}' if tier else ''), d.get('description', ''),
                         r['unlocked_at'][:10], 'logro', {'label': 'Ver', 'url': '/logros'}))
    for r in db.execute("""SELECT key, unlocked_at, xp_earned, coins_earned FROM achievements
                           WHERE unlocked_at IS NOT NULL AND COALESCE(notified,0)=0 AND substr(unlocked_at,1,10) >= ?""",
                        (desde,)).fetchall():
        d = ACHIEVEMENT_DEFS.get(r['key'])
        if not d:
            continue
        premio = ' · '.join(x for x in (f"+{r['xp_earned']} XP" if r['xp_earned'] else '',
                                        f"+{r['coins_earned']} EC" if r['coins_earned'] else '') if x)
        out.append(aviso(f"log:logro:{r['key']}:{r['unlocked_at'][:10]}", 'Logros', (lucide_for(d.get('icon')).replace('circle', 'trophy')),
                         f"Logro: {d['name']}", premio or d.get('description', ''),
                         r['unlocked_at'][:10], 'logro', {'label': 'Ver', 'url': '/logros'}))
    return out


def marcar_vistos(db, claves):
    """notified=1 en las insignias/logros de esas claves (log:badge|logro:<key>:…)."""
    n = 0
    for c in claves:
        partes = c.split(':')
        if len(partes) < 3 or partes[0] != 'log':
            continue
        tabla = {'badge': 'badges', 'logro': 'achievements'}.get(partes[1])
        if tabla:
            n += db.execute(f"UPDATE {tabla} SET notified=1 WHERE key=? AND COALESCE(notified,0)=0", (partes[2],)).rowcount
    return n
