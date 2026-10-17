"""
test_finanzas_mi_parte_signo.py — bug real confirmado en vivo por el usuario:
"COMO ESTAS SUMANDO AL FINAL CON EL MONTO TOTAL O MI PARTE PORQUE SINO CORRIGE
QUE SI HAY MONTO EN MI PARTE AGARRE ESE PARA QUE NO SE INFLE EL NUMERO".

mi_parte se captura y guarda como magnitud POSITIVA ("pon aquí solo lo que te
corresponde a ti", ver update_transaction) sin importar el signo de monto
(negativo en GASTO, positivo en INGRESO, según el parser real --
bbva_debit.py: `tipo = "INGRESO" if monto >= 0 else "GASTO"`). El _MONTO
anterior (`COALESCE(mi_parte, monto)`) sustituía un monto negativo por un
mi_parte positivo sin normalizar signo, invirtiendo la contribución de esa
fila dentro de un SUM() y cancelando gasto real contra el resto.

Reproducido en vivo: 3 movimientos ALIMENTACION (uno con mi_parte=1349.33,
monto=-4048; dos sin mi_parte, monto=-1000 y -200) daban "Total gastado"
$149.33 (= 1349.33 - 1000 - 200) en vez de los ~$2,549.33 reales
(= 1349.33 + 1000 + 200). _MONTO/_monto_expr ahora normalizan el signo de
mi_parte al de monto antes de sumar.

Nota de convención: los totales de GASTO en estos endpoints se devuelven
en NEGATIVO (mismo signo que monto crudo -- confirmado por el precedente
ya existente en test_finanzas_reportes_no_inflar_ingresos.py:
`assert data['total_expense'] == -1200.0`). El front (U()/qi) invierte el
signo solo para mostrarlo -- el backend nunca lo hace.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-09-10', fecha_cargo=None, descripcion='X',
                     monto=-100.0, mi_parte=None, banco='BBVA_TDC', periodo='',
                     categoria='ALIMENTACION', subcategoria='Restaurante', tipo='GASTO')
    defaults.update(kw)
    cur = db.execute(
        """INSERT INTO est_movimientos
           (fecha,fecha_cargo,descripcion,monto,mi_parte,banco,periodo,categoria,subcategoria,tipo)
           VALUES (:fecha,:fecha_cargo,:descripcion,:monto,:mi_parte,:banco,:periodo,:categoria,
                   :subcategoria,:tipo)""",
        defaults,
    )
    return cur.lastrowid


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


# ── El escenario exacto reportado por el usuario ────────────────────────────

def test_escenario_reportado_total_gastado_correcto(client, test_db):
    with database.get_db() as db:
        _insert(db, descripcion='LA CHURRASCA PREMIUM', monto=-4048.0, mi_parte=1349.33,
                subcategoria='Restaurante')
        _insert(db, descripcion='WALMART SUPER', monto=-1000.0, mi_parte=None,
                subcategoria='Súper')
        _insert(db, descripcion='OXXO CONVENIENCIA', monto=-200.0, mi_parte=None,
                subcategoria='Conveniencia')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/stats',
                       query_string={'date_from': '2026-09-01', 'date_to': '2026-09-30'})
    data = resp.get_json()
    assert data['total_expense'] == -round(1349.33 + 1000 + 200, 2)


def test_by_category_mismo_escenario(client, test_db):
    with database.get_db() as db:
        _insert(db, descripcion='LA CHURRASCA PREMIUM', monto=-4048.0, mi_parte=1349.33)
        _insert(db, descripcion='WALMART SUPER', monto=-1000.0)
        _insert(db, descripcion='OXXO CONVENIENCIA', monto=-200.0)
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-category',
                       query_string={'date_from': '2026-09-01', 'date_to': '2026-09-30'})
    row = next(r for r in resp.get_json() if r['categoria'] == 'ALIMENTACION')
    assert row['total'] == -round(1349.33 + 1000 + 200, 2)


# ── Casos base (sin mi_parte, no debe cambiar nada) ─────────────────────────

def test_sin_mi_parte_no_cambia(client, test_db):
    with database.get_db() as db:
        _insert(db, descripcion='WALMART', monto=-500.0, mi_parte=None)
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/stats',
                       query_string={'date_from': '2026-09-01', 'date_to': '2026-09-30'})
    assert resp.get_json()['total_expense'] == -500.0


def test_mi_parte_igual_a_monto_no_cambia_nada(client, test_db):
    """Caso trivial: si mi_parte == |monto| (nadie te reembolsó nada), el
    total debe ser exactamente el mismo que sin mi_parte."""
    with database.get_db() as db:
        _insert(db, descripcion='WALMART', monto=-500.0, mi_parte=500.0)
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/stats',
                       query_string={'date_from': '2026-09-01', 'date_to': '2026-09-30'})
    assert resp.get_json()['total_expense'] == -500.0


# ── by-naturaleza ────────────────────────────────────────────────────────────

def test_by_naturaleza_normaliza_signo(client, test_db):
    with database.get_db() as db:
        _insert(db, descripcion='RENTA', monto=-7000.0, mi_parte=3500.0,
                categoria='VIVIENDA', subcategoria='Renta')
        db.commit()

    resp = client.get('/finanzas/estados/api/summary/by-naturaleza',
                       query_string={'date_from': '2026-09-01', 'date_to': '2026-09-30'})
    data = {r['naturaleza']: r['total'] for r in resp.get_json()}
    assert data['FIJO'] == -3500.0


# ── presupuestos (budgets) ───────────────────────────────────────────────────

def test_budgets_normaliza_signo(client, test_db):
    with database.get_db() as db:
        db.execute(
            "INSERT INTO est_budgets (categoria, nombre, limite) VALUES (?,?,?)",
            ('ALIMENTACION', 'Alimentación', 5000.0),
        )
        _insert(db, descripcion='WALMART', monto=-1000.0, mi_parte=400.0,
                categoria='ALIMENTACION', fecha=datetime.now().strftime('%Y-%m-%d'))
        db.commit()

    resp = client.get('/finanzas/estados/api/budgets')
    row = next((r for r in resp.get_json() if r['categoria'] == 'ALIMENTACION'), None)
    assert row is not None
    assert row['gastado'] == -400.0


# ── viajes (trips) ────────────────────────────────────────────────────────────

def test_trip_summary_normaliza_signo(client, test_db):
    with database.get_db() as db:
        trip_id = db.execute(
            "INSERT INTO viajes (nombre, fecha_inicio, fecha_fin, created_at) VALUES (?,?,?,datetime('now'))",
            ('Tabasco', '2026-09-01', '2026-09-10'),
        ).lastrowid
        tx_id = _insert(db, descripcion='HOTEL COMPARTIDO', monto=-6000.0, mi_parte=2000.0,
                         categoria='VIAJES', subcategoria='Hospedaje')
        db.execute("UPDATE est_movimientos SET viaje_id=? WHERE id=?", (trip_id, tx_id))
        db.commit()

    resp = client.get(f'/finanzas/estados/api/trips/{trip_id}/summary')
    data = resp.get_json()
    assert data['total_gastado'] == -2000.0


def test_list_trips_total_gastado_normaliza_signo(client, test_db):
    with database.get_db() as db:
        trip_id = db.execute(
            "INSERT INTO viajes (nombre, fecha_inicio, fecha_fin, created_at) VALUES (?,?,?,datetime('now'))",
            ('Tabasco', '2026-09-01', '2026-09-10'),
        ).lastrowid
        tx_id = _insert(db, descripcion='HOTEL COMPARTIDO', monto=-6000.0, mi_parte=2000.0,
                         categoria='VIAJES', subcategoria='Hospedaje')
        db.execute("UPDATE est_movimientos SET viaje_id=? WHERE id=?", (trip_id, tx_id))
        db.commit()

    resp = client.get('/finanzas/estados/api/trips')
    trip = next(t for t in resp.get_json() if t['id'] == trip_id)
    assert trip['total_gastado'] == -2000.0
