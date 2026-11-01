import { useMemo, useState } from 'react';
import { BASE, api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { fmtDate, money, norm } from '../lib/format.js';
import { bankName } from '../lib/meta.js';
import { Empty, ErrorNote, Field, Icon, Modal, Progress, Skel, confirmDialog, toast, useLoad } from '../components/ui.jsx';

// Conciliación de Expense por lotes (solo PC). Varias facturas se suben
// juntas y la empresa paga un depósito (o varios) por el lote. El estado se
// calcula solo y marca las facturas como Pagado cuando el lote queda cubierto;
// las «Pagado a compañero» conservan su estatus.

const TONE = { Pendiente: 'warning', 'Reembolsado parcial': 'info', Reembolsado: 'success', 'Sin gastos': 'neutral', Cerrado: 'neutral' };
// Etiquetas en lenguaje llano: «conciliado» = el depósito de la empresa cubre las facturas del lote.
const ESTADO_LBL = { Pendiente: 'Esperando pago', 'Reembolsado parcial': 'Pago parcial', Reembolsado: 'Conciliado', 'Sin gastos': 'Vacío', Cerrado: 'Histórico · pagado' };
const ESTADO_ICON = { Pendiente: 'clock', 'Reembolsado parcial': 'circle-dashed', Reembolsado: 'circle-check', 'Sin gastos': 'circle', Cerrado: 'archive' };
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

/** Cuadre del lote: facturas vs. lo que ya depositó la empresa, con barra. */
function LoteBalance({ l }) {
  if (l.estado === 'Cerrado') {
    return (
      <div className="fz-ex-bal" data-tone="neutral">
        <div className="fz-ex-bal-row">
          <span><span className="t-meta">Facturas</span> <b className="num">{money(l.total)}</b></span>
          <span><span className="t-meta">Depósitos</span> <b className="num">{money(l.depositado)}</b></span>
        </div>
        <div className="t-meta">Cerrado sin conciliar · cuenta como pagado</div>
      </div>
    );
  }
  const pct = l.total > 0 ? (l.depositado / l.total) * 100 : 0;
  const ok = l.estado === 'Reembolsado';
  return (
    <div className="fz-ex-bal" data-tone={TONE[l.estado]}>
      <div className="fz-ex-bal-row">
        <span><span className="t-meta">Facturas</span> <b className="num">{money(l.total)}</b></span>
        <span><span className="t-meta">Recibido</span> <b className="num fg-success">{money(l.depositado)}</b></span>
      </div>
      <Progress className="fz-progress-tone" pct={pct} label={`${l.nombre}: recibido ${Math.round(pct)}%`} />
      <div className="t-meta fz-tone-fg">
        {ok
          ? (l.diferencia > 1 ? `✓ Cubierto · depositaron ${money(l.diferencia)} de más` : '✓ El depósito cubre todas las facturas')
          : l.depositado > 0 ? `Faltan ${money(l.pendiente)} por recibir` : `Falta ligar el depósito de ${money(l.pendiente)}`}
      </div>
    </div>
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
          <h2 className="t-card">{l.nombre} <span className={`eu-badge eu-badge--${TONE[l.estado]}`}><Icon name={ESTADO_ICON[l.estado]} size={12} />{ESTADO_LBL[l.estado] || l.estado}</span></h2>
          <span className="t-meta">
            {l.desde ? `${fmtDate(l.desde, true)} – ${fmtDate(l.hasta, true)} · ` : ''}{plural(l.gastos.length, 'factura', 'facturas')}
            {l.terceros > 0 ? ` · a compañeros ${money(l.terceros)}` : ''}{l.notas ? ` · ${l.notas}` : ''}
          </span>
        </div>
        <LoteBalance l={l} />
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
        {l.estado !== 'Reembolsado' && l.estado !== 'Cerrado' && (
          <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" onClick={() => open({ kind: 'dep', lote: l })} disabled={!cand}>Ligar depósito</button>
        )}
        {l.estado !== 'Cerrado' && (
          <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => open({ kind: 'add', lote: l })} disabled={!cand}>Agregar facturas</button>
        )}
        <span className="eu-grow" />
        <button type="button" className="eu-iconbtn" aria-label={`Borrar lote ${l.nombre}`} title="Borrar lote" onClick={borrar}><Icon name="trash-2" /></button>
      </div>
    </section>
  );
}

const CONF_TONE = { alta: 'success', media: 'warning', baja: 'danger', aproximada: 'info' };
const CONF_LBL = { alta: 'Confianza alta', media: 'Confianza media', baja: 'Confianza baja', aproximada: 'Aproximada · revisa la diferencia' };

/** Sugerencias automáticas: depósito de la empresa + facturas de hasta ~3
 * meses antes que suman lo mismo. Se confirma una por una o todas. */
function Sugerencias({ refreshKey, saved }) {
  const sug = useLoad(() => api.get('/expense/sugerencias'), [refreshKey]);
  const [abierta, setAbierta] = useState(null);
  const [busy, setBusy] = useState(false);
  const lista = sug.data || [];
  if (sug.loading || lista.length === 0) return null;

  async function crear(items) {
    setBusy(true);
    try {
      for (const s of items) {
        await api.post('/expense/lotes', {
          nombre: s.nombre, notas: 'Sugerido automáticamente',
          gasto_ids: s.facturas.map((f) => f.id), deposito_ids: (s.depositos || [s.deposito]).map((d) => d.id),
        });
      }
      toast(items.length === 1 ? 'Lote creado' : `${items.length} lotes creados`, 'ok');
      saved();
    } catch (e) { toast(e.message || 'No se pudo crear el lote', 'err'); }
    setBusy(false);
  }

  return (
    <section className="eu-card eu-card--flush" aria-label="Sugerencias de lotes">
      <div className="eu-between fz-card-hd fz-wrap">
        <div className="eu-vstack">
          <h2 className="t-card">Posibles coincidencias <span className="eu-badge eu-badge--info">{lista.length}</span></h2>
          <span className="t-meta">Encontré depósitos de la empresa que suman lo mismo que un grupo de tus facturas. Ábrelas para ver qué facturas son y confirma con «Crear lote».</span>
          <details className="t-meta fz-ex-how"><summary>¿Cómo las busco?</summary>
            Solo facturas que suman el depósito (±$1): primero tandas seguidas, luego combinaciones de hasta 3, 6 y 12 meses antes y pares de depósitos. Lo que no cuadra exacto no se sugiere: ármalo a mano.
          </details>
        </div>
        <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" disabled={busy || !lista.some((x) => x.confianza === 'alta')}
          onClick={() => crear(lista.filter((x) => x.confianza === 'alta'))} title="Solo las de confianza alta; las demás revísalas una por una">
          <Icon name="check-check" />Crear todas las de confianza alta
        </button>
      </div>
      <ul className="eu-list fz-list-inset">
        {lista.map((s) => (
          <li key={s.deposito.id} className="eu-vstack fz-gap-2 fz-pad">
            <div className="eu-between fz-wrap">
              <button type="button" className="fz-link eu-grow" aria-expanded={abierta === s.deposito.id} onClick={() => setAbierta(abierta === s.deposito.id ? null : s.deposito.id)}>
                <span className={`eu-badge eu-badge--${CONF_TONE[s.confianza] || 'info'}`}>{CONF_LBL[s.confianza] || s.confianza}</span>{' '}
                {(s.depositos || [s.deposito]).map((d, i) => (
                  <span key={d.id}>{i > 0 ? ' + ' : ''}<span className="num fg-3">{fmtDate(d.fecha, true)}</span> · {d.descripcion} · <b className="num fg-success">+{money(d.monto)}</b></span>
                ))}
                <span className="t-meta"> ← {plural(s.facturas.length, 'factura', 'facturas')} ({fmtDate(s.facturas[0].fecha, true)} – {fmtDate(s.facturas[s.facturas.length - 1].fecha, true)})
                  {Math.abs(s.diferencia) >= 0.01 ? ` · dif. ${money(s.diferencia)}` : ''}</span>
              </button>
              <button type="button" className="eu-btn eu-btn--primary eu-btn--sm" disabled={busy} onClick={() => crear([s])}>Crear lote</button>
            </div>
            {abierta === s.deposito.id && (
              <table className="eu-table fz-ex-table">
                <colgroup><col className="c-date" /><col /><col className="c-amt" /></colgroup>
                <tbody>
                  {s.facturas.map((f) => (
                    <tr key={f.id}><td className="num fg-3">{fmtDate(f.fecha, true)}</td><td><span className="fz-ellipsis fz-td-desc" title={f.descripcion}>{f.descripcion}</span></td><td className="r num">{money(f.monto)}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Lo que queda suelto después de las sugerencias: depósitos de la empresa
 * sin facturas que los cubran y facturas pendientes sin depósito. */
function Sueltos({ refreshKey, onNuevo }) {
  const res = useLoad(() => api.get('/expense/sueltos'), [refreshKey]);
  const d = res.data;
  if (res.loading || !d || (d.depositos.length === 0 && d.facturas.length === 0)) return null;
  const tabla = (rows, signo) => (
    <table className="eu-table fz-ex-table fz-sc-table">
      <colgroup><col className="c-date" /><col /><col className="c-amt" /></colgroup>
      <tbody>
        {rows.map((m) => (
          <tr key={m.id}>
            <td className="num fg-3">{fmtDate(m.fecha, true)}</td>
            <td><span className="fz-ellipsis fz-td-desc" title={m.descripcion}>{m.descripcion}</span></td>
            <td className={`r num${signo ? ' fg-success' : ''}`}>{signo}{money(m.monto)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <section className="eu-card eu-card--flush" aria-label="Quedan sueltos">
      <div className="eu-between fz-card-hd fz-wrap">
        <div className="eu-vstack">
          <h2 className="t-card">Sin pareja todavía</h2>
          <span className="t-meta">No encontré coincidencia automática para estos. Júntalos tú con «Nuevo lote»: elige las facturas y el depósito que las paga. Es normal si el depósito cubre facturas muy viejas o falta cargar alguna.</span>
        </div>
        <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={onNuevo}><Icon name="plus" />Nuevo lote</button>
      </div>
      {d.depositos.length > 0 && <details className="fz-pad" open={d.depositos.length <= 12}>
        <summary className="t-ui">{plural(d.depositos.length, 'depósito', 'depósitos')} de la empresa sin facturas · <b className="num fg-success">+{money(d.total_depositos)}</b></summary>
        {tabla(d.depositos, '+')}
      </details>}
      {d.facturas.length > 0 && <details className="fz-pad" open={d.facturas.length <= 12}>
        <summary className="t-ui">{plural(d.facturas.length, 'factura pendiente', 'facturas pendientes')} sin depósito · <b className="num">{money(d.total_facturas)}</b></summary>
        {tabla(d.facturas, '')}
      </details>}
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

  const abiertos = (d?.lotes || []).filter((l) => l.estado !== 'Reembolsado' && l.estado !== 'Cerrado');
  const historico = (d?.lotes || []).filter((l) => l.estado === 'Cerrado');
  const cerrados = (d?.lotes || []).filter((l) => l.estado === 'Reembolsado');
  const totalSueltos = sueltosPend.reduce((s, g) => s + g.monto, 0);
  const totalAbiertos = abiertos.reduce((s, l) => s + l.pendiente, 0);
  const nuevo = () => setModal({ kind: 'new' });

  return (
    <div className="fz-vstack-lg fz-pc">
      <div className="eu-between fz-wrap">
        <div className="eu-vstack">
          <span className="t-meta">Por cobrar a la empresa</span>
          {res.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(d?.por_cobrar || 0)}</div>}
          <span className="t-meta">Reembolsado en {new Date().getFullYear()}: <b className="num fg-success">{money(d?.reembolsado_anio || 0)}</b></span>
        </div>
        <div className="eu-hstack">
          <a className="eu-btn eu-btn--ghost" href={`${BASE}/expense/export.csv`} download><Icon name="download" />Descargar CSV</a>
          <button type="button" className="eu-btn eu-btn--primary" onClick={nuevo} disabled={!cand.data}>
            <Icon name="plus" />Nuevo lote
          </button>
        </div>
      </div>

      {/* El camino de una factura: sin lote → lote esperando pago → conciliado. */}
      <ol className="fz-ex-flow" aria-label="Cómo se concilia un gasto de trabajo">
        <li data-tone={sueltosPend.length ? 'warning' : 'neutral'}>
          <span className="fz-ex-step">1</span>
          <div className="eu-vstack">
            <b>Facturas sin lote</b>
            <span className="t-meta">Gastos de trabajo que aún no juntas para cobrar</span>
            <span className="fz-ex-flow-val">{res.loading ? '…' : <>{plural(sueltosPend.length, 'factura', 'facturas')} · <span className="num">{money(totalSueltos)}</span></>}</span>
            {sueltosPend.length > 0 && <button type="button" className="fz-link" onClick={nuevo} disabled={!cand.data}>Juntar en un lote<Icon name="arrow-right" size={14} /></button>}
          </div>
        </li>
        <li data-tone={abiertos.length ? 'info' : 'neutral'}>
          <span className="fz-ex-step">2</span>
          <div className="eu-vstack">
            <b>Esperando pago</b>
            <span className="t-meta">Lotes enviados; falta el depósito de la empresa</span>
            <span className="fz-ex-flow-val">{res.loading ? '…' : <>{plural(abiertos.length, 'lote', 'lotes')} · <span className="num">{money(totalAbiertos)}</span></>}</span>
          </div>
        </li>
        <li data-tone="success">
          <span className="fz-ex-step"><Icon name="check" size={14} /></span>
          <div className="eu-vstack">
            <b>Conciliado</b>
            <span className="t-meta">El depósito cubre el lote; sus facturas quedan Pagado</span>
            <span className="fz-ex-flow-val">{res.loading ? '…' : plural(cerrados.length, 'lote', 'lotes')}</span>
          </div>
        </li>
      </ol>

      <Sugerencias refreshKey={app.refreshKey} saved={saved} />
      <Sueltos refreshKey={app.refreshKey} onNuevo={nuevo} />

      <ErrorNote error={res.error} onRetry={res.reload} />
      {res.loading ? <Skel rows={3} h={120} /> : !d || d.lotes.length === 0 ? (
        <Empty icon="receipt" title="Sin lotes todavía"
          text="Cuando subas un grupo de facturas a la empresa, júntalas en un lote; al llegar el depósito lo ligas y el lote queda conciliado.">
          <button type="button" className="eu-btn eu-btn--primary" onClick={nuevo} disabled={!cand.data}><Icon name="plus" />Nuevo lote</button>
        </Empty>
      ) : (
        <>
          {abiertos.length > 0 && (
            <div className="eu-vstack fz-gap-3">
              <h2 className="t-card fz-ex-sec"><Icon name="clock" />Esperando pago <span className="t-meta">· liga el depósito cuando llegue</span></h2>
              {abiertos.map((l) => <LoteCard key={l.id} l={l} cand={cand.data} saved={saved} open={setModal} />)}
            </div>
          )}
          {cerrados.length > 0 && (
            <details className="fz-ex-done" open={abiertos.length === 0}>
              <summary className="t-card fz-ex-sec"><Icon name="circle-check" />Conciliados <span className="t-meta">· {plural(cerrados.length, 'lote', 'lotes')} cubiertos por su depósito</span></summary>
              <div className="eu-vstack fz-gap-3">
                {cerrados.map((l) => <LoteCard key={l.id} l={l} cand={cand.data} saved={saved} open={setModal} />)}
              </div>
            </details>
          )}
          {historico.length > 0 && (
            <details className="fz-ex-done">
              <summary className="t-card fz-ex-sec"><Icon name="archive" />Histórico cerrado <span className="t-meta">· 2025 y antes, marcado como pagado sin conciliar · {plural(historico.length, 'lote', 'lotes')} · {money(historico.reduce((s, l) => s + l.total, 0))}</span></summary>
              <div className="eu-vstack fz-gap-3">
                {historico.map((l) => <LoteCard key={l.id} l={l} cand={cand.data} saved={saved} open={setModal} />)}
              </div>
            </details>
          )}
        </>
      )}

      {modal?.kind === 'new' && cand.data && <NuevoLote cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
      {modal?.kind === 'add' && cand.data && <AgregarFacturas lote={modal.lote} cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
      {modal?.kind === 'dep' && cand.data && <LigarDeposito lote={modal.lote} cand={cand.data} onClose={() => setModal(null)} onSaved={saved} />}
    </div>
  );
}
