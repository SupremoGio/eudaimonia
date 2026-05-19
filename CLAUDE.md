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
│   └── uploads/             ← fotos subidas por el usuario (no se commitean)
├── CLAUDE.md                ← este archivo
├── README.md
├── Procfile                 ← gunicorn para Railway/Heroku
├── runtime.txt              ← python-3.12.0
├── railway.json             ← config Railway (build + deploy)
├── nixpacks.toml            ← config Nixpacks
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

- Config activa: `railway.json` en la raíz
- Build: `pip install -r gio_v3/requirements.txt`
- Start: `cd gio_v3 && gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 1 --timeout 120`

## Worktrees de Claude

Claude Code crea worktrees en `.claude/worktrees/<nombre>/`. Estos son clones
temporales del repo. **Los scripts de datos que tocan la DB deben apuntar
explícitamente a `gio_v3/pipeline.db` del repo principal**, no al del worktree.

## Deuda técnica UX

- **DEUDA (Sprint 1):** migrar `gio_v3/templates/finanzas/consumo_detalle.html` y
  `gio_v3/templates/finanzas/lock.html` a `eu/layout_sub.html`, luego borrar
  `gio_v3/templates/tw/layout.html`.
