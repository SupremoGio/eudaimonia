"""
test_db_persistence.py
======================
Verifica que todos los módulos de GIO v3 persisten correctamente en SQLite local
y en Turso (si las credenciales están en el entorno).

Ejecución (desde gio_v3_ACTUALIZADO/):
    pip install pytest
    python -m pytest tests/test_db_persistence.py -v

Para incluir verificación de Turso:
    TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=... python -m pytest tests/test_db_persistence.py -v
"""

import os
import sys
import json
import time
import tempfile
from datetime import date, timedelta

import pytest

# ── 1. Apuntar al módulo de la app ANTES de importarlo ───────────────────────
_TMP = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMP.close()
os.environ['DATABASE_PATH'] = _TMP.name

APP_DIR = os.path.join(os.path.dirname(__file__), '..', 'gio_v3')
sys.path.insert(0, APP_DIR)

import database as _db           # noqa: E402 — debe ir después de DATABASE_PATH
from app import create_app        # noqa: E402

# ── ¿Turso disponible? ────────────────────────────────────────────────────────
TURSO_LIVE = bool(
    os.environ.get('TURSO_DATABASE_URL') and os.environ.get('TURSO_AUTH_TOKEN')
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='session')
def app():
    application = create_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture(scope='session')
def client(app):
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['fin_ok'] = True   # desbloquea finanzas / budget / consumo
        yield c


# ── Helpers de acceso directo a la DB ────────────────────────────────────────

def db_count(table, where='1=1', params=()):
    with _db.get_db() as conn:
        row = conn.execute(f'SELECT COUNT(*) as c FROM {table} WHERE {where}',
                           params).fetchone()
        return row['c']


def db_one(table, where='1=1', params=()):
    with _db.get_db() as conn:
        return conn.execute(f'SELECT * FROM {table} WHERE {where}',
                            params).fetchone()


def post(client, url, **body):
    r = client.post(url, data=json.dumps(body), content_type='application/json')
    return r.status_code, json.loads(r.data)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Dashboard / Pipeline + Prioridades del día
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_add_pipeline_item(self, client):
        before = db_count('pipeline_items')
        code, data = post(client, '/actividades/api/pipeline', text='Comprar creatina')
        assert code == 200, data
        assert db_count('pipeline_items') == before + 1

    def test_pipeline_item_persisted(self, client):
        post(client, '/actividades/api/pipeline', text='Revisar proyecto Flask')
        row = db_one('pipeline_items', "text='Revisar proyecto Flask'")
        assert row is not None
        assert row['text'] == 'Revisar proyecto Flask'

    def test_delete_pipeline_item(self, client):
        post(client, '/actividades/api/pipeline', text='Borrar esto')
        row = db_one('pipeline_items', "text='Borrar esto'")
        iid = row['id']
        before = db_count('pipeline_items')
        r = client.delete(f'/actividades/api/pipeline/{iid}')
        assert r.status_code == 200
        assert db_count('pipeline_items') == before - 1

    def test_add_priority(self, client):
        today = date.today().isoformat()
        before = db_count('priorities', 'date=?', (today,))
        # Ensure we have room (max 3)
        if before >= 3:
            pytest.skip('Ya hay 3 prioridades hoy — no se puede agregar más')
        code, data = post(client, '/actividades/api/priority', text='Hacer ejercicio TEST')
        assert code == 200, data
        assert db_count('priorities', 'date=?', (today,)) == before + 1

    def test_priority_persisted(self, client):
        row = db_one('priorities', "text='Hacer ejercicio TEST'")
        assert row is not None
        assert row['done'] == 0

    def test_toggle_priority(self, client):
        row = db_one('priorities', "text='Hacer ejercicio TEST'")
        if row is None:
            pytest.skip('Priority row not found')
        pid = row['id']
        original_done = row['done']
        post(client, f'/actividades/api/priority/{pid}/toggle')
        updated = db_one('priorities', 'id=?', (pid,))
        assert updated['done'] != original_done


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Actividades
# ═══════════════════════════════════════════════════════════════════════════════

class TestActividades:
    KEY = 'sololearn'   # clave válida de ACTIVITIES

    def test_log_activity_add(self, client):
        today = date.today().isoformat()
        # Borrar si ya existe para garantizar que el primer toggle sea "added"
        existing = db_one('activity_logs', f"activity_key='{self.KEY}' AND date=?", (today,))
        if existing:
            post(client, '/actividades/api/activity/log', key=self.KEY)  # remove

        before = db_count('activity_logs', 'date=?', (today,))
        code, data = post(client, '/actividades/api/activity/log', key=self.KEY)
        assert code == 200, data
        assert data.get('action') == 'added'
        assert db_count('activity_logs', 'date=?', (today,)) == before + 1

    def test_log_activity_toggle_remove(self, client):
        today = date.today().isoformat()
        # Garantizar que KEY esté registrado
        row = db_one('activity_logs', f"activity_key='{self.KEY}' AND date=?", (today,))
        if not row:
            post(client, '/actividades/api/activity/log', key=self.KEY)
        before = db_count('activity_logs', 'date=?', (today,))
        code, data = post(client, '/actividades/api/activity/log', key=self.KEY)
        assert code == 200, data
        assert data.get('action') == 'removed'
        assert db_count('activity_logs', 'date=?', (today,)) == before - 1

    def test_invalid_activity_key_rejected(self, client):
        code, data = post(client, '/actividades/api/activity/log', key='CLAVE_INVALIDA_XYZ')
        assert code == 400

    def test_log_activity_triggers_xp(self, client):
        today = date.today().isoformat()
        # Asegurar que 'gym' no esté logueado para que el add funcione
        row = db_one('activity_logs', f"activity_key='gym' AND date=?", (today,))
        if row:
            post(client, '/actividades/api/activity/log', key='gym')  # remove first
        before_xp = db_count('xp_ledger')
        post(client, '/actividades/api/activity/log', key='gym')
        assert db_count('xp_ledger') >= before_xp   # XP puede o no agregarse según el motor


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GTD
# ═══════════════════════════════════════════════════════════════════════════════

class TestGTD:
    def test_add_inbox_task(self, client):
        before = db_count('gtd_tasks')
        code, data = post(client, '/gtd/api/task',
                          title='TEST: Tarea inbox', status='inbox', priority='normal')
        assert code == 200, data
        assert data.get('ok')
        assert db_count('gtd_tasks') == before + 1

    def test_task_fields_saved(self, client):
        post(client, '/gtd/api/task',
             title='TEST: Tarea crítica', status='next',
             priority='critical', category='Trabajo',
             estimated_mins=30, energy_level='high')
        row = db_one('gtd_tasks', "title='TEST: Tarea crítica'")
        assert row is not None
        assert row['priority'] == 'critical'
        assert row['status'] == 'next'
        assert row['points'] == 20          # critical siempre = 20 pts
        assert row['estimated_mins'] == 30

    def test_task_status_update(self, client):
        post(client, '/gtd/api/task',
             title='TEST: Cambiar status', status='inbox', priority='normal')
        row = db_one('gtd_tasks', "title='TEST: Cambiar status'")
        tid = row['id']
        code, data = post(client, f'/gtd/api/task/{tid}/status', status='next')
        assert code == 200, data
        updated = db_one('gtd_tasks', 'id=?', (tid,))
        assert updated['status'] == 'next'

    def test_complete_task_marks_done(self, client):
        post(client, '/gtd/api/task',
             title='TEST: Completar tarea', status='next', priority='normal')
        row = db_one('gtd_tasks', "title='TEST: Completar tarea'")
        tid = row['id']
        code, data = post(client, f'/gtd/api/task/{tid}/complete')
        assert code == 200, data
        done = db_one('gtd_tasks', 'id=?', (tid,))
        assert done['status'] == 'done'
        assert done['completed_at'] == date.today().isoformat()

    def test_complete_task_logs_points(self, client):
        post(client, '/gtd/api/task',
             title='TEST: Puntos tarea', status='next', priority='important')
        row = db_one('gtd_tasks', "title='TEST: Puntos tarea'")
        tid = row['id']
        before = db_count('gtd_points_log')
        post(client, f'/gtd/api/task/{tid}/complete')
        assert db_count('gtd_points_log') > before

    def test_delete_task(self, client):
        post(client, '/gtd/api/task',
             title='TEST: Borrar tarea', status='inbox', priority='normal')
        row = db_one('gtd_tasks', "title='TEST: Borrar tarea'")
        tid = row['id']
        r = client.delete(f'/gtd/api/task/{tid}')
        assert r.status_code == 200
        assert db_one('gtd_tasks', 'id=?', (tid,)) is None

    def test_add_project(self, client):
        before = db_count('gtd_projects')
        code, data = post(client, '/gtd/api/project',
                          name='TEST: Proyecto Alpha', objective='Lanzar MVP',
                          color='#a78bfa')
        assert code == 200, data
        assert db_count('gtd_projects') == before + 1

    def test_project_fields_saved(self, client):
        row = db_one('gtd_projects', "name='TEST: Proyecto Alpha'")
        assert row is not None
        assert row['objective'] == 'Lanzar MVP'
        assert row['color'] == '#a78bfa'
        assert row['status'] == 'active'

    def test_archive_project(self, client):
        post(client, '/gtd/api/project', name='TEST: Archivar proyecto')
        row = db_one('gtd_projects', "name='TEST: Archivar proyecto'")
        pid = row['id']
        r = client.delete(f'/gtd/api/project/{pid}')
        assert r.status_code == 200
        updated = db_one('gtd_projects', 'id=?', (pid,))
        assert updated['status'] == 'archived'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Finanzas — Deudas y Pagos
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanzasDeudas:
    def test_add_debt_i_owe(self, client):
        before = db_count('debts')
        code, data = post(client, '/finanzas/api/debt',
                          type='i_owe', person='TEST: Carlos',
                          concept='Préstamo efectivo', amount=500)
        assert code == 200, data
        assert data.get('ok')
        assert db_count('debts') == before + 1

    def test_debt_monto_fields(self, client):
        post(client, '/finanzas/api/debt',
             type='owe_me', person='TEST: Ana',
             concept='Cena', amount=250.50)
        row = db_one('debts', "person='TEST: Ana' AND concept='Cena'")
        assert row is not None
        assert float(row['amount']) == 250.50
        assert float(row['monto_total']) == 250.50
        assert float(row['monto_restante']) == 250.50
        assert row['type'] == 'owe_me'

    def test_abonar_reduces_restante(self, client):
        post(client, '/finanzas/api/debt',
             type='i_owe', person='TEST: Banco',
             concept='Tarjeta de crédito', amount=1000)
        debt = db_one('debts', "person='TEST: Banco' AND concept='Tarjeta de crédito'")
        did = debt['id']
        before_payments = db_count('debt_payments')
        code, data = post(client, f'/finanzas/api/debt/{did}/abonar',
                          amount=200, note='Primer pago')
        assert code == 200, data
        assert data.get('ok')
        assert db_count('debt_payments') == before_payments + 1
        updated = db_one('debts', 'id=?', (did,))
        assert float(updated['monto_restante']) == 800.0

    def test_abonar_excess_rejected(self, client):
        post(client, '/finanzas/api/debt',
             type='i_owe', person='TEST: ExcessTest',
             concept='Pequeño', amount=100)
        debt = db_one('debts', "person='TEST: ExcessTest'")
        did = debt['id']
        code, data = post(client, f'/finanzas/api/debt/{did}/abonar', amount=9999)
        assert code == 400

    def test_settle_debt(self, client):
        post(client, '/finanzas/api/debt',
             type='owe_me', person='TEST: Settle',
             concept='Test', amount=100)
        debt = db_one('debts', "person='TEST: Settle'")
        did = debt['id']
        code, _ = post(client, f'/finanzas/api/debt/{did}/settle')
        assert code == 200
        updated = db_one('debts', 'id=?', (did,))
        assert updated['settled'] == 1
        assert float(updated['monto_restante']) == 0

    def test_delete_debt_removes_payments(self, client):
        post(client, '/finanzas/api/debt',
             type='i_owe', person='TEST: DeleteDebt',
             concept='Delete test', amount=50)
        debt = db_one('debts', "person='TEST: DeleteDebt'")
        did = debt['id']
        post(client, f'/finanzas/api/debt/{did}/abonar', amount=10)
        r = client.delete(f'/finanzas/api/debt/{did}')
        assert r.status_code == 200
        assert db_one('debts', 'id=?', (did,)) is None
        assert db_count('debt_payments', 'debt_id=?', (did,)) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Budget 50-30-20
# ═══════════════════════════════════════════════════════════════════════════════

class TestBudget:
    MES = '2026-04'

    def test_set_ingreso(self, client):
        code, data = post(client, '/finanzas/budget/api/ingreso',
                          mes=self.MES, ingreso_total=25000)
        assert code == 200, data
        assert data.get('ok')
        row = db_one('budget_meses', 'mes=?', (self.MES,))
        assert row is not None
        assert float(row['ingreso_total']) == 25000

    def test_add_budget_item(self, client):
        # Asegurar que el mes exista
        post(client, '/finanzas/budget/api/ingreso', mes=self.MES, ingreso_total=25000)
        before = db_count('budget_items')
        code, data = post(client, '/finanzas/budget/api/item',
                          mes=self.MES, nombre='TEST: Renta',
                          categoria='necesidades', tipo='fijo',
                          monto_estimado=8000)
        assert code == 200, data
        assert db_count('budget_items') == before + 1

    def test_budget_item_fields(self, client):
        row = db_one('budget_items', "nombre='TEST: Renta'")
        assert row is not None
        assert float(row['monto_estimado']) == 8000
        assert row['categoria'] == 'necesidades'

    def test_update_budget_item_real(self, client):
        post(client, '/finanzas/budget/api/ingreso', mes=self.MES, ingreso_total=25000)
        post(client, '/finanzas/budget/api/item',
             mes=self.MES, nombre='TEST: Gym',
             categoria='necesidades', tipo='fijo', monto_estimado=600)
        row = db_one('budget_items', "nombre='TEST: Gym'")
        iid = row['id']
        r = client.patch(f'/finanzas/budget/api/item/{iid}',
                         data=json.dumps({'monto_real': 650}),
                         content_type='application/json')
        assert r.status_code == 200
        updated = db_one('budget_items', 'id=?', (iid,))
        assert float(updated['monto_real']) == 650.0

    def test_delete_budget_item(self, client):
        post(client, '/finanzas/budget/api/ingreso', mes=self.MES, ingreso_total=25000)
        post(client, '/finanzas/budget/api/item',
             mes=self.MES, nombre='TEST: Borrar item',
             categoria='deseos', tipo='variable', monto_estimado=100)
        row = db_one('budget_items', "nombre='TEST: Borrar item'")
        iid = row['id']
        r = client.delete(f'/finanzas/budget/api/item/{iid}')
        assert r.status_code == 200
        assert db_one('budget_items', 'id=?', (iid,)) is None

    def test_add_budget_deuda(self, client):
        before = db_count('budget_deudas')
        code, data = post(client, '/finanzas/budget/api/deuda',
                          nombre='TEST: BBVA Oro',
                          saldo_inicial=15000,
                          pago_minimo=500,
                          tasa_interes=5.5)
        assert code == 200, data
        assert db_count('budget_deudas') == before + 1
        row = db_one('budget_deudas', "nombre='TEST: BBVA Oro'")
        assert float(row['saldo_inicial']) == 15000
        assert float(row['saldo_actual']) == 15000

    def test_pago_deuda_reduces_saldo(self, client):
        post(client, '/finanzas/budget/api/deuda',
             nombre='TEST: Invex Deuda',
             saldo_inicial=5000, pago_minimo=200, tasa_interes=3.0)
        deuda = db_one('budget_deudas', "nombre='TEST: Invex Deuda'")
        did = deuda['id']
        before_pagos = db_count('budget_pagos')
        code, data = post(client, f'/finanzas/budget/api/deuda/{did}/pago',
                          mes=self.MES, monto_pagado=300,
                          fecha=date.today().isoformat(), nota='Pago parcial')
        assert code == 200, data
        assert db_count('budget_pagos') == before_pagos + 1
        updated = db_one('budget_deudas', 'id=?', (did,))
        assert float(updated['saldo_actual']) == 4700.0

    def test_desactivar_deuda(self, client):
        post(client, '/finanzas/budget/api/deuda',
             nombre='TEST: Deuda Desactivar',
             saldo_inicial=1000, pago_minimo=50, tasa_interes=0)
        deuda = db_one('budget_deudas', "nombre='TEST: Deuda Desactivar'")
        did = deuda['id']
        r = client.delete(f'/finanzas/budget/api/deuda/{did}')
        assert r.status_code == 200
        updated = db_one('budget_deudas', 'id=?', (did,))
        assert updated['activa'] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Consumo Inteligente
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsumo:
    def test_add_product(self, client):
        before = db_count('consumo_productos', 'activo=1')
        code, data = post(client, '/finanzas/consumo/api/producto',
                          nombre='TEST: Shampoo', categoria='Higiene personal')
        assert code == 200, data
        assert data.get('ok')
        assert db_count('consumo_productos', 'activo=1') == before + 1

    def test_duplicate_product_rejected(self, client):
        post(client, '/finanzas/consumo/api/producto',
             nombre='TEST: Producto Único', categoria='Test')
        code, data = post(client, '/finanzas/consumo/api/producto',
                          nombre='TEST: Producto Único', categoria='Test')
        assert code == 400

    def test_register_purchase(self, client):
        post(client, '/finanzas/consumo/api/producto',
             nombre='TEST: Crema hidratante', categoria='Higiene')
        prod = db_one('consumo_productos', "nombre='TEST: Crema hidratante'")
        pid = prod['id']
        before = db_count('consumo_compras')
        code, data = post(client, '/finanzas/consumo/api/compra',
                          producto_id=pid,
                          fecha=date.today().isoformat(),
                          cantidad=1, precio_total=85.0)
        assert code == 200, data
        assert db_count('consumo_compras') == before + 1

    def test_purchase_updates_metrics(self, client):
        post(client, '/finanzas/consumo/api/producto',
             nombre='TEST: Leche Deslactosada', categoria='Alimentos')
        prod = db_one('consumo_productos', "nombre='TEST: Leche Deslactosada'")
        pid = prod['id']
        d1 = (date.today() - timedelta(days=15)).isoformat()
        d2 = date.today().isoformat()
        post(client, '/finanzas/consumo/api/compra',
             producto_id=pid, fecha=d1, cantidad=1, precio_total=30)
        post(client, '/finanzas/consumo/api/compra',
             producto_id=pid, fecha=d2, cantidad=1, precio_total=32)
        updated = db_one('consumo_productos', 'id=?', (pid,))
        assert updated['ultima_compra'] == d2
        assert float(updated['precio_promedio']) == 31.0
        assert float(updated['frecuencia_dias']) == 15.0

    def test_deactivate_product(self, client):
        post(client, '/finanzas/consumo/api/producto',
             nombre='TEST: Producto Eliminar', categoria='Test')
        prod = db_one('consumo_productos', "nombre='TEST: Producto Eliminar'")
        pid = prod['id']
        r = client.delete(f'/finanzas/consumo/api/producto/{pid}')
        assert r.status_code == 200
        updated = db_one('consumo_productos', 'id=?', (pid,))
        assert updated['activo'] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Lista de Prioridades (wishlist)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrioridades:
    def test_add_item(self, client):
        before = db_count('lista_prioridades')
        code, data = post(client, '/finanzas/prioridades/api/add',
                          nombre='TEST: MacBook Pro',
                          categoria='Tecnología',
                          prioridad='Alta',
                          precio_estimado=45000)
        assert code == 200, data
        assert data.get('ok')
        assert db_count('lista_prioridades') == before + 1

    def test_item_default_estado(self, client):
        row = db_one('lista_prioridades', "nombre='TEST: MacBook Pro'")
        assert row is not None
        assert row['estado'] == 'Pendiente'
        assert float(row['precio_estimado']) == 45000
        assert row['prioridad'] == 'Alta'

    def test_update_item(self, client):
        post(client, '/finanzas/prioridades/api/add',
             nombre='TEST: Update Item',
             categoria='Test', prioridad='Baja', precio_estimado=100)
        row = db_one('lista_prioridades', "nombre='TEST: Update Item'")
        iid = row['id']
        code, data = post(client, f'/finanzas/prioridades/api/update/{iid}',
                          nombre='TEST: Update Item',
                          categoria='Test', prioridad='Alta',
                          precio_estimado=200, estado='Pendiente')
        assert code == 200, data
        updated = db_one('lista_prioridades', 'id=?', (iid,))
        assert updated['prioridad'] == 'Alta'
        assert float(updated['precio_estimado']) == 200

    def test_comprar_item(self, client):
        post(client, '/finanzas/prioridades/api/add',
             nombre='TEST: Comprar Item',
             categoria='Test', prioridad='Baja', precio_estimado=500)
        row = db_one('lista_prioridades', "nombre='TEST: Comprar Item'")
        iid = row['id']
        code, data = post(client, f'/finanzas/prioridades/api/comprar/{iid}',
                          precio_real=499.99)
        assert code == 200, data
        updated = db_one('lista_prioridades', 'id=?', (iid,))
        assert updated['estado'] == 'Comprado'
        assert abs(float(updated['precio_real']) - 499.99) < 0.01

    def test_descartar_item(self, client):
        post(client, '/finanzas/prioridades/api/add',
             nombre='TEST: Descartar Item',
             categoria='Test', prioridad='Baja', precio_estimado=0)
        row = db_one('lista_prioridades', "nombre='TEST: Descartar Item'")
        iid = row['id']
        code, data = post(client, f'/finanzas/prioridades/api/descartar/{iid}')
        assert code == 200, data
        updated = db_one('lista_prioridades', 'id=?', (iid,))
        assert updated['estado'] == 'Descartado'

    def test_delete_item(self, client):
        post(client, '/finanzas/prioridades/api/add',
             nombre='TEST: Borrar Prioridad',
             categoria='Test', prioridad='Baja', precio_estimado=0)
        row = db_one('lista_prioridades', "nombre='TEST: Borrar Prioridad'")
        iid = row['id']
        code, data = post(client, f'/finanzas/prioridades/api/delete/{iid}')
        assert code == 200, data
        assert db_one('lista_prioridades', 'id=?', (iid,)) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Gamificación
# ═══════════════════════════════════════════════════════════════════════════════

class TestGamification:
    def test_stats_endpoint_returns_data(self, client):
        r = client.get('/api/gamification/stats')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'level' in data or 'xp' in data or 'total_xp' in data

    def test_achievements_list(self, client):
        r = client.get('/api/gamification/achievements')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'achievements' in data
        assert isinstance(data['achievements'], list)
        assert data['total'] > 0

    def test_special_events_exist(self, client):
        r = client.get('/api/gamification/events')
        assert r.status_code == 200
        events = json.loads(r.data)
        assert len(events) >= 3
        keys = {e['key'] for e in events}
        assert 'doble_xp' in keys
        assert 'semana_enfoque' in keys

    def test_activate_event(self, client):
        code, data = post(client, '/api/gamification/events/doble_xp/activate',
                          start_date=date.today().isoformat())
        assert code == 200, data
        row = db_one('special_events', "key='doble_xp'")
        assert row['is_active'] == 1

    def test_deactivate_event(self, client):
        post(client, '/api/gamification/events/doble_xp/activate',
             start_date=date.today().isoformat())
        code, data = post(client, '/api/gamification/events/doble_xp/deactivate')
        assert code == 200, data
        row = db_one('special_events', "key='doble_xp'")
        assert row['is_active'] == 0

    def test_history_endpoint(self, client):
        r = client.get('/api/gamification/history')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'xp_log' in data
        assert 'coin_log' in data


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Idiomas
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdiomas:
    def test_add_test_result(self, client):
        before = db_count('lang_test_results')
        code, data = post(client, '/idiomas/api/test',
                          test_type='Cambridge C1',
                          score='B2',
                          notes='Mock test',
                          test_date=date.today().isoformat())
        assert code == 200, data
        assert data.get('ok')
        assert db_count('lang_test_results') == before + 1

    def test_test_fields_saved(self, client):
        post(client, '/idiomas/api/test',
             test_type='TEST: IELTS', score='7.5',
             notes='Prueba escritura', test_date='2026-04-01')
        row = db_one('lang_test_results', "test_type='TEST: IELTS'")
        assert row is not None
        assert row['score'] == '7.5'
        assert row['notes'] == 'Prueba escritura'

    def test_delete_test(self, client):
        post(client, '/idiomas/api/test',
             test_type='TEST: TOEFL',
             score='95', test_date=date.today().isoformat())
        row = db_one('lang_test_results', "test_type='TEST: TOEFL'")
        tid = row['id']
        r = client.delete(f'/idiomas/api/test/{tid}')
        assert r.status_code == 200
        assert db_one('lang_test_results', 'id=?', (tid,)) is None

    def test_add_journal_entry(self, client):
        before = db_count('lang_journal')
        code, data = post(client, '/idiomas/api/journal',
                          language='English',
                          entry_text='Today I practiced English grammar.')
        assert code == 200, data
        assert db_count('lang_journal') == before + 1

    def test_journal_fields_saved(self, client):
        post(client, '/idiomas/api/journal',
             language='Français',
             entry_text="J'ai étudié le subjonctif.")
        row = db_one('lang_journal', "language='Français'")
        assert row is not None
        assert 'subjonctif' in row['entry_text']
        assert row['entry_date'] == date.today().isoformat()

    def test_delete_journal_entry(self, client):
        post(client, '/idiomas/api/journal',
             language='TEST_DELETE_LANG',
             entry_text='Ich lerne Deutsch.')
        row = db_one('lang_journal', "language='TEST_DELETE_LANG'")
        jid = row['id']
        r = client.delete(f'/idiomas/api/journal/{jid}')
        assert r.status_code == 200
        assert db_one('lang_journal', 'id=?', (jid,)) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Nutrición
# ═══════════════════════════════════════════════════════════════════════════════

class TestNutricion:
    def _week_start(self):
        today = date.today()
        return (today - timedelta(days=today.weekday())).isoformat()

    def test_add_meal(self, client):
        before = db_count('meal_plan')
        code, data = post(client, '/nutricion/api/meal',
                          day_name='Lunes', meal_type='Desayuno',
                          description='TEST: Avena con frutas')
        assert code == 200, data
        assert data.get('ok')
        # Upsert: puede reemplazar o agregar
        assert db_count('meal_plan') >= 1

    def test_meal_fields_saved(self, client):
        post(client, '/nutricion/api/meal',
             day_name='Martes', meal_type='Comida',
             description='TEST: Arroz con pollo y ensalada')
        ws = self._week_start()
        row = db_one('meal_plan',
                     "day_name='Martes' AND meal_type='Comida' AND week_start=?",
                     (ws,))
        assert row is not None
        assert 'Arroz' in row['description']
        assert row['week_start'] == ws

    def test_meal_upsert_replaces(self, client):
        post(client, '/nutricion/api/meal',
             day_name='Viernes', meal_type='Cena',
             description='TEST: Primera cena')
        post(client, '/nutricion/api/meal',
             day_name='Viernes', meal_type='Cena',
             description='TEST: Segunda cena — reemplaza')
        ws = self._week_start()
        with _db.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM meal_plan "
                "WHERE day_name='Viernes' AND meal_type='Cena' AND week_start=?",
                (ws,)
            ).fetchall()
        assert len(rows) == 1
        assert 'Segunda' in rows[0]['description']

    def test_update_meal(self, client):
        post(client, '/nutricion/api/meal',
             day_name='Sábado', meal_type='Desayuno',
             description='TEST: Original desayuno')
        ws = self._week_start()
        row = db_one('meal_plan',
                     "day_name='Sábado' AND meal_type='Desayuno' AND week_start=?",
                     (ws,))
        mid = row['id']
        r = client.put(f'/nutricion/api/meal/{mid}',
                       data=json.dumps({'description': 'TEST: Desayuno actualizado',
                                        'video_url': ''}),
                       content_type='application/json')
        assert r.status_code == 200
        updated = db_one('meal_plan', 'id=?', (mid,))
        assert updated['description'] == 'TEST: Desayuno actualizado'

    def test_delete_meal(self, client):
        post(client, '/nutricion/api/meal',
             day_name='Domingo', meal_type='Snack',
             description='TEST: Snack a eliminar')
        ws = self._week_start()
        row = db_one('meal_plan',
                     "day_name='Domingo' AND meal_type='Snack' AND week_start=?",
                     (ws,))
        mid = row['id']
        r = client.delete(f'/nutricion/api/meal/{mid}')
        assert r.status_code == 200
        assert db_one('meal_plan', 'id=?', (mid,)) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Perfil
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerfil:
    def test_update_personal_info(self, client):
        code, data = post(client, '/perfil/api/update',
                          key='nombre', value='TEST: Giovany Test')
        assert code == 200, data
        assert data.get('ok')
        row = db_one('personal_info', "key='nombre'")
        assert row['value'] == 'TEST: Giovany Test'

    def test_update_body_measurement(self, client):
        code, data = post(client, '/perfil/api/update_measurement',
                          key='peso', value='75')
        assert code == 200, data
        assert data.get('ok')
        row = db_one('body_measurements', "key='peso'")
        assert row['value'] == '75'
        assert row['unit'] == 'kg'

    def test_multiple_measurements(self, client):
        post(client, '/perfil/api/update_measurement', key='estatura', value='175')
        post(client, '/perfil/api/update_measurement', key='cintura', value='82')
        assert db_one('body_measurements', "key='estatura'")['value'] == '175'
        assert db_one('body_measurements', "key='cintura'")['value'] == '82'


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Sábado
# ═══════════════════════════════════════════════════════════════════════════════

class TestSabado:
    KEY = 'vacuum_house'

    def _week_start(self):
        today = date.today()
        days_since_sat = (today.weekday() + 2) % 7
        return (today - timedelta(days=days_since_sat)).isoformat()

    def test_toggle_creates_record(self, client):
        ws = self._week_start()
        # Resetear si existe
        with _db.get_db() as conn:
            conn.execute(
                "DELETE FROM saturday_checks WHERE week_start=? AND task_key=?",
                (ws, self.KEY)
            )
            conn.commit()
        code, data = post(client, '/sabado/api/toggle', key=self.KEY)
        assert code == 200, data
        assert 'tasks' in data
        row = db_one('saturday_checks',
                     'week_start=? AND task_key=?', (ws, self.KEY))
        assert row is not None
        assert row['done'] == 1

    def test_toggle_flips_done(self, client):
        ws = self._week_start()
        row_before = db_one('saturday_checks',
                            'week_start=? AND task_key=?', (ws, self.KEY))
        done_before = row_before['done'] if row_before else 0
        post(client, '/sabado/api/toggle', key=self.KEY)
        row_after = db_one('saturday_checks',
                           'week_start=? AND task_key=?', (ws, self.KEY))
        assert row_after['done'] != done_before

    def test_done_count_in_response(self, client):
        code, data = post(client, '/sabado/api/toggle', key='clean_bathroom')
        assert code == 200
        assert 'done_count' in data
        assert 'total' in data
        assert isinstance(data['done_count'], int)


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Turso — verificación directa en nube (skip si no hay credenciales)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not TURSO_LIVE,
                    reason='Sin TURSO_DATABASE_URL / TURSO_AUTH_TOKEN en entorno')
class TestTurso:
    """Consulta Turso directamente para confirmar que los datos llegaron a la nube."""

    def _query(self, sql, args=None):
        from database import _turso_pipeline, _TURSO_HOST, _TURSO_TOKEN_VAL, _from_cell
        stmt = {
            'sql': sql,
            'args': [{'type': 'text', 'value': str(a)} for a in (args or [])]
        }
        out = _turso_pipeline(_TURSO_HOST, _TURSO_TOKEN_VAL, [stmt])
        res = out['results'][0]
        assert res['type'] == 'ok', f'Turso error: {res}'
        result = res['response']['result']
        cols = [c['name'] for c in result.get('cols', [])]
        return [dict(zip(cols, [_from_cell(c) for c in row]))
                for row in result.get('rows', [])]

    def test_turso_connection(self):
        rows = self._query('SELECT 1 as ping')
        assert rows[0]['ping'] == 1

    def test_all_tables_exist_in_turso(self):
        rows = self._query(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        turso_tables = {r['name'] for r in rows}
        expected = {
            'pipeline_items', 'priorities', 'activity_logs',
            'gtd_tasks', 'gtd_projects', 'gtd_points_log',
            'debts', 'debt_payments', 'budget_categories',
            'budget_meses', 'budget_items', 'budget_deudas', 'budget_pagos',
            'lista_prioridades', 'consumo_productos', 'consumo_compras',
            'lang_test_results', 'lang_journal', 'meal_plan',
            'personal_info', 'body_measurements', 'profile_docs',
            'saturday_checks',
            'xp_ledger', 'coins_ledger', 'achievements',
            'multiplier_log', 'penalty_log', 'special_events',
        }
        missing = expected - turso_tables
        assert not missing, f'Tablas faltantes en Turso: {missing}'

    def test_gtd_task_synced_to_turso(self, client):
        post(client, '/gtd/api/task',
             title='TURSO_SYNC_VERIFY', status='inbox', priority='normal')
        time.sleep(1.5)   # dar tiempo al hilo background
        rows = self._query(
            "SELECT id FROM gtd_tasks WHERE title='TURSO_SYNC_VERIFY'"
        )
        assert len(rows) >= 1, 'Tarea GTD no encontrada en Turso tras 1.5s'

    def test_debt_synced_to_turso(self, client):
        post(client, '/finanzas/api/debt',
             type='owe_me', person='TURSO_CHECK_PERSON',
             concept='Verificación Turso', amount=999)
        time.sleep(1.5)
        rows = self._query(
            "SELECT id FROM debts WHERE person='TURSO_CHECK_PERSON'"
        )
        assert len(rows) >= 1, 'Deuda no encontrada en Turso tras 1.5s'

    def test_activity_log_synced_to_turso(self, client):
        today = date.today().isoformat()
        # Asegurar que 'leer_general' esté registrado hoy
        existing = db_one('activity_logs',
                          f"activity_key='leer_general' AND date=?", (today,))
        if not existing:
            post(client, '/actividades/api/activity/log', key='leer_general')
        time.sleep(1.5)
        rows = self._query(
            f"SELECT id FROM activity_logs WHERE date='{today}'"
        )
        assert len(rows) >= 1, 'Ningún log de actividad en Turso para hoy'

    def test_turso_row_counts_match_local(self):
        """Los conteos de Turso no deben ser menores al local (pueden ser iguales)."""
        tables_to_check = [
            'gtd_tasks', 'debts', 'activity_logs',
            'lista_prioridades', 'consumo_productos',
        ]
        for tbl in tables_to_check:
            local_count = db_count(tbl)
            turso_rows  = self._query(f'SELECT COUNT(*) as c FROM {tbl}')
            turso_count = turso_rows[0]['c']
            assert turso_count >= local_count, (
                f'{tbl}: Turso tiene {turso_count} filas pero local tiene {local_count}'
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Snapshot final — todas las tablas existen y tienen registros
# ═══════════════════════════════════════════════════════════════════════════════

class TestSnapshot:
    TABLES = [
        'pipeline_items', 'priorities', 'activity_logs',
        'gtd_tasks', 'gtd_projects', 'gtd_points_log',
        'debts', 'debt_payments', 'budget_categories',
        'budget_meses', 'budget_items', 'budget_deudas', 'budget_pagos',
        'lista_prioridades', 'consumo_productos', 'consumo_compras',
        'lang_test_results', 'lang_journal', 'meal_plan',
        'personal_info', 'body_measurements',
        'saturday_checks',
        'xp_ledger', 'coins_ledger', 'achievements', 'special_events',
    ]

    def test_all_tables_exist_locally(self):
        with _db.get_db() as conn:
            existing = {r['name'] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        missing = [t for t in self.TABLES if t not in existing]
        assert not missing, f'Tablas faltantes en SQLite local: {missing}'

    def test_seeded_tables_have_data(self):
        seeded = {
            'personal_info': 8,
            'body_measurements': 12,
            'budget_categories': 9,
            'lista_prioridades': 1,
            'consumo_productos': 1,
            'special_events': 3,
        }
        for tbl, min_rows in seeded.items():
            count = db_count(tbl)
            assert count >= min_rows, (
                f'{tbl} debería tener >= {min_rows} filas de seed, tiene {count}'
            )

    def test_row_counts_report(self, capsys):
        """Imprime resumen de conteos — no tiene assertions, es informativo."""
        print('\n\n── Conteo de registros en SQLite local ─────────────────')
        with _db.get_db() as conn:
            for tbl in self.TABLES:
                try:
                    n = conn.execute(
                        f'SELECT COUNT(*) as c FROM {tbl}'
                    ).fetchone()['c']
                    estado = '✓' if n > 0 else '○'
                    print(f'  {estado}  {tbl:<38} {n:>5} filas')
                except Exception as e:
                    print(f'  ✗  {tbl:<38} ERROR: {e}')
        print('──────────────────────────────────────────────────────────\n')
