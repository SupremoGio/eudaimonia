import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import css from './estados.css?inline';
import App from './App.jsx';

// Estilos propios del SPA (solo var(--*) de app.css + clases eu-*). Se
// inyectan desde aquí para que el build siga siendo un único estados.js.
if (!document.getElementById('fz-styles')) {
  const style = document.createElement('style');
  style.id = 'fz-styles';
  style.textContent = css;
  document.head.appendChild(style);
}

const el = document.getElementById('estados-root') || document.getElementById('root');
// createRoot reemplaza el esqueleto de carga que trae la plantilla.
createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
