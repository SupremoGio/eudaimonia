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
// Pista del servidor (abonos.py): qué es probablemente cada abono.
const PISTAS = { prestamo: 'Préstamo', expense: 'Expense', propia: 'Entre tus cuentas', ninguna: 'Sin pista' };
const pistaDe = (m) => m.pista?.tipo || 'ninguna';

// Filtros y orden se recuerdan en este navegador: editar un movimiento,
// cambiar de pestaña o recargar no los deshace.
const MEMO_KEY = 'fz-sc-filtros';
const DEF = { anio: '', grupo: '', pista: '', q: '', banco: '', sort: 'fecha', dir: 'desc' };
function leerMemo() {
  try { return { ...DEF, ...(JSON.parse(localStorage.getItem(MEMO_KEY)) || {}) }; } catch { return DEF; }
}
function guardarMemo(v) {
  try { localStorage.setItem(MEMO_KEY, JSON.stringify(v)); } catch { /* sin almacenamiento */ }
}
const SORT_VAL = {
  fecha: (m) => m.fecha || '',
  desc: (m) => (m.descripcion || '').toLowerCase(),
  tipo: (m) => nombreGrupo(grupoDe(m)).toLowerCase(),
  banco: (m) => bankName(m.banco).toLowerCase(),
  monto: (m) => Math.abs(m.monto),
};

export default function SinConciliar() {
  const app = useApp();
  const [f, setF] = useState(leerMemo);
  const set = (patch) => setF((prev) => { const n = { ...prev, ...patch }; guardarMemo(n); return n; });
  const { anio, grupo, pista, q, banco, sort, dir } = f;
  const res = useLoad(() => api.get('/abonos/sin-conciliar', anio ? { anio } : {}), [app.refreshKey, anio]);
  const d = res.data;

  const rows = useMemo(() => {
    let r = d?.movimientos || [];
    if (grupo) r = r.filter((m) => grupoDe(m) === grupo);
    if (pista) r = r.filter((m) => pistaDe(m) === pista);
    if (banco) r = r.filter((m) => m.banco === banco);
    if (q.trim()) { const nq = norm(q.trim()); r = r.filter((m) => norm(`${m.descripcion} ${m.fecha} ${Math.abs(m.monto)}`).includes(nq)); }
    const val = SORT_VAL[sort] || SORT_VAL.fecha;
    const sign = dir === 'asc' ? 1 : -1;
    return [...r].sort((a, b) => {
      const x = val(a), y = val(b);
      const c = typeof x === 'string' ? x.localeCompare(y) : x - y;
      return c * sign || (b.fecha || '').localeCompare(a.fecha || '');
    });
  }, [d, grupo, pista, banco, q, sort, dir]);
  const bancos = [...new Set((d?.movimientos || []).map((m) => m.banco))].sort();
  const sortBy = (col) => set(sort === col ? { dir: dir === 'asc' ? 'desc' : 'asc' } : { sort: col, dir: ['desc', 'tipo', 'banco'].includes(col) ? 'asc' : 'desc' });
  const th = (col, label, cls) => (
    <th className={cls} aria-sort={sort === col ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}>
      <button type="button" className="fz-th-btn" onClick={() => sortBy(col)}>
        {label}{sort === col && <Icon name={dir === 'asc' ? 'arrow-up' : 'arrow-down'} size={12} />}
      </button>
    </th>
  );
  const hayFiltros = grupo || pista || banco || q.trim();
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
          <select className="eu-select fz-input-sm fz-w-auto" aria-label="Año" value={anio} onChange={(e) => set({ anio: e.target.value })}>
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
            <button type="button" className="eu-chip" aria-pressed={!grupo} onClick={() => set({ grupo: '' })}>Todos · {money(d.total, { cents: false })}</button>
            {d.grupos.map((g) => (
              <button key={g.grupo} type="button" className="eu-chip" aria-pressed={grupo === g.grupo} onClick={() => set({ grupo: grupo === g.grupo ? '' : g.grupo })}>
                {nombreGrupo(g.grupo)} · {g.n} · {money(g.total, { cents: false })}
              </button>
            ))}
          </div>
          {(d.por_pista || []).length > 0 && (
            <div className="eu-hstack fz-wrap" role="group" aria-label="Filtrar por pista">
              <span className="t-meta">Qué parece:</span>
              {d.por_pista.map((g) => (
                <button key={g.tipo} type="button" className="eu-chip" aria-pressed={pista === g.tipo} onClick={() => set({ pista: pista === g.tipo ? '' : g.tipo })}>
                  {PISTAS[g.tipo] || g.tipo} · {g.n} · {money(g.total, { cents: false })}
                </button>
              ))}
            </div>
          )}
          <div className="eu-between t-meta fz-wrap">
            <div className="eu-hstack fz-wrap">
              <div className="eu-input-wrap">
                <Icon name="search" />
                <input className="eu-input fz-input-sm" type="search" placeholder="Buscar descripción, fecha o monto…" aria-label="Buscar abono" value={q} onChange={(e) => set({ q: e.target.value })} />
              </div>
              <select className="eu-select fz-input-sm fz-w-auto" aria-label="Cuenta" value={banco} onChange={(e) => set({ banco: e.target.value })}>
                <option value="">Todas las cuentas</option>
                {bancos.map((b) => <option key={b} value={b}>{bankName(b)}</option>)}
              </select>
              {hayFiltros && <button type="button" className="fz-link" onClick={() => set({ grupo: '', pista: '', banco: '', q: '' })}>Quitar filtros</button>}
            </div>
            <span>{rows.length} de {d.movimientos.length} · Total <b className="num fz-fg-1">{money(total)}</b></span>
          </div>
          <div className="fz-table-wrap">
            <table className="eu-table fz-ex-table fz-sc-table">
              <colgroup><col className="c-date" /><col /><col className="c-st" /><col className="c-st" /><col className="c-amt" /></colgroup>
              <thead><tr>{th('fecha', 'Fecha')}{th('desc', 'Descripción')}{th('tipo', 'Tipo')}{th('banco', 'Cuenta')}{th('monto', 'Monto', 'r')}</tr></thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.id} className="fz-tr" tabIndex={0} onClick={() => app.openTx(m)} onKeyDown={(e) => { if (e.key === 'Enter') app.openTx(m); }}>
                    <td className="num fg-3">{fmtDate(m.fecha, true)}</td>
                    <td>
                      <span className="fz-ellipsis fz-td-desc" title={m.descripcion}>{m.descripcion}</span>
                      {m.pista && <span className="fz-ellipsis t-meta" title={m.pista.texto}>{m.pista.texto}</span>}
                    </td>
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
