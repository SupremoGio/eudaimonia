"""
Deuda con Papá por el seguro del carro 2026 (el usuario, 2026-11-01, con su
hoja de control: «ajústame lo que debo de seguro de carro; los 555 son de
pagos mensuales»).

Lo que Papá cubrió: póliza $6,665 + $1,500 + $700 + $5,000 (08/may) =
$13,865. Lo que Gio le ha pagado: $555.50 al mes más $2,200 (15/abr) y
$5,555 (15/may) = $12,199. Debe $1,666.

Queda como un «debo» (est_prestamos RECIBIDO) a Papá, con los pagos de la
hoja como abonos manuales: los movimientos del banco no se re-categorizan
(los mensuales siguen como TRANSPORTE/Seguro auto). Si ya hay un «debo» de
seguro con Papá, se ajusta ese (monto y abonos manuales) en vez de crear
otro. Los $5,000 del 08/may estaban como regalo (ingreso): son parte de la
deuda, pasan a PRESTAMOS para no contar como ingreso.
"""
from . import prestamos as _p

PERSONA = 'Papá'
CONCEPTO = 'Seguro del carro 2026'
FECHA = '2026-01-15'
CARGOS = (('2026-01-15', 6665.0, 'Póliza'), (None, 1500.0, ''), (None, 700.0, ''), ('2026-05-08', 5000.0, ''))
TOTAL = round(sum(m for _, m, _ in CARGOS), 2)             # 13,865
PAGOS = (('2026-01-15', 555.5), ('2026-02-27', 555.5), ('2026-04-15', 555.5), ('2026-04-15', 555.5),
         ('2026-04-15', 2200.0), ('2026-05-15', 5555.0), ('2026-06-15', 555.5), ('2026-08-15', 555.5),
         ('2026-09-17', 555.5), ('2026-10-18', 555.5))
PAGADO = round(sum(m for _, m in PAGOS), 2)                 # 12,199
NOTAS = ('Papá cubrió: póliza $6,665 (15/ene) + $1,500 + $700 + $5,000 (08/may) = $13,865. '
         'Abonos: $555.50 mensuales + $2,200 (15/abr) + $5,555 (15/may).')
NOTA_ABONO = 'Hoja de control del seguro'


def aplicar(db) -> dict:
    _p.asegurar(db)
    if not db.execute("""SELECT 1 FROM est_movimientos WHERE substr(fecha,1,4)='2026'
                          AND (subcategoria='Seguro auto' OR (tipo='INGRESO' AND substr(fecha,1,10)='2026-05-08'
                               AND ABS(ABS(monto)-5000) < 0.01))""").fetchone():
        raise RuntimeError('sin movimientos del seguro 2026 todavía; se reintenta en el próximo arranque')
    res = {'creado': 0, 'ajustado': 0, 'abonos': 0, 'regalo_a_deuda': 0}
    fila = db.execute("""SELECT id FROM est_prestamos WHERE direccion='RECIBIDO'
                           AND (contraparte LIKE 'Pap%' OR contraparte LIKE 'Eli%')
                           AND (LOWER(COALESCE(concepto,'')) LIKE '%seguro%' OR LOWER(COALESCE(notas,'')) LIKE '%seguro%')
                         ORDER BY id LIMIT 1""").fetchone()
    if fila:
        pid = fila['id']
        db.execute("UPDATE est_prestamos SET monto=?, concepto=?, notas=? WHERE id=?", (TOTAL, CONCEPTO, NOTAS, pid))
        db.execute("DELETE FROM est_prestamo_abonos WHERE prestamo_id=?", (pid,))
        res['ajustado'] = 1
    else:
        pid = db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, concepto, created_at)
                            VALUES (?, 'RECIBIDO', ?, ?, ?, ?, ?)""",
                         (PERSONA, TOTAL, FECHA, NOTAS, CONCEPTO, _p.ahora())).lastrowid
        res['creado'] = 1
    # Pagos ya ligados desde el banco (si los hay) cuentan; el resto, manual.
    ligado = round(sum(abs(float(r['monto'])) for r in db.execute("""
        SELECT m.monto FROM est_prestamo_devoluciones d JOIN est_movimientos m ON m.id = d.movimiento_id
        WHERE d.prestamo_id=?""", (pid,)).fetchall()), 2)
    falta = round(PAGADO - ligado, 2)
    if ligado < 0.005:
        for f, m in PAGOS:
            db.execute("INSERT INTO est_prestamo_abonos (prestamo_id, monto, fecha, nota, created_at) VALUES (?,?,?,?,?)",
                       (pid, m, f, NOTA_ABONO, _p.ahora()))
            res['abonos'] += 1
    elif falta > 0.005:
        db.execute("INSERT INTO est_prestamo_abonos (prestamo_id, monto, fecha, nota, created_at) VALUES (?,?,?,?,?)",
                   (pid, falta, '2026-10-18', NOTA_ABONO + ' (lo no ligado al banco)', _p.ahora()))
        res['abonos'] = 1
    res['regalo_a_deuda'] = db.execute("""
        UPDATE est_movimientos SET categoria='PRESTAMOS', subcategoria=''
        WHERE tipo='INGRESO' AND substr(fecha,1,10)='2026-05-08' AND ABS(ABS(monto)-5000) < 0.01
          AND categoria='OTROS' AND UPPER(descripcion) LIKE '%PRE%'""").rowcount
    return res
