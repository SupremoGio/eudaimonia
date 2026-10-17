"""
test_finanzas_coach.py — paquete «Descargar para el coach»: un Markdown con
el prompt y el resumen de finanzas, que nunca falla aunque la base esté vacía.
"""
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas import coach


def _ins(db, fecha, desc, monto, tipo, cat, sub=''):
    db.execute("""INSERT INTO est_movimientos (fecha, descripcion, monto, banco, categoria, subcategoria, tipo)
                  VALUES (?,?,?, 'BBVA_DEB', ?, ?, ?)""", (fecha, desc, monto, cat, sub, tipo))


def test_base_vacia_no_falla(test_db):
    with database.get_db() as db:
        md = coach.generar(db, date(2026, 10, 1))
    assert md.startswith('# Coach financiero personal')
    assert 'No se pudo calcular' not in md


def test_resumen_con_datos(test_db):
    with database.get_db() as db:
        for mes in ('2026-07', '2026-08', '2026-09'):
            _ins(db, f'{mes}-15', 'NOMINA EMPRESA', -30000, 'INGRESO', 'NOMINA', 'Sueldo')
            _ins(db, f'{mes}-05', 'SUPER CHEDRAUI', 4000, 'GASTO', 'SUPER', 'Súper')
            _ins(db, f'{mes}-10', 'NETFLIX', 299, 'GASTO', 'DIGITAL', 'Suscripciones entretenimiento')
        db.execute("""INSERT INTO est_prestamos (contraparte, direccion, monto, fecha, notas, created_at)
                      VALUES ('Jorge', 'OTORGADO', 10000, '2026-08-01', '', datetime('now'))""")
        db.commit()
        md = coach.generar(db, date(2026, 10, 1))
    assert 'No se pudo calcular' not in md
    assert 'sep 2026' in md and 'SUPER CHEDRAUI' in md and 'NETFLIX' in md
    assert '| Jorge | $10,000 |' in md


def test_pagina_y_descarga(test_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["app_ok"] = True
        assert c.get('/finanzas/coach/').status_code == 302          # sin PIN de finanzas
        with c.session_transaction() as sess:
            sess["fin_ok"] = True
        assert 'Descargar para el coach' in c.get('/finanzas/coach/').get_data(as_text=True)
        r = c.get('/finanzas/coach/descargar')
        assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
        assert r.get_data(as_text=True).startswith('# Coach financiero personal')
