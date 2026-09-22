# PROJECT_CONTEXT — Eudaimonia OS v3

> Documento de contexto para que otra IA entienda el proyecto sin leer el código completo.
> Generado a partir del análisis del repo `supremogio/eudaimonia` (rama `main`, 2026-09-22).
> Complementa a `CLAUDE.md` (reglas operativas: DB, uploads, deploy) — leer ambos.

---

## 1. Resumen Ejecutivo

### ¿Qué hace la aplicación?
**Eudaimonia OS** es un "sistema operativo personal" web: una sola app que concentra la vida de una persona
(hábitos, finanzas, salud, aprendizaje, productividad, ropa, vehículo, plantas, viajes) y la **gamifica** con
una estética y vocabulario de **filosofía estoica/griega**.

- Cada acción registrada (leer, ir al gym, registrar gastos, planchar ropa…) otorga **XP** y **Euda-Credits (EC)**.
- XP sube de **nivel** (10 niveles: PROKOPTON → EUDAIMÓN, meta 5 500 XP en 1 año).
- EC se canjean en una **tienda de recompensas** reales (1 EC = $10 MXN, `ec_constants.py`).
- Hay rachas (streaks), clasificación diaria (Carbón/Hierro/Oro/Diamante), combos, badges/logros y penalizaciones.
- Cada área de vida es un **módulo** con nombre griego ("virtud"): Oikonomia (finanzas), Hegemonikon (salud),
  Paideia (conocimiento), Cosmopolitismo (idiomas), Ataraxia (orden/rutina), Eurythmia (baile), Logoi
  (programación), Harma (vehículo), etc.

### ¿Quién es el usuario objetivo?
**Un único usuario** (el dueño, en México — montos en MXN, bancos BBVA/HSBC/Invex). No es multi-tenant:
login con una sola contraseña global guardada como hash en `app_settings`. Uso principal **móvil (iPhone/Safari)**
y también desktop. Todo el texto de UI está en **español**.

### Flujo principal
1. Login (`/login`, contraseña única) → sesión de 8 h.
2. **Dashboard `/`**: hero de XP/nivel, heatmap de racha, tarjetas de módulos, radar de deadlines, sugerencia
   contextual, palabra/cita del día.
3. **Acta Diurna `/actividades/`**: registro diario de hábitos por categoría → suma XP/EC con animación.
4. Entrar a un módulo (sidebar desktop / bottom-nav móvil / ⌘K) para gestionar su dominio
   (p. ej. subir un estado de cuenta PDF a Finanzas, registrar comida en Nutrición, prenda en Guardarropa).
5. Revisar progreso en **Logros `/logros`** y canjear EC en **Recompensas `/recompensas`**.

---

## 2. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Backend** | Python 3.12 · **Flask 3.1** (app factory `create_app()` en `gio_v3/app.py`), Blueprints por módulo |
| **Servidor** | Gunicorn 23 (1 worker, timeout 120 s) |
| **Frontend (principal)** | **Server-side rendering con Jinja2** + JavaScript vanilla inline en cada template (fetch a endpoints `/api/...` JSON) |
| **Frontend (Finanzas / Estados de cuenta)** | **SPA React** precompilada (`static/finanzas/assets/estados.js`, ~240 KB minificado). **No existe el código fuente JSX en el repo** — el bundle se edita a mano |
| **CSS** | **Tailwind CSS 3.4** (precompilado a `static/css/tailwind-built.css`, se commitea) + tokens CSS propios en `static/css/app.css` + muchísimo CSS inline/`<style>` por template |
| **Iconos** | **Lucide** vía CDN (`unpkg.com/lucide@1.31.0`, `data-lucide="..."`) |
| **Fuentes** | Google Fonts: Cormorant Garamond, DM Sans, JetBrains Mono |
| **Base de datos** | **SQLite** (`pipeline.db`, en volumen persistente de Railway) + **Turso/libSQL** como respaldo cloud (HTTP `/v2/pipeline`, cliente propio en `database.py`) |
| **Seguridad** | Flask-WTF (CSRF), Flask-Limiter (rate-limit login), cookies HttpOnly/Secure/SameSite, headers de seguridad, HSTS |
| **Procesamiento de documentos** | pdfplumber, PyMuPDF, pytesseract (OCR), Pillow, pandas, openpyxl → parsers de estados de cuenta bancarios |
| **Tests** | pytest + pytest-flask (~460 tests, mayoría de Finanzas) |
| **Deploy** | Railway (Nixpacks, Root Directory = `gio_v3`) |

### Librerías principales (Python — `gio_v3/requirements.txt`)
```
flask==3.1.3          flask-limiter==3.12     flask-wtf==1.3.0
werkzeug==3.1.6       jinja2==3.1.6           click==8.3.1
markupsafe==3.0.3     itsdangerous==2.2.0     gunicorn==23.0.0
python-dotenv==1.0.1  cryptography==50.0.1    tzdata==2026.3
requests==2.33.1      pdfplumber==0.11.10     pymupdf==1.28.2
pytesseract==0.3.13   Pillow==12.3.0          pandas==3.0.5
openpyxl==3.1.5       pytest==9.1.1           pytest-flask==1.3.0
```
`cryptography` se usa para el **password vault** cifrado (tabla `password_vault`, módulo Perfil).

---

## 3. Estructura de Carpetas

```
eudaimonia/                         ← raíz del repo
├── CLAUDE.md                       ← reglas para IAs (DB, uploads, deploy) — LEER
├── README.md                       ← reglas de gamificación (XP, niveles, EC, combos)
├── railway.json                    ← build/start de Railway
├── Procfile, runtime.txt, requirements.txt, run.py   ← fallback raíz (no usados por Railway actual)
├── docs/
│   ├── PROJECT_CONTEXT.md          ← este documento
│   └── design/                     ← referencia visual (NO se sirve ni se importa)
│       ├── prototipo-app/          ← PROTOTIPO React original: eu-app.jsx, eu-components.jsx,
│       │                             eu-screens.jsx, eu-data.js, screenshots/ — referencia histórica
│       └── ux-patches/             ← specs visuales de rediseños (HTML + JSX de referencia)
│           ├── README.md           ← roadmap UX de 5 sprints (todos implementados a 2026-08-15)
│           ├── EUDAIMONIA UX Patches.html, Oikonomia Redesño.html, Presupuesto Radiografia.html
│           └── eu-patches-{tokens,acta,nav,celebrate}.jsx, design-canvas.jsx
└── gio_v3/                         ← TODO el código de la app vive aquí (Root Directory en Railway)
    ├── .env.example                ← plantilla de variables de entorno
    ├── app.py                      ← create_app(): registra 28 blueprints, login obligatorio, /health
    ├── database.py                 ← (~5 200 líneas) esquema (86 CREATE TABLE), migraciones,
    │                                 conexión SQLite + réplica Turso, helpers de consulta
    ├── data.py                     ← catálogo de ACTIVITIES (XP/EC/tier/categoría)
    ├── ec_constants.py             ← valor del EC, hues por categoría
    ├── extensions.py               ← limiter + csrf
    ├── utils.py                    ← uploads_base_dir() y helpers
    ├── run.py                      ← arranque local (localhost:5000)
    ├── nixpacks.toml               ← providers python+node para Railway
    ├── package.json, tailwind.config.js   ← build de Tailwind (solo local)
    ├── modules/                    ← un paquete por módulo (Blueprint + lógica)
    │   ├── auth/                   ← login/logout/setup contraseña
    │   ├── dashboard/              ← "/" hub principal + APIs de XP/estado
    │   ├── actividades/            ← Acta Diurna (registro de hábitos) + activity_defs.py
    │   ├── gamification/           ← engine.py (XP, niveles, streaks, clasificación), badges, achievements, /logros
    │   ├── recompensas/            ← tienda de EC
    │   ├── gtd/                    ← "Praxis": tareas GTD con puntos
    │   ├── ataraxia/               ← rutinas/checklists por bloques (sábado/domingo)
    │   ├── finanzas/               ← "Oikonomia"
    │   │   ├── routes.py           ← hub + deudas
    │   │   ├── budget.py           ← presupuesto mensual
    │   │   ├── consumo.py          ← seguimiento de consumo de productos
    │   │   ├── inversiones.py, prioridades.py, salud.py (salud financiera/patrimonio)
    │   │   └── estados/            ← estados de cuenta: routes.py (~2 800 líneas, 46 rutas),
    │   │                             config.py (taxonomía/keywords),
    │   │                             parsers/ (bbva, bbva_csv, bbva_debit, bbva_debit_xlsx,
    │   │                             bbva_legacy_csv, bbva_libreton, hsbc, invex)
    │   ├── bienestar/              ← "Hegemonikon": hub, salud.py (médico), futbol.py
    │   ├── nutricion/, recetas/    ← plan de comidas, Bristol, recetas
    │   ├── guardarropa/            ← prendas, outfits, tallas + wishlist.py
    │   ├── viajes/                 ← viajes, días, maleta, outfits por día
    │   ├── idiomas/                ← "Cosmopolitismo": SRS de vocabulario, journal, tests
    │   ├── paideia/                ← libros y películas
    │   ├── eurythmia/              ← baile: repertorio, sesiones, álbumes
    │   ├── harma/                  ← vehículo: servicios, pólizas, siniestros, documentos
    │   ├── plantas/                ← riego/trasplante + care_data.py
    │   └── perfil/                 ← datos personales, medidas corporales, documentos, vault
    ├── templates/                  ← Jinja2 (espejo de modules/)
    │   ├── eu/layout_sub.html      ← LAYOUT BASE ÚNICO (sidebar, topbar, bottom-nav, ⌘K, toast, loadbar)
    │   ├── gtd_base.html           ← sub-layout de GTD (extiende layout_sub)
    │   ├── _partials/empty.html    ← estado vacío reutilizable
    │   ├── dashboard/ (index + _deadline_card, _greek_column)
    │   ├── finanzas/ (hub, budget, consumo, consumo_detalle, estados, inversiones, prioridades, salud, viajes)
    │   └── <modulo>/index.html     ← una página (grande) por módulo
    ├── static/
    │   ├── css/app.css             ← TOKENS DE DISEÑO (fuente única) + utilidades grid + animaciones
    │   ├── css/tailwind-src.css → tailwind-built.css
    │   ├── js/eu-celebrate.js      ← partículas/celebración (vanilla)
    │   ├── finanzas/assets/estados.js   ← SPA React compilada (la monta templates/finanzas/estados.html)
    │   └── img/logo.png
    ├── migrations/                 ← migraciones versionadas (registran en migration_log)
    ├── scripts/                    ← pre_deploy_check.py, fixes puntuales
    ├── tests/                      ← 56 archivos pytest (mayoría finanzas) — único directorio de tests
    └── uploads/                    ← fotos/documentos locales (gitignored; en prod viven en el volumen)
```

---

## 4. Componentes de UI

### Páginas (templates que renderizan una pantalla)
| Pantalla | Template | Notas |
|---|---|---|
| Login | `auth/login.html` | contraseña única / setup inicial |
| Dashboard | `dashboard/index.html` | hero XP, nivel, heatmap 21 días, grid de módulos, deadlines, sugerencia, palabra/cita, reflexión |
| Acta Diurna | `actividades/index.html` | checklist de hábitos por categoría, undo toast, animación de ícono |
| Ataraxia | `ataraxia/index.html` | rutinas por bloques (fin de semana dual) |
| Praxis (GTD) | `gtd/praxis.html`, `gtd/points.html` | captura rápida, secciones plegables, puntos |
| Logros | `gamification/logros.html` | badges, clasificación, XP |
| Recompensas | `recompensas/index.html` | tienda de EC, cooldowns |
| Oikonomia hub | `finanzas/hub.html` | patrimonio (ocultable), deudas, links a submódulos |
| Estados de cuenta | `finanzas/estados.html` | monta la **SPA React** (tabs: Resumen, Movimientos, Cuentas, Presupuestos, Reglas, Reportes; modal por categoría) |
| Presupuesto | `finanzas/budget.html` | por mes (`/finanzas/budget/<mes>`) |
| Consumo | `finanzas/consumo.html`, `consumo_detalle.html` | |
| Inversiones / Prioridades / Salud financiera | `finanzas/inversiones.html`, `prioridades.html`, `salud.html` | |
| Viajes (gastos) | `finanzas/viajes.html` | `/finanzas/estados/viajes/` |
| Hegemonikon hub | `bienestar/index.html` | links a salud, fútbol, nutrición, recetas, guardarropa, viajes |
| Salud médica / Fútbol | `bienestar/salud.html`, `bienestar/futbol.html` | |
| Nutrición / Recetas | `nutricion/index.html`, `recetas/index.html` | |
| Guardarropa / Wishlist | `guardarropa/index.html` (~2 300 líneas), `guardarropa/wishlist.html` | fotos, outfits |
| Viajes | `viajes/index.html` | itinerario, maleta, outfits por día |
| Cosmopolitismo | `idiomas/index.html` | |
| Paideia | `paideia/index.html` | libros/películas |
| Eurythmia | `eurythmia/index.html` | |
| Harma | `harma/index.html` | vehículo |
| Plantas | `plantas/index.html` | |
| Perfil | `perfil/index.html` | datos, medidas, documentos, vault |

### Componentes reutilizables
No hay sistema de componentes formal (ni macros Jinja significativas). La reutilización ocurre vía:
- **`eu/layout_sub.html`** (heredado por TODAS las pantallas): sidebar desktop (≥1024 px), topbar con
  botón ← + breadcrumb (móvil: eyebrow + título), toggle claro/oscuro, logout, **command palette ⌘K**
  (lee sus items del sidebar), **bottom-nav móvil** (4 tabs: Ἀρχή/Inicio, Praxis, Acta, Αὐτός/Perfil),
  **toast** global `toast(msg, type)`, **loadbar** global (wrapper de `window.fetch` que además inyecta el
  token CSRF), máscara de patrimonio (`.nw-real`/`.nw-mask`), activación por teclado `.eu-activate`.
- **Clases CSS compartidas** (definidas en el `<style>` de `layout_sub.html`):
  `.tile`/`.tile-lbl` (tarjeta), `.btn-a` (primario dorado), `.btn-g` (ghost), `.btn-r` (destructivo),
  `.btn-gr` (éxito), `.fi`/`.fl` (input/label), `.modal-bg`/`.modal`/`.modal-title`/`.modal-actions`
  (bottom-sheet en móvil), `.pg-hd`/`.pg-t`/`.pg-s` (encabezado de página), `.ch2` (chips/filtros),
  `.pri-*`/`.pt-*` (pills de prioridad), `.t-row` (fila de tarea), `.empty-s`/`.empty-rich` (vacíos),
  `.sk` (skeleton shimmer, en app.css), utilidades grid `.g2 .g3 .g4 .g-auto`.
- **`_partials/empty.html`**: estado vacío con ícono, título, descripción y CTA (+ atajo de teclado).
- **`static/js/eu-celebrate.js`**: `euCelebrate(el)` burst de partículas y refuerzos (level-up, logros).
- **SPA Finanzas**: componentes React internos (tabla de movimientos, modal de categoría, gráficas, reglas)
  sólo accesibles editando el bundle minificado.

### Sistema de diseño actual
- **Tokens** en `static/css/app.css` (`:root, html.dark` y `html.light`) — fuente única de verdad.
- Tailwind configurado para mapear `surface/card/border/dim/mid/gio-*` a esas variables CSS.
- Dos temas: **oscuro (default)** y **claro "pergamino"**, persistidos en `localStorage['eu-theme']`
  con script anti-FOUC.
- Escala tipográfica `--fs-xs 11 / sm 13 / base 15 / lg 18 / xl 24 / 2xl 36 px`.
- Hue por categoría (`CATEGORY_HUES` en `ec_constants.py`) usado con `oklch()` para colorear módulos.
- Foco visible global dorado, `:active scale(.97)` global, respeto a `prefers-reduced-motion`.

---

## 5. Flujo de Navegación

### Rutas de pantalla
| Ruta | Pantalla | Grupo (sidebar) |
|---|---|---|
| `/login` | Login | público |
| `/` | Dashboard | principal |
| `/actividades/` | Acta Diurna | principal |
| `/ataraxia/` | Ataraxia (rutinas) | principal |
| `/gtd/` (`/gtd/dashboard`), `/gtd/points` | Praxis GTD | principal |
| `/finanzas/` | Oikonomia hub | Módulos |
| `/finanzas/estados/` | Estados de cuenta (SPA React) | ↳ Oikonomia |
| `/finanzas/estados/viajes/` | Gastos de viajes | ↳ Oikonomia |
| `/finanzas/budget/`, `/finanzas/budget/<mes>` | Presupuesto | ↳ Oikonomia |
| `/finanzas/consumo/`, `/finanzas/consumo/producto/<id>` | Consumo | ↳ Oikonomia |
| `/finanzas/inversiones/`, `/finanzas/prioridades/`, `/finanzas/salud/` | Submódulos | ↳ Oikonomia |
| `/bienestar/` | Hegemonikon hub | Módulos |
| `/bienestar/salud/`, `/bienestar/futbol/` | Salud médica, Fútbol | ↳ Hegemonikon |
| `/nutricion/`, `/recetas/`, `/guardarropa/`, `/guardarropa/wishlist/`, `/viajes/` | | ↳ Hegemonikon |
| `/paideia/` | Paideia | Módulos |
| `/idiomas/` | Cosmopolitismo | Módulos |
| `/eurythmia/` | Eurythmia | Módulos |
| `/harma/` | Harma | Módulos |
| `/plantas/` | Plantas | Módulos |
| `/perfil/` | Perfil | Sistema |
| `/logros` | Logros | Sistema |
| `/recompensas/` | Recompensas | Sistema |
| `/health`, `/api/health/v31` | health checks públicos | — |

Legacy → redirect: `/classic`, `/v2`, `/tw`, `/logoi` → `/`; `/gtd/inbox|next|someday|projects` → `/gtd/`.
Rutas `*/admin/*` (auditorías y fixes de datos de Finanzas) y ~260 endpoints `*/api/*` JSON.
En total hay **~330 rutas** en 28 blueprints.

### Cómo navega el usuario
- **Móvil (<1024 px)**: bottom-nav fijo (Inicio · Praxis · Acta · Perfil) + botón ← en el topbar
  (sube al hub del módulo padre, o a `/` si ya está en la raíz) + ⌘K (botón lupa).
- **Desktop (≥1024 px)**: sidebar fijo de 256 px con 3 grupos (principal, Módulos, Sistema) + breadcrumb
  `Módulos › <Padre> › <Página>` + ⌘K / Ctrl+K.
- Hubs intermedios: Dashboard (grid de módulos) → Oikonomia hub / Hegemonikon hub → subpáginas.
- La jerarquía padre↔hijo está en el diccionario `_pm` de `layout_sub.html` (variable `pg` que cada
  template define con `{% set pg='...' %}`).
- Interacción dentro de cada página: formularios en **modales** (bottom-sheet en móvil) que hacen `fetch`
  a `/api/...` y actualizan el DOM sin recargar; feedback con `toast()` y la loadbar.

---

## 6. Paleta Visual Actual

### Colores (tema oscuro — default)
| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#09070F` | fondo (negro violáceo) |
| `--surf` | `#0F0C1A` | superficies, nav |
| `--card` / `--card2` | `#1A1627` / `#221D32` | tarjetas / inputs |
| `--b` / `--b2` | `rgba(201,168,76,.15/.30)` | bordes (dorado translúcido) |
| `--gold` / `--gold-l` | `#C9A84C` / `#E8C96D` | **color de marca**, acentos, activo, foco |
| `--text` / `--mid` / `--dim` / `--muted` | `#F2EDE0` / `#A89880` / `#8A7A60` / `#6A6050` | texto (crema cálido) |
| Semánticos | violet `#a78bfa`, cyan `#06b6d4`, emerald `#10b981`, amber `#f59e0b`, coral `#f43f5e`, blue `#3b82f6`, pink `#ec4899` | estados/categorías, cada uno con `-l` (claro) y `-d` (tinte 10%) |

**Tema claro**: `--bg #F5F0E7` (pergamino), `--card #FFFFFF`, `--gold #8B6914`, `--text #1C1610`, semánticos más oscuros.

**Excepción importante:** la SPA de Estados de cuenta usa su **propia paleta Tailwind "slate"**
(`#0f172a`, `#1e293b`, `#334155`, `#94a3b8`, `#f1f5f9`, rojo `#ef4444`, verde `#10b981`, violeta `#7c3aed`)
y `estados.html` intenta "parcharla" con overrides CSS `[style*="background:#0f172a"] { … !important }`.

### Tipografías
- **Cormorant Garamond** (serif, itálica) — títulos de página, marca "EUDAIMONIA", modales, labels del bottom-nav
  (incluye palabras en griego: Ἀρχή, Αὐτός).
- **DM Sans** — texto de UI y cuerpo.
- **JetBrains Mono** — números, kbd, datos.
- Muchos labels en MAYÚSCULAS con `letter-spacing` amplio (.14–.28em).

### Espaciados
- Sin escala formal de spacing: valores ad-hoc en px (padding de tarjeta 20 px, modal 28 px, gaps 8/12/14 px).
- Radios: 6–10 px (controles), 14–16 px (tarjetas/modales), 22 px (bottom-sheet), 100 px (pills).
- Contenido `p-4` (móvil) / `p-6` (desktop); topbar 56 px; sidebar 256 px; bottom-nav max 430 px.
- Breakpoints: 500, 767/768, 1023/1024 px.

### Estilo general
"**Templo estoico nocturno**": fondo casi negro con acentos **dorados**, tipografía serif clásica, vocabulario
griego, bordes finos dorados translúcidos, blur en barras, micro-animaciones de recompensa (partículas,
level-up, pulso dorado). Densidad de información alta, look de "dashboard de juego RPG" sobrio.

---

## 7. Oportunidades de Mejora UX/UI

### Problemas visuales detectados
1. **Finanzas/Estados se ve como otra app**: la SPA React usa paleta slate/azul-gris, sombras y radios propios,
   solo DM Sans; se "forza" con selectores de atributo `!important` frágiles.
2. **CSS inline masivo**: ~1 850 atributos `style="…"`, ~280 colores hex hardcodeados y ~210 `font-size` en `rem`
   literales en templates, fuera de los tokens → deriva visual y el modo claro falla en esos puntos.
3. **Templates gigantes** (guardarropa 2 300 líneas, perfil 1 600, paideia 1 300, actividades 1 250) con su
   propio `<style>` (37 bloques) → cada módulo reinventa tarjetas, botones y chips con pequeñas diferencias.
4. **Tamaños de texto muy pequeños** en muchos lugares (9.5–11 px, labels uppercase), contraste bajo de
   `--dim`/`--muted` sobre `--card` (especialmente `#6A6050` sobre `#1A1627`).
5. Colores con `rgba(201,168,76,…)` hardcodeados (dorado del tema oscuro) que no cambian en tema claro.

### Inconsistencias
- **Dos sistemas de diseño** conviviendo (Jinja+tokens dorados vs. React slate).
- Clases con nombres crípticos y duplicadas por módulo (`.px-*`, `.btn-a/g/r/gr`, `.ch2`, `.fi`) sin documentación
  ni librería de componentes.
- Nomenclatura mezclada griego/español/inglés ("Praxis" = GTD, "Αὐτός" = Perfil, "Hegemonikon" = Bienestar)
  — bonito pero con curva de aprendizaje; los subtítulos lo compensan solo en el sidebar.
- "Salud" aparece en dos lugares (salud financiera `/finanzas/salud/` y salud médica `/bienestar/salud/`);
  "Viajes" también (`/viajes/` logística y `/finanzas/estados/viajes/` gastos).
- Iconografía mixta: Lucide + SVG inline + emojis.
- Bottom-nav móvil (Inicio/Praxis/Acta/Perfil) no coincide con los grupos del sidebar desktop.
- Algunos breakpoints distintos por página (500 / 767 / 768 / 1023).

### Recomendaciones
1. **Unificar Finanzas**: reconstruir la SPA de estados con fuente versionada (Vite + React) consumiendo los mismos
   tokens CSS (`var(--card)`, `var(--gold)`…), o migrarla a Jinja + JS como el resto. Eliminar los overrides `!important`.
2. **Biblioteca de componentes**: mover las clases de `layout_sub.html` a `app.css`/componentes Tailwind
   (`@layer components`) y crear **macros Jinja** (`card`, `button`, `modal`, `stat`, `chip`, `empty`, `form_field`).
3. **Escala de spacing y radios** como tokens (`--sp-1…--sp-8`, `--r-sm/md/lg`) y lint de hex/rem literales.
4. **Accesibilidad**: subir mínimo de texto a 12–13 px, revisar contraste WCAG AA de `--dim`/`--muted`,
   reducir uppercase, targets táctiles ≥44 px en todas las acciones.
5. **Jerarquía de navegación**: alinear bottom-nav y sidebar; mostrar el nombre funcional junto al griego
   ("Oikonomia · Finanzas") en títulos, no solo en el sidebar.
6. **Dividir templates grandes** en partials por sección y extraer el JS inline a archivos `static/js/<modulo>.js`.
7. Estados de carga/vacío/errores consistentes (ya existen `.sk` y `empty.html`; aplicarlos en todos los módulos).

---

## 8. Dependencias

### `gio_v3/package.json` (completo)
```json
{
  "name": "gio_v3",
  "version": "1.0.0",
  "description": "EUDAIMONIA OS — build de CSS (Tailwind compilado, ya no vía CDN)",
  "private": true,
  "scripts": {
    "build:css": "tailwindcss -i ./static/css/tailwind-src.css -o ./static/css/tailwind-built.css --minify"
  },
  "keywords": [],
  "author": "",
  "license": "ISC",
  "devDependencies": {
    "tailwindcss": "^3.4.19"
  }
}
```
Node **solo** se usa para compilar Tailwind en local; el CSS resultante se commitea. No hay bundler JS:
la SPA de Finanzas es un artefacto compilado sin `package.json` ni fuentes en el repo.

### Librerías importantes
- **Runtime Python**: ver lista completa en §2 (`gio_v3/requirements.txt`).
- **CDN en el navegador**: Lucide `1.31.0` (unpkg), Google Fonts. React/ReactDOM vienen **embebidos** en `estados.js`.
- **Servicios externos**: Turso (libSQL por HTTP) como respaldo de la DB; Google Gemini (`GEMINI_API_KEY`)
  para análisis de prendas en Guardarropa.
- **Binario del sistema**: Tesseract (para `pytesseract`, OCR de estados de cuenta escaneados).

### Variables de entorno
`SECRET_KEY`, `DATABASE_PATH` (volumen Railway), `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `GEMINI_API_KEY`, `UPLOADS_DIR` (opcional),
`PORT` (lo inyecta el hosting; activa cookies Secure y HSTS).

---

## 9. Estado Actual del Proyecto

### Qué funciona
- App en producción en Railway, con **SQLite en volumen persistente** como fuente de verdad y **Turso** como
  respaldo async (bootstrap automático si el volumen está vacío).
- Login con contraseña única, CSRF, rate-limit, headers de seguridad.
- Gamificación completa v3.1 (XP, niveles, EC, streaks, clasificación diaria, badges, penalizaciones, tienda).
- **Finanzas es el módulo más maduro**: importación de estados de cuenta PDF/CSV/XLSX de BBVA (varios formatos),
  HSBC e Invex, deduplicación, categorización automática por keywords/reglas, taxonomía con subcategorías,
  `mi_parte` (gastos compartidos), MSI, presupuestos, reportes, viajes, patrimonio, deudas, inversiones.
- Más de 15 módulos de vida con CRUD funcional; uploads de fotos/documentos persistentes en el volumen.
- Tema claro/oscuro, navegación responsive (sidebar/bottom-nav/⌘K), skeletons y estados vacíos.
- Tests: **435 pasan / 18 fallan** (corrida local 2026-09-22, tras la limpieza; ver riesgos).

### Qué falta
- Código fuente de la SPA de Finanzas (solo existe el bundle minificado).
- Sistema de componentes / design system documentado; unificación visual de Finanzas.
- CI automatizado (no hay workflows de GitHub Actions para correr tests).
- Tests de frontend / E2E (ninguno).
- PWA/offline, notificaciones push de deadlines (no existen).

### Riesgos técnicos
1. **Bundle React editado a mano** (`estados.js`): cualquier cambio en Finanzas-Estados es frágil, sin tipos,
   sin build reproducible; nombres minificados (`s.jsx`, `U()`, `o`…).
2. **Archivos monolíticos**: `database.py` (~5 200 líneas), `finanzas/estados/routes.py` (~2 800),
   templates de 1 000–2 300 líneas con CSS+JS inline → difícil de mantener y revisar.
3. **Tests desactualizados**: 18 fallos — 13 en `test_gamification_v31.py` (catálogo de actividades de fin de
   semana cambió con la rutina v4) y 5 en tests de Finanzas (reportes/taxonomía/renta/ingresos: montos esperados divergentes). Sin CI, nadie lo detecta.
4. **Single-user, 1 worker Gunicorn**, rate-limiter en memoria, SQLite: correcto para uso personal, no escala.
5. **Migraciones ad-hoc** dentro de `database.py` y endpoints `/admin/*` que corrigen datos en producción
   (sin framework de migraciones versionado tipo Alembic).
6. **Dependencia de CDNs** (Lucide, Google Fonts) — hay try/catch, pero sin ellos la UI pierde íconos/fuentes.
7. Datos sensibles (finanzas, salud, documentos, vault de contraseñas) en una app con una sola contraseña y
   sin 2FA.
8. Configuración crítica fuera del repo (Root Directory y volumen de Railway) — ver `CLAUDE.md`.

---

## 10. Prompt para un diseñador senior UI/UX

```text
Eres un diseñador senior de producto UI/UX (10+ años, experto en design systems, mobile-first y
accesibilidad WCAG 2.2). Vas a modernizar "Eudaimonia OS", una web app personal de un solo usuario
(uso principal en iPhone, también desktop) que gamifica la vida con filosofía estoica: cada hábito
registrado da XP y "Euda-Credits" canjeables; hay 10 niveles con nombres griegos, rachas,
clasificación diaria (Carbón/Hierro/Oro/Diamante), logros y una tienda de recompensas.

CONTEXTO TÉCNICO (restricciones duras):
- Backend Flask + templates Jinja2 server-rendered + JS vanilla con fetch a endpoints /api JSON.
- Tailwind 3.4 precompilado + tokens CSS en static/css/app.css (fuente única) con tema oscuro
  (default) y claro. Iconos Lucide. Fuentes: Cormorant Garamond (display), DM Sans (UI), JetBrains Mono (datos).
- Un layout base (eu/layout_sub.html): sidebar desktop ≥1024px, topbar con back + breadcrumb,
  bottom-nav móvil de 4 tabs, command palette ⌘K, toast global, modales que en móvil son bottom-sheets.
- El módulo Finanzas > Estados de cuenta es una SPA React embebida con paleta distinta (slate) que
  hoy rompe la coherencia visual.
- Todo el texto está en español. Montos en MXN.

MÓDULOS (todas sus funciones deben seguir existiendo):
Dashboard (XP/nivel, heatmap de racha, grid de módulos, radar de deadlines, sugerencia del momento,
palabra y cita del día) · Acta Diurna (checklist diario de hábitos por categoría con recompensa
animada y undo) · Ataraxia (rutinas por bloques de fin de semana) · Praxis/GTD (captura rápida,
tareas por estado, puntos) · Oikonomia/Finanzas (hub de patrimonio ocultable, deudas, presupuesto
mensual, consumo, inversiones, prioridades, salud financiera, estados de cuenta con importación de
PDF bancarios, movimientos, categorías, reglas, reportes, viajes, "tu parte" en gastos compartidos)
· Hegemonikon/Bienestar (salud médica, fútbol, nutrición, recetas, guardarropa con fotos y outfits,
wishlist, viajes con maleta) · Paideia (libros/películas) · Cosmopolitismo (idiomas: vocabulario SRS,
journal, tests) · Eurythmia (baile) · Harma (vehículo: servicios, pólizas, documentos) · Plantas
(riego/trasplante) · Perfil (datos, medidas, documentos, vault) · Logros · Recompensas.

IDENTIDAD A CONSERVAR:
"Templo estoico nocturno": fondo casi negro violáceo (#09070F), acento dorado (#C9A84C), texto
crema (#F2EDE0), serif clásica para títulos, nombres griegos de los módulos, micro-celebraciones
al ganar XP. Moderniza sin perder ese carácter: más aire, mejor jerarquía, menos ruido.

PROBLEMAS A RESOLVER:
1. Dos sistemas visuales (Jinja dorado vs React slate en Finanzas) → un solo design system.
2. ~1 850 estilos inline, ~280 hex hardcodeados, tamaños de fuente 9–11px y labels uppercase
   excesivos; contraste bajo de textos secundarios (#8A7A60/#6A6050 sobre #1A1627).
3. Cada módulo reinventa tarjetas, botones, chips y modales con pequeñas diferencias.
4. Sin escala de spacing ni radios; breakpoints inconsistentes (500/767/768/1023).
5. Navegación: bottom-nav móvil y sidebar desktop no reflejan la misma jerarquía; los nombres
   griegos no siempre muestran su función en español.
6. Densidad alta de información en pantallas grandes (Guardarropa, Perfil, Paideia, Acta Diurna).

ENTREGABLES:
A. Design tokens v2 (JSON + variables CSS) para tema oscuro y claro: color (neutros, marca,
   semánticos, 9 hues de categoría), tipografía (escala fluida, pesos, line-height), spacing
   (escala 4/8), radios, sombras/elevación, motion (duraciones, easings, reduced-motion).
   Todos los pares texto/fondo con contraste AA mínimo.
B. Biblioteca de componentes con estados (default/hover/focus/active/disabled/loading/error/empty)
   y variantes: Button, IconButton, Card/StatCard, Chip/Filter, Input/Select/Textarea, Modal/
   BottomSheet, Toast, Tabs, Table/List row (con badges tipo "tu parte"), ProgressBar/XP bar,
   Heatmap, Badge/Pill, EmptyState, Skeleton, Navigation (Sidebar, BottomNav, Topbar, ⌘K).
   Especifica cada uno de forma implementable como macro Jinja + clases Tailwind @layer components.
C. Rediseño de pantallas clave en móvil (390px) y desktop (1440px): Dashboard, Acta Diurna,
   Oikonomia hub, Estados de cuenta (Resumen, Movimientos, modal de categoría), Guardarropa,
   Logros/Recompensas, Login.
D. Arquitectura de navegación propuesta (mapa de sitio + qué va en bottom-nav vs sidebar vs ⌘K).
E. Guía de migración incremental por sprints, priorizada por impacto/esfuerzo, sin romper
   funcionalidad ni rutas existentes, y compatible con el stack actual (sin reescribir a otro
   framework salvo la SPA de Finanzas, que puede reconstruirse con Vite+React usando los mismos tokens).

REGLAS:
- No elimines ninguna funcionalidad, dato ni ruta; si propones fusionar pantallas, muestra dónde
  queda cada función.
- Mobile-first, targets táctiles ≥44px, safe-areas de iOS, soporte teclado y lectores de pantalla.
- La gamificación debe sentirse gratificante pero sobria (nada infantil).
- Justifica cada decisión con un principio de UX (jerarquía, reconocimiento vs recuerdo, ley de
  Fitts/Hick, consistencia, feedback) y entrega specs medibles (px, tokens, contrastes).
```
