"""
test_finanzas_retiros_renta_2023.py — los 6 retiros sin tarjeta de 2023 que el
usuario señaló (renta pagada en efectivo) van a VIVIENDA/Renta; ningún otro
retiro se toca y «Aplicar reglas» no los regresa.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import routes as er


def _mov(fecha, desc, monto, tipo='GASTO'):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco)
                            VALUES (?,?,?,?, 'FINANZAS', 'Retiro efectivo', 'BBVA')""", (fecha, desc, monto, tipo)).lastrowid
        db.commit()
        return rid


def _cat(rid):
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria FROM est_movimientos WHERE id=?", (rid,)).fetchone()
        return (r['categoria'], r['subcategoria'])


def test_solo_los_seis_retiros_senalados(test_db):
    renta = [_mov(f, 'RETIRO SIN TARJETA QR' if f == '2023-02-16' else 'RETIRO SIN TARJETA', -m)
             for f, m in er.RETIROS_RENTA_2023]
    otro_dia = _mov('2023-04-19', 'RETIRO SIN TARJETA', -8600)
    otro_monto = _mov('2023-04-18', 'RETIRO SIN TARJETA', -500)
    otra_desc = _mov('2023-05-18', 'SPEI ENVIADO', -8500)
    with database.get_db() as db:
        assert er._corregir_retiros_renta(db) == 6
        db.commit()
    assert all(_cat(r) == ('VIVIENDA', 'Renta') for r in renta)
    assert _cat(otro_dia) == _cat(otro_monto) == _cat(otra_desc) == ('FINANZAS', 'Retiro efectivo')
    with database.get_db() as db:
        assert er._corregir_retiros_renta(db) == 0          # idempotente


def test_la_migracion_los_mueve(test_db):
    rid = _mov('2023-09-16', 'RETIRO SIN TARJETA', -7600)
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_retiros_renta_2023'")
        db.commit()
    database.init_db()
    assert _cat(rid) == ('VIVIENDA', 'Renta')
