"""
test_finanzas_pedidos_amazon.py — pedidos de Amazon que pasa el usuario:
cada uno se liga a su cargo «AMAZON» por total y fecha y toma su categoría.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import pedidos_amazon as amz
from modules.finanzas.estados import msi
from modules.finanzas.estados.config import SUBCATEGORIAS


def _ins(db, fecha, desc, monto, cat='DIGITAL', sub='Accesorios tech', pn=None, pt=None):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo,
                                                      parcialidad_num, parcialidad_total)
                         VALUES (?,?,?, 'BBVA_TDC', ?, ?, 'GASTO', ?, ?)""",
                      (fecha, desc, monto, cat, sub, pn, pt)).lastrowid


def _cat(db, i):
    return tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())


def test_categorias_validas():
    for *_, cat, sub in amz.PEDIDOS:
        assert sub in SUBCATEGORIAS[cat], (cat, sub)


def test_pedidos_se_ligan_a_su_cargo(test_db):
    with database.get_db() as db:
        maleta = _ins(db, '2026-07-13', 'AMAZON', 999.0, 'DIGITAL', 'Suscripciones entretenimiento')
        casa = _ins(db, '2026-07-13', 'AMAZON', 246.25)
        deso = _ins(db, '2026-07-19', 'AMAZON', 45.45)                 # cobrado 5 días después
        otro = _ins(db, '2026-09-01', 'AMAZON', 45.45)                 # fuera de la ventana
        db.commit()
        ok, faltan = amz.aplicar(db)
        assert _cat(db, maleta) == ('VIVIENDA', 'Artículos del hogar')
        assert _cat(db, casa) == ('VIVIENDA', 'Artículos del hogar')
        assert _cat(db, deso) == ('CUIDADO_PERSONAL', 'Higiene')
        assert _cat(db, otro) == ('DIGITAL', 'Accesorios tech')
        assert (ok, faltan) == (3, len(amz.PEDIDOS) + len(amz.DEVUELTOS) - 3)   # el resto: sus cargos no están en esta base
        assert amz.aplicar(db)[0] == 0


def test_mensualidades_oral_b_a_cuidado_personal(test_db):
    with database.get_db() as db:
        oral = _ins(db, '2026-08-22', 'AMAZON A MESES', 146.0, pn=2, pt=15)
        otra = _ins(db, '2026-08-22', 'AMAZON A MESES', 480.0, pn=3, pt=15)
        db.commit()
        ajena = _ins(db, '2026-08-22', 'AMAZON MX A MESES', 200.0, pn=9, pt=12)
        db.commit()
        msi.marcar_compras(db)
        assert _cat(db, oral) == ('CUIDADO_PERSONAL', 'Higiene')
        assert _cat(db, otra) == ('TECH/DIGITAL', 'Accesorios')          # Apple Watch
        assert _cat(db, ajena) == ('DIGITAL', 'Accesorios tech')


def test_mensualidades_ram_power_bank_hdmi_a_tech(test_db):
    with database.get_db() as db:
        ids = [_ins(db, '2026-07-22', 'AMAZON A MESES', m, pn=6, pt=6) for m in (323.0, 114.0, 14.89)]
        db.commit()
        msi.marcar_compras(db)
        assert all(_cat(db, i) == ('TECH/DIGITAL', 'Accesorios') for i in ids)


def test_desodorante_de_43_20_no_es_suscripcion(test_db):
    from modules.finanzas.estados.routes import _corregir_amazon_suscripciones
    with database.get_db() as db:
        deso = _ins(db, '2026-05-24', 'AMAZON MEXICO', 43.20)
        db.commit()
        _corregir_amazon_suscripciones(db)                             # corre antes en «Aplicar reglas»
        amz.aplicar(db)
        assert _cat(db, deso) == ('CUIDADO_PERSONAL', 'Higiene')


def test_devuelto_con_reembolso_sale_del_gasto(test_db):
    with database.get_db() as db:
        cargo = _ins(db, '2026-04-29', 'AMAZON', 970.0)
        abono = _ins(db, '2026-05-10', 'AMAZON', -970.0)
        db.commit()
        amz.aplicar(db)
        assert _cat(db, cargo) == ('FINANZAS', 'Reembolsable')
        assert _cat(db, abono) == ('FINANZAS', 'Reembolsable')
        p = next(x for x in amz.plan(db) if x.get('devuelto'))
        assert p['cargo']['id'] == cargo and p['reembolso']['id'] == abono


def test_devuelto_sin_reembolso_no_se_toca(test_db):
    with database.get_db() as db:
        cargo = _ins(db, '2026-04-29', 'AMAZON', 970.0)
        db.commit()
        amz.aplicar(db)
        assert _cat(db, cargo) == ('DIGITAL', 'Accesorios tech')
        assert next(x for x in amz.plan(db) if x.get('devuelto'))['reembolso'] is None


def test_admin_pedidos_amazon(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
        assert c.get('/finanzas/estados/admin/pedidos-amazon').status_code == 403
        with c.session_transaction() as sess:
            sess["fin_ok"] = True
        r = c.get('/finanzas/estados/admin/pedidos-amazon')
        assert r.status_code == 200
        assert len(r.get_json()['pedidos']) == len(amz.PEDIDOS) + len(amz.DEVUELTOS)


def test_bose_a_meses_y_pedido_partido_en_cargos(test_db):
    with database.get_db() as db:
        bose = [_ins(db, f, 'AMAZON MX A MESES', m, pn=n, pt=15) for f, m, n in
                (('2025-08-22', 200.0, 1), ('2026-09-22', 199.0, 15))]
        pc = [_ins(db, '2025-09-26', 'STR AMAZON', m) for m in (189.05, 145.0)]
        db.commit()
        msi.marcar_compras(db)
        amz.aplicar(db)
        assert all(_cat(db, i) == ('TECH/DIGITAL', 'Accesorios') for i in bose + pc)


def test_plan_muestra_cercanos_libres(test_db):
    with database.get_db() as db:
        tomado = _ins(db, '2026-07-13', 'AMAZON', 999.0)
        libre = _ins(db, '2026-04-05', 'STR AMAZON CIUDAD DE MEX', 470.0)
        db.commit()
        p = next(x for x in amz.plan(db) if x['producto'].startswith('Pants Nike'))
        assert p['cargo'] is None and [m['id'] for m in p['cercanos']] == [libre]
        assert 'cercanos' not in next(x for x in amz.plan(db) if x['producto'] == 'Maleta de mano rígida')


def test_caja_devuelta_con_abono_tipo_pago(test_db):
    with database.get_db() as db:
        cargo = _ins(db, '2025-10-07', 'STRIPE AMAZON', 88.0)
        abono = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                              VALUES ('2025-10-20', 'STRIPE AMAZON', -88.0, 'BBVA_TDC', 'PAGO', '', 'PAGO')""").lastrowid
        echo = [_ins(db, '2025-10-22', 'AMAZON A MESES', m, pn=n, pt=3) for m, n in ((250.0, 1), (249.0, 3))]
        db.commit()
        amz.aplicar(db)
        msi.marcar_compras(db)
        assert _cat(db, cargo) == _cat(db, abono) == ('FINANZAS', 'Reembolsable')
        assert all(_cat(db, i) == ('VIVIENDA', 'Artículos del hogar') for i in echo)
