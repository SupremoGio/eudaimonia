"""
test_finanzas_reconciliar_pdf.py — reconciliar un corte de tarjeta contra su
PDF: descripciones corridas respecto al monto se corrigen conservando la
clasificación del usuario, los duplicados se borran, lo que faltaba (MSI)
se inserta heredando la categoría de su serie; y el dedup del import ya no
descarta una compra de crédito porque ese día hubo algo del mismo monto en
débito.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from modules.finanzas.estados.reconciliar import reconciliar, reconciliar_cortes_bbva_tdc_2026

PER = '2026-07-23 al 2026-08-22'


def _ins(mid, fecha, desc, monto, cat, sub='', tipo='GASTO', banco='BBVA_TDC', **kw):
    with database.get_db() as db:
        db.execute("""INSERT INTO est_movimientos (id, fecha, descripcion, monto, banco, categoria, subcategoria, tipo, parcialidad_num, parcialidad_total)
                      VALUES (?,?,?,?,?,?,?,?,?,?)""", (mid, fecha, desc, monto, banco, cat, sub, tipo, kw.get('pn'), kw.get('pt')))
        db.commit()


def _pdf(fecha, desc, monto, cat='OTROS', sub='', tipo='GASTO', pn=None, pt=None):
    return {'fecha': fecha, 'fecha_cargo': fecha, 'descripcion': desc, 'monto': monto, 'tipo': tipo,
            'categoria': cat, 'subcategoria': sub, 'periodo': PER, 'parcialidad_num': pn, 'parcialidad_total': pt}


def _row(mid):
    with database.get_db() as db:
        r = db.execute("SELECT * FROM est_movimientos WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None


def test_reconcilia_un_corte(test_db):
    # Descripciones corridas: DQ era $614 y Alta Proteína $57 (el usuario marcó ambas EXPENSE)
    _ins(1, '2026-08-14', 'DQ PROVIDENCIA', 57.0, 'EXPENSE')
    _ins(2, '2026-08-14', 'BPK MISC ALTA PRO', 279.95, 'EXPENSE')
    _ins(3, '2026-08-14', '1539 GDL LAS AMER', 110.49, 'EXPENSE')
    _ins(4, '2026-08-01', 'MERPAGO MIGUELOVANDOR', 92.0, 'SUPER')
    _ins(5, '2026-08-02', 'MERPAGO MIGUELOVANDOR', 92.0, 'SUPER')          # duplicado con otra fecha
    _ins(6, '2026-08-11', 'REST QIN MIDTOWN', 26.5, 'COMIDA_FUERA')        # fantasma
    _ins(7, '2026-06-22', '09 DE 12 CRISTAL VILLAHERMO', 1038.0, 'FAMILIA_REGALOS', 'Anillo Cornelius')   # serie previa (fuera del corte)
    _ins(8, '2026-08-05', 'SPEI ENVIADO X', 500.0, 'OTROS', banco='BBVA_DEB')   # otro banco: no se toca
    pdf = [_pdf('2026-08-14', 'DQ PROVIDENCIA', 614.0, 'COMIDA_FUERA'),
           _pdf('2026-08-14', 'BPK MISC ALTA PROTGAMA', 57.0),
           _pdf('2026-08-14', '539 GDL LAS AMERICAS ZAPOPA', 279.95),
           _pdf('2026-08-01', 'MERPAGO MIGUELOVANDOR', 92.0, 'SUPER'),
           _pdf('2026-07-23', 'FRESKO MIDTOWN', 358.0, 'SUPER', 'Súper'),
           _pdf('2026-08-22', 'CRISTAL VILLAHERMOSA', 1038.0, 'FAMILIA_REGALOS', 'Regalos', pn=11, pt=12)]
    with database.get_db() as db:
        plan = reconciliar(db, pdf, 'BBVA_TDC', dry_run=True)
        assert _row(5) is not None                                    # dry run no toca nada
        assert {b['id'] for b in plan['borrados']} == {5, 6}
        plan = reconciliar(db, pdf, 'BBVA_TDC', dry_run=False)
        db.commit()
    assert (_row(1)['monto'], _row(1)['categoria']) == (614.0, 'EXPENSE')      # conserva la clasificación
    assert (_row(2)['descripcion'], _row(2)['monto']) == ('BPK MISC ALTA PROTGAMA', 57.0)
    assert (_row(3)['descripcion'], _row(3)['monto'], _row(3)['categoria']) == ('539 GDL LAS AMERICAS ZAPOPA', 279.95, 'EXPENSE')
    assert _row(5) is None and _row(6) is None and _row(8) is not None
    with database.get_db() as db:
        nuevos = {r['descripcion']: dict(r) for r in db.execute(
            "SELECT * FROM est_movimientos WHERE id IN (%s)" % ','.join('?' * len(plan['nuevos_ids'])), plan['nuevos_ids'])}
    assert set(nuevos) == {'FRESKO MIDTOWN', 'CRISTAL VILLAHERMOSA'}
    assert nuevos['CRISTAL VILLAHERMOSA']['subcategoria'] == 'Anillo Cornelius'      # hereda de su serie
    assert nuevos['CRISTAL VILLAHERMOSA']['parcialidad_num'] == 11
    with database.get_db() as db:
        again = reconciliar(db, pdf, 'BBVA_TDC', dry_run=True)
    assert not again['borrados'] and not again['insertados'] and not again['corregidos']   # idempotente


def test_migracion_no_inserta_en_base_vacia(test_db):
    with database.get_db() as db:
        assert reconciliar_cortes_bbva_tdc_2026(db) == []
        assert db.execute("SELECT COUNT(*) FROM est_movimientos WHERE banco='BBVA_TDC'").fetchone()[0] == 0


def test_dedup_no_descarta_compra_de_credito_por_un_spei_de_debito():
    from modules.finanzas.estados.routes import _desc_parecida
    assert not _desc_parecida('AMAZON MX A MESES', 'SPEI ENVIADO ARCUS FI')
    assert _desc_parecida('PAGO DE NOMINA HH', 'PAGO DE NOMINA / HH 4206466060 FIBRA HOTELERA')
    assert _desc_parecida('SPEI RECIBIDO', 'DEPOSITO')        # sin palabras que distingan: como antes
