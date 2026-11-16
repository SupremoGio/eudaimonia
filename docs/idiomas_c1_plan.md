# Plan B2 → C1 · Inglés y francés (v2)

Pilar Cosmopolitismo. Empieza el 2026-11-16 y termina el 2027-06-13, con 3 fases de 10 semanas.

**Cómo llega a la app** (dos migraciones en `gio_v3/database.py`, cada una corre una sola vez):
- **`idiomas_c1_plan_2026_11`:** parte las anclas de idioma en sesiones A y B y agrega el repaso y los hitos.
- **`idiomas_ajuste_v2_2026_11`:** aplica `eudaimonia_ajuste_v2.json`: menos casillas por día, foco en idiomas y fases de 10 semanas.

## Reglas globales

- **Versión mínima de cada ancla:** da el 50 % del XP (redondeado hacia arriba), 0 EC y conserva la racha, porque el día queda registrado. Antes daba ⅓.
- **Vista del día en Acta:**
  - las anclas del día;
  - **«Foco de hoy»:** los touches con `foco`, hasta 8;
  - **«Extras»:** el resto, por virtud y plegado.
- **Un idioma por escucha y el otro por lectura, cada día;** el sábado se repasan los dos.

## Hábitos de Cosmopolitismo

| Hábito | Clave | Día | Tipo | Min (mínima) | XP · EC | Foco |
|---|---|---|---|---|---|---|
| Inglés · Sesión A (input) | `ancla_ingles` | lun | ancla | 60 (20) | 6 · 2 | — |
| Francés · Sesión A (input) | `ancla_frances` | mar | ancla | 60 (20) | 6 · 2 | — |
| Inglés · Sesión B (output) | `ancla_ingles_b` | jue | ancla | 60 (20) | 7 · 2 | — |
| Francés · Sesión B (output) | `ancla_frances_b` | vie | ancla | 60 (20) | 7 · 2 | — |
| Repaso semanal EN+FR | `ancla_repaso_idiomas` | sáb (salvo checkpoints) | ancla | 60 (25) | 6 · 2 | — |
| Autodiagnóstico C1 (EN + FR) | `autodiagnostico_c1` | 2027-01-23 · 04-03 · 06-12 | ancla, en lugar del repaso | 90 | 30 · 10 | — |
| Anki EN+FR · 10 min | `anki_idiomas` | diario, mañana | touch | 10 | 2 · 0 | sí |
| Escucha extensiva EN · 20 min | `escucha_en` | lun, mié, jue | touch | 20 | 2 · 0 | sí |
| Escucha extensiva FR · 20 min | `escucha_fr` | mar, vie, dom | touch | 20 | 2 · 0 | sí |
| Lectura extensiva FR · 20 min | `lectura_fr` | lun, mié, jue, noche | touch | 20 | 3 · 1 | sí |
| Lectura extensiva EN · 20 min | `lectura_en` | mar, vie, dom, noche | touch | 20 | 3 · 1 | sí |
| Conversación con humano 10 min+ | `conversacion` | cuando ocurra | ocasional | — | 5 · 2 | — |
| 15 hitos (monólogo, conversación, novela, película…) | `hito_*` | una sola vez | ocasional `one_time` | — | 20–100 | — |

**Desactivados:** Repaso de vocabulario, VividVocab y Anki 10 min (se fusionan en Anki EN+FR diario). También Writing journal (va dentro de la Sesión B; el journal de Idiomas sigue funcionando, pero ya no da XP de Acta), Podcast/escucha mixta, Lectura mixta y Test certificación.

## Fusiones en otras virtudes

| Antes | Ahora |
|---|---|
| Skin care · Corrección diaria · 3 agradecimientos | **Ritual nocturno** (5 XP). Una casilla con su checklist; hereda el cuadro de reflexión escrita (corrección y gratitud), que no lo marca solo porque el ritual también incluye el skin care |
| Meditar · Visualización | **Meditar + visualizar** (3 XP) |
| Comer fruta · Colación saludable | **Nutrición del día (fruta + colación)** (2 XP, sin foco) |
| Partido | **Partido extra (fuera del miércoles)**, para no contar doble con el ancla del miércoles |

Las insignias de salud base y el «Siguiente paso» de Inicio ya cuentan las claves nuevas.

## Calendario

| Día | Anclas de idioma | Escucha | Lectura |
|---|---|---|---|
| Lun | Inglés A | EN | FR |
| Mar | Francés A | FR | EN |
| Mié | — | EN | FR |
| Jue | Inglés B | EN | FR |
| Vie | Francés B | FR | EN |
| Sáb | Repaso EN+FR (o Autodiagnóstico) | — | — |
| Dom | — | FR | EN |

Anki EN+FR va todos los días por la mañana.

## Estructura de las sesiones

**Sesión A · Input (60 min; mínima de 20 min: solo el input intensivo)**

| Min | Bloque |
|---|---|
| 25 | Input intensivo: artículo o podcast con transcripción |
| 15 | Shadowing de 2–3 min del mismo audio |
| 20 | Gramática y léxico del foco de la fase; tarjetas a Anki |

**Sesión B · Output (60 min; mínima de 20 min: solo la conversación con IA)**

| Min | Bloque |
|---|---|
| 20 | Conversación por voz con IA sobre un tema abstracto |
| 25 | Writing de 250–400 palabras, corregido por IA (o en Idiomas › Journal, que revisa con LanguageTool) |
| 15 | Cuaderno de errores: pasar los errores a Anki |

**Repaso del sábado (60 min; mínima de 25 min)**

| Min | Bloque |
|---|---|
| 20 | Cuaderno de errores EN+FR de la semana |
| 10 | Registrar las métricas de la semana |
| 30 | Episodio o película sin subtítulos (alterna el idioma cada semana) |

**Prompt de corrección con IA:**
> «Actúa como corrector nativo de [inglés/francés] de nivel C2. Devuélveme: 1) mi texto corregido; 2) una tabla error → corrección → regla, clasificada en gramática, léxico, colocación o registro; 3) 3 reformulaciones más idiomáticas de mis frases más débiles; 4) una nota de 1 a 5 sobre coherencia, riqueza léxica, precisión y registro. No reescribas mi estilo si es correcto.»

Verifica siempre lo que diga la IA con LanguageTool (EN y FR) o Antidote (FR).

## Fases

| Fase | Fechas | Foco EN | Foco FR | Checkpoint |
|---|---|---|---|---|
| 1 · Cimientos C1 | 2026-11-16 → 2027-01-24 | Input denso (ensayos, podcasts largos), phrasal verbs y collocations | Litote y figuras de estilo, léxico fino, concordance des temps, comprensión oral | sáb 2027-01-23 |
| 2 · Output y argumentación | 2027-01-25 → 2027-04-04 | Argumentar, matizar y conectar ideas complejas al hablar y escribir | Argumentación escrita y oral, conectores, registro formal | sáb 2027-04-03 |
| 3 · Precisión y registro | 2027-04-05 → 2027-06-13 | Implícitos, humor, ironía, cambio de registro | Lo mismo | sáb 2027-06-12 |

## Pruebas del autodiagnóstico (EN y FR)

| Prueba | Criterio aprobado |
|---|---|
| Grabarte 3 min sobre un tema abstracto, sin preparar | Ninguna pausa de más de 3 s buscando palabras; ideas conectadas |
| Episodio de serie o podcast nativo sin subtítulos | Comprensión estimada ≥85 % y captar al menos un chiste o ironía |
| Resumir un artículo de opinión largo | Tesis, argumentos y postura implícita del autor |
| Ensayo de 400 palabras corregido por IA | ≤3 errores cada 100 palabras y estructura clara |

## Métricas semanales (se anotan en el repaso del sábado)

| Métrica | Idioma | Meta |
|---|---|---|
| Días con Anki completo | EN+FR | 6 |
| Minutos de escucha extensiva | EN · FR | 60 c/u |
| Minutos de lectura extensiva | EN · FR | 60 c/u |
| Textos escritos y corregidos | EN · FR | 1 c/u |
| Minutos de conversación | EN · FR | 20 c/u |
| Errores nuevos al cuaderno | EN+FR | 10 |

La app todavía no guarda estas métricas; por ahora se anotan aparte.

## Recursos

Precios aproximados en USD, **verificar** antes de pagar.

**Inglés**
- **Gramática y vocabulario:** *Advanced Grammar in Use* (Hewings); *English Collocations in Use: Advanced* y *English Vocabulary in Use: Advanced* (McCarthy & O'Dell).
- **Lectura:** *Educated* (Westover); *Never Let Me Go* y *The Remains of the Day* (Ishiguro); *Thinking, Fast and Slow* (Kahneman); The Guardian *The long read*, *Aeon* y *The Atlantic*.
- **Escucha:** *Luke's English Podcast*, *Hidden Brain*, *Freakonomics Radio*, *99% Invisible*, *In Our Time*; *Rachel's English* (shadowing).
- **Series:** *The West Wing*, *Succession*.
- **Herramientas:** YouGlish, Cambridge Dictionary, LanguageTool.

**Francés**
- **Gramática y vocabulario:** *Grammaire progressive du français – perfectionnement* (CLE, verificar edición); *Bescherelle*.
- **Estilo y lectura:** *Exercices de style* (Queneau); *L'Élégance du hérisson*, *La Vie devant soi*, *Chanson douce*, *Petite Poucette*, *L'Étranger*.
- **Prensa:** *Le Monde* (Idées), franceinfo.
- **Escucha:** *Les Pieds sur terre*, *Les Chemins de la philosophie*, *Affaires sensibles*, *Transfert*; *HugoDécrypte*, *Monsieur Phi*, *Nota Bene*.
- **Series:** *Le Bureau des légendes*, *Dix pour cent*.
- **Herramientas:** CNRTL, Reverso Context, Antidote, TV5Monde Apprendre.

**Para conversar:** la práctica base es por voz con IA. Con personas: italki o Preply (pago) y Tandem o HelloTalk (gratis), y lo marcas como «Conversación con humano».
