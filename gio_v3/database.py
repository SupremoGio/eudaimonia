import os, json as _json, http.client, threading
from datetime import date, timedelta

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

import sqlite3 as _sqlite3

# Priority: DATABASE_PATH env var (Railway Volume) > sibling pipeline.db
_LOCAL     = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline.db')
)
_LOCAL_TMP = "/tmp/eudaimonia.db"   # fast local cache when Turso is active

# ── Turso HTTP (writes only) ──────────────────────────────────────────────────

_tls = threading.local()   # thread-local storage for HTTP connections

def _to_arg(v):
    if v is None:            return {"type": "null"}
    if isinstance(v, bool):  return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):   return {"type": "integer", "value": str(v)}
    if isinstance(v, float): return {"type": "float",   "value": v}
    return {"type": "text", "value": str(v)}

def _from_cell(cell):
    if cell is None:              return None
    t = cell.get("type", "text")
    v = cell.get("value")
    if t == "null" or v is None:  return None
    if t == "integer":            return int(v)
    if t in ("float", "real"):    return float(v)
    return v

def _turso_pipeline(host, token, stmts):
    reqs = [{"type": "execute", "stmt": s} for s in stmts]
    reqs.append({"type": "close"})
    body = _json.dumps({"requests": reqs}).encode()
    hdrs = {"Authorization": f"Bearer {token}",
            "Content-Type": "application/json", "Connection": "keep-alive"}
    for attempt in range(3):
        try:
            # Use a thread-local connection — avoids race conditions between workers
            conn = getattr(_tls, 'conn', None)
            if conn is None:
                conn = http.client.HTTPSConnection(host, timeout=15)
                _tls.conn = conn
            conn.request("POST", "/v2/pipeline", body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {data[:100]}")
            return _json.loads(data.decode())
        except Exception as e:
            _tls.conn = None   # reset only this thread's connection
            if attempt == 2:
                raise

def _turso_sync(host, token, writes):
    """Background: replay write statements to Turso for persistence."""
    try:
        BATCH = 20
        for i in range(0, len(writes), BATCH):
            _turso_pipeline(host, token, writes[i:i+BATCH])
    except Exception as e:
        print(f"[DB] Turso sync warning: {e}")

def _restore_from_turso(host, token):
    """On startup: copy all Turso data into local SQLite."""
    try:
        out = _turso_pipeline(host, token, [
            {"sql": "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL", "args": []}
        ])
        res = out["results"][0]
        if res["type"] != "ok":
            return False
        r   = res["response"]["result"]
        tbl_cols = [c["name"] for c in r.get("cols", [])]
        tables   = [dict(zip(tbl_cols, [_from_cell(c) for c in row]))
                    for row in r.get("rows", [])]

        local = _sqlite3.connect(_LOCAL_TMP)
        local.execute("PRAGMA journal_mode=WAL")
        for t in tables:
            name, ddl = t.get("name",""), t.get("sql","")
            if not name or not ddl or name.startswith("sqlite_"):
                continue
            try:
                local.execute(ddl)
            except Exception:
                pass
            # Copy rows
            try:
                dout = _turso_pipeline(host, token,
                    [{"sql": f"SELECT * FROM [{name}]", "args": []}])
                dr = dout["results"][0]
                if dr["type"] != "ok":
                    continue
                dres  = dr["response"]["result"]
                dcols = [c["name"] for c in dres.get("cols", [])]
                ph    = ",".join(["?" for _ in dcols])
                cn    = ",".join([f'[{c}]' for c in dcols])
                for raw in dres.get("rows", []):
                    vals = [_from_cell(cell) for cell in raw]
                    try:
                        local.execute(f"INSERT OR REPLACE INTO [{name}] ({cn}) VALUES ({ph})", vals)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[DB] restore {name}: {e}")
        local.commit()
        local.close()
        print(f"[DB] Restored {len(tables)} tables from Turso ✓")
        return True
    except Exception as e:
        print(f"[DB] Restore failed: {e}")
        return False

# ── Hybrid connection: local SQLite reads + async Turso writes ────────────────

class _HybridConn:
    def __init__(self, db_path, turso_host, turso_token):
        self._db    = _sqlite3.connect(db_path)
        self._db.row_factory = _sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._host  = turso_host
        self._token = turso_token
        self._writes = []

    def _track(self, sql, args=()):
        u = sql.strip().upper()
        if not u.startswith(("SELECT", "PRAGMA")):
            self._writes.append({"sql": sql, "args": [_to_arg(p) for p in args]})

    def execute(self, sql, params=()):
        self._track(sql, params)
        return self._db.execute(sql, params)

    def executemany(self, sql, param_list):
        rows = list(param_list)
        self._db.executemany(sql, rows)
        for p in rows:
            self._track(sql, p)

    def executescript(self, sql):
        self._db.executescript(sql)
        for s in sql.split(';'):
            lines = [l for l in s.split('\n') if not l.strip().startswith('--')]
            s = '\n'.join(lines).strip()
            if s:
                self._track(s)

    def commit(self):
        self._db.commit()
        if self._writes:
            writes, self._writes = self._writes[:], []
            threading.Thread(
                target=_turso_sync, args=(self._host, self._token, writes),
                daemon=True
            ).start()

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.commit()
        self.close()

# ── Backend selection ─────────────────────────────────────────────────────────

_USE_HYBRID = False
_TURSO_HOST = ""
_TURSO_TOKEN_VAL = ""
_DB_PATH = _LOCAL


if TURSO_URL and TURSO_TOKEN:
    try:
        _host = TURSO_URL.replace("libsql://", "")
        _turso_pipeline(_host, TURSO_TOKEN, [{"sql": "SELECT 1", "args": []}])
        print("[DB] Turso conectado ✓ — restaurando datos locales...")
        _restore_from_turso(_host, TURSO_TOKEN)
        _USE_HYBRID   = True
        _TURSO_HOST   = _host
        _TURSO_TOKEN_VAL = TURSO_TOKEN
        _DB_PATH      = _LOCAL_TMP
        print("[DB] Modo híbrido: SQLite local (rápido) + Turso (persistencia) ✓")
    except Exception as e:
        print(f"[DB] Turso falló ({e}), usando SQLite local")

def get_db():
    if _USE_HYBRID:
        return _HybridConn(_DB_PATH, _TURSO_HOST, _TURSO_TOKEN_VAL)
    c = _sqlite3.connect(_DB_PATH)
    c.row_factory = _sqlite3.Row
    return c


def init_db():
  try:
    with get_db() as db:
        db.executescript("""
        -- ── DASHBOARD ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS pipeline_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS priorities (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            date    TEXT    NOT NULL,
            text    TEXT    NOT NULL,
            done    INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS activity_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_key TEXT    NOT NULL,
            date         TEXT    NOT NULL,
            pts          INTEGER NOT NULL
        );

        -- ── GTD ──────────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS gtd_projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            objective   TEXT    DEFAULT '',
            color       TEXT    DEFAULT '#c5a36c',
            status      TEXT    DEFAULT 'active',
            created_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gtd_tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            description  TEXT    DEFAULT '',
            status       TEXT    DEFAULT 'inbox',
            priority     TEXT    DEFAULT 'normal',
            due_date     TEXT    DEFAULT '',
            category     TEXT    DEFAULT '',
            points       INTEGER DEFAULT 10,
            project_id   INTEGER DEFAULT NULL,
            completed_at TEXT    DEFAULT NULL,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gtd_points_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id       INTEGER DEFAULT NULL,
            points_earned INTEGER NOT NULL,
            reason        TEXT    DEFAULT '',
            date          TEXT    NOT NULL
        );

        -- ── FINANZAS ─────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS debts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT    NOT NULL,
            person     TEXT    NOT NULL,
            concept    TEXT    NOT NULL,
            amount     REAL    NOT NULL,
            settled    INTEGER DEFAULT 0,
            created_at TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_categories (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            budgeted REAL    DEFAULT 0,
            spent    REAL    DEFAULT 0,
            color    TEXT    DEFAULT '#c5a36c'
        );

        -- ── PERFIL ───────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS personal_info (
            key     TEXT PRIMARY KEY,
            label   TEXT NOT NULL,
            value   TEXT NOT NULL,
            private INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS body_measurements (
            key     TEXT PRIMARY KEY,
            label   TEXT NOT NULL,
            value   TEXT NOT NULL,
            unit    TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS profile_docs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT NOT NULL,
            original    TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        );

        -- ── SÁBADO ───────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS saturday_checks (
            week_start TEXT NOT NULL,
            task_key   TEXT NOT NULL,
            done       INTEGER DEFAULT 0,
            PRIMARY KEY (week_start, task_key)
        );

        -- ── DEBT PAYMENTS (abonos) ──────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS debt_payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id    INTEGER NOT NULL,
            amount     REAL    NOT NULL,
            note       TEXT    DEFAULT '',
            paid_at    TEXT    NOT NULL,
            FOREIGN KEY(debt_id) REFERENCES debts(id)
        );

        -- ── IDIOMAS ─────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS lang_test_results (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            test_type  TEXT    NOT NULL,
            score      TEXT    NOT NULL,
            notes      TEXT    DEFAULT '',
            test_date  TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lang_journal (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            language   TEXT    NOT NULL,
            entry_text TEXT    NOT NULL,
            feedback   TEXT    DEFAULT '',
            entry_date TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        );

        -- ── GUARDARROPA ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS wardrobe_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT    NOT NULL,
            categoria    TEXT    NOT NULL DEFAULT 'Camisa',
            subcategoria TEXT    DEFAULT '',
            color_hex    TEXT    DEFAULT '#C9A84C',
            color_name   TEXT    DEFAULT '',
            marca        TEXT    DEFAULT '',
            ocasion      TEXT    DEFAULT '',
            temporada    TEXT    DEFAULT 'todo',
            estado       TEXT    DEFAULT 'bueno',
            precio       REAL    DEFAULT 0,
            veces_usado  INTEGER DEFAULT 0,
            foto         TEXT    DEFAULT '',
            notas        TEXT    DEFAULT '',
            activo       INTEGER DEFAULT 1,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outfits (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre     TEXT    NOT NULL,
            ocasion    TEXT    DEFAULT '',
            rating     INTEGER DEFAULT 0,
            foto       TEXT    DEFAULT '',
            notas      TEXT    DEFAULT '',
            created_at TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outfit_items (
            outfit_id  INTEGER NOT NULL,
            item_id    INTEGER NOT NULL,
            PRIMARY KEY (outfit_id, item_id),
            FOREIGN KEY (outfit_id) REFERENCES outfits(id),
            FOREIGN KEY (item_id) REFERENCES wardrobe_items(id)
        );

        -- ── WISHLIST / PROTOCOLO DE COMPRA ───────────────────────────────────
        CREATE TABLE IF NOT EXISTS wishlist_items (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre                  TEXT    NOT NULL,
            categoria               TEXT    DEFAULT '',
            precio_estimado         REAL    DEFAULT 0,
            descripcion             TEXT    DEFAULT '',
            url                     TEXT    DEFAULT '',
            marca                   TEXT    DEFAULT '',
            -- Phase 1: Dopamine firewall
            dias_deseo              INTEGER DEFAULT NULL,
            q1_persiste             INTEGER DEFAULT NULL,
            -- Phase 2: Solvency
            q2_estado_financiero    TEXT    DEFAULT NULL,
            q2_clasificacion        TEXT    DEFAULT NULL,
            -- Phase 3: Logic algorithm
            q3_es_util              INTEGER DEFAULT NULL,
            q3_tiene_alternativa    INTEGER DEFAULT NULL,
            q3_usos_mes             REAL    DEFAULT NULL,
            q3_cpu_ok               INTEGER DEFAULT NULL,
            q3_mantenimiento_ok     INTEGER DEFAULT NULL,
            q3_costo_oportunidad_ok INTEGER DEFAULT NULL,
            -- Result
            score                   INTEGER DEFAULT NULL,
            recomendacion           TEXT    DEFAULT NULL,
            razon_recomendacion     TEXT    DEFAULT '',
            -- Decision
            estado                  TEXT    DEFAULT 'evaluando',
            decision_override       INTEGER DEFAULT 0,
            notas_decision          TEXT    DEFAULT '',
            purchased_at            TEXT    DEFAULT NULL,
            created_at              TEXT    NOT NULL,
            updated_at              TEXT    DEFAULT NULL
        );

        -- ── RECETAS ──────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS recetas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT    NOT NULL,
            categoria      TEXT    DEFAULT 'Almuerzo',
            descripcion    TEXT    DEFAULT '',
            ingredientes   TEXT    DEFAULT '[]',
            instrucciones  TEXT    DEFAULT '[]',
            calorias       INTEGER DEFAULT 0,
            proteina       REAL    DEFAULT 0,
            carbos         REAL    DEFAULT 0,
            grasa          REAL    DEFAULT 0,
            tiempo_prep    INTEGER DEFAULT 0,
            tiempo_coccion INTEGER DEFAULT 0,
            porciones      INTEGER DEFAULT 1,
            video_url      TEXT    DEFAULT '',
            tags           TEXT    DEFAULT '',
            favorita       INTEGER DEFAULT 0,
            created_at     TEXT    NOT NULL
        );

        -- ── NUTRICION ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS meal_plan (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start  TEXT    NOT NULL,
            day_name    TEXT    NOT NULL,
            meal_type   TEXT    NOT NULL,
            description TEXT    NOT NULL,
            video_url   TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL
        );

        -- ── GAMIFICATION ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS xp_ledger (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            amount       INTEGER NOT NULL,
            source       TEXT    NOT NULL,
            reference_id INTEGER DEFAULT NULL,
            description  TEXT    DEFAULT '',
            multiplier   REAL    DEFAULT 1.0,
            date         TEXT    NOT NULL,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS coins_ledger (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            amount       INTEGER NOT NULL,
            source       TEXT    NOT NULL,
            reference_id INTEGER DEFAULT NULL,
            description  TEXT    DEFAULT '',
            multiplier   REAL    DEFAULT 1.0,
            date         TEXT    NOT NULL,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS achievements (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key          TEXT    NOT NULL UNIQUE,
            unlocked_at  TEXT    DEFAULT NULL,
            coins_earned INTEGER DEFAULT 0,
            xp_earned    INTEGER DEFAULT 0,
            notified     INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS multiplier_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            type         TEXT    NOT NULL,
            multiplier   REAL    NOT NULL,
            triggered_by TEXT    NOT NULL,
            applies_to   TEXT    NOT NULL,
            date         TEXT    NOT NULL,
            expires_at   TEXT    DEFAULT NULL,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS penalty_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            type         TEXT    NOT NULL,
            coins_lost   INTEGER NOT NULL,
            description  TEXT    NOT NULL,
            date         TEXT    NOT NULL,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS special_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            key             TEXT    NOT NULL UNIQUE,
            name            TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            event_type      TEXT    NOT NULL,
            xp_multiplier   REAL    DEFAULT 1.0,
            coin_multiplier REAL    DEFAULT 1.0,
            focus_category  TEXT    DEFAULT '',
            focus_bonus     REAL    DEFAULT 1.0,
            is_active       INTEGER DEFAULT 0,
            start_date      TEXT    DEFAULT NULL,
            end_date        TEXT    DEFAULT NULL,
            created_at      TEXT    NOT NULL
        );

        -- ── RECORDATORIOS ────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT    NOT NULL,
            type        TEXT    NOT NULL DEFAULT 'unico',
            freq_unit   TEXT    DEFAULT '',
            freq_value  INTEGER DEFAULT 1,
            target_date TEXT    DEFAULT NULL,
            next_date   TEXT    DEFAULT NULL,
            last_done   TEXT    DEFAULT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT    NOT NULL
        );
        """)

        # ── Migrate gtd_tasks ────────────────────────────────────────────────
        try:
            gtd_cols = [r["name"] for r in db.execute("PRAGMA table_info(gtd_tasks)").fetchall()]
            if 'context' not in gtd_cols:
                db.execute("ALTER TABLE gtd_tasks ADD COLUMN context TEXT DEFAULT ''")
            if 'estimated_mins' not in gtd_cols:
                db.execute("ALTER TABLE gtd_tasks ADD COLUMN estimated_mins INTEGER DEFAULT 0")
            if 'energy_level' not in gtd_cols:
                db.execute("ALTER TABLE gtd_tasks ADD COLUMN energy_level TEXT DEFAULT 'medium'")
            db.commit()
        except Exception as e:
            print(f"[DB] gtd migration warning: {e}")

        # ── Migrate debts ────────────────────────────────────────────────────
        try:
            cols = [r["name"] for r in db.execute("PRAGMA table_info(debts)").fetchall()]
            if 'monto_total' not in cols:
                db.execute("ALTER TABLE debts ADD COLUMN monto_total REAL DEFAULT 0")
                db.execute("ALTER TABLE debts ADD COLUMN monto_restante REAL DEFAULT 0")
                db.execute("UPDATE debts SET monto_total=amount, monto_restante=amount WHERE monto_total=0")
                db.commit()
        except Exception as e:
            print(f"[DB] debts migration warning: {e}")

        # Seed body_measurements
        if db.execute("SELECT COUNT(*) as c FROM body_measurements").fetchone()["c"] == 0:
            db.executemany(
                "INSERT INTO body_measurements (key, label, value, unit) VALUES (?,?,?,?)",
                [
                    ("peso",       "Peso",          "— editar —", "kg"),
                    ("estatura",   "Estatura",       "— editar —", "cm"),
                    ("pecho",      "Pecho",          "— editar —", "cm"),
                    ("cintura",    "Cintura",        "— editar —", "cm"),
                    ("cadera",     "Cadera",         "— editar —", "cm"),
                    ("hombros",    "Hombros",        "— editar —", "cm"),
                    ("manga",      "Manga",          "— editar —", "cm"),
                    ("cuello",     "Cuello",         "— editar —", "cm"),
                    ("entrepier",  "Entrepierna",    "— editar —", "cm"),
                    ("pie",        "Pie (talla)",    "— editar —", "MX"),
                    ("t_camisa",   "Talla camisa",   "— editar —", ""),
                    ("t_pantalon", "Talla pantalón", "— editar —", ""),
                ]
            )

        # Seed personal_info
        if db.execute("SELECT COUNT(*) as c FROM personal_info").fetchone()["c"] == 0:
            db.executemany(
                "INSERT INTO personal_info (key, label, value, private) VALUES (?,?,?,?)",
                [
                    ("nombre",         "Nombre Completo",    "— editar —", 0),
                    ("rfc",            "RFC",                 "— editar —", 1),
                    ("curp",           "CURP",                "— editar —", 1),
                    ("nss",            "NSS (IMSS)",          "— editar —", 1),
                    ("telefono",       "Teléfono",            "— editar —", 0),
                    ("email",          "Email",               "— editar —", 0),
                    ("clabe",          "CLABE bancaria",      "— editar —", 1),
                    ("direccion",      "Dirección",           "— editar —", 0),
                    ("fecha_nac",      "Fecha de Nacimiento", "— editar —", 0),
                    ("poliza_seguro",  "Póliza de Seguro",    "— editar —", 1),
                ]
            )

        # Add poliza_seguro if missing (existing DBs)
        try:
            keys = [r["key"] for r in db.execute("SELECT key FROM personal_info").fetchall()]
            if "poliza_seguro" not in keys:
                db.execute(
                    "INSERT INTO personal_info (key, label, value, private) VALUES (?,?,?,?)",
                    ("poliza_seguro", "Póliza de Seguro", "— editar —", 1)
                )
                db.commit()
        except Exception as e:
            print(f"[DB] poliza_seguro seed warning: {e}")

        # Seed budget categories
        if db.execute("SELECT COUNT(*) as c FROM budget_categories").fetchone()["c"] == 0:
            db.executemany(
                "INSERT INTO budget_categories (name, budgeted, spent, color) VALUES (?,?,?,?)",
                [
                    ("Renta",            0, 0, "#c5a36c"),
                    ("Comida / Super",   0, 0, "#a78bfa"),
                    ("Transporte",       0, 0, "#60a5fa"),
                    ("Suscripciones",    0, 0, "#f472b6"),
                    ("Gym / Salud",      0, 0, "#4ade80"),
                    ("Ahorro",           0, 0, "#34d399"),
                    ("Ropa / Personal",  0, 0, "#fb923c"),
                    ("Entretenimiento",  0, 0, "#f87171"),
                    ("Otros",            0, 0, "#94a3b8"),
                ]
            )
        # ── BUDGET 50-30-20 ──────────────────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS budget_meses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            mes           TEXT    NOT NULL UNIQUE,
            ingreso_total REAL    DEFAULT 0,
            created_at    TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_items (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id      INTEGER NOT NULL,
            nombre         TEXT    NOT NULL,
            categoria      TEXT    NOT NULL,
            tipo           TEXT    DEFAULT 'fijo',
            monto_estimado REAL    DEFAULT 0,
            monto_real     REAL    DEFAULT NULL,
            deuda_id       INTEGER DEFAULT NULL,
            FOREIGN KEY(budget_id) REFERENCES budget_meses(id)
        );
        CREATE TABLE IF NOT EXISTS budget_deudas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL,
            saldo_inicial REAL    NOT NULL,
            saldo_actual  REAL    NOT NULL,
            pago_minimo   REAL    DEFAULT 0,
            tasa_interes  REAL    DEFAULT 0,
            activa        INTEGER DEFAULT 1,
            created_at    TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_pagos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            deuda_id     INTEGER NOT NULL,
            mes          TEXT    NOT NULL,
            monto_pagado REAL    NOT NULL,
            fecha_pago   TEXT    NOT NULL,
            nota         TEXT    DEFAULT '',
            created_at   TEXT    NOT NULL,
            FOREIGN KEY(deuda_id) REFERENCES budget_deudas(id)
        );
        """)

        # ── LISTA DE PRIORIDADES ─────────────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS lista_prioridades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            categoria       TEXT DEFAULT '',
            prioridad       TEXT DEFAULT 'Media',
            precio_estimado REAL DEFAULT 0,
            precio_real     REAL DEFAULT NULL,
            estado          TEXT DEFAULT 'Pendiente',
            mes_objetivo    TEXT DEFAULT '',
            tienda          TEXT DEFAULT '',
            url             TEXT DEFAULT '',
            notas           TEXT DEFAULT '',
            purchased_at    TEXT DEFAULT NULL,
            created_at      TEXT NOT NULL
        );
        """)

        # Seed lista_prioridades desde Notion
        if db.execute("SELECT COUNT(*) as c FROM lista_prioridades").fetchone()["c"] == 0:
            import datetime as _dtp
            _now = _dtp.datetime.now().isoformat()
            db.executemany(
                """INSERT INTO lista_prioridades
                   (nombre, categoria, prioridad, precio_estimado, precio_real, estado, mes_objetivo, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [
                    ("Pila portátil",        "Tecnología",      "Alta",  0,    None, "Pendiente", "", _now),
                    ("Sartenes",             "Hogar",           "Alta",  0,    None, "Pendiente", "", _now),
                    ("Ram 16 Gb",            "Tecnología",      "Alta",  0,    None, "Comprado",  "", _now),
                    ("Under Armour HeatGear","Ropa · Accesorios","Media",0,    None, "Pendiente", "", _now),
                    ("Wallet tarjetero",     "Ropa · Accesorios","Media",0,    None, "Pendiente", "", _now),
                    ("Toallas beige",        "Hogar",           "Media", 0,    None, "Pendiente", "", _now),
                    ("Apple Watch",          "Tecnología",      "Baja",  6000, None, "Pendiente", "", _now),
                    ("Robot Limpieza",       "Hogar",           "Baja",  6000, 6000,"Comprado",  "", _now),
                    ("Cuadro",               "Hogar",           "Baja",  0,    None, "Pendiente", "", _now),
                    ("Espejo grande pie",    "Hogar",           "Baja",  0,    None, "Pendiente", "", _now),
                    ("Kit cambio llantas",   "Auto",            "Baja",  0,    None, "Pendiente", "", _now),
                    ("Bocina pequeña",       "Tecnología",      "Baja",  0,    None, "Pendiente", "", _now),
                    ("Nespresso travel mug", "Hogar",           "Baja",  0,    None, "Comprado",  "", _now),
                    ("Mouse MX Master",      "Tecnología",      "Baja",  0,    None, "Comprado",  "", _now),
                    ("Espejo baño",          "Hogar",           "Baja",  0,    None, "Comprado",  "", _now),
                    ("Bata baño",            "Hogar",           "Baja",  0,    None, "Pendiente", "", _now),
                ]
            )

        # ── CONSUMO INTELIGENTE ───────────────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS consumo_productos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            categoria       TEXT    NOT NULL DEFAULT '',
            precio_promedio REAL    DEFAULT 0,
            ultima_compra   TEXT    DEFAULT NULL,
            frecuencia_dias REAL    DEFAULT NULL,
            activo          INTEGER DEFAULT 1,
            created_at      TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS consumo_compras (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id  INTEGER NOT NULL,
            fecha_compra TEXT    NOT NULL,
            cantidad     REAL    DEFAULT 1,
            precio_total REAL    NOT NULL,
            created_at   TEXT    NOT NULL,
            FOREIGN KEY(producto_id) REFERENCES consumo_productos(id)
        );

        -- ── SALUD FINANCIERA ─────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS salud_cuentas (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre               TEXT    NOT NULL,
            tipo                 TEXT    NOT NULL,
            institucion          TEXT    DEFAULT '',
            saldo                REAL    DEFAULT 0,
            moneda               TEXT    DEFAULT 'MXN',
            color                TEXT    DEFAULT '#C9A84C',
            activa               INTEGER DEFAULT 1,
            ultima_actualizacion TEXT    DEFAULT NULL,
            notas                TEXT    DEFAULT '',
            created_at           TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS salud_saldos_historial (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cuenta_id   INTEGER NOT NULL,
            saldo       REAL    NOT NULL,
            fecha       TEXT    NOT NULL,
            nota        TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL,
            FOREIGN KEY(cuenta_id) REFERENCES salud_cuentas(id)
        );
        CREATE TABLE IF NOT EXISTS salud_bienes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT    NOT NULL,
            categoria      TEXT    NOT NULL,
            descripcion    TEXT    DEFAULT '',
            precio_compra  REAL    DEFAULT 0,
            valor_actual   REAL    DEFAULT 0,
            fecha_compra   TEXT    DEFAULT '',
            lugar_compra   TEXT    DEFAULT '',
            garantia_hasta TEXT    DEFAULT '',
            notas          TEXT    DEFAULT '',
            activo         INTEGER DEFAULT 1,
            created_at     TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS salud_patrimonio_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            total_activos   REAL    NOT NULL,
            total_pasivos   REAL    NOT NULL,
            patrimonio_neto REAL    NOT NULL,
            fecha           TEXT    NOT NULL,
            created_at      TEXT    NOT NULL
        );
        """)

        # Seed productos iniciales
        if db.execute("SELECT COUNT(*) as c FROM consumo_productos").fetchone()["c"] == 0:
            import datetime as _dt2
            _now = _dt2.datetime.now().isoformat()
            db.executemany(
                "INSERT INTO consumo_productos (nombre, categoria, created_at) VALUES (?,?,?)",
                [
                    ("Papel de baño",             "Desechables",      _now),
                    ("Toallitas húmedas",          "Desechables",      _now),
                    ("Toallitas desinfectantes",   "Desechables",      _now),
                    ("Bolsas basura",              "Desechables",      _now),
                    ("Jabón cuerpo Dove",          "Higiene corporal", _now),
                    ("Jabón manos",                "Higiene corporal", _now),
                    ("Pastilla WC",                "Limpieza hogar",   _now),
                    ("Líquido limpiar WC",         "Limpieza hogar",   _now),
                    ("Limpia cristales",           "Limpieza hogar",   _now),
                    ("Jabón ropa",                 "Lavandería",       _now),
                    ("Suavizante ropa",            "Lavandería",       _now),
                    ("Creatina",                   "Suplementación",   _now),
                    ("Jabón cara",                 "Higiene personal", _now),
                    ("Protector solar",            "Higiene personal", _now),
                    ("Desodorante",                "Higiene personal", _now),
                    ("Gel cabello",                "Higiene personal", _now),
                ]
            )

        # ── GAMIFICATION v3.0 — Badges & Rewards ─────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS badges (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            key               TEXT    NOT NULL UNIQUE,
            tier              TEXT    NOT NULL,
            unlocked_at       TEXT    DEFAULT NULL,
            perks_active_until TEXT   DEFAULT NULL,
            notified          INTEGER DEFAULT 0,
            created_at        TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rewards (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            description      TEXT    DEFAULT '',
            ec_cost          INTEGER NOT NULL DEFAULT 0,
            level_required   INTEGER DEFAULT 1,
            badge_required   TEXT    DEFAULT '',
            cooldown_days    INTEGER DEFAULT 0,
            last_redeemed    TEXT    DEFAULT NULL,
            status           TEXT    DEFAULT 'available',
            created_at       TEXT    NOT NULL
        );
        """)

        # Seed default rewards if empty
        if db.execute("SELECT COUNT(*) as c FROM rewards").fetchone()["c"] == 0:
            import datetime as _dtr
            _now = _dtr.datetime.now().isoformat()
            db.executemany(
                """INSERT INTO rewards (name, description, ec_cost, level_required, badge_required, cooldown_days, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                [
                    ("Ropa Nike",          "Comprar ropa Nike nueva",          50,  3,  "",               30,  _now),
                    ("Libro técnico",      "Comprar libro de programación",    30,  2,  "script_junior",  7,   _now),
                    ("Kindle",             "Comprar Kindle",                   120, 4,  "fullstack_arete", 90, _now),
                    ("Salida / Experiencia","Experiencia o salida especial",   80,  5,  "",               30,  _now),
                    ("Apple Watch",        "Comprar Apple Watch",              300, 7,  "stoic_commander", 180,_now),
                    ("Viaje",              "Viaje o vacaciones merecidas",     500, 10, "diplomatico",    365, _now),
                ]
            )
            db.commit()

        # Migrate lista_prioridades: add protocol columns if missing
        try:
            lp_cols = [r["name"] for r in db.execute("PRAGMA table_info(lista_prioridades)").fetchall()]
            if "protocolo_score" not in lp_cols:
                db.execute("ALTER TABLE lista_prioridades ADD COLUMN protocolo_score INTEGER DEFAULT NULL")
            if "protocolo_rec" not in lp_cols:
                db.execute("ALTER TABLE lista_prioridades ADD COLUMN protocolo_rec TEXT DEFAULT NULL")
            if "comprar_con_ec" not in lp_cols:
                db.execute("ALTER TABLE lista_prioridades ADD COLUMN comprar_con_ec INTEGER DEFAULT 0")
            if "ec_pagado" not in lp_cols:
                db.execute("ALTER TABLE lista_prioridades ADD COLUMN ec_pagado INTEGER DEFAULT 0")
            db.commit()
        except Exception as e:
            print(f"[DB] lista_prioridades protocol migration warning: {e}")

        # Migrate wishlist_items: add EC columns if missing
        try:
            wl_cols = [r["name"] for r in db.execute("PRAGMA table_info(wishlist_items)").fetchall()]
            if "comprar_con_ec" not in wl_cols:
                db.execute("ALTER TABLE wishlist_items ADD COLUMN comprar_con_ec INTEGER DEFAULT 0")
            if "ec_sugerido" not in wl_cols:
                db.execute("ALTER TABLE wishlist_items ADD COLUMN ec_sugerido INTEGER DEFAULT NULL")
            if "ec_pagado" not in wl_cols:
                db.execute("ALTER TABLE wishlist_items ADD COLUMN ec_pagado INTEGER DEFAULT 0")
            db.commit()
        except Exception as e:
            print(f"[DB] wishlist EC migration warning: {e}")

        # Migrate profile_docs: add field_key column if missing
        try:
            pd_cols = [r["name"] for r in db.execute("PRAGMA table_info(profile_docs)").fetchall()]
            if "field_key" not in pd_cols:
                db.execute("ALTER TABLE profile_docs ADD COLUMN field_key TEXT DEFAULT NULL")
                db.commit()
        except Exception as e:
            print(f"[DB] profile_docs migration warning: {e}")

        # Migrate activity_logs: add xp column if not present (legacy support)
        try:
            al_cols = [r["name"] for r in db.execute("PRAGMA table_info(activity_logs)").fetchall()]
            if "xp" not in al_cols:
                db.execute("ALTER TABLE activity_logs ADD COLUMN xp INTEGER DEFAULT 0")
                db.commit()
        except Exception as e:
            print(f"[DB] activity_logs migration warning: {e}")

        # Seed default special events (inactive by default)
        if db.execute("SELECT COUNT(*) as c FROM special_events").fetchone()["c"] == 0:
            import datetime as _dt
            now = _dt.datetime.now().isoformat()
            db.executemany(
                """INSERT INTO special_events
                   (key, name, description, event_type, xp_multiplier, coin_multiplier,
                    focus_category, focus_bonus, is_active, created_at)
                   VALUES (?,?,?,?,?,?,?,?,0,?)""",
                [
                    ("doble_xp",
                     "Día Doble XP",
                     "Todo el XP ganado se duplica durante este período",
                     "double_xp", 2.0, 1.0, "", 1.0, now),
                    ("semana_enfoque",
                     "Semana de Enfoque",
                     "Las actividades de Programación generan el doble de coins",
                     "category_focus", 1.0, 1.0, "Programación", 2.0, now),
                    ("boost_disciplina",
                     "Boost de Disciplina",
                     "Las actividades de Salud Física generan +50% coins",
                     "coin_boost", 1.0, 1.5, "Salud Física", 1.5, now),
                ]
            )

        db.commit()
  except Exception as e:
    print(f"[DB] init_db error (app seguirá iniciando): {e}")


# ── Shared stat helpers ───────────────────────────────────────────────────────

def get_activity_streak():
    with get_db() as db:
        dates = [r["date"] for r in db.execute(
            "SELECT DISTINCT date FROM activity_logs ORDER BY date DESC"
        ).fetchall()]
        streak, check = 0, date.today()
        for d in dates:
            if d == check.isoformat():
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        return streak


def get_gtd_streak():
    with get_db() as db:
        dates = [r["date"] for r in db.execute(
            "SELECT DISTINCT date FROM gtd_points_log ORDER BY date DESC"
        ).fetchall()]
        streak, check = 0, date.today()
        for d in dates:
            if d == check.isoformat():
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        return streak


def get_gtd_stats():
    # Deferred import to avoid circular dependency (engine.py imports database.py)
    from modules.gamification.engine import get_level_info, get_gamification_streak

    today       = date.today().isoformat()
    week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()
    with get_db() as db:
        # XP contributed by PRAXIS tasks to the main ledger
        pts_today  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task' AND date=?",  (today,)).fetchone()["s"]
        pts_week   = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task' AND date>=?", (week_start,)).fetchone()["s"]
        pts_month  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task' AND date>=?", (month_start,)).fetchone()["s"]
        pts_total  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task'").fetchone()["s"]
        # Global XP for level calculation (same source as main dashboard)
        total_xp   = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger").fetchone()["s"]
        done_today = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE completed_at=?", (today,)).fetchone()["c"]
        inbox_n    = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE status='inbox'").fetchone()["c"]
        next_n     = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE status='next'").fetchone()["c"]
        proj_n     = db.execute("SELECT COUNT(*) as c FROM gtd_projects WHERE status='active'").fetchone()["c"]
    # Use the main gamification engine — same level thresholds and streak logic
    streak     = get_gamification_streak()
    level_info = get_level_info(total_xp)
    return dict(pts_today=pts_today, pts_week=pts_week, pts_month=pts_month, pts_total=pts_total,
                total_xp=total_xp, done_today=done_today, inbox_n=inbox_n, next_n=next_n, proj_n=proj_n,
                streak=streak,
                level=level_info["level"], level_name=level_info["level_name"],
                level_pct=level_info["level_pct"], xp_to_next=level_info["xp_to_next"])


def get_db_status():
    """Diagnostic snapshot: persistence mode, table row counts, last activity."""
    status = {
        "mode":        "hybrid (SQLite + Turso)" if _USE_HYBRID else "local SQLite only",
        "turso_url":   TURSO_URL[:40] + "..." if TURSO_URL else "NOT SET",
        "db_path":     _DB_PATH,
        "db_exists":   os.path.exists(_DB_PATH),
        "tables":      {},
        "last_activity": None,
        "total_xp":    0,
    }
    try:
        with get_db() as db:
            for tbl in ["activity_logs", "gtd_tasks", "priorities", "xp_ledger",
                        "coins_ledger", "gtd_projects", "lang_journal", "meal_plan",
                        "budget_items", "lista_prioridades", "achievements"]:
                try:
                    n = db.execute(f"SELECT COUNT(*) as c FROM {tbl}").fetchone()["c"]
                    status["tables"][tbl] = n
                except Exception:
                    status["tables"][tbl] = "?"
            try:
                status["total_xp"] = db.execute(
                    "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger"
                ).fetchone()["s"]
                last = db.execute(
                    "SELECT date, activity_key FROM activity_logs ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if last:
                    status["last_activity"] = f"{last['date']} — {last['activity_key']}"
            except Exception:
                pass
    except Exception as e:
        status["error"] = str(e)
    return status
