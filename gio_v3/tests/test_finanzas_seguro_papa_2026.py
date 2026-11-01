"""
test_finanzas_seguro_papa_2026.py — la deuda del seguro del carro con Papá
queda como en la hoja del usuario: $13,865 cubiertos, $12,199 pagados, debe
$1,666; los $5,000 del 08/may dejan de contar como regalo (ingreso).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import correcciones_seguro_papa_2026 as C
from modules.finanzas.estados import prestamos as P


def test_deuda_seguro_papa(test_db):
    with database.get_db() as db:
        regalo = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                               VALUES ('2026-05-08', 'PAGO CUENTA DE TERCERO BNET PRE', 5000, 'BBVA_DEB', 'OTROS', '', 'INGRESO')""").lastrowid
        r = C.aplicar(db)
        db.commit()
        assert r == {'creado': 1, 'ajustado': 0, 'abonos': 10, 'regalo_a_deuda': 1}
        r2 = C.aplicar(db)                                    # otra vez: ajusta el mismo, no duplica
        assert r2['creado'] == 0 and r2['ajustado'] == 1
        debo = [p for p in P.listar(db, 'RECIBIDO') if p['concepto'] == C.CONCEPTO]
        assert len(debo) == 1
        assert debo[0]['monto'] == 13865.0 and debo[0]['pendiente'] == 1666.0
        assert db.execute("SELECT categoria FROM est_movimientos WHERE id=?", (regalo,)).fetchone()[0] == 'PRESTAMOS'
