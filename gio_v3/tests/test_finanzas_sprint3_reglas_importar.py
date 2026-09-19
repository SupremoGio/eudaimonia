"""
test_finanzas_sprint3_reglas_importar.py — cubre el Sprint 3 ORIGINAL
("Reglas automáticas al importar", distinto de los sprints de taxonomía ya
aplicados y ya cubiertos por test_finanzas_taxonomia_sprint1.py):

  1. Las mensualidades de una compra a MSI (línea "N DE M COMERCIO $monto"
     dentro de la sección de meses sin intereses de un estado de cuenta)
     ya NO se descartan al parsear — se guardan como GASTO real con
     parcialidad_num/parcialidad_total/compra_msi_id (parsers/_base.py,
     usado por bbva.py e invex.py; también bbva_legacy_csv.py y hsbc.py).
  2. _detectar_avisos_msi (routes.py) avisa -- nunca corrige solo -- si un
     grupo de compra_msi_id tiene más mensualidades de las esperadas o una
     mensualidad repetida.
  3. _unify_movimiento_interno (routes.py) reclasifica, solo entre las filas
     recién insertadas, pago de TDC / SPEI-hacia-TDC a
     categoria=PAGO_TDC, tipo=MOVIMIENTO_INTERNO -- de forma uniforme sin
     importar qué parser/banco las produjo (antes cada parser decidía esto
     por su cuenta con su propia lista payment_keywords).
  4. _sugerir_viaje_tabasco (routes.py) SUGIERE -- nunca asigna solo -- un
     viaje FAMILIA_TABASCO existente por rango de fechas para gastos que
     mencionan Villahermosa/VSA/Tabasco.
  5. _sugerir_reembolsos (routes.py) SUGIERE -- nunca marca solo -- conciliar
     un depósito recién importado contra un EXPENSE pendiente cuyo monto
     coincida dentro de ±1%; /api/expenses/<id>/conciliar es quien de verdad
     marca PAGADO, y solo cuando se le llama explícitamente.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.parsers._base import parse_text_statement, msi_group_id
from modules.finanzas.estados.parsers.bbva_legacy_csv import _make_mov
from modules.finanzas.estados.routes import (
    _es_movimiento_interno,
    _unify_movimiento_interno,
    _detectar_avisos_msi,
    _sugerir_viaje_tabasco,
    _sugerir_reembolsos,
)

PAYMENT_KW = ["BMOVIL", "PAGO TDC", "SPEI RECIBIDO", "ABONO RECIBIDO", "PAGO TARJETA"]


# ── 1) Captura de mensualidades MSI en parse_text_statement (_base.py) ────────

MSI_SAMPLE_TEXT = """COMPRAS Y CARGOS DIFERIDOS A MESES SIN INTERESES
03-ene-26  03-ene-26  3 DE 12 WALMART VENTA EN L  +$500.00
04-feb-26  04-feb-26  4 DE 12 WALMART VENTA EN L  +$500.00
CARGOS,COMPRAS Y ABONOS REGULARES
05-mar-26  05-mar-26  OXXO GAS  +$100.00"""


def test_msi_installment_is_kept_not_dropped():
    movs = parse_text_statement(MSI_SAMPLE_TEXT, PAYMENT_KW, periodo=None)
    walmart = [m for m in movs if "WALMART" in m["descripcion"]]
    assert len(walmart) == 2, "antes de este sprint estas líneas se descartaban por completo"


def test_msi_installment_captures_parcialidad_num_and_total():
    movs = parse_text_statement(MSI_SAMPLE_TEXT, PAYMENT_KW, periodo=None)
    by_num = {m["parcialidad_num"]: m for m in movs if m["descripcion"].startswith("WALMART")}
    assert by_num[3]["parcialidad_total"] == 12
    assert by_num[4]["parcialidad_total"] == 12
    assert by_num[3]["monto"] == 500.00


def test_msi_installments_of_same_purchase_share_compra_msi_id():
    movs = parse_text_statement(MSI_SAMPLE_TEXT, PAYMENT_KW, periodo=None)
    walmart = [m for m in movs if m["descripcion"].startswith("WALMART")]
    assert walmart[0]["compra_msi_id"] is not None
    assert walmart[0]["compra_msi_id"] == walmart[1]["compra_msi_id"]


def test_regular_non_msi_transaction_has_no_parcialidad():
    movs = parse_text_statement(MSI_SAMPLE_TEXT, PAYMENT_KW, periodo=None)
    oxxo = next(m for m in movs if "OXXO" in m["descripcion"])
    assert oxxo["parcialidad_num"] is None
    assert oxxo["parcialidad_total"] is None
    assert oxxo["compra_msi_id"] is None


def test_different_purchases_get_different_compra_msi_id():
    text = """COMPRAS Y CARGOS DIFERIDOS A MESES SIN INTERESES
01-ene-26  01-ene-26  1 DE 6 AMAZON MX  +$300.00
01-ene-26  01-ene-26  1 DE 3 LIVERPOOL  +$900.00
CARGOS,COMPRAS Y ABONOS REGULARES"""
    movs = parse_text_statement(text, PAYMENT_KW, periodo=None)
    ids = {m["compra_msi_id"] for m in movs}
    assert len(ids) == 2


# ── 1b) Lo mismo para bbva_legacy_csv.py (formato CSV, no PDF) ────────────────

def test_legacy_csv_msi_installment_captures_parcialidad():
    mov = _make_mov("2026-01-03", "2026-01-03", "5 DE 12 WALMART VENTA EN L", 500.00, False)
    assert mov["parcialidad_num"] == 5
    assert mov["parcialidad_total"] == 12
    assert mov["compra_msi_id"] is not None
    assert mov["descripcion"] == "WALMART VENTA EN L"  # prefijo N DE M ya limpio


def test_legacy_csv_msi_shares_id_with_base_parser_for_same_comercio_y_monto():
    base_movs = parse_text_statement(MSI_SAMPLE_TEXT, PAYMENT_KW, periodo=None)
    walmart_base = next(m for m in base_movs if m["parcialidad_num"] == 3)
    mov_csv = _make_mov("2026-01-03", "2026-01-03", "3 DE 12 WALMART VENTA EN L", 500.00, False)
    assert mov_csv["compra_msi_id"] == walmart_base["compra_msi_id"]


def test_legacy_csv_non_msi_row_has_no_parcialidad():
    mov = _make_mov("2026-01-05", "2026-01-05", "OXXO GAS", 100.00, False)
    assert mov["parcialidad_num"] is None
    assert mov["compra_msi_id"] is None


def test_msi_group_id_is_none_without_parcialidad():
    assert msi_group_id("", 100.0) is None


# ── 2) _es_movimiento_interno / _unify_movimiento_interno ─────────────────────

def _insert(db, **kw):
    defaults = dict(fecha='2026-01-01', fecha_cargo=None, descripcion='X', monto=100.0,
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


def test_es_movimiento_interno_matches_real_pago_tarjeta_credito():
    assert _es_movimiento_interno("PAGO TARJETA DE CREDITO")


def test_es_movimiento_interno_matches_real_pagos_interbancarios():
    # Descripción real confirmada por el usuario (ver migración
    # finanzas_taxonomia_2026_09_sprint1) — viene con artefactos de OCR.
    assert _es_movimiento_interno("PAGOS INTERBANCARIOS. [-|")


def test_es_movimiento_interno_matches_spei_hacia_tdc():
    assert _es_movimiento_interno("SPEI ENVIADO STP0000000001 PAGO TDC BBVA")


def test_es_movimiento_interno_does_not_match_unrelated_spei():
    # SPEI a una persona no menciona TDC — no debe marcarse como interno.
    assert not _es_movimiento_interno("SPEI ENVIADO NU MEXICO 638 REGALO PARA ANA")


def test_es_movimiento_interno_does_not_match_regular_gasto():
    assert not _es_movimiento_interno("WALMART VENTA EN LINEA")


# Ampliado tras auditar "AQUÍ SI TODOS SON PAGOS A TDC PERO TUS CATEGORIAS
# SON CONFUSAS DEJALOS TODOS EN PAGO_TDC": HSBC e INVEX en esta app son
# exclusivamente bancos emisores de TDC (ver BANK_META), así que un "SPEI
# ENVIADO" hacia cualquiera de los dos siempre es un abono a esa tarjeta,
# nunca un gasto real -- y BBVA/HSBC/INVEX describen ese mismo abono con
# varias frases distintas (BMOVIL.PAGO TDC, [SU PAGO GRACIAS SPEI, SU PAGO
# POR SPEI_T) que antes caían en FINANZAS/Pago servicios en vez de
# MOVIMIENTO_INTERNO/PAGO_TDC.

def test_es_movimiento_interno_matches_spei_enviado_hsbc():
    assert _es_movimiento_interno("SPEI ENVIADO HSBC")


def test_es_movimiento_interno_matches_spei_enviado_invex():
    assert _es_movimiento_interno("A GIOVANY A SPEI ENVIADO INVEX")


def test_es_movimiento_interno_matches_bmovil_pago_tdc():
    assert _es_movimiento_interno("BMOVIL.PAGO TDC")


def test_es_movimiento_interno_matches_pago_gracias_variantes():
    assert _es_movimiento_interno("[SU PAGO GRACIAS SPEI")
    assert _es_movimiento_interno("SUPAGO GRACIAS SPEI")
    assert _es_movimiento_interno("SU PAGO GRACIAS SPEL")  # typo real del banco


def test_es_movimiento_interno_matches_pago_por_spei():
    assert _es_movimiento_interno("SU PAGO POR SPEI_T 8045")


def test_es_movimiento_interno_does_not_match_spei_enviado_a_persona():
    # SPEI enviado a otro banco/persona que no sea HSBC/INVEX no debe
    # marcarse como pago interno de TDC.
    assert not _es_movimiento_interno("SPEI ENVIADO NU MEXICO 638 REGALO PARA ANA")


def test_unify_reclassifies_only_the_given_ids(test_db):
    import database
    with database.get_db() as db:
        id_tdc = _insert(db, descripcion='PAGO TARJETA DE CREDITO', monto=5000.0,
                          categoria='PAGO_TDC', tipo='GASTO')
        id_spei_tdc = _insert(db, descripcion='SPEI ENVIADO STP0000000001 PAGO TDC BBVA',
                               monto=3000.0, categoria='SPEI_ENVIADO', tipo='GASTO')
        id_normal = _insert(db, descripcion='WALMART VENTA EN LINEA', monto=250.0,
                             categoria='ALIMENTACION', subcategoria='Súper', tipo='GASTO')
        # Fila fuera de `ids` -- ya clasificada, no debe tocarse aunque el
        # texto calzaría con la regla.
        id_out_of_scope = _insert(db, descripcion='PAGO TARJETA DE CREDITO', monto=999.0,
                                   categoria='OTRA_COSA_MANUAL', tipo='GASTO')
        db.commit()

        n = _unify_movimiento_interno(db, [id_tdc, id_spei_tdc, id_normal])
        assert n == 2

        row_tdc = db.execute("SELECT categoria, tipo FROM est_movimientos WHERE id=?", (id_tdc,)).fetchone()
        row_spei = db.execute("SELECT categoria, tipo FROM est_movimientos WHERE id=?", (id_spei_tdc,)).fetchone()
        row_normal = db.execute("SELECT tipo FROM est_movimientos WHERE id=?", (id_normal,)).fetchone()
        row_out = db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (id_out_of_scope,)).fetchone()

        assert row_tdc["categoria"] == "PAGO_TDC" and row_tdc["tipo"] == "MOVIMIENTO_INTERNO"
        assert row_spei["categoria"] == "PAGO_TDC" and row_spei["tipo"] == "MOVIMIENTO_INTERNO"
        assert row_normal["tipo"] == "GASTO"
        assert row_out["categoria"] == "OTRA_COSA_MANUAL"  # nunca tocada, no estaba en `ids`


def test_unify_with_empty_ids_does_nothing(test_db):
    import database
    with database.get_db() as db:
        assert _unify_movimiento_interno(db, []) == 0


# ── 3) _detectar_avisos_msi ────────────────────────────────────────────────

def test_avisos_msi_empty_when_no_msi_groups(test_db):
    import database
    with database.get_db() as db:
        _insert(db, descripcion='OXXO GAS', monto=100.0)
        db.commit()
        assert _detectar_avisos_msi(db) == []


def test_avisos_msi_silent_when_group_is_consistent(test_db):
    import database
    with database.get_db() as db:
        gid = msi_group_id("WALMART VENTA EN L", 500.0)
        db.execute("""INSERT INTO est_movimientos
                      (fecha,descripcion,monto,banco,categoria,tipo,
                       parcialidad_num,parcialidad_total,compra_msi_id)
                      VALUES ('2026-01-01','WALMART VENTA EN L',500.0,'BBVA_TDC','ALIMENTACION','GASTO',3,12,?)""",
                   (gid,))
        db.execute("""INSERT INTO est_movimientos
                      (fecha,descripcion,monto,banco,categoria,tipo,
                       parcialidad_num,parcialidad_total,compra_msi_id)
                      VALUES ('2026-02-01','WALMART VENTA EN L',500.0,'BBVA_TDC','ALIMENTACION','GASTO',4,12,?)""",
                   (gid,))
        db.commit()
        assert _detectar_avisos_msi(db) == []


def test_avisos_msi_warns_on_repeated_parcialidad_num(test_db):
    import database
    with database.get_db() as db:
        gid = msi_group_id("WALMART VENTA EN L", 500.0)
        for fecha in ("2026-01-01", "2026-01-02"):
            db.execute("""INSERT INTO est_movimientos
                          (fecha,descripcion,monto,banco,categoria,tipo,
                           parcialidad_num,parcialidad_total,compra_msi_id)
                          VALUES (?,'WALMART VENTA EN L',500.0,'BBVA_TDC','ALIMENTACION','GASTO',3,12,?)""",
                       (fecha, gid))
        db.commit()
        avisos = _detectar_avisos_msi(db)
        assert len(avisos) == 1
        assert avisos[0]["tipo"] == "PARCIALIDAD_REPETIDA"


def test_avisos_msi_warns_on_more_installments_than_expected(test_db):
    import database
    with database.get_db() as db:
        gid = msi_group_id("LIVERPOOL", 900.0)
        for num in range(1, 5):  # 4 mensualidades distintas...
            db.execute("""INSERT INTO est_movimientos
                          (fecha,descripcion,monto,banco,categoria,tipo,
                           parcialidad_num,parcialidad_total,compra_msi_id)
                          VALUES (?,'LIVERPOOL',900.0,'BBVA_TDC','ROPA','GASTO',?,3,?)""",
                       (f"2026-0{num}-01", num, gid))  # ...pero la compra es a 3
        db.commit()
        avisos = _detectar_avisos_msi(db)
        assert len(avisos) == 1
        assert avisos[0]["tipo"] == "MAS_MENSUALIDADES_DE_LAS_ESPERADAS"


# ── 4) _sugerir_viaje_tabasco ──────────────────────────────────────────────

def _insert_viaje(db, nombre, fecha_inicio, fecha_fin, tipo_viaje=''):
    cur = db.execute(
        """INSERT INTO viajes (nombre, destino, fecha_inicio, fecha_fin, tipo_viaje, created_at)
           VALUES (?,?,?,?,?,datetime('now'))""",
        (nombre, '', fecha_inicio, fecha_fin, tipo_viaje),
    )
    return cur.lastrowid


def test_sugerir_viaje_tabasco_matches_by_tipo_viaje_and_date_range(test_db):
    import database
    with database.get_db() as db:
        viaje_id = _insert_viaje(db, 'Visita a la familia', '2026-03-01', '2026-03-10',
                                  tipo_viaje='FAMILIA_TABASCO')
        tx_id = _insert(db, fecha='2026-03-05', descripcion='RESTAURANTE FS VILLAHERMOSA',
                         monto=450.0, categoria='ALIMENTACION', tipo='GASTO')
        db.commit()
        sugerencias = _sugerir_viaje_tabasco(db, [tx_id])
        assert len(sugerencias) == 1
        assert sugerencias[0]['viaje_id'] == viaje_id
        assert sugerencias[0]['id'] == tx_id


def test_sugerir_viaje_tabasco_never_assigns_only_suggests(test_db):
    import database
    with database.get_db() as db:
        _insert_viaje(db, 'Visita a la familia', '2026-03-01', '2026-03-10',
                       tipo_viaje='FAMILIA_TABASCO')
        tx_id = _insert(db, fecha='2026-03-05', descripcion='OXXO VSA CENTRO',
                         monto=80.0, categoria='ALIMENTACION', tipo='GASTO')
        db.commit()
        _sugerir_viaje_tabasco(db, [tx_id])
        row = db.execute("SELECT viaje_id FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()
        assert row['viaje_id'] is None  # sigue sin asignar -- solo se sugirió


def test_sugerir_viaje_tabasco_no_match_outside_date_range(test_db):
    import database
    with database.get_db() as db:
        _insert_viaje(db, 'Visita a la familia', '2026-03-01', '2026-03-10',
                       tipo_viaje='FAMILIA_TABASCO')
        tx_id = _insert(db, fecha='2026-06-01', descripcion='RESTAURANTE FS VILLAHERMOSA',
                         monto=450.0, categoria='ALIMENTACION', tipo='GASTO')
        db.commit()
        assert _sugerir_viaje_tabasco(db, [tx_id]) == []


def test_sugerir_viaje_tabasco_no_trip_no_suggestion(test_db):
    import database
    with database.get_db() as db:
        tx_id = _insert(db, fecha='2026-03-05', descripcion='RESTAURANTE FS VILLAHERMOSA',
                         monto=450.0, categoria='ALIMENTACION', tipo='GASTO')
        db.commit()
        assert _sugerir_viaje_tabasco(db, [tx_id]) == []


def test_sugerir_viaje_tabasco_ignores_unrelated_descripcion(test_db):
    import database
    with database.get_db() as db:
        _insert_viaje(db, 'Visita a la familia', '2026-03-01', '2026-03-10',
                       tipo_viaje='FAMILIA_TABASCO')
        tx_id = _insert(db, fecha='2026-03-05', descripcion='STARBUCKS PLAZA NORTE',
                         monto=80.0, categoria='ALIMENTACION', tipo='GASTO')
        db.commit()
        assert _sugerir_viaje_tabasco(db, [tx_id]) == []


# ── 5) _sugerir_reembolsos / /api/expenses/<id>/conciliar ─────────────────────

def test_sugerir_reembolsos_matches_within_one_percent(test_db):
    import database
    with database.get_db() as db:
        expense_id = _insert(db, fecha='2026-01-01', descripcion='EXPENSE VUELO CLIENTE',
                              monto=-1000.0, categoria='EXPENSE', tipo='GASTO')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PENDIENTE' WHERE id=?", (expense_id,))
        dep_id = _insert(db, fecha='2026-01-15', descripcion='SPEI RECIBIDO REEMBOLSO CLIENTE',
                          monto=1005.0, categoria='SPEI_RECIBIDO', tipo='INGRESO')
        db.commit()
        sugerencias = _sugerir_reembolsos(db, [dep_id])
        assert len(sugerencias) == 1
        assert sugerencias[0]['expense_id'] == expense_id
        assert sugerencias[0]['deposito_id'] == dep_id


def test_sugerir_reembolsos_no_match_outside_one_percent(test_db):
    import database
    with database.get_db() as db:
        expense_id = _insert(db, fecha='2026-01-01', descripcion='EXPENSE VUELO CLIENTE',
                              monto=-1000.0, categoria='EXPENSE', tipo='GASTO')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PENDIENTE' WHERE id=?", (expense_id,))
        dep_id = _insert(db, fecha='2026-01-15', descripcion='SPEI RECIBIDO OTRA COSA',
                          monto=1100.0, categoria='SPEI_RECIBIDO', tipo='INGRESO')
        db.commit()
        assert _sugerir_reembolsos(db, [dep_id]) == []


def test_sugerir_reembolsos_ignores_expense_already_pagado(test_db):
    import database
    with database.get_db() as db:
        expense_id = _insert(db, fecha='2026-01-01', descripcion='EXPENSE VUELO CLIENTE',
                              monto=-1000.0, categoria='EXPENSE', tipo='GASTO')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PAGADO' WHERE id=?", (expense_id,))
        dep_id = _insert(db, fecha='2026-01-15', descripcion='SPEI RECIBIDO REEMBOLSO CLIENTE',
                          monto=1000.0, categoria='SPEI_RECIBIDO', tipo='INGRESO')
        db.commit()
        assert _sugerir_reembolsos(db, [dep_id]) == []


def test_sugerir_reembolsos_never_marks_pagado_by_itself(test_db):
    import database
    with database.get_db() as db:
        expense_id = _insert(db, fecha='2026-01-01', descripcion='EXPENSE VUELO CLIENTE',
                              monto=-1000.0, categoria='EXPENSE', tipo='GASTO')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PENDIENTE' WHERE id=?", (expense_id,))
        dep_id = _insert(db, fecha='2026-01-15', descripcion='SPEI RECIBIDO REEMBOLSO CLIENTE',
                          monto=1000.0, categoria='SPEI_RECIBIDO', tipo='INGRESO')
        db.commit()
        _sugerir_reembolsos(db, [dep_id])
        row = db.execute("SELECT estatus_reembolso FROM est_movimientos WHERE id=?", (expense_id,)).fetchone()
        assert row['estatus_reembolso'] == 'PENDIENTE'  # solo se sugirió, no se marcó solo


def test_conciliar_expense_endpoint_marks_pagado(test_db):
    import database
    from app import create_app
    with database.get_db() as db:
        expense_id = _insert(db, fecha='2026-01-01', descripcion='EXPENSE VUELO CLIENTE',
                              monto=-1000.0, categoria='EXPENSE', tipo='GASTO')
        db.execute("UPDATE est_movimientos SET estatus_reembolso='PENDIENTE' WHERE id=?", (expense_id,))
        db.commit()

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['app_ok'] = True
            sess['fin_ok'] = True
        resp = client.post(f'/finanzas/estados/api/expenses/{expense_id}/conciliar',
                            json={'fecha_reembolso': '2026-01-15'})
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

    with database.get_db() as db:
        row = db.execute(
            "SELECT estatus_reembolso, fecha_reembolso FROM est_movimientos WHERE id=?", (expense_id,)
        ).fetchone()
    assert row['estatus_reembolso'] == 'PAGADO'
    assert row['fecha_reembolso'] == '2026-01-15'
