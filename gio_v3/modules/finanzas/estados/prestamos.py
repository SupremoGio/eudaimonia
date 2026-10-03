"""
Préstamos por cobrar — lógica compartida entre la API de Estados de cuenta
(routes.py) y la Radiografía del mes (budget.py).

Modelo:
  - est_prestamos: un préstamo otorgado (persona = contraparte, fecha, monto),
    normalmente creado desde el movimiento bancario con el que se prestó
    (movimiento_id, categoría PRESTAMOS / tipo GASTO).
  - est_prestamo_devoluciones: movimientos de ingreso ligados a un préstamo.
    Una devolución ligada queda con categoría PRESTAMOS, así que no cuenta
    como ingreso en ningún lado: solo baja el pendiente.
  - perdido_fecha: «Perdido» es manual; el pendiente cuenta como gasto en
    Familia y regalos del mes en que se PRESTÓ (fecha del préstamo), no del
    mes en que se marcó -- marcar de golpe préstamos viejos inflaba el mes en
    curso (pedido del usuario). Solo en la Radiografía (registro interno, no
    un movimiento bancario).

El estado se calcula (Pendiente / Pagado parcial / Pagado) para que nunca se
desincronice de las devoluciones; solo «Perdido» se marca a mano.
"""
from datetime import datetime
import re

PENDIENTE, PARCIAL, PAGADO, PERDIDO = 'Pendiente', 'Pagado parcial', 'Pagado', 'Perdido'

# Categorías de ingreso que se ofrecen como posible devolución: las que ya son
# PRESTAMOS primero y luego transferencias recibidas / sin clasificar, que es
# como suele llegar alguien que te paga.
_CATS_DEVOLUCION = ('PRESTAMOS', 'FINANZAS', 'OTROS')


def estado(monto: float, devuelto: float, perdido_fecha) -> str:
    if perdido_fecha:
        return PERDIDO
    if devuelto >= monto - 0.005:
        return PAGADO
    return PARCIAL if devuelto > 0 else PENDIENTE


def _devoluciones(db) -> dict:
    """prestamo_id -> [devolución] con monto positivo."""
    out = {}
    for r in db.execute("""
        SELECT d.prestamo_id, m.id AS movimiento_id, m.fecha, m.descripcion, ABS(m.monto) AS monto
        FROM est_prestamo_devoluciones d
        JOIN est_movimientos m ON m.id = d.movimiento_id
        ORDER BY m.fecha
    """).fetchall():
        out.setdefault(r['prestamo_id'], []).append({
            'movimiento_id': r['movimiento_id'], 'fecha': r['fecha'],
            'descripcion': r['descripcion'], 'monto': round(float(r['monto']), 2),
        })
    return out


def listar(db) -> list[dict]:
    devs = _devoluciones(db)
    rows = db.execute("""
        SELECT p.*, m.descripcion AS mov_descripcion
        FROM est_prestamos p
        LEFT JOIN est_movimientos m ON m.id = p.movimiento_id
        WHERE p.direccion = 'OTORGADO'
        ORDER BY p.fecha DESC, p.id DESC
    """).fetchall()
    out = []
    for r in rows:
        monto = round(abs(float(r['monto'])), 2)
        d = devs.get(r['id'], [])
        devuelto = round(sum(x['monto'] for x in d), 2)
        pendiente = round(max(monto - devuelto, 0), 2)
        out.append({
            'id': r['id'], 'persona': r['contraparte'], 'fecha': r['fecha'],
            'monto': monto, 'devuelto': devuelto, 'pendiente': pendiente,
            'estado': estado(monto, devuelto, r['perdido_fecha']),
            'perdido_fecha': r['perdido_fecha'], 'notas': r['notas'] or '',
            'movimiento_id': r['movimiento_id'], 'descripcion': r['mov_descripcion'] or '',
            'devoluciones': d,
        })
    return out


def resumen(db) -> dict:
    """Total por cobrar y detalle por persona. Los perdidos no suman al
    pendiente (ya no se espera cobrarlos) pero se siguen listando."""
    prestamos = listar(db)
    personas = {}
    for p in prestamos:
        g = personas.setdefault(p['persona'], {'persona': p['persona'], 'prestado': 0.0,
                                               'devuelto': 0.0, 'pendiente': 0.0, 'prestamos': []})
        g['prestado'] += p['monto']
        g['devuelto'] += p['devuelto']
        if p['estado'] != PERDIDO:
            g['pendiente'] += p['pendiente']
        g['prestamos'].append(p)
    grupos = sorted(personas.values(), key=lambda g: (-g['pendiente'], g['persona'].lower()))
    for g in grupos:
        for k in ('prestado', 'devuelto', 'pendiente'):
            g[k] = round(g[k], 2)
    return {
        'total_pendiente': round(sum(g['pendiente'] for g in grupos), 2),
        'total_perdido': round(sum(p['pendiente'] for p in prestamos if p['estado'] == PERDIDO), 2),
        'personas': grupos,
    }


def perdidos_detalle_en_rango(db, desde: str, hasta: str) -> list[dict]:
    """Préstamos perdidos que se PRESTARON en [desde, hasta), con lo que quedó
    pendiente: el detalle de lo que suma perdidos_en_rango."""
    return [p for p in listar(db)
            if p['perdido_fecha'] and p['fecha'] and desde <= p['fecha'][:10] < hasta and p['pendiente'] > 0]


def perdidos_en_rango(db, desde: str, hasta: str) -> float:
    """Pendiente de los préstamos perdidos que se prestaron en [desde, hasta):
    es el gasto que la Radiografía suma a Familia y regalos ese mes."""
    return round(sum(p['pendiente'] for p in perdidos_detalle_en_rango(db, desde, hasta)), 2)


def candidatos(db) -> dict:
    """Movimientos para crear préstamos (gastos PRESTAMOS sin préstamo) y para
    ligar como devolución (ingresos no ligados), más las personas ya usadas."""
    nuevos = db.execute("""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, banco FROM est_movimientos
        WHERE categoria = 'PRESTAMOS' AND tipo = 'GASTO'
          AND id NOT IN (SELECT movimiento_id FROM est_prestamos WHERE movimiento_id IS NOT NULL)
        ORDER BY fecha DESC
    """).fetchall()
    nuevos = [r for r in nuevos if not _mensualidad_de(r)]
    ph = ','.join('?' * len(_CATS_DEVOLUCION))
    devs = db.execute(f"""
        SELECT id, fecha, descripcion, ABS(monto) AS monto, banco, categoria FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ({ph})
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY CASE WHEN categoria = 'PRESTAMOS' THEN 0 ELSE 1 END, fecha DESC
        LIMIT 200
    """, _CATS_DEVOLUCION).fetchall()
    personas = [r['contraparte'] for r in db.execute(
        "SELECT DISTINCT contraparte FROM est_prestamos ORDER BY contraparte COLLATE NOCASE")]
    return {'prestamos': [dict(r) for r in nuevos], 'devoluciones': [dict(r) for r in devs],
            'personas': personas}


def _tabla_descartados(db) -> None:
    # Grupos de «posibles duplicados» que el usuario revisó y no lo son. La
    # llave son los ids del grupo: si aparece otro movimiento ese día y monto,
    # el grupo cambia y vuelve a avisar.
    db.execute("""CREATE TABLE IF NOT EXISTS est_duplicados_descartados (
                      ids TEXT PRIMARY KEY, created_at TEXT NOT NULL)""")


def _llave(ids) -> str:
    return ','.join(str(i) for i in sorted(int(i) for i in ids))


def descartar_duplicado(db, ids) -> None:
    _tabla_descartados(db)
    db.execute("INSERT OR IGNORE INTO est_duplicados_descartados (ids, created_at) VALUES (?,?)",
               (_llave(ids), ahora()))


def duplicados(db) -> list[dict]:
    """Posibles duplicados entre movimientos de préstamo: mismo día y mismo
    monto. Solo lectura: el usuario confirma y borra desde Movimientos, o
    marca «No es duplicado» (descartar_duplicado)."""
    _tabla_descartados(db)
    vistos = {r[0] for r in db.execute("SELECT ids FROM est_duplicados_descartados")}
    grupos = db.execute("""
        SELECT fecha, ABS(monto) AS monto, COUNT(*) AS n FROM est_movimientos
        WHERE categoria = 'PRESTAMOS' OR tipo IN ('PRESTAMO', 'COBRO_PRESTAMO')
        GROUP BY fecha, ABS(monto) HAVING COUNT(*) > 1
        ORDER BY fecha DESC
    """).fetchall()
    out = []
    for g in grupos:
        movs = db.execute("""
            SELECT id, fecha, descripcion, monto, tipo, categoria, banco FROM est_movimientos
            WHERE fecha = ? AND ABS(monto) = ?
              AND (categoria = 'PRESTAMOS' OR tipo IN ('PRESTAMO', 'COBRO_PRESTAMO'))
            ORDER BY id
        """, (g['fecha'], g['monto'])).fetchall()
        if _llave(m['id'] for m in movs) in vistos:
            continue
        out.append({'fecha': g['fecha'], 'monto': round(float(g['monto']), 2),
                    'movimientos': [dict(m) for m in movs]})
    return out


# Grupos que el usuario ya revisó (2026-10-01: «estos no son duplicados»).
REVISADOS = (('2026-05-12', 2000.0), ('2026-03-08', 2000.0), ('2026-01-25', 4500.0))


def descartar_revisados(db) -> int:
    n = 0
    for g in duplicados(db):
        if any(g['fecha'][:10] == f and abs(g['monto'] - m) < 0.01 for f, m in REVISADOS):
            descartar_duplicado(db, [x['id'] for x in g['movimientos']])
            n += 1
    return n


def ahora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def reafirmar_categorias(db) -> int:
    """Los movimientos ligados a un préstamo (el que lo originó y sus
    devoluciones) deben seguir siendo PRESTAMOS aunque una regla de keyword
    («Aplicar reglas» o un import) les ponga otra categoría; si no, volverían
    a contar como gasto o ingreso."""
    n = db.execute("""
        UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='Prestado'
        WHERE id IN (SELECT movimiento_id FROM est_prestamos WHERE movimiento_id IS NOT NULL)
          AND categoria != 'PRESTAMOS'
    """).rowcount
    n += db.execute("""
        UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria=''
        WHERE id IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
          AND categoria != 'PRESTAMOS'
    """).rowcount
    return n


def filas_csv(db) -> list[list]:
    """Todos los movimientos de préstamo (categoría PRESTAMOS o tipo legacy)
    con la persona y el estado si ya están registrados/ligados; la columna
    Persona queda vacía en los que falta clasificar."""
    por_mov, dev_de = {}, {}
    for p in listar(db):
        if p['movimiento_id']:
            por_mov[p['movimiento_id']] = p
        for d in p['devoluciones']:
            dev_de[d['movimiento_id']] = p
    por_notas = {p['notas']: p for p in listar(db) if p['notas']}
    rows = db.execute("""
        SELECT id, fecha, descripcion, monto, banco, tipo FROM est_movimientos
        WHERE categoria = 'PRESTAMOS' OR tipo IN ('PRESTAMO', 'COBRO_PRESTAMO')
           OR id IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY fecha DESC, id DESC
    """).fetchall()
    out = []
    for r in rows:
        es_dev = r['tipo'] in ('INGRESO', 'COBRO_PRESTAMO')
        p = dev_de.get(r['id']) if es_dev else (por_mov.get(r['id']) or por_notas.get(_mensualidad_de(r)))
        out.append([
            r['id'], r['fecha'], 'Devolución' if es_dev else 'Préstamo', r['descripcion'],
            round(abs(float(r['monto'])), 2), r['banco'] or '',
            p['persona'] if p else '',
            p['estado'] if p else ('Sin ligar' if es_dev else 'Sin registrar'),
            p['pendiente'] if p and not es_dev else '',
        ])
    return out


# iPhone de MacStore A 18 MSI ($20,999, 19/11/2022) que fue para alguien más
# (msi.MENSUALIDADES_PRESTADAS ya manda sus mensualidades a PRESTAMOS). Esa
# persona le fue depositando «PAGO CUENTA DE TERCERO BNET PAGO 2», «PAGO 3»,
# «PAGO 4 Y 5»… (el usuario, 2026-09-29, con captura). Solo los que llevan
# número: el «BNET PAGO» de $1,000 del 22/07/2023 no es de esto.
IPHONE_NOTAS = 'iPhone MacStore A 18 MSI (19/11/2022)'
IPHONE_MONTO = 20999.0
IPHONE_PERSONA = 'Astro'   # el usuario, 2026-09-29: «la persona es Astro», y lo que falta ya se da por perdido


def marcar_iphone_perdido(db, hoy: str) -> int:
    """Pone a Astro como persona y marca el préstamo del iPhone como Perdido."""
    return db.execute("""UPDATE est_prestamos SET contraparte=?, perdido_fecha=COALESCE(perdido_fecha, ?)
                         WHERE notas=?""", (IPHONE_PERSONA, hoy, IPHONE_NOTAS)).rowcount
_IPHONE_DEV_RE = re.compile(r'BNET PAGO \d', re.IGNORECASE)


def ligar_iphone_macstore(db) -> tuple[int, int]:
    """Registra el préstamo (si no existe y hay depósitos) y le liga los «BNET PAGO n».
    Devuelve (préstamo creado 0/1, devoluciones ligadas). Idempotente."""
    devs = [r['id'] for r in db.execute("""
        SELECT id, descripcion FROM est_movimientos
        WHERE tipo='INGRESO' AND UPPER(descripcion) LIKE '%BNET PAGO%' AND substr(fecha,1,10) >= '2022-11-19'
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
    """).fetchall() if _IPHONE_DEV_RE.search(r['descripcion'] or '')]
    if not devs:
        return 0, 0
    p = db.execute("SELECT id FROM est_prestamos WHERE notas=?", (IPHONE_NOTAS,)).fetchone()
    creado = 0
    if p:
        pid = p['id']
    else:
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                            VALUES (?, 'OTORGADO', ?, '2022-11-19', ?, NULL, ?)""",
                         (IPHONE_PERSONA, IPHONE_MONTO, IPHONE_NOTAS, ahora())).lastrowid
        creado = 1
    for mid in devs:
        db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='' WHERE id=?", (mid,))
        db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (pid, mid, ahora()))
    return creado, len(devs)


# Mensualidades a MSI que son un préstamo ya registrado como uno solo (sin
# movimiento_id): (texto, cuota, desde, hasta, notas del préstamo). No se
# ofrecen como «sin persona» y el CSV les pone la persona de ese préstamo.
MENSUALIDADES_DE_PRESTAMO = (
    ('MACSTORE', 1167.0, '2022-11-01', '2024-04-30', IPHONE_NOTAS),
)


def _mensualidad_de(r) -> str:
    desc, fecha = (r['descripcion'] or '').upper(), (r['fecha'] or '')[:10]
    for texto, cuota, desde, hasta, notas in MENSUALIDADES_DE_PRESTAMO:
        if texto in desc and abs(abs(float(r['monto'])) - cuota) <= 1 and desde <= fecha <= hasta:
            return notas
    return ''


# Lista «Préstamos sin persona» que el usuario contestó (2026-10-01).
_SUB_PROPIA = 'Entre cuentas propias'   # = abonos.SUB_PROPIA (abonos importa este módulo)
# (fecha, monto, texto) -> persona
PRESTAMOS_MANUALES = (
    ('2026-05-12', 2000.0, 'BNET TACOS', 'Cornelius'),   # la que sí fue a Cornelius (ver IDA_Y_VUELTA)
    ('2024-10-18', 10000.0, 'CIRUJIA CAMBIO SEX', 'Jorge'),
)
# Préstamos de los que solo quedó la devolución (la salida no se identifica):
# (persona, fecha, monto, notas, devolución (fecha, monto, texto)). Quedan
# pagados. El usuario, 2026-10-03: «GRACIAS BEBO» fue Judi pagándole «un
# dinero que le presté a mi hermana, es del 2023, ya no recuerdo de qué».
PRESTAMOS_SOLO_DEVOLUCION = (
    ('Judi', '2023-05-12', 4250.0, 'Préstamo de 2023 (no recuerdo de qué)',
     ('2023-05-12', 4250.0, 'GRACIAS BEBO')),
)

# Transferencias que fueron y regresaron (salida, y el abono de vuelta que el
# lector de BBVA dejó como cargo): las dos quedan «Entre cuentas propias» y
# sin préstamo. (fecha, monto, prefijo exacto de la descripción) de la salida
# y del regreso. El usuario, 2026-10-03: «le transferí a Judi, me dijo mejor
# a Cornelius, me lo regresó y el 12 se lo pasé a Corner» — el regreso de
# Judi es «… REGRESO AL CORNER» y lo de Cornelius es «BNET TACOS …».
IDA_Y_VUELTA = (
    (('2026-05-11', 2000.0, 'PAGO CUENTA DE TERCERO BNET TRANSF A JUDITH A'),
     ('2026-05-12', 2000.0, 'PAGO CUENTA DE TERCERO BNET REGRESO AL CORNER')),
)

# Abonos que el lector de BBVA dejó como cargo («PAGO CUENTA DE TERCERO» es
# ambiguo y sin saldo impreso queda como cargo; ver parsers/bbva_libreton.py):
# devoluciones de un préstamo (fecha, monto, texto) -> (persona, fecha del
# préstamo, monto del préstamo). El usuario, 2026-10-03: Jorge le pagó los
# $10,000 de la cirugía en dos partes ($4,900 + $100 el 24/10 y $5,000 el
# 1/11, «este día me liquidó»); el $4,900 estaba registrado como otro préstamo.
DEVOLUCIONES_LEIDAS_COMO_CARGO = (
    ('2024-10-24', 4900.0, 'BNET JORGE', ('Jorge', '2024-10-18', 10000.0)),
    ('2024-10-24', 100.0, 'BNET GIO', ('Jorge', '2024-10-18', 10000.0)),
    ('2024-11-01', 5000.0, 'JORGE 2 PAGO', ('Jorge', '2024-10-18', 10000.0)),
)

# «parece que se regresó»: transferencias de $13,000 que volvieron (el
# usuario, 2026-10-03: «me prestaron y regresé»; el dinero prestado no llegó a
# una cuenta cargada en la app, el depósito del 12/09 es un retiro de CETES). Se cancelan
# con el depósito del mismo monto más cercano (15 días antes o después; el
# usuario, 2026-10-03: «un día antes me lo prestaron, al día siguiente lo
# devolví», así que el depósito puede llegar ANTES de la transferencia): las dos
# quedan como «Entre cuentas propias» (ni gasto, ni ingreso, ni Sin conciliar);
# si no aparece el depósito se dejan como están.
REGRESADOS = (
    ('2024-09-11', 13000.0, 'TRANSF A GIOVANY A'),
    ('2024-09-12', 13000.0, 'BNET DEUDA'),
)


def _mov(db, fecha, monto, texto, tipo='GASTO'):
    return db.execute("""SELECT id, fecha, monto FROM est_movimientos
                         WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005
                           AND UPPER(descripcion) LIKE ? AND tipo=?""",
                      (fecha, monto, f"%{texto}%", tipo)).fetchone()


def registrar_manuales(db) -> tuple[int, int]:
    """Registra PRESTAMOS_MANUALES y cancela REGRESADOS con su depósito.
    Devuelve (préstamos creados, parejas canceladas). Idempotente."""
    for persona, p_fecha, p_monto, notas, (d_fecha, d_monto, d_texto) in PRESTAMOS_SOLO_DEVOLUCION:
        d = db.execute("""SELECT id FROM est_movimientos WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005
                            AND UPPER(descripcion) LIKE ? AND tipo='INGRESO' ORDER BY id LIMIT 1""",
                       (d_fecha, d_monto, f"%{d_texto}%")).fetchone()
        if not d:
            continue
        p = db.execute("SELECT id FROM est_prestamos WHERE contraparte=? AND notas=?", (persona, notas)).fetchone()
        pid = p['id'] if p else db.execute(
            """INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
               VALUES (?, 'OTORGADO', ?, ?, ?, NULL, ?)""", (persona, p_monto, p_fecha, notas, ahora())).lastrowid
        db.execute("DELETE FROM est_prestamo_devoluciones WHERE movimiento_id=? AND prestamo_id != ?", (d['id'], pid))
        db.execute("INSERT OR IGNORE INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (pid, d['id'], ahora()))
        db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='' WHERE id=?", (d['id'],))
    for ida, vuelta in IDA_Y_VUELTA:
        filas = [db.execute("""SELECT id FROM est_movimientos WHERE substr(fecha,1,10)=?
                                 AND ABS(ABS(monto) - ?) < 0.005 AND UPPER(descripcion) LIKE ? ORDER BY id LIMIT 1""",
                            (f, mo, f"{t}%")).fetchone() for f, mo, t in (ida, vuelta)]
        if not all(filas):
            continue
        ids = [r['id'] for r in filas]
        if any(db.execute("""SELECT 1 FROM est_prestamo_devoluciones d JOIN est_prestamos p ON p.id = d.prestamo_id
                               WHERE p.movimiento_id=? OR d.movimiento_id=?""", (i, i)).fetchone() for i in ids):
            continue   # ya tiene devoluciones ligadas: se revisa a mano
        db.execute(f"DELETE FROM est_prestamos WHERE movimiento_id IN ({','.join('?' * len(ids))})", ids)
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=? WHERE id=?", (_SUB_PROPIA, ids[0]))
        db.execute("UPDATE est_movimientos SET tipo='INGRESO', categoria='FINANZAS', subcategoria=? WHERE id=?",
                   (_SUB_PROPIA, ids[1]))
    creados = 0
    for fecha, monto, texto, persona in PRESTAMOS_MANUALES:
        m = _mov(db, fecha, monto, texto)
        if not m or db.execute("SELECT 1 FROM est_prestamos WHERE movimiento_id=?", (m['id'],)).fetchone():
            continue
        db.execute("UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria='Prestado' WHERE id=?", (m['id'],))
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, movimiento_id, created_at)
                      VALUES (?, 'OTORGADO', ?, ?, '', ?, ?)""",
                   (persona, abs(float(m['monto'])), m['fecha'][:10], m['id'], ahora()))
        creados += 1
    for fecha, monto, texto, (persona, p_fecha, p_monto) in DEVOLUCIONES_LEIDAS_COMO_CARGO:
        m = db.execute("""SELECT id FROM est_movimientos
                          WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.005 AND UPPER(descripcion) LIKE ?""",
                       (fecha, monto, f"%{texto}%")).fetchone()
        p = db.execute("""SELECT id FROM est_prestamos WHERE contraparte=? AND substr(fecha,1,10)=?
                            AND ABS(monto - ?) < 0.005 AND COALESCE(movimiento_id, 0) NOT IN (SELECT ?)""",
                       (persona, p_fecha, p_monto, m['id'] if m else 0)).fetchone()
        if not m or not p or db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE movimiento_id=?",
                                        (m['id'],)).fetchone():
            continue
        # El «préstamo» que se registró sobre este movimiento no existe (sin devoluciones propias).
        for (pid,) in db.execute("SELECT id FROM est_prestamos WHERE movimiento_id=?", (m['id'],)).fetchall():
            if not db.execute("SELECT 1 FROM est_prestamo_devoluciones WHERE prestamo_id=?", (pid,)).fetchone():
                db.execute("DELETE FROM est_prestamos WHERE id=?", (pid,))
        db.execute("UPDATE est_movimientos SET tipo='INGRESO', categoria='PRESTAMOS', subcategoria='' WHERE id=?",
                   (m['id'],))
        db.execute("INSERT INTO est_prestamo_devoluciones (prestamo_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (p['id'], m['id'], ahora()))
    parejas = 0
    for fecha, monto, texto in REGRESADOS:
        m = _mov(db, fecha, monto, texto)
        if not m or db.execute("SELECT 1 FROM est_prestamos WHERE movimiento_id=?", (m['id'],)).fetchone():
            continue
        if db.execute("SELECT 1 FROM est_movimientos WHERE id=? AND categoria='FINANZAS' AND subcategoria=?",
                      (m['id'], _SUB_PROPIA)).fetchone():
            continue
        dep = db.execute("""SELECT id FROM est_movimientos
                            WHERE tipo='INGRESO' AND ABS(ABS(monto) - ?) < 0.005
                              AND substr(fecha,1,10) BETWEEN date(?, '-15 days') AND date(?, '+15 days')
                              AND NOT (categoria='FINANZAS' AND subcategoria=?)
                              AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
                            ORDER BY ABS(julianday(substr(fecha,1,10)) - julianday(?)), fecha, id
                            LIMIT 1""", (monto, fecha, fecha, _SUB_PROPIA, fecha)).fetchone()
        # Sin depósito en esta base (el préstamo le llegó por otro lado) la
        # salida igual queda fuera del gasto y de Por cobrar: el usuario
        # confirmó que fue regresar un préstamo que le hicieron.
        ids = (m['id'], dep['id']) if dep else (m['id'],)
        db.execute(f"UPDATE est_movimientos SET categoria='FINANZAS', subcategoria=? "
                   f"WHERE id IN ({','.join('?' * len(ids))})", (_SUB_PROPIA, *ids))
        parejas += 1
    return creados, parejas
