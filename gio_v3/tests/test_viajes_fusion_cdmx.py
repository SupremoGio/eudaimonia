"""
test_viajes_fusion_cdmx.py — «FUSION CASINO CDMX» era un duplicado de «Salsa
Fusion CDMX - Mayo 2026»: se fusionan en uno solo del 28 al 31 de mayo.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def test_fusiona_viajes_duplicados(test_db):
    with database.get_db() as db:
        ins = lambda n, a, b: db.execute("""INSERT INTO viajes (nombre, destino, fecha_inicio, fecha_fin, estado, created_at)
                                            VALUES (?, 'CDMX', ?, ?, 'planificado', 'x')""", (n, a, b)).lastrowid
        # El viaje ya lo crea una migración de arranque (sprint 2 de finanzas).
        row = db.execute("SELECT id FROM viajes WHERE nombre='Salsa Fusion CDMX - Mayo 2026'").fetchone()
        keep = row['id'] if row else ins('Salsa Fusion CDMX - Mayo 2026', '2026-05-24', '2026-05-31')
        dup = ins('FUSION CASINO CDMX', '2026-05-28', '2026-05-31')
        for d in ('2026-05-24', '2026-05-25', '2026-05-28'):
            db.execute("INSERT INTO viaje_dias (viaje_id, fecha, descripcion) VALUES (?,?,'x')", (keep, d))
        db.execute("INSERT INTO viaje_dias (viaje_id, fecha, descripcion) VALUES (?, '2026-05-29', 'x')", (dup,))
        m1 = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo, viaje_id)
                           VALUES ('2026-05-24', 'BOLETO', 900, 'BBVA_TDC', 'SALSA', 'GASTO', ?)""", (keep,)).lastrowid
        m2 = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, tipo, viaje_id)
                           VALUES ('2026-05-29', 'UBER', 120, 'BBVA_TDC', 'TRANSPORTE', 'GASTO', ?)""", (dup,)).lastrowid
        db.execute("DELETE FROM migration_log WHERE version='viajes_fusion_cdmx_mayo_2026'")
        db.commit()
    database.init_db()
    with database.get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM viajes WHERE id=?", (dup,)).fetchone()[0] == 0
        v = db.execute("SELECT fecha_inicio, fecha_fin FROM viajes WHERE id=?", (keep,)).fetchone()
        assert (v['fecha_inicio'], v['fecha_fin']) == ('2026-05-28', '2026-05-31')
        assert {r[0] for r in db.execute("SELECT viaje_id FROM est_movimientos WHERE id IN (?,?)", (m1, m2))} == {keep}
        assert [r[0] for r in db.execute("SELECT fecha FROM viaje_dias WHERE viaje_id=? ORDER BY fecha", (keep,))] == \
            ['2026-05-28', '2026-05-29', '2026-05-30', '2026-05-31']
        assert db.execute("SELECT COUNT(*) FROM viaje_dias WHERE viaje_id=?", (dup,)).fetchone()[0] == 0
