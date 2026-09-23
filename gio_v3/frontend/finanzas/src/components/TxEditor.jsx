import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { todayISO } from '../lib/format.js';
import { BANKS, catMeta } from '../lib/meta.js';
import { categoryKeys, getCategories, getTrips, subcatsFor } from '../lib/store.js';
import { Field, Icon, Kbd, Modal, confirmDialog, saveKey, toast } from './ui.jsx';

const TIPOS_EDIT = [['GASTO', 'Gasto'], ['INGRESO', 'Ingreso'], ['PAGO', 'Pago']];

function initial(tx) {
  if (!tx) {
    return {
      tipo: 'GASTO', descripcion: '', monto: '', categoria: 'OTROS', subcategoria: '', banco: 'MANUAL',
      fecha: todayISO(), mi_parte: '', viaje_id: '', reembolso_cat: '', estatus_reembolso: '', fecha_reembolso: '',
    };
  }
  return {
    tipo: tx.tipo,
    descripcion: tx.descripcion || '',
    monto: String(Math.abs(tx.monto ?? '')),
    categoria: tx.categoria || 'OTROS',
    subcategoria: tx.subcategoria || '',
    banco: tx.banco || 'MANUAL',
    fecha: (tx.fecha || '').slice(0, 10),
    mi_parte: tx.mi_parte != null ? String(tx.mi_parte) : '',
    viaje_id: tx.viaje_id != null ? String(tx.viaje_id) : '',
    reembolso_cat: tx.reembolso_cat || '',
    estatus_reembolso: tx.estatus_reembolso || '',
    fecha_reembolso: tx.fecha_reembolso || '',
  };
}

/** Editor completo de un movimiento (o alta de uno nuevo si no hay `tx`). */
export default function TxEditor({ tx, onClose, onSaved }) {
  const isNew = !tx;
  const [f, setF] = useState(() => initial(tx));
  const [cats, setCats] = useState([]);
  const [trips, setTrips] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [dup, setDup] = useState(false);

  useEffect(() => { getCategories().then(setCats).catch(() => {}); getTrips().then(setTrips); }, []);

  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  // Cambiar de categoría limpia la subcategoría: la anterior casi nunca
  // existe en la nueva (antes se quedaba escrita, p. ej. «Transferencia
  // enviada» al pasar de FINANZAS a VIVIENDA).
  const setCategoria = (v) => setF((s) => (s.categoria === v ? s : { ...s, categoria: v, subcategoria: '' }));

  const subs = subcatsFor(cats, f.categoria, f.tipo);
  const keys = categoryKeys(cats, f.categoria);
  const idp = isNew ? 'fz-n' : 'fz-e';

  async function save(force = false) {
    if (busy) return;
    if (!f.descripcion.trim() || !f.monto || Number.isNaN(parseFloat(f.monto))) {
      setErr('Descripción y monto son obligatorios.');
      return;
    }
    setBusy(true); setErr(''); setDup(false);
    try {
      if (isNew) {
        await api.post('/transactions', {
          tipo: f.tipo, descripcion: f.descripcion.trim(), monto: parseFloat(f.monto), categoria: f.categoria,
          subcategoria: f.subcategoria, banco: f.banco, fecha: f.fecha, ...(force ? { force: true } : {}),
        });
        toast('Movimiento agregado', 'ok');
      } else {
        await api.patch(`/transactions/${tx.id}`, { ...f, descripcion: f.descripcion.trim(), monto: parseFloat(f.monto) });
        toast('Movimiento actualizado', 'ok');
      }
      onSaved && onSaved();
      onClose();
    } catch (e) {
      setErr(e.message || 'Error al guardar.');
      setDup(!!(e.data && e.data.possible_duplicate));
      setBusy(false);
    }
  }

  async function remove() {
    const ok = await confirmDialog('¿Eliminar este movimiento? No se puede deshacer.', { confirmLabel: 'Eliminar', danger: true });
    if (!ok) return;
    setBusy(true);
    try {
      await api.del(`/transactions/${tx.id}`);
      toast('Movimiento eliminado', 'ok');
      onSaved && onSaved();
      onClose();
    } catch (e) { setErr(e.message || 'Error al eliminar.'); setBusy(false); }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
  };

  return (
    <Modal title={isNew ? 'Nuevo movimiento' : 'Editar movimiento'} eyebrow={isNew ? 'Captura manual' : catMeta(tx.categoria).name} onClose={onClose}
      footer={(
        <>
          {!isNew && <button type="button" className="eu-btn eu-btn--danger fz-ft-start" onClick={remove} disabled={busy}><Icon name="trash-2" />Eliminar</button>}
          <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
          <button type="submit" form={`${idp}-form`} className="eu-btn eu-btn--primary" disabled={busy} aria-busy={busy || undefined}>
            {isNew ? 'Agregar' : 'Guardar'} <Kbd>{saveKey}</Kbd>
          </button>
        </>
      )}>
      <form id={`${idp}-form`} className="eu-modal-bd" onSubmit={(e) => { e.preventDefault(); save(); }} onKeyDown={onKeyDown} noValidate>
        <div className="eu-seg fz-seg-block" role="radiogroup" aria-label="Tipo de movimiento">
          {TIPOS_EDIT.map(([id, name]) => (
            <button key={id} type="button" role="radio" aria-checked={f.tipo === id} onClick={() => set('tipo', id)}>{name}</button>
          ))}
        </div>
        {!isNew && !TIPOS_EDIT.some(([id]) => id === f.tipo) && <div className="t-meta">Tipo actual: {f.tipo}</div>}

        <Field label="Descripción" htmlFor={`${idp}-desc`}>
          <input id={`${idp}-desc`} className="eu-input" value={f.descripcion} maxLength={300} onChange={(e) => set('descripcion', e.target.value)} placeholder="Ej. OXXO Insurgentes" />
        </Field>
        <div className="eu-grid-2">
          <Field label="Monto (MXN)" htmlFor={`${idp}-monto`}>
            <input id={`${idp}-monto`} className="eu-input eu-input--money" inputMode="decimal" type="number" step="0.01" min="0" value={f.monto} onChange={(e) => set('monto', e.target.value)} placeholder="0.00" />
          </Field>
          <Field label="Fecha" htmlFor={`${idp}-fecha`}>
            <input id={`${idp}-fecha`} className="eu-input" type="date" value={f.fecha} onChange={(e) => set('fecha', e.target.value)} />
          </Field>
        </div>
        <div className="eu-grid-2">
          <Field label="Categoría" htmlFor={`${idp}-cat`}>
            <select id={`${idp}-cat`} className="eu-select" value={f.categoria} onChange={(e) => setCategoria(e.target.value)}>
              {keys.map((k) => <option key={k} value={k}>{catMeta(k).name}</option>)}
            </select>
          </Field>
          <Field label="Banco" htmlFor={`${idp}-banco`}>
            <select id={`${idp}-banco`} className="eu-select" value={f.banco} onChange={(e) => set('banco', e.target.value)}>
              {BANKS.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              {!BANKS.some((b) => b.id === f.banco) && <option value={f.banco}>{f.banco}</option>}
            </select>
          </Field>
        </div>
        {f.categoria !== 'EXPENSE' && (
          <Field label="Subcategoría (opcional)" htmlFor={`${idp}-sub`}>
            <select id={`${idp}-sub`} className="eu-select" value={f.subcategoria} onChange={(e) => set('subcategoria', e.target.value)}>
              <option value="">— Sin subcategoría —</option>
              {subs.map((s) => <option key={s} value={s}>{s}</option>)}
              {f.subcategoria && !subs.includes(f.subcategoria) && <option value={f.subcategoria}>{f.subcategoria}</option>}
            </select>
          </Field>
        )}

        {!isNew && f.tipo === 'GASTO' && (
          <div className="eu-grid-2">
            <Field label="Mi parte (opcional)" htmlFor={`${idp}-parte`}
              help="Si alguien más pagó o te reembolsó parte, pon solo lo que te corresponde. Vacío = 100 % tuyo.">
              <input id={`${idp}-parte`} className="eu-input eu-input--money" type="number" step="0.01" min="0" inputMode="decimal" value={f.mi_parte} onChange={(e) => set('mi_parte', e.target.value)} placeholder="Ej. 600" />
            </Field>
            <Field label="Viaje (opcional)" htmlFor={`${idp}-viaje`}>
              <select id={`${idp}-viaje`} className="eu-select" value={f.viaje_id} onChange={(e) => set('viaje_id', e.target.value)}>
                <option value="">Sin viaje</option>
                {trips.map((t) => <option key={t.id} value={String(t.id)}>{t.nombre || t.name || `Viaje ${t.id}`}</option>)}
              </select>
            </Field>
          </div>
        )}

        {!isNew && f.categoria === 'EXPENSE' && (
          <fieldset className="fz-fieldset">
            <legend className="t-eyebrow">Reembolso</legend>
            <Field label="Categoría del gasto reembolsable" htmlFor={`${idp}-rcat`}>
              <input id={`${idp}-rcat`} className="eu-input" value={f.reembolso_cat} onChange={(e) => set('reembolso_cat', e.target.value)} placeholder="Ej. Viaje cliente X" />
            </Field>
            <div className="eu-grid-2">
              <Field label="Estatus" htmlFor={`${idp}-rest`}>
                <select id={`${idp}-rest`} className="eu-select" value={f.estatus_reembolso} onChange={(e) => set('estatus_reembolso', e.target.value)}>
                  <option value="">—</option>
                  <option value="PENDIENTE">Pendiente</option>
                  <option value="PAGADO">Pagado</option>
                </select>
              </Field>
              <Field label="Fecha de reembolso" htmlFor={`${idp}-rfecha`}>
                <input id={`${idp}-rfecha`} className="eu-input" type="date" value={f.fecha_reembolso} onChange={(e) => set('fecha_reembolso', e.target.value)} />
              </Field>
            </div>
          </fieldset>
        )}

        {err && (
          <div className="fz-note" data-tone="danger" role="alert">
            <Icon name="circle-alert" size={16} />
            <span className="eu-grow">{err}</span>
            {dup && isNew && <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => save(true)}>Guardar de todos modos</button>}
          </div>
        )}
      </form>
    </Modal>
  );
}
