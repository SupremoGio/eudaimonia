"""
test_finanzas_bank_detection.py — cubre el ajuste a _detect_bank_pdf, a
petición explícita del usuario tras confirmar (con screenshot) que el
mismo depósito de nómina real se importó dos veces con banco distinto:
"PAGO DE NOMINA HH" quedó como BBVA_DEB y "PAGO DE NOMINA / HH
4206466060 FIBRA HOTELERA SC" quedó como BBVA_TDC.

Antes, cuando el texto extraído del PDF contenía "BBVA" pero no calzaba
con ninguna de las dos firmas de encabezado conocidas (LIB o DEB), la
función asumía TDC a ciegas -- sin importar si en realidad era un
estado de cuenta de débito con una plantilla/extracción distinta a la
esperada. Ahora, en ese caso ambiguo, primero se revisa si el nombre
del archivo trae una pista explícita de débito antes de asumir TDC.
"""
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finanzas.estados import parsers


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakePdf:
    def __init__(self, text):
        self.pages = [_FakePage(text)]
        self.closed = False

    def close(self):
        self.closed = True


def _detect(monkeypatch, text, filename):
    monkeypatch.setattr(parsers, "_open_pdf", lambda path: _FakePdf(text))
    return parsers._detect_bank_pdf(Path(filename))


def test_deb_signature_still_detected_as_deb(monkeypatch):
    text = "BBVA ... DETALLES DE MOVIMIENTOS ... SALDO TOTAL ..."
    assert _detect(monkeypatch, text, "estado_cuenta.pdf") == "BBVA_DEB"


def test_lib_signature_still_detected_as_lib(monkeypatch):
    text = "BBVA ... DETALLE DE MOVIMIENTOS REALIZADOS ..."
    assert _detect(monkeypatch, text, "libreton.pdf") == "BBVA_LIB"


def test_ambiguous_bbva_text_defaults_to_tdc_when_filename_has_no_hint(monkeypatch):
    text = "BBVA ALGO QUE NO CALZA NINGUNA FIRMA CONOCIDA"
    assert _detect(monkeypatch, text, "descarga.pdf") == "BBVA_TDC"


def test_ambiguous_bbva_text_uses_filename_debito_hint_instead_of_tdc(monkeypatch):
    """El caso que causó el bug real: texto ambiguo (ninguna firma calza)
    mezclado con un archivo que sí se llama como estado de débito --
    ya no debe asumirse TDC a ciegas."""
    text = "BBVA ALGO QUE NO CALZA NINGUNA FIRMA CONOCIDA"
    assert _detect(monkeypatch, text, "BBVA_DEB_agosto.pdf") == "BBVA_DEB"
    assert _detect(monkeypatch, text, "estado_debito_septiembre.pdf") == "BBVA_DEB"
    assert _detect(monkeypatch, text, "cheques_bbva.pdf") == "BBVA_DEB"


def test_ambiguous_bbva_text_with_tdc_filename_hint_stays_tdc(monkeypatch):
    text = "BBVA ALGO QUE NO CALZA NINGUNA FIRMA CONOCIDA"
    assert _detect(monkeypatch, text, "BBVA_TDC_agosto.pdf") == "BBVA_TDC"
