"""
test_finanzas_zaira_restaurante.py — ZTL ZAIRAAXZAYMENDOZAM va a
COMIDA_FUERA/Restaurante: el keyword de config.py para imports nuevos, la
migración única para lo ya guardado y el blindaje en «Aplicar reglas».
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados import routes as er
from modules.finanzas.estados.config import get_categoria_subcategoria

RESTAURANTE = ('COMIDA_FUERA', 'Restaurante', 'GASTO')


def _mov(desc, categoria, subcategoria, tipo='GASTO', monto=-180.0):
    with database.get_db() as db:
        rid = db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, tipo, categoria, subcategoria, banco)
                            VALUES ('2026-08-10', ?, ?, ?, ?, ?, 'BBVA_TDC')""",
                         (desc, monto, tipo, categoria, subcategoria)).lastrowid
        db.commit()
        return rid


def _cls(rid):
    with database.get_db() as db:
        r = db.execute("SELECT categoria, subcategoria, tipo FROM est_movimientos WHERE id=?", (rid,)).fetchone()
        return (r['categoria'], r['subcategoria'], r['tipo'])


def test_keyword_para_imports_nuevos():
    assert get_categoria_subcategoria('ZTL ZAIRAAXZAYMENDOZAM') == ('COMIDA_FUERA', 'Restaurante')
    assert get_categoria_subcategoria('ZTL VIVO') == ('VIVIENDA', 'Artículos del hogar')


def test_corrige_todas_y_no_toca_otras(test_db):
    zaira = [
        _mov('ZTL ZAIRAAXZAYMENDOZAM', 'SUPER', 'Súper'),
        _mov('ZTL ZAIRAAXZAYMENDOZAM', 'VIVIENDA', 'Artículos del hogar', monto=-95.5),
        _mov('ztl zairaaxzaymendozam 02', 'OTROS', ''),
    ]
    reembolso = _mov('ZTL ZAIRAAXZAYMENDOZAM', 'FINANZAS', 'Reembolsable', tipo='INGRESO', monto=180.0)
    otro = _mov('ZTL VIVO', 'VIVIENDA', 'Artículos del hogar')
    with database.get_db() as db:
        assert er._corregir_zaira_restaurante(db) == 3
        db.commit()
    assert all(_cls(r) == RESTAURANTE for r in zaira)
    assert _cls(reembolso) == ('FINANZAS', 'Reembolsable', 'INGRESO')
    assert _cls(otro) == ('VIVIENDA', 'Artículos del hogar', 'GASTO')
    with database.get_db() as db:
        assert er._corregir_zaira_restaurante(db) == 0          # idempotente


def test_la_migracion_los_mueve(test_db):
    rid = _mov('ZTL ZAIRAAXZAYMENDOZAM', 'SUPER', 'Súper')
    with database.get_db() as db:
        db.execute("DELETE FROM migration_log WHERE version='finanzas_zaira_restaurante'")
        db.commit()
    database.init_db()
    assert _cls(rid) == RESTAURANTE
