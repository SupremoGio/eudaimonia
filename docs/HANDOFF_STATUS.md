# Estado de los handoffs v2

Revisado el 2026-11-13 leyendo el código de la rama `claude/modest-cray-h9zrlf`, que es `main` más los commits de Capturas, A11y y el catálogo, todavía sin mergear. Las rutas son relativas a `gio_v3/`.

**Fuente de los handoffs:** las carpetas `design_handoff_*/` no están en el repo. Se auditaron las copias subidas a la sesión: `design_handoff_ORDEN.md`, `FASE0.md` y un `SPRINTS.md` por paquete.

**Cómo se clasifica:**
- **hecho:** el código tiene lo que piden las tareas y los criterios de «Aceptación».
- **parcial:** la columna «Falta» dice qué queda.
- **pendiente:** no hay evidencia.
- **verificar a mano:** el criterio es visual (móvil, orden en pantalla), de teclado o depende de datos reales, así que leer el código no basta para confirmarlo. Esos criterios se revisaron con Playwright y axe al implementar cada sprint, pero aquí se marcan para revisarlos en el dispositivo.

**Resumen:**
- Los 16 paquetes del ORDEN (70 sprints) y los transversales están **hechos**.
- De **Remates**, Login S1 está **hecho**, Recetas S1 está **parcial** y Wishlist S1 está **pendiente**.

## Inicio v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · criterios del siguiente rango | hecho | `modules/gamification/engine.py:727` (`_next_rank_criteria`), `:579` (`criteria`); `tests/test_clasificacion_criterios.py` | — |
| S2 · héroe + «Siguiente paso» | hecho | `modules/dashboard/routes.py:112` (`_build_next_step`); `tests/test_dashboard_siguiente_paso.py`, `test_dashboard_hero_v2.py` | — |
| S3 · equilibrio de la semana (60%) | hecho | `modules/gamification/engine.py:8` (regla de balance); `tests/test_dashboard_balance_semana.py` | — |
| S4 · Pendiente primero + Inspiración | hecho | `templates/dashboard/index.html:12`; `tests/test_dashboard_pendiente_inspiracion.py` | — |
| S5 · constancia por rango + meta de racha | hecho | `modules/gamification/routes.py:328` (`constancia`); `tests/test_clasificacion_diaria_v2.py`, `test_dashboard_constancia_racha.py` | — |
| S6 · móvil, limpieza y QA | hecho | `templates/dashboard/index.html:16` (`page_head`) | verificar a mano: orden de bloques en móvil (Héroe → Pendiente → …) y topbar sin XP: es layout, se ve en pantalla |

## Oikonomia v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · datos del resumen | hecho | `modules/finanzas/routes.py:223` (metas 50·30·20), `:226` (`BUDGET_RISK_PCT`); `tests/test_oikonomia_hub.py` | — |
| S2 · «Marcar pagado» | hecho | `modules/finanzas/pagos_ciclo.py:69` (`pagados`); `tests/test_pago_ciclo.py` | — |
| S3 · encabezado + héroe | hecho | `templates/finanzas/hub/_hero.html:1` | — |
| S4 · Próximos pagos + Categorías en riesgo | hecho | `modules/finanzas/routes.py:144` (`_hub_debts`), `:200` (`_hub_budget_rows`); `templates/finanzas/hub/_debts.html:1` | — |
| S5 · accesos compactos, móvil y limpieza | hecho | `templates/finanzas/hub/_subs.html` | verificar a mano: disposición móvil de los accesos |

## Acta v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · clasificación con criterios | hecho | `modules/gamification/engine.py:579` (`criteria`); `tests/test_acta_v2.py` | — |
| S2 · «Anclas de hoy» + virtudes compactas | hecho | `modules/actividades/routes.py:205` (`acta_anchors`); `templates/actividades/_anchors.html` | — |
| S3 · encabezado y filtros | hecho | `templates/actividades/index.html` (`page_head`); `tests/test_acta_v2.py` | — |
| S4 · panel lateral, móvil y limpieza | hecho | `templates/actividades/index.html:32` (pipeline plegado) | verificar a mano: panel lateral en móvil |

## Praxis v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · captura en una barra | hecho | `templates/gtd/_capture.html`; `tests/test_praxis_v2.py` | — |
| S2 · Inbox de un clic, fechas relativas | hecho | `templates/gtd/praxis.html`; `tests/test_praxis_v2.py` | — |
| S3 · Hoy destacada + bono visible | hecho | `modules/gtd/prioridades.py:221` (bono diario en `xp_ledger`) | — |
| S4 · una sola moneda XP (D1) | hecho | `modules/gtd/routes.py:38` (`/points` solo redirige); `tests/test_praxis_v2.py` | — |
| S5 · pipeline de Acta = Ideas (D2) | hecho | `modules/actividades/routes.py:81` (`_pipeline_ideas`), `:477` | — |
| S6 · prioridades = estrellas (D3) | hecho | `modules/gamification/engine.py:1025` | — |

## Ataraxia v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · encabezado, pestañas y recompensas | hecho | `templates/ataraxia/index.html:15` (`role="tablist"`); `tests/test_ataraxia_v2.py` | — |
| S2 · un bloque abierto «Ahora» | hecho | `modules/ataraxia/routes.py:527` | — |
| S3 · revisión semanal automática | hecho | `modules/ataraxia/routes.py:267` (métricas automáticas), `modules/gamification/routes.py:365` | — |
| S4 · prioridades semanales desde Praxis | hecho | `modules/ataraxia/routes.py:9` (`prio`), `:68`; `modules/gtd/prioridades.py:29` (`semana_eleccion`) | — |

## Paideia v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · ritmo, XP y ancla de Acta | hecho | `modules/paideia/routes.py:82` (`ritmo`), `:29` (`_LIBRO_XP`); `tests/test_paideia_libros.py` | — |
| S2 · encabezado + héroe | hecho | `templates/paideia/index.html:10` (`page_head` con meta anual) | — |
| S3 · biblioteca en portadas | hecho | `templates/paideia/index.html` | verificar a mano: portadas reales dependen de las URL de imagen guardadas |
| S4 (opcional) · una escala de calificación | hecho | películas en ★ 1–5 (commit `c83cf60`) | — |

## Guardarropa v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · razón de la sugerencia y rotación | hecho | `modules/guardarropa/stylist.py:465` (`_razon`), `:517`; `tests/test_guardarropa_stylist.py` | — |
| S2 · encabezado + «Outfit de hoy» | hecho | `templates/guardarropa/index.html` | — |
| S3 · filtros en una fila + fotos | hecho | `templates/guardarropa/index.html` | verificar a mano: fotos: dependen del volumen de uploads en Railway |
| S4 (opcional) · wishlist contra el armario | hecho | `modules/guardarropa/routes.py:52` (`_armario`), `:97` (`_wishlist_summary`); `tests/test_wishlist_duplicados.py` | — |

## Logros v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · ETA de nivel, progreso de insignias, constancia | hecho | `modules/gamification/routes.py:242` (`dias_siguiente`), `modules/gamification/badges.py:27` (`progress_of`); `tests/test_logros.py` | — |
| S2 · encabezado + héroe de nivel | hecho | `templates/gamification/_head.html` | — |
| S3 · pestaña Colección | hecho | `modules/gamification/routes.py:246` (`coleccion_con_progreso`); `templates/gamification/_collection.html` | — |
| S4 · pestaña Historial | hecho | `templates/gamification/_historial.html`; `modules/gamification/routes.py:427` | — |

## Recompensas v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · ETA, meta y requisitos | hecho | `modules/recompensas/routes.py:196` (`eta_dias`); `tests/test_recompensas.py` | — |
| S2 · saldo y siguiente meta | hecho | `templates/recompensas/index.html` | — |
| S3 · grupos + canje con confirmación | hecho | `templates/recompensas/index.html` (`euConfirm` al canjear) | — |
| S4 · desde tus wishlists | hecho | `modules/recompensas/routes.py:340` (`wishlists_ec`) | — |

## Perfil v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · contadores y «Requiere atención» | hecho | `modules/perfil/resumen.py:174` (`atencion`); `tests/test_perfil.py` | — |
| S2 · lateral + Resumen | hecho | `templates/perfil/_resumen.html`, `_sechead.html` | — |
| S3 · copiar con un clic, privados | hecho | `templates/perfil/_vault.html`; `/perfil/api/privados` | — |
| S4 · medidas en lote | hecho | `modules/perfil/routes.py:158` (`/api/medidas/lote`), `:100` | — |
| S5 · recordatorios ↔ Oikonomia | hecho | `modules/perfil/resumen.py:143` (`vinculado_oikonomia`); `tests/test_perfil_recordatorios_grupos.py` | — |

## Hegemonikon v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · resumen del cuerpo, tratamiento | hecho | `modules/bienestar/salud.py:164` (`tratamiento`); `tests/test_hegemonikon.py` | — |
| S2 · «Hoy en tu cuerpo» + «En tratamiento» | hecho | `templates/bienestar/_hoy.html`, `_tratamiento.html` | — |
| S3 · partido, «Cuerpo» y «También aquí» | hecho | `modules/bienestar/routes.py:147` (`_proximo_partido`); `templates/bienestar/index.html:62` | — |
| S4 · Salud sin resumen repetido | hecho | `templates/bienestar/salud.html` | — |

## Harma v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · ritmo, edad del km, ETA y gasto | hecho | `modules/harma/plan.py:27` (`ritmo_km_mes`); `tests/test_harma.py` | — |
| S2 · odómetro y plan por urgencia | hecho | `templates/harma/index.html` | — |
| S3 · papeles y bitácora | hecho | `modules/harma/plan.py:93` (`papeles`); `templates/harma/_papeles.html`, `_bitacora.html` | — |
| S4 · verificación con Perfil, gasto con Oikonomia | hecho | `modules/harma/plan.py:152` (`crear_gasto`) | — |

## Eurythmia v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · espaciado, dominio, semana y bonos | hecho | `modules/eurythmia/routes.py:230` (`sugerencias`); `tests/test_eurythmia.py` | — |
| S2 · franja + «Sesión de hoy» | hecho | `templates/eurythmia/index.html:56` | — |
| S3 · repertorio y lateral | hecho | `templates/eurythmia/_progreso.html` | — |
| S4 · volver a Acta | hecho | `templates/actividades/_item.html:11`, `_anchors.html:24` | — |

## Viajes v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · maleta automática, consumibles, sugerencias | hecho | `modules/viajes/routes.py:347` (`_regenerar_maleta`), `:512` (`sugerencias`); `tests/test_viajes_v2.py` | — |
| S2 · encabezado, preparación y fases | hecho | `templates/viajes/_detail.html` | — |
| S3 · outfits en la fila, maleta en 2 columnas | hecho | `static/js/viajes.js:3` | verificar a mano: las 2 columnas de la maleta son layout |
| S4 · una sola página, Dinero en el lateral | hecho | `templates/viajes/_detail.html:43` (`vj-money`) | — |

## Idiomas v2 (Cosmopolitismo)

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · XP, Acta, plan real, feedback guardado | hecho | `modules/actividades/touch.py:12` (`marcar_touch`), `modules/idiomas/routes.py:9`; `tests/test_idiomas.py` | — |
| S2 · selector de idioma y repaso | hecho | `static/js/idiomas.js:1` (`id_lang`), `modules/idiomas/routes.py:282` | — |
| S3 · journal con revisión y tendencia | hecho | `modules/idiomas/routes.py:228` (`/api/journal/revisar`) | — |
| S4 · palabra del día, tests por destreza, Acta | hecho | `modules/idiomas/routes.py:615` (`ultimo_por_destreza`) | — |

## Nutrición v2

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · XP por el motor, racha calculada | hecho | `modules/nutricion/routes.py:630` (`_log`); `tests/test_nutricion_engine.py` | — |
| S2 · Hoy por hora + «¿Cómo cayó?» | hecho | `templates/nutricion/index.html`, `static/js/nutricion.js` | — |
| S3 · el día, Bristol y disparadores | hecho | `templates/nutricion/index.html:69`, `modules/nutricion/routes.py:721` (`disparadores_30d`) | — |
| S4 · un solo recetario | hecho | `modules/nutricion/routes.py:481` (`migrar_banco`); `recetas.fodmap` y `recetas.momento` en `modules/recetas/routes.py:14`, `:19` | verificar a mano: que `migrar_banco` ya corrió en producción (no se corren migraciones en esta auditoría) |

## Navegación

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · `ui.page_head`, `VIEWS` y `nav_view` | hecho | `modules/nav.py:232` (`VIEWS`), `:299` (`view_of`); `templates/_ui/macros.html:231` (`page_head`) | — |
| S2 · la regla en todas las pantallas | hecho | `tests/test_nav.py` (un h1 por ruta de NAV = `nav_title`) | — |

## Captura rápida

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · registro `QUICK` + `/api/quick/options` | hecho | `modules/nav.py:122` (`QUICK`), `:205` (`quick_for`); `modules/quick.py`; `tests/test_quick.py` | — |
| S2 · «+» en la barra, hoja y contadores | hecho | `templates/eu/layout_sub.html:122` (`#eu-quick`), `static/js/eu-quick.js` | — |
| S3 · ⌘K que registra | hecho | `static/js/eu-quick.js:29` (`parse`); `tests/quick_parse_cases.json` | — |

## Avisos

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · contrato `avisos(db, hoy)` + `recolectar()` | hecho | `modules/avisos.py:51` (`FUENTES`), `:189` (`recolectar`); `tests/test_avisos.py` | — |
| S2 · campana + panel | hecho | `templates/eu/layout_sub.html:106` (`#eu-avisos-btn`), `static/js/eu-avisos.js` | — |
| S3 · preferencias + Inicio | hecho | `modules/quick.py:47` (`preferencias`), `templates/perfil/_ajustes.html` (`avisos_off:<fuente>`) | — |

## Revisión semanal

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · ruta, pasos 1–2, guardado parcial | hecho | `modules/ataraxia/routes.py:740` (`revision`), `:919` (`save_revision`); `tests/test_revision.py` | — |
| S2 · pasos 3–4, cierre y entradas | hecho | `modules/ataraxia/routes.py:614` (`_cabos`); `templates/ataraxia/revision.html`, `static/js/revision.js` | — |

## Estados vacíos

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| S1 · `ui.empty(kind=…)`, migración y `?demo=1` | hecho | `templates/_ui/macros.html:120` (`empty`), `modules/demo.py:33` (`_seed`); `tests/test_vacios.py` | — |
| S2 · Primeros pasos | hecho | `modules/onboarding.py`, `templates/_ui/onboarding.html` | — |

## Plantas y Ajustes

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| Plantas S1 · «Hoy» y cuadrícula compacta | hecho | `modules/plantas/routes.py:162` (`cuidados_hoy`); `tests/test_plantas_ajustes.py` | — |
| Plantas S2 · panel con pestañas | hecho | `templates/plantas/index.html` (`#pl-panel`, `<details id="pl-avanzado">`), `static/js/plantas.js` | verificar a mano: hoja a pantalla completa en móvil |
| Ajustes S1 · un solo lugar para lo configurable | hecho | `modules/perfil/routes.py:595` (`/api/ajustes`), `:650` (`/api/exportar`); `templates/perfil/_ajustes.html` | — |

## A11y + catálogo (y Capturas)

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| Capturas · `scripts/capturas.py` | hecho | `scripts/capturas.py` (`--comparar a b`) | sin mergear a `main` |
| S1 · `a11y_lint` en `pre_deploy_check` | hecho | `scripts/pre_deploy_check.py:115` (`_check_a11y`), `scripts/a11y_lint.py`; `tests/test_a11y_lint.py` | sin mergear a `main` |
| S2 · línea base en 0 y `euDialog` | hecho | `scripts/a11y_baseline.json` (vacío), `static/js/eu-dialog.js:3` | sin mergear a `main`; verificar a mano: lector de pantalla real (VoiceOver), axe no lo cubre |
| S3 · `/_ui` y `docs/COMPONENTES.md` | hecho | `app.py:136` (`/_ui`), `scripts/pre_deploy_check.py:132`, `scripts/gen_componentes_md.py`; `tests/test_catalogo_ui.py` | sin mergear a `main` |

## Remates (Login, Recetas, Wishlist de Oikonomia)

| Sprint | Estado | Evidencia (archivo:línea) | Falta |
|---|---|---|---|
| Login S1 · pulido | hecho | una sola cita: `templates/auth/login.html:24` (`au-hero-q`, solo escritorio) y `:41` (`au-mob-q`, solo móvil), sin `au-q`; mínimo 8: `modules/auth/routes.py:8` (`MIN_PASS`), contador «N de 8» `login.html:60` (`#au-pw-n`, `eu-help`), `static/js/login.js:33` (`contar`); coincidencia en el segundo campo: `login.js:41` (`coincide`), `login.html:65` (`#au-err2`); mostrar/ocultar: `ui.iconbtn('eye', …, pressed=False)` en `login.html:54`, `:59`, `:64`; bloqueo: `app.py:203` (429 con `retry_after` y `Retry-After`), `login.js:70` (`bloquear`, botón deshabilitado y «Espera N s»); busy: `aria-busy` + spinner de `components.css:55`; `tests/test_login.py` | verificar a mano: que en el iPhone se vea una sola cita y la cuenta regresiva (en Playwright con iPhone 13 se ve una cita, y «Espera 60 s» → «59 s» con el botón deshabilitado). En móvil la página no tiene `h1` visible porque el del hero se oculta. Ya pasaba antes y no se cambió, porque `a11y_lint` no admite dos `h1`. |
| Recetas S1 · encontrar y usar | parcial | búsqueda por ingrediente: `static/js/recetas.js:31`; chip «Apta FODMAP» aparte: `templates/recetas/index.html:25` | 1) Siguen las 3 `eu-stat` (`templates/recetas/index.html:15`–`17`). 2) Falta «Para hoy», que necesita una ruta que lea los momentos del plan de Nutrición y «Usar» contra su endpoint. 3) Las categorías siguen como `eu-chips` (`:22`), no como `eu-seg`, y el FODMAP no se activa por la fase de eliminación (`modules/recetas/routes.py:46` solo lee `?fodmap=`). 4) El detalle no tiene franja de macros, selector de porciones, pasos con casilla ni modo «Cocinar» con `wakeLock`. 5) El modal no tiene «Avanzado». **No se cumple ningún criterio de aceptación.** |
| Wishlist de Oikonomia S1 · por mes y contra el presupuesto | pendiente | solo lo que ya había: redirección sin `fin_ok`, `modules/finanzas/prioridades.py:13`; dedup al crear, `:74` (`wishlist_dedup.existente`); `/api/ec-status`, `:163` | Todo el sprint. 1) El antetítulo dice «Lista de prioridades · N pendientes», sin el «$X» (`templates/finanzas/prioridades.html:13`). 2) Siguen las 4 `eu-stat` (`:19`–`21`). Falta el «libre para deseos» de Oikonomia S1: hoy solo existe `deseos.total_gastado` del presupuesto 50·30·20 (`modules/finanzas/coach.py:110`), así que la celda «Este mes» necesita definir ese cálculo. 3) Falta agrupar por `mes_objetivo`; hoy hay chips de estado y prioridad (`static/js/prioridades.js:40`). 4) Faltan las acciones en la fila: «Comprado» con precio en línea, «Mover de mes» y «⋯». 5) Falta «o N EC». 6) Falta el enlace «también en Guardarropa». El criterio «sin `fin_ok` redirige» ya se cumple. |

## Notas de la Fase 1 que ya quedaron resueltas
- **XP negativo del desliz (antes de 1.2):** el motor no acepta montos negativos, porque `process_activity` aplica `max(1, …)`. El desliz se descuenta con `engine._award_xp(-pen, 'activity', …, log_id)`, y `remove_activity` lo revierte. Está documentado en `modules/nutricion/routes.py`, sección «XP por el motor».
- **Insignias con el histórico (después de 1.2):** no se reprocesa el histórico de `xp_ledger` con `source='nutricion'`, y la marca `app_settings.nutri_engine_since` separa lo viejo de lo nuevo. Ninguna insignia recibe de golpe acciones viejas.
- **Helper de touch de Acta (1.3 / 1.4):** es `modules/actividades/touch.py` (`marcar_touch`). Lo usan Idiomas y la reflexión de Acta.
- **Columnas `origen` y `origen_id` de recordatorios:** existen una sola vez y las usa Harma (`plan.upsert_recordatorio`).

## Notas de Avisos
- **«Estado de cuenta por subir»:** `summary_pendientes()` no lo calcula. El aviso nuevo solo cubre BBVA TDC, la única tarjeta con día de corte conocido (22). Se dispara si pasaron 3 días del corte y no hay ningún movimiento de esa tarjeta en el periodo que cerró (`ESTADO_CORTE` en `modules/finanzas/routes.py`).
- **Deshacer:** solo se ofrece cuando el módulo tiene endpoint inverso: pago de tarjeta (`DELETE /finanzas/api/pago-ciclo`), posponer y descartar (`/api/avisos/<clave>/restaurar`). «Hecho» en recordatorios y tareas, y «Registrar» en Harma, no tienen inverso que restaure el estado anterior, así que no muestran Deshacer.
- **Logros:** antes nada marcaba `notified=1`, así que todo el histórico seguía en 0. El grupo Logros solo muestra lo desbloqueado en los últimos 14 días.
- **Fuentes extra:** Plantas y Fútbol entran al centro para que «Pendiente» de Inicio y la campana muestren los mismos pendientes de hoy. Nutrición no tiene un «síntoma sin registrar» con fecha que avisar, así que quedó fuera.

## Notas de Revisión semanal
- **XP una sola vez:** antes se pagaba en el primer guardado. Ahora se paga al cerrar (`cerrar: true`) y se marca `xp_pagado`. La migración `revision_semanal_v2` deja como pagadas las revisiones que ya existían, así que cerrar una semana guardada con el formulario viejo no vuelve a pagar.
- **Calorías quemadas:** ya no se piden (el mockup trae 9 métricas sin ellas). La columna y el histórico se quedan, y Logros › Semanas la sigue mostrando.
- **Racha de anclas:** es la racha de Acta que usa Inicio (días seguidos con actividad), contada al domingo de la semana revisada.
- **«Mover» en vencidas:** pasa la fecha límite al lunes siguiente. «Hoy» la pone para hoy y la manda al cuadrante Hoy.
- **Casilla de la rutina:** `check_tarea` ya no vuelve a pagar una casilla que estaba marcada.

## Notas de Estados vacíos
- **`?demo=1`:** cada petición usa una copia temporal de una base de ejemplo (esquema completo y datos de muestra). La copia se borra al terminar, así que nada llega a la base real ni a Turso. En el navegador, el `fetch` global bloquea las escrituras y agrega `demo=1` a las lecturas.
- **Primer uso:** la primera escritura del módulo en una pantalla con `setup` recarga la página para pasar al contenido. En Eurythmia e Idiomas la pantalla principal es la primera acción, así que el botón solo muestra el contenido.
- **Datos que ya vienen sembrados:** las anclas, las recompensas de ejemplo, el repertorio de Eurythmia y el plan de Idiomas. Por eso «Elige tus anclas» aparece hecho desde el inicio, y para «tu primera recompensa» las de ejemplo no cuentan. Eurythmia muestra el `setup` mientras no hay ninguna sesión, e Idiomas mientras no hay tests ni journal.

## Notas de Plantas y Ajustes
- **«Regar las N»:** usa el mismo `/api/riego-grupo`, que riega todas las del entorno con el riego no al día, igual que antes. Por eso la barra cuenta así, y puede incluir alguna «próxima» que todavía no está en la lista de Hoy.
- **Panel:** en escritorio se abre solo, con la primera planta de Hoy. En móvil es una hoja a pantalla completa. Esc lo cierra y el foco vuelve a la tarjeta.
- **Ajustes:** la sección «Avisos» de Perfil desaparece. `/perfil/?sec=avisos` redirige a `?sec=ajustes#avisos`. `/api/avisos/preferencias` sigue existiendo por compatibilidad.
- **Exportar:** pide `fin_ok`, porque incluye finanzas. Deja fuera la bóveda de contraseñas, `app_settings` (tokens y hashes) y las fotos.

## Notas de A11y + catálogo
- **Línea base inicial: 29 problemas.** Eran 13 de `--fg-4` en texto, 10 de `outline:none` sin reemplazo, 4 campos sin etiqueta y 2 `onclick` en fondos. Uno de los campos era un `<select>` dentro de un comentario HTML; ahora el lint ignora los comentarios. Hoy la línea base está en 0, sin excepciones.
- **Anillo de foco de los campos:** `outline:2px solid transparent` en vez de `none`. El anillo visible sigue siendo el `box-shadow`, y el outline transparente aparece en modo de alto contraste.
- **`euConfirm`** (`eu-motion.js`) conserva su propio manejo: es un `alertdialog` creado al vuelo, con foco atrapado y Esc. No pasa por `euDialog`.
- **Catálogo `/_ui`:** responde 404 salvo con `FLASK_ENV=development`, `app.debug` o `session['is_admin']`. El ejemplo de `page_head` baja su `h1` a `role=heading` de nivel 2 para no tener dos `h1` en la página.

## Siguiente paso
- **ORDEN (Fases 1–3):** no queda ningún sprint pendiente.
- **Siguiente: Remates · Recetas S1.** Login S1 ya está hecho, y los tres sprints de Remates son independientes, así que sigue el próximo del `SPRINTS.md`. Toca `templates/recetas/*`, el archivo de choque con Nutrición S4 y Hegemonikon S3, que ya están hechos. «Para hoy» usa el endpoint de Nutrición S4, que también está hecho.
- **Después: Wishlist de Oikonomia S1.** Toca `modules/finanzas/*`, así que conviene correrla sola. Antes hay que decidir cómo se calcula «libre para deseos». Si no existe, la celda «Este mes» no aparece, como dice el sprint.
- **Sin mergear:** Capturas, A11y + catálogo y Login S1 siguen en la rama.
