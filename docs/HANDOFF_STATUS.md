# Estado de los handoffs v2 (Fase 0 de `design_handoff_ORDEN.md`)

Revisado el 2026-11-12 contra `main`, después del merge de Nutrición v2 (PR #121).
**Los 16 paquetes del ORDEN (70 sprints) y los transversales Navegación (2) y Captura rápida (3) están hechos.** La evidencia es el commit en `main` y una ruta `archivo:línea` del código que cada sprint pide.
Las rutas son relativas a `gio_v3/`.

Algunos paquetes se implementaron en un solo commit con todos sus sprints. En esos casos se repite el commit y la evidencia de cada sprint apunta a su pieza.

| Paquete | Sprint | Estado | Commit | Evidencia |
|---|---|---|---|---|
| Inicio v2 | S1 · criterios del siguiente rango | hecho | `511f4d6` | `modules/gamification/engine.py:727` (`_next_rank_criteria`), `:579` (`criteria`) |
| Inicio v2 | S2 · héroe + «Siguiente paso» | hecho | `1169660` | `modules/dashboard/routes.py:112` (`_build_next_step`) |
| Inicio v2 | S3 · equilibrio de la semana (60%) | hecho | `db8b156` | `modules/gamification/engine.py:8` (regla de balance) |
| Inicio v2 | S4 · Pendiente primero + Inspiración | hecho | `627cf70` | `templates/dashboard/` (columna lateral) |
| Inicio v2 | S5 · constancia por rango + meta de racha | hecho | `60e69e9` | `modules/gamification/routes.py:328` (`constancia`) |
| Inicio v2 | S6 · móvil, limpieza y QA | hecho | `e01f08c` | topbar sin XP en Inicio |
| Oikonomia v2 | S1 · datos del resumen | hecho | `53e1a2c` | `modules/finanzas/routes.py:142` (`BUDGET_RISK_PCT`), `:24` |
| Oikonomia v2 | S2 · «Marcar pagado» | hecho | `7f89ea6` | `modules/finanzas/pagos_ciclo.py:69` (`pagados`) |
| Oikonomia v2 | S3 · encabezado + héroe | hecho | `f7793a1` | `templates/finanzas/hub/` |
| Oikonomia v2 | S4 · Próximos pagos + Categorías en riesgo | hecho | `5d2d5c6` | `templates/finanzas/hub/_debts.html:1`, `_subs.html:2` |
| Oikonomia v2 | S5 · accesos compactos, móvil y limpieza | hecho | `f8b2639` | `templates/finanzas/hub/_subs.html` |
| Acta v2 | S1 · clasificación con criterios | hecho | `7b372d1` | `modules/gamification/engine.py:763` |
| Acta v2 | S2 · «Anclas de hoy» + virtudes compactas | hecho | `e719c4c` | `modules/actividades/routes.py:203` |
| Acta v2 | S3 · encabezado y filtros | hecho | `815429f` | `templates/actividades/` |
| Acta v2 | S4 · panel lateral, móvil y limpieza | hecho | `c04c418` | `templates/actividades/` |
| Praxis v2 | S1 · captura en una barra | hecho | `a275697` | `templates/gtd/` |
| Praxis v2 | S2 · Inbox de un clic, fechas relativas | hecho | `394944a` | `templates/gtd/` |
| Praxis v2 | S3 · Hoy destacada + bono visible | hecho | `9b2f184` | `templates/gtd/` |
| Praxis v2 | S4 · una sola moneda XP (D1) | hecho | `91f9076` | `modules/gtd/prioridades.py:226`, `modules/gtd/routes.py:40` |
| Praxis v2 | S5 · pipeline de Acta = Ideas (D2) | hecho | `bee8c4d` | `modules/actividades/routes.py:81`, `:477` |
| Praxis v2 | S6 · prioridades = estrellas (D3) | hecho | `9302e54` | `modules/gamification/engine.py:1025`, `modules/gtd/prioridades.py:92` |
| Ataraxia v2 | S1 · encabezado, pestañas y recompensas | hecho | `7276406` | `templates/ataraxia/` |
| Ataraxia v2 | S2 · un bloque abierto «Ahora» | hecho | `ba11882` | `modules/ataraxia/routes.py:434` |
| Ataraxia v2 | S3 · revisión semanal automática | hecho | `753b614` | `modules/ataraxia/routes.py:126`, `modules/gamification/routes.py:365` |
| Ataraxia v2 | S4 · prioridades semanales desde Praxis | hecho | `1273c9e` | `modules/ataraxia/routes.py:503`, `templates/ataraxia/_bloque.html:40` |
| Paideia v2 | S1 · ritmo, XP y ancla de Acta | hecho | `d21b63f` | `modules/paideia/routes.py:82` (`ritmo`), `:29` (`_LIBRO_XP`) |
| Paideia v2 | S2 · encabezado + héroe | hecho | `f6bc81d` | `templates/paideia/` |
| Paideia v2 | S3 · biblioteca en portadas | hecho | `f3011ae` | `templates/paideia/` |
| Paideia v2 | S4 (opcional) · una escala de calificación | hecho | `c83cf60` | películas en ★ 1–5 |
| Guardarropa v2 | S1 · razón de la sugerencia y rotación | hecho | `cfefd78` | `modules/guardarropa/stylist.py:419` |
| Guardarropa v2 | S2 · encabezado + «Outfit de hoy» | hecho | `5ee3c17` | `templates/guardarropa/` |
| Guardarropa v2 | S3 · filtros en una fila + fotos | hecho | `2dbd520` | `templates/guardarropa/` |
| Guardarropa v2 | S4 (opcional) · wishlist contra el armario | hecho | `67c29e9` | `modules/guardarropa/routes.py:1091` |
| Logros v2 | S1 · ETA de nivel, progreso de insignias, constancia | hecho | `2d6ecdd` | `modules/gamification/routes.py:242` (`dias_siguiente`), `modules/gamification/badges.py:27` |
| Logros v2 | S2 · encabezado + héroe de nivel | hecho | `2d6ecdd` | `templates/gamification/` |
| Logros v2 | S3 · pestaña Colección | hecho | `2d6ecdd` | `modules/gamification/routes.py:246` (`coleccion_con_progreso`) |
| Logros v2 | S4 · pestaña Historial | hecho | `2d6ecdd` | historial de canjes y XP en Logros |
| Recompensas v2 | S1 · ETA, meta y requisitos | hecho | `5240d1e` | `modules/recompensas/routes.py:196` (`eta_dias`), `:299` |
| Recompensas v2 | S2 · saldo y siguiente meta | hecho | `5240d1e` | `templates/recompensas/` |
| Recompensas v2 | S3 · grupos + canje con confirmación | hecho | `5240d1e` | `templates/recompensas/` |
| Recompensas v2 | S4 · desde tus wishlists | hecho | `5240d1e` | `modules/recompensas/routes.py:340` (`wishlists_ec`) |
| Perfil v2 | S1 · contadores y «Requiere atención» | hecho | `e797790` | `modules/perfil/resumen.py:174` (`atencion`) |
| Perfil v2 | S2 · lateral + Resumen | hecho | `e797790` | `templates/perfil/` |
| Perfil v2 | S3 · copiar con un clic, privados | hecho | `e797790` | `/perfil/api/privados` |
| Perfil v2 | S4 · medidas en lote | hecho | `e797790` | `modules/perfil/routes.py:146` |
| Perfil v2 | S5 · recordatorios ↔ Oikonomia | hecho | `e797790` | `modules/perfil/resumen.py:143` (`vinculado_oikonomia`) |
| Hegemonikon v2 | S1 · resumen del cuerpo, tratamiento | hecho | `d9a05eb` | `modules/bienestar/salud.py:136` (`tratamiento`) |
| Hegemonikon v2 | S2 · «Hoy en tu cuerpo» + «En tratamiento» | hecho | `d9a05eb` | `templates/bienestar/` |
| Hegemonikon v2 | S3 · partido, «Cuerpo» y «También aquí» | hecho | `d9a05eb` | `modules/bienestar/routes.py:54` (`_proximo_partido`) |
| Hegemonikon v2 | S4 · Salud sin resumen repetido | hecho | `d9a05eb` | `templates/bienestar/` |
| Harma v2 | S1 · ritmo, edad del km, ETA y gasto | hecho | `2512fd4` | `modules/harma/plan.py:27` (`ritmo_km_mes`) |
| Harma v2 | S2 · odómetro y plan por urgencia | hecho | `2512fd4` | `templates/harma/` |
| Harma v2 | S3 · papeles y bitácora | hecho | `2512fd4` | `modules/harma/plan.py:93` (`papeles`) |
| Harma v2 | S4 · verificación con Perfil, gasto con Oikonomia | hecho | `2512fd4` | `modules/harma/plan.py:152` (`crear_gasto`) |
| Eurythmia v2 | S1 · espaciado, dominio, semana y bonos | hecho | `2671a18` | `modules/eurythmia/routes.py:230` (`sugerencias`) |
| Eurythmia v2 | S2 · franja + «Sesión de hoy» | hecho | `2671a18` | `templates/eurythmia/index.html` |
| Eurythmia v2 | S3 · repertorio y lateral | hecho | `2671a18` | `templates/eurythmia/_progreso.html` |
| Eurythmia v2 | S4 · volver a Acta | hecho | `2671a18` | `templates/actividades/_item.html:11`, `_anchors.html:24` |
| Viajes v2 | S1 · maleta automática, consumibles, sugerencias | hecho | `627967f` | `modules/viajes/routes.py:347` (`_regenerar_maleta`), `:512` (`sugerencias`) |
| Viajes v2 | S2 · encabezado, preparación y fases | hecho | `627967f` | `templates/viajes/_detail.html` |
| Viajes v2 | S3 · outfits en la fila, maleta en 2 columnas | hecho | `627967f` | `static/js/viajes.js` |
| Viajes v2 | S4 · una sola página, Dinero en el lateral | hecho | `627967f` | `templates/viajes/_detail.html` (`vj-money`), `templates/finanzas/viajes.html` |
| Idiomas v2 | S1 · XP, Acta, plan real, feedback guardado | hecho | `8fbaa2b` | `modules/actividades/touch.py:12` (`marcar_touch`), `modules/idiomas/routes.py` |
| Idiomas v2 | S2 · selector de idioma y repaso | hecho | `8fbaa2b` | `static/js/idiomas.js` (`id_lang`) |
| Idiomas v2 | S3 · journal con revisión y tendencia | hecho | `8fbaa2b` | `/idiomas/api/journal/revisar` |
| Idiomas v2 | S4 · palabra del día, tests por destreza, Acta | hecho | `8fbaa2b` | `modules/idiomas/routes.py:615` (`ultimo_por_destreza`) |
| Nutrición v2 | S1 · XP por el motor, racha calculada | hecho | `d48fef6` | `modules/nutricion/routes.py:630` (`_log`) |
| Nutrición v2 | S2 · Hoy por hora + «¿Cómo cayó?» | hecho | `d48fef6` | `templates/nutricion/index.html`, `static/js/nutricion.js` |
| Nutrición v2 | S3 · el día, Bristol y disparadores | hecho | `d48fef6` | `disparadores_30d` en `modules/nutricion/routes.py` |
| Nutrición v2 | S4 · un solo recetario | hecho | `d48fef6` | `modules/nutricion/routes.py:503` (`migrar_banco`), `recetas.fodmap` y `recetas.momento` |
| Navegación | S1 · `ui.page_head`, `VIEWS` y `nav_view` | hecho | `637162d` | `modules/nav.py` (`VIEWS`, `view_of`, `page_info`), `templates/_ui/macros.html` (`page_head`) |
| Navegación | S2 · la regla en todas las pantallas | hecho | `637162d` | `tests/test_nav.py` (un h1 por ruta de NAV = `nav_title`, sin lemas) |
| Captura rápida | S1 · registro `QUICK` + `/api/quick/options` | hecho | rama actual | `modules/nav.py` (`QUICK`, `quick_for`), `modules/quick.py` |
| Captura rápida | S2 · «+» en la barra, hoja y contadores | hecho | rama actual | `templates/eu/layout_sub.html` (`#eu-quick`), `static/js/eu-quick.js`, `/api/quick/badges` |
| Captura rápida | S3 · ⌘K que registra | hecho | rama actual | `eu-quick.js` (`parse`), `tests/quick_parse_cases.json` |

## Notas de la Fase 1 que ya quedaron resueltas
- **XP negativo del desliz (antes de 1.2):** el motor no acepta montos negativos, porque `process_activity` aplica `max(1, …)`. El desliz se descuenta con `engine._award_xp(-pen, 'activity', …, log_id)`, y `remove_activity` lo revierte. Está documentado en `modules/nutricion/routes.py`, sección «XP por el motor».
- **Insignias con el histórico (después de 1.2):** no se reprocesa el histórico de `xp_ledger` con `source='nutricion'`, y la marca `app_settings.nutri_engine_since` separa lo viejo de lo nuevo. Ninguna insignia recibe de golpe acciones viejas.
- **Helper de touch de Acta (1.3 / 1.4):** es `modules/actividades/touch.py` (`marcar_touch`). Lo usan Idiomas y la reflexión de Acta.
- **Columnas `origen` y `origen_id` de recordatorios:** existen una sola vez y las usa Harma (`plan.upsert_recordatorio`).

## Siguiente paso
No queda ningún sprint pendiente en el ORDEN. Cualquier handoff nuevo empieza con su propio `SPRINTS.md`.
