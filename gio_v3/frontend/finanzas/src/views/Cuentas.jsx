import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { money, pct } from '../lib/format.js';
import { Empty, ErrorNote, Icon, Skel, useLoad, Progress } from '../components/ui.jsx';
import AccountCard from '../components/AccountCard.jsx';

export default function Cuentas() {
  const app = useApp();
  const { data, loading, error, reload } = useLoad(() => api.get('/accounts'), [app.refreshKey]);
  const accts = data || [];
  const income = accts.reduce((s, a) => s + Math.abs(a.income), 0);
  const expense = accts.reduce((s, a) => s + Math.abs(a.expense), 0);
  const byExpense = [...accts].sort((a, b) => Math.abs(b.expense) - Math.abs(a.expense));

  if (loading) return <Skel rows={3} h={96} />;
  return (
    <div className="fz-vstack-lg">
      <ErrorNote error={error} onRetry={reload} />
      {accts.length === 0 ? (
        <div className="eu-card">
          <Empty icon="credit-card" title="Sin cuentas todavía" text="Las cuentas aparecen solas al importar estados de cuenta de BBVA, Invex o HSBC.">
            <button type="button" className="eu-btn eu-btn--primary" onClick={app.openImport}><Icon name="upload" />Subir estado de cuenta</button>
          </Empty>
        </div>
      ) : (
        <>
          <div className="eu-grid-2 fz-stats-2">
            <div className="eu-card eu-stat"><div className="eu-stat-lbl"><Icon name="arrow-down-left" />Total ingresado</div><div className="eu-stat-val fg-success">{money(income, { cents: false })}</div><div className="t-meta">Histórico, todas las cuentas</div></div>
            <div className="eu-card eu-stat"><div className="eu-stat-lbl"><Icon name="arrow-up-right" />Total gastado</div><div className="eu-stat-val">{money(expense, { cents: false })}</div><div className="t-meta">Tu parte, sin pagos internos</div></div>
          </div>

          <div className="fz-accts-grid">
            {accts.map((a) => <AccountCard key={a.id} a={a} onClick={() => app.goTo('movimientos', { bank: a.id })} />)}
          </div>

          <div className="eu-card eu-vstack fz-card-gap">
            <div className="eu-between"><h2 className="t-card">Distribución del gasto por cuenta</h2><span className="t-meta">{money(expense, { cents: false })}</span></div>
            <div className="eu-vstack fz-gap-3">
              {byExpense.map((a) => (
                <div key={a.id} className="eu-vstack fz-gap-1">
                  <div className="eu-between"><span className="t-ui">{a.name}</span><span className="t-data">{money(a.expense, { cents: false })} <span className="t-meta">· {pct(Math.abs(a.expense), expense)} %</span></span></div>
                  <Progress className="eu-progress--brand" pct={pct(Math.abs(a.expense), expense)} label={`${a.name}: parte del gasto`} />
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
