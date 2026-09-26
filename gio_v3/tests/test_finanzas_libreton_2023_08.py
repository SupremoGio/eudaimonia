"""
test_finanzas_libreton_2023_08.py — carga manual del Libretón BBVA Débito
07/08-06/09/2023 (PDF solo imagen): cuadra con el resumen del banco, no
duplica filas que ya existan y es idempotente.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import libreton_2023_08 as lib


def test_cuadra_con_el_resumen_del_banco():
    cargos = [m for m in lib.MOVIMIENTOS if m[6] == 'GASTO' or (m[6] == 'INVERSION' and 'APORTACION' == m[5])]
    abonos = [m for m in lib.MOVIMIENTOS if m not in cargos]
    assert len(cargos) == 17 and round(sum(m[3] for m in cargos), 2) == 36045.62
    assert len(abonos) == 8 and round(sum(m[3] for m in abonos), 2) == 32968.23
    assert round(8780.97 + sum(m[3] for m in abonos) - sum(m[3] for m in cargos), 2) == 5703.58


def test_inserta_sin_duplicar(test_db):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                      VALUES ('2023-08-15', 'PAGO DE NOMINA', 7604.56, 'BBVA_DEB', 'NOMINA', 'Pago nominal', 'INGRESO')""")
        db.commit()
        ins, ya = lib.aplicar(db)
        db.commit()
        assert (ins, ya) == (24, 1)
        assert lib.aplicar(db) == (0, 25)
        rows = db.execute("""SELECT * FROM est_movimientos WHERE banco='BBVA_DEB'
                             AND fecha BETWEEN '2023-08-07' AND '2023-09-06'""").fetchall()
        assert len(rows) == 25
        didi = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE 'DLOCAL*DIDI%'").fetchone()
        assert (didi['categoria'], didi['subcategoria']) == ('COMIDA_FUERA', 'Delivery')
        exp = db.execute("SELECT * FROM est_movimientos WHERE descripcion LIKE '%EXPENSE BOTANAS'").fetchone()
        assert exp['categoria'] == 'EXPENSE' and exp['tipo'] == 'GASTO'


def test_auditoria_omite_tramos_confirmados_vacios(test_db):
    from modules.finanzas.estados.routes import _auditar_banco
    with database.get_db() as db:
        for f, per in (('2026-05-07', '2026-05-07 al 2026-05-29'), ('2026-05-29', '2026-05-07 al 2026-05-29'),
                       ('2026-06-02', '2026-06-02 al 2026-06-20'), ('2026-06-20', '2026-06-02 al 2026-06-20')):
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, tipo)
                          VALUES (?, ?, 1, 'BBVA_DEB', ?, 'OTROS', 'GASTO')""", (f, 'X' + f, per))
            db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, periodo, categoria, tipo)
                          VALUES (?, ?, 1, 'HSBC', ?, 'OTROS', 'GASTO')""", (f, 'H' + f, per))
        db.commit()
        assert _auditar_banco(db, 'BBVA_DEB', '2026-06-20', 25)['huecos_entre_periodos'] == []
        assert len(_auditar_banco(db, 'HSBC', '2026-06-20', 25)['huecos_entre_periodos']) == 1   # solo BBVA_DEB se verificó
