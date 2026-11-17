"""
Temario del plan C1 de inglés y francés (v2) — fuente única del «qué toca».

3 fases de 10 semanas desde el lunes 2026-11-16 (docs/idiomas_c1_plan.md).
Cada semana y cada idioma tiene:
  · tema         de qué va la semana;
  · foco         gramática o léxico que se trabaja (fijo);
  · material     input sugerido para la Sesión A (editable: el usuario puede
                 cambiarlo, se guarda en lang_temario_material);
  · conversacion tema de la conversación por voz con IA (Sesión B, fijo);
  · writing      prompt del texto de 250–400 palabras (Sesión B, fijo; es
                 también el prompt del journal de Idiomas esa semana).

El material se sugiere por fuente y búsqueda («busca un episodio sobre…»),
no por episodio exacto, para no inventar títulos: las fuentes existen; lo
concreto lo eliges tú (y puedes cambiarlo en Cosmopolitismo › Plan).

Días (los de Acta): Inglés A lun · Francés A mar · Inglés B jue · Francés B
vie · Repaso sáb (Autodiagnóstico C1 en los sábados de checkpoint). Escucha
EN + lectura FR lun/mié/jue; escucha FR + lectura EN mar/vie/dom. Anki diario.
"""
from datetime import date, timedelta

INICIO = date(2026, 11, 16)
SEMANAS = 30

FASES = [
    {"fase": 1, "nombre": "Cimientos C1", "semanas": (1, 10),
     "foco_en": "Input denso (ensayos, podcasts largos) + phrasal verbs y collocations",
     "foco_fr": "Litote y figuras de estilo, léxico fino, concordance des temps, comprensión oral",
     "checkpoint": date(2027, 1, 23)},
    {"fase": 2, "nombre": "Output y argumentación", "semanas": (11, 20),
     "foco_en": "Argumentar, matizar y conectar ideas complejas al hablar y escribir",
     "foco_fr": "Argumentación escrita y oral, conectores y registro formal",
     "checkpoint": date(2027, 4, 3)},
    {"fase": 3, "nombre": "Precisión y registro", "semanas": (21, 30),
     "foco_en": "Implícitos, humor, ironía y cambio de registro",
     "foco_fr": "Implícitos, humor, ironía y cambio de registro",
     "checkpoint": date(2027, 6, 12)},
]

# Pruebas del autodiagnóstico (cada checkpoint, en los dos idiomas)
PRUEBAS = [
    ("Grabarte 3 min sobre un tema abstracto, sin preparar",
     "Ninguna pausa de más de 3 s buscando palabras; ideas conectadas"),
    ("Episodio de serie o podcast nativo sin subtítulos",
     "Comprensión estimada ≥85 % y captar al menos un chiste o ironía"),
    ("Resumir un artículo de opinión largo",
     "Tesis, argumentos y postura implícita del autor"),
    ("Ensayo de 400 palabras corregido por IA",
     "≤3 errores cada 100 palabras y estructura clara"),
]

# Bloques de cada sesión (minutos) y su versión mínima
SESIONES = {
    "A": {"titulo": "Sesión A · input", "min": 60, "minima": 20,
          "minima_txt": "solo el input intensivo",
          "bloques": [(25, "Input intensivo con transcripción (el material de la semana)"),
                      (15, "Shadowing de 2–3 min del mismo audio"),
                      (20, "Foco de la semana: gramática o léxico, y tarjetas a Anki")]},
    "B": {"titulo": "Sesión B · output", "min": 60, "minima": 20,
          "minima_txt": "solo la conversación con IA",
          "bloques": [(20, "Conversación por voz con IA sobre el tema de la semana"),
                      (25, "Writing de 250–400 palabras con el prompt de la semana, corregido por IA (o en el journal)"),
                      (15, "Cuaderno de errores: pasar los errores a Anki")]},
    "R": {"titulo": "Repaso semanal EN+FR", "min": 60, "minima": 25,
          "minima_txt": "cuaderno de errores y métricas",
          "bloques": [(20, "Cuaderno de errores EN+FR de la semana"),
                      (10, "Registrar las métricas de la semana"),
                      (30, "Episodio o película sin subtítulos (alterna el idioma cada semana)")]},
}

# Semanas ligeras (fiestas): vale la versión mínima sin culpa
LIGERAS = {6: "Semana de fiestas: si no da el tiempo, haz la versión mínima.",
           7: "Semana de fiestas: si no da el tiempo, haz la versión mínima."}

_CHECKPOINT = {
    "tema": "Checkpoint de fase",
    "foco": "Consolidación: repasa los focos de la fase y tu top 10 de errores del cuaderno",
    "material": "Un episodio largo nativo que no hayas oído (prueba de comprensión sin subtítulos)",
    "conversacion": "Monólogo de 3 min sin preparar sobre un tema abstracto (grábalo: es la prueba oral)",
    "writing": "Ensayo de 400 palabras sobre un tema abstracto, sin herramientas (es la prueba escrita)",
}


def _s(tema, foco, material, conversacion, writing):
    return {"tema": tema, "foco": foco, "material": material, "conversacion": conversacion, "writing": writing}


TEMARIO = {
    "en": [
        # ── Fase 1 · Cimientos C1 ──────────────────────────────────────────
        _s("Trabajo y productividad",
           "Phrasal verbs de trabajo: take on, follow up, fall behind, carry out, wind down",
           "Hidden Brain (NPR): busca un episodio sobre hábitos o productividad",
           "Is productivity culture making us better or just busier?",
           "Describe a change in how you work that made the biggest difference, and explain why it worked."),
        _s("Tecnología y atención",
           "Collocations con make / do / take: make a point, take into account, do justice to",
           "The Guardian · The long read: busca «attention» o «smartphones»",
           "Should social media be regulated like tobacco?",
           "Argue for or against banning smartphones in schools."),
        _s("Ciudades",
           "Phrasal verbs de cambio: phase out, scale up, turn around, bring about",
           "99% Invisible: un episodio sobre diseño urbano",
           "What makes a city genuinely livable?",
           "Describe your city's biggest problem and propose a realistic solution."),
        _s("Ciencia y evidencia",
           "Collocations de evidencia: strong evidence, draw a conclusion, raise concerns, pose a risk",
           "Freakonomics Radio: un episodio sobre salud o datos",
           "Is it rational to trust experts when they disagree?",
           "Summarise an article you read this week and evaluate how strong its evidence is."),
        _s("Dinero",
           "Phrasal verbs de dinero: cut back, splash out, run up, pay off, set aside",
           "Planet Money (NPR): un episodio sobre deuda o ahorro",
           "Is financial literacy a personal or a public responsibility?",
           "Write a letter to your younger self with advice about money."),
        _s("Tradiciones",
           "Idioms de reunión y recuerdo: get together, catch up, look back on, drift apart",
           "The Royal Institution Christmas Lectures (YouTube), o una película clásica de Navidad sin subtítulos",
           "How do traditions survive in a globalised world?",
           "Describe a family tradition and what it says about the people who keep it."),
        _s("Metas y cambio personal",
           "Futuro avanzado: be bound to, be on the verge of, be due to, be about to",
           "TED: «Inside the mind of a master procrastinator» (Tim Urban)",
           "Why do most New Year's resolutions fail?",
           "Your plan for 2027: goals, likely obstacles and what you will do when they appear."),
        _s("Educación",
           "Collocations académicas: conduct research, a body of evidence, shed light on, fall short of",
           "Aeon: un ensayo sobre educación o aprendizaje",
           "Is a university degree still worth it?",
           "Compare two education systems you know: what each gets right and wrong."),
        _s("Medio ambiente",
           "Phrasal verbs de problemas: run out of, use up, cut down on, wipe out",
           "The Guardian o The Economist: busca «climate adaptation»",
           "Individual action or systemic change: which matters more for the climate?",
           "Problem–solution essay on one environmental issue in your country."),
        dict(_CHECKPOINT),
        # ── Fase 2 · Output y argumentación ───────────────────────────────
        _s("Verdad y desinformación",
           "Hedging: it could be argued, arguably, to some extent, there is reason to believe",
           "The Ezra Klein Show (NYT): busca un episodio sobre desinformación",
           "Should free speech have limits online?",
           "Opinion piece on misinformation using at least five hedging expressions."),
        _s("Trabajo remoto",
           "Contraste y concesión: whereas, albeit, notwithstanding, even so, that said",
           "The Atlantic o The Guardian: busca «remote work»",
           "Defend the opposite of your real opinion on remote work.",
           "For-and-against essay on remote work with a clear conclusion."),
        _s("Identidad y pertenencia",
           "Cleft sentences y énfasis: What I find…, It is X that…, All I want is…",
           "This American Life o BBC The Documentary: busca «migration» o «belonging»",
           "What does it mean to belong somewhere?",
           "Personal essay: a place where you felt you belonged, and why."),
        _s("Decisiones",
           "Condicionales mixtos e inversión: Had I known…, Should you…, Were it not for…",
           "Hidden Brain: un episodio sobre decisiones o arrepentimiento",
           "Talk about a decision you would make differently today.",
           "Reflective essay on a turning point, using mixed conditionals."),
        _s("Desigualdad",
           "Causa y efecto: stem from, give rise to, contribute to, trigger, result in",
           "Freakonomics Radio o The Guardian long read: busca «inequality»",
           "Is some inequality inevitable — or even useful?",
           "Cause-and-effect essay on one form of inequality."),
        _s("Tu trabajo, en formal",
           "Registro formal escrito: propuesta, correo profesional, fórmulas de cortesía",
           "Un informe, blog técnico o caso de estudio de tu área profesional",
           "Role-play: present a project to a senior stakeholder and handle objections.",
           "Formal proposal email: a change you would make in your workplace."),
        _s("IA y empleo",
           "Matizar opiniones: I'm inclined to think, I'd go as far as to say, that's not to say",
           "Hard Fork (NYT): un episodio sobre IA y trabajo",
           "Will AI make work more meaningful or less?",
           "Balanced argument on AI and jobs, ending with your nuanced position."),
        _s("Salud mental",
           "Reporting verbs: claim, concede, dismiss, acknowledge, contend",
           "Aeon o The Guardian: un ensayo sobre salud mental",
           "Summarise and critique an argument you disagree with.",
           "Summary of an article using at least six different reporting verbs."),
        _s("Ciencia y sociedad",
           "Nominalización y estilo académico",
           "In Our Time (BBC Radio 4): un episodio de ciencia",
           "Explain a complex idea from your field to a non-expert in 3 minutes.",
           "Rewrite a paragraph of your own in academic style, then compare both versions."),
        dict(_CHECKPOINT),
        # ── Fase 3 · Precisión y registro ─────────────────────────────────
        _s("Ironía británica",
           "Understatement e ironía: not bad at all, a bit of a problem, I'm not entirely convinced",
           "The Office (UK) o Yes, Minister: un episodio sin subtítulos",
           "Explain a joke or ironic scene you watched this week.",
           "Rewrite a formal announcement in an ironic, understated tone."),
        _s("Registro informal",
           "Phrasal verbs informales y slang moderado",
           "Ted Lasso (Apple TV+): un episodio sin subtítulos",
           "Informal role-play: making plans with a close friend.",
           "The same message in three registers: to a friend, to a colleague, to a client."),
        _s("Leer entre líneas",
           "Inferencias: lo que se implica en una entrevista",
           "Fresh Air (NPR): una entrevista larga",
           "What did the interviewee imply without saying it?",
           "Analyse the subtext of a conversation or interview you heard."),
        _s("Humor",
           "Juegos de palabras (puns) y timing cómico",
           "Un especial de stand-up en inglés (Netflix o YouTube), sin subtítulos",
           "Explain why something is funny — and why it may not translate.",
           "Write a humorous anecdote from your own life."),
        _s("Negociación y cortesía",
           "Estrategias de cortesía: softeners, indirect requests, polite refusals",
           "Succession: un episodio (poder y subtexto)",
           "Role-play: negotiate a deadline or a raise.",
           "Decline a request politely in an email without damaging the relationship."),
        _s("Retórica política",
           "Metáforas, tríadas y otros recursos retóricos",
           "Un discurso político célebre en video (por ejemplo, el de Obama en la convención demócrata de 2004)",
           "Analyse the rhetoric of a speech you watched.",
           "Rhetorical analysis of a speech: aims, devices, effect on the audience."),
        _s("Acentos y variedades",
           "Comprensión de acentos: escocés, irlandés, australiano",
           "Derry Girls o Line of Duty: un episodio sin subtítulos",
           "Cultural stereotypes: useful shortcuts or lazy thinking?",
           "Compare two English-speaking cultures you know."),
        _s("Narrador poco fiable",
           "Lo implícito en la ficción: narrador poco fiable, ironía dramática",
           "The Remains of the Day (Kazuo Ishiguro): un capítulo",
           "What does Stevens refuse to say, and why?",
           "Character analysis based on what the narrator leaves unsaid."),
        _s("Debate",
           "Integración: argumentar, conceder y refutar en tiempo real",
           "Intelligence Squared (YouTube): un debate completo",
           "10-minute debate defending the side you disagree with.",
           "Rebuttal essay answering the strongest argument against your view."),
        dict(_CHECKPOINT),
    ],
    "fr": [
        # ── Fase 1 · Cimientos C1 ──────────────────────────────────────────
        _s("L'art de dire sans dire",
           "Litote y euphémisme: «ce n'est pas mal», «il n'est pas bête», «va, je ne te hais point»",
           "Le Monde · Idées: una tribune; subraya cada litote que encuentres",
           "Décris quelque chose que tu aimes et quelque chose que tu détestes, seulement avec des litotes.",
           "Critique d'un film ou d'un livre en utilisant au moins cinq litotes."),
        _s("Souvenirs",
           "Concordance des temps en el pasado: imparfait, plus-que-parfait, conditionnel passé",
           "Les Pieds sur terre (France Culture): un testimonio",
           "Raconte un souvenir d'enfance précis et ce que tu en as compris plus tard.",
           "Récit au passé d'un souvenir, avec au moins trois phrases au discours indirect."),
        _s("L'actualité rapportée",
           "Discours indirect y concordance: il a dit qu'il viendrait, qu'il était venu…",
           "franceinfo: un reportaje o una entrevista larga",
           "Rapporte ce qu'a dit une personne interviewée, sans la citer directement.",
           "Compte rendu d'une interview au discours indirect."),
        _s("Le travail",
           "Léxico fino: sustituir dire / faire / chose (évoquer, souligner, mettre en œuvre, élément)",
           "Le Monde · Économie o Emploi: un artículo",
           "Décris ton travail sans utiliser «faire», «dire» ni «chose».",
           "Courriel professionnel présentant un projet, sans verbes passe-partout."),
        _s("Exercices de style",
           "Figuras: métaphore, hyperbole, antithèse, oxymore",
           "Exercices de style (Raymond Queneau): lee diez de los estilos",
           "Raconte la même anecdote dans trois styles différents.",
           "Ta propre anecdote réécrite en trois styles (soutenu, familier, poétique)."),
        _s("Les fêtes",
           "Subjonctif tras sentimiento y duda: je souhaite que, je doute que, bien que",
           "Película: Joyeux Noël (Christian Carion, 2005), sin subtítulos",
           "Les traditions de fin d'année : chez toi et en France.",
           "Lettre de vœux à quelqu'un que tu n'as pas vu depuis longtemps (avec le subjonctif)."),
        _s("Bilan de l'année",
           "Expressions idiomatiques: avoir le cafard, poser un lapin, tomber des nues",
           "HugoDécrypte (YouTube): un video de resumen del año",
           "Ton bilan de l'année et ce que tu veux changer.",
           "Résolutions pour 2027, avec les obstacles prévisibles et comment les éviter."),
        _s("L'école",
           "Connecteurs C1: en revanche, néanmoins, d'autant plus que, quand bien même",
           "France Culture: un debate sobre la escuela",
           "Compare le système éducatif français et celui de ton pays.",
           "Comparaison argumentée de deux systèmes éducatifs."),
        _s("Le français parlé",
           "Comprensión rápida: registro familiar y verlan básico",
           "Dix pour cent (Call My Agent!): un episodio sin subtítulos",
           "Décris les personnages de l'épisode et leurs relations.",
           "Résumé de l'épisode en registre standard."),
        dict(_CHECKPOINT),
        # ── Fase 2 · Output y argumentación ───────────────────────────────
        _s("Liberté et sécurité",
           "Estructura de la dissertation: thèse, antithèse, synthèse",
           "Le Monde · Idées: una tribune sobre libertades",
           "Faut-il sacrifier un peu de liberté pour plus de sécurité ?",
           "Plan dialectique et introduction complète sur ce sujet."),
        _s("Le télétravail",
           "Concession: bien que + subjonctif, certes… mais, il n'en demeure pas moins",
           "Libération o Le Monde: un artículo sobre télétravail",
           "Défends l'opinion contraire à la tienne sur le télétravail.",
           "Texte argumentatif avec au moins quatre structures concessives."),
        _s("L'écologie",
           "Nominalisation et style soutenu",
           "Reporterre (reporterre.net): un artículo",
           "La transition écologique : qui doit payer ?",
           "Réécris un paragraphe de ton texte en style nominal soutenu."),
        _s("Les choix de vie",
           "Hipótesis: si + plus-que-parfait, au cas où, pour peu que, à supposer que",
           "Les Pieds sur terre: un testimonio sobre un cambio de vida",
           "Et si tu avais choisi un autre métier ?",
           "Uchronie personnelle : ta vie si un choix avait été différent."),
        _s("Les inégalités",
           "Cause et conséquence: en raison de, faute de, si bien que, d'où",
           "Entendez-vous l'éco ? (France Culture): un episodio",
           "Quelles sont les causes principales des inégalités ?",
           "Essai cause–conséquence sur une inégalité précise."),
        _s("Le registre formel",
           "Carta formal: formules d'appel et de politesse, structure",
           "Modelos de cartas formales (lettre de réclamation, lettre de motivation)",
           "Jeu de rôle : régler un problème avec une administration.",
           "Lettre de réclamation formelle."),
        _s("L'intelligence artificielle",
           "Nuancer: il semblerait que, dans une certaine mesure, force est de constater",
           "France Inter o France Culture: un programa sobre IA",
           "L'IA va-t-elle rendre le travail plus intéressant ?",
           "Tribune nuancée sur l'IA et le travail."),
        _s("Les médias",
           "Verbes introducteurs: affirmer, prétendre, admettre, réfuter, souligner",
           "L'Esprit public (France Culture): un debate",
           "Fais la synthèse d'un débat que tu as écouté.",
           "Synthèse de documents avec au moins six verbes introducteurs."),
        _s("L'exposé",
           "Exposé oral estructurado: annonce du plan, transitions, conclusion",
           "Monsieur Phi (YouTube): un video (fíjate en la estructura)",
           "Exposé de 5 minutes sur un sujet de ton travail.",
           "Rédige ton exposé, avec les transitions."),
        dict(_CHECKPOINT),
        # ── Fase 3 · Precisión y registro ─────────────────────────────────
        _s("L'ironie",
           "Ironie et antiphrase",
           "Película: Le Dîner de cons (Francis Veber, 1998), sin subtítulos",
           "Explique une scène ironique du film.",
           "Texte ironique sur une situation du quotidien."),
        _s("Le registre familier",
           "Argot, verlan y abreviaciones",
           "Película: La Haine (Mathieu Kassovitz, 1995)",
           "Traduis des répliques du familier au soutenu, à voix haute.",
           "Le même message en trois registres : familier, courant, soutenu."),
        _s("Les sous-entendus",
           "Lo implícito en las entrevistas",
           "Boomerang (France Inter): una entrevista",
           "Qu'est-ce que l'invité a laissé entendre sans le dire ?",
           "Analyse des sous-entendus d'une interview."),
        _s("L'humour",
           "Jeux de mots et humour",
           "Una crónica de humor de France Inter o un espectáculo de stand-up en francés",
           "Explique une blague et pourquoi elle est difficile à traduire.",
           "Anecdote humoristique de ta vie."),
        _s("La négociation",
           "Politesse et atténuation: conditionnel de politesse, je me permets de…",
           "Le Bureau des légendes: un episodio",
           "Jeu de rôle : négocier un délai ou une augmentation.",
           "Refuser poliment une demande par courriel."),
        _s("La rhétorique",
           "Rétorica política: anaphore, gradation, prétérition",
           "Discurso de Simone Veil en la Asamblea Nacional (1974) sobre la ley del aborto (video o texto)",
           "Analyse la rhétorique d'un discours.",
           "Analyse rhétorique d'un discours."),
        _s("La francophonie",
           "Variedades: francés de Quebec, de Bélgica y de África",
           "Película: C.R.A.Z.Y. (Jean-Marc Vallée, 2005), o reportajes francófonos de TV5Monde",
           "Qu'est-ce que la francophonie aujourd'hui ?",
           "Comparaison entre deux pays francophones."),
        _s("L'Étranger",
           "Lo implícito y el estilo blanco de Camus",
           "L'Étranger (Albert Camus): un capítulo",
           "Pourquoi Meursault ne dit-il presque rien de ce qu'il ressent ?",
           "Analyse d'un passage de L'Étranger."),
        _s("Le débat",
           "Integración: argumentar, conceder y refutar en tiempo real",
           "Répliques (France Culture): un debate",
           "Débat de 10 minutes en défendant la position contraire à la tienne.",
           "Réfutation de l'argument le plus fort contre ta position."),
        dict(_CHECKPOINT),
    ],
}
assert all(len(v) == SEMANAS for v in TEMARIO.values())

IDIOMA = {"en": "Inglés", "fr": "Francés"}
# Día de la semana (0 = lunes) → qué toca
_SESION_DEL_DIA = {0: ("en", "A"), 1: ("fr", "A"), 3: ("en", "B"), 4: ("fr", "B"), 5: (None, "R")}
_ESCUCHA = {0: "en", 2: "en", 3: "en", 1: "fr", 4: "fr", 6: "fr"}       # la lectura es el otro idioma
# Ancla de Acta de cada sesión
ANCLAS = {"ancla_ingles": ("en", "A"), "ancla_ingles_b": ("en", "B"),
          "ancla_frances": ("fr", "A"), "ancla_frances_b": ("fr", "B"),
          "ancla_repaso_idiomas": (None, "R"), "autodiagnostico_c1": (None, "C")}


def semana_de(d=None):
    """1..30 durante el plan; 0 antes de empezar; 31 después de terminar."""
    from utils import today_date
    d = d or today_date()
    if d < INICIO:
        return 0
    return min((d - INICIO).days // 7 + 1, SEMANAS + 1)


def fase_de(semana):
    for f in FASES:
        if f["semanas"][0] <= semana <= f["semanas"][1]:
            return f
    return FASES[0] if semana < 1 else FASES[-1]


def fecha_de(semana, dia=0):
    """Fecha del día `dia` (0 = lunes) de la semana `semana`."""
    return INICIO + timedelta(weeks=semana - 1, days=dia)


def es_checkpoint(d):
    return any(f["checkpoint"] == d for f in FASES)


def overrides(db):
    """{(lang, semana): material} que el usuario cambió."""
    try:
        return {(r["lang"], r["semana"]): r["material"]
                for r in db.execute("SELECT lang, semana, material FROM lang_temario_material")}
    except Exception:
        return {}


def semana(lang, n, ovr=None):
    """La entrada de la semana `n` (1..30) para `lang`, con su material efectivo."""
    n = max(1, min(n, SEMANAS))
    e = dict(TEMARIO[lang][n - 1])
    e["semana"] = n
    e["material_sugerido"] = e["material"]
    if ovr and (lang, n) in ovr:
        e["material"] = ovr[(lang, n)]
        e["material_propio"] = True
    return e


def hoy(d=None, ovr=None):
    """Lo que toca el día `d`: la sesión (si hay), escucha, lectura y Anki."""
    from utils import today_date
    d = d or today_date()
    n = semana_de(d)
    out = {"fecha": d.isoformat(), "semana": n, "total": SEMANAS, "antes": n == 0, "terminado": n > SEMANAS}
    if out["antes"] or out["terminado"]:
        return out
    f = fase_de(n)
    out.update(fase=f["fase"], fase_nombre=f["nombre"], ligera=LIGERAS.get(n))
    wd = d.weekday()
    lang_s, tipo = _SESION_DEL_DIA.get(wd, (None, None))
    if tipo == "R" and es_checkpoint(d):
        tipo = "C"
    if tipo in ("A", "B"):
        sem = semana(lang_s, n, ovr)
        out["sesion"] = {"tipo": tipo, "lang": lang_s, "idioma": IDIOMA[lang_s], **SESIONES[tipo],
                         "titulo": f"{IDIOMA[lang_s]} · {SESIONES[tipo]['titulo']}", "contenido": sem}
    elif tipo == "R":
        out["sesion"] = {"tipo": "R", **SESIONES["R"],
                         "idioma_peli": "Inglés" if n % 2 else "Francés"}
    elif tipo == "C":
        out["sesion"] = {"tipo": "C", "titulo": f"Autodiagnóstico C1 · checkpoint de la fase {f['fase']}",
                         "min": 90, "pruebas": PRUEBAS}
    esc = _ESCUCHA.get(wd)
    if esc:
        lec = "fr" if esc == "en" else "en"
        out["escucha"] = {"lang": esc, "idioma": IDIOMA[esc], "min": 20}
        out["lectura"] = {"lang": lec, "idioma": IDIOMA[lec], "min": 20}
    return out


def para_ancla(key, d=None, ovr=None):
    """Una línea para la tarjeta del ancla en Acta («Semana 1 · foco…»), o None."""
    if key not in ANCLAS:
        return None
    n = semana_de(d)
    if not 1 <= n <= SEMANAS:
        return None
    lang, tipo = ANCLAS[key]
    if tipo == "A":
        return f"Semana {n} · {semana(lang, n, ovr)['foco']}"
    if tipo == "B":
        return f"Semana {n} · {semana(lang, n, ovr)['tema']}: conversación y writing"
    if tipo == "C":
        return "Pruebas oral, escucha, lectura y ensayo (EN + FR)"
    return f"Semana {n} · cuaderno de errores, métricas y una película"
