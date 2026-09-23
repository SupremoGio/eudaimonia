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

      <Audits />
    </div>
  );
}
