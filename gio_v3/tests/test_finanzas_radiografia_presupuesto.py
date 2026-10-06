"""
test_finanzas_radiografia_presupuesto.py — ajustes al cálculo de la
Radiografía del mes (budget.py) pedidos por el usuario para que el 50-30-20
refleje la realidad. Un bloque por paso:

  1a. PRESTAMOS no es gasto: antes caía en Deseos por no tener bucket.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.budget import _calc_budget, _racha_bajo_presupuesto


def _mov(db, cat, monto, tipo='GASTO', sub='', fecha='2026-09-05', desc=None):
    return db.execute(
        "INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo, "
        "categoria, subcategoria, tipo) VALUES (?,?,?,?,?,?,?,?,?)",
        (fecha, fecha, desc or f'{cat} {sub} {monto} {fecha}', monto, 'BBVA', '', cat, sub, tipo)).lastrowid


# ── 1a. Préstamos fuera del gasto ────────────────────────────────────────────

def test_prestamos_no_cuentan_como_deseos_ni_gasto_total(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'OCIO', 500)
        _mov(db, 'PRESTAMOS', 3000)
        d = _calc_budget('2026-09', db)
    assert d['buckets']['deseos']['total_gastado'] == 500
    assert [c['categoria'] for c in d['buckets']['deseos']['cats']] == ['OCIO']
    assert d['total_gastado'] == 500


def test_prestamos_no_rompen_la_racha(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 1000, tipo='INGRESO', sub='Pago nominal')
        for i in range(4):
            _mov(db, 'OCIO', 100, fecha=f'2026-09-0{i + 2}')
        _mov(db, 'PRESTAMOS', 5000)   # sin exclusión: 5400 > 1000 → «over»
        _, meses = _racha_bajo_presupuesto(db, '2026-09', max_meses=1)
    assert meses[-1]['status'] == 'ok'


# ── 2. Inversiones netas dentro de Ahorro y deudas ───────────────────────────

def test_ahorro_suma_aportaciones_menos_retiros_por_subcategoria(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        # El signo no manda: la dirección sale de la subcategoría.
        _mov(db, 'GBM', -3000, tipo='INVERSION', sub='APORTACION')
        _mov(db, 'CETES', 1000, tipo='INVERSION', sub='APORTACION')
        _mov(db, 'GBM', 500, tipo='INVERSION', sub='RETIRO')
        _mov(db, 'GBM', 80, tipo='INVERSION', sub='RENDIMIENTO')      # no cuenta
        _mov(db, 'GBM', 9999, tipo='INVERSION', sub='APORTACION', fecha='2026-08-30')  # otro mes
        d = _calc_budget('2026-09', db)
    ahorro = d['buckets']['ahorro_deuda']
    inv = next(c for c in ahorro['cats'] if c.get('inversion'))
    assert inv['inversion'] == {'aportado': 4000, 'retirado': 500, 'neto': 3500, 'n': 3}
    assert ahorro['total_gastado'] == 3500
    assert d['total_gastado'] == 3500
    assert d['disponible'] == 16500


def test_gasto_con_categoria_inversion_no_se_cuenta_dos_veces(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'INVERSION', 700, sub='Ahorro')                        # tipo GASTO
        _mov(db, 'GBM', 1000, tipo='INVERSION', sub='APORTACION')
        d = _calc_budget('2026-09', db)
    ahorro = d['buckets']['ahorro_deuda']
    assert sorted(c['gastado'] for c in ahorro['cats']) == [700, 1000]
    assert ahorro['total_gastado'] == 1700


def test_neto_negativo_se_muestra_negativo(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'GBM', 5000, tipo='INVERSION', sub='RETIRO')
        _mov(db, 'GBM', 1000, tipo='INVERSION', sub='APORTACION')
        d = _calc_budget('2026-09', db)
    assert d['buckets']['ahorro_deuda']['total_gastado'] == -4000
    assert d['seg']['ahorro_deuda'] == 0          # la barra no pinta anchos negativos


# ── 3. Ingreso recurrente vs. extraordinario ─────────────────────────────────

def test_disponible_y_metas_usan_solo_el_recurrente(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'NOMINA', 5000, tipo='INGRESO', sub='Bono')
        _mov(db, 'NOMINA', 3000, tipo='INGRESO', sub='PTU')
        _mov(db, 'FAMILIA_REGALOS', 50000, tipo='INGRESO', sub='Regalos')
        _mov(db, 'PRESTAMOS', 1000, tipo='INGRESO')                    # devolución: no es ingreso
        _mov(db, 'OCIO', 1000)
        d = _calc_budget('2026-09', db)
    assert d['ingreso_recurrente'] == 20000
    assert d['ingreso_extraordinario'] == 58000
    assert d['ingreso_real'] == 20000
    assert d['disponible'] == 19000
    assert d['buckets']['necesidades']['target_monto'] == 10000
    assert d['buckets']['deseos']['target_monto'] == 6000


def test_nomina_sin_subcategoria_cuenta_como_recurrente(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 18000, tipo='INGRESO', sub='')
        _mov(db, 'NOMINA', 4000, tipo='INGRESO', sub='Fondo de ahorro')
        d = _calc_budget('2026-09', db)
    assert (d['ingreso_recurrente'], d['ingreso_extraordinario']) == (18000, 4000)


def test_sin_recurrente_usa_el_ingreso_manual_del_mes(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 5000, tipo='INGRESO', sub='Bono')
        db.execute("INSERT INTO budget_meses (mes, ingreso_total, created_at) VALUES ('2026-09', 21000, '2026-09-01')")
        d = _calc_budget('2026-09', db)
    assert (d['ingreso_real'], d['ingreso_es_override'], d['ingreso_extraordinario']) == (21000, True, 5000)


def test_sin_recurrente_ni_manual_la_base_es_cero(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 5000, tipo='INGRESO', sub='Bono')
        d = _calc_budget('2026-09', db)
    assert d['ingreso_real'] == 0 and d['buckets']['deseos']['target_monto'] == 0


def test_racha_no_se_salva_con_un_ingreso_extraordinario(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 1000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'FAMILIA_REGALOS', 50000, tipo='INGRESO', sub='Regalos')
        for i in range(5):
            _mov(db, 'OCIO', 500, fecha=f'2026-09-0{i + 2}')
        _, meses = _racha_bajo_presupuesto(db, '2026-09', max_meses=1)
    assert meses[-1]['status'] == 'over'


# ── 4. Meta mínima de Ahorro y deudas (piso, no tope) ────────────────────────

def test_meta_minima_inicial_4000_decide_el_color(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'GBM', 3000, tipo='INVERSION', sub='APORTACION')
        d = _calc_budget('2026-09', db)
        ah = d['buckets']['ahorro_deuda']
        assert (ah['meta_minima'], ah['cumple_meta'], ah['over']) == (4000, False, True)
        assert ah['target_monto'] == 4000          # 20 % del recurrente, de referencia
        _mov(db, 'CETES', 1500, tipo='INVERSION', sub='APORTACION')
        ah = _calc_budget('2026-09', db)['buckets']['ahorro_deuda']
    assert (ah['cumple_meta'], ah['over'], ah['pct_of_meta']) == (True, False, 112)


def test_meta_configurable_y_la_migracion_no_la_pisa(test_db):
    from app import create_app
    app = create_app(); app.config['TESTING'] = True
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True; s['fin_ok'] = True
        assert c.post('/finanzas/budget/api/meta-ahorro', json={'valor': 0}).status_code == 400
        assert c.post('/finanzas/budget/api/meta-ahorro', json={'valor': 2500}).get_json()['ok']
    database.init_db()          # correr otra vez no regresa a 4000
    with database.get_db() as db:
        assert _calc_budget('2026-09', db)['buckets']['ahorro_deuda']['meta_minima'] == 2500


# ── 5. Proyectos: Hosting/Software cuentan; Publicidad/Reclutamiento no ──────

def test_proyectos_hosting_y_software_en_deseos_publicidad_fuera(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'PROYECTOS', 300, sub='Hosting')
        _mov(db, 'PROYECTOS', 200, sub='Software')
        _mov(db, 'PROYECTOS', 900, sub='Publicidad')
        _mov(db, 'PROYECTOS', 700, sub='Reclutamiento')
        d = _calc_budget('2026-09', db)
    proy = [c for c in d['buckets']['deseos']['cats'] if c['categoria'] == 'PROYECTOS']
    assert proy and proy[0]['gastado'] == 500 and proy[0]['n'] == 2
    assert d['total_gastado'] == 500


def test_detalle_de_proyectos_cuadra_con_la_fila(test_db):
    from app import create_app
    with database.get_db() as db:
        _mov(db, 'PROYECTOS', 300, sub='Hosting')
        _mov(db, 'PROYECTOS', 900, sub='Publicidad')
        db.commit()
    app = create_app(); app.config['TESTING'] = True
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['app_ok'] = True; s['fin_ok'] = True
        movs = c.get('/finanzas/budget/api/cat-movs/2026-09/PROYECTOS').get_json()['movimientos']
    assert [m['mi_monto'] for m in movs] == [300]


def test_resumen_del_hub_no_resta_retiros_de_inversion_al_gasto(test_db):
    """Retirar $8,000 de GBM no es «gasto negativo»: el Resumen del hub
    mostraba Gastos $4.0k con $12k de consumo (usuario, 2026-10-01)."""
    from unittest.mock import patch
    from modules.finanzas import routes as fin
    with database.get_db() as db:
        _mov(db, 'NOMINA', 21000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'VIVIENDA', 12000, sub='Renta')
        _mov(db, 'GBM', 8000, tipo='INVERSION', sub='RETIRO')
        d = _calc_budget('2026-09', db)
    assert d['consumo'] == 12000 and d['inversion_neta'] == -8000
    assert d['total_gastado'] == 12000                # Radiografía: el retiro tampoco resta (2026-10-06)
    assert d['disponible'] == 9000 and d['retiro_inversiones'] == 8000
    assert d['buckets']['ahorro_deuda']['total_gastado'] == -8000   # el desahorro sí se ve en su bucket
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    captured = {}
    def _render(tpl, **kw):
        captured.update(kw)
        return ''
    with app.test_request_context(), patch.object(fin, 'today_date', return_value=__import__('datetime').date(2026, 9, 30)), \
            patch.object(fin, 'render_template', _render):
        fin.index()
    b = captured['budget']
    assert b['gastado'] == 12000 and b['pct'] == 57 and b['ahorro_pct'] == 43
    assert b['disponible'] == 9000


def test_tarjeta_presupuesto_dice_el_mes_si_no_es_el_actual(test_db):
    """1/oct sin movimientos de octubre: la tarjeta muestra septiembre y lo dice."""
    from unittest.mock import patch
    import datetime as dt
    from modules.finanzas import routes as fin
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        for i in range(5):
            _mov(db, 'OCIO', 100, fecha=f'2026-09-0{i + 1}')
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c, patch.object(fin, 'today_date', return_value=dt.date(2026, 10, 1)):
        with c.session_transaction() as sess:
            sess['app_ok'] = sess['fin_ok'] = True
        html = c.get('/finanzas/').get_data(as_text=True)
    assert 'Septiembre · 2% usado' in html          # $500 / $20,000


# ── 6. Gasto total de la Radiografía = consumo + aportación (2026-10-06) ─────

def test_radiografia_septiembre_con_retiros_de_cetes(test_db):
    """Caso real: sep-2026 con $12,500 sacados de CETES. La Radiografía decía
    Gasto $6,129 / Disponible $14,886 / 29 % gastado con ~$18.6k de consumo."""
    with database.get_db() as db:
        _mov(db, 'NOMINA', 21015, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'VIVIENDA', 11243, sub='Renta')
        _mov(db, 'OCIO', 7355)
        _mov(db, 'COSTOS_FINANCIEROS', 31)
        for m in (2700.51, 5299.49, 3083.34, 1416.66):
            _mov(db, 'CETES', m, tipo='INVERSION', sub='RETIRO')
        d = _calc_budget('2026-09', db)
    assert d['total_gastado'] == 18629 == d['consumo']
    assert d['disponible'] == 21015 - 18629
    assert d['retiro_inversiones'] == 12500
    # Los segmentos de la barra suman el Gasto total (antes: 88.5 % vs. 29 %)
    assert round(sum(d['seg'].values()), 1) == round(18629 / 21015 * 100, 1)
    assert d['seg']['ahorro_deuda'] == 0.1        # los $31 de costos financieros, no el retiro


def test_aportacion_si_ocupa_ingreso(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 20000, tipo='INGRESO', sub='Pago nominal')
        _mov(db, 'OCIO', 5000)
        _mov(db, 'GBM', 3000, tipo='INVERSION', sub='APORTACION')
        d = _calc_budget('2026-09', db)
    assert (d['consumo'], d['total_gastado'], d['disponible'], d['retiro_inversiones']) == (5000, 8000, 12000, 0)
    assert d['seg']['ahorro_deuda'] == 15.0


def test_racha_un_retiro_de_inversion_no_salva_el_mes(test_db):
    with database.get_db() as db:
        _mov(db, 'NOMINA', 10000, tipo='INGRESO', sub='Pago nominal')
        for i in range(5):
            _mov(db, 'OCIO', 3000, fecha=f'2026-09-0{i + 2}')
        _mov(db, 'CETES', 9000, tipo='INVERSION', sub='RETIRO')
        _, meses = _racha_bajo_presupuesto(db, '2026-09', max_meses=1)
    assert meses[-1]['status'] == 'over'


def test_racha_mes_en_curso_no_suma_ni_rompe(test_db, monkeypatch):
    import datetime as dt
    from modules.finanzas import budget
    monkeypatch.setattr(budget, 'today_date', lambda: dt.date(2026, 10, 3))
    with database.get_db() as db:
        for mes in ('2026-08', '2026-09'):
            _mov(db, 'NOMINA', 10000, tipo='INGRESO', sub='Pago nominal', fecha=f'{mes}-01')
            for i in range(5):
                _mov(db, 'OCIO', 100, fecha=f'{mes}-0{i + 2}')
        _mov(db, 'OCIO', 100, fecha='2026-10-02')          # 1 movimiento: antes «sin datos» → racha 0
        racha, meses = _racha_bajo_presupuesto(db, '2026-10', max_meses=3)
    assert [m['status'] for m in meses] == ['ok', 'ok', 'en_curso']
    assert racha == 2


def test_racha_mes_en_curso_ya_sobre_presupuesto_la_rompe(test_db, monkeypatch):
    import datetime as dt
    from modules.finanzas import budget
    monkeypatch.setattr(budget, 'today_date', lambda: dt.date(2026, 10, 20))
    with database.get_db() as db:
        _mov(db, 'NOMINA', 10000, tipo='INGRESO', sub='Pago nominal', fecha='2026-09-01')
        for i in range(5):
            _mov(db, 'OCIO', 100, fecha=f'2026-09-0{i + 2}')
        _mov(db, 'NOMINA', 1000, tipo='INGRESO', sub='Pago nominal', fecha='2026-10-01')
        _mov(db, 'OCIO', 5000, fecha='2026-10-02')
        racha, meses = _racha_bajo_presupuesto(db, '2026-10', max_meses=2)
    assert [m['status'] for m in meses] == ['ok', 'over'] and racha == 0
