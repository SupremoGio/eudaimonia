import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// El build escribe UN solo archivo con nombre fijo en
// gio_v3/static/finanzas/assets/estados.js, que es lo que carga
// templates/finanzas/estados.html (<script type="module">). Sin hash en el
// nombre: la plantilla no cambia entre builds. Los estilos se importan con
// ?inline y se inyectan desde JS, así que no se genera un .css aparte.
const outDir = fileURLToPath(new URL('../../static/finanzas/assets', import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: '/static/finanzas/assets/',
  build: {
    outDir,
    emptyOutDir: false,
    target: 'es2020',
    sourcemap: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: fileURLToPath(new URL('./src/main.jsx', import.meta.url)),
      output: {
        format: 'es',
        entryFileNames: 'estados.js',
        inlineDynamicImports: true,
      },
    },
  },
  server: {
    // `npm run dev` levanta Vite en :5173 y reenvía la API a Flask (:5000).
    proxy: { '/finanzas': 'http://localhost:5000', '/static': 'http://localhost:5000' },
  },
});
