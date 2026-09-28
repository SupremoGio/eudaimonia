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
    """).fetchall() if _lotes._DEP_RE.search(r['descripcion'] or '')]


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
    return hechos
