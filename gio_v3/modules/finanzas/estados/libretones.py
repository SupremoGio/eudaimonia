"""
Estados de cuenta del Libretón BBVA Débito (cuenta 1520361804) -- y cortes de
BBVA Crédito del formato viejo «Tarjeta Oro» (data/bbva_tdc_oro) -- que el usuario
mandó para llenar los huecos de la auditoría (2026-09-26, «te voy a pasar 5
por 5»). Cada archivo de data/bbva_deb_libreton/<AAAAMM>.json es la salida del
parser del Libretón (bbva_libreton._parse_text) sobre el PDF del banco, ya
cuadrada contra «Total importe cargos/abonos» del propio PDF (ver `totales`).
Cuando el saldo impreso no alcanza para decidir si una transferencia fue
cargo o abono, el tipo se fijó a mano y quedó anotado en `ajustes`.

Cada archivo se aplica una sola vez (migración finanzas_libreton_<AAAAMM>) y
pasa por lo mismo que un import: post-proceso de inversiones, pagos de TDC
como movimiento interno, nómina y «Aplicar reglas», más lo que el usuario ya
decidió en el CSV corregido (_decisiones_previas).

Nunca duplica: un movimiento del PDF se da por existente si BBVA_DEB ya tiene
una fila del mismo monto en su fecha de operación o de liquidación (las
descargas de la app pueden traer cualquiera de las dos). Se cuenta por
multiconjunto: dos transferencias de $500 el mismo día en el PDF contra una
en la base -> se inserta solo una.
"""
import json
import os

# carpeta en data/ -> (banco, prefijo de la migración). BBVA Crédito: cortes
# del formato viejo «Tarjeta Oro BBVA» (parsers/bbva.py::parse_tarjeta_oro).
CARPETAS = {
    'bbva_deb_libreton': ('BBVA_DEB', 'finanzas_libreton_'),
    'bbva_tdc_oro':      ('BBVA_TDC', 'finanzas_bbva_tdc_oro_'),
    # Formato actual de BBVA Crédito (parsers/bbva.py), cortes 2025-2026 que
    # el usuario mandó; su base ya tenía esos meses (de CSV) sin las
    # mensualidades a meses.
    'bbva_tdc':          ('BBVA_TDC', 'finanzas_bbva_tdc_pdf_'),
}
_BASE = os.path.join(os.path.dirname(__file__), 'data')


def archivos(carpeta: str = 'bbva_deb_libreton') -> list[str]:
    """Claves AAAAMM disponibles, en orden."""
    d = os.path.join(_BASE, carpeta)
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith('.json')) if os.path.isdir(d) else []


def cargar(clave: str, carpeta: str = 'bbva_deb_libreton') -> dict:
    with open(os.path.join(_BASE, carpeta, f'{clave}.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _decisiones_previas(db, ids: list) -> None:
    """Lo que el usuario ya decidió para movimientos iguales en el CSV
    corregido (correcciones_csv_2026_09_26): SPEI de NAFIN recibido es
    retiro de CETES; «expense» pagado es EXPENSE y el depósito de expense
    es su reembolso. Por la misma lógica (SPEI a GBM -> GBM/APORTACION): SPEI
    enviado a NAFIN es aportación a CETES y el SPEI devuelto por NAFIN, su
    retiro (se compensan). Fondo de ahorro y PTU van a NOMINA; cualquier otro
    SPEI devuelto, a FINANZAS/Reembolsable (como «SPEI DEVUELTOSANTANDER»)."""
    ph = ','.join('?' * len(ids))
    db.execute(f"""UPDATE est_movimientos SET categoria='CETES', subcategoria='APORTACION', tipo='INVERSION'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'SPEI ENVIADO NAFIN%'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='CETES', subcategoria='RETIRO', tipo='INVERSION'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'SPEI DEVUELTONAFIN%'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Fondo de ahorro'
                   WHERE id IN ({ph}) AND (UPPER(descripcion) LIKE '%FDO AHORRO%' OR UPPER(descripcion) LIKE '%FONDO AHORRO%')
                     AND tipo='INGRESO'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='NOMINA', subcategoria='PTU'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE '%PTU%' AND tipo='INGRESO'""", ids)
    # SPEI devuelto (el pago no pasó): fuera de ingreso, como «SPEI DEVUELTOSANTANDER»
    # en el CSV corregido. El de NAFIN ya se trató arriba como retiro de CETES.
    db.execute(f"""UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'SPEI DEVUELTO%'
                     AND UPPER(descripcion) NOT LIKE 'SPEI DEVUELTONAFIN%'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='CETES', subcategoria='RETIRO', tipo='INVERSION'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'SPEI RECIBIDONAFIN%'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='', tipo='GASTO'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE '%EXPENSE%' AND tipo='GASTO'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE '%EXPENSE%' AND tipo='INGRESO'""", ids)


def aplicar(db, clave: str, carpeta: str = 'bbva_deb_libreton') -> tuple[int, int]:
    """Inserta los movimientos faltantes de un estado de cuenta; (insertados, ya existían)."""
    from .routes import (_auto_clasificar_nomina, _postproceso_inversiones,
                         _reaplicar_reglas, _unify_movimiento_interno)
    banco = CARPETAS[carpeta][0]
    data = cargar(clave, carpeta)
    movs = data['movimientos']
    fechas = sorted({m['fecha'] for m in movs} | {m['fecha_cargo'] for m in movs})
    existentes = [dict(r) for r in db.execute(
        f"""SELECT id, substr(fecha,1,10) AS fecha, ABS(monto) AS monto, parcialidad_num FROM est_movimientos
            WHERE banco=? AND substr(fecha,1,10) IN ({','.join('?' * len(fechas))})""",
        [banco] + fechas).fetchall()]
    usados, nuevas, ya = set(), [], 0
    repetidos = {}
    for m in movs:
        # Dos movimientos reales idénticos el mismo día (ej. 2 retiros de $300)
        # chocarían con el índice único (fecha, descripcion, monto): el 2º
        # lleva « (2)» en la descripción.
        k = (m['fecha'], m['descripcion'], m['monto'])
        repetidos[k] = repetidos.get(k, 0) + 1
        desc = m['descripcion'] if repetidos[k] == 1 else f"{m['descripcion']} ({repetidos[k]})"
        match = next((e for e in existentes if e['id'] not in usados
                      and e['fecha'] in (m['fecha'], m['fecha_cargo'])
                      and abs(e['monto'] - abs(m['monto'])) < 0.005), None)
        if match:
            usados.add(match['id'])
            ya += 1
            # Ya estaba (p. ej. de un CSV) pero sin su «k de n»: se le pone,
            # para que la conciliación de compras a meses la ligue.
            if m.get('parcialidad_num') and not match['parcialidad_num']:
                db.execute("""UPDATE est_movimientos SET parcialidad_num=?, parcialidad_total=?, compra_msi_id=?
                              WHERE id=?""", (m['parcialidad_num'], m.get('parcialidad_total'),
                                               m.get('compra_msi_id'), match['id']))
            continue
        cur = db.execute("""INSERT OR IGNORE INTO est_movimientos
                            (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo,
                             parcialidad_num, parcialidad_total, compra_msi_id)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (m['fecha'], m['fecha_cargo'], desc, m['monto'], banco, data['periodo'],
                          m['categoria'], m['subcategoria'], m['tipo'],
                          m.get('parcialidad_num'), m.get('parcialidad_total'), m.get('compra_msi_id')))
        if cur.rowcount:
            nuevas.append(cur.lastrowid)
        else:
            ya += 1
    if nuevas:
        _decisiones_previas(db, nuevas)
        _reaplicar_reglas(db)
        _postproceso_inversiones(db)
        _unify_movimiento_interno(db, nuevas)
        _auto_clasificar_nomina(db, nuevas)
    return len(nuevas), ya
