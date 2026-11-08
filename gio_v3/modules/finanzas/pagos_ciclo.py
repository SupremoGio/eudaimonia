"""
Pagos del ciclo de las tarjetas (Oikonomia v2, Sprint 2).

PAY_DAYS (routes.py) dice qué día se paga cada tarjeta, pero no había ningún
registro de «este mes ya lo pagué»: el aviso y el badge «Hoy» salían aunque
el pago ya estuviera hecho. Tabla fin_pagos_ciclo (cuenta, ciclo YYYY-MM,
UNIQUE): una fila = ese ciclo ya está pagado.

- Ciclo de una tarjeta = el mes de su próxima fecha de pago (hoy incluido).
  Pagar el 15-oct cierra el ciclo 2026-10; el 16-oct el próximo pago es el
  15-nov, ciclo 2026-11, todavía pendiente.
- Se marca a mano desde el hub (origen 'manual') o se detecta solo cuando
  el estado de cuenta trae un movimiento PAGO_TDC de esa tarjeta después del
  pago anterior y hasta la fecha de pago (origen 'estado').
"""
import calendar
from datetime import date, datetime

from utils import today_date


def _due(y, m, day):
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def ciclo(pay, hoy=None):
    """(ciclo 'YYYY-MM', fecha de pago, fecha de pago anterior) de una tarjeta."""
    hoy = hoy or today_date()
    due = _due(hoy.year, hoy.month, pay['day'])
    if due < hoy:
        y, m = (hoy.year, hoy.month + 1) if hoy.month < 12 else (hoy.year + 1, 1)
        due = _due(y, m, pay['day'])
    py, pm = (due.year, due.month - 1) if due.month > 1 else (due.year - 1, 12)
    return due.strftime('%Y-%m'), due, _due(py, pm, pay['day'])


def _pay(cuenta):
    from .routes import PAY_DAYS
    return next((p for p in PAY_DAYS if p['match'] == cuenta), None)


def detectar(db, hoy=None):
    """Registra como pagados (origen 'estado') los ciclos cuyo PAGO_TDC ya entró
    en un estado de cuenta. Idempotente. Devuelve cuántos registró."""
    from .routes import PAY_DAYS
    n = 0
    for p in PAY_DAYS:
        cic, due, prev = ciclo(p, hoy)
        if db.execute("SELECT 1 FROM fin_pagos_ciclo WHERE cuenta=? AND ciclo=?", (p['match'], cic)).fetchone():
            continue
        # Por banco solo cuenta el estado de la propia tarjeta (BBVA_TDC,
        # INVEX, HSBC): un SPEI a Invex sale de BBVA_DEB y no es pago de BBVA.
        # Desde otra cuenta, solo si la descripción nombra la tarjeta.
        m = p['match'].upper()
        r = db.execute("""
            SELECT id, ABS(monto) AS monto FROM est_movimientos
            WHERE categoria='PAGO_TDC' AND substr(fecha,1,10) > ? AND substr(fecha,1,10) <= ?
              AND (UPPER(banco) IN (?, ?) OR UPPER(descripcion) LIKE ?)
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, (prev.isoformat(), due.isoformat(), m, f'{m}_TDC', f'%{m}%')).fetchone()
        if r:
            db.execute("""INSERT OR IGNORE INTO fin_pagos_ciclo (cuenta, ciclo, monto, origen, movimiento_id, created_at)
                          VALUES (?,?,?,?,?,?)""",
                       (p['match'], cic, r['monto'], 'estado', r['id'], datetime.now().isoformat(timespec='seconds')))
            n += 1
    return n


def pagados(db, hoy=None):
    """{cuenta: fila} de las tarjetas con el ciclo actual pagado."""
    from .routes import PAY_DAYS
    out = {}
    for p in PAY_DAYS:
        cic = ciclo(p, hoy)[0]
        r = db.execute("SELECT * FROM fin_pagos_ciclo WHERE cuenta=? AND ciclo=?", (p['match'], cic)).fetchone()
        if r:
            out[p['match']] = dict(r)
    return out


def marcar(db, cuenta, monto=None, hoy=None):
    """Marca a mano el ciclo actual de `cuenta` como pagado. Devuelve la fila
    (la existente si ya estaba pagado). ValueError si la cuenta no existe."""
    p = _pay(cuenta)
    if not p:
        raise ValueError('Cuenta desconocida')
    cic = ciclo(p, hoy)[0]
    db.execute("""INSERT OR IGNORE INTO fin_pagos_ciclo (cuenta, ciclo, monto, origen, movimiento_id, created_at)
                  VALUES (?,?,?,?,NULL,?)""", (cuenta, cic, monto, 'manual', datetime.now().isoformat(timespec='seconds')))
    return dict(db.execute("SELECT * FROM fin_pagos_ciclo WHERE cuenta=? AND ciclo=?", (cuenta, cic)).fetchone())


def deshacer(db, cuenta, hoy=None):
    """Quita la marca manual del ciclo actual. Un pago detectado en el estado
    de cuenta no se deshace aquí (volvería a detectarse): ValueError."""
    p = _pay(cuenta)
    if not p:
        raise ValueError('Cuenta desconocida')
    cic = ciclo(p, hoy)[0]
    r = db.execute("SELECT origen FROM fin_pagos_ciclo WHERE cuenta=? AND ciclo=?", (cuenta, cic)).fetchone()
    if r and r['origen'] == 'estado':
        raise ValueError('Ese pago viene del estado de cuenta: no se puede desmarcar desde aquí.')
    db.execute("DELETE FROM fin_pagos_ciclo WHERE cuenta=? AND ciclo=?", (cuenta, cic))
    return bool(r)
