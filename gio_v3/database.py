import os
from datetime import date, timedelta

TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

import sqlite3 as _sqlite3
_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline.db')

if TURSO_URL and TURSO_TOKEN:
    try:
        import libsql_experimental as _libsql
        # Direct HTTP connection — no embedded replica, no sync handshake
        def get_db():
            conn = _libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
            conn.row_factory = _libsql.Row
            return conn
        # Test connection at startup
        _test = get_db()
        _test.execute("SELECT 1").fetchone()
        _test.close()
        print("[DB] Turso cloud connected ✓")
    except Exception as e:
        print(f"[DB] Turso failed ({e}), falling back to local SQLite")
        def get_db():
            conn = _sqlite3.connect(_LOCAL)
            conn.row_factory = _sqlite3.Row
            return conn
else:
    print("[DB] No Turso env vars — using local SQLite")
    def get_db():
        conn = _sqlite3.connect(_LOCAL)
        conn.row_factory = _sqlite3.Row
        return conn


def init_db():
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
        """)

        # ── Migrate gtd_tasks: context / estimated_mins / energy_level ──────────
        gtd_cols = [r["name"] for r in db.execute("PRAGMA table_info(gtd_tasks)").fetchall()]
        if 'context' not in gtd_cols:
            db.execute("ALTER TABLE gtd_tasks ADD COLUMN context TEXT DEFAULT ''")
        if 'estimated_mins' not in gtd_cols:
            db.execute("ALTER TABLE gtd_tasks ADD COLUMN estimated_mins INTEGER DEFAULT 0")
        if 'energy_level' not in gtd_cols:
            db.execute("ALTER TABLE gtd_tasks ADD COLUMN energy_level TEXT DEFAULT 'medium'")
        db.commit()

        # ── Migrate debts table: add monto_total/monto_restante if missing ──
        cols = [r["name"] for r in db.execute("PRAGMA table_info(debts)").fetchall()]
        if 'monto_total' not in cols:
            db.execute("ALTER TABLE debts ADD COLUMN monto_total REAL DEFAULT 0")
            db.execute("ALTER TABLE debts ADD COLUMN monto_restante REAL DEFAULT 0")
            db.execute("UPDATE debts SET monto_total=amount, monto_restante=amount WHERE monto_total=0")
            db.commit()

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
                    ("nombre",   "Nombre Completo",    "— editar —", 0),
                    ("rfc",      "RFC",                 "— editar —", 1),
                    ("curp",     "CURP",                "— editar —", 1),
                    ("nss",      "NSS (IMSS)",          "— editar —", 1),
                    ("telefono", "Teléfono",            "— editar —", 0),
                    ("email",    "Email",               "— editar —", 0),
                    ("clabe",    "CLABE bancaria",      "— editar —", 1),
                    ("direccion","Dirección",           "— editar —", 0),
                ]
            )

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
    today       = date.today().isoformat()
    week_start  = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()
    LEVELS = ["","PROKOPTON","EFEBO","ASQUETÉS","ESTRATEGOS","AUTARKÉS",
              "POLÍMATA","ARETÉ","HEGEMÓN","SOPHOS","EUDAIMÓN"]
    with get_db() as db:
        pts_today  = db.execute("SELECT COALESCE(SUM(points_earned),0) as s FROM gtd_points_log WHERE date=?",  (today,)).fetchone()["s"]
        pts_week   = db.execute("SELECT COALESCE(SUM(points_earned),0) as s FROM gtd_points_log WHERE date>=?", (week_start,)).fetchone()["s"]
        pts_month  = db.execute("SELECT COALESCE(SUM(points_earned),0) as s FROM gtd_points_log WHERE date>=?", (month_start,)).fetchone()["s"]
        pts_total  = db.execute("SELECT COALESCE(SUM(points_earned),0) as s FROM gtd_points_log").fetchone()["s"]
        done_today = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE completed_at=?", (today,)).fetchone()["c"]
        inbox_n    = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE status='inbox'").fetchone()["c"]
        next_n     = db.execute("SELECT COUNT(*) as c FROM gtd_tasks WHERE status='next'").fetchone()["c"]
        proj_n     = db.execute("SELECT COUNT(*) as c FROM gtd_projects WHERE status='active'").fetchone()["c"]
    streak     = get_gtd_streak()
    level      = max(1, pts_total // 100)
    level_name = LEVELS[min(level, 10)]
    return dict(pts_today=pts_today, pts_week=pts_week, pts_month=pts_month, pts_total=pts_total,
                done_today=done_today, inbox_n=inbox_n, next_n=next_n, proj_n=proj_n,
                streak=streak, level=level, level_name=level_name, level_pct=pts_total % 100)
