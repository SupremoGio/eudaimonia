import { useMemo, useState } from 'react';
import { BASE, api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { fmtDate, money, norm } from '../lib/format.js';
import { bankName, catMeta } from '../lib/meta.js';
import { Empty, ErrorNote, Icon, Skel, useLoad } from '../components/ui.jsx';

// Abonos sin conciliar (solo PC): dinero que te entró, no cuenta como
// ingreso (Finanzas, Préstamos, Expense) y no está ligado ni a un préstamo
// (Por cobrar) ni a un lote de Expense. Clic en una fila para abrirla y
// cambiarle la categoría; para ligarla, ir a Por cobrar o Expense.

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const grupoDe = (m) => (m.categoria !== 'FINANZAS' ? m.categoria : (m.subcategoria || 'Sin subcategoría'));
const nombreGrupo = (g) => (['PRESTAMOS', 'EXPENSE'].includes(g) ? catMeta(g).name : g);

export default function SinConciliar() {
  const app = useApp();
  const [anio, setAnio] = useState('');
  const [grupo, setGrupo] = useState('');
  const [q, setQ] = useState('');
  const res = useLoad(() => api.get('/abonos/sin-conciliar', anio ? { anio } : {}), [app.refreshKey, anio]);
  const d = res.data;

  const rows = useMemo(() => {
    let r = d?.movimientos || [];
    if (grupo) r = r.filter((m) => grupoDe(m) === grupo);
    if (q.trim()) { const nq = norm(q.trim()); r = r.filter((m) => norm(`${m.descripcion} ${m.fecha} ${Math.abs(m.monto)}`).includes(nq)); }
    return r;
  }, [d, grupo, q]);
  const total = rows.reduce((s, m) => s + Math.abs(m.monto), 0);

  return (
    <div className="fz-vstack-lg fz-pc">
      <div className="eu-between fz-wrap">
        <div className="eu-hstack fz-pc-stats">
          <div className="eu-card eu-stat">
            <div className="eu-stat-lbl"><Icon name="inbox" />Abonos sin conciliar{anio ? ` ${anio}` : ''}</div>
            {res.loading ? <div className="eu-skel fz-skel-val" /> : <div className="eu-stat-val">{money(d?.total || 0)}</div>}
            <div className="t-meta">{d ? plural(d.movimientos.length, 'movimiento', 'movimientos') : ' '}</div>
          </div>
        </div>
        <div className="eu-hstack">
          <select className="eu-select fz-input-sm fz-w-auto" aria-label="Año" value={anio} onChange={(e) => { setAnio(e.target.value); setGrupo(''); }}>
            <option value="">Todos los años</option>
            {(d?.anios || []).map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <a className="eu-btn eu-btn--ghost" href={`${BASE}/abonos/sin-conciliar.csv${anio ? `?anio=${anio}` : ''}`} download>
            <Icon name="download" />CSV para comentar
          </a>
        </div>
      </div>

      <div className="fz-note" data-tone="info" role="note">
        <Icon name="info" size={16} />
        <span className="eu-grow">
          Dinero que te entró y no cuenta como ingreso, sin ligar a un préstamo ni a un lote de Expense.
          Si es una devolución, lígala en <button type="button" className="fz-link" onClick={() => app.goTo('porcobrar')}>Por cobrar</button>;
          si es un reembolso de la empresa, en <button type="button" className="fz-link" onClick={() => app.goTo('expense')}>Expense</button>;
          si fue ingreso real, ábrela y cámbiale la categoría.
        </span>
      </div>

      <ErrorNote error={res.error} onRetry={res.reload} />
      {res.loading ? <Skel rows={4} /> : !d || d.movimientos.length === 0 ? (
        <Empty icon="check-check" title="Todo conciliado" text="No hay abonos sueltos en este periodo." />
      ) : (
        <>
          <div className="eu-hstack fz-wrap" role="group" aria-label="Filtrar por tipo">
            <button type="button" className="eu-chip" aria-pressed={!grupo} onClick={() => setGrupo('')}>Todos · {money(d.total, { cents: false })}</button>
            {d.grupos.map((g) => (
              <button key={g.grupo} type="button" className="eu-chip" aria-pressed={grupo === g.grupo} onClick={() => setGrupo(grupo === g.grupo ? '' : g.grupo)}>
                {nombreGrupo(g.grupo)} · {g.n} · {money(g.total, { cents: false })}
              </button>
            ))}
          </div>
          <div className="eu-between t-meta fz-wrap">
            <div className="eu-input-wrap">
              <Icon name="search" />
              <input className="eu-input fz-input-sm" type="search" placeholder="Buscar…" aria-label="Buscar abono" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <span>{rows.length} de {d.movimientos.length} · Total <b className="num fz-fg-1">{money(total)}</b></span>
          </div>
          <div className="fz-table-wrap">
            <table className="eu-table fz-ex-table fz-sc-table">
              <colgroup><col className="c-date" /><col /><col className="c-st" /><col className="c-st" /><col className="c-amt" /></colgroup>
              <thead><tr><th>Fecha</th><th>Descripción</th><th>Tipo</th><th>Cuenta</th><th className="r">Monto</th></tr></thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.id} className="fz-tr" tabIndex={0} onClick={() => app.openTx(m)} onKeyDown={(e) => { if (e.key === 'Enter') app.openTx(m); }}>
                    <td className="num fg-3">{fmtDate(m.fecha, true)}</td>
                    <td><span className="fz-ellipsis fz-td-desc" title={m.descripcion}>{m.descripcion}</span></td>
                    <td className="fg-3">{nombreGrupo(grupoDe(m))}</td>
                    <td className="fg-3">{bankName(m.banco)}</td>
                    <td className="r num fg-success">+{money(Math.abs(m.monto))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
