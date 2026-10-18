import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { money } from '../lib/format.js';
import { PRESTAMO_PERSONAS } from '../lib/meta.js';
import { Field, Icon, toast } from './ui.jsx';

/**
 * «¿Alguien te debe parte de esto?» en un gasto (p. ej. pagaste el seguro del
 * carro completo y te deben la mitad). Al guardar el movimiento queda en Por
 * cobrar ligado a este gasto, y el gasto cuenta solo tu parte (mi_parte =
 * total − lo que te deben). Los abonos se ligan después desde Por cobrar o
 * Salud financiera. `txId` es null en un movimiento nuevo.
 */
export function useCompartido(txId) {
  const [existente, setExistente] = useState(null); // {id, persona, monto, devuelto}
  const [on, setOn] = useState(false);
  const [persona, setPersona] = useState('');
  const [monto, setMonto] = useState('');
  const [personas, setPersonas] = useState(PRESTAMO_PERSONAS);

  useEffect(() => {
    let vivo = true;
    setExistente(null); setOn(false); setPersona(''); setMonto('');
    api.get('/prestamos').then((d) => {
      if (!vivo) return;
      const grupos = d.personas || [];
      setPersonas([...new Set([...PRESTAMO_PERSONAS, ...grupos.map((g) => g.persona)])]);
      const p = txId ? grupos.flatMap((g) => g.prestamos).find((x) => x.movimiento_id === txId && x.compartido) : null;
      if (p) {
        setExistente({ id: p.id, persona: p.persona, monto: p.monto, devuelto: p.devuelto });
        setOn(true); setPersona(p.persona); setMonto(String(p.monto));
      }
    }).catch(() => {});
    return () => { vivo = false; };
  }, [txId]);

  /** Mensaje de error o '' si se puede guardar con este total del gasto.
   *  `v` permite validar otros valores que los del estado (el panel lateral
   *  los deriva de «Tu parte»). */
  function validar(total, v = { on, persona, monto }) {
    if (!v.on && existente && existente.devuelto > 0) return `${existente.persona} ya te ha pagado ${money(existente.devuelto)} de esto: quítalo desde Por cobrar.`;
    if (!v.on) return '';
    const m = parseFloat(v.monto);
    if (!v.persona.trim()) return 'Indica quién te debe parte del gasto.';
    if (!(m > 0)) return 'Indica cuánto te deben.';
    if (total && m > total + 0.005) return `No te pueden deber más que el gasto (${money(total)}).`;
    return '';
  }

  /** Llamar después de guardar el movimiento. Con `conservarParte` al
   *  quitarlo, el gasto conserva su mi_parte (sigue siendo compartido). */
  async function guardar(movId, descripcion, v = { on, persona, monto }, { conservarParte = false } = {}) {
    if (!movId) return;
    try {
      if (v.on && !existente) {
        const r = await api.post('/prestamos', { movimiento_id: movId, persona: v.persona.trim(), monto: parseFloat(v.monto), compartido: true, concepto: descripcion });
        setExistente({ id: r && r.id, persona: v.persona.trim(), monto: parseFloat(v.monto), devuelto: 0 });
      } else if (v.on) {
        // Siempre se manda el monto: recalcula tu parte si cambió el total del gasto.
        await api.patch(`/prestamos/${existente.id}`, { persona: v.persona.trim(), monto: parseFloat(v.monto) });
      } else if (existente) {
        await api.del(`/prestamos/${existente.id}${conservarParte ? '?conservar_parte=1' : ''}`);
        setExistente(null);
      }
    } catch (e) {
      toast(`Se guardó el movimiento, pero no lo que te deben: ${e.message || 'error'}`, 'err');
    }
  }

  return { existente, on, setOn, persona, setPersona, monto, setMonto, personas, validar, guardar };
}

/** `total` = monto del gasto (para sugerir la mitad y mostrar tu parte). */
export function CompartidoField({ c, total, idp }) {
  const debe = parseFloat(c.monto) || 0;
  const activar = (v) => {
    c.setOn(v);
    if (v && !c.monto && total > 0) c.setMonto((total / 2).toFixed(2));
  };
  return (
    <fieldset className="fz-fieldset">
      <legend className="t-eyebrow">Te deben parte</legend>
      <label className="eu-hstack fz-gap-2" htmlFor={`${idp}-comp`}>
        <input id={`${idp}-comp`} type="checkbox" checked={c.on} onChange={(e) => activar(e.target.checked)} />
        <span>¿Alguien te debe parte de este gasto?</span>
      </label>
      {c.on && (
        <>
          <div className="eu-grid-2">
            <Field label="¿Quién?" htmlFor={`${idp}-comp-persona`}>
              <input id={`${idp}-comp-persona`} className="eu-input" list={`${idp}-comp-personas`} value={c.persona}
                onChange={(e) => c.setPersona(e.target.value)} placeholder="Nombre" autoComplete="off" />
              <datalist id={`${idp}-comp-personas`}>{c.personas.map((x) => <option key={x} value={x} />)}</datalist>
            </Field>
            <Field label="¿Cuánto te debe? (MXN)" htmlFor={`${idp}-comp-monto`}>
              <input id={`${idp}-comp-monto`} className="eu-input eu-input--money" type="number" step="0.01" min="0" inputMode="decimal"
                value={c.monto} onChange={(e) => c.setMonto(e.target.value)} placeholder="0.00" />
            </Field>
          </div>
          {total > 0 && (
            <div className="eu-hstack fz-wrap fz-gap-2">
              {[['Mitad', total / 2], ['Todo', total]].map(([lbl, v]) => (
                <button key={lbl} type="button" className="eu-chip" onClick={() => c.setMonto(v.toFixed(2))}>{lbl} · {money(v)}</button>
              ))}
            </div>
          )}
          <div className="fz-note" data-tone="info" role="note">
            <Icon name="hand-coins" size={16} />
            <span className="eu-grow">
              Queda en Por cobrar ligado a este gasto, y el gasto cuenta solo tu parte
              {total > 0 && debe > 0 && debe <= total ? <> (<b className="num">{money(total - debe)}</b>)</> : null}.
              {c.existente && c.existente.devuelto > 0 ? ` Ya te ha pagado ${money(c.existente.devuelto)}.` : ' Sus pagos se ligan después desde Por cobrar o Salud financiera.'}
            </span>
          </div>
        </>
      )}
    </fieldset>
  );
}
