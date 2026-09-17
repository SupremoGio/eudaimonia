#!/usr/bin/env python3
"""
fix_libreton_year_bug.py — Corrige en la DB los movimientos de BBVA Libretón
que quedaron con el año equivocado por el bug arreglado en
modules/finanzas/estados/parsers/bbva_libreton.py (commit "Corregir año
incorrecto en movimientos de diciembre del parser BBVA Libretón").

El bug: en un estado de cuenta cuyo periodo cruza de año (ej. "07/12/2024
al 06/01/2025"), el parser viejo le ponía a TODAS las fechas el año de fin
del periodo — los movimientos de diciembre quedaron guardados con el año
siguiente (ej. "2025-12-07" en vez de "2024-12-07").

Esta corrección usa exactamente esa misma columna `periodo` que ya quedó
guardada en cada fila (formato "DD/MM/YYYY al DD/MM/YYYY") para saber, por
fila, cuál es el año de inicio y el de fin del estado de cuenta de origen,
y así decidir si la fecha guardada necesita corregirse.

Uso:
  cd gio_v3 && python scripts/fix_libreton_year_bug.py                                   # dry-run (no escribe nada)
  cd gio_v3 && python scripts/fix_libreton_year_bug.py --apply                           # corrige fechas
  cd gio_v3 && python scripts/fix_libreton_year_bug.py --apply --delete-duplicates       # corrige fechas y borra duplicados confirmados

Si el mismo estado de cuenta se subió dos veces (antes y después del fix
del parser), la fila vieja (año malo) choca en (fecha, descripcion) con la
fila nueva (año bueno) al intentar corregirla. Cuando además coinciden en
monto y tipo, se clasifica como duplicado confirmado — con
--delete-duplicates se borra la fila vieja (la información ya existe
correcta en la nueva). Si monto o tipo no coinciden, se dejan para revisión
manual y nunca se tocan automáticamente.

Solo toca filas con banco IN ('BBVA_LIB','BBVA_DEB') — se aceptan ambos
valores porque el backfill que unifica BBVA_LIB en BBVA_DEB (ver
database.py) puede haber corrido ya antes que este script; el filtro real
de "es Libretón" es el formato del `periodo` guardado ("DD/MM/YYYY al
DD/MM/YYYY"), así que un BBVA_DEB de otro formato simplemente no matchea
y se ignora. Es seguro correrlo varias veces (idempotente): una fila ya
corregida no vuelve a aparecer como afectada.
"""
import sys, os, re, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db

PERIODO_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s+al\s+(\d{2})/(\d{2})/(\d{4})")


def _fix_date(fecha: str, m1: int, y1: int, m2: int, y2: int) -> str | None:
    """Devuelve la fecha corregida, o None si ya está bien / no aplica."""
    if not fecha or len(fecha) != 10:
        return None
    y, m, d = fecha[:4], fecha[5:7], fecha[8:10]
    try:
        y, mnum = int(y), int(m)
    except ValueError:
        return None
    if mnum == m1 and y != y1:
        return f"{y1}-{m}-{d}"
    if mnum == m2 and y != y2:
        return f"{y2}-{m}-{d}"
    return None


def find_fixes(db):
    """Escanea est_movimientos y devuelve (rows, fixes, duplicates, review).

    fixes: lista de (id, nueva_fecha, nueva_fecha_cargo, fila) a corregir
    directamente (no chocan con ninguna fila existente).

    duplicates: lista de (fila_vieja, fila_correcta_existente) — la fila con
    el año malo choca con otra que YA tiene la fecha correcta y además
    coincide en monto y tipo. Esto pasa cuando el mismo estado de cuenta se
    volvió a subir después del fix del parser: la copia vieja (año malo) y
    la nueva (año bueno) quedaron ambas en la tabla. La fila vieja es un
    duplicado seguro de borrar — la información ya existe correcta en la
    fila nueva.

    review: lista de (fila_vieja, nueva_fecha, fila_existente) — choca con
    otra fila en (fecha, descripcion) pero monto o tipo NO coinciden, así
    que podría ser una coincidencia real (dos transacciones distintas el
    mismo día con la misma descripción) en vez de un duplicado. Nunca se
    toca automáticamente.

    No escribe nada en la DB — solo lee.
    """
    rows = db.execute(
        "SELECT id, fecha, fecha_cargo, descripcion, monto, tipo, periodo "
        "FROM est_movimientos WHERE banco IN ('BBVA_LIB','BBVA_DEB') "
        "AND periodo IS NOT NULL AND periodo != ''"
    ).fetchall()

    fixes = []       # (id, nueva_fecha, nueva_fecha_cargo, fila)
    duplicates = []  # (fila_vieja, fila_correcta_existente)
    review = []      # (fila_vieja, nueva_fecha, fila_existente)
    for r in rows:
        pm = PERIODO_RE.search(r["periodo"] or "")
        if not pm:
            continue
        d1, m1, y1, d2, m2, y2 = pm.groups()
        m1, y1, m2, y2 = int(m1), int(y1), int(m2), int(y2)
        if y1 == y2:
            continue  # periodo dentro de un solo año: no puede estar afectado

        nueva_fecha = _fix_date(r["fecha"], m1, y1, m2, y2) or r["fecha"]
        nueva_fecha_cargo = _fix_date(r["fecha_cargo"], m1, y1, m2, y2) or r["fecha_cargo"]
        if nueva_fecha == r["fecha"] and nueva_fecha_cargo == r["fecha_cargo"]:
            continue  # esta fila ya está bien

        if nueva_fecha != r["fecha"]:
            existing = db.execute(
                "SELECT id, monto, tipo FROM est_movimientos WHERE fecha=? AND descripcion=? AND id != ?",
                (nueva_fecha, r["descripcion"], r["id"]),
            ).fetchone()
            if existing:
                if existing["monto"] == r["monto"] and existing["tipo"] == r["tipo"]:
                    duplicates.append((r, existing))
                else:
                    review.append((r, nueva_fecha, existing))
                continue

        fixes.append((r["id"], nueva_fecha, nueva_fecha_cargo, r))

    return rows, fixes, duplicates, review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Aplica las correcciones de fecha (por defecto solo muestra qué cambiaría).")
    ap.add_argument("--delete-duplicates", action="store_true",
                     help="Además, borra las filas viejas (año malo) que son duplicado confirmado "
                          "(mismo monto y tipo) de una fila que ya tiene la fecha correcta.")
    args = ap.parse_args()

    with get_db() as db:
        rows, fixes, duplicates, review = find_fixes(db)

        print(f"Filas BBVA_LIB/BBVA_DEB con periodo Libretón: revisadas {len(rows)}")
        print(f"Filas a corregir: {len(fixes)}")
        for _id, nf, nfc, r in fixes:
            print(f"  #{_id}  {r['fecha']} -> {nf}   (liq {r['fecha_cargo']} -> {nfc})   "
                  f"${r['monto']:.2f} {r['tipo']:8s} {r['descripcion'][:50]}")

        if duplicates:
            print(f"\nDuplicados confirmados (fila vieja con año malo == misma fila con fecha ya corregida, mismo monto y tipo — se borraría la vieja):")
            for r, existing in duplicates:
                print(f"  #{r['id']} ({r['fecha']}, ${r['monto']:.2f}, {r['tipo']}) es duplicado de #{existing['id']} ya correcta — {r['descripcion'][:50]}")

        if review:
            print(f"\nFilas que NO se pudieron resolver automáticamente (chocan en fecha+descripción pero monto o tipo NO coinciden — revisa a mano si es un duplicado real o una coincidencia):")
            for r, nf, existing in review:
                print(f"  #{r['id']} fecha={r['fecha']} -> {nf} choca con fila #{existing['id']} "
                      f"(monto=${existing['monto']:.2f} tipo={existing['tipo']})  desc={r['descripcion'][:50]}")

        if not fixes and not duplicates:
            print("\nNada que corregir." if not review else "\nNada se corrigió automáticamente — revisa las filas de arriba.")
            return

        if not args.apply:
            print(f"\nDry-run: no se escribió nada. Corre con --apply para aplicar {len(fixes)} correcciones de fecha"
                  + (f" y --delete-duplicates para borrar {len(duplicates)} duplicados." if duplicates else "."))
            return

        for _id, nf, nfc, _r in fixes:
            db.execute(
                "UPDATE est_movimientos SET fecha=?, fecha_cargo=? WHERE id=?",
                (nf, nfc, _id),
            )
        print(f"\nAplicado: {len(fixes)} filas corregidas.")

        if duplicates:
            if args.delete_duplicates:
                for r, _existing in duplicates:
                    db.execute("DELETE FROM est_movimientos WHERE id=?", (r["id"],))
                print(f"Borrados: {len(duplicates)} duplicados confirmados.")
            else:
                print(f"{len(duplicates)} duplicados confirmados sin borrar — corre con --delete-duplicates para borrarlos.")

        db.commit()


if __name__ == "__main__":
    main()
