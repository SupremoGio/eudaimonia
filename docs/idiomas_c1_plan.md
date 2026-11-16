# Plan B2 → C1 · Inglés y francés

Pilar Cosmopolitismo. Empieza el 2026-11-16. Lo aplica la migración `idiomas_c1_plan_2026_11`, en `gio_v3/database.py`.

- **Meta:** C1 funcional en inglés en ~44 semanas y en francés en ~36 semanas, sin exámenes oficiales.
- **Carga:** 5 h por semana:
  - 2 sesiones de 60 min por idioma;
  - 1 repaso de 60 min el sábado;
  - micro-hábitos opcionales.
- **Principio:** input comprensible en volumen, más output forzado con corrección real, más repetición espaciada de lo que se corrige.

## En la app

| Hábito | Clave | Día | Tipo | Recompensa |
|---|---|---|---|---|
| Inglés · Sesión A (input: escucha + lectura) | `ancla_ingles` | lunes | ancla | la del ancla de inglés (6 XP · 2 EC) |
| Inglés · Sesión B (output con corrección) | `ancla_ingles_b` | jueves | ancla | igual |
| Francés · Sesión A (input: escucha + lectura) | `ancla_frances` | martes | ancla | la del ancla de francés (6 XP · 2 EC) |
| Francés · Sesión B (output con corrección) | `ancla_frances_b` | viernes | ancla | igual |
| Repaso semanal EN+FR (Anki, errores, reescritura) | `ancla_repaso_idiomas` | sábado, tarde | ancla | igual que inglés |
| Anki EN+FR · 10 min *(opcional)* | `anki_idiomas` | miércoles y domingo | touch | 1 XP |
| Escucha extensiva EN/FR · 20 min *(opcional)* | `podcast_idiomas` (el «Podcast en idiomas» de siempre) | diario | touch | 1 XP |
| Lectura extensiva EN/FR · 15 min *(opcional)* | `lectura_idiomas` | diario, noche | touch | 1 XP |
| Writing journal | `idiomas_journal` | se registra solo al escribir en Idiomas › Journal (sesión B) | touch | 5 XP · 1 EC |
| Conversación real 10 min+ | `conversacion` | charlas fuera de las sesiones | touch | 5 XP · 2 EC |

- **Días:** son los que ya tenía cada ancla. La key existente se queda con el primer día (sesión A y su historial) y la nueva `_b` con el resto.
- **Certificación:** «Test certificación (DALF/IELTS)» queda desactivado, porque el plan no prepara exámenes.
- **Hitos:** son ocasionales de una sola vez. Están en Acta › «Ocasionales y hitos», y al marcarlos dan su XP y desaparecen.
- **Checkpoints:** son recordatorios con fecha en Perfil › Recordatorios. Caen en sábado, el día del repaso.

| Hito | XP |
|---|---|
| Monólogo de 3 min sin bloquearme (EN · FR) | 25 c/u |
| 30 min de conversación sin bloquearme (EN · FR) | 50 c/u |
| Primera novela completa sin diccionario (EN · FR) | 40 c/u |
| Película sin subtítulos, ≤10 % perdido (EN · FR) | 30 c/u |
| Ensayo de 600 palabras con ≤1 error cada 100 (EN) | 40 |
| Concordance des temps: 3 textos sin error (FR) | 30 |
| Cazador de litotes: ≥4 figuras en una página (FR) | 20 |
| 100 días de Anki (EN · FR) | 30 c/u |
| C1 funcional: checklist completa (EN · FR) | 100 c/u |

## Calendario semanal

| Día | Bloque | Min |
|---|---|---|
| Lun | Inglés · Sesión A (tarde) | 60 |
| Mar | Francés · Sesión A (tarde) | 60 |
| Mié | Anki 10 min *(opcional)* | 10 |
| Jue | Inglés · Sesión B (tarde, clase con tutor) | 60 |
| Vie | Francés · Sesión B (tarde, clase con tutor) | 60 |
| Sáb | Repaso EN+FR (tarde; el baile va de noche) | 60 |
| Dom | Anki 10 min *(opcional)* | 10 |

**Las 5 destrezas cada semana, en los dos idiomas:**
- **Sesión A:** comprensión oral (CO) y comprensión escrita (CE).
- **Sesión B:** expresión oral (EO), interacción (IO) y expresión escrita (EE).

## Estructura de las sesiones

**Sesión A · Input (60 min)**

| Min | Bloque | Objetivo medible |
|---|---|---|
| 0–5 | Shadowing de 1 min del audio del día | 3 repeticiones |
| 5–30 | Escucha activa: primera pasada sin transcripción y segunda solo en los tramos difíciles | 5 ideas clave anotadas |
| 30–50 | Lectura de un artículo de opinión o capítulo, más un resumen oral de 1 min | Tesis en 3 frases |
| 50–60 | Minado de 8–10 colocaciones a Anki (siempre en contexto) | ≥8 tarjetas |

**Sesión B · Output con corrección (60 min)**

| Min | Bloque | Objetivo medible |
|---|---|---|
| 0–10 | Monólogo grabado de 3 min sobre el tema de la sesión A; escúchalo y anota 2 errores | 1 grabación y 2 errores al registro |
| 10–40 | Tutor (o intercambio): debate del texto de la sesión A, con las correcciones por chat | ≥5 correcciones anotadas |
| 40–60 | Escritura de 250–350 palabras (600 en la fase 4) en Idiomas › Journal; luego el prompt de IA y LanguageTool o Antidote | 1 texto corregido |

**Repaso del sábado (60 min)**

| Min | Bloque |
|---|---|
| 0–20 | Anki EN y FR al día |
| 20–40 | Registro de errores, 10 min por idioma: marca los repetidos y elige el foco de la semana |
| 40–50 | Reescribe un texto aplicando las correcciones (alterna EN y FR) |
| 50–60 | Prepara la semana y anota las métricas |

## El ciclo de corrección

**Pasos:**
1. Produces: monólogo o texto.
2. Te corrigen: el tutor en vivo, o la IA más un corrector automático.
3. Lo anotas en el registro de errores: error → forma correcta → regla.
4. Haces una tarjeta de Anki con la frase entera.
5. Lo reutilizas a propósito en la siguiente sesión B.

Si un error se repite 3 veces, pasa a ser el foco de la semana.

**Prompt de corrección con IA:**
> «Actúa como corrector nativo de [inglés/francés] de nivel C2. Devuélveme: 1) mi texto corregido; 2) una tabla error → corrección → regla, clasificada en gramática, léxico, colocación o registro; 3) 3 reformulaciones más idiomáticas de mis frases más débiles; 4) una nota de 1 a 5 sobre coherencia, riqueza léxica, precisión y registro. No reescribas mi estilo si es correcto.»

La IA a veces se equivoca o corrige de más. Verifícala siempre con LanguageTool (EN y FR) o Antidote (FR), y dale al tutor 1 texto al mes para validar.

## Checklist C1 (línea base y cierre de cada fase)

| # | Prueba | Umbral C1 |
|---|---|---|
| CO1 | Episodio largo sin transcripción (EN: *In Our Time* · FR: *Les Chemins de la philosophie*). 8 ideas clave, luego comparas con la transcripción | 7 de 8 |
| CO2 | 10 min de película o serie sin subtítulos; luego los vuelves a ver con subtítulos y cuentas las líneas perdidas | ≤10 % |
| CO3 | Ironías, dobles sentidos y emociones implícitas en esos 10 min | ≥3 |
| CE1 | Resumen en 120 palabras de un artículo de opinión de 1 500 palabras: tesis, argumentos y postura implícita | Tesis y postura correctas |
| CE2 | 20 páginas de novela sin diccionario | ≤1 palabra bloqueante por página |
| CE3 | Figuras de estilo e ironía en una página (FR: litote, euphémisme, antiphrase · EN: understatement, irony) | ≥4 |
| EO1 | 3 min grabado sobre un tema abstracto, sin guion, transcrito con dictado | Ver condiciones abajo |
| EO2 | Explicar un proceso de tu trabajo a alguien no experto, en 3 min | Intro → pasos → cierre, ≤1 reformulación fallida |
| IO1 | 30 min con tutor sobre un tema que él elige en el momento | ≥4/5 en fluidez, reparación y matices |
| IO2 | 10 min defendiendo la postura contraria a la tuya | Sin cambiar de idioma ni pausas de más de 3 s |
| EE1 | Ensayo de 600 palabras en 60 min, sin herramientas; lo corrige el tutor y el corrector | ≤1 error cada 100 palabras, estructura aprobada |
| EE2 | El mismo contenido en registro formal e informal | Registro correcto según el tutor |

Condiciones de EO1:
- ≤3 pausas de más de 2 s;
- ≥6 conectores distintos;
- ≤1 error cada 30 s.

## Fases

| Fase | EN | FR | Objetivo | Foco | Criterio de salida |
|---|---|---|---|---|---|
| 1 · Base y ciclo de corrección | sem. 1–10 | sem. 1–8 | ≥90 % de sesiones hechas, ≥40 errores registrados, Anki al día | EO, IO, CO con ritmo medio | EO1 ≤5 pausas; CO2 ≤20 %; IO1 ≥3/5 |
| 2 · Precisión y léxico | 11–20 | 9–18 | 300 colocaciones; errores repetidos −50 % | EE, CE, registro formal | EE1 ≤2 errores cada 100 palabras; CE1 correcto; EO1 ≥5 conectores |
| 3 · Lo implícito y la espontaneidad | 21–32 | 19–28 | Ritmo nativo sin subtítulos; debate de 10 min | CO (ironía, humor), IO; FR: figuras de estilo y concordance des temps | CO2 ≤12 %; CO3 ≥3; IO2; CE3 ≥4 |
| 4 · Integración C1 | 33–44 | 29–36 | Checklist en verde | Novela completa, conversación de 30–45 min, dos registros | Checklist completa |

Si fallas un checkpoint, la fase se extiende 4 semanas solo en la destreza que falló.

**Fechas de los checkpoints** (recordatorios, en sábado):

| Fecha | Checkpoint |
|---|---|
| 2026-11-21 | Línea base EN y FR |
| 2027-01-09 | FR, fase 1 |
| 2027-01-23 | EN, fase 1 |
| 2027-03-20 | FR, fase 2 |
| 2027-04-03 | EN, fase 2 |
| 2027-05-29 | FR, fase 3 |
| 2027-06-26 | EN, fase 3 |
| 2027-07-24 | FR, fase 4 |
| 2027-09-18 | EN, fase 4 |

## Métricas semanales (por idioma; se anotan en el repaso del sábado)

| Métrica | Meta |
|---|---|
| Tarjetas de Anki repasadas | ≥150 |
| Minutos de escucha | ≥90 |
| Páginas leídas | ≥40 |
| Textos escritos y corregidos | ≥1 |
| Minutos de conversación | ≥30 |
| Monólogos grabados | ≥1 |
| Errores nuevos en el registro | ≥5 |

**Métricas mensuales:**
- porcentaje de errores repetidos sobre el total del registro (debe bajar);
- nota media de la IA en coherencia, riqueza léxica, precisión y registro;
- pausas del monólogo EO1.

**Reglas de ajuste:**
1. **Menos del 70 % de las métricas 2 semanas seguidas:** la sesión A baja a 45 min; la sesión B nunca se recorta.
2. **Los errores repetidos no bajan en 4 semanas:** 10 frases con esa estructura al inicio de la sesión B, corregidas por el tutor.
3. **Las pausas de EO1 no mejoran en 4 semanas:** 10 min de la lectura pasan a shadowing y monólogo.
4. **CO2 por encima del 15 %:** escucha extensiva a diario durante 4 semanas, con audio un escalón más fácil.
5. **El francés llega a C1 primero:** pasa a mantenimiento (A y B alternando semanas) y el tiempo libre va al inglés.

## Recursos

Precios aproximados en USD, **verificar** antes de pagar.

**Inglés**
- **Gramática y vocabulario:** *Advanced Grammar in Use* (Hewings, Cambridge, ~$40); *English Collocations in Use: Advanced* y *English Vocabulary in Use: Advanced* (McCarthy & O'Dell, ~$35 c/u).
- **Lectura:** *Educated* (Westover); *Never Let Me Go* y *The Remains of the Day* (Ishiguro); *Thinking, Fast and Slow* (Kahneman); The Guardian *The long read* y *Aeon* (gratis); *The Atlantic* (pago).
- **Escucha:** *Luke's English Podcast*, *Hidden Brain*, *Freakonomics Radio*, *99% Invisible* e *In Our Time* (gratis); YouTube: *Rachel's English* (shadowing), *Wendover Productions*, *Vox*.
- **Series:** *The West Wing*, *Succession*, *Line of Duty* (verificar disponibilidad).
- **Herramientas:** YouGlish, Cambridge Dictionary y Oxford Learner's Dictionaries (gratis); LanguageTool (gratis o ~$5 al mes).

**Francés**
- **Gramática y vocabulario:** *Grammaire progressive du français – niveau perfectionnement* (CLE International, ~$30, verificar edición); *Vocabulaire progressif du français – perfectionnement* (CLE, verificar que exista en ese nivel); *Bescherelle – La conjugaison pour tous* (Hatier).
- **Estilo y lectura:** *Exercices de style* (Queneau); *L'Élégance du hérisson* (Barbery); *La Vie devant soi* (Gary/Ajar); *Chanson douce* (Slimani); *Petite Poucette* (Serres); *L'Étranger* y *Le Mythe de Sisyphe* (Camus).
- **Prensa:** *Le Monde* (sección Idées) y *Le Monde diplomatique* (pago); franceinfo y France 24 (gratis).
- **Escucha:** *Les Pieds sur terre*, *Les Chemins de la philosophie* (France Culture); *Affaires sensibles* (France Inter); *Transfert* (Slate.fr); *Le Code a changé* (verificar si sigue activo); YouTube: *HugoDécrypte*, *Monsieur Phi*, *Nota Bene*, *Linguisticae* (verificar actividad).
- **Series y películas:** *Le Bureau des légendes*, *Dix pour cent*, *La Haine*, *Le Dîner de cons*.
- **Herramientas:** TV5Monde Apprendre, CNRTL, Le Robert y Reverso Context (gratis); Projet Voltaire; Antidote (~$70–130, el mejor corrector de francés).

**Para los dos idiomas**
- **Tutores:** italki o Preply, *community tutors*, 30 min por semana y por idioma (~$80–130 al mes por los dos; verificar precios).
- **Intercambio:** Tandem y HelloTalk (gratis).
- **Anki:** gratis en escritorio y Android; AnkiMobile en iOS (~$25, pago único).

Si el presupuesto aprieta, alterna una semana de tutor con una de intercambio.
