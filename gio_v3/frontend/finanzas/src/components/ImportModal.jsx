import { useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { fmtDate, money } from '../lib/format.js';
import { Icon, Modal, toast } from './ui.jsx';

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

function Notice({ tone = 'info', icon, children }) {
  return (
    <div className="fz-note" data-tone={tone}>
      <Icon name={icon} size={16} />
      <div className="eu-grow">{children}</div>
    </div>
  );
}

/** Subir un estado de cuenta (PDF, CSV o Excel) a /upload y mostrar lo que pasó. */
export default function ImportModal({ onClose, onImported }) {
  const input = useRef(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [res, setRes] = useState(null);
  const [done, setDone] = useState({});

  // Varios archivos (re-subir estados viejos corrige la dirección cargo/abono
  // de lo ya guardado): se suben uno por uno y los resultados se suman.
  function merge(a, b) {
    if (!a) return b;
    const out = { ...a };
    for (const [k, v] of Object.entries(b)) {
      if (typeof v === 'number' && typeof a[k] === 'number') out[k] = a[k] + v;
      else if (Array.isArray(v) && Array.isArray(a[k])) out[k] = a[k].concat(v);
      else if (v != null && a[k] == null) out[k] = v;
    }
    if (a.bank && b.bank && a.bank !== b.bank) out.bank = '';
    return out;
  }

  async function upload(files) {
    const list = Array.from(files || []).filter(Boolean);
    if (!list.length || busy) return;
    setBusy(true); setErr(''); setRes(null); setDone({});
    try {
      let data = null;
      const fallos = [];
      for (const file of list) {
        const d = await api.upload(file);
        if (d && d.ok === false) fallos.push(`${file.name}: ${d.error || 'sin transacciones'}`);
        else data = merge(data, d);
      }
      if (fallos.length) setErr(fallos.join(' · '));
      if (data) {
        setRes(data);
        onImported && onImported();
        const gam = data && data.gamification;
        if (gam && (gam.xp || gam.ec) && window.euRewardSheet) {
          const n = data.inserted || 0;
          window.euRewardSheet({
            icon: 'sparkles',
            eyebrow: 'Estado de cuenta importado',
            title: `+${gam.xp || 0} XP · +${gam.ec || 0} EC`,
            desc: `${n} movimiento${n === 1 ? '' : 's'} nuevo${n === 1 ? '' : 's'} registrado${n === 1 ? '' : 's'}`,
            burst: true,
          });
        }
      }
    } catch (e) {
      setErr(e.message && !/^Error \d+$/.test(e.message) ? e.message : 'Error al subir el archivo.');
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  async function act(key, fn, okMsg) {
    try { await fn(); setDone((d) => ({ ...d, [key]: true })); toast(okMsg, 'ok'); onImported && onImported(); }
    catch (e) { toast(e.message || 'No se pudo completar.', 'err'); }
  }

  const r = res || {};
  return (
    <Modal title="Importar estado de cuenta" eyebrow="PDF · CSV · Excel" onClose={onClose}
      footer={<button type="button" className="eu-btn eu-btn--secondary" onClick={onClose}>{res ? 'Listo' : 'Cancelar'}</button>}>
      <div className="eu-modal-bd">
        <button
          type="button"
          className={`fz-drop${drag ? ' is-drag' : ''}`}
          aria-busy={busy || undefined}
          aria-describedby="fz-drop-help"
          onClick={() => input.current && input.current.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
          disabled={busy}
        >
          <span className="eu-empty-ic"><Icon name={busy ? 'loader-circle' : 'upload'} className={busy ? 'fz-spin' : ''} /></span>
          <span className="t-ui">{busy ? 'Procesando…' : 'Arrastra tus PDF o CSV aquí'}</span>
          <span className="t-meta" id="fz-drop-help">o toca para elegir uno o varios archivos · BBVA, Invex, HSBC</span>
        </button>
        <input ref={input} type="file" accept=".pdf,.csv,.xlsx,.xls" multiple hidden onChange={(e) => upload(e.target.files)} />

        {err && <Notice tone="danger" icon="circle-alert">{err}</Notice>}

        {res && (
          <div className="eu-vstack fz-import-res" aria-live="polite">
            <Notice tone="success" icon="circle-check">
              <b>{plural(r.inserted || 0, 'movimiento importado', 'movimientos importados')}</b>{r.bank ? ` · ${r.bank}` : ''}
              {r.skipped > 0 && <div className="t-meta">{plural(r.skipped, 'duplicado omitido', 'duplicados omitidos')}</div>}
            </Notice>
            {r.dedup_conflict > 0 && (
              <Notice tone="warning" icon="triangle-alert">
                {plural(r.dedup_conflict, 'transacción no guardada', 'transacciones no guardadas')} (coincide fecha + descripción con otra existente) — revísalo a mano.
              </Notice>
            )}
            {r.direcciones_corregidas && r.direcciones_corregidas.length > 0 && (
              <Notice tone="info" icon="arrow-left-right">
                {plural(r.direcciones_corregidas.length, 'movimiento ya guardado cambió', 'movimientos ya guardados cambiaron')} de dirección
                (entrada/salida) según los totales del estado de cuenta.
                <ul className="fz-import-list">
                  {r.direcciones_corregidas.slice(0, 20).map((d) => (
                    <li key={d.id} className="t-meta">{fmtDate(d.fecha, true)} · {d.descripcion} · {money(d.monto)} → {d.ahora === 'INGRESO' ? 'entrada' : 'salida'}</li>
                  ))}
                </ul>
              </Notice>
            )}
            {r.direcciones_revisar && r.direcciones_revisar.length > 0 && (
              <Notice tone="warning" icon="triangle-alert">
                {plural(r.direcciones_revisar.length, 'movimiento ligado', 'movimientos ligados')} a un préstamo trae la dirección al revés — revísalo en Por cobrar:
                <ul className="fz-import-list">
                  {r.direcciones_revisar.map((d) => (
                    <li key={d.id} className="t-meta">{fmtDate(d.fecha, true)} · {d.descripcion} · {money(d.monto)} → {d.ahora === 'INGRESO' ? 'entrada' : 'salida'}</li>
                  ))}
                </ul>
              </Notice>
            )}
            {r.review_needed && r.review_needed.length > 0 && (
              <Notice tone="info" icon="inbox">{plural(r.review_needed.length, 'depósito pendiente', 'depósitos pendientes')} de clasificar.</Notice>
            )}
            {r.movimiento_interno_reclasificados > 0 && (
              <Notice tone="info" icon="arrow-left-right">
                {plural(r.movimiento_interno_reclasificados, 'pago de tarjeta reclasificado', 'pagos de tarjeta reclasificados')} a movimiento interno.
              </Notice>
            )}
            {r.avisos_msi && r.avisos_msi.length > 0 && (
              <Notice tone="warning" icon="triangle-alert">
                {plural(r.avisos_msi.length, 'aviso', 'avisos')} de posible doble conteo en compras a MSI — revísalo a mano.
              </Notice>
            )}

            {r.sugerencias_viaje_tabasco && r.sugerencias_viaje_tabasco.length > 0 && (
              <div className="eu-card eu-card--inset fz-sugg">
                <div className="t-ui eu-hstack"><Icon name="plane" size={16} />{plural(r.sugerencias_viaje_tabasco.length, 'gasto', 'gastos')} posiblemente de un viaje</div>
                {r.sugerencias_viaje_tabasco.map((s) => (
                  <div key={s.id} className="eu-between fz-sugg-row">
                    <span className="eu-grow t-meta fz-ellipsis">{s.descripcion} · <span className="num">{money(s.monto)}</span> · {s.viaje_nombre}</span>
                    {done[`v${s.id}`]
                      ? <span className="eu-badge eu-badge--success"><Icon name="check" />Asignado</span>
                      : <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" onClick={() => act(`v${s.id}`, () => api.patch(`/transactions/${s.id}`, { viaje_id: s.viaje_id }), 'Gasto asignado al viaje')}>Asignar</button>}
                  </div>
                ))}
              </div>
            )}

            {r.sugerencias_reembolso && r.sugerencias_reembolso.length > 0 && (
              <div className="eu-card eu-card--inset fz-sugg">
                <div className="t-ui eu-hstack"><Icon name="undo-2" size={16} />{plural(r.sugerencias_reembolso.length, 'posible reembolso recibido', 'posibles reembolsos recibidos')}</div>
                {r.sugerencias_reembolso.map((s) => (
                  <div key={s.expense_id} className="eu-between fz-sugg-row">
                    <span className="eu-grow t-meta fz-ellipsis">{s.expense_descripcion} (<span className="num">{money(s.expense_monto)}</span>) ← {s.deposito_descripcion}</span>
                    {done[`r${s.expense_id}`]
                      ? <span className="eu-badge eu-badge--success"><Icon name="check" />Conciliado</span>
                      : <button type="button" className="eu-btn eu-btn--secondary eu-btn--sm" onClick={() => act(`r${s.expense_id}`, () => api.post(`/expenses/${s.expense_id}/conciliar`, { fecha_reembolso: s.deposito_fecha }), 'Reembolso conciliado')}>Conciliar</button>}
                  </div>
                ))}
              </div>
            )}

            {r.avisos_posible_duplicado && r.avisos_posible_duplicado.length > 0 && (
              <div className="eu-card eu-card--inset fz-sugg" data-tone="warning">
                <div className="t-ui eu-hstack fz-tone-fg"><Icon name="copy" size={16} />{plural(r.avisos_posible_duplicado.length, 'posible duplicado', 'posibles duplicados')} — mismo día y monto que uno que ya tenías</div>
                {r.avisos_posible_duplicado.map((a) => (
                  <div key={a.id} className="t-meta fz-sugg-row">
                    {fmtDate(a.fecha, true)} · <span className="num">{money(a.monto)}</span> · {a.descripcion} ({a.banco}) ↔ {a.posible_duplicado_descripcion} ({a.posible_duplicado_banco})
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
