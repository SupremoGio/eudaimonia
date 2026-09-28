"""
test_finanzas_expense_plataforma.py — conciliación de Expense con el export de
la plataforma: cada depósito de la empresa toma los gastos de la plataforma
que lo suman (FIFO primero) y se crea su lote con los cargos del banco.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import expense_plataforma as P, expense_lotes as E


def _mov(db, fecha, desc, monto, cat, sub='', tipo='GASTO'):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (?,?,?, 'BBVA_TDC', ?,?,?)""", (fecha, desc, monto, cat, sub, tipo)).lastrowid


def test_datos_de_la_plataforma():
    it = P.items()
    assert len(it) == 176 and round(sum(x['monto'] for x in it), 2) == 194325.27


def test_conciliar_crea_lotes(test_db, monkeypatch):
    gastos = [{'fecha': '2024-11-29', 'titulo': 'Decoracion Navidad', 'tipo': '', 'monto': 1047.0},
              {'fecha': '2024-11-29', 'titulo': 'REGALOS POSADA', 'tipo': '', 'monto': 4895.0},
              {'fecha': '2024-11-29', 'titulo': 'SNACK', 'tipo': '', 'monto': 196.0},
              {'fecha': '2024-12-05', 'titulo': 'pastel dic', 'tipo': '', 'monto': 395.0},
              {'fecha': '2024-12-11', 'titulo': 'pastel dic', 'tipo': '', 'monto': 320.0}]
    monkeypatch.setattr(P, 'items', lambda: [{**x, 'idx': i} for i, x in enumerate(gastos)])
    with database.get_db() as db:
        c1 = _mov(db, '2024-11-30', 'LIVERPOOL', 1047.0, 'VIVIENDA', 'Artículos del hogar')   # cargo 1 día después
        c2 = _mov(db, '2024-11-29', 'SAMS', 4895.0, 'EXPENSE')
        otro = _mov(db, '2024-11-29', 'SAMS PERSONAL', 4895.0, 'SUPER', 'Súper')             # mismo monto: no se usa
        c4 = _mov(db, '2024-12-06', 'PASTELERIA', 395.0, 'CAFE/PAN', 'Pan')
        c5 = _mov(db, '2024-12-12', 'PASTELERIA', 320.0, 'CAFE/PAN', 'Pan')
        d1 = _mov(db, '2024-12-06', 'SITH20000001490 FIDEICOMISO F 1596', 6138.0, 'FINANZAS', 'Fideicomiso', 'INGRESO')
        d2 = _mov(db, '2024-12-20', 'SITH20000001541 FIDEICOMISO F 1596', 715.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        hechos = P.conciliar(db)
        db.commit()
        assert len(hechos) == 2
        lotes = {l['depositos'][0]['id']: l for l in E.listar(db)}
        assert {g['id'] for g in lotes[d1]['gastos']} == {c1, c2}          # el SNACK de $196 no tiene cargo
        assert 'sin cargo en el banco' in lotes[d1]['notas'] and 'SNACK' in lotes[d1]['notas']
        assert {g['id'] for g in lotes[d2]['gastos']} == {c4, c5} and lotes[d2]['estado'] == 'Reembolsado'
        cat = lambda i: db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (i,)).fetchone()[0]
        assert cat(c1) == cat(c4) == 'EXPENSE' and cat(otro) == 'SUPER'
        assert P.conciliar(db) == []                                    # idempotente
