import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { money } from '../lib/format.js';
import { PRESTAMO_PERSONAS, catMeta } from '../lib/meta.js';
import { Icon, toast } from './ui.jsx';

/**
 * «Debo» desde el movimiento (préstamos RECIBIDO):
 *  - en un ingreso, «Me prestaron este dinero»: deja de contar como ingreso y
 *    queda en lo que debes (Salud financiera);
 *  - en un gasto, «¿Es un pago de lo que debes?»: se liga como pago. Si te
 *    prestaron dinero no cuenta como gasto; si pagaron algo por ti, toma la
 *    categoría de eso (es tu gasto real).
 */
export function useDeuda(tx) {
  const [info, setInfo] = useState(null); // {origen, pago_de, deudas}
  const [prestaron, setPrestaron] = useState(false);
  const [persona, setPersona] = useState('');
  const [pagoDe, setPagoDe] = useState(''); // id de la deuda (string) o ''

  useEffect(() => {
    let vivo = true;
    setInfo(null); setPrestaron(false); setPersona(''); setPagoDe('');
    api.get(`/prestamos/movimiento/${tx.id}`).then((d) => {
      if (!vivo) return;
      setInfo(d);
      if (d.origen && d.origen.direccion === 'RECIBIDO') { setPrestaron(true); setPersona(d.origen.persona); }
      if (d.pago_de && d.pago_de.direccion === 'RECIBIDO') setPagoDe(String(d.pago_de.id));
    }).catch(() => {});
    return () => { vivo = false; };
  }, [tx.id]);

  const origenMio = info?.origen?.direccion === 'RECIBIDO' ? info.origen : null;
  const pagoActual = info?.pago_de?.direccion === 'RECIBIDO' ? info.pago_de : null;
  // Ya ligado del lado «me deben» (préstamo hecho con él, parte de un gasto o
  // devolución): ahí se maneja, aquí no se ofrece nada.
  const ligadoMeDeben = info && ((info.origen && info.origen.direccion === 'OTORGADO') || (info.pago_de && info.pago_de.direccion === 'OTORGADO'));
  const deuda = (id) => [...(info?.deudas || []), ...(pagoActual ? [pagoActual] : [])].find((x) => String(x.id) === String(id));

  /** Categoría con la que quedará el movimiento, o null si no cambia. */
  function categoriaFinal() {
    if (tx.tipo === 'INGRESO' && prestaron) return 'PRESTAMOS';
    if (tx.tipo === 'GASTO' && pagoDe) return deuda(pagoDe)?.pago_cat || 'PRESTAMOS';
    return null;
  }

  function validar() {
    if (tx.tipo === 'INGRESO' && prestaron && !persona.trim()) return '¿Quién te prestó?';
    if (tx.tipo === 'INGRESO' && !prestaron && origenMio && origenMio.devuelto > 0) return `Ya le pagaste ${money(origenMio.devuelto)} a ${origenMio.persona}: quítalo desde Salud financiera.`;
    if (tx.tipo === 'GASTO' && pagoDe && !pagoActual) {
      const d = deuda(pagoDe);
      if (d && Math.abs(tx.monto) > d.pendiente + 0.01) return `El pago (${money(Math.abs(tx.monto))}) es mayor a lo que debes a ${d.persona} (${money(d.pendiente)}).`;
    }
    return '';
  }

  /** Llamar después de guardar el movimiento. */
  async function guardar() {
    if (!info || ligadoMeDeben) return;
    try {
      if (tx.tipo === 'INGRESO') {
        if (prestaron && !origenMio) await api.post('/prestamos', { direccion: 'RECIBIDO', movimiento_id: tx.id, persona: persona.trim() });
        else if (prestaron && origenMio.persona !== persona.trim()) await api.patch(`/prestamos/${origenMio.id}`, { persona: persona.trim() });
        else if (!prestaron && origenMio) await api.del(`/prestamos/${origenMio.id}`);
      } else if (tx.tipo === 'GASTO' && String(pagoActual?.id || '') !== pagoDe) {
        if (pagoActual) await api.del(`/prestamos/${pagoActual.id}/devoluciones/${tx.id}`);
        if (pagoDe) await api.post(`/prestamos/${pagoDe}/devoluciones`, { movimiento_id: tx.id });
      }
    } catch (e) {
      toast(`Se guardó el movimiento, pero no lo que debes: ${e.message || 'error'}`, 'err');
    }
  }

  return { info, prestaron, setPrestaron, persona, setPersona, pagoDe, setPagoDe, origenMio, pagoActual, ligadoMeDeben, deuda, categoriaFinal, validar, guardar };
}

export function DeudaField({ d, tx, idp, oculto }) {
  if (!d.info || d.ligadoMeDeben || oculto) return null;
  if (tx.tipo === 'INGRESO') {
    return (
      <div className="eu-vstack fz-gap-2 fz-cz-sec">
        <label className="eu-hstack fz-gap-2" htmlFor={`${idp}-prest`}>
          <input id={`${idp}-prest`} type="checkbox" checked={d.prestaron} onChange={(e) => d.setPrestaron(e.target.checked)} />
          <span className="t-ui">Me prestaron este dinero</span>
        </label>
        {d.prestaron && (
          <>
            <input className="eu-input fz-input-sm" list={`${idp}-prest-p`} aria-label="¿Quién te prestó?" placeholder="¿Quién te prestó?"
              value={d.persona} onChange={(e) => d.setPersona(e.target.value)} autoComplete="off" />
            <datalist id={`${idp}-prest-p`}>{PRESTAMO_PERSONAS.map((x) => <option key={x} value={x} />)}</datalist>
            <span className="t-meta">
              {d.origenMio
                ? `Debes ${money(d.origenMio.pendiente)} a ${d.origenMio.persona} · sus pagos se ligan desde tus transferencias`
                : 'No cuenta como ingreso y queda en «Debo» de Salud financiera'}
            </span>
          </>
        )}
      </div>
    );
  }
  if (tx.tipo !== 'GASTO') return null;
  const opciones = [...(d.info.deudas || [])];
  if (d.pagoActual && !opciones.some((x) => x.id === d.pagoActual.id)) opciones.unshift(d.pagoActual);
  if (!opciones.length) return null;
  const sel = d.pagoDe ? d.deuda(d.pagoDe) : null;
  return (
    <div className="eu-vstack fz-gap-2 fz-cz-sec">
      <label className="eu-label" htmlFor={`${idp}-pago`}>¿Es un pago de lo que debes?</label>
      <select id={`${idp}-pago`} className="eu-select fz-input-sm" value={d.pagoDe} onChange={(e) => d.setPagoDe(e.target.value)}>
        <option value="">No</option>
        {opciones.map((x) => (
          <option key={x.id} value={String(x.id)}>{x.persona}{x.concepto ? ` · ${x.concepto}` : ''} · debes {money(x.pendiente)}</option>
        ))}
      </select>
      {sel && (
        <span className="t-meta eu-hstack fz-gap-2">
          <Icon name="info" size={14} />
          {sel.pago_cat ? `Cuenta como gasto de ${catMeta(sel.pago_cat).name}: es lo que pagó por ti.` : 'No cuenta como gasto: le regresas lo que te prestó.'}
        </span>
      )}
    </div>
  );
}
