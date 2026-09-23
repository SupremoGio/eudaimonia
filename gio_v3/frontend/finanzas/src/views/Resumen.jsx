import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { MONTHS_LONG, fmtDate, money, pct, presetRange } from '../lib/format.js';
import { NATURALEZA, catMeta } from '../lib/meta.js';
import { CatIcon, Empty, ErrorNote, Icon, Skel, useLoad } from '../components/ui.jsx';
import FlowBars from '../components/FlowBars.jsx';

const monthName = MONTHS_LONG[new Date().getMonth()];

function Stat({ label, icon, children, foot }) {
  return (
    <div className="eu-card eu-stat fz-stat">
      <div className="eu-stat-lbl"><Icon name={icon} />{label}</div>
      {children}
      {foot}
    </div>
  );
}

// Sin bloque «Cuentas»: el usuario pidió quitarlo del Resumen porque repite
// la pestaña Cuentas (antes se ocultaba con CSS en estados.html).
export default function Resumen() {
  const app = useApp();
  const k = app.refreshKey;
  const ov = useLoad(() => api.get('/summary/overview'), [k]);
  const monthly = useLoad(() => api.get('/summary/monthly', { months: 6 }), [k]);
  const pend = useLoad(() => api.get('/summary/pendientes'), [k]);
  const bycat = useLoad(() => api.get('/summary/by-category', { tipo: 'GASTO' }), [k]);
  const recent = useLoad(() => api.get('/transactions', { limit: 5 }).then((d) => d.data || []), [k]);
  const nat = useLoad(() => api.get('/summary/by-naturaleza'), [k]);
  const loans = useLoad(() => api.get('/loans').catch(() => null), [k]);

  const o = ov.data || { income: 0, expense: 0, savings_pct: 0 };
  const months = monthly.data || [];
  const prev = months.length >= 2 ? months[months.length - 2] : null;
  const delta = prev && prev.expense ? Math.round(((Math.abs(o.expense) - Math.abs(prev.expense)) / Math.abs(prev.expense)) * 100) : null;
  const p = pend.data || {};
  const budgetsBy = Object.fromEntries((app.budgets || []).map((b) => [b.categoria, b]));
  const cats = (bycat.data || []).filter((c) => Math.abs(c.total) > 0);
  const catTotal = cats.reduce((s, c) => s + Math.abs(c.total), 0);
  const topCats = cats.slice(0, 6);
  const natRows = (nat.data || []).filter((n) => Math.abs(n.total) > 0);
  const natTotal = natRows.reduce((s, n) => s + Math.abs(n.total), 0);
  const l = loans.data;
  const period = presetRange('this_month');

  const openCat = (categoria) => app.openCategory({ categoria, tipo: 'GASTO', period, periodLabel: `Este mes · ${monthName}` });

  return (
    <div className="fz-vstack-lg">
      <ErrorNote error={ov.error} onRetry={ov.reload} />
      <div className="eu-grid-4 fz-stats">
        <Stat label="Gastado · tu parte" icon="wallet"
          foot={delta != null ? <div className={`eu-stat-delta ${delta > 0 ? 'down' : 'up'}`}><Icon name={delta > 0 ? 'trending-up' : 'trending-down'} size={12} />{delta > 0 ? '+' : ''}{delta} % vs {prev.month.toLowerCase()}</div> : <div className="t-meta">En {monthName}</div>}>
          {ov.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(o.expense, { cents: false })}</div>}
        </Stat>
        <Stat label="Ingresos" icon="banknote"
          foot={<div className="t-meta">{o.income > 0 ? `Ahorro ${o.savings_pct} %` : `En ${monthName}`}</div>}>
          {ov.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val fg-success">{money(o.income, { cents: false })}</div>}
        </Stat>
        <Stat label="MSI activos" icon="calendar-clock"
          foot={<div className="t-meta">{p.msi_compras_activas ? `${p.msi_compras_activas} compra${p.msi_compras_activas === 1 ? '' : 's'} · por pagar` : 'Sin compras a meses'}</div>}>
          {pend.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(p.msi_restante_total || 0, { cents: false })}</div>}
        </Stat>
        <Stat label="Sin categoría" icon="circle-help"
          foot={app.unclassified > 0
            ? <button type="button" className="fz-link" onClick={() => app.goTo('movimientos', { category: 'OTROS' })}>Categorizar ahora<Icon name="arrow-right" size={14} /></button>
            : <div className="t-meta">Todo clasificado este mes</div>}>
          <div className={`eu-stat-val${app.unclassified > 0 ? ' fg-warning' : ''}`}>{app.unclassified}</div>
        </Stat>
      </div>

      {((p.reembolsos_pendientes_count || 0) > 0 || (l && l.pendiente > 0)) && (
        <div className="fz-notes">
          {p.reembolsos_pendientes_count > 0 && (
            <div className="fz-note" data-tone="info">
              <Icon name="undo-2" size={16} />
              <span className="eu-grow">{p.reembolsos_pendientes_count} reembolso{p.reembolsos_pendientes_count === 1 ? '' : 's'} pendiente{p.reembolsos_pendientes_count === 1 ? '' : 's'} de cobrar</span>
              <span className="t-data">{money(p.reembolsos_pendientes_total)}</span>
            </div>
          )}
          {l && l.pendiente > 0 && (
            <div className="fz-note" data-tone="info">
              <Icon name="handshake" size={16} />
              <span className="eu-grow">Préstamos por cobrar · prestado {money(l.prestado, { cents: false })}, cobrado {money(l.cobrado, { cents: false })}</span>
              <span className="t-data">{money(l.pendiente)}</span>
            </div>
          )}
        </div>
      )}

      <div className="fz-split">
        <div className="eu-card eu-vstack fz-card-gap">
          <div className="eu-between">
            <h2 className="t-card">Flujo · 6 meses</h2>
            <div className="fz-legend t-meta">
              <span><i className="fz-sw fz-sw--in" />Ingreso</span>
              <span><i className="fz-sw fz-sw--out" />Gasto</span>
            </div>
          </div>
          <ErrorNote error={monthly.error} onRetry={monthly.reload} />
          {monthly.loading ? <Skel rows={1} h={160} /> : months.length ? <FlowBars data={months} /> : <Empty icon="chart-column" title="Sin datos aún" text="Sube un estado de cuenta para ver tu flujo." />}
        </div>

        <div className="eu-card eu-card--flush">
          <div className="eu-between fz-card-hd">
            <h2 className="t-card">Por categoría</h2>
            <span className="t-meta">{monthName} · vs presupuesto</span>
          </div>
          {bycat.loading ? <div className="fz-pad"><Skel rows={4} h={40} /></div> : topCats.length === 0 ? (
            <Empty icon="pie-chart" title="Sin gastos este mes" text="Cuando registres gastos aparecerán aquí por categoría." />
          ) : (
            <div className="eu-list">
              {topCats.map((c) => {
                const b = budgetsBy[c.categoria];
                const t = Math.abs(c.total);
                const used = b ? pct(t, b.limite) : pct(t, catTotal);
                const tone = b ? (used > 100 ? 'danger' : used >= 90 ? 'warning' : null) : null;
                return (
                  <button key={c.categoria} type="button" className="eu-row eu-row--interactive fz-row-btn" onClick={() => openCat(c.categoria)} data-tone={tone || undefined}>
                    <CatIcon cat={c.categoria} />
                    <div className="eu-row-main">
                      <div className="eu-between">
                        <span className="eu-row-t">{catMeta(c.categoria).name}</span>
                        <span className="t-data">{money(t, { cents: false })}{b && <span className="t-meta"> / {money(b.limite, { cents: false })}</span>}</span>
                      </div>
                      <div className={`eu-progress eu-progress--thin fz-mt-1 ${tone ? 'fz-progress-tone' : 'eu-progress--cat'}`} data-cat={catMeta(c.categoria).tone || undefined}>
                        <i style={{ width: `${Math.min(100, used)}%` }} />
                      </div>
                      <div className="eu-row-s">{b ? `${used} % del presupuesto` : `${used} % del gasto`}{c.pct_change != null && <span className={c.pct_change > 0 ? 'fg-danger' : 'fg-success'}>· {c.pct_change > 0 ? '▲' : '▼'} {Math.abs(c.pct_change)} %</span>}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
          <div className="fz-card-ft">
            <button type="button" className="fz-link" onClick={() => app.goTo('reportes')}>Ver reportes<Icon name="arrow-right" size={14} /></button>
          </div>
        </div>
      </div>

      <div className="fz-split fz-split--even">
        <div className="eu-card eu-card--flush">
          <div className="eu-between fz-card-hd">
            <h2 className="t-card">Movimientos recientes</h2>
            <button type="button" className="fz-link" onClick={() => app.goTo('movimientos')}>Ver todos<Icon name="arrow-right" size={14} /></button>
          </div>
          {recent.loading ? <div className="fz-pad"><Skel rows={3} h={40} /></div> : (recent.data || []).length === 0 ? (
            <Empty icon="receipt" title="Sin movimientos" text="Sube tu primer estado de cuenta.">
              <button type="button" className="eu-btn eu-btn--primary" onClick={app.openImport}><Icon name="upload" />Subir estado de cuenta</button>
            </Empty>
          ) : (
            <div className="eu-list">
              {recent.data.map((t) => (
                <button key={t.id} type="button" className="eu-row eu-row--interactive fz-row-btn" onClick={() => app.openTx(t)}>
                  <CatIcon cat={t.categoria} />
                  <div className="eu-row-main">
                    <div className="eu-row-t">{t.descripcion}</div>
                    <div className="eu-row-s">{fmtDate(t.fecha, true)} · {t.categoria === 'OTROS' ? 'Sin clasificar' : catMeta(t.categoria).name}</div>
                  </div>
                  <div className="eu-row-end"><span className={`eu-amt${t.tipo === 'INGRESO' ? ' pos' : ''}`}>{t.tipo === 'INGRESO' ? '+' : '−'}{money(t.monto)}</span></div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="eu-card eu-vstack fz-card-gap">
          <div className="eu-between">
            <h2 className="t-card">Gasto por naturaleza</h2>
            <span className="t-meta">{monthName}</span>
          </div>
          {nat.loading ? <Skel rows={3} h={32} /> : natRows.length === 0 ? <div className="t-meta">Sin gastos este mes.</div> : (
            <div className="eu-vstack fz-gap-3">
              {natRows.map((n) => {
                const m = NATURALEZA[n.naturaleza] || { name: n.naturaleza, tone: 'neutral' };
                return (
                  <div key={n.naturaleza} className="eu-vstack fz-gap-1" data-tone={m.tone}>
                    <div className="eu-between"><span className="t-ui">{m.name}</span><span className="t-data">{money(n.total, { cents: false })} <span className="t-meta">· {pct(Math.abs(n.total), natTotal)} %</span></span></div>
                    <div className="eu-progress fz-progress-tone"><i style={{ width: `${pct(Math.abs(n.total), natTotal)}%` }} /></div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
