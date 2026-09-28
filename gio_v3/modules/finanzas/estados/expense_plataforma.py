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
DIAS_CARGO = 10


def items() -> list[dict]:
    with open(_ARCHIVO, encoding='utf-8') as fh:
        data = json.load(fh)['items']
    out = [{**x, 'idx': i} for i, x in enumerate(sorted(data, key=lambda x: (x['fecha'], x['titulo'])))]
    return out


def _exacto(cand, monto):
    uno = [x for x in cand if abs(x['monto'] - monto) <= 0.01]
    return [uno[0]] if uno else None


def _fifo(cand, monto):
    s, out = 0.0, []
    for x in cand:
        s += x['monto']
        out.append(x)
        if abs(s - monto) <= TOL:
            return out if len(out) > 1 else None
        if s > monto + TOL:
            return None
    return None


def _bloque(cand, monto):
    idx = _lotes._bloque_seguido([x['monto'] for x in cand], monto)
    return [cand[i] for i in idx] if idx is not None else None


def _suma(cand, monto):
    idx = _lotes._combinacion([x['monto'] for x in cand], monto)
    return [cand[i] for i in idx] if idx is not None else None


PASADAS = (('mismo monto', 120, _exacto), ('FIFO', 185, _fifo), ('bloque', 120, _bloque),
           ('combinación', 120, _suma), ('combinación', 240, _suma))


def asignar(depositos: list[dict], gastos: list[dict]) -> dict:
    """depósito id -> (pasada, [gastos de la plataforma])."""
    usados, res = set(), {}
    for nombre, dias, fn in PASADAS:
        for d in depositos:
            if d['id'] in res:
                continue
            desde = (date.fromisoformat(d['fecha'][:10]) - timedelta(days=dias)).isoformat()
            cand = [x for x in gastos if x['idx'] not in usados and desde <= x['fecha'] <= d['fecha'][:10]]
            sel = fn(cand, float(d['monto'])) if cand else None
            if sel:
                usados.update(x['idx'] for x in sel)
                res[d['id']] = (nombre, sel)
    return res


def _cargos_libres(db) -> list[dict]:
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, categoria, banco
        FROM est_movimientos
        WHERE tipo IN ('GASTO', 'PAGO') AND categoria NOT IN ('PAGO_TDC', 'FINANZAS', 'PRESTAMOS', 'INVERSION')
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_gastos)
        ORDER BY CASE WHEN categoria = 'EXPENSE' THEN 0 ELSE 1 END, fecha, id
    """).fetchall()]


def _cargo_de(item, cargos, usados):
    hasta = (date.fromisoformat(item['fecha']) + timedelta(days=DIAS_CARGO)).isoformat()
    for c in cargos:
        if c['id'] not in usados and item['fecha'] <= c['fecha'] <= hasta and abs(c['monto'] - item['monto']) <= 0.01:
            return c
    return None


def plan(db) -> list[dict]:
    """Lo que conciliar() haría, sin tocar nada (para revisar)."""
    deps = _lotes._depositos_sin_lote(db)
    asign = asignar(deps, items())
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


def conciliar(db) -> list[str]:
    """Crea un lote por depósito emparejado; devuelve un resumen por lote."""
    hechos = []
    for p in plan(db):
        if not p['pasada']:
            continue
        d = p['deposito']
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
    return hechos
