import { useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { fmtDate, money, myAmount, norm, pct } from '../lib/format.js';
import { bankName, catMeta } from '../lib/meta.js';
import { Empty, ErrorNote, Icon, Modal, Skel, useLoad, useMedia } from './ui.jsx';

const SORTS = [
  ['fecha_desc', 'Más recientes'], ['fecha_asc', 'Más antiguos'],
  ['monto_desc', 'Monto: mayor a menor'], ['monto_asc', 'Monto: menor a mayor'],
  ['estab_asc', 'Establecimiento A–Z'], ['estab_desc', 'Establecimiento Z–A'],
];
const SIN_SUB = '__SIN_SUB__';
const merchantOf = (t) => (t.descripcion || '').trim() || '(sin descripción)';

function sortRows(rows, key) {
  const r = [...rows];
  const cmp = {
    monto_desc: (a, b) => Math.abs(b.monto) - Math.abs(a.monto),
    monto_asc: (a, b) => Math.abs(a.monto) - Math.abs(b.monto),
    estab_asc: (a, b) => (a.descripcion || '').localeCompare(b.descripcion || ''),
    estab_desc: (a, b) => (b.descripcion || '').localeCompare(a.descripcion || ''),
    fecha_asc: (a, b) => a.fecha.localeCompare(b.fecha),
    fecha_desc: (a, b) => b.fecha.localeCompare(a.fecha),
  }[key];
  return r.sort(cmp);
}

/** Detalle de una categoría en un periodo: desglose por subcategoría o
 * establecimiento, filtros, búsqueda y la lista de movimientos. */
export default function CategoryModal({ categoria, tipo = 'GASTO', period = {}, bank = '', periodLabel = '', onClose, onOpenTx }) {
  const isIngreso = categoria === '__INGRESO__';
  const meta = isIngreso ? { name: 'Ingresos', icon: 'banknote', tone: 'ataraxia' } : catMeta(categoria);
  const wide = useMedia('(min-width: 768px)');
  const [groupBy, setGroupBy] = useState('sub');
  const [sub, setSub] = useState('');
  const [merchant, setMerchant] = useState('');
  const [sortKey, setSortKey] = useState('fecha_desc');
  const [q, setQ] = useState('');

  const { data, loading, error, reload } = useLoad(
    () => api.get('/transactions', {
      ...(isIngreso ? { tipo: 'INGRESO' } : { category: categoria, tipo }),
      limit: 2000, bank, ...period,
    }).then((d) => d.data || []),
    [categoria, tipo, bank, JSON.stringify(period)],
  );
  const tx = data || [];

  const groups = useMemo(() => {
    const g = {};
    tx.forEach((t) => {
      const k = groupBy === 'merchant' ? merchantOf(t) : (t.subcategoria || 'Sin subcategoría');
      g[k] = g[k] || { key: k, total: 0, n: 0, raw: groupBy === 'merchant' ? k : (t.subcategoria || SIN_SUB) };
      g[k].total += myAmount(t);
      g[k].n += 1;
    });
    return Object.values(g).sort((a, b) => b.total - a.total);
  }, [tx, groupBy]);
  const total = groups.reduce((s, g) => s + g.total, 0);
  const shown = groupBy === 'merchant' ? groups.slice(0, 8) : groups;
  const extra = groups.length - shown.length;

  const subcats = [...new Set(tx.map((t) => t.subcategoria).filter(Boolean))].sort();
  const hasSinSub = tx.some((t) => !t.subcategoria);

  const rows = useMemo(() => {
    let r = tx;
    if (groupBy === 'merchant') { if (merchant) r = r.filter((t) => merchantOf(t) === merchant); }
    else if (sub === SIN_SUB) r = r.filter((t) => !t.subcategoria);
    else if (sub) r = r.filter((t) => t.subcategoria === sub);
    if (q.trim()) {
      const nq = norm(q.trim());
      r = r.filter((t) => norm(`${t.descripcion} ${t.subcategoria || ''} ${t.banco} ${t.fecha} ${Math.abs(t.monto)}`).includes(nq));
    }
    return sortRows(r, sortKey);
  }, [tx, groupBy, merchant, sub, q, sortKey]);
  const rowsTotal = rows.reduce((s, t) => s + myAmount(t), 0);

  const activeKey = groupBy === 'merchant' ? merchant : sub;
  const pick = (g) => {
    if (groupBy === 'merchant') setMerchant(merchant === g.raw ? '' : g.raw);
    else setSub(sub === g.raw ? '' : g.raw);
  };
  const sortBy = (field) => setSortKey(
    sortKey === `${field}_asc` ? `${field}_desc`
      : sortKey === `${field}_desc` ? `${field}_asc`
        : field === 'estab' ? 'estab_asc' : `${field}_desc`,
  );
  const ariaSort = (field) => (sortKey === `${field}_asc` ? 'ascending' : sortKey === `${field}_desc` ? 'descending' : undefined);

  const sortTh = (field, children, className) => (
    <th className={className} aria-sort={ariaSort(field)}>
      <button type="button" className="fz-th-btn" onClick={() => sortBy(field)}>
        {children}
        {ariaSort(field) && <Icon name={ariaSort(field) === 'ascending' ? 'arrow-up' : 'arrow-down'} size={12} />}
      </button>
    </th>
  );

  return (
    <Modal size="wide" title={meta.name} eyebrow={periodLabel || (isIngreso ? 'Ingresos del periodo' : 'Detalle de categoría')} onClose={onClose} initialFocus={false}>
      <div className="eu-modal-bd fz-cm" data-cat={meta.tone || undefined}>
        <div className="fz-cm-sum">
          <span className="eu-row-ic fz-ic" data-cat={meta.tone || undefined}><Icon name={meta.icon} /></span>
          <div className="eu-grow">
            <div className="t-data-xl">{money(total)}</div>
            <div className="t-meta">{tx.length} movimiento{tx.length === 1 ? '' : 's'}{bank ? ` · ${bankName(bank)}` : ''}</div>
          </div>
        </div>

        <ErrorNote error={error} onRetry={reload} />
        {loading ? <Skel rows={4} /> : tx.length === 0 ? (
          <Empty icon="search-x" title="Sin movimientos" text="No hay movimientos de esta categoría en el periodo." />
        ) : (
          <div className="fz-cm-grid">
            <div className="fz-cm-left">
              <div className="eu-vstack fz-gap-2">
                <span className="t-ui">Desglose</span>
                <div className="eu-seg fz-seg-block" role="tablist" aria-label="Agrupar por">
                  <button type="button" role="tab" aria-selected={groupBy === 'sub'} onClick={() => { setGroupBy('sub'); setMerchant(''); }}>Subcategoría</button>
                  <button type="button" role="tab" aria-selected={groupBy === 'merchant'} onClick={() => { setGroupBy('merchant'); setSub(''); }}>Comercio</button>
                </div>
              </div>
              <ul className="fz-bd-list">
                {shown.map((g) => (
                  <li key={g.key}>
                    <button type="button" className="fz-bd" aria-pressed={activeKey === g.raw} onClick={() => pick(g)}>
                      <span className="eu-between">
                        <span className="t-ui fz-ellipsis">{g.key}</span>
                        <span className="t-data">{money(g.total, { cents: false })}</span>
                      </span>
                      <span className="eu-progress eu-progress--cat eu-progress--thin" aria-hidden="true"><i style={{ width: `${pct(g.total, total)}%` }} /></span>
                      <span className="t-meta">{g.n} mov. · {pct(g.total, total)} %</span>
                    </button>
                  </li>
                ))}
              </ul>
              {extra > 0 && <div className="t-meta">+{extra} comercios más</div>}
            </div>

            <div className="fz-cm-right">
              <div className="fz-cm-tools">
                <div className="eu-input-wrap fz-grow-2">
                  <Icon name="search" />
                  <input className="eu-input fz-input-sm" type="search" placeholder="Buscar…" aria-label="Buscar en los movimientos" value={q} onChange={(e) => setQ(e.target.value)} />
                </div>
                {groupBy === 'sub' ? (
                  <select className="eu-select fz-input-sm" aria-label="Subcategoría" value={sub} onChange={(e) => setSub(e.target.value)}>
                    <option value="">Todas las subcategorías</option>
                    {subcats.map((s) => <option key={s} value={s}>{s}</option>)}
                    {hasSinSub && <option value={SIN_SUB}>Sin subcategoría</option>}
                  </select>
                ) : merchant ? (
                  <button type="button" className="eu-chip" aria-pressed="true" onClick={() => setMerchant('')}>
                    <span className="fz-ellipsis">{merchant}</span><Icon name="x" />
                  </button>
                ) : null}
                <select className="eu-select fz-input-sm" aria-label="Ordenar" value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
                  {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </div>

              <div className="eu-between t-meta">
                <span>{rows.length} de {tx.length}</span>
                <span>Total <b className="num fz-fg-1">{money(rowsTotal)}</b></span>
              </div>

              {rows.length === 0 ? <div className="t-meta fz-pad">Nada coincide con «{q}».</div> : wide ? (
                <div className="fz-table-wrap">
                  <table className="eu-table fz-cm-table">
                    {/* Con una subcategoría ya filtrada, su columna solo repetiría el mismo valor. */}
                    <colgroup>
                      <col className="c-date" /><col />{!sub && <col className="c-sub" />}<col className="c-amt" />
                    </colgroup>
                    <thead>
                      <tr>
                        {sortTh('fecha', 'Fecha')}
                        {sortTh('estab', 'Establecimiento')}
                        {!sub && <th>Subcategoría</th>}
                        {sortTh('monto', 'Monto', 'r')}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((t) => (
                        <tr key={t.id} className="fz-tr" tabIndex={0} onClick={() => onOpenTx(t)}
                          onKeyDown={(e) => { if (e.key === 'Enter') onOpenTx(t); }}>
                          <td className="num fg-3 fz-td-date">{fmtDate(t.fecha, true)}</td>
                          <td>
                            <span className="fz-ellipsis fz-td-desc" title={t.descripcion}>{t.descripcion}</span>
                            {t.parcialidad_num && t.parcialidad_total ? <span className="eu-badge eu-badge--info">MSI {t.parcialidad_num}/{t.parcialidad_total}</span> : null}
                          </td>
                          {!sub && <td className="fg-3"><span className="fz-td-sub" title={t.subcategoria || ''}>{t.subcategoria || '—'}</span></td>}
                          <td className="r">
                            <span className="num">{money(t.monto)}</span>
                            {t.mi_parte != null && Math.abs(t.mi_parte) !== Math.abs(t.monto) && (
                              <div className="t-meta fz-nowrap">tu parte <span className="num">{money(t.mi_parte)}</span></div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="eu-list fz-list-inset">
                  {rows.map((t) => (
                    <button key={t.id} type="button" className="eu-row eu-row--interactive fz-row-btn" onClick={() => onOpenTx(t)}>
                      <div className="eu-row-main">
                        <div className="eu-row-t">{t.descripcion}</div>
                        <div className="eu-row-s">
                          {fmtDate(t.fecha, true)}{t.subcategoria ? ` · ${t.subcategoria}` : ''}
                          {t.parcialidad_num && t.parcialidad_total ? <span className="eu-badge eu-badge--info">MSI {t.parcialidad_num}/{t.parcialidad_total}</span> : null}
                        </div>
                      </div>
                      <div className="eu-row-end">
                        <div className="eu-amt">{money(t.monto)}</div>
                        {t.mi_parte != null && Math.abs(t.mi_parte) !== Math.abs(t.monto) && <div className="t-meta">tu parte {money(t.mi_parte)}</div>}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
