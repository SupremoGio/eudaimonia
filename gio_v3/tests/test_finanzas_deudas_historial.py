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
        ids = {r['person']: r['id'] for r in db.execute("SELECT id, person FROM debts")}
    c.post(f"/finanzas/api/debt/{ids['Corner']}/abonar", json={'amount': 1000, 'note': 'transferencia'})
    h = c.get(f"/finanzas/api/debt/{ids['Corner']}/historial").get_json()
    assert h['person'] == 'Corner' and h['pagado'] == 1000 and h['monto_restante'] == 2509
    assert [p['note'] for p in h['payments']] == ['transferencia']

    c.post(f"/finanzas/api/debt/{ids['ELI']}/abonar", json={'amount': 400})
    c.post(f"/finanzas/api/debt/{ids['ELI']}/settle")
    liq = c.get('/finanzas/api/debts/historial').get_json()['debts']
    assert [d['person'] for d in liq] == ['ELI']
    assert liq[0]['pagado'] == 1000 and [p['amount'] for p in liq[0]['payments']] == [400, 600]
    assert liq[0]['payments'][-1]['note'] == 'Liquidado'

    html = c.get('/finanzas/salud/').get_data(as_text=True)
    assert 'data-debts-hist' in html and f'data-hist="{ids["Corner"]}"' in html and 'm-debt-hist' in html
