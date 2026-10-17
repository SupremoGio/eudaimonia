import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { PRESTAMO_OTROS, PRESTAMO_PERSONAS } from '../lib/meta.js';
import { Field, Icon, toast } from './ui.jsx';

/**
 * «¿A quién le prestaste?» al poner la categoría Préstamos en un gasto, desde
 * el editor o el categorizador rápido: al guardar el movimiento queda
 * registrado (o actualizado) en «Por cobrar», sin tener que ir allá aparte.
 * `txId` es null en un movimiento nuevo.
 */
export function usePrestamoPersona(txId) {
  const [prestamo, setPrestamo] = useState(null); // {id, persona} si ya existe
  const [persona, setPersona] = useState('');
  const [otro, setOtro] = useState('');
  const [personas, setPersonas] = useState([]);

  useEffect(() => {
    let vivo = true;
    setPrestamo(null); setPersona(''); setOtro('');
    api.get('/prestamos').then((d) => {
      if (!vivo) return;
      const grupos = d.personas || [];
      setPersonas(grupos.map((g) => g.persona).filter((p) => !PRESTAMO_PERSONAS.includes(p) && p !== PRESTAMO_OTROS));
      const p = txId ? grupos.flatMap((g) => g.prestamos).find((x) => x.movimiento_id === txId) : null;
      if (p) {
        setPrestamo({ id: p.id, persona: p.persona });
        if (PRESTAMO_PERSONAS.includes(p.persona)) setPersona(p.persona);
        else { setPersona(PRESTAMO_OTROS); setOtro(p.persona === PRESTAMO_OTROS ? '' : p.persona); }
      }
    }).catch(() => {});
    return () => { vivo = false; };
  }, [txId]);

  const quien = persona === PRESTAMO_OTROS ? (otro.trim() || PRESTAMO_OTROS) : persona;

  /** Llamar después de guardar el movimiento (ya como PRESTAMOS/GASTO). */
  async function guardar(movId) {
    if (!quien || !movId) return;
    try {
      if (prestamo) {
        if (prestamo.persona !== quien) await api.patch(`/prestamos/${prestamo.id}`, { persona: quien });
      } else {
        const r = await api.post('/prestamos', { movimiento_id: movId, persona: quien });
        setPrestamo({ id: r && r.id, persona: quien });
      }
    } catch (e) {
      toast(`Se guardó el movimiento, pero no el préstamo: ${e.message || 'error'}`, 'err');
    }
  }

  return { prestamo, persona, setPersona, otro, setOtro, personas, quien, guardar };
}

/** Campos de persona; `activo` = la categoría elegida es Préstamos en un gasto. */
export function PrestamoPersonaField({ p, activo, idp, compact = false }) {
  if (!activo) {
    return p.prestamo ? (
      <div className="fz-note" data-tone="warning" role="note">
        <Icon name="triangle-alert" size={16} />
        <span className="eu-grow">Este movimiento sigue registrado como préstamo a {p.prestamo.persona} en Por cobrar. Si ya no es préstamo, bórralo ahí; si no, se volverá a clasificar como Préstamos.</span>
      </div>
    ) : null;
  }
  const select = (
    <select id={`${idp}-persona`} className={`eu-select${compact ? ' fz-input-sm' : ''}`} aria-label="¿A quién le prestaste?"
      value={p.persona} onChange={(e) => p.setPersona(e.target.value)}>
      <option value="">— ¿A quién le prestaste? —</option>
      {PRESTAMO_PERSONAS.map((x) => <option key={x} value={x}>{x}</option>)}
      <option value={PRESTAMO_OTROS}>Otros</option>
    </select>
  );
  const otro = p.persona === PRESTAMO_OTROS && (
    <>
      <input id={`${idp}-otro`} className={`eu-input${compact ? ' fz-input-sm' : ''}`} aria-label="Nombre de la persona" list={`${idp}-personas`}
        value={p.otro} onChange={(e) => p.setOtro(e.target.value)} placeholder="Nombre (vacío = «Otros»)" autoComplete="off" />
      <datalist id={`${idp}-personas`}>{p.personas.map((x) => <option key={x} value={x} />)}</datalist>
    </>
  );
  if (compact) return <div className="eu-vstack fz-gap-2">{select}{otro}</div>;
  return (
    <div className="eu-grid-2">
      <Field label="¿A quién le prestaste?" htmlFor={`${idp}-persona`}
        help={p.prestamo ? 'Ya está en Por cobrar; cambiar la persona la actualiza ahí.' : 'Al guardar queda registrado en Por cobrar.'}>
        {select}
      </Field>
      {otro && <Field label="Nombre (opcional)" htmlFor={`${idp}-otro`}>{otro}</Field>}
    </div>
  );
}
