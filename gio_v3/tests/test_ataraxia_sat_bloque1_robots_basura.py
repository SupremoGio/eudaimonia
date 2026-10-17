"""Bloque 1 del sábado (Mantenimiento & Recepción): robot aspiradora sala y
cuarto + vaciar botes de basura (usuario, 2026-10-10)."""
import database


def test_bloque1_trae_robots_y_basura(test_db):
    with database.get_db() as db:
        rows = {r['id']: r['nombre'] for r in db.execute(
            "SELECT id, nombre FROM rutina_bloques WHERE dia='sabado' AND bloque_id='sat_bloque1'")}
    assert rows['sat_robot_sala'] == 'Pasar robot aspiradora (sala)'
    assert rows['sat_robot_cuarto'] == 'Pasar robot aspiradora (cuarto)'
    assert rows['sat_basura'] == 'Vaciar botes de basura'
    assert len(rows) == 8


def test_migracion_repone_robots_si_faltan(test_db):
    """El caso de producción: la migración vieja quedó registrada pero sin las filas."""
    with database.get_db() as db:
        db.execute("DELETE FROM rutina_bloques WHERE id IN ('sat_robot_sala','sat_robot_cuarto','sat_basura')")
        db.execute("DELETE FROM migration_log WHERE version='sat_bloque1_robots_y_basura'")
        db.commit()
    database.init_db()
    database.init_db()                                   # idempotente
    with database.get_db() as db:
        n = db.execute("SELECT COUNT(*) FROM rutina_bloques WHERE id IN "
                       "('sat_robot_sala','sat_robot_cuarto','sat_basura')").fetchone()[0]
    assert n == 3
