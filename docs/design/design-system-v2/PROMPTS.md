# Prompts para Claude Code — un prompt por sesión

Pega cada bloque en Claude Code, **en orden**. Al terminar cada fase, pruébala y despliégala antes de empezar la siguiente.

---

## Fase 1 — Alto impacto, bajo esfuerzo

```
Lee CLAUDE.md, PROJECT_CONTEXT.md y design_handoff_design_system_v2/README.md.
Abre design_handoff_design_system_v2/referencia/Design System V2.html como referencia visual.

Objetivo: aplicar los tokens V2 SIN romper ningún template.

1. En gio_v3/static/css/app.css, reemplaza los bloques `:root, html.dark {…}` y `html.light {…}`
   por el contenido completo de design_handoff_design_system_v2/css/tokens.css.
   Conserva todo lo demás de app.css. Los alias legacy (--bg, --card, --gold, --dim…) deben seguir existiendo.
2. Añade JetBrains Mono 400/500 al <link> de Google Fonts en templates/eu/layout_sub.html.
3. Busca en templates/ los font-size entre .4rem y .6rem, y los de 9px, 9.5px y 10px:
   cámbialos por var(--fs-12) (o var(--fs-11) si es un eyebrow en mayúsculas).
4. Reemplaza los hex hardcodeados #6A6050 y #8A7A60 por var(--fg-3), y rgba(201,168,76,0.15)
   usado como borde por var(--border-default).
5. Elimina las animaciones infinitas decorativas en reposo (iconFloat, iconWiggle, iconPulseScale
   con `infinite`) en dashboard y actividades.
6. Bottom nav de layout_sub.html: 5 pestañas (Inicio /, Acta /actividades/, Praxis /gtd/,
   Módulos → abre un bottom sheet con grid de todos los módulos, Tú /perfil/).
   Usa las clases .eu-bnav de components.css (cópialas al <style> de layout_sub por ahora).
7. En cada encabezado de página (.pg-hd), añade la función en español junto al nombre griego:
   «Oikonomia · Finanzas».

Aceptación: pytest pasa igual que antes; ninguna ruta cambia; el tema claro se ve bien;
ningún texto de la app mide menos de 11px.
```

## Fase 2 — Adopción del sistema

```
Lee design_handoff_design_system_v2/README.md.

1. Crea gio_v3/static/css/components.css con el contenido de design_handoff_design_system_v2/css/components.css
   (quita del principio el reset de body/a/*, porque ya existe en app.css) e impórtalo dentro de
   @layer components en static/css/tailwind-src.css.
2. Añade aliases temporales en @layer components:
   .btn-a → eu-btn eu-btn--primary · .btn-g → eu-btn--ghost · .btn-r → eu-btn--danger ·
   .tile → eu-card · .fi → eu-input · .ch2 → eu-chip. Luego mueve las clases compartidas del <style>
   de layout_sub.html a components.css.
3. Copia design_handoff_design_system_v2/jinja/_ui/macros.html a gio_v3/templates/_ui/macros.html.
4. Crea gio_v3/modules/nav.py con NAV (grupos Hoy / Virtudes / Vida / Tú, cada ítem con id, label,
   greek opcional, fn, cat, icon Lucide, url y children) y ACTIONS para ⌘K. Inyéctalos con un
   context_processor en app.py. Reescribe el sidebar, el sheet de Módulos, el breadcrumb y ⌘K de
   layout_sub.html para que lean NAV. Elimina el dict _pm.
   Etiquetas: /finanzas/salud/ = «Patrimonio», /finanzas/estados/viajes/ = «Gastos de viaje»,
   /finanzas/estados/ = «Movimientos». Guardarropa, Viajes, Harma y Plantas pasan al grupo «Vida».
5. Rediseña el sidebar, la topbar y ⌘K según «DS V2 — Navegación, Auditoría y Migración.html».
6. npm run build:css y commitea tailwind-built.css.

Aceptación: sidebar, bottom nav, ⌘K y breadcrumb salen de una sola fuente (NAV);
todos los tests pasan; las rutas no cambian.
```

## Fase 3 — Unificación de módulos (una sesión por pantalla)

```
Lee design_handoff_design_system_v2/README.md, sección «Screens», punto <N>.
Abre design_handoff_design_system_v2/referencia/Pantallas V2 — A.html (o — B.html),
frames «<NN> … móvil» y «<NN> … desktop».

Recrea templates/<modulo>/index.html para que se vea exactamente así, en 390px y en 1440px:
- Usa {% import '_ui/macros.html' as ui %} y las clases eu-* / t-*.
- Cero style="" con colores o tamaños, cero hex, espaciado solo con var(--sp-*).
- Categorías con data-cat="{{ categoria|lower }}", nunca :nth-child.
- Divide el template en partials por sección (templates/<modulo>/_*.html).
- Mueve el JS inline a static/js/<modulo>.js.
- Conserva TODA la funcionalidad y los endpoints /api existentes.
- Revisa el resultado en ambos temas (noche/día).

Orden sugerido: 02 Dashboard → 03 Acta Diurna → 04 Logros → 05 Recompensas → 10 Perfil →
01 Login → 09 Guardarropa → 06 Oikonomia Hub → resto de módulos.
```

## Fase 4 — Rediseño de Finanzas (SPA de Estados de cuenta)

```
Lee design_handoff_design_system_v2/README.md, puntos 7 y 8 de «Screens».
Contexto: static/finanzas/assets/estados.js es un bundle React minificado sin fuente.

1. Crea gio_v3/frontend/finanzas/ con Vite + React (sin TypeScript obligatorio).
   El build genera static/finanzas/assets/estados.js (el mismo nombre de archivo) para que
   estados.html siga funcionando.
2. Reconstruye las vistas consumiendo los MISMOS endpoints /finanzas/estados/api/* que usa el
   bundle actual (inspecciona estados.js y routes.py): Resumen, Movimientos (tabla + drawer de 400px
   en desktop, bottom sheet en móvil), Cuentas, Presupuestos, Reglas, Reportes y modal de categoría.
3. Estilos: solo var(--*) de tokens.css y las clases eu-* de components.css. Nada de slate.
4. Borra de estados.html todos los overrides [style*="…"] !important.
5. Añade un README en frontend/finanzas con cómo compilar.

Aceptación: la funcionalidad es la misma que antes (importar PDF, categorizar, tu parte, MSI,
reglas, reportes); Finanzas no se distingue visualmente del resto de la app;
los tests de finanzas pasan.
```

## Fase 5 — Pulido

```
Lee la sección «Interactions & Behavior» del README.
1. Implementa las coreografías de XP ganada, logro y level-up con los tokens de motion
   (ver la sección Motion en Design System V2.html). eu-celebrate.js solo se usa para level-up.
2. Pon .eu-skel y ui.empty() en toda carga y lista vacía.
3. Accesibilidad: navegación por teclado completa, foco visible, roles de modal/tabs/progressbar,
   aria-live en el toast. Revisa con axe en ambos temas y con VoiceOver en iPhone.
4. PWA: manifest.json, íconos, theme-color #09070F, safe areas.
```
