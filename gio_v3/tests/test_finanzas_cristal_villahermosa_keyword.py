"""
test_finanzas_cristal_villahermosa_keyword.py — al investigar "qué pasó con
los pagos de CRISTAL VILLAHERMOSA de jul-ago-sep" se encontró que config.py
tenía un keyword genérico "CRISTAL" -> VIVIENDA/Artículos del hogar (junto a
TEMU, MONARCA, MINISO -- tiendas de artículos para el hogar), y por ser
substring-match interceptaba también "CRISTAL VILLAHERMOSA" en cualquier
importación futura, mandándolo a VIVIENDA en vez de FAMILIA_REGALOS/Regalos
como pidió el usuario ("PONLO TODOS COMO FAMILIA_REGALOS").

Esto es el mismo patrón de bug que SALSA/FUSION GIO y ZEPELIN: un keyword
más amplio y anterior en el diccionario CATEGORIAS ganaba antes de que se
pudiera evaluar el más específico. Fix: se agrega "CRISTAL VILLAHERMOSA"
como su propia entrada, antes de "CRISTAL" en el diccionario (insertion
order = orden de evaluación, primer match gana), sin tocar el
comportamiento del keyword genérico "CRISTAL" para compras reales de
cristalería/vidrio.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados.config import get_categoria_subcategoria


def test_cristal_villahermosa_va_a_familia_regalos():
    cat, sub = get_categoria_subcategoria('SPEI ENVIADO CRISTAL VILLAHERMOSA')
    assert (cat, sub) == ('FAMILIA_REGALOS', 'Regalos')


def test_cristal_villahermosa_con_prefijo_bancario():
    cat, sub = get_categoria_subcategoria('766236 PAGO A CRISTAL VILLAHERMOSA MBAN')
    assert (cat, sub) == ('FAMILIA_REGALOS', 'Regalos')


def test_cristal_generico_sigue_siendo_vivienda():
    """Una compra real de cristalería/vidrio (sin 'VILLAHERMOSA') no debe
    verse afectada -- el keyword genérico 'CRISTAL' sigue mapeando a
    VIVIENDA/Artículos del hogar."""
    cat, sub = get_categoria_subcategoria('TIENDA CRISTAL Y ACCESORIOS')
    assert (cat, sub) == ('VIVIENDA', 'Artículos del hogar')
