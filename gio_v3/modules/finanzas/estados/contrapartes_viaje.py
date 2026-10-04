"""
Contrapartes y viaje a Guadalajara (PROMPT_CLAUDE_CODE_contrapartes_y_viaje.md,
2026-10-04). Plan (simulación) -> respaldo -> aplicar, como auditoria_pdf.

1. Compromisos del viaje (dic 2025): a cada persona le tocó $4,809.02
   (boletos 2,195.95 + Airbnb 1,823.06 + Navidalia 790). Cada abono se deja
   como dice el usuario y, cuando hay depósito del banco, se liga a él (queda
   FINANZAS/Reembolso compartido: no es ingreso). Los abonos que ya existen se
   reconocen por monto; uno que sobre no se borra: se reporta.
2. Revisión de las correcciones puntuales (3b–3f) que ya aplicó la auditoría
   contra el PDF: solo se verifica que la base esté así.
3. PREGUNTAS: lo que choca con decisiones anteriores no se aplica hasta que el
   usuario conteste (DECISIONES).
"""
import re
from datetime import datetime

from modules.finanzas import compromisos as _comp
from . import contrapartes as _contra

VIAJE = 'Viaje GDL'
TOTAL = 4809.02
_VIAJE_RE = re.compile(r'VIAJE|GDL|GUADALAJARA', re.IGNORECASE)

# persona (como está en Compromisos), cuenta, abonos [(fecha, monto, nota, [depósitos (fecha, monto)])]
COMPROMISOS = (
    ('Eli', '1239', [
        ('2025-12-15', 3199.00, 'dic-2025 (sin movimiento bancario)', []),
        ('2026-02-01', 1610.02, 'feb-2026', [('2026-02-01', 1610.00)]),
    ], ()),
    ('Lenis', '3042', [
        ('2025-11-30', 800.00, 'nov-2025', []),
        ('2025-12-31', 500.00, 'dic-2025', []),
        ('2026-01-30', 1700.00, 'ene-2026', [('2026-01-04', 850.00), ('2026-01-30', 850.00)]),
        ('2026-03-04', 400.00, 'mar-2026', [('2026-03-04', 400.00)]),
        # «ya me lo pagó»: sin depósito hasta que diga cuáles transferencias abr–jun fueron
        ('2026-06-30', 1409.02, 'liquidación (depósitos por identificar)', []),
    ], ()),
    ('Judicial', '6230', [
        ('2025-11-30', 852.00, 'nov-2025', []),
        ('2025-12-31', 1150.00, 'dic-2025', [('2025-12-01', 702.00)]),   # el $702 es parte de nov/dic
        ('2026-02-15', 300.00, 'feb-2026', [('2026-02-15', 300.00)]),
    ], ()),
    ('Corner', '5937', [
        ('2025-12-31', 1300.00, 'dic-2025', []),
        ('2026-05-13', 1000.00, 'ABONO VIAJE GDL', []),
    ], (('2026-07-11', 1000.00),)),   # «deyvi cornelio»: es de otra cosa, no se liga ni se sugiere
)

# Lo que choca con decisiones anteriores: None = falta la respuesta del usuario.
# Respuestas del usuario (2026-10-04).
DECISIONES = {
    'papa_2023': 'neutro',   # «haz lo que recomiendas»: Entre cuentas propias los dos (prestamos.PRESTAMOS_RECIBIDOS_PAGADOS)
    '1749': None,            # $2,500 «capital» a Judith (15-feb-2026) que regresaron el mismo día (1750)
    '1979': 'deuda',         # «si yo pagué todo, es deuda» (CATEGORIAS)
    '3004': 'judi',          # «quizá le transferí a mi hermana Judi, pero es lo mismo: Cornelius es su esposo»
}

# Categorías que el usuario corrigió: (sección, id, fecha, monto, texto, categoría, subcategoría, por qué).
# Un préstamo registrado sobre el movimiento (sin devoluciones) se borra: no le prestó a nadie.
CATEGORIAS = (
    ('3a', 3351, '2024-01-07', 7000.0, 'ABONO DEUDA', 'FINANZAS', 'Transferencia enviada',
     'abono de deuda a Papá (…1239): le pagaste, no le prestaste'),
    ('3f', 1979, '2026-04-15', 3311.0, 'DEUDA', 'FINANZAS', 'Transferencia enviada',
     '«si yo pagué todo, es deuda»: pago de deuda a Papá, no seguro'),
)

# Correcciones que ya aplicó la auditoría contra el PDF: id -> (campo, valor esperado | None = no debe existir)
VERIFICAR = (
    ('3b', 2540, 'fecha', '2026-09-05'), ('3b', 2540, 'fecha_cargo', '2026-09-07'),
    ('3c', 1806, None, None), ('3c', 1807, None, None), ('3c', 1817, None, None),
    ('3c', 1812, 'descripcion', 'RETIRO SIN TARJETA'), ('3c', 1823, 'descripcion', 'RETIRO SIN TARJETA'),
    ('3c', 1815, 'descripcion', 'SPEI ENVIADO BANAMEX 2901260ARBITRAJE GIO'),
    ('3c', 1805, 'descripcion', 'PAGO CUENTA DE TERCERO BNET COLECTA MARTHA'),
    ('3d', 2059, 'fecha', '2026-05-07'), ('3d', 2059, 'fecha_cargo', '2026-05-07'),
    ('3d', 1956, 'descripcion', 'DEPOSITO EFECTIVO PRACTIC ******1804 ABR07 18:08 PRAC D797'),
    ('3d', 1959, 'descripcion', 'CFE SUM SERV BAS CR MU ******7830 RFC: CSS 160330CP7 17:40 AUT:'),
    ('3d', 2006, 'descripcion', 'SITH2PAGOGDLAC FIDEICOMISO F 1596'),
    ('3e', 2077, None, None), ('3e', 2124, 'descripcion', 'RETIRO SIN TARJETA'),
    ('3e', 2085, 'descripcion', 'PAGO CUENTA DE TERCERO BNET TACOS'),
    ('3f', 1732, 'subcategoria', 'Retiro efectivo'), ('3f', 1980, 'subcategoria', 'Retiro efectivo'),
    ('3f', 2108, 'subcategoria', 'Retiro efectivo'),
)


def _l(seccion, accion, objeto, motivo='', antes='', despues='', fn=None, **kw):
    out = {'seccion': seccion, 'accion': accion, 'objeto': objeto, 'antes': antes, 'despues': despues,
           'motivo': motivo, **kw}
    if fn:
        out['_fn'] = fn
    return out


def _debt(db, persona, cuenta):
    rows = [dict(r) for r in db.execute("SELECT * FROM debts WHERE type='owe_me' ORDER BY id").fetchall()]
    suyas = [d for d in rows if d.get('contraparte') == cuenta or d['person'].strip().lower() == persona.lower()
             or _contra.de_persona(db, d['person']) == cuenta]
    viaje = [d for d in suyas if _VIAJE_RE.search(d['concept'] or '')] or \
            [d for d in suyas if abs((d['monto_total'] or 0) - TOTAL) < 1]
    return min(viaje, key=lambda d: (abs((d['monto_total'] or 0) - TOTAL), d['id'])) if viaje else None


def _deposito(db, cuenta, fecha, monto):
    """El depósito del banco: misma fecha (±1 día) y monto; si hay varios, el de esa cuenta."""
    rows = [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, tipo, categoria, subcategoria,
               contraparte, cuenta_contraparte
        FROM est_movimientos WHERE tipo='INGRESO' AND ABS(ABS(monto) - ?) < 0.02
          AND substr(fecha,1,10) BETWEEN date(?, '-1 day') AND date(?, '+1 day')
        ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?)), id""", (monto, fecha, fecha, fecha)).fetchall()]
    de_cuenta = [r for r in rows if cuenta in (r['contraparte'], r['cuenta_contraparte'])]
    sin_cuenta = [r for r in rows if not r['cuenta_contraparte']]
    return de_cuenta[0] if de_cuenta else (sin_cuenta[0] if len(sin_cuenta) == 1 else None), rows


def _plan_compromiso(db, persona, cuenta, abonos, no_ligar) -> list[dict]:
    out, ctx = [], {}
    sec = f'viaje · {persona}'
    d = _debt(db, persona, cuenta)
    if not d:
        def crear(db, persona=persona, cuenta=cuenta):
            ctx['debt'] = db.execute("""INSERT INTO debts (type, person, concept, amount, monto_total, monto_restante,
                                         settled, created_at, contraparte) VALUES ('owe_me',?,?,?,?,?,0,?,?)""",
                                     (persona, VIAJE, TOTAL, TOTAL, TOTAL, '2025-12-15T12:00:00', cuenta)).lastrowid
        out.append(_l(sec, 'creado', 'compromiso', 'no había compromiso del viaje', '', f'{persona} · {VIAJE} · ${TOTAL:,.2f}', crear))
        pagos = []
    else:
        ctx['debt'] = d['id']
        if abs((d['monto_total'] or 0) - TOTAL) >= 0.005:
            out.append(_l(sec, 'actualizado', f'compromiso #{d["id"]} total', 'a cada persona le tocó $4,809.02',
                          d['monto_total'], TOTAL,
                          lambda db, did=d['id']: db.execute("UPDATE debts SET monto_total=?, amount=? WHERE id=?", (TOTAL, TOTAL, did))))
        if d.get('contraparte') != cuenta:
            out.append(_l(sec, 'actualizado', f'compromiso #{d["id"]} contraparte', 'para sugerir sus depósitos',
                          d.get('contraparte') or '', f'…{cuenta}',
                          lambda db, did=d['id']: db.execute("UPDATE debts SET contraparte=? WHERE id=?", (cuenta, did))))
        pagos = [dict(p) for p in db.execute("SELECT * FROM debt_payments WHERE debt_id=? ORDER BY paid_at, id", (d['id'],)).fetchall()]
    usados = set()
    for i, (fecha, monto, nota, depositos) in enumerate(abonos):
        p = next((p for p in pagos if p['id'] not in usados and abs(p['amount'] - monto) < 0.01), None)
        if p:
            usados.add(p['id'])
            ctx[i] = p['id']
            out.append(_l(sec, 'sin cambio', f'abono #{p["id"]}', 'ya está', '', f'{p["paid_at"][:10]} ${monto:,.2f} {p["note"] or ""}'.strip()))
        else:
            def agregar(db, i=i, fecha=fecha, monto=monto, nota=nota):
                ctx[i] = db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?,?,?,?)",
                                    (ctx['debt'], monto, nota, f'{fecha}T12:00:00')).lastrowid
            out.append(_l(sec, 'abono agregado', 'abono', 'según tu lista', '', f'{fecha} ${monto:,.2f} · {nota}', agregar))
        for df, dm in depositos:
            mov, cands = _deposito(db, cuenta, df, dm)
            if not mov:
                out.append(_l(sec, 'pendiente revisión', f'depósito {df} ${dm:,.2f}',
                              f'{len(cands)} depósitos de ese día y monto: no sé cuál es' if cands else 'no está en la base'))
                continue
            ligado = db.execute("SELECT payment_id FROM debt_payment_movs WHERE movimiento_id=?", (mov['id'],)).fetchone()
            if ligado and ligado['payment_id'] == ctx.get(i):
                out.append(_l(sec, 'sin cambio', f'movimiento #{mov["id"]}', 'ya ligado a su abono'))
            elif ligado:
                out.append(_l(sec, 'pendiente revisión', f'movimiento #{mov["id"]}', f'ya es el abono #{ligado["payment_id"]} de otro compromiso'))
            elif db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (mov['id'],)).fetchone():
                out.append(_l(sec, 'pendiente revisión', f'movimiento #{mov["id"]}', 'está ligado como devolución de un préstamo'))
            else:
                out.append(_l(sec, 'ligado', f'movimiento #{mov["id"]} ({mov["fecha"]} {mov["descripcion"]})',
                              'el depósito del abono: deja de contar como ingreso',
                              f'{mov["categoria"]}/{mov["subcategoria"] or ""}', f'abono ${monto:,.2f} · FINANZAS/Reembolso compartido',
                              lambda db, i=i, mid=mov['id']: _comp.ligar(db, ctx[i], mid)))
    for p in pagos:
        if p['id'] not in usados:
            out.append(_l(sec, 'pendiente revisión', f'abono #{p["id"]}', 'no está en tu lista: no se borra, dime qué es',
                          f'{p["paid_at"][:10]} ${p["amount"]:,.2f} {p["note"] or ""}'.strip()))
    extra = sum(p['amount'] for p in pagos if p['id'] not in usados)
    pendiente = round(TOTAL - sum(a[1] for a in abonos) - extra, 2)
    antes = d and (round(d['monto_restante'] or 0, 2), bool(d['settled']))
    if antes != (max(pendiente, 0), pendiente <= 0.005):
        def recalcular(db):
            pagado = db.execute("SELECT COALESCE(SUM(amount),0) FROM debt_payments WHERE debt_id=?", (ctx['debt'],)).fetchone()[0]
            rest = round(max(TOTAL - pagado, 0), 2)
            db.execute("UPDATE debts SET monto_restante=?, settled=? WHERE id=?", (rest, 1 if rest <= 0.005 else 0, ctx['debt']))
        out.append(_l(sec, 'actualizado', 'pendiente', 'total menos abonos',
                      f'${antes[0]:,.2f}{" (liquidado)" if antes[1] else ""}' if antes else '',
                      'LIQUIDADO' if pendiente <= 0.005 else f'${pendiente:,.2f}', recalcular))
    else:
        out.append(_l(sec, 'sin cambio', 'pendiente', '', '', 'LIQUIDADO' if pendiente <= 0.005 else f'${pendiente:,.2f}'))
    for df, dm in no_ligar:
        mov, _ = _deposito(db, cuenta, df, dm)
        if mov and not db.execute("SELECT 1 FROM debt_sugerencias_descartadas WHERE movimiento_id=?", (mov['id'],)).fetchone():
            out.append(_l(sec, 'actualizado', f'movimiento #{mov["id"]} ({mov["fecha"]} {mov["descripcion"]})',
                          'es de otra cosa: no se sugiere como abono', '', 'descartado',
                          lambda db, mid=mov['id']: _comp.descartar(db, mid)))
    return out


def _categorias(db) -> list[dict]:
    out = []
    for sec, mid, fecha, monto, texto, cat, sub, por_que in CATEGORIAS:
        r = db.execute("SELECT * FROM est_movimientos WHERE id=? AND substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005",
                       (mid, fecha, monto)).fetchone() or db.execute(
            """SELECT * FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005
                 AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""", (fecha, monto, f'%{texto}%')).fetchone()
        if not r:
            out.append(_l(sec, 'pendiente revisión', f'{fecha} ${monto:,.2f} «{texto}»', 'no está en la base'))
            continue
        for p in db.execute("SELECT id, contraparte FROM est_prestamos WHERE movimiento_id=?", (r['id'],)).fetchall():
            if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE prestamo_id=?", (p['id'],)).fetchone():
                out.append(_l(sec, 'pendiente revisión', f'préstamo #{p["id"]}', 'tiene devoluciones ligadas: dime qué hago'))
            else:
                out.append(_l(sec, 'préstamo borrado', f'préstamo a {p["contraparte"]} (#{r["id"]})', por_que,
                              fn=lambda db, pid=p['id']: db.execute("DELETE FROM est_prestamos WHERE id=?", (pid,))))
        antes = f"{r['categoria']}/{r['subcategoria'] or ''}"
        if (r['categoria'], r['subcategoria'] or '', r['mi_parte']) == (cat, sub, None):
            out.append(_l(sec, 'sin cambio', f'#{r["id"]}', 'ya está', antes, antes))
        else:
            out.append(_l(sec, 'actualizado', f'#{r["id"]} {fecha} ${monto:,.2f} {r["descripcion"]}', por_que, antes, f'{cat}/{sub}',
                          lambda db, mid=r['id'], cat=cat, sub=sub:
                          db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=?, mi_parte=NULL WHERE id=?",
                                     (cat, sub, mid))))
    return out


def _verificar(db) -> list[dict]:
    out = []
    for sec, mid, campo, valor in VERIFICAR:
        r = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone()
        if campo is None:
            out.append(_l(sec, 'verificado' if not r else 'pendiente revisión', f'#{mid}',
                          'borrado (duplicado)' if not r else 'debía estar borrado: corre la auditoría contra el PDF'))
            continue
        if not r:
            out.append(_l(sec, 'pendiente revisión', f'#{mid}', 'no está en la base'))
            continue
        actual = (r[campo] or '')[:10] if campo.startswith('fecha') else (r[campo] or '')
        out.append(_l(sec, 'verificado' if actual == valor else 'pendiente revisión', f'#{mid} {campo}',
                      '' if actual == valor else 'lo corrige la auditoría contra el PDF (?aplicar=1 en auditoria-pdf)',
                      actual, valor))
    return out


def _preguntas(db) -> list[dict]:
    q = []
    if DECISIONES['papa_2023'] is None:
        q.append(_l('3a', 'pregunta', 'préstamo de Papá jun-2023 ($7,000)',
                    'hoy los dos están como Entre cuentas propias (neto 0, no cuentan). El prompt pide abono → OTROS '
                    '(contaría $7,000 de ingreso en jun-2023) y cargo → Transferencia enviada'))
    if DECISIONES['1749'] is None:
        q.append(_l('3f', 'pregunta', '#1749 $2,500 «capital» a Judith (15-feb-2026)',
                    'le mandaste $2,500 y ese mismo día te regresaron $2,500 (#1750); hoy los dos son Entre cuentas '
                    'propias (no cuentan). El prompt lo quiere como préstamo: ¿lo marco como préstamo ya pagado?'))
    if DECISIONES['1979'] is None:
        q.append(_l('3f', 'pregunta', '#1979 $3,311 a Papá (15-abr-2026)',
                    'el 3-oct dijiste: seguro mar+abr ($1,111) + préstamos ($1,500 + $700). El prompt: todo es pago de deuda'))
    if DECISIONES['3004'] is None:
        q.append(_l('1', 'pregunta', '$2,513 «jefe de famil repo» (27-mar-2025, …5937)',
                    '…5937 es Cornelius, pero hoy es devolución de un préstamo de Judi ($5,025 con los $2,512)'))
    return q


def plan(db) -> list[dict]:
    out = []
    for persona, cuenta, abonos, no_ligar in COMPROMISOS:
        out += _plan_compromiso(db, persona, cuenta, abonos, no_ligar)
    return out + _categorias(db) + _verificar(db) + _preguntas(db)


def aplicar(db, lineas=None) -> list[dict]:
    """Ejecuta el plan en orden (el caller respalda antes y hace commit)."""
    lineas = plan(db) if lineas is None else lineas
    for l in lineas:
        if '_fn' in l:
            l['_fn'](db)
    _contra.actualizar(db)
    return lineas


def resumen_compromisos(db) -> list[dict]:
    out = []
    for persona, cuenta, _, _ in COMPROMISOS:
        d = _debt(db, persona, cuenta)
        if d:
            pagos = db.execute("SELECT id, amount, note, paid_at FROM debt_payments WHERE debt_id=? ORDER BY paid_at, id",
                               (d['id'],)).fetchall()
            out.append({'persona': persona, 'cuenta': f'…{cuenta}', 'compromiso': d['id'], 'total': d['monto_total'],
                        'pendiente': d['monto_restante'], 'liquidado': bool(d['settled']),
                        'abonos': [{'fecha': p['paid_at'][:10], 'monto': p['amount'], 'nota': p['note'],
                                    'depositos': [m['id'] for m in _comp.movs_de_pago(db, p['id'])]} for p in pagos]})
    return out


def reporte_md(lineas, compromisos, respaldo) -> str:
    l = ['# Reporte: contrapartes y viaje a Guadalajara', '',
         f'Generado {datetime.now():%Y-%m-%d %H:%M}. ' + (f'Respaldo: `{respaldo}`.' if respaldo else 'Simulación: no se escribió nada.'), '',
         '## Compromisos del viaje', '', '| Persona | Total | Abonos | Pendiente |', '|---|---:|---|---:|']
    for c in compromisos:
        ab = '; '.join(f"{a['fecha']} ${a['monto']:,.2f}" + (f" (#{', #'.join(map(str, a['depositos']))})" if a['depositos'] else '')
                       for a in c['abonos'])
        l.append(f"| {c['persona']} {c['cuenta']} | ${c['total']:,.2f} | {ab} | "
                 f"{'LIQUIDADO' if c['liquidado'] else '$' + format(c['pendiente'], ',.2f')} |")
    l += ['', '## Cambios', '', '| Sección | Acción | Qué | Antes | Después | Por qué |', '|---|---|---|---|---|---|']
    for x in lineas:
        if x['accion'] != 'sin cambio':
            l.append(f"| {x['seccion']} | {x['accion']} | {x['objeto']} | {x['antes']} | {x['despues']} | {x['motivo']} |")
    return '\n'.join(l) + '\n'
