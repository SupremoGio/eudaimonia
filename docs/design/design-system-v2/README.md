# Handoff: Eudaimonia OS — Design System V2

## Overview
Un rediseño completo del sistema visual de Eudaimonia OS (`SupremoGio/eudaimonia`, carpeta `gio_v3/`). Incluye:
- tokens de diseño para los temas oscuro y claro, con contraste AA;
- una librería de componentes `eu-*`;
- navegación unificada (sidebar, bottom nav, topbar y ⌘K);
- 10 pantallas en móvil (390 px) y desktop (1440 px);
- una auditoría UX y un plan de migración en 5 fases.

**Nada de esto cambia la funcionalidad, las rutas ni los endpoints `/api`.**

## About the Design Files
Los archivos en `referencia/` son **diseños de referencia hechos en HTML**. Muestran el aspecto y el comportamiento que se busca, pero no son código de producción. La tarea es **recrearlos dentro del stack actual**: Flask + Jinja2 + Tailwind 3.4 + JS vanilla + Lucide.

La excepción son estos archivos, que sí están pensados para copiarse tal cual:
- `css/tokens.css` → contenido de variables de `gio_v3/static/css/app.css`
- `css/components.css` → `@layer components`
- `jinja/_ui/macros.html` → `gio_v3/templates/_ui/macros.html`

## Fidelity
**Alta fidelidad.** Colores, tipografía, espaciado, radios, estados y motion son los definitivos. Hay que reproducir las pantallas con fidelidad de píxel, pero usando los macros y las clases `eu-*`, no copiando el HTML de las maquetas. Las maquetas usan JS para generar listas repetidas; en la app, esas listas se hacen con bucles Jinja.

---

## Cómo implementarlo (lee esto primero)
1. Descarga esta carpeta y cópiala a la raíz del repo como `design_handoff_design_system_v2/`.
2. Abre Claude Code en el repo.
3. Pega **un prompt a la vez** desde `PROMPTS.md` (Fase 1 → 5). Cada fase tiene criterios de aceptación y se puede desplegar por separado.
4. Después de cada fase:
   - corre `npm run build:css` desde `gio_v3/` y commitea `tailwind-built.css`;
   - corre `pytest`;
   - revisa la app en iPhone y en desktop, en los dos temas.

---

## Design Tokens (fuente: `css/tokens.css`)
### Color — oscuro (default)
| Token | Valor | Uso |
|---|---|---|
| `--bg-canvas` | `#09070F` | fondo de la app |
| `--bg-sunken` | `#0F0C1A` | sidebar, nav, zonas hundidas |
| `--bg-surface` | `#1A1627` | tarjetas |
| `--bg-raised` | `#221D32` | inputs, elementos anidados, popovers |
| `--bg-hover` | `#2B2540` | hover |
| `--border-subtle` / `default` / `strong` | `rgba(242,237,224,.06/.10/.18)` | bordes **neutros** |
| `--border-brand` | `rgba(201,168,76,.34)` | solo énfasis |
| `--fg-1` | `#F2EDE0` | texto principal (15.6:1) |
| `--fg-2` | `#C2B69E` | texto secundario (9.4:1) |
| `--fg-3` | `#978870` | meta y labels (5.1:1, AA) |
| `--fg-4` | `#6A6050` | **solo** deshabilitado |
| `--brand` | `#C9A84C` | marca, CTA, foco |
| `--fg-brand-strong` / `--xp-fg` | `#E8C96D` | cifras de XP |
| `--fg-on-brand` | `#09070F` | texto sobre oro (8.7:1) |
| `--ec-fg` | `#D9D0AE` | Euda-Credits (electrum) |
| success / warning / danger / info | `oklch(.79 .12 158)` / `oklch(.84 .12 82)` / `oklch(.74 .14 22)` / `oklch(.79 .08 240)` | cada uno con `-bg` y `-border` |
| tiers | carbón `#9A93A6` · hierro `#AEB8C6` · oro `#E8C96D` · diamante `#A9DDE8` | clasificación diaria |
| rareza | bronce `#CF9A73` · plata `#C9CED6` · oro `#E8C96D` · especial `#A9DDE8` | badges |

El tema claro está en `html.light`: canvas `#F5F0E7`, surface `#FFFFFF`, texto `#1C1610 / #4F4230 / #6E5E42`, marca `#8B6914`.

**Categorías:** cualquier elemento con `data-cat="oikonomia"` recibe `--cat-fg`, `--cat-bg` y `--cat-border`, calculados con `oklch()` a partir de `CATEGORY_HUES` (`ec_constants.py`). **Se elimina todo `:nth-child` de color.**

**Alias legacy:** `--bg --surf --card --card2 --b --b2 --gold --gold-l --text --mid --dim --muted --fs-*` siguen existiendo y apuntan a los tokens nuevos. Por eso la Fase 1 no rompe nada.

### Tipografía
| Rol | Clase | Spec |
|---|---|---|
| Hero | `.t-hero` | Cormorant 600 · 40 px (56 ≥1024) · lh 1.05 · −.01em |
| Página | `.t-page` | Cormorant 600 · 28 (32 ≥1024) · 1.2 |
| Sección | `.t-section` | Cormorant 600 · 20 (24 ≥1024) · 1.2 |
| Tarjeta | `.t-card` | Cormorant 600 · 17 · 1.2 · +.01em |
| Cita | `.t-quote` | Cormorant italic 400 · 20 · 1.4 |
| Cuerpo | `.t-body` | DM Sans 400 · 15 · 1.6 |
| UI / nav | `.t-ui` | DM Sans 500 · 13 · 1.45 |
| Meta | `.t-meta` | DM Sans 400 · 12 · `--fg-3` |
| Eyebrow | `.t-eyebrow` | DM Sans 500 · 11 · MAYÚSCULAS · .14em · oro |
| Dato XL | `.t-data-xl` | JetBrains Mono 500 · 32 · tabular · −.02em |
| Dato | `.t-data` | JetBrains Mono 500 · 15 · tabular |

Reglas:
- El mínimo es **12 px**. Los 11 px solo se permiten en eyebrows.
- Mayúsculas solo en eyebrows y chips de estado, con un máximo de 2 niveles por pantalla.
- Todos los montos, XP y EC van en JetBrains Mono.

### Espaciado · radios · elevación · motion
- **Espaciado** (base 4): `--sp-1…--sp-20` = 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80. **No se permite ningún otro valor.**
- **Gutter:** 16 / 32 (≥768) / 40 (≥1280).
- **Padding de tarjeta:** 16 / 20.
- **Separación entre secciones:** 32 / 48.
- **Radios:** xs 4 · sm 8 (botones e inputs) · md 12 · lg 16 (tarjetas) · xl 24 (modal y sheet) · full.
- **Elevación:** `--e-1` es un filo interior de 1 px (tarjetas); `--e-2` y `--e-3` son sombras solo para lo que flota. `--glow-brand` se usa **solo** en el momento de recompensa.
- **Duración:** instant 80 · fast 140 · base 220 · slow 360 · deliberate 600 · ceremony 1200.
- **Easing:** standard `(.2,0,0,1)` · enter `(0,0,.2,1)` · exit `(.4,0,1,1)` · emphasis `(.3,0,0,1)` · settle `(.34,1.25,.64,1)`.
- **Prohibido:** animaciones infinitas en reposo (float, wiggle y pulse de íconos).
- **Breakpoints:** 640 · 768 · 1024 · 1280, los de Tailwind por defecto.

### Iconos
Se usa **solo Lucide 1.31** (ya está en el repo), con trazo 1.5 y tamaños 16, 20 o 24. **Se quitan los emojis y Flaticon.**

Íconos por módulo:
- logoi `code-2`
- hegemonikon `heart-pulse`
- oikonomia `landmark`
- cosmopolitismo `languages`
- paideia `book-open`
- ataraxia `sun-dim`
- eurythmia `music-2`
- harma `car`
- identidad `user-round`
- acta `scroll-text`
- praxis `list-checks`
- plantas `sprout`
- guardarropa `shirt`
- logros `trophy`
- recompensas `gift`
- EC `coins`

---

## Navegación
- **Bottom nav (móvil, 5 pestañas):**
  - Inicio `/`
  - Acta `/actividades/`
  - Praxis `/gtd/`
  - **Módulos**: abre un sheet con grid 4×3 de todos los módulos
  - **Tú** `/perfil/` (con accesos a Logros y Recompensas)

  Alto de 64 + safe area, fondo de vidrio con `blur(20px)`, pestaña activa en oro con trazo 2.
- **Sidebar (≥1024, 256 px):**
  - Grupos: **Hoy** (Inicio, Acta, Praxis, Ataraxia) · **Virtudes** (Oikonomia, Hegemonikon, Paideia, Cosmopolitismo, Eurythmia) · **Vida** (Guardarropa, Viajes, Harma, Plantas) · **Tú** (Logros, Recompensas, Perfil).
  - Las subpáginas solo aparecen dentro del módulo activo, con un máximo de 4 + «Más…».
  - Pie: nivel, barra de XP, EC, tema y colapsar.
- **Topbar:**
  - Desktop: breadcrumb de 3 niveles máximo · búsqueda que abre ⌘K · badge de XP del día · badge de EC · avatar.
  - Móvil: ← (hub padre) · título en serif 17 con la función debajo en 11 px · EC · buscar.
- **⌘K:** grupos Acciones (Registrar gasto, Marcar actividad, Subir estado, Nueva tarea, Nueva prenda) · Páginas · Recientes · Sistema. Busca en griego y en español.
- **Fuente única:** `modules/nav.py` con `NAV` y `ACTIONS`, inyectado mediante un context processor. Reemplaza el dict `_pm` de `layout_sub.html`.
- **Renombres de etiqueta** (las rutas no cambian):
  - `/finanzas/salud/` → «Patrimonio»
  - `/finanzas/estados/viajes/` → «Gastos de viaje»
  - `/finanzas/estados/` → «Movimientos»

## Screens (ver `referencia/Pantallas V2 — A.html` y `— B.html`)
Todas las pantallas comparten:
- **Móvil 390:** status bar + topbar 52 + contenido con padding 16 y gap 12 + bottom nav.
- **Desktop 1440:** sidebar 256 + topbar 56 + cuerpo con padding 28/40 y gap 24.

1. **Login** (`auth/login.html`).
   - Móvil: sello de 64 al centro, «EUDAIMONIA» con tracking .22em, cita de Marco Aurelio y el formulario anclado abajo (input de 44 con ícono de candado y botón lg a ancho completo).
   - Desktop: dos columnas (1.3fr / 1fr). A la izquierda, hero de 72 px («Cada día, / un acto de carácter.») con 3 cifras abajo. A la derecha, formulario de 360 px con estado de error y una cita de Séneca.
2. **Dashboard** (`dashboard/index.html`). Tres zonas: **Hoy** (tarjeta featured de XP del día con barra y 4 tiers + nivel), **Pendiente** (radar) e **Inspiración** (palabra y cita).
   - Desktop: grid `1fr 360px`. A la izquierda, saludo, tarjeta héroe en dos columnas (XP del día · nivel/racha/EC/perks), grid de virtudes de 4 columnas y heatmap de 16 semanas. A la derecha, «Siguiente paso» (sugerencia con la regla de balance), Radar de 7 días, Palabra del día y cita.
   - Móvil: XP, siguiente paso, pendiente y un grid de virtudes de 4×2.
3. **Acta Diurna** (`actividades/index.html`).
   - Cada actividad es un `ui.activity()` (fila de 52, check circular, tinte de su categoría al marcarla).
   - Bloques por virtud: en desktop, una tarjeta por categoría en 2 columnas; en móvil, lista con cabecera de categoría.
   - Panel derecho en desktop: resumen del día, combos con progreso y regla de balance.
   - Toast de XP con «Deshacer» y un temporizador de 5 s.
   - Atajos: `1–9` y `⌘Z`.
4. **Logros** (`gamification/logros.html`).
   - Sello del nivel y nombre en mayúsculas con tracking .1em.
   - Desktop: línea de 10 niveles con los umbrales del README, stats (racha, días diamante, badges), tabs (Todos, Ganados, En curso, Bloqueados), grid de 4 `eu-ach` y perks activos (máx. 2).
5. **Recompensas** (`recompensas/index.html`).
   - Hero de saldo EC con radial electrum y equivalencia en MXN (`EC_RATE`).
   - Chips: Disponibles, Por nivel, En espera.
   - Cada tarjeta muestra costo en EC y MXN, nivel requerido, cooldown y, si no alcanza, una barra de progreso hacia el costo.
   - Desktop: panel de saldo más canjes recientes.
6. **Oikonomia Hub** (`finanzas/hub.html`).
   - Hero «wallet» de patrimonio neto con el toggle de ocultar (se mantienen `.nw-real`/`.nw-mask`).
   - Desktop: 3 stats (ingresos, gastos, ahorro), tabla de deudas con un badge de vencimiento, presupuesto por categoría (≥90% en warning, >100% en danger) y 6 accesos a submódulos.
7. **Finance Dashboard** (`finanzas/estados.html`, pestaña Resumen).
   - Tabs: Resumen, Movimientos, Cuentas, Presupuestos, Reglas, Reportes, Gastos de viaje.
   - 4 stats: gastado (tu parte), ingresos, MSI activos y sin categoría (con CTA).
   - Flujo de 6 meses en barras de ingreso y gasto; categorías frente a presupuesto; tarjetas de cuentas.
8. **Transaction Analysis** (`estados.html`, pestaña Movimientos).
   - Desktop: tabla `eu-table` con drawer derecho de 400 px para el movimiento seleccionado. El drawer tiene grid de categorías, select de subcategoría, bloque «Tu parte» (Todo / 50% / Monto), nota, «Crear regla» y guardar con `⌘↵`.
   - Móvil: filas agrupadas por día y un bottom sheet de categorización con «Aplicar siempre», que da +1 XP.
9. **Guardarropa** (`guardarropa/index.html`).
   - Segmented: Prendas, Outfits, Wishlist. Chips por tipo con conteo.
   - Grid de fotos en 3:4: 5 columnas en desktop, 2 en móvil. Las prendas con 0 usos en 90 días van en warning.
   - Panel lateral: outfit de hoy (+1 XP), rotación de 90 días y wishlist. En móvil, el FAB «+» abre «Nueva prenda».
10. **Perfil** (`perfil/index.html`). Hub «Tú».
    - Móvil: avatar, accesos a Logros y Recompensas, filas (datos, medidas, documentos, vault), tema y cerrar sesión.
    - Desktop: columna de 280 (tarjeta y subnav) más contenido (datos en 3 columnas, medidas en 6 tarjetas inset con su delta, documentos, vault con contraseña maestra).

## Interactions & Behavior
- **Marcar actividad:**
  1. Actualización optimista: `aria-pressed=true` y el check con settle de 220 ms.
  2. «+N XP» sube 600 ms.
  3. `.eu-xpbar.is-gaining` anima 1.2 s.
  4. El contador sube con tabular-nums.
  5. Toast con undo de 5 s.

  Si el `fetch` falla: revertir y mostrar un toast danger.
- **Logro:** el sello escala de .86 a 1 (settle, 700 ms) con un halo de 1 px que se expande una sola vez. Sin confeti.
- **Level-up:** scrim de 360 ms → eyebrow → nombre con tracking que pasa de .32em a .12em en 1.2 s → cita. Se cierra al tocar. Es el único uso de `eu-celebrate.js`.
- **Modales:** en ≥768 son modal de 480 px; en móvil son bottom sheet (mismo markup). Llevan `role=dialog`, foco atrapado, cierre con Esc y el foco vuelve al disparador.
- **Loading:** `.eu-skel` con `aria-busy`. Los botones usan `aria-busy="true"`.
- **Vacíos:** `ui.empty()` con CTA y atajo.
- **Targets táctiles:** mínimo 44 px (`pointer:coarse`). Los inputs usan 16 px en móvil para evitar el zoom de iOS.
- **`prefers-reduced-motion`:** todas las animaciones se reducen a 1 ms.

## Assets
- No hay imágenes nuevas. Las fotos de Guardarropa son las existentes (`uploads_base_dir()/wardrobe/`).
- Fuentes: Google Fonts (Cormorant Garamond 400/500/600 + italic, DM Sans 400/500/600, JetBrains Mono 400/500).
- Iconos: Lucide.

## Files
- `css/tokens.css`: tokens + alias legacy. **Producción.**
- `css/components.css`: componentes `eu-*`. **Producción.**
- `jinja/_ui/macros.html`: macros button, iconbtn, card, stat, badge, chip, field, progress, xpbar, activity, row, modal, empty. **Producción.**
- `PROMPTS.md`: un prompt por fase para Claude Code.
- `referencia/Design System V2.html`: fundamentos + los 23 componentes con estados.
- `referencia/DS V2 — Navegación, Auditoría y Migración.html`.
- `referencia/Pantallas V2 — A.html` y `— B.html`: las 10 pantallas.
