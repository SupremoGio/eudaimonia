"""
Estados de cuenta del Libretón BBVA Débito (cuenta …1804) -- y cortes de
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
import re

from .contrapartes import cuenta_de

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


def _palabras(desc: str) -> set:
    """Palabras del comercio (sin el prefijo «NN DE NN»), para saber si dos
    filas del mismo monto son el mismo cargo."""
    d = re.sub(r'^\d{1,2} DE \d{1,2}\s+', '', (desc or '').upper())
    return {w for w in re.split(r'[^A-Z0-9ÁÉÍÓÚÑ]+', d) if len(w) >= 4}


def _match(existentes, usados, m):
    """La fila de la base que ya es este movimiento del PDF, o None. Primero
    una del mismo comercio en su fecha de operación o de liquidación; si no,
    cualquiera del mismo monto en la MISMA fecha de operación. Por fecha de
    liquidación con otro comercio no: la mensualidad Amazon $114 del 22/07
    no es el Little Caesars de $114 del 23/07."""
    libres = [e for e in existentes if e['id'] not in usados and abs(e['monto'] - abs(m['monto'])) < 0.005]
    pal = _palabras(m['descripcion'])
    return (next((e for e in libres if e['fecha'] in (m['fecha'], m['fecha_cargo'])
                  and pal & _palabras(e['descripcion'])), None)
            or next((e for e in libres if e['fecha'] == m['fecha']), None))


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
                   WHERE id IN ({ph}) AND (UPPER(descripcion) LIKE '%FDO AHORRO%' OR UPPER(descripcion) LIKE '%FONDO AHORRO%'
                                           OR UPPER(descripcion) LIKE '%FONDO DE AHORRO%')
                     AND tipo='INGRESO'""", ids)
    # Libretones de 2021-2022 (empresa anterior, depósitos «BMRCASH»):
    # «PAGO DE AGUINALDO» y la quincena «DEPOSITO DE TERCERO PAGO Q8 ABR2022».
    db.execute(f"""UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Aguinaldo'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE '%AGUINALDO%' AND tipo='INGRESO'""", ids)
    db.execute(f"""UPDATE est_movimientos SET categoria='NOMINA', subcategoria='Pago nominal'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'DEPOSITO DE TERCERO PAGO Q%' AND tipo='INGRESO'""", ids)
    # Devuelve una recarga de celular del mismo día: resta al gasto de celular.
    db.execute(f"""UPDATE est_movimientos SET categoria='DIGITAL', subcategoria='Celular'
                   WHERE id IN ({ph}) AND UPPER(descripcion) LIKE 'CORRECCION COMPRA TIEMPO%' AND tipo='INGRESO'""", ids)
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
        f"""SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, parcialidad_num FROM est_movimientos
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
        match = _match(existentes, usados, m)
        if match:
            usados.add(match['id'])
            ya += 1
            # El periodo de débito lo decide la fecha de liquidación: si la
            # fila venía sin ella (exportación de movimientos), se le pone.
            if banco == 'BBVA_DEB' and (cuenta := cuenta_de(m['descripcion'])):
                db.execute("UPDATE est_movimientos SET cuenta_contraparte=? WHERE id=? AND cuenta_contraparte IS NULL",
                           (cuenta, match['id']))
            if banco == 'BBVA_DEB' and m.get('fecha_cargo') and m['fecha_cargo'] != m['fecha']:
                db.execute("""UPDATE est_movimientos SET fecha_cargo=? WHERE id=?
                              AND (fecha_cargo IS NULL OR fecha_cargo='' OR substr(fecha_cargo,1,10)=substr(fecha,1,10))""",
                           (m['fecha_cargo'], match['id']))
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


def reparar_parcialidades(db) -> list:
    """Una sola vez: el cargador viejo empataba por monto y fecha de
    liquidación sin ver el comercio, y a veces le ponía la «k de n» de una
    mensualidad a otro cargo (Little Caesars $114 del 23/07/2026 se quedó con
    la «6 de 6» de Amazon del 22/07, y la mensualidad no se insertó). Por cada
    mensualidad de los PDFs cargados: si la fila que tiene su «k de n» es de
    otro comercio, se le quita y se inserta la mensualidad."""
    from .routes import _reaplicar_reglas, _unify_movimiento_interno
    arreglos, nuevas = [], []
    for carpeta, (banco, _) in CARPETAS.items():
        for clave in archivos(carpeta):
            data = cargar(clave, carpeta)
            for m in data['movimientos']:
                if not m.get('parcialidad_num'):
                    continue
                filas = db.execute("""
                    SELECT id, descripcion FROM est_movimientos
                    WHERE banco=? AND substr(fecha,1,10) IN (?,?) AND ABS(ABS(monto) - ?) < 0.005
                      AND parcialidad_num=? AND parcialidad_total IS ?""",
                    (banco, m['fecha'], m['fecha_cargo'], abs(m['monto']),
                     m['parcialidad_num'], m.get('parcialidad_total'))).fetchall()
                pal = _palabras(m['descripcion'])
                if not filas or any(pal & _palabras(f['descripcion']) for f in filas):
                    continue
                for f in filas:
                    db.execute("""UPDATE est_movimientos SET parcialidad_num=NULL, parcialidad_total=NULL,
                                  compra_msi_id=NULL WHERE id=?""", (f['id'],))
                ya = db.execute("""SELECT 1 FROM est_movimientos WHERE banco=? AND substr(fecha,1,10)=?
                                   AND ABS(ABS(monto) - ?) < 0.005 AND UPPER(descripcion)=?""",
                                (banco, m['fecha'], abs(m['monto']), m['descripcion'].upper())).fetchone()
                if not ya:
                    cur = db.execute("""INSERT OR IGNORE INTO est_movimientos
                        (fecha, fecha_cargo, descripcion, monto, banco, periodo, categoria, subcategoria, tipo,
                         parcialidad_num, parcialidad_total, compra_msi_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (m['fecha'], m['fecha_cargo'], m['descripcion'], m['monto'], banco, data['periodo'],
                         m['categoria'], m['subcategoria'], m['tipo'], m['parcialidad_num'],
                         m.get('parcialidad_total'), m.get('compra_msi_id')))
                    if cur.rowcount:
                        nuevas.append(cur.lastrowid)
                arreglos.append(f"{m['fecha']} {m['descripcion']} ${abs(m['monto']):,.2f} "
                                f"(estaba en: {', '.join(f['descripcion'] for f in filas)})")
    if nuevas:
        _unify_movimiento_interno(db, nuevas)
    if arreglos:
        _reaplicar_reglas(db)
    return arreglos
