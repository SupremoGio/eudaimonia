import { useState } from 'react';
import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { fmtDate, money } from '../lib/format.js';
import { bankName } from '../lib/meta.js';
import { Empty, ErrorNote, Field, Icon, Modal, Skel, confirmDialog, toast, useLoad } from '../components/ui.jsx';

// Préstamos por cobrar (solo PC). Un préstamo nace de un movimiento de gasto
// (el SPEI o retiro con el que prestaste); las devoluciones son ingresos que
// se ligan y bajan el pendiente sin contar como ingreso. El estado se calcula
// solo; «Perdido» es manual y en la Radiografía se vuelve gasto de Familia y
// regalos del mes en que se marca.

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const TONE = { Pendiente: 'warning', 'Pagado parcial': 'info', Pagado: 'success', Perdido: 'danger' };

function movLabel(m) {
  return `${fmtDate(m.fecha, true)} · ${m.descripcion} · ${money(m.monto)}${m.banco ? ` · ${bankName(m.banco)}` : ''}`;
}

function NuevoPrestamo({ cand, onClose, onSaved }) {
  const [mov, setMov] = useState(cand.prestamos[0] ? String(cand.prestamos[0].id) : '');
  const [persona, setPersona] = useState('');
  const [notas, setNotas] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!mov) { setErr('Elige el movimiento con el que prestaste.'); return; }
    if (!persona.trim()) { setErr('Indica a quién le prestaste.'); return; }
    setBusy(true); setErr('');
    try {
      await api.post('/prestamos', { movimiento_id: Number(mov), persona: persona.trim(), notas });
      toast('Préstamo registrado', 'ok');
      onSaved(); onClose();
    } catch (ex) { setErr(ex.message || 'No se pudo guardar.'); setBusy(false); }
  }

  return (
    <Modal title="Nuevo préstamo" eyebrow="Por cobrar" onClose={onClose}
      footer={<>
        <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
        <button type="submit" form="fz-pc-new" className="eu-btn eu-btn--primary" disabled={busy || !cand.prestamos.length} aria-busy={busy || undefined}>Registrar</button>
      </>}>
      <form id="fz-pc-new" className="eu-modal-bd" onSubmit={submit} noValidate>
        {cand.prestamos.length === 0 ? (
          <Empty compact icon="search-x" title="Sin movimientos disponibles"
            text="Primero ponle la categoría «Préstamos» al movimiento con el que prestaste (en Movimientos)." />
        ) : (
          <Field label="Movimiento con el que prestaste" htmlFor="fz-pc-mov" help="Gastos con categoría Préstamos que aún no tienen préstamo.">
            <select id="fz-pc-mov" className="eu-select" value={mov} onChange={(e) => setMov(e.target.value)}>
              {cand.prestamos.map((m) => <option key={m.id} value={m.id}>{movLabel(m)}</option>)}
            </select>
          </Field>
        )}
        <Field label="Persona" htmlFor="fz-pc-persona">
          <input id="fz-pc-persona" className="eu-input" list="fz-pc-personas" value={persona} onChange={(e) => setPersona(e.target.value)} placeholder="¿A quién le prestaste?" autoComplete="off" />
          <datalist id="fz-pc-personas">{cand.personas.map((p) => <option key={p} value={p} />)}</datalist>
        </Field>
        <Field label="Notas (opcional)" htmlFor="fz-pc-notas" error={err}>
          <input id="fz-pc-notas" className="eu-input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej. para el depósito del depa" />
        </Field>
      </form>
    </Modal>
  );
}

function LigarDevolucion({ prestamo, cand, onClose, onSaved }) {
  const [mov, setMov] = useState(cand.devoluciones[0] ? String(cand.devoluciones[0].id) : '');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!mov) { setErr('Elige el ingreso con el que te pagaron.'); return; }
    setBusy(true); setErr('');
    try {
      await api.post(`/prestamos/${prestamo.id}/devoluciones`, { movimiento_id: Number(mov) });
      toast('Devolución ligada', 'ok');
      onSaved(); onClose();
    } catch (ex) { setErr(ex.message || 'No se pudo ligar.'); setBusy(false); }
  }

  return (
    <Modal title={`Devolución de ${prestamo.persona}`} eyebrow={`Pendiente ${money(prestamo.pendiente)}`} onClose={onClose}
      footer={<>
        <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
        <button type="submit" form="fz-pc-dev" className="eu-btn eu-btn--primary" disabled={busy || !cand.devoluciones.length} aria-busy={busy || undefined}>Ligar</button>
      </>}>
      <form id="fz-pc-dev" className="eu-modal-bd" onSubmit={submit} noValidate>
        {cand.devoluciones.length === 0 ? (
          <Empty compact icon="search-x" title="Sin ingresos disponibles" text="No hay ingresos sin ligar en Préstamos, Finanzas u Otros." />
        ) : (
          <Field label="Ingreso recibido" htmlFor="fz-pc-devmov" error={err}
            help="Al ligarlo deja de contar como ingreso y solo baja el pendiente.">
            <select id="fz-pc-devmov" className="eu-select" value={mov} onChange={(e) => setMov(e.target.value)}>
              {cand.devoluciones.map((m) => <option key={m.id} value={m.id}>{movLabel(m)}</option>)}
            </select>
          </Field>
        )}
      </form>
    </Modal>
  );
}

export default function PorCobrar() {
  const app = useApp();
  const res = useLoad(() => api.get('/prestamos'), [app.refreshKey]);
  const cand = useLoad(() => api.get('/prestamos/candidatos'), [app.refreshKey]);
  const dup = useLoad(() => api.get('/prestamos/duplicados'), [app.refreshKey]);
  const [modal, setModal] = useState(null); // {kind:'new'} | {kind:'dev', prestamo}
  const saved = () => app.refresh();
  const d = res.data;

  async function setPerdido(p, perdido) {
    const ok = !perdido || await confirmDialog(
      `¿Marcar como perdido el préstamo a ${p.persona}? Sus ${money(p.pendiente)} pendientes contarán como gasto en Familia y regalos este mes.`,
      { confirmLabel: 'Marcar perdido', danger: true });
    if (!ok) return;
    try { await api.patch(`/prestamos/${p.id}`, { perdido }); toast(perdido ? 'Marcado como perdido' : 'Préstamo reactivado', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo actualizar', 'err'); }
  }
  async function unlink(p, dv) {
    const ok = await confirmDialog(`¿Quitar la devolución de ${money(dv.monto)} del préstamo a ${p.persona}?`, { confirmLabel: 'Quitar' });
    if (!ok) return;
    try { await api.del(`/prestamos/${p.id}/devoluciones/${dv.movimiento_id}`); toast('Devolución quitada', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo quitar', 'err'); }
  }
  async function remove(p) {
    const ok = await confirmDialog(`¿Borrar el registro del préstamo a ${p.persona}? Los movimientos del banco no se tocan.`, { confirmLabel: 'Borrar', danger: true });
    if (!ok) return;
    try { await api.del(`/prestamos/${p.id}`); toast('Préstamo borrado', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo borrar', 'err'); }
  }

  return (
    <div className="fz-vstack-lg fz-pc">
      <div className="eu-between fz-wrap">
        <div className="eu-hstack fz-pc-stats">
          <div className="eu-card eu-stat">
            <div className="eu-stat-lbl"><Icon name="hand-coins" />Por cobrar</div>
            {res.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(d?.total_pendiente || 0)}</div>}
            <div className="t-meta">{d ? plural(d.personas.filter((g) => g.pendiente > 0).length, 'persona con saldo', 'personas con saldo') : ' '}</div>
          </div>
          {d?.total_perdido > 0 && (
            <div className="eu-card eu-stat" data-tone="danger">
              <div className="eu-stat-lbl"><Icon name="circle-x" />Perdido</div>
              <div className="eu-stat-val fg-danger">{money(d.total_perdido)}</div>
              <div className="t-meta">Contado como gasto en Familia y regalos</div>
            </div>
          )}
        </div>
        <button type="button" className="eu-btn eu-btn--primary" onClick={() => setModal({ kind: 'new' })} disabled={!cand.data}>
          <Icon name="plus" />Nuevo préstamo
        </button>
      </div>

      {(cand.data?.prestamos || []).length > 0 && (
        <div className="fz-note" data-tone="info" role="note">
          <Icon name="user-plus" size={16} />
          <span className="eu-grow">{plural(cand.data.prestamos.length, 'movimiento con categoría Préstamos aún no tiene', 'movimientos con categoría Préstamos aún no tienen')} persona asignada.</span>
          <button type="button" className="fz-link" onClick={() => setModal({ kind: 'new' })}>Registrar<Icon name="arrow-right" size={14} /></button>
        </div>
      )}

      {(dup.data || []).length > 0 && (
        <div className="fz-note" data-tone="warning" role="note">
          <Icon name="copy" size={16} />
          <div className="eu-grow eu-vstack fz-gap-2">
            <b>Posibles duplicados: mismo día y monto</b>
            <span className="t-meta">Solo es un aviso: revísalos y, si sobra alguno, bórralo desde Movimientos.</span>
            <ul className="fz-pc-dups">
              {dup.data.map((g) => (
                <li key={`${g.fecha}-${g.monto}`}>
                  <span className="num">{fmtDate(g.fecha, true)} · {money(g.monto)}</span>
                  <span className="t-meta">{g.movimientos.map((m) => m.descripcion).join('  ·  ')}</span>
                  <button type="button" className="fz-link" onClick={() => app.goTo('movimientos', { search: g.movimientos[0].descripcion })}>
                    Ver en Movimientos<Icon name="arrow-right" size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <ErrorNote error={res.error} onRetry={res.reload} />
      {res.loading ? <Skel rows={3} h={120} /> : !d || d.personas.length === 0 ? (
        <Empty icon="hand-coins" title="Sin préstamos registrados"
          text="Cuando prestes dinero, ponle la categoría «Préstamos» al movimiento y regístralo aquí con la persona.">
          <button type="button" className="eu-btn eu-btn--primary" onClick={() => setModal({ kind: 'new' })} disabled={!cand.data}><Icon name="plus" />Nuevo préstamo</button>
        </Empty>
      ) : (
        <div className="eu-vstack fz-gap-3">
          {d.personas.map((g) => (
            <section key={g.persona} className="eu-card eu-card--flush fz-pc-person" aria-label={`Préstamos a ${g.persona}`}>
              <div className="eu-between fz-card-hd">
                <h2 className="t-card">{g.persona}</h2>
                <span className="t-meta">Prestado {money(g.prestado)} · devuelto {money(g.devuelto)} · <b className="num fz-fg-1">pendiente {money(g.pendiente)}</b></span>
              </div>
              <table className="eu-table fz-pc-table">
                <colgroup><col className="c-date" /><col /><col className="c-amt" /><col className="c-amt" /><col className="c-amt" /><col className="c-st" /><col className="c-act" /></colgroup>
                <thead>
                  <tr><th>Fecha</th><th>Movimiento</th><th className="r">Monto</th><th className="r">Devuelto</th><th className="r">Pendiente</th><th>Estado</th><th><span className="fz-sr">Acciones</span></th></tr>
                </thead>
                <tbody>
                  {g.prestamos.map((p) => (
                    <tr key={p.id}>
                      <td className="num fg-3">{fmtDate(p.fecha, true)}</td>
                      <td>
                        <span className="fz-ellipsis fz-td-desc" title={p.descripcion}>{p.descripcion || 'Sin movimiento'}</span>
                        {p.notas && <div className="t-meta fz-ellipsis">{p.notas}</div>}
                        {p.devoluciones.length > 0 && (
                          <ul className="fz-pc-devs">
                            {p.devoluciones.map((dv) => (
                              <li key={dv.movimiento_id} className="t-meta">
                                <Icon name="corner-down-right" size={12} />{fmtDate(dv.fecha, true)} · <span className="num">{money(dv.monto)}</span>
                                <button type="button" className="eu-iconbtn fz-pc-x" aria-label={`Quitar devolución de ${money(dv.monto)}`} title="Quitar devolución" onClick={() => unlink(p, dv)}><Icon name="x" size={12} /></button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                      <td className="r num">{money(p.monto)}</td>
                      <td className="r num">{money(p.devuelto)}</td>
                      <td className="r num">{money(p.pendiente)}</td>
                      <td><span className={`eu-badge eu-badge--${TONE[p.estado]}`}>{p.estado}</span>{p.perdido_fecha && <div className="t-meta">{fmtDate(p.perdido_fecha, true)}</div>}</td>
                      <td className="r fz-pc-acts">
                        {p.estado !== 'Pagado' && p.estado !== 'Perdido' && (
                          <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" onClick={() => setModal({ kind: 'dev', prestamo: p })} disabled={!cand.data}>Ligar devolución</button>
                        )}
                        {p.estado === 'Perdido' ? (
                          <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => setPerdido(p, false)}>Reactivar</button>
                        ) : p.estado !== 'Pagado' && (
                          <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => setPerdido(p, true)}>Perdido</button>
                        )}
                        <button type="button" className="eu-iconbtn" aria-label={`Borrar préstamo a ${p.persona}`} title="Borrar registro" onClick={() => remove(p)}><Icon name="trash-2" /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}

      {modal?.kind === 'new' && cand.data && <NuevoPrestamo cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
      {modal?.kind === 'dev' && cand.data && <LigarDevolucion prestamo={modal.prestamo} cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
    </div>
  );
}
