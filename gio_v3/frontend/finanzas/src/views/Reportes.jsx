import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { MONTHS, PRESETS, fmtDate, money, monthLabel, pct, presetRange } from '../lib/format.js';
import { BANKS, RANK_TONES, bankName, catMeta } from '../lib/meta.js';
import { CatIcon, Empty, ErrorNote, Icon, Skel, useLoad, useMedia } from '../components/ui.jsx';
import FlowBars from '../components/FlowBars.jsx';

const DONUT_MAX = 6;

/** ['2024','2025','2026'] → «2024, 2025 y 2026». */
const listJoin = (a) => (a.length < 2 ? a.join('') : `${a.slice(0, -1).join(', ')} y ${a[a.length - 1]}`);

function Donut({ items, total, label }) {
  const R = 52, C = 2 * Math.PI * R;
  let acc = 0;
  return (
    <figure className="fz-donut">
      <svg viewBox="0 0 140 140" role="img" aria-label={label}>
        <circle className="fz-donut-bg" cx="70" cy="70" r={R} />
        {items.map((it) => {
          const frac = total > 0 ? it.value / total : 0;
          const len = Math.max(0, frac * C - (items.length > 1 ? 2 : 0));
          const el = (
            <circle key={it.key} className="fz-donut-seg" data-cat={it.tone || undefined} data-rest={it.tone ? undefined : ''}
              cx="70" cy="70" r={R} strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc * C} />
          );
          acc += frac;
          return el;
        })}
      </svg>
      <figcaption className="fz-donut-c">
        <span className="t-data">{money(total, { cents: false })}</span>
        <span className="t-meta">total</span>
      </figcaption>
    </figure>
  );
}

function StatBox({ label, value, tone, onClick, hint }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag type={onClick ? 'button' : undefined} className={`eu-card eu-stat fz-stat-sm${onClick ? ' eu-card--interactive' : ''}`} onClick={onClick}>
      <span className="eu-stat-lbl">{label}</span>
      <span className={`t-data fz-stat-sm-v${tone ? ` fg-${tone}` : ''}`}>{value}</span>
      {hint && <span className="t-meta">{hint}</span>}
    </Tag>
  );
}

export default function Reportes() {
  const app = useApp();
  const wide = useMedia('(min-width: 768px)');
  const now = new Date();
  const [preset, setPreset] = useState('this_month');
  // Personalizado: uno o varios años × (opcional) meses del año. Los meses
  // elegidos se aplican a cada año seleccionado (ej. ene–mar de 2024 y 2025).
  const [years, setYears] = useState(() => new Set([now.getFullYear()]));
  const [months, setMonths] = useState(() => new Set());
  const [bank, setBank] = useState('');
  const [banks, setBanks] = useState([]);
  const [view, setView] = useState('GASTO');
  const [trendN, setTrendN] = useState(6);
  useEffect(() => { api.get('/summary/banks').then((b) => setBanks(b || [])).catch(() => {}); }, []);

  const yearList = [...years].sort((a, b) => a - b);
  const monthList = [...months].sort((a, b) => a - b);
  const yearsKey = yearList.join(','), monthsKey = monthList.join(',');
  const contiguous = yearList.every((y, i) => i === 0 || y === yearList[i - 1] + 1);
  const period = useMemo(() => {
    if (preset !== 'custom') return presetRange(preset);
    if (!monthList.length && contiguous) return { date_from: `${yearList[0]}-01-01`, date_to: `${yearList[yearList.length - 1]}-12-31` };
    const cur = now.getFullYear(), curM = now.getMonth() + 1;
    const ms = monthList.length ? monthList : Array.from({ length: 12 }, (_, i) => i + 1);
    const yms = yearList.flatMap((y) => ms.filter((m) => y < cur || m <= curM).map((m) => `${y}-${String(m).padStart(2, '0')}`));
    return { months: yms.join(',') };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset, yearsKey, monthsKey]);
  const yearsText = listJoin(yearList.map(String));
  const periodLabel = preset === 'custom'
    ? (monthList.length ? `${monthList.map((m) => MONTHS[m - 1]).join(', ')} · ${yearsText}` : `Todo ${yearsText}`)
    : PRESETS.find((p) => p.id === preset).label;
  const params = { ...period, bank };
  const pk = JSON.stringify(params);

  const stats = useLoad(() => api.get('/summary/stats', params), [pk, app.refreshKey]);
  const bycat = useLoad(() => api.get('/summary/by-category', { ...params, tipo: view }), [pk, view, app.refreshKey]);
  const trend = useLoad(() => api.get('/summary/monthly', { months: trendN, bank }), [trendN, bank, app.refreshKey]);
  const top = useLoad(() => api.get('/transactions', { ...params, tipo: 'GASTO', limit: 2000 })
    .then((d) => [...(d.data || [])].sort((a, b) => Math.abs(b.monto) - Math.abs(a.monto)).slice(0, 10)), [pk, app.refreshKey]);

  const s = stats.data || {};
  const cats = (bycat.data || []).filter((c) => Math.abs(c.total) > 0);
  const catTotal = cats.reduce((a, c) => a + Math.abs(c.total), 0);
  const donut = cats.slice(0, DONUT_MAX).map((c, i) => ({ key: c.categoria, value: Math.abs(c.total), tone: RANK_TONES[i % RANK_TONES.length] }));
  const rest = cats.slice(DONUT_MAX).reduce((a, c) => a + Math.abs(c.total), 0);
  if (rest > 0) donut.push({ key: '__rest', value: rest, tone: null });
  const toneOf = (i) => (i < DONUT_MAX ? RANK_TONES[i % RANK_TONES.length] : null);

  const openCat = (categoria, tipo = view) => app.openCategory({ categoria, tipo, period, bank, periodLabel });
  const toggleMonth = (mi) => setMonths((m) => { const n = new Set(m); if (n.has(mi)) n.delete(mi); else n.add(mi); return n; });
  // Siempre queda al menos un año elegido.
  // Si solo queda el año en curso, se sueltan los meses que aún no llegan.
  const toggleYear = (y) => {
    const n = new Set(years);
    if (n.has(y)) { if (n.size > 1) n.delete(y); } else n.add(y);
    setYears(n);
    if (n.size === 1 && n.has(now.getFullYear())) setMonths((m) => new Set([...m].filter((mi) => mi <= now.getMonth() + 1)));
  };
  const yearOpts = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);
  const onlyCurrent = yearList.length === 1 && yearList[0] === now.getFullYear();
  const bankOpts = [...new Set([...BANKS.map((b) => b.id), ...banks])];

  return (
    <div className="fz-vstack-lg">
      <div className="eu-card eu-vstack fz-card-gap fz-period">
        <div className="eu-chips" role="group" aria-label="Periodo">
          {PRESETS.map((p) => <button key={p.id} type="button" className="eu-chip" aria-pressed={preset === p.id} onClick={() => setPreset(p.id)}>{p.label}</button>)}
        </div>
        {preset === 'custom' && (
          <div className="eu-vstack fz-gap-2">
            <div className="eu-chips" role="group" aria-label="Años (puedes elegir varios)">
              {yearOpts.map((y) => (
                <button key={y} type="button" className="eu-chip" aria-pressed={years.has(y)} onClick={() => toggleYear(y)}>{y}</button>
              ))}
            </div>
            <div className="fz-months" role="group" aria-label={`Meses de ${yearsText}`}>
              {MONTHS.map((m, i) => (
                <button key={m} type="button" className="eu-chip" aria-pressed={months.has(i + 1)} disabled={onlyCurrent && i > now.getMonth()} onClick={() => toggleMonth(i + 1)}>{m}</button>
              ))}
            </div>
            <div className="eu-between t-meta">
              <span>{monthList.length
                ? `${monthList.length} mes${monthList.length === 1 ? '' : 'es'}${yearList.length > 1 ? ` en cada año (${yearsText})` : ` de ${yearsText}`}`
                : `Sin meses elegidos: se usa todo ${yearsText}`}</span>
              {(monthList.length > 0 || yearList.length > 1) && <button type="button" className="fz-link" onClick={() => { setMonths(new Set()); setYears(new Set([now.getFullYear()])); }}>Quitar selección</button>}
            </div>
          </div>
        )}
        <div className="eu-between fz-wrap">
          <select className="eu-select fz-input-sm fz-w-auto" aria-label="Cuenta" value={bank} onChange={(e) => setBank(e.target.value)}>
            <option value="">Todas las cuentas</option>
            {bankOpts.map((b) => <option key={b} value={b}>{bankName(b)}</option>)}
          </select>
          <a className="eu-btn eu-btn--ghost eu-btn--sm" href={api.csvUrl(params)} download><Icon name="download" />Exportar CSV</a>
        </div>
      </div>

      <ErrorNote error={stats.error} onRetry={stats.reload} />
      {stats.loading ? <Skel rows={2} h={72} /> : (
        <div className="fz-stat-grid">
          <StatBox label="Total gastado" value={money(s.total_expense, { cents: false })} />
          <StatBox label="Total ingreso" value={money(s.total_income, { cents: false })} tone="success" onClick={() => openCat('__INGRESO__', 'INGRESO')} hint="Ver detalle" />
          <StatBox label="Tasa de ahorro" value={`${s.savings_pct || 0} %`} tone={(s.savings_pct || 0) < 0 ? 'danger' : undefined} />
          <StatBox label="Promedio diario" value={money(s.avg_daily, { cents: false })} hint={s.days ? `${s.days} días` : undefined} />
          <StatBox label="Por transacción" value={money(s.avg_per_tx, { cents: false })} />
          <StatBox label="Transacciones" value={s.tx_count || 0} />
          <StatBox label="Sin clasificar" value={s.unclassified || 0} tone={s.unclassified > 0 ? 'warning' : undefined} onClick={s.unclassified > 0 ? () => openCat('OTROS', 'GASTO') : undefined} hint={s.unclassified > 0 ? 'Revisar' : undefined} />
          {s.max_tx_amount > 0 && (
            <div className="eu-card eu-stat fz-stat-sm fz-stat-wide">
              <span className="eu-stat-lbl"><Icon name="arrow-up-right" />Mayor gasto</span>
              <span className="t-data fz-stat-sm-v">{money(s.max_tx_amount)}</span>
              <span className="t-meta fz-ellipsis">{s.max_tx_desc}</span>
            </div>
          )}
        </div>
      )}

      <div className="fz-split">
        <div className="eu-card eu-vstack fz-card-gap">
          <div className="eu-between fz-wrap">
            <h2 className="t-card">{view === 'GASTO' ? 'Gastos' : 'Ingresos'} por categoría</h2>
            <div className="eu-seg" role="tablist" aria-label="Ver">
              <button type="button" role="tab" aria-selected={view === 'GASTO'} onClick={() => setView('GASTO')}>Gastos</button>
              <button type="button" role="tab" aria-selected={view === 'INGRESO'} onClick={() => setView('INGRESO')}>Ingresos</button>
            </div>
          </div>
          <ErrorNote error={bycat.error} onRetry={bycat.reload} />
          {bycat.loading ? <Skel rows={4} h={40} /> : cats.length === 0 ? (
            <Empty icon="pie-chart" title="Sin datos" text={`No hay ${view === 'GASTO' ? 'gastos' : 'ingresos'} en ${periodLabel.toLowerCase()}.`} />
          ) : (
            <div className="fz-cats-chart">
              <Donut items={donut} total={catTotal} label={`Distribución de ${view === 'GASTO' ? 'gastos' : 'ingresos'} por categoría`} />
              <ul className="fz-cat-legend">
                {cats.map((c, i) => (
                  <li key={c.categoria}>
                    <button type="button" className="fz-cat-legend-btn" onClick={() => openCat(c.categoria)}>
                      <i className="fz-dot" data-cat={toneOf(i) || undefined} data-rest={toneOf(i) ? undefined : ''} />
                      <span className="eu-grow fz-ellipsis t-ui">{catMeta(c.categoria).name}</span>
                      {c.pct_change != null && (
                        <span className={`t-meta fz-nowrap ${(c.pct_change > 0) === (view === 'GASTO') ? 'fg-danger' : 'fg-success'}`} title="vs periodo anterior">
                          {c.pct_change > 0 ? '▲' : '▼'} {Math.abs(c.pct_change)} %
                        </span>
                      )}
                      <span className="t-meta fz-pct">{pct(Math.abs(c.total), catTotal)} %</span>
                      <span className="t-data">{money(c.total, { cents: false })}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="eu-card eu-vstack fz-card-gap">
          <div className="eu-between fz-wrap">
            <h2 className="t-card">Tendencia mensual</h2>
            <div className="eu-seg" role="tablist" aria-label="Meses">
              {[3, 6, 12].map((n) => <button key={n} type="button" role="tab" aria-selected={trendN === n} onClick={() => setTrendN(n)}>{n} m</button>)}
            </div>
          </div>
          <div className="fz-legend t-meta"><span><i className="fz-sw fz-sw--in" />Ingreso</span><span><i className="fz-sw fz-sw--out" />Gasto</span></div>
          {trend.loading ? <Skel rows={1} h={160} /> : (trend.data || []).length === 0 ? <div className="t-meta">Sin datos.</div> : (
            <>
              <FlowBars data={trend.data} tall />
              <div className="eu-list fz-list-inset">
                {[...trend.data].reverse().map((m) => (
                  <div key={m.year_month} className="eu-between fz-trend-row">
                    <span className="t-ui">{monthLabel(m.year_month)}</span>
                    <span className="t-meta">
                      <span className="num fg-success">+{money(m.income, { cents: false })}</span> · <span className="num fz-fg-1">−{money(m.expense, { cents: false })}</span>
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="eu-card eu-card--flush">
        <div className="eu-between fz-card-hd"><h2 className="t-card">Top 10 gastos</h2><span className="t-meta">{periodLabel}</span></div>
        {top.loading ? <div className="fz-pad"><Skel rows={4} h={40} /></div> : (top.data || []).length === 0 ? (
          <div className="t-meta fz-pad">Sin gastos en el periodo.</div>
        ) : wide ? (
          <div className="fz-table-wrap">
            <table className="eu-table">
              <thead><tr><th>#</th><th>Fecha</th><th>Comercio</th><th>Categoría</th><th>Cuenta</th><th className="r">Monto</th></tr></thead>
              <tbody>
                {top.data.map((t, i) => (
                  <tr key={t.id} className="fz-tr" tabIndex={0} onClick={() => app.openTx(t)} onKeyDown={(e) => { if (e.key === 'Enter') app.openTx(t); }}>
                    <td className="num fg-3">{i + 1}</td>
                    <td className="num fg-3 fz-td-date">{fmtDate(t.fecha, true)}</td>
                    <td><span className="fz-ellipsis fz-td-desc">{t.descripcion}</span></td>
                    <td className="fg-2">{catMeta(t.categoria).name}</td>
                    <td className="fg-3">{bankName(t.banco)}</td>
                    <td className="r num">{money(t.monto)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="eu-list">
            {top.data.map((t) => (
              <button key={t.id} type="button" className="eu-row eu-row--interactive fz-row-btn" onClick={() => app.openTx(t)}>
                <CatIcon cat={t.categoria} />
                <div className="eu-row-main"><div className="eu-row-t">{t.descripcion}</div><div className="eu-row-s">{fmtDate(t.fecha, true)} · {catMeta(t.categoria).name}</div></div>
                <div className="eu-row-end"><span className="eu-amt">{money(t.monto)}</span></div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
