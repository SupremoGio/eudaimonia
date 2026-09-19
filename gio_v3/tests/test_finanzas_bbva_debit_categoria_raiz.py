"""
test_finanzas_bbva_debit_categoria_raiz.py — causa raíz de los duplicados
DEB/TDC y de varias reclasificaciones incorrectas que el usuario reportó en
la auditoría "AUDITA PORQUE HAY MONTOS Y DIAS REPETIDOS...": bbva_debit.py
y bbva_libreton.py (los parsers de estado de cuenta débito BBVA) tenían su
propio diccionario de categorización (CATS_DEBIT/CATS_LIBRETON) que nunca
pasaba por get_categoria_subcategoria() de config.py -- así que ninguno de
los keywords de comercio acumulados esta sesión (CRISTAL VILLAHERMOSA,
ZEPELIN, SALSA, etc.) aplicaba a movimientos importados por estos dos
parsers, y además:
  - "NOMINA" hacía match con la sola palabra "FIBRA HOTELERA", clasificando
    como nómina real depósitos de reembolso de EXPENSE del mismo empleador
    ("FIBRA HOTELERA SC PAGO CUENTA DE TERCERO BNET").
  - "INVERSION" (con "NAFIN" incluido en bbva_libreton.py) generaba
    categoria='INVERSION' literal, un formato inválido para el modelo de
    inversiones (categoria debe ser la plataforma, ej. CETES/GBM).

Fix: get_categoria_subcategoria() (config.py) se prueba primero (solo para
GASTO, igual que parsers/_base.py), y el cajón legacy que sigue existiendo
para movimientos bancarios genéricos remapea a la taxonomía unificada
(NOMINA solo con "PAGO DE NOMINA", el resto a FINANZAS/<subcategoria
descriptiva>, sin bucket de INVERSION).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.parsers.bbva_debit import _categorize as categorize_debit
from modules.finanzas.estados.parsers.bbva_libreton import _categorize as categorize_libreton


# ── bbva_debit.py ────────────────────────────────────────────────────────────

def test_debit_usa_config_primero_para_gasto():
    """Un GASTO con un keyword de comercio conocido en config.py (ZEPELIN)
    debe clasificarse con esa regla, no caer en el cajón legacy."""
    cat, sub = categorize_debit('CLIP MX MEC ZEPELIN EN GUADALAJARA', es_gasto=True)
    assert (cat, sub) == ('ALIMENTACION', 'Fast Food')


def test_debit_no_prueba_config_para_ingreso():
    """Para INGRESO no se prueba config.py (pensado para texto de
    comercio en compras) -- cae directo al cajón legacy bancario."""
    cat, sub = categorize_debit('SPEI RECIBIDO DE ALGUIEN', es_gasto=False)
    assert cat == 'FINANZAS'
    assert sub == 'Transferencia recibida'


def test_debit_nomina_requiere_pago_de_nomina_explicito():
    cat, sub = categorize_debit('PAGO DE NOMINA FIBRA HOTELERA SC', es_gasto=False)
    assert (cat, sub) == ('NOMINA', 'Pago nominal')


def test_debit_fibra_hotelera_sola_ya_no_es_nomina():
    """Caso real: un reembolso de EXPENSE del mismo empleador, sin "PAGO DE
    NOMINA", ya no debe caer en NOMINA."""
    cat, sub = categorize_debit('FIBRA HOTELERA SC PAGO CUENTA DE TERCERO BNET', es_gasto=False)
    assert cat != 'NOMINA'
    assert (cat, sub) == ('FINANZAS', 'Transferencia')


def test_debit_ya_no_produce_categoria_inversion_literal():
    """CATS_DEBIT nunca tuvo bucket INVERSION explícito, pero se confirma
    que ningún texto de fondo/inversión cae ahí -- debe ir a OTROS."""
    cat, sub = categorize_debit('FONDO DE INVERSION XYZ', es_gasto=False)
    assert cat != 'INVERSION'


def test_debit_transferencia_legacy_va_a_finanzas():
    cat, sub = categorize_debit('PAGO CUENTA DE TERCERO BNET TRANSF A ALGUIEN', es_gasto=False)
    assert (cat, sub) == ('FINANZAS', 'Transferencia')


def test_debit_pago_tdc_mantiene_categoria_pago_tdc():
    cat, sub = categorize_debit('PAGO TARJETA DE CREDITO', es_gasto=False)
    assert (cat, sub) == ('PAGO_TDC', '')


def test_debit_fideicomiso_va_a_finanzas():
    cat, sub = categorize_debit('SITH2PAGOGDLAC FIDEICOMISO F 1596', es_gasto=False)
    assert (cat, sub) == ('FINANZAS', 'Fideicomiso')


def test_debit_sin_match_es_otros():
    cat, sub = categorize_debit('ALGO COMPLETAMENTE DESCONOCIDO XYZ', es_gasto=False)
    assert (cat, sub) == ('OTROS', '')


# ── bbva_libreton.py ─────────────────────────────────────────────────────────

def test_libreton_nafin_ya_no_produce_categoria_inversion_literal():
    """Caso real: retiros de CETES vía NAFIN quedaban con categoria=
    'INVERSION' literal porque "NAFIN" estaba en el bucket INVERSION de
    CATS_LIBRETON -- ese bucket ya no existe."""
    cat, sub = categorize_libreton('SPEI RECIBIDONAFIN 135 EGRESOS SPEI SVD', es_gasto=False)
    assert cat != 'INVERSION'


def test_libreton_usa_config_primero_para_gasto():
    cat, sub = categorize_libreton('CLIP MX MEC ZEPELIN EN GUADALAJARA', es_gasto=True)
    assert (cat, sub) == ('ALIMENTACION', 'Fast Food')


def test_libreton_nomina_requiere_pago_de_nomina_explicito():
    cat, sub = categorize_libreton('PAGO DE NOMINA FIBRA HOTELERA SC', es_gasto=False)
    assert (cat, sub) == ('NOMINA', 'Pago nominal')


def test_libreton_fibra_hotelera_sola_ya_no_es_nomina():
    cat, sub = categorize_libreton('FIBRA HOTELERA SC RETIRO SIN TARJETA', es_gasto=False)
    assert cat != 'NOMINA'
