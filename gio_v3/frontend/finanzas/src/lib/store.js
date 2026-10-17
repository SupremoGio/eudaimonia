import { api } from './api.js';

// Catálogos que casi no cambian: se piden una vez por carga de página.
let catsP = null;
let tripsP = null;

export function getCategories() {
  if (!catsP) catsP = api.get('/categories').catch((e) => { catsP = null; throw e; });
  return catsP;
}

export function getTrips() {
  if (!tripsP) tripsP = api.get('/trips').then((d) => (Array.isArray(d) ? d : d.data || [])).catch(() => { tripsP = null; return []; });
  return tripsP;
}

/** Claves de categoría para selects: taxonomía actual + EXPENSE (+ la actual si es legacy). */
export function categoryKeys(cats, current) {
  const keys = (cats || []).map((c) => c.categoria);
  if (!keys.includes('EXPENSE')) keys.push('EXPENSE');
  if (current && !keys.includes(current)) keys.push(current);
  return keys;
}

export function subcatsFor(cats, categoria, tipo) {
  const subs = ((cats || []).find((c) => c.categoria === categoria) || {}).subcategorias || [];
  // VIVIENDA: «Renta» es del lado gasto y «Aportación renta» del lado ingreso.
  return subs.filter((s) => !(categoria === 'VIVIENDA' && (tipo === 'INGRESO' ? s === 'Renta' : s === 'Aportación renta')));
}

/* Alertas de presupuesto ya vistas (misma clave que el bundle anterior). */
const SEEN_KEY = 'eu_finanzas_alerts_seen';
export function alertKey(b) {
  const d = new Date();
  const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return `${b.id}:${ym}:${Math.abs(b.gastado) > b.limite ? 'exceeded' : 'warning'}`;
}
export function readSeen() {
  try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); } catch { return new Set(); }
}
export function writeSeen(set) {
  try { localStorage.setItem(SEEN_KEY, JSON.stringify([...set])); } catch { /* sin storage */ }
}
export const budgetAlerts = (budgets) => (budgets || []).filter((b) => b.limite > 0 && Math.abs(b.gastado) / b.limite >= 0.85);
