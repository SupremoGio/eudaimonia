import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { dayLabel, fmtDate, money } from '../lib/format.js';
import { BANKS, TIPOS, bankName, catMeta } from '../lib/meta.js';
import { categoryKeys, getCategories, getTrips } from '../lib/store.js';
import { CatBadge, CatIcon, Empty, ErrorNote, Icon, Modal, Skel, useMedia } from '../components/ui.jsx';
import Categorizer from '../components/Categorizer.jsx';

const PAGE = 50;
const EMPTY = { search: '', tipo: '', category: '', bank: '', date_from: '', date_to: '' };

function Amount({ t, mode }) {
  const ingreso = t.tipo === 'INGRESO';
  const hasParte = t.mi_parte != null && Math.abs(t.mi_parte) !== Math.abs(t.monto);
  const main = mode === 'mi_parte' && t.mi_parte != null ? Math.abs(t.mi_parte) : Math.abs(t.monto);
  const alt = mode === 'mi_parte' ? Math.abs(t.monto) : Math.abs(t.mi_parte);
  return (
    <>
      <span className={`eu-amt${ingreso ? ' pos' : ''}`}>{ingreso ? '+' : '−'}{money(main)}</span>
      {hasParte && <div className="t-meta fz-nowrap">{mode === 'mi_parte' ? `de ${money(alt)}` : `tuyo ${money(alt)}`}</div>}
    </>
  );
}

function Flags({ t }) {
  return (
    <>
      {t.parcialidad_num && t.parcialidad_total ? <span className="eu-badge eu-badge--info">MSI {t.parcialidad_num}/{t.parcialidad_total}</span> : null}
      {t.mi_parte != null && Math.abs(t.mi_parte) !== Math.abs(t.monto) ? <span className="eu-badge eu-badge--info"><Icon name="users" />Tu parte</span> : null}
    </>
  );
}

export default function Movimientos({ initial }) {
  const app = useApp();
  const desktop = useMedia('(min-width: 1024px)');
  const [f, setF] = useState(() => ({ ...EMPTY, ...(initial || {}) }));
  const [searchDraft, setSearchDraft] = useState(f.search);
  const [page, setPage] = useState(0);
  const [mode, setMode] = useState('completo');
  const [showFilters, setShowFilters] = useState(() => !!(initial && (initial.bank || initial.tipo || initial.date_from)));
  const [st, setSt] = useState({ rows: [], total: 0, loading: true, error: null });
  const [sel, setSel] = useState(null); // id seleccionado
  const [cats, setCats] = useState([]);
  const [trips, setTrips] = useState([]);
  const [banks, setBanks] = useState([]);
  const tableRef = useRef(null);

  useEffect(() => {
    getCategories().then(setCats).catch(() => {});
    getTrips().then(setTrips);
    api.get('/summary/banks').then((b) => setBanks(b || [])).catch(() => {});
  }, []);

  // Búsqueda con debounce: no se pide a la API en cada tecla.
  useEffect(() => {
    const h = setTimeout(() => { setF((s) => (s.search === searchDraft ? s : { ...s, search: searchDraft })); setPage(0); }, 300);
    return () => clearTimeout(h);
  }, [searchDraft]);

  const load = useCallback(() => {
    setSt((s) => ({ ...s, loading: true, error: null }));
    return api.get('/transactions', { ...f, limit: PAGE, offset: page * PAGE })
      .then((d) => setSt({ rows: d.data || [], total: d.total || 0, loading: false, error: null }))
      .catch((error) => setSt((s) => ({ ...s, loading: false, error })));
  }, [f, page]);
  useEffect(() => { load(); }, [load, app.refreshKey]);

  const setFilter = (k, v) => { setF((s) => ({ ...s, [k]: v })); setPage(0); };
  const clear = () => { setF(EMPTY); setSearchDraft(''); setPage(0); };
  const active = ['tipo', 'bank', 'date_from', 'date_to'].filter((k) => f[k]).length + (f.category && f.category !== 'OTROS' ? 1 : 0);
  const anyFilter = active > 0 || f.search || f.category;

  const rows = st.rows;
  const idx = rows.findIndex((r) => r.id === sel);
  const current = idx >= 0 ? rows[idx] : null;
  const go = (d) => { const n = rows[idx + d]; if (n) setSel(n.id); };

  // j/k o flechas navegan entre movimientos mientras el drawer está abierto.
  useEffect(() => {
    if (!desktop || !current) return undefined;
    const on = (e) => {
      if (/INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName || '') || e.metaKey || e.ctrlKey || e.altKey) return;
      if (document.querySelector('.fz-scrim')) return;
      if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); go(1); }
      else if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); go(-1); }
      else if (e.key === 'Escape') setSel(null);
    };
    document.addEventListener('keydown', on);
    return () => document.removeEventListener('keydown', on);
  });

  const onSaved = (upd, { advance }) => {
    const next = advance ? rows[idx + 1] : null;
    setSt((s) => ({ ...s, rows: s.rows.map((r) => (r.id === upd.id ? { ...r, ...upd } : r)) }));
    if (!desktop) setSel(null);
    else if (next) setSel(next.id);
    app.refresh();
  };

  const groups = useMemo(() => {
    const g = [];
    rows.forEach((t) => {
      const last = g[g.length - 1];
      if (last && last.fecha === t.fecha) last.items.push(t);
      else g.push({ fecha: t.fecha, items: [t] });
    });
    return g.map((d) => ({ ...d, net: d.items.reduce((s, t) => s + (t.tipo === 'INGRESO' ? 1 : t.tipo === 'GASTO' ? -1 : 0) * Math.abs(t.monto), 0) }));
  }, [rows]);

  const bankOpts = [...new Set([...BANKS.map((b) => b.id), ...banks])];
  const catKeys = categoryKeys(cats).filter((k) => k !== 'OTROS');
  const from = st.total ? page * PAGE + 1 : 0;
  const to = Math.min(st.total, (page + 1) * PAGE);

  const toolbar = (
    <div className="fz-mv-tools">
      <div className="eu-input-wrap fz-mv-search">
        <Icon name="search" />
        <input className="eu-input fz-input-sm" type="search" placeholder="Buscar comercio o descripción" aria-label="Buscar movimientos"
          value={searchDraft} onChange={(e) => setSearchDraft(e.target.value)} />
      </div>
      <div className="eu-chips" role="group" aria-label="Filtro rápido">
        <button type="button" className="eu-chip" aria-pressed={!f.category} onClick={() => setFilter('category', '')}>
          Todo {!f.category && st.total > 0 && <span className="ct">{st.total}</span>}
        </button>
        <button type="button" className="eu-chip" aria-pressed={f.category === 'OTROS'} onClick={() => setFilter('category', f.category === 'OTROS' ? '' : 'OTROS')}>
          Sin categoría {f.category === 'OTROS' ? <span className="ct">{st.total}</span> : app.unclassified > 0 && <span className="ct">{app.unclassified}</span>}
        </button>
        <button type="button" className="eu-chip" aria-pressed={showFilters} aria-expanded={showFilters} aria-controls="fz-mv-filters" onClick={() => setShowFilters((v) => !v)}>
          <Icon name="sliders-horizontal" />Filtros{active > 0 && <span className="ct">{active}</span>}
        </button>
      </div>
      <div className="eu-hstack fz-mv-actions">
        <div className="eu-seg" role="radiogroup" aria-label="Ver montos">
          <button type="button" role="radio" aria-checked={mode === 'completo'} onClick={() => setMode('completo')}>Completo</button>
          <button type="button" role="radio" aria-checked={mode === 'mi_parte'} onClick={() => setMode('mi_parte')}>Mi parte</button>
        </div>
        <a className="eu-btn eu-btn--ghost eu-btn--sm" href={api.csvUrl({ ...f })} download><Icon name="download" />CSV</a>
      </div>
    </div>
  );

  const filters = showFilters && (
    <div className="eu-card eu-card--inset fz-mv-filters" id="fz-mv-filters">
      <div className="eu-field"><label className="eu-label" htmlFor="fz-f-tipo">Tipo</label>
        <select id="fz-f-tipo" className="eu-select fz-input-sm" value={f.tipo} onChange={(e) => setFilter('tipo', e.target.value)}>
          <option value="">Todos</option>
          {TIPOS.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></div>
      <div className="eu-field"><label className="eu-label" htmlFor="fz-f-cat">Categoría</label>
        <select id="fz-f-cat" className="eu-select fz-input-sm" value={f.category} onChange={(e) => setFilter('category', e.target.value)}>
          <option value="">Todas</option>
          <option value="OTROS">Sin clasificar</option>
          {catKeys.map((k) => <option key={k} value={k}>{catMeta(k).name}</option>)}
          {f.category && f.category !== 'OTROS' && !catKeys.includes(f.category) && <option value={f.category}>{catMeta(f.category).name}</option>}
        </select></div>
      <div className="eu-field"><label className="eu-label" htmlFor="fz-f-bank">Cuenta</label>
        <select id="fz-f-bank" className="eu-select fz-input-sm" value={f.bank} onChange={(e) => setFilter('bank', e.target.value)}>
          <option value="">Todas</option>
          {bankOpts.map((b) => <option key={b} value={b}>{bankName(b)}</option>)}
        </select></div>
      <div className="eu-field"><label className="eu-label" htmlFor="fz-f-from">Desde</label>
        <input id="fz-f-from" type="date" className="eu-input fz-input-sm" value={f.date_from} onChange={(e) => setFilter('date_from', e.target.value)} /></div>
      <div className="eu-field"><label className="eu-label" htmlFor="fz-f-to">Hasta</label>
        <input id="fz-f-to" type="date" className="eu-input fz-input-sm" value={f.date_to} onChange={(e) => setFilter('date_to', e.target.value)} /></div>
      <div className="fz-mv-filters-end">
        <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={clear} disabled={!anyFilter}><Icon name="rotate-ccw" />Limpiar</button>
      </div>
    </div>
  );

  const pager = st.total > PAGE && (
    <div className="eu-between fz-pager">
      <span className="t-meta">{from}–{to} de {st.total}</span>
      <div className="eu-hstack">
        <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" disabled={page === 0} onClick={() => { setPage((p) => p - 1); setSel(null); }}><Icon name="chevron-left" />Anterior</button>
        <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" disabled={to >= st.total} onClick={() => { setPage((p) => p + 1); setSel(null); }}>Siguiente<Icon name="chevron-right" /></button>
      </div>
    </div>
  );

  let body;
  if (st.loading && !rows.length) body = <Skel rows={6} h={48} />;
  else if (!rows.length) {
    body = (
      <Empty icon={anyFilter ? 'search-x' : 'receipt'} title={anyFilter ? 'Nada coincide' : 'Aún no hay movimientos'}
        text={anyFilter ? 'Prueba con otros filtros o limpia la búsqueda.' : 'Sube tu primer estado de cuenta o captura un movimiento.'}>
        {anyFilter
          ? <button type="button" className="eu-btn eu-btn--secondary" onClick={clear}>Limpiar filtros</button>
          : <button type="button" className="eu-btn eu-btn--primary" onClick={app.openImport}><Icon name="upload" />Subir estado de cuenta</button>}
      </Empty>
    );
  } else if (desktop) {
    body = (
      <div className="fz-table-wrap" ref={tableRef} aria-busy={st.loading || undefined}>
        <table className="eu-table fz-mv-table">
          <thead><tr><th className="fz-col-date">Fecha</th><th>Comercio</th><th>Categoría</th><th>Cuenta</th><th className="r">Monto</th></tr></thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="fz-tr" tabIndex={0} aria-selected={t.id === sel}
                onClick={() => setSel(t.id === sel ? null : t.id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSel(t.id); } }}>
                <td className="num fg-3 fz-td-date">{fmtDate(t.fecha, true)}</td>
                <td>
                  <span className="fz-td-merchant">
                    <CatIcon cat={t.categoria} size="sm" />
                    <span className="fz-minw0">
                      <span className="fz-ellipsis fz-td-desc">{t.descripcion}</span>
                      <span className="fz-td-flags"><Flags t={t} /></span>
                    </span>
                  </span>
                </td>
                <td>
                  <CatBadge cat={t.categoria} />
                  {t.subcategoria && <div className="t-meta fz-ellipsis">{t.subcategoria}</div>}
                </td>
                <td className="fg-3 fz-td-bank">{bankName(t.banco)}</td>
                <td className="r"><Amount t={t} mode={mode} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  } else {
    body = (
      <div className="fz-days" aria-busy={st.loading || undefined}>
        {groups.map((g) => (
          <section key={g.fecha} aria-label={dayLabel(g.fecha)}>
            <div className="fz-day"><span>{dayLabel(g.fecha)}</span>{g.net !== 0 && <span className="num">{money(g.net, { sign: true })}</span>}</div>
            <div className="eu-list">
              {g.items.map((t) => (
                <button key={t.id} type="button" className="eu-row eu-row--interactive fz-row-btn" onClick={() => setSel(t.id)}>
                  <CatIcon cat={t.categoria} />
                  <div className="eu-row-main">
                    <div className="eu-row-t">{t.descripcion}</div>
                    <div className="eu-row-s">
                      {t.categoria === 'OTROS' || !t.categoria ? <span className="eu-badge eu-badge--warning">Sin categoría</span> : <span>{catMeta(t.categoria).name}{t.subcategoria ? ` · ${t.subcategoria}` : ''}</span>}
                      <span>· {bankName(t.banco)}</span>
                      <Flags t={t} />
                    </div>
                  </div>
                  <div className="eu-row-end"><Amount t={t} mode={mode} /></div>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    );
  }

  const drawerOpen = desktop && current;
  return (
    <div className="fz-mv">
      <div className="fz-mv-main">
        {toolbar}
        {filters}
        <ErrorNote error={st.error} onRetry={load} />
        <div className="eu-between t-meta fz-mv-meta">
          <span>{st.total} movimiento{st.total === 1 ? '' : 's'}{f.category === 'OTROS' ? ' sin clasificar' : ''}</span>
          {desktop && <span className="fz-hide-md">Clic en una fila para categorizar · <span className="kbd">j</span> <span className="kbd">k</span> para moverte</span>}
        </div>
        <div className={desktop ? 'eu-card eu-card--flush' : 'eu-card eu-card--flush fz-mv-card-m'}>{body}</div>
        {pager}
      </div>

      {drawerOpen && (
        <aside className="fz-drawer" aria-labelledby="fz-dr-t">
          <Categorizer tx={current} cats={cats} trips={trips} variant="drawer" headingId="fz-dr-t"
            onSaved={onSaved} onClose={() => setSel(null)} onMore={() => app.openTx(current)}
            onPrev={idx > 0 ? () => go(-1) : null} onNext={idx < rows.length - 1 ? () => go(1) : null} />
        </aside>
      )}

      {!desktop && current && (
        <Modal title="Categorizar" eyebrow={dayLabel(current.fecha)} onClose={() => setSel(null)} initialFocus={false}>
          <div className="eu-modal-bd">
            <Categorizer tx={current} cats={cats} trips={trips} variant="sheet" headingId="fz-sh-t"
              onSaved={onSaved} onClose={() => setSel(null)} onMore={() => { const t = current; setSel(null); app.openTx(t); }} />
          </div>
        </Modal>
      )}

    </div>
  );
}

