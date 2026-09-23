import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from './lib/api.js';
import { AppCtx } from './lib/ctx.js';
import { alertKey, budgetAlerts, readSeen, writeSeen } from './lib/store.js';
import { money, pct } from './lib/format.js';
import { Icon, Modal, Empty } from './components/ui.jsx';
import Resumen from './views/Resumen.jsx';
import Movimientos from './views/Movimientos.jsx';
import Cuentas from './views/Cuentas.jsx';
import Presupuestos from './views/Presupuestos.jsx';
import Reglas from './views/Reglas.jsx';
import Reportes from './views/Reportes.jsx';
import TxEditor from './components/TxEditor.jsx';
import ImportModal from './components/ImportModal.jsx';
import CategoryModal from './components/CategoryModal.jsx';

const TABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'movimientos', label: 'Movimientos' },
  { id: 'cuentas', label: 'Cuentas' },
  { id: 'presupuestos', label: 'Presupuestos' },
  { id: 'reglas', label: 'Reglas' },
  { id: 'reportes', label: 'Reportes' },
];
const VIAJES_URL = '/finanzas/estados/viajes/';

const tabFromHash = () => {
  const h = (window.location.hash || '').replace('#', '');
  return TABS.some((t) => t.id === h) ? h : 'resumen';
};

export default function App() {
  const [tab, setTab] = useState(tabFromHash);
  const [txFilter, setTxFilter] = useState(null); // filtros iniciales al saltar a Movimientos
  const [refreshKey, setRefreshKey] = useState(0);
  const [unclassified, setUnclassified] = useState(0);
  const [budgets, setBudgets] = useState([]);
  const [seen, setSeen] = useState(readSeen);
  const [modal, setModal] = useState(null); // {kind:'tx'|'new'|'import'|'cat'|'alerts', ...}

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    const on = () => setTab(tabFromHash());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  useEffect(() => {
    api.get('/summary/stats').then((d) => setUnclassified(d.unclassified || 0)).catch(() => {});
    api.get('/budgets').then((d) => setBudgets(d || [])).catch(() => {});
  }, [refreshKey]);

  const selectTab = useCallback((id, filter) => {
    setTxFilter(filter || null);
    setTab(id);
    try { window.history.replaceState(null, '', `#${id}`); } catch { /* noop */ }
    window.scrollTo({ top: 0 });
  }, []);

  const alerts = budgetAlerts(budgets);
  const unseen = alerts.some((b) => !seen.has(alertKey(b)));
  const openAlerts = () => {
    const next = new Set(seen);
    alerts.forEach((b) => next.add(alertKey(b)));
    writeSeen(next);
    setSeen(next);
    setModal({ kind: 'alerts' });
  };

  const ctx = useMemo(() => ({
    refreshKey,
    refresh,
    unclassified,
    budgets,
    goTo: selectTab,
    openTx: (tx) => setModal({ kind: 'tx', tx }),
    openNew: () => setModal({ kind: 'new' }),
    openImport: () => setModal({ kind: 'import' }),
    openCategory: (opts) => setModal({ kind: 'cat', ...opts }),
  }), [refreshKey, refresh, unclassified, budgets, selectTab]);

  const close = () => setModal(null);
  // El modal de categoría puede abrir el editor encima; al cerrar éste se vuelve a él.
  const [catBehind, setCatBehind] = useState(null);

  let view;
  switch (tab) {
    case 'movimientos': view = <Movimientos key={`m${JSON.stringify(txFilter)}`} initial={txFilter} />; break;
    case 'cuentas': view = <Cuentas />; break;
    case 'presupuestos': view = <Presupuestos />; break;
    case 'reglas': view = <Reglas />; break;
    case 'reportes': view = <Reportes />; break;
    default: view = <Resumen />;
  }

  return (
    <AppCtx.Provider value={ctx}>
      <div className="fz" data-cat="oikonomia">
        <header className="fz-hd">
          <div className="fz-hd-t">
            <div className="t-eyebrow">Oikonomia · Finanzas</div>
            <h1 className="t-page">Estados de cuenta</h1>
          </div>
          <div className="eu-hstack fz-hd-actions">
            <button type="button" className="eu-iconbtn eu-iconbtn--outline fz-bell" onClick={openAlerts}
              aria-label={`Alertas de presupuesto${alerts.length ? ` (${alerts.length})` : ''}`} title="Alertas de presupuesto">
              <Icon name="bell" />
              {unseen && <span className="fz-bell-dot" aria-hidden="true" />}
            </button>
            <button type="button" className="eu-btn eu-btn--secondary" onClick={() => setModal({ kind: 'import' })}>
              <Icon name="upload" /><span className="fz-hide-sm">Subir estado de cuenta</span><span className="fz-show-sm">Importar</span>
            </button>
            <button type="button" className="eu-btn eu-btn--primary" onClick={() => setModal({ kind: 'new' })}>
              <Icon name="plus" /><span>Nuevo</span>
            </button>
          </div>
        </header>

        <nav className="eu-tabs fz-tabs" aria-label="Secciones de estados de cuenta">
          {/* El enlace a Gastos de viaje (otra página) va fuera del tablist. */}
          <div className="fz-tablist" role="tablist" aria-label="Secciones de estados de cuenta">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" id={`fz-tab-${t.id}`} aria-selected={tab === t.id}
              aria-controls="fz-panel" onClick={() => selectTab(t.id)}>
              {t.label}
              {t.id === 'movimientos' && unclassified > 0 && (
                <span className="eu-badge eu-badge--warning fz-tab-ct" title={`${unclassified} sin categoría este mes`}>{unclassified}</span>
              )}
            </button>
          ))}
          </div>
          <a className="fz-tab-link" href={VIAJES_URL}>Gastos de viaje<Icon name="arrow-up-right" size={14} /></a>
        </nav>

        <section id="fz-panel" role="tabpanel" aria-labelledby={`fz-tab-${tab}`} className="fz-panel">
          {view}
        </section>
      </div>

      {modal?.kind === 'tx' && (
        <TxEditor tx={modal.tx} onClose={() => { close(); if (catBehind) { setModal(catBehind); setCatBehind(null); } }}
          onSaved={refresh} />
      )}
      {modal?.kind === 'new' && <TxEditor onClose={close} onSaved={refresh} />}
      {modal?.kind === 'import' && <ImportModal onClose={close} onImported={refresh} />}
      {modal?.kind === 'cat' && (
        <CategoryModal {...modal} onClose={close}
          onOpenTx={(tx) => { setCatBehind(modal); setModal({ kind: 'tx', tx }); }} />
      )}
      {modal?.kind === 'alerts' && (
        <Modal title="Alertas de presupuesto" eyebrow="Este mes" onClose={close}>
          <div className="eu-modal-bd">
            {alerts.length === 0 ? (
              <Empty icon="circle-check" title="Todo en orden" text="Ningún presupuesto pasa del 85 % este mes." />
            ) : (
              <div className="eu-list fz-list-inset">
                {alerts.map((b) => {
                  const g = Math.abs(b.gastado);
                  const over = g > b.limite;
                  return (
                    <div key={b.id} className="eu-row" data-tone={over ? 'danger' : 'warning'}>
                      <span className="eu-row-ic fz-ic--tone"><Icon name={over ? 'octagon-alert' : 'triangle-alert'} /></span>
                      <div className="eu-row-main">
                        <div className="eu-row-t">{b.nombre}</div>
                        <div className="eu-row-s fz-tone-fg">{over ? `Excedido por ${money(g - b.limite)}` : `${pct(g, b.limite)} % usado`}</div>
                      </div>
                      <div className="eu-row-end"><span className="t-data">{money(g)}</span><div className="t-meta">de {money(b.limite, { cents: false })}</div></div>
                    </div>
                  );
                })}
              </div>
            )}
            <button type="button" className="eu-btn eu-btn--secondary" onClick={() => { close(); selectTab('presupuestos'); }}>
              Ver presupuestos<Icon name="arrow-right" />
            </button>
          </div>
        </Modal>
      )}
    </AppCtx.Provider>
  );
}
