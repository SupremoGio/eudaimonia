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
from .config import get_categoria_subcategoria
from .correcciones_sin_conciliar import _referenciado

_DIR = os.path.join(os.path.dirname(__file__), 'data')
DATA = os.path.join(_DIR, 'auditoria_pdf_2022_2026.csv')
RESUMEN = os.path.join(_DIR, 'auditoria_pdf_resumen.csv')
VERSION = 'auditoria_pdf_2022_2026_v1'

# El usuario ya había decidido estas filas (2026-10-03) leyendo la descripción
# mezclada con el renglón vecino; el PDF dice otra cosa (todas son abonos).
# No se tocan hasta que confirme.
PENDIENTES_USUARIO = {
    1816: 'el PDF dice abono de …3042 «p»; tenía «ARBITRAJE GIO» pegado del renglón vecino',
    1888: 'el PDF dice abono de …3042 «Transf a GIOVANY»; se había pasado a SUPER como gasto',
    1975: 'el PDF dice abono de …3042 «Transf a GIOVANY»; «MENS GIO» venía del renglón vecino',
    2242: 'el PDF dice abono de …3042 «p»; se había pasado a SALUD/Consultas como gasto',
}

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
    cat, sub = f['categoria_sugerida'], f['subcategoria_sugerida']
    actual = (r['categoria'] or '', r['subcategoria'] or '')
    if cat and r['id'] not in CATEGORIA_SE_QUEDA and not (f['banco'] == 'BBVA_TDC' and tipo in _TIPOS_INTERNOS):
        if not sub and cat == 'FINANZAS' and tipo == 'INGRESO':
            sub = 'Transferencia recibida'     # sale en Sin conciliar para clasificarla
        if (cat, sub) != actual and ('tipo' in cambios or actual in _GENERICAS or 'RFC' in nota):
            _cambiar_categoria(cambios, actual, (cat, sub))
    elif 'tipo' in cambios and tipo in ('INGRESO', 'GASTO') and r['tipo'] in _TIPOS_INTERNOS:
        _cambiar_categoria(cambios, actual, bbva_libreton._categorize(cambios.get('descripcion', r['descripcion']),
                                                                      es_gasto=tipo == 'GASTO'))
    out = []
    for campo, valor in cambios.items():
        motivo = CATEGORIA_SE_QUEDA.get(r['id']) or TIPO_INTERNO_ERRONEO.get(r['id']) or ''
        out.append(_linea(f, r, 'actualizado', campo, r[campo], valor, motivo))
    queda = (r['categoria'] or '', r['subcategoria'] or '')
    if cat and 'categoria' not in cambios and 'subcategoria' not in cambios and (cat, sub or '') != queda:
        por_que = (CATEGORIA_SE_QUEDA.get(r['id'])
                   or ('pago de tarjeta: se queda como movimiento interno' if f['banco'] == 'BBVA_TDC'
                       else 'se queda la que elegiste'))
        out.append(_linea(f, r, 'sin cambio', 'categoria', '/'.join(queda), '/'.join(queda),
                          f'sugerida {cat}/{sub} no aplicada: {por_que}'))
    return out or [_linea(f, r, 'sin cambio', motivo='ya está como en el PDF')]


# ── SOBRA_EN_APP ─────────────────────────────────────────────────────────────

def _gemelo(db, r, ids):
    for i in ids:
        g = db.execute("SELECT * FROM est_movimientos WHERE id=?", (i,)).fetchone()
        if g and g['banco'] == r['banco'] and abs(abs(g['monto']) - abs(r['monto'])) < 0.01 \
                and abs((date.fromisoformat(g['fecha'][:10]) - date.fromisoformat(r['fecha'][:10])).days) <= 3:
            return g
    return None


def _plan_sobra(db, f, ocupados) -> list[dict]:
    r = _buscar(db, f)
    if not r:
        return [_linea(f, None, 'sin cambio', motivo='ya no está en la base')]
    ocupados.add(r['id'])
    if (motivo := _intocable(db, r)):
        return [_linea(f, r, 'pendiente revisión', motivo=motivo)]
    if abs(r['monto']) < 0.005:
        return [_linea(f, r, 'borrado', 'fila', r['descripcion'], '', 'monto 0.00')]
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
    cat, sub = f['categoria_sugerida'], f['subcategoria_sugerida']
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
        if mismo_lado:
            usados.add(r['id'])
            return [_linea(f, r, 'sin cambio', motivo=f'ya existe (id {r["id"]}: {r["descripcion"]})')]
    return [_linea(f, None, 'creado', 'fila', '', f"{nueva['descripcion']} [{nueva['tipo']} "
                                                  f"{nueva['categoria']}/{nueva['subcategoria']}] {nueva['monto']:.2f}")
            | {'_nueva': nueva}]


# ── Plan / aplicar ───────────────────────────────────────────────────────────

def plan(db) -> list[dict]:
    todas = filas()
    ocupados: set = set()
    out = []
    for f in todas:                        # primero las que apuntan a una fila existente
        if f['estado'] == 'CORREGIR':
            out += _plan_corregir(db, f, ocupados)
        elif f['estado'] == 'SOBRA_EN_APP':
            out += _plan_sobra(db, f, ocupados)
        elif f['estado'] == 'DUDA':
            r = _buscar(db, f) if f['id_app'] else None
            if r:
                ocupados.add(r['id'])
            out.append(_linea(f, r, 'pendiente revisión', motivo='DUDA: ' + f['nota']))
    usados: set = set()
    for f in todas:
        if f['estado'] == 'FALTA_EN_APP':
            out += _plan_falta(db, f, ocupados, usados)
    out.sort(key=lambda x: (x['banco'], x['fecha'], x['id_app'] or 0))
    return out


def resumen(lineas: list[dict]) -> dict:
    por = {}
    for l in lineas:
        k = f"{l['banco']} · {l['accion']}" + (f" · {l['campo']}" if l['campo'] and l['accion'] == 'actualizado' else '')
        por[k] = por.get(k, 0) + 1
    return dict(sorted(por.items()))


def respaldar(db_path: str) -> str:
    """Copia consistente de la base (API de respaldo de SQLite) junto a ella."""
    destino_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'respaldos')
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, f"pipeline_{datetime.now():%Y%m%d_%H%M%S}_antes_auditoria_pdf.db")
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
    for l in lineas:
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
    return r['tipo'] == 'INGRESO' or (r['tipo'] == 'INVERSION' and (r['subcategoria'] or '') == 'RETIRO')


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
        rows = db.execute("""SELECT banco, monto, tipo, subcategoria FROM est_movimientos
                             WHERE banco=? AND substr(fecha,1,10) BETWEEN ? AND ?""",
                          (e['banco'], m.group(1), m.group(2))).fetchall()
        ab = round(sum(abs(r['monto']) for r in rows if _es_abono(r)), 2)
        ca = round(sum(abs(r['monto']) for r in rows if not _es_abono(r)), 2)
        pab, pca = float(e['total_abonos_pdf']), float(e['total_cargos_pdf'])
        out.append({'banco': e['banco'], 'periodo': e['periodo'], 'abonos_pdf': pab, 'abonos_app': ab,
                    'cargos_pdf': pca, 'cargos_app': ca, 'dif_abonos': round(ab - pab, 2),
                    'dif_cargos': round(ca - pca, 2),
                    'cuadra': abs(ab - pab) < 0.01 and abs(ca - pca) < 0.01})
    return out
