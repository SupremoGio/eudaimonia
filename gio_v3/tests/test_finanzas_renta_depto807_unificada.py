"""
test_finanzas_renta_depto807_unificada.py — el usuario pidió, de seguido
al fix de Aportación renta/Renta en ingresos: "tambien renta depto 807".

El script /admin/apply-migrations (modules/finanzas/routes.py) generó dos
variantes de VIVIENDA/Renta -- "Renta + deposito" y "Renta depto 807 +
deposito" -- para distinguir el pago mensual normal ($6,000, mi_parte)
del pago de nov-2025 que incluía el depósito inicial ($7,000, mi_parte).
Esa distinción ya vive en mi_parte, no hace falta una subcategoria
aparte, así que se unifican a 'Renta' -- mismo patrón que Aportación
renta/Renta del lado ingreso.

Tres piezas:
  1. _normalize_subcategoria (estados/routes.py) ahora también colapsa
     esas variantes a 'Renta' cuando categoria=VIVIENDA -- corre en cada
     punto de escritura (alta manual, edición, reglas de keyword).
  2. El propio script /admin/apply-migrations ya no genera la variante
     si se vuelve a correr (escribe 'Renta' directo).
  3. finanzas_renta_depto807_unificada_2026_09 (database.py) -- backfill
     de lo que ya exista con las variantes viejas.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.routes import _normalize_subcategoria


def _insert(db, **kw):
    defaults = dict(fecha='2025-11-05', fecha_cargo=None, descripcion='PAGO TARJETA DE TERCEROS MBAN',
                     monto=-13000.0, banco='BBVA_DEB', periodo='', categoria='VIVIENDA',
                     subcategoria='Renta + deposito', tipo='GASTO', mi_parte=7000.0)
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo,mi_parte)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo,:mi_parte)""",
        defaults,
    )
    return cur.lastrowid


# ── _normalize_subcategoria (unidad) ────────────────────────────────────────

def test_normalize_unifica_renta_mas_deposito():
    assert _normalize_subcategoria('VIVIENDA', 'Renta + deposito') == 'Renta'


def test_normalize_unifica_renta_depto807_mas_deposito():
    assert _normalize_subcategoria('VIVIENDA', 'Renta depto 807 + deposito') == 'Renta'


def test_normalize_no_toca_renta_plana():
    assert _normalize_subcategoria('VIVIENDA', 'Renta') == 'Renta'


def test_normalize_no_toca_variantes_de_otra_categoria():
    assert _normalize_subcategoria('OTROS', 'Renta + deposito') == 'Renta + deposito'


# ── create_transaction usa el normalizador ──────────────────────────────────

def test_create_transaction_unifica_renta_deposito(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        resp = c.post("/finanzas/estados/api/transactions", json={
            "fecha": "2025-11-05", "descripcion": "PAGO TARJETA DE TERCEROS DEPOSITO",
            "monto": -13000.0, "tipo": "GASTO", "categoria": "VIVIENDA",
            "subcategoria": "Renta + deposito",
        })
        assert resp.status_code == 201
    import database
    with database.get_db() as db:
        row = db.execute(
            "SELECT subcategoria FROM est_movimientos WHERE descripcion='PAGO TARJETA DE TERCEROS DEPOSITO'"
        ).fetchone()
    assert row['subcategoria'] == 'Renta'


# ── Migración retroactiva ────────────────────────────────────────────────────

def test_migration_backfills_ambas_variantes_sin_tocar_mi_parte(test_db):
    import database
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_renta_depto807_unificada_2026_09'")
        id1 = _insert(db, descripcion='DEPOSITO NOV', subcategoria='Renta + deposito', mi_parte=7000.0)
        id2 = _insert(db, descripcion='DEPTO807 VIEJO', subcategoria='Renta depto 807 + deposito',
                       mi_parte=7000.0)
        id3 = _insert(db, descripcion='RENTA NORMAL', subcategoria='Renta', mi_parte=6000.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row1 = db.execute("SELECT subcategoria, mi_parte FROM est_movimientos WHERE id=?", (id1,)).fetchone()
        row2 = db.execute("SELECT subcategoria, mi_parte FROM est_movimientos WHERE id=?", (id2,)).fetchone()
        row3 = db.execute("SELECT subcategoria, mi_parte FROM est_movimientos WHERE id=?", (id3,)).fetchone()
    assert row1['subcategoria'] == 'Renta'
    assert row1['mi_parte'] == 7000.0  # el depósito sigue distinguible por mi_parte
    assert row2['subcategoria'] == 'Renta'
    assert row2['mi_parte'] == 7000.0
    assert row3['subcategoria'] == 'Renta'
    assert row3['mi_parte'] == 6000.0


def test_migration_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_renta_depto807_unificada_2026_09'"
        ).fetchall()
    assert len(rows) == 1


# ── El script /admin/apply-migrations ya no regenera la variante ───────────

def test_apply_migrations_ya_no_escribe_renta_mas_deposito(test_db):
    import database
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        with database.get_db() as db:
            _insert(db, descripcion='PAGO TARJETA DE TERCEROS MBAN NOV', monto=13000.0,
                    fecha='2025-11-08', banco='BBVA_DEB', categoria='OTROS',
                    subcategoria='', tipo='GASTO', mi_parte=None)
            db.commit()
        resp = c.post("/finanzas/admin/apply-migrations")
        assert resp.status_code == 200
    with database.get_db() as db:
        row = db.execute(
            "SELECT subcategoria, mi_parte FROM est_movimientos WHERE descripcion='PAGO TARJETA DE TERCEROS MBAN NOV'"
        ).fetchone()
    assert row['subcategoria'] == 'Renta'
    assert row['mi_parte'] == 7000.0
