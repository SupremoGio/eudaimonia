import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { useApp } from '../lib/ctx.js';
import { MONTHS_LONG, money, norm, pct, presetRange } from '../lib/format.js';
import { catMeta } from '../lib/meta.js';
import { getCategories } from '../lib/store.js';
import { CatIcon, Empty, ErrorNote, Field, Icon, Modal, Skel, confirmDialog, toast, useLoad } from '../components/ui.jsx';

const monthName = MONTHS_LONG[new Date().getMonth()];
const toneFor = (p) => (p > 100 ? 'danger' : p >= 85 ? 'warning' : 'success');

function BudgetForm({ budget, existing, onClose, onSaved }) {
  const isNew = !budget;
  const [cats, setCats] = useState([]);
  const [categoria, setCategoria] = useState(budget ? budget.categoria : '');
  const [nombre, setNombre] = useState(budget ? budget.nombre : '');
  const [limite, setLimite] = useState(budget ? String(budget.limite) : '');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { getCategories().then(setCats).catch(() => {}); }, []);
  const options = cats.map((c) => c.categoria).filter((k) => k !== 'OTROS' && (!existing.includes(k) || k === categoria));

  async function submit(e) {
    e.preventDefault();
    const lim = parseFloat(limite);
    if (isNew && !categoria) { setErr('Elige una categoría.'); return; }
    if (!(lim > 0)) { setErr('El límite debe ser mayor a 0.'); return; }
    setBusy(true); setErr('');
    try {
      if (isNew) await api.post('/budgets', { categoria, nombre: nombre.trim() || catMeta(categoria).name, limite: lim });
      else await api.patch(`/budgets/${budget.id}`, { nombre: nombre.trim() || budget.nombre, limite: lim });
      toast(isNew ? 'Presupuesto creado' : 'Presupuesto actualizado', 'ok');
      onSaved(); onClose();
    } catch (ex) { setErr(ex.message || 'No se pudo guardar.'); setBusy(false); }
  }

  return (
    <Modal title={isNew ? 'Nuevo presupuesto' : `Editar · ${budget.nombre}`} eyebrow="Límite mensual" onClose={onClose}
      footer={<>
        <button type="button" className="eu-btn eu-btn--ghost" onClick={onClose}>Cancelar</button>
        <button type="submit" form="fz-bf" className="eu-btn eu-btn--primary" disabled={busy} aria-busy={busy || undefined}>{isNew ? 'Crear' : 'Guardar'}</button>
      </>}>
      <form id="fz-bf" className="eu-modal-bd" onSubmit={submit} noValidate>
        {isNew && (
          <Field label="Categoría" htmlFor="fz-bf-cat">
            <select id="fz-bf-cat" className="eu-select" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              <option value="">Elige una categoría…</option>
              {options.map((k) => <option key={k} value={k}>{catMeta(k).name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Nombre (opcional)" htmlFor="fz-bf-nombre">
          <input id="fz-bf-nombre" className="eu-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder={categoria ? catMeta(categoria).name : 'Ej. Súper y mercado'} />
        </Field>
        <Field label="Límite mensual (MXN)" htmlFor="fz-bf-lim" error={err}>
          <input id="fz-bf-lim" className="eu-input eu-input--money" type="number" inputMode="decimal" min="0" step="100" value={limite} onChange={(e) => setLimite(e.target.value)} placeholder="0" />
        </Field>
      </form>
    </Modal>
  );
}

export default function Presupuestos() {
  const app = useApp();
  const { data, loading, error, reload } = useLoad(() => api.get('/budgets'), [app.refreshKey]);
  const [form, setForm] = useState(null); // {budget?}
  const budgets = (data || []).map((b) => ({ ...b, gastado: Math.abs(b.gastado) }));
  const limit = budgets.reduce((s, b) => s + b.limite, 0);
  const spent = budgets.reduce((s, b) => s + b.gastado, 0);
  const gp = pct(spent, limit);
  const saved = () => { reload(); app.refresh(); };

  async function remove(b) {
    const ok = await confirmDialog(`¿Eliminar el presupuesto de ${b.nombre}?`, { confirmLabel: 'Eliminar', danger: true });
    if (!ok) return;
    try { await api.del(`/budgets/${b.id}`); toast('Presupuesto eliminado', 'ok'); saved(); }
    catch (e) { toast(e.message || 'No se pudo eliminar', 'err'); }
  }

  const period = presetRange('this_month');
  return (
    <div className="fz-vstack-lg">
      <ErrorNote error={error} onRetry={reload} />
      <div className="eu-between fz-wrap">
        <div><h2 className="t-section">Presupuestos de {monthName}</h2><div className="t-meta">Gasto real (tu parte) contra el límite de cada categoría.</div></div>
        <button type="button" className="eu-btn eu-btn--primary" onClick={() => setForm({})}><Icon name="plus" />Presupuesto</button>
      </div>

      {loading ? <Skel rows={3} h={88} /> : budgets.length === 0 ? (
        <div className="eu-card">
          <Empty icon="target" title="Sin presupuestos" text="Define cuánto quieres gastar al mes por categoría y te avisamos al llegar al 85 %.">
            <button type="button" className="eu-btn eu-btn--primary" onClick={() => setForm({})}><Icon name="plus" />Crear presupuesto</button>
          </Empty>
        </div>
      ) : (
        <>
          <div className="eu-card eu-vstack fz-card-gap" data-tone={toneFor(gp)}>
            <div className="eu-between fz-wrap">
              <div className="eu-stat">
                <div className="eu-stat-lbl"><Icon name="target" />Total del mes</div>
                <div className="eu-stat-val">{money(spent, { cents: false })}<span className="t-meta"> / {money(limit, { cents: false })}</span></div>
              </div>
              <div className="fz-right">
                <div className="t-data fz-tone-fg">{gp} % usado</div>
                <div className="t-meta">{spent > limit ? `Excedido por ${money(spent - limit, { cents: false })}` : `Libre ${money(limit - spent, { cents: false })}`}</div>
              </div>
            </div>
            <div className="eu-progress fz-progress-tone"><i style={{ width: `${Math.min(100, gp)}%` }} /></div>
          </div>

          <div className="fz-budgets">
            {budgets.map((b) => {
              const p = pct(b.gastado, b.limite);
              const tone = toneFor(p);
              return (
                <div key={b.id} className="eu-card eu-vstack fz-card-gap fz-budget" data-tone={tone}>
                  <div className="eu-hstack fz-gap-3">
                    <CatIcon cat={b.categoria} />
                    <button type="button" className="eu-grow fz-budget-t" onClick={() => app.openCategory({ categoria: b.categoria, tipo: 'GASTO', period, periodLabel: `Este mes · ${monthName}` })}>
                      <span className="t-ui">{b.nombre}</span>
                      {norm(b.nombre) !== norm(catMeta(b.categoria).name) && <span className="t-meta">{catMeta(b.categoria).name}</span>}
                    </button>
                    <button type="button" className="eu-iconbtn" aria-label={`Editar ${b.nombre}`} title="Editar" onClick={() => setForm({ budget: b })}><Icon name="pencil" /></button>
                    <button type="button" className="eu-iconbtn" aria-label={`Eliminar ${b.nombre}`} title="Eliminar" onClick={() => remove(b)}><Icon name="trash-2" /></button>
                  </div>
                  <div className="eu-between">
                    <span className="t-data">{money(b.gastado, { cents: false })} <span className="t-meta">de {money(b.limite, { cents: false })}</span></span>
                    <span className={`t-ui ${tone === 'success' ? 'fz-fg-3' : 'fz-tone-fg'}`}>{p} %</span>
                  </div>
                  <div className="eu-progress fz-progress-tone"><i style={{ width: `${Math.min(100, p)}%` }} /></div>
                  <div className="t-meta">
                    {b.gastado > b.limite
                      ? <span className="fz-tone-fg"><Icon name="octagon-alert" size={12} /> Excedido por {money(b.gastado - b.limite, { cents: false })}</span>
                      : p >= 85 ? <span className="fz-tone-fg"><Icon name="triangle-alert" size={12} /> Quedan {money(b.limite - b.gastado, { cents: false })}</span>
                        : `Libre ${money(b.limite - b.gastado, { cents: false })}`}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {form && <BudgetForm budget={form.budget} existing={budgets.map((b) => b.categoria)} onClose={() => setForm(null)} onSaved={saved} />}
    </div>
  );
}
