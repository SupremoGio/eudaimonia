# EUDAIMONIA · UX Patches — Spec para Claude Code

Esta carpeta contiene la spec visual de **19 mejoras de UI/UX** organizadas en **5 sprints**, para aplicar al repo `gio_v3_ACTUALIZADO`.

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

**Cambios:**
1. **Escala tipográfica** — añadir en `gio_v3/templates/eu/layout.html` (dentro de `:root`):
   ```css
   --fs-xs:   11px;   /* labels, eyebrows */
   --fs-sm:   13px;   /* UI secundaria */
   --fs-base: 15px;   /* texto cuerpo */
   --fs-lg:   18px;   /* títulos sección */
   --fs-xl:   24px;   /* títulos pantalla */
   --fs-2xl:  36px;   /* hero · brand */
   ```
   Buscar y reemplazar TODAS las ocurrencias de `.42rem`, `.44rem`, `.46rem`, `.48rem`, `.5rem`, `.56rem`, `.58rem`, `.6rem`, `.62rem`, `.68rem`, `.7rem` en `templates/**/*.html` y `static/css/app.css` por la variable adecuada.

2. **Contraste WCAG** — en `eu/layout.html`:
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
- `gio_v3/templates/eu/layout.html`
- `gio_v3/templates/eu/layout_sub.html`
- `gio_v3/templates/tw/layout.html` ← **adicional: borrar este archivo y migrar `actividades/index.html` a `eu/layout_sub.html`**
- `gio_v3/static/css/app.css`
- `gio_v3/ec_constants.py`
- `gio_v3/templates/actividades/index.html`

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

1. **Dashboard `/` nuevo** — actualmente vacío (`templates/dashboard/` no tiene templates). Crear `templates/dashboard/index.html` con:
   - "Buenos días, Gio" + fecha + día de racha
   - Hero con XP del día (mismo componente que Sprint 2)
   - "Próximas 3 acciones" (de GTD next)
   - Sugerencia del día (próximo hábito que falta de la categoría más completa)
   - Quote del día

   Backend: en `gio_v3/modules/dashboard/routes.py` agregar la query de `next_tasks[:3]` desde GTD y la lógica de "sugerencia del día".

2. **Bottom nav mobile** — en `eu/layout.html`, agregar:
   ```html
   <nav class="md-bottom-nav lg:hidden">
     <a href="/"><span class="lbl">Ἀρχή</span><span class="sub">Inicio</span></a>
     <a href="/actividades"><span class="lbl">Acta</span><span class="sub">Diurna</span></a>
     <a href="/gtd"><span class="lbl">Πρᾶξις</span><span class="sub">Praxis</span></a>
     <a href="/perfil"><span class="lbl">Αὐτός</span><span class="sub">Perfil</span></a>
   </nav>
   ```
   CSS: `position:fixed; bottom:0; width:100%; backdrop-filter:blur(20px);`. Marcar `.active` según `pg`. Ver `BottomNavPatch()` para el styling exacto.

   Mover el contenido principal a `padding-bottom: 70px` en mobile para no taparse.

3. **Command palette ⌘K** — nuevo módulo JS en `static/js/command-palette.js`. Atajos: `Cmd/Ctrl+K` abrir, `↑↓` navegar, `⏎` ejecutar, `Esc` cerrar. Fuzzy search sobre:
   - Rutas (de `eu/layout.html` sidebar)
   - Acciones rápidas (capturar, log meditar, toggle theme, etc.)

   Cargarlo en `eu/layout.html` para que esté disponible en toda la app.

4. **Sidebar rediseño** — reagrupar links por verbo: HOY · MÓDULOS · SISTEMA. Subir tamaño de fuente: items principales `--fs-base` (15px), subitems `--fs-sm` (13px). Iconos 18px.

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

2. **Skeleton loaders** — keyframe `euShimmer` ya existe en `base_eudaimonia.html`. Crear clase `.sk` reutilizable y aplicar mientras `fetch()` está en curso (en lugar del flash blanco).

3. **Reset → /perfil** — quitar el botón rojo de Acta Diurna. Añadir en `templates/perfil/index.html` una sección "Zona de peligro" al final con el mismo modal de confirmación. Ver `DangerZonePatch()`.

---

## 🎯 Reglas generales para Claude Code

- **No tocar la lógica de gamificación** (engine, thresholds, EC math). Solo presentación.
- **Mantener compatibilidad con modo claro** — todos los cambios deben funcionar en `html.light` (ver paleta light en `eu/layout.html`).
- **Mobile-first** — probar cada cambio en viewport 390x844 antes de declararlo listo.
- **No introducir librerías nuevas** — ya hay Tailwind (CDN), Lucide, fonts Google. Suficiente.
- **Preservar `data-comment-anchor` si existe** en cualquier elemento que muevas/restructures.
- **Commits atómicos** — un commit por patch, no uno gigante por sprint.

---

## ❓ Si algo no está claro

Las specs `.jsx` son código React legible — pueden leerse como pseudo-código. Cada función `XxxPatch()` muestra exactamente cómo se ve el resultado (colors, sizes, layout). Si Claude Code tiene duda de un valor concreto, abrir el `.jsx` y leer el JSX directamente — todos los pixels, paddings y colores están literalmente ahí.

Para preguntas de alto nivel ("¿cómo conecto esto al backend?"), volver al usuario.
