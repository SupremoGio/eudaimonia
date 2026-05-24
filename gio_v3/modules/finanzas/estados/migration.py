"""
One-time migration: imports transactions from the SG project's local SQLite
(gastos_alto_rendimiento.db) into Eudaimonia's database.

Usage (from the gio_v3/ directory):
    python -m modules.finanzas.estados.migration --db /path/to/gastos_alto_rendimiento.db

On Windows (SG project default path):
    python -m modules.finanzas.estados.migration --db "C:/Users/magos/Desktop/SG_CREDIT_CARD_PROJECT/data/gastos_alto_rendimiento.db"
"""
import argparse
import sqlite3
import sys
from pathlib import Path

# Make Eudaimonia root importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from database import get_db


def migrate(source_path: str, dry_run: bool = False) -> None:
    src_path = Path(source_path)
    if not src_path.exists():
        print(f"[ERROR] No se encontró el archivo: {src_path}")
        sys.exit(1)

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row

    try:
        rows = src.execute(
            "SELECT * FROM movimientos ORDER BY fecha ASC"
        ).fetchall()
    except Exception as e:
        print(f"[ERROR] No se pudo leer la tabla movimientos: {e}")
        sys.exit(1)

    print(f"Encontradas {len(rows)} transacciones en la fuente.")

    if dry_run:
        print("[DRY RUN] No se realizarán cambios.")
        for r in rows[:5]:
            print(f"  {dict(r)}")
        src.close()
        return

    inserted = skipped = errors = 0

    with get_db() as db:
        for row in rows:
            try:
                db.execute("""
                    INSERT OR IGNORE INTO est_movimientos
                    (fecha, fecha_cargo, descripcion, monto, banco,
                     periodo, categoria, subcategoria, tipo)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    row['fecha'],
                    row['fecha_cargo'] or row['fecha'],
                    row['descripcion'],
                    row['monto'],
                    row['banco'],
                    row['periodo'] or '',
                    row['categoria'],
                    row['subcategoria'] or '',
                    row['tipo'],
                ))
                inserted += 1
            except Exception as e:
                print(f"  [SKIP] {row['fecha']} {str(row['descripcion'])[:40]} — {e}")
                errors += 1

        db.commit()

    src.close()
    print(f"\nMigración completada:")
    print(f"  ✓ Insertadas:  {inserted}")
    print(f"  ○ Omitidas (duplicados): {skipped}")
    if errors:
        print(f"  ✗ Errores:    {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra datos de SG Project a Eudaimonia")
    parser.add_argument(
        "--db", required=True,
        help="Ruta al archivo gastos_alto_rendimiento.db del SG project"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Muestra los primeros registros sin insertar nada"
    )
    args = parser.parse_args()
    migrate(args.db, dry_run=args.dry_run)
