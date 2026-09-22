# Eudaimonia OS v3 — Guía para Claude

## Estructura del proyecto

```
gio_v3_ACTUALIZADO/          ← raíz del repo
├── gio_v3/                  ← TODO el código vive aquí
│   ├── app.py               ← Flask factory (create_app)
│   ├── database.py          ← capa de DB (SQLite local + Turso cloud)
│   ├── run.py               ← punto de entrada local
│   ├── pipeline.db          ← SQLite LOCAL (no se commitea, en .gitignore)
│   ├── utils.py
│   ├── data.py
│   ├── ec_constants.py
│   ├── modules/             ← un subdirectorio por módulo
│   │   ├── dashboard/
│   │   ├── finanzas/
│   │   ├── guardarropa/     ← routes.py + wishlist.py
│   │   ├── gtd/
│   │   ├── idiomas/
│   │   ├── nutricion/
│   │   ├── recetas/
│   │   └── ...
│   ├── templates/           ← Jinja2 (espejo de modules/)
│   ├── static/              ← CSS, JS, imágenes
│   ├── uploads/             ← fotos subidas por el usuario (no se commitean)
│   ├── package.json         ← build local de Tailwind (npm run build:css)
│   └── nixpacks.toml        ← config Nixpacks — Railway tiene Root Directory
│                                = "gio_v3", así que nixpacks busca su config
│                                AQUÍ, no en la raíz del repo (ver Deployment)
├── CLAUDE.md                ← este archivo
├── README.md
├── Procfile                 ← gunicorn para Heroku/repo-root fallback (no usado
│                                por el Railway actual, ver Deployment)
├── runtime.txt              ← python-3.12.0
├── railway.json             ← config Railway (build + deploy)
└── .gitignore
```

## Base de datos

**Regla crítica:** la base de datos activa es siempre `gio_v3/pipeline.db`.

- `database.py` resuelve el path relativo a su propia ubicación (`__file__`), por eso
  el DB siempre está en `gio_v3/pipeline.db` sin importar desde dónde se arranque el proceso.
- En producción Railway usa la variable de entorno `DATABASE_PATH`, que **debe** apuntar
  a un volumen persistente montado (ver "Volumen de Railway" abajo) — es la fuente de
  verdad: sobrevive redeploys por sí solo.
- Turso (cloud) es un **respaldo asíncrono fuera del camino crítico** cuando hay volumen
  (`DATABASE_PATH` definido): cada escritura se confirma primero en el volumen y el push a
  Turso corre en background — si Turso está lento o caído, la app no se entera. Si el
  volumen aparece vacío al arrancar (primer deploy o volumen nuevo), se hace un bootstrap
  restaurando desde Turso una sola vez; nunca se pisa un volumen que ya tiene datos.
- **Sin `DATABASE_PATH`** (dev local sin volumen) el filesystem es efímero, así que si
  Turso está configurado el comportamiento es el modo previo: cada escritura bloquea hasta
  que Turso la confirma, porque es la única copia que sobrevive un reinicio.
- Diagnóstico: `get_db_status()` en `database.py` expone el modo activo
  (`"volume + Turso backup (async)"` / `"hybrid (SQLite + Turso, sync)"` / `"local SQLite only"`).

### Volumen de Railway — configuración manual (una sola vez)

Esto **no se puede hacer desde el repo**, es un recurso del dashboard de Railway:

1. En el servicio de Railway → pestaña **Volumes** → crear un volumen, mount path
   sugerido `/data` (cualquier ruta escribible del contenedor sirve).
2. Variable de entorno del servicio: `DATABASE_PATH=/data/pipeline.db` (debe apuntar a un
   archivo *dentro* del mount path, no al directorio).
3. Redeploy. En los logs de arranque debe aparecer
   `[DB] Modo: SQLite en volumen (fuente de verdad) + Turso backup async OK` — si sale
   `Modo hibrido: ... (sync)` es que `DATABASE_PATH` no llegó a definirse o el volumen no
   quedó montado ahí.
- Los uploads (`UPLOADS_DIR`, ver sección de Uploads) ya usan el mismo volumen vía
  `uploads_base_dir()` — no hace falta un volumen aparte para eso.

**Cuando necesites ejecutar un script que toca la DB:**

```bash
# Opción A — desde la raíz del repo (recomendado)
python -c "import sqlite3; conn = sqlite3.connect('gio_v3/pipeline.db'); ..."

# Opción B — cd primero
cd gio_v3 && python tu_script.py
```

**Nunca** apuntes al `pipeline.db` de la raíz del repo — ese archivo no existe
(fue eliminado en la limpieza del 2026-05-15) y si vuelve a aparecer es una copia
obsoleta generada accidentalmente.

## Uploads (fotos y documentos subidos por el usuario)

**Regla crítica:** el directorio base de uploads lo resuelve `utils.uploads_base_dir()`,
nunca lo hardcodees relativo a `__file__` en un módulo nuevo.

- Prioridad: env var `UPLOADS_DIR` > **mismo directorio** que contiene el archivo de
  `DATABASE_PATH` (mismo volumen de Railway que ya usa la DB) > `gio_v3/uploads` local
  (dev, en .gitignore).
- Los módulos que suben archivos (`guardarropa`, `perfil`, `plantas`, `harma`,
  `bienestar/salud`) construyen su `UPLOAD_DIR` como
  `os.path.join(uploads_base_dir(), '<subdir>')` — esa subcarpeta (`wardrobe/`, `docs/`,
  `harma/`, `medico/`, `plantas/`) vive **directamente** dentro del directorio de
  `DATABASE_PATH`, sin un nivel intermedio `uploads/` (en producción el volumen ya
  está montado en una carpeta llamada `uploads`, ej. `DATABASE_PATH=/app/uploads/pipeline.db`
  y las fotos están en `/app/uploads/wardrobe/...`).
- **Por qué existe esto:** hasta 2026-09-07 cada módulo hardcodeaba su `UPLOAD_DIR`
  relativo a su propia ubicación en el código (`gio_v3/uploads/...`), fuera del volumen
  persistente de Railway (que solo cubría `DATABASE_PATH`, ej. `/data/pipeline.db`).
  Cada redeploy crea un contenedor con filesystem nuevo, así que las fotos subidas
  desaparecían (el usuario las reportó como "efímeras") aunque la DB sí persistía y
  seguía referenciando el nombre de archivo ya perdido. Al derivar `UPLOADS_DIR` del
  mismo volumen que `DATABASE_PATH`, los uploads persisten igual que la DB sin
  necesitar configurar nada nuevo en Railway.
- **Bug corregido 2026-09-22:** la primera versión de `uploads_base_dir()` unía un
  `uploads` extra al directorio de `DATABASE_PATH` (`dirname(DATABASE_PATH)/uploads`),
  asumiendo que el volumen se llamaría algo distinto a "uploads". En este deploy real
  el volumen SÍ se llama `uploads`, así que esa ruta nunca existió
  (`/app/uploads/uploads/wardrobe`) y las 89 fotos de Guardarropa se veían rotas en la
  app aunque los archivos originales seguían intactos un nivel arriba
  (`/app/uploads/wardrobe/`). Diagnosticado con el endpoint de solo lectura
  `/guardarropa/admin/audit-fotos` (busca cada foto por nombre en todo el volumen antes
  de darla por perdida). Cero fotos se perdieron — fue puramente un bug de ruta.

## Cómo arrancar la app localmente

```bash
# Desde la raíz del repo
python gio_v3/run.py

# O bien
cd gio_v3 && python run.py
```

App disponible en `http://localhost:5000`.

## Variables de entorno

Crea `gio_v3/.env` (nunca se commitea). Usa `gio_v3/.env.example` como plantilla si existe.

```
TURSO_DATABASE_URL=libsql://...
TURSO_AUTH_TOKEN=eyJ...
SECRET_KEY=...
# DATABASE_PATH solo se usa en Railway (volumen persistente)
```

## Módulos y rutas

| Módulo | URL | Archivo principal |
|--------|-----|-------------------|
| Dashboard | `/` | `modules/dashboard/routes.py` |
| GTD | `/gtd` | `modules/gtd/routes.py` |
| Finanzas | `/finanzas` | `modules/finanzas/routes.py` |
| Guardarropa | `/guardarropa` | `modules/guardarropa/routes.py` |
| Wishlist | `/guardarropa/wishlist` | `modules/guardarropa/wishlist.py` |
| Idiomas | `/idiomas` | `modules/idiomas/routes.py` |
| Nutrición | `/nutricion` | `modules/nutricion/routes.py` |
| Recetas | `/recetas` | `modules/recetas/routes.py` |
| Recompensas | `/recompensas` | `modules/recompensas/routes.py` |
| Perfil | `/perfil` | `modules/perfil/routes.py` |

## Deployment (Railway)

**Importante:** el servicio de Railway tiene **Root Directory = `gio_v3`** configurado
en su dashboard (no en ningún archivo del repo). Esto significa que el contexto de
build de Railway/nixpacks YA ES el contenido de `gio_v3/` — ninguna ruta en
`railway.json`, `gio_v3/nixpacks.toml`, o los comandos de build/start debe llevar el
prefijo `gio_v3/` ni hacer `cd gio_v3`. Si un comando falla con
`cd: gio_v3: No such file or directory`, esa es la causa.

- `railway.json` (raíz del repo): Railway lo lee de ahí sin importar el Root
  Directory — controla `buildCommand`/`startCommand`.
- `gio_v3/nixpacks.toml`: nixpacks busca su propio archivo de config **dentro**
  del Root Directory configurado, no en la raíz del repo — por eso vive en
  `gio_v3/`, no junto a `railway.json`. Declara `providers = ["python", "node"]`
  explícitamente: al haber tanto `requirements.txt` como `package.json` (este
  último solo para compilar Tailwind localmente), nixpacks elegía un único
  provider "principal" y dejaba Python fuera del setup phase (`pip: command
  not found`) si no se fuerza la combinación de ambos.
- Build: `pip install -r requirements.txt` (sin prefijo — ya estás en `gio_v3/`)
- Start: `gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
- El CSS de Tailwind (`static/css/tailwind-built.css`) se compila localmente
  con `npm run build:css` y se commitea ya construido — no se recompila en
  cada deploy de Railway.

## Worktrees de Claude

Claude Code crea worktrees en `.claude/worktrees/<nombre>/`. Estos son clones
temporales del repo. **Los scripts de datos que tocan la DB deben apuntar
explícitamente a `gio_v3/pipeline.db` del repo principal**, no al del worktree.

