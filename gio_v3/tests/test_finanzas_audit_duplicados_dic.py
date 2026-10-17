"""
test_finanzas_audit_duplicados_dic.py — el usuario mandó "AUDITA PORQUE HAY
MONTOS Y DIAS REPETIDOS..." con evidencia real de duplicados BBVA_DEB/
BBVA_TDC (mismo día, mismo monto, banco distinto -- confirmó que ese tipo
de ingreso nunca llega por TDC) más ~16 reclasificaciones puntuales con
ids/descripciones reales. Todo se implementó en la migración
finanzas_audit_duplicados_dic_2026_09 (database.py).

Regla del usuario, reforzada explícitamente en este mensaje: nunca borrar
datos automáticamente. Los duplicados confirmados se marcan (categoria=
FINANZAS, fuera de Total Ingreso/Gasto) en vez de eliminarse, quedando
visibles para que el usuario los revise o borre a mano si está de acuerdo.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _insert(db, **kw):
    defaults = dict(fecha='2026-06-02', fecha_cargo='2026-06-02',
                     descripcion='X', monto=100.0,
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


def _reset_migration(db):
    db.execute("DELETE FROM migration_log WHERE version='finanzas_audit_duplicados_dic_2026_09'")
    db.execute("DELETE FROM migration_log WHERE version='finanzas_dedup_nafin_tdc_2026_09'")


def _row(db, tx_id):
    return db.execute("SELECT * FROM est_movimientos WHERE id=?", (tx_id,)).fetchone()


def _force_next_id(db, target_id):
    db.execute("DELETE FROM sqlite_sequence WHERE name='est_movimientos'")
    db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('est_movimientos', ?)", (target_id - 1,))


# ── 1) Duplicados DEB/TDC de SPEI RECIBIDO ──────────────────────────────────

def test_duplicado_tdc_de_spei_recibido_se_marca_no_se_borra(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        id_deb = _insert(db, descripcion='SPEI RECIBIDONU MEXICO 638 0040826TRANSFERENCIA',
                          monto=3000.0, banco='BBVA_DEB', categoria='APORTACION_RENTA', tipo='INGRESO')
        id_tdc = _insert(db, descripcion='SPEI RECIBIDONU MEXICO / 0192086653 638 0040826TRANSFERENCIA',
                          monto=3000.0, banco='BBVA_TDC', categoria='APORTACION_RENTA', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        deb = _row(db, id_deb)
        tdc = _row(db, id_tdc)
    # El DEB sobrevive y se unifica a la clasificación real de ingreso.
    assert deb['categoria'] == 'VIVIENDA'
    assert deb['subcategoria'] == 'Aportación renta'
    # El TDC se marca como duplicado (nunca borrado) y queda fuera de FINANZAS.
    assert tdc['categoria'] == 'FINANZAS'
    assert 'duplicado' in tdc['subcategoria'].lower()
    # Ninguna fila desapareció.
    with database.get_db() as db:
        total = db.execute("SELECT COUNT(*) c FROM est_movimientos").fetchone()['c']
    assert total == 2


def test_apartacion_renta_sin_gemelo_tdc_no_se_marca_duplicado(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SPEI RECIBIDONU MEXICO 638 0170426TRANSFERENCIA',
                         monto=500.0, banco='BBVA_DEB', categoria='APORTACION_RENTA', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Aportación renta'


def test_id_2238_marcado_duplicado_de_2121(test_db):
    """El usuario confirmó, tras revisar el marcado, que sí son duplicados
    y pidió borrar todo menos el lado BBVA_DEB -- ver
    finanzas_borra_duplicados_confirmados_2026_09 (test dedicado en
    test_finanzas_borra_duplicados_confirmados.py). Aquí solo se confirma
    que el lado BBVA_DEB (2121) sigue vivo y bien clasificado."""
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2121)
        id_2121 = _insert(db, descripcion='DEPOSITO DE TERCERO REFBNTC00305286 PREPAGO GDLAC BMRCASH',
                           monto=4582.0, banco='BBVA_DEB', categoria='INVERSION', tipo='INVERSION')
        assert id_2121 == 2121
        db.commit()
    database.init_db()
    with database.get_db() as db:
        gemelo = _row(db, 2121)
    assert gemelo['categoria'] == 'FINANZAS'
    assert gemelo['subcategoria'] == 'Reembolsable'


# ── 2) Mojibake subcategoria ─────────────────────────────────────────────────

def test_mojibake_aportacion_renta_corregido(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SPEI RECIBIDONUBANK', categoria='VIVIENDA',
                         subcategoria='AportaciÃ³n renta', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['subcategoria'] == 'Aportación renta'


# ── 3) Renta re-barrida (CASA/HOGAR o VIVIENDA/Artículos del hogar) ─────────

def test_renta_depto_807_re_barrida_desde_casa_hogar(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='BNET 8B PAGO TARJETA DE TERCEROS MBAN DEPOSITO EFECTIVO PRACTIC ******1804 MAR09',
                         monto=3800.0, categoria='CASA/HOGAR', subcategoria='Renta depto 807')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_renta_re_barrida_desde_articulos_del_hogar_mal_migrado(test_db):
    """Simula el caso en que la migración anterior (batch EJECUTA ESTO) ya
    había corrido y dejado, por su filtro de monto=12000 exacto, una fila
    de renta en VIVIENDA/Artículos del hogar en vez de VIVIENDA/Renta."""
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='DEPOSITO EFECTIVO RENTA DEPTO 807',
                         monto=3800.0, categoria='VIVIENDA', subcategoria='Artículos del hogar')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'


def test_articulos_del_hogar_reales_no_se_tocan(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='HOME DEPOT MEXICO', monto=800.0,
                         categoria='VIVIENDA', subcategoria='Artículos del hogar')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['subcategoria'] == 'Artículos del hogar'


# ── 4) Depósito de renta marcado GASTO en vez de INGRESO ────────────────────

def test_deposito_efectivo_renta_se_voltea_a_gasto(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='DEPOSITO EFECTIVO PRACTIC ******1804 RENTA A178 FOLIO:2710',
                         monto=4000.0, categoria='FINANZAS', subcategoria='Transferencia', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'GASTO'
    assert row['categoria'] == 'VIVIENDA'
    assert row['subcategoria'] == 'Renta'
    assert row['monto'] == -4000.0


# ── 5) Reembolsos de EXPENSE mal etiquetados (por id exacto) ────────────────

def test_reembolsos_expense_por_id_van_a_finanzas_reembolsable(test_db):
    ids_reales = [1810, 1975, 1909, 1955, 1831, 2123, 2023, 2390, 1852, 1976, 1905, 2124, 1921]
    tx_ids = []
    with database.get_db() as db:
        _reset_migration(db)
        for target_id in sorted(ids_reales):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion=f'PAGO CUENTA DE TERCERO BNET {target_id}',
                              categoria='NOMINA', subcategoria='Regalos', tipo='INGRESO')
            assert new_id == target_id
            tx_ids.append(new_id)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in tx_ids:
            row = _row(db, tx_id)
            assert row['categoria'] == 'FINANZAS'
            assert row['subcategoria'] == 'Reembolsable'


def test_fila_no_listada_no_se_toca_por_reembolsos_expense(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 9999)
        tx_id = _insert(db, descripcion='PAGO DE NOMINA FIBRA HOTELERA SC', categoria='NOMINA',
                        subcategoria='Pago nominal', tipo='INGRESO')
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'NOMINA'
    assert row['subcategoria'] == 'Pago nominal'


# ── 6) FIDEICOMISO F 1596 unificado ─────────────────────────────────────────

def test_fideicomiso_unificado_por_id(test_db):
    ids_reales = [2580, 2529, 2494, 2371, 2247, 2057, 2006, 1625, 2104, 1726]
    tx_ids = []
    with database.get_db() as db:
        _reset_migration(db)
        for i, target_id in enumerate(sorted(ids_reales)):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion='FIDEICOMISO F 1596', categoria='FINANZAS',
                              subcategoria='Transferencia', tipo='INGRESO', monto=100.0 + i)
            assert new_id == target_id
            tx_ids.append(new_id)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in tx_ids:
            row = _row(db, tx_id)
            assert row['subcategoria'] == 'Fideicomiso'


# ── 7) Retiros de CETES (NAFIN) alineados al modelo INVERSION ──────────────

def test_retiros_cetes_nafin_alineados_a_inversion(test_db):
    # 2236 y 2235 se excluyen de aquí a propósito: son los duplicados
    # BBVA_TDC de 2143/2139 (ver test_ids_2236_2235_marcados_duplicado_no_cetes
    # abajo) -- no deben terminar como un retiro de CETES real más, o
    # duplicarían el monto retirado en la vista de Inversiones.
    ids_reales = [1842, 1961, 2573, 2572, 2576, 2575, 2139, 2143, 2076]
    tx_ids = []
    with database.get_db() as db:
        _reset_migration(db)
        for i, target_id in enumerate(sorted(ids_reales)):
            _force_next_id(db, target_id)
            new_id = _insert(db, descripcion='SPEI RECIBIDONAFIN', categoria='FINANZAS',
                              subcategoria='Transferencia', tipo='INGRESO', monto=700.0 + i)
            assert new_id == target_id
            tx_ids.append(new_id)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        for tx_id in tx_ids:
            row = _row(db, tx_id)
            assert row['tipo'] == 'INVERSION'
            assert row['categoria'] == 'CETES'
            assert row['subcategoria'] == 'RETIRO'
            assert row['monto'] >= 700.0


def test_ids_2236_2235_no_duplican_retiro_de_cetes(test_db):
    """2236/2235 (BBVA_TDC) son el mismo movimiento real que 2143/2139
    (BBVA_DEB, mismo día, mismo monto, misma referencia "135 ... EGRESOS
    SPEI SVD") -- el usuario ya confirmó que sí son duplicados y pidió
    borrarlos (ver finanzas_borra_duplicados_confirmados_2026_09, con test
    dedicado en test_finanzas_borra_duplicados_confirmados.py). Aquí solo
    se confirma que el lado BBVA_DEB (2143/2139) sigue vivo como retiro
    real de CETES."""
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2139)
        id_deb_1 = _insert(db, descripcion='SPEI RECIBIDONAFIN 135 EGRESOS SPEI SVD',
                            banco='BBVA_DEB', categoria='FINANZAS', subcategoria='Transferencia',
                            tipo='INGRESO', monto=4107.78, fecha='2026-06-10')
        assert id_deb_1 == 2139
        _force_next_id(db, 2143)
        id_deb_2 = _insert(db, descripcion='SPEI RECIBIDONAFIN 135 EGRESOS SPEI SVD DOS',
                            banco='BBVA_DEB', categoria='FINANZAS', subcategoria='Transferencia',
                            tipo='INGRESO', monto=10000.0, fecha='2026-06-08')
        assert id_deb_2 == 2143
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row_2139 = _row(db, 2139)
        row_2143 = _row(db, 2143)
    assert row_2139['tipo'] == 'INVERSION'
    assert row_2139['categoria'] == 'CETES'
    assert row_2143['tipo'] == 'INVERSION'
    assert row_2143['categoria'] == 'CETES'


def test_categoria_inversion_literal_corregida_a_cetes(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SPEI RECIBIDONAFIN', categoria='INVERSION',
                         subcategoria='', tipo='INVERSION', monto=6500.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'CETES'
    assert row['subcategoria'] == 'RETIRO'


def test_fila_3220_ya_correcta_no_se_altera(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 3220)
        tx_id = _insert(db, descripcion='SPEI RECIBIDONAFIN', categoria='CETES',
                        subcategoria='RETIRO', tipo='INVERSION', monto=4090.15)
        assert tx_id == 3220
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'CETES'
    assert row['subcategoria'] == 'RETIRO'
    assert row['monto'] == 4090.15


# ── 8) ids 2121 y 1886 ───────────────────────────────────────────────────────

def test_id_2121_es_reembolso_expense_no_inversion(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2121)
        tx_id = _insert(db, descripcion='DEPOSITO DE TERCERO REFBNTC00305286 PREPAGO GDLAC BMRCASH',
                        categoria='INVERSION', subcategoria='', tipo='INVERSION', monto=4582.0)
        assert tx_id == 2121
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'INGRESO'
    assert row['categoria'] == 'FINANZAS'
    assert row['subcategoria'] == 'Reembolsable'


def test_id_1886_es_pago_tdc_invex_no_inversion(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 1886)
        tx_id = _insert(db, descripcion='SPEI ENVIADO INVEX', categoria='INVERSION',
                        subcategoria='', tipo='INVERSION', monto=928.0)
        assert tx_id == 1886
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'MOVIMIENTO_INTERNO'
    assert row['categoria'] == 'PAGO_TDC'


# ── 9) NOMINA nunca en BBVA_TDC ─────────────────────────────────────────────

def test_nomina_en_bbva_tdc_se_corrige_a_bbva_deb(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='PAGO DE NOMINA / HH 4206466060 FIBRA HOTELERA SC',
                         categoria='NOMINA', subcategoria='Pago nominal', banco='BBVA_TDC',
                         tipo='INGRESO', monto=10273.28)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['banco'] == 'BBVA_DEB'


def test_nomina_en_bbva_deb_no_se_toca(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='PAGO DE NOMINA FIBRA HOTELERA SC', categoria='NOMINA',
                         subcategoria='Pago nominal', banco='BBVA_DEB', tipo='INGRESO', monto=10367.36)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['banco'] == 'BBVA_DEB'


# ── 10) id 3228 TRANSFERENCIA -> PRESTAMOS ──────────────────────────────────

def test_id_3228_transferencia_a_prestamos(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 3228)
        tx_id = _insert(db, descripcion='PAGO CUENTA DE TERCERO BNET TRANSF A GIOVANY A',
                        categoria='TRANSFERENCIA', tipo='INGRESO', monto=1900.0)
        assert tx_id == 3228
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'PRESTAMOS'


# ── 11) Consolidación MOVIMIENTO_INTERNO -> PAGO_TDC ────────────────────────

def test_movimiento_interno_existente_unificado_a_pago_tdc(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SPEI ENVIADO HSBC 021 0509260TDC HSBC',
                         categoria='FINANZAS', subcategoria='Pago servicios', tipo='MOVIMIENTO_INTERNO',
                         monto=502.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'PAGO_TDC'
    assert row['subcategoria'] == ''


# ── 12) Pagos de TDC reconocidos por texto -> MOVIMIENTO_INTERNO/PAGO_TDC ──

def test_pago_tdc_por_texto_se_convierte_movimiento_interno(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='BMOVIL.PAGO TDC', categoria='FINANZAS',
                         subcategoria='Pago servicios', tipo='PAGO', monto=-14380.57)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'MOVIMIENTO_INTERNO'
    assert row['categoria'] == 'PAGO_TDC'


def test_su_pago_gracias_se_convierte_movimiento_interno(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='SU PAGO GRACIAS SPEI | -|', banco='HSBC',
                         categoria='FINANZAS', subcategoria='Pago servicios', tipo='PAGO', monto=2695.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'MOVIMIENTO_INTERNO'
    assert row['categoria'] == 'PAGO_TDC'


def test_ajuste_tipo_cambio_no_se_toca(test_db):
    """No es un pago de TDC -- es un ajuste de tipo de cambio de un cargo
    de suscripción, debe quedarse tal cual."""
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='AJUSTE TIPO CAMBIO ANTHROPIC CLAUDE SU', banco='INVEX',
                         categoria='FINANZAS', subcategoria='Pago servicios', tipo='PAGO', monto=-2.09)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'PAGO'
    assert row['categoria'] == 'FINANZAS'


def test_retiro_efectivo_no_se_toca_por_regla_tdc(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='BNET P RETIRO SIN TARJETA ******7852',
                         categoria='FINANZAS', subcategoria='Retiro efectivo', tipo='PAGO', monto=1500.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['tipo'] == 'PAGO'
    assert row['subcategoria'] == 'Retiro efectivo'


def test_restaurante_no_se_toca_por_regla_tdc(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        tx_id = _insert(db, descripcion='BNET TACOS PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER',
                         categoria='ALIMENTACION', subcategoria='Restaurante', tipo='PAGO', monto=2000.0)
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row = _row(db, tx_id)
    assert row['categoria'] == 'ALIMENTACION'
    assert row['subcategoria'] == 'Restaurante'


# ── 13) ids 2445/2440: aportación de renta del roomie, no PAGO ─────────────

def test_ids_2445_2440_son_aportacion_renta_roomie(test_db):
    with database.get_db() as db:
        _reset_migration(db)
        _force_next_id(db, 2440)
        id_2440 = _insert(db, descripcion='SPEI RECIBIDONUBANK / 0155726146 638 0140826TRANSFERENCIA',
                          banco='BBVA_TDC', categoria='FINANZAS', subcategoria='Pago servicios',
                          tipo='PAGO', monto=1000.0)
        assert id_2440 == 2440
        _force_next_id(db, 2445)
        id_2445 = _insert(db, descripcion='SPEI RECIBIDONUBANK / 0110384402 638 0070826TRANSFERENCIA',
                          banco='BBVA_TDC', categoria='FINANZAS', subcategoria='Pago servicios',
                          tipo='PAGO', monto=2500.0)
        assert id_2445 == 2445
        db.commit()
    database.init_db()
    with database.get_db() as db:
        row_2440 = _row(db, 2440)
        row_2445 = _row(db, 2445)
    for row in (row_2440, row_2445):
        assert row['tipo'] == 'INGRESO'
        assert row['categoria'] == 'VIVIENDA'
        assert row['subcategoria'] == 'Aportación renta'
        assert row['monto'] > 0


# ── Migración idempotente / logueada una vez ────────────────────────────────

def test_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_audit_duplicados_dic_2026_09'"
        ).fetchall()
    assert len(rows) == 1


def test_dedup_nafin_tdc_migration_logged_once(test_db):
    with database.get_db() as db:
        rows = db.execute(
            "SELECT id FROM migration_log WHERE version='finanzas_dedup_nafin_tdc_2026_09'"
        ).fetchall()
    assert len(rows) == 1
