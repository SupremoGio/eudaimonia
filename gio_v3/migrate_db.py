"""
Script de migración: adapta el pipeline.db viejo al esquema nuevo.
Ejecutar UNA sola vez desde la carpeta gio_v3/:  python migrate_db.py
"""
import sqlite3, datetime

DB = 'pipeline.db'
now = datetime.datetime.now().isoformat()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
db = conn.cursor()


def table_exists(name):
    return db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def col_exists(table, col):
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return col in cols


print("=== Migración pipeline.db ===")

# ── 1. Crear tablas nuevas si no existen ──────────────────────────────────────
new_tables = """
CREATE TABLE IF NOT EXISTS activity_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_key TEXT    NOT NULL,
    date         TEXT    NOT NULL,
    pts          INTEGER NOT NULL
);
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
CREATE TABLE IF NOT EXISTS meal_plan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start  TEXT    NOT NULL,
    day_name    TEXT    NOT NULL,
    meal_type   TEXT    NOT NULL,
    description TEXT    NOT NULL,
    video_url   TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL
);
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
"""
conn.executescript(new_tables)
print("  [OK] Tablas nuevas creadas")

# ── 2. Migrar logs -> activity_logs ───────────────────────────────────────────
if table_exists('logs'):
    rows = db.execute("SELECT activity_key, date, pts FROM logs").fetchall()
    if rows:
        existing = db.execute("SELECT COUNT(*) FROM activity_logs").fetchone()[0]
        if existing == 0:
            db.executemany(
                "INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                [(r['activity_key'], r['date'], r['pts']) for r in rows]
            )
            print(f"  [OK] {len(rows)} filas migradas: logs -> activity_logs")
        else:
            print(f"  [SKIP] activity_logs ya tiene datos, no se sobreescribe")
    db.execute("DROP TABLE logs")
    print("  [OK] Tabla 'logs' eliminada")

# ── 3. Migrar language_journal -> lang_journal ─────────────────────────────────
if table_exists('language_journal'):
    rows = db.execute("SELECT entry, fecha, created_at FROM language_journal").fetchall()
    if rows:
        existing = db.execute("SELECT COUNT(*) FROM lang_journal").fetchone()[0]
        if existing == 0:
            db.executemany(
                "INSERT INTO lang_journal (language, entry_text, feedback, entry_date, created_at) VALUES (?,?,?,?,?)",
                [('English', r['entry'], '', r['fecha'], r['created_at']) for r in rows]
            )
            print(f"  [OK] {len(rows)} filas migradas: language_journal -> lang_journal")
        else:
            print(f"  [SKIP] lang_journal ya tiene datos")
    db.execute("DROP TABLE language_journal")
    print("  [OK] Tabla 'language_journal' eliminada")

# ── 4. Migrar language_tests -> lang_test_results ─────────────────────────────
if table_exists('language_tests'):
    rows = db.execute("SELECT tipo, score, fecha, notas, created_at FROM language_tests").fetchall()
    if rows:
        existing = db.execute("SELECT COUNT(*) FROM lang_test_results").fetchone()[0]
        if existing == 0:
            db.executemany(
                "INSERT INTO lang_test_results (test_type, score, notes, test_date, created_at) VALUES (?,?,?,?,?)",
                [(r['tipo'], r['score'], r['notas'] or '', r['fecha'], r['created_at']) for r in rows]
            )
            print(f"  [OK] {len(rows)} filas migradas: language_tests -> lang_test_results")
    db.execute("DROP TABLE language_tests")
    print("  [OK] Tabla 'language_tests' eliminada")

# ── 5. Migrar nutrition_menu -> meal_plan ─────────────────────────────────────
if table_exists('nutrition_menu'):
    rows = db.execute("SELECT dia, comida, descripcion, video_url, created_at FROM nutrition_menu").fetchall()
    if rows:
        existing = db.execute("SELECT COUNT(*) FROM meal_plan").fetchone()[0]
        if existing == 0:
            db.executemany(
                "INSERT INTO meal_plan (week_start, day_name, meal_type, description, video_url, created_at) VALUES (?,?,?,?,?,?)",
                [('', r['dia'], r['comida'], r['descripcion'], r['video_url'] or '', r['created_at']) for r in rows]
            )
            print(f"  [OK] {len(rows)} filas migradas: nutrition_menu -> meal_plan")
        else:
            print(f"  [SKIP] meal_plan ya tiene datos")
    db.execute("DROP TABLE nutrition_menu")
    print("  [OK] Tabla 'nutrition_menu' eliminada")

# ── 6. Fix debt_payments (columnas viejas: monto/fecha/nota -> amount/paid_at/note) ──
if table_exists('debt_payments') and col_exists('debt_payments', 'monto'):
    rows = db.execute("SELECT debt_id, monto, fecha, nota FROM debt_payments").fetchall()
    db.execute("DROP TABLE debt_payments")
    db.execute("""CREATE TABLE debt_payments (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        debt_id    INTEGER NOT NULL,
        amount     REAL    NOT NULL,
        note       TEXT    DEFAULT '',
        paid_at    TEXT    NOT NULL,
        FOREIGN KEY(debt_id) REFERENCES debts(id)
    )""")
    if rows:
        db.executemany(
            "INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?,?,?,?)",
            [(r['debt_id'], r['monto'], r['nota'] or '', r['fecha']) for r in rows]
        )
    print(f"  [OK] debt_payments reconstruida ({len(rows)} filas)")

# ── 7. Fix debts: agregar monto_total/monto_restante si faltan ────────────────
if table_exists('debts'):
    if not col_exists('debts', 'monto_total'):
        db.execute("ALTER TABLE debts ADD COLUMN monto_total REAL DEFAULT 0")
        db.execute("ALTER TABLE debts ADD COLUMN monto_restante REAL DEFAULT 0")
        db.execute("UPDATE debts SET monto_total=amount, monto_restante=amount WHERE monto_total=0")
        print("  [OK] Columnas monto_total/monto_restante añadidas a debts")

# ── 8. Seed special_events si está vacío ─────────────────────────────────────
if db.execute("SELECT COUNT(*) FROM special_events").fetchone()[0] == 0:
    db.executemany(
        """INSERT INTO special_events
           (key, name, description, event_type, xp_multiplier, coin_multiplier,
            focus_category, focus_bonus, is_active, created_at)
           VALUES (?,?,?,?,?,?,?,?,0,?)""",
        [
            ("doble_xp", "Día Doble XP",
             "Todo el XP ganado se duplica durante este período",
             "double_xp", 2.0, 1.0, "", 1.0, now),
            ("semana_enfoque", "Semana de Enfoque",
             "Las actividades de Programación generan el doble de coins",
             "category_focus", 1.0, 1.0, "Programación", 2.0, now),
            ("boost_disciplina", "Boost de Disciplina",
             "Las actividades de Salud Física generan +50% coins",
             "coin_boost", 1.0, 1.5, "Salud Física", 1.5, now),
        ]
    )
    print("  [OK] special_events sembrado con eventos por defecto")

conn.commit()
conn.close()
print("\n=== Migración completada. Backup guardado en pipeline_backup.db ===")
