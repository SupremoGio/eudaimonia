"""
test_finanzas_nomina_backfill_legacy_frozen.py — el usuario reportó, con
screenshot de Ingresos filtrado por "Sin subcategoría", varias filas
categoria=NOMINA con montos chicos y descripciones que claramente no son
sueldo: "RETIRO SIN TARJETA... FIBRA HOTELERA SC" $500.00, "SPEI ENVIADO
SANTANDER... FIBRA HOTELERA SC" $750.00, etc.

Causa raíz: a diferencia de TODAS las demás migraciones de database.py,
el backfill original de nómina (líneas ~1598 en database.py, anterior a
esta sesión) nunca estuvo protegido por migration_log -- corría en CADA
arranque de la app, sin filtro de monto, forzando tipo='INGRESO' a
cualquier movimiento que mencionara "FIBRA HOTELERA". Si el usuario
corregía una de estas filas a mano, el siguiente arranque la revertía.

Dos piezas:
  1. finanzas_nomina_backfill_legacy_frozen_2026_09 -- congela el
     backfill con el guardarraíl estándar de migration_log: corre esta
     última vez con el mismo comportamiento (para no perder su efecto
     histórico) y nunca más, para no seguir pisando correcciones
     manuales futuras.
  2. /admin/audit-nomina-sospechosa -- reporte de solo lectura (nunca
     modifica nada) de las filas categoria=NOMINA con monto fuera del
     rango realista de sueldo ($9,000-$12,000), para que el usuario las
     revise y corrija manualmente -- no se adivina el tipo/categoria
     correcto de cada una.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _insert(db, **kw):
    defaults = dict(fecha='2026-07-30', fecha_cargo=None, descripcion='X', monto=500.0,
                     banco='BBVA_DEB', periodo='', categoria='OTROS', subcategoria='',
                     tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


# ── El backfill legacy ya no revierte correcciones manuales ─────────────────

def test_backfill_legacy_is_logged_once(test_db):
    import database
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_nomina_backfill_legacy_frozen_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_backfill_legacy_ya_no_revierte_correccion_manual(test_db):
    """El caso real del bug: una fila que el backfill legacy marcó como
    NOMINA/INGRESO (ej. un retiro que mencionaba FIBRA HOTELERA), y que
    el usuario corrige a mano de vuelta a GASTO/FINANZAS -- un reinicio
    de la app (init_db() de nuevo) NO debe revertir esa corrección,
    ahora que el backfill está congelado."""
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='RETIRO SIN TARJETA FIBRA HOTELERA SC',
                         categoria='NOMINA', subcategoria='', tipo='INGRESO', monto=500.0)
        db.commit()
        # El usuario corrige a mano vía el modal de editar.
        db.execute(
            "UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Retiro efectivo', "
            "tipo='GASTO', monto=-500.0 WHERE id=?",
            (tx_id,),
        )
        db.commit()

    # Simula un reinicio de la app / redeploy.
    database.init_db()

    with database.get_db() as db:
        row = db.execute(
            "SELECT categoria, subcategoria, tipo, monto FROM est_movimientos WHERE id=?", (tx_id,)
        ).fetchone()
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Retiro efectivo'
    assert row['tipo'] == 'GASTO'
    assert row['monto'] == -500.0


# ── /admin/audit-nomina-sospechosa ──────────────────────────────────────────

def test_audit_nomina_sospechosa_encuentra_filas_fuera_de_rango(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='RETIRO SIN TARJETA FIBRA HOTELERA SC',
                categoria='NOMINA', subcategoria='', tipo='INGRESO', monto=500.0)
        _insert(db, descripcion='SPEI ENVIADO SANTANDER FIBRA HOTELERA SC',
                categoria='NOMINA', subcategoria='', tipo='INGRESO', monto=750.0)
        _insert(db, descripcion='PAGO DE NOMINA REAL', categoria='NOMINA',
                subcategoria='Pago nominal', tipo='INGRESO', monto=10500.0)
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-nomina-sospechosa')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_sospechosas'] == 2
    descripciones = {m['descripcion'] for m in data['movimientos']}
    assert 'RETIRO SIN TARJETA FIBRA HOTELERA SC' in descripciones
    assert 'SPEI ENVIADO SANTANDER FIBRA HOTELERA SC' in descripciones
    assert 'PAGO DE NOMINA REAL' not in descripciones


def test_audit_nomina_sospechosa_ordena_por_monto_ascendente(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='CHICA', categoria='NOMINA', tipo='INGRESO', monto=100.0)
        _insert(db, descripcion='MEDIANA', categoria='NOMINA', tipo='INGRESO', monto=2000.0)
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-nomina-sospechosa')
    data = resp.get_json()
    assert [m['descripcion'] for m in data['movimientos']] == ['CHICA', 'MEDIANA']


def test_audit_nomina_sospechosa_never_modifies_data(client, test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='RETIRO SOSPECHOSO', categoria='NOMINA',
                         subcategoria='', tipo='INGRESO', monto=500.0)
        db.commit()

    client.get('/finanzas/estados/admin/audit-nomina-sospechosa')

    with database.get_db() as db:
        row = db.execute("SELECT categoria, subcategoria, tipo, monto FROM est_movimientos WHERE id=?",
                          (tx_id,)).fetchone()
    assert row['categoria'] == 'NOMINA'
    assert row['tipo'] == 'INGRESO'
    assert row['monto'] == 500.0
