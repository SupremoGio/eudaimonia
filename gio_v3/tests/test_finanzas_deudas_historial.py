"""Historial de deudas personales: abonos con fecha y deudas liquidadas."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _client():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["app_ok"] = sess["fin_ok"] = True
    return c


def test_historial_y_liquidar(test_db):
    c = _client()
    c.post('/finanzas/api/debt', json={'type': 'owe_me', 'person': 'Corner', 'concept': 'Viaje GDL', 'amount': 3509})
    c.post('/finanzas/api/debt', json={'type': 'i_owe', 'person': 'ELI', 'concept': 'Seguro', 'amount': 1000})
    import database
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM debts").fetchone()[0] == 0   # viven en est_prestamos
        pid = db.execute("SELECT id FROM est_prestamos WHERE contraparte='Corner'").fetchone()[0]
        eli = db.execute("SELECT id FROM est_prestamos WHERE contraparte='ELI' AND direccion='RECIBIDO'").fetchone()[0]
    c.post(f"/finanzas/api/prestamo/{pid}/abonar", json={'amount': 1000, 'note': 'transferencia'})
    h = c.get(f"/finanzas/api/prestamo/{pid}/historial").get_json()
    assert h['person'] == 'Corner' and h['pagado'] == 1000 and h['monto_restante'] == 2509
    assert [p['note'] for p in h['payments']] == ['transferencia']

    c.post(f"/finanzas/api/prestamo/{eli}/abonar", json={'amount': 400})
    c.post(f"/finanzas/api/prestamo/{eli}/settle")
    liq = c.get('/finanzas/api/debts/historial').get_json()['debts']
    assert [d['person'] for d in liq] == ['ELI']
    assert liq[0]['pagado'] == 1000 and [p['amount'] for p in liq[0]['payments']] == [400, 600]
    assert liq[0]['payments'][-1]['note'] == 'Liquidado'

    c.post(f"/finanzas/api/prestamo/{pid}/settle")
    liq = c.get('/finanzas/api/debts/historial').get_json()['debts']
    assert {d['person'] for d in liq} == {'ELI', 'Corner'}
    corner = next(d for d in liq if d['person'] == 'Corner')
    assert corner['pagado'] == 3509 and corner['payments'][-1]['note'] == 'Liquidado'

    html = c.get('/finanzas/salud/').get_data(as_text=True)
    assert 'data-debts-hist' in html and 'm-debt-hist' in html and 'id="ma-movs"' in html
