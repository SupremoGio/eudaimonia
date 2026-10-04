"""Auditoría 2022-2026 de los movimientos BBVA contra los PDF (Cowork, 2026-10-03).

`data/auditoria_pdf_2022_2026.csv` trae SOLO las filas con error, con la
columna `estado`:
  - CORREGIR      dirección, descripción mezclada/perdida, RFC en lugar del
                  comercio o monto distinto -> se corrige la fila `id_app`.
  - FALTA_EN_APP  se crea con lo del PDF.
  - SOBRA_EN_APP  monto 0.00 -> se borra; «posible duplicado de id X» -> se
                  borra solo si X existe y es el mismo movimiento; si no está
                  en el PDF y no es duplicado, NO se borra (queda a revisión).
  - DUDA          no se toca, solo sale en el reporte.

`plan(db)` es la simulación (no escribe nada) y `aplicar(db)` ejecuta el mismo
plan después de respaldar la base. El plan se calcula contra lo que hay HOY
en la base: una fila que ya está como dice el PDF sale «sin cambio», así que
aplicar dos veces no hace nada la segunda.

Nunca se borra un movimiento que algo usa (préstamo, devolución, lote de
expense) ni uno con viaje, mi_parte o reembolso que su gemelo no tenga.
"""
import csv
import os
import re
import sqlite3
from datetime import date, datetime, timedelta

from .parsers import bbva_libreton
from .parsers._base import _MSI_INSTALLMENT_RE, clean_desc
from .config import cuenta_conocida, get_categoria_subcategoria
from .correcciones_sin_conciliar import _referenciado

_DIR = os.path.join(os.path.dirname(__file__), 'data')
DATA = os.path.join(_DIR, 'auditoria_pdf_2022_2026.csv')
RESUMEN = os.path.join(_DIR, 'auditoria_pdf_resumen.csv')
VERSION = 'auditoria_pdf_2022_2026_v1'

# El usuario ya había decidido estas filas (2026-10-03) leyendo la descripción
# mezclada con el renglón vecino; el PDF dice otra cosa (todas son abonos).
# No se tocan hasta que confirme.
PENDIENTES_USUARIO = {
    # (las de …3042 y Fresko ya las aclaró: ver _sugerida)
}

# Cuentas que le devuelven al usuario lo que él pagó (config.CUENTAS_CONOCIDAS): …3042 es su
# mamá, Mommita («devolución de gasto que yo hice de viajes o de boletos que les compré»).
# Sus abonos no son ingreso: «Reembolso compartido»; si la fila ya está en
# VIAJES se queda ahí, como entrada que resta del viaje.
def _sugerida(f, actual=None):
    _, datos = cuenta_conocida(f['descripcion_real'])
    if f['tipo_real'] == 'INGRESO' and datos and datos.get('reembolsa'):
        if actual and actual[0] == 'VIAJES':
            return actual
        return 'FINANZAS', 'Reembolso compartido'
    return f['categoria_sugerida'], f['subcategoria_sugerida']


# Lo que sobra en la app (no está en el PDF) y el usuario explicó (2026-10-03).
SOBRA_DECIDIDO = {
    1102: ('borrar', 'Sheraton: depósito en garantía, nunca se cobró'),
    2053: ('borrar', 'AMAZONVALIDACION: validación de la tarjeta, no es un cargo'),
    2031: ('conservar', 'Steam: un juego que compró'),
    1306: ('conservar', 'compra a 12 MSI de los anillos de los Corners (no cuenta como gasto; '
                        'el gasto lo llevan las mensualidades)'),
    19: ('conservar', 'el usuario pidió dejarlo así (2026-10-04)'),
    20: ('conservar', 'el usuario pidió dejarlo así (2026-10-04)'),
    68: ('conservar', 'el usuario pidió dejarlo así (2026-10-04)'),
}

# Compras que se cancelaron y se reembolsaron (banco, fecha, monto): el cargo
# se crea y, con su reembolso, quedan como movimiento interno (ni gasto ni
# ingreso). Palacio de Hierro, cafetera Nespresso: dos intentos el 10 y 12 de
# nov-2025, reembolsados el 13-nov (el usuario mandó el comprobante).
COMPRAS_CANCELADAS = {
    ('BBVA_TDC', '2025-11-10', 2345.0): 'Palacio de Hierro: intento de compra cancelado, reembolsado el 13-nov',
    ('BBVA_TDC', '2025-11-12', 2345.0): 'Palacio de Hierro: intento de compra cancelado, reembolsado el 13-nov',
}

# Envíos que regresaron (id del envío): el envío y su devolución quedan como
# «Entre cuentas propias» (ni gasto ni ingreso).
ENVIOS_DEVUELTOS = {
    3163: 'renta oct-2024 mandada a BANORTE; el casero la regresó y se pagó a BBVA (…5198)',
}

# Categoría de un faltante que el usuario explicó: (fecha, monto, operación) -> (cat, sub).
FALTA_CATEGORIA = {
    ('2024-10-08', 11000.0, 'PAGO TARJETA'): ('VIVIENDA', 'Renta'),   # la renta de oct-2024, pagada a BBVA
}

# Filas ligadas a préstamos / lotes de expense cuya dirección el usuario
# confirmó contra el PDF (2026-10-03): id -> (categoría, subcategoría, por qué).
# La categoría None = ligar como devolución a un préstamo abierto de esa persona
# (DEVOLUCION_DE); si no tiene, Reembolso compartido.
CONFIRMADOS_LIGADOS = {
    3351: ('PRESTAMOS', '', '«sí, yo aboné deuda»: le pagó $7,000 a su papá'),
    2999: (None, None, '«sí es devolución de Judi»'),
    # Le entró (no fue préstamo que dio): es la devolución de un préstamo ya
    # pagado (prestamos.PRESTAMOS_SOLO_DEVOLUCION), por eso queda en PRESTAMOS.
    3004: ('PRESTAMOS', '', '«así es»: «jefe de famil repo» le entró de …5937; «es un préstamo ya pagado»'),
    2124: ('FINANZAS', 'Retiro efectivo', '«fue retiro»'),
    2303: ('FINANZAS', 'Reembolsable', '«tuve que regresar un expense que no era mío»'),
}
DEVOLUCION_DE = {2999: 'Judi'}

# Duplicados ligados (préstamo/devolución): «hagamos lo que dice Cowork» -> el
# vínculo pasa al gemelo y la copia se borra.
RELIGAR_DUPLICADOS = {1831, 2077}

# Sobrantes que encontró el cuadre por estado de cuenta (no venían en los CSV):
# id que sobra -> (id de la copia buena, por qué). Feb-2026 cuadraba +$250 en
# abonos y +$2,100 en cargos contra el PDF: justo estas tres filas.
SOBRAN_POR_CUADRE = {
    1806: (1808, 'abono de $250 del 3-mar repetido («BNET MARTHA», id 1808)'),
    1807: (1805, 'el PDF solo trae el abono de $600 de Martha del 3-mar (id 1805), no un cargo'),
    1817: (1812, 'retiro de $1,500 del 4-mar repetido (el de la colecta, id 1812)'),
}

# Revisión de los periodos que no cuadraban contra el PDF (feb, abr y may 2026,
# 2026-10-04): id -> {campo: (texto que tiene hoy, valor del PDF)}. Solo se
# cambia si la fila todavía tiene el texto mezclado.
CORRECCIONES_CUADRE = {
    1812: {'descripcion': ('BNET P RETIRO', 'RETIRO SIN TARJETA')},
    1823: {'descripcion': ('A JUDITH A RETIRO', 'RETIRO SIN TARJETA')},
    2124: {'descripcion': ('FIBRA HOTELERA SC RETIRO', 'RETIRO SIN TARJETA')},
    # 2026-10-04 (prompt de contrapartes): el concepto completo del PDF, «2901260Arbitraje Gio».
    1815: {'descripcion': (('GIO SPEI ENVIADO BANAMEX', 'SPEI ENVIADO BANAMEX ARBITRAJE GIO'),
                           'SPEI ENVIADO BANAMEX 2901260ARBITRAJE GIO'),
           'categoria': ('CUIDADO_PERSONAL', 'DEPORTE'), 'subcategoria': ('Barbería', 'Fútbol')},
    1805: {'descripcion': ('BNET MARTHA PAGO CUENTA', 'PAGO CUENTA DE TERCERO BNET COLECTA MARTHA')},
    1956: {'descripcion': ('A GIOVANY A DEPOSITO', 'DEPOSITO EFECTIVO PRACTIC ******1804 ABR07 18:08 PRAC D797')},
    1959: {'descripcion': ('A GIOVANY A CFE', 'CFE SUM SERV BAS CR MU ******7830 RFC: CSS 160330CP7 17:40 AUT:')},
    2006: {'descripcion': ('GIOVANY SITH2PAGOGDLAC', 'SITH2PAGOGDLAC FIDEICOMISO F 1596')},
    2085: {'descripcion': ('PAGO CUENTA DE TERCERO', 'PAGO CUENTA DE TERCERO BNET TACOS')},
    # En el PDF es del 7-may: pasa al estado de mayo (abr +$300 / may -$300).
    2059: {'fecha': ('2026-05-06', '2026-05-07'), 'fecha_cargo': ('2026-05-06', '2026-05-07')},
    # «capital» a Judith y los $2,500 que regresaron el mismo día: ida y vuelta.
    1749: {'subcategoria': ('Retiro efectivo', 'Entre cuentas propias')},
    1750: {'subcategoria': ('Reembolso compartido', 'Entre cuentas propias')},
    # «metí dinero para invertir»: lo que llegó por STP el 18-may se fue a GBM ese día.
    2100: {'categoria': ('NOMINA', 'FINANZAS'), 'subcategoria': ('Bono', 'Entre cuentas propias')},
    # Retiros sin tarjeta: efectivo, no un gasto en ese comercio.
    1732: {'categoria': ('COMIDA_FUERA', 'FINANZAS'), 'subcategoria': ('Restaurante', 'Retiro efectivo')},
    1980: {'categoria': ('COMIDA_FUERA', 'FINANZAS'), 'subcategoria': ('Restaurante', 'Retiro efectivo')},
    2108: {'categoria': ('SUPER', 'FINANZAS'), 'subcategoria': ('Súper', 'Retiro efectivo')},
    # SPEI «corte gio» $150 del sábado 5-sep: el banco lo liquidó el lunes 7 y
    # va en el periodo de septiembre (ago +$150 / sep -$150). La fecha de
    # operación se queda; cambia la de liquidación.
    2540: {'fecha_cargo': ('2026-09-05', '2026-09-07')},
}

# Faltantes que encontró el cuadre (banco, fecha, monto, descripción, categoría, subcategoría):
# jul-2024 tenía $99 menos que el PDF; ese día hubo dos cargos de $99.
CREAR_POR_CUADRE = (
    ('BBVA_TDC', '2024-07-28', 99.0, 'BURGER KING AVILA C', 'COMIDA_FUERA', 'Fast Food'),
)

# Duplicados que tienen un préstamo encima y cuyo gemelo ya tiene el suyo: el
# préstamo se queda (sin movimiento) y la copia se borra. 2077: «BNET TACOS …
# REGRESO AL CORNER» de $2,000 (12-may-2026) repetido de 2130; «BNET TACOS»
# venía del renglón de $400 «tacos» (id 2085).
SOLTAR_PRESTAMO_Y_BORRAR = {2077}

_TABLAS_LIGA = ('est_prestamos', 'est_prestamo_devoluciones', 'est_expense_lote_gastos', 'est_expense_lote_depositos')

# Sugerencia de categoría que NO se aplica porque contradice lo que el
# usuario explicó de ese movimiento.
CATEGORIA_SE_QUEDA = {
    3111: '«me prestaron y regresé» (sep-2024): Entre cuentas propias, no ingreso extraordinario',
}

# Filas que la descripción mezclada metió en un tipo interno (inversión) que
# el movimiento real no tiene: el PDF dice retiro sin tarjeta / pago a un tercero.
TIPO_INTERNO_ERRONEO = {
    2375: '«INVERSION GIO» venía del renglón vecino; es un retiro sin tarjeta QR',
    2008: '«ABRIL GIO HSBC» venía del renglón vecino; es un pago a …3854, no a la tarjeta',
    1979: '«INVEX ABRIL» venía del renglón vecino; es un pago a …1239 (el seguro, ver GASTOS)',
}

# Categorías que el usuario no eligió (las pone el import o una regla genérica):
# ahí sí se aplica la categoría sugerida por la auditoría.
_GENERICAS = {('', ''), ('OTROS', ''), ('FINANZAS', ''), ('FINANZAS', 'Transferencia'),
              ('FINANZAS', 'Transferencia recibida'), ('FINANZAS', 'Transferencia enviada')}
_TIPOS_INTERNOS = ('MOVIMIENTO_INTERNO', 'INVERSION', 'PAGO')
_CORTE_TDC = 22


def filas() -> list[dict]:
    with open(DATA, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _monto(f) -> float:
    return round(float(f['monto']), 2)


def _monto_app_nota(f):
    """«monto distinto: app 555.00 vs PDF 5,555.00» -> (555.0, 5555.0)."""
    m = re.search(r'app ([\d,]+\.\d{2}) vs PDF ([\d,]+\.\d{2})', f['nota'])
    return (float(m.group(1).replace(',', '')), float(m.group(2).replace(',', ''))) if m else None


def desc_real(f) -> str:
    """La descripción del PDF en el formato que deja el importador (así una
    nueva subida del mismo PDF la reconoce como el mismo movimiento)."""
    d = re.sub(r'\s*\[[^\]]*\]', '', f['descripcion_real'])
    d = re.sub(r'\s*\|\s*\((?:del resumen|sección)[^)]*\)?.*$', '', d)
    if f['banco'] == 'BBVA_DEB':
        return bbva_libreton._clean(d.replace(' | ', ' ')) or 'SIN DESCRIPCION'
    return clean_desc(d.replace(' | ', ' '))[:80]


def _periodo_tdc(fecha: str) -> str:
    d = date.fromisoformat(fecha)
    fin = d.replace(day=_CORTE_TDC) if d.day <= _CORTE_TDC else (
        date(d.year + 1, 1, _CORTE_TDC) if d.month == 12 else date(d.year, d.month + 1, _CORTE_TDC))
    ini = (fin.replace(day=1) - timedelta(days=1)).replace(day=_CORTE_TDC + 1)
    return f"{ini.isoformat()} al {fin.isoformat()}"


def _buscar(db, f):
    """La fila de la base que corresponde a `f`: por id_app, validando banco,
    fecha y monto (por si el id no es de esta base); si no, por descripción."""
    montos = {_monto(f)}
    if (mn := _monto_app_nota(f)):
        montos |= set(mn)
    if f['id_app']:
        r = db.execute("SELECT * FROM est_movimientos WHERE id=?", (int(f['id_app']),)).fetchone()
        if r and r['banco'] == f['banco'] and (r['fecha'] or '')[:10] == f['fecha'] \
                and any(abs(abs(r['monto']) - m) < 0.01 for m in montos):
            return r
    for m in montos:
        r = db.execute("""SELECT * FROM est_movimientos WHERE banco=? AND substr(fecha,1,10)=?
                          AND ABS(ABS(monto) - ?) < 0.01 AND descripcion=? ORDER BY id LIMIT 1""",
                       (f['banco'], f['fecha'], m, f['descripcion_app'])).fetchone()
        if r:
            return r
    return None


def _intocable(db, r) -> str | None:
    if _referenciado(db, r['id']):
        return 'lo usa un préstamo, una devolución o un lote de expense'
    return None


def _linea(f, r, accion, campo='', antes='', despues='', motivo=''):
    return {'id_app': r['id'] if r else (int(f['id_app']) if f.get('id_app') else None),
            'banco': f['banco'], 'fecha': f['fecha'], 'monto': _monto(f),
            'estado_auditoria': f['estado'], 'accion': accion, 'campo': campo,
            'valor_antes': '' if antes is None else antes, 'valor_despues': '' if despues is None else despues,
            'motivo': motivo or f['nota']}


def _cambiar_categoria(cambios, actual, nueva):
    if nueva[0] != actual[0]:
        cambios['categoria'] = nueva[0]
    if (nueva[1] or '') != actual[1]:
        cambios['subcategoria'] = nueva[1] or ''


# ── CORREGIR ─────────────────────────────────────────────────────────────────

def _plan_corregir(db, f, ocupados) -> list[dict]:
    r = _buscar(db, f)
    if not r:
        return [_linea(f, None, 'pendiente revisión', motivo='no se encontró en la base (¿ya se borró o cambió?)')]
    ocupados.add(r['id'])
    if r['id'] in PENDIENTES_USUARIO:
        return [_linea(f, r, 'pendiente revisión', motivo='pregunta al usuario: ' + PENDIENTES_USUARIO[r['id']])]
    nota = f['nota']
    cambios: dict = {}
    tipo = r['tipo']
    if 'dirección' in nota:
        if f['banco'] == 'BBVA_TDC':
            # En la tarjeta el abono va con monto negativo (como lo deja el
            # importador: PAGO -x). Un INGRESO de la app ya es abono.
            if tipo in ('PAGO', 'MOVIMIENTO_INTERNO') and r['monto'] > 0:
                cambios['monto'] = -r['monto']
        elif f['tipo_real'] in ('INGRESO', 'GASTO') and r['id'] in CONFIRMADOS_LIGADOS:
            return _plan_ligado(db, f, r)
        elif f['tipo_real'] in ('INGRESO', 'GASTO') and tipo != f['tipo_real']:
            if (motivo := _intocable(db, r)):
                return [_linea(f, r, 'pendiente revisión', 'tipo', tipo, f['tipo_real'], motivo)]
            cambios['tipo'] = tipo = f['tipo_real']
    if r['id'] in TIPO_INTERNO_ERRONEO and tipo in _TIPOS_INTERNOS and f['tipo_real'] in ('INGRESO', 'GASTO'):
        cambios['tipo'] = tipo = f['tipo_real']
    if re.search(r'descripción (mezclada|perdida)|RFC', nota):
        nueva = desc_real(f)
        if nueva != r['descripcion']:
            otra = db.execute("SELECT id FROM est_movimientos WHERE fecha=? AND descripcion=? AND monto=? AND id != ?",
                              (r['fecha'], nueva, r['monto'], r['id'])).fetchone()
            if otra:
                return [_linea(f, r, 'pendiente revisión', 'descripcion', r['descripcion'], nueva,
                               f'ya existe otra fila igual (id {otra["id"]}): posible duplicado')]
            cambios['descripcion'] = nueva
    if (mn := _monto_app_nota(f)) and abs(abs(r['monto']) - mn[1]) >= 0.01:
        cambios['monto'] = mn[1] if r['monto'] >= 0 else -mn[1]
    actual = (r['categoria'] or '', r['subcategoria'] or '')
    cat, sub = _sugerida(f, actual)
    if cat == 'FINANZAS' and not sub and actual not in _GENERICAS \
            and actual[0] not in ('PAGO_TDC', 'PRESTAMOS', 'CETES', 'OTRO', 'INVERSION'):
        # Cowork solo dice «FINANZAS»; la categoría que tiene dice de qué es
        # (viaje, hospedaje del congreso, boleto, recarga): la entrada resta de ella.
        cat, sub = actual
    if cat and r['id'] not in CATEGORIA_SE_QUEDA and not (f['banco'] == 'BBVA_TDC' and tipo in _TIPOS_INTERNOS):
        if not sub and cat == 'FINANZAS' and tipo == 'INGRESO':
            sub = 'Transferencia recibida'     # sale en Sin conciliar para clasificarla
        if (cat, sub) != actual and ('tipo' in cambios or actual in _GENERICAS or 'RFC' in nota):
            _cambiar_categoria(cambios, actual, (cat, sub))
    elif 'tipo' in cambios and tipo in ('INGRESO', 'GASTO') and r['tipo'] in _TIPOS_INTERNOS:
        _cambiar_categoria(cambios, actual, bbva_libreton._categorize(cambios.get('descripcion', r['descripcion']),
                                                                      es_gasto=tipo == 'GASTO'))
    if r['id'] in ENVIOS_DEVUELTOS:
        _cambiar_categoria(cambios, actual, ('FINANZAS', 'Entre cuentas propias'))
        cat = ''
    out = []
    for campo, valor in cambios.items():
        motivo = (CATEGORIA_SE_QUEDA.get(r['id']) or TIPO_INTERNO_ERRONEO.get(r['id'])
                  or ENVIOS_DEVUELTOS.get(r['id']) or '')
        out.append(_linea(f, r, 'actualizado', campo, r[campo], valor, motivo))
    queda = (r['categoria'] or '', r['subcategoria'] or '')
    if cat and 'categoria' not in cambios and 'subcategoria' not in cambios and (cat, sub or '') != queda:
        por_que = (CATEGORIA_SE_QUEDA.get(r['id'])
                   or ('pago de tarjeta: se queda como movimiento interno' if f['banco'] == 'BBVA_TDC'
                       else 'se queda la que elegiste'))
        out.append(_linea(f, r, 'sin cambio', 'categoria', '/'.join(queda), '/'.join(queda),
                          f'sugerida {cat}/{sub} no aplicada: {por_que}'))
    return out or [_linea(f, r, 'sin cambio', motivo='ya está como en el PDF')]


def _sql_linea(f, r, accion, campo, antes, despues, motivo, sql):
    return _linea(f, r, accion, campo, antes, despues, motivo) | {'_sql': sql}


def _plan_ligado(db, f, r) -> list[dict]:
    """Voltea la dirección de una fila ligada que el usuario confirmó y deshace
    los vínculos que con la dirección real no tienen sentido."""
    cat, sub, por_que = CONFIRMADOS_LIGADOS[r['id']]
    nuevo = f['tipo_real']
    out = []
    if r['tipo'] != nuevo:
        out.append(_linea(f, r, 'actualizado', 'tipo', r['tipo'], nuevo, por_que))
    ignorar_prestamos = set()
    for p in db.execute("SELECT * FROM est_prestamos WHERE movimiento_id=?", (r['id'],)).fetchall():
        # Un préstamo que diste empieza con dinero que sale; uno que te dieron, con dinero que entra.
        if (p['direccion'] == 'OTORGADO') == (nuevo == 'GASTO'):
            continue
        ignorar_prestamos.add(p['id'])
        for d in db.execute("""SELECT d.movimiento_id, m.descripcion, m.categoria FROM est_prestamo_devoluciones d
                               JOIN est_movimientos m ON m.id = d.movimiento_id WHERE d.prestamo_id=?""",
                            (p['id'],)).fetchall():
            sql = [("DELETE FROM est_prestamo_devoluciones WHERE movimiento_id=?", (d['movimiento_id'],))]
            if d['categoria'] == 'PRESTAMOS':
                sql.append(("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Transferencia recibida' "
                            "WHERE id=?", (d['movimiento_id'],)))
            out.append(_sql_linea(f, r, 'desligado', 'devolución', d['movimiento_id'], '',
                                  f'devolución ({d["descripcion"]}) de un préstamo que no existió; queda en Sin conciliar', sql))
        out.append(_sql_linea(f, r, 'préstamo borrado', 'préstamo', f'{p["contraparte"]} ${abs(p["monto"]):,.2f}', '',
                              f'no fue préstamo: el PDF dice que el dinero {"entró" if nuevo == "INGRESO" else "salió"}',
                              [("DELETE FROM est_prestamos WHERE id=?", (p['id'],))]))
    if nuevo == 'GASTO':
        for d in db.execute("""SELECT d.prestamo_id, p.contraparte, p.direccion FROM est_prestamo_devoluciones d
                               JOIN est_prestamos p ON p.id = d.prestamo_id WHERE d.movimiento_id=?""", (r['id'],)).fetchall():
            if d['direccion'] == 'OTORGADO':
                out.append(_sql_linea(f, r, 'desligado', 'devolución', f'préstamo a {d["contraparte"]}', '',
                                      'un dinero que sale no es la devolución de un préstamo que diste',
                                      [("DELETE FROM est_prestamo_devoluciones WHERE movimiento_id=?", (r['id'],))]))
        tabla_mala = 'est_expense_lote_depositos'
    else:
        tabla_mala = 'est_expense_lote_gastos'
    if db.execute(f"SELECT 1 FROM {tabla_mala} WHERE movimiento_id=?", (r['id'],)).fetchone():
        out.append(_sql_linea(f, r, 'desligado', 'lote de expense', tabla_mala.rsplit('_', 1)[1], '',
                              'con la dirección real no es ' + ('depósito' if nuevo == 'GASTO' else 'gasto') + ' del lote',
                              [(f"DELETE FROM {tabla_mala} WHERE movimiento_id=?", (r['id'],))]))
    if cat is None:
        from . import prestamos
        persona = DEVOLUCION_DE[r['id']]
        ya = db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?", (r['id'],)).fetchone()
        abiertos = [p for p in prestamos.listar(db) if p['persona'].strip().lower() == persona.lower()
                    and p['id'] not in ignorar_prestamos and p['pendiente'] >= abs(r['monto']) - 0.01
                    and not p['perdido_fecha']]
        antes = [p for p in abiertos if (p['fecha'] or '')[:10] <= f['fecha']]
        # Solo un préstamo anterior al abono: lo que llega antes no puede pagar uno posterior.
        p = max(antes, key=lambda p: p['fecha']) if antes else None
        if ya:
            cat, sub = 'PRESTAMOS', ''
        elif p:
            cat, sub = 'PRESTAMOS', ''
            out.append(_sql_linea(f, r, 'ligado', 'devolución', '', f'préstamo a {persona} del {p["fecha"][:10]} '
                                  f'(${p["monto"]:,.2f}, pendiente ${p["pendiente"]:,.2f})', por_que,
                                  [("INSERT OR IGNORE INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) "
                                    "VALUES (?,?,datetime('now'))", (p['id'], r['id']))]))
        else:
            cat, sub = 'FINANZAS', 'Reembolso compartido'
    cambios = {}
    _cambiar_categoria(cambios, (r['categoria'] or '', r['subcategoria'] or ''), (cat, sub))
    out += [_linea(f, r, 'actualizado', c, r[c], v, por_que) for c, v in cambios.items()]
    return out or [_linea(f, r, 'sin cambio', motivo='ya está como en el PDF')]


# ── SOBRA_EN_APP ─────────────────────────────────────────────────────────────

def _gemelo(db, r, ids):
    for i in ids:
        g = db.execute("SELECT * FROM est_movimientos WHERE id=?", (i,)).fetchone()
        if g and g['banco'] == r['banco'] and abs(abs(g['monto']) - abs(r['monto'])) < 0.01 \
                and abs((date.fromisoformat(g['fecha'][:10]) - date.fromisoformat(r['fecha'][:10])).days) <= 3:
            return g
    return None


def _ids_duplicado(f) -> list[int]:
    return [int(x) for x in re.findall(r'\d+', (re.search(r'posible duplicado de id ([\d,\s]+)', f['nota']) or [''])[0])]


def _plan_soltar(db, f, r) -> list[dict]:
    otros = [t for t in _TABLAS_LIGA[1:] if db.execute(f"SELECT 1 FROM {t} WHERE movimiento_id=?", (r['id'],)).fetchone()]
    if otros:
        return [_linea(f, r, 'pendiente revisión', motivo='duplicado ligado a ' + ', '.join(otros))]
    out = [_sql_linea(f, r, 'desligado', 'préstamo', f'{p["contraparte"]} ${abs(p["monto"]):,.2f}', '',
                      'el préstamo se queda, sin la fila duplicada',
                      [("UPDATE est_prestamos SET movimiento_id=NULL WHERE id=?", (p['id'],))])
           for p in db.execute("SELECT * FROM est_prestamos WHERE movimiento_id=?", (r['id'],)).fetchall()]
    out.append(_linea(f, r, 'borrado', 'fila', f'{r["descripcion"]} [{r["tipo"]} {r["categoria"]}]', '',
                      'duplicado (no está en el PDF)'))
    return out


def _plan_religar(db, f, r) -> list[dict]:
    """Duplicado ligado: el vínculo pasa al gemelo (que no tenga ya uno) y la copia se borra."""
    gemelos = [g for g in (db.execute("SELECT * FROM est_movimientos WHERE id=?", (i,)).fetchone()
                           for i in _ids_duplicado(f)) if g]
    gemelos = [g for g in gemelos if g['banco'] == r['banco'] and abs(abs(g['monto']) - abs(r['monto'])) < 0.01
               and not _referenciado(db, g['id'])]
    if not gemelos:
        return [_linea(f, r, 'pendiente revisión', motivo='duplicado ligado, pero ningún gemelo libre para pasarle el vínculo')]
    g = gemelos[0]
    sql = [(f"UPDATE {t} SET movimiento_id=? WHERE movimiento_id=?", (g['id'], r['id'])) for t in _TABLAS_LIGA]
    if r['viaje_id'] is not None and g['viaje_id'] is None:
        sql.append(("UPDATE est_movimientos SET viaje_id=? WHERE id=?", (r['viaje_id'], g['id'])))
    out = [_sql_linea(f, r, 'religado', 'vínculo', r['id'], g['id'], f'el vínculo pasa a id {g["id"]} ({g["descripcion"]})', sql)]
    if (r['categoria'], r['tipo']) != (g['categoria'], g['tipo']) and r['categoria'] == 'PRESTAMOS':
        out.append(_linea(f, g, 'actualizado', 'categoria', g['categoria'], 'PRESTAMOS', 'hereda la categoría de su copia ligada'))
        if (g['subcategoria'] or '') != (r['subcategoria'] or ''):
            out.append(_linea(f, g, 'actualizado', 'subcategoria', g['subcategoria'], r['subcategoria'] or '',
                              'hereda la categoría de su copia ligada'))
    out.append(_linea(f, r, 'borrado', 'fila', f'{r["descripcion"]} [{r["tipo"]} {r["categoria"]}]', '',
                      f'duplicado de id {g["id"]} (no está en el PDF)'))
    return out


def _plan_sobra(db, f, ocupados) -> list[dict]:
    r = _buscar(db, f)
    if not r:
        return [_linea(f, None, 'sin cambio', motivo='ya no está en la base')]
    ocupados.add(r['id'])
    if r['id'] in SOLTAR_PRESTAMO_Y_BORRAR:
        return _plan_soltar(db, f, r)
    if r['id'] in RELIGAR_DUPLICADOS:
        return _plan_religar(db, f, r)
    if (motivo := _intocable(db, r)):
        return [_linea(f, r, 'pendiente revisión', motivo=motivo)]
    if abs(r['monto']) < 0.005:
        return [_linea(f, r, 'borrado', 'fila', r['descripcion'], '', 'monto 0.00')]
    if r['id'] in SOBRA_DECIDIDO:
        accion, por_que = SOBRA_DECIDIDO[r['id']]
        if accion == 'borrar':
            return [_linea(f, r, 'borrado', 'fila', f'{r["descripcion"]} [{r["tipo"]} {r["categoria"]}]', '', por_que)]
        return [_linea(f, r, 'sin cambio', motivo='se queda: ' + por_que)]
    ids = [int(x) for x in re.findall(r'\d+', (re.search(r'posible duplicado de id ([\d,\s]+)', f['nota']) or [''])[0])]
    g = _gemelo(db, r, ids) if ids else None
    if not g:
        return [_linea(f, r, 'pendiente revisión', motivo=f['nota'] + ('' if ids else '; no se borra: no está en el PDF y no es duplicado'))]
    extras = [c for c in ('viaje_id', 'mi_parte', 'reembolso_cat') if r[c] is not None and g[c] is None]
    if extras:
        return [_linea(f, r, 'pendiente revisión',
                       motivo=f'duplicado de id {g["id"]}, pero esta copia tiene {", ".join(extras)} y la otra no')]
    return [_linea(f, r, 'borrado', 'fila', f'{r["descripcion"]} [{r["tipo"]} {r["categoria"]}/{r["subcategoria"] or ""}]', '',
                   f'duplicado de id {g["id"]} ({g["descripcion"]})')]


# ── FALTA_EN_APP ─────────────────────────────────────────────────────────────

def _nueva_fila(f) -> dict:
    desc = desc_real(f)
    monto = _monto(f)
    cat, sub = _sugerida(f)
    if f['banco'] == 'BBVA_TDC':
        if f['tipo_real'] == 'INGRESO':          # abono a la tarjeta: como lo deja el importador
            return dict(descripcion=desc, monto=-monto, tipo='PAGO', categoria='PAGO', subcategoria='',
                        periodo=_periodo_tdc(f['fecha']))
        if not cat:
            cat, sub = get_categoria_subcategoria(desc)
        msi = _MSI_INSTALLMENT_RE.match(f['descripcion_real'])
        return dict(descripcion=desc, monto=monto, tipo='GASTO', categoria=cat, subcategoria=sub,
                    periodo=_periodo_tdc(f['fecha']),
                    parcialidad_num=int(msi.group(1)) if msi else None,
                    parcialidad_total=int(msi.group(2)) if msi else None)
    tipo = f['tipo_real']
    fijo = FALTA_CATEGORIA.get((f['fecha'], monto, ' '.join(_operacion(desc))))
    if fijo:
        return dict(descripcion=desc, monto=monto, tipo=tipo, categoria=fijo[0], subcategoria=fijo[1], periodo=None)
    if 'envío y devolución' in f['nota']:
        # Sale y regresa el mismo día: ni gasto ni ingreso.
        return dict(descripcion=desc, monto=monto, tipo='MOVIMIENTO_INTERNO', categoria='FINANZAS',
                    subcategoria='Entre cuentas propias', periodo=None)
    from .routes import _es_movimiento_interno       # misma regla que el import
    if tipo == 'GASTO' and _es_movimiento_interno(desc.upper()):
        return dict(descripcion=desc, monto=monto, tipo='MOVIMIENTO_INTERNO', categoria='PAGO_TDC',
                    subcategoria='', periodo=None)
    if not cat:
        cat, sub = bbva_libreton._categorize(desc, es_gasto=tipo == 'GASTO')
    elif not sub and cat == 'FINANZAS' and tipo == 'INGRESO':
        sub = 'Transferencia recibida'
    return dict(descripcion=desc, monto=monto, tipo=tipo, categoria=cat, subcategoria=sub, periodo=None)


def _operacion(desc: str) -> tuple:
    return tuple(re.findall(r'[A-Z]+', (desc or '').upper())[:2])


def _plan_falta(db, f, ocupados, usados) -> list[dict]:
    if f['banco'] == 'BBVA_TDC' and re.match(r'\d{2} DE \d{2} ANUALIDAD', f['descripcion_real']):
        return [_linea(f, None, 'pendiente revisión',
                       motivo='mensualidad de la anualidad: el banco no la suma en TOTAL IMPORTES y la '
                              'anualidad completa ya sale en Comisiones (contarla sería doble)')]
    nueva = _nueva_fila(f)
    igual = db.execute("SELECT id FROM est_movimientos WHERE fecha=? AND descripcion=? AND ABS(monto - ?) < 0.005",
                       (f['fecha'], nueva['descripcion'], nueva['monto'])).fetchone()
    if igual:
        return [_linea(f, None, 'sin cambio', motivo=f'ya existe una fila idéntica (id {igual["id"]})')]
    ingreso = nueva['tipo'] == 'INGRESO' or nueva['monto'] < 0
    for r in db.execute("""SELECT * FROM est_movimientos WHERE banco=? AND substr(fecha,1,10)=?
                           AND ABS(ABS(monto) - ?) < 0.01 ORDER BY id""", (f['banco'], f['fecha'], _monto(f))).fetchall():
        if r['id'] in ocupados or r['id'] in usados:
            continue
        mismo_lado = r['tipo'] in _TIPOS_INTERNOS or ((r['tipo'] == 'INGRESO' or r['monto'] < 0) == ingreso)
        # Misma operación del banco («PAGO TARJETA» no es «PAGO CUENTA»): el
        # 5-may-2024 había un PAGO CUENTA DE TERCERO y faltaba el PAGO TARJETA
        # DE CREDITO del mismo monto.
        if mismo_lado and _operacion(r['descripcion']) == _operacion(nueva['descripcion']):
            usados.add(r['id'])
            return [_linea(f, r, 'sin cambio', motivo=f'ya existe (id {r["id"]}: {r["descripcion"]})')]
    return [_linea(f, None, 'creado', 'fila', '', f"{nueva['descripcion']} [{nueva['tipo']} "
                                                  f"{nueva['categoria']}/{nueva['subcategoria']}] {nueva['monto']:.2f}")
            | {'_nueva': nueva}]


# ── Plan / aplicar ───────────────────────────────────────────────────────────

def plan(db) -> list[dict]:
    _REEMBOLSOS_TOMADOS.clear()
    todas = filas()
    ocupados: set = set()
    out = []
    for f in todas:                        # primero las que apuntan a una fila existente
        if f['estado'] == 'CORREGIR':
            out += _plan_corregir(db, f, ocupados)
        elif f['estado'] == 'SOBRA_EN_APP':
            out += _plan_sobra(db, f, ocupados)
        elif f['estado'] == 'DUDA' and (f['banco'], f['fecha'], _monto(f)) in COMPRAS_CANCELADAS:
            out += _plan_compra_cancelada(db, f)
        elif f['estado'] == 'DUDA':
            r = _buscar(db, f) if f['id_app'] else None
            if r:
                ocupados.add(r['id'])
            out.append(_linea(f, r, 'pendiente revisión', motivo='DUDA: ' + f['nota']))
    usados: set = set()
    for f in todas:
        if f['estado'] == 'FALTA_EN_APP':
            out += _plan_falta(db, f, ocupados, usados)
    out += _plan_devoluciones(db)
    out += _plan_sobran_por_cuadre(db)
    out += _plan_crear_por_cuadre(db)
    out += _plan_correcciones_cuadre(db, {l['id_app'] for l in out if l['accion'] == 'borrado'})
    out.sort(key=lambda x: (x['banco'], x['fecha'], x['id_app'] or 0))
    return out


def _plan_devoluciones(db) -> list[dict]:
    """La devolución de cada envío de ENVIOS_DEVUELTOS: abono del mismo monto en
    los 20 días siguientes -> Entre cuentas propias."""
    out = []
    for mid, por_que in ENVIOS_DEVUELTOS.items():
        e = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone()
        if not e:
            continue
        f = {'banco': e['banco'], 'fecha': e['fecha'][:10], 'monto': abs(e['monto']), 'estado': 'AJUSTE',
             'nota': por_que, 'id_app': ''}
        d = db.execute("""SELECT * FROM est_movimientos WHERE banco=? AND tipo='INGRESO' AND ABS(ABS(monto) - ?) < 0.01
                           AND substr(fecha,1,10) BETWEEN ? AND date(?, '+20 days') ORDER BY fecha, id LIMIT 1""",
                        (e['banco'], abs(e['monto']), e['fecha'][:10], e['fecha'][:10])).fetchone()
        if not d:
            out.append(_linea(f, None, 'pendiente revisión', motivo='no encontré la devolución: ' + por_que))
            continue
        f['fecha'] = d['fecha'][:10]
        cambios = {}
        _cambiar_categoria(cambios, (d['categoria'] or '', d['subcategoria'] or ''), ('FINANZAS', 'Entre cuentas propias'))
        out += [_linea(f, d, 'actualizado', c, d[c], v, 'devolución: ' + por_que) for c, v in cambios.items()] \
            or [_linea(f, d, 'sin cambio', motivo='devolución ya está como Entre cuentas propias')]
    return out


def _plan_sobran_por_cuadre(db) -> list[dict]:
    out = []
    for mid, (gid, por_que) in SOBRAN_POR_CUADRE.items():
        r = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone()
        if not r:
            continue
        f = {'banco': r['banco'], 'fecha': r['fecha'][:10], 'monto': abs(r['monto']), 'estado': 'CUADRE',
             'nota': por_que, 'id_app': str(mid)}
        g = db.execute("SELECT * FROM est_movimientos WHERE id=?", (gid,)).fetchone()
        if not g:
            out.append(_linea(f, r, 'pendiente revisión', motivo=f'no está la copia buena (id {gid})'))
            continue
        sql = []
        if _referenciado(db, mid):
            if _referenciado(db, gid) or (r['tipo'] == 'INGRESO') != (g['tipo'] == 'INGRESO'):
                out.append(_linea(f, r, 'pendiente revisión', motivo=por_que + '; está ligada a un préstamo o expense'))
                continue
            sql = [(f"UPDATE {t} SET movimiento_id=? WHERE movimiento_id=?", (gid, mid)) for t in _TABLAS_LIGA]
            out.append(_sql_linea(f, r, 'religado', 'vínculo', mid, gid, f'el vínculo pasa a id {gid}', sql))
        out.append(_linea(f, r, 'borrado', 'fila', f'{r["descripcion"]} [{r["tipo"]} {r["categoria"]}/'
                                                    f'{r["subcategoria"] or ""}]', '', por_que))
    return out


def _plan_crear_por_cuadre(db) -> list[dict]:
    out = []
    for banco, fecha, monto, desc, cat, sub in CREAR_POR_CUADRE:
        f = {'banco': banco, 'fecha': fecha, 'monto': monto, 'estado': 'CUADRE', 'nota': 'faltaba según el PDF',
             'id_app': ''}
        if db.execute("SELECT 1 FROM est_movimientos WHERE banco=? AND substr(fecha,1,10)=? AND descripcion=?",
                      (banco, fecha, desc)).fetchone():
            out.append(_linea(f, None, 'sin cambio', motivo='ya existe'))
            continue
        nueva = dict(descripcion=desc, monto=monto, tipo='GASTO', categoria=cat, subcategoria=sub,
                     periodo=_periodo_tdc(fecha) if banco == 'BBVA_TDC' else None)
        out.append(_linea(f, None, 'creado', 'fila', '', f'{desc} [GASTO {cat}/{sub}] {monto:.2f}', 'faltaba según el PDF')
                   | {'_nueva': nueva})
    return out


def _plan_correcciones_cuadre(db, borrados) -> list[dict]:
    out = []
    for mid, campos in CORRECCIONES_CUADRE.items():
        r = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone()
        if not r:
            continue
        f = {'banco': r['banco'], 'fecha': r['fecha'][:10], 'monto': abs(r['monto']), 'estado': 'CUADRE',
             'nota': 'revisión contra el PDF', 'id_app': str(mid)}
        cambios = {}
        for campo, (hoy, nuevo) in campos.items():
            actual = (r[campo] or '')
            if campo == 'fecha':
                actual = actual[:10]
            elif campo == 'fecha_cargo':          # sin fecha de liquidación = la de operación
                actual = (actual or r['fecha'])[:10]
            if actual == nuevo:
                continue
            hoys = hoy if isinstance(hoy, tuple) else (hoy,)   # varios textos de antes posibles
            if not any(actual == h or actual.startswith(h) for h in hoys):
                out.append(_linea(f, r, 'pendiente revisión', campo, actual, nuevo,
                                  f'ya no tiene «{hoys[0]}»: alguien la cambió, no se toca'))
                continue
            cambios[campo] = nuevo
        if 'descripcion' in cambios or 'fecha' in cambios:
            fecha = cambios.get('fecha', r['fecha'])
            otra = db.execute("""SELECT id FROM est_movimientos WHERE fecha=? AND descripcion=? AND monto=? AND id != ?""",
                              (fecha, cambios.get('descripcion', r['descripcion']), r['monto'], mid)).fetchone()
            if otra and otra['id'] not in borrados:
                out.append(_linea(f, r, 'pendiente revisión', motivo=f'chocaría con la fila {otra["id"]}'))
                continue
        out += [_linea(f, r, 'actualizado', c, r[c], v, 'revisión contra el PDF') for c, v in cambios.items()]
    return out


_NEUTRO = ('MOVIMIENTO_INTERNO', 'FINANZAS', 'Entre cuentas propias')


def _plan_compra_cancelada(db, f) -> list[dict]:
    por_que = COMPRAS_CANCELADAS[(f['banco'], f['fecha'], _monto(f))]
    desc = desc_real(f)
    out = []
    ya = db.execute("""SELECT id FROM est_movimientos WHERE banco=? AND substr(fecha,1,10)=? AND ABS(monto - ?) < 0.005
                         AND tipo='MOVIMIENTO_INTERNO'""", (f['banco'], f['fecha'], _monto(f))).fetchone()
    if ya:
        out.append(_linea(f, None, 'sin cambio', motivo='ya está el cargo de la compra cancelada'))
    else:
        nueva = dict(descripcion=desc, monto=_monto(f), tipo=_NEUTRO[0], categoria=_NEUTRO[1],
                     subcategoria=_NEUTRO[2], periodo=_periodo_tdc(f['fecha']))
        out.append(_linea(f, None, 'creado', 'fila', '', f'{desc} [{_NEUTRO[0]} {_NEUTRO[1]}/{_NEUTRO[2]}] '
                                                          f'{_monto(f):.2f}', por_que) | {'_nueva': nueva})
    # Su reembolso: un abono del mismo monto en los 20 días siguientes que no sea ya neutro.
    usados = {l['id_app'] for l in out}
    for r in db.execute("""SELECT * FROM est_movimientos WHERE banco=? AND ABS(ABS(monto) - ?) < 0.005
                            AND substr(fecha,1,10) BETWEEN ? AND date(?, '+20 days')
                            AND (monto < 0 OR tipo='INGRESO') ORDER BY fecha, id""",
                         (f['banco'], _monto(f), f['fecha'], f['fecha'])).fetchall():
        if (r['tipo'], r['categoria'], r['subcategoria'] or '') == _NEUTRO:
            continue
        if any(r['id'] == x for x in usados) or r['id'] in _REEMBOLSOS_TOMADOS:
            continue
        _REEMBOLSOS_TOMADOS.add(r['id'])
        g = {'banco': f['banco'], 'fecha': r['fecha'][:10], 'monto': abs(r['monto']), 'estado': 'AJUSTE',
             'nota': por_que, 'id_app': str(r['id'])}
        for campo, valor in zip(('tipo', 'categoria', 'subcategoria'), _NEUTRO):
            if (r[campo] or '') != valor:
                out.append(_linea(g, r, 'actualizado', campo, r[campo], valor, 'reembolso de la compra cancelada'))
        break
    return out


_REEMBOLSOS_TOMADOS: set = set()


def resumen(lineas: list[dict]) -> dict:
    por = {}
    for l in lineas:
        k = f"{l['banco']} · {l['accion']}" + (f" · {l['campo']}" if l['campo'] and l['accion'] == 'actualizado' else '')
        por[k] = por.get(k, 0) + 1
    return dict(sorted(por.items()))


def respaldar(db_path: str, motivo: str = 'auditoria_pdf') -> str:
    """Copia consistente de la base (API de respaldo de SQLite) junto a ella."""
    destino_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'respaldos')
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, f"pipeline_{datetime.now():%Y%m%d_%H%M%S}_antes_{motivo}.db")
    src, dst = sqlite3.connect(db_path), sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return destino


def aplicar(db, lineas: list[dict] | None = None) -> list[dict]:
    """Ejecuta el plan (el que se mostró, o uno recalculado). El caller hace
    el respaldo antes y el commit después."""
    lineas = plan(db) if lineas is None else lineas
    orden = {'religado': 0, 'desligado': 0, 'préstamo borrado': 0, 'borrado': 1}
    for l in sorted(lineas, key=lambda l: orden.get(l['accion'], 2)):
        for sql, args in l.get('_sql', ()):
            db.execute(sql, args)
        if '_sql' in l:
            continue
        if l['accion'] == 'actualizado':
            db.execute(f"UPDATE est_movimientos SET {l['campo']}=? WHERE id=?", (l['valor_despues'], l['id_app']))
        elif l['accion'] == 'borrado':
            db.execute("DELETE FROM est_movimientos WHERE id=?", (l['id_app'],))
        elif l['accion'] == 'creado':
            n = l['_nueva']
            cur = db.execute("""INSERT OR IGNORE INTO est_movimientos
                (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo,
                 parcialidad_num, parcialidad_total)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (l['fecha'], l['fecha'], n['descripcion'], n['monto'], l['banco'], n.get('periodo'),
                 n['categoria'], n['subcategoria'], n['tipo'], n.get('parcialidad_num'), n.get('parcialidad_total')))
            if cur.rowcount:
                l['id_app'] = cur.lastrowid
            else:
                l['accion'], l['motivo'] = 'sin cambio', 'ya existía una fila idéntica (fecha, descripción, monto)'
    db.execute("INSERT OR IGNORE INTO migration_log (version, applied_at) VALUES (?, ?)",
               (VERSION, datetime.now().isoformat(timespec='seconds')))
    return lineas


# ── Cuadre por estado de cuenta (después de aplicar) ─────────────────────────

def _es_abono(r) -> bool:
    if r['banco'] == 'BBVA_TDC':
        return r['monto'] < 0 or r['tipo'] == 'INGRESO'
    d = (r['descripcion'] or '').upper()
    return (r['tipo'] == 'INGRESO' or (r['tipo'] == 'INVERSION' and (r['subcategoria'] or '') == 'RETIRO')
            or (r['tipo'] == 'MOVIMIENTO_INTERNO' and ('DEVUELTO' in d or 'RECIBIDO' in d)))


def _fecha_periodo(banco: str) -> str:
    """Columna (SQL) que decide en qué estado de cuenta cae una fila. En débito
    manda la fecha de liquidación (LIQ): una operación del sábado 5-sep que el
    banco liquida el lunes 7 va en el estado que empieza el 7. Sin fecha de
    liquidación, la de operación. La TDC sigue por fecha de operación (así
    cuadran todos sus estados)."""
    if banco == 'BBVA_DEB':
        return "substr(COALESCE(NULLIF(fecha_cargo, ''), fecha), 1, 10)"
    return 'substr(fecha, 1, 10)'


def movimientos_periodo(db, banco: str, desde: str, hasta: str) -> list[dict]:
    """Lo que tiene la app en un periodo, del lado (abono/cargo) que cuenta el
    cuadre: para comparar renglón por renglón contra el PDF."""
    col = _fecha_periodo(banco)
    rows = db.execute(f"""SELECT id, fecha, {col} AS fecha_liq, descripcion, monto, tipo, categoria,
                                 subcategoria, banco
                          FROM est_movimientos WHERE banco=? AND {col} BETWEEN ? AND ?
                          ORDER BY fecha_liq, fecha, id""", (banco, desde, hasta)).fetchall()
    return [{'id': r['id'], 'fecha': r['fecha'][:10], 'fecha_liq': r['fecha_liq'],
             'lado': 'abono' if _es_abono(r) else 'cargo',
             'monto': round(abs(r['monto']), 2), 'descripcion': r['descripcion'], 'tipo': r['tipo'],
             'categoria': f"{r['categoria']}/{r['subcategoria'] or ''}"} for r in rows]


def cuadre(db) -> list[dict]:
    """Por cada estado de cuenta de resumen_por_estado.csv: abonos y cargos que
    tiene hoy la app en ese periodo contra los totales del PDF. Es aproximado
    para débito (los tipos internos no dicen de qué lado van)."""
    with open(RESUMEN, encoding='utf-8-sig') as fh:
        estados = list(csv.DictReader(fh))
    out = []
    for e in estados:
        m = re.match(r'(\d{4}-\d{2}-\d{2}) al (\d{4}-\d{2}-\d{2})', e['periodo'])
        if not m:
            continue
        col = _fecha_periodo(e['banco'])
        rows = db.execute(f"""SELECT banco, monto, tipo, subcategoria, descripcion FROM est_movimientos
                              WHERE banco=? AND {col} BETWEEN ? AND ?""",
                          (e['banco'], m.group(1), m.group(2))).fetchall()
        ab = round(sum(abs(r['monto']) for r in rows if _es_abono(r)), 2)
        ca = round(sum(abs(r['monto']) for r in rows if not _es_abono(r)), 2)
        pab, pca = float(e['total_abonos_pdf']), float(e['total_cargos_pdf'])
        out.append({'banco': e['banco'], 'periodo': e['periodo'], 'abonos_pdf': pab, 'abonos_app': ab,
                    'cargos_pdf': pca, 'cargos_app': ca, 'dif_abonos': round(ab - pab, 2),
                    'dif_cargos': round(ca - pca, 2),
                    'cuadra': abs(ab - pab) < 0.01 and abs(ca - pca) < 0.01})
    return out
