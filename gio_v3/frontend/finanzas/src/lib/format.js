const MXN = new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const MXN0 = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 0 });

export const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
export const MONTHS_LONG = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

/** $1,234.50 — magnitud; el signo lo decide quien llama (sign=true antepone − / +). */
export function money(n, { cents = true, sign = false } = {}) {
  const v = Number(n) || 0;
  const s = (cents ? MXN : MXN0).format(Math.abs(v));
  if (!sign) return `$${s}`;
  return `${v < 0 ? '−' : '+'}$${s}`;
}

export function pad(n) { return String(n).padStart(2, '0'); }
export function iso(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
export function todayISO() { return iso(new Date()); }
export function parseISO(s) {
  const [y, m, d] = String(s || '').slice(0, 10).split('-').map(Number);
  return new Date(y || 1970, (m || 1) - 1, d || 1);
}

/** 22 sep 2026 (o 22 sep si es del año en curso y short=true) */
export function fmtDate(s, short = false) {
  if (!s) return '';
  const d = parseISO(s);
  const base = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  return short && d.getFullYear() === new Date().getFullYear() ? base : `${base} ${d.getFullYear()}`;
}

export function dayLabel(s) {
  const t = todayISO();
  const y = new Date(); y.setDate(y.getDate() - 1);
  if (s === t) return `Hoy · ${fmtDate(s, true)}`;
  if (s === iso(y)) return `Ayer · ${fmtDate(s, true)}`;
  return fmtDate(s, true);
}

export function monthLabel(ym) {
  const [y, m] = String(ym).split('-').map(Number);
  return `${MONTHS[(m || 1) - 1]} ${y}`;
}

export const pct = (n, d) => (d > 0 ? Math.round((n / d) * 100) : 0);

/** Periodos predefinidos de Reportes → parámetros de la API. */
export const PRESETS = [
  { id: 'this_month', label: 'Este mes' },
  { id: 'last_month', label: 'Mes pasado' },
  { id: '3_months', label: '3 meses' },
  { id: '6_months', label: '6 meses' },
  { id: 'this_year', label: 'Este año' },
  { id: 'custom', label: 'Personalizado' },
];

export function presetRange(id) {
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth();
  switch (id) {
    case 'last_month':
      return { date_from: iso(new Date(y, m - 1, 1)), date_to: iso(new Date(y, m, 0)) };
    case '3_months':
      return { date_from: iso(new Date(y, m - 2, 1)), date_to: iso(now) };
    case '6_months':
      return { date_from: iso(new Date(y, m - 5, 1)), date_to: iso(now) };
    case 'this_year':
      return { date_from: `${y}-01-01`, date_to: iso(now) };
    case 'this_month':
    default:
      return { date_from: iso(new Date(y, m, 1)), date_to: iso(now) };
  }
}

/** Normaliza para búsquedas: minúsculas y sin acentos. */
export function norm(s) {
  return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/** Monto efectivo para el usuario: mi_parte si existe (siempre magnitud). */
export const myAmount = (t) => Math.abs(t.mi_parte != null ? t.mi_parte : t.monto);
