import { money } from '../lib/format.js';

/** Barras pareadas ingreso/gasto por mes. El último mes va resaltado. */
export default function FlowBars({ data, showIncome = true, tall = false }) {
  const max = Math.max(1, ...data.map((d) => Math.max(showIncome ? Math.abs(d.income) : 0, Math.abs(d.expense))));
  const last = data.length - 1;
  return (
    <figure className={`fz-bars${tall ? ' fz-bars--tall' : ''}`}>
      <div className="fz-bars-plot" aria-hidden="true">
        {data.map((d, i) => (
          <div key={d.year_month} className={`fz-bars-col${i === last ? ' is-now' : ''}`}
            title={`${d.month} ${d.year_month.slice(0, 4)} · ${showIncome ? `ingreso ${money(d.income, { cents: false })} · ` : ''}gasto ${money(d.expense, { cents: false })}`}>
            <div className="fz-bars-pair">
              {showIncome && <i className="fz-bar fz-bar--in" style={{ height: `${(Math.abs(d.income) / max) * 100}%` }} />}
              <i className="fz-bar fz-bar--out" style={{ height: `${(Math.abs(d.expense) / max) * 100}%` }} />
            </div>
            <span className="fz-bars-lbl">{d.month}</span>
          </div>
        ))}
      </div>
      <table className="fz-sr">
        <caption>Ingreso y gasto por mes</caption>
        <thead><tr><th>Mes</th>{showIncome && <th>Ingreso</th>}<th>Gasto</th></tr></thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.year_month}><td>{d.month} {d.year_month.slice(0, 4)}</td>{showIncome && <td>{money(d.income)}</td>}<td>{money(d.expense)}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
