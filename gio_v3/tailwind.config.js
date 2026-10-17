/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './static/js/**/*.jsx',
  ],
  // Clases de components.css (@layer components) que Tailwind purgaría por
  // no aparecer literales en templates: los macros de _ui/ arman nombres
  // ('eu-btn--' ~ variant), Lucide agrega .lucide en runtime y hay estados
  // que solo pone JS (is-gaining, is-on, today…).
  safelist: [
    { pattern: /^eu-/ },
    { pattern: /^t-(hero|page|section|card|body|ui|meta|eyebrow|quote|data|data-xl|greek)$/ },
    { pattern: /^fg-/ },
    'num', 'kbd', 'lucide', 'is-gaining', 'is-on', 'is-now', 'is-past', 'is-earned',
    'is-locked', 'is-active', 'today', 'up', 'down', 'neg', 'pos', 'grow', 'ct', 'gr', 'r', 'fn',
  ],
  theme: {
    extend: {
      colors: {
        // Apuntan a las variables CSS de app.css (fuente única de verdad) en
        // vez de hex fijos, para que utilidades como text-dim / bg-surface
        // reaccionen solas al toggle claro/oscuro sin overrides !important.
        surface: 'var(--surf)',
        card: 'var(--card)',
        card2: 'var(--card2)',
        border: 'var(--b)',
        border2: 'var(--b2)',
        dim: 'var(--dim)',
        mid: 'var(--mid)',
        gio: {
          violet: 'var(--violet)',
          vl: 'var(--violet-l)',
          vd: 'var(--violet-d)',
          cyan: 'var(--cyan)',
          amber: 'var(--amber)',
          coral: 'var(--coral)',
          emerald: 'var(--emerald)',
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['"DM Sans"', 'sans-serif'],
        serif: ['"Cormorant Garamond"', 'serif'],
      },
    },
  },
  plugins: [],
};
