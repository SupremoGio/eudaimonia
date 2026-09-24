"""
Recordatorios — presentación agrupada por urgencia y cálculo de la siguiente
ocurrencia de los periódicos.

La lista plana ordenada por fecha escondía lo vencido entre lo de la próxima
semana; aquí cada recordatorio se etiqueta con su fecha relativa («hoy», «en 5
días», «hace 3 meses») y su frecuencia en palabras, y se reparte en grupos
Vencidos / Hoy / Esta semana / Este mes / Más adelante / Sin fecha.
"""
import calendar
from datetime import date, timedelta

MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')
DIAS_SEM = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')

# (clave, título, predicado sobre días hasta la fecha; None = sin fecha)
GRUPOS = (
    ('vencidos', 'Vencidos', lambda d: d is not None and d < 0),
    ('hoy', 'Hoy', lambda d: d == 0),
    ('semana', 'Esta semana', lambda d: d is not None and 1 <= d <= 7),
    ('mes', 'Este mes', lambda d: d is not None and 8 <= d <= 31),
    ('despues', 'Más adelante', lambda d: d is not None and d > 31),
    ('sin_fecha', 'Sin fecha', lambda d: d is None),
)


def fecha_de(r) -> str | None:
    return r.get('next_date') or r.get('target_date') or None


def frecuencia(r) -> str:
    if r.get('type') != 'periodico':
        return ''
    n = int(r.get('freq_value') or 1)
    u = r.get('freq_unit') or 'dias'
    if u == 'dias' and n % 7 == 0:
        u, n = 'semanas', n // 7
    if n == 1:
        return {'dias': 'Diario', 'semanas': 'Semanal', 'meses': 'Mensual'}.get(u, 'Periódico')
    if u == 'meses' and n in (2, 3, 6, 12):
        return {2: 'Bimestral', 3: 'Trimestral', 6: 'Semestral', 12: 'Anual'}[n]
    return f"Cada {n} {({'dias': 'días', 'semanas': 'semanas', 'meses': 'meses'}).get(u, u)}"


def relativa(dias: int, f: date) -> str:
    if dias == 0:
        return 'Hoy'
    if dias == 1:
        return 'Mañana'
    if dias == -1:
        return 'Ayer'
    if dias < 0:
        n = -dias
        if n < 14:
            return f'Hace {n} días'
        if n < 60:
            return f'Hace {n // 7} semanas'
        return f'Hace {n // 30} meses'
    if dias <= 6:
        return f'{DIAS_SEM[f.weekday()].capitalize()} · en {dias} días'
    return f'{f.day} {MESES[f.month - 1]} · en {dias} días'


def agrupar(reminders: list[dict], hoy: date | None = None) -> list[dict]:
    """Grupos no vacíos en orden de urgencia; cada item lleva `dias`,
    `rel` (fecha relativa) y `freq` (frecuencia en palabras)."""
    hoy = hoy or date.today()
    grupos = {k: {'key': k, 'titulo': t, 'items': []} for k, t, _ in GRUPOS}
    for r in reminders:
        r = dict(r)
        f = fecha_de(r)
        dias = None
        if f:
            try:
                fd = date.fromisoformat(f[:10])
                dias = (fd - hoy).days
                r['rel'] = relativa(dias, fd)
            except ValueError:
                r['rel'] = f
        r['dias'], r['fecha'], r['freq'] = dias, f, frecuencia(r)
        for k, _, pred in GRUPOS:
            if pred(dias):
                grupos[k]['items'].append(r)
                break
    for g in grupos.values():
        g['items'].sort(key=lambda r: (r['fecha'] or '9999', r.get('created_at') or ''))
    return [grupos[k] for k, _, _ in GRUPOS if grupos[k]['items']]


def _paso(ancla: date, fu: str, fv: int, k: int) -> date:
    """k-ésima ocurrencia contada desde el ancla (sin arrastrar el día del mes
    recortado: del 31 de enero se pasa al 28 feb y luego al 31 mar)."""
    if fu == 'semanas':
        return ancla + timedelta(weeks=fv * k)
    if fu == 'meses':
        m = ancla.month - 1 + fv * k
        y, m = ancla.year + m // 12, m % 12 + 1
        return date(y, m, min(ancla.day, calendar.monthrange(y, m)[1]))
    return ancla + timedelta(days=fv * k)


def siguiente(r: dict, hoy: str) -> str:
    """Siguiente fecha de un periódico al marcarlo hecho: la primera ocurrencia
    del ciclo (anclado en target_date, la fecha que puso el usuario) posterior
    tanto a hoy como a la fecha programada actual. Así posponer una vez no
    mueve el día del ciclo, y pagar tarde o temprano tampoco."""
    fv = int(r.get('freq_value') or 1)
    fu = r.get('freq_unit') or 'dias'
    prog = r.get('next_date') or r.get('target_date') or hoy
    ancla = date.fromisoformat((r.get('target_date') or prog)[:10])
    limite = max(hoy, prog[:10])
    k = 1
    while (cand := _paso(ancla, fu, fv, k)).isoformat() <= limite:
        k += 1
    return cand.isoformat()
