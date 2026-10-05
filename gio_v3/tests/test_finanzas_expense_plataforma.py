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


def test_no_reofrece_gastos_ya_pagados_y_cargo_antes_o_transferencia(test_db, monkeypatch):
    gastos = [{'fecha': '2025-01-08', 'titulo': 'PASTEL ENERO', 'tipo': '', 'monto': 420.0},
              {'fecha': '2025-01-06', 'titulo': 'BOTANA', 'tipo': '', 'monto': 222.0},
              {'fecha': '2025-03-20', 'titulo': 'CAPACITACION', 'tipo': '', 'monto': 441.3}]
    monkeypatch.setattr(P, 'items', lambda: [{**x, 'idx': i} for i, x in enumerate(sorted(gastos, key=lambda g: g['fecha']))])
    with database.get_db() as db:
        d1 = _mov(db, '2025-01-22', 'SITH20000001608 FIDEICOMISO F 1596', 642.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        P.conciliar(db); db.commit()                      # primera pasada: lote de d1
        c_antes = _mov(db, '2025-03-15', 'PAGO CUENTA DE TERCERO BNET CAPACITACION', 441.3, 'FINANZAS', 'Transferencia')
        d2 = _mov(db, '2025-04-09', 'SITH20000001908 FIDEICOMISO F 1596', 441.3, 'FINANZAS', 'Reembolsable', 'INGRESO')
        d3 = _mov(db, '2025-04-30', 'SITH20000002002 FIDEICOMISO F 1596', 642.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        P.conciliar(db); db.commit()
        lotes = {l['depositos'][0]['id']: l for l in E.listar(db)}
        assert d3 not in lotes                           # los gastos de $642 ya los pagó d1
        assert [g['id'] for g in lotes[d2]['gastos']] == [c_antes]   # transferencia 5 días antes del recibo


def test_reparacion_toma_gastos_de_otro_deposito_si_este_se_reempareja():
    """U solo cuadra con el gasto de $300 que tomó M; M también cuadra con otro de $300 libre."""
    g = [{'idx': 0, 'fecha': '2024-01-05', 'titulo': 'A', 'monto': 300.0},
         {'idx': 1, 'fecha': '2024-01-06', 'titulo': 'B', 'monto': 200.0},
         {'idx': 2, 'fecha': '2024-02-20', 'titulo': 'C', 'monto': 300.0}]
    m = {'id': 1, 'fecha': '2024-03-01', 'monto': 300.0}      # «mismo monto»: toma A (el primero)
    u = {'id': 2, 'fecha': '2024-01-20', 'monto': 500.0}      # necesita A + B (C es posterior a su fecha)
    res = P.asignar([u, m], g)
    assert {x['idx'] for x in res[2][1]} == {0, 1} and [x['idx'] for x in res[1][1]] == [2]


def test_deposito_561_fuera_y_rearmado(test_db, monkeypatch):
    gastos = [{'fecha': '2024-05-15', 'titulo': 'PASTEL DIA DE LAS MADRES', 'tipo': '', 'monto': 561.0},
              {'fecha': '2024-05-15', 'titulo': 'PASTEL DIA MADRE', 'tipo': '', 'monto': 561.0}]
    monkeypatch.setattr(P, 'items', lambda: [{**x, 'idx': i} for i, x in enumerate(gastos)])
    with database.get_db() as db:
        c = _mov(db, '2024-05-15', 'PASTELERIA', 561.0, 'CAFE/PAN', 'Pan')
        d561 = _mov(db, '2024-05-28', 'SITH2 FIDEICOMISO F 1596', 561.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        d2 = _mov(db, '2024-05-20', 'DEPOSITO DE TERCERO EXPENSE GIO BMRCASH', 1122.0, 'FINANZAS', 'Reembolsable', 'INGRESO')
        db.commit()
        monkeypatch.setattr(P, 'DEPOSITOS_FUERA', ())
        P.conciliar(db); db.commit()                      # como en producción: el de $561 tomó un pastel
        monkeypatch.setattr(P, 'DEPOSITOS_FUERA', (('2024-05-28', 561.0),))
        assert P.liberar_lotes_plataforma(db) >= 1
        P.conciliar(db); db.commit()
        lotes = {l['depositos'][0]['id']: l for l in E.listar(db)}
        assert d561 not in lotes and [g['id'] for g in lotes[d2]['gastos']] == [c]


def test_exacto_al_centavo_gana_a_redondeo():
    """El de $4,365.55 cuadra al centavo con 6 gastos; el de $2,215.60 (antes)
    no debe quitárselos con una combinación que solo cuadra redondeando."""
    g = [{'idx': i, 'fecha': f, 'titulo': t, 'monto': m} for i, (f, t, m) in enumerate((
        ('2024-10-18', 'DESPENSA', 1904.40), ('2024-10-18', 'pastel cocina', 415.0), ('2024-10-18', 'PASTEL OCT', 740.0),
        ('2024-10-22', 'DIA DEL CHEF', 415.0), ('2024-10-22', 'REFRESCO', 160.14), ('2024-10-25', 'pastel act', 427.0),
        ('2024-10-30', 'pan de muerto', 138.85), ('2024-10-31', 'PAPELERIA', 335.0), ('2024-11-06', 'Corona', 1044.0)))]
    a = {'id': 1, 'fecha': '2024-11-01', 'monto': 2215.60}
    b = {'id': 2, 'fecha': '2024-11-15', 'monto': 4365.55}
    res = P.asignar([a, b], g)
    assert round(sum(x['monto'] for x in res[2][1]), 2) == 4365.54
    assert {x['titulo'] for x in res[2][1]} == {'DESPENSA', 'pastel cocina', 'DIA DEL CHEF', 'REFRESCO', 'pastel act', 'Corona'}


def test_aproximado_aceptado_y_viaticos(test_db, monkeypatch):
    """738.70 toma confeti + globos + pastel agosto (aceptado por el usuario);
    los de viáticos quedan en un lote propio sin gastos y fuera de sin-lote."""
    gastos = [{'fecha': '2024-06-05', 'titulo': 'CONFETI AC ANIVERSARIO', 'tipo': '', 'monto': 100.02},
              {'fecha': '2024-06-05', 'titulo': 'GLOBOS AC ANIVERSARIO', 'tipo': '', 'monto': 134.66},
              {'fecha': '2024-08-16', 'titulo': 'pastel agosto', 'tipo': '', 'monto': 533.0}]
    monkeypatch.setattr(P, 'items', lambda: [{**x, 'idx': i} for i, x in enumerate(gastos)])
    with database.get_db() as db:
        c = _mov(db, '2024-08-17', 'PASTELERIA', 533.0, 'CAFE/PAN', 'Pan')
        d = _mov(db, '2024-08-30', 'SITH20000001188 FIDEICOMISO F 1596', 738.70, 'FINANZAS', 'Fideicomiso', 'INGRESO')
        v1 = _mov(db, '2024-08-13', 'SITH20000001150 FIDEICOMISO F 1596', 1815.63, 'FINANZAS', 'Fideicomiso', 'INGRESO')
        v2 = _mov(db, '2024-09-13', 'SITH20000001239 FIDEICOMISO F 1596', 512.00, 'FINANZAS', 'Fideicomiso', 'INGRESO')
        db.commit()
        P.conciliar(db); db.commit()
        lotes = {l['depositos'][0]['id']: l for l in E.listar(db)}
        assert [g['id'] for g in lotes[d]['gastos']] == [c] and 'aproximado' in lotes[d]['notas']
        assert lotes[v1]['nombre'] == 'Viáticos 2024-08-13' and lotes[v2]['gastos'] == []
        assert not {v1, v2, d} & {x['id'] for x in E._depositos_sin_lote(db)}
        assert P.liberar_lotes_plataforma(db) == 3 and len(P.conciliar(db)) == 3   # se rearman igual
