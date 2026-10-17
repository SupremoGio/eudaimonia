"""
test_finanzas_audit_buscar.py — el usuario reportó pagos de renta
(~$12,000/mes, "PAGO TARJETA DE TERCEROS MBAN") visibles may-sep 2026
pero ausentes ene-abr 2026, y confirmó "ya los tenia ahi" (ya estaban
importados antes). Se investigó database.py y se encontró
est_dedup_backfill_v1_done: un backfill automático que ya corrió una vez
en el pasado (protegido por app_settings, no por migration_log como el
resto) y borra duplicados usando descripción normalizada -- posible
explicación de datos perdidos.

/admin/audit-buscar da evidencia de solo lectura: si ese backfill llegó
a correr, y una búsqueda de texto libre sin ningún filtro de categoría/
tipo, agrupada por mes -- para confirmar en qué meses hay datos y en
cuáles no hay nada en absoluto.
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
    defaults = dict(fecha='2026-05-05', fecha_cargo='2026-05-05',
                     descripcion='PAGO TARJETA DE TERCEROS MBAN', monto=12000.0,
                     banco='BBVA_DEB', periodo='', categoria='VIVIENDA', subcategoria='Renta',
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


def test_audit_buscar_agrupa_por_mes(client, test_db):
    import database
    with database.get_db() as db:
        _insert(db, fecha='2026-05-05', fecha_cargo='2026-05-05')
        _insert(db, fecha='2026-06-07', fecha_cargo='2026-06-07')
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-buscar', query_string={'q': 'TERCEROS'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_filas_encontradas'] == 2
    assert sorted(data['meses_con_datos']) == ['2026-05', '2026-06']
    assert '2026-01' not in data['meses_con_datos']


def test_audit_buscar_no_filtra_por_categoria_ni_tipo(client, test_db):
    """A propósito busca en TODA la tabla sin importar categoria/tipo,
    para descartar que un filtro esté ocultando filas que siguen ahí."""
    import database
    with database.get_db() as db:
        _insert(db, descripcion='PAGO TARJETA DE TERCEROS MBAN', categoria='OTROS',
                subcategoria='', tipo='PAGO')
        db.commit()

    resp = client.get('/finanzas/estados/admin/audit-buscar', query_string={'q': 'TERCEROS'})
    data = resp.get_json()
    assert data['total_filas_encontradas'] == 1


def test_audit_buscar_reporta_si_dedup_backfill_corrio(client, test_db):
    import database
    resp = client.get('/finanzas/estados/admin/audit-buscar')
    data = resp.get_json()
    assert 'dedup_backfill_v1_corrio_en_esta_db' in data
    # En una DB de test fresca ya corrió (init_db se ejecuta completo).
    assert isinstance(data['dedup_backfill_v1_corrio_en_esta_db'], bool)


def test_audit_buscar_never_modifies_data(client, test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, descripcion='PAGO TARJETA DE TERCEROS MBAN')
        db.commit()

    client.get('/finanzas/estados/admin/audit-buscar', query_string={'q': 'TERCEROS'})

    with database.get_db() as db:
        row = db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
    assert row is not None
