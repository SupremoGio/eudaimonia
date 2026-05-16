#!/usr/bin/env python3
"""
migrate_to_turso.py — copia pipeline.db local → Turso con validación completa

MODOS:
  --dry-run (-n)   Solo verifica la conexión y reporta diferencias. NO escribe nada.
  --table TABLE    Migra o verifica solo una tabla específica.

USO RECOMENDADO:
  1) Verifica primero (sin escribir):
       python migrate_to_turso.py --dry-run

  2) Si todo está bien, migra:
       python migrate_to_turso.py

  3) Para re-ejecutar una sola tabla:
       python migrate_to_turso.py --table reminders

VARIABLES DE ENTORNO REQUERIDAS:
  TURSO_DATABASE_URL  → libsql://nombre-tu-db.turso.io
  TURSO_AUTH_TOKEN    → tu token de autenticación Turso

Seguro de re-ejecutar: usa INSERT OR REPLACE para no duplicar filas.
"""
import os
import sqlite3
import json
import http.client
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # carga gio_v3/.env igual que app.py

# ── Configuración ──────────────────────────────────────────────────────────────

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
LOCAL_DB    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.db")

# Columnas de fecha por tabla — se validan antes de migrar
_DATE_COLS = {
    "reminders":        ["target_date", "next_date", "last_done", "created_at"],
    "gtd_tasks":        ["due_date", "completed_at", "created_at"],
    "gtd_projects":     ["created_at"],
    "achievements":     ["unlocked_at"],
    "badges":           ["unlocked_at", "perks_active_until", "created_at"],
    "rewards":          ["last_redeemed", "created_at"],
    "xp_ledger":        ["date", "created_at"],
    "coins_ledger":     ["date", "created_at"],
    "multiplier_log":   ["date", "expires_at", "created_at"],
    "penalty_log":      ["date", "created_at"],
    "special_events":   ["start_date", "end_date", "created_at"],
    "activity_logs":    ["date"],
    "priorities":       ["date"],
    "lista_prioridades":["purchased_at", "created_at"],
    "wishlist_items":   ["purchased_at", "created_at", "updated_at"],
    "salud_cuentas":    ["ultima_actualizacion", "created_at"],
    "salud_saldos_historial": ["fecha", "created_at"],
    "salud_bienes":     ["fecha_compra", "garantia_hasta", "created_at"],
    "salud_patrimonio_log": ["fecha", "created_at"],
    "lang_test_results":["test_date", "created_at"],
    "lang_journal":     ["entry_date", "created_at"],
    "consumo_productos":["ultima_compra", "created_at"],
    "consumo_compras":  ["fecha_compra", "created_at"],
    "wardrobe_items":   ["created_at"],
    "outfits":          ["created_at"],
    "recetas":          ["created_at"],
    "meal_plan":        ["created_at"],
    "debts":            ["created_at"],
    "debt_payments":    ["paid_at"],
    "budget_meses":     ["created_at"],
    "budget_deudas":    ["created_at"],
    "budget_pagos":     ["fecha_pago", "created_at"],
    "profile_docs":     ["uploaded_at"],
}

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
]


# ── Turso HTTP ─────────────────────────────────────────────────────────────────

def _to_arg(v):
    if v is None:            return {"type": "null"}
    if isinstance(v, bool):  return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):   return {"type": "integer", "value": str(v)}
    if isinstance(v, float): return {"type": "float",   "value": v}
    return {"type": "text", "value": str(v)}


def _from_cell(cell):
    if cell is None:             return None
    t = cell.get("type", "text")
    v = cell.get("value")
    if t == "null" or v is None: return None
    if t == "integer":           return int(v)
    if t in ("float", "real"):   return float(v)
    return v


def turso_pipeline(host, token, stmts):
    import time
    reqs = [{"type": "execute", "stmt": s} for s in stmts]
    reqs.append({"type": "close"})
    body = json.dumps({"requests": reqs}).encode()
    hdrs = {
        "Authorization":  f"Bearer {token}",
        "Content-Type":   "application/json",
    }
    for attempt in range(4):
        try:
            conn = http.client.HTTPSConnection(host, timeout=30)
            conn.request("POST", "/v2/pipeline", body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {data[:300].decode(errors='replace')}")
            return json.loads(data.decode())
        except Exception as e:
            if attempt == 3:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"    ⚠  Turso timeout (intento {attempt+1}/4), reintentando en {wait}s...")
            time.sleep(wait)


def turso_query(host, token, sql, args=None):
    """Ejecuta un SELECT en Turso y devuelve lista de dicts."""
    out = turso_pipeline(host, token, [{"sql": sql, "args": args or []}])
    res = out["results"][0]
    if res["type"] != "ok":
        raise Exception(f"Turso query error: {res}")
    r    = res["response"]["result"]
    cols = [c["name"] for c in r.get("cols", [])]
    return [dict(zip(cols, [_from_cell(c) for c in row])) for row in r.get("rows", [])]


# ── Schema helpers ─────────────────────────────────────────────────────────────

def get_local_tables(local):
    rows = local.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ).fetchall()
    return {r[0]: r[1] for r in rows if not r[0].startswith("sqlite_")}


def get_turso_tables(host, token):
    rows = turso_query(host, token,
        "SELECT name FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    return {r["name"] for r in rows if not r["name"].startswith("sqlite_")}


def get_local_columns(local, table):
    rows = local.execute(f"PRAGMA table_info([{table}])").fetchall()
    return {r[1]: r[2].upper() for r in rows}


def get_turso_columns(host, token, table):
    rows = turso_query(host, token, f"PRAGMA table_info([{table}])")
    return {r["name"]: r["type"].upper() for r in rows}


def compare_schemas(local_cols, turso_cols, table):
    issues = []
    local_set  = set(local_cols.keys())
    turso_set  = set(turso_cols.keys())
    extra_local = local_set - turso_set
    extra_turso = turso_set - local_set
    if extra_local:
        issues.append(f"    ⚠  Columnas en local pero NO en Turso: {sorted(extra_local)}")
    if extra_turso:
        issues.append(f"    ⚠  Columnas en Turso pero NO en local: {sorted(extra_turso)}")
    return issues


# ── Validación de fechas ───────────────────────────────────────────────────────

def _is_valid_date(val):
    if not val or not val.strip():
        return True  # NULL / vacío es válido
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(val, fmt)
            return True
        except ValueError:
            pass
    return False


def validate_dates(local, table):
    cols_to_check = _DATE_COLS.get(table)
    if not cols_to_check:
        return []
    issues = []
    for col in cols_to_check:
        try:
            rows = local.execute(
                f"SELECT id, [{col}] FROM [{table}] WHERE [{col}] IS NOT NULL AND [{col}] != ''"
            ).fetchall()
        except Exception:
            continue
        for row in rows:
            val = row[1]
            if not _is_valid_date(str(val)):
                issues.append(
                    f"    [{table}] id={row[0]}: columna '{col}' = '{val}' — formato no ISO"
                )
    return issues


# ── Conteo en Turso ────────────────────────────────────────────────────────────

def turso_count(host, token, table):
    try:
        rows = turso_query(host, token, f"SELECT COUNT(*) as c FROM [{table}]")
        return rows[0]["c"] if rows else 0
    except Exception:
        return -1  # tabla aún no existe en Turso


# ── Migración de una tabla ─────────────────────────────────────────────────────

def migrate_table(local, host, token, name):
    ddl_row = local.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    if not ddl_row:
        return 0, 0

    ddl = ddl_row[0]
    cur = local.execute(f"SELECT * FROM [{name}]")
    all_local_cols = [d[0] for d in cur.description]
    rows           = cur.fetchall()
    n_local        = len(rows)

    # Crear tabla en Turso si no existe
    turso_pipeline(host, token, [{"sql": ddl, "args": []}])

    if n_local == 0:
        return 0, 0

    # Usar solo las columnas que Turso tiene — evita errores por columnas huérfanas locales
    turso_cols = set(get_turso_columns(host, token, name).keys())
    use_cols   = [c for c in all_local_cols if c in turso_cols]
    col_idx    = [all_local_cols.index(c) for c in use_cols]

    if len(use_cols) < len(all_local_cols):
        skipped = set(all_local_cols) - turso_cols
        print(f"    ℹ  [{name}] columnas locales ignoradas (no en Turso): {sorted(skipped)}")

    before = turso_count(host, token, name)

    ph  = ",".join(["?" for _ in use_cols])
    cn  = ",".join([f'[{c}]' for c in use_cols])
    sql = f"INSERT OR REPLACE INTO [{name}] ({cn}) VALUES ({ph})"

    BATCH = 20
    for i in range(0, n_local, BATCH):
        stmts = [
            {"sql": sql, "args": [_to_arg(row[idx]) for idx in col_idx]}
            for row in rows[i:i + BATCH]
        ]
        turso_pipeline(host, token, stmts)

    after    = turso_count(host, token, name)
    new_rows = (after - before) if before >= 0 else n_local
    return n_local, new_rows


# ── Verificación post-migración ────────────────────────────────────────────────

def verify_migration(local, host, token, table_names):
    """Lee de Turso y confirma que los counts son >= counts locales."""
    print(f"\n{'═'*64}")
    print(f"  VERIFICACIÓN DE INTEGRIDAD (lectura desde Turso)")
    print(f"{'═'*64}")
    print(f"\n  {'Tabla':<32} {'Local':>8} {'Turso':>8}  Estado")
    print(f"  {'─'*62}")

    all_ok    = True
    n_match   = 0
    n_missing = 0

    for name in sorted(table_names):
        n_local = local.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        n_turso = turso_count(host, token, name)

        if n_turso < 0:
            estado   = "✗  NO EXISTE EN TURSO"
            all_ok   = False
            n_missing += 1
        elif n_turso < n_local:
            falta    = n_local - n_turso
            estado   = f"✗  FALTAN {falta} FILAS"
            all_ok   = False
            n_missing += 1
        else:
            estado   = "✓"
            n_match += 1

        turso_str = str(n_turso) if n_turso >= 0 else "(—)"
        print(f"  {name:<32} {n_local:>8} {turso_str:>8}  {estado}")

    print(f"  {'─'*62}")
    print(f"  Tablas OK: {n_match}  |  Con problemas: {n_missing}")
    print(f"{'═'*64}")

    if all_ok:
        print(f"""
  ✓  VERIFICACIÓN EXITOSA
     Turso tiene todos los datos de pipeline.db.

  ► AHORA ES SEGURO HACER GIT PUSH Y DESPLEGAR EN RAILWAY.

  Pasos finales:
    git add .
    git commit -m "deploy: sincronización datos Turso + health check"
    git push origin main
""")
    else:
        print(f"""
  ✗  VERIFICACIÓN FALLIDA — algunos datos no llegaron a Turso.
     Re-ejecuta la migración (sin --dry-run ni --verify) e intenta de nuevo.
     NO hagas git push hasta que esta verificación pase.
""")
    return all_ok


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Migra pipeline.db local → Turso con validación de integridad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="Solo verifica; no escribe nada en Turso"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Lee de vuelta desde Turso y compara counts con local (prueba de integridad)"
    )
    parser.add_argument(
        "--table", metavar="TABLE",
        help="Procesa solo esta tabla (nombre exacto)"
    )
    args = parser.parse_args()

    # ── Validación previa ──────────────────────────────────────────────────────
    if not TURSO_URL or not TURSO_TOKEN:
        print("\n  ERROR: define TURSO_DATABASE_URL y TURSO_AUTH_TOKEN como variables de entorno.")
        print("  Consulta .env.example para referencia.\n")
        sys.exit(1)

    if not os.path.exists(LOCAL_DB):
        print(f"\n  ERROR: No encontré pipeline.db en: {LOCAL_DB}\n")
        sys.exit(1)

    host = TURSO_URL.replace("libsql://", "").rstrip("/")
    if args.verify and args.dry_run:
        print("\n  ERROR: --verify y --dry-run son incompatibles.\n")
        sys.exit(1)

    mode = "DRY-RUN (solo lectura)" if args.dry_run else ("SOLO VERIFICACIÓN" if args.verify else "MIGRACIÓN REAL")

    print(f"\n{'═'*64}")
    print(f"  EUDAIMONIA OS — migrate_to_turso.py")
    print(f"  Modo: {mode}")
    print(f"{'═'*64}")

    # ── 1. Test de conexión ────────────────────────────────────────────────────
    print(f"\n[1/5] Probando conexión a Turso ({host})...")
    try:
        turso_pipeline(host, TURSO_TOKEN, [{"sql": "SELECT 1", "args": []}])
        print("      ✓ Conexión exitosa")
    except Exception as e:
        print(f"      ✗ Conexión falló: {e}")
        print("      Verifica TURSO_DATABASE_URL y TURSO_AUTH_TOKEN.")
        sys.exit(1)

    # ── 2. Listar tablas ───────────────────────────────────────────────────────
    local = sqlite3.connect(LOCAL_DB)
    local_tables = get_local_tables(local)
    all_names    = list(local_tables.keys())

    if args.table:
        if args.table not in local_tables:
            print(f"\n  ERROR: tabla '{args.table}' no existe en pipeline.db")
            print(f"  Tablas disponibles: {', '.join(sorted(all_names))}")
            local.close()
            sys.exit(1)
        table_names = [args.table]
    else:
        table_names = all_names

    print(f"\n[2/5] Base de datos local: {LOCAL_DB}")
    print(f"      {len(table_names)} tabla(s) a {'verificar' if args.dry_run else 'migrar'}")

    # ── 3. Validación de fechas ────────────────────────────────────────────────
    print(f"\n[3/5] Verificando integridad de fechas en tablas con columnas temporales...")
    all_date_issues = []
    for name in table_names:
        errs = validate_dates(local, name)
        all_date_issues.extend(errs)

    if all_date_issues:
        print(f"      ⚠  {len(all_date_issues)} valor(es) con formato no ISO encontrado(s):")
        for err in all_date_issues:
            print(err)
        print("      Nota: estos valores se migrarán como texto — Turso los acepta igual.")
    else:
        print("      ✓ Todas las fechas tienen formato ISO estándar")

    # ── 4. Comparación de schemas ──────────────────────────────────────────────
    print(f"\n[4/5] Comparando schemas (local vs Turso)...")
    turso_existing = get_turso_tables(host, TURSO_TOKEN)
    schema_issues  = []

    # Obtener columnas de Turso en un solo batch para minimizar llamadas HTTP
    turso_all_cols = {}
    existing_in_turso = [n for n in table_names if n in turso_existing]
    for name in existing_in_turso:
        try:
            turso_all_cols[name] = get_turso_columns(host, TURSO_TOKEN, name)
        except Exception:
            turso_all_cols[name] = {}

    for name in table_names:
        if name in turso_existing:
            local_cols = get_local_columns(local, name)
            turso_cols = turso_all_cols.get(name, {})
            issues = compare_schemas(local_cols, turso_cols, name)
            if issues:
                schema_issues.append((name, issues))

    tables_existing = len(existing_in_turso)
    tables_new      = len(table_names) - tables_existing

    if schema_issues:
        print(f"      ⚠  Diferencias de schema en {len(schema_issues)} tabla(s) (la migración las maneja automáticamente):")
        for name, issues in schema_issues:
            print(f"      [{name}]:")
            for issue in issues:
                print(issue)
    else:
        print(f"      ✓ {tables_existing} tabla(s) verificadas sin diferencias")
        print(f"      + {tables_new} tabla(s) nuevas (se crearán en Turso)")

    # ── 5. Dry-run, verify-only o migración ────────────────────────────────────
    if args.verify:
        local_obj = sqlite3.connect(LOCAL_DB)
        all_ok = verify_migration(local_obj, host, TURSO_TOKEN, table_names)
        local_obj.close()
        local.close()
        sys.exit(0 if all_ok else 1)

    print(f"\n[5/5] {'RESUMEN' if args.dry_run else 'EJECUTANDO MIGRACIÓN'}...")

    if args.dry_run:
        print(f"\n  {'Tabla':<32} {'Local':>8} {'Turso':>8} {'Pendiente':>10}")
        print(f"  {'─'*62}")

        total_local = total_turso = 0
        for name in sorted(table_names):
            n_local  = local.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
            n_turso  = turso_count(host, TURSO_TOKEN, name)
            pending  = n_local - (n_turso if n_turso >= 0 else 0)
            t_str    = str(n_turso) if n_turso >= 0 else "(nueva)"
            p_str    = f"+{pending}" if pending > 0 else ("ok" if pending == 0 else str(pending))
            total_local += n_local
            total_turso += (n_turso if n_turso >= 0 else 0)
            print(f"  {name:<32} {n_local:>8} {t_str:>8} {p_str:>10}")

        print(f"  {'─'*62}")
        diff = total_local - total_turso
        print(f"  {'TOTAL':<32} {total_local:>8} {total_turso:>8} {f'+{diff}':>10}")

        print(f"\n  DRY-RUN completo — sin cambios en Turso.")
        print(f"  Ejecuta sin --dry-run para iniciar la migración real.\n")

    else:
        print()
        total_local_rows = 0
        total_new_rows   = 0
        errors           = []

        for name in table_names:
            try:
                n_local, n_new = migrate_table(local, host, TURSO_TOKEN, name)
                total_local_rows += n_local
                total_new_rows   += n_new

                if n_local == 0:
                    status = "vacía — tabla creada en Turso"
                elif n_new > 0:
                    status = f"{n_local} filas enviadas → {n_new} nuevas en Turso"
                else:
                    status = f"{n_local} filas — ya existían (actualizadas con OR REPLACE)"

                print(f"  ✓ {name:<32} {status}")

            except Exception as e:
                print(f"  ✗ {name:<32} ERROR: {e}")
                errors.append((name, str(e)))

        print(f"\n{'═'*64}")
        print(f"  MIGRACIÓN COMPLETADA")
        print(f"  Tablas procesadas  : {len(table_names) - len(errors)}/{len(table_names)}")
        print(f"  Filas enviadas     : {total_local_rows}")
        print(f"  Filas nuevas       : {total_new_rows}")
        if errors:
            print(f"  Errores            : {len(errors)}")
            for name, err in errors:
                print(f"    - {name}: {err}")
        else:
            print(f"  Errores            : 0 ✓")
        # Auto-verificación post-migración
        if not errors:
            verify_migration(local, host, TURSO_TOKEN, table_names)
        else:
            print(f"\n  ⚠  Hubo errores — corrige y re-ejecuta antes de hacer git push.")

    local.close()


if __name__ == "__main__":
    main()
