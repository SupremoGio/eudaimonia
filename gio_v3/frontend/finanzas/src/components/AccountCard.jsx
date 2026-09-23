import { money } from '../lib/format.js';
import { Icon } from './ui.jsx';

const TYPE = { credit: 'Crédito', debit: 'Débito', cash: 'Efectivo', credito: 'Crédito', debito: 'Débito' };

export default function AccountCard({ a, onClick }) {
  const typeLbl = TYPE[String(a.type || '').toLowerCase()] || a.type || '';
  return (
    <button type="button" className="eu-card eu-card--interactive fz-acct" onClick={onClick}>
      <span className="eu-between">
        <span className="eu-row-ic fz-ic"><Icon name={a.icon || 'credit-card'} /></span>
        <span className="t-meta">{typeLbl}</span>
      </span>
      <span className="t-ui">{a.name}</span>
      <span className="t-meta">{a.tx_count} movimiento{a.tx_count === 1 ? '' : 's'}</span>
      <span className="fz-acct-nums">
        <span><span className="t-meta">Gastado</span><span className="t-data">{money(a.expense, { cents: false })}</span></span>
        <span><span className="t-meta">Ingresado</span><span className="t-data fg-success">{money(a.income, { cents: false })}</span></span>
      </span>
    </button>
  );
}
