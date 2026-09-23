import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { fmtDate, money } from '../lib/format.js';
import { bankName, catMeta, tipoName } from '../lib/meta.js';
import { categoryKeys, subcatsFor } from '../lib/store.js';
import { Icon, Kbd, saveKey, toast } from './ui.jsx';

const FREQUENT = ['ALIMENTACION', 'CAFE/PAN', 'TRANSPORTE', 'VIVIENDA', 'OCIO', 'DIGITAL', 'SALUD', 'ROPA'];
const STOP = new Set(['COMPRA', 'PAGO', 'CARGO', 'SPEI', 'TRANSFERENCIA', 'DE', 'EN', 'LA', 'EL', 'POR', 'MX', 'MEX', 'CDMX', 'SA', 'CV']);

/** Palabra clave sugerida para una regla a partir de la descripción del banco. */
export function suggestKeyword(desc) {
  const words = String(desc || '').toUpperCase().replace(/[^A-ZÁÉÍÓÚÑ0-9 ]/g, ' ').split(/\s+/)
    .filter((w) => w && !/^\d+$/.test(w) && !STOP.has(w));
  if (!words.length) return '';
  return words[0].length < 4 && words[1] ? `${words[0]} ${words[1]}` : words[0];
}

function parteInit(tx) {
  if (tx.mi_parte == null) return { mode: 'all', amount: '' };
  const half = Math.round((Math.abs(tx.monto) / 2) * 100) / 100;
  if (Math.abs(Math.abs(tx.mi_parte) - half) < 0.01) return { mode: 'half', amount: String(half) };
  return { mode: 'amount', amount: String(Math.abs(tx.mi_parte)) };
}

/**
 * Categorización rápida de un movimiento. Se usa en el drawer de escritorio
 * (variant="drawer") y en el bottom sheet de móvil (variant="sheet").
 */
export default function Categorizer({ tx, cats, trips, variant = 'drawer', onSaved, onClose, onMore, onPrev, onNext, headingId }) {
  const [categoria, setCategoria] = useState(tx.categoria || 'OTROS');
  const [sub, setSub] = useState(tx.subcategoria || '');
  const [parte, setParte] = useState(() => parteInit(tx));
  const [viaje, setViaje] = useState(tx.viaje_id != null ? String(tx.viaje_id) : '');
  const [showAll, setShowAll] = useState(false);
  const [kw, setKw] = useState(() => suggestKeyword(tx.descripcion));
  const [always, setAlways] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ruleBusy, setRuleBusy] = useState(false);

  // Al cambiar de movimiento (anterior/siguiente) se reinicia el formulario.
  useEffect(() => {
    setCategoria(tx.categoria || 'OTROS'); setSub(tx.subcategoria || ''); setParte(parteInit(tx));
    setViaje(tx.viaje_id != null ? String(tx.viaje_id) : ''); setKw(suggestKeyword(tx.descripcion)); setAlways(false);
    setShowAll(false);
  }, [tx]);

  const isGasto = tx.tipo === 'GASTO';
  const total = Math.abs(tx.monto);
  const keys = categoryKeys(cats, categoria);
  const picks = useMemo(() => {
    if (showAll) return keys;
    const base = [categoria, ...FREQUENT].filter((k, i, a) => k !== 'OTROS' && a.indexOf(k) === i && keys.includes(k));
    return base.slice(0, variant === 'sheet' ? 7 : 8);
  }, [showAll, keys, categoria, variant]);
  const subs = subcatsFor(cats, categoria, tx.tipo);
  const mine = parte.mode === 'all' ? total : parte.mode === 'half' ? Math.round((total / 2) * 100) / 100 : Math.min(total, parseFloat(parte.amount) || 0);

  const pickCat = (k) => { if (k !== categoria) { setCategoria(k); setSub(''); } };

  async function createRule(silent) {
    const keyword = kw.trim().toUpperCase();
    if (!keyword) { toast('Escribe la palabra clave de la regla', 'err'); return false; }
    setRuleBusy(true);
    try {
      const d = await api.post('/keywords', { keyword, categoria, subcategoria: sub, apply_to_existing: true });
      if (!silent) toast(`Regla creada · ${d.updated_transactions || 0} movimiento(s) actualizados`, 'ok');
      return d;
    } catch (e) { toast(e.message || 'No se pudo crear la regla', 'err'); return false; }
    finally { setRuleBusy(false); }
  }

  async function save() {
    if (busy) return;
    setBusy(true);
    const body = { categoria, subcategoria: sub };
    if (isGasto) {
      body.mi_parte = parte.mode === 'all' ? null : mine;
      body.viaje_id = viaje || null;
    }
    try {
      await api.patch(`/transactions/${tx.id}`, body);
      let extra = '';
      if (always) {
        const d = await createRule(true);
        if (d) extra = ` · regla «${kw.trim().toUpperCase()}» (${d.updated_transactions || 0})`;
      }
      toast(`Guardado: ${catMeta(categoria).name}${extra}`, 'ok');
      onSaved && onSaved({ ...tx, ...body, mi_parte: body.mi_parte ?? (isGasto ? null : tx.mi_parte) }, { advance: true });
    } catch (e) {
      toast(e.message || 'No se pudo guardar', 'err');
    } finally {
      setBusy(false);
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
  };

  const ingreso = tx.tipo === 'INGRESO';
  return (
    <div className={`fz-cz fz-cz--${variant}`} onKeyDown={onKeyDown}>
      {variant === 'drawer' && (
        <div className="eu-between fz-cz-bar">
          <span className="t-eyebrow">Movimiento</span>
          <div className="eu-hstack fz-gap-0">
            <button type="button" className="eu-iconbtn" aria-label="Anterior" title="Anterior (k)" onClick={onPrev} disabled={!onPrev}><Icon name="chevron-up" /></button>
            <button type="button" className="eu-iconbtn" aria-label="Siguiente" title="Siguiente (j)" onClick={onNext} disabled={!onNext}><Icon name="chevron-down" /></button>
            <button type="button" className="eu-iconbtn" aria-label="Cerrar" title="Cerrar" onClick={onClose}><Icon name="x" /></button>
          </div>
        </div>
      )}

      <div className="fz-cz-head">
        <div className={variant === 'sheet' ? 'eu-between fz-cz-sheet-hd' : ''}>
          <div className="fz-minw0">
            <h2 className="t-section fz-cz-t" id={headingId}>{tx.descripcion}</h2>
            {variant === 'sheet' && <div className="t-meta">{fmtDate(tx.fecha)} · {bankName(tx.banco)}</div>}
          </div>
          <div className={`${variant === 'sheet' ? 't-data fz-cz-amt-sm' : 't-data-xl fz-cz-amt'}${ingreso ? ' fg-success' : ''}`}>
            {ingreso ? '+' : '−'}{money(total)}
          </div>
        </div>
        {variant === 'drawer' && (
          <div className="t-meta">{fmtDate(tx.fecha)} · {bankName(tx.banco)} · {tipoName(tx.tipo)}</div>
        )}
        {(tx.parcialidad_num && tx.parcialidad_total) ? (
          <span className="eu-badge eu-badge--info">MSI {tx.parcialidad_num}/{tx.parcialidad_total}</span>
        ) : null}
      </div>

      <div className="eu-vstack fz-cz-sec">
        <span className="eu-label" id={`${headingId}-cat`}>Categoría{tx.categoria === 'OTROS' ? ' · sin clasificar' : ''}</span>
        <div className={`fz-catpick${variant === 'sheet' ? ' fz-catpick--4' : ''}`} role="radiogroup" aria-labelledby={`${headingId}-cat`}>
          {picks.map((k) => {
            const m = catMeta(k);
            return (
              <button key={k} type="button" role="radio" aria-checked={categoria === k} className="fz-cat-opt" data-cat={m.tone || undefined} onClick={() => pickCat(k)}>
                <Icon name={m.icon} /><span>{m.name}</span>
              </button>
            );
          })}
          {!showAll && (
            <button type="button" className="fz-cat-opt" onClick={() => setShowAll(true)}>
              <Icon name="ellipsis" /><span>Otra</span>
            </button>
          )}
        </div>
        {categoria !== 'EXPENSE' && (
          <select className="eu-select fz-input-sm" aria-label="Subcategoría" value={sub} onChange={(e) => setSub(e.target.value)}>
            <option value="">— Sin subcategoría —</option>
            {subs.map((s) => <option key={s} value={s}>{s}</option>)}
            {sub && !subs.includes(sub) && <option value={sub}>{sub}</option>}
          </select>
        )}
      </div>

      {isGasto && (
        <div className="eu-card fz-parte">
          <div className="eu-between">
            <span className="t-ui">Tu parte</span>
            <span className="eu-seg" role="radiogroup" aria-label="Tu parte">
              {[['all', 'Todo'], ['half', '50%'], ['amount', 'Monto']].map(([id, l]) => (
                <button key={id} type="button" role="radio" aria-checked={parte.mode === id} aria-selected={parte.mode === id}
                  onClick={() => setParte((p) => ({ mode: id, amount: id === 'amount' ? (p.amount || '') : p.amount }))}>{l}</button>
              ))}
            </span>
          </div>
          {parte.mode === 'amount' && (
            <input className="eu-input eu-input--money fz-input-sm" type="number" inputMode="decimal" min="0" step="0.01" max={total}
              aria-label="Monto que te corresponde" placeholder="0.00" value={parte.amount} onChange={(e) => setParte({ mode: 'amount', amount: e.target.value })} />
          )}
          <div className="eu-between"><span className="t-meta">Tú pagas</span><span className="t-data">{money(mine)}</span></div>
          {mine < total && <div className="eu-between"><span className="t-meta">Por cobrar</span><span className="t-data fz-fg-3">{money(total - mine)}</span></div>}
        </div>
      )}

      {isGasto && trips && trips.length > 0 && variant === 'drawer' && (
        <div className="eu-field">
          <label className="eu-label" htmlFor={`${headingId}-viaje`}>Viaje</label>
          <select id={`${headingId}-viaje`} className="eu-select fz-input-sm" value={viaje} onChange={(e) => setViaje(e.target.value)}>
            <option value="">Sin viaje</option>
            {trips.map((t) => <option key={t.id} value={String(t.id)}>{t.nombre || `Viaje ${t.id}`}</option>)}
          </select>
        </div>
      )}

      {variant === 'drawer' ? (
        <div className="fz-rule">
          <Icon name="wand-sparkles" size={16} className="fg-brand" />
          <div className="eu-grow fz-minw0">
            <div className="t-meta fz-fg-2">Crear regla: «{kw.trim().toUpperCase() || '…'}» → {catMeta(categoria).name}</div>
            <input className="eu-input fz-input-xs" aria-label="Palabra clave de la regla" value={kw} onChange={(e) => setKw(e.target.value)} />
          </div>
          <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={() => createRule(false).then((d) => d && onSaved && onSaved({ ...tx, categoria, subcategoria: sub }, { advance: false, rule: true }))} disabled={ruleBusy || categoria === 'OTROS'} aria-busy={ruleBusy || undefined}>Crear</button>
        </div>
      ) : (
        <label className="fz-always">
          <Icon name="wand-sparkles" size={16} className="fg-brand" />
          <span className="eu-grow t-ui">Aplicar siempre a «{kw.trim().toUpperCase() || '…'}»</span>
          <input type="checkbox" role="switch" className="fz-switch" checked={always} onChange={(e) => setAlways(e.target.checked)} disabled={categoria === 'OTROS'} />
        </label>
      )}

      <div className={variant === 'sheet' ? 'eu-vstack' : 'eu-hstack fz-cz-actions'}>
        {variant === 'drawer' && <button type="button" className="eu-btn eu-btn--ghost" onClick={onMore}>Más campos</button>}
        <button type="button" className={`eu-btn eu-btn--primary${variant === 'sheet' ? ' eu-btn--lg eu-btn--block' : ''}`} onClick={save} disabled={busy} aria-busy={busy || undefined}>
          Guardar {variant === 'drawer' && <Kbd>{saveKey}</Kbd>}
        </button>
        {variant === 'sheet' && <button type="button" className="eu-btn eu-btn--ghost eu-btn--block" onClick={onMore}>Editar todos los campos</button>}
      </div>
    </div>
  );
}
