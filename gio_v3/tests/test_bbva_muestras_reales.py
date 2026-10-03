"""Regresión con texto real (cuentas enmascaradas) de los PDF de BBVA, sacado
con pdfplumber por la auditoría 2022-2026 (tests/fixtures/bbva_muestras/).

- Libretón abr-2026, págs. 3-4: no traen el encabezado «CARGOS ABONOS» (solo
  sale en la pág. 1) y la muestra no trae el saldo anterior, así que el saldo
  no alcanza para decidir los «PAGO CUENTA DE TERCERO». Seis abonos salían
  como GASTO; la columna del monto (layout) los decide.
- Exportación «movimientos*.pdf» sep-2026: monto con signo y centavos sin
  punto; descripción en la línea anterior y posterior a la fecha, y un renglón
  («prestamo») que se parte entre páginas.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.finanzas.estados.parsers import bbva_debit, bbva_libreton

_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'bbva_muestras')


def _paginas(nombre, layout):
    with open(os.path.join(_DIR, nombre), encoding='utf-8') as f:
        bloques = f.read().split('===== PÁGINA')[1:]
    return '\n'.join(cuerpo for cab, cuerpo in (b.split('=====\n', 1) for b in bloques)
                     if ('layout=True' in cab) == layout)


def test_libreton_sin_encabezado_decide_por_columna():
    # La muestra es parcial (falta la pág. 2): sus totales impresos no pueden cuadrar.
    plano = _paginas('libreton_debito.txt', False).replace('TOTAL IMPORTE', 'XTOTAL')
    movs = bbva_libreton._parse_text(plano, (3, 2026, 4, 2026), None)
    bbva_libreton.blindar(movs, plano, _paginas('libreton_debito.txt', True))
    tipo = {(m['fecha'], m['monto']): m['tipo'] for m in movs}
    for clave in [('2026-03-10', 2000.0), ('2026-03-22', 57.0), ('2026-03-23', 500.0),
                  ('2026-03-23', 1110.0), ('2026-03-26', 227.0), ('2026-03-29', 6000.0),
                  ('2026-03-13', 10415.58), ('2026-03-09', 3800.0), ('2026-03-31', 2299.0)]:
        assert tipo[clave] == 'INGRESO', clave
    for clave in [('2026-03-12', 505.0), ('2026-03-17', 1700.0), ('2026-03-17', 3.0),
                  ('2026-03-19', 8000.0), ('2026-03-09', 12000.0), ('2026-03-30', 13937.06),
                  ('2026-04-01', 200.0)]:
        assert tipo[clave] == 'GASTO', clave
    assert all(m.get('dir_verificada') for m in movs)
    desc = {(m['fecha'], m['monto']): m['descripcion'] for m in movs}
    assert desc[('2026-03-29', 6000.0)] == 'PAGO CUENTA DE TERCERO BNET …6230 TRANSF A GIOVANY A'
    assert 'FIBRA' not in desc[('2026-03-29', 6000.0)]
    assert 'FIDEICOMISO' in desc[('2026-03-31', 2299.0)]


def test_exportacion_movimientos_signo_y_descripcion():
    movs = bbva_debit._parse_text(_paginas('movimientos_exportacion.txt', False), None)
    assert len(movs) == 29
    assert not [m for m in movs if m['monto'] == 0]
    por = {(m['fecha'], m['monto'], m['tipo']): m['descripcion'] for m in movs}
    # Envío y devolución de $4,500 el 11 sep: dos movimientos, uno de cada lado.
    assert por[('2026-09-11', 4500.0, 'INGRESO')] == 'PAGO CUENTA DE TERCERO BNET …6230 TRANSF A GIOVANY A'
    assert por[('2026-09-11', 4500.0, 'GASTO')] == 'PAGO CUENTA DE TERCERO BNET …6230 PRESTAMO'
    assert por[('2026-09-19', 4486.0, 'GASTO')].startswith('SPEI ENVIADO INVEX')
    assert por[('2026-09-17', 555.0, 'GASTO')].endswith('SEGURO CARRO SEPT')
    assert por[('2026-09-15', 10507.57, 'INGRESO')] == 'PAGO DE NOMINA HH FIBRA HOTELERA SC'
    assert por[('2026-09-09', 17963.43, 'GASTO')] == 'PAGO TARJETA DE CREDITO'
    assert ('2026-09-25', 105.0, 'INGRESO') in por
    assert ('2026-08-23', 1700.0, 'GASTO') in por
    assert round(sum(m['monto'] for m in movs if m['tipo'] == 'INGRESO'), 2) == 48421.40
