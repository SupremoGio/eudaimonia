"""
Reconciliar un corte de tarjeta contra su PDF (fuente de verdad).

Caso real (BBVA Crédito, cortes jul/ago 2026): el corte quedó en la base con
descripciones corridas un renglón respecto a su monto («DQ PROVIDENCIA $57»
cuando en el PDF DQ es $614 y los $57 son de Alta Proteína), duplicados con
otra fecha y 22 movimientos que nunca entraron (mensualidades a MSI
incluidas). Re-importar no lo arregla: el dedup ve «ya existe» algo con ese
día y monto.

Algoritmo, solo sobre las filas de ese banco dentro del periodo del PDF:
  1. Cada renglón del PDF se casa con la fila de la base cuya DESCRIPCIÓN se
     parece más (la clasificación del usuario sigue a la descripción: marcó
     EXPENSE «Alta Proteína», no «$279.95»); a igual parecido, gana el mismo
     monto y luego la fecha más cercana. Sin descripción parecida, solo se
     casa si coincide monto y la fecha está a ≤2 días.
  2. Fila casada: toma fecha, descripción, monto, periodo y MSI del PDF y
     conserva categoría/subcategoría/tipo/mi parte/estatus (lo del usuario).
  3. Fila de la base sin pareja: sobra (duplicado o mal importada) y se
     borra, salvo que esté ligada a un lote o préstamo (se reporta).
  4. Renglón del PDF sin pareja: faltaba y se inserta.
Con dry_run=True solo devuelve el plan.
"""
import re
from datetime import date

_STOP = frozenset({'DE', 'LA', 'EL', 'LOS', 'LAS', 'MX', 'MEX', 'SA', 'CV', 'DEL', 'Y'})


def _tokens(desc):
    return [w for w in re.findall(r'[A-ZÁÉÍÓÚÑ]{2,}', (desc or '').upper()) if w not in _STOP]


def _igual(x, y):
    return x == y or (min(len(x), len(y)) >= 3 and (x.startswith(y) or y.startswith(x)))


def _sim(a, b):
    """Palabras compartidas; una cuenta si es igual o una es prefijo (≥3) de
    la otra («AMER»/«AMERICAS», «PRO»/«PROTGAMA»). La primera palabra (el
    comercio) tiene que coincidir: «REST QIN MIDTOWN» no es «FRESKO MIDTOWN»
    aunque compartan la plaza."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb or not _igual(ta[0], tb[0]):
        return 0
    n = 0
    for x in ta:
        if any(_igual(x, y) for y in tb):
            n += 1
    return n


def _d(s):
    return date.fromisoformat(s[:10])


def _ligada(db, mid):
    return any(db.execute(f"SELECT 1 FROM {t} WHERE movimiento_id=?", (mid,)).fetchone() for t in (
        'est_expense_lote_gastos', 'est_expense_lote_depositos', 'est_prestamo_devoluciones', 'est_prestamos'))


def reconciliar(db, movimientos, banco, dry_run=True):
    """`movimientos`: salida del parser (un solo periodo). Devuelve el plan
    (y lo aplica si dry_run=False)."""
    periodos = {m.get('periodo') for m in movimientos if m.get('periodo')}
    if len(periodos) != 1:
        raise ValueError('El PDF debe traer un solo periodo de corte.')
    periodo = periodos.pop()
    ini, fin = periodo.split(' al ')
    base = [dict(r) for r in db.execute(
        "SELECT * FROM est_movimientos WHERE banco=? AND substr(fecha,1,10) BETWEEN ? AND ?",
        (banco, ini, fin)).fetchall()]

    pares = []
    for i, m in enumerate(movimientos):
        for r in base:
            s = _sim(m['descripcion'], r['descripcion'])
            mismo = abs(abs(float(r['monto'])) - abs(float(m['monto']))) < 0.005
            dias = abs((_d(r['fecha']) - _d(m['fecha'])).days)
            if s == 0 and not (mismo and dias <= 2):
                continue
            if dias > 20:
                continue
            pares.append((-s, 0 if mismo else 1, dias, i, r['id']))
    pares.sort()
    usados_pdf, usados_db, casados = set(), set(), []
    for _, _, _, i, rid in pares:
        if i in usados_pdf or rid in usados_db:
            continue
        usados_pdf.add(i); usados_db.add(rid)
        casados.append((movimientos[i], next(r for r in base if r['id'] == rid)))

    plan = {'periodo': periodo, 'pdf': len(movimientos), 'base': len(base),
            'corregidos': [], 'iguales': 0, 'borrados': [], 'ligados_sin_pareja': [], 'insertados': []}
    for m, r in casados:
        # Signo: la base guarda los pagos a la tarjeta en positivo como
        # movimiento interno; se respeta el signo que ya tenía.
        monto = abs(float(m['monto'])) if float(r['monto']) >= 0 else -abs(float(m['monto']))
        cambios = {}
        if r['descripcion'] != m['descripcion']:
            cambios['descripcion'] = m['descripcion']
        if abs(float(r['monto']) - monto) >= 0.005:
            cambios['monto'] = monto
        if (r['fecha'] or '')[:10] != m['fecha']:
            cambios['fecha'] = m['fecha']
            cambios['fecha_cargo'] = m.get('fecha_cargo') or m['fecha']
        if (r['periodo'] or '') != periodo:
            cambios['periodo'] = periodo
        for k in ('parcialidad_num', 'parcialidad_total', 'compra_msi_id'):
            if m.get(k) and r.get(k) != m.get(k):
                cambios[k] = m[k]
        if cambios:
            plan['corregidos'].append({'id': r['id'], 'antes': f"{r['fecha'][:10]} {r['descripcion']} ${abs(float(r['monto'])):,.2f}",
                                       'despues': f"{m['fecha']} {m['descripcion']} ${abs(float(m['monto'])):,.2f}",
                                       'categoria': r['categoria'], 'cambios': cambios})
        else:
            plan['iguales'] += 1
    for r in base:
        if r['id'] in usados_db:
            continue
        item = {'id': r['id'], 'fila': f"{r['fecha'][:10]} {r['descripcion']} ${abs(float(r['monto'])):,.2f} ({r['categoria']})"}
        (plan['ligados_sin_pareja'] if _ligada(db, r['id']) else plan['borrados']).append(item)
    for i, m in enumerate(movimientos):
        if i not in usados_pdf:
            plan['insertados'].append(m)

    if not dry_run:
        # Primero borrar (libera el índice único fecha+descripción+monto),
        # luego corregir y al final insertar lo que faltaba.
        for b in plan['borrados']:
            db.execute("DELETE FROM est_movimientos WHERE id=?", (b['id'],))
        for c in plan['corregidos']:
            cols = list(c['cambios'])
            db.execute(f"UPDATE OR IGNORE est_movimientos SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?",
                       (*[c['cambios'][k] for k in cols], c['id']))
        nuevos = []
        for m in plan['insertados']:
            # Una mensualidad a MSI hereda la categoría de su serie (ej.
            # «Anillo Cornelius» en vez de la genérica del keyword).
            if m.get('parcialidad_total'):
                serie = db.execute("""
                    SELECT categoria, subcategoria FROM est_movimientos
                    WHERE banco=? AND (descripcion=? OR descripcion LIKE ?)
                      AND substr(fecha,1,10) < ? AND categoria != 'OTROS'
                    ORDER BY fecha DESC LIMIT 1""",
                    (banco, m['descripcion'], f"__ DE {int(m['parcialidad_total']):02d} {m['descripcion'][:12]}%", m['fecha'])).fetchone()
                if serie:
                    m = {**m, 'categoria': serie['categoria'], 'subcategoria': serie['subcategoria']}
            cur = db.execute("""
                INSERT OR IGNORE INTO est_movimientos
                (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo,
                 parcialidad_num, parcialidad_total, compra_msi_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (m['fecha'], m.get('fecha_cargo', m['fecha']), m['descripcion'], m['monto'], banco, periodo,
                 m['categoria'], m.get('subcategoria', ''), m['tipo'],
                 m.get('parcialidad_num'), m.get('parcialidad_total'), m.get('compra_msi_id')))
            if cur.rowcount:
                nuevos.append(cur.lastrowid)
        plan['nuevos_ids'] = nuevos
    plan['insertados'] = [f"{m['fecha']} {m['descripcion']} ${abs(float(m['monto'])):,.2f}" for m in plan['insertados']]
    return plan


def _cobertura(db, movimientos, banco) -> float:
    """Fracción de renglones del PDF que ya están en la base (fecha + monto)."""
    if not movimientos:
        return 0.0
    hay = sum(1 for m in movimientos if db.execute(
        "SELECT 1 FROM est_movimientos WHERE banco=? AND substr(fecha,1,10)=? AND ABS(ABS(monto)-?) < 0.005 LIMIT 1",
        (banco, m['fecha'], abs(float(m['monto'])))).fetchone())
    return hay / len(movimientos)


def reconciliar_cortes_bbva_tdc_2026(db) -> list:
    """Migración única: reconcilia los cortes jul/ago/sep 2026 de BBVA Crédito
    contra los PDF que el usuario compartió (data/bbva_tdc_cortes_2026_07_09.json),
    y después aplica las reglas de clasificación del usuario a lo nuevo y
    recalcula los lotes de Expense cuyas facturas cambiaron de monto."""
    import json, os
    from . import routes as r
    from . import expense_lotes as lotes
    ruta = os.path.join(os.path.dirname(__file__), 'data', 'bbva_tdc_cortes_2026_07_09.json')
    datos = json.load(open(ruta, encoding='utf-8'))
    resumen = []
    for corte in datos['cortes']:
        # Candado: solo se reconcilia un corte que ya está en la base (al
        # menos la mitad de sus renglones con la misma fecha y monto). En una
        # base vacía o ajena (tests, un volumen nuevo antes de restaurar de
        # Turso) no se toca nada y la migración no se marca como aplicada.
        if _cobertura(db, corte['movimientos'], datos['banco']) < 0.5:
            continue
        plan = reconciliar(db, corte['movimientos'], datos['banco'], dry_run=False)
        resumen.append({'periodo': plan['periodo'], 'corregidos': len(plan['corregidos']),
                        'borrados': len(plan['borrados']), 'insertados': len(plan['nuevos_ids']),
                        'ligados_sin_pareja': len(plan['ligados_sin_pareja'])})
    if not resumen:
        return []
    for f in (r._corregir_spei_invex, r._corregir_zaira_restaurante, r._corregir_walmart_lavadora,
              r._corregir_didi_delivery, r._corregir_amazon_suscripciones, r._corregir_celular,
              r._corregir_expense_terceros, lotes.reafirmar_categorias):
        f(db)
    for (lid,) in db.execute("SELECT id FROM est_expense_lotes").fetchall():
        lotes.sincronizar(db, lid)
    return resumen
