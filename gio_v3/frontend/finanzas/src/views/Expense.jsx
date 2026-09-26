import { useMemo, useState } from 'react';
import { BASE, api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { fmtDate, money, norm } from '../lib/format.js';
import { bankName } from '../lib/meta.js';
import { Empty, ErrorNote, Field, Icon, Modal, Skel, confirmDialog, toast, useLoad } from '../components/ui.jsx';

// Conciliación de Expense por lotes (solo PC). Varias facturas se suben
// juntas y la empresa paga un depósito (o varios) por el lote. El estado se
// calcula solo y marca las facturas como Pagado cuando el lote queda cubierto;
// las «Pagado a compañero» conservan su estatus.

const TONE = { Pendiente: 'warning', 'Reembolsado parcial': 'info', Reembolsado: 'success', 'Sin gastos': 'neutral' };
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const cerca = (a, b) => Math.abs(a - b) <= 1;

function depLabel(m) {
  return `${fmtDate(m.fecha, true)} · ${m.descripcion} · ${money(m.monto)}${m.banco ? ` · ${bankName(m.banco)}` : ''}`;
}

function EstatusTag({ g }) {
  if (g.estatus_reembolso === 'TERCERO') return <span className="eu-badge">Pagado a compañero</span>;
  if (g.estatus_reembolso === 'PAGADO') return <span className="eu-badge eu-badge--success">Pagado</span>;
  return <span className="eu-badge eu-badge--warning">Pendiente</span>;
}

/** Lista de facturas con casillas, buscador y total de lo elegido. */
function ElegirFacturas({ gastos, sel, setSel }) {
  const [q, setQ] = useState('');
  const [soloPend, setSoloPend] = useState(true);
  const rows = useMemo(() => {
    let r = gastos;
    if (soloPend) r = r.filter((g) => (g.estatus_reembolso || 'PENDIENTE') !== 'PAGADO' || sel.has(g.id));
    if (q.trim()) { const nq = norm(q.trim()); r = r.filter((g) => norm(`${g.descripcion} ${g.fecha} ${g.monto}`).includes(nq)); }
    return r;
  }, [gastos, q, soloPend, sel]);
  const toggle = (id) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  return (
    <div className="eu-vstack fz-gap-2">
      <div className="eu-hstack fz-wrap">
        <div className="eu-input-wrap eu-grow">
          <Icon name="search" />
          <input className="eu-input fz-input-sm" type="search" placeholder="Buscar factura…" aria-label="Buscar factura" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <label className="eu-hstack t-meta"><input type="checkbox" checked={soloPend} onChange={(e) => setSoloPend(e.target.checked)} /> Ocultar las ya pagadas</label>
      </div>
      {rows.length === 0 ? <div className="t-meta">No hay facturas sin lote que coincidan.</div> : (
        <ul className="fz-ex-pick">
          {rows.map((g) => (
            <li key={g.id}>
              <label>
                <input type="checkbox" checked={sel.has(g.id)} onChange={() => toggle(g.id)} />
                <span className="num fg-3 fz-ex-date">{fmtDate(g.fecha, true)}</span>
                <span className="eu-grow fz-ellipsis" title={g.descripcion}>{g.descripcion}</span>
                <EstatusTag g={g} />
                <span className="num fz-ex-amt">{money(g.monto)}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NuevoLote({ cand, onClose, onSaved }) {
  const [nombre, setNombre] = useState('');
  const [notas, setNotas] = useState('');
  const [sel, setSel] = useState(new Set());
  const [dep, setDep] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const total = cand.gastos.filter((g) => sel.has(g.id)).reduce((s, g) => s + g.monto, 0);

  async function submit(e) {
    e.preventDefault();
    if (!nombre.trim()) { setErr('Ponle un nombre al lote (ej. «Facturas mayo»).'); return; }
    if (!sel.size) { setErr('Elige al menos una factura.'); return; }
    setBusy(true); setErr('');
    try {
      await api.post('/expense/lotes', { nombre, notas, gasto_ids: [...sel], deposito_ids: dep ? [Number(dep)] : [] });
      toast('Lote creado', 'ok'); onSaved(); onClose();
    } catch (ex) { setErr(ex.message || 'No se pudo guardar.'); setBusy(false); }
  }

  return (
    <Modal size="wide" title="Nuevo lote de reembolso" eyebrow="Expense" onClose={onClose}
      footer={<>
        <span className="eu-grow t-meta">{plural(sel.size, 'factura', 'facturas')} · <b className="num fz-fg-1">{money(total)}</b></span>
        <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
        <button type="submit" form="fz-ex-new" className="eu-btn eu-btn--primary" disabled={busy} aria-busy={busy || undefined}>Crear lote</button>
      </>}>
      <form id="fz-ex-new" className="eu-modal-bd" onSubmit={submit} noValidate>
        <div className="eu-grid-2">
          <Field label="Nombre del lote" htmlFor="fz-ex-nombre">
            <input id="fz-ex-nombre" className="eu-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej. Facturas mayo" autoComplete="off" />
          </Field>
          <Field label="Notas (opcional)" htmlFor="fz-ex-notas">
            <input id="fz-ex-notas" className="eu-input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej. viaje a Cancún" />
          </Field>
        </div>
        <Field label="Facturas del lote" help="Gastos EXPENSE que aún no están en ningún lote. Incluye los «PAGO CUENTA DE TERCERO» si ese reembolso cubre la factura de un compañero.">
          {cand.gastos.length === 0
            ? <Empty compact icon="search-x" title="Sin facturas disponibles" text="Ponle la categoría EXPENSE a los gastos de trabajo (en Movimientos)." />
            : <ElegirFacturas gastos={cand.gastos} sel={sel} setSel={setSel} />}
        </Field>
        <Field label="Depósito de la empresa (opcional)" htmlFor="fz-ex-dep" error={err}
          help="Si ya te pagaron el lote, elige el depósito; si no, lo ligas después.">
          <select id="fz-ex-dep" className="eu-select" value={dep} onChange={(e) => setDep(e.target.value)}>
            <option value="">Todavía no me lo pagan</option>
            {cand.depositos.map((m) => (
              <option key={m.id} value={m.id}>{sel.size && cerca(m.monto, total) ? '✓ coincide · ' : ''}{depLabel(m)}</option>
            ))}
          </select>
        </Field>
      </form>
    </Modal>
  );
}

function AgregarFacturas({ lote, cand, onClose, onSaved }) {
  const [sel, setSel] = useState(new Set());
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (!sel.size) { setErr('Elige al menos una factura.'); return; }
    setBusy(true); setErr('');
    try { await api.post(`/expense/lotes/${lote.id}/gastos`, { movimiento_ids: [...sel] }); toast('Facturas agregadas', 'ok'); onSaved(); onClose(); }
    catch (ex) { setErr(ex.message || 'No se pudo agregar.'); setBusy(false); }
  }
  return (
    <Modal size="wide" title={`Agregar facturas a «${lote.nombre}»`} eyebrow="Expense" onClose={onClose}
      footer={<>
        <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
        <button type="submit" form="fz-ex-add" className="eu-btn eu-btn--primary" disabled={busy} aria-busy={busy || undefined}>Agregar</button>
      </>}>
      <form id="fz-ex-add" className="eu-modal-bd" onSubmit={submit} noValidate>
        <Field label="Facturas sin lote" error={err}>
          {cand.gastos.length === 0 ? <div className="t-meta">No hay facturas sin lote.</div>
            : <ElegirFacturas gastos={cand.gastos} sel={sel} setSel={setSel} />}
        </Field>
      </form>
    </Modal>
  );
}

function LigarDeposito({ lote, cand, onClose, onSaved }) {
  const match = cand.depositos.find((m) => cerca(m.monto, lote.pendiente));
  const [dep, setDep] = useState(String((match || cand.depositos[0] || {}).id || ''));
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (!dep) { setErr('Elige el depósito de la empresa.'); return; }
    setBusy(true); setErr('');
    try { await api.post(`/expense/lotes/${lote.id}/depositos`, { movimiento_id: Number(dep) }); toast('Depósito ligado', 'ok'); onSaved(); onClose(); }
    catch (ex) { setErr(ex.message || 'No se pudo ligar.'); setBusy(false); }
  }
  return (
    <Modal title={`Depósito de «${lote.nombre}»`} eyebrow={`Pendiente ${money(lote.pendiente)}`} onClose={onClose}
      footer={<>
        <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
        <button type="submit" form="fz-ex-dep2" className="eu-btn eu-btn--primary" disabled={busy || !cand.depositos.length} aria-busy={busy || undefined}>Ligar</button>
      </>}>
      <form id="fz-ex-dep2" className="eu-modal-bd" onSubmit={submit} noValidate>
        {cand.depositos.length === 0 ? (
          <Empty compact icon="search-x" title="Sin depósitos disponibles" text="No hay ingresos sin ligar en Finanzas, Otros o Expense." />
        ) : (
          <Field label="Depósito recibido" htmlFor="fz-ex-depsel" error={err}
            help="Queda como Finanzas · Reembolsable (no cuenta como ingreso). Si cubre el lote, sus facturas pasan a Pagado.">
            <select id="fz-ex-depsel" className="eu-select" value={dep} onChange={(e) => setDep(e.target.value)}>
              {cand.depositos.map((m) => <option key={m.id} value={m.id}>{cerca(m.monto, lote.pendiente) ? '✓ coincide · ' : ''}{depLabel(m)}</option>)}
            </select>
          </Field>
        )}
      </form>
    </Modal>
  );
}

function LoteCard({ l, cand, saved, open }) {
  async function quitarGasto(g) {
    if (!await confirmDialog(`¿Sacar «${g.descripcion}» del lote?`, { confirmLabel: 'Sacar' })) return;
    try { await api.del(`/expense/lotes/${l.id}/gastos/${g.id}`); toast('Factura quitada', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo quitar', 'err'); }
  }
  async function quitarDep(d) {
    if (!await confirmDialog(`¿Quitar el depósito de ${money(d.monto)} del lote?`, { confirmLabel: 'Quitar' })) return;
    try { await api.del(`/expense/lotes/${l.id}/depositos/${d.id}`); toast('Depósito quitado', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo quitar', 'err'); }
  }
  async function borrar() {
    if (!await confirmDialog(`¿Borrar el lote «${l.nombre}»? Las facturas y depósitos del banco no se tocan.`, { confirmLabel: 'Borrar', danger: true })) return;
    try { await api.del(`/expense/lotes/${l.id}`); toast('Lote borrado', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo borrar', 'err'); }
  }
  return (
    <section className="eu-card eu-card--flush" aria-label={`Lote ${l.nombre}`}>
      <div className="eu-between fz-card-hd fz-wrap">
        <div className="eu-vstack">
          <h2 className="t-card">{l.nombre} <span className={`eu-badge eu-badge--${TONE[l.estado]}`}>{l.estado}</span></h2>
          <span className="t-meta">
            {l.desde ? `${fmtDate(l.desde, true)} – ${fmtDate(l.hasta, true)} · ` : ''}{plural(l.gastos.length, 'factura', 'facturas')}
            {l.terceros > 0 ? ` · a compañeros ${money(l.terceros)}` : ''}{l.notas ? ` · ${l.notas}` : ''}
          </span>
        </div>
        <span className="t-meta">
          Facturas {money(l.total)} · depositado {money(l.depositado)} · <b className="num fz-fg-1">pendiente {money(l.pendiente)}</b>
          {l.diferencia > 1 && <span className="fg-warning"> · depositaron {money(l.diferencia)} de más</span>}
        </span>
      </div>
      <table className="eu-table fz-ex-table">
        <colgroup><col className="c-date" /><col /><col className="c-st" /><col className="c-amt" /><col className="c-x" /></colgroup>
        <thead><tr><th>Fecha</th><th>Factura</th><th>Estatus</th><th className="r">Monto</th><th><span className="fz-sr">Quitar</span></th></tr></thead>
        <tbody>
          {l.gastos.map((g) => (
            <tr key={g.id}>
              <td className="num fg-3">{fmtDate(g.fecha, true)}</td>
              <td><span className="fz-ellipsis fz-td-desc" title={g.descripcion}>{g.descripcion}</span></td>
              <td><EstatusTag g={g} /></td>
              <td className="r num">{money(g.monto)}</td>
              <td className="r"><button type="button" className="eu-iconbtn fz-pc-x" aria-label={`Sacar ${g.descripcion} del lote`} title="Sacar del lote" onClick={() => quitarGasto(g)}><Icon name="x" size={12} /></button></td>
            </tr>
          ))}
          {l.depositos.map((d) => (
            <tr key={`d${d.id}`} className="fz-ex-dep">
              <td className="num fg-3">{fmtDate(d.fecha, true)}</td>
              <td><Icon name="corner-down-right" size={12} /> <span title={d.descripcion}>Depósito · {d.descripcion}</span></td>
              <td><span className="eu-badge eu-badge--success">Depósito</span></td>
              <td className="r num fg-success">+{money(d.monto)}</td>
              <td className="r"><button type="button" className="eu-iconbtn fz-pc-x" aria-label={`Quitar depósito de ${money(d.monto)}`} title="Quitar depósito" onClick={() => quitarDep(d)}><Icon name="x" size={12} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="eu-hstack fz-pad fz-ex-acts">
        {l.estado !== 'Reembolsado' && (
          <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" onClick={() => open({ kind: 'dep', lote: l })} disabled={!cand}>Ligar depósito</button>
        )}
        <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => open({ kind: 'add', lote: l })} disabled={!cand}>Agregar facturas</button>
        <span className="eu-grow" />
        <button type="button" className="eu-iconbtn" aria-label={`Borrar lote ${l.nombre}`} title="Borrar lote" onClick={borrar}><Icon name="trash-2" /></button>
      </div>
    </section>
  );
}

export default function Expense() {
  const app = useApp();
  const res = useLoad(() => api.get('/expense/lotes'), [app.refreshKey]);
  const cand = useLoad(() => api.get('/expense/candidatos'), [app.refreshKey]);
  const [modal, setModal] = useState(null); // {kind:'new'} | {kind:'add'|'dep', lote}
  const saved = () => app.refresh();
  const d = res.data;
  const sueltosPend = (d?.sin_lote || []).filter((g) => (g.estatus_reembolso || 'PENDIENTE') === 'PENDIENTE');

  return (
    <div className="fz-vstack-lg fz-pc">
      <div className="eu-between fz-wrap">
        <div className="eu-hstack fz-pc-stats">
          <div className="eu-card eu-stat">
            <div className="eu-stat-lbl"><Icon name="receipt" />Por cobrar a la empresa</div>
            {res.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(d?.por_cobrar || 0)}</div>}
            <div className="t-meta">{d ? plural(d.lotes_abiertos, 'lote abierto', 'lotes abiertos') : ' '}</div>
          </div>
          <div className="eu-card eu-stat">
            <div className="eu-stat-lbl"><Icon name="badge-check" />Reembolsado {new Date().getFullYear()}</div>
            {res.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(d?.reembolsado_anio || 0)}</div>}
            <div className="t-meta">Depósitos ligados a lotes</div>
          </div>
        </div>
        <div className="eu-hstack">
          <a className="eu-btn eu-btn--ghost" href={`${BASE}/expense/export.csv`} download><Icon name="download" />Descargar CSV</a>
          <button type="button" className="eu-btn eu-btn--primary" onClick={() => setModal({ kind: 'new' })} disabled={!cand.data}>
            <Icon name="plus" />Nuevo lote
          </button>
        </div>
      </div>

      {sueltosPend.length > 0 && (
        <div className="fz-note" data-tone="info" role="note">
          <Icon name="files" size={16} />
          <span className="eu-grow">{plural(sueltosPend.length, 'factura pendiente no está', 'facturas pendientes no están')} en ningún lote · {money(sueltosPend.reduce((s, g) => s + g.monto, 0))}</span>
          <button type="button" className="fz-link" onClick={() => setModal({ kind: 'new' })}>Armar lote<Icon name="arrow-right" size={14} /></button>
        </div>
      )}

      <ErrorNote error={res.error} onRetry={res.reload} />
      {res.loading ? <Skel rows={3} h={120} /> : !d || d.lotes.length === 0 ? (
        <Empty icon="receipt" title="Sin lotes todavía"
          text="Cuando subas un grupo de facturas a la empresa, júntalas en un lote; al llegar el depósito lo ligas y el lote queda reembolsado.">
          <button type="button" className="eu-btn eu-btn--primary" onClick={() => setModal({ kind: 'new' })} disabled={!cand.data}><Icon name="plus" />Nuevo lote</button>
        </Empty>
      ) : (
        <div className="eu-vstack fz-gap-3">
          {d.lotes.map((l) => <LoteCard key={l.id} l={l} cand={cand.data} saved={saved} open={setModal} />)}
        </div>
      )}

      {modal?.kind === 'new' && cand.data && <NuevoLote cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
      {modal?.kind === 'add' && cand.data && <AgregarFacturas lote={modal.lote} cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
      {modal?.kind === 'dep' && cand.data && <LigarDeposito lote={modal.lote} cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
    </div>
  );
}
