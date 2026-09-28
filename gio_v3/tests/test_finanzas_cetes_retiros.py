"""
test_finanzas_cetes_retiros.py — los retiros instruidos en CETESDirecto se
ligan a su «SPEI RECIBIDONAFIN» (mismo importe o unos centavos menos por ISR)
y quedan como CETES/RETIRO, fuera de «Sin conciliar».
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import cetes_retiros as C, abonos
from modules.finanzas.estados.routes import _reaplicar_reglas


def _mov(db, fecha, desc, monto, cat='FINANZAS', sub='Transferencia recibida', tipo='INGRESO'):
    return db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                         VALUES (?,?,?, 'BBVA_DEB', ?,?,?)""", (fecha, desc, monto, cat, sub, tipo)).lastrowid


def test_retiros_ligados_con_retencion(test_db):
    with database.get_db() as db:
        a = _mov(db, '2026-09-09', 'SPEI RECIBIDONAFIN / 0114022434 135 9401446EGRESO', 2700.51)
        b = _mov(db, '2026-09-09', 'SPEI RECIBIDONAFIN / 0114021774 135 9401444EGRESO', 5298.71)
        c = _mov(db, '2026-09-11', 'SPEI RECIBIDONAFIN / 0127122779 135 0613239EGRESO', 3083.34)
        d = _mov(db, '2026-09-11', 'SPEI RECIBIDONAFIN / 0127122778 135 0613237EGRESO', 1416.14)
        otro = _mov(db, '2026-06-09', 'SPEI RECIBIDOBANORTE / 1', 10000.0)
        db.commit()
        p = {(x['fecha'], x['instruido']): x for x in C.plan(db)}
        assert p[('2026-09-09', 5299.49)]['deposito']['id'] == b and p[('2026-09-09', 5299.49)]['retencion'] == 0.78
        assert p[('2026-09-11', 1416.66)]['deposito']['id'] == d
        assert p[('2026-06-08', 10000.0)]['deposito'] is None          # sin NAFIN no se toma
        _reaplicar_reglas(db); db.commit()
        cats = {r[0]: (r[1], r[2], r[3]) for r in db.execute("SELECT id, categoria, subcategoria, tipo FROM est_movimientos")}
        assert all(cats[i] == ('CETES', 'RETIRO', 'INVERSION') for i in (a, b, c, d)) and cats[otro][0] == 'FINANZAS'
        assert not {a, b, c, d} & {m['id'] for m in abonos.sin_conciliar(db)['movimientos']}


def test_spei_enviado_nafin_es_aportacion(test_db):
    with database.get_db() as db:
        e = _mov(db, '2026-02-01', 'SPEI ENVIADO NAFIN / 0001', 3000.0, 'FINANZAS', 'Transferencia enviada', 'GASTO')
        _reaplicar_reglas(db); db.commit()
        assert tuple(db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (e,)).fetchone()) == \
            ('CETES', 'APORTACION', 'INVERSION')
