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
  cd gio_v3 && python scripts/fix_libreton_year_bug.py            # dry-run (no escribe nada)
  cd gio_v3 && python scripts/fix_libreton_year_bug.py --apply    # aplica los cambios

Solo toca filas con banco='BBVA_LIB'. Es seguro correrlo varias veces
(idempotente): una fila ya corregida no vuelve a aparecer como afectada.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Aplica los cambios (por defecto solo muestra qué cambiaría).")
    args = ap.parse_args()

    with get_db() as db:
        rows = db.execute(
            "SELECT id, fecha, fecha_cargo, descripcion, monto, tipo, periodo "
            "FROM est_movimientos WHERE banco='BBVA_LIB' AND periodo IS NOT NULL AND periodo != ''"
        ).fetchall()

        fixes = []      # (id, nueva_fecha, nueva_fecha_cargo, fila)
        collisions = [] # filas que no se pueden corregir sin chocar con otra ya existente
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
                    collisions.append((r, nueva_fecha, existing))
                    continue

            fixes.append((r["id"], nueva_fecha, nueva_fecha_cargo, r))

        print(f"Filas BBVA_LIB con periodo cruzando año: revisadas {len(rows)}")
        print(f"Filas a corregir: {len(fixes)}")
        for _id, nf, nfc, r in fixes:
            print(f"  #{_id}  {r['fecha']} -> {nf}   (liq {r['fecha_cargo']} -> {nfc})   "
                  f"${r['monto']:.2f} {r['tipo']:8s} {r['descripcion'][:50]}")

        if collisions:
            print(f"\nFilas que NO se pudieron corregir automáticamente (ya existe otra fila con la fecha/descripción corregida — revisa a mano si es un duplicado real o una coincidencia):")
            for r, nf, existing in collisions:
                print(f"  #{r['id']} fecha={r['fecha']} -> {nf} choca con fila #{existing['id']} "
                      f"(monto=${existing['monto']:.2f} tipo={existing['tipo']})  desc={r['descripcion'][:50]}")

        if not fixes:
            print("\nNada que corregir." if not collisions else "\nNada se corrigió automáticamente — revisa las colisiones de arriba.")
            return

        if not args.apply:
            print(f"\nDry-run: no se escribió nada. Corre con --apply para aplicar estos {len(fixes)} cambios.")
            return

        for _id, nf, nfc, _r in fixes:
            db.execute(
                "UPDATE est_movimientos SET fecha=?, fecha_cargo=? WHERE id=?",
                (nf, nfc, _id),
            )
        db.commit()
        print(f"\nAplicado: {len(fixes)} filas corregidas.")


if __name__ == "__main__":
    main()
