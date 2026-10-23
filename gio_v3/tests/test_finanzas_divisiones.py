"""
test_finanzas_divisiones.py — un cargo del banco repartido en varias
categorías (pedido de Amazon con desodorante + ropa + balón, transferencia
mitad renta / mitad préstamo). El cargo queda intacto en FINANZAS/Dividido
(fuera del gasto) y cada parte cuenta en su categoría, aunque se vuelvan a
aplicar las reglas o se vuelva a cargar el estado.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database
from modules.finanzas.estados import divisiones as div

API = '/finanzas/estados/api'

PARTES = [
    {'monto': 45.45, 'categoria': 'CUIDADO_PERSONAL', 'subcategoria': 'Higiene', 'nota': 'Desodorante'},
    {'monto': 300.00, 'categoria': 'ROPA', 'subcategoria': 'Ropa', 'nota': 'Playera'},
    {'monto': 154.55, 'categoria': 'DEPORTE', 'subcategoria': 'Equipo', 'nota': 'Balón'},
]


@pytest.fixture
def client(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
            sess["fin_ok"] = True
        yield c


def _mov(desc='AMAZON MX MARKETPLACE', monto=500.0, tipo='GASTO', cat='DIGITAL', sub='Accesorios tech',
         fecha='2026-07-14', banco='BBVA_TDC'):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, fecha_cargo, descripcion, monto, banco, periodo,
                                                         categoria, subcategoria, tipo)
                            VALUES (?,?,?,?,?, '2026-07-01 al 2026-07-31', ?,?,?)""",
                         (fecha, fecha, desc, monto, banco, cat, sub, tipo)).lastrowid
        db.commit()
    return rid


def _filas(padre):
    with database.get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM est_movimientos WHERE id=? OR dividido_de=? ORDER BY id", (padre, padre)).fetchall()]


def _por_categoria(client):
    r = client.get(f'{API}/summary/by-category?date_from=2026-07-01&date_to=2026-07-31')
    return {x['categoria']: x['total'] for x in r.get_json()}


def test_dividir_reparte_el_gasto(client):
    pid = _mov()
    r = client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    assert r.status_code == 200, r.get_json()

    filas = _filas(pid)
    padre, hijos = filas[0], filas[1:]
    # El cargo del banco no cambia: fecha, descripción y monto intactos.
    assert (padre['descripcion'], padre['monto']) == ('AMAZON MX MARKETPLACE', 500.0)
    assert (padre['categoria'], padre['subcategoria']) == ('FINANZAS', 'Dividido')
    assert [(h['categoria'], h['monto'], h['banco'], h['tipo']) for h in hijos] == [
        ('CUIDADO_PERSONAL', 45.45, 'BBVA_TDC', 'GASTO'),
        ('ROPA', 300.0, 'BBVA_TDC', 'GASTO'),
        ('DEPORTE', 154.55, 'BBVA_TDC', 'GASTO'),
    ]
    assert hijos[1]['descripcion'] == 'AMAZON MX MARKETPLACE · Playera (2/3)'

    totales = _por_categoria(client)
    assert totales == {'ROPA': 300.0, 'DEPORTE': 154.55, 'CUIDADO_PERSONAL': 45.45}   # sin DIGITAL ni FINANZAS


def test_partes_deben_sumar_el_cargo(client):
    pid = _mov()
    malas = [dict(PARTES[0]), dict(PARTES[1])]
    r = client.put(f'{API}/transactions/{pid}/division', json={'partes': malas})
    assert r.status_code == 400
    assert 'suman' in r.get_json()['error']
    r = client.put(f'{API}/transactions/{pid}/division', json={'partes': [PARTES[0]]})
    assert r.status_code == 400
    assert len(_filas(pid)) == 1
    assert _filas(pid)[0]['categoria'] == 'DIGITAL'


def test_reglas_no_deshacen_la_division(client):
    pid = _mov()
    client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    with database.get_db() as db:
        # La regla de keyword AMAZON -> DIGITAL toca el cargo y las partes.
        db.execute("INSERT INTO est_keywords (keyword, categoria, subcategoria) VALUES ('AMAZON', 'DIGITAL', '')")
        db.commit()
    r = client.post(f'{API}/keywords/apply-all')
    assert r.status_code == 200
    filas = _filas(pid)
    assert [f['categoria'] for f in filas] == ['FINANZAS', 'CUIDADO_PERSONAL', 'ROPA', 'DEPORTE']
    assert _por_categoria(client) == {'ROPA': 300.0, 'DEPORTE': 154.55, 'CUIDADO_PERSONAL': 45.45}


def test_editar_categoria_de_una_parte_se_conserva(client):
    pid = _mov()
    client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    balon = _filas(pid)[3]
    # El editor reenvía todos los campos (monto igual): se acepta.
    r = client.patch(f'{API}/transactions/{balon["id"]}',
                     json={'categoria': 'FAMILIA_REGALOS', 'subcategoria': 'Regalos', 'monto': 154.55})
    assert r.status_code == 200
    client.post(f'{API}/keywords/apply-all')
    assert _filas(pid)[3]['categoria'] == 'FAMILIA_REGALOS'
    # Cambiar el monto de una parte fuera de la división se rechaza.
    r = client.patch(f'{API}/transactions/{balon["id"]}', json={'monto': 100})
    assert r.status_code == 409


def test_cargo_no_cambia_categoria_ni_monto_desde_el_editor(client):
    pid = _mov()
    client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    r = client.patch(f'{API}/transactions/{pid}', json={'categoria': 'OTROS', 'monto': 500, 'descripcion': 'AMAZON MX MARKETPLACE'})
    assert r.status_code == 200
    assert _filas(pid)[0]['categoria'] == 'FINANZAS'
    r = client.patch(f'{API}/transactions/{pid}', json={'monto': 450})
    assert r.status_code == 409


def test_reemplazar_y_deshacer(client):
    pid = _mov()
    client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    hijo = _filas(pid)[1]['id']
    # Se puede editar la división desde una parte.
    dos = [{'monto': 250, 'categoria': 'ROPA', 'subcategoria': 'Ropa'},
           {'monto': 250, 'categoria': 'DEPORTE', 'subcategoria': 'Equipo'}]
    r = client.put(f'{API}/transactions/{hijo}/division', json={'partes': dos})
    assert r.status_code == 200
    assert [f['monto'] for f in _filas(pid)] == [500.0, 250.0, 250.0]
    assert client.get(f'{API}/transactions/{pid}/division').get_json()['division']['partes'][0]['categoria'] == 'ROPA'

    # Borrar una parte suelta no se permite (dejaría el cargo sin cuadrar).
    parte = _filas(pid)[1]['id']
    assert client.delete(f'{API}/transactions/{parte}').status_code == 409

    r = client.delete(f'{API}/transactions/{pid}/division')
    assert r.get_json()['ok']
    filas = _filas(pid)
    assert len(filas) == 1
    assert (filas[0]['categoria'], filas[0]['subcategoria']) == ('DIGITAL', 'Accesorios tech')
    assert client.get(f'{API}/transactions/{pid}/division').get_json()['division'] is None


def test_borrar_el_cargo_borra_sus_partes(client):
    pid = _mov()
    client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    assert client.delete(f'{API}/transactions/{pid}').status_code == 200
    assert _filas(pid) == []
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM est_division_partes").fetchone()[0] == 0


def test_reafirmar_repara_partes_borradas_y_huerfanas(test_db):
    pid = _mov()
    with database.get_db() as db:
        div.guardar(db, pid, PARTES)
        hijos = [r['id'] for r in db.execute("SELECT id FROM est_movimientos WHERE dividido_de=?", (pid,))]
        db.execute("DELETE FROM est_movimientos WHERE id=?", (hijos[0],))      # otra ruta borró una parte
        db.commit()
        assert div.reafirmar(db) == 1
        assert db.execute("SELECT COUNT(*) FROM est_movimientos WHERE dividido_de=?", (pid,)).fetchone()[0] == 3
        db.execute("DELETE FROM est_movimientos WHERE id=?", (pid,))           # se borró el cargo
        div.reafirmar(db)
        assert db.execute("SELECT COUNT(*) FROM est_movimientos WHERE dividido_de=?", (pid,)).fetchone()[0] == 0
        assert div.reafirmar(db) == 0


def test_transferencia_dividida_renta_y_prestamo(client):
    """Una transferencia enviada de $10,000: $6,000 renta y $4,000 prestados.
    Solo la renta cuenta como gasto."""
    pid = _mov('SPEI ENVIADO BANORTE', 10000.0, cat='FINANZAS', sub='Transferencia enviada', banco='BBVA_DEB')
    r = client.put(f'{API}/transactions/{pid}/division', json={'partes': [
        {'monto': 6000, 'categoria': 'VIVIENDA', 'subcategoria': 'Renta'},
        {'monto': 4000, 'categoria': 'PRESTAMOS', 'subcategoria': 'Prestado'},
    ]})
    assert r.status_code == 200
    assert _por_categoria(client) == {'VIVIENDA': 6000.0}


def test_ingreso_dividido(client):
    """Un depósito que es parte reembolso y parte ingreso: solo cuenta lo que es ingreso."""
    pid = _mov('SPEI RECIBIDO JUAN', 3000.0, tipo='INGRESO', cat='FINANZAS', sub='Transferencia recibida',
               banco='BBVA_DEB')
    r = client.put(f'{API}/transactions/{pid}/division', json={'partes': [
        {'monto': 1000, 'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'},
        {'monto': 2000, 'categoria': 'PROYECTOS', 'subcategoria': 'Software'},
    ]})
    assert r.status_code == 200
    r = client.get(f'{API}/summary/by-category?tipo=INGRESO&date_from=2026-07-01&date_to=2026-07-31')
    assert {x['categoria']: x['total'] for x in r.get_json()} == {'PROYECTOS': 2000.0}


def test_parte_no_tapa_un_cargo_real_al_cargar_estado(client):
    """El dedup de la carga ignora las partes: un cargo real de $300 el mismo
    día que la parte de $300 sí se guarda; el cargo original no se duplica."""
    pid = _mov()
    client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    with database.get_db() as db:
        n = db.execute(f"SELECT COUNT(*) FROM est_movimientos WHERE fecha='2026-07-14' AND ABS(monto-300) < 0.01 "
                       f"AND tipo='GASTO' AND {div.SOLO_BANCO}").fetchone()[0]
        assert n == 0
    r = client.post(f'{API}/transactions', json={'fecha': '2026-07-14', 'descripcion': 'LIVERPOOL', 'monto': 300,
                                                 'categoria': 'ROPA', 'tipo': 'GASTO'})
    assert r.status_code == 201


def test_no_divide_con_mi_parte_ni_una_parte(client):
    pid = _mov()
    with database.get_db() as db:
        db.execute("UPDATE est_movimientos SET mi_parte=200 WHERE id=?", (pid,))
        db.commit()
    r = client.put(f'{API}/transactions/{pid}/division', json={'partes': PARTES})
    assert r.status_code == 400
    assert 'Mi parte' in r.get_json()['error']
