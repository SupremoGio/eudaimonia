import os, json as _json, http.client, threading, base64 as _base64, time as _time
from datetime import date, timedelta
from utils import today_str, today_date

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

import sqlite3 as _sqlite3
import tempfile as _tempfile
import traceback as _traceback

# Priority: DATABASE_PATH env var (Railway Volume) > sibling pipeline.db
_LOCAL     = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline.db')
)
_LOCAL_TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eudaimonia_sync.db")  # persistent hybrid cache (no usar tempdir — se borra)

# ── Turso HTTP (writes only) ──────────────────────────────────────────────────

_tls = threading.local()   # thread-local storage for HTTP connections

def _to_arg(v):
    if v is None:                        return {"type": "null"}
    if isinstance(v, bool):              return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):               return {"type": "integer", "value": str(v)}
    if isinstance(v, float):             return {"type": "float",   "value": v}
    if isinstance(v, (bytes, bytearray)): return {"type": "blob",   "value": _base64.b64encode(bytes(v)).decode()}
    return {"type": "text", "value": str(v)}

def _from_cell(cell):
    if cell is None:              return None
    t = cell.get("type", "text")
    v = cell.get("value")
    if t == "null" or v is None:  return None
    if t == "integer":            return int(v)
    if t in ("float", "real"):    return float(v)
    if t == "blob":               return _base64.b64decode(v) if v else b""
    return v

def _turso_pipeline(host, token, stmts, timeout=15, retries=3):
    reqs = [{"type": "execute", "stmt": s} for s in stmts]
    reqs.append({"type": "close"})
    body = _json.dumps({"requests": reqs}).encode()
    hdrs = {"Authorization": f"Bearer {token}",
            "Content-Type": "application/json", "Connection": "keep-alive"}
    for attempt in range(retries):
        try:
            # Use a thread-local connection — avoids race conditions between workers
            conn = getattr(_tls, 'conn', None)
            if conn is None:
                conn = http.client.HTTPSConnection(host, timeout=timeout)
                _tls.conn = conn
            conn.request("POST", "/v2/pipeline", body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {data[:100]}")
            return _json.loads(data.decode())
        except Exception as e:
            _tls.conn = None   # reset only this thread's connection
            if attempt == retries - 1:
                raise

def _turso_sync(host, token, writes):
    """Background: replay write statements to Turso for persistence."""
    try:
        BATCH = 20
        for i in range(0, len(writes), BATCH):
            _turso_pipeline(host, token, writes[i:i+BATCH])
    except Exception as e:
        print(f"[DB] Turso sync warning: {e}")

_RESTORE_BUDGET_SECS = 25  # tope duro: nunca dejar colgado el boot del server


def _restore_from_turso(host, token, target_path):
    """On startup: copy all Turso data into local SQLite at `target_path`.

    Acotado a _RESTORE_BUDGET_SECS de reloj: con decenas de tablas, cada una
    con hasta 3 reintentos de 15s si Turso está lento/inalcanzable, esto podía
    tardar minutos y colgar el arranque de gunicorn (nunca llega a bindear el
    puerto -> el hosting mata el deploy por timeout). Si se agota el
    presupuesto, sigue con lo que ya se restauró en vez de tardar indefinido.
    """
    deadline = _time.monotonic() + _RESTORE_BUDGET_SECS
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

        local = _sqlite3.connect(target_path)
        local.execute("PRAGMA journal_mode=WAL")
        restored, skipped = 0, 0
        for t in tables:
            if _time.monotonic() > deadline:
                skipped = len(tables) - restored
                print(f"[DB] Restore: presupuesto de {_RESTORE_BUDGET_SECS}s agotado, "
                      f"{restored} tablas restauradas, {skipped} omitidas (arrancando de todos modos)")
                break
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
                    [{"sql": f"SELECT * FROM [{name}]", "args": []}], retries=1)
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
                restored += 1
            except Exception as e:
                print(f"[DB] restore {name}: {e}")
        local.commit()
        local.close()
        print(f"[DB] Restored {restored}/{len(tables)} tables from Turso OK")
        return True
    except Exception as e:
        print(f"[DB] Restore failed: {e}")
        _traceback.print_exc()
        return False

# ── Hybrid connection: local SQLite reads + async Turso writes ────────────────

class _HybridConn:
    def __init__(self, db_path, turso_host, turso_token, async_sync=False):
        self._db    = _sqlite3.connect(db_path)
        self._db.row_factory = _sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._host  = turso_host
        self._token = turso_token
        self._writes = []
        self._sync_thread = None
        # True cuando db_path vive en un volumen persistente de Railway (ver
        # selección de backend más abajo): el SQLite local ya sobrevive un
        # redeploy por sí solo, así que Turso es un respaldo fuera del camino
        # crítico y el commit no necesita esperarlo. False (default) preserva
        # el comportamiento síncrono de siempre para cuando NO hay volumen y
        # el filesystem local es efímero -- ahí sí hay que esperar a Turso.
        self._async_sync = async_sync

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
            if self._async_sync:
                # db_path vive en un volumen persistente de Railway: el
                # commit de arriba YA es durable por sí solo y sobrevive un
                # redeploy sin ayuda de Turso. Empujar a Turso en background
                # evita que la latencia de red a Turso (o que esté caído)
                # bloquee cada escritura de la app -- si el push falla o
                # tarda, el dato ya está a salvo en el volumen; Turso solo
                # pierde ese respaldo puntual y se pone al día en el
                # siguiente write.
                threading.Thread(
                    target=_turso_sync, args=(self._host, self._token, writes),
                    daemon=True,
                ).start()
            else:
                # Síncrono a propósito: sin volumen, el SQLite local vive en
                # el filesystem efímero del contenedor -- si el redeploy
                # ocurre antes de que un sync en background termine, esos
                # writes nunca llegan a Turso y el próximo arranque los borra
                # sin aviso, aunque SQLite local ya los haya confirmado. Un
                # caso real: ~50 filas recuperadas por /admin/recover-montos
                # se perdieron así al redesplegar minutos después. Bloquear
                # aquí hasta que Turso confirme el escrito es la única forma
                # de que "ya se guardó" signifique lo mismo para el usuario
                # que para el próximo arranque del contenedor.
                _turso_sync(self._host, self._token, writes)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.commit()
        self.close()

# ── Backend selection ─────────────────────────────────────────────────────────

_USE_HYBRID  = False
_TURSO_HOST  = ""
_TURSO_TOKEN_VAL = ""
_TURSO_ASYNC = False

# DATABASE_PATH solo se define en Railway cuando hay un volumen persistente
# montado (ver CLAUDE.md) -- su presencia es la señal de que el SQLite local
# sobrevive un redeploy por sí mismo y puede ser la fuente de verdad.
_HAS_VOLUME = bool(os.environ.get("DATABASE_PATH"))

# Verificación real, no solo confiar en que la env var está puesta: si
# DATABASE_PATH apunta a una carpeta que no existe en el contenedor, el
# volumen de Railway NO está montado ahí (mount path mal configurado o
# distinto al de la variable) -- sqlite3.connect() fallaría con
# "unable to open database file" en cada request. Mejor caer al modo
# síncrono de siempre (que sí funciona, aunque sin volumen) que arrancar
# "en modo volumen" creyendo tener persistencia y no tenerla.
if _HAS_VOLUME and not os.path.isdir(os.path.dirname(_LOCAL) or "."):
    print(f"[DB] AVISO: DATABASE_PATH={_LOCAL!r} pero esa carpeta no existe en "
          f"el contenedor -- el volumen de Railway no está montado ahí "
          f"(revisa el Mount Path del volumen en Railway y que coincida con "
          f"DATABASE_PATH). Usando modo sin volumen por ahora para no romper "
          f"la app ni perder datos silenciosamente.")
    _HAS_VOLUME = False
    # _LOCAL apuntaba a una carpeta inexistente (DATABASE_PATH roto) -- cae
    # al mismo path que se usaría si DATABASE_PATH nunca se hubiera definido,
    # para que _DB_PATH (más abajo) y todo lo demás quede consistente.
    _LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline.db')

_DB_PATH = _LOCAL

if TURSO_URL and TURSO_TOKEN:
    try:
        _host = TURSO_URL.replace("libsql://", "")
        # timeout corto + un solo intento: si Turso no responde (host caído,
        # credenciales de otro entorno, red que no lo alcanza), hay que
        # saber eso en segundos y arrancar con SQLite local — no en minutos.
        _turso_pipeline(_host, TURSO_TOKEN, [{"sql": "SELECT 1", "args": []}], timeout=6, retries=1)
        _USE_HYBRID      = True
        _TURSO_HOST      = _host
        _TURSO_TOKEN_VAL = TURSO_TOKEN

        if _HAS_VOLUME:
            # Volumen de Railway presente: el SQLite en _LOCAL (DATABASE_PATH)
            # es la fuente de verdad, Turso es un respaldo async fuera del
            # camino crítico (ver _HybridConn.commit). Solo se restaura DESDE
            # Turso si el volumen está vacío (primer deploy o volumen nuevo)
            # -- nunca se pisa un volumen que ya tiene datos con una copia de
            # Turso que podría ser más vieja que lo último escrito local.
            _DB_PATH     = _LOCAL
            _TURSO_ASYNC = True
            if not os.path.exists(_LOCAL):
                print("[DB] Volumen vacio - restaurando bootstrap desde Turso...")
                _restore_from_turso(_host, TURSO_TOKEN, _LOCAL)
            print("[DB] Modo: SQLite en volumen (fuente de verdad) + Turso backup async OK")
        else:
            # Sin DATABASE_PATH no hay volumen montado -- el filesystem del
            # contenedor es efímero y Turso es la única copia que sobrevive
            # un redeploy, así que el write debe bloquear hasta que Turso lo
            # confirme (ver rama síncrona en _HybridConn.commit).
            print("[DB] Turso conectado OK - restaurando datos locales (sin volumen, modo sync)...")
            _restore_from_turso(_host, TURSO_TOKEN, _LOCAL_TMP)
            _DB_PATH = _LOCAL_TMP
            print("[DB] Modo hibrido: SQLite local (rapido) + Turso (persistencia, sync) OK")
    except Exception as e:
        print(f"[DB] TURSO FALLO ({e}) - usando SQLite local"
              f"{' en volumen' if _HAS_VOLUME else ' (datos NO persistiran en redeploy)'}")

def get_db():
    if _USE_HYBRID:
        return _HybridConn(_DB_PATH, _TURSO_HOST, _TURSO_TOKEN_VAL, async_sync=_TURSO_ASYNC)
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
        CREATE TABLE IF NOT EXISTS body_measurements_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
        -- Lectura de plicómetro (calibrador de pliegues cutáneos): el usuario
        -- registra los 3 valores que ya obtuvo de su propia tabla/dispositivo
        -- (mm, % de grasa, categoría) — no calculamos la fórmula acá para no
        -- inventar una conversión que no coincida con su tabla real.
        CREATE TABLE IF NOT EXISTS pliegue_grasa_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha      TEXT NOT NULL,
            mm         REAL NOT NULL,
            porcentaje REAL NOT NULL,
            categoria  TEXT DEFAULT '',
            notas      TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        -- Talla de ropa por marca: camisa/playera/pantalón varían de marca a
        -- marca, por eso es una lista (una fila por marca) y no un valor único.
        CREATE TABLE IF NOT EXISTS tallas_marca (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            prenda     TEXT NOT NULL,
            marca      TEXT NOT NULL,
            talla      TEXT NOT NULL,
            notas      TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profile_docs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT NOT NULL,
            original    TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        );
        -- password_enc guarda el cifrado Fernet (derivado de SECRET_KEY) del
        -- password en texto plano — nunca se guarda ni se manda sin cifrar.
        CREATE TABLE IF NOT EXISTS password_vault (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            servicio     TEXT    NOT NULL,
            usuario      TEXT    DEFAULT '',
            password_enc TEXT    NOT NULL,
            url          TEXT    DEFAULT '',
            notas        TEXT    DEFAULT '',
            created_at   TEXT    NOT NULL,
            updated_at   TEXT    DEFAULT NULL
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
        CREATE TABLE IF NOT EXISTS lang_vocab_srs (
            word           TEXT    NOT NULL,
            language       TEXT    NOT NULL,
            interval_days  INTEGER NOT NULL DEFAULT 1,
            ease           REAL    NOT NULL DEFAULT 2.3,
            next_review    TEXT    NOT NULL,
            correct_count  INTEGER NOT NULL DEFAULT 0,
            wrong_count    INTEGER NOT NULL DEFAULT 0,
            last_seen      TEXT,
            PRIMARY KEY (word, language)
        );
        CREATE TABLE IF NOT EXISTS lang_plan_checkpoints (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fase          INTEGER NOT NULL,
            nombre        TEXT    NOT NULL,
            semana_fin    INTEGER NOT NULL,
            criterio      TEXT    NOT NULL,
            completado    INTEGER NOT NULL DEFAULT 0,
            completado_at TEXT
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
            ultimo_uso   TEXT    DEFAULT NULL,
            foto         TEXT    DEFAULT '',
            notas        TEXT    DEFAULT '',
            url          TEXT    DEFAULT '',
            activo       INTEGER DEFAULT 1,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outfits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT    NOT NULL,
            ocasion     TEXT    DEFAULT '',
            rating      INTEGER DEFAULT 0,
            foto        TEXT    DEFAULT '',
            notas       TEXT    DEFAULT '',
            veces_usado INTEGER DEFAULT 0,
            ultimo_uso  TEXT    DEFAULT NULL,
            created_at  TEXT    NOT NULL
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
                ]
            )

        # Migrate body_measurements: agregar medidas de rendimiento atlético
        # (idempotente vía INSERT OR IGNORE — key es PRIMARY KEY)
        db.executemany(
            "INSERT OR IGNORE INTO body_measurements (key, label, value, unit) VALUES (?,?,?,?)",
            [
                ("biceps",         "Bíceps",          "— editar —", "cm"),
                ("antebrazo",      "Antebrazo",       "— editar —", "cm"),
                ("muslo",          "Muslo",           "— editar —", "cm"),
                ("pantorrilla",    "Pantorrilla",     "— editar —", "cm"),
                ("grasa_corporal", "Grasa corporal",  "— editar —", "%"),
                ("masa_muscular",  "Masa muscular",   "— editar —", "%"),
            ]
        )

        # Las tallas de ropa (camisa/playera/pantalón) varían por marca, así que
        # dejaron de ser un valor único en body_measurements y pasaron a
        # tallas_marca (una fila por marca). Se quitan las llaves viejas si
        # quedaron de una versión anterior.
        db.execute("DELETE FROM body_measurements WHERE key IN ('t_camisa','t_playera','t_pantalon')")
        db.execute("DELETE FROM body_measurements_history WHERE key IN ('t_camisa','t_playera','t_pantalon')")
        db.commit()

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

        # Dedup rewards — keep lowest id per name (idempotent)
        try:
            db.execute("""
                DELETE FROM rewards WHERE id NOT IN (
                    SELECT MIN(id) FROM rewards GROUP BY LOWER(TRIM(name))
                )
            """)
            db.commit()
        except Exception as e:
            print(f"[DB] rewards dedup warning: {e}")

        # Migrate rewards: add weekend_only (recompensas de fin de semana, tipo gasto pequeño)
        try:
            rw_cols = [r["name"] for r in db.execute("PRAGMA table_info(rewards)").fetchall()]
            if "weekend_only" not in rw_cols:
                db.execute("ALTER TABLE rewards ADD COLUMN weekend_only INTEGER DEFAULT 0")
                db.commit()
        except Exception as e:
            print(f"[DB] rewards weekend_only migration warning: {e}")

        # Seed recompensa "Cápsula Nespresso" — fin de semana + cooldown semanal (idempotente)
        if db.execute("SELECT COUNT(*) as c FROM rewards WHERE LOWER(name)=?", ("cápsula nespresso",)).fetchone()["c"] == 0:
            import datetime as _dtc
            db.execute(
                """INSERT INTO rewards (name, description, ec_cost, level_required, badge_required, cooldown_days, weekend_only, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    "Cápsula Nespresso",
                    "Un café de fin de semana — te la ganaste, no un hábito diario",
                    8, 1, "", 7, 1,
                    _dtc.datetime.now().isoformat(),
                )
            )
            db.commit()

        # Dedup consumo_productos — keep lowest id per nombre, orphan compras go too
        try:
            db.execute("""
                DELETE FROM consumo_compras WHERE producto_id NOT IN (
                    SELECT MIN(id) FROM consumo_productos GROUP BY LOWER(TRIM(nombre))
                )
            """)
            db.execute("""
                DELETE FROM consumo_productos WHERE id NOT IN (
                    SELECT MIN(id) FROM consumo_productos GROUP BY LOWER(TRIM(nombre))
                )
            """)
            db.commit()
        except Exception as e:
            print(f"[DB] consumo dedup warning: {e}")

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

        # Migrate gtd_tasks: add Eisenhower/Praxis columns if missing
        try:
            gtd_cols = [r["name"] for r in db.execute("PRAGMA table_info(gtd_tasks)").fetchall()]
            praxis_alters = [
                ('importante',       'ALTER TABLE gtd_tasks ADD COLUMN importante INTEGER DEFAULT NULL'),
                ('urgente',          'ALTER TABLE gtd_tasks ADD COLUMN urgente INTEGER DEFAULT NULL'),
                ('cuadrante',        'ALTER TABLE gtd_tasks ADD COLUMN cuadrante TEXT DEFAULT NULL'),
                ('tipo',             "ALTER TABLE gtd_tasks ADD COLUMN tipo TEXT DEFAULT 'tarea'"),
                ('completado',       'ALTER TABLE gtd_tasks ADD COLUMN completado INTEGER DEFAULT 0'),
                ('fecha_completado', 'ALTER TABLE gtd_tasks ADD COLUMN fecha_completado TEXT DEFAULT NULL'),
                ('fecha_limite',     'ALTER TABLE gtd_tasks ADD COLUMN fecha_limite TEXT DEFAULT NULL'),
                ('notas',            'ALTER TABLE gtd_tasks ADD COLUMN notas TEXT DEFAULT NULL'),
                ('actualizado_en',   'ALTER TABLE gtd_tasks ADD COLUMN actualizado_en TEXT DEFAULT NULL'),
            ]
            for col, sql in praxis_alters:
                if col not in gtd_cols:
                    db.execute(sql)
            db.commit()
            # Populate new columns from old data (idempotent)
            db.execute("""UPDATE gtd_tasks SET completado=1,
                fecha_completado=COALESCE(NULLIF(completed_at,''), created_at)
                WHERE status='done' AND (completado IS NULL OR completado=0)""")
            db.execute("""UPDATE gtd_tasks SET importante=0, urgente=0, cuadrante='ideas'
                WHERE status='someday' AND importante IS NULL""")
            db.execute("""UPDATE gtd_tasks SET fecha_limite=due_date
                WHERE due_date IS NOT NULL AND due_date!=''
                AND (fecha_limite IS NULL OR fecha_limite='')""")
            db.execute("""UPDATE gtd_tasks SET notas=description
                WHERE description IS NOT NULL AND description!=''
                AND (notas IS NULL OR notas='')""")
            # "Nota" (tipo de captura) se renombró a "Mantenimiento" — mismo flujo
            # de Inbox/cuadrantes, solo cambia la etiqueta/ícono en Praxis.
            db.execute("UPDATE gtd_tasks SET tipo='mantenimiento' WHERE tipo='nota'")
            db.commit()
        except Exception as e:
            print(f"[DB] gtd_tasks praxis migration warning: {e}")

        # Deduplicate personal_info rows with same label — keep lowest rowid, migrate docs
        try:
            dupes = db.execute(
                "SELECT label FROM personal_info GROUP BY label HAVING COUNT(*) > 1"
            ).fetchall()
            for d in dupes:
                rows = db.execute(
                    "SELECT key FROM personal_info WHERE label=? ORDER BY rowid", (d['label'],)
                ).fetchall()
                keep_key = rows[0]['key']
                for row in rows[1:]:
                    del_key = row['key']
                    db.execute(
                        "UPDATE profile_docs SET field_key=? WHERE field_key=?",
                        (keep_key, del_key)
                    )
                    db.execute("DELETE FROM personal_info WHERE key=?", (del_key,))
            if dupes:
                db.commit()
        except Exception as e:
            print(f"[DB] personal_info dedup warning: {e}")

        # Migrate profile_docs: add field_key and content columns if missing
        try:
            pd_cols = [r["name"] for r in db.execute("PRAGMA table_info(profile_docs)").fetchall()]
            if "field_key" not in pd_cols:
                db.execute("ALTER TABLE profile_docs ADD COLUMN field_key TEXT DEFAULT NULL")
                db.commit()
            if "content" not in pd_cols:
                db.execute("ALTER TABLE profile_docs ADD COLUMN content BLOB DEFAULT NULL")
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

        # Migrate wardrobe_items: add url column if not present
        try:
            wi_cols = [r["name"] for r in db.execute("PRAGMA table_info(wardrobe_items)").fetchall()]
            if "url" not in wi_cols:
                db.execute("ALTER TABLE wardrobe_items ADD COLUMN url TEXT DEFAULT ''")
                db.commit()
            # ultimo_uso: fecha del último uso (para «sin usar en 90 días»).
            # Las prendas previas a esta columna quedan en NULL.
            if "ultimo_uso" not in wi_cols:
                db.execute("ALTER TABLE wardrobe_items ADD COLUMN ultimo_uso TEXT DEFAULT NULL")
                db.commit()
        except Exception as e:
            print(f"[DB] wardrobe_items migration warning: {e}")

        # Migrate outfits: add usage tracking columns if not present
        try:
            ot_cols = [r["name"] for r in db.execute("PRAGMA table_info(outfits)").fetchall()]
            if "veces_usado" not in ot_cols:
                db.execute("ALTER TABLE outfits ADD COLUMN veces_usado INTEGER DEFAULT 0")
            if "ultimo_uso" not in ot_cols:
                db.execute("ALTER TABLE outfits ADD COLUMN ultimo_uso TEXT DEFAULT NULL")
            db.commit()
        except Exception as e:
            print(f"[DB] outfits migration warning: {e}")

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

        # ── HEGEMONIKON — Salud médica ───────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS medico_episodios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo         TEXT    NOT NULL DEFAULT 'enfermedad',
            titulo       TEXT    NOT NULL,
            descripcion  TEXT    DEFAULT '',
            zona_cuerpo  TEXT    DEFAULT '',
            fecha_inicio TEXT    NOT NULL,
            fecha_fin    TEXT    DEFAULT NULL,
            activo       INTEGER DEFAULT 1,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS medico_recetas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            episodio_id  INTEGER NOT NULL,
            medico       TEXT    DEFAULT '',
            especialidad TEXT    DEFAULT '',
            fecha        TEXT    NOT NULL,
            notas        TEXT    DEFAULT '',
            created_at   TEXT    NOT NULL,
            FOREIGN KEY (episodio_id) REFERENCES medico_episodios(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS medico_medicamentos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            receta_id     INTEGER NOT NULL,
            nombre        TEXT    NOT NULL,
            dosis         TEXT    DEFAULT '',
            frecuencia    TEXT    DEFAULT '',
            duracion_dias INTEGER DEFAULT NULL,
            tomando       INTEGER DEFAULT 1,
            created_at    TEXT    NOT NULL,
            FOREIGN KEY (receta_id) REFERENCES medico_recetas(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS medico_documentos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            episodio_id     INTEGER NOT NULL,
            tipo            TEXT    NOT NULL DEFAULT 'receta',
            nombre_archivo  TEXT    NOT NULL,
            nombre_original TEXT    DEFAULT '',
            fecha           TEXT    NOT NULL,
            created_at      TEXT    NOT NULL,
            FOREIGN KEY (episodio_id) REFERENCES medico_episodios(id) ON DELETE CASCADE
        );
        """)

        # ── MIGRATIONS LOG ───────────────────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS migration_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            version     TEXT    NOT NULL UNIQUE,
            description TEXT    DEFAULT '',
            applied_at  TEXT    NOT NULL
        );
        """)

        # ── ATARAXIA — Rutinas fin de semana ─────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS rutina_bloques (
            id           TEXT PRIMARY KEY,
            dia          TEXT NOT NULL,
            bloque_id    TEXT NOT NULL,
            nombre       TEXT NOT NULL,
            tier         TEXT NOT NULL DEFAULT 'micro',
            xp           INTEGER DEFAULT 0,
            ec           INTEGER DEFAULT 0,
            categoria    TEXT DEFAULT '',
            opcional     INTEGER DEFAULT 0,
            duracion_min INTEGER DEFAULT 0,
            orden        INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rutina_progreso (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            bloque_id       TEXT NOT NULL,
            semana_id       TEXT NOT NULL,
            completado      INTEGER DEFAULT 0,
            completado_at   TEXT,
            tiempo_real_seg INTEGER,
            UNIQUE(bloque_id, semana_id)
        );
        """)

        if db.execute("SELECT COUNT(*) as c FROM rutina_bloques").fetchone()["c"] == 0:
            db.executemany(
                """INSERT INTO rutina_bloques
                   (id, dia, bloque_id, nombre, tier, xp, ec, categoria, opcional, duracion_min, orden)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    # ── SÁBADO ───────────────────────────────────────────────
                    ("sat_arranque",   "sabado","sat_bloque1","Café · robot sala · 1ª carga de ropa",       "micro",   0,0,"",       0, 20,  1),
                    ("sat_limpieza",   "sabado","sat_bloque1","Limpieza: baño · buró · cocina · mop · plantas","progreso",3,1,"",    0, 65,  2),
                    ("sat_transicion", "sabado","sat_bloque1","Tender ropa · robot recámara",               "micro",   0,0,"",       0,  5,  3),
                    ("sat_jugos_r",    "sabado","sat_bloque1","Preparar jugos",                             "progreso",2,1,"SOMA",   1, 25,  4),
                    ("sat_ensayo",     "sabado","sat_bloque2","Ensayo",                                     "alto",    4,2,"PAIDEIA",0,120,  5),
                    ("sat_gym",        "sabado","sat_bloque3","Gym (1.5 hrs + traslado)",                  "alto",    4,2,"SOMA",   0,105,  6),
                    ("sat_ropa",       "sabado","sat_bloque3","Recoger ropa · orden general rápido",        "micro",   0,0,"",       0, 20,  7),
                    ("sat_cierre",     "sabado","sat_bloque3","Cierre: casa limpia · ensayo hecho · gym hecho","micro", 0,0,"",      0, 15,  8),
                    # ── DOMINGO ──────────────────────────────────────────────
                    ("sun_arranque",   "domingo","sun_reflexion","Café · enchufar todos los dispositivos",  "micro",   0,0,"",            0, 20,  1),
                    ("sun_gym_r",      "domingo","sun_reflexion","Gym",                                   "alto",    4,2,"SOMA",         0,105,  2),
                    ("sun_comidas_r",  "domingo","sun_comidas",  "Preparar comida semanal (1 hora enfocada)","progreso",3,1,"SOMA",       0, 60,  3),
                    ("sun_planchar_r", "domingo","sun_planchar", "Planchar uniforme (20 min)",             "micro",   0,0,"",            0, 20,  4),
                    ("sun_finanzas",   "domingo","sun_diseno",   "Finanzas: gastos semana · proyección",   "alto",    4,2,"HEGEMONIKON",  0, 40,  5),
                    ("sun_planeacion", "domingo","sun_reflexion","Planeación: agenda · compromisos · GTD", "alto",    4,2,"HEGEMONIKON",  0, 45,  6),
                    ("sun_prioridades","domingo","sun_reflexion","3 prioridades de la semana",             "progreso",3,1,"HEGEMONIKON",  0, 15,  7),
                    ("sun_jugos_r",    "domingo","sun_jugos",    "Preparar jugos",                         "progreso",2,1,"SOMA",         0, 25,  8),
                    ("sun_cargas",     "domingo","sun_planchar", "Verificar cargas: pila · audífonos · iPad","micro", 0,0,"",            0, 15,  9),
                    ("sun_cierre",     "domingo","sun_reflexion","Cierre: prioridades claras · preparar lunes","micro",0,0,"",           0, 15, 10),
                ]
            )
            db.commit()

        # Migrate rutina_bloques v2 — nueva estructura Sáb/Dom sin Ensayo
        try:
            already = db.execute(
                "SELECT COUNT(*) as c FROM rutina_bloques WHERE id='sat_ventilacion'"
            ).fetchone()["c"]
            if not already:
                db.execute("DELETE FROM rutina_bloques WHERE dia IN ('sabado','domingo')")
                db.executemany(
                    """INSERT INTO rutina_bloques
                       (id, dia, bloque_id, nombre, tier, xp, ec, categoria, opcional, duracion_min, orden)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        # ── SÁBADO — 7 bloques ──────────────────────────────────────────
                        # Bloque 1: Mantenimiento & Recepción (5 sub-tareas)
                        ("sat_ventilacion","sabado","sat_bloque1","Ventilación Fast Track (abrir ventanas)",                        "micro",   0,0,"",       0,  5,  1),
                        ("sat_nespresso",  "sabado","sat_bloque1","Mantenimiento Nespresso (vaciar cápsulas · enjuagar · bandeja)",  "micro",   0,0,"",       0, 10,  2),
                        ("sat_cocina_r",   "sabado","sat_bloque1","Reset de Cocina (platos lavados · barra limpia)",               "micro",   0,0,"",       0, 10,  3),
                        ("sat_despensa",   "sabado","sat_bloque1","Recibir despensa (recibir · desinfectar · acomodar)",            "micro",   0,0,"",       0, 20,  4),
                        ("sat_carga1",     "sabado","sat_bloque1","Carga Inicial (1ª tanda de ropa en lavadora)",                   "micro",   0,0,"",       0,  5,  5),
                        # Gym slot (12:30 – 2:00 PM)
                        ("sat_gym",        "sabado","sat_gym_bloque","Gym (entrenamiento de fuerza / hipertrofia)",                 "alto",    4,2,"SOMA",   0, 90,  6),
                        # Bloque 2: Deep Work Limpieza — cada tarea es su propio bloque
                        ("sat_textiles_r", "sabado","sat_textiles_bloque","Textiles fuera · cambio de sábanas y toallas · carga 2", "micro",   0,0,"",       0, 15,  7),
                        ("sat_limpieza_r", "sabado","sat_limpieza_bloque","Limpieza de arriba a abajo (polvo · escritorios · repisas · setup)", "progreso",3,1,"", 0, 30, 8),
                        ("sat_bano_r",     "sabado","sat_bano_bloque","Desinfección de Baño (espejo · lavabo · WC · regadera)",     "progreso",2,1,"",       0, 20,  9),
                        ("sat_barrido_r",  "sabado","sat_barrido_bloque","Barrido y Trapeado General",                              "micro",   0,0,"",       0, 20, 10),
                        ("sat_jugos_r",    "sabado","sat_jugos_bloque","Preparar jugos de la semana (procesar · guardar)",          "progreso",2,1,"SOMA",   0, 30, 11),
                        # ── DOMINGO — 10 bloques ─────────────────────────────────────────
                        ("sun_cafe",       "domingo","sun_cafe_bloque","Café · enchufar todos los dispositivos",                   "micro",   0,0,"",            0, 15,  1),
                        ("sun_gym",        "domingo","sun_gym_bloque","Gym (entrenamiento enfocado · gym vacío)",                  "alto",    4,2,"SOMA",        0, 90,  2),
                        ("sun_nevera",     "domingo","sun_nevera_bloque","Nevera y Despensa (revisión rápida · limpieza de repisas)","micro",  0,0,"",            0, 15,  3),
                        ("sun_comidas",    "domingo","sun_comidas_bloque","Meal Prep: porcionar proteínas y carbohidratos (1 hora enfocada)","progreso",3,1,"SOMA", 0, 60, 4),
                        ("sun_guardado",   "domingo","sun_guardado_bloque","Guardado de ropa (doblar ropa limpia del sábado)",      "micro",   0,0,"",            0, 15,  5),
                        ("sun_planchar",   "domingo","sun_planchar_bloque","Planchado de uniforme para la semana",                  "micro",   0,0,"",            0, 20,  6),
                        ("sun_planeacion", "domingo","sun_planeacion_bloque","Planeación: agenda · compromisos · GTD",              "alto",    4,2,"HEGEMONIKON",  0, 45,  7),
                        ("sun_prioridades","domingo","sun_prioridades_bloque","3 prioridades de la semana",                        "progreso",3,1,"HEGEMONIKON",  0, 15,  8),
                        ("sun_reset",      "domingo","sun_reset_bloque","Eudaimonia OS Reset (Notion · finanzas · metas · código)", "progreso",2,1,"HEGEMONIKON",  0, 30,  9),
                        ("sun_cierre",     "domingo","sun_cierre_bloque","Cierre: prioridades claras · preparar lunes",            "micro",   0,0,"",            0, 15, 10),
                    ]
                )
                db.commit()
                print("[DB] rutina_bloques v2 migration OK — nueva estructura Sáb/Dom")
        except Exception as e:
            print(f"[DB] rutina_bloques v2 migration warning: {e}")

        # Migrate rutina_bloques v3 — Bloque 2 Baño movido después de Bloque 1;
        # Baño / Limpieza arriba-abajo / Barrido desglosados en sub-tareas; Jugos opcional
        try:
            already = db.execute(
                "SELECT COUNT(*) as c FROM rutina_bloques WHERE id='sat_bano_vidrio'"
            ).fetchone()["c"]
            if not already:
                db.execute("DELETE FROM rutina_bloques WHERE dia='sabado'")
                db.executemany(
                    """INSERT INTO rutina_bloques
                       (id, dia, bloque_id, nombre, tier, xp, ec, categoria, opcional, duracion_min, orden)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        # Bloque 1: Mantenimiento & Recepción (sin cambios)
                        ("sat_ventilacion","sabado","sat_bloque1","Ventilación Fast Track (abrir ventanas)",                        "micro",   0,0,"",       0,  5,  1),
                        ("sat_nespresso",  "sabado","sat_bloque1","Mantenimiento Nespresso (vaciar cápsulas · enjuagar · bandeja)",  "micro",   0,0,"",       0, 10,  2),
                        ("sat_cocina_r",   "sabado","sat_bloque1","Reset de Cocina (platos lavados · barra limpia)",               "micro",   0,0,"",       0, 10,  3),
                        ("sat_despensa",   "sabado","sat_bloque1","Recibir despensa (recibir · desinfectar · acomodar)",            "micro",   0,0,"",       0, 20,  4),
                        ("sat_carga1",     "sabado","sat_bloque1","Carga Inicial (1ª tanda de ropa en lavadora)",                   "micro",   0,0,"",       0,  5,  5),
                        # Bloque 2: Baño (nuevo — desglosado en sub-tareas)
                        ("sat_bano_vidrio",  "sabado","sat_bano_bloque","Limpieza de vidrio",  "micro",   0,0,"", 0,  4,  6),
                        ("sat_bano_espejo",  "sabado","sat_bano_bloque","Limpieza de espejo",  "micro",   0,0,"", 0,  3,  7),
                        ("sat_bano_lavabo",  "sabado","sat_bano_bloque","Limpieza de lavabo",  "micro",   0,0,"", 0,  4,  8),
                        ("sat_bano_wc",      "sabado","sat_bano_bloque","Limpieza de WC",      "micro",   0,0,"", 0,  5,  9),
                        ("sat_bano_repisa",  "sabado","sat_bano_bloque","Limpieza de repisa", "micro",   0,0,"", 0,  3, 10),
                        ("sat_bano_trapear", "sabado","sat_bano_bloque","Trapear",             "progreso",2,1,"", 0,  6, 11),
                        # Gym slot (12:30 – 2:00 PM)
                        ("sat_gym",        "sabado","sat_gym_bloque","Gym (entrenamiento de fuerza / hipertrofia)",                 "alto",    4,2,"SOMA",   0, 90, 12),
                        # Textiles
                        ("sat_textiles_r", "sabado","sat_textiles_bloque","Textiles fuera · cambio de sábanas y toallas · carga 2", "micro",   0,0,"",       0, 15, 13),
                        # Limpieza de Arriba a Abajo (desglosado en sub-tareas)
                        ("sat_limpieza_escritorio", "sabado","sat_limpieza_bloque","Limpiar Escritorio",  "micro",   0,0,"", 0,  4, 14),
                        ("sat_limpieza_buro",       "sabado","sat_limpieza_bloque","Limpiar Buró",        "micro",   0,0,"", 0,  3, 15),
                        ("sat_limpieza_mesa",       "sabado","sat_limpieza_bloque","Limpiar Mesa",        "micro",   0,0,"", 0,  3, 16),
                        ("sat_limpieza_microondas", "sabado","sat_limpieza_bloque","Limpiar Microondas",   "micro",   0,0,"", 0,  4, 17),
                        ("sat_limpieza_cocina",     "sabado","sat_limpieza_bloque","Limpiar Cocina",       "progreso",3,1,"", 0,  8, 18),
                        # Trapeado (antes "Barrido y Trapeado General" — desglosado en sub-tareas)
                        ("sat_trapear_sala",   "sabado","sat_barrido_bloque","Trapear Sala",   "micro", 0,0,"", 0,  7, 19),
                        ("sat_trapear_cuarto", "sabado","sat_barrido_bloque","Trapear Cuarto", "micro", 0,0,"", 0,  7, 20),
                        ("sat_trapear_bano",   "sabado","sat_barrido_bloque","Trapear Baño",    "micro", 0,0,"", 0,  6, 21),
                        # Jugos de la semana — ahora opcional
                        ("sat_jugos_r",    "sabado","sat_jugos_bloque","Preparar jugos de la semana (procesar · guardar)",          "progreso",2,1,"SOMA",   1, 30, 22),
                    ]
                )
                db.commit()
                print("[DB] rutina_bloques v3 migration OK — Bloque 2 Baño + sub-tareas + Jugos opcional")
        except Exception as e:
            print(f"[DB] rutina_bloques v3 migration warning: {e}")

        # Migrate rutina_bloques v4 — Domingo: "Arranque del Día" desglosado en
        # sub-tareas (café + cargas) y se elimina el bloque "Eudaimonia OS Reset"
        try:
            already = db.execute(
                "SELECT COUNT(*) as c FROM rutina_bloques WHERE id='sun_cafe_agua'"
            ).fetchone()["c"]
            if not already:
                db.execute("DELETE FROM rutina_bloques WHERE dia='domingo'")
                db.executemany(
                    """INSERT INTO rutina_bloques
                       (id, dia, bloque_id, nombre, tier, xp, ec, categoria, opcional, duracion_min, orden)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        # Bloque 1: Arranque del Día (desglosado en sub-tareas)
                        ("sun_cafe",            "domingo","sun_cafe_bloque","Café",                            "micro",0,0,"",0,  5,  1),
                        ("sun_cafe_agua",       "domingo","sun_cafe_bloque","Cargar dispensador de agua",       "micro",0,0,"",0,  2,  2),
                        ("sun_cafe_carro",      "domingo","sun_cafe_bloque","Cargar dispositivo del carro",     "micro",0,0,"",0,  2,  3),
                        ("sun_cafe_audifonos",  "domingo","sun_cafe_bloque","Cargar audífonos",                 "micro",0,0,"",0,  1,  4),
                        ("sun_cafe_aspiradora", "domingo","sun_cafe_bloque","Cargar aspiradora",                "micro",0,0,"",0,  2,  5),
                        ("sun_cafe_pila",       "domingo","sun_cafe_bloque","Cargar pila portátil",             "micro",0,0,"",0,  2,  6),
                        # Resto de bloques del domingo (sin cambios; "Eudaimonia OS Reset" eliminado)
                        ("sun_gym",        "domingo","sun_gym_bloque","Gym (entrenamiento enfocado · gym vacío)",                  "alto",    4,2,"SOMA",        0, 90,  7),
                        ("sun_nevera",     "domingo","sun_nevera_bloque","Nevera y Despensa (revisión rápida · limpieza de repisas)","micro",  0,0,"",            0, 15,  8),
                        ("sun_comidas",    "domingo","sun_comidas_bloque","Meal Prep: porcionar proteínas y carbohidratos (1 hora enfocada)","progreso",3,1,"SOMA", 0, 60,  9),
                        ("sun_guardado",   "domingo","sun_guardado_bloque","Guardado de ropa (doblar ropa limpia del sábado)",      "micro",   0,0,"",            0, 15, 10),
                        ("sun_planchar",   "domingo","sun_planchar_bloque","Planchado de uniforme para la semana",                  "micro",   0,0,"",            0, 20, 11),
                        ("sun_planeacion", "domingo","sun_planeacion_bloque","Planeación: agenda · compromisos · GTD",              "alto",    4,2,"HEGEMONIKON",  0, 45, 12),
                        ("sun_prioridades","domingo","sun_prioridades_bloque","3 prioridades de la semana",                        "progreso",3,1,"HEGEMONIKON",  0, 15, 13),
                        ("sun_cierre",     "domingo","sun_cierre_bloque","Cierre: prioridades claras · preparar lunes",            "micro",   0,0,"",            0, 15, 14),
                    ]
                )
                db.commit()
                print("[DB] rutina_bloques v4 migration OK — Arranque del Día desglosado + Eudaimonia OS Reset eliminado")
        except Exception as e:
            print(f"[DB] rutina_bloques v4 migration warning: {e}")

        # ── ACTA SÁBADO — se agregan "Robot aspiradora sala" y "Robot
        # aspiradora cuarto" al Bloque 1 (Mantenimiento & Recepción), y
        # "Cambiar toallas" al Bloque 2 (Baño).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='sat_robot_aspiradora_y_toallas'"
        ).fetchone():
            db.executemany(
                """INSERT INTO rutina_bloques
                   (id, dia, bloque_id, nombre, tier, xp, ec, categoria, opcional, duracion_min, orden)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    ("sat_robot_sala",   "sabado","sat_bloque1",    "Robot aspiradora sala",   "micro",0,0,"",0,5, 6),
                    ("sat_robot_cuarto", "sabado","sat_bloque1",    "Robot aspiradora cuarto", "micro",0,0,"",0,5, 7),
                    ("sat_bano_toallas", "sabado","sat_bano_bloque","Cambiar toallas",         "micro",0,0,"",0,3,12),
                ]
            )
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("sat_robot_aspiradora_y_toallas",
                 "Agrega 'Robot aspiradora sala' y 'Robot aspiradora cuarto' al Bloque 1, y 'Cambiar toallas' al Bloque 2 (Baño) del sábado.")
            )
            db.commit()

        db.executescript("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # ── VIAJES — Outfit planner + maleta ────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS viajes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT    NOT NULL,
            destino      TEXT    DEFAULT '',
            fecha_inicio TEXT    NOT NULL,
            fecha_fin    TEXT    NOT NULL,
            estado       TEXT    DEFAULT 'planificado',
            tipo_clima   TEXT    DEFAULT '',
            ocasion      TEXT    DEFAULT '',
            notas        TEXT    DEFAULT '',
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS viaje_dias (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            viaje_id    INTEGER NOT NULL,
            fecha       TEXT    NOT NULL,
            descripcion TEXT    DEFAULT '',
            FOREIGN KEY (viaje_id) REFERENCES viajes(id) ON DELETE CASCADE,
            UNIQUE (viaje_id, fecha)
        );
        CREATE TABLE IF NOT EXISTS viaje_dia_outfits (
            dia_id    INTEGER NOT NULL,
            outfit_id INTEGER NOT NULL,
            PRIMARY KEY (dia_id, outfit_id),
            FOREIGN KEY (dia_id)    REFERENCES viaje_dias(id) ON DELETE CASCADE,
            FOREIGN KEY (outfit_id) REFERENCES outfits(id)
        );
        CREATE TABLE IF NOT EXISTS viaje_maleta (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            viaje_id      INTEGER NOT NULL,
            nombre        TEXT    NOT NULL,
            categoria     TEXT    DEFAULT 'Varios',
            cantidad      INTEGER DEFAULT 1,
            packed_ida    INTEGER DEFAULT 0,
            packed_vuelta INTEGER DEFAULT 0,
            es_extra      INTEGER DEFAULT 0,
            item_id       INTEGER DEFAULT NULL,
            FOREIGN KEY (viaje_id) REFERENCES viajes(id) ON DELETE CASCADE
        );
        """)

        # ── VIAJES — unificación: "Presupuesto de viaje" (Oikonomia) tenía su
        # propia tabla est_viajes, separada de esta `viajes` (Hegemonikon,
        # outfits/maleta) — dos módulos de viaje independientes, cada uno con
        # su propio "crear viaje": un mismo viaje real había que darlo de
        # alta dos veces y ninguna pantalla se enteraba de la otra. Se
        # agrega la columna `presupuesto` que traía est_viajes para que
        # modules/finanzas/estados/routes.py lea/escriba esta misma tabla en
        # vez de la suya — un solo viaje, visible en ambas pantallas.
        # est_viajes se deja de usar (se conserva vacía, sin lectura/escritura,
        # por si algún entorno viejo aún la tiene creada — no se borra).
        try:
            v_cols = [r["name"] for r in db.execute("PRAGMA table_info(viajes)").fetchall()]
            if "presupuesto" not in v_cols:
                db.execute("ALTER TABLE viajes ADD COLUMN presupuesto REAL DEFAULT 0")
                db.commit()
        except Exception as e:
            print(f"[DB] viajes presupuesto migration warning: {e}")

        # ── ESTADOS DE CUENTA (SG Credit Card module) ────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS est_movimientos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha         TEXT    NOT NULL,
            fecha_cargo   TEXT,
            descripcion   TEXT    NOT NULL,
            monto         REAL    NOT NULL,
            banco         TEXT    NOT NULL DEFAULT '',
            periodo       TEXT,
            categoria     TEXT    NOT NULL DEFAULT '',
            subcategoria  TEXT    DEFAULT '',
            tipo          TEXT    NOT NULL DEFAULT 'GASTO',
            mi_parte      REAL    DEFAULT NULL,
            reembolso_cat TEXT    DEFAULT NULL,
            viaje_id      INTEGER DEFAULT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_est_mov_dedup
            ON est_movimientos (fecha, descripcion, monto);
        CREATE TABLE IF NOT EXISTS est_keywords (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword      TEXT    NOT NULL UNIQUE,
            categoria    TEXT    NOT NULL,
            subcategoria TEXT    NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS est_budgets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT    NOT NULL UNIQUE,
            nombre    TEXT,
            limite    REAL    NOT NULL,
            periodo   TEXT    NOT NULL DEFAULT 'monthly'
        );
        CREATE TABLE IF NOT EXISTS est_viajes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT    NOT NULL,
            destino      TEXT    DEFAULT '',
            fecha_inicio TEXT    NOT NULL,
            fecha_fin    TEXT    NOT NULL,
            presupuesto  REAL    DEFAULT 0,
            estado       TEXT    DEFAULT 'planificado',
            notas        TEXT    DEFAULT '',
            created_at   TEXT    NOT NULL
        );
        """)

        # Migrate existing est_movimientos tables that lack newer columns
        for col, definition in [
            ("mi_parte",      "REAL    DEFAULT NULL"),
            ("reembolso_cat", "TEXT    DEFAULT NULL"),
            ("viaje_id",      "INTEGER DEFAULT NULL"),
        ]:
            try:
                db.execute(f"ALTER TABLE est_movimientos ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists

        # Backfill: depósitos de nómina (BBVA) importados antes de que los
        # parsers reconocieran "PAGO DE NOMINA"/"FIBRA HOTELERA" como NOMINA,
        # o importados por una vía que no aplicó esa regla, quedaban con
        # categoria/tipo incorrectos. Los parsers bbva_debit.py y
        # bbva_libreton.py ya clasifican esto bien para importaciones nuevas
        # (categoria=NOMINA, tipo=INGRESO por el signo del monto).
        #
        # BUG REAL (2026-09, confirmado por el usuario con screenshot): a
        # diferencia de TODAS las demás migraciones de este archivo, este
        # bloque nunca estuvo protegido por migration_log -- corría en
        # CADA arranque de la app. Sin filtro de monto y forzando
        # tipo='INGRESO' a cualquier cosa que mencionara "FIBRA HOTELERA"
        # (un retiro en efectivo, un SPEI enviado, una compra de comida),
        # terminó marcando como NOMINA/INGRESO movimientos que claramente
        # no eran sueldo (ej. "RETIRO SIN TARJETA... FIBRA HOTELERA SC"
        # $500.00, "SPEI ENVIADO SANTANDER... FIBRA HOTELERA SC" $750.00).
        # Peor: como no tenía guardarraíl, si el usuario corregía una de
        # estas filas a mano, el siguiente arranque se la revertía sola.
        # Se congela con migration_log para que corra esta última vez
        # (mismo comportamiento que ya tenía) y nunca más -- deja de
        # pisar correcciones manuales futuras. Las filas ya afectadas por
        # las corridas anteriores (sin guardarraíl) se exponen para
        # revisión manual en /admin/audit-nomina-sospechosa (ver
        # estados/routes.py) en vez de adivinar su tipo/categoria correcta.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_backfill_legacy_frozen_2026_09'"
        ).fetchone():
            try:
                db.execute("""
                    UPDATE est_movimientos
                    SET categoria='NOMINA', tipo='INGRESO'
                    WHERE (UPPER(descripcion) LIKE '%PAGO DE NOMINA%'
                        OR UPPER(descripcion) LIKE '%FIBRA HOTELERA%'
                        OR descripcion LIKE '%4206466060%')
                      AND (categoria != 'NOMINA' OR tipo != 'INGRESO')
                """)
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_nomina_backfill_legacy_frozen_2026_09",
                     "Congela el backfill legacy de nómina (antes corría sin guardarraíl en "
                     "cada arranque, sin filtro de monto, forzando tipo=INGRESO a cualquier "
                     "cosa que mencionara FIBRA HOTELERA -- incluyendo retiros y SPEI "
                     "enviados que no eran sueldo, y revirtiendo correcciones manuales del "
                     "usuario en cada deploy). Corre esta última vez con el mismo "
                     "comportamiento de siempre y queda protegido por migration_log.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_nomina_backfill_legacy_frozen_2026_09 migration warning: {e}")

        # Backfill: "BBVA" (bare) siempre fue en realidad la tarjeta de
        # crédito (TDC) — BBVA_DEB (débito) ya estaba bien separado, pero el
        # nombre ambiguo "BBVA" vs "BBVA_DEB" no dejaba claro cuál era cuál.
        # Se renombra a BBVA_TDC en movimientos existentes; los parsers ya
        # quedaron actualizados para etiquetar así las importaciones nuevas.
        try:
            db.execute("UPDATE est_movimientos SET banco='BBVA_TDC' WHERE banco='BBVA'")
            db.commit()
        except Exception as e:
            print(f"[DB] est_movimientos BBVA_TDC rename warning: {e}")

        # Backfill: "BBVA_LIB" (formato Libretón) y "BBVA_DEB" (el otro
        # formato de débito) son la misma cuenta, solo cambia la plantilla
        # del PDF — se unifican bajo "BBVA_DEB". El valor "BBVA_LIB" no
        # estaba en las opciones del <select> de Banco del front (mostraba
        # la primera opción, "BBVA_TDC", en vez del banco real) y quedaba
        # fuera de las reglas de categorización que filtran por
        # banco='BBVA_DEB' (nómina, renta depto 807, etc.).
        try:
            db.execute("UPDATE est_movimientos SET banco='BBVA_DEB' WHERE banco='BBVA_LIB'")
            db.commit()
        except Exception as e:
            print(f"[DB] est_movimientos BBVA_LIB->BBVA_DEB merge warning: {e}")

        # Migración: idx_est_mov_dedup solo consideraba (fecha, descripcion)
        # — dos transacciones reales el mismo día con la misma descripción
        # pero distinto monto (ej. dos "PAGO CUENTA DE TERCERO ... TRANSF A
        # X" el mismo día) colisionaban en el índice único, y la segunda se
        # perdía en silencio vía INSERT OR IGNORE al importar (confirmado
        # auditando estados de cuenta reales contra sus propios totales
        # oficiales — ver /admin/audit-montos y /admin/recover-montos). Se
        # amplía el índice para incluir también el monto; los datos
        # existentes ya cumplen la restricción vieja (más estricta), así
        # que siempre cumplen la nueva (más laxa) — no puede fallar por
        # duplicados al recrearlo.
        try:
            idx = db.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_est_mov_dedup'"
            ).fetchone()
            if idx and idx["sql"] and "monto" not in idx["sql"]:
                db.execute("DROP INDEX idx_est_mov_dedup")
                db.execute(
                    "CREATE UNIQUE INDEX idx_est_mov_dedup ON est_movimientos (fecha, descripcion, monto)"
                )
                db.commit()
        except Exception as e:
            print(f"[DB] idx_est_mov_dedup widen migration warning: {e}")

        # Backfill: "CAFE/SOCIAL" y "CAFE/PAN" eran la misma categoría con dos
        # nombres — CAFE/SOCIAL es un código huérfano (ninguna regla de
        # config.py ni de est_keywords actual la genera) que se quedó en
        # movimientos viejos y aparecía sin mapeo en el front (ícono genérico,
        # nombre en mayúsculas sin formatear) en vez de fusionarse con
        # "Café & Pan". Se reclasifican movimientos y reglas de palabra clave
        # existentes; el budget de CAFE/SOCIAL se elimina si ya hay uno para
        # CAFE/PAN (categoria es UNIQUE en est_budgets) o si no, se renombra.
        try:
            db.execute("UPDATE est_movimientos SET categoria='CAFE/PAN' WHERE categoria='CAFE/SOCIAL'")
            db.execute("UPDATE est_keywords SET categoria='CAFE/PAN' WHERE categoria='CAFE/SOCIAL'")
            if db.execute("SELECT 1 FROM est_budgets WHERE categoria='CAFE/PAN'").fetchone():
                db.execute("DELETE FROM est_budgets WHERE categoria='CAFE/SOCIAL'")
            else:
                db.execute("UPDATE est_budgets SET categoria='CAFE/PAN' WHERE categoria='CAFE/SOCIAL'")
            db.commit()
        except Exception as e:
            print(f"[DB] est_movimientos CAFE/SOCIAL merge warning: {e}")

        # Backfill: limpiar duplicados reales colados antes del fix de dedup
        # en /api/upload (esa dedup usaba fecha+monto+banco+tipo; el mismo
        # movimiento real importado una vez desde PDF y otra desde CSV/Excel
        # de la misma cuenta podía quedar con banco distinto —p.ej. BBVA_DEB
        # vs BBVA_TDC— y coló ambas filas). Aquí se agrupa por fecha+monto+
        # tipo (ignorando banco) y, DENTRO de cada grupo, solo se considera
        # duplicado si la descripción normalizada (sin dígitos ni puntuación)
        # coincide — así no se borra por accidente una coincidencia real de
        # dos transacciones distintas el mismo día por el mismo monto. Se
        # conserva la fila con la descripción más larga (suele traer más
        # detalle, ej. la referencia numérica) y se borran las demás.
        #
        # Corre UNA SOLA VEZ (flag en app_settings). Antes se repetía en
        # cada arranque de la app y volvía a escanear TODA la tabla en cada
        # deploy — con la heurística de "misma fecha+monto+tipo y descripción
        # normalizada igual" eso puede confundir dos compras reales distintas
        # (ej. dos cafés de $65 en el mismo Starbucks el mismo día) con un
        # duplicado, y borrarla para siempre sin aviso. Al ser backfill de un
        # bug histórico ya corregido en /api/upload, con una corrida basta.
        try:
            already_ran = db.execute(
                "SELECT 1 FROM app_settings WHERE key='est_dedup_backfill_v1_done'"
            ).fetchone()
            if not already_ran:
                import re as _re

                def _norm_desc(s):
                    s = _re.sub(r'\d+', '', s or '')
                    s = _re.sub(r'[^A-ZÁÉÍÓÚÑ ]', ' ', s.upper())
                    return _re.sub(r'\s+', ' ', s).strip()

                rows = db.execute("""
                    SELECT id, fecha, monto, tipo, descripcion FROM est_movimientos
                    WHERE monto > 0
                """).fetchall()
                groups = {}
                for r in rows:
                    key = (r['fecha'], round(r['monto'], 2), r['tipo'])
                    groups.setdefault(key, []).append(dict(r))

                to_delete = []
                for key, items in groups.items():
                    if len(items) < 2:
                        continue
                    by_norm = {}
                    for it in items:
                        by_norm.setdefault(_norm_desc(it['descripcion']), []).append(it)
                    for norm, dupes in by_norm.items():
                        if len(dupes) < 2:
                            continue
                        dupes.sort(key=lambda it: (-len(it['descripcion']), it['id']))
                        to_delete.extend(it['id'] for it in dupes[1:])

                if to_delete:
                    ph = ','.join('?' * len(to_delete))
                    db.execute(f"DELETE FROM est_movimientos WHERE id IN ({ph})", to_delete)
                    print(f"[DB] est_movimientos duplicate cleanup: removed {len(to_delete)} rows")

                db.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('est_dedup_backfill_v1_done','1')"
                )
                db.commit()
        except Exception as e:
            print(f"[DB] est_movimientos duplicate cleanup warning: {e}")

        # ── ESTADOS DE CUENTA — Sprint 1 taxonomía (reembolsos, MSI, viajes,
        # préstamos, naturaleza del gasto) ──────────────────────────────────
        # Solo columnas/tablas nuevas (aditivo, no destructivo) + backfills
        # deterministas de casos NO ambiguos. Los casos ambiguos (ver auditoría
        # sobre transacciones_1.csv) se dejan tal cual o se marcan
        # PENDIENTE_REVISION — no se inventan clasificaciones.
        db.executescript("""
        CREATE TABLE IF NOT EXISTS est_categoria_naturaleza (
            categoria    TEXT NOT NULL,
            subcategoria TEXT NOT NULL DEFAULT '',
            naturaleza   TEXT NOT NULL,
            PRIMARY KEY (categoria, subcategoria)
        );
        CREATE TABLE IF NOT EXISTS est_prestamos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            contraparte      TEXT    NOT NULL,
            direccion        TEXT    NOT NULL DEFAULT 'OTORGADO',
            monto            REAL    NOT NULL,
            fecha            TEXT    NOT NULL,
            notas            TEXT    DEFAULT '',
            movimiento_id    INTEGER DEFAULT NULL,
            created_at       TEXT    NOT NULL,
            FOREIGN KEY (movimiento_id) REFERENCES est_movimientos(id)
        );
        -- Devoluciones de un préstamo (est_prestamos): cada movimiento de
        -- ingreso se liga a lo más a un préstamo; un préstamo puede tener
        -- varias. Ligada, la devolución no cuenta como ingreso: solo baja el
        -- pendiente (ver modules/finanzas/estados/prestamos.py).
        CREATE TABLE IF NOT EXISTS est_prestamo_devoluciones (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            prestamo_id   INTEGER NOT NULL,
            movimiento_id INTEGER NOT NULL UNIQUE,
            created_at    TEXT    NOT NULL,
            FOREIGN KEY (prestamo_id)   REFERENCES est_prestamos(id),
            FOREIGN KEY (movimiento_id) REFERENCES est_movimientos(id)
        );
        """)

        # «Perdido» es manual y guarda cuándo se marcó: ese mes el pendiente
        # cuenta como gasto en Familia y regalos (solo en la Radiografía).
        try:
            if "perdido_fecha" not in [r["name"] for r in db.execute("PRAGMA table_info(est_prestamos)").fetchall()]:
                db.execute("ALTER TABLE est_prestamos ADD COLUMN perdido_fecha TEXT DEFAULT NULL")
        except Exception as e:
            print(f"[DB] est_prestamos perdido_fecha migration warning: {e}")

        for col, definition in [
            ("estatus_reembolso", "TEXT    DEFAULT NULL"),
            ("fecha_reembolso",   "TEXT    DEFAULT NULL"),
            ("parcialidad_num",   "INTEGER DEFAULT NULL"),
            ("parcialidad_total", "INTEGER DEFAULT NULL"),
            ("compra_msi_id",     "TEXT    DEFAULT NULL"),
        ]:
            try:
                db.execute(f"ALTER TABLE est_movimientos ADD COLUMN {col} {definition}")
            except Exception:
                pass  # columna ya existe

        try:
            v_cols = [r["name"] for r in db.execute("PRAGMA table_info(viajes)").fetchall()]
            if "tipo_viaje" not in v_cols:
                db.execute("ALTER TABLE viajes ADD COLUMN tipo_viaje TEXT DEFAULT ''")
                db.commit()
        except Exception as e:
            print(f"[DB] viajes tipo_viaje migration warning: {e}")

        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_taxonomia_2026_09_sprint1'"
        ).fetchone():
            try:
                # 1) Normalizar duplicados de subcategoria por mayúsculas/typos
                #    confirmados en la auditoría (no cambia categoría, solo grafía).
                norm_fixes = [
                    ("GASOLINA/AUTO",  "seguro carro", "Seguro Carro"),
                    ("ENTRETENIMIENTO","cine",         "Cine"),
                    ("SUSCRIPCIONES",  "Telefonia",    "Telefonía"),
                    ("SALSA",          "tranporte",    "Transporte"),
                ]
                for cat, old, new in norm_fixes:
                    db.execute(
                        "UPDATE est_movimientos SET subcategoria=? WHERE categoria=? AND subcategoria=?",
                        (new, cat, old),
                    )

                # 2) EXPENSE: estatus_reembolso a partir de reembolso_cat, tal
                #    como se pidió — PAGADO si ya tiene reembolso_cat, si no
                #    PENDIENTE. No se toca tipo/categoria (ver nota más abajo).
                db.execute("""
                    UPDATE est_movimientos
                    SET estatus_reembolso='PAGADO'
                    WHERE categoria='EXPENSE' AND reembolso_cat IS NOT NULL AND reembolso_cat != ''
                """)
                db.execute("""
                    UPDATE est_movimientos
                    SET estatus_reembolso='PENDIENTE'
                    WHERE categoria='EXPENSE' AND (reembolso_cat IS NULL OR reembolso_cat = '')
                """)

                # 3) Movimientos que no son gasto real: pago de tarjeta de
                #    crédito (PAGO_TDC, siempre "PAGO TARJETA DE CREDITO" /
                #    "PAGO INTERBANCARIO TDC" / SPEI con "TDC" en la
                #    descripción — nunca ambiguo) y retiros de efectivo
                #    (descripción empieza con "RETIRO" — cajero o QR).
                #    NO se tocan TRANSFERENCIA, SPEI_ENVIADO, DEPOSITO ni
                #    PRESTAMOS/PAGO: la auditoría encontró que esas categorías
                #    mezclan gasto real (tacos, regalos, uniformes) con
                #    movimientos entre cuentas bajo la misma descripción
                #    genérica "PAGO CUENTA DE TERCERO BNET ..." — reclasificar
                #    en bloque ahí inventaría datos. Quedan para revisión manual.
                db.execute("""
                    UPDATE est_movimientos SET tipo='MOVIMIENTO_INTERNO'
                    WHERE categoria='PAGO_TDC' AND tipo='GASTO'
                """)
                db.execute("""
                    UPDATE est_movimientos SET tipo='MOVIMIENTO_INTERNO'
                    WHERE categoria='RETIRO' AND tipo='GASTO'
                      AND UPPER(descripcion) LIKE 'RETIRO%'
                """)

                # 4) Casos explícitamente ambiguos señalados por el usuario:
                #    se marcan PENDIENTE_REVISION en vez de adivinar.
                pendientes = [
                    ("2026-07-18", "601 2206260INVERSION GIO RETIRO SIN TARJETA QR ******7852", 5500.0),
                    ("2026-09-11", "PAGO CUENTA DE TERCERO BNET PRESTAMO", 4500.0),
                    ("2026-05-25", "SPEI ENVIADO NU MEXICO 638 0805260SALSA FUSION GIO", 2150.0),
                ]
                for fecha, desc, monto in pendientes:
                    db.execute(
                        """UPDATE est_movimientos SET subcategoria='PENDIENTE_REVISION'
                           WHERE fecha=? AND descripcion=? AND monto=?""",
                        (fecha, desc, monto),
                    )

                # 5) Catálogo naturaleza (FIJO/VARIABLE/IRREGULAR/EVITABLE) por
                #    (categoria, subcategoria) — primera propuesta a partir de
                #    la taxonomía que dio el usuario, mapeada sobre las
                #    categorías reales que ya existen en config.py (no se
                #    reemplaza el árbol de categorías existente). subcategoria
                #    '' = default para esa categoria cuando no hay fila más
                #    específica. Tabla nueva, no la lee ningún código todavía
                #    — no cambia ningún total actual. Pendiente de revisión
                #    del usuario antes de usarse en dashboards (Sprint 4).
                naturaleza_seed = [
                    ('APORTACION_RENTA', '', 'FIJO'),
                    ('APRENDIZAJE', '', 'VARIABLE'),
                    ('CAFE/PAN', '', 'VARIABLE'),
                    ('CASA/HOGAR', 'Alquiler', 'FIJO'),
                    ('CASA/HOGAR', 'Renta depto 807', 'FIJO'),
                    ('CASA/HOGAR', 'Renta depto 807 + deposito', 'FIJO'),
                    ('CASA/HOGAR', 'Agua', 'FIJO'),
                    ('CASA/HOGAR', 'Internet', 'FIJO'),
                    ('CASA/HOGAR', '', 'IRREGULAR'),
                    ('COMIDA/REST', '', 'VARIABLE'),
                    ('DEPORTE', '', 'VARIABLE'),
                    ('ENTRETENIMIENTO', '', 'VARIABLE'),
                    ('FINANZAS', 'Cargos bancarios', 'EVITABLE'),
                    ('GASOLINA/AUTO', 'Gasolina', 'VARIABLE'),
                    ('GASOLINA/AUTO', 'Seguro', 'FIJO'),
                    ('GASOLINA/AUTO', 'Seguro Carro', 'FIJO'),
                    ('GASOLINA/AUTO', 'Mantenimiento', 'IRREGULAR'),
                    ('GASOLINA/AUTO', 'Tenencia & Trámites', 'IRREGULAR'),
                    ('GASOLINA/AUTO', '', 'VARIABLE'),
                    ('GYM', '', 'FIJO'),
                    ('REGALO', '', 'IRREGULAR'),
                    ('ROPA', '', 'VARIABLE'),
                    ('SALSA', 'Clases', 'VARIABLE'),
                    ('SALSA', 'Evento', 'VARIABLE'),
                    ('SALSA', 'Congreso', 'VARIABLE'),
                    ('SALSA', 'Música', 'VARIABLE'),
                    ('SALSA', 'Café', 'VARIABLE'),
                    ('SALSA', '', 'VARIABLE'),
                    ('SALUD', '', 'VARIABLE'),
                    ('SERVICIOS', 'Internet', 'FIJO'),
                    ('SERVICIOS', 'Luz', 'FIJO'),
                    ('SERVICIOS', 'Saldo telefono', 'FIJO'),
                    ('SERVICIOS', '', 'FIJO'),
                    ('SUSCRIPCIONES', '', 'FIJO'),
                    ('TECH/DIGITAL', 'Accesorios', 'VARIABLE'),
                    ('TECH/DIGITAL', 'Software', 'FIJO'),
                    ('TECH/DIGITAL', '', 'VARIABLE'),
                    ('TRANSPORTE', '', 'VARIABLE'),
                    ('VIAJES/VUELOS', '', 'IRREGULAR'),
                    ('VIVERES/SUPER', '', 'VARIABLE'),
                ]
                db.executemany(
                    "INSERT OR IGNORE INTO est_categoria_naturaleza (categoria, subcategoria, naturaleza) VALUES (?,?,?)",
                    naturaleza_seed,
                )

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_taxonomia_2026_09_sprint1",
                     "Sprint 1 taxonomía finanzas: tablas est_categoria_naturaleza y est_prestamos, "
                     "columnas estatus_reembolso/fecha_reembolso/parcialidad_*/compra_msi_id en "
                     "est_movimientos, tipo_viaje en viajes, normalización de 4 subcategorias "
                     "duplicadas, backfill de estatus_reembolso en EXPENSE, reclasificación de "
                     "PAGO_TDC y RETIRO a tipo=MOVIMIENTO_INTERNO, y marcado PENDIENTE_REVISION "
                     "de 3 transacciones ambiguas señaladas por el usuario.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_taxonomia_2026_09_sprint1 migration warning: {e}")

        # ── ESTADOS DE CUENTA — Sprint 2 taxonomía (marcado de pendientes,
        # préstamos por descripción, viaje de mayo 2026) ───────────────────
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_taxonomia_2026_09_sprint2'"
        ).fetchone():
            try:
                # 1) TRANSFERENCIA/PRESTAMOS con "PRESTAMO" literal en la
                #    descripción -> tipo PRESTAMO. Se excluye a propósito la
                #    fila del 11-sep-2026 ($4500, "...BNET PRESTAMO") porque
                #    el usuario mismo señaló que no sabe si es préstamo
                #    otorgado o un pago -- ya quedó PENDIENTE_REVISION en el
                #    sprint 1 y no se le adivina la dirección aquí.
                db.execute("""
                    UPDATE est_movimientos SET tipo='PRESTAMO'
                    WHERE categoria IN ('TRANSFERENCIA','PRESTAMOS')
                      AND UPPER(descripcion) LIKE '%PRESTAMO%'
                      AND NOT (fecha='2026-09-11' AND monto=4500.0
                               AND descripcion='PAGO CUENTA DE TERCERO BNET PRESTAMO')
                """)

                # 2) DEPOSITO, SPEI_ENVIADO y el RETIRO que no encaja con su
                #    propia categoría -> PENDIENTE_REVISION, tal como se
                #    pidió (no se reclasifican a ciegas: mezclan gasto real,
                #    transferencias a personas y movimientos entre cuentas
                #    bajo la misma descripción genérica "PAGO CUENTA DE
                #    TERCERO BNET ..." / "SPEI ENVIADO ...").
                db.execute("""
                    UPDATE est_movimientos SET subcategoria='PENDIENTE_REVISION'
                    WHERE categoria IN ('DEPOSITO','SPEI_ENVIADO')
                """)
                db.execute("""
                    UPDATE est_movimientos SET subcategoria='PENDIENTE_REVISION'
                    WHERE categoria='RETIRO' AND tipo='GASTO'
                      AND UPPER(descripcion) NOT LIKE 'RETIRO%'
                """)

                # 3) Viaje de mayo 2026 encontrado al auditar SALSA: del
                #    24 al 31-may-2026 hay un cluster claro de autobús
                #    (PRIMERA PLUS), hotel (COURTYARD BY MARRIOTT) y
                #    comercios de CDMX (CASADETONO PATRIOTISMO, CAFEBRERIA
                #    PENDULO POL) -- coincide con lo que el usuario describió
                #    como "el viaje de mayo 2026" a agrupar. Se crea el viaje
                #    (reusa la tabla `viajes` compartida con el planner de
                #    maleta/outfits, ver Sprint 1) y se asignan por
                #    fecha+descripcion+monto exactos las 8 transacciones de
                #    esa ventana -- incluida la de $2150 "SALSA FUSION GIO"
                #    que ya quedó PENDIENTE_REVISION en el sprint 1 (el
                #    viaje y el estado de revisión son cosas independientes).
                trip = db.execute(
                    "SELECT id FROM viajes WHERE nombre='Salsa Fusion CDMX - Mayo 2026'"
                ).fetchone()
                if trip:
                    trip_id = trip['id']
                else:
                    cur = db.execute(
                        """INSERT INTO viajes
                           (nombre, destino, fecha_inicio, fecha_fin, presupuesto,
                            estado, tipo_viaje, notas, created_at)
                           VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
                        ("Salsa Fusion CDMX - Mayo 2026", "Ciudad de México",
                         "2026-05-24", "2026-05-31", 0, "planificado",
                         "OCIO_EVENTO",
                         "Creado automáticamente al agrupar los movimientos de "
                         "categoría SALSA del 24 al 31 de mayo de 2026 "
                         "(auditoría de taxonomía finanzas, sprint 2)."),
                    )
                    trip_id = cur.lastrowid

                viaje_mayo = [
                    ("2026-05-31", "PRIMERA PLUS", 1198.12),
                    ("2026-05-31", "DTM WEB CYBER", 1411.07),
                    ("2026-05-30", "COURTYARD BY MARRIOTT", 120.0),
                    ("2026-05-30", "CASADETONO PATRIOTISMO", 176.0),
                    ("2026-05-29", "CAFEBRERIA PENDULO POL", 335.5),
                    ("2026-05-26", "SPEI ENVIADO SANTANDER 014 0805260GIO DEM", 85.0),
                    ("2026-05-25", "SPEI ENVIADO NU MEXICO 638 0805260SALSA FUSION GIO", 2150.0),
                    ("2026-05-24", "ROLL BITS", 671.71),
                ]
                for fecha, desc, monto in viaje_mayo:
                    db.execute(
                        """UPDATE est_movimientos SET viaje_id=?
                           WHERE fecha=? AND descripcion=? AND monto=? AND categoria='SALSA'""",
                        (trip_id, fecha, desc, monto),
                    )

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_taxonomia_2026_09_sprint2",
                     "Sprint 2 taxonomía finanzas: TRANSFERENCIA/PRESTAMOS con 'PRESTAMO' en "
                     "descripción a tipo=PRESTAMO (excluyendo la fila ambigua ya marcada "
                     "PENDIENTE_REVISION); DEPOSITO, SPEI_ENVIADO y el RETIRO suelto marcados "
                     "PENDIENTE_REVISION; viaje 'Salsa Fusion CDMX - Mayo 2026' creado y 8 "
                     "transacciones de esa semana agrupadas bajo su viaje_id.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_taxonomia_2026_09_sprint2 migration warning: {e}")

        # ── ESTADOS DE CUENTA — Sprint 3 taxonomía (árbol de categorías nuevo:
        # Vivienda, Alimentación, Transporte, Salud, Cuidado personal, Ropa,
        # Digital, Deporte, Ocio, Salsa, Viajes, Familia y regalos, Proyectos,
        # Costos financieros, Aprendizaje) — reemplaza CASA/HOGAR, COMIDA/REST,
        # CAFE/PAN, VIVERES/SUPER, GASOLINA/AUTO, TECH/DIGITAL, SUSCRIPCIONES,
        # ENTRETENIMIENTO, GYM, REGALO, PUBLICIDAD, VIAJES/VUELOS y parte de
        # FINANZAS/SERVICIOS. Mapeo confirmado transacción por transacción con
        # el usuario vía CSV de dry-run antes de escribir esto. Corre sobre lo
        # que ya trae la DB en ese momento (después de sprint 1-2), guardado
        # por migration_log. config.py ya clasifica así las importaciones
        # nuevas -- esto solo pone al día lo que ya estaba en la DB.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_taxonomia_2026_09_sprint3'"
        ).fetchone():
            try:
                _S3_EXCLUIDAS = ('PAGO_TDC', 'RETIRO', 'DEPOSITO', 'SPEI_ENVIADO',
                                 'TRANSFERENCIA', 'PRESTAMOS', 'PAGO', 'OTROS', 'EXPENSE')

                _S3_FAST_FOOD_KW = ["BURGER KING", "CARLS JR", "KFC", "LITTLE CAESAR", "SUBWAY",
                                     "MCDONALDS", "WINGSTOP", "DAIRY QUEEN", "DOMINO",
                                     "HAMBURGUESAS AL CARBON", "BOSTONS PIZZA", "PIZZERIA", "WINGMAN"]
                _S3_DELIVERY_KW = ["RAPPI", "UBER EATS", "COM RAP", "STR RAPPI", "APP FOODS"]
                _S3_MOVIMIENTO_KW = ["RETIRO", "SPEI ENVIADO", "TRANSFERENCIA", "PRSTAMO"]

                def _s3_classify_comida(desc, existing_sub):
                    du = desc.upper()
                    if any(k in du for k in _S3_FAST_FOOD_KW): return "Fast Food"
                    if existing_sub == 'Delivery': return "Delivery"
                    if existing_sub == 'Restaurante': return "Restaurante"
                    if any(k in du for k in _S3_DELIVERY_KW): return "Delivery"
                    if any(k in du for k in _S3_MOVIMIENTO_KW): return ""
                    return "Restaurante"

                # (keywords, categoria_nueva, subcategoria_nueva) -- solo se aplica
                # cuando el mapeo base (_S3_M) dejo la subcategoria en blanco.
                _S3_KEYWORD_RULES = [
                    (["APPLE.COM/BILL"], "DIGITAL", "Suscripciones entretenimiento"),
                    (["AMAZON PRIME"], "DIGITAL", "Suscripciones entretenimiento"),
                    (["SPOTIFY"], "DIGITAL", "Suscripciones entretenimiento"),
                    (["RAILWAY"], "PROYECTOS", "Hosting"),
                    (["PROTON AG"], "DIGITAL", "Suscripciones IA/productividad"),
                    (["ACCES CONTROL EXPERT"], "DIGITAL", "Suscripciones entretenimiento"),
                    (["TRAINING INNOVATION"], "DEPORTE", "Gym"),
                    (["WEB TICKETS"], "OCIO", "Eventos y congresos"),
                    (["D LOCAL UDEMY", "UDEMY"], "APRENDIZAJE", "Cursos"),
                    (["AMAZON", "STRIPE AMAZON", "STR AMAZON", "MACSTORE"], "DIGITAL", "Accesorios tech"),
                    (["TEMU.COM", "DLO TDA TEMU", "DOLLARCITY", "MISC DOLLA", "SODIMAC"], "VIVIENDA", "Artículos del hogar"),
                    (["MERPAGO LAGARRAFERIA", "MERPAGO VIVOINTERIOR"], "VIVIENDA", "Artículos del hogar"),
                    (["INIMEX", "BPK MISC ALTA PROTGAMA", "ZTL ZAIRAAXZAYMENDOZAM", "COMERCIO MONARCA 01",
                      "MISC 5004 DOLLA"], "VIVIENDA", "Artículos del hogar"),
                    (["MERPAGO FLORERIAOLGA"], "FAMILIA_REGALOS", "Regalos"),
                    (["TRANSF A AURORA EL"], "FAMILIA_REGALOS", "Apoyo familiar"),
                    (["COLECTA"], "FAMILIA_REGALOS", "Colectas"),
                    (["BNET AYUDA"], "FAMILIA_REGALOS", "Apoyo familiar"),
                    (["PRESTAMO MOMMITA"], "REGALO", "PENDIENTE_REVISION"),
                    (["BNET REGA", "REGALITOS DI", "BNET REGALO", "LAS LENIS", "BNET MARTHA", "CP ISAYMON",
                      "GLADYS CORTES VEJAR", "MOMMITAS DAY", "PAGO FLORES GIOVAN", "CARPINTERIA ALBERT",
                      "COMIDA CUMPLE", "FLORES GIO", "A JUDITH A RETIRO", "BNET PASTEL",
                      "PAGO CUENTA DE TERCERO"], "FAMILIA_REGALOS", "Regalos"),
                    (["ARBITRAJE", "ARBITEAJE", "FUTBOL SOCCER", "CUENTA GIO", "SPEI ENVIADO BANAMEX",
                      "SPEI ENVIADO BANORTE"], "DEPORTE", "Fútbol"),
                    (["DECATHLON", "INNOVASPORT"], "DEPORTE", "Equipo"),
                    (["CINEPOLIS"], "OCIO", "Cine"),
                    (["RECORCHOLIS", "MAGNO BOLICHE", "LA MAESTRANZA"], "OCIO", "Salidas"),
                    (["MEDICAMENTOS", "HONORARIOS MEDICOS", "DRA ", "SALUD DIGNA"], "SALUD", "Consultas"),
                    (["FARMACIAS ARMO", "FARMACIASBE", "FARMACIA ISLA DORADA", "FARMACIA ARROCHA"], "SALUD", "Farmacia"),
                    (["VIVA AEROBUS", "VIVAAEROBUS", "SIMFIY.COM"], "VIAJES", "Transporte"),
                    (["AIRBNB"], "VIAJES", "Hospedaje"),
                    (["AFRICAM", "PARQUE SENDELA"], "VIAJES", "Otros"),
                    (["CENTRO TAB", "ISSET CENTRO", "ALEC S CAFE", "MERPAGO LACASITA", "MERCADOP MELIMAS"], "VIAJES", "Comida"),
                    (["IGLESIA"], "VIAJES", "Otros"),
                    (["BNET VIAJE", "BNET VACACIONES", "BNET VIAJESITO", "BNET VACA"], "VIAJES", "Otros"),
                    (["CLASE GIO", "CLASES GIO", "CLASEGIO", "CLASEGIOVANY", "TRANSF A DAVID YAE",
                      "SPEI ENVIADO BANREGIO", "SPEI ENVIADO SANTANDER", "SPEI ENVIADO AZTECA", "BUGALO",
                      "AME 970109GW0", "CMA 120606QG1", "CCE 090505CXA"], "SALSA", "Clases"),
                    (["TRANSF A JENNIFER"], "SALSA", "Social"),
                ]

                def _s3_keyword_rules(desc, cn, sn):
                    if cn and sn:
                        return None
                    du = desc.upper()
                    for kws, cn2, sn2 in _S3_KEYWORD_RULES:
                        if any(k in du for k in kws):
                            return cn2, sn2
                    return None

                _S3_M = {}
                def _s3_m(cv, sv, cn, sn):
                    _S3_M[(cv, sv)] = (cn, sn)
                _s3_m("APORTACION_RENTA", "Parte renta Nu Mexico", "VIVIENDA", "Renta")
                _s3_m("CASA/HOGAR", "", "VIVIENDA", "")
                _s3_m("CASA/HOGAR", "Agua", "VIVIENDA", "Agua")
                _s3_m("CASA/HOGAR", "Alquiler", "VIVIENDA", "")
                _s3_m("CASA/HOGAR", "Decoración", "VIVIENDA", "Artículos del hogar")
                _s3_m("CASA/HOGAR", "Envíos", "VIVIENDA", "Artículos del hogar")
                _s3_m("CASA/HOGAR", "Hogar general", "VIVIENDA", "Artículos del hogar")
                _s3_m("CASA/HOGAR", "Internet", "VIVIENDA", "Internet")
                _s3_m("CASA/HOGAR", "Mantenimiento", "VIVIENDA", "Artículos del hogar")
                _s3_m("CASA/HOGAR", "Muebles", "VIVIENDA", "Artículos del hogar")
                _s3_m("CASA/HOGAR", "Plantas", "VIVIENDA", "Artículos del hogar")
                _s3_m("CASA/HOGAR", "Renta depto 807", "VIVIENDA", "Renta")
                _s3_m("CASA/HOGAR", "Renta depto 807 + deposito", "VIVIENDA", "Renta")
                _s3_m("CASA/HOGAR", "Supermercado", "ALIMENTACION", "Súper")
                _s3_m("SERVICIOS", "Internet", "VIVIENDA", "Internet")
                _s3_m("SERVICIOS", "Luz", "VIVIENDA", "Luz")
                _s3_m("CAFE/PAN", "", "ALIMENTACION", "Café")
                _s3_m("CAFE/PAN", "Café", "ALIMENTACION", "Café")
                _s3_m("COMIDA/REST", "Café", "ALIMENTACION", "Café")
                _s3_m("VIVERES/SUPER", "", "ALIMENTACION", "Súper")
                _s3_m("VIVERES/SUPER", "Conveniencia", "ALIMENTACION", "Conveniencia")
                _s3_m("VIVERES/SUPER", "Supermercado", "ALIMENTACION", "Súper")
                _s3_m("GASOLINA/AUTO", "", "TRANSPORTE", "Gasolina")
                _s3_m("GASOLINA/AUTO", "Gasolina", "TRANSPORTE", "Gasolina")
                _s3_m("GASOLINA/AUTO", "Mantenimiento", "TRANSPORTE", "Mantenimiento auto")
                _s3_m("GASOLINA/AUTO", "Seguro", "TRANSPORTE", "Seguro auto")
                _s3_m("GASOLINA/AUTO", "Seguro Carro", "TRANSPORTE", "Seguro auto")
                _s3_m("GASOLINA/AUTO", "Tenencia & Trámites", "TRANSPORTE", "Mantenimiento auto")
                _s3_m("TRANSPORTE", "", "TRANSPORTE", "Taxi/apps")
                _s3_m("TRANSPORTE", "Aeropuerto", "TRANSPORTE", "Taxi/apps")
                _s3_m("TRANSPORTE", "Autobús", "TRANSPORTE", "Taxi/apps")
                _s3_m("TRANSPORTE", "Taxi", "TRANSPORTE", "Taxi/apps")
                _s3_m("SALUD", "", "SALUD", "")
                _s3_m("SALUD", "Farmacia", "SALUD", "Farmacia")
                _s3_m("SALUD", "Laboratorio", "SALUD", "Estudios")
                _s3_m("SALUD", "Médico", "SALUD", "Consultas")
                _s3_m("SALUD", "Corte de cabello", "CUIDADO_PERSONAL", "Barbería")
                _s3_m("ROPA", "", "ROPA", "Ropa")
                _s3_m("ROPA", "Calzado", "ROPA", "Calzado")
                _s3_m("ROPA", "Ropa", "ROPA", "Ropa")
                _s3_m("ROPA", "Ropa deportiva", "ROPA", "Ropa deportiva")
                _s3_m("SERVICIOS", "Saldo telefono", "DIGITAL", "Celular")
                _s3_m("SUSCRIPCIONES", "", "DIGITAL", "")
                _s3_m("SUSCRIPCIONES", "Digital", "DIGITAL", "Suscripciones entretenimiento")
                _s3_m("SUSCRIPCIONES", "Diseño", "DIGITAL", "Suscripciones IA/productividad")
                _s3_m("SUSCRIPCIONES", "Gym", "DEPORTE", "Gym")
                _s3_m("SUSCRIPCIONES", "Internet/TV", "DIGITAL", "Suscripciones entretenimiento")
                _s3_m("SUSCRIPCIONES", "Música", "DIGITAL", "Suscripciones entretenimiento")
                _s3_m("SUSCRIPCIONES", "Productividad", "DIGITAL", "Suscripciones IA/productividad")
                _s3_m("SUSCRIPCIONES", "Tech", "PROYECTOS", "Hosting")
                _s3_m("SUSCRIPCIONES", "Telefonía", "DIGITAL", "Celular")
                _s3_m("TECH/DIGITAL", "", "DIGITAL", "")
                _s3_m("TECH/DIGITAL", "Accesorios", "DIGITAL", "Accesorios tech")
                _s3_m("TECH/DIGITAL", "Deudas MSI", "TECH/DIGITAL", "Deudas MSI")
                _s3_m("TECH/DIGITAL", "Software", "DIGITAL", "Suscripciones IA/productividad")
                _s3_m("DEPORTE", "", "DEPORTE", "")
                _s3_m("DEPORTE", "Uniforme Fut", "DEPORTE", "Equipo")
                _s3_m("GYM", "Gym", "DEPORTE", "Gym")
                _s3_m("ENTRETENIMIENTO", "", "OCIO", "")
                _s3_m("ENTRETENIMIENTO", "Bar & Antro", "OCIO", "Salidas")
                _s3_m("ENTRETENIMIENTO", "Cine", "OCIO", "Cine")
                _s3_m("ENTRETENIMIENTO", "Cultura", "OCIO", "Salidas")
                _s3_m("ENTRETENIMIENTO", "Eventos", "OCIO", "Eventos y congresos")
                _s3_m("ENTRETENIMIENTO", "Golf", "OCIO", "Salidas")
                _s3_m("ENTRETENIMIENTO", "Salidas", "OCIO", "Salidas")
                _s3_m("SALSA", "", "SALSA", "")
                _s3_m("SALSA", "Clases", "SALSA", "Clases")
                _s3_m("SALSA", "Congreso", "SALSA", "Congreso")
                _s3_m("SALSA", "Evento", "SALSA", "Social")
                _s3_m("SALSA", "Música", "SALSA", "")
                _s3_m("SALSA", "Autobús", "VIAJES", "Transporte")
                _s3_m("SALSA", "Café", "VIAJES", "Comida")
                _s3_m("SALSA", "Transporte", "VIAJES", "Transporte")
                _s3_m("SALSA", "Parte renta Nu Mexico", "SALSA", "Congreso")
                _s3_m("SALSA", "PENDIENTE_REVISION", "SALSA", "PENDIENTE_REVISION")
                _s3_m("VIAJES/VUELOS", "", "VIAJES", "Otros")
                _s3_m("VIAJES/VUELOS", "Hogar general", "VIAJES", "Otros")
                _s3_m("VIAJES/VUELOS", "Hotel", "VIAJES", "Hospedaje")
                _s3_m("VIAJES/VUELOS", "Restaurante", "VIAJES", "Comida")
                _s3_m("VIAJES/VUELOS", "Salidas", "VIAJES", "Otros")
                _s3_m("VIAJES/VUELOS", "Supermercado", "VIAJES", "Comida")
                _s3_m("VIAJES/VUELOS", "Vuelos", "VIAJES", "Transporte")
                _s3_m("VIAJES/VUELOS", "telefono", "VIAJES", "Otros")
                _s3_m("REGALO", "", "FAMILIA_REGALOS", "")
                _s3_m("REGALO", "Anillo a cornelius", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "anillo", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "Boda", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "Cumpleaños", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "Decoración", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "Hogar general", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "Libros", "FAMILIA_REGALOS", "Regalos")
                _s3_m("REGALO", "PENDIENTE_REVISION", "REGALO", "PENDIENTE_REVISION")
                _s3_m("PUBLICIDAD", "", "PROYECTOS", "Publicidad")
                _s3_m("PUBLICIDAD", "Meta Ads", "PROYECTOS", "Publicidad")
                _s3_m("PUBLICIDAD", "Reclutamiento", "PROYECTOS", "Reclutamiento")
                _s3_m("FINANZAS", "Cargos bancarios", "COSTOS_FINANCIEROS", "Comisiones")
                _s3_m("FINANZAS", "Retiro efectivo", "FINANZAS", "")
                _s3_m("FINANZAS", "Transferencia", "FINANZAS", "")
                _s3_m("APRENDIZAJE", "", "APRENDIZAJE", "")
                _s3_m("APRENDIZAJE", "Cursos online", "APRENDIZAJE", "Cursos")
                _s3_m("APRENDIZAJE", "Idiomas", "APRENDIZAJE", "Cursos")
                _s3_m("APRENDIZAJE", "Papelería", "APRENDIZAJE", "Papelería")

                # Overrides puntuales por transaccion exacta (fecha, descripcion,
                # monto), confirmados por el usuario en el chat -- ganan sobre
                # todo lo demas.
                _S3_OVERRIDES = {
                    ("2024-03-19", "AQUAMATIC PABLO NERUDA (2)", 41.0):  ("VIVIENDA", "Lavandería", "GASTO"),
                    ("2024-03-19", "AQUAMATIC PABLO NERUDA", 83.0):      ("VIVIENDA", "Lavandería", "GASTO"),
                    ("2024-07-14", "BBV CAJERO E281", 300.0):            ("ALIMENTACION", "Restaurante", "GASTO"),
                    ("2023-10-07", "BBV CAJERO A019", 1000.0):           ("VIVIENDA", "Mudanza", "GASTO"),
                    ("2025-12-19", "PAGOS INTERBANCARIOS. [-|", 1800.0): ("PAGO_TDC", "", "MOVIMIENTO_INTERNO"),
                    ("2025-10-01", "PAGOS INTERBANCARIOS [-|", 1200.0):  ("PAGO_TDC", "", "MOVIMIENTO_INTERNO"),
                    ("2025-09-01", "PAGOS INTERBANCARIOS [|", 1400.0):   ("PAGO_TDC", "", "MOVIMIENTO_INTERNO"),
                    ("2024-12-29", "SERVIFACIL GORDO Y SAN", 300.0):     ("TRANSPORTE", "Gasolina", "GASTO"),
                    ("2022-04-04", "SERVIFACIL VILLA FRONT", 100.0):     ("TRANSPORTE", "Gasolina", "GASTO"),
                    ("2026-05-25", "SPEI ENVIADO NU MEXICO 638 0805260SALSA FUSION GIO", 2150.0): ("SALSA", "Congreso", "GASTO"),
                    ("2026-05-15", "SPEI ENVIADO NU MEXICO 638 1404260FUSION GIO", 1734.0):        ("SALSA", "Congreso", "GASTO"),
                    ("2026-05-24", "ROLL BITS", 671.71):                              ("VIAJES", "Transporte", "GASTO"),
                    ("2025-06-18", "PAGO CUENTA DE TERCERO BNET WEN", 415.0):         ("SALSA", "Congreso", "GASTO"),
                    ("2026-05-30", "CASADETONO PATRIOTISMO", 176.0):                  ("VIAJES", "Comida", "GASTO"),
                    ("2026-05-30", "COURTYARD BY MARRIOTT", 120.0):                   ("SALSA", "Social", "GASTO"),
                }
                # Las filas de "comida pagada en efectivo" (retiro/SPEI, ya
                # etiquetadas COMIDA/REST) van a Restaurante por default --
                # confirmado con el usuario: sabemos que fue comida, no el lugar.
                _S3_ALIMENTACION_EFECTIVO_DEFAULT = "Restaurante"

                _s3_rows = db.execute(
                    "SELECT id, fecha, descripcion, monto, categoria, subcategoria FROM est_movimientos"
                ).fetchall()

                n_updated = 0
                for r in _s3_rows:
                    key = (r['fecha'], r['descripcion'], float(r['monto']))
                    cat, sub = (r['categoria'] or '').strip(), (r['subcategoria'] or '').strip()

                    if key in _S3_OVERRIDES:
                        new_cat, new_sub, new_tipo = _S3_OVERRIDES[key]
                        db.execute(
                            "UPDATE est_movimientos SET categoria=?, subcategoria=?, tipo=? WHERE id=?",
                            (new_cat, new_sub, new_tipo, r['id']),
                        )
                        n_updated += 1
                        continue

                    if cat == 'COMIDA/REST' and sub != 'Café':
                        new_sub = _s3_classify_comida(r['descripcion'], sub)
                        if new_sub == '':
                            new_sub = _S3_ALIMENTACION_EFECTIVO_DEFAULT
                        db.execute(
                            "UPDATE est_movimientos SET categoria='ALIMENTACION', subcategoria=? WHERE id=?",
                            (new_sub, r['id']),
                        )
                        n_updated += 1
                        continue

                    if cat in _S3_EXCLUIDAS:
                        continue

                    new_cat, new_sub = _S3_M.get((cat, sub), (cat, sub))
                    kw = _s3_keyword_rules(r['descripcion'], new_cat, new_sub)
                    if kw is not None:
                        new_cat, new_sub = kw
                    if (new_cat, new_sub) != (cat, sub):
                        db.execute(
                            "UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?",
                            (new_cat, new_sub, r['id']),
                        )
                        n_updated += 1

                # Re-sembrar el catalogo de naturaleza con los codigos nuevos --
                # el de sprint 1 usaba los codigos viejos (CASA/HOGAR, COMIDA/REST,
                # etc.), ya no aplican a la taxonomia actual.
                db.execute("DELETE FROM est_categoria_naturaleza")
                naturaleza_seed_v2 = [
                    ('VIVIENDA', 'Renta', 'FIJO'),
                    ('VIVIENDA', 'Luz', 'FIJO'),
                    ('VIVIENDA', 'Agua', 'FIJO'),
                    ('VIVIENDA', 'Internet', 'FIJO'),
                    ('VIVIENDA', 'Artículos del hogar', 'IRREGULAR'),
                    ('VIVIENDA', 'Lavandería', 'VARIABLE'),
                    ('VIVIENDA', 'Mudanza', 'IRREGULAR'),
                    ('VIVIENDA', '', 'FIJO'),
                    ('ALIMENTACION', 'Súper', 'VARIABLE'),
                    ('ALIMENTACION', 'Conveniencia', 'VARIABLE'),
                    ('ALIMENTACION', 'Café', 'VARIABLE'),
                    ('ALIMENTACION', 'Pan', 'VARIABLE'),
                    ('ALIMENTACION', 'Delivery', 'VARIABLE'),
                    ('ALIMENTACION', 'Restaurante', 'VARIABLE'),
                    ('ALIMENTACION', 'Fast Food', 'VARIABLE'),
                    ('TRANSPORTE', 'Gasolina', 'VARIABLE'),
                    ('TRANSPORTE', 'Seguro auto', 'FIJO'),
                    ('TRANSPORTE', 'Mantenimiento auto', 'IRREGULAR'),
                    ('TRANSPORTE', 'Taxi/apps', 'VARIABLE'),
                    ('SALUD', 'Consultas', 'VARIABLE'),
                    ('SALUD', 'Farmacia', 'VARIABLE'),
                    ('SALUD', 'Estudios', 'VARIABLE'),
                    ('SALUD', '', 'VARIABLE'),
                    ('CUIDADO_PERSONAL', 'Barbería', 'VARIABLE'),
                    ('CUIDADO_PERSONAL', 'Higiene', 'VARIABLE'),
                    ('ROPA', 'Ropa', 'VARIABLE'),
                    ('ROPA', 'Ropa deportiva', 'VARIABLE'),
                    ('ROPA', 'Calzado', 'VARIABLE'),
                    ('DIGITAL', 'Celular', 'FIJO'),
                    ('DIGITAL', 'Suscripciones IA/productividad', 'FIJO'),
                    ('DIGITAL', 'Suscripciones entretenimiento', 'FIJO'),
                    ('DIGITAL', 'Accesorios tech', 'VARIABLE'),
                    ('DIGITAL', '', 'FIJO'),
                    ('DEPORTE', 'Gym', 'FIJO'),
                    ('DEPORTE', 'Fútbol', 'VARIABLE'),
                    ('DEPORTE', 'Equipo', 'VARIABLE'),
                    ('OCIO', 'Eventos y congresos', 'VARIABLE'),
                    ('OCIO', 'Cine', 'VARIABLE'),
                    ('OCIO', 'Salidas', 'VARIABLE'),
                    ('OCIO', 'Videojuegos', 'VARIABLE'),
                    ('OCIO', '', 'VARIABLE'),
                    ('SALSA', 'Clases', 'VARIABLE'),
                    ('SALSA', 'Congreso', 'VARIABLE'),
                    ('SALSA', 'Social', 'VARIABLE'),
                    ('SALSA', 'Taller', 'VARIABLE'),
                    ('SALSA', 'App', 'VARIABLE'),
                    ('SALSA', '', 'VARIABLE'),
                    ('FAMILIA_REGALOS', 'Regalos', 'IRREGULAR'),
                    ('FAMILIA_REGALOS', 'Apoyo familiar', 'IRREGULAR'),
                    ('FAMILIA_REGALOS', 'Colectas', 'IRREGULAR'),
                    ('FAMILIA_REGALOS', '', 'IRREGULAR'),
                    ('VIAJES', 'Transporte', 'IRREGULAR'),
                    ('VIAJES', 'Hospedaje', 'IRREGULAR'),
                    ('VIAJES', 'Comida', 'IRREGULAR'),
                    ('VIAJES', 'Otros', 'IRREGULAR'),
                    ('PROYECTOS', 'Publicidad', 'VARIABLE'),
                    ('PROYECTOS', 'Hosting', 'VARIABLE'),
                    ('PROYECTOS', 'Software', 'VARIABLE'),
                    ('PROYECTOS', 'Reclutamiento', 'VARIABLE'),
                    ('COSTOS_FINANCIEROS', 'Intereses', 'EVITABLE'),
                    ('COSTOS_FINANCIEROS', 'Comisiones', 'EVITABLE'),
                    ('COSTOS_FINANCIEROS', 'Penalizaciones', 'EVITABLE'),
                    ('APRENDIZAJE', 'Cursos', 'VARIABLE'),
                    ('APRENDIZAJE', 'Libros', 'VARIABLE'),
                    ('APRENDIZAJE', 'Papelería', 'VARIABLE'),
                    ('APRENDIZAJE', '', 'VARIABLE'),
                ]
                db.executemany(
                    "INSERT OR IGNORE INTO est_categoria_naturaleza (categoria, subcategoria, naturaleza) VALUES (?,?,?)",
                    naturaleza_seed_v2,
                )

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_taxonomia_2026_09_sprint3",
                     f"Sprint 3 taxonomía finanzas: nuevo árbol de categorías (Vivienda, "
                     f"Alimentación, Transporte, Salud, Cuidado personal, Ropa, Digital, "
                     f"Deporte, Ocio, Salsa, Viajes, Familia y regalos, Proyectos, Costos "
                     f"financieros, Aprendizaje) reemplaza a CASA/HOGAR, COMIDA/REST, "
                     f"CAFE/PAN, VIVERES/SUPER, GASOLINA/AUTO, TECH/DIGITAL, SUSCRIPCIONES, "
                     f"ENTRETENIMIENTO, GYM, REGALO, PUBLICIDAD, VIAJES/VUELOS y parte de "
                     f"FINANZAS/SERVICIOS. {n_updated} filas reclasificadas. Mapeo confirmado "
                     f"con el usuario transacción por transacción vía CSV de dry-run. "
                     f"est_categoria_naturaleza resembrada con los códigos nuevos.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_taxonomia_2026_09_sprint3 migration warning: {e}")

        # ── ESTADOS DE CUENTA — revivir CAFE/PAN como categoria propia (a
        #    petición explícita del usuario: el Sprint 3 de taxonomía la había
        #    fusionado dentro de ALIMENTACION/Café y ALIMENTACION/Pan; café y
        #    pan son un "deseo" distinto de comprar despensa o comer fuera) ──
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_cafe_pan_categoria_propia_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='CAFE/PAN'
                    WHERE categoria='ALIMENTACION' AND subcategoria IN ('Café', 'Pan')
                """)
                n_cafe_pan = cur.rowcount

                db.executemany(
                    "INSERT OR IGNORE INTO est_categoria_naturaleza (categoria, subcategoria, naturaleza) VALUES (?,?,?)",
                    [
                        ('CAFE/PAN', 'Café', 'VARIABLE'),
                        ('CAFE/PAN', 'Pan', 'VARIABLE'),
                        ('CAFE/PAN', '', 'VARIABLE'),
                    ],
                )

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_cafe_pan_categoria_propia_2026_09",
                     f"CAFE/PAN revivida como categoria propia a petición explícita del "
                     f"usuario. {n_cafe_pan} filas reclasificadas de "
                     f"categoria='ALIMENTACION' (subcategoria Café/Pan) de vuelta a "
                     f"categoria='CAFE/PAN' -- se conserva la subcategoria Café/Pan tal "
                     f"cual. est_categoria_naturaleza sembrada con los códigos CAFE/PAN "
                     f"(VARIABLE, igual que en la semilla original pre-Sprint-3).")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_cafe_pan_categoria_propia_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — Qin/Tortas planchadas/Gorditas a Fast Food (a
        #    petición explícita del usuario) ─────────────────────────────────
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_fast_food_qin_tortas_gorditas_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Fast Food'
                    WHERE categoria='ALIMENTACION' AND subcategoria='Restaurante'
                      AND (UPPER(descripcion) LIKE '%QIN%'
                           OR UPPER(descripcion) LIKE '%TOR PLANCHADAS%'
                           OR UPPER(descripcion) LIKE '%GORDITAS%')
                """)
                n_fast_food = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_fast_food_qin_tortas_gorditas_2026_09",
                     f"Reclasificación a petición del usuario: transacciones de Qin "
                     f"(comida china), tortas planchadas y gorditas que estaban en "
                     f"ALIMENTACION/Restaurante pasan a ALIMENTACION/Fast Food. "
                     f"{n_fast_food} filas actualizadas. config.py también actualizado "
                     f"(REST QIN, TOR PLANCHADAS, GORDITAS) para que las próximas "
                     f"importaciones clasifiquen ahí directamente.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_fast_food_qin_tortas_gorditas_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — EXPENSE es una categoria plana, sin
        #    subcategoria (a petición explícita del usuario: "va todo junto
        #    en uno solo"). Se habían acumulado subcategorias inconsistentes
        #    (de edición manual y de reglas de keyword personalizadas) — se
        #    limpian aquí, y create_transaction/update_transaction/
        #    create_keyword/apply_all_keywords/el aplicador de keywords al
        #    importar (routes.py) ahora fuerzan subcategoria='' cada vez que
        #    categoria='EXPENSE', para que no se vuelva a acumular basura ─
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_expense_sin_subcategoria_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria=''
                    WHERE categoria='EXPENSE' AND subcategoria IS NOT NULL AND subcategoria != ''
                """)
                n_expense_limpiadas = cur.rowcount

                cur2 = db.execute("""
                    UPDATE est_keywords SET subcategoria=''
                    WHERE categoria='EXPENSE' AND subcategoria IS NOT NULL AND subcategoria != ''
                """)
                n_keywords_limpiadas = cur2.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_expense_sin_subcategoria_2026_09",
                     f"EXPENSE es una categoria plana, sin subcategoria (a petición del "
                     f"usuario). {n_expense_limpiadas} movimientos y "
                     f"{n_keywords_limpiadas} reglas de keyword con categoria='EXPENSE' "
                     f"tenían subcategoria y se limpiaron. routes.py ahora fuerza "
                     f"subcategoria='' en cada punto de escritura cuando "
                     f"categoria='EXPENSE'.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_expense_sin_subcategoria_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — limpieza de subcategorias del lado de ingreso
        #    (a petición explícita del usuario) ───────────────────────────────
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_ingreso_subcategorias_2026_09'"
        ).fetchone():
            try:
                # 1) Un ingreso (pago de seguro) había quedado con
                #    categoria=TRANSPORTE, subcategoria='Gasolina' -- se
                #    reclasifica a la subcategoria que ya existe para esto
                #    ('Seguro auto'), sin tocar los GASTO reales de gasolina.
                cur1 = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Seguro auto'
                    WHERE tipo='INGRESO' AND categoria='TRANSPORTE' AND subcategoria='Gasolina'
                """)
                n_seguro = cur1.rowcount

                # 2) Ingresos de VIVIENDA/Renta (alguien aportando para la
                #    renta) se distinguen del GASTO real de renta -- solo se
                #    toca el lado INGRESO.
                cur2 = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Aportación renta'
                    WHERE tipo='INGRESO' AND categoria='VIVIENDA' AND subcategoria='Renta'
                """)
                n_aportacion = cur2.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_ingreso_subcategorias_2026_09",
                     f"Limpieza de subcategorias del lado de ingreso a petición del "
                     f"usuario: {n_seguro} fila(s) INGRESO de TRANSPORTE/Gasolina -> "
                     f"TRANSPORTE/Seguro auto (era un pago de seguro, no gasolina real). "
                     f"{n_aportacion} fila(s) INGRESO de VIVIENDA/Renta -> VIVIENDA/"
                     f"Aportación renta (aporte de alguien más, no la renta que paga el "
                     f"usuario). SUBCATEGORIAS también gana NOMINA:[Pago nominal, Bono] "
                     f"y VIVIENDA gana 'Aportación renta' como opción -- sin tocar "
                     f"transacciones existentes de nómina/bono, se pidió solo agregar "
                     f"las opciones.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_ingreso_subcategorias_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — nómina auto-detectada por fecha+monto (a
        #    petición explícita del usuario) ─────────────────────────────────
        # Un ingreso que menciona FIBRA HOTELERA/NOMINA, cae en los primeros
        # (1-3) o últimos (29-31) días del mes -- cuando normalmente paga la
        # nómina -- y su monto está entre $10,000 y $12,000 (rango típico de
        # la quincena/mensualidad), se marca categoria=NOMINA,
        # subcategoria='Pago nominal'. La misma regla corre también en cada
        # import futuro (ver _auto_clasificar_nomina en estados/routes.py).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Pago nominal'
                    WHERE tipo='INGRESO'
                      AND (UPPER(descripcion) LIKE '%FIBRA HOTELERA%'
                           OR UPPER(descripcion) LIKE '%NOMINA%'
                           OR UPPER(descripcion) LIKE '%NÓMINA%')
                      AND ((CAST(strftime('%d', fecha) AS INTEGER) BETWEEN 1 AND 3)
                           OR (CAST(strftime('%d', fecha) AS INTEGER) BETWEEN 29 AND 31))
                      AND monto BETWEEN 10000 AND 12000
                """)
                n_nomina = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_nomina_pago_nominal_2026_09",
                     f"Auto-clasificación de nómina a petición del usuario: ingresos que "
                     f"mencionan FIBRA HOTELERA/NOMINA, caen en los días 1-3 o 29-31 del "
                     f"mes, y su monto está entre $10,000 y $12,000 -> "
                     f"categoria=NOMINA, subcategoria='Pago nominal'. "
                     f"{n_nomina} filas reclasificadas. La misma regla corre en cada "
                     f"import futuro (_auto_clasificar_nomina en estados/routes.py).")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_nomina_pago_nominal_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — nómina auto-detectada, v2 sin filtro de
        #    fecha (a petición explícita del usuario) ────────────────────────
        # La v1 (finanzas_nomina_pago_nominal_2026_09) exigía también que la
        # fecha cayera en los días 1-3/29-31 del mes. Un caso real confirmado
        # (PAGO DE NOMINA FIBRA HOTELERA SC, $10,422.25, 02/13/2026) llegó el
        # día 13 -- el banco no siempre paga en fechas fijas -- así que se
        # quita esa condición y se deja solo texto+monto. Se corre como
        # migración nueva (no se reescribe la v1) porque la v1 pudo haber
        # corrido ya en producción antes de este ajuste.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v2_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Pago nominal'
                    WHERE tipo='INGRESO'
                      AND (UPPER(descripcion) LIKE '%FIBRA HOTELERA%'
                           OR UPPER(descripcion) LIKE '%NOMINA%'
                           OR UPPER(descripcion) LIKE '%NÓMINA%')
                      AND monto BETWEEN 10000 AND 12000
                """)
                n_nomina_v2 = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_nomina_pago_nominal_v2_2026_09",
                     f"Ajuste a la regla de auto-clasificación de nómina: se quita la "
                     f"condición de día del mes (1-3/29-31) de la v1 -- el banco no "
                     f"siempre paga en fechas fijas, y un caso real (02/13/2026) no "
                     f"calzaba con esa ventana. Ahora solo se exige texto (FIBRA "
                     f"HOTELERA/NOMINA) + monto ($10,000-$12,000). "
                     f"{n_nomina_v2} filas adicionales reclasificadas a "
                     f"categoria=NOMINA, subcategoria='Pago nominal'.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_nomina_pago_nominal_v2_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — nómina auto-detectada, v3 con rango de monto
        #    ampliado para cubrir 2025 (a petición explícita del usuario) ──────
        # v1/v2 usaban el rango $10,000-$12,000, que calza con el sueldo de
        # 2026. El sueldo de 2025 (antes de un aumento) caía entre $9,000 y
        # $11,000 -- fuera del piso de $10,000 -- así que esos ingresos de
        # nómina de 2025 nunca se reclasificaron aunque el texto (FIBRA
        # HOTELERA/NOMINA) sí calzaba. Se amplía el rango a $9,000-$12,000
        # para cubrir ambos años con una sola regla. Se corre como migración
        # nueva (no se reescribe v1/v2) porque esas ya pudieron haber corrido
        # en producción antes de este ajuste.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_pago_nominal_v3_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Pago nominal'
                    WHERE tipo='INGRESO'
                      AND (UPPER(descripcion) LIKE '%FIBRA HOTELERA%'
                           OR UPPER(descripcion) LIKE '%NOMINA%'
                           OR UPPER(descripcion) LIKE '%NÓMINA%')
                      AND monto BETWEEN 9000 AND 12000
                """)
                n_nomina_v3 = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_nomina_pago_nominal_v3_2026_09",
                     f"Ajuste a la regla de auto-clasificación de nómina: se amplía el "
                     f"rango de monto de $10,000-$12,000 (v1/v2) a $9,000-$12,000 para "
                     f"cubrir el sueldo de 2025 (antes de un aumento), que caía entre "
                     f"$9,000 y $11,000. "
                     f"{n_nomina_v3} filas adicionales reclasificadas a "
                     f"categoria=NOMINA, subcategoria='Pago nominal'.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_nomina_pago_nominal_v3_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — EXPENSE mal usado en ingresos (a petición
        #    explícita del usuario) ──────────────────────────────────────────
        # EXPENSE es exclusivamente para el lado del GASTO (algo que pagas y
        # te van a reembolsar -- ver estatus_reembolso/_sugerir_reembolsos).
        # El usuario confirmó que por costumbre le pone EXPENSE también al
        # depósito que le regresan; como EXPENSE nunca lleva subcategoria
        # (_normalize_subcategoria en estados/routes.py), ese ingreso le
        # quedaba "sin categoría". Se reclasifica cualquier movimiento
        # tipo=INGRESO con categoria=EXPENSE existente a FINANZAS/
        # Reembolsable -- la categoría real pensada para un reembolso
        # recibido. La misma corrección corre también hacia adelante en
        # create_transaction, update_transaction, apply_all_keywords y el
        # import (ver _corregir_expense_en_ingreso en estados/routes.py).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_expense_ingreso_reembolsable_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                    WHERE tipo='INGRESO' AND categoria='EXPENSE'
                """)
                n_expense_ingreso = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_expense_ingreso_reembolsable_2026_09",
                     f"Reclasificación de EXPENSE mal usado en ingresos: EXPENSE es solo "
                     f"para el gasto original que se va a reembolsar, no para el depósito "
                     f"que regresa. Movimientos tipo=INGRESO con categoria=EXPENSE -> "
                     f"categoria=FINANZAS, subcategoria='Reembolsable'. "
                     f"{n_expense_ingreso} filas reclasificadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_expense_ingreso_reembolsable_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — categorías legacy de movimientos bancarios ->
        #    FINANZAS (a petición explícita del usuario) ───────────────────────
        # El sprint de taxonomía anterior (finanzas_taxonomia_2026_09_sprint3)
        # ya reemplazó las categorías de consumo viejas (CASA/HOGAR,
        # COMIDA/REST, GASOLINA/AUTO, VIVERES/SUPER, ENTRETENIMIENTO, GYM,
        # VIAJES/VUELOS, SUSCRIPCIONES, REGALO, PUBLICIDAD) pero nunca tocó
        # las categorías legacy de "movimiento bancario, no gasto/ingreso
        # real": DEPOSITO, FIDEICOMISO, SPEI_RECIBIDO, SPEI_ENVIADO,
        # TRANSFERENCIA, RETIRO, PAGO, PAGO_TDC. El usuario las vio mezcladas
        # con la taxonomía nueva en el dropdown y confirmó mandarlas todas a
        # FINANZAS, con la subcategoria que más calza:
        #   DEPOSITO, FIDEICOMISO, SPEI_RECIBIDO, SPEI_ENVIADO, TRANSFERENCIA
        #     -> FINANZAS / Transferencia
        #   RETIRO -> FINANZAS / Retiro efectivo
        #   PAGO, PAGO_TDC -> FINANZAS / Pago servicios
        # budget.py ya excluye FINANZAS del lado de gasto (bucket=None y en
        # la lista NOT IN de _calc_budget) -- pero _INGRESO_EXCLUIR NO tenía
        # 'FINANZAS' listado, solo los nombres viejos (TRANSFERENCIA,
        # PAGO_TDC, RETIRO, DEPOSITO, SPEI_RECIBIDO) uno por uno. Sin
        # agregar 'FINANZAS' ahí, estos movimientos de ingreso que hoy están
        # excluidos del ingreso real del presupuesto habrían empezado a
        # contarse de más en cuanto cambiara su categoria -- exactamente el
        # "sumando de más" que el usuario pidió evitar. Se corrige en el
        # mismo cambio (ver _INGRESO_EXCLUIR en budget.py).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_legacy_bancario_a_finanzas_2026_09'"
        ).fetchone():
            try:
                mapeo = [
                    ('DEPOSITO',      'Transferencia'),
                    ('FIDEICOMISO',   'Transferencia'),
                    ('SPEI_RECIBIDO', 'Transferencia'),
                    ('SPEI_ENVIADO',  'Transferencia'),
                    ('TRANSFERENCIA', 'Transferencia'),
                    ('RETIRO',        'Retiro efectivo'),
                    ('PAGO',          'Pago servicios'),
                    ('PAGO_TDC',      'Pago servicios'),
                ]
                total_reclasificados = 0
                detalle = []
                for categoria_vieja, subcategoria_nueva in mapeo:
                    cur = db.execute(
                        "UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=? "
                        "WHERE categoria=?",
                        (subcategoria_nueva, categoria_vieja),
                    )
                    if cur.rowcount:
                        detalle.append(f"{categoria_vieja}->{subcategoria_nueva} ({cur.rowcount})")
                    total_reclasificados += cur.rowcount

                # Auditoría de duplicados pedida explícitamente por el
                # usuario: entre TODAS las filas reclasificadas (sin importar
                # de qué categoria vieja vinieron), busca si alguna comparte
                # fecha + monto (redondeado a centavos) con otra fila ya
                # existente en la tabla -- misma lógica que
                # _detectar_posibles_duplicados/admin/audit-duplicados en
                # estados/routes.py, para no dejar pasar en silencio un
                # movimiento real contado dos veces bajo categorías viejas
                # distintas.
                categorias_viejas = [c for c, _ in mapeo]
                placeholders = ','.join('?' * len(categorias_viejas))
                dup_rows = db.execute(f"""
                    SELECT fecha, ROUND(monto,2) AS monto_r, COUNT(*) AS n
                    FROM est_movimientos
                    WHERE monto != 0
                    GROUP BY fecha, monto_r
                    HAVING COUNT(*) > 1
                """).fetchall()
                n_grupos_duplicados = len(dup_rows)

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_legacy_bancario_a_finanzas_2026_09",
                     f"Categorías legacy de movimiento bancario (DEPOSITO, FIDEICOMISO, "
                     f"SPEI_RECIBIDO, SPEI_ENVIADO, TRANSFERENCIA, RETIRO, PAGO, PAGO_TDC) "
                     f"-> categoria=FINANZAS con subcategoria correspondiente. "
                     f"{total_reclasificados} filas reclasificadas ({', '.join(detalle) or 'ninguna'}). "
                     f"Se agregó 'FINANZAS' a _INGRESO_EXCLUIR en budget.py para que estos "
                     f"movimientos sigan excluidos del ingreso real (antes lo estaban por "
                     f"nombre de categoria vieja) y no se cuenten de más. "
                     f"Auditoría de duplicados (fecha+monto en TODA la tabla, no solo lo "
                     f"reclasificado): {n_grupos_duplicados} grupo(s) con más de una fila -- "
                     f"revisar en /admin/audit-duplicados o la tab Reglas si n_grupos_duplicados > 0.")
                )
                db.commit()
                if n_grupos_duplicados:
                    print(f"[DB] finanzas_legacy_bancario_a_finanzas_2026_09: "
                          f"{n_grupos_duplicados} grupo(s) de posibles duplicados detectados "
                          f"en toda la tabla -- revisar en /admin/audit-duplicados")
            except Exception as e:
                print(f"[DB] finanzas_legacy_bancario_a_finanzas_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — APORTACION_RENTA (categoria legacy) ->
        #    VIVIENDA (a petición explícita del usuario) ─────────────────────
        # El usuario vio, en el filtro "Sin subcategoría" de Ingresos, una
        # fila "SPEI RECIBIDONUBANK... Aportación renta +$5,000.00" y
        # reportó que quedaba sin subcategoría. Causa: APORTACION_RENTA es
        # una categoria de NIVEL SUPERIOR legacy (con ese mismo nombre de
        # display "Aportación renta") que quedó fuera de la migración
        # finanzas_legacy_bancario_a_finanzas_2026_09 -- una colisión de
        # nombre con la subcategoria NUEVA "Aportación renta" que se
        # agregó bajo VIVIENDA (finanzas_ingreso_subcategorias_2026_09).
        # Ya no se genera en ningún import (ningún keyword en config.py
        # apunta a ella), es puro remanente histórico. Se reclasifica según
        # tipo, igual que el resto de VIVIENDA: INGRESO -> Aportación
        # renta, GASTO -> Renta (por si quedó alguna fila así).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_aportacion_renta_legacy_2026_09'"
        ).fetchone():
            try:
                cur_ingreso = db.execute("""
                    UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Aportación renta'
                    WHERE categoria='APORTACION_RENTA' AND tipo='INGRESO'
                """)
                cur_gasto = db.execute("""
                    UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Renta'
                    WHERE categoria='APORTACION_RENTA' AND tipo='GASTO'
                """)
                total_ar = cur_ingreso.rowcount + cur_gasto.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_aportacion_renta_legacy_2026_09",
                     f"Categoria legacy APORTACION_RENTA (nivel superior, colisionaba de "
                     f"nombre con la subcategoria nueva VIVIENDA/Aportación renta) -> "
                     f"categoria=VIVIENDA. {cur_ingreso.rowcount} fila(s) INGRESO -> "
                     f"subcategoria='Aportación renta', {cur_gasto.rowcount} fila(s) GASTO -> "
                     f"subcategoria='Renta'. {total_ar} filas reclasificadas en total.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_aportacion_renta_legacy_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — VIVIENDA/Renta en un ingreso -> Aportación
        #    renta (a petición explícita del usuario) ───────────────────────
        # El usuario confirmó, con screenshot: "aportacion renta y parte
        # renta Nu son lo mismo unificalo" -- un depósito de alguien
        # aportando a la renta (ej. vía Nu) quedó con subcategoria='Renta'
        # en vez de 'Aportación renta' en algún movimiento tipo=INGRESO,
        # probablemente de antes del fix que filtra el dropdown de
        # subcategoria por tipo (VIVIENDA/Renta es la del lado GASTO). Se
        # unifica: cualquier categoria=VIVIENDA, subcategoria='Renta',
        # tipo=INGRESO -> subcategoria='Aportación renta'. La misma
        # corrección corre hacia adelante en create_transaction,
        # update_transaction, apply_all_keywords y el import (ver
        # _corregir_renta_en_ingreso en estados/routes.py).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_renta_ingreso_unificada_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Aportación renta'
                    WHERE categoria='VIVIENDA' AND subcategoria='Renta' AND tipo='INGRESO'
                """)
                n_renta_ingreso = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_renta_ingreso_unificada_2026_09",
                     f"Unifica 'Aportación renta' y 'Renta' en el lado de ingreso (el mismo "
                     f"concepto real -- alguien aportando a la renta): categoria=VIVIENDA, "
                     f"subcategoria='Renta', tipo=INGRESO -> subcategoria='Aportación renta'. "
                     f"{n_renta_ingreso} filas reclasificadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_renta_ingreso_unificada_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — variantes de VIVIENDA/Renta unificadas (a
        #    petición explícita del usuario) ─────────────────────────────────
        # El script /admin/apply-migrations (modules/finanzas/routes.py)
        # generó "Renta + deposito" y "Renta depto 807 + deposito" para
        # distinguir el pago mensual normal del pago de nov-2025 que
        # incluía el depósito inicial -- pero esa distinción ya vive en
        # mi_parte (6000 vs 7000), no hace falta una subcategoria aparte.
        # El usuario pidió unificarlo: "tambien renta depto 807" (mismo
        # pedido que Aportación renta/Renta del lado ingreso). Se
        # reclasifican a subcategoria='Renta' sin tocar mi_parte.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_renta_depto807_unificada_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Renta'
                    WHERE categoria='VIVIENDA'
                      AND subcategoria IN ('Renta + deposito', 'Renta depto 807 + deposito')
                """)
                n_renta_variantes = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_renta_depto807_unificada_2026_09",
                     f"Unifica variantes de VIVIENDA/Renta ('Renta + deposito', 'Renta depto "
                     f"807 + deposito') a subcategoria='Renta' -- la distinción del depósito "
                     f"queda en mi_parte, no en la subcategoria. {n_renta_variantes} filas "
                     f"reclasificadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_renta_depto807_unificada_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — ZEPELIN (hot dogs) -> ALIMENTACION/Fast Food
        #    (a petición explícita del usuario) ───────────────────────────────
        # ZEPELIN es una cadena de hot dogs/fast food -- estaba mal mapeada
        # como TRANSPORTE/Mantenimiento auto (keyword "CLIP MX MEC ZEPELIN",
        # el prefijo "MEC" del terminal de pago se leyó como "mecánico").
        # El usuario mandó varias filas confirmando el patrón real: "CLIP MX
        # MEC ZEPELIN EN ...", "PAYCLIP MEC ZEPELIN EN ..." por distintos
        # bancos (INVEX, BBVA_TDC, HSBC), siempre ~$105. config.py ya se
        # corrigió (keyword "ZEPELIN" -> Fast Food, reemplazando la entrada
        # vieja) -- esto reclasifica lo que ya estaba importado.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_zepelin_fast_food_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='ALIMENTACION', subcategoria='Fast Food'
                    WHERE UPPER(descripcion) LIKE '%ZEPELIN%'
                """)
                n_zepelin = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_zepelin_fast_food_2026_09",
                     f"ZEPELIN (hot dogs) estaba mal mapeado como TRANSPORTE/Mantenimiento "
                     f"auto (el prefijo 'MEC' del terminal de pago se leyó como 'mecánico') "
                     f"-> ALIMENTACION/Fast Food. {n_zepelin} filas reclasificadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_zepelin_fast_food_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — FUSION GIO -> SALSA/Congreso (a petición
        #    explícita del usuario, reportado DOS VECES) ───────────────────────
        # "esto por que sigue ahí ya habiamos dicho que es Salsa
        # subcategoria congreso" -- SPEI ENVIADO NU MEXICO ...FUSION GIO
        # (un congreso de salsa) seguía cayendo en APORTACION_RENTA/
        # VIVIENDA porque una regla de keyword más amplia (custom_kw en
        # est_keywords, prioritaria sobre el keyword genérico "SALSA" de
        # config.py) la interceptaba antes. Se corrige por texto
        # directamente. La misma corrección corre hacia adelante después
        # de aplicar reglas de keyword (ver _corregir_fusion_gio en
        # estados/routes.py) para que ninguna regla la vuelva a pisar.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_fusion_gio_salsa_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='SALSA', subcategoria='Congreso'
                    WHERE UPPER(descripcion) LIKE '%FUSION GIO%'
                """)
                n_fusion_gio = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_fusion_gio_salsa_2026_09",
                     f"FUSION GIO (congreso de salsa) -> categoria=SALSA, "
                     f"subcategoria='Congreso'. {n_fusion_gio} filas reclasificadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_fusion_gio_salsa_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — MERPAGO PANADERIA -> CAFE/PAN/Pan (a
        #    petición explícita del usuario) ─────────────────────────────────
        # "esto mandalo a cafe y pan subcategoria pan" -- MERPAGO PANADERIA
        # se quedó como ALIMENTACION (import de antes de que existiera el
        # keyword "PANADERIA" -> CAFE/PAN/Pan en config.py, o de antes de
        # la revivida de CAFE/PAN como categoria propia). Se reclasifica
        # cualquier fila con "PANADERIA" en la descripción que no esté ya
        # en CAFE/PAN.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_merpago_panaderia_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='CAFE/PAN', subcategoria='Pan'
                    WHERE UPPER(descripcion) LIKE '%PANADERIA%' AND categoria != 'CAFE/PAN'
                """)
                n_panaderia = cur.rowcount

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_merpago_panaderia_2026_09",
                     f"PANADERIA (ej. MERPAGO PANADERIA) -> categoria=CAFE/PAN, "
                     f"subcategoria='Pan'. {n_panaderia} filas reclasificadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_merpago_panaderia_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — re-agrupar compra_msi_id con prefijo corto
        #    (a petición explícita del usuario, con caso real confirmado) ─────
        # El usuario mandó un caso real de Walmart a 20 meses ($509 c/u):
        # el banco no siempre trunca la descripción igual entre
        # mensualidades ("WALMART VENTA EN L" vs "WALMART VENTA EN
        # LIN3"), así que msi_group_id (hash de descripción completa +
        # monto) las partía en dos compra_msi_id distintos -- cada grupo
        # reiniciaba su propia numeración, por eso se veían "18 de 20" y
        # "19 de 20" repetidos en vez de una sola secuencia de 20.
        # msi_group_id ahora usa solo los primeros 15 caracteres (ver
        # parsers/_base.py) -- esto recalcula compra_msi_id para las
        # filas ya importadas con la fórmula vieja.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_msi_group_id_prefijo_2026_09'"
        ).fetchone():
            try:
                import hashlib as _hashlib
                _MSI_PREFIX_LEN = 15
                filas_msi = db.execute("""
                    SELECT id, descripcion, monto FROM est_movimientos
                    WHERE parcialidad_num IS NOT NULL
                """).fetchall()
                n_regrupadas = 0
                for fila in filas_msi:
                    prefix = (fila['descripcion'] or '').strip().upper()[:_MSI_PREFIX_LEN]
                    key = f"{prefix}|{abs(round(fila['monto'], 2)):.2f}"
                    nuevo_id = _hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]
                    db.execute(
                        "UPDATE est_movimientos SET compra_msi_id=? WHERE id=?",
                        (nuevo_id, fila['id']),
                    )
                    n_regrupadas += 1

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_msi_group_id_prefijo_2026_09",
                     f"Recalcula compra_msi_id con prefijo de 15 caracteres + monto (antes "
                     f"usaba la descripción completa, que se partía en grupos distintos "
                     f"cuando el banco truncaba la descripción de forma inconsistente entre "
                     f"mensualidades). {n_regrupadas} filas de MSI recalculadas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_msi_group_id_prefijo_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — lote "EJECUTA ESTO" (batch de 12 correcciones
        #    puntuales pedidas explícitamente por el usuario con datos reales
        #    fila por fila) ────────────────────────────────────────────────────
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_ejecuta_esto_batch_2026_09'"
        ).fetchone():
            try:
                detalle = []

                # 1) AMAZON MEXICO marcado como EXPENSE reembolsable, pero es
                #    gasto normal de casa -> VIVIENDA/Artículos del hogar.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Artículos del hogar'
                    WHERE categoria='EXPENSE' AND UPPER(descripcion) LIKE '%AMAZON MEXICO%'
                """)
                detalle.append(f"AMAZON MEXICO EXPENSE->VIVIENDA/Artículos del hogar: {cur.rowcount}")

                # 2) CRISTAL VILLAHERMOSA -> FAMILIA_REGALOS/Regalos, sin
                #    importar la categoria actual.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='FAMILIA_REGALOS', subcategoria='Regalos'
                    WHERE UPPER(descripcion) LIKE '%CRISTAL VILLAHERMOSA%'
                """)
                detalle.append(f"CRISTAL VILLAHERMOSA->FAMILIA_REGALOS/Regalos: {cur.rowcount}")

                # 3) Unificación general: categoria=REGALO ya no debe existir,
                #    todo lo que quedó ahí también va a FAMILIA_REGALOS/Regalos.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='FAMILIA_REGALOS', subcategoria='Regalos'
                    WHERE categoria='REGALO'
                """)
                detalle.append(f"REGALO (legacy)->FAMILIA_REGALOS/Regalos: {cur.rowcount}")

                # 4) PRESTAMOS puntuales -> se quedan como PRESTAMOS, sin
                #    subcategoria ("no pongas subcategoria").
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria=''
                    WHERE id IN (2571, 2306, 2130)
                """)
                detalle.append(f"PRESTAMOS (ids 2571,2306,2130) subcategoria limpiada: {cur.rowcount}")

                # 5) RAILWAY -> PROYECTOS/Hosting (no existe categoria
                #    "SUSCRIPCIONES" en la taxonomía; se mantiene PROYECTOS,
                #    que ya es la categoria correcta, y se agrega la
                #    subcategoria pedida).
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='PROYECTOS', subcategoria='Hosting'
                    WHERE UPPER(descripcion) LIKE '%RAILWAY%'
                """)
                detalle.append(f"RAILWAY->PROYECTOS/Hosting: {cur.rowcount}")

                # 6) ZTL ZAIRAAXZAYMENDOZAM puntuales -> ALIMENTACION
                #    ("mandala a comida").
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='ALIMENTACION', subcategoria=''
                    WHERE id IN (1988, 1612)
                """)
                detalle.append(f"ZTL ZAIRAAXZAYMENDOZAM (ids 1988,1612)->ALIMENTACION: {cur.rowcount}")

                # 7) SPEI ENVIADO STP puntual -> INVERSION/GBM/APORTACION.
                #    Modelo de inversiones guarda monto siempre positivo
                #    (ver inversiones.py), el signo lo da la dirección.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INVERSION', categoria='GBM', subcategoria='APORTACION', monto=ABS(monto)
                    WHERE id=3239
                """)
                detalle.append(f"SPEI ENVIADO STP (id 3239)->INVERSION/GBM/APORTACION: {cur.rowcount}")

                # 8) SPEI ENVIADO INVEX puntual -> PAGO/PAGO_TDC/Invex TDC.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='PAGO', categoria='PAGO_TDC', subcategoria='Invex TDC'
                    WHERE id=3224
                """)
                detalle.append(f"SPEI ENVIADO INVEX (id 3224)->PAGO/PAGO_TDC/Invex TDC: {cur.rowcount}")

                # 9) RECARGAS Y PAQUETES BMOV puntuales -> DIGITAL/Saldo
                #    telefono (no existe categoria "SERVICIO" en la
                #    taxonomía; DIGITAL es el equivalente más cercano ya
                #    existente).
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='DIGITAL', subcategoria='Saldo telefono'
                    WHERE id IN (1983, 1751, 1663)
                """)
                detalle.append(f"RECARGAS Y PAQUETES BMOV (ids 1983,1751,1663)->DIGITAL/Saldo telefono: {cur.rowcount}")

                # 10) PLANTITA puntual -> EXPENSE ("esto es pago expense").
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='EXPENSE', subcategoria=''
                    WHERE id=3235
                """)
                detalle.append(f"PLANTITA (id 3235)->EXPENSE: {cur.rowcount}")

                # 11) GIOVANY puntual -> es INGRESO, no GASTO
                #     (FINANZAS/Transferencia, monto positivo).
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INGRESO', categoria='FINANZAS', subcategoria='Transferencia', monto=ABS(monto)
                    WHERE id=3225
                """)
                detalle.append(f"GIOVANY (id 3225)->INGRESO/FINANZAS/Transferencia: {cur.rowcount}")

                # 12) VIVERES/SUPER (legacy) -> ALIMENTACION/Súper.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='ALIMENTACION', subcategoria='Súper'
                    WHERE categoria='VIVERES/SUPER'
                """)
                detalle.append(f"VIVERES/SUPER (legacy)->ALIMENTACION/Súper: {cur.rowcount}")

                # 13) CASA/HOGAR (legacy) -> se unifica con VIVIENDA. Las
                #     filas que son en realidad el pago de renta ("PAGO
                #     TARJETA DE TERCEROS MBAN" por $12,000) se marcan
                #     VIVIENDA/Renta; el resto va a VIVIENDA/Artículos del
                #     hogar.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Renta'
                    WHERE categoria='CASA/HOGAR'
                      AND UPPER(descripcion) LIKE '%PAGO TARJETA DE TERCEROS%MBAN%'
                      AND ABS(monto)=12000
                """)
                detalle.append(f"CASA/HOGAR (renta $12,000 MBAN)->VIVIENDA/Renta: {cur.rowcount}")

                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria='Artículos del hogar'
                    WHERE categoria='CASA/HOGAR'
                """)
                detalle.append(f"CASA/HOGAR (resto, legacy)->VIVIENDA/Artículos del hogar: {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_ejecuta_esto_batch_2026_09",
                     "Lote de 13 correcciones puntuales pedidas explícitamente por el "
                     "usuario (mensaje 'EJECUTA ESTO', con ids/descripciones/montos "
                     "reales fila por fila). " + " | ".join(detalle))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_ejecuta_esto_batch_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — auditoría a detalle de duplicados DEB/TDC +
        #    lote de reclasificaciones (mensaje "AUDITA PORQUE HAY MONTOS Y
        #    DIAS REPETIDOS..." con ~18 sub-auditorías y datos reales
        #    fila por fila) ───────────────────────────────────────────────────
        # Root cause de los duplicados DEB/TDC: bbva_debit.py y
        # bbva_libreton.py (parsers/) tienen su propio diccionario de
        # categorización (CATS_DEBIT/CATS_LIBRETON) que nunca pasaba por
        # get_categoria_subcategoria() de config.py -- así que un mismo
        # movimiento real, importado una vez desde un PDF/CSV con
        # descripción ligeramente distinta (ej. con/sin número de
        # referencia), podía colarse dos veces bajo dos bancos distintos.
        # El fix de código (más abajo, ver parsers/bbva_debit.py y
        # bbva_libreton.py) corrige la causa hacia adelante; esta migración
        # limpia el histórico ya importado.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_audit_duplicados_dic_2026_09'"
        ).fetchone():
            try:
                detalle = []

                # 1) Marcar como "posible duplicado" cualquier fila
                #    BBVA_TDC de SPEI RECIBIDO que tenga una fila gemela en
                #    BBVA_DEB con la misma fecha y el mismo monto exacto --
                #    el usuario confirmó que este tipo de ingreso nunca
                #    llega por TDC, siempre es débito. No se borra (regla
                #    del usuario: nunca borrar automático): se marca fuera
                #    de FINANZAS (ya excluido de Total Ingreso/Gasto) para
                #    que deje de inflar los totales, visible para revisión
                #    manual.
                cur = db.execute("""
                    UPDATE est_movimientos AS t
                    SET categoria='FINANZAS', subcategoria='Posible duplicado (mismo día/monto en BBVA_DEB)'
                    WHERE t.banco='BBVA_TDC'
                      AND UPPER(t.descripcion) LIKE '%SPEI RECIBIDO%'
                      AND t.subcategoria != 'Posible duplicado (mismo día/monto en BBVA_DEB)'
                      AND EXISTS (
                          SELECT 1 FROM est_movimientos d
                          WHERE d.banco='BBVA_DEB'
                            AND d.fecha=t.fecha
                            AND ROUND(d.monto,2)=ROUND(t.monto,2)
                            AND UPPER(d.descripcion) LIKE '%SPEI RECIBIDO%'
                      )
                """)
                detalle.append(f"Posibles duplicados BBVA_TDC de SPEI RECIBIDO marcados: {cur.rowcount}")

                # 1b) Mismo patrón pero confirmado puntualmente por el
                #     usuario en un caso que no dice "SPEI RECIBIDO": id
                #     2238 es la misma REFBNTC00305286/PREPAGO GDLAC BMRCASH
                #     que el id 2121 (BBVA_DEB), solo que importada también
                #     como BBVA_TDC.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='FINANZAS', subcategoria='Posible duplicado (ver id 2121)'
                    WHERE id=2238
                """)
                detalle.append(f"id 2238 (duplicado de 2121) marcado: {cur.rowcount}")

                # 2) Unificar todo lo que sigue en categoria=APORTACION_RENTA
                #    (legacy) a VIVIENDA/Aportación renta -- lo mismo que se
                #    unificó antes para otras filas de renta ("ESTO MANDALO
                #    TAMBIEN A APORTE RENTA A LA CLASIFICACION QUE
                #    UNIFICAMOS"). Solo toca lo que sobrevivió al paso 1
                #    (los duplicados ya salieron de esta categoria).
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='VIVIENDA', subcategoria='Aportación renta', tipo='INGRESO', monto=ABS(monto)
                    WHERE categoria='APORTACION_RENTA'
                """)
                detalle.append(f"APORTACION_RENTA (legacy, sobrevivientes)->VIVIENDA/Aportación renta: {cur.rowcount}")

                # 3) Mojibake en subcategoria de una fila ya migrada
                #    (id 2541): "AportaciÃ³n renta" -> "Aportación renta".
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET subcategoria='Aportación renta'
                    WHERE categoria='VIVIENDA' AND subcategoria='AportaciÃ³n renta'
                """)
                detalle.append(f"Mojibake 'AportaciÃ³n renta' corregido: {cur.rowcount}")

                # 4) Filas de renta (depto 807 / "PAGO TARJETA DE TERCEROS
                #    ... MBAN" / "DEPTO 807") que la migración anterior
                #    (finanzas_ejecuta_esto_batch_2026_09, con su filtro
                #    demasiado estrecho de monto=12000 exacto) dejó
                #    incorrectamente en VIVIENDA/Artículos del hogar, o que
                #    seguían en CASA/HOGAR sin migrar -- se re-barren con un
                #    patrón de texto más amplio a VIVIENDA/Renta.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='VIVIENDA', subcategoria='Renta'
                    WHERE (categoria='CASA/HOGAR' OR (categoria='VIVIENDA' AND subcategoria='Artículos del hogar'))
                      AND (
                          UPPER(descripcion) LIKE '%TERCEROS%MBAN%'
                          OR UPPER(descripcion) LIKE '%DEPTO 807%'
                          OR UPPER(descripcion) LIKE '%RENTA%'
                      )
                """)
                detalle.append(f"Filas de renta re-barridas a VIVIENDA/Renta: {cur.rowcount}")

                # 5) id 2312: "DEPOSITO EFECTIVO ... RENTA A178 FOLIO" --
                #    depósito de renta que el usuario señaló como GASTO,
                #    no INGRESO (misma terminal/patrón que otras filas de
                #    renta que él paga). Se voltea signo y clasificación.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='VIVIENDA', subcategoria='Renta', tipo='GASTO', monto=-ABS(monto)
                    WHERE categoria='FINANZAS' AND tipo='INGRESO'
                      AND UPPER(descripcion) LIKE '%DEPOSITO EFECTIVO%RENTA%'
                """)
                detalle.append(f"Depósitos de renta mal marcados INGRESO->GASTO/VIVIENDA/Renta: {cur.rowcount}")

                # 6) Reembolsos de EXPENSE que llegaron mal etiquetados
                #    (FINANZAS/Transferencia, o categoria=NOMINA por el
                #    keyword "FIBRA HOTELERA" de bbva_debit.py/CATS_DEBIT
                #    que también hacía match con estos depósitos de
                #    reembolso del mismo empleador) -- se unifican al mismo
                #    destino que usa _corregir_expense_en_ingreso().
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='FINANZAS', subcategoria='Reembolsable'
                    WHERE id IN (1810,1975,1909,1955,1831,2123,2023,2390,1852,1976,1905,2124,1921)
                """)
                detalle.append(f"Reembolsos de EXPENSE mal etiquetados->FINANZAS/Reembolsable: {cur.rowcount}")

                # 7) FIDEICOMISO F 1596 -- ingresos recurrentes de un
                #    fideicomiso, con subcategoria inconsistente
                #    (Reembolsable/Transferencia mezclados). Se unifica a
                #    su propia subcategoria clara.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='FINANZAS', subcategoria='Fideicomiso'
                    WHERE id IN (2580,2529,2494,2371,2247,2057,2006,1625,2104,1726)
                """)
                detalle.append(f"FIDEICOMISO F 1596 unificado a FINANZAS/Fideicomiso: {cur.rowcount}")

                # 8) Depósitos de retiro de CETES (SPEI RECIBIDONAFIN) que
                #    llegaron como FINANZAS/Transferencia -- el usuario
                #    confirmó que son dinero saliendo de su inversión en
                #    CETES, no un ingreso regular. Se alinean al modelo de
                #    INVERSION (categoria=plataforma, subcategoria=
                #    dirección) igual que la fila 3220, que ya estaba bien.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INVERSION', categoria='CETES', subcategoria='RETIRO', monto=ABS(monto)
                    WHERE id IN (1842,1961,2573,2572,2576,2575,2139,2143,2076,2236,2235)
                """)
                detalle.append(f"Retiros de CETES (NAFIN) alineados al modelo INVERSION: {cur.rowcount}")

                # 9) Filas ya tipo=INVERSION pero con categoria='INVERSION'
                #    literal (formato inválido del modelo -- categoria debe
                #    ser la plataforma, ej. CETES/GBM, no la palabra
                #    "INVERSION") -- se corrige a CETES/RETIRO.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='CETES', subcategoria='RETIRO'
                    WHERE tipo='INVERSION' AND categoria='INVERSION'
                """)
                detalle.append(f"categoria='INVERSION' literal corregida a CETES/RETIRO: {cur.rowcount}")

                # 10) id 2121: mal quedó como INVERSION -- el usuario
                #     confirmó que es un ingreso de expense, no inversión.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INGRESO', categoria='FINANZAS', subcategoria='Reembolsable', monto=ABS(monto)
                    WHERE id=2121
                """)
                detalle.append(f"id 2121 (INVERSION mal etiquetada)->INGRESO/FINANZAS/Reembolsable: {cur.rowcount}")

                # 11) id 1886: "SPEI ENVIADO INVEX" -- confirmado como pago
                #     de TDC Invex, no inversión.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='MOVIMIENTO_INTERNO', categoria='PAGO_TDC', subcategoria=''
                    WHERE id=1886
                """)
                detalle.append(f"id 1886 (INVERSION mal etiquetada)->MOVIMIENTO_INTERNO/PAGO_TDC: {cur.rowcount}")

                # 12) NOMINA nunca debe ir a BBVA_TDC -- el usuario confirmó
                #     que la nómina siempre cae en débito.
                cur = db.execute("""
                    UPDATE est_movimientos SET banco='BBVA_DEB'
                    WHERE categoria='NOMINA' AND banco='BBVA_TDC'
                """)
                detalle.append(f"NOMINA con banco=BBVA_TDC corregido a BBVA_DEB: {cur.rowcount}")

                # 13) id 3228: transferencia a Giovany -- confirmado como
                #     pago de préstamo recibido.
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='PRESTAMOS', subcategoria=''
                    WHERE id=3228
                """)
                detalle.append(f"id 3228 (TRANSFERENCIA legacy)->PRESTAMOS: {cur.rowcount}")

                # 14) Unificar todas las filas ya tipo=MOVIMIENTO_INTERNO a
                #     categoria=PAGO_TDC sin subcategoria ("AQUÍ SI TODOS
                #     SON PAGOS A TDC PERO TUS CATEGORIAS SON CONFUSAS
                #     DEJALOS TODOS EN PAGO_TDC").
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET categoria='PAGO_TDC', subcategoria=''
                    WHERE tipo='MOVIMIENTO_INTERNO'
                      AND (categoria != 'PAGO_TDC' OR subcategoria != '')
                """)
                detalle.append(f"MOVIMIENTO_INTERNO unificado a PAGO_TDC: {cur.rowcount}")

                # 15) Pagos/abonos de TDC identificables por patrón de texto
                #     (BMOVIL.PAGO TDC, PAGO TARJETA DE CREDITO, SU/SUPAGO
                #     GRACIAS SPEI, SU PAGO POR SPEI_T, SPEI ENVIADO
                #     HSBC/INVEX, INTERN.PAGO TDC) -- se pasan a
                #     MOVIMIENTO_INTERNO/PAGO_TDC. Al no ser ni GASTO ni
                #     INGRESO, tipo=MOVIMIENTO_INTERNO queda automáticamente
                #     fuera de toda suma de Total Gastado/Total Ingreso
                #     (esas solo suman tipo='GASTO'/'INGRESO'), sin importar
                #     el signo con que haya quedado guardado el monto --
                #     así se resuelve "no estes corrompiendo o sumando los
                #     negativos" sin necesidad de casar manualmente cada par
                #     positivo/negativo. Se excluyen explícitamente los
                #     ajustes de tipo de cambio (no son pagos de TDC) y los
                #     casos ya tratados aparte (aportación de renta del
                #     roomie, retiro de efectivo, restaurante).
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='MOVIMIENTO_INTERNO', categoria='PAGO_TDC', subcategoria=''
                    WHERE tipo='PAGO'
                      AND id NOT IN (2445, 2440, 1812, 2077)
                      AND UPPER(descripcion) NOT LIKE '%AJUSTE TIPO CAMBIO%'
                      AND (
                          UPPER(descripcion) LIKE '%PAGO TDC%'
                          OR UPPER(descripcion) LIKE '%PAGO TARJETA DE CREDITO%'
                          OR UPPER(descripcion) LIKE '%PAGO GRACIAS%'
                          OR UPPER(descripcion) LIKE '%PAGO POR SPEI%'
                          OR UPPER(descripcion) LIKE '%SPEI ENVIADO HSBC%'
                          OR UPPER(descripcion) LIKE '%SPEI ENVIADO INVEX%'
                          OR (banco='MANUAL' AND UPPER(descripcion)='TDC')
                          OR (UPPER(descripcion) LIKE '%TARJETA DE CREDITO%' AND UPPER(descripcion) LIKE '%PAGO CUENTA DE TERCERO%')
                          OR (UPPER(descripcion) LIKE '%GIOVANY%' AND UPPER(descripcion) LIKE '%SPEI ENVIADO%'
                              AND (UPPER(descripcion) LIKE '%HSBC%' OR UPPER(descripcion) LIKE '%INVEX%'))
                      )
                """)
                detalle.append(f"Pagos de TDC (PAGO, texto reconocido)->MOVIMIENTO_INTERNO/PAGO_TDC: {cur.rowcount}")

                # 16) ids 2445/2440: NO son pago de TDC -- son la
                #     aportación de renta del roomie, mal clasificada
                #     porque coincidía con un patrón de SPEI recibido en
                #     TDC (ver punto 1, pero estas dos SÍ son reales, sin
                #     fila gemela en BBVA_DEB).
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='INGRESO', categoria='VIVIENDA', subcategoria='Aportación renta', monto=ABS(monto)
                    WHERE id IN (2445, 2440)
                """)
                detalle.append(f"ids 2445/2440 (aportación renta roomie, no PAGO)->VIVIENDA/Aportación renta: {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_audit_duplicados_dic_2026_09",
                     "Auditoría a detalle de duplicados BBVA_DEB/BBVA_TDC (mismo día/monto) "
                     "y lote de ~16 reclasificaciones puntuales pedidas por el usuario, con "
                     "datos reales fila por fila. " + " | ".join(detalle))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_audit_duplicados_dic_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — corrección de la migración anterior: ids
        #    2236/2235 (usuario preguntó "cuales son esos que dices que no
        #    tocaste pero que estan repetidos", lo que llevó a re-revisar la
        #    lista completa) ──────────────────────────────────────────────────
        # finanzas_audit_duplicados_dic_2026_09 metió los ids 2236/2235
        # (SPEI RECIBIDONAFIN, banco=BBVA_TDC) en el mismo lote que sus
        # gemelos reales 2143/2139 (banco=BBVA_DEB, mismo día, mismo monto,
        # misma referencia "135 ... EGRESOS SPEI SVD") -- los cuatro
        # terminaron con tipo=INVERSION/categoria=CETES/subcategoria=RETIRO,
        # duplicando el monto "retirado" en la vista de Inversiones en vez
        # de marcar el lado TDC como duplicado (como sí se hizo con el par
        # 2121/2238, que sigue el mismo patrón). Se corrige aquí sin
        # reescribir la migración ya aplicada.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_dedup_nafin_tdc_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    UPDATE est_movimientos
                    SET tipo='PAGO', categoria='FINANZAS', subcategoria='Posible duplicado (ver id 2143/2139)'
                    WHERE id IN (2236, 2235)
                """)
                n = cur.rowcount
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_dedup_nafin_tdc_2026_09",
                     f"Corrige finanzas_audit_duplicados_dic_2026_09: ids 2236/2235 (BBVA_TDC, "
                     f"gemelos de 2143/2139 en BBVA_DEB) se sacan de CETES/RETIRO y se marcan "
                     f"como posible duplicado en vez de duplicar el monto retirado. {n} filas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_dedup_nafin_tdc_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — borrado puntual, explícitamente confirmado
        #    por el usuario (id 2318, $50,000 del 16/07/2026) ─────────────────
        # Única excepción a "nunca borrar automático" de esta sesión: el
        # usuario confirmó directamente, tras revisar su propia DB, que esta
        # fila es un duplicado real de algo que ya tiene registrado como
        # INGRESO/REGALO -- "2318 NO ES PAGO YA LO TENEMOS EN INGRESO BORRA
        # ESE DE PAGO". No es una migración automática adivinando: es un
        # borrado de una fila puntual, identificada por id, con confirmación
        # explícita del usuario sobre su propia base de datos.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_borra_2318_duplicado_2026_09'"
        ).fetchone():
            try:
                cur = db.execute("""
                    DELETE FROM est_movimientos
                    WHERE id=2318 AND UPPER(descripcion) LIKE '%IGUAL TQM%'
                """)
                n = cur.rowcount
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_borra_2318_duplicado_2026_09",
                     f"Borrado puntual confirmado explícitamente por el usuario: id 2318 "
                     f"($50,000, 16/07/2026, 'PAGO CUENTA DE TERCERO...IGUAL TQM') es un "
                     f"duplicado de una fila que ya tiene registrada como INGRESO/REGALO. "
                     f"{n} filas borradas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_borra_2318_duplicado_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — borrado de los duplicados DEB/TDC
        #    confirmados por el usuario ("SI SON DUPLICADOS SOLO DEJA EL QUE
        #    ESTA EN BBVA DEB LOS DEMAS ELIMINALOS") ────────────────────────────
        # Los 8 ids de abajo son el lado BBVA_TDC de cada par que
        # finanzas_audit_duplicados_dic_2026_09 / finanzas_dedup_nafin_tdc_2026_09
        # habían marcado (categoria=FINANZAS, subcategoria='Posible
        # duplicado...') en vez de borrar -- el usuario ya los revisó y
        # confirmó que sí son el mismo movimiento repetido, lado BBVA_DEB
        # incluido (2121/2238, que tenían fechas distintas). Se borran solo
        # estos ids puntuales, nunca por patrón de texto/fecha/monto.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_borra_duplicados_confirmados_2026_09'"
        ).fetchone():
            try:
                ids_a_borrar = (2387, 2321, 2234, 2237, 2239, 2236, 2235, 2238)
                cur = db.execute(
                    f"DELETE FROM est_movimientos WHERE id IN ({','.join('?' * len(ids_a_borrar))})",
                    ids_a_borrar,
                )
                n = cur.rowcount
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_borra_duplicados_confirmados_2026_09",
                     f"Borrado de los 8 duplicados BBVA_TDC confirmados explícitamente por el "
                     f"usuario (ids 2387,2321,2234,2237,2239,2236,2235,2238) -- se queda solo "
                     f"el lado BBVA_DEB de cada par (2383,2308,2137,2144,2148,2143,2139,2121). "
                     f"{n} filas borradas.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_borra_duplicados_confirmados_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — lote "MANDA A SUBCATEGORIA SUPER" (7
        #    correcciones puntuales + unificación Cobrado/Reembolsable) ────────
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_lote_super_reembolsable_2026_09'"
        ).fetchone():
            try:
                detalle = []

                # 1) ZTL ZAIRAAXZAYMENDOZAM (ids 1988, 1612) -> subcategoria Súper.
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Súper'
                    WHERE id IN (1988, 1612)
                """)
                detalle.append(f"ZTL (ids 1988,1612)->ALIMENTACION/Súper: {cur.rowcount}")

                # 2) FIDEICOMISO F 1596 -- "cambia eso de fideicomiso a expense
                #    pagado, ya lo habiamos hablado": se unifica al mismo
                #    destino que un reembolso de EXPENSE cobrado.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                    WHERE id IN (2580,2529,2494,2371,2247,2104,2057,2006,1726,1625)
                """)
                detalle.append(f"FIDEICOMISO F 1596 (10 ids)->FINANZAS/Reembolsable: {cur.rowcount}")

                # 3) id 3228: corrige la decisión anterior (se había mandado a
                #    PRESTAMOS) -- el usuario confirmó que es "ingreso pago
                #    expense", no un cobro de préstamo.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                    WHERE id=3228
                """)
                detalle.append(f"id 3228 (PRESTAMOS->FINANZAS/Reembolsable): {cur.rowcount}")

                # 4) id 2079 -> subcategoria Regalos.
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria='Regalos'
                    WHERE id=2079
                """)
                detalle.append(f"id 2079->FAMILIA_REGALOS/Regalos: {cur.rowcount}")

                # 5) CETES: "DOMICILIACION"/"ENVIADO" es dinero saliendo de la
                #    cuenta para invertir (APORTACION), no un RETIRO -- ver el
                #    fix en upload_file() (misma lógica, para nuevas
                #    importaciones). Corrige el histórico ya importado con la
                #    lógica vieja (dirección por tipo, no por texto).
                cur = db.execute("""
                    UPDATE est_movimientos SET subcategoria='APORTACION'
                    WHERE id IN (1605,1621,1632,1653,1926,2021,2099,2248)
                      AND subcategoria='RETIRO'
                """)
                detalle.append(f"CETES RETIRO->APORTACION (8 ids, ENVIADO/DOMICILIACION): {cur.rowcount}")

                # 6) id 1679: préstamo a la hermana del usuario.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria=''
                    WHERE id=1679
                """)
                detalle.append(f"id 1679->PRESTAMOS: {cur.rowcount}")

                # 7) "COBRADO Y REEMBOLSABLE ES LO MISMO UNIFICA": cualquier
                #    fila PRESTAMOS/Cobrado que exista se unifica al mismo
                #    destino (ver también config.py::SUBCATEGORIAS, donde
                #    "Cobrado" ya se quitó de las opciones de PRESTAMOS).
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                    WHERE categoria='PRESTAMOS' AND subcategoria='Cobrado'
                """)
                detalle.append(f"PRESTAMOS/Cobrado->FINANZAS/Reembolsable: {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_lote_super_reembolsable_2026_09",
                     "Lote de correcciones puntuales ('MANDA A SUBCATEGORIA SUPER' y "
                     "siguientes) + unificación Cobrado/Reembolsable. " + " | ".join(detalle))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_lote_super_reembolsable_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — FAR GUAD por monto (a petición explícita
        #    del usuario) ──────────────────────────────────────────────────────
        # "todo lo que venga de FAR GUAD y es menor a 200 pesos es
        # alimentacion subcategoria conveniencia todo lo que sea mayor a eso
        # seguramente son medicamentos e iria en salud subcategoria
        # farmacia". Backfill del histórico ya importado; el mismo criterio
        # corre hacia adelante en cada import/aplicación de reglas (ver
        # _corregir_far_guad en estados/routes.py).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_far_guad_por_monto_2026_09'"
        ).fetchone():
            try:
                cur1 = db.execute("""
                    UPDATE est_movimientos SET categoria='ALIMENTACION', subcategoria='Conveniencia'
                    WHERE UPPER(descripcion) LIKE '%FAR GUAD%'
                      AND ABS(monto) < 200
                      AND categoria != 'EXPENSE'
                """)
                cur2 = db.execute("""
                    UPDATE est_movimientos SET categoria='SALUD', subcategoria='Farmacia'
                    WHERE UPPER(descripcion) LIKE '%FAR GUAD%'
                      AND ABS(monto) >= 200
                      AND categoria != 'EXPENSE'
                """)
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_far_guad_por_monto_2026_09",
                     f"FAR GUAD < $200 -> ALIMENTACION/Conveniencia ({cur1.rowcount} filas), "
                     f">= $200 -> SALUD/Farmacia ({cur2.rowcount} filas). No toca categoria=EXPENSE.")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_far_guad_por_monto_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — barrido final de COMIDA/REST y VIAJES/VUELOS
        #    (categorías legacy que ya "reemplazaba" finanzas_taxonomia_
        #    2026_09_sprint3, pero -- mismo patrón que CASA/HOGAR, VIVERES/
        #    SUPER y REGALO esta sesión -- dejó filas sin migrar) ────────────
        # "borra las viejas categorias de categoria me confunden hay comida
        # y luego alimentancion tambien esta el viejo de viajes/vuelos y el
        # nuevo". Se barre lo que haya quedado sin necesidad de reconstruir
        # el mapeo exacto de sprint3 (_S3_M): cualquier COMIDA/REST->
        # ALIMENTACION (Café se respeta si ya lo tenía, el resto a
        # Restaurante, el mismo default que usaba sprint3) y cualquier
        # VIAJES/VUELOS->VIAJES (con el mismo mapeo de subcategoria que
        # sprint3 ya usaba, más un catch-all a "Otros" para cualquier
        # subcategoria no contemplada ahí).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_barrido_comida_viajes_legacy_2026_09'"
        ).fetchone():
            try:
                detalle = []

                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='ALIMENTACION'
                    WHERE categoria='COMIDA/REST' AND subcategoria='Café'
                """)
                detalle.append(f"COMIDA/REST Café->ALIMENTACION/Café: {cur.rowcount}")

                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='ALIMENTACION', subcategoria='Restaurante'
                    WHERE categoria='COMIDA/REST'
                """)
                detalle.append(f"COMIDA/REST (resto)->ALIMENTACION/Restaurante: {cur.rowcount}")

                _viajes_mapeo = [
                    ('Hotel',       'Hospedaje'),
                    ('Restaurante', 'Comida'),
                    ('Supermercado','Comida'),
                    ('Vuelos',      'Transporte'),
                    ('Hogar general', 'Otros'),
                    ('Salidas',     'Otros'),
                    ('telefono',    'Otros'),
                    ('',            'Otros'),
                ]
                for sub_vieja, sub_nueva in _viajes_mapeo:
                    cur = db.execute("""
                        UPDATE est_movimientos SET categoria='VIAJES', subcategoria=?
                        WHERE categoria='VIAJES/VUELOS' AND subcategoria=?
                    """, (sub_nueva, sub_vieja))
                    if cur.rowcount:
                        detalle.append(f"VIAJES/VUELOS '{sub_vieja}'->VIAJES/{sub_nueva}: {cur.rowcount}")

                # Catch-all: cualquier VIAJES/VUELOS que sobreviva con una
                # subcategoria no contemplada arriba.
                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='VIAJES', subcategoria='Otros'
                    WHERE categoria='VIAJES/VUELOS'
                """)
                if cur.rowcount:
                    detalle.append(f"VIAJES/VUELOS (subcategoria no contemplada)->VIAJES/Otros: {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_barrido_comida_viajes_legacy_2026_09",
                     "Barrido final de COMIDA/REST->ALIMENTACION y VIAJES/VUELOS->VIAJES "
                     "(sprint3 las 'reemplazó' pero dejó filas sin migrar, mismo patrón que "
                     "CASA/HOGAR/VIVERES/SUPER/REGALO). " + " | ".join(detalle))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_barrido_comida_viajes_legacy_2026_09 migration warning: {e}")

        # El usuario reportó que CASA/HOGAR y VIVERES/SUPER seguían
        # reapareciendo pese a las migraciones de barrido anteriores
        # (finanzas_ejecuta_esto_batch_2026_09,
        # finanzas_barrido_comida_viajes_legacy_2026_09, etc.): "vivienda
        # y casa/hogar es lo mismo... misma cosa con viveres/super...
        # esas categorias viejas no deben exisitir cuantas veces te lo
        # debo repetir". Causa raíz: barrer solo est_movimientos no basta
        # -- reglas guardadas en est_keywords ANTES del retiro de estas
        # categorías todavía tenían categoria=<vieja>, y cada "Aplicar
        # todas a lo existente" o import nuevo las revivía en
        # est_movimientos, deshaciendo el barrido. Esta migración corrige
        # AMBAS tablas de una vez para las 4 categorías legacy conocidas
        # (CASA/HOGAR, VIVERES/SUPER, COMIDA/REST, VIAJES/VUELOS); el
        # blindaje contra recurrencia futura (_corregir_categorias_legacy,
        # wireado en apply_all_keywords y upload_file) vive en
        # modules/finanzas/estados/routes.py.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_unifica_categorias_legacy_2026_09'"
        ).fetchone():
            try:
                detalle = []
                _legacy_map = [
                    ('CASA/HOGAR',    'VIVIENDA',     'Renta'),
                    ('VIVERES/SUPER', 'ALIMENTACION', 'Súper'),
                    ('COMIDA/REST',   'ALIMENTACION', 'Restaurante'),
                    ('VIAJES/VUELOS', 'VIAJES',       'Otros'),
                ]
                for legacy, cat, sub in _legacy_map:
                    cur = db.execute(
                        "UPDATE est_keywords SET categoria=?, subcategoria=? WHERE categoria=?",
                        (cat, sub, legacy),
                    )
                    if cur.rowcount:
                        detalle.append(f"est_keywords {legacy}->{cat}/{sub}: {cur.rowcount}")
                    cur = db.execute(
                        "UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE categoria=?",
                        (cat, sub, legacy),
                    )
                    if cur.rowcount:
                        detalle.append(f"est_movimientos {legacy}->{cat}/{sub}: {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_unifica_categorias_legacy_2026_09",
                     "Barrido definitivo de categorías legacy (CASA/HOGAR, VIVERES/SUPER, "
                     "COMIDA/REST, VIAJES/VUELOS) en est_movimientos Y est_keywords -- las "
                     "migraciones anteriores solo tocaban est_movimientos y reglas guardadas "
                     "las revivían. " + (" | ".join(detalle) if detalle else "nada que corregir"))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_unifica_categorias_legacy_2026_09 migration warning: {e}")

        # El usuario reportó dos reclasificaciones puntuales el mismo día:
        # 1) "REGALO" (categoria plana legacy, mismo patrón que CASA/HOGAR
        #    etc. -- el usuario incluso lo marcó explícitamente: "mismo
        #    problema repetiste regalo ya tenemos familia regalo") es
        #    enteramente el pago a CRISTAL VILLAHERMOSA a 12 meses (un
        #    anillo): "manda eso a familia y regalos a la subcategoria
        #    Anillo Cornelius". Se unifica igual que los demás legacy --
        #    est_movimientos Y est_keywords, por la misma causa raíz.
        # 2) STEAMGAMES.COM caía en DIGITAL/Suscripciones IA/productividad
        #    en vez de OCIO/Videojuegos (ya existente como subcategoria):
        #    "manda estos a Entretenimiento y crea una subcategoria de
        #    videojuegos". Blindaje futuro (_corregir_steamgames, wireado
        #    en apply_all_keywords/upload_file) y keyword nueva en
        #    config.py viven fuera de esta migración -- aquí solo el
        #    backfill histórico.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_regalo_steamgames_2026_09'"
        ).fetchone():
            try:
                detalle = []

                cur = db.execute(
                    "UPDATE est_keywords SET categoria='FAMILIA_REGALOS', subcategoria='Anillo Cornelius' WHERE categoria='REGALO'"
                )
                if cur.rowcount:
                    detalle.append(f"est_keywords REGALO->FAMILIA_REGALOS/Anillo Cornelius: {cur.rowcount}")
                cur = db.execute(
                    "UPDATE est_movimientos SET categoria='FAMILIA_REGALOS', subcategoria='Anillo Cornelius' WHERE categoria='REGALO'"
                )
                if cur.rowcount:
                    detalle.append(f"est_movimientos REGALO->FAMILIA_REGALOS/Anillo Cornelius: {cur.rowcount}")

                cur = db.execute("""
                    UPDATE est_movimientos SET categoria='OCIO', subcategoria='Videojuegos'
                    WHERE UPPER(descripcion) LIKE '%STEAMGAMES%'
                      AND (categoria != 'OCIO' OR subcategoria != 'Videojuegos')
                """)
                if cur.rowcount:
                    detalle.append(f"STEAMGAMES.COM->OCIO/Videojuegos: {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_regalo_steamgames_2026_09",
                     "REGALO (legacy)->FAMILIA_REGALOS/Anillo Cornelius y STEAMGAMES.COM->"
                     "OCIO/Videojuegos. " + (" | ".join(detalle) if detalle else "nada que corregir"))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_regalo_steamgames_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — unifica "Servicios" dentro de Vivienda ──────────
        # El usuario reportó los mismos gastos de servicios del hogar (luz,
        # agua, gas, internet...) partidos en dos lugares: categoria='SERVICIOS'
        # (categoria plana legacy -- el sprint de taxonomía de arriba
        # (finanzas_taxonomia_2026_09_sprint3) solo migró sus filas con
        # subcategoria Internet/Luz/Saldo telefono, dejando Agua/Gas/'' sin
        # tocar) y VIVIENDA con subcategoria='Servicios' (genérica, no es una
        # subcategoría válida del árbol actual -- ver SUBCATEGORIAS en
        # config.py). Confirmado con el usuario: parte viene de reglas
        # personalizadas en est_keywords, parte de datos ya guardados en
        # est_movimientos -- se corrigen ambas tablas de una vez, igual que
        # finanzas_unifica_categorias_legacy_2026_09 hizo con CASA/HOGAR y
        # compañía. El blindaje contra recurrencia futura
        # (_corregir_servicios_legacy, wireado en apply_all_keywords y
        # upload_file) vive en modules/finanzas/estados/routes.py.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_unifica_servicios_2026_09'"
        ).fetchone():
            try:
                detalle = []
                _servicios_subcat_map = [
                    ('Internet',       'VIVIENDA', 'Internet'),
                    ('Luz',            'VIVIENDA', 'Luz'),
                    ('Agua',           'VIVIENDA', 'Agua'),
                    ('Gas',            'VIVIENDA', 'Gas'),
                    ('Saldo telefono', 'DIGITAL',  'Celular'),
                    ('',               'VIVIENDA', ''),
                ]
                for sub_vieja, cat, sub in _servicios_subcat_map:
                    cur = db.execute(
                        "UPDATE est_keywords SET categoria=?, subcategoria=? "
                        "WHERE UPPER(categoria)='SERVICIOS' AND UPPER(COALESCE(subcategoria,''))=?",
                        (cat, sub, sub_vieja.upper()),
                    )
                    if cur.rowcount:
                        detalle.append(f"est_keywords SERVICIOS/{sub_vieja or '(vacío)'}->{cat}/{sub}: {cur.rowcount}")
                    cur = db.execute(
                        "UPDATE est_movimientos SET categoria=?, subcategoria=? "
                        "WHERE UPPER(categoria)='SERVICIOS' AND UPPER(COALESCE(subcategoria,''))=?",
                        (cat, sub, sub_vieja.upper()),
                    )
                    if cur.rowcount:
                        detalle.append(f"est_movimientos SERVICIOS/{sub_vieja or '(vacío)'}->{cat}/{sub}: {cur.rowcount}")

                # Catch-all: cualquier fila que siga en SERVICIOS con una
                # subcategoria no contemplada arriba -- se sube a VIVIENDA de
                # todos modos; conserva la subcategoria solo si ya es válida
                # ahí (VIVIENDA sí trae "Plantas" para esta fecha), si no se
                # blanquea en vez de adivinar.
                _validas_vivienda = {
                    "Renta", "Aportación renta", "Luz", "Agua", "Gas", "Internet",
                    "Artículos del hogar", "Lavandería", "Mudanza", "Plantas",
                }
                sobrantes_kw = db.execute(
                    "SELECT rowid, subcategoria FROM est_keywords WHERE UPPER(categoria)='SERVICIOS'"
                ).fetchall()
                for row in sobrantes_kw:
                    sub = (row['subcategoria'] or '').strip()
                    db.execute(
                        "UPDATE est_keywords SET categoria='VIVIENDA', subcategoria=? WHERE rowid=?",
                        (sub if sub in _validas_vivienda else '', row['rowid']),
                    )
                if sobrantes_kw:
                    detalle.append(f"est_keywords SERVICIOS sobrantes->VIVIENDA: {len(sobrantes_kw)}")

                sobrantes_mov = db.execute(
                    "SELECT id, subcategoria FROM est_movimientos WHERE UPPER(categoria)='SERVICIOS'"
                ).fetchall()
                for row in sobrantes_mov:
                    sub = (row['subcategoria'] or '').strip()
                    db.execute(
                        "UPDATE est_movimientos SET categoria='VIVIENDA', subcategoria=? WHERE id=?",
                        (sub if sub in _validas_vivienda else '', row['id']),
                    )
                if sobrantes_mov:
                    detalle.append(f"est_movimientos SERVICIOS sobrantes->VIVIENDA: {len(sobrantes_mov)}")

                # VIVIENDA/Servicios genérico: no es una subcategoría real y
                # no hay pista distinta a "Servicios" para inferir cuál sub
                # específica le toca -- se blanquea.
                cur = db.execute(
                    "UPDATE est_keywords SET subcategoria='' "
                    "WHERE UPPER(categoria)='VIVIENDA' AND UPPER(subcategoria)='SERVICIOS'"
                )
                if cur.rowcount:
                    detalle.append(f"est_keywords VIVIENDA/Servicios->VIVIENDA/(vacío): {cur.rowcount}")
                cur = db.execute(
                    "UPDATE est_movimientos SET subcategoria='' "
                    "WHERE UPPER(categoria)='VIVIENDA' AND UPPER(subcategoria)='SERVICIOS'"
                )
                if cur.rowcount:
                    detalle.append(f"est_movimientos VIVIENDA/Servicios->VIVIENDA/(vacío): {cur.rowcount}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_unifica_servicios_2026_09",
                     "Unifica la categoría legacy SERVICIOS y VIVIENDA/subcategoria "
                     "'Servicios' (genérica, inválida) dentro de VIVIENDA con subcategorías "
                     "específicas (Luz/Agua/Gas/Internet) o DIGITAL/Celular para saldo "
                     "telefónico -- corrige est_keywords Y est_movimientos. " +
                     (" | ".join(detalle) if detalle else "nada que corregir"))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_unifica_servicios_2026_09 migration warning: {e}")

        # ── ESTADOS DE CUENTA — unifica "Suscripciones" dentro de Digital ───────
        # Mismo patrón que finanzas_unifica_servicios_2026_09, aplicado a otra
        # categoria plana legacy: SUSCRIPCIONES. El sprint de taxonomía de
        # arriba (finanzas_taxonomia_2026_09_sprint3) ya trae el mapeo por
        # subcategoria (Telefonía->Digital/Celular, Digital/Internet-TV/
        # Música->Digital/Suscripciones entretenimiento, Diseño/Productividad
        # ->Digital/Suscripciones IA-productividad, Gym->Deporte/Gym,
        # Tech->Proyectos/Hosting) pero -- igual que con SERVICIOS -- nunca
        # tuvo blindaje contra recurrencia, así que reglas guardadas en
        # est_keywords ANTES de esa migración la seguían reviviendo. El
        # usuario reportó ver "saldo teléfono" partido entre SERVICIOS y
        # SUSCRIPCIONES; se unifica el teléfono en DIGITAL/Celular en ambos
        # casos (mismo destino que ya usa SERVICIOS) y de paso se termina de
        # barrer toda la categoria SUSCRIPCIONES, no solo el pedazo de
        # teléfono, para que no vuelva a aparecer partida por otra
        # subcategoria. El blindaje contra recurrencia futura
        # (_corregir_suscripciones_legacy, wireado en apply_all_keywords y
        # upload_file) vive en modules/finanzas/estados/routes.py.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_unifica_suscripciones_2026_09'"
        ).fetchone():
            try:
                detalle = []
                _suscripciones_subcat_map = [
                    ('',              'DIGITAL',   ''),
                    ('Digital',       'DIGITAL',   'Suscripciones entretenimiento'),
                    ('Diseño',        'DIGITAL',   'Suscripciones IA/productividad'),
                    ('Gym',           'DEPORTE',   'Gym'),
                    ('Internet/TV',   'DIGITAL',   'Suscripciones entretenimiento'),
                    ('Música',        'DIGITAL',   'Suscripciones entretenimiento'),
                    ('Productividad', 'DIGITAL',   'Suscripciones IA/productividad'),
                    ('Tech',          'PROYECTOS', 'Hosting'),
                    ('Telefonía',     'DIGITAL',   'Celular'),
                ]
                for sub_vieja, cat, sub in _suscripciones_subcat_map:
                    cur = db.execute(
                        "UPDATE est_keywords SET categoria=?, subcategoria=? "
                        "WHERE UPPER(categoria)='SUSCRIPCIONES' AND UPPER(COALESCE(subcategoria,''))=?",
                        (cat, sub, sub_vieja.upper()),
                    )
                    if cur.rowcount:
                        detalle.append(f"est_keywords SUSCRIPCIONES/{sub_vieja or '(vacío)'}->{cat}/{sub}: {cur.rowcount}")
                    cur = db.execute(
                        "UPDATE est_movimientos SET categoria=?, subcategoria=? "
                        "WHERE UPPER(categoria)='SUSCRIPCIONES' AND UPPER(COALESCE(subcategoria,''))=?",
                        (cat, sub, sub_vieja.upper()),
                    )
                    if cur.rowcount:
                        detalle.append(f"est_movimientos SUSCRIPCIONES/{sub_vieja or '(vacío)'}->{cat}/{sub}: {cur.rowcount}")

                # Variantes de "saldo teléfono" no cubiertas por el mapeo
                # exacto (typos, sin acento, etc.) -- cualquier subcategoria
                # que mencione teléfono/saldo/celular se va a DIGITAL/Celular,
                # igual que en SERVICIOS.
                _telefono_kw = ('TELEFON', 'SALDO', 'CELULAR')
                n_tel = 0
                for tabla, pk in (('est_keywords', 'rowid'), ('est_movimientos', 'id')):
                    rows = db.execute(
                        f"SELECT {pk} AS pk, subcategoria FROM {tabla} WHERE UPPER(categoria)='SUSCRIPCIONES'"
                    ).fetchall()
                    for row in rows:
                        sub_u = (row['subcategoria'] or '').upper()
                        if any(kw in sub_u for kw in _telefono_kw):
                            db.execute(
                                f"UPDATE {tabla} SET categoria='DIGITAL', subcategoria='Celular' WHERE {pk}=?",
                                (row['pk'],),
                            )
                            n_tel += 1
                if n_tel:
                    detalle.append(f"variantes 'saldo teléfono' no exactas -> DIGITAL/Celular: {n_tel}")

                # Catch-all: cualquier fila que siga en SUSCRIPCIONES -- se
                # sube a DIGITAL de todos modos; conserva la subcategoria
                # solo si ya es válida ahí, si no se blanquea.
                _validas_digital = {
                    "Celular", "Suscripciones IA/productividad",
                    "Suscripciones entretenimiento", "Accesorios tech",
                }
                n_sobrantes = 0
                for tabla, pk in (('est_keywords', 'rowid'), ('est_movimientos', 'id')):
                    rows = db.execute(
                        f"SELECT {pk} AS pk, subcategoria FROM {tabla} WHERE UPPER(categoria)='SUSCRIPCIONES'"
                    ).fetchall()
                    for row in rows:
                        sub = (row['subcategoria'] or '').strip()
                        db.execute(
                            f"UPDATE {tabla} SET categoria='DIGITAL', subcategoria=? WHERE {pk}=?",
                            (sub if sub in _validas_digital else '', row['pk']),
                        )
                        n_sobrantes += 1
                if n_sobrantes:
                    detalle.append(f"SUSCRIPCIONES sobrantes->DIGITAL: {n_sobrantes}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_unifica_suscripciones_2026_09",
                     "Unifica la categoría legacy SUSCRIPCIONES dentro de DIGITAL (o "
                     "DEPORTE/Gym, PROYECTOS/Hosting según subcategoria) -- corrige "
                     "est_keywords Y est_movimientos, y consolida 'saldo teléfono' en "
                     "DIGITAL/Celular igual que ya hace SERVICIOS. " +
                     (" | ".join(detalle) if detalle else "nada que corregir"))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_unifica_suscripciones_2026_09 migration warning: {e}")

        # ── DÍAITA — Nutrición FODMAP ────────────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS nutricion_semana (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start   TEXT    NOT NULL,
            day_key      TEXT    NOT NULL,
            slot         TEXT    NOT NULL,
            time_str     TEXT    DEFAULT '00:00',
            name         TEXT    NOT NULL,
            kcal         INTEGER DEFAULT 0,
            protein      REAL    DEFAULT 0,
            tag          TEXT    DEFAULT 'safe',
            note         TEXT    DEFAULT '',
            items_json   TEXT    DEFAULT '[]',
            swap         TEXT    DEFAULT '',
            custom       INTEGER DEFAULT 0,
            done         INTEGER DEFAULT 0,
            symptom      TEXT    DEFAULT NULL,
            sym_tags_json TEXT   DEFAULT '[]',
            xp           INTEGER DEFAULT 12,
            created_at   TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS nutricion_deslices (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT    NOT NULL,
            trig_id   TEXT    NOT NULL,
            label     TEXT    NOT NULL,
            glyph     TEXT    DEFAULT '',
            pen       INTEGER DEFAULT 0,
            over      INTEGER DEFAULT 0,
            note      TEXT    DEFAULT '',
            created_at TEXT   DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS nutricion_bristol (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL,
            valor      INTEGER NOT NULL,
            created_at TEXT    DEFAULT (datetime('now'))
        );
        """)

        # ── EURYTHMIA — Salsa ────────────────────────────────────────────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS eury_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT    NOT NULL,
            min             INTEGER NOT NULL,
            split_diso      INTEGER NOT NULL,
            split_paso      INTEGER NOT NULL,
            split_improv    INTEGER NOT NULL,
            step            TEXT    DEFAULT '',
            flow            INTEGER NOT NULL,
            improv_note     TEXT    DEFAULT '',
            xp              INTEGER NOT NULL,
            grabado         INTEGER DEFAULT 0,
            activity_log_id INTEGER DEFAULT NULL,
            created_at      TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS eury_repertoire (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT    NOT NULL,
            step_key    TEXT    NOT NULL UNIQUE,
            name        TEXT    NOT NULL,
            note        TEXT    DEFAULT '',
            mastery     INTEGER DEFAULT 0,
            reps        INTEGER DEFAULT 0,
            created_at  TEXT    NOT NULL
        );
        """)

        # ── HARMA — Mecánica y mantenimiento del carro (submódulo de Ataraxia) ─
        db.executescript("""
        CREATE TABLE IF NOT EXISTS harma_vehiculo (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT    NOT NULL DEFAULT 'Mi carro',
            marca          TEXT    DEFAULT '',
            modelo         TEXT    DEFAULT '',
            anio           INTEGER DEFAULT NULL,
            placas         TEXT    DEFAULT '',
            km_actual      INTEGER DEFAULT 0,
            km_actualizado TEXT    DEFAULT NULL,
            created_at     TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS harma_servicios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo            TEXT    NOT NULL DEFAULT 'otro',
            titulo          TEXT    NOT NULL,
            descripcion     TEXT    DEFAULT '',
            km              INTEGER DEFAULT NULL,
            costo           REAL    DEFAULT 0,
            taller          TEXT    DEFAULT '',
            fecha           TEXT    NOT NULL,
            plan_item_id    TEXT    DEFAULT NULL,
            activity_log_id INTEGER DEFAULT NULL,
            created_at      TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS harma_plan_items (
            id             TEXT PRIMARY KEY,
            cat            TEXT    NOT NULL DEFAULT 'motor',
            name           TEXT    NOT NULL,
            km_interval    INTEGER NOT NULL,
            meses_interval INTEGER NOT NULL,
            last_km        INTEGER DEFAULT 0,
            last_date      TEXT    DEFAULT NULL,
            critical       INTEGER DEFAULT 0,
            desc           TEXT    DEFAULT '',
            created_at     TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS harma_documentos (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo              TEXT    NOT NULL DEFAULT 'seguro',
            titulo            TEXT    NOT NULL,
            nombre_archivo    TEXT    DEFAULT '',
            nombre_original   TEXT    DEFAULT '',
            fecha_vencimiento TEXT    DEFAULT NULL,
            notas             TEXT    DEFAULT '',
            created_at        TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS harma_polizas (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            aseguradora         TEXT    NOT NULL DEFAULT '',
            numero_poliza       TEXT    DEFAULT '',
            vigencia_inicio     TEXT    DEFAULT NULL,
            vigencia_fin        TEXT    DEFAULT NULL,
            prima               REAL    DEFAULT 0,
            deducible           REAL    DEFAULT 0,
            telefono_asistencia TEXT    DEFAULT '',
            notas               TEXT    DEFAULT '',
            nombre_archivo      TEXT    DEFAULT '',
            nombre_original     TEXT    DEFAULT '',
            created_at          TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS harma_siniestros (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha            TEXT    NOT NULL,
            tipo             TEXT    NOT NULL DEFAULT 'otro',
            descripcion      TEXT    DEFAULT '',
            costo_estimado   REAL    DEFAULT 0,
            costo_cubierto   REAL    DEFAULT 0,
            deducible_pagado REAL    DEFAULT 0,
            taller           TEXT    DEFAULT '',
            estado           TEXT    NOT NULL DEFAULT 'reportado',
            poliza_id        INTEGER DEFAULT NULL,
            nombre_archivo   TEXT    DEFAULT '',
            nombre_original  TEXT    DEFAULT '',
            created_at       TEXT    NOT NULL,
            FOREIGN KEY (poliza_id) REFERENCES harma_polizas(id) ON DELETE SET NULL
        );
        """)

        # ── PLANTAS — riego/trasplante (submódulo de Ataraxia, como HARMA) ─────
        # Mismo patrón que harma_plan_items pero cada planta tiene DOS
        # calendarios independientes en vez de uno con doble métrica (km/
        # tiempo) — riego (días) y trasplante (meses) no comparten "el que
        # llegue primero manda", son dos cuidados distintos con su propio
        # last_*/intervalo. El estado (nominal/próximo/urgente/vencido) de
        # cada uno se calcula igual que en HARMA: pct = tiempo_transcurrido
        # / intervalo.
        db.executescript("""
        CREATE TABLE IF NOT EXISTS plantas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre           TEXT    NOT NULL,
            especie          TEXT    DEFAULT '',
            ubicacion        TEXT    DEFAULT '',
            foto             TEXT    DEFAULT NULL,
            dias_riego       INTEGER NOT NULL DEFAULT 7,
            meses_trasplante INTEGER NOT NULL DEFAULT 12,
            last_riego       TEXT    DEFAULT NULL,
            last_trasplante  TEXT    DEFAULT NULL,
            notas            TEXT    DEFAULT '',
            created_at       TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS plantas_bitacora (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            planta_id       INTEGER NOT NULL,
            tipo            TEXT    NOT NULL,
            fecha           TEXT    NOT NULL,
            notas           TEXT    DEFAULT '',
            activity_log_id INTEGER DEFAULT NULL,
            created_at      TEXT    NOT NULL,
            FOREIGN KEY (planta_id) REFERENCES plantas(id) ON DELETE CASCADE
        );
        """)

        # ── FÚTBOL — Historial de partidos (submódulo de Hegemonikon) ──────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS futbol_partidos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha            TEXT    NOT NULL,
            hora             TEXT    DEFAULT '',
            cancha           TEXT    DEFAULT '',
            rival            TEXT    DEFAULT '',
            goles_favor      INTEGER DEFAULT 0,
            goles_contra     INTEGER DEFAULT 0,
            goles_propios    INTEGER DEFAULT 0,
            asistencias      INTEGER DEFAULT 0,
            minutos_jugados  INTEGER DEFAULT NULL,
            rendimiento      REAL    DEFAULT NULL,
            gol_log_id       INTEGER DEFAULT NULL,
            created_at       TEXT    NOT NULL
        );
        """)

        # Migrar futbol_partidos: agregar estado (programado/jugado) — refleja el
        # flujo real: primero se programa el partido (fecha/hora/cancha/rival que
        # mandan), y después de jugarlo se registra el resultado y rendimiento.
        # Las filas existentes ya tienen resultado, así que su default es 'jugado'.
        try:
            fb_cols = [r["name"] for r in db.execute("PRAGMA table_info(futbol_partidos)").fetchall()]
            if "estado" not in fb_cols:
                db.execute("ALTER TABLE futbol_partidos ADD COLUMN estado TEXT DEFAULT 'jugado'")
                db.commit()
        except Exception as e:
            print(f"[DB] futbol_partidos estado migration warning: {e}")

        # ── PAIDEIA — Control de lectura (submódulo de Conocimiento) ───────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS paideia_libros (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo           TEXT    NOT NULL,
            autor            TEXT    DEFAULT '',
            categoria        TEXT    NOT NULL DEFAULT 'Otro',
            estado           TEXT    NOT NULL DEFAULT 'por_leer',
            paginas_totales  INTEGER DEFAULT NULL,
            paginas_actuales INTEGER DEFAULT 0,
            rating           INTEGER DEFAULT NULL,
            fecha_inicio     TEXT    DEFAULT NULL,
            fecha_fin        TEXT    DEFAULT NULL,
            notas            TEXT    DEFAULT '',
            created_at       TEXT    NOT NULL
        );
        """)

        # Migrate paideia_libros: portada (URL de la carátula vía OpenLibrary Covers API)
        try:
            pl_cols = [r["name"] for r in db.execute("PRAGMA table_info(paideia_libros)").fetchall()]
            if "portada" not in pl_cols:
                db.execute("ALTER TABLE paideia_libros ADD COLUMN portada TEXT DEFAULT NULL")
            db.commit()
        except Exception as e:
            print(f"[DB] paideia_libros portada migration warning: {e}")

        # Migrate paideia_libros: progreso_pct (seguimiento por % en vez de
        # páginas — el conteo de páginas de una edición Kindle/ebook casi
        # nunca coincide con el de la edición física que se registró)
        try:
            pl_cols = [r["name"] for r in db.execute("PRAGMA table_info(paideia_libros)").fetchall()]
            if "progreso_pct" not in pl_cols:
                db.execute("ALTER TABLE paideia_libros ADD COLUMN progreso_pct INTEGER DEFAULT NULL")
            db.commit()
        except Exception as e:
            print(f"[DB] paideia_libros progreso_pct migration warning: {e}")

        # Ranking de películas dentro de PAIDEIA — mismo patrón que eury_albums
        # (Música dentro de EURYTHMIA): tabla propia + sub-ratings 1-10 que
        # promedian a mi_rating + XP/EC al calificar. A diferencia de álbumes
        # (semilla fija del Top 100 de Apple Music) no hay lista canónica de
        # películas, así que aquí sí se agregan/borran a mano desde la UI.
        db.executescript("""
        CREATE TABLE IF NOT EXISTS paideia_peliculas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo       TEXT    NOT NULL,
            director     TEXT    DEFAULT '',
            anio         INTEGER,
            genero       TEXT    DEFAULT '',
            vista        INTEGER NOT NULL DEFAULT 0,
            mi_rating    REAL,
            notas        TEXT    DEFAULT '',
            vista_at     TEXT,
            rating_guion      INTEGER DEFAULT NULL,
            rating_actuacion  INTEGER DEFAULT NULL,
            rating_direccion  INTEGER DEFAULT NULL,
            rating_rewatch    INTEGER DEFAULT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)

        # Migrate paideia_peliculas: portada (póster vía iTunes Search API,
        # mismo patrón que paideia_libros + OpenLibrary Covers)
        try:
            pp_cols = [r["name"] for r in db.execute("PRAGMA table_info(paideia_peliculas)").fetchall()]
            if "portada" not in pp_cols:
                db.execute("ALTER TABLE paideia_peliculas ADD COLUMN portada TEXT DEFAULT NULL")
            db.commit()
        except Exception as e:
            print(f"[DB] paideia_peliculas portada migration warning: {e}")

        # Migrate lang_journal / lang_test_results: fase, destreza, idioma explícitos
        # (antes de esto el progreso de idiomas quedaba como actividad suelta, sin
        # poder filtrarse por fase de un plan de estudio ni por destreza).
        try:
            lj_cols = [r["name"] for r in db.execute("PRAGMA table_info(lang_journal)").fetchall()]
            if "fase" not in lj_cols:
                db.execute("ALTER TABLE lang_journal ADD COLUMN fase INTEGER DEFAULT NULL")
            if "destreza" not in lj_cols:
                db.execute("ALTER TABLE lang_journal ADD COLUMN destreza TEXT DEFAULT ''")
            lt_cols = [r["name"] for r in db.execute("PRAGMA table_info(lang_test_results)").fetchall()]
            if "idioma" not in lt_cols:
                db.execute("ALTER TABLE lang_test_results ADD COLUMN idioma TEXT DEFAULT ''")
            if "destreza" not in lt_cols:
                db.execute("ALTER TABLE lang_test_results ADD COLUMN destreza TEXT DEFAULT ''")
            db.commit()
        except Exception as e:
            print(f"[DB] lang_journal/lang_test_results fase/destreza migration warning: {e}")

        # Seed de las 4 fases del plan C1 (26 semanas) — solo si la tabla está vacía
        if db.execute("SELECT COUNT(*) as c FROM lang_plan_checkpoints").fetchone()["c"] == 0:
            db.executemany(
                "INSERT INTO lang_plan_checkpoints (fase, nombre, semana_fin, criterio) VALUES (?,?,?,?)",
                [
                    (1, "Diagnóstico y cierre de brechas", 6,
                     'Cero recurrencia de tu "top 10" de errores en producción escrita controlada.'),
                    (2, "Expansión de rango", 14,
                     "80%+ de comprensión relevante en un podcast nativo estándar, sin apoyo."),
                    (3, "Producción y automatización", 22,
                     "Ensayos en banda C1 de corrección de forma consistente (no ocasional)."),
                    (4, "Consolidación y examen", 26,
                     "Puntaje de mock exam en rango C1, en inglés y en francés."),
                ]
            )
            db.commit()

        # Seed vehículo por defecto (una fila — se edita desde la UI)
        if db.execute("SELECT COUNT(*) as c FROM harma_vehiculo").fetchone()["c"] == 0:
            import datetime as _dth
            db.execute(
                "INSERT INTO harma_vehiculo (nombre, km_actual, created_at) VALUES (?,?,?)",
                ("Mi carro", 0, _dth.datetime.now().isoformat())
            )

        # Migrate harma_vehiculo: add motor/color if missing
        try:
            hv_cols = [r["name"] for r in db.execute("PRAGMA table_info(harma_vehiculo)").fetchall()]
            if "motor" not in hv_cols:
                db.execute("ALTER TABLE harma_vehiculo ADD COLUMN motor TEXT DEFAULT ''")
            if "color" not in hv_cols:
                db.execute("ALTER TABLE harma_vehiculo ADD COLUMN color TEXT DEFAULT ''")
            db.commit()
        except Exception as e:
            print(f"[DB] harma_vehiculo motor/color migration warning: {e}")

        # Migrate harma_servicios: add plan_item_id if missing (tablas creadas antes de esta versión)
        try:
            hs_cols = [r["name"] for r in db.execute("PRAGMA table_info(harma_servicios)").fetchall()]
            if "plan_item_id" not in hs_cols:
                db.execute("ALTER TABLE harma_servicios ADD COLUMN plan_item_id TEXT DEFAULT NULL")
                db.commit()
        except Exception as e:
            print(f"[DB] harma_servicios plan_item_id migration warning: {e}")

        # Seed plan de mantenimiento (catálogo VAG de referencia, arranca desde el km/fecha actual)
        if db.execute("SELECT COUNT(*) as c FROM harma_plan_items").fetchone()["c"] == 0:
            import datetime as _dthp
            _veh = db.execute("SELECT km_actual FROM harma_vehiculo ORDER BY id LIMIT 1").fetchone()
            _base_km = _veh["km_actual"] if _veh else 0
            _base_fecha = _dthp.date.today().isoformat()
            _now_p = _dthp.datetime.now().isoformat()
            db.executemany(
                "INSERT INTO harma_plan_items (id, cat, name, km_interval, meses_interval, last_km, last_date, critical, desc, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    ("aceite",     "motor",      "Aceite motor + filtro",       10000,  12, _base_km, _base_fecha, 1, "5W-30 long-life · filtro original", _now_p),
                    ("aire",       "motor",      "Filtro de aire",               30000,  24, _base_km, _base_fecha, 0, "Sustitución cada 2 años o intervalo de km", _now_p),
                    ("habitaculo", "motor",      "Filtro de habitáculo",         15000,  12, _base_km, _base_fecha, 0, "Filtro de polen / antipolvo", _now_p),
                    ("combust",    "motor",      "Filtro de combustible",        60000,  48, _base_km, _base_fecha, 1, "Crítico en diésel · evita averías de bomba", _now_p),
                    ("bujias",     "motor",      "Bujías de calentamiento",      60000,  60, _base_km, _base_fecha, 0, "Solo TDI · revisar arranque en frío", _now_p),
                    ("balDel",     "frenos",     "Balatas delanteras",           40000,  48, _base_km, _base_fecha, 1, "Inspección visual cada 10,000 km", _now_p),
                    ("balTra",     "frenos",     "Balatas traseras",             70000,  60, _base_km, _base_fecha, 0, "Desgaste menor que delanteras", _now_p),
                    ("discDel",    "frenos",     "Discos delanteros",            80000,  60, _base_km, _base_fecha, 1, "Cambio recomendado cada 2 juegos de balatas", _now_p),
                    ("discTra",    "frenos",     "Discos traseros",             120000,  96, _base_km, _base_fecha, 0, "Inspección de espesor mínimo", _now_p),
                    ("liqFre",     "fluidos",    "Líquido de frenos",            30000,  24, _base_km, _base_fecha, 0, "DOT 4 · higroscópico, caduca por tiempo", _now_p),
                    ("amort",      "suspension", "Amortiguadores",                80000,  84, _base_km, _base_fecha, 1, "Test de rebote · revisar fugas", _now_p),
                    ("alineacion", "suspension", "Alineación y balanceo",         10000,  12, _base_km, _base_fecha, 0, "Cada cambio de neumáticos o golpe", _now_p),
                    ("distrib",    "trans",      "Correa de distribución",       120000,  60, _base_km, _base_fecha, 1, "CRÍTICO · rotura = motor destruido", _now_p),
                    ("accesorios", "trans",      "Correa de accesorios",          90000,  72, _base_km, _base_fecha, 0, "Alternador, A/C, dirección asistida", _now_p),
                    ("aceiteCaja", "trans",      "Aceite de caja",                60000,  60, _base_km, _base_fecha, 0, "Manual: 75W · revisar fugas", _now_p),
                    ("embrague",   "trans",      "Embrague",                     150000, 120, _base_km, _base_fecha, 0, "Solo si hay patinaje o pedal duro", _now_p),
                    ("neumaticos", "rodaje",     "Neumáticos",                    50000,  60, _base_km, _base_fecha, 1, "Revisar dibujo · TWI · presión semanal", _now_p),
                    ("bateria",    "rodaje",     "Batería 12V",                   99999,  60, _base_km, _base_fecha, 0, "Test de carga · cambiar cada 4-5 años", _now_p),
                    ("anticong",   "fluidos",    "Anticongelante",                60000,  48, _base_km, _base_fecha, 0, "G13 · sustitución integral cada 4 años", _now_p),
                ]
            )

        # Seed repertoire (real starting point: mastery/reps en 0)
        if db.execute("SELECT COUNT(*) as c FROM eury_repertoire").fetchone()["c"] == 0:
            import datetime as _dte
            _now = _dte.datetime.now().isoformat()
            db.executemany(
                "INSERT INTO eury_repertoire (kind, step_key, name, note, mastery, reps, created_at) VALUES (?,?,?,?,0,0,?)",
                [
                    ("libres", "guapea",    "Guapea",               "Base del casino",        _now),
                    ("libres", "basico",    "Paso básico / marcaje","Peso y tiempo",           _now),
                    ("libres", "suelta",    "Suelta (shine)",       "Footwork en solo",        _now),
                    ("libres", "despelote", "Despelote",             "Cadera afrocubana",       _now),
                    ("libres", "son",       "Son básico",            "Contratiempo, elegante",  _now),
                    ("libres", "rumba",     "Rumba / guaguancó",     "Cuerpo y vacunao",        _now),
                    ("pareja", "dileque",   "Dile que no",           "Figura fundamental",      _now),
                    ("pareja", "enchufla",  "Enchufla",              "Cambio y giro",           _now),
                    ("pareja", "enchufla2", "Enchufla doble",        "Dos giros seguidos",      _now),
                    ("pareja", "vacilala",  "Vacílala",              "Exhibición de la dama",   _now),
                    ("pareja", "setenta",   "Setenta",               "Enredo de brazos",        _now),
                    ("pareja", "sombrero",  "Sombrero",              "Brazos sobre la cabeza",  _now),
                    ("pareja", "dame",      "Dame una",              "Base de rueda",           _now),
                    ("pareja", "setenta2",  "Setenta complicado",    "Familia del setenta",     _now),
                ]
            )

        # ── ACTA DIURNA — Definiciones editables (sesión, pilar, tipo) ─────────
        db.executescript("""
        CREATE TABLE IF NOT EXISTS activity_defs (
            key         TEXT PRIMARY KEY,
            label       TEXT    NOT NULL,
            cat         TEXT    NOT NULL DEFAULT '',
            pts         INTEGER NOT NULL DEFAULT 1,
            ec          INTEGER NOT NULL DEFAULT 0,
            tier        TEXT    NOT NULL DEFAULT 'micro',
            session     TEXT,
            pillar      TEXT    NOT NULL,
            type        TEXT    NOT NULL DEFAULT 'touch',
            active      INTEGER NOT NULL DEFAULT 1,
            hidden      INTEGER NOT NULL DEFAULT 0,
            custom      INTEGER NOT NULL DEFAULT 0,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS pillar_focus (
            pillar      TEXT PRIMARY KEY,
            focus_key   TEXT,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)

        if db.execute("SELECT COUNT(*) as c FROM activity_defs").fetchone()["c"] == 0:
            db.executemany(
                """INSERT INTO activity_defs
                   (key, label, cat, pts, ec, tier, session, pillar, type, active, hidden, custom, sort_order)
                   VALUES (?,?,?,?,?,?,?,?,?,1,0,0,?)""",
                [
                    # ── Mañana ───────────────────────────────────────────────
                    ("tender_cama",         "Tender cama",                      "Orden",         1, 0, "micro",    "morning", "atar",   "touch", 1),
                    ("jugo_verde",          "Jugo verde",                       "Salud Base",    2, 0, "micro",    "morning", "hege",   "touch", 2),
                    ("comer_fruta",         "Comer fruta",                      "Salud Base",    1, 0, "micro",    "morning", "hege",   "touch", 3),
                    ("meditar",             "Meditar",                          "Salud Mental",  2, 0, "micro",    "morning", "hege",   "touch", 4),
                    ("dormir_8h",           "Dormir 8 horas",                   "Salud Base",    2, 0, "micro",    "morning", "hege",   "touch", 5),
                    ("outfit",              "Outfit cuidado / presencia",       "Identidad",     1, 0, "micro",    "morning", "eury",   "touch", 6),
                    ("llegar_puntual",      "Llegar Puntual",                   "Identidad",     4, 1, "progreso", "morning", "atar",   "touch", 7),
                    ("mit",                 "Most Important Task",              "Ataraxia",      2, 0, "micro",    "morning", "atar",   "touch", 8),
                    ("recuperacion_fisica", "Recuperación física",              "Hegemonikon",   1, 0, "micro",    "morning", "hege",   "touch", 9),
                    ("visualizacion",       "Visualización mental",             "Hegemonikon",   1, 0, "micro",    "morning", "hege",   "touch", 10),
                    # ── Tarde ────────────────────────────────────────────────
                    ("gym",                 "Ejercicio Gym",                    "Salud Física",  4, 1, "progreso", "afternoon", "hege", "ancla", 1),
                    ("sololearn",           "Lección SoloLearn / Mimo",         "Programación",  1, 0, "micro",    "afternoon", "logoi","touch", 2),
                    ("leer_prog",           "Leer programación",                "Programación",  2, 0, "micro",    "afternoon", "logoi","touch", 3),
                    ("python100",           "Lección 100 Días Python",          "Programación",  2, 1, "progreso", "afternoon", "logoi","touch", 4),
                    ("ccna",                "Curso CCNA / Frontend",            "Programación",  3, 1, "progreso", "afternoon", "logoi","touch", 5),
                    ("resolver_codigo",     "Resolver 5 problemas reales",      "Programación",  6, 2, "alto",     "afternoon", "logoi","touch", 6),
                    ("github",              "Subir proyecto a GitHub",          "Programación",  8, 3, "alto",     "afternoon", "logoi","touch", 7),
                    ("leccion_idiomas",     "Lecciones idiomas",                "Idiomas",       2, 1, "progreso", "afternoon", "cosmo","touch", 8),
                    ("conversacion",        "Conversación real 10min+",         "Idiomas",       5, 2, "alto",     "afternoon", "cosmo","touch", 9),
                    ("pliometria",          "Pliometría",                       "Salud Física",  3, 1, "progreso", "afternoon", "hege", "touch", 10),
                    ("abdominales",         "Abdominales",                      "Salud Física",  2, 0, "micro",    "afternoon", "hege", "touch", 11),
                    ("gymbook",             "GymBook",                          "Salud Física",  2, 0, "micro",    "afternoon", "hege", "touch", 12),
                    ("leer_general",        "Leer 5 páginas",                   "Paideia",       1, 0, "micro",    "afternoon", "paideia","touch", 13),
                    ("registrar_gastos",    "Registrar gastos",                 "Finanzas",      2, 1, "progreso", "afternoon", "oiko", "touch", 14),
                    ("planchar",            "Planchar ropa",                    "Orden",         2, 1, "progreso", "afternoon", "atar", "touch", 15),
                    # ── Noche ────────────────────────────────────────────────
                    ("skincare_noche",      "Skin Care nocturno",               "Salud Base",    2, 0, "micro",    "night", "hege",     "touch", 1),
                    ("leer_psico",          "Leer psicología",                  "Paideia",       1, 0, "micro",    "night", "paideia",  "touch", 2),
                    ("leer_365_dias",       "Leer 365 días",                    "Paideia",       1, 0, "micro",    "night", "paideia",  "touch", 3),
                    ("brilliant",           "Lección Brilliant",                "Paideia",       2, 1, "progreso", "night", "paideia",  "touch", 4),
                    ("correccion_diaria",   "Corrección diaria",                "Hegemonikon",   1, 0, "micro",    "night", "hege",     "touch", 5),
                    ("ritual_nocturno",     "Ritual nocturno de preparación",   "Ataraxia",      1, 0, "micro",    "night", "atar",     "touch", 6),
                    # ── Cualquier momento ────────────────────────────────────
                    ("podcast_idiomas",     "Podcast en idiomas",               "Idiomas",       1, 0, "micro",    "any", "cosmo",  "touch", 1),
                    ("VividVocab",          "Lección VividVocab",               "Idiomas",       1, 0, "micro",    "any", "cosmo",  "touch", 2),
                    ("colacion",            "Colación saludable",               "Salud Base",    1, 0, "micro",    "any", "hege",   "touch", 3),
                    ("finanzas_udemy",      "Lección finanzas",                 "Finanzas",      2, 1, "progreso", "any", "oiko",   "touch", 4),
                    ("ahorrar",             "Ahorrar dinero (mensual)",         "Finanzas",      6, 3, "alto",     "any", "oiko",   "touch", 5),
                    ("lavar_carro",         "Lavar carro",                      "Orden",         2, 0, "micro",    "any", "atar",   "touch", 6),
                    ("lenguaje_corporal",   "Lenguaje corporal consciente",     "Identidad",     1, 0, "micro",    "any", "eury",   "touch", 7),
                    ("redes_control",       "<3.5h redes sociales",             "Identidad",     4, 1, "progreso", "any", "hege",   "touch", 8),
                    # ── Ocasional — no cuenta para el tier ──────────────────
                    ("partido",             "Partido",                         "Salud Física",  3, 1, "progreso", None, "hege",  "ocasional", 1),
                    ("gol",                 "Gol (bonus partido)",              "Salud Física",  2, 0, "micro",    None, "hege",  "ocasional", 2),
                    ("test_cert",           "Test certificación (DALF/IELTS)",  "Idiomas",       8, 3, "alto",     None, "cosmo", "ocasional", 3),
                ]
            )
            # gbm: auto-log oculto desde el import de estados de cuenta (Finanzas), no checkbox manual
            db.execute(
                """INSERT INTO activity_defs
                   (key, label, cat, pts, ec, tier, session, pillar, type, active, hidden, custom, sort_order)
                   VALUES (?,?,?,?,?,?,?,?,?,1,1,0,?)""",
                ("gbm", "Investigar en GBM", "Finanzas", 2, 1, "progreso", None, "oiko", "touch", 1)
            )

        if db.execute("SELECT COUNT(*) as c FROM pillar_focus").fetchone()["c"] == 0:
            db.execute(
                "INSERT INTO pillar_focus (pillar, focus_key) VALUES (?,?)",
                ("logoi", "resolver_codigo")
            )

        # ── ACTA DIURNA Fase 2 — pilar Philia, gratitud, síntesis activa ───────
        # cadence: 'daily' (default) | 'weekly' — los touches 'weekly' no cuentan
        # en el % diario de touches del tier (ver engine.get_daily_classification),
        # solo en la cobertura de pilares si se registran alguna vez en la semana.
        try:
            ad_cols = [r["name"] for r in db.execute("PRAGMA table_info(activity_defs)").fetchall()]
            if "cadence" not in ad_cols:
                db.execute("ALTER TABLE activity_defs ADD COLUMN cadence TEXT NOT NULL DEFAULT 'daily'")
                db.commit()
        except Exception as e:
            print(f"[DB] activity_defs cadence migration warning: {e}")

        db.executemany(
            """INSERT OR IGNORE INTO activity_defs
               (key, label, cat, pts, ec, tier, session, pillar, type, cadence, active, hidden, custom, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,1,0,0,?)""",
            [
                ("conexion_genuina", "Momento de conexión genuina",        "Philia", 1, 0, "micro",    "any",   "philia", "touch", "daily",  9),
                ("tiempo_calidad",   "Tiempo de calidad sin pantallas",    "Philia", 2, 1, "progreso", "any",   "philia", "touch", "weekly", 10),
                ("networking",       "Acción de networking real",          "Philia", 2, 1, "progreso", "any",   "philia", "touch", "weekly", 11),
                ("gratitud_diaria",  "3 cosas por las que estás agradecido","Hegemonikon", 1, 0, "micro", "night", "hege", "touch", "daily",  7),
                ("sintesis_activa",  "Explicar lo que aprendiste hoy",     "Paideia", 2, 0, "micro",    "night", "paideia", "touch", "daily", 8),
            ]
        )

        # ── ACTA DIURNA Fase 3 — anclas semanales rotativas ─────────────────────
        # days_of_week: CSV de mon/tue/wed/thu/fri/sat/sun, NULL = todos los días
        # (comportamiento por default de todo lo sembrado en Fases 1-2). Estas
        # anclas SÍ ocurren en fin de semana — no chocan con nada porque el
        # checklist diario manual nunca excluyó sábado/domingo (esa exclusión
        # solo aplica al sistema aparte de bloques Sábado Reset/Domingo Strategy).
        # Baile no tiene fila aquí: su "ancla" es eurythmia_session ya existente,
        # ver EURYTHMIA_ANCLA_DAYS en modules/actividades/routes.py.
        try:
            ad_cols2 = [r["name"] for r in db.execute("PRAGMA table_info(activity_defs)").fetchall()]
            if "days_of_week" not in ad_cols2:
                db.execute("ALTER TABLE activity_defs ADD COLUMN days_of_week TEXT")
                db.commit()
        except Exception as e:
            print(f"[DB] activity_defs days_of_week migration warning: {e}")

        db.executemany(
            """INSERT OR IGNORE INTO activity_defs
               (key, label, cat, pts, ec, tier, session, pillar, type, cadence, days_of_week, active, hidden, custom, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,1,0,0,?)""",
            [
                ("ancla_ccna_prog",  "CCNA / Programación — sesión profunda", "Programación", 8, 3, "alto", "afternoon", "logoi",   "ancla", "daily", "mon,wed,fri", 16),
                ("ancla_ingles",     "Inglés — sesión profunda",              "Idiomas",       6, 2, "alto", "afternoon", "cosmo",   "ancla", "daily", "mon,thu",     17),
                ("ancla_frances",    "Francés — sesión profunda",             "Idiomas",       6, 2, "alto", "afternoon", "cosmo",   "ancla", "daily", "tue,fri",     18),
                ("ancla_leer_psico", "Leer psicología — sesión profunda",     "Paideia",       6, 2, "alto", "night",     "paideia", "ancla", "daily", "sun",         9),
            ]
        )

        # ── ACTA DIURNA Fase 4 — limpieza: retira touches Fase 1 que quedaron
        # duplicados por las anclas semanales de Fase 3 (mismo tema: CCNA y
        # sesión profunda de idiomas — 'ccna'/'leccion_idiomas' promovidos a
        # ancla por el foco del mes chocaban visualmente con 'ancla_ccna_prog'/
        # 'ancla_ingles'/'ancla_frances', y aparecían incluso los días en que
        # la ancla semanal no tocaba). También mueve "Leer 5 páginas" a la
        # sesión Noche (quedó en Tarde desde Fase 1, antes de que existiera
        # bloque de lectura nocturno). Con guard de migration_log para que
        # sea de una sola vez y no pelee con ediciones manuales futuras.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='acta_diurna_fase4_cleanup'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET active=0 WHERE key IN ('ccna','leccion_idiomas')")
            db.execute("DELETE FROM pillar_focus WHERE focus_key IN ('ccna','leccion_idiomas')")
            db.execute("UPDATE activity_defs SET session='night' WHERE key='leer_general'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("acta_diurna_fase4_cleanup",
                 "Retira 'ccna'/'leccion_idiomas' (Fase 1, duplicaban anclas Fase 3) y mueve 'Leer 5 páginas' a sesión Noche.")
            )

        # ── ACTA DIURNA — separa 'python100' de 'ancla_ccna_prog' (2026-09):
        # 'python100' ("Lección 100 Días Python") se quedó sin restricción de
        # días desde Fase 1, así que aparecía TODOS los días — incluyendo
        # lunes/miércoles/viernes, cuando además toca 'ancla_ccna_prog' ("CCNA
        # / Programación — sesión profunda"). Dos sesiones de programación
        # pesadas el mismo día. Se reparten en días alternos sin choque:
        # CCNA lun/mié/vie, Python mar/jue/sáb, domingo libre de programación.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='python_ccna_dias_alternos_2026_09'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET days_of_week='tue,thu,sat' WHERE key='python100'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("python_ccna_dias_alternos_2026_09",
                 "'python100' pasa de sin restricción a days_of_week='tue,thu,sat' para no chocar con "
                 "'ancla_ccna_prog' (mon,wed,fri).")
            )

        # ── ACTA DIURNA — "Podcast en idiomas" pasa de "cualquier momento" a
        # las tres sesiones fijas (Mañana/Tarde/Noche). El campo session admite
        # CSV (igual que days_of_week) — get_active_grouped() lo reparte en
        # cada tarjeta, pero sigue siendo una sola actividad/key: se marca una
        # vez y aparece completada en las tres a la vez.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='podcast_idiomas_multisesion'"
        ).fetchone():
            db.execute(
                "UPDATE activity_defs SET session='morning,afternoon,night' WHERE key='podcast_idiomas'"
            )
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("podcast_idiomas_multisesion",
                 "'Podcast en idiomas' pasa de sesión 'any' a 'morning,afternoon,night'.")
            )

        # ── ACTA DIURNA — retira "Planchar ropa" del checklist (soft delete,
        # el historial en activity_logs queda intacto).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='planchar_ropa_retirado'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET active=0 WHERE key='planchar'")
            db.execute("DELETE FROM pillar_focus WHERE focus_key='planchar'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("planchar_ropa_retirado", "Retira 'Planchar ropa' del checklist de Acta Diurna.")
            )

        # ── ACTA DIURNA — reforma de hábitos de Mañana (2026-08):
        # - "Podcast en idiomas" regresa de las 3 sesiones fijas a solo
        #   "cualquier momento" (revierte 'podcast_idiomas_multisesion').
        # - "Comer fruta" pasa de Mañana a "cualquier momento".
        # - "Jugo verde" se restringe a lunes/miércoles/sábado (days_of_week).
        # - "Outfit cuidado / presencia" se retira del checklist (soft delete).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='acta_diurna_manana_reshape_2026_08'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET session='any' WHERE key='podcast_idiomas'")
            db.execute("UPDATE activity_defs SET session='any' WHERE key='comer_fruta'")
            db.execute("UPDATE activity_defs SET days_of_week='mon,wed,sat' WHERE key='jugo_verde'")
            db.execute("UPDATE activity_defs SET active=0 WHERE key='outfit'")
            db.execute("DELETE FROM pillar_focus WHERE focus_key='outfit'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("acta_diurna_manana_reshape_2026_08",
                 "Podcast en idiomas -> solo 'any'; Comer fruta -> 'any'; Jugo verde -> mon,wed,sat; Outfit retirado.")
            )

        # ── ACTA DIURNA — días de mes (equivalente a days_of_week pero para
        # touches ligados a fechas del calendario, no del ciclo semanal).
        # CSV de números de día (1-31) o el token especial "last" (último día
        # real del mes — 28/29/30/31 según corresponda, ver eligible_today())
        # para no depender de un número fijo que nunca ocurre en meses cortos.
        try:
            ad_cols3 = [r["name"] for r in db.execute("PRAGMA table_info(activity_defs)").fetchall()]
            if "days_of_month" not in ad_cols3:
                db.execute("ALTER TABLE activity_defs ADD COLUMN days_of_month TEXT")
                db.commit()
        except Exception as e:
            print(f"[DB] activity_defs days_of_month migration warning: {e}")

        # ── ACTA DIURNA — "Ahorrar dinero (mensual)" solo tiene sentido
        # revisarlo al cierre del mes (para saber si de verdad se ahorró),
        # no cualquier día — se restringe al último día del mes.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='ahorrar_fin_de_mes'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET days_of_month='last' WHERE key='ahorrar'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("ahorrar_fin_de_mes",
                 "'Ahorrar dinero (mensual)' se restringe al último día del mes (days_of_month='last').")
            )

        # ── ACTA DIURNA — contenido de texto para los touches reflexivos
        # (gratitud, corrección diaria, síntesis de aprendizaje). Fase 1:
        # solo captura y persiste el texto (editable, un registro por
        # key+fecha) para que una fase futura pueda armar un recuento
        # mensual. No hay reporte mensual todavía.
        db.executescript("""
        CREATE TABLE IF NOT EXISTS reflexion_diaria (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_key  TEXT NOT NULL,
            date          TEXT NOT NULL,
            texto         TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(activity_key, date)
        );
        """)

        # ── ACTA DIURNA — "Ritual nocturno de preparación" pasa antes de las
        # tarjetas de reflexión (Corrección diaria, que ahora ocupa el ancho
        # completo con su textarea): quedaba una tarjeta compacta encajada
        # entre dos de ancho completo, se veía desordenado.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='ritual_nocturno_antes_de_reflexion'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET sort_order=5 WHERE key='ritual_nocturno'")
            db.execute("UPDATE activity_defs SET sort_order=6 WHERE key='correccion_diaria'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("ritual_nocturno_antes_de_reflexion",
                 "'Ritual nocturno de preparación' se mueve antes de 'Corrección diaria' para agrupar las tarjetas de reflexión (ancho completo) juntas.")
            )

        # ── ACTA DIURNA — "<3.5h redes sociales" (redes_control) se retira:
        # es redundante con el campo "Pantalla en redes" (screen_time_horas)
        # que ya existe en la Revisión Semanal de Ataraxia.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='redes_control_retirado'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET active=0 WHERE key='redes_control'")
            db.execute("DELETE FROM pillar_focus WHERE focus_key='redes_control'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("redes_control_retirado",
                 "Retira '<3.5h redes sociales' del checklist — ya cubierto por 'Pantalla en redes' en la Revisión Semanal de Ataraxia.")
            )

        # ── ACTA DIURNA — intervalo de N semanas anclado a una fecha (para
        # touches que no son ni diarios ni semanales fijos, ej. "cada 3
        # semanas"). interval_weeks=NULL = sin restricción de intervalo
        # (comportamiento actual, solo days_of_week si aplica). Con
        # interval_weeks seteado, además de cumplir days_of_week, se exige
        # que (fecha - interval_anchor).days sea múltiplo de interval_weeks*7
        # — ver eligible_today() en modules/actividades/activity_defs.py.
        try:
            ad_cols4 = [r["name"] for r in db.execute("PRAGMA table_info(activity_defs)").fetchall()]
            if "interval_weeks" not in ad_cols4:
                db.execute("ALTER TABLE activity_defs ADD COLUMN interval_weeks INTEGER")
                db.commit()
            if "interval_anchor" not in ad_cols4:
                db.execute("ALTER TABLE activity_defs ADD COLUMN interval_anchor TEXT")
                db.commit()
        except Exception as e:
            print(f"[DB] activity_defs interval_weeks migration warning: {e}")

        # ── ACTA DIURNA — "Lavar carro" pasa de "cualquier momento, todos
        # los días" a cada 3 semanas en domingo, empezando el domingo 23 de
        # agosto de 2026 (ese domingo cuenta como la 1ª aparición; la
        # siguiente es 3 domingos después: 13 sep, luego 4 oct, ...).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='lavar_carro_cada_3_domingos'"
        ).fetchone():
            db.execute(
                "UPDATE activity_defs SET session='any', days_of_week='sun', "
                "interval_weeks=3, interval_anchor='2026-08-23' WHERE key='lavar_carro'"
            )
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("lavar_carro_cada_3_domingos",
                 "'Lavar carro' se restringe a domingo cada 3 semanas, ancla 2026-08-23 (siguiente: 2026-09-13).")
            )

        # ── ACTA DIURNA — "Registrar gastos" se retira del checklist diario
        # (Tarde) y pasa a ser una tarea del bloque "Cierre Semanal" de
        # Ataraxia (domingo), junto al cierre de la semana.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='registrar_gastos_a_ataraxia_cierre'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET active=0 WHERE key='registrar_gastos'")
            db.execute("DELETE FROM pillar_focus WHERE focus_key='registrar_gastos'")
            if not db.execute(
                "SELECT id FROM rutina_bloques WHERE id='sun_cierre_gastos'"
            ).fetchone():
                db.execute(
                    """INSERT INTO rutina_bloques
                       (id, dia, bloque_id, nombre, tier, xp, ec, categoria, opcional, duracion_min, orden)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    ("sun_cierre_gastos", "domingo", "sun_cierre_bloque", "Registrar gastos",
                     "progreso", 2, 1, "HEGEMONIKON", 0, 10, 15)
                )
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("registrar_gastos_a_ataraxia_cierre",
                 "'Registrar gastos' se retira del checklist diario (Tarde) y se agrega como tarea del bloque 'Cierre Semanal' de Ataraxia (domingo).")
            )

        # ── ACTA DIURNA — "Lavar carro" y "Ahorrar dinero (mensual)" se
        # retiran del checklist: ambos quedan duplicados con seguimiento que
        # ya existe en Ataraxia — "Lavar carro" con el servicio "Lavado /
        # detallado" de Harma (registro real con fecha/costo, no un simple
        # check diario), y "Ahorrar dinero" con "Finanzas: gastos semana ·
        # proyección" del bloque Domingo, que ya cubre la proyección de
        # ahorro mensual como parte del cierre semanal.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='lavar_carro_y_ahorrar_retirados'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET active=0 WHERE key IN ('lavar_carro','ahorrar')")
            db.execute("DELETE FROM pillar_focus WHERE focus_key IN ('lavar_carro','ahorrar')")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("lavar_carro_y_ahorrar_retirados",
                 "'Lavar carro' y 'Ahorrar dinero (mensual)' se retiran del checklist diario — ya cubiertos por el "
                 "servicio 'Lavado / detallado' de Harma y por 'Finanzas: gastos semana · proyección' de Ataraxia (domingo).")
            )

        # ── ACTA DIURNA — "solo una vez": actividades creadas desde el form
        # de "+ Agregar actividad" que no se repiten. one_time=1 hace que
        # log_activity() (modules/actividades/routes.py) desactive la
        # actividad automáticamente en cuanto se marca como hecha, en vez de
        # quedar en el checklist para siempre como las recurrentes.
        try:
            ad_cols5 = [r["name"] for r in db.execute("PRAGMA table_info(activity_defs)").fetchall()]
            if "one_time" not in ad_cols5:
                db.execute("ALTER TABLE activity_defs ADD COLUMN one_time INTEGER NOT NULL DEFAULT 0")
                db.commit()
        except Exception as e:
            print(f"[DB] activity_defs one_time migration warning: {e}")

        # ── ACTA DIURNA — "Leer psicología — sesión profunda" se duplica a
        # Martes además de Domingo (no se mueve): paideia sube a 2 sesiones
        # profundas semanales sin perder la de domingo, que cuesta menos
        # esfuerzo real aunque en la tabla de anclas por día se vea vacía.
        # Martes era el día más flojo en anclas (6 pts, solo francés) pero
        # con pocas horas libres reales — se acepta esa carga porque es la
        # única forma de subir paideia a 2x/semana sin tocar domingo.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='ancla_leer_psico_martes_domingo'"
        ).fetchone():
            db.execute("UPDATE activity_defs SET days_of_week='tue,sun' WHERE key='ancla_leer_psico'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("ancla_leer_psico_martes_domingo",
                 "'Leer psicología — sesión profunda' pasa de days_of_week='sun' a 'tue,sun' (duplicación, no movimiento).")
            )

        # ── ACTA DIURNA — quita el foco del mes de Cosmopolitismo ────────────
        # El usuario reportó dos anclas a la vez en Cosmopolitismo: "Francés —
        # sesión profunda" (ancla real, custom) y "Conversación real 10min+"
        # (touch normal en el seed base -- ver activity_defs, session
        # "afternoon" -- que se muestra como ancla solo porque pillar_focus
        # la tiene marcada como foco del mes de "cosmo"; ver _effective_type
        # en modules/actividades/activity_defs.py: un touch cuyo key coincide
        # con el focus_key de su pilar se pinta como ancla sin cambiar su
        # tipo real). Pidió dejarla como touch normal y moverla a "Cualquier
        # momento": se quita el foco del mes de cosmo (deja de promoverse a
        # ancla) y se cambia su session de "afternoon" a "any".
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='acta_diurna_conversacion_a_cualquier_momento'"
        ).fetchone():
            db.execute("DELETE FROM pillar_focus WHERE pillar='cosmo' AND focus_key='conversacion'")
            db.execute("UPDATE activity_defs SET session='any' WHERE key='conversacion'")
            db.execute(
                "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                ("acta_diurna_conversacion_a_cualquier_momento",
                 "'Conversación real 10min+' deja de ser el foco del mes de Cosmopolitismo "
                 "(deja de mostrarse como ancla) y pasa de session='afternoon' a session='any' "
                 "(Cualquier momento). 'Francés — sesión profunda' queda como la única ancla "
                 "de Cosmopolitismo.")
            )
            db.commit()

        # ALIMENTACION se separa en SUPER (Súper/Conveniencia -> Necesidades)
        # y COMIDA_FUERA (Restaurante/Fast Food/Delivery -> Deseos). El usuario
        # lo pidió porque juntas inflaban «Necesidades» del 50-30-20 (~$3,300
        # al mes de comida fuera contada como necesidad): "manda en super todo
        # lo que sea conveniencia y super como categoria y deja comida afuera
        # como otra categoria y subcategoria fast food, restaurante y
        # delivery". Se corrigen movimientos, reglas guardadas (est_keywords,
        # para que no la revivan), el catálogo de naturaleza y el límite de
        # est_budgets. El blindaje contra recurrencia vive en
        # _corregir_alimentacion_split (modules/finanzas/estados/routes.py).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_separa_alimentacion_2026_09'"
        ).fetchone():
            try:
                detalle = []
                from modules.finanzas.estados.config import split_alimentacion
                for tabla, texto in (('est_movimientos', 'descripcion'), ('est_keywords', 'keyword')):
                    filas = db.execute(f"SELECT id, subcategoria, {texto} AS t FROM {tabla} "
                                       f"WHERE categoria='ALIMENTACION'").fetchall()
                    for r in filas:
                        cat, sub = split_alimentacion(r['subcategoria'], r['t'])
                        db.execute(f"UPDATE {tabla} SET categoria=?, subcategoria=? WHERE id=?",
                                   (cat, sub, r['id']))
                    detalle.append(f"{tabla}: {len(filas)}")

                for cat, sub, nat in [('SUPER', 'Súper', 'VARIABLE'), ('SUPER', 'Conveniencia', 'VARIABLE'),
                                      ('COMIDA_FUERA', 'Restaurante', 'VARIABLE'),
                                      ('COMIDA_FUERA', 'Fast Food', 'VARIABLE'),
                                      ('COMIDA_FUERA', 'Delivery', 'VARIABLE')]:
                    db.execute("INSERT OR IGNORE INTO est_categoria_naturaleza (categoria, subcategoria, naturaleza) "
                               "VALUES (?,?,?)", (cat, sub, nat))
                db.execute("DELETE FROM est_categoria_naturaleza WHERE categoria='ALIMENTACION'")

                # Límite: el presupuesto original (Excel 2026) era VIVERES/SUPER
                # $2,500 + COMIDA/REST $2,000 = los $4,500 de ALIMENTACION. Si
                # el usuario lo cambió después, se reparte en la misma proporción.
                b = db.execute("SELECT limite FROM est_budgets WHERE categoria='ALIMENTACION'").fetchone()
                if b is not None:
                    lim = float(b['limite'] or 0)
                    sup = 2500.0 if lim == 4500 else round(lim * 2500 / 4500 / 50) * 50
                    for cat, nombre, val in [('SUPER', 'Súper', sup), ('COMIDA_FUERA', 'Comida fuera', lim - sup)]:
                        db.execute("INSERT OR IGNORE INTO est_budgets (categoria, nombre, limite, periodo) "
                                   "VALUES (?,?,?,'mensual')", (cat, nombre, val))
                    db.execute("DELETE FROM est_budgets WHERE categoria='ALIMENTACION'")
                    detalle.append(f"límite {lim:.0f} -> Súper {sup:.0f} + Comida fuera {lim - sup:.0f}")

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_separa_alimentacion_2026_09",
                     "ALIMENTACION -> SUPER (Súper/Conveniencia, Necesidades) + COMIDA_FUERA "
                     "(Restaurante/Fast Food/Delivery, Deseos). " + " | ".join(detalle))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_separa_alimentacion_2026_09 migration warning: {e}")

        # Préstamos: había dos formas de marcarlos (tipo PRESTAMO/COBRO_PRESTAMO,
        # que el editor de movimientos no expone, y categoria PRESTAMOS con el
        # tipo real). El usuario pidió unificarlas en la segunda: categoría
        # PRESTAMOS y tipo GASTO (presté) / INGRESO (me devolvieron), para que
        # se puedan editar desde la app y la dirección no se pierda. No toca
        # fecha/descripcion/monto (la llave única de est_movimientos).
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_prestamos_tipo_real_2026_09'"
        ).fetchone():
            try:
                n1 = db.execute("UPDATE est_movimientos SET tipo='GASTO', categoria='PRESTAMOS' "
                                "WHERE tipo='PRESTAMO'").rowcount
                n2 = db.execute("UPDATE est_movimientos SET tipo='INGRESO', categoria='PRESTAMOS' "
                                "WHERE tipo='COBRO_PRESTAMO'").rowcount
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_prestamos_tipo_real_2026_09",
                     f"tipo PRESTAMO -> GASTO/PRESTAMOS: {n1} | tipo COBRO_PRESTAMO -> INGRESO/PRESTAMOS: {n2}")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_prestamos_tipo_real_2026_09 migration warning: {e}")

        # Meta mínima del grupo Ahorro y deudas en la Radiografía (piso, no
        # tope): valor inicial $4,000. INSERT OR IGNORE: nunca pisa el valor
        # que el usuario ya haya configurado.
        db.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('presupuesto_meta_ahorro', '4000')")
        db.commit()

        # Clasificación de préstamos que el usuario hizo sobre el CSV exportado
        # de «Por cobrar» (prestamos_2026-09-23_corregido.csv) + sus respuestas:
        # 2571 es devolución del 2138 aunque entró como Gasto; 2306 es de
        # Cornelius; 1560 (ABONO) se liga al 1469; de 2130/2077 (mismo día y
        # monto) solo se registra 2130. Sin registrar a propósito: 2077
        # (posible duplicado) y 2999 (sin persona). Cada fila solo se aplica si
        # el id coincide con fecha y monto del CSV; no toca préstamos o ligas
        # que el usuario ya haya hecho a mano.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_prestamos_clasificacion_csv_2026_09'"
        ).fetchone():
            try:
                _prest_csv = [  # (movimiento, fecha, monto, persona)
                    (2306, '2026-07-11', 3400, 'Cornelius'), (2307, '2026-07-10', 1000, 'Judi'),
                    (2138, '2026-06-10', 4500, 'Judi'),      (2088, '2026-05-15', 1000, 'Judi'),
                    (2130, '2026-05-12', 2000, 'Cornelius'), (2073, '2026-05-11', 2000, 'Judi'),
                    (1836, '2026-03-08', 2000, 'Judi'),      (1772, '2026-02-23', 2000, 'Judi'),
                    (1679, '2026-01-25', 4500, 'Judi'),      (1534, '2025-12-15', 150, 'Aurora'),
                    (1469, '2025-11-26', 10000, 'Judi'),     (1444, '2025-11-21', 2000, 'Judi'),
                    (2779, '2025-09-15', 7000, 'Judi'),      (2767, '2025-09-07', 950, 'Judi'),
                    (2810, '2025-08-23', 500, 'Judi'),       (2903, '2025-07-04', 1500, 'Judi'),
                    (2870, '2025-06-11', 412, 'Judi'),       (2864, '2025-06-07', 600, 'Judi'),
                    (3004, '2025-03-27', 2513, 'Judi'),      (3026, '2025-02-23', 500, 'Judi'),
                    (3785, '2023-06-16', 7000, 'Judi'),
                ]
                _dev_csv = [  # (devolución, fecha, monto, movimiento del préstamo)
                    (2571, '2026-09-11', 4500, 2138), (1560, '2025-12-22', 5000, 1469),
                    (2776, '2025-09-11', 7000, 2779), (2898, '2025-07-02', 1500, 2903),
                    (2872, '2025-06-11', 600, 2864),  (3003, '2025-03-27', 2512, 3004),
                    (3028, '2025-02-24', 500, 3026),
                ]

                def _coincide(mid, fecha, monto):
                    r = db.execute("SELECT fecha, monto, tipo FROM est_movimientos WHERE id=?", (mid,)).fetchone()
                    if r and r['fecha'] == fecha and round(abs(float(r['monto'])), 2) == round(float(monto), 2):
                        return r
                    return None

                reg, omit = 0, []
                for mid, fecha, monto, persona in _prest_csv:
                    r = _coincide(mid, fecha, monto)
                    if not r or r['tipo'] != 'GASTO':
                        omit.append(f"préstamo {mid}: no coincide")
                        continue
                    if db.execute("SELECT 1 FROM est_prestamos WHERE movimiento_id=?", (mid,)).fetchone():
                        continue  # ya registrado a mano
                    db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='Prestado' WHERE id=?", (mid,))
                    db.execute(
                        "INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at) "
                        "VALUES (?, 'OTORGADO', ?, ?, 'Clasificado desde CSV', ?, datetime('now'))",
                        (persona, float(monto), fecha, mid))
                    reg += 1

                lig = 0
                for did, fecha, monto, loan_mid in _dev_csv:
                    r = _coincide(did, fecha, monto)
                    p = db.execute("SELECT id FROM est_prestamos WHERE movimiento_id=?", (loan_mid,)).fetchone()
                    if not r or not p:
                        omit.append(f"devolución {did}: {'no coincide' if not r else f'sin préstamo {loan_mid}'}")
                        continue
                    if db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (did,)).fetchone():
                        continue
                    # 2571 entró como Gasto; el usuario confirmó que es dinero que regresó.
                    db.execute("UPDATE est_movimientos SET tipo='INGRESO', categoria='PRESTAMOS', subcategoria='' WHERE id=?", (did,))
                    db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) "
                               "VALUES (?, ?, datetime('now'))", (p['id'], did))
                    lig += 1

                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_prestamos_clasificacion_csv_2026_09",
                     f"Préstamos registrados: {reg} | devoluciones ligadas: {lig}"
                     + (" | omitidos: " + "; ".join(omit) if omit else ""))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_prestamos_clasificacion_csv_2026_09 migration warning: {e}")

        # Saldo de corte de inversiones (modules/finanzas/inversiones.py): el
        # usuario dio sus saldos reales al 2026-09-24 -- CETES 51,124.65, Finsus
        # 102,933.66 y GBM 65,965.58; «no hay otro, eso es todo» -- así que el
        # resto de plataformas arranca en 0. Desde ahí el saldo es el corte +
        # los movimientos posteriores. INSERT OR IGNORE: un ajuste hecho desde
        # la app nunca se pisa. Los movimientos OTRO que mencionan FINSUS pasan
        # a la plataforma nueva.
        db.execute("""
            CREATE TABLE IF NOT EXISTS inv_saldo_base (
                plataforma TEXT PRIMARY KEY,
                saldo      REAL NOT NULL,
                fecha      TEXT NOT NULL,
                updated_at TEXT
            )""")
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='inversiones_saldo_corte_2026_09_24'"
        ).fetchone():
            try:
                for plat, saldo in [('CETES', 51124.65), ('FINSUS', 102933.66), ('GBM', 65965.58),
                                    ('INVEX', 0), ('CRYPTO', 0), ('FIBRA', 0), ('OTRO', 0)]:
                    db.execute("INSERT OR IGNORE INTO inv_saldo_base (plataforma, saldo, fecha, updated_at) "
                               "VALUES (?, ?, '2026-09-24', datetime('now'))", (plat, saldo))
                n = db.execute("UPDATE est_movimientos SET categoria='FINSUS' WHERE tipo='INVERSION' "
                               "AND categoria='OTRO' AND UPPER(descripcion) LIKE '%FINSUS%'").rowcount
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("inversiones_saldo_corte_2026_09_24",
                     f"Corte al 2026-09-24: CETES 51,124.65 · FINSUS 102,933.66 · GBM 65,965.58 · resto 0 | OTRO->FINSUS: {n}")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] inversiones_saldo_corte_2026_09_24 migration warning: {e}")

        # Ancla «Partido de fútbol» (ver activity_defs.ajustar_por_partido): solo
        # aparece los miércoles con partido en futbol_partidos, y ese día
        # sustituye a Ejercicio Gym y GymBook. Mismos puntos y pilar que el gym.
        db.execute("""
            INSERT OR IGNORE INTO activity_defs
              (key, label, cat, pts, ec, tier, session, pillar, type, active, hidden, custom, sort_order, days_of_week)
            VALUES ('partido_futbol', 'Partido de fútbol', 'Salud Física', 4, 1, 'progreso', 'afternoon',
                    'hege', 'ancla', 1, 0, 0, 0, 'wed')""")
        db.commit()

        # Presupuestos: solo los del plan. La carga de límites del plan
        # (finanzas_limites_plan_2026_09) actualizó los 14 del plan pero dejó
        # los del Excel viejo (CASA/HOGAR «Vivienda» $6,000 en $0, MENSUALIDAD,
        # INVERSION, EXPENSE…), que duplicaban tarjetas e inflaban el total del
        # mes. El usuario: «deja las nuevas y borra las antiguas». Se borra todo
        # lo que no está en el plan; los del plan que falten se crean sin pisar
        # los que ya existen (ediciones del usuario). Lo borrado queda en el log.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_presupuesto_solo_plan_2026_09'"
        ).fetchone():
            try:
                from modules.finanzas.presupuesto_plan import PLAN_LIMITES
                plan = [c for c, _, _ in PLAN_LIMITES]
                ph = ','.join('?' * len(plan))
                borrados = db.execute(f"SELECT categoria, nombre, limite FROM est_budgets WHERE categoria NOT IN ({ph})",
                                      plan).fetchall()
                db.execute(f"DELETE FROM est_budgets WHERE categoria NOT IN ({ph})", plan)
                for cat, nombre, lim in PLAN_LIMITES:
                    db.execute("INSERT OR IGNORE INTO est_budgets (categoria, nombre, limite, periodo) "
                               "VALUES (?, ?, ?, 'mensual')", (cat, nombre, lim))
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_presupuesto_solo_plan_2026_09",
                     "Borrados fuera del plan: " + (", ".join(f"{r['categoria']} ({r['nombre']}) {r['limite']:.0f}"
                                                                for r in borrados) or "ninguno"))
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_presupuesto_solo_plan_2026_09 migration warning: {e}")

        # Receta pedida por el usuario: Poke Bowl de quinoa, atún y zanahoria.
        # Solo se inserta si no existe una receta con ese nombre (no duplica
        # si ya la capturó a mano ni si la migración corre de nuevo).
        _poke = "Poke Bowl de Quinoa, Atún Aleta Amarilla y Zanahoria"
        if not db.execute("SELECT 1 FROM recetas WHERE nombre=?", (_poke,)).fetchone():
            try:
                import json as _json
                _ings = [
                    {"item": "Quinoa orgánica (lavada; cocida en 1 taza de agua 12 min)", "cantidad": "1/2", "unidad": "taza"},
                    {"item": "Atún aleta amarilla en cubitos", "cantidad": "200", "unidad": "g"},
                    {"item": "Salsa de soya baja en sodio (marinada)", "cantidad": "1.5", "unidad": "cda"},
                    {"item": "Aceite de ajonjolí tostado (marinada)", "cantidad": "1", "unidad": "cdta"},
                    {"item": "Jugo de limón (marinada)", "cantidad": "1/2", "unidad": "limón"},
                    {"item": "Sal de mar (marinada)", "cantidad": "1", "unidad": "pizca"},
                    {"item": "Zanahoria rallada fina o en tiras delgadas", "cantidad": "1/2", "unidad": "pieza"},
                    {"item": "Aguacate rebanado o en cubos", "cantidad": "1/2", "unidad": "pieza"},
                    {"item": "Ajonjolí negro tostado", "cantidad": "1", "unidad": "cda"},
                ]
                _pasos = [
                    "Quinoa: enjuagar la quinoa bajo el grifo durante 30 segundos. Cocinar con el doble de agua (1 taza) a fuego bajo y tapada durante 12 minutos. Apagar el fuego, dejar reposar 3 minutos y ahuecar con un tenedor.",
                    "Marinada: mezclar los cubitos de atún con la salsa de soya, el aceite de ajonjolí y el jugo de limón. Refrigerar 10 minutos.",
                    "Vegetales: rallar 1/2 zanahoria fina (puedes agregarle unas gotas de limón para mantener la frescura) y cortar el aguacate.",
                    "Ensamblado: colocar la quinoa como cama en el bowl. Añadir el atún marinado, la zanahoria rallada y el aguacate distribuidos en secciones.",
                    "Toque final: espolvorear el ajonjolí negro por encima.",
                ]
                db.execute(
                    """INSERT INTO recetas (nombre, categoria, descripcion, ingredientes, instrucciones, calorias,
                       proteina, carbos, grasa, tiempo_prep, tiempo_coccion, porciones, video_url, tags, favorita, created_at)
                       VALUES (?, 'Post-Entrenamiento', ?, ?, ?, 515, 38, 43, 18, 20, 0, 1, '', ?, 0, datetime('now'))""",
                    (_poke,
                     "Nutrición deportiva · comida principal. Objetivo: alto rendimiento / post-entrenamiento. "
                     "Proteína del atún aleta amarilla y la quinoa, carbohidratos complejos de quinoa y zanahoria, "
                     "grasas saludables del aguacate y el aceite de ajonjolí. Fibra ~7 g · ~500-530 kcal.",
                     _json.dumps(_ings, ensure_ascii=False), _json.dumps(_pasos, ensure_ascii=False),
                     "HighProtein, Quinoa, Atún, Zanahoria, PostWorkout, CleanEating, PokeBowl"))
                db.commit()
            except Exception as e:
                print(f"[DB] receta poke bowl warning: {e}")

        # Límites del plan de presupuesto acordado con el usuario (total ~$20,900
        # con $4,000 de ahorro como meta mínima aparte). Súper va en $2,000 y no
        # en los $1,500 del plan: la limpieza y el cuidado personal comprados en
        # el súper caen en esa categoría (el banco da un cargo por ticket).
        # Viajes = 0 en el plan («se pagan con extras»); en la app un límite 0
        # significa «sin presupuesto», así que se quita su límite. Una sola vez
        # (migration_log): si luego el usuario edita un límite, no se pisa.
        if not db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_limites_plan_2026_09'"
        ).fetchone():
            try:
                _limites = [
                    ('VIVIENDA', 'Vivienda', 6950), ('SUPER', 'Súper', 2000), ('SALUD', 'Salud', 300),
                    ('TRANSPORTE', 'Transporte', 2105), ('CUIDADO_PERSONAL', 'Cuidado personal', 500),
                    ('COMIDA_FUERA', 'Comida fuera', 2200), ('CAFE/PAN', 'Café & Pan', 300),
                    ('DIGITAL', 'Digital', 1246), ('FAMILIA_REGALOS', 'Familia y regalos', 500),
                    ('SALSA', 'Salsa / Baile', 300), ('DEPORTE', 'Deporte', 200), ('ROPA', 'Ropa', 400),
                    ('OCIO', 'Ocio', 200), ('PROYECTOS', 'Proyectos', 200),
                ]
                for cat, nombre, lim in _limites:
                    db.execute(
                        "INSERT INTO est_budgets (categoria, nombre, limite, periodo) VALUES (?, ?, ?, 'mensual') "
                        "ON CONFLICT(categoria) DO UPDATE SET limite=excluded.limite, nombre=excluded.nombre",
                        (cat, nombre, float(lim)))
                n_viajes = db.execute("DELETE FROM est_budgets WHERE categoria='VIAJES'").rowcount
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("finanzas_limites_plan_2026_09",
                     f"{len(_limites)} límites del plan cargados (Súper 2,000); límite de Viajes quitado: {n_viajes}")
                )
                db.commit()
            except Exception as e:
                print(f"[DB] finanzas_limites_plan_2026_09 migration warning: {e}")

        # Migrate rewards: unica — artículos que se compran una sola vez (Kindle,
        # Apple Watch…). Antes solo existía el cooldown, así que al vencer
        # (90 días en el Kindle) la recompensa volvía a aparecer como disponible.
        # Una vez canjeada, una recompensa única queda como «Conseguida».
        try:
            rw_cols = [r["name"] for r in db.execute("PRAGMA table_info(rewards)").fetchall()]
            if "unica" not in rw_cols:
                db.execute("ALTER TABLE rewards ADD COLUMN unica INTEGER DEFAULT 0")
                db.commit()
            if not db.execute(
                "SELECT id FROM migration_log WHERE version='rewards_unica_2026_09'"
            ).fetchone():
                from modules.recompensas.routes import es_unica_por_nombre
                _ids = [r["id"] for r in db.execute("SELECT id, name FROM rewards").fetchall()
                        if es_unica_por_nombre(r["name"])]
                for _id in _ids:
                    db.execute("UPDATE rewards SET unica=1 WHERE id=?", (_id,))
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("rewards_unica_2026_09", f"{len(_ids)} recompensas marcadas como de una sola vez por nombre")
                )
                db.commit()
        except Exception as e:
            print(f"[DB] rewards unica migration warning: {e}")

        # ── RECORDATORIOS — tema (Finanzas / Casa y cuidado / Eventos / Otros)
        # para filtrar con chips. La columna se agrega si falta; el tema se
        # asigna por palabras clave solo a los que no tienen uno (una vez,
        # migration_log), así un tema que el usuario cambió no se pisa.
        try:
            if 'tema' not in [r["name"] for r in db.execute("PRAGMA table_info(reminders)").fetchall()]:
                db.execute("ALTER TABLE reminders ADD COLUMN tema TEXT DEFAULT ''")
                db.commit()
            if not db.execute(
                "SELECT id FROM migration_log WHERE version='recordatorios_tema_2026_09'"
            ).fetchone():
                from modules.perfil.recordatorios import tema_auto
                _rows = db.execute(
                    "SELECT id, description FROM reminders WHERE COALESCE(tema, '') = ''").fetchall()
                for _r in _rows:
                    db.execute("UPDATE reminders SET tema=? WHERE id=?", (tema_auto(_r["description"]), _r["id"]))
                db.execute(
                    "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,datetime('now'))",
                    ("recordatorios_tema_2026_09", f"Tema asignado por palabras clave a {len(_rows)} recordatorios")
                )
                db.commit()
        except Exception as e:
            print(f"[DB] recordatorios_tema_2026_09 migration warning: {e}")

        db.executescript("""
        CREATE TABLE IF NOT EXISTS revision_semanal (
            semana_id         TEXT PRIMARY KEY,
            dias_lectura      REAL,
            horas_sueno       REAL,
            presupuesto_pct   REAL,
            calorias_quemadas REAL,
            screen_time_horas REAL,
            notas             TEXT DEFAULT '',
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS eury_albums (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            rank         INTEGER NOT NULL UNIQUE,
            artista      TEXT NOT NULL,
            album        TEXT NOT NULL,
            anio         INTEGER,
            genero       TEXT DEFAULT '',
            escuchado    INTEGER NOT NULL DEFAULT 0,
            mi_rating    REAL,
            notas        TEXT DEFAULT '',
            escuchado_at TEXT
        );
        """)

        # Migración: sub-ratings cuantitativos (1-10) que promedian a mi_rating
        ea_cols = [r["name"] for r in db.execute("PRAGMA table_info(eury_albums)").fetchall()]
        for col in ("rating_sonido", "rating_letras", "rating_consistencia", "rating_replay"):
            if col not in ea_cols:
                db.execute(f"ALTER TABLE eury_albums ADD COLUMN {col} INTEGER DEFAULT NULL")

        # Seed: Apple Music 100 Best Albums — solo rank/artista/álbum/año/
        # género (dato de referencia). Escuchado/rating/notas son míos, se
        # llenan usando la app, no vienen precargados.
        if db.execute("SELECT COUNT(*) as c FROM eury_albums").fetchone()["c"] == 0:
            db.executemany(
                "INSERT INTO eury_albums (rank, artista, album, anio, genero) VALUES (?,?,?,?,?)",
                [
                    (1, 'Lauryn Hill', 'The Miseducation of Lauryn Hill', 1998, 'Hip-Hop/R&B'),
                    (2, 'Michael Jackson', 'Thriller', 1982, 'Pop'),
                    (3, 'The Beatles', 'Abbey Road', 1969, 'Rock'),
                    (4, 'Prince & The Revolution', 'Purple Rain', 1984, 'Pop/Rock/R&B'),
                    (5, 'Frank Ocean', 'Blonde', 2016, 'R&B/Alternative'),
                    (6, 'Stevie Wonder', 'Songs in the Key of Life', 1976, 'R&B/Soul'),
                    (7, 'Kendrick Lamar', 'Good Kid, M.A.A.D City', 2012, 'Hip-Hop'),
                    (8, 'Amy Winehouse', 'Back to Black', 2006, 'Soul/R&B'),
                    (9, 'Nirvana', 'Nevermind', 1991, 'Rock/Grunge'),
                    (10, 'Beyoncé', 'Lemonade', 2016, 'R&B/Pop'),
                    (11, 'Fleetwood Mac', 'Rumours', 1977, 'Rock'),
                    (12, 'Radiohead', 'OK Computer', 1997, 'Rock/Alternative'),
                    (13, 'Jay-Z', 'The Blueprint', 2001, 'Hip-Hop'),
                    (14, 'Bob Dylan', 'Highway 61 Revisited', 1965, 'Rock/Folk'),
                    (15, 'Adele', '21', 2011, 'Pop/Soul'),
                    (16, 'Joni Mitchell', 'Blue', 1971, 'Folk'),
                    (17, 'Marvin Gaye', "What's Going On", 1971, 'Soul'),
                    (18, 'Taylor Swift', "1989 (Taylor's Version)", 2023, 'Pop'),
                    (19, 'Dr. Dre', 'The Chronic', 1992, 'Hip-Hop'),
                    (20, 'The Beach Boys', 'Pet Sounds', 1966, 'Rock/Pop'),
                    (21, 'The Beatles', 'Revolver', 1966, 'Rock'),
                    (22, 'Bruce Springsteen', 'Born to Run', 1975, 'Rock'),
                    (23, 'Daft Punk', 'Discovery', 2001, 'Electronic'),
                    (24, 'David Bowie', 'The Rise and Fall of Ziggy Stardust', 1972, 'Rock/Glam'),
                    (25, 'Miles Davis', 'Kind of Blue', 1959, 'Jazz'),
                    (26, 'Kanye West', 'My Beautiful Dark Twisted Fantasy', 2010, 'Hip-Hop'),
                    (27, 'Led Zeppelin', 'Led Zeppelin II', 1969, 'Rock'),
                    (28, 'Pink Floyd', 'The Dark Side of the Moon', 1973, 'Rock'),
                    (29, 'A Tribe Called Quest', 'The Low End Theory', 1991, 'Hip-Hop'),
                    (30, 'Billie Eilish', 'When We All Fall Asleep, Where Do We Go?', 2019, 'Pop'),
                    (31, 'Alanis Morissette', 'Jagged Little Pill', 1995, 'Rock/Alternative'),
                    (32, 'The Notorious B.I.G.', 'Ready to Die', 1994, 'Hip-Hop'),
                    (33, 'Radiohead', 'Kid A', 2000, 'Electronic/Art Rock'),
                    (34, 'Public Enemy', 'It Takes a Nation of Millions to Hold Us Back', 1988, 'Hip-Hop'),
                    (35, 'The Clash', 'London Calling', 1979, 'Rock/Punk'),
                    (36, 'Beyoncé', 'Beyoncé', 2013, 'R&B/Pop'),
                    (37, 'Wu-Tang Clan', 'Enter the Wu-Tang (36 Chambers)', 1993, 'Hip-Hop'),
                    (38, 'Carole King', 'Tapestry', 1971, 'Pop/Folk'),
                    (39, 'Nas', 'Illmatic', 1994, 'Hip-Hop'),
                    (40, 'Aretha Franklin', 'I Never Loved a Man the Way I Love You', 1967, 'Soul'),
                    (41, 'OutKast', 'Aquemini', 1998, 'Hip-Hop'),
                    (42, 'Janet Jackson', 'Control', 1986, 'Pop/R&B'),
                    (43, 'Talking Heads', 'Remain in Light', 1980, 'Rock/New Wave'),
                    (44, 'Stevie Wonder', 'Innervisions', 1973, 'R&B/Soul'),
                    (45, 'Björk', 'Homogenic', 1997, 'Electronic/Art Pop'),
                    (46, 'Bob Marley & The Wailers', 'Exodus', 1977, 'Reggae'),
                    (47, 'Drake', 'Take Care', 2011, 'Hip-Hop/R&B'),
                    (48, 'Beastie Boys', "Paul's Boutique", 1989, 'Hip-Hop'),
                    (49, 'U2', 'The Joshua Tree', 1987, 'Rock'),
                    (50, 'Kate Bush', 'Hounds of Love', 1985, 'Art Pop/Rock'),
                    (51, 'Prince', "Sign o' the Times", 1987, 'R&B/Pop/Rock'),
                    (52, "Guns N' Roses", 'Appetite for Destruction', 1987, 'Rock'),
                    (53, 'The Rolling Stones', 'Exile on Main Street', 1972, 'Rock'),
                    (54, 'John Coltrane', 'A Love Supreme', 1964, 'Jazz'),
                    (55, 'Rihanna', 'Anti', 2016, 'R&B/Pop'),
                    (56, 'The Cure', 'Disintegration', 1989, 'Rock/Alternative'),
                    (57, "D'Angelo", 'Voodoo', 2000, 'R&B/Neo-Soul'),
                    (58, 'Oasis', "(What's the Story) Morning Glory?", 1995, 'Rock'),
                    (59, 'Arctic Monkeys', 'AM', 2013, 'Rock'),
                    (60, 'The Velvet Underground & Nico', 'The Velvet Underground and Nico', 1967, 'Rock/Experimental'),
                    (61, 'Sade', 'Love Deluxe', 1992, 'R&B/Soul'),
                    (62, '2Pac', 'All Eyez on Me', 1996, 'Hip-Hop'),
                    (63, 'The Jimi Hendrix Experience', 'Are You Experienced', 1967, 'Rock'),
                    (64, 'Erykah Badu', 'Baduizm', 1997, 'R&B/Neo-Soul'),
                    (65, 'De La Soul', '3 Feet High and Rising', 1989, 'Hip-Hop'),
                    (66, 'The Smiths', 'The Queen Is Dead', 1986, 'Rock/Alternative'),
                    (67, 'The Strokes', 'Is This It', 2001, 'Rock'),
                    (68, 'Portishead', 'Dummy', 1994, 'Electronic/Trip-Hop'),
                    (69, 'Metallica', 'Master of Puppets', 1986, 'Metal'),
                    (70, 'N.W.A.', 'Straight Outta Compton', 1988, 'Hip-Hop'),
                    (71, 'Kraftwerk', 'Trans-Europe Express', 1977, 'Electronic'),
                    (72, 'SZA', 'SOS', 2022, 'R&B/Pop'),
                    (73, 'Steely Dan', 'Aja', 1977, 'Rock/Jazz'),
                    (74, 'Nine Inch Nails', 'The Downward Spiral', 1994, 'Industrial Rock'),
                    (75, 'Missy Elliott', 'Supa Dupa Fly', 1997, 'Hip-Hop'),
                    (76, 'Bad Bunny', 'Un Verano Sin Ti', 2022, 'Latin Pop/Reggaeton'),
                    (77, 'Madonna', 'Like a Prayer', 1989, 'Pop'),
                    (78, 'Elton John', 'Goodbye Yellow Brick Road', 1973, 'Rock/Pop'),
                    (79, 'Lana Del Ray', 'Norman Fucking Rockwell', 2019, 'Pop/Alternative'),
                    (80, 'Eminem', 'The Marshall Mathers LP', 2000, 'Hip-Hop'),
                    (81, 'Neil Young', 'After the Gold Rush', 1970, 'Rock/Folk'),
                    (82, '50 Cent', 'Get Rich or Die Trying', 2003, 'Hip-Hop'),
                    (83, 'Patti Smith', 'Horses', 1975, 'Rock'),
                    (84, 'Snoop Doggy Dogg', 'Doggystyle', 1993, 'Hip-Hop'),
                    (85, 'Kacey Musgroves', 'Golden Hour', 2018, 'Country/Pop'),
                    (86, 'Mary J. Blige', 'My Life', 1994, 'R&B'),
                    (87, 'Massive Attack', 'Blue Lines', 1991, 'Electronic/Trip-Hop'),
                    (88, 'Nina Simone', 'I Put a Spell on You', 1965, 'Jazz/Soul'),
                    (89, 'Lady Gaga', 'The Fame Monster', 2009, 'Pop'),
                    (90, 'AC/DC', 'Back in Black', 1980, 'Rock'),
                    (91, 'George Michael', 'Listen Without Prejudice, Vol. 1', 1990, 'Pop'),
                    (92, 'Tyler the Creator', 'Flower Boy', 2017, 'Hip-Hop'),
                    (93, 'Solange', 'A Seat at the Table', 2016, 'R&B'),
                    (94, 'Burial', 'Untrue', 2007, 'Electronic'),
                    (95, 'Usher', 'Confessions', 2004, 'R&B'),
                    (96, 'Lorde', 'Pure Heroine', 2013, 'Pop'),
                    (97, 'Rage Against The Machine', 'Rage Against The Machine', 1992, 'Rock/Metal'),
                    (98, 'Travis Scott', 'Astroworld', 2018, 'Hip-Hop'),
                    (99, 'Eagles', 'Hotel California', 1976, 'Rock'),
                    (100, 'Robyn', 'Body Talk', 2010, 'Electronic/Pop'),
                ]
            )

        # ── Prioridades de la semana (ritual dominical de Ataraxia) — un solo
        # lugar donde se capturan las 3 prioridades, que luego se siembran en
        # `priorities` (el widget diario "Prioridades" de Acta Diurna) para
        # cada día de la semana que arranca el lunes siguiente. `semana_id`
        # en `priorities` marca cuáles filas vienen de este sembrado, para
        # poder re-guardar sin duplicar ni pisar prioridades sueltas del día.
        db.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_priorities (
            semana_id  TEXT PRIMARY KEY,
            p1         TEXT,
            p2         TEXT,
            p3         TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)
        pr_cols = [r["name"] for r in db.execute("PRAGMA table_info(priorities)").fetchall()]
        if "semana_id" not in pr_cols:
            db.execute("ALTER TABLE priorities ADD COLUMN semana_id TEXT")

        # Pasos promedio/día — nueva métrica de la Revisión Semanal Objetiva,
        # junto a calorías quemadas (ver modules/ataraxia/routes.py).
        rs_cols = [r["name"] for r in db.execute("PRAGMA table_info(revision_semanal)").fetchall()]
        if "pasos_promedio" not in rs_cols:
            db.execute("ALTER TABLE revision_semanal ADD COLUMN pasos_promedio REAL")

        db.commit()
  except Exception as e:
    print(f"[DB] init_db error (app seguirá iniciando): {e}")
    _traceback.print_exc()


# ── Shared stat helpers ───────────────────────────────────────────────────────

def get_gtd_stats():
    # Deferred import to avoid circular dependency (engine.py imports database.py)
    from modules.gamification.engine import get_level_info, get_gamification_streak

    today       = today_str()
    _td         = today_date()
    week_start  = (_td - timedelta(days=_td.weekday())).isoformat()
    month_start = _td.replace(day=1).isoformat()
    with get_db() as db:
        # XP contributed by PRAXIS tasks to the main ledger
        pts_today  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task' AND date=?",  (today,)).fetchone()["s"]
        pts_week   = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task' AND date>=?", (week_start,)).fetchone()["s"]
        pts_month  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task' AND date>=?", (month_start,)).fetchone()["s"]
        pts_total  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='task'").fetchone()["s"]
        # Global XP for level calculation (same source as main dashboard)
        total_xp   = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger").fetchone()["s"]
        done_today = db.execute(
            "SELECT COUNT(*) as c FROM gtd_tasks WHERE fecha_completado=? OR completed_at=?",
            (today, today)).fetchone()["c"]
        inbox_n = db.execute(
            "SELECT COUNT(*) as c FROM gtd_tasks WHERE cuadrante IS NULL AND completado=0"
        ).fetchone()["c"]
        hoy_n = db.execute(
            "SELECT COUNT(*) as c FROM gtd_tasks WHERE cuadrante='hoy' AND completado=0"
        ).fetchone()["c"]
        next_n  = hoy_n  # backward compat alias
        proj_n  = db.execute("SELECT COUNT(*) as c FROM gtd_projects WHERE status='active'").fetchone()["c"]
    # Use the main gamification engine — same level thresholds and streak logic
    streak     = get_gamification_streak()
    level_info = get_level_info(total_xp)
    return dict(pts_today=pts_today, pts_week=pts_week, pts_month=pts_month, pts_total=pts_total,
                total_xp=total_xp, done_today=done_today, inbox_n=inbox_n,
                hoy_n=hoy_n, next_n=next_n, proj_n=proj_n,
                streak=streak,
                level=level_info["level"], level_name=level_info["level_name"],
                level_pct=level_info["level_pct"], xp_to_next=level_info["xp_to_next"])


def get_db_status():
    """Diagnostic snapshot: persistence mode, table row counts, last activity."""
    if _USE_HYBRID:
        _mode = "volume + Turso backup (async)" if _TURSO_ASYNC else "hybrid (SQLite + Turso, sync)"
    else:
        _mode = "local SQLite only"
    status = {
        "mode":        _mode,
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
