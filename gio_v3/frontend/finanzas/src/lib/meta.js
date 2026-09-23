// Presentación de categorías, bancos y tipos. El color sale del tono de una
// de las 10 categorías del sistema (data-cat → --cat-fg/bg/border en
// app.css): aquí solo se decide qué tono le toca a cada categoría de gasto.
export const CAT_META = {
  SUPER: { name: 'Súper', icon: 'shopping-cart', tone: 'harma' },
  COMIDA_FUERA: { name: 'Comida fuera', icon: 'utensils', tone: 'philia' },
  ALIMENTACION: { name: 'Alimentación', icon: 'utensils', tone: 'harma' }, // legado
  'CAFE/PAN': { name: 'Café & Pan', icon: 'coffee', tone: 'hegemonikon' },
  VIVIENDA: { name: 'Vivienda', icon: 'house', tone: 'oikonomia' },
  TRANSPORTE: { name: 'Transporte', icon: 'car', tone: 'cosmopolitismo' },
  'GASOLINA/AUTO': { name: 'Gasolina / Auto', icon: 'fuel', tone: 'cosmopolitismo' },
  SALUD: { name: 'Salud', icon: 'stethoscope', tone: 'ataraxia' },
  CUIDADO_PERSONAL: { name: 'Cuidado personal', icon: 'scissors', tone: 'eurythmia' },
  ROPA: { name: 'Ropa', icon: 'shirt', tone: 'identidad' },
  DIGITAL: { name: 'Digital', icon: 'laptop', tone: 'paideia' },
  'TECH/DIGITAL': { name: 'Tech / Digital', icon: 'cpu', tone: 'paideia' },
  SUSCRIPCIONES: { name: 'Suscripciones', icon: 'repeat', tone: 'paideia' },
  DEPORTE: { name: 'Deporte', icon: 'dumbbell', tone: 'logoi' },
  GYM: { name: 'Gym', icon: 'dumbbell', tone: 'logoi' },
  OCIO: { name: 'Ocio', icon: 'drama', tone: 'philia' },
  ENTRETENIMIENTO: { name: 'Entretenimiento', icon: 'clapperboard', tone: 'philia' },
  SALSA: { name: 'Salsa', icon: 'music', tone: 'eurythmia' },
  VIAJES: { name: 'Viajes', icon: 'plane', tone: 'cosmopolitismo' },
  FAMILIA_REGALOS: { name: 'Familia y regalos', icon: 'gift', tone: 'philia' },
  PROYECTOS: { name: 'Proyectos', icon: 'briefcase', tone: 'hegemonikon' },
  PUBLICIDAD: { name: 'Publicidad', icon: 'megaphone', tone: 'hegemonikon' },
  COSTOS_FINANCIEROS: { name: 'Costos financieros', icon: 'triangle-alert', tone: 'identidad' },
  APRENDIZAJE: { name: 'Aprendizaje', icon: 'book-open', tone: 'paideia' },
  INVERSION: { name: 'Inversión', icon: 'trending-up', tone: 'logoi' },
  NOMINA: { name: 'Nómina', icon: 'banknote', tone: 'ataraxia' },
  FINANZAS: { name: 'Finanzas', icon: 'landmark', tone: 'oikonomia' },
  PRESTAMOS: { name: 'Préstamos', icon: 'handshake', tone: 'oikonomia' },
  EXPENSE: { name: 'Expense (reembolsable)', icon: 'receipt', tone: 'cosmopolitismo' },
  OTROS: { name: 'Sin clasificar', icon: 'circle-help', tone: null },
};

export function catMeta(key) {
  if (!key) return CAT_META.OTROS;
  return CAT_META[key] || { name: prettify(key), icon: 'tag', tone: null };
}

export function prettify(key) {
  const s = String(key || '').replace(/_/g, ' ').toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const BANKS = [
  { id: 'BBVA_TDC', name: 'BBVA TDC', type: 'Crédito', icon: 'credit-card' },
  { id: 'BBVA_DEB', name: 'BBVA Débito', type: 'Débito', icon: 'wallet' },
  { id: 'INVEX', name: 'Invex', type: 'Crédito', icon: 'credit-card' },
  { id: 'HSBC', name: 'HSBC', type: 'Crédito', icon: 'credit-card' },
  { id: 'MANUAL', name: 'Manual', type: 'Efectivo', icon: 'hand-coins' },
];
export const bankName = (id) => (BANKS.find((b) => b.id === id) || { name: String(id || '').replace(/_/g, ' ') }).name;

export const TIPOS = [
  { id: 'GASTO', name: 'Gasto' },
  { id: 'INGRESO', name: 'Ingreso' },
  { id: 'PAGO', name: 'Pago' },
  { id: 'INVERSION', name: 'Inversión' },
  { id: 'PRESTAMO', name: 'Préstamo' },
  { id: 'COBRO_PRESTAMO', name: 'Cobro de préstamo' },
];
export const tipoName = (id) => (TIPOS.find((t) => t.id === id) || { name: id }).name;

/** Tonos ordinales para gráficas de categorías (donut, barras): 7 tonos del
 * sistema separados en el círculo cromático, asignados por rango. */
export const RANK_TONES = ['hegemonikon', 'cosmopolitismo', 'eurythmia', 'ataraxia', 'paideia', 'harma', 'logoi'];

/* Tonos (hue OKLCH) para el ranking de la dona de Reportes: 10 colores, uno
   por puesto. No reutiliza los tonos de categoría porque varios quedan casi
   iguales entre sí (philia 10 / harma 15, identidad 280 / paideia 265); estos
   se reparten en todo el círculo y alternan para que dos puestos seguidos
   nunca se parezcan. Misma luz/croma que --cat-fg en ambos temas. */
export const RANK_HUES = [45, 215, 330, 155, 265, 15, 120, 190, 85, 300];

export const NATURALEZA = {
  FIJO: { name: 'Fijo', tone: 'info' },
  VARIABLE: { name: 'Variable', tone: 'brand' },
  IRREGULAR: { name: 'Irregular', tone: 'warning' },
  EVITABLE: { name: 'Evitable', tone: 'danger' },
  SIN_CLASIFICAR: { name: 'Sin clasificar', tone: 'neutral' },
};
