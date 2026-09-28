"""
Retiros de CETESDirecto a la cuenta de débito (capturas de «Instrucciones de
retiro» del usuario, 2026-09-28: «conciliemos estos retiros que he hecho de
CETES para mi cuenta de débito»).

En el banco llegan como «SPEI RECIBIDONAFIN / …» el mismo día o 1-3 días
después. El importe que llega puede ser unos centavos menor que el instruido
(retención de ISR de NAFIN): 11/09/2026 instruido $1,416.66 → llegaron
$1,416.14; 09/09/2026 $5,299.49 → $5,298.71.

Cada instrucción se liga a su depósito, que queda como CETES/RETIRO
(INVERSION): es dinero propio que vuelve, no ingreso.
"""
from datetime import date, timedelta

# (fecha de la instrucción, producto, importe instruido)
RETIROS = (
    ('2026-03-09', 'BONDDIA', 6500.00),
    ('2026-04-08', 'BONDDIA', 700.00),
    ('2026-05-11', 'CETES', 5000.00),
    ('2026-06-08', 'CETES', 10000.00),
    ('2026-06-10', 'CETES', 4109.09),
    ('2026-09-09', 'CETES', 2700.51),
    ('2026-09-09', 'CETES', 5299.49),
    ('2026-09-11', 'CETES', 3083.34),
    ('2026-09-11', 'CETES', 1416.66),
)
DIAS = 3


def _retencion_max(instruido: float) -> float:
    return max(2.0, round(instruido * 0.005, 2))


def _candidatos(db, desde: str, hasta: str) -> list[dict]:
    return [dict(r) for r in db.execute("""
        SELECT id, substr(fecha,1,10) AS fecha, descripcion, ABS(monto) AS monto, categoria, subcategoria, tipo
        FROM est_movimientos
        WHERE substr(fecha,1,10) BETWEEN ? AND ?
          AND (tipo = 'INGRESO' OR (tipo = 'INVERSION' AND categoria = 'CETES' AND subcategoria = 'RETIRO'))
          AND UPPER(descripcion) LIKE '%NAFIN%'
        ORDER BY fecha, id
    """, (desde, hasta)).fetchall()]


def plan(db) -> list[dict]:
    """Cada instrucción con su depósito en el banco (o None). Primero los del
    mismo importe exacto, luego los de unos centavos menos (ISR); entre
    candidatos, el más cercano en fecha. Solo depósitos que digan NAFIN: con
    montos redondos ($5,000, $10,000) una transferencia de otra persona el
    mismo día podría tomarse por el retiro."""
    usados, res = set(), {}
    for exacto in (True, False):
        for i, (f, prod, monto) in enumerate(RETIROS):
            if i in res:
                continue
            d0 = date.fromisoformat(f)
            cands = [c for c in _candidatos(db, f, (d0 + timedelta(days=DIAS)).isoformat())
                     if c['id'] not in usados
                     and (abs(c['monto'] - monto) < 0.005 if exacto
                          else 0 <= monto - c['monto'] <= _retencion_max(monto))]
            cands.sort(key=lambda c: (date.fromisoformat(c['fecha']) - d0).days)
            if cands:
                usados.add(cands[0]['id'])
                res[i] = cands[0]
    return [{'fecha': f, 'producto': prod, 'instruido': monto, 'deposito': res.get(i),
             'retencion': round(monto - res[i]['monto'], 2) if i in res else None}
            for i, (f, prod, monto) in enumerate(RETIROS)]


def conciliar(db) -> dict:
    p = plan(db)
    ligados = [x for x in p if x['deposito']]
    for x in ligados:
        db.execute("UPDATE est_movimientos SET categoria='CETES', subcategoria='RETIRO', tipo='INVERSION' WHERE id=?",
                   (x['deposito']['id'],))
    return {'ligados': len(ligados), 'faltan': [f"{x['fecha']} ${x['instruido']:,.2f}" for x in p if not x['deposito']]}
