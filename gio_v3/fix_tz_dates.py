"""
fix_tz_dates.py — One-time migration: corrige fechas UTC-corruptas en la BD.

Problema: Railway corre en UTC. Actividades registradas después de las 18:00
hora México (= 00:00 UTC día siguiente) se guardaron con la fecha UTC incorrecta
en lugar de la fecha México correcta.

Ejemplo real:
  - Usuario registra actividad el 26/04 a las 19:00 México
  - Servidor Railway = 01:00 UTC del 27/04
  - date.today() en UTC → '2026-04-27'  ← INCORRECTO
  - Fix: recalcular desde created_at → '2026-04-26' en México

Uso:
  cd gio_v3
  python fix_tz_dates.py --dry-run     # Ver qué cambiaría sin escribir
  python fix_tz_dates.py               # Aplicar cambios a pipeline.db local

Para Turso (producción Railway):
  python fix_tz_dates.py --turso       # Aplica también en Turso cloud

El script es idempotente: seguro correrlo múltiples veces.
"""
import argparse, os, sys, json, http.client, threading
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

MEXICO  = ZoneInfo("America/Mexico_City")
UTC_TZ  = ZoneInfo("UTC")


# ── Date correction helper ────────────────────────────────────────────────────

def utc_str_to_mexico_date(utc_iso: str) -> str:
    """
    Recalcula la fecha en zona México desde un string UTC ISO (sin tzinfo).
    Ej: '2026-04-27T01:00:00' → '2026-04-26'
    """
    dt = datetime.fromisoformat(utc_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(MEXICO).date().isoformat()


# ── SQLite local fix ──────────────────────────────────────────────────────────

def fix_local(db_path: str, dry_run: bool) -> list[tuple]:
    """
    Corrige xp_ledger, coins_ledger y activity_logs en el SQLite local.
    Devuelve lista de (tabla, id, fecha_vieja, fecha_nueva) para sincronizar a Turso.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    changes = []  # (tabla, id, old_date, new_date)

    # ── xp_ledger ─────────────────────────────────────────────────────────────
    rows = cur.execute(
        "SELECT id, date, created_at FROM xp_ledger WHERE created_at IS NOT NULL"
    ).fetchall()
    xp_fixes = []
    for r in rows:
        try:
            correct = utc_str_to_mexico_date(r["created_at"])
            if correct != r["date"]:
                xp_fixes.append((correct, r["id"], r["date"]))
                changes.append(("xp_ledger", r["id"], r["date"], correct))
        except Exception as e:
            print(f"  WARN xp_ledger id={r['id']}: {e}")

    if xp_fixes:
        print(f"xp_ledger     : {len(xp_fixes)} filas a corregir")
        for new_d, rid, old_d in xp_fixes[:5]:
            print(f"    id={rid}: {old_d} → {new_d}")
        if len(xp_fixes) > 5:
            print(f"    … y {len(xp_fixes) - 5} más")
        if not dry_run:
            cur.executemany("UPDATE xp_ledger SET date=? WHERE id=?",
                            [(d, i) for d, i, _ in xp_fixes])
    else:
        print("xp_ledger     : OK (sin cambios)")

    # ── coins_ledger ──────────────────────────────────────────────────────────
    rows = cur.execute(
        "SELECT id, date, created_at FROM coins_ledger WHERE created_at IS NOT NULL"
    ).fetchall()
    coin_fixes = []
    for r in rows:
        try:
            correct = utc_str_to_mexico_date(r["created_at"])
            if correct != r["date"]:
                coin_fixes.append((correct, r["id"], r["date"]))
                changes.append(("coins_ledger", r["id"], r["date"], correct))
        except Exception as e:
            print(f"  WARN coins_ledger id={r['id']}: {e}")

    if coin_fixes:
        print(f"coins_ledger  : {len(coin_fixes)} filas a corregir")
        if not dry_run:
            cur.executemany("UPDATE coins_ledger SET date=? WHERE id=?",
                            [(d, i) for d, i, _ in coin_fixes])
    else:
        print("coins_ledger  : OK (sin cambios)")

    # ── activity_logs — corregir via xp_ledger.reference_id ─────────────────
    # xp_ledger ya tiene las fechas corregidas en memoria; comparamos con activity_logs
    act_rows = cur.execute(
        """
        SELECT al.id      AS al_id,
               al.date    AS al_date,
               xl.date    AS xl_date
        FROM   activity_logs al
        JOIN   xp_ledger xl
               ON  xl.reference_id = al.id
               AND xl.source       = 'activity'
        WHERE  al.date != xl.date
        """
    ).fetchall()

    # También aplicar las correcciones pendientes de xp_ledger que aún no se committed
    act_fixes = []
    for r in act_rows:
        act_fixes.append((r["xl_date"], r["al_id"], r["al_date"]))
        changes.append(("activity_logs", r["al_id"], r["al_date"], r["xl_date"]))

    # Recalcular después de aplicar xp_fixes en memoria para detectar las nuevas diferencias
    if xp_fixes and not act_fixes:
        # Las correcciones xp todavía no se committed; buscar diferencias manualmente
        xp_correct_map = {rid: new_d for new_d, rid, _ in xp_fixes}
        act_rows2 = cur.execute(
            """SELECT al.id, al.date, xl.reference_id
               FROM activity_logs al
               JOIN xp_ledger xl ON xl.reference_id = al.id AND xl.source = 'activity'"""
        ).fetchall()
        for r in act_rows2:
            if r["reference_id"] in xp_correct_map:
                new_d = xp_correct_map[r["reference_id"]]
                if new_d != r["date"]:
                    act_fixes.append((new_d, r["id"], r["date"]))
                    changes.append(("activity_logs", r["id"], r["date"], new_d))

    act_fixes = list({(d, i): (d, i, o) for d, i, o in act_fixes}.values())  # dedup

    if act_fixes:
        print(f"activity_logs : {len(act_fixes)} filas a corregir")
        for new_d, rid, old_d in act_fixes[:5]:
            print(f"    id={rid}: {old_d} → {new_d}")
        if not dry_run:
            cur.executemany("UPDATE activity_logs SET date=? WHERE id=?",
                            [(d, i) for d, i, _ in act_fixes])
    else:
        print("activity_logs : OK (sin cambios)")

    if not dry_run:
        conn.commit()

    conn.close()
    return changes


# ── Turso cloud sync ──────────────────────────────────────────────────────────

def fix_turso(changes: list[tuple]):
    """Replica los mismos UPDATE en Turso via HTTP pipeline."""
    url   = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not url or not token:
        print("\nTurso: TURSO_DATABASE_URL / TURSO_AUTH_TOKEN no configurados. Saltando.")
        return

    host = url.replace("libsql://", "").replace("https://", "").rstrip("/")

    stmts = []
    for tabla, rid, _, new_d in changes:
        stmts.append({
            "sql":  f"UPDATE {tabla} SET date=? WHERE id=?",
            "args": [{"type": "text", "value": new_d},
                     {"type": "integer", "value": str(rid)}]
        })

    if not stmts:
        print("Turso: nada que sincronizar.")
        return

    BATCH = 20
    total_ok = 0
    for i in range(0, len(stmts), BATCH):
        batch = stmts[i:i + BATCH]
        reqs  = [{"type": "execute", "stmt": s} for s in batch]
        reqs.append({"type": "close"})
        body = json.dumps({"requests": reqs}).encode()
        hdrs = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
        try:
            conn = http.client.HTTPSConnection(host, timeout=15)
            conn.request("POST", "/v2/pipeline", body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            if resp.status != 200:
                print(f"  Turso batch {i}: HTTP {resp.status} — {data[:120]}")
            else:
                total_ok += len(batch)
        except Exception as e:
            print(f"  Turso batch {i} error: {e}")

    print(f"Turso: {total_ok}/{len(stmts)} sentencias aplicadas.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Corrige fechas UTC-corruptas en la BD de Eudaimonia OS"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Muestra qué cambiaría sin escribir nada"
    )
    parser.add_argument(
        "--turso", action="store_true",
        help="Replica los fixes también en Turso cloud (necesita vars de entorno)"
    )
    parser.add_argument(
        "--db", default=None,
        help="Ruta al pipeline.db (default: detecta automáticamente)"
    )
    args = parser.parse_args()

    db_path = args.db or os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.db")
    )

    if not os.path.exists(db_path):
        print(f"ERROR: No se encontró la base de datos en: {db_path}")
        print("Usa --db para especificar la ruta.")
        sys.exit(1)

    print("=" * 60)
    print("FIX TIMEZONE DATES — Eudaimonia OS")
    print(f"BD      : {db_path}")
    print(f"Modo    : {'DRY RUN (sin cambios)' if args.dry_run else 'ESCRITURA REAL'}")
    print(f"Turso   : {'SÍ' if args.turso else 'NO'}")
    print("=" * 60)

    changes = fix_local(db_path, args.dry_run)

    total = len(changes)
    if args.dry_run:
        print(f"\nDry run: se corregirían {total} filas en total.")
        print("Ejecuta sin --dry-run para aplicar los cambios.")
    else:
        print(f"\nLocal OK: {total} filas corregidas.")
        if args.turso and changes:
            print("\nSincronizando a Turso cloud…")
            fix_turso(changes)
        elif args.turso:
            print("Turso: no hay cambios que sincronizar.")

    print("\nDone.")


if __name__ == "__main__":
    main()
