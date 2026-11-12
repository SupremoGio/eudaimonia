"""
Harma v2 — lo que el plan necesita para decir qué toca y cuándo.

· ritmo:     km/mes de los últimos 12 meses (servicios + odómetro).
· enriquecer: por ítem, qué manda (km o tiempo), el motivo en palabras,
             si es un fluido (caduca aunque no lo uses) y la ETA en meses.
· grupos:    ahora (vencido + urgente), siguiente (próximo), al día.
· papeles:   documentos y pólizas en una sola lista por vencimiento.
· integraciones: recordatorio de Perfil para verificación y póliza, y el
             gasto de cada servicio en Oikonomia (solo con fin_ok).
"""
from datetime import date, timedelta

SIN_KM = 999999          # ítem solo por tiempo
SIN_MESES = 999          # ítem solo por km
PAPEL_PROXIMO_DIAS = 30
FIN_CATEGORIA, FIN_SUB = 'TRANSPORTE', 'Mantenimiento auto'   # «Auto · mantenimiento» en Oikonomia


def _d(iso):
    try:
        return date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return None


def ritmo_km_mes(db, vehiculo, hoy):
    """Promedio km/mes de 12 meses con los km de harma_servicios y el odómetro
    actual. Un punto por fecha; con menos de 2 fechas distintas, None."""
    desde = (hoy - timedelta(days=365)).isoformat()
    puntos = {}
    for r in db.execute("SELECT fecha, km FROM harma_servicios WHERE km IS NOT NULL AND km > 0 AND fecha >= ?", (desde,)):
        f = _d(r['fecha'])
        if f:
            puntos[f] = max(puntos.get(f, 0), r['km'])
    if vehiculo and vehiculo.get('km_actual'):
        f = _d(vehiculo.get('km_actualizado')) or hoy
        puntos[f] = max(puntos.get(f, 0), vehiculo['km_actual'])
    if len(puntos) < 2:
        return None
    a, b = min(puntos), max(puntos)
    meses = (b - a).days / 30.44
    km = puntos[b] - puntos[a]
    if meses <= 0 or km <= 0:
        return None
    return round(km / meses)


def _fmt_km(n):
    return f"{int(n):,}"


def enriquecer(it, ritmo, meses_desde):
    """Agrega manda, motivo, fluido y eta_meses a un ítem de _compute_plan_item."""
    con_km = bool(it['km_interval']) and it['km_interval'] < SIN_KM
    con_t = bool(it['meses_interval']) and it['meses_interval'] < SIN_MESES
    manda = 'tiempo' if (con_t and (it['time_pct'] >= it['km_pct'] or not con_km)) else 'km'
    if manda == 'tiempo':
        motivo = f"por tiempo · {max(0, meses_desde)} de {it['meses_interval']} meses"
        eta = max(0, it['meses_interval'] - meses_desde)
    else:
        usados = max(0, it['km_interval'] - it['km_left'])
        motivo = f"por km · {_fmt_km(usados)} de {_fmt_km(it['km_interval'])}"
        eta = (max(0, it['km_left']) / ritmo) if ritmo else None
        if eta is not None:
            eta = round(eta, 1)
    fluido = it['cat'] == 'fluidos'
    return {**it, 'manda': manda, 'motivo': motivo, 'fluido': fluido, 'eta_meses': eta,
            'con_km': con_km, 'con_tiempo': con_t, 'eta_txt': eta_txt(eta)}


def eta_txt(meses):
    if meses is None:
        return '—'
    if meses <= 0:
        return 'ya'
    if meses < 1:
        return '≈ este mes'
    if meses < 12:
        n = round(meses)
        return f"≈ {n} mes{'es' if n != 1 else ''}"
    return f"≈ {meses / 12:.1f} años"


def grupos(plan):
    ahora = sorted((i for i in plan if i['status'] in ('vencido', 'urgente')), key=lambda i: -i['pct'])
    siguiente = sorted((i for i in plan if i['status'] == 'proximo'), key=lambda i: -i['pct'])
    al_dia = sorted((i for i in plan if i['status'] == 'nominal'),
                    key=lambda i: (i['eta_meses'] is None, i['eta_meses'] if i['eta_meses'] is not None else 0, -i['pct']))
    return {'ahora': ahora, 'siguiente': siguiente, 'al_dia': al_dia}


def papeles(documentos, polizas, hoy, status_fn):
    """Documentos y pólizas en una lista: vencidas, próximas y el resto."""
    out = []
    for d in documentos:
        out.append({'tipo': 'documento', 'id': d['id'], 'titulo': d['titulo'], 'vence': d.get('fecha_vencimiento'),
                    'archivo': d.get('nombre_archivo') or ''})
    for p in polizas:
        out.append({'tipo': 'poliza', 'id': p['id'], 'titulo': 'Póliza · ' + (p.get('aseguradora') or ''),
                    'vence': p.get('vigencia_fin'), 'archivo': p.get('nombre_archivo') or ''})
    for x in out:
        x['status'] = status_fn({'vigencia_fin': x['vence']}, hoy)
        f = _d(x['vence'])
        x['dias'] = (f - hoy).days if f else None
        if x['status'] == 'vigente' and x['dias'] is not None and x['dias'] <= PAPEL_PROXIMO_DIAS:
            x['status'] = 'proximo'
    orden = {'vencida': 0, 'proximo': 1, 'vigente': 2, 'sin_fecha': 3}
    out.sort(key=lambda x: (orden[x['status']], x['dias'] if x['dias'] is not None else 10 ** 6))
    return out


# ── Integraciones (Sprint 4) ────────────────────────────────────────────────

def upsert_recordatorio(db, texto, vence, origen_id):
    """Recordatorio de Perfil (origen='harma') 14 días antes del vencimiento.
    Uno por texto: subir una verificación nueva actualiza el existente."""
    f = _d(vence)
    if not f:
        return None
    fecha = (f - timedelta(days=14)).isoformat()
    row = db.execute("SELECT id FROM reminders WHERE origen='harma' AND description=? ORDER BY id LIMIT 1", (texto,)).fetchone()
    if row:
        db.execute("UPDATE reminders SET target_date=?, next_date=?, is_active=1, origen_id=?, tema='casa' WHERE id=?",
                   (fecha, fecha, origen_id, row['id']))
        rid = row['id']
    else:
        from datetime import datetime
        rid = db.execute(
            """INSERT INTO reminders (description, type, target_date, next_date, is_active, created_at, tema, origen, origen_id)
               VALUES (?, 'unico', ?, ?, 1, ?, 'casa', 'harma', ?)""",
            (texto, fecha, fecha, datetime.now().isoformat(), origen_id)).lastrowid
    db.commit()
    return rid


def vincular_recordatorios(db):
    """Migración idempotente: el recordatorio manual de verificación que ya
    exista queda vinculado a Harma (en lugar de duplicarse)."""
    n = 0
    if not db.execute("SELECT 1 FROM reminders WHERE origen='harma' AND description='Renovar verificación vehicular'").fetchone():
        r = db.execute("""SELECT id FROM reminders WHERE COALESCE(origen,'')='' AND is_active=1
                          AND lower(description) LIKE '%verificaci%' ORDER BY id LIMIT 1""").fetchone()
        if r:
            db.execute("UPDATE reminders SET origen='harma', description='Renovar verificación vehicular' WHERE id=?", (r['id'],))
            n += 1
    if n:
        db.commit()
    return n


def crear_gasto(db, titulo, costo, fecha, servicio_id):
    """Movimiento de gasto en Oikonomia (categoría «Auto · mantenimiento»)."""
    desc = f"Harma · {titulo}"
    if db.execute("SELECT 1 FROM est_movimientos WHERE fecha=? AND descripcion=? AND monto=?", (fecha, desc, costo)).fetchone():
        desc = f"{desc} #{servicio_id}"
    cur = db.execute(
        """INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo)
           VALUES (?,?,?,?, 'MANUAL', '', ?, ?, 'GASTO')""", (fecha, fecha, desc, costo, FIN_CATEGORIA, FIN_SUB))
    db.execute("UPDATE harma_servicios SET fin_mov_id=? WHERE id=?", (cur.lastrowid, servicio_id))
    db.commit()
    return cur.lastrowid
