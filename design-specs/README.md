# EUDAIMONIA · UX Patches — Spec para Claude Code

Esta carpeta contiene la spec visual de **19 mejoras de UI/UX** organizadas en **5 sprints**, para aplicar al repo `gio_v3_ACTUALIZADO`.

> **Estado (2026-08-15):** la mayoría de estos sprints ya está implementada — tokens (Sprint 1), Acta Diurna (Sprint 2), dashboard/bottom-nav/sidebar (Sprint 3, salvo ⌘K), streak heatmap/clasificación (Sprint 4) y estados vacíos/skeletons (Sprint 5). `gio_v3/templates/eu/layout.html`, citado varias veces abajo como el archivo a editar, **nunca llegó a servirse por ningún route y se borró** — el layout base real desde entonces es `eu/layout_sub.html`, con los tokens de diseño en `static/css/app.css`. Las referencias a `eu/layout.html` que quedan abajo son históricas; donde aplica, edita `eu/layout_sub.html` o `app.css` en su lugar. Lo único de este roadmap que sigue pendiente de verdad es el command palette ⌘K (punto 3 del Sprint 3).

---

## 📁 Archivos

| Archivo | Contiene |
|---|---|
| `EUDAIMONIA UX Patches.html` | Abrir en navegador para ver visualmente todos los patches (ANTES vs DESPUÉS). Pan/zoom + focus mode por artboard. |
| `eu-patches-tokens.jsx` | Spec Sprint 1: escala tipográfica, contraste WCAG, hue por categoría, dieta de uppercase |
| `eu-patches-acta.jsx` | Spec Sprint 2: Acta Diurna refactor (hero, bloque categoría, botón actividad, undo toast) |
| `eu-patches-nav.jsx` | Spec Sprint 3: Dashboard `/`, bottom nav mobile, command palette ⌘K, sidebar |
| `eu-patches-celebrate.jsx` | Spec Sprints 4 + 5: level-up modal, streak heatmap, clasificación, empty states, skeletons, zona de peligro |
| `design-canvas.jsx` | Componente host (solo para que el `.html` renderice) |

⚠️ Los archivos `.jsx` **NO se importan al backend Flask**. Son únicamente la **referencia visual** que tú (Claude Code) lees para entender qué cambiar en los templates Jinja + CSS reales.

---

## 🚀 Cómo usar esta spec — flujo recomendado

### Paso 1 — abre el HTML para ver el contexto visual
```bash
# en tu navegador
open "EUDAIMONIA UX Patches.html"
```

### Paso 2 — trabaja un sprint a la vez, en rama separada

```bash
git checkout -b ux/sprint-1-tokens
# implementar
git commit -am "Sprint 1: design tokens (typography scale, contrast, hue)"
# revisar visualmente con: python gio_v3/run.py
```

Cuando confirmes que se ve bien, mergea a `main` y pasa al siguiente.

---

## 🗺️ Roadmap de implementación

### ① Sprint 1 — Tokens · Fundamentos
**Archivo de referencia:** `eu-patches-tokens.jsx`

**Cambios:** (✅ ya implementados — ver nota de estado arriba)
1. ~~**Escala tipográfica** — añadir en `gio_v3/templates/eu/layout.html` (dentro de `:root`)~~ — ya vive en `gio_v3/static/css/app.css`:
   ```css
   --fs-xs:   11px;   /* labels, eyebrows */
   --fs-sm:   13px;   /* UI secundaria */
   --fs-base: 15px;   /* texto cuerpo */
   --fs-lg:   18px;   /* títulos sección */
   --fs-xl:   24px;   /* títulos pantalla */
   --fs-2xl:  36px;   /* hero · brand */
   ```
   Buscar y reemplazar TODAS las ocurrencias de `.42rem`, `.44rem`, `.46rem`, `.48rem`, `.5rem`, `.56rem`, `.58rem`, `.6rem`, `.62rem`, `.68rem`, `.7rem` en `templates/**/*.html` y `static/css/app.css` por la variable adecuada.

2. **Contraste WCAG** — en `static/css/app.css`:
   ```css
   --dim: #8A7A60;  /* era #6A6050 — ahora 6:1 ratio */
   ```

3. **Hue por categoría** — añadir en `gio_v3/ec_constants.py`:
   ```python
   CATEGORY_HUES = {
       'LOGOI':          120,
       'HEGEMONIKON':     45,
       'OIKONOMIA':       80,
       'COSMOPOLITISMO': 215,
       'PAIDEIA':        265,
       'ATARAXIA':       155,
       'EURYTHMIA':      330,
       'HARMA':           15,
       'IDENTIDAD':      280,
   }
   ```
   En `templates/actividades/index.html`, eliminar el bloque `:nth-child(8n+x)` y usar `--cat-hue` declarado por categoría:
   ```html
   <div class="cat-block" style="--cat-hue: {{ category_hues[cat] }}">
   ```
   ```css
   .cat-n {
     color: oklch(65% 0.15 var(--cat-hue));
     background: oklch(18% 0.04 var(--cat-hue));
     border-color: oklch(35% 0.09 var(--cat-hue));
   }
   ```

4. **Dieta de uppercase** — quitar `text-transform:uppercase` de descripciones largas y subtítulos. Conservar solo en: eyebrows (etiquetas chicas arriba de títulos) y chips de estado.

**Archivos tocados:**
- `gio_v3/templates/eu/layout_sub.html`
- `gio_v3/static/css/app.css`
- `gio_v3/ec_constants.py`
- `gio_v3/templates/actividades/index.html`

(`gio_v3/templates/eu/layout.html` y `gio_v3/templates/tw/layout.html` ya no existen — se retiraron.)

---

### ② Sprint 2 — Acta Diurna refactor
**Archivo de referencia:** `eu-patches-acta.jsx`

**Cambios en `gio_v3/templates/actividades/index.html`:**

1. **Hero unificado** — eliminar las 5 stat cards + 2 cards (clasificación + nivel). Reemplazar con un solo hero con:
   - XP del día como número grande (font-size 64px, Cormorant)
   - Barra de progreso hacia meta diaria
   - Chip de clasificación (⚔️ Hierro)
   - Stats secundarios (semana, mes, EC, racha) en una fila pequeña abajo

   Ver mock exacto en `ActaHeroAfter()` del archivo jsx.

2. **Bloque de categoría** con header (nombre + conteo + barra de progreso) y botones grid 2 columnas. Ver `CategoryBlockPatch()`.

3. **Botón de actividad** — stack vertical: nombre arriba, "cat · tier" abajo, "+X XP" + "+Y EC" a la derecha. Ver `ActivityButtonPatch()`.

4. **Undo toast** — al hacer `logAct(key)`, mostrar toast con botón "Deshacer (5s)". Requiere endpoint nuevo:
   ```python
   # gio_v3/modules/gamification/routes.py
   @gam_bp.route('/api/activity/undo/<int:log_id>', methods=['POST'])
   def undo_activity(log_id):
       # buscar log_id en la tabla de logs del día, revertir XP/EC, eliminar el registro
       ...
   ```
   El frontend guarda el `log_id` que devuelve `logAct` y lo manda al undo.

5. **Sacar "Word of the Day"** del column right de Acta Diurna → moverlo a `templates/idiomas/index.html` (donde tiene contexto).

6. **Sacar "Reset Gamificación"** de Acta Diurna → mover a `templates/perfil/index.html` (sección "Zona de peligro"). Ver Sprint 5.

---

### ③ Sprint 3 — Navegación + Dashboard
**Archivo de referencia:** `eu-patches-nav.jsx`

1. ✅ **Dashboard `/` nuevo** — implementado en `templates/dashboard/index.html` (Jinja, no React): XP del día, clasificación, nivel, grid de módulos, racha, reflexión del día, word of the day, deadline radar. `modules/dashboard/routes.py` calcula todo server-side.

2. ✅ **Bottom nav mobile** — implementado en `eu/layout_sub.html` (clase `.eu-bottom-nav`, visible solo `<1024px`, `.active` vía `pg`). Mismos 4 tabs (Inicio/Módulos/Acta/Perfil).

3. ⏳ **Command palette ⌘K** — sigue pendiente. Cuando se implemente: JS vanilla en `static/js/command-palette.js`, atajos `Cmd/Ctrl+K` abrir / `↑↓` navegar / `⏎` ejecutar / `Esc` cerrar, fuzzy search sobre las rutas del sidebar (`eu/layout_sub.html`) + acciones rápidas. Cargarlo en `eu/layout_sub.html` para que esté disponible en toda la app.

4. ✅ **Sidebar rediseño** — implementado en `eu/layout_sub.html` (clase `.eu-sidebar`, visible solo `≥1024px`), agrupado HOY/Praxis · MÓDULOS · SISTEMA como se pedía.

---

### ④ Sprint 4 — Celebración + Streak + Clasificación
**Archivo de referencia:** `eu-patches-celebrate.jsx`

1. **Level-up modal** — cuando `/api/log` devuelve `level_up: true`, mostrar modal fullscreen con columna griega + nombre del nuevo nivel. Ver `LevelUpModalPatch()` para el SVG de la columna y el styling.

2. **Streak heatmap** — reemplazar el número solo de racha por un grid 21 días (3 semanas) con intensidad oro = XP del día. Backend: nuevo endpoint `/api/gamification/streak/heatmap?days=21` que devuelve `[{date, xp}, ...]`.

3. **Clasificación con escala visible** — en Acta Diurna y Dashboard, mostrar los 4 tiers (Carbón → Diamante) con el actual destacado y "faltan X XP / Y categorías para el siguiente". Ver `ClassificationPatch()`.

---

### ⑤ Sprint 5 — Estados + Seguridad
**Archivo de referencia:** `eu-patches-celebrate.jsx` (mismo)

1. **Empty states** — reemplazar todos los `<div class="empty-s">...</div>` por versiones con:
   - Icono pequeño dentro de un cuadro con borde
   - Mensaje en Cormorant italic
   - Descripción 13px en `--dim`
   - CTA con la siguiente acción concreta + atajo de teclado

   Ver `EmptyStatePatch()`.

2. ✅ **Skeleton loaders** — implementado: `.sk` + `@keyframes euShimmer` en `static/css/app.css`, definición única (antes vivía duplicada en 3 archivos).

3. **Reset → /perfil** — quitar el botón rojo de Acta Diurna. Añadir en `templates/perfil/index.html` una sección "Zona de peligro" al final con el mismo modal de confirmación. Ver `DangerZonePatch()`.

---

## 🎯 Reglas generales para Claude Code

- **No tocar la lógica de gamificación** (engine, thresholds, EC math). Solo presentación.
- **Mantener compatibilidad con modo claro** — todos los cambios deben funcionar en `html.light` (ver paleta light en `static/css/app.css`).
- **Mobile-first** — probar cada cambio en viewport 390x844 antes de declararlo listo.
- **No introducir librerías nuevas** — ya hay Tailwind (CDN), Lucide, fonts Google. Suficiente.
- **Preservar `data-comment-anchor` si existe** en cualquier elemento que muevas/restructures.
- **Commits atómicos** — un commit por patch, no uno gigante por sprint.

---

## ❓ Si algo no está claro

Las specs `.jsx` son código React legible — pueden leerse como pseudo-código. Cada función `XxxPatch()` muestra exactamente cómo se ve el resultado (colors, sizes, layout). Si Claude Code tiene duda de un valor concreto, abrir el `.jsx` y leer el JSX directamente — todos los pixels, paddings y colores están literalmente ahí.

Para preguntas de alto nivel ("¿cómo conecto esto al backend?"), volver al usuario.
