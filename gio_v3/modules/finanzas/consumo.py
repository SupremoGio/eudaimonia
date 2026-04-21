"""
Consumo Inteligente — trackea productos de uso regular y calcula frecuencias.
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database import get_db
from datetime import date, datetime, timedelta

consumo_bp = Blueprint(
    'consumo',
    __name__,
    template_folder='../../templates')


# ── Auth guard ────────────────────────────────────────────────────────────────

@consumo_bp.before_request
def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')


# ── Intelligence core ─────────────────────────────────────────────────────────

def _calcular_metricas(producto_id, db):
    """Recalculate precio_promedio, ultima_compra, frecuencia_dias in-place."""
    compras = db.execute(
        "SELECT fecha_compra, precio_total FROM consumo_compras "
        "WHERE producto_id=? ORDER BY fecha_compra ASC",
        (producto_id,)
    ).fetchall()
    if not compras:
        return

    precio_promedio = round(sum(c["precio_total"] for c in compras) / len(compras), 2)
    ultima_compra   = compras[-1]["fecha_compra"]

    frecuencia_dias = None
    if len(compras) >= 2:
        gaps = []
        for i in range(1, len(compras)):
            d1  = date.fromisoformat(compras[i - 1]["fecha_compra"])
            d2  = date.fromisoformat(compras[i]["fecha_compra"])
            gap = (d2 - d1).days
            if gap > 0:
                gaps.append(gap)
        if gaps:
            frecuencia_dias = round(sum(gaps) / len(gaps), 1)

    db.execute(
        "UPDATE consumo_productos "
        "SET precio_promedio=?, ultima_compra=?, frecuencia_dias=? WHERE id=?",
        (precio_promedio, ultima_compra, frecuencia_dias, producto_id),
    )


def _generar_insights(prod, compras):
    """
    Returns a list of insight dicts: {tipo, msg}
    tipos: info | ok | proximo | warning | tip | trend
    """
    insights = []
    freq   = prod.get("frecuencia_dias")
    ultima = prod.get("ultima_compra")
    n      = len(compras)

    if not freq:
        if n == 0:
            insights.append({"tipo": "info", "msg": "Sin historial — registra tu primera compra"})
        elif n == 1:
            insights.append({"tipo": "info", "msg": "Con 2+ compras calcularé tu frecuencia"})
        return insights

    # Days since last purchase
    dias_desde = (date.today() - date.fromisoformat(ultima)).days if ultima else None

    if dias_desde is not None:
        dias_restantes = int(freq - dias_desde)
        if dias_desde > freq * 1.15:
            insights.append({
                "tipo": "warning",
                "msg":  f"Llevas {dias_desde}d sin comprar (tu ciclo: {freq:.0f}d)",
            })
        elif dias_restantes <= 4:
            insights.append({
                "tipo": "proximo",
                "msg":  f"Podrías necesitarlo pronto — ~{max(0, dias_restantes)}d restantes",
            })
        else:
            insights.append({
                "tipo": "ok",
                "msg":  f"Próxima compra aprox en {dias_restantes}d",
            })

    # Main frequency message
    insights.insert(0, {"tipo": "frecuencia", "msg": f"Lo compras cada {freq:.0f} días en promedio"})

    # Trend: compare recent vs historical (need 4+ purchases)
    if n >= 4:
        gaps = []
        for i in range(1, n):
            d1  = date.fromisoformat(compras[i - 1]["fecha_compra"])
            d2  = date.fromisoformat(compras[i]["fecha_compra"])
            gap = (d2 - d1).days
            if gap > 0:
                gaps.append(gap)
        if len(gaps) >= 3:
            hist_avg = sum(gaps[:-2]) / max(len(gaps[:-2]), 1)
            rec_avg  = sum(gaps[-2:]) / 2
            if rec_avg < hist_avg * 0.75:
                insights.append({"tipo": "trend", "msg": "Tendencia: lo compras más frecuente que antes"})
            elif rec_avg > hist_avg * 1.35:
                insights.append({"tipo": "trend", "msg": "Tendencia: lo compras menos seguido"})

    # Bulk-buy tip
    if freq and freq <= 10 and n >= 3:
        insights.append({"tipo": "tip", "msg": "Alta frecuencia — considera comprar en mayor cantidad"})

    return insights


def _enrich(prod, db):
    """Add dias_desde, status and insights to a product dict."""
    p = dict(prod)
    compras = db.execute(
        "SELECT fecha_compra, precio_total FROM consumo_compras "
        "WHERE producto_id=? ORDER BY fecha_compra ASC",
        (p["id"],),
    ).fetchall()
    p["n_compras"] = len(compras)
    p["dias_desde"] = None
    if p.get("ultima_compra"):
        p["dias_desde"] = (date.today() - date.fromisoformat(p["ultima_compra"])).days

    # status for visual dot
    freq = p.get("frecuencia_dias")
    if not freq or p["dias_desde"] is None:
        p["status"] = "sin_datos"
    else:
        ratio = p["dias_desde"] / freq
        if ratio >= 1.15:
            p["status"] = "atrasado"
        elif ratio >= 0.85:
            p["status"] = "proximo"
        else:
            p["status"] = "ok"

    p["insights"] = _generar_insights(p, [dict(c) for c in compras])
    return p


# ── Routes ────────────────────────────────────────────────────────────────────

@consumo_bp.route("/")
def index():
    with get_db() as db:
        productos_raw = db.execute(
            "SELECT * FROM consumo_productos WHERE activo=1 ORDER BY categoria, nombre"
        ).fetchall()
        productos = [_enrich(p, db) for p in productos_raw]

        month_start = date.today().replace(day=1).isoformat()
        stats = db.execute(
            "SELECT COUNT(*) as c, COALESCE(SUM(precio_total),0) as s "
            "FROM consumo_compras WHERE fecha_compra >= ?",
            (month_start,),
        ).fetchone()
        categorias = db.execute(
            "SELECT DISTINCT categoria FROM consumo_productos WHERE activo=1 ORDER BY categoria"
        ).fetchall()

    atrasados = sum(1 for p in productos if p["status"] == "atrasado")
    proximos  = sum(1 for p in productos if p["status"] == "proximo")

    return render_template(
        "finanzas/consumo.html",
        productos=productos,
        categorias=[r["categoria"] for r in categorias],
        compras_mes=stats["c"],
        gasto_mes=round(stats["s"], 2),
        atrasados=atrasados,
        proximos=proximos,
    )


@consumo_bp.route("/producto/<int:pid>")
def detalle(pid):
    with get_db() as db:
        prod = db.execute("SELECT * FROM consumo_productos WHERE id=?", (pid,)).fetchone()
        if not prod:
            return redirect("/finanzas/consumo/")
        compras = db.execute(
            "SELECT * FROM consumo_compras WHERE producto_id=? ORDER BY fecha_compra DESC",
            (pid,),
        ).fetchall()
        compras_asc = list(reversed([dict(c) for c in compras]))

    prod = _enrich(prod, db)
    insights = _generar_insights(prod, compras_asc)

    # Price trend: last 5 purchases
    precio_trend = [
        {"fecha": c["fecha_compra"], "precio": c["precio_total"]}
        for c in compras_asc[-5:]
    ]

    return render_template(
        "finanzas/consumo_detalle.html",
        prod=prod,
        compras=compras,
        insights=insights,
        precio_trend=precio_trend,
    )


# ── API endpoints ─────────────────────────────────────────────────────────────

@consumo_bp.route("/api/compra", methods=["POST"])
def registrar_compra():
    data        = request.json or {}
    producto_id = data.get("producto_id")
    fecha       = data.get("fecha") or date.today().isoformat()
    cantidad    = float(data.get("cantidad") or 1)
    precio      = float(data.get("precio_total") or 0)
    now         = datetime.now().isoformat()

    if not producto_id or precio <= 0:
        return jsonify({"error": "precio_total requerido y > 0"}), 400

    with get_db() as db:
        if not db.execute("SELECT id FROM consumo_productos WHERE id=?", (producto_id,)).fetchone():
            return jsonify({"error": "Producto no encontrado"}), 404

        db.execute(
            "INSERT INTO consumo_compras (producto_id, fecha_compra, cantidad, precio_total, created_at)"
            " VALUES (?,?,?,?,?)",
            (producto_id, fecha, cantidad, precio, now),
        )
        _calcular_metricas(producto_id, db)
        db.commit()

        prod    = db.execute("SELECT * FROM consumo_productos WHERE id=?", (producto_id,)).fetchone()
        compras = db.execute(
            "SELECT fecha_compra, precio_total FROM consumo_compras "
            "WHERE producto_id=? ORDER BY fecha_compra ASC",
            (producto_id,),
        ).fetchall()

    prod    = _enrich(prod, db)
    insights = _generar_insights(prod, [dict(c) for c in compras])

    return jsonify({"ok": True, "prod": prod, "insights": insights})


@consumo_bp.route("/api/producto", methods=["POST"])
def agregar_producto():
    data      = request.json or {}
    nombre    = (data.get("nombre") or "").strip()
    categoria = (data.get("categoria") or "").strip()
    now       = datetime.now().isoformat()

    if not nombre:
        return jsonify({"error": "Nombre requerido"}), 400

    with get_db() as db:
        if db.execute(
            "SELECT id FROM consumo_productos WHERE nombre=? AND activo=1", (nombre,)
        ).fetchone():
            return jsonify({"error": "Ya existe ese producto"}), 400

        db.execute(
            "INSERT INTO consumo_productos (nombre, categoria, created_at) VALUES (?,?,?)",
            (nombre, categoria, now),
        )
        db.commit()
        prod = dict(db.execute(
            "SELECT * FROM consumo_productos ORDER BY id DESC LIMIT 1"
        ).fetchone())

    prod["n_compras"] = 0
    prod["dias_desde"] = None
    prod["status"] = "sin_datos"
    prod["insights"] = [{"tipo": "info", "msg": "Sin historial — registra tu primera compra"}]
    return jsonify({"ok": True, "prod": prod})


@consumo_bp.route("/api/producto/<int:pid>", methods=["DELETE"])
def desactivar_producto(pid):
    with get_db() as db:
        db.execute("UPDATE consumo_productos SET activo=0 WHERE id=?", (pid,))
        db.commit()
    return jsonify({"ok": True})


@consumo_bp.route("/api/proximas")
def proximas_compras():
    """Productos próximos a necesitar — para integración con dashboard/GTD."""
    today = date.today()
    with get_db() as db:
        productos = db.execute(
            "SELECT * FROM consumo_productos "
            "WHERE activo=1 AND ultima_compra IS NOT NULL AND frecuencia_dias IS NOT NULL"
        ).fetchall()

    proximas = []
    for p in productos:
        dias_desde = (today - date.fromisoformat(p["ultima_compra"])).days
        ratio = dias_desde / p["frecuencia_dias"]
        if ratio >= 0.8:
            proximas.append({
                "id":         p["id"],
                "nombre":     p["nombre"],
                "categoria":  p["categoria"],
                "dias_desde": dias_desde,
                "frecuencia": p["frecuencia_dias"],
                "urgencia":   "alta" if ratio >= 1.15 else "media",
            })

    proximas.sort(key=lambda x: x["dias_desde"] / x["frecuencia"], reverse=True)
    return jsonify({"proximas": proximas[:10]})
