"""
Conciliación de Expense con el export de la plataforma de reembolsos de la
empresa (data/expense_plataforma.json, 176 gastos mar 2024 - jul 2026; el
usuario, 2026-09-28: «ya encontré el csv de la plataforma que paga expense,
con esto ya puedes conciliar todo»).

La plataforma dice QUÉ se reembolsó y cuánto, pero no con qué depósito ni con
qué cargo del banco. Dos pasos:

1. Depósito ↔ gastos de la plataforma. Los depósitos de la empresa sin lote
   (FIDEICOMISO F 1596, SITH2…, EXPENSE BMRCASH; expense_lotes._DEP_RE) se
   atienden del más antiguo al más reciente, y cada uno toma gastos de la
   plataforma de antes de su fecha, en este orden de pasadas:
     - un gasto del mismo monto (≤120 días antes);
     - «FIFO»: los gastos pendientes más antiguos, seguidos, que suman el
       depósito (la empresa paga en orden; ≤185 días);
     - un bloque de gastos seguidos que suma el depósito (≤120 días);
     - cualquier combinación que sume el depósito (≤120, luego ≤240 días).
   Se eligió comparando variantes contra los depósitos de las capturas del
   usuario: así la mediana entre gasto y depósito es de ~24 días y ninguno
   pasa de 6 meses (con ventanas más largas salían emparejamientos de más de
   un año).

2. Gasto de la plataforma ↔ cargo del banco: mismo monto (±$0.01), del día
   del gasto hasta 10 días después (lo que tarda en aparecer el cargo), un
   cargo por gasto; primero los que ya están como EXPENSE.

Con eso se crea un lote por depósito (sus cargos pasan a EXPENSE y quedan
Pagado). Los gastos sin cargo en el banco (efectivo, otra tarjeta sin estado
de cuenta) quedan anotados en las notas del lote.
"""
import json
import os
from datetime import date, timedelta

from . import expense_lotes as _lotes

_ARCHIVO = os.path.join(os.path.dirname(__file__), 'data', 'expense_plataforma.json')
TOL = 1.0
# Cargo del banco: desde 7 días antes del gasto (se pagó y el recibo se
# registró después) hasta 15 días después (lo que tarda en aparecer).
DIAS_ANTES, DIAS_DESPUES = 7, 15


# Gastos del export que no son del usuario (2026-10-05: «servyviajes yo no
# pagué nada de eso», «este tampoco es mío»): (fecha, título, monto).
NO_SON_MIOS = (
    ('2025-12-01', 'SERVIVYAJES', 10461.00),
    ('2025-12-01', 'SERVYVIAJES', 4694.00),
    ('2026-03-04', 'ACTIVIDAD INTEGRACION MARRIOTT BONVOY', 1442.00),
    ('2025-07-06', 'UBER GDL - AEROPUERTO', 364.80),
    ('2025-12-17', 'ACTIVIDAD INTEGRACION MARRIOTT BONVOY', 21273.00),
)


def _no_es_mio(x) -> bool:
    return any(x['fecha'] == f and x['titulo'] == t and abs(x['monto'] - m) < 0.005 for f, t, m in NO_SON_MIOS)


def items() -> list[dict]:
    with open(_ARCHIVO, encoding='utf-8') as fh:
        data = [x for x in json.load(fh)['items'] if not _no_es_mio(x)]
    out = [{**x, 'idx': i} for i, x in enumerate(sorted(data, key=lambda x: (x['fecha'], x['titulo'])))]
    return out


def _exacto(cand, monto, tol):
    uno = [x for x in cand if abs(x['monto'] - monto) <= min(tol, 0.01)]
    return [uno[0]] if uno else None


def _fifo(cand, monto, tol):
    s, out = 0.0, []
    for x in cand:
        s += x['monto']
        out.append(x)
        if abs(s - monto) <= tol:
            return out if len(out) > 1 else None
        if s > monto + tol:
            return None
    return None


def _bloque(cand, monto, tol):
    for i in range(len(cand)):
        s = 0.0
        for j in range(i, len(cand)):
            s += cand[j]['monto']
            if j > i and abs(s - monto) <= tol:
                return cand[i:j + 1]
            if s > monto + tol:
                break
    return None


def _suma(cand, monto, tol):
    idx = _lotes._combinacion([x['monto'] for x in cand], monto, tol)
    return [cand[i] for i in idx] if idx is not None else None


_PASADAS_BASE = (('mismo monto', 120, _exacto), ('FIFO', 185, _fifo), ('bloque', 120, _bloque),
                 ('combinación', 120, _suma), ('combinación', 240, _suma))
# Primero todo lo que cuadra al centavo y después lo que cuadra con hasta $1
# de redondeo: el de $4,365.55 (15/11/2024) cuadra exacto ($4,365.54) con
# Despensa + pasteles + Día del Chef + Corona, pero el de $2,215.60 se los
# ganaba antes con una combinación que daba $2,215.99.
PASADAS = tuple((n, d, f, 0.02) for n, d, f in _PASADAS_BASE) + \
          tuple((n + ' ±$1', d, f, TOL) for n, d, f in _PASADAS_BASE if f is not _exacto)


def _ventana(d, gastos, libres, dias):
    desde = (date.fromisoformat(d['fecha'][:10]) - timedelta(days=dias)).isoformat()
    return [x for x in gastos if x['idx'] in libres and desde <= x['fecha'] <= d['fecha'][:10]]


def _emparejar(d, gastos, libres):
    for nombre, dias, fn, tol in PASADAS:
        cand = _ventana(d, gastos, libres, dias)
        sel = fn(cand, float(d['monto']), tol) if cand else None
        if sel:
            return nombre, sel
    return None


# Emparejamientos aproximados aceptados por el usuario (2026-09-28, «dalos por
# buenos»): (fecha, monto) del depósito -> títulos de los gastos. El de
# $738.70 del 30/08/2024 con confeti + globos del aniversario + pastel agosto
# ($767.68; la empresa rechazó $28.98).
APROXIMADOS = {('2024-08-30', 738.70): ('CONFETI AC ANIVERSARIO', 'GLOBOS AC ANIVERSARIO', 'pastel agosto')}


def _es(d, clave) -> bool:
    return d['fecha'][:10] == clave[0] and abs(float(d['monto']) - clave[1]) < 0.005


def asignar(depositos: list[dict], gastos: list[dict]) -> dict:
    """depósito id -> (pasada, [gastos de la plataforma])."""
    usados, res = set(), {}
    for clave, titulos in APROXIMADOS.items():
        d = next((d for d in depositos if _es(d, clave)), None)
        sel = [next((x for x in gastos if x['titulo'] == t and x['idx'] not in usados and x['fecha'] <= clave[0]), None)
               for t in titulos]
        if d and all(sel):
            usados.update(x['idx'] for x in sel)
            res[d['id']] = ('aproximado (aceptado)', sel)
    for nombre, dias, fn, tol in PASADAS:
        for d in depositos:
            if d['id'] in res:
                continue
            desde = (date.fromisoformat(d['fecha'][:10]) - timedelta(days=dias)).isoformat()
            cand = [x for x in gastos if x['idx'] not in usados and desde <= x['fecha'] <= d['fecha'][:10]]
            sel = fn(cand, float(d['monto']), tol) if cand else None
            if sel:
                usados.update(x['idx'] for x in sel)
                res[d['id']] = (nombre, sel)
    # Reparación: un depósito sin pareja puede tomar gastos que se quedó otro
    # depósito cercano, si ese otro se puede volver a emparejar con gastos
    # libres (p. ej. un depósito de $561 tomó uno de los dos pasteles de $561
    # que necesitaba el de $2,973.24 del Día de las Madres).
    por_idx = {x['idx']: x for x in gastos}
    for u in depositos:
        if u['id'] in res:
            continue
        ventana_u = {x['idx'] for x in _ventana(u, gastos, set(por_idx), PASADAS[-1][1])}
        for m in depositos:
            if m['id'] not in res or m['id'] == u['id']:
                continue
            _, sel_m = res[m['id']]
            if not {x['idx'] for x in sel_m} & ventana_u:
                continue
            libres = (set(por_idx) - usados) | {x['idx'] for x in sel_m}
            nuevo_u = _emparejar(u, gastos, libres)
            if not nuevo_u:
                continue
            nuevo_m = _emparejar(m, gastos, libres - {x['idx'] for x in nuevo_u[1]})
            if not nuevo_m:
                continue
            usados -= {x['idx'] for x in sel_m}
            usados |= {x['idx'] for x in nuevo_u[1]} | {x['idx'] for x in nuevo_m[1]}
            res[u['id']] = (nuevo_u[0] + ' (reparado)', nuevo_u[1])
            res[m['id']] = (nuevo_m[0], nuevo_m[1])
            break
    return res


def _cargos_libres(db) -> list[dict]:
    """Cargos que pueden ser un gasto de Expense: compras con tarjeta y también
    transferencias BNET/SPEI a un proveedor (FINANZAS/Transferencia…)."""
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, categoria, banco
        FROM est_movimientos
        WHERE tipo IN ('GASTO', 'PAGO') AND categoria NOT IN ('PAGO_TDC', 'PRESTAMOS', 'INVERSION')
          AND NOT (categoria = 'FINANZAS' AND COALESCE(subcategoria, '') NOT IN
                   ('Transferencia', 'Transferencia enviada', ''))
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_gastos)
        ORDER BY CASE WHEN categoria = 'EXPENSE' THEN 0 ELSE 1 END, fecha, id
    """).fetchall()]


def _cargo_de(item, cargos, usados):
    f = date.fromisoformat(item['fecha'])
    desde, hasta = (f - timedelta(days=DIAS_ANTES)).isoformat(), (f + timedelta(days=DIAS_DESPUES)).isoformat()
    candidatos = [c for c in cargos if c['id'] not in usados and desde <= c['fecha'] <= hasta
                  and abs(c['monto'] - item['monto']) <= 0.01]
    # Primero los que ya son EXPENSE (vienen ordenados así) y, entre iguales, el más cercano en fecha.
    candidatos.sort(key=lambda c: (c['categoria'] != 'EXPENSE', abs((date.fromisoformat(c['fecha']) - f).days)))
    return candidatos[0] if candidatos else None


# Depósitos que no pagan gastos de la plataforma (el usuario, 2026-09-28): el
# de $561 del 28/05/2024 se quedaba con uno de los dos pasteles de $561 del
# Día de las Madres que necesita el de $2,973.24 del 20/05/2024 («sí, quita
# ese de 561 para que cuadre»).
DEPOSITOS_FUERA = (('2024-05-28', 561.0),)

# Depósitos que pagaron viáticos, no gastos de la plataforma (el usuario,
# 2026-09-28: «esos mételos como pagado de viáticos»): ninguna combinación de
# gastos del export los forma. El de $512 del 13/09/2024 se suma aquí porque
# el confeti y los globos que lo aproximaban ya los tomó el de $738.70.
VIATICOS = (('2024-06-04', 2414.94), ('2024-07-02', 1561.68), ('2024-08-13', 1815.63),
            ('2024-09-13', 512.00), ('2025-04-30', 4828.01))


def _fuera(d) -> bool:
    return any(_es(d, c) for c in DEPOSITOS_FUERA)


def _viaticos(d) -> bool:
    return any(_es(d, c) for c in VIATICOS)


def liberar_lotes_plataforma(db) -> int:
    """Borra los lotes que creó la conciliación con la plataforma (notas
    «Plataforma de Expense…»; los armados a mano no se tocan) para volver a
    armarlos todos juntos con la asignación corregida. Sus cargos siguen en
    EXPENSE y quedan libres; el depósito queda sin lote hasta reconciliar."""
    lotes = [r[0] for r in db.execute(
        "SELECT id FROM est_expense_lotes WHERE notas LIKE 'Plataforma de Expense%'").fetchall()]
    for lid in lotes:
        gastos = [g[0] for g in db.execute("SELECT movimiento_id FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))]
        db.execute("DELETE FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lote_depositos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lotes WHERE id=?", (lid,))
        for gid in gastos:
            db.execute("""UPDATE est_movimientos SET estatus_reembolso=NULL, fecha_reembolso=NULL
                          WHERE id=? AND COALESCE(estatus_reembolso,'') != ?""", (gid, _lotes.ESTATUS_TERCERO))
    return len(lotes)


def _depositos_empresa(db) -> list[dict]:
    """Todos los depósitos de la empresa, estén o no en un lote: la asignación
    se recalcula siempre sobre todos para que los gastos que ya pagó un lote
    no se vuelvan a ofrecer a otro depósito."""
    return [{**dict(r), 'monto': round(float(r['monto']), 2)} for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, banco,
               id IN (SELECT movimiento_id FROM est_expense_lote_depositos) AS en_lote
        FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ('FINANZAS', 'EXPENSE')
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY fecha, id
    """).fetchall() if _lotes._DEP_RE.search(r['descripcion'] or '') and not _fuera(r) and not _viaticos(r)]


def _depositos_viaticos(db) -> list[dict]:
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ('FINANZAS', 'EXPENSE')
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY fecha, id
    """).fetchall() if _lotes._DEP_RE.search(r['descripcion'] or '') and _viaticos(r)]


def plan(db) -> list[dict]:
    """Lo que conciliar() haría, sin tocar nada (para revisar)."""
    todos = _depositos_empresa(db)
    asign = asignar(todos, items())
    deps = [d for d in todos if not d['en_lote']]
    cargos, usados, out = _cargos_libres(db), set(), []
    for d in deps:
        if d['id'] not in asign:
            out.append({'deposito': d, 'pasada': None, 'gastos': []})
            continue
        pasada, sel = asign[d['id']]
        gastos = []
        for it in sel:
            c = _cargo_de(it, cargos, usados)
            if c:
                usados.add(c['id'])
            gastos.append({**it, 'cargo': c})
        out.append({'deposito': d, 'pasada': pasada, 'gastos': gastos})
    return out


def asignacion_completa(db) -> dict:
    """Para revisar: cada depósito de la empresa con los gastos de la
    plataforma que le tocan (esté o no en lote) y los gastos que no quedaron
    en ningún depósito."""
    todos = _depositos_empresa(db)
    it = items()
    asign = asignar(todos, it)
    usados = {x['idx'] for _, sel in asign.values() for x in sel}
    return {
        'depositos': [{**d, 'pasada': asign.get(d['id'], (None, []))[0],
                       'gastos': asign.get(d['id'], (None, []))[1]} for d in todos],
        'sin_deposito': [x for x in it if x['idx'] not in usados],
    }


def posibles_cargos(db, item, dias: int = 45) -> list[dict]:
    """Para revisar un gasto «sin cargo»: movimientos del mismo monto (±$0.01)
    a ±dias, de cualquier categoría, y si ya están en un lote."""
    f = date.fromisoformat(item['fecha'])
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, categoria, subcategoria, tipo, banco,
               id IN (SELECT movimiento_id FROM est_expense_lote_gastos) AS en_lote
        FROM est_movimientos
        WHERE ABS(ABS(monto) - ?) <= 0.01 AND substr(fecha,1,10) BETWEEN ? AND ?
        ORDER BY fecha
    """, (item['monto'], (f - timedelta(days=dias)).isoformat(), (f + timedelta(days=dias)).isoformat())).fetchall()]


def conciliar(db) -> list[str]:
    """Crea un lote por depósito emparejado; devuelve un resumen por lote."""
    hechos = []
    for p in plan(db):
        if not p['pasada']:
            continue
        d = p['deposito']
        if d.get('en_lote'):
            continue
        con = [g for g in p['gastos'] if g['cargo']]
        sin = [g for g in p['gastos'] if not g['cargo']]
        notas = f"Plataforma de Expense ({p['pasada']}): {len(p['gastos'])} gastos"
        if sin:
            notas += " · sin cargo en el banco: " + "; ".join(f"{g['fecha']} {g['titulo']} ${g['monto']:,.2f}" for g in sin)
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (f"Expense {d['fecha'][:10]}", notas[:300], _lotes.ahora())).lastrowid
        for g in con:
            db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='' WHERE id=?", (g['cargo']['id'],))
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, g['cargo']['id'], _lotes.ahora()))
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (d['id'],))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, d['id'], _lotes.ahora()))
        _lotes.sincronizar(db, lid)
        hechos.append(f"{d['fecha'][:10]} ${float(d['monto']):,.2f}: {len(con)} cargos"
                      + (f", {len(sin)} sin cargo" if sin else ""))
    # Los de viáticos quedan en un lote propio sin gastos: así salen de
    # «depósitos sin lote» / «sin conciliar» y el nombre dice qué pagaron.
    for d in _depositos_viaticos(db):
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (f"Viáticos {d['fecha']}", "Plataforma de Expense: pagado de viáticos (sin gastos en la plataforma)",
                          _lotes.ahora())).lastrowid
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (d['id'],))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, d['id'], _lotes.ahora()))
        hechos.append(f"{d['fecha']} ${float(d['monto']):,.2f}: viáticos")
    return hechos
