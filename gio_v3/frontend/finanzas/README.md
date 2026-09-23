# Finanzas · Estados de cuenta (SPA)

Fuente de la página `/finanzas/estados/` (`templates/finanzas/estados.html`).
Vite + React, sin TypeScript. El build escribe **un solo archivo** con nombre
fijo: `gio_v3/static/finanzas/assets/estados.js`, que la plantilla carga con
`<script type="module">`. Ese archivo se commitea ya compilado (Railway no
corre Node en el deploy, igual que con Tailwind).

## Compilar

```bash
cd gio_v3/frontend/finanzas
npm install          # solo la primera vez
npm run build        # → ../../static/finanzas/assets/estados.js
```

Después de cualquier cambio en `src/`, corre `npm run build` y commitea
también `static/finanzas/assets/estados.js`.

- `npm run watch` recompila al guardar (útil con `python gio_v3/run.py`
  corriendo: basta recargar la página).
- `npm run dev` levanta Vite en `:5173` con proxy de `/finanzas` y `/static`
  a Flask en `:5000`. Hay que haber iniciado sesión en `:5000` en el mismo
  navegador para que la API responda.

## Estructura

```
src/
  main.jsx            monta <App/> en #estados-root e inyecta estados.css
  App.jsx             cabecera, pestañas (hash #movimientos…), alertas, modales globales
  estados.css         composición propia (prefijo fz-): SOLO var(--*) de app.css
  lib/api.js          cliente de /finanzas/estados/api/* (window.__EU_API_BASE__)
  lib/format.js       dinero, fechas, periodos de Reportes
  lib/meta.js         nombre/ícono/tono de cada categoría, bancos, tipos
  lib/store.js        catálogos cacheados (categorías, viajes) y alertas vistas
  views/              Resumen, Movimientos, Cuentas, Presupuestos, Reglas, Reportes
  components/         Categorizer (drawer/sheet), TxEditor, ImportModal,
                      CategoryModal, FlowBars, AccountCard, ui.jsx (Icon, Modal…)
```

## Reglas de estilo

- Solo tokens `var(--*)` (`static/css/app.css`) y componentes `eu-*`
  (`static/css/components.css`). Nada de hex, rgb ni paletas tipo slate.
- Color de categoría = uno de los 10 tonos del sistema vía `data-cat`
  (ver `CAT_META` en `lib/meta.js`); estados con `data-tone`.
- Íconos: `<Icon name="…"/>` dibuja el SVG desde el Lucide 1.31 global que
  ya carga el layout (no se empaqueta lucide).
- Modales con el mismo markup que `ui.modal()` (`eu-scrim > eu-modal`): en
  móvil se vuelven bottom sheet solos.

## API usada

Los mismos endpoints que el bundle anterior: `transactions` (GET/POST/PATCH/
DELETE, `export/csv`), `summary/{overview,monthly,by-category,by-naturaleza,
pendientes,stats,banks}`, `accounts`, `loans`, `budgets`, `categories`,
`keywords` (+ `apply-all`), `trips`, `expenses/<id>/conciliar`, `upload`, y
los reportes de solo lectura `/finanzas/estados/admin/audit-duplicados` y
`audit-nomina-sospechosa`.
