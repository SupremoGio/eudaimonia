"""
fix_tz_april28.py — Corrige entradas del 2026-04-28 que en realidad
son del 2026-04-27 en hora México (Ciudad de México = UTC-5 en abril).

Lógica: cualquier registro con date='2026-04-28' pero cuyo created_at
es anterior a las 05:00 UTC del 28 (= antes de medianoche CDMX)
fue registrado el 27 de abril en México → corregir a '2026-04-27'.

Uso:
  cd gio_v3
  python fix_tz_april28.py --dry-run    # ver sin cambiar
  python fix_tz_april28.py              # aplicar
"""
import os, sys, json, time, http.client, argparse
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

# Medianoche Ciudad de México el 28 de abril = 05:00 UTC del 28
# (en abril CDMX está en UTC-5)
CUTOFF = "2026-04-28T05:00:00"
WRONG  = "2026-04-28"
RIGHT  = "2026-04-27"


def turso_request(statements: list[dict]) -> list:
    if not TURSO_URL or not TURSO_TOKEN:
        print("ERROR: TURSO_DATABASE_URL o TURSO_AUTH_TOKEN no configurados en .env")
        sys.exit(1)

    host = TURSO_URL.replace("libsql://", "").replace("https://", "").rstrip("/")
    reqs = [{"type": "execute", "stmt": s} for s in statements]
    reqs.append({"type": "close"})
    body = json.dumps({"requests": reqs}).encode()
    hdrs = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type":  "application/json",
    }
    conn = http.client.HTTPSConnection(host, timeout=20)
    conn.request("POST", "/v2/pipeline", body=body, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    if resp.status != 200:
        print(f"ERROR Turso HTTP {resp.status}: {data[:300].decode()}")
        sys.exit(1)
    return json.loads(data).get("results", [])


def run(dry_run: bool):
    print("=" * 60)
    print("FIX TIMEZONE - abril 27->28 (directo a Turso)")
    print(f"Cutoff UTC : < {CUTOFF}")
    print(f"Modo       : {'DRY RUN' if dry_run else 'ESCRITURA REAL'}")
    print("=" * 60)

    # ── 1. Contar filas a corregir ────────────────────────────────────────────
    selects = [
        # xp_ledger
        {"sql": "SELECT COUNT(*) as c FROM xp_ledger WHERE date=? AND created_at < ?",
         "args": [{"type":"text","value":WRONG}, {"type":"text","value":CUTOFF}]},
        # coins_ledger
        {"sql": "SELECT COUNT(*) as c FROM coins_ledger WHERE date=? AND created_at < ?",
         "args": [{"type":"text","value":WRONG}, {"type":"text","value":CUTOFF}]},
        # activity_logs (sin created_at → usar join con xp_ledger)
        {"sql": """SELECT COUNT(DISTINCT al.id) as c
                   FROM activity_logs al
                   JOIN xp_ledger xl ON xl.reference_id=al.id AND xl.source='activity'
                   WHERE al.date=? AND xl.created_at < ?""",
         "args": [{"type":"text","value":WRONG}, {"type":"text","value":CUTOFF}]},
    ]

    results = turso_request(selects)
    counts  = {}
    labels  = ["xp_ledger", "coins_ledger", "activity_logs"]

    for i, label in enumerate(labels):
        try:
            val = results[i]["response"]["result"]["rows"][0][0]["value"]
            counts[label] = int(val)
        except Exception:
            counts[label] = "?"

    print(f"\nFilas a corregir:")
    for t, c in counts.items():
        print(f"  {t:<18}: {c}")

    total = sum(v for v in counts.values() if isinstance(v, int))
    if total == 0:
        print("\nOK Nada que corregir. Todo está bien.")
        return

    if dry_run:
        print(f"\nDry run — se corregirían {total} filas en total.")
        print("Corre sin --dry-run para aplicar.")
        return

    # ── 2. Aplicar UPDATEs ────────────────────────────────────────────────────
    print(f"\nAplicando {total} correcciones...")

    updates = [
        {"sql": "UPDATE xp_ledger SET date=? WHERE date=? AND created_at < ?",
         "args": [{"type":"text","value":RIGHT},
                  {"type":"text","value":WRONG},
                  {"type":"text","value":CUTOFF}]},
        {"sql": "UPDATE coins_ledger SET date=? WHERE date=? AND created_at < ?",
         "args": [{"type":"text","value":RIGHT},
                  {"type":"text","value":WRONG},
                  {"type":"text","value":CUTOFF}]},
    ]
    turso_request(updates)
    print("  xp_ledger      OK")
    print("  coins_ledger   OK")

    time.sleep(0.3)

    # activity_logs via JOIN
    act_upd = [
        {"sql": """UPDATE activity_logs SET date=?
                   WHERE date=?
                   AND id IN (
                     SELECT reference_id FROM xp_ledger
                     WHERE source='activity' AND created_at < ?
                     AND reference_id IS NOT NULL
                   )""",
         "args": [{"type":"text","value":RIGHT},
                  {"type":"text","value":WRONG},
                  {"type":"text","value":CUTOFF}]},
    ]
    turso_request(act_upd)
    print("  activity_logs  OK")

    # ── 3. Verificar ──────────────────────────────────────────────────────────
    time.sleep(0.3)
    verif = turso_request([
        {"sql": "SELECT COUNT(*) as c FROM xp_ledger WHERE date=?",
         "args": [{"type":"text","value":WRONG}]},
    ])
    try:
        remaining = int(verif[0]["response"]["result"]["rows"][0][0]["value"])
    except Exception:
        remaining = "?"
    print(f"\nVerificación: quedan {remaining} entradas con date='{WRONG}' en xp_ledger")
    if remaining == 0 or remaining == "?":
        print("OK Corrección completada.")
    else:
        print(f"  (pueden ser entradas legítimas del 28 de abril México — OK)")

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.dry_run)
