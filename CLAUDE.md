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
- En producción Railway usa la variable de entorno `DATABASE_PATH` (volumen montado).
- Turso (cloud) se sincroniza en escritura si `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN` están definidos.

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

