import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { fmtDate, money, norm } from '../lib/format.js';
import { bankName, catMeta } from '../lib/meta.js';
import { categoryKeys, getCategories, subcatsFor } from '../lib/store.js';
import { CatBadge, Empty, ErrorNote, Field, Icon, Skel, confirmDialog, toast, useLoad } from '../components/ui.jsx';

function Audits() {
  const app = useApp();
  const dup = useLoad(() => api.admin('/audit-duplicados'), [app.refreshKey]);
  const nom = useLoad(() => api.admin('/audit-nomina-sospechosa'), [app.refreshKey]);
  const [busy, setBusy] = useState({});

  async function delDup(mv) {
    const ok = await confirmDialog(`¿Borrar «${mv.descripcion}»? No se puede deshacer.`, { confirmLabel: 'Borrar', danger: true });
    if (!ok) return;
    setBusy((b) => ({ ...b, [mv.id]: true }));
    try { await api.del(`/transactions/${mv.id}`); toast('Movimiento borrado', 'ok'); dup.reload(); app.refresh(); }
    catch (e) { toast(e.message || 'No se pudo borrar', 'err'); }
    finally { setBusy((b) => ({ ...b, [mv.id]: false })); }
  }
  const find = (desc) => app.goTo('movimientos', { search: desc });

  const d = dup.data;
  const n = nom.data;
  if (!(d && d.grupos_duplicados > 0) && !(n && n.total_sospechosas > 0)) return null;
  return (
    <div className="fz-vstack-lg">
      <h2 className="t-section">Revisión</h2>
      {d && d.grupos_duplicados > 0 && (
        <div className="eu-card eu-card--flush" data-tone="warning">
          <div className="fz-card-hd">
            <div className="eu-hstack fz-tone-fg"><Icon name="copy" size={16} /><h3 className="t-card">Posibles duplicados</h3></div>
            <p className="t-meta fz-mt-1">{d.grupos_duplicados} grupo{d.grupos_duplicados === 1 ? '' : 's'} con el mismo día y monto. Pueden ser compras reales iguales: revisa antes de borrar.</p>
          </div>
          {d.duplicados.map((g) => (
            <div key={`${g.fecha}${g.monto}`} className="fz-dup">
              <div className="fz-day"><span>{fmtDate(g.fecha)}</span><span className="num">{money(g.monto)}</span></div>
              <div className="eu-list">
                {g.movimientos.map((mv) => (
                  <div key={mv.id} className="eu-row">
                    <div className="eu-row-main">
                      <div className="eu-row-t">{mv.descripcion}</div>
                      <div className="eu-row-s">{bankName(mv.banco)} · {mv.tipo} · {catMeta(mv.categoria).name}{mv.subcategoria ? ` · ${mv.subcategoria}` : ''}</div>
                    </div>
                    <button type="button" className="eu-iconbtn" aria-label={`Buscar «${mv.descripcion}» en Movimientos`} title="Ver en Movimientos" onClick={() => find(mv.descripcion)}><Icon name="search" /></button>
                    <button type="button" className="eu-iconbtn" aria-label={`Borrar «${mv.descripcion}»`} title="Borrar" disabled={busy[mv.id]} onClick={() => delDup(mv)}><Icon name="trash-2" /></button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {n && n.total_sospechosas > 0 && (
        <div className="eu-card eu-card--flush" data-tone="warning">
          <div className="fz-card-hd">
            <div className="eu-hstack fz-tone-fg"><Icon name="triangle-alert" size={16} /><h3 className="t-card">Nómina sospechosa</h3></div>
            <p className="t-meta fz-mt-1">{n.total_sospechosas} movimiento{n.total_sospechosas === 1 ? '' : 's'} en Nómina fuera del rango habitual ($9,000–$12,000). Corrígelos desde Movimientos.</p>
          </div>
          <div className="eu-list">
            {n.movimientos.map((mv) => (
              <button key={mv.id} type="button" className="eu-row eu-row--interactive fz-row-btn" onClick={() => find(mv.descripcion)}>
                <div className="eu-row-main">
                  <div className="eu-row-t">{mv.descripcion}</div>
                  <div className="eu-row-s">{fmtDate(mv.fecha)} · {bankName(mv.banco)} · {mv.tipo}{mv.subcategoria ? ` · ${mv.subcategoria}` : ''}</div>
                </div>
                <div className="eu-row-end"><span className="t-data">{money(mv.monto)}</span></div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Contrapartes: quién está detrás de cada cuenta BNET (últimos 4 dígitos).
function catOptions(cats) {
  const out = [];
  categoryKeys(cats).forEach((k) => {
    out.push({ v: `${k}/`, l: catMeta(k).name });
    subcatsFor(cats, k).forEach((s) => out.push({ v: `${k}/${s}`, l: `${catMeta(k).name} · ${s}` }));
  });
  return out;
}
const catLabel = (opts, v) => (opts.find((o) => o.v === v) || { l: v }).l;
const NUEVA = { cuenta: '', nombre: '', alias: '', cat_abono: '', cat_cargo: '', reglas: [], auto: false };

function Contrapartes({ cats }) {
  const app = useApp();
  const list = useLoad(() => api.get('/contrapartes'), [app.refreshKey]);
  const [ed, setEd] = useState(null);   // contraparte en edición
  const [regla, setRegla] = useState({ palabra: '', lado: 'abono', cat: '' });
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const opts = catOptions(cats);

  const edit = (c) => { setErr(''); setRegla({ palabra: '', lado: 'abono', cat: '' }); setEd(c ? { ...c, alias: (c.alias || []).join(', ') } : { ...NUEVA }); };
  const set = (k, v) => setEd((e) => ({ ...e, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setBusy(true); setErr('');
    try {
      await api.post('/contrapartes', ed);
      toast(`Contraparte …${ed.cuenta.slice(-4)} guardada`, 'ok');
      setEd(null); list.reload(); app.refresh();
    } catch (ex) { setErr(ex.message || 'No se pudo guardar.'); }
    setBusy(false);
  }
  async function remove(c) {
    const ok = await confirmDialog(`¿Quitar a ${c.nombre} (…${c.cuenta})? Sus movimientos se quedan como están, solo sin nombre.`, { confirmLabel: 'Quitar', danger: true });
    if (!ok) return;
    try { await api.del(`/contrapartes/${c.cuenta}`); toast('Contraparte quitada', 'ok'); list.reload(); app.refresh(); }
    catch (ex) { toast(ex.message || 'No se pudo quitar', 'err'); }
  }
  const addRegla = () => {
    if (!regla.palabra.trim() || !regla.cat) return;
    set('reglas', [...(ed.reglas || []), [regla.palabra.trim().toUpperCase(), regla.lado, regla.cat]]);
    setRegla({ palabra: '', lado: 'abono', cat: '' });
  };

  return (
    <div className="eu-card eu-card--flush">
      <div className="eu-between fz-card-hd fz-wrap">
        <div><h3 className="t-card">Contrapartes</h3>
          <p className="t-meta fz-mt-1">Quién está detrás de cada cuenta (últimos 4 dígitos que pone BBVA: «BNET …6230»). Un alias en el concepto gana sobre la cuenta («regreso al corner» es de Cornelius aunque vaya a otra cuenta).</p></div>
        <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" onClick={() => edit(null)}><Icon name="plus" />Agregar</button>
      </div>
      <ErrorNote error={list.error} onRetry={list.reload} />
      {ed && (
        <form className="fz-pad fz-vstack" onSubmit={save} noValidate>
          <div className="fz-rule-form">
            <Field label="Últimos 4 dígitos" htmlFor="fz-cp-c" error={err}>
              <input id="fz-cp-c" className="eu-input num" inputMode="numeric" maxLength={4} value={ed.cuenta} onChange={(e) => set('cuenta', e.target.value.replace(/\D/g, ''))} placeholder="6230" />
            </Field>
            <Field label="Nombre" htmlFor="fz-cp-n"><input id="fz-cp-n" className="eu-input" value={ed.nombre} onChange={(e) => set('nombre', e.target.value)} placeholder="Judith" /></Field>
            <Field label="Alias (separados por coma)" htmlFor="fz-cp-a"><input id="fz-cp-a" className="eu-input" value={ed.alias} onChange={(e) => set('alias', e.target.value)} placeholder="Judi, Judicial" /></Field>
          </div>
          <div className="fz-rule-form">
            <Field label="Lo que te manda" htmlFor="fz-cp-ab">
              <select id="fz-cp-ab" className="eu-select" value={ed.cat_abono} onChange={(e) => set('cat_abono', e.target.value)}>
                <option value="">— Sin sugerencia —</option>
                {opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </Field>
            <Field label="Lo que le mandas" htmlFor="fz-cp-ca">
              <select id="fz-cp-ca" className="eu-select" value={ed.cat_cargo} onChange={(e) => set('cat_cargo', e.target.value)}>
                <option value="">— Sin sugerencia —</option>
                {opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </Field>
            <label className="eu-hstack t-ui"><input type="checkbox" checked={!!ed.auto} onChange={(e) => set('auto', e.target.checked)} />Aplicarla sola (si no, solo se sugiere)</label>
          </div>
          <div className="t-meta">Reglas por palabra del concepto</div>
          <div className="eu-hstack fz-wrap">
            {(ed.reglas || []).map(([p, l, c], i) => (
              <span key={`${p}${l}${i}`} className="eu-badge">{l === 'abono' ? 'Te manda' : 'Le mandas'} «{p}» → {catLabel(opts, c)}
                <button type="button" className="fz-link" aria-label={`Quitar regla ${p}`} onClick={() => set('reglas', ed.reglas.filter((_, j) => j !== i))}><Icon name="x" /></button></span>
            ))}
          </div>
          <div className="fz-rule-form">
            <Field label="Palabra" htmlFor="fz-cp-rp"><input id="fz-cp-rp" className="eu-input" value={regla.palabra} onChange={(e) => setRegla((r) => ({ ...r, palabra: e.target.value }))} placeholder="SEGURO" /></Field>
            <Field label="Cuando" htmlFor="fz-cp-rl">
              <select id="fz-cp-rl" className="eu-select" value={regla.lado} onChange={(e) => setRegla((r) => ({ ...r, lado: e.target.value }))}>
                <option value="abono">Te manda</option><option value="cargo">Le mandas</option>
              </select>
            </Field>
            <Field label="Categoría" htmlFor="fz-cp-rc">
              <select id="fz-cp-rc" className="eu-select" value={regla.cat} onChange={(e) => setRegla((r) => ({ ...r, cat: e.target.value }))}>
                <option value="">—</option>
                {opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </Field>
            <div className="fz-rule-form-end"><button type="button" className="eu-btn eu-btn--ghost" onClick={addRegla}><Icon name="plus" />Regla</button></div>
          </div>
          <div className="eu-hstack">
            <button type="submit" className="eu-btn eu-btn--primary" disabled={busy} aria-busy={busy || undefined}>Guardar</button>
            <button type="button" className="eu-btn eu-btn--ghost" onClick={() => setEd(null)}>Cancelar</button>
          </div>
        </form>
      )}
      {list.loading ? <div className="fz-pad"><Skel rows={3} h={44} /></div> : (
        <div className="eu-list">
          {(list.data?.data || []).map((c) => (
            <div key={c.cuenta} className="eu-row">
              <div className="eu-row-main">
                <div className="eu-row-t">{c.nombre} <span className="num fg-3">…{c.cuenta}</span></div>
                <div className="eu-row-s">
                  {c.alias.length > 0 && <span>{c.alias.join(', ')}</span>}
                  {c.cat_abono && <span>· te manda → {catLabel(opts, c.cat_abono)}{c.auto ? ' (sola)' : ''}</span>}
                  {c.reglas.length > 0 && <span>· {c.reglas.length} regla{c.reglas.length === 1 ? '' : 's'}</span>}
                  <button type="button" className="fz-link" onClick={() => app.goTo('movimientos', { contraparte: c.cuenta })}>{c.movimientos} movimiento{c.movimientos === 1 ? '' : 's'}</button>
                </div>
              </div>
              <button type="button" className="eu-iconbtn" aria-label={`Editar a ${c.nombre}`} title="Editar" onClick={() => edit(c)}><Icon name="pencil" /></button>
              <button type="button" className="eu-iconbtn" aria-label={`Quitar a ${c.nombre}`} title="Quitar" onClick={() => remove(c)}><Icon name="trash-2" /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Reglas() {
  const app = useApp();
  const rules = useLoad(() => api.get('/keywords'), [app.refreshKey]);
  const [cats, setCats] = useState([]);
  const [kw, setKw] = useState('');
  const [categoria, setCategoria] = useState('');
  const [sub, setSub] = useState('');
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { getCategories().then((c) => { setCats(c); setCategoria((v) => v || (c[0] && c[0].categoria) || 'OTROS'); }).catch(() => {}); }, []);

  const subs = subcatsFor(cats, categoria, 'GASTO');
  const list = (rules.data || []).filter((r) => !q.trim() || norm(`${r.keyword} ${r.categoria} ${r.subcategoria || ''} ${catMeta(r.categoria).name}`).includes(norm(q.trim())));

  async function add(e) {
    e.preventDefault();
    if (!kw.trim()) { setErr('Escribe una palabra clave.'); return; }
    setBusy(true); setErr('');
    try {
      const d = await api.post('/keywords', { keyword: kw.trim(), categoria, subcategoria: sub, apply_to_existing: true });
      toast(`Regla guardada · ${d.updated_transactions || 0} movimiento(s) actualizados`, 'ok');
      setKw(''); setSub('');
      rules.reload(); app.refresh();
    } catch (ex) { setErr(ex.message || 'Error al guardar.'); }
    setBusy(false);
  }

  async function applyAll() {
    setBusy(true);
    try {
      const d = await api.post('/keywords/apply-all', {});
      toast(`${d.updated_transactions || 0} movimiento(s) actualizados`, 'ok');
      app.refresh();
    } catch (ex) { toast(ex.message || 'No se pudo aplicar', 'err'); }
    setBusy(false);
  }

  async function remove(r) {
    const ok = await confirmDialog(`¿Eliminar la regla «${r.keyword}»? Los movimientos ya clasificados no cambian.`, { confirmLabel: 'Eliminar', danger: true });
    if (!ok) return;
    try { await api.del(`/keywords/${encodeURIComponent(r.keyword)}`); toast('Regla eliminada', 'ok'); rules.reload(); }
    catch (ex) { toast(ex.message || 'No se pudo eliminar', 'err'); }
  }

  return (
    <div className="fz-vstack-lg">
      <div className="eu-between fz-wrap">
        <div><h2 className="t-section">Reglas de clasificación</h2><div className="t-meta">Si la descripción contiene la palabra clave, el movimiento se clasifica solo al importar.</div></div>
        <button type="button" className="eu-btn eu-btn--secondary" onClick={applyAll} disabled={busy} aria-busy={busy || undefined}><Icon name="wand-sparkles" />Aplicar todas a lo existente</button>
      </div>

      <form className="eu-card fz-rule-form" onSubmit={add} noValidate>
        <Field label="Palabra clave" htmlFor="fz-r-kw" error={err}>
          <input id="fz-r-kw" className="eu-input" value={kw} onChange={(e) => setKw(e.target.value)} placeholder="Ej. FIBRA HOTELERA" autoCapitalize="characters" />
        </Field>
        <Field label="Categoría" htmlFor="fz-r-cat">
          <select id="fz-r-cat" className="eu-select" value={categoria} onChange={(e) => { setCategoria(e.target.value); setSub(''); }}>
            {categoryKeys(cats).map((k) => <option key={k} value={k}>{catMeta(k).name}</option>)}
          </select>
        </Field>
        <Field label="Subcategoría (opcional)" htmlFor="fz-r-sub">
          <select id="fz-r-sub" className="eu-select" value={sub} onChange={(e) => setSub(e.target.value)} disabled={!subs.length}>
            <option value="">— Sin subcategoría —</option>
            {subs.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <div className="fz-rule-form-end">
          <button type="submit" className="eu-btn eu-btn--primary" disabled={busy}><Icon name="plus" />Agregar</button>
        </div>
      </form>

      <div className="eu-card eu-card--flush">
        <div className="eu-between fz-card-hd fz-wrap">
          <h3 className="t-card">{(rules.data || []).length} regla{(rules.data || []).length === 1 ? '' : 's'}</h3>
          <div className="eu-input-wrap fz-rules-search">
            <Icon name="search" />
            <input className="eu-input fz-input-sm" type="search" placeholder="Filtrar reglas" aria-label="Filtrar reglas" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
        <ErrorNote error={rules.error} onRetry={rules.reload} />
        {rules.loading ? <div className="fz-pad"><Skel rows={4} h={44} /></div> : list.length === 0 ? (
          <Empty icon="wand-sparkles" title={q ? 'Ninguna regla coincide' : 'Sin reglas todavía'} text={q ? 'Prueba con otra palabra.' : 'Crea la primera arriba o desde el drawer de un movimiento.'} />
        ) : (
          <div className="eu-list">
            {list.map((r) => (
              <div key={r.keyword} className="eu-row">
                <div className="eu-row-main">
                  <div className="eu-row-t num">{r.keyword}</div>
                  <div className="eu-row-s"><CatBadge cat={r.categoria} />{r.subcategoria && <span>{r.subcategoria}</span>}</div>
                </div>
                <button type="button" className="eu-iconbtn" aria-label={`Eliminar la regla ${r.keyword}`} title="Eliminar" onClick={() => remove(r)}><Icon name="trash-2" /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      <Contrapartes cats={cats} />

      <Audits />
    </div>
  );
}
