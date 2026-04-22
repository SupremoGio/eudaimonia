"""
migrate_to_turso.py — copia pipeline.db local → Turso

Uso:
  set TURSO_DATABASE_URL=libsql://tu-db.turso.io
  set TURSO_AUTH_TOKEN=tu-token
  python migrate_to_turso.py

Seguro de re-ejecutar: usa INSERT OR REPLACE para no duplicar filas.
"""
import os, sqlite3, json, http.client, sys

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
LOCAL_DB    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.db")

if not TURSO_URL or not TURSO_TOKEN:
    print("ERROR: define TURSO_DATABASE_URL y TURSO_AUTH_TOKEN como variables de entorno.")
    sys.exit(1)

HOST = TURSO_URL.replace("libsql://", "")


def _to_arg(v):
    if v is None:           return {"type": "null"}
    if isinstance(v, bool): return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):  return {"type": "integer", "value": str(v)}
    if isinstance(v, float):return {"type": "float",   "value": v}
    return {"type": "text", "value": str(v)}


def turso_pipeline(stmts):
    reqs = [{"type": "execute", "stmt": s} for s in stmts]
    reqs.append({"type": "close"})
    body = json.dumps({"requests": reqs}).encode()
    hdrs = {"Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json"}
    conn = http.client.HTTPSConnection(HOST, timeout=30)
    conn.request("POST", "/v2/pipeline", body=body, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    if resp.status != 200:
        raise Exception(f"HTTP {resp.status}: {data[:200]}")
    return json.loads(data.decode())


def get_tables(local):
    rows = local.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ).fetchall()
    return [(r[0], r[1]) for r in rows if not r[0].startswith("sqlite_")]


def migrate_table(local, name):
    # Create table on Turso (IF NOT EXISTS)
    ddl_row = local.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    if not ddl_row:
        return 0
    ddl = ddl_row[0]
    turso_pipeline([{"sql": ddl, "args": []}])

    # Read all rows from local
    cur = local.execute(f"SELECT * FROM [{name}]")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        return 0

    # Push in batches of 20
    ph  = ",".join(["?" for _ in cols])
    cn  = ",".join([f'[{c}]' for c in cols])
    sql = f"INSERT OR REPLACE INTO [{name}] ({cn}) VALUES ({ph})"
    BATCH = 20
    pushed = 0
    for i in range(0, len(rows), BATCH):
        stmts = [
            {"sql": sql, "args": [_to_arg(v) for v in row]}
            for row in rows[i:i+BATCH]
        ]
        turso_pipeline(stmts)
        pushed += len(stmts)
    return pushed


def main():
    if not os.path.exists(LOCAL_DB):
        print(f"ERROR: No encuentro {LOCAL_DB}")
        sys.exit(1)

    local = sqlite3.connect(LOCAL_DB)
    tables = get_tables(local)
    print(f"Conectado a Turso ({HOST})")
    print(f"Migrando {len(tables)} tablas desde {LOCAL_DB}...\n")

    total = 0
    for name, _ in tables:
        try:
            n = migrate_table(local, name)
            status = f"{n} filas" if n else "vacía (ok)"
            print(f"  ✓ {name:30s} {status}")
            total += n
        except Exception as e:
            print(f"  ✗ {name:30s} ERROR: {e}")

    local.close()
    print(f"\nMigración completa — {total} filas enviadas a Turso.")
    print("Ahora configura TURSO_DATABASE_URL y TURSO_AUTH_TOKEN en Railway y redespliega.")


if __name__ == "__main__":
    main()
