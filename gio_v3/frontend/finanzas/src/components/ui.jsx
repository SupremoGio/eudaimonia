import { createElement, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { catMeta } from '../lib/meta.js';

/* ── Icon: Lucide 1.31 (el global `lucide` que carga el layout) ─────────── */
const pascal = (n) => String(n).replace(/(^|-)([a-z0-9])/g, (_, __, c) => c.toUpperCase());
export function Icon({ name, size, className = '', label }) {
  const L = typeof window !== 'undefined' ? window.lucide : null;
  const node = L && ((L.icons && L.icons[pascal(name)]) || L[pascal(name)]);
  const kids = Array.isArray(node) ? (node[0] === 'svg' ? node[2] : node) : [];
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      width={size || 24} height={size || 24}
      className={`lucide lucide-${name} ${className}`.trim()}
      aria-hidden={label ? undefined : 'true'} role={label ? 'img' : undefined} aria-label={label}
    >
      {(kids || []).map(([tag, attrs], i) => createElement(tag, { key: i, ...attrs }))}
    </svg>
  );
}

/* ── Hooks ──────────────────────────────────────────────────────────────── */
export function useMedia(query) {
  const get = () => typeof window !== 'undefined' && window.matchMedia(query).matches;
  const [m, setM] = useState(get);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setM(mq.matches);
    mq.addEventListener('change', on);
    on();
    return () => mq.removeEventListener('change', on);
  }, [query]);
  return m;
}

/** Carga asíncrona con estado { data, loading, error, reload }. */
export function useLoad(fn, deps) {
  const [st, setSt] = useState({ data: null, loading: true, error: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setSt((s) => ({ ...s, loading: true, error: null }));
    Promise.resolve()
      .then(fn)
      .then((data) => alive && setSt({ data, loading: false, error: null }))
      .catch((error) => alive && setSt({ data: null, loading: false, error }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...st, reload: () => setTick((t) => t + 1) };
}

/* ── Globals del layout (toast, euConfirm, euRewardSheet) con fallback ── */
export const toast = (msg, kind = 'ok') => (window.toast ? window.toast(msg, kind) : undefined);
export const confirmDialog = (msg, opts) =>
  window.euConfirm ? window.euConfirm(msg, opts) : Promise.resolve(window.confirm(msg));

/* ── Modal / bottom sheet ───────────────────────────────────────────────
   Mismo markup que ui.modal() (eu-scrim > eu-modal): en ≥768 es un modal
   centrado, en móvil components.css lo convierte en bottom sheet. Foco
   atrapado, Esc cierra el de arriba de la pila, el foco vuelve al
   disparador y el scroll de la página se bloquea mientras hay alguno. */
const stack = [];
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function Modal({ title, eyebrow, onClose, size, children, footer, initialFocus = true, labelId }) {
  const ref = useRef(null);
  const autoId = useId();
  const tid = labelId || `fz-m-${autoId.replace(/:/g, '')}`;
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const opener = document.activeElement;
    const me = {};
    stack.push(me);
    document.documentElement.style.overflow = 'hidden';
    const el = ref.current;
    if (initialFocus && el) {
      const f = [...el.querySelectorAll(FOCUSABLE)];
      const first = f.find((n) => /INPUT|SELECT|TEXTAREA/.test(n.tagName)) || f[0];
      setTimeout(() => first && first.focus(), 10);
    }
    const onKey = (e) => {
      if (stack[stack.length - 1] !== me) return;
      if (e.key === 'Escape') { e.preventDefault(); closeRef.current(); return; }
      if (e.key === 'Tab' && el) {
        const f = [...el.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null);
        if (!f.length) return;
        const a = f[0], z = f[f.length - 1];
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      const i = stack.indexOf(me);
      if (i >= 0) stack.splice(i, 1);
      if (!stack.length) document.documentElement.style.overflow = '';
      if (opener && opener.focus && document.contains(opener)) opener.focus();
    };
  }, [initialFocus]);

  return createPortal(
    <div
      className="eu-scrim fz-scrim" data-cat="oikonomia" ref={ref}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className={`eu-modal fz-modal${size ? ` fz-modal--${size}` : ''}`} role="dialog" aria-modal="true" aria-labelledby={tid}>
        <div className="eu-modal-hd">
          <div className="eu-grow">
            {eyebrow && <div className="t-eyebrow">{eyebrow}</div>}
            <h2 className="t-section fz-modal-t" id={tid}>{title}</h2>
          </div>
          <button type="button" className="eu-iconbtn" aria-label="Cerrar" title="Cerrar" onClick={onClose}><Icon name="x" /></button>
        </div>
        {children}
        {footer && <div className="eu-modal-ft">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

/* ── Piezas pequeñas ────────────────────────────────────────────────────── */
export function Field({ label, help, error, htmlFor, children, className = '' }) {
  return (
    <div className={`eu-field ${className}`.trim()}>
      {label && <label className="eu-label" htmlFor={htmlFor}>{label}</label>}
      {children}
      {help && !error && <div className="eu-help">{help}</div>}
      {error && <div className="eu-err" role="alert"><Icon name="circle-alert" size={14} />{error}</div>}
    </div>
  );
}

export function Empty({ icon = 'inbox', title, text, children }) {
  return (
    <div className="eu-empty">
      <div className="eu-empty-ic"><Icon name={icon} /></div>
      <div className="t-card">{title}</div>
      {text && <p>{text}</p>}
      {children}
    </div>
  );
}

export function Skel({ rows = 3, h = 56 }) {
  return (
    <div className="fz-skel" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="eu-skel" style={{ height: `${h}px` }} />)}
    </div>
  );
}

export function CatIcon({ cat, size = 'md' }) {
  const m = catMeta(cat);
  const unc = !cat || cat === 'OTROS';
  return (
    <span className={`eu-row-ic fz-ic fz-ic--${size}${unc ? ' fz-ic--warn' : ''}`} data-cat={m.tone || undefined}>
      <Icon name={m.icon} />
    </span>
  );
}

export function CatBadge({ cat }) {
  if (!cat || cat === 'OTROS') return <span className="eu-badge eu-badge--warning">Sin categoría</span>;
  const m = catMeta(cat);
  return <span className="eu-badge eu-badge--cat" data-cat={m.tone || undefined}>{m.name}</span>;
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="fz-note" data-tone="danger" role="alert">
      <Icon name="circle-alert" size={16} />
      <span className="eu-grow">{error.message || 'No se pudo cargar.'}</span>
      {onRetry && <button type="button" className="eu-btn eu-btn--ghost eu-btn--sm" onClick={onRetry}>Reintentar</button>}
    </div>
  );
}

export function Kbd({ children }) {
  return <span className="kbd fz-kbd">{children}</span>;
}

export const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
export const saveKey = isMac ? '⌘↵' : 'Ctrl ↵';
