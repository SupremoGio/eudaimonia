"""
Coach financiero — paquete para analizar en Claude (claude.ai).

No llama a ninguna IA: arma un solo archivo Markdown con el prompt del coach
y un resumen de las finanzas del usuario (totales por mes y por categoría,
deudas, préstamos, inversiones, patrimonio y viajes), para subirlo a un chat
y pedir el diagnóstico (el usuario, 2026-10-01: prefirió esto a pagar la API).
Reutiliza los cálculos de Presupuesto, Patrimonio, Inversiones, Préstamos y
MSI para que las cifras cuadren con lo que ya muestra la app. Cada sección es
independiente: si una falla, el archivo sale igual con una nota.
"""
from flask import Blueprint, render_template, session, redirect, Response

from database import get_db
from utils import now_local

coach_bp = Blueprint('coach', __name__, template_folder='../../templates')

_MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

PROMPT = """\
# Coach financiero personal

Eres mi coach y consultor financiero personal. Abajo tienes un resumen de mis
finanzas exportado de mi app (montos en MXN). Quiero llegar a un nivel élite
en finanzas personales: sé directo, honesto y concreto, sin sermones ni
advertencias genéricas. Cada observación debe citar números de estos datos.

Dame el diagnóstico con esta estructura:

1. **Cómo voy** — calificación general de 0 a 100 y un semáforo (verde,
   amarillo, rojo) para: tasa de ahorro, gasto en deseos vs necesidades,
   deuda vs ingreso, fondo de emergencia (meses de gasto que cubre mi
   líquido) y dinero prestado sin cobrar.
2. **Lo que hago bien** — 2 o 3 puntos.
3. **Fugas y riesgos** — las 3 más importantes, con cuánto me cuestan al mes
   y al año.
4. **Plan de acción** — 3 a 5 acciones concretas, ordenadas por impacto en
   pesos.
5. **Meta del próximo mes** — una sola, medible.

Después sigue como mi coach: respóndeme preguntas, ayúdame a decidir compras
y viajes, y cuando te pase un archivo nuevo compáralo con el anterior.

Notas para leer los datos:
- «Ingreso recurrente» es nómina y entradas fijas; «extraordinario» son
  bonos, aguinaldo y otros ingresos que no se repiten.
- El gasto ya descuenta lo que otros me reembolsaron y no incluye préstamos,
  traspasos entre mis cuentas ni gastos de trabajo (Expense).
- La regla de referencia de la app es 50 % necesidades, 30 % deseos y 20 %
  ahorro y deudas.
"""


def _require_auth():
    if not session.get('fin_ok'):
        return redirect('/finanzas/')


coach_bp.before_request(_require_auth)


def _mx(v) -> str:
    v = float(v or 0)
    return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


def _pct(a, b) -> str:
    return f"{a / b * 100:.0f} %" if b else '—'


def _tabla(encabezados, filas) -> str:
    out = ['| ' + ' | '.join(encabezados) + ' |',
           '|' + '|'.join('---' for _ in encabezados) + '|']
    out += ['| ' + ' | '.join(str(c).replace('|', '/') for c in f) + ' |' for f in filas]
    return '\n'.join(out)


def _meses_atras(hoy, n):
    """Los n meses cerrados más el actual, del más viejo al más nuevo."""
    y, m = hoy.year, hoy.month
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def _nombre_mes(mes):
    return f"{_MESES[int(mes[5:]) - 1]} {mes[:4]}"


# ── Secciones ─────────────────────────────────────────────────────────────────

def _sec_meses(db, hoy):
    from modules.finanzas.budget import _calc_budget, _meta_ahorro
    filas, por_cat, n_meses = [], {}, 0
    ultimos3 = {}
    meses = _meses_atras(hoy, 13)
    for i, mes in enumerate(meses):
        bd = _calc_budget(mes, db)
        if not bd['n_movimientos']:
            continue
        b = bd['buckets']
        ing = bd['ingreso_total']
        gasto = bd['consumo']
        nota = ' (en curso)' if bd['es_mes_actual'] else ''
        filas.append([
            _nombre_mes(mes) + nota, _mx(bd['ingreso_recurrente']), _mx(bd['ingreso_extraordinario']),
            _mx(gasto), _mx(b['necesidades']['total_gastado']), _mx(b['deseos']['total_gastado']),
            _mx(b['ahorro_deuda']['total_gastado'] - bd['inversion_neta']), _mx(bd['inversion_neta']),
            _mx(ing - gasto), _pct(ing - gasto, ing),
        ])
        if bd['es_mes_actual']:
            continue
        n_meses += 1
        for bk in b.values():
            for c in bk['cats']:
                if c.get('inversion'):   # va en su columna, no es gasto
                    continue
                k = c['nombre']
                por_cat[k] = por_cat.get(k, 0) + c['gastado']
                if i >= len(meses) - 4:
                    ultimos3[k] = ultimos3.get(k, 0) + c['gastado']
    txt = ["## Mes a mes (últimos 12 meses y el actual)",
           "Gasto = consumo (no incluye inversiones). «Deudas y ahorro en gasto» son pagos de deudas y "
           "gastos categorizados como ahorro. «Inversión neta» = aportaciones − retiros a inversiones "
           "(negativa si saqué dinero). Ahorro = ingreso total − gasto.",
           _tabla(['Mes', 'Ingreso recurrente', 'Extraordinario', 'Gasto', 'Necesidades', 'Deseos',
                   'Deudas y ahorro en gasto', 'Inversión neta', 'Ahorro', 'Tasa de ahorro'], filas) if filas else '_Sin movimientos._',
           f"Meta mínima de ahorro mensual configurada: {_mx(_meta_ahorro(db))}"]
    if por_cat and n_meses:
        top = sorted(por_cat.items(), key=lambda kv: -kv[1])
        txt += [f"## Gasto por categoría ({n_meses} meses cerrados)",
                _tabla(['Categoría', 'Total', 'Promedio mensual', 'Promedio últimos 3 meses'],
                       [[k, _mx(v), _mx(v / n_meses), _mx(ultimos3.get(k, 0) / 3)] for k, v in top])]
    return '\n\n'.join(txt)


def _sec_comercios(db, hoy):
    from modules.finanzas.budget import _GASTO_WHERE
    desde = _meses_atras(hoy, 4)[0] + '-01'
    rows = db.execute(f"""
        SELECT descripcion, categoria, COUNT(*) AS n, SUM(COALESCE(mi_parte, monto)) AS total
        FROM est_movimientos
        WHERE tipo='GASTO' AND {_GASTO_WHERE} AND fecha >= ?
        GROUP BY UPPER(descripcion) ORDER BY total DESC LIMIT 20
    """, (desde,)).fetchall()
    subs = db.execute(f"""
        SELECT descripcion, COUNT(*) AS n, SUM(COALESCE(mi_parte, monto)) AS total, MAX(substr(fecha,1,10)) AS ultima
        FROM est_movimientos
        WHERE tipo='GASTO' AND {_GASTO_WHERE} AND fecha >= ? AND subcategoria LIKE 'Suscripciones%'
        GROUP BY UPPER(descripcion) ORDER BY total DESC
    """, (desde,)).fetchall()
    txt = [f"## Dónde se va el dinero (desde {desde})",
           _tabla(['Comercio / concepto', 'Categoría', 'Veces', 'Total'],
                  [[r['descripcion'], r['categoria'], r['n'], _mx(r['total'])] for r in rows])
           if rows else '_Sin gastos._']
    if subs:
        txt += ["### Suscripciones",
                _tabla(['Servicio', 'Cobros', 'Total', 'Último cobro'],
                       [[r['descripcion'], r['n'], _mx(r['total']), r['ultima']] for r in subs])]
    return '\n\n'.join(txt)


def _sec_patrimonio(db, hoy):
    from modules.finanzas.salud import _compute_patrimonio
    from modules.finanzas.inversiones import _portafolio
    pat = _compute_patrimonio()
    port = _portafolio(db)
    txt = ["## Patrimonio e inversiones",
           _tabla(['Concepto', 'Monto'], [
               ['Activos totales', _mx(pat['total_activos'])],
               ['Líquido (efectivo y bancos)', _mx(pat['liquido'])],
               ['Bienes', _mx(pat['total_bienes'])],
               ['Pasivos (tarjetas y créditos capturados)', _mx(pat['total_pasivos'])],
               ['Patrimonio neto', _mx(pat['patrimonio_neto'])],
           ])]
    if port['plataformas']:
        txt += ["### Inversiones por plataforma",
                _tabla(['Plataforma', 'Saldo', 'Aportado', 'Retirado', 'Rendimiento', '% del portafolio'],
                       [[p['label'], _mx(p['saldo']), _mx(p['aportado']), _mx(p['retirado']),
                         _mx(p['rendimiento']), f"{p['pct']} %"] for p in port['plataformas']]),
                f"Total invertido: {_mx(port['saldo_total'])}"]
    hist = pat['historial']
    if len(hist) >= 2:
        txt += ["### Evolución del patrimonio neto",
                _tabla(['Fecha', 'Patrimonio neto'], [[h['fecha'], _mx(h['patrimonio_neto'])] for h in hist])]
    return '\n\n'.join(txt)


def _sec_deudas(db, hoy):
    from modules.finanzas.estados.routes import msi_por_pagar
    activos, _ = msi_por_pagar()
    txt = ["## Deudas: compras a meses por pagar"]
    if activos:
        txt += [_tabla(['Compra', 'Banco', 'Cuota', 'Pagadas', 'Faltan', 'Restante'],
                       [[a['descripcion'], a['banco'], _mx(a['cuota']), f"{a['pagadas']}/{a['mensualidades']}",
                         a['faltan'], _mx(a['restante'])] for a in sorted(activos, key=lambda a: -a['restante'])]),
                f"Total por pagar a MSI: {_mx(sum(a['restante'] for a in activos))}; "
                f"cuota mensual: {_mx(sum(a['cuota'] for a in activos))}"]
    else:
        txt.append('_Sin compras a meses activas._')
    return '\n\n'.join(txt)


def _sec_prestamos(db, hoy):
    from modules.finanzas.estados.prestamos import resumen
    r = resumen(db)
    txt = ["## Dinero que presté",
           f"Por cobrar: {_mx(r['total_pendiente'])} · dado por perdido: {_mx(r['total_perdido'])}"]
    if r['personas']:
        filas = []
        for g in r['personas']:
            ultimo = max((p['fecha'] or '')[:10] for p in g['prestamos'])
            estados = sorted({p['estado'] for p in g['prestamos']})
            filas.append([g['persona'], _mx(g['prestado']), _mx(g['devuelto']), _mx(g['pendiente']),
                          ', '.join(estados), ultimo])
        txt.append(_tabla(['Persona', 'Prestado', 'Devuelto', 'Pendiente', 'Estado', 'Último préstamo'], filas))
    return '\n\n'.join(txt)


def _sec_viajes(db, hoy):
    from modules.finanzas.estados.routes import _GASTO_FILTER, _MONTO
    desde = _meses_atras(hoy, 13)[0] + '-01'
    rows = db.execute(f"""
        SELECT v.nombre, v.fecha_inicio, v.fecha_fin,
               (SELECT COALESCE(SUM({_MONTO}), 0) FROM est_movimientos WHERE viaje_id=v.id AND {_GASTO_FILTER}) AS gasto,
               (SELECT COALESCE(SUM(ABS(monto)), 0) FROM est_movimientos
                 WHERE viaje_id=v.id AND tipo='INGRESO' AND COALESCE(subcategoria,'') != 'Reembolso compartido') AS te_pagaron
        FROM viajes v WHERE v.fecha_inicio >= ? ORDER BY v.fecha_inicio
    """, (desde,)).fetchall()
    rows = [r for r in rows if r['gasto']]
    if not rows:
        return "## Viajes\n\n_Sin viajes con gastos en los últimos 12 meses._"
    return '\n\n'.join(["## Viajes (últimos 12 meses)",
                      _tabla(['Viaje', 'Fechas', 'Gastado', 'Te pagaron', 'Neto'],
                             [[r['nombre'], f"{r['fecha_inicio']} a {r['fecha_fin']}", _mx(r['gasto']),
                               _mx(r['te_pagaron']), _mx(r['gasto'] - r['te_pagaron'])] for r in rows])])


SECCIONES = (('Mes a mes', _sec_meses), ('Patrimonio', _sec_patrimonio), ('Deudas', _sec_deudas),
             ('Préstamos', _sec_prestamos), ('Comercios', _sec_comercios), ('Viajes', _sec_viajes))


def generar(db, hoy=None) -> str:
    hoy = hoy or now_local().date()
    partes = [PROMPT, '---', f"# Mis datos al {hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}"]
    for nombre, fn in SECCIONES:
        try:
            partes.append(fn(db, hoy))
        except Exception as e:   # una sección rota no tumba el archivo
            print(f"[coach] sección {nombre}: {e}")
            partes.append(f"## {nombre}\n\n_No se pudo calcular esta sección._")
    return '\n\n'.join(partes) + '\n'


# ── Vistas ────────────────────────────────────────────────────────────────────

@coach_bp.route('/')
def index():
    return render_template('finanzas/coach.html')


@coach_bp.route('/descargar')
def descargar():
    hoy = now_local().date()
    with get_db() as db:
        md = generar(db, hoy)
    return Response(md, mimetype='text/markdown; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename="coach-financiero-{hoy.isoformat()}.md"'})
