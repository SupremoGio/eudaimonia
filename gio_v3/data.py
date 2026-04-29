from datetime import date

# ── QUOTES ────────────────────────────────────────────────────────────────────
QUOTES = [
    {"text": "Discipline is the bridge between goals and accomplishment.", "author": "Jim Rohn"},
    {"text": "No man is free who is not master of himself.", "author": "Epictetus"},
    {"text": "The impediment to action advances action. What stands in the way becomes the way.", "author": "Marcus Aurelius"},
    {"text": "We suffer more in imagination than in reality.", "author": "Séneca"},
    {"text": "Hard times create strong men. Strong men create good times.", "author": "G. Michael Hopf"},
    {"text": "Waste no more time arguing what a good man should be. Be one.", "author": "Marcus Aurelius"},
    {"text": "Do not go where the path may lead; go where there is no path and leave a trail.", "author": "Emerson"},
    {"text": "El que tiene un por qué vivir puede soportar casi cualquier cómo.", "author": "Nietzsche"},
    {"text": "A man who conquers himself is greater than one who conquers a thousand men in battle.", "author": "Buda"},
    {"text": "Forged in fire. Built in silence. Delivered in results.", "author": "—"},
    {"text": "Your future self is watching you right now through your memories.", "author": "—"},
    {"text": "Gana en silencio. El ruido es para los que necesitan testigos.", "author": "—"},
    {"text": "Complacency is the enemy of excellence.", "author": "—"},
    {"text": "Every day you don't level up, someone else does.", "author": "—"},
    {"text": "You have power over your mind, not outside events. Realize this and you will find strength.", "author": "Marcus Aurelius"},
    {"text": "El dolor es inevitable, el sufrimiento es opcional.", "author": "Buda"},
    {"text": "Sufrir o no sufrir, eso siempre dependerá de ti.", "author": "Epicteto"},
    {"text": "The secret of getting ahead is getting started.", "author": "Mark Twain"},
    {"text": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucio"},
    {"text": "Success is not final, failure is not fatal: it is the courage to continue that counts.", "author": "Churchill"},
]

# ── WORD OF THE DAY ───────────────────────────────────────────────────────────
WORDS = [
    {"word": "Perspicacious", "phonetic": "/ˌpɜːspɪˈkeɪʃəs/", "meaning": "Having a ready insight; shrewd and discerning.", "example": "Her perspicacious analysis of the market impressed the entire board.", "french": "Perspicace"},
    {"word": "Equanimity",    "phonetic": "/ˌɛkwəˈnɪmɪti/",   "meaning": "Mental calmness and composure under pressure.",           "example": "He faced the crisis with remarkable equanimity.",                "french": "Sérénité"},
    {"word": "Indefatigable", "phonetic": "/ˌɪndɪˈfætɪɡəbl/", "meaning": "Persisting tirelessly; incapable of being fatigued.",     "example": "Her indefatigable dedication led to eventual success.",         "french": "Infatigable"},
    {"word": "Sagacious",     "phonetic": "/səˈɡeɪʃəs/",       "meaning": "Having keen mental discernment and good judgment.",       "example": "The sagacious investor knew when to hold and when to divest.", "french": "Sagace"},
    {"word": "Ephemeral",     "phonetic": "/ɪˈfɛmərəl/",       "meaning": "Lasting for a very short time; transitory.",             "example": "The ephemeral nature of trends makes long-term strategy essential.", "french": "Éphémère"},
    {"word": "Tenacious",     "phonetic": "/tɪˈneɪʃəs/",       "meaning": "Holding fast; persistent and determined.",               "example": "His tenacious pursuit of excellence set him apart.",            "french": "Tenace"},
    {"word": "Acumen",        "phonetic": "/ˈækjʊmɛn/",        "meaning": "The ability to make good judgments and quick decisions.", "example": "His financial acumen helped the startup reach profitability.", "french": "Perspicacité"},
    {"word": "Fortitude",     "phonetic": "/ˈfɔːtɪtjuːd/",     "meaning": "Courage in pain or adversity; mental strength.",         "example": "It takes fortitude to rebuild after a major setback.",          "french": "Fortitude"},
    {"word": "Resilience",    "phonetic": "/rɪˈzɪlɪəns/",      "meaning": "The capacity to recover quickly from difficulties.",      "example": "Resilience is the most important trait of high performers.",   "french": "Résilience"},
    {"word": "Audacious",     "phonetic": "/ɔːˈdeɪʃəs/",       "meaning": "Showing willingness to take bold risks; daring.",        "example": "The audacious pivot changed the company's trajectory entirely.", "french": "Audacieux"},
    {"word": "Meticulous",    "phonetic": "/mɪˈtɪkjʊləs/",     "meaning": "Showing great attention to detail; very careful.",       "example": "Meticulous documentation separates good engineers from great ones.", "french": "Méticuleux"},
    {"word": "Stoic",         "phonetic": "/ˈstəʊɪk/",         "meaning": "Enduring pain without showing feelings.",                "example": "His stoic response commanded the respect of the whole team.", "french": "Stoïque"},
    {"word": "Voracious",     "phonetic": "/vəˈreɪʃəs/",       "meaning": "Having a very eager, insatiable approach to an activity.", "example": "His voracious appetite for knowledge made him the most well-rounded in the room.", "french": "Vorace"},
    {"word": "Candor",        "phonetic": "/ˈkændər/",          "meaning": "The quality of being open and honest; frankness.",       "example": "His candor in the negotiation built an unexpected level of trust.", "french": "Franchise"},
    {"word": "Assiduous",     "phonetic": "/əˈsɪdjʊəs/",       "meaning": "Showing great care and perseverance; diligent.",         "example": "Her assiduous preparation was evident in the flawless presentation.", "french": "Assidu"},
    {"word": "Lucid",         "phonetic": "/ˈluːsɪd/",         "meaning": "Expressed clearly; easy to understand.",                 "example": "A lucid explanation is the hallmark of true expertise.",        "french": "Lucide"},
    {"word": "Intrepid",      "phonetic": "/ɪnˈtrɛpɪd/",       "meaning": "Fearless and adventurous; courageous.",                  "example": "The intrepid entrepreneur launched three companies before age 30.", "french": "Intrépide"},
    {"word": "Pragmatic",     "phonetic": "/præɡˈmætɪk/",      "meaning": "Dealing with things realistically and practically.",     "example": "A pragmatic approach to problem-solving yields faster results.", "french": "Pragmatique"},
    {"word": "Malleable",     "phonetic": "/ˈmælɪəbl/",        "meaning": "Easily influenced; adaptable to new conditions.",        "example": "A malleable mindset is essential for rapidly changing industries.", "french": "Malléable"},
    {"word": "Formidable",    "phonetic": "/ˈfɔːmɪdəbl/",      "meaning": "Inspiring respect through being impressively capable.",  "example": "She built a formidable reputation through consistent excellence.", "french": "Redoutable"},
]

# ── C1 QUIZ ───────────────────────────────────────────────────────────────────
QUIZ_EN = [
    {"word":"Ubiquitous","question":"What does 'ubiquitous' mean?","options":["Found everywhere; omnipresent","Unique and extremely rare","Moving very quickly","Related to water"],"answer":0,"example":"Smartphones have become ubiquitous in modern society."},
    {"word":"Alacrity","question":"'Alacrity' describes:","options":["Great sadness or grief","Brisk and cheerful readiness","Extreme physical strength","A legal dispute"],"answer":1,"example":"She accepted the challenge with alacrity."},
    {"word":"Recalcitrant","question":"Someone 'recalcitrant' is:","options":["Very intelligent and quick","Having an excellent memory","Stubbornly resistant to authority","Extremely generous"],"answer":2,"example":"The recalcitrant student refused to follow any rules."},
    {"word":"Pernicious","question":"What does 'pernicious' mean?","options":["Having a subtle harmful effect","Full of joy and energy","Extremely precise","Related to money"],"answer":0,"example":"The pernicious influence of propaganda shaped an entire generation."},
    {"word":"Sanguine","question":"A 'sanguine' outlook is:","options":["Pessimistic and gloomy","Related to blood","Optimistic, especially in difficult situations","Logical and analytical"],"answer":2,"example":"Despite the setbacks, she remained sanguine about their chances."},
    {"word":"Obfuscate","question":"To 'obfuscate' means to:","options":["Make it clear and transparent","Make it confused or unclear","Strengthen or reinforce","Analyze thoroughly"],"answer":1,"example":"Politicians often obfuscate the truth with vague language."},
    {"word":"Laconic","question":"A 'laconic' reply is:","options":["Very long and detailed","Emotional and passionate","Brief and concise","Loud and aggressive"],"answer":2,"example":"His laconic 'yes' was the only reply to the lengthy proposal."},
    {"word":"Propitious","question":"'Propitious' means:","options":["Giving a good chance of success","Extremely dangerous","Related to property","Confused or disoriented"],"answer":0,"example":"The timing seemed propitious for launching the new product."},
    {"word":"Intransigent","question":"An 'intransigent' person is:","options":["Very agreeable and flexible","Unwilling to change their views","Highly intelligent","Shy and reserved"],"answer":1,"example":"The intransigent negotiator refused every compromise."},
    {"word":"Circumspect","question":"To be 'circumspect' means to be:","options":["Completely circular in reasoning","Wary and unwilling to take risks","Extremely talkative","Very generous"],"answer":1,"example":"A circumspect investor avoids impulsive decisions."},
    {"word":"Enervate","question":"To 'enervate' someone means to:","options":["Give them energy","Make them stronger","Drain their vitality or strength","Irritate them"],"answer":2,"example":"The oppressive heat enervated the workers by midday."},
    {"word":"Loquacious","question":"A 'loquacious' person tends to:","options":["Speak very little","Eat a lot","Talk a great deal","Move slowly"],"answer":2,"example":"The loquacious host kept the party entertained all evening."},
    {"word":"Truculent","question":"'Truculent' behavior is:","options":["Eager to argue or fight; aggressively defiant","Shy and withdrawn","Precise and methodical","Cheerful and optimistic"],"answer":0,"example":"His truculent attitude made negotiations nearly impossible."},
    {"word":"Mendacious","question":"A 'mendacious' person is:","options":["Very hardworking","Not telling the truth; lying","Extremely generous","Skilled with their hands"],"answer":1,"example":"The mendacious politician promised what he couldn't deliver."},
    {"word":"Fastidious","question":"A 'fastidious' person is:","options":["Reckless and careless","Very demanding about quality and detail","Extremely fast","Generous and open-handed"],"answer":1,"example":"She was fastidious about the presentation of her work."},
    {"word":"Inveterate","question":"An 'inveterate' habit is:","options":["Easy to break","Related to winter","Deep-rooted and long-established","Beneficial to health"],"answer":2,"example":"He was an inveterate gambler who couldn't stop."},
    {"word":"Perfidious","question":"'Perfidious' means:","options":["Very generous and kind","Deceitful and untrustworthy","Extremely talented","Related to perfumes"],"answer":1,"example":"His perfidious behavior destroyed years of trust."},
    {"word":"Dissemble","question":"To 'dissemble' means to:","options":["Take apart carefully","Conceal one's true motives","Distribute widely","Analyze in detail"],"answer":1,"example":"He dissembled his true intentions behind a friendly facade."},
    {"word":"Pellucid","question":"'Pellucid' writing is:","options":["Translucently clear and easy to understand","Very technical and complex","Emotional and dramatic","Very brief"],"answer":0,"example":"His pellucid explanation made the complex theory accessible to all."},
    {"word":"Perspicacious","question":"A 'perspicacious' observer is:","options":["Easily fooled","Having sharp insight and keen perception","Very loud and assertive","Extremely slow"],"answer":1,"example":"Her perspicacious analysis impressed the entire board."},
]

QUIZ_FR = [
    {"word":"Assidu","question":"Que signifie 'assidu' ?","options":["Qui manque souvent","Qui fréquente régulièrement avec application","Qui parle beaucoup","Qui est très rapide"],"answer":1,"example":"Un étudiant assidu finit toujours par réussir."},
    {"word":"Perspicace","question":"Une personne 'perspicace' est :","options":["Très lente à comprendre","Qui voit clairement au-delà des apparences","Qui parle fort","Très timide"],"answer":1,"example":"Son analyse perspicace a révélé les failles du projet."},
    {"word":"Péremptoire","question":"Un ton 'péremptoire' est :","options":["Doux et hésitant","Qui n'admet pas la contradiction ; catégorique","Très humoristique","Triste et mélancolique"],"answer":1,"example":"Il répondit d'un ton péremptoire qui ne laissait place à aucun débat."},
    {"word":"Circonspect","question":"Agir de manière 'circonspecte' signifie :","options":["Agir impulsivement","Agir avec prudence et réflexion","Agir rapidement","Agir généreusement"],"answer":1,"example":"Soyez circonspect avant de prendre une telle décision."},
    {"word":"Équivoque","question":"'Équivoque' signifie :","options":["Très clair et précis","Qui peut être interprété de plusieurs façons ; ambigu","Très juste et équitable","Très vocal"],"answer":1,"example":"Sa réponse équivoque laissait place à toutes les interprétations."},
    {"word":"Inébranlable","question":"Une conviction 'inébranlable' est :","options":["Fragile et incertaine","Qui ne peut être ébranlée ; ferme et solide","Nouvelle et récente","Partiellement vraie"],"answer":1,"example":"Sa confiance inébranlable lui a permis de surmonter tous les obstacles."},
    {"word":"Fallacieux","question":"Un argument 'fallacieux' est :","options":["Très convaincant et juste","Basé sur une erreur ; trompeur","Très ancien","Complexe et difficile"],"answer":1,"example":"Son raisonnement fallacieux trompa de nombreux auditeurs."},
    {"word":"Véhément","question":"Une protestation 'véhémente' est :","options":["Calme et mesurée","Exprimée avec force et passion","Écrite et formelle","Silencieuse"],"answer":1,"example":"Il s'opposa de façon véhémente à la décision du directeur."},
    {"word":"Prégnant","question":"Une image 'prégnante' est :","options":["Floue et difficile à voir","Qui s'impose fortement à l'esprit","Très ancienne","Très petite"],"answer":1,"example":"Ce souvenir reste prégnant dans sa mémoire après toutes ces années."},
    {"word":"Subreptice","question":"Une action 'subreptice' est faite :","options":["De manière ouverte et transparente","De manière furtive, secrète","Avec beaucoup d'enthousiasme","Avec grande précision"],"answer":1,"example":"Il s'empara subrepticement des documents pendant la réunion."},
    {"word":"Inéluctable","question":"Quelque chose d'inéluctable est :","options":["Facilement évitable","Auquel on ne peut échapper ; inévitable","Très difficile à comprendre","Très coûteux"],"answer":1,"example":"Sa victoire semblait inéluctable dès le début du match."},
    {"word":"Acrimonieux","question":"Un échange 'acrimonieux' est :","options":["Agréable et cordial","Plein d'amertume et d'hostilité","Très formel","Très bref"],"answer":1,"example":"La réunion tourna à l'échange acrimonieux entre les deux parties."},
]

def get_quiz_questions(lang='en', n=5):
    import random
    pool = QUIZ_EN if lang == 'en' else QUIZ_FR
    return random.sample(pool, min(n, len(pool)))

def get_quote_of_day():
    return QUOTES[date.today().toordinal() % len(QUOTES)]

def get_word_of_day():
    return WORDS[date.today().toordinal() % len(WORDS)]

import random
def get_random_word():
    return random.choice(WORDS)

def get_random_quote():
    return random.choice(QUOTES)

# ── ACTIVITIES v3.0 ──────────────────────────────────────────────────────────
#
# pts  = XP directo (sin multiplicador)
# ec   = Euda-Credits otorgados
# tier = 'micro' | 'progreso' | 'alto'
# weekend = 'sat' | 'sun' | None  (solo visible ese día)
#
ACTIVITIES = {
    # ── LOGOI — Programación ──────────────────────────────────────────────────
    "sololearn":        {"label": "Lección SoloLearn / Mimo",        "cat": "Programación",     "pts": 1, "ec": 0, "tier": "micro"},
    "leer_prog":        {"label": "Leer programación",               "cat": "Programación",     "pts": 2, "ec": 0, "tier": "micro"},
    "python100":        {"label": "Lección 100 Días Python",         "cat": "Programación",     "pts": 2, "ec": 1, "tier": "progreso"},
    "ccna":             {"label": "Curso CCNA / Frontend",           "cat": "Programación",     "pts": 3, "ec": 1, "tier": "progreso"},
    "resolver_codigo":  {"label": "Resolver 5 problemas reales",     "cat": "Programación",     "pts": 6, "ec": 2, "tier": "alto"},
    "github":           {"label": "Subir proyecto a GitHub",         "cat": "Programación",     "pts": 8, "ec": 3, "tier": "alto"},

    # ── COSMOPOLITISMO — Idiomas ──────────────────────────────────────────────
    "podcast_idiomas":  {"label": "Podcast en idiomas",              "cat": "Idiomas",          "pts": 1, "ec": 0, "tier": "micro"},
    "VividVocab":       {"label": "Lección VividVocab",              "cat": "Idiomas",          "pts": 1, "ec": 0, "tier": "micro"},
    "leccion_idiomas":  {"label": "Lecciones idiomas",               "cat": "Idiomas",          "pts": 2, "ec": 1, "tier": "progreso"},
    "conversacion":     {"label": "Conversación real 10min+",        "cat": "Idiomas",          "pts": 5, "ec": 2, "tier": "alto"},
    "test_cert":        {"label": "Test certificación (DALF/IELTS)", "cat": "Idiomas",          "pts": 8, "ec": 3, "tier": "alto"},

    # ── HEGEMONIKON — Salud Mental ────────────────────────────────────────────
    "meditar":          {"label": "Meditar",                         "cat": "Salud Mental",     "pts": 2, "ec": 0, "tier": "micro"},

    # ── HEGEMONIKON — Salud Física ────────────────────────────────────────────
    "gym":              {"label": "Ejercicio Gym",                   "cat": "Salud Física",     "pts": 4, "ec": 1, "tier": "progreso"},
    "pliometria":       {"label": "Pliometría",                      "cat": "Salud Física",     "pts": 3, "ec": 1, "tier": "progreso"},
    "partido":          {"label": "Partido",                         "cat": "Salud Física",     "pts": 3, "ec": 1, "tier": "progreso"},
    "gol":              {"label": "Gol (bonus partido)",             "cat": "Salud Física",     "pts": 2, "ec": 0, "tier": "micro"},

    # ── HEGEMONIKON — Salud Base ──────────────────────────────────────────────
    "colacion":         {"label": "Colación saludable",              "cat": "Salud Base",       "pts": 1, "ec": 0, "tier": "micro"},
    "jugo_verde":       {"label": "Jugo verde",                      "cat": "Salud Base",       "pts": 1, "ec": 0, "tier": "micro"},
    "comer_fruta":      {"label": "Comer fruta",                     "cat": "Salud Base",       "pts": 1, "ec": 0, "tier": "micro"},
    "dormir_8h":        {"label": "Dormir 8 horas",                  "cat": "Salud Base",       "pts": 2, "ec": 0, "tier": "micro"},
    "skincare_noche":   {"label": "Skin Care nocturno",              "cat": "Salud Base",       "pts": 2, "ec": 0, "tier": "micro"},

    # ── EURYTHMIA — Baile ─────────────────────────────────────────────────────
    "baile":            {"label": "Practicar baile",                 "cat": "Baile",            "pts": 2, "ec": 1, "tier": "progreso"},
    "grabar_baile":     {"label": "Grabar práctica de baile",        "cat": "Baile",            "pts": 3, "ec": 1, "tier": "progreso"},

    # ── PAIDEIA — Conocimiento ────────────────────────────────────────────────
    "leer_general":     {"label": "Leer 5 páginas",                  "cat": "Paideia",          "pts": 1, "ec": 0, "tier": "micro"},
    "leer_psico":       {"label": "Leer psicología",                 "cat": "Paideia",          "pts": 1, "ec": 0, "tier": "micro"},
    "leer_365_dias":    {"label": "Leer 365 días",                   "cat": "Paideia",          "pts": 1, "ec": 0, "tier": "micro"},
    "brilliant":        {"label": "Lección Brilliant",               "cat": "Paideia",          "pts": 2, "ec": 1, "tier": "progreso"},

    # ── OIKONOMIA — Finanzas ──────────────────────────────────────────────────
    "registrar_gastos": {"label": "Registrar gastos",                "cat": "Finanzas",         "pts": 2, "ec": 1, "tier": "progreso"},
    "finanzas_udemy":   {"label": "Lección finanzas",                "cat": "Finanzas",         "pts": 2, "ec": 1, "tier": "progreso"},
    "gbm":              {"label": "Investigar en GBM",               "cat": "Finanzas",         "pts": 2, "ec": 1, "tier": "progreso"},
    "ahorrar":          {"label": "Ahorrar dinero (mensual)",        "cat": "Finanzas",         "pts": 6, "ec": 3, "tier": "alto"},

    # ── ATARAXIA — Orden ──────────────────────────────────────────────────────
    "tender_cama":      {"label": "Tender cama",                     "cat": "Orden",            "pts": 1, "ec": 0, "tier": "micro"},
    "planchar":         {"label": "Planchar ropa",                   "cat": "Orden",            "pts": 2, "ec": 1, "tier": "progreso"},
    "prep_comida":      {"label": "Preparar comida semana",          "cat": "Orden",            "pts": 3, "ec": 1, "tier": "progreso"},
    "limpieza":         {"label": "Limpieza semanal",                "cat": "Orden",            "pts": 3, "ec": 1, "tier": "progreso"},
    "lavar_carro":      {"label": "Lavar carro",                     "cat": "Orden",            "pts": 2, "ec": 0, "tier": "micro"},
    "revision_semanal": {"label": "Revisión semanal",                "cat": "Orden",            "pts": 7, "ec": 3, "tier": "alto"},

    # ── IDENTIDAD — Presencia / Enfoque ──────────────────────────────────────
    "outfit":           {"label": "Outfit cuidado / presencia",      "cat": "Identidad",        "pts": 1, "ec": 0, "tier": "micro"},
    "lenguaje_corporal":{"label": "Lenguaje corporal consciente",    "cat": "Identidad",        "pts": 1, "ec": 0, "tier": "micro"},
    "redes_control":    {"label": "<3.5h redes sociales",            "cat": "Identidad",        "pts": 4, "ec": 1, "tier": "progreso"},

    # ── SÁBADO RESET — solo sábado ────────────────────────────────────────────
    "sat_bloque1":      {"label": "Bloque 1 — Arranque & Limpieza",      "cat": "Sábado Reset", "pts": 4, "ec": 2, "tier": "progreso", "weekend": "sat"},
    "sat_bloque2":      {"label": "Bloque 2 — Ensayo",                   "cat": "Sábado Reset", "pts": 4, "ec": 2, "tier": "alto",     "weekend": "sat"},
    "sat_bloque3":      {"label": "Bloque 3 — Gym & Cierre",             "cat": "Sábado Reset", "pts": 4, "ec": 2, "tier": "alto",     "weekend": "sat"},
    "sat_jugos":        {"label": "Preparar jugos (opcional)",           "cat": "Sábado Reset", "pts": 2, "ec": 1, "tier": "progreso", "weekend": "sat", "optional": True},
    "sat_flow":         {"label": "Bonus — Flow continuo",               "cat": "Sábado Reset", "pts": 2, "ec": 1, "tier": "progreso", "weekend": "sat"},

    # ── DOMINGO STRATEGY — solo domingo ──────────────────────────────────────
    "sun_reflexion":    {"label": "Reflexión — Planeación + Prioridades","cat": "Domingo Strategy", "pts": 4, "ec": 2, "tier": "alto",    "weekend": "sun"},
    "sun_diseno":       {"label": "Finanzas — Revisión semanal",         "cat": "Domingo Strategy", "pts": 4, "ec": 2, "tier": "alto",    "weekend": "sun"},
    "sun_comidas":      {"label": "Sistema — Super + Comida semanal",    "cat": "Domingo Strategy", "pts": 3, "ec": 1, "tier": "progreso","weekend": "sun"},
    "sun_jugos":        {"label": "Sistema — Preparar jugos",            "cat": "Domingo Strategy", "pts": 2, "ec": 1, "tier": "progreso","weekend": "sun"},
    "sun_planchar":     {"label": "Sistema — Planchar & Cargas",         "cat": "Domingo Strategy", "pts": 2, "ec": 1, "tier": "progreso","weekend": "sun"},
}

# Canonical categories for weekday activities
ACTIVITY_CATEGORIES = [
    "Programación", "Idiomas",
    "Salud Mental", "Salud Física", "Salud Base",
    "Baile", "Paideia", "Finanzas", "Orden", "Identidad",
]

# Mapping virtud → category keys for combo/balance logic
VIRTUE_CATS = {
    "LOGOI":          ["Programación"],
    "COSMOPOLITISMO": ["Idiomas"],
    "HEGEMONIKON":    ["Salud Mental", "Salud Física", "Salud Base"],
    "EURYTHMIA":      ["Baile"],
    "PAIDEIA":        ["Paideia"],
    "OIKONOMIA":      ["Finanzas"],
    "ATARAXIA":       ["Orden"],
    "IDENTIDAD":      ["Identidad"],
}

# ── SATURDAY TASKS ────────────────────────────────────────────────────────────
SATURDAY_TASKS = [
    {"key": "vacuum_house",    "label": "🤖 Lancer vacuum robot — casa"},
    {"key": "hang_clothes",    "label": "👔 Hang clothes / wash second load"},
    {"key": "clean_bathroom",  "label": "🚿 Clean bathroom"},
    {"key": "sortir_poubelle", "label": "🗑️ Sortir la poubelle"},
    {"key": "coffee",          "label": "☕ Make some coffeeee :)"},
    {"key": "wipeout_tables",  "label": "🧹 Wipeout night table, table & computer"},
    {"key": "prepare_bkfast",  "label": "🍳 Prepare breakfast"},
    {"key": "take_bkfast",     "label": "🥣 Take breakfast"},
    {"key": "plants",          "label": "🌱 Check your plants"},
    {"key": "vacuum_bedroom",  "label": "🤖 Lancer vacuum robot — bedroom"},
    {"key": "passer_mop",      "label": "🧺 Passer le mop"},
    {"key": "wash_clothes",    "label": "👕 Wash clothes"},
    {"key": "wash_plates",     "label": "🍽️ Wash plates"},
    {"key": "change_sheets",   "label": "🛏️ Change sheets if applicable"},
    {"key": "wipeout_kitchen", "label": "🍴 Wipeout kitchen, table & microwave"},
]

DAYS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
MEAL_TYPES = ["Desayuno","Comida","Cena","Snack"]
