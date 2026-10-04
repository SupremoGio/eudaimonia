"""Contrapartes por los últimos 4 dígitos de la cuenta BNET y compromisos
ligados a su depósito (2026-10-04, contrapartes y viaje GDL)."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import contrapartes as cp
from modules.finanzas import compromisos as comp


def _client():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["app_ok"] = sess["fin_ok"] = True
    return c


def _mov(db, fecha, desc, monto, tipo='INGRESO', cat='FINANZAS', sub='Transferencia recibida'):
    return db.execute("""INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (?,?,?,?, 'BBVA_DEB', ?,?,?)""", (fecha, fecha, desc, monto, cat, sub, tipo)).lastrowid


def test_cuenta_de_la_descripcion():
    assert cp.cuenta_de('PAGO CUENTA DE TERCERO BNET …6230 COSITAS') == '6230'
    assert cp.cuenta_de('PAGO TARJETA DE TERCEROS CUENTA: …5198 MBAN') == '5198'
    assert cp.cuenta_de('DEPOSITO EFECTIVO PRACTIC ******1804 ABR07') is None   # tarjeta propia, no BNET
    assert cp.cuenta_de('PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A') is None


def test_semilla_resuelve_y_corner_gana_a_la_cuenta(test_db):
    with database.get_db() as db:
        a = _mov(db, '2026-03-23', 'PAGO CUENTA DE TERCERO BNET …1239 TRANSF A GIOVANY A', 500)
        b = _mov(db, '2026-05-12', 'PAGO CUENTA DE TERCERO BNET …6230 REGRESO AL CORNER', 2000, 'GASTO')
        c = _mov(db, '2026-03-17', 'PAGO CUENTA DE TERCERO BNET …6230 PRESTAMITO', 1700, 'GASTO')
        d = _mov(db, '2026-03-26', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 227)
        cp.actualizar(db)
        got = {r['id']: r['contraparte'] for r in db.execute("SELECT id, contraparte FROM est_movimientos")}
        assert (got[a], got[b], got[c], got[d]) == ('1239', '5937', '6230', None)
        assert db.execute("SELECT cuenta_contraparte FROM est_movimientos WHERE id=?", (b,)).fetchone()[0] == '6230'


def test_auto_solo_para_mama_y_gastos_compartidos(test_db):
    with database.get_db() as db:
        mama = _mov(db, '2026-01-04', 'PAGO CUENTA DE TERCERO BNET …3042 TRANSF A GIOVANY A', 850)
        papa = _mov(db, '2026-02-01', 'PAGO CUENTA DE TERCERO BNET …1239 TRANSF A GIOVANY A', 1610)
        elegida = _mov(db, '2026-01-05', 'PAGO CUENTA DE TERCERO BNET …3042 CENA', 300, cat='COMIDA_FUERA', sub='Restaurante')
        cp.actualizar(db)
        cp.aplicar_auto(db)
        cat = lambda i: tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert cat(mama) == ('FINANZAS', 'Reembolso compartido')
        assert cat(papa) == ('FINANZAS', 'Transferencia recibida')        # Papá: solo sugerencia
        assert cat(elegida) == ('COMIDA_FUERA', 'Restaurante')


def test_sugerencia_por_reglas():
    papa = {'cuenta': '1239', 'nombre': 'Papá', 'alias': [], 'cat_abono': 'OTROS/', 'cat_cargo': '',
            'reglas': [['SEGURO', 'cargo', 'TRANSPORTE/Seguro auto']]}
    assert cp.sugerencia(papa, 'GASTO', 'BNET …1239 SEGURO ABRIL')[:2] == ('TRANSPORTE', 'Seguro auto')
    assert cp.sugerencia(papa, 'INGRESO', 'BNET …1239 TRANSF')[:2] == ('OTROS', '')
    assert cp.sugerencia(papa, 'GASTO', 'BNET …1239 DEUDA') is None


def test_api_contrapartes_y_filtro(test_db):
    c = _client()
    with database.get_db() as db:
        m = _mov(db, '2026-07-11', 'PAGO CUENTA DE TERCERO BNET …4321 DEYVI', 1000)
        db.commit()
    r = c.post('/finanzas/estados/api/contrapartes', json={'cuenta': '4321', 'nombre': 'Deyvi', 'alias': 'Dey, Deyvi'})
    assert r.status_code == 200
    lista = {x['cuenta']: x for x in c.get('/finanzas/estados/api/contrapartes').get_json()['data']}
    assert lista['4321']['movimientos'] == 1 and lista['4321']['alias'] == ['Dey', 'Deyvi']
    tx = c.get('/finanzas/estados/api/transactions?contraparte=4321').get_json()
    assert [t['id'] for t in tx['data']] == [m] and tx['data'][0]['contraparte_nombre'] == 'Deyvi'
    assert c.post('/finanzas/estados/api/contrapartes', json={'cuenta': '12', 'nombre': 'x'}).status_code == 400
    c.delete('/finanzas/estados/api/contrapartes/4321')
    assert c.get('/finanzas/estados/api/transactions?contraparte=4321').get_json()['total'] == 0


def test_compromiso_sugiere_y_liga_abonos(test_db):
    c = _client()
    c.post('/finanzas/api/debt', json={'type': 'owe_me', 'person': 'Judicial', 'concept': 'Viaje GDL', 'amount': 4809.02})
    with database.get_db() as db:
        did = db.execute("SELECT id FROM debts").fetchone()[0]
        db.execute("UPDATE debts SET created_at='2025-12-10T10:00:00' WHERE id=?", (did,))   # el viaje fue en dic
        dep = _mov(db, '2026-02-15', 'PAGO CUENTA DE TERCERO BNET …6230 TRANSF A GIOVANY A', 300)
        otro = _mov(db, '2026-02-16', 'PAGO CUENTA DE TERCERO BNET …1239 TRANSF A GIOVANY A', 300)
        cp.actualizar(db)
        db.commit()
    sug = c.get('/finanzas/api/debts/sugerencias').get_json()['sugerencias']
    assert [(s['debt_id'], s['movimiento']['id']) for s in sug] == [(did, dep)]
    r = c.post(f'/finanzas/api/debt/{did}/abonar', json={'amount': 300, 'note': 'feb', 'movimiento_ids': [dep]})
    assert r.get_json()['monto_restante'] == 4509.02
    assert c.get('/finanzas/api/debts/sugerencias').get_json()['sugerencias'] == []
    h = c.get(f'/finanzas/api/debt/{did}/historial').get_json()
    assert [m['id'] for m in h['payments'][0]['movimientos']] == [dep]
    with database.get_db() as db:
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (dep,)).fetchone()) == \
            ('FINANZAS', 'Reembolso compartido')
        pid = db.execute("SELECT id FROM debt_payments").fetchone()[0]
    # un depósito ya ligado no se liga a otro abono; uno de otra persona sí se puede ligar a mano
    assert c.post(f'/finanzas/api/debt-payment/{pid}/ligar', json={'movimiento_id': otro}).status_code == 200
    c.delete(f'/finanzas/api/debt-payment/movimiento/{otro}')
    with database.get_db() as db:
        assert db.execute("SELECT subcategoria FROM est_movimientos WHERE id=?", (otro,)).fetchone()[0] == 'Transferencia recibida'


def test_sugerencia_descartada_no_vuelve(test_db):
    c = _client()
    c.post('/finanzas/api/debt', json={'type': 'owe_me', 'person': 'Corner', 'concept': 'Viaje GDL', 'amount': 4809.02})
    with database.get_db() as db:
        dep = _mov(db, '2026-07-11', 'PAGO CUENTA DE TERCERO BNET …5937 DEYVI CORNELIO', 1000)
        cp.actualizar(db)
        db.commit()
    assert len(c.get('/finanzas/api/debts/sugerencias').get_json()['sugerencias']) == 1
    c.post(f'/finanzas/api/debts/sugerencias/{dep}/descartar')
    assert c.get('/finanzas/api/debts/sugerencias').get_json()['sugerencias'] == []


def test_salud_muestra_depositos_sugeridos(test_db):
    c = _client()
    c.post('/finanzas/api/debt', json={'type': 'owe_me', 'person': 'Corner', 'concept': 'Viaje GDL', 'amount': 4809.02})
    with database.get_db() as db:
        dep = _mov(db, '2026-09-30', 'PAGO CUENTA DE TERCERO BNET …5937 ABONO', 500)
        cp.actualizar(db)
        db.commit()
    html = c.get('/finanzas/salud/').get_data(as_text=True)
    assert 'Depósitos que pueden ser abonos' in html and f'data-mov="{dep}"' in html and 'id="ma-movs"' in html


def _viaje_como_prod(db):
    """Compromisos como estaban: Eli liquidado en la app, Lenis sin el último
    abono, Judicial y Corner con sus abonos, depósitos sin ligar."""
    from modules.finanzas.estados import contrapartes_viaje as cv
    ins = lambda per, rest, settled: db.execute("""INSERT INTO debts (type, person, concept, amount, monto_total, monto_restante,
                                                   settled, created_at) VALUES ('owe_me',?,'Viaje GDL',4809.02,4809.02,?,?,'2025-12-10T10:00:00')""",
                                                (per, rest, settled)).lastrowid
    pago = lambda d, m, n, f: db.execute("INSERT INTO debt_payments (debt_id, amount, note, paid_at) VALUES (?,?,?,?)", (d, m, n, f))
    eli = ins('Eli', 0, 1); pago(eli, 3199, '', '2025-12-20T10:00'); pago(eli, 1610.02, 'Liquidado', '2026-02-02T10:00')
    lenis = ins('Lenis', 1409.02, 0)
    for m, f in ((800, '2025-11-30'), (500, '2025-12-20'), (1700, '2026-01-30'), (400, '2026-03-04')):
        pago(lenis, m, '', f + 'T10:00')
    jud = ins('Judicial', 2507.02, 0); pago(jud, 852, '', '2025-11-30T10:00'); pago(jud, 1150, '', '2025-12-20T10:00')
    cor = ins('Corner', 2509.02, 0); pago(cor, 1300, '', '2025-12-20T10:00'); pago(cor, 1000, 'ABONO VIAJE GDL', '2026-05-13T10:00')
    deps = {k: _mov(db, f, d, m) for k, f, d, m in (
        ('eli', '2026-02-01', 'PAGO CUENTA DE TERCERO BNET …1239 TRANSF A GIOVANY A', 1610),
        ('l1', '2026-01-04', 'PAGO CUENTA DE TERCERO BNET …3042 TRANSF A GIOVANY A', 850),
        ('l2', '2026-01-30', 'PAGO CUENTA DE TERCERO BNET …3042 TRANSF A GIOVANY A', 850),
        ('l3', '2026-03-04', 'PAGO CUENTA DE TERCERO BNET …3042 TRANSF A GIOVANY A', 400),
        ('j1', '2025-12-01', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 702),
        ('j2', '2026-02-15', 'PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A', 300),
        ('deyvi', '2026-07-11', 'PAGO CUENTA DE TERCERO BNET …5937 DEYVI CORNELIO', 1000))}
    cp.actualizar(db)
    return {'eli': eli, 'lenis': lenis, 'jud': jud, 'cor': cor}, deps


def test_viaje_gdl_plan_y_aplicar(test_db):
    from modules.finanzas.estados import contrapartes_viaje as cv
    with database.get_db() as db:
        debts, deps = _viaje_como_prod(db)
        antes = db.execute("SELECT COUNT(*) FROM debt_payment_movs").fetchone()[0]
        lineas = cv.plan(db)
        assert db.execute("SELECT COUNT(*) FROM debt_payment_movs").fetchone()[0] == antes == 0   # simulación
        ligados = [l for l in lineas if l['accion'] == 'ligado']
        assert len(ligados) == 6
        assert {l['seccion'] for l in lineas if l['accion'] == 'abono agregado'} == {'viaje · Lenis', 'viaje · Judicial'}
        assert [l['accion'] for l in lineas if l['accion'] == 'pregunta'] == ['pregunta'] * 4
        cv.aplicar(db, lineas)
        res = {c['persona']: c for c in cv.resumen_compromisos(db)}
        assert (res['Eli']['liquidado'], res['Lenis']['liquidado']) == (True, True)
        assert (res['Judicial']['pendiente'], res['Corner']['pendiente']) == (2507.02, 2509.02)
        assert round(res['Judicial']['pendiente'] + res['Corner']['pendiente'], 2) == 5016.04
        assert sorted(sum((a['depositos'] for a in res['Lenis']['abonos']), [])) == sorted([deps['l1'], deps['l2'], deps['l3']])
        jud = {a['monto']: a['depositos'] for a in res['Judicial']['abonos']}
        assert jud[1150] == [deps['j1']] and jud[300] == [deps['j2']]
        assert res['Corner']['abonos'][1]['depositos'] == []
        cat = lambda i: tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (i,)).fetchone())
        assert all(cat(deps[k]) == ('FINANZAS', 'Reembolso compartido') for k in ('eli', 'l1', 'l2', 'l3', 'j1', 'j2'))
        assert cat(deps['deyvi']) == ('FINANZAS', 'Transferencia recibida')
        assert not [s for s in comp.sugerencias(db) if s['movimiento']['id'] == deps['deyvi']]
        # idempotente
        assert {l['accion'] for l in cv.plan(db)} <= {'sin cambio', 'verificado', 'pendiente revisión', 'pregunta'}
        md = cv.reporte_md(cv.plan(db), cv.resumen_compromisos(db), None)
        assert '| Judicial …6230 | $4,809.02 |' in md and '$2,507.02' in md


def test_endpoint_contrapartes_viaje_simula(test_db):
    c = _client()
    with database.get_db() as db:
        _viaje_como_prod(db)
        db.commit()
    j = c.get('/finanzas/estados/admin/contrapartes-viaje').get_json()
    assert j['respaldo'] is None and j['modo'].startswith('simulacion') and len(j['preguntas']) == 4
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM debt_payment_movs").fetchone()[0] == 0
    md = c.get('/finanzas/estados/admin/contrapartes-viaje?formato=md')
    assert md.status_code == 200 and b'Compromisos del viaje' in md.data


def test_totales_pdf_de_los_periodos_2026():
    """Los totales del PDF que se usan para el cuadre son los del estado de cuenta."""
    import csv
    from modules.finanzas.estados import auditoria_pdf as aud
    filas = {r['periodo'][:10]: r for r in csv.DictReader(open(aud.RESUMEN, encoding='utf-8-sig')) if r['banco'] == 'BBVA_DEB'}
    esperado = {'2026-02-07': (47162.82, 43777.28), '2026-04-07': (40631.86, 37600.41), '2026-05-07': (85844.35, 88638.63)}
    for p, (a, c) in esperado.items():
        assert (float(filas[p]['total_abonos_pdf']), float(filas[p]['total_cargos_pdf'])) == (a, c)


def test_abono_deuda_a_papa_no_es_prestamo(test_db):
    from modules.finanzas.estados import contrapartes_viaje as cv
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES (3351, '2024-01-07', 'PAGO CUENTA DE TERCERO BNET ABONO DEUDA', 7000, 'BBVA_DEB', 'PRESTAMOS', '', 'GASTO')""")
        cv.aplicar(db)
        assert tuple(db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=3351").fetchone()) == \
            ('FINANZAS', 'Transferencia enviada')
        assert [l['accion'] for l in cv.plan(db) if l['objeto'] == '#3351'] == ['sin cambio']
