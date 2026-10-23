import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { money } from '../lib/format.js';
import { catMeta } from '../lib/meta.js';
import { categoryKeys, subcatsFor } from '../lib/store.js';
import { Icon, confirmDialog, toast } from './ui.jsx';

/**
 * «Dividir en categorías»: un solo cargo del banco que fue de varias cosas
 * (Amazon con desodorante + playera + balón, una transferencia mitad renta y
 * mitad préstamo). El cargo original queda como «Dividido» (no suma) y cada
 * parte cuenta en su categoría. Las partes deben sumar el total del cargo.
 * Ver modules/finanzas/estados/divisiones.py.
 */
export const esCargoDividido = (tx) => !!tx && tx.categoria === 'FINANZAS' && tx.subcategoria === 'Dividido';
export const esParteDividida = (tx) => !!tx && tx.dividido_de != null;

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const vacia = () => ({ monto: '', categoria: '', subcategoria: '', nota: '' });

export function DivisionPanel({ tx, cats, idp, autoEdit = false, onChanged }) {
  const [div, setDiv] = useState(undefined);   // undefined = cargando; null = sin dividir
  const [partes, setPartes] = useState(null);  // null = no editando
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    let vivo = true;
    api.get(`/transactions/${tx.id}/division`)
      .then((d) => { if (vivo) setDiv(d.division || null); })
      .catch(() => { if (vivo) setDiv(null); });
    return () => { vivo = false; };
  }, [tx.id]);

  // Abierto desde «Dividir» del panel rápido: arranca editando.
  useEffect(() => {
    if (autoEdit && div !== undefined && partes === null) editar();
  }, [autoEdit, div]); // eslint-disable-line react-hooks/exhaustive-deps

  if (div === undefined) return null;

  const total = r2(Math.abs(div ? div.padre.monto : tx.monto));
  const asignado = r2((partes || []).reduce((s, p) => s + (parseFloat(p.monto) || 0), 0));
  const falta = r2(total - asignado);
  const cuadra = Math.abs(falta) < 0.01;
  const keys = categoryKeys(cats).filter((k) => k !== 'EXPENSE');

  function editar() {
    setErr('');
    if (div) {
      setPartes(div.partes.map((p) => ({ monto: String(p.monto), categoria: p.categoria, subcategoria: p.subcategoria || '', nota: p.nota || '' })));
    } else {
      // Arranca con la categoría actual por el total y una parte vacía: al
      // escribir la segunda, «Resto» ajusta la primera.
      setPartes([{ monto: String(total), categoria: tx.categoria || '', subcategoria: tx.subcategoria || '', nota: '' }, vacia()]);
    }
  }

  const setParte = (i, k, v) => setPartes((ps) => ps.map((p, j) => {
    if (j !== i) return p;
    if (k === 'categoria') return p.categoria === v ? p : { ...p, categoria: v, subcategoria: '' };
    return { ...p, [k]: v };
  }));
  const quitar = (i) => setPartes((ps) => ps.filter((_, j) => j !== i));
  const resto = (i) => setPartes((ps) => {
    const otros = ps.reduce((s, p, j) => s + (j === i ? 0 : parseFloat(p.monto) || 0), 0);
    return ps.map((p, j) => (j === i ? { ...p, monto: String(Math.max(r2(total - otros), 0)) } : p));
  });

  async function guardar() {
    if (busy) return;
    if (partes.some((p) => !p.categoria)) { setErr('Cada parte necesita su categoría.'); return; }
    if (partes.some((p) => !(parseFloat(p.monto) > 0))) { setErr('Cada parte necesita un monto mayor a 0.'); return; }
    if (!cuadra) { setErr(`Las partes deben sumar ${money(total)} (${falta > 0 ? 'faltan' : 'sobran'} ${money(Math.abs(falta))}).`); return; }
    setBusy(true); setErr('');
    try {
      await api.put(`/transactions/${tx.id}/division`, {
        partes: partes.map((p) => ({ ...p, monto: parseFloat(p.monto) })),
      });
      toast(`Dividido en ${partes.length} categorías`, 'ok');
      onChanged && onChanged();
    } catch (e) { setErr(e.message || 'No se pudo guardar la división.'); setBusy(false); }
  }

  async function deshacer() {
    const ok = await confirmDialog('¿Deshacer la división? Se borran las partes y el movimiento vuelve a su categoría anterior.', { confirmLabel: 'Deshacer', danger: true });
    if (!ok) return;
    setBusy(true);
    try {
      await api.del(`/transactions/${tx.id}/division`);
      toast('División deshecha', 'ok');
      onChanged && onChanged();
    } catch (e) { setErr(e.message || 'No se pudo deshacer.'); setBusy(false); }
  }

  if (!partes) {
    if (!div) {
      return (
        <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm fz-div-open" onClick={editar}>
          <Icon name="split" size={16} />Dividir en varias categorías
        </button>
      );
    }
    return (
      <fieldset className="fz-fieldset">
        <legend className="t-eyebrow">Dividido en {div.partes.length} categorías</legend>
        {esParteDividida(tx) && <div className="t-meta">Esta es una parte de «{div.padre.descripcion}» ({money(total)}).</div>}
        <ul className="fz-div-list">
          {div.partes.map((p) => (
            <li key={p.id} aria-current={p.hijo_id === tx.id || undefined}>
              <span className="eu-grow">{catMeta(p.categoria).name}{p.subcategoria ? ` · ${p.subcategoria}` : ''}{p.nota ? <span className="t-meta"> — {p.nota}</span> : null}</span>
              <span className="t-data">{money(p.monto)}</span>
            </li>
          ))}
        </ul>
        <div className="fz-div-actions">
          <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={editar} disabled={busy}><Icon name="pencil" size={16} />Editar división</button>
          <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={deshacer} disabled={busy}><Icon name="undo-2" size={16} />Deshacer</button>
        </div>
        {err && <div className="fz-note" data-tone="danger" role="alert"><Icon name="circle-alert" size={16} /><span>{err}</span></div>}
      </fieldset>
    );
  }

  return (
    <fieldset className="fz-fieldset">
      <legend className="t-eyebrow">Dividir {money(total)} en categorías</legend>
      <div className="t-meta">El cargo del banco no cambia; cada parte cuenta en su categoría (p. ej. un pedido de Amazon con varias cosas).</div>
      {partes.map((p, i) => {
        const subs = subcatsFor(cats, p.categoria, tx.tipo);
        const k = `${idp}-dv${i}`;
        return (
          <div key={i} className="fz-div-row">
            <input id={`${k}-m`} aria-label={`Monto de la parte ${i + 1}`} className="eu-input eu-input--money" type="number" step="0.01" min="0" inputMode="decimal"
              value={p.monto} onChange={(e) => setParte(i, 'monto', e.target.value)} placeholder="0.00" />
            <select aria-label={`Categoría de la parte ${i + 1}`} className="eu-select" value={p.categoria} onChange={(e) => setParte(i, 'categoria', e.target.value)}>
              <option value="">Categoría…</option>
              {keys.map((c) => <option key={c} value={c}>{catMeta(c).name}</option>)}
            </select>
            <select aria-label={`Subcategoría de la parte ${i + 1}`} className="eu-select" value={p.subcategoria} onChange={(e) => setParte(i, 'subcategoria', e.target.value)} disabled={!subs.length}>
              <option value="">— Sin subcategoría —</option>
              {subs.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <input aria-label={`Qué fue la parte ${i + 1}`} className="eu-input" maxLength={80} value={p.nota} onChange={(e) => setParte(i, 'nota', e.target.value)} placeholder="Qué fue (opcional)" />
            <div className="fz-div-row-act">
              {!cuadra && <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => resto(i)} title="Ajustar esta parte para que cuadre el total">Resto</button>}
              {partes.length > 2 && <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => quitar(i)} aria-label={`Quitar parte ${i + 1}`}><Icon name="x" size={16} /></button>}
            </div>
          </div>
        );
      })}
      <div className="fz-div-actions">
        <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => setPartes((ps) => [...ps, vacia()])} disabled={partes.length >= 20}><Icon name="plus" size={16} />Agregar parte</button>
        <span className="eu-grow t-meta" aria-live="polite" data-tone={cuadra ? undefined : 'warning'}>
          {cuadra ? `Cuadra: ${money(total)}` : `${money(asignado)} de ${money(total)} · ${falta > 0 ? 'faltan' : 'sobran'} ${money(Math.abs(falta))}`}
        </span>
      </div>
      {err && <div className="fz-note" data-tone="danger" role="alert"><Icon name="circle-alert" size={16} /><span>{err}</span></div>}
      <div className="fz-div-actions">
        <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => { setPartes(null); setErr(''); }} disabled={busy}>Cancelar</button>
        <button type="button" className="eu-btn eu-btn--primary eu-btn--sm" onClick={guardar} disabled={busy || !cuadra} aria-busy={busy || undefined}>Guardar división</button>
      </div>
    </fieldset>
  );
}
