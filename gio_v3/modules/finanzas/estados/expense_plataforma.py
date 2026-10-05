"""
Conciliación de Expense con el export de la plataforma de reembolsos de la
empresa (data/expense_plataforma.json, 176 gastos mar 2024 - jul 2026; el
usuario, 2026-09-28: «ya encontré el csv de la plataforma que paga expense,
con esto ya puedes conciliar todo»).

La plataforma dice QUÉ se reembolsó y cuánto, pero no con qué depósito ni con
qué cargo del banco. Dos pasos:

1. Depósito ↔ gastos de la plataforma. Los depósitos de la empresa sin lote
   (FIDEICOMISO F 1596, SITH2…, EXPENSE BMRCASH; expense_lotes._DEP_RE) se
   atienden del más antiguo al más reciente, y cada uno toma gastos de la
   plataforma de antes de su fecha, en este orden de pasadas:
     - un gasto del mismo monto (≤120 días antes);
     - «FIFO»: los gastos pendientes más antiguos, seguidos, que suman el
       depósito (la empresa paga en orden; ≤185 días);
     - un bloque de gastos seguidos que suma el depósito (≤120 días);
     - cualquier combinación que sume el depósito (≤120, luego ≤240 días).
   Se eligió comparando variantes contra los depósitos de las capturas del
   usuario: así la mediana entre gasto y depósito es de ~24 días y ninguno
   pasa de 6 meses (con ventanas más largas salían emparejamientos de más de
   un año).

2. Gasto de la plataforma ↔ cargo del banco: mismo monto (±$0.01), del día
   del gasto hasta 10 días después (lo que tarda en aparecer el cargo), un
   cargo por gasto; primero los que ya están como EXPENSE.

Con eso se crea un lote por depósito (sus cargos pasan a EXPENSE y quedan
Pagado). Los gastos sin cargo en el banco (efectivo, otra tarjeta sin estado
de cuenta) quedan anotados en las notas del lote.
"""
import json
import os
from datetime import date, timedelta

from . import expense_lotes as _lotes

_ARCHIVO = os.path.join(os.path.dirname(__file__), 'data', 'expense_plataforma.json')
TOL = 1.0
# Cargo del banco: desde 7 días antes del gasto (se pagó y el recibo se
# registró después) hasta 15 días después (lo que tarda en aparecer).
DIAS_ANTES, DIAS_DESPUES = 7, 15


# Gastos del export que no son del usuario (2026-10-05: «servyviajes yo no
# pagué nada de eso», «este tampoco es mío»): (fecha, título, monto).
NO_SON_MIOS = (
    ('2025-12-01', 'SERVIVYAJES', 10461.00),
    ('2025-12-01', 'SERVYVIAJES', 4694.00),
    ('2026-03-04', 'ACTIVIDAD INTEGRACION MARRIOTT BONVOY', 1442.00),
    ('2025-12-17', 'ACTIVIDAD INTEGRACION MARRIOTT BONVOY', 21273.00),
    # Duplicado de «DECORACION POSADA» $1,010 del 18/12/2025, ya pagado.
    ('2025-12-26', 'EXPENSE DECORACION POSADA', 1010.00),
)


def _no_es_mio(x) -> bool:
    return any(x['fecha'] == f and x['titulo'] == t and abs(x['monto'] - m) < 0.005 for f, t, m in NO_SON_MIOS)


# Gastos que el usuario pasó de reportes posteriores al export (que llega al
# 09/07/2026): fecha, título, tipo y monto en MXN (Amount LC).
EXTRA = (
    # Reporte de jul-2026 (56.88 USD), pagado con el depósito de $986.50 del 18/08/2026.
    {'fecha': '2026-07-28', 'titulo': 'PIZZAS EVENTO LP', 'tipo': 'Associate Celebrations Meals PS(655641) / SUN(624401)', 'monto': 796.00},
    {'fecha': '2026-07-28', 'titulo': 'REFRESCOS LP', 'tipo': 'Associate Celebrations Meals PS(655641) / SUN(624401)', 'monto': 190.50},
)


def items() -> list[dict]:
    with open(_ARCHIVO, encoding='utf-8') as fh:
        data = [x for x in json.load(fh)['items'] if not _no_es_mio(x)] + [dict(x) for x in EXTRA]
    out = [{**x, 'idx': i} for i, x in enumerate(sorted(data, key=lambda x: (x['fecha'], x['titulo'])))]
    return out


def _exacto(cand, monto, tol):
    uno = [x for x in cand if abs(x['monto'] - monto) <= min(tol, 0.01)]
    return [uno[0]] if uno else None


def _fifo(cand, monto, tol):
    s, out = 0.0, []
    for x in cand:
        s += x['monto']
        out.append(x)
        if abs(s - monto) <= tol:
            return out if len(out) > 1 else None
        if s > monto + tol:
            return None
    return None


def _bloque(cand, monto, tol):
    for i in range(len(cand)):
        s = 0.0
        for j in range(i, len(cand)):
            s += cand[j]['monto']
            if j > i and abs(s - monto) <= tol:
                return cand[i:j + 1]
            if s > monto + tol:
                break
    return None


def _suma(cand, monto, tol):
    idx = _lotes._combinacion([x['monto'] for x in cand], monto, tol)
    return [cand[i] for i in idx] if idx is not None else None


_PASADAS_BASE = (('mismo monto', 120, _exacto), ('FIFO', 185, _fifo), ('bloque', 120, _bloque),
                 ('combinación', 120, _suma), ('combinación', 240, _suma))
# Primero todo lo que cuadra al centavo y después lo que cuadra con hasta $1
# de redondeo: el de $4,365.55 (15/11/2024) cuadra exacto ($4,365.54) con
# Despensa + pasteles + Día del Chef + Corona, pero el de $2,215.60 se los
# ganaba antes con una combinación que daba $2,215.99.
PASADAS = tuple((n, d, f, 0.02) for n, d, f in _PASADAS_BASE) + \
          tuple((n + ' ±$1', d, f, TOL) for n, d, f in _PASADAS_BASE if f is not _exacto)


def _ventana(d, gastos, libres, dias):
    desde = (date.fromisoformat(d['fecha'][:10]) - timedelta(days=dias)).isoformat()
    return [x for x in gastos if x['idx'] in libres and desde <= x['fecha'] <= d['fecha'][:10]]


def _emparejar(d, gastos, libres):
    for nombre, dias, fn, tol in PASADAS:
        cand = _ventana(d, gastos, libres, dias)
        sel = fn(cand, float(d['monto']), tol) if cand else None
        if sel:
            return nombre, sel
    return None


# Emparejamientos aproximados aceptados por el usuario (2026-09-28, «dalos por
# buenos»): (fecha, monto) del depósito -> títulos de los gastos. El de
# $738.70 del 30/08/2024 con confeti + globos del aniversario + pastel agosto
# ($767.68; la empresa rechazó $28.98).
APROXIMADOS = {('2024-08-30', 738.70): ('CONFETI AC ANIVERSARIO', 'GLOBOS AC ANIVERSARIO', 'pastel agosto')}


# Asignación fija depósito -> gastos (fecha, título, monto), revisada con el
# usuario (2026-10-05). Es la de la v6 con la corrección de Día de las Madres
# 2024 por los reportes que pasó: cada uno de los dos reportes trae sus
# propias bolsas, flores y pastel (no son duplicados). Así un cambio en el
# export (quitar un gasto ajeno) no mueve los demás depósitos; el algoritmo
# solo empareja depósitos nuevos.
FIJOS = {
    ('2024-04-23', 410.0): (
        ('2024-03-27', 'MARISA PASTEL', 410.0),
    ),
    ('2024-05-14', 2944.0): (
        ('2024-04-30', 'dulces dia del nino', 544.03),
        ('2024-04-30', 'juguetes dia del nino', 2400.0),
    ),
    # Reporte 12169 «DIA DE LAS MADRES» (179.22 USD): bolsas + flores + la mitad
    # de los regalos ($2,340; la otra mitad va en el reporte «DÍA DE LA MADRE»).
    ('2024-05-20', 2973.24): (
        ('2024-05-08', 'REGALOS DIA MADRE', 4680.0),
        ('2024-05-13', 'BOLSAS DIA DE MADRES', 285.0),
        ('2024-05-13', 'FLORES DIA DE LAS MADRES', 348.24),
    ),
    # Reporte 12170 «PASTEL DIA DE LAS MADRES» (33.82 USD).
    ('2024-05-28', 561.0): (
        ('2024-05-15', 'PASTEL DIA DE LAS MADRES', 561.0),
    ),
    ('2024-05-28', 4640.0): (
        ('2024-05-24', 'PASTEL ANIVERSARIO GDLAC', 4640.0),
    ),
    ('2024-07-16', 542.0): (
        ('2024-07-10', 'PASTEL CUMPLEAÑOS JULIO', 542.0),
    ),
    ('2024-08-30', 738.7): (
        ('2024-06-05', 'CONFETI AC ANIVERSARIO', 100.02),
        ('2024-06-05', 'GLOBOS AC ANIVERSARIO', 134.66),
        ('2024-08-16', 'pastel agosto', 533.0),
    ),
    ('2024-09-09', 518.0): (
        ('2024-09-02', 'PASTEL SEPTIEMBRE', 518.0),
    ),
    ('2024-10-04', 527.5): (
        ('2024-09-09', 'PASTEL SEPTIEMBRE', 420.0),
        ('2024-09-10', 'DULCES ACTIVIDADES SEPTIEMBRE', 107.5),
    ),
    ('2024-10-11', 738.0): (
        ('2024-09-27', 'actividad septiembre', 343.0),
        ('2024-10-08', 'PASTEL OCTUBRE CUMPLEAÑOS', 395.0),
    ),
    ('2024-10-18', 372.5): (
        ('2024-10-09', 'Dulces oct', 107.0),
        ('2024-10-11', 'Actividad mental health', 265.0),
    ),
    ('2024-11-01', 2215.6): (
        ('2024-05-17', 'DULCES ACTIVIDAD MAYO', 149.5),
        ('2024-06-28', 'DULCES JUNTA MENSUAL', 309.0),
        ('2024-10-18', 'PASTEL OCT', 740.0),
        ('2024-10-22', 'refrescos dia chef', 86.0),
        ('2024-10-25', 'pizza actividad oct', 596.0),
        ('2024-10-31', 'PAPELERIA ALTAR DE MUERTO', 335.0),
    ),
    ('2024-11-15', 4365.55): (
        ('2024-10-18', 'DESPENSA SERVE 360', 1904.4),
        ('2024-10-18', 'pastel cocina', 415.0),
        ('2024-10-22', 'DIA DEL CHEF ACTIVIDAD', 415.0),
        ('2024-10-22', 'REFRESCO ACTI DIA DELCHEF', 160.14),
        ('2024-10-25', 'pastel act oct', 427.0),
        ('2024-11-06', 'Corona', 1044.0),
    ),
    ('2024-11-29', 477.0): (
        ('2024-11-13', 'DULCES NOV', 107.0),
        ('2024-11-25', 'PASTEL NOC', 370.0),
    ),
    ('2024-12-06', 6138.0): (
        ('2024-11-29', 'Decoracion Navidad', 1047.0),
        ('2024-11-29', 'REGALOS POSADA', 4895.0),
        ('2024-11-29', 'SNACK ACTIVIDAD PINO NAVIDAD', 196.0),
    ),
    ('2024-12-20', 715.0): (
        ('2024-12-05', 'pastle dic', 395.0),
        ('2024-12-11', 'pastel dic', 320.0),
    ),
    ('2025-01-10', 3500.9): (
        ('2024-12-13', 'CUADROS RECONOCIMIENTO', 625.0),
        ('2024-12-13', 'DECORACION POSADA', 239.9),
        ('2024-12-13', 'DULCES PIÑATA POSADA', 758.0),
        ('2024-12-20', 'BOTANA POSADA', 529.0),
        ('2024-12-20', 'PAPEL REGALO POSADA', 688.5),
        ('2024-12-20', 'RECONOCIMIENTOS POSADA', 201.5),
        ('2024-12-23', 'pastel dic', 459.0),
    ),
    ('2025-01-22', 642.0): (
        ('2025-01-06', 'ACTIVIDAD VIERNES BOTANA', 222.0),
        ('2025-01-08', 'PASTEL ENERO', 420.0),
    ),
    ('2025-02-26', 445.0): (
        ('2025-02-17', 'PASTEL FEB', 445.0),
    ),
    ('2025-02-26', 2030.0): (
        ('2025-02-06', 'ACTIVIDAD TAMALES', 2030.0),
    ),
    ('2025-03-12', 1239.0): (
        ('2025-02-26', 'PASTEL 1FEB', 520.0),
        ('2025-02-28', 'DULCES PULSE SURVEY', 339.0),
        ('2025-02-28', 'PASTEL 2FEB', 380.0),
    ),
    ('2025-04-09', 441.3): (
        ('2025-03-20', 'ACTIVIDAD CAPACITACION MARZO', 441.3),
    ),
    ('2025-04-23', 480.0): (
        ('2025-03-26', 'PASTEL MARZO', 480.0),
    ),
    ('2025-06-04', 442.0): (
        ('2025-04-25', 'actividad snack abril', 442.0),
    ),
    ('2025-06-09', 42674.84): (
        ('2024-10-30', 'pan de muerto', 138.85),
        ('2024-11-06', 'Globos decoracion', 71.5),
        ('2024-11-06', 'pastel noviembre', 395.0),
        ('2024-11-07', 'uniforme asociado', 558.0),
        ('2025-04-30', 'ACTIVIDAD BRAND INMERSION', 254.5),
        ('2025-05-07', 'Snack lunes  Elotes', 1740.0),
        ('2025-05-08', 'snack elotes pt 2', 1740.0),
        ('2025-05-09', 'FLORES DIA MADRE', 265.0),
        ('2025-05-09', 'REGALO DIA DE LAS MADRES', 3667.0),
        ('2025-05-14', 'SNACK AAW CHURROS', 3229.43),
        ('2025-05-16', 'BANQUETE AAW', 19329.66),
        ('2025-05-16', 'CANDADO ACTIVIDAD AAW', 65.0),
        ('2025-05-16', 'DULCE ACTIVIDAD AAW', 97.0),
        ('2025-05-16', 'PASTEL CUMPLEAÑO MAYO', 440.0),
        ('2025-05-19', 'COMIDA HOT DOG MARTES AAW', 6214.25),
        ('2025-05-20', 'PIPZAS 2 VIERNES AAW', 1490.0),
        ('2025-05-20', 'PIZZAS 1 VIERNES AAW', 1490.0),
        ('2025-05-20', 'PIZZAS 3 VIERNES AAW', 1490.0),
    ),
    ('2025-06-11', 124.9): (
        ('2025-06-03', 'DULCES ENCUESTA PULSE', 124.9),
    ),
    ('2025-07-02', 1805.2): (
        ('2025-05-22', 'UNIFORMES RRHH', 1003.0),
        ('2025-06-10', 'SNACK VIERNES BOTANA', 558.2),
        ('2025-06-13', 'ACTIVIDAD CAPACITACION', 244.0),
    ),
    ('2025-07-23', 735.0): (
        ('2025-06-30', 'Pastel julio', 355.0),
        ('2025-07-03', 'Pastel julio', 380.0),
    ),
    # Depósito de expense de sep-2025 (confirmado por el usuario): el reporte
    # del HR Summit completo (7 gastos, 133.67 USD = $2,478.11) + pasteles,
    # dulces y actividad de may–jul 2025 ($2,434.50; $1 de redondeo).
    ('2025-09-03', 4913.61): (
        ('2025-07-06', 'UBER GDL - AEROPUERTO', 364.8),
        ('2025-07-06', 'UBER AEROPUERTO- CDMX', 179.91),
        ('2025-07-10', 'UBER CDMX - AEROPUERTO', 139.41),
        ('2025-07-14', 'Taxi 1', 455.0),
        ('2025-07-14', 'COMIDA HR SUMMIT', 756.0),
        ('2025-07-14', 'COMIDA 3 SUMMIT', 246.0),
        ('2025-07-15', 'COMIDA 2 SUMMIT', 336.99),
        ('2025-04-30', 'PASTEL MAYO', 525.0),
        ('2025-06-16', 'PASTEL JUNIO', 445.0),
        ('2025-06-18', 'DULCES ACTIVIDAD JUNIO', 122.5),
        ('2025-07-07', 'ACTIVIDAD JULIO', 228.0),
        ('2025-07-30', 'Dulces Actividad Junta Mensual', 559.0),
        ('2025-07-30', 'Pastel julio', 555.0),
    ),
    ('2025-09-10', 835.0): (
        ('2025-08-21', 'pastel agosto', 380.0),
        ('2025-08-29', 'VASOS ACTIVIDAD', 75.0),
        ('2025-08-29', 'pastel agosto', 380.0),
    ),
    ('2025-10-01', 2788.71): (
        ('2025-03-27', 'PASTEL CUMPLEAÑOS MARZO', 380.0),
        ('2025-04-21', 'pastel abril', 510.01),
        ('2025-07-29', 'cuadro', 315.0),
        ('2025-09-08', 'PASTEL SEPT', 434.01),
        ('2025-09-10', 'PASTEL SEPT', 499.0),
        ('2025-09-22', 'DHL CONTRATO CTM', 418.71),
        ('2025-09-23', 'HSKP week', 92.0),
    ),
    ('2025-10-22', 389.0): (
        ('2025-05-13', 'CAJA REGALOS DIA MADRES', 240.0),
        ('2025-10-22', 'EXPENSE LISTONES ROSAS', 150.0),
    ),
    ('2025-11-26', 4759.25): (
        ('2025-09-19', 'DULCES HSKP WEEK', 413.0),
        ('2025-10-21', 'DULCES GRADUACION WORLD VISION', 214.0),
        ('2025-10-24', 'FLORES GRADUACION WORLD VISION', 2900.0),
        ('2025-10-31', 'PAPELERIA ALTAR DE MUERTO', 329.0),
        ('2025-11-03', 'DULCES ALTAR DE MUERTO', 277.25),
        ('2025-11-03', 'DULCES ALTAR DE MUERTOS', 277.25),
        ('2025-11-04', 'FLORES ALTAR DE MUERTOS', 348.62),
    ),
    ('2025-12-11', 920.0): (
        ('2025-11-18', 'CANDADO ESTANTE SKYBAR', 108.0),
        ('2025-12-01', 'SNACK ARBOL DE NAVIDAD', 152.0),
        ('2025-12-02', 'LUCES ARBOL DE NAVIDAD', 660.0),
    ),
    ('2026-01-07', 4479.0): (
        ('2025-10-22', 'LISTON ROSA CANCER DE MAMA', 150.0),
        ('2025-10-24', 'FLORES GRADUACION', 2963.18),
        ('2025-11-04', 'FLORES PARA ALTAR', 340.0),
        ('2025-12-15', 'OPALINA INVITACION POSADA', 270.0),
    ),
    ('2026-02-10', 454.0): (
        ('2026-01-07', 'EXPENSE CHIP CEL RH', 99.0),
        ('2026-01-07', 'PASTEL ENERO', 355.0),
    ),
    ('2026-03-25', 1862.0): (
        ('2025-10-21', 'Dulces Halloween', 214.0),
        ('2025-10-31', 'PAPELERIA ALTAR', 329.0),
        ('2025-11-01', 'PASTEL NOV', 549.0),
        ('2025-12-04', 'DULCES INVITACION POSADA', 770.0),
    ),
    ('2026-04-23', 3142.39): (
        ('2026-04-13', 'PASTEL CUMPLEAÑOS ABRIL', 570.0),
        ('2026-04-14', 'ARREGLO FLORAL', 2572.39),
    ),
    ('2026-05-06', 690.0): (
        ('2026-04-02', 'velas hora del planeta', 140.0),
        ('2026-04-21', 'pastel cumpleaños abril', 550.0),
    ),
    ('2026-05-20', 10143.5): (
        ('2026-04-28', 'GLOBOS DECORACION DIA DEL NINO', 374.92),
        ('2026-04-30', 'DESPEDIDA PRACTICANTES', 420.0),
        ('2026-05-05', 'IMPRESIONES DIA DEL NIÑO', 119.8),
        ('2026-05-07', 'DECORACION DIA DEL NINO', 347.0),
        ('2026-05-13', 'REGALOS DIAS DE LAS MADRES', 8067.68),
        ('2026-05-15', 'ACTIVIDAD AAW', 334.1),
        ('2026-05-15', 'PASTEL CUMPLEANEROS MAYO', 480.0),
    ),
    ('2026-05-27', 4582.0): (
        ('2026-05-27', 'PASTEL ANIVERSARIO HOTEL', 4582.0),
    ),
    ('2026-06-04', 4582.0): (
        ('2026-06-01', 'PASTEL ANIVERSARIO PT 2', 4582.0),
    ),
    ('2026-06-18', 709.0): (
        ('2026-05-18', 'IMPRESION AAW', 334.1),
        ('2026-05-19', 'REFRESCOS AAW', 176.0),
        ('2026-05-26', 'ACTIVIDAD AAW', 98.9),
        ('2026-05-26', 'ACTIVIDAD CLAUSURA AAW', 100.0),
    ),
    ('2026-07-22', 7163.62): (
        ('2025-12-19', 'boletos bus taskforce', 6105.08),
        ('2026-06-02', 'CUMPLEAÑOS JULIO', 580.0),
        ('2026-06-20', 'EXPENSE CUMPLEAÑOS JULIO', 244.49),
        ('2026-07-09', 'AMENIDAD ANIVERSARIOS', 235.0),
    ),
    ('2026-08-12', 3799.4): (
        ('2025-12-18', 'DECORACION POSADA', 1010.0),
        ('2026-04-09', 'JUNTA DEPARTAMENTAL FRONT ABRIL', 476.0),
        ('2026-05-28', 'Gastos decoracion Junta mensual Asociados junio 2026', 371.0),
        ('2026-05-30', 'Gastos decoracion Junta mensual Asociados junio 2026', 1045.0),
        ('2026-06-30', 'CUADRO DESPEDIDA M', 684.4),
        ('2026-07-08', 'IMPRESION DESPEDIDA GM', 213.0),
    ),
    # Reporte de jul-2026 (56.88 USD): pizzas + refrescos LP.
    ('2026-08-18', 986.5): (
        ('2026-07-28', 'PIZZAS EVENTO LP', 796.0),
        ('2026-07-28', 'REFRESCOS LP', 190.5),
    ),
    ('2026-09-15', 4174.94): (
        ('2026-05-07', 'JUNTA DEPARTAMENTAL FD MAYO', 1157.0),
        ('2026-05-14', 'DESPEDIDA ASOCIADOS FRONT', 485.0),
        ('2026-06-12', 'REFRESCOS  ACTIVIDAD MUNDIAL', 198.0),
        ('2026-06-23', 'ACTIVIDAD JULIO', 1860.13),
        ('2026-07-09', 'PASTEL CUMPLEAÑO JULIO', 475.0),
    ),
}


def _es(d, clave) -> bool:
    return d['fecha'][:10] == clave[0] and abs(float(d['monto']) - clave[1]) < 0.005


def asignar(depositos: list[dict], gastos: list[dict]) -> dict:
    """depósito id -> (pasada, [gastos de la plataforma])."""
    usados, res = set(), {}
    for clave, gastos_fijos in FIJOS.items():
        d = next((d for d in depositos if _es(d, clave)), None)
        if not d:
            continue
        sel = []
        for f, t, m in gastos_fijos:
            x = next((x for x in gastos if x['fecha'] == f and x['titulo'] == t and abs(x['monto'] - m) < 0.005
                      and x['idx'] not in usados and x['idx'] not in {y['idx'] for y in sel}), None)
            if x:
                sel.append(x)
        if sel:
            usados.update(x['idx'] for x in sel)
            res[d['id']] = ('fijo', sel)
    for clave, titulos in APROXIMADOS.items():
        d = next((d for d in depositos if _es(d, clave)), None)
        sel = [next((x for x in gastos if x['titulo'] == t and x['idx'] not in usados and x['fecha'] <= clave[0]), None)
               for t in titulos]
        if d and d['id'] not in res and all(sel):
            usados.update(x['idx'] for x in sel)
            res[d['id']] = ('aproximado (aceptado)', sel)
    for nombre, dias, fn, tol in PASADAS:
        for d in depositos:
            if d['id'] in res:
                continue
            desde = (date.fromisoformat(d['fecha'][:10]) - timedelta(days=dias)).isoformat()
            cand = [x for x in gastos if x['idx'] not in usados and desde <= x['fecha'] <= d['fecha'][:10]]
            sel = fn(cand, float(d['monto']), tol) if cand else None
            if sel:
                usados.update(x['idx'] for x in sel)
                res[d['id']] = (nombre, sel)
    # Reparación: un depósito sin pareja puede tomar gastos que se quedó otro
    # depósito cercano, si ese otro se puede volver a emparejar con gastos
    # libres (p. ej. un depósito de $561 tomó uno de los dos pasteles de $561
    # que necesitaba el de $2,973.24 del Día de las Madres).
    por_idx = {x['idx']: x for x in gastos}
    for u in depositos:
        if u['id'] in res:
            continue
        ventana_u = {x['idx'] for x in _ventana(u, gastos, set(por_idx), PASADAS[-1][1])}
        for m in depositos:
            if m['id'] not in res or m['id'] == u['id']:
                continue
            _, sel_m = res[m['id']]
            if not {x['idx'] for x in sel_m} & ventana_u:
                continue
            libres = (set(por_idx) - usados) | {x['idx'] for x in sel_m}
            nuevo_u = _emparejar(u, gastos, libres)
            if not nuevo_u:
                continue
            nuevo_m = _emparejar(m, gastos, libres - {x['idx'] for x in nuevo_u[1]})
            if not nuevo_m:
                continue
            usados -= {x['idx'] for x in sel_m}
            usados |= {x['idx'] for x in nuevo_u[1]} | {x['idx'] for x in nuevo_m[1]}
            res[u['id']] = (nuevo_u[0] + ' (reparado)', nuevo_u[1])
            res[m['id']] = (nuevo_m[0], nuevo_m[1])
            break
    return res


def _cargos_libres(db) -> list[dict]:
    """Cargos que pueden ser un gasto de Expense: compras con tarjeta y también
    transferencias BNET/SPEI a un proveedor (FINANZAS/Transferencia…)."""
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, categoria, banco
        FROM est_movimientos
        WHERE tipo IN ('GASTO', 'PAGO') AND categoria NOT IN ('PAGO_TDC', 'PRESTAMOS', 'INVERSION')
          AND NOT (categoria = 'FINANZAS' AND COALESCE(subcategoria, '') NOT IN
                   ('Transferencia', 'Transferencia enviada', ''))
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_gastos)
        ORDER BY CASE WHEN categoria = 'EXPENSE' THEN 0 ELSE 1 END, fecha, id
    """).fetchall()]


def _cargo_de(item, cargos, usados):
    f = date.fromisoformat(item['fecha'])
    desde, hasta = (f - timedelta(days=DIAS_ANTES)).isoformat(), (f + timedelta(days=DIAS_DESPUES)).isoformat()
    candidatos = [c for c in cargos if c['id'] not in usados and desde <= c['fecha'] <= hasta
                  and abs(c['monto'] - item['monto']) <= 0.01]
    # Primero los que ya son EXPENSE (vienen ordenados así) y, entre iguales, el más cercano en fecha.
    candidatos.sort(key=lambda c: (c['categoria'] != 'EXPENSE', abs((date.fromisoformat(c['fecha']) - f).days)))
    return candidatos[0] if candidatos else None


# Depósitos que no pagan gastos de la plataforma (el usuario, 2026-09-28): el
# de $561 del 28/05/2024 se quedaba con uno de los dos pasteles de $561 del
# Día de las Madres que necesita el de $2,973.24 del 20/05/2024 («sí, quita
# ese de 561 para que cuadre»).
# 2026-10-05: el de $561 sí es expense, paga el reporte 12170 (pastel Día de
# las Madres, 33.82 USD); está en FIJOS.
DEPOSITOS_FUERA = ()

# Depósitos que pagaron viáticos, no gastos de la plataforma (el usuario,
# 2026-09-28: «esos mételos como pagado de viáticos»): ninguna combinación de
# gastos del export los forma. El de $512 del 13/09/2024 se suma aquí porque
# el confeti y los globos que lo aproximaban ya los tomó el de $738.70.
VIATICOS = (('2024-06-04', 2414.94), ('2024-07-02', 1561.68), ('2024-08-13', 1815.63),
            ('2024-09-13', 512.00), ('2025-04-30', 4828.01))


def _fuera(d) -> bool:
    return any(_es(d, c) for c in DEPOSITOS_FUERA)


def _viaticos(d) -> bool:
    return any(_es(d, c) for c in VIATICOS)


def liberar_lotes_plataforma(db) -> int:
    """Borra los lotes que creó la conciliación con la plataforma (notas
    «Plataforma de Expense…»; los armados a mano no se tocan) para volver a
    armarlos todos juntos con la asignación corregida. Sus cargos siguen en
    EXPENSE y quedan libres; el depósito queda sin lote hasta reconciliar."""
    lotes = [r[0] for r in db.execute(
        "SELECT id FROM est_expense_lotes WHERE notas LIKE 'Plataforma de Expense%'").fetchall()]
    for lid in lotes:
        gastos = [g[0] for g in db.execute("SELECT movimiento_id FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))]
        db.execute("DELETE FROM est_expense_lote_gastos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lote_depositos WHERE lote_id=?", (lid,))
        db.execute("DELETE FROM est_expense_lotes WHERE id=?", (lid,))
        for gid in gastos:
            db.execute("""UPDATE est_movimientos SET estatus_reembolso=NULL, fecha_reembolso=NULL
                          WHERE id=? AND COALESCE(estatus_reembolso,'') != ?""", (gid, _lotes.ESTATUS_TERCERO))
    return len(lotes)


def _depositos_empresa(db) -> list[dict]:
    """Todos los depósitos de la empresa, estén o no en un lote: la asignación
    se recalcula siempre sobre todos para que los gastos que ya pagó un lote
    no se vuelvan a ofrecer a otro depósito."""
    return [{**dict(r), 'monto': round(float(r['monto']), 2)} for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, banco,
               id IN (SELECT movimiento_id FROM est_expense_lote_depositos) AS en_lote
        FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ('FINANZAS', 'EXPENSE')
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY fecha, id
    """).fetchall() if _lotes._DEP_RE.search(r['descripcion'] or '') and not _fuera(r) and not _viaticos(r)]


def _depositos_viaticos(db) -> list[dict]:
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto FROM est_movimientos
        WHERE tipo = 'INGRESO' AND categoria IN ('FINANZAS', 'EXPENSE')
          AND id NOT IN (SELECT movimiento_id FROM est_expense_lote_depositos)
          AND id NOT IN (SELECT movimiento_id FROM est_prestamo_devoluciones)
        ORDER BY fecha, id
    """).fetchall() if _lotes._DEP_RE.search(r['descripcion'] or '') and _viaticos(r)]


def plan(db) -> list[dict]:
    """Lo que conciliar() haría, sin tocar nada (para revisar)."""
    todos = _depositos_empresa(db)
    asign = asignar(todos, items())
    deps = [d for d in todos if not d['en_lote']]
    cargos, usados, out = _cargos_libres(db), set(), []
    for d in deps:
        if d['id'] not in asign:
            out.append({'deposito': d, 'pasada': None, 'gastos': []})
            continue
        pasada, sel = asign[d['id']]
        gastos = []
        for it in sel:
            c = _cargo_de(it, cargos, usados)
            if c:
                usados.add(c['id'])
            gastos.append({**it, 'cargo': c})
        out.append({'deposito': d, 'pasada': pasada, 'gastos': gastos})
    return out


def asignacion_completa(db) -> dict:
    """Para revisar: cada depósito de la empresa con los gastos de la
    plataforma que le tocan (esté o no en lote) y los gastos que no quedaron
    en ningún depósito."""
    todos = _depositos_empresa(db)
    it = items()
    asign = asignar(todos, it)
    usados = {x['idx'] for _, sel in asign.values() for x in sel}
    return {
        'depositos': [{**d, 'pasada': asign.get(d['id'], (None, []))[0],
                       'gastos': asign.get(d['id'], (None, []))[1]} for d in todos],
        'sin_deposito': [x for x in it if x['idx'] not in usados],
    }


def posibles_cargos(db, item, dias: int = 45) -> list[dict]:
    """Para revisar un gasto «sin cargo»: movimientos del mismo monto (±$0.01)
    a ±dias, de cualquier categoría, y si ya están en un lote."""
    f = date.fromisoformat(item['fecha'])
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, categoria, subcategoria, tipo, banco,
               id IN (SELECT movimiento_id FROM est_expense_lote_gastos) AS en_lote
        FROM est_movimientos
        WHERE ABS(ABS(monto) - ?) <= 0.01 AND substr(fecha,1,10) BETWEEN ? AND ?
        ORDER BY fecha
    """, (item['monto'], (f - timedelta(days=dias)).isoformat(), (f + timedelta(days=dias)).isoformat())).fetchall()]


def conciliar(db) -> list[str]:
    """Crea un lote por depósito emparejado; devuelve un resumen por lote."""
    hechos = []
    for p in plan(db):
        if not p['pasada']:
            continue
        d = p['deposito']
        if d.get('en_lote'):
            continue
        con = [g for g in p['gastos'] if g['cargo']]
        sin = [g for g in p['gastos'] if not g['cargo']]
        notas = f"Plataforma de Expense ({p['pasada']}): {len(p['gastos'])} gastos"
        if sin:
            notas += " · sin cargo en el banco: " + "; ".join(f"{g['fecha']} {g['titulo']} ${g['monto']:,.2f}" for g in sin)
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (f"Expense {d['fecha'][:10]}", notas[:300], _lotes.ahora())).lastrowid
        for g in con:
            db.execute("UPDATE est_movimientos SET categoria='EXPENSE', subcategoria='' WHERE id=?", (g['cargo']['id'],))
            db.execute("INSERT INTO est_expense_lote_gastos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                       (lid, g['cargo']['id'], _lotes.ahora()))
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (d['id'],))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, d['id'], _lotes.ahora()))
        _lotes.sincronizar(db, lid)
        hechos.append(f"{d['fecha'][:10]} ${float(d['monto']):,.2f}: {len(con)} cargos"
                      + (f", {len(sin)} sin cargo" if sin else ""))
    # Los de viáticos quedan en un lote propio sin gastos: así salen de
    # «depósitos sin lote» / «sin conciliar» y el nombre dice qué pagaron.
    for d in _depositos_viaticos(db):
        lid = db.execute("INSERT INTO est_expense_lotes (nombre, notas, created_at) VALUES (?,?,?)",
                         (f"Viáticos {d['fecha']}", "Plataforma de Expense: pagado de viáticos (sin gastos en la plataforma)",
                          _lotes.ahora())).lastrowid
        db.execute("UPDATE est_movimientos SET categoria='FINANZAS', subcategoria='Reembolsable' WHERE id=?", (d['id'],))
        db.execute("INSERT INTO est_expense_lote_depositos (lote_id, movimiento_id, created_at) VALUES (?,?,?)",
                   (lid, d['id'], _lotes.ahora()))
        hechos.append(f"{d['fecha']} ${float(d['monto']):,.2f}: viáticos")
    return hechos
