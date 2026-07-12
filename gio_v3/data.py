from datetime import date
from utils import today_date

# ── QUOTES ────────────────────────────────────────────────────────────────────
QUOTES = [
    # ── Estoicas ──────────────────────────────────────────────────────────────
    {"text": "No man is free who is not master of himself.", "author": "Epicteto · Enquiridión", "category": "stoic"},
    {"text": "The impediment to action advances action. What stands in the way becomes the way.", "author": "Marco Aurelio · Meditaciones", "category": "stoic"},
    {"text": "We suffer more in imagination than in reality.", "author": "Séneca · Cartas a Lucilio", "category": "stoic"},
    {"text": "Waste no more time arguing what a good man should be. Be one.", "author": "Marco Aurelio · Meditaciones VIII", "category": "stoic"},
    {"text": "You have power over your mind, not outside events. Realize this and you will find strength.", "author": "Marco Aurelio · Meditaciones", "category": "stoic"},
    {"text": "Sufrir o no sufrir, eso siempre dependerá de ti.", "author": "Epicteto · Enquiridión", "category": "stoic"},
    {"text": "Busca dentro. Dentro está la fuente del bien, y siempre brotará, si siempre cavas.", "author": "Marco Aurelio · Meditaciones VII", "category": "stoic"},
    {"text": "No turbará tu mente lo que te acontece desde fuera; pues depende solo de tus juicios.", "author": "Marco Aurelio · Meditaciones IV", "category": "stoic"},
    {"text": "La felicidad de tu vida depende de la calidad de tus pensamientos.", "author": "Marco Aurelio · Meditaciones V", "category": "stoic"},
    {"text": "Soporta y abstente: ese es el doble mandato de la filosofía estoica.", "author": "Epicteto · Enquiridión", "category": "stoic"},
    {"text": "Pierde el tiempo el que mide el tiempo; aprovéchalo el que lo vive.", "author": "Séneca · Cartas a Lucilio", "category": "stoic"},
    {"text": "Vive conforme a la naturaleza; en eso reside la virtud y la felicidad.", "author": "Zenón de Citio", "category": "stoic"},
    {"text": "Haz cada acto de tu vida como si fuera el último.", "author": "Marco Aurelio · Meditaciones II", "category": "stoic"},
    {"text": "If it is not right, do not do it. If it is not true, do not say it.", "author": "Marco Aurelio · Meditaciones XII", "category": "stoic"},
    {"text": "Nunca dejes que el futuro te perturbe. Lo enfrentarás con las mismas armas de la razón con que hoy enfrentas el presente.", "author": "Marco Aurelio · Meditaciones VII", "category": "stoic"},
    {"text": "Elige no ser dañado y no te sentirás dañado. No te sientas dañado y no lo estarás.", "author": "Marco Aurelio · Meditaciones IV", "category": "stoic"},
    {"text": "Begin at once to live, and count each separate day as a separate life.", "author": "Séneca · Cartas a Lucilio", "category": "stoic"},
    {"text": "Dwell on the beauty of life. Watch the stars, and see yourself running with them.", "author": "Marco Aurelio · Meditaciones", "category": "stoic"},
    {"text": "Very little is needed to make a happy life; it is all within yourself, in your way of thinking.", "author": "Marco Aurelio · Meditaciones VII", "category": "stoic"},
    {"text": "He who fears death will never do anything worthy of a living man.", "author": "Séneca", "category": "stoic"},
    {"text": "Make the best use of what is in your power, and take the rest as it happens.", "author": "Epicteto · Enquiridión", "category": "stoic"},
    {"text": "First say to yourself what you would be; and then do what you have to do.", "author": "Epicteto · Discursos", "category": "stoic"},
    {"text": "La vida es corta, pero el arte es largo, la oportunidad fugaz, la experiencia engañosa, el juicio difícil.", "author": "Hipócrates", "category": "stoic"},
    {"text": "Wealth consists not in having great possessions, but in having few wants.", "author": "Epicteto", "category": "stoic"},
    {"text": "Omnia aliena sunt, tempus tantum nostrum est — Todo lo ajeno nos pertenece por poco; solo el tiempo es realmente nuestro.", "author": "Séneca · Cartas I", "category": "stoic"},
    {"text": "El tiempo descubre la verdad.", "author": "Séneca", "category": "stoic"},
    {"text": "A gem cannot be polished without friction, nor a man perfected without trials.", "author": "Séneca", "category": "stoic"},
    {"text": "Recuerda que eres actor de una obra, cuyo carácter determina el autor. Si es corta, de una corta; si es larga, de una larga.", "author": "Epicteto · Enquiridión", "category": "stoic"},
    {"text": "The soul that has no fixed purpose loses itself, for to be everywhere is to be nowhere.", "author": "Séneca · Cartas a Lucilio", "category": "stoic"},
    {"text": "El que tiene un porqué vivir puede soportar casi cualquier cómo.", "author": "Nietzsche", "category": "stoic"},
    # ── Motivacionales ────────────────────────────────────────────────────────
    {"text": "Discipline is the bridge between goals and accomplishment.", "author": "Jim Rohn", "category": "motivational"},
    {"text": "Hard times create strong men. Strong men create good times.", "author": "G. Michael Hopf", "category": "motivational"},
    {"text": "Do not go where the path may lead; go where there is no path and leave a trail.", "author": "Emerson", "category": "motivational"},
    {"text": "A man who conquers himself is greater than one who conquers a thousand men in battle.", "author": "Buda", "category": "motivational"},
    {"text": "Forged in fire. Built in silence. Delivered in results.", "author": "—", "category": "motivational"},
    {"text": "Your future self is watching you right now through your memories.", "author": "—", "category": "motivational"},
    {"text": "Gana en silencio. El ruido es para los que necesitan testigos.", "author": "—", "category": "motivational"},
    {"text": "Complacency is the enemy of excellence.", "author": "—", "category": "motivational"},
    {"text": "Every day you don't level up, someone else does.", "author": "—", "category": "motivational"},
    {"text": "El dolor es inevitable, el sufrimiento es opcional.", "author": "Buda", "category": "motivational"},
    {"text": "The secret of getting ahead is getting started.", "author": "Mark Twain", "category": "motivational"},
    {"text": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucio", "category": "motivational"},
    {"text": "Success is not final, failure is not fatal: it is the courage to continue that counts.", "author": "Churchill", "category": "motivational"},
    {"text": "Do the hard things first. The rest will be easy.", "author": "—", "category": "motivational"},
    {"text": "No one is going to come save you. This life is 100% your responsibility.", "author": "—", "category": "motivational"},
    {"text": "You don't rise to the level of your goals, you fall to the level of your systems.", "author": "James Clear · Atomic Habits", "category": "motivational"},
    {"text": "Standard of performance, not results. Control the process.", "author": "—", "category": "motivational"},
    {"text": "Motivation is what gets you started. Habit is what keeps you going.", "author": "Jim Ryun", "category": "motivational"},
    {"text": "El éxito no es la clave de la felicidad. La felicidad es la clave del éxito.", "author": "Albert Schweitzer", "category": "motivational"},
    {"text": "Iron sharpens iron. Pressure builds diamonds.", "author": "—", "category": "motivational"},
    {"text": "The man who moves a mountain begins by carrying away small stones.", "author": "Confucio", "category": "motivational"},
    {"text": "Don't count the days, make the days count.", "author": "Muhammad Ali", "category": "motivational"},
    {"text": "We are what we repeatedly do. Excellence, then, is not an act, but a habit.", "author": "Aristóteles", "category": "motivational"},
    {"text": "The only person you are destined to become is the person you decide to be.", "author": "Emerson", "category": "motivational"},
    {"text": "Inaction breeds doubt and fear. Action breeds confidence and courage.", "author": "Dale Carnegie", "category": "motivational"},
    {"text": "Lo que no te mata te hace más fuerte.", "author": "Nietzsche", "category": "motivational"},
    {"text": "Champions aren't made in gyms. Champions are made from something they have deep inside: a desire, a dream, a vision.", "author": "Muhammad Ali", "category": "motivational"},
    {"text": "Pursue what is meaningful, not what is expedient.", "author": "Jordan B. Peterson", "category": "motivational"},
    {"text": "You have to be odd to be number one.", "author": "Dr. Seuss", "category": "motivational"},
    {"text": "Amateurs sit and wait for inspiration. The rest of us just get up and go to work.", "author": "Stephen King", "category": "motivational"},
    {"text": "The two most important days in your life are the day you are born, and the day you find out why.", "author": "Mark Twain", "category": "motivational"},
    {"text": "Act as if what you do makes a difference. It does.", "author": "William James", "category": "motivational"},
    {"text": "En medio de la dificultad yace la oportunidad.", "author": "Albert Einstein", "category": "motivational"},
]

# ── WORD OF THE DAY — C1 Vocabulary ──────────────────────────────────────────
WORDS = [
    # ── Existing core ─────────────────────────────────────────────────────────
    {"word": "Perspicacious", "phonetic": "/ˌpɜːspɪˈkeɪʃəs/", "meaning": "Having a ready insight into things; shrewd.", "example": "Her perspicacious analysis of the market impressed the entire board.", "french": "Perspicace"},
    {"word": "Equanimity",    "phonetic": "/ˌɛkwəˈnɪmɪti/",   "meaning": "Mental calmness and composure, especially in difficult situations.", "example": "He faced the crisis with remarkable equanimity.", "french": "Sérénité"},
    {"word": "Indefatigable", "phonetic": "/ˌɪndɪˈfætɪɡəbl/", "meaning": "Persisting tirelessly; incapable of being fatigued.", "example": "Her indefatigable dedication led to eventual success.", "french": "Infatigable"},
    {"word": "Sagacious",     "phonetic": "/səˈɡeɪʃəs/",       "meaning": "Having keen mental discernment and good judgment.", "example": "The sagacious investor knew when to hold and when to divest.", "french": "Sagace"},
    {"word": "Ephemeral",     "phonetic": "/ɪˈfɛmərəl/",       "meaning": "Lasting for a very short time; transitory.", "example": "The ephemeral nature of trends makes long-term strategy essential.", "french": "Éphémère"},
    {"word": "Tenacious",     "phonetic": "/tɪˈneɪʃəs/",       "meaning": "Holding fast; persistent and determined.", "example": "His tenacious pursuit of excellence set him apart.", "french": "Tenace"},
    {"word": "Acumen",        "phonetic": "/ˈækjʊmɛn/",        "meaning": "The ability to make good judgments and quick decisions.", "example": "His financial acumen helped the startup reach profitability.", "french": "Perspicacité"},
    {"word": "Fortitude",     "phonetic": "/ˈfɔːtɪtjuːd/",     "meaning": "Courage in pain or adversity; mental strength.", "example": "It takes fortitude to rebuild after a major setback.", "french": "Fortitude"},
    {"word": "Resilience",    "phonetic": "/rɪˈzɪlɪəns/",      "meaning": "The capacity to recover quickly from difficulties.", "example": "Resilience is the most important trait of high performers.", "french": "Résilience"},
    {"word": "Audacious",     "phonetic": "/ɔːˈdeɪʃəs/",       "meaning": "Showing willingness to take bold risks; daring.", "example": "The audacious pivot changed the company's trajectory entirely.", "french": "Audacieux"},
    {"word": "Meticulous",    "phonetic": "/mɪˈtɪkjʊləs/",     "meaning": "Showing great attention to detail; very careful.", "example": "Meticulous documentation separates good engineers from great ones.", "french": "Méticuleux"},
    {"word": "Stoic",         "phonetic": "/ˈstəʊɪk/",         "meaning": "Enduring pain or hardship without complaint.", "example": "His stoic response commanded the respect of the whole team.", "french": "Stoïque"},
    {"word": "Voracious",     "phonetic": "/vəˈreɪʃəs/",       "meaning": "Having a very eager, insatiable approach to an activity.", "example": "His voracious appetite for knowledge made him the most well-rounded in the room.", "french": "Vorace"},
    {"word": "Candor",        "phonetic": "/ˈkændər/",          "meaning": "The quality of being open and honest; frankness.", "example": "His candor in the negotiation built an unexpected level of trust.", "french": "Franchise"},
    {"word": "Assiduous",     "phonetic": "/əˈsɪdjʊəs/",       "meaning": "Showing great care and perseverance; diligent.", "example": "Her assiduous preparation was evident in the flawless presentation.", "french": "Assidu"},
    {"word": "Lucid",         "phonetic": "/ˈluːsɪd/",         "meaning": "Expressed clearly; easy to understand.", "example": "A lucid explanation is the hallmark of true expertise.", "french": "Lucide"},
    {"word": "Intrepid",      "phonetic": "/ɪnˈtrɛpɪd/",       "meaning": "Fearless and adventurous; courageous.", "example": "The intrepid entrepreneur launched three companies before age 30.", "french": "Intrépide"},
    {"word": "Pragmatic",     "phonetic": "/præɡˈmætɪk/",      "meaning": "Dealing with things realistically and practically.", "example": "A pragmatic approach to problem-solving yields faster results.", "french": "Pragmatique"},
    {"word": "Malleable",     "phonetic": "/ˈmælɪəbl/",        "meaning": "Easily influenced; adaptable to new conditions.", "example": "A malleable mindset is essential for rapidly changing industries.", "french": "Malléable"},
    {"word": "Formidable",    "phonetic": "/ˈfɔːmɪdəbl/",      "meaning": "Inspiring respect through being impressively capable.", "example": "She built a formidable reputation through consistent excellence.", "french": "Redoutable"},
    # ── C1 Expansion ──────────────────────────────────────────────────────────
    {"word": "Ubiquitous",    "phonetic": "/juːˈbɪkwɪtəs/",    "meaning": "Present, appearing, or found everywhere.", "example": "Smartphones have become ubiquitous in modern society.", "french": "Omniprésent"},
    {"word": "Alacrity",      "phonetic": "/əˈlækrɪti/",       "meaning": "Brisk and cheerful readiness to act.", "example": "She accepted the challenge with alacrity.", "french": "Empressement"},
    {"word": "Recalcitrant",  "phonetic": "/rɪˈkælsɪtrənt/",   "meaning": "Stubbornly resistant to authority or control.", "example": "The recalcitrant employee refused every coaching attempt.", "french": "Récalcitrant"},
    {"word": "Pernicious",    "phonetic": "/pəˈnɪʃəs/",        "meaning": "Having a harmful effect in a gradual or subtle way.", "example": "The pernicious influence of short-term thinking destroyed long-term value.", "french": "Pernicieux"},
    {"word": "Sanguine",      "phonetic": "/ˈsæŋɡwɪn/",        "meaning": "Optimistic, especially in difficult situations.", "example": "Despite the setbacks, she remained sanguine about their chances.", "french": "Optimiste"},
    {"word": "Laconic",       "phonetic": "/ləˈkɒnɪk/",        "meaning": "Using very few words; brief and concise.", "example": "His laconic reply conveyed more than a paragraph ever could.", "french": "Laconique"},
    {"word": "Propitious",    "phonetic": "/prəˈpɪʃəs/",       "meaning": "Giving or indicating a good chance of success.", "example": "The timing seemed propitious for launching the new venture.", "french": "Propice"},
    {"word": "Intransigent",  "phonetic": "/ɪnˈtrænsɪdʒənt/",  "meaning": "Unwilling to change one's views or agree to a compromise.", "example": "The intransigent negotiator refused every reasonable offer.", "french": "Intransigeant"},
    {"word": "Circumspect",   "phonetic": "/ˈsɜːkəmspɛkt/",    "meaning": "Wary and unwilling to take risks; cautious.", "example": "A circumspect investor avoids impulsive decisions.", "french": "Circonspect"},
    {"word": "Enervate",      "phonetic": "/ˈɛnəveɪt/",        "meaning": "To drain someone of energy or vitality.", "example": "The oppressive heat enervated the workers by midday.", "french": "Épuiser"},
    {"word": "Loquacious",    "phonetic": "/ləˈkweɪʃəs/",      "meaning": "Tending to talk a great deal; talkative.", "example": "The loquacious host kept the party entertained all evening.", "french": "Loquace"},
    {"word": "Truculent",     "phonetic": "/ˈtrʌkjʊlənt/",     "meaning": "Eager or quick to argue or fight; aggressively defiant.", "example": "His truculent attitude made negotiations nearly impossible.", "french": "Agressif"},
    {"word": "Mendacious",    "phonetic": "/mɛnˈdeɪʃəs/",      "meaning": "Not telling the truth; lying.", "example": "The mendacious report misled investors for months.", "french": "Mensonger"},
    {"word": "Fastidious",    "phonetic": "/fæˈstɪdɪəs/",      "meaning": "Very attentive to accuracy and detail; hard to please.", "example": "She was fastidious about the presentation of her work.", "french": "Méticuleux"},
    {"word": "Inveterate",    "phonetic": "/ɪnˈvɛtərɪt/",      "meaning": "Having a habit or activity deeply established.", "example": "He was an inveterate reader who rarely went anywhere without a book.", "french": "Invétéré"},
    {"word": "Perfidious",    "phonetic": "/pəˈfɪdɪəs/",       "meaning": "Deceitful and untrustworthy; guilty of betrayal.", "example": "His perfidious behavior destroyed years of trust.", "french": "Perfide"},
    {"word": "Dissemble",     "phonetic": "/dɪˈsɛmbl/",        "meaning": "To conceal one's true motives or feelings.", "example": "He dissembled his true intentions behind a friendly facade.", "french": "Dissimuler"},
    {"word": "Pellucid",      "phonetic": "/pɛˈluːsɪd/",       "meaning": "Translucently clear; easily understood.", "example": "His pellucid explanation made the complex theory accessible to all.", "french": "Limpide"},
    {"word": "Obdurate",      "phonetic": "/ˈɒbdjʊrɪt/",       "meaning": "Stubbornly refusing to change one's opinion; hardened.", "example": "Despite the evidence, the committee remained obdurate.", "french": "Obstiné"},
    {"word": "Garrulous",     "phonetic": "/ˈɡærʊləs/",        "meaning": "Excessively talkative, especially on trivial matters.", "example": "The garrulous consultant consumed half the meeting with anecdotes.", "french": "Bavard"},
    {"word": "Equivocate",    "phonetic": "/ɪˈkwɪvəkeɪt/",     "meaning": "To use ambiguous language to conceal the truth.", "example": "Stop equivocating — give us a clear answer.", "french": "Équivoquer"},
    {"word": "Inimical",      "phonetic": "/ɪˈnɪmɪkl/",        "meaning": "Tending to obstruct or harm; hostile.", "example": "The culture was inimical to innovation.", "french": "Hostile"},
    {"word": "Obstreperous",  "phonetic": "/əbˈstrɛpərəs/",    "meaning": "Noisy and difficult to control.", "example": "The obstreperous crowd derailed the entire session.", "french": "Turbulent"},
    {"word": "Querulous",     "phonetic": "/ˈkwɛrʊləs/",       "meaning": "Complaining in a petulant or whining manner.", "example": "His querulous emails undermined his authority with the team.", "french": "Grognon"},
    {"word": "Sycophant",     "phonetic": "/ˈsɪkəfænt/",       "meaning": "A person who acts obsequiously to gain advantage.", "example": "Surrounded by sycophants, the CEO lost touch with reality.", "french": "Flagorneur"},
    {"word": "Veracious",     "phonetic": "/vəˈreɪʃəs/",       "meaning": "Truthful; habitually observing truth.", "example": "A veracious witness is invaluable in complex litigation.", "french": "Véridique"},
    {"word": "Tenuous",       "phonetic": "/ˈtɛnjʊəs/",        "meaning": "Very weak or slight; lacking substance.", "example": "The connection between the two events was tenuous at best.", "french": "Ténu"},
    {"word": "Propensity",    "phonetic": "/prəˈpɛnsɪti/",     "meaning": "A natural tendency to behave in a particular way.", "example": "His propensity for risk-taking defined his entire career.", "french": "Propension"},
    {"word": "Recondite",     "phonetic": "/ˈrɛkəndaɪt/",      "meaning": "Little known; abstruse; obscure.", "example": "His recondite knowledge of Byzantine history impressed the professors.", "french": "Peu connu"},
    {"word": "Paucity",       "phonetic": "/ˈpɔːsɪti/",        "meaning": "The presence of something in only small or insufficient quantities.", "example": "The paucity of evidence made conviction impossible.", "french": "Pénurie"},
    {"word": "Dilettante",    "phonetic": "/ˌdɪlɪˈtænti/",     "meaning": "A person who cultivates an area of interest superficially.", "example": "Professionals quickly distinguish themselves from dilettantes.", "french": "Dilettante"},
    {"word": "Vertiginous",   "phonetic": "/vɜːˈtɪdʒɪnəs/",    "meaning": "Causing or involving a feeling of dizzying speed or scale.", "example": "The startup achieved vertiginous growth in its second year.", "french": "Vertigineux"},
    {"word": "Opprobrious",   "phonetic": "/əˈprəʊbrɪəs/",     "meaning": "Deserving or bringing disgrace or shame.", "example": "The opprobrious conduct cost him his position.", "french": "Honteux"},
    {"word": "Impervious",    "phonetic": "/ɪmˈpɜːvɪəs/",      "meaning": "Unable to be affected by; not allowing penetration.", "example": "He was impervious to criticism, which was both his strength and flaw.", "french": "Imperméable"},
    {"word": "Cogent",        "phonetic": "/ˈkəʊdʒənt/",       "meaning": "Clear, logical, and convincing.", "example": "She made a cogent argument that shifted the entire room.", "french": "Convaincant"},
    {"word": "Abstruse",      "phonetic": "/æbˈstruːs/",       "meaning": "Difficult to understand; obscure.", "example": "The abstruse mathematical proof took years to verify.", "french": "Abstrus"},
    {"word": "Inexorable",    "phonetic": "/ɪnˈɛksərəbl/",     "meaning": "Impossible to stop or prevent; relentless.", "example": "The inexorable march of automation reshaped the labor market.", "french": "Inexorable"},
    {"word": "Indelible",     "phonetic": "/ɪnˈdɛlɪbl/",       "meaning": "Making marks that cannot be removed; unforgettable.", "example": "The experience left an indelible mark on his worldview.", "french": "Indélébile"},
    {"word": "Insolvent",     "phonetic": "/ɪnˈsɒlvənt/",      "meaning": "Unable to pay debts; bankrupt.", "example": "The company was declared insolvent after three consecutive quarters of losses.", "french": "Insolvable"},
    {"word": "Salient",       "phonetic": "/ˈseɪlɪənt/",       "meaning": "Most noticeable or important; prominent.", "example": "The salient point of the report was buried in the appendix.", "french": "Saillant"},
    {"word": "Impetuous",     "phonetic": "/ɪmˈpɛtʃʊəs/",      "meaning": "Acting or done quickly without thought or care.", "example": "His impetuous decision cost the company its biggest client.", "french": "Impétueux"},
    {"word": "Sedulous",      "phonetic": "/ˈsɛdjʊləs/",       "meaning": "Showing dedication and diligence; hardworking.", "example": "Her sedulous attention to craft elevated the entire project.", "french": "Assidu"},
    {"word": "Vacuous",       "phonetic": "/ˈvækjʊəs/",        "meaning": "Having or showing a lack of thought or intelligence.", "example": "The vacuous marketing copy alienated their most sophisticated customers.", "french": "Vide"},
    {"word": "Iconoclast",    "phonetic": "/aɪˈkɒnəklæst/",    "meaning": "A person who challenges cherished beliefs or institutions.", "example": "Every disruptive era produces its iconic iconoclasts.", "french": "Iconoclaste"},
    {"word": "Duplicitous",   "phonetic": "/djuːˈplɪsɪtəs/",   "meaning": "Deceitful; behaving in a double-dealing manner.", "example": "His duplicitous strategy eventually unraveled in public.", "french": "Duplice"},
    {"word": "Magnanimous",   "phonetic": "/mæɡˈnænɪməs/",     "meaning": "Very generous or forgiving; especially toward a rival.", "example": "In victory, she was magnanimous enough to acknowledge the opponent's strengths.", "french": "Magnanime"},
    {"word": "Nomenclature",  "phonetic": "/nəˈmɛŋklətʃər/",   "meaning": "The system of names or terms used in a particular discipline.", "example": "Mastering the nomenclature of a field signals intellectual fluency.", "french": "Nomenclature"},
    {"word": "Vicarious",     "phonetic": "/vɪˈkɛərɪəs/",      "meaning": "Experienced in the imagination through another person.", "example": "Reading biographies provides vicarious exposure to extraordinary lives.", "french": "Par procuration"},
    {"word": "Perfunctory",   "phonetic": "/pəˈfʌŋktərɪ/",     "meaning": "Carried out with minimal effort; superficial.", "example": "A perfunctory review is worse than no review at all.", "french": "Superficiel"},
    {"word": "Redoubtable",   "phonetic": "/rɪˈdaʊtəbl/",      "meaning": "Inspiring fear or respect through being formidably impressive.", "example": "She was a redoubtable opponent who never underestimated anyone.", "french": "Redoutable"},
    {"word": "Limpid",        "phonetic": "/ˈlɪmpɪd/",         "meaning": "Clear and calm; free from confusion.", "example": "His limpid prose made difficult ideas instantly accessible.", "french": "Limpide"},
    {"word": "Obstinate",     "phonetic": "/ˈɒbstɪnɪt/",       "meaning": "Stubbornly refusing to change one's opinion or chosen course.", "example": "His obstinate refusal to delegate nearly killed the company.", "french": "Obstiné"},
    {"word": "Nebulous",      "phonetic": "/ˈnɛbjʊləs/",       "meaning": "Unclear, vague, or ill-defined.", "example": "The strategy was too nebulous to be actionable.", "french": "Nébuleux"},
    {"word": "Voluble",       "phonetic": "/ˈvɒljʊbl/",        "meaning": "Speaking fluently and at length; articulate.", "example": "The voluble speaker held the audience's attention for two hours.", "french": "Volubile"},
    {"word": "Supercilious",  "phonetic": "/ˌsuːpəˈsɪlɪəs/",   "meaning": "Behaving as if one thinks they are superior to others.", "example": "His supercilious tone alienated everyone in the room.", "french": "Condescendant"},
    {"word": "Disingenuous",  "phonetic": "/ˌdɪsɪnˈdʒɛnjʊəs/", "meaning": "Not candid or sincere; pretending ignorance.", "example": "The disingenuous apology made things worse, not better.", "french": "Hypocrite"},
    {"word": "Implacable",    "phonetic": "/ɪmˈplækəbl/",      "meaning": "Unable to be appeased or placated; relentless.", "example": "She was an implacable opponent of bureaucratic inertia.", "french": "Implacable"},
    {"word": "Stolid",        "phonetic": "/ˈstɒlɪd/",         "meaning": "Calm and dependable; showing little emotion or animation.", "example": "His stolid demeanor made him the ideal crisis manager.", "french": "Impassible"},
    {"word": "Mercurial",     "phonetic": "/mɜːˈkjʊərɪəl/",    "meaning": "Subject to sudden or unpredictable changes of mood.", "example": "His mercurial temperament made long-term planning impossible.", "french": "Lunatique"},
    {"word": "Vitriolic",     "phonetic": "/ˌvɪtrɪˈɒlɪk/",     "meaning": "Filled with bitter criticism or malice.", "example": "The vitriolic review damaged the artist's reputation unfairly.", "french": "Acerbe"},
    {"word": "Compunction",   "phonetic": "/kəmˈpʌŋkʃən/",     "meaning": "A feeling of guilt or moral scruple about one's actions.", "example": "He signed the order without compunction.", "french": "Remords"},
    {"word": "Acrimony",      "phonetic": "/ˈækrɪməni/",       "meaning": "Bitterness or ill feeling, especially in speech or manner.", "example": "The negotiation ended in acrimony after the final offer was rejected.", "french": "Acrimonie"},
    {"word": "Surreptitious", "phonetic": "/ˌsʌrəpˈtɪʃəs/",    "meaning": "Kept secret, especially because it would not be approved of.", "example": "The surreptitious data collection violated user trust.", "french": "Subreptice"},
    {"word": "Immutable",     "phonetic": "/ɪˈmjuːtəbl/",      "meaning": "Unchanging over time or unable to be changed.", "example": "Some principles are immutable regardless of cultural context.", "french": "Immuable"},
    {"word": "Dexterous",     "phonetic": "/ˈdɛkstrəs/",       "meaning": "Showing or having skill, especially with the hands.", "example": "Dexterous handling of competing interests is the art of diplomacy.", "french": "Adroit"},
    {"word": "Contrite",      "phonetic": "/ˈkɒntraɪt/",       "meaning": "Feeling or expressing remorse; penitent.", "example": "A contrite acknowledgment of the mistake restored confidence.", "french": "Contrit"},
    {"word": "Precipitous",   "phonetic": "/prɪˈsɪpɪtəs/",     "meaning": "Dangerously steep; done too hastily.", "example": "A precipitous rate cut can undermine the very confidence it seeks to build.", "french": "Précipité"},
    {"word": "Ominous",       "phonetic": "/ˈɒmɪnəs/",         "meaning": "Giving the impression something bad is going to happen.", "example": "The ominous silence before the announcement unnerved the entire room.", "french": "Sinistre"},
    {"word": "Prodigious",    "phonetic": "/prəˈdɪdʒəs/",      "meaning": "Remarkably great in extent, size, or degree.", "example": "Her prodigious memory gave her an edge in every negotiation.", "french": "Prodigieux"},
    {"word": "Discernment",   "phonetic": "/dɪˈsɜːnmənt/",     "meaning": "The ability to judge well; perceptive insight.", "example": "Discernment is what separates a good leader from a great one.", "french": "Discernement"},
    {"word": "Impunity",      "phonetic": "/ɪmˈpjuːnɪti/",     "meaning": "Exemption from punishment or freedom from consequences.", "example": "A culture where mistakes are punished kills the innovation it claims to seek.", "french": "Impunité"},
    {"word": "Sanctimonious", "phonetic": "/ˌsæŋktɪˈməʊnɪəs/", "meaning": "Making a show of being morally superior; self-righteous.", "example": "His sanctimonious lecture drove away the very team he was trying to inspire.", "french": "Moralisateur"},
    {"word": "Incisive",      "phonetic": "/ɪnˈsaɪsɪv/",       "meaning": "Intelligently analytical and clear-thinking.", "example": "Her incisive feedback cut through ambiguity and clarified the path forward.", "french": "Incisif"},
    {"word": "Harbinger",     "phonetic": "/ˈhɑːbɪndʒər/",     "meaning": "A person or thing that signals the approach of something.", "example": "The first layoffs were a harbinger of a much deeper restructuring.", "french": "Précurseur"},
    {"word": "Inexplicable",  "phonetic": "/ɪnˈɛksplɪkəbl/",   "meaning": "Unable to be explained or accounted for.", "example": "The inexplicable drop in conversion rate baffled every analyst.", "french": "Inexplicable"},
    {"word": "Equivocal",     "phonetic": "/ɪˈkwɪvəkl/",       "meaning": "Open to more than one interpretation; ambiguous.", "example": "His equivocal response left investors deeply uncertain.", "french": "Équivoque"},
    {"word": "Ameliorate",    "phonetic": "/əˈmiːlɪəreɪt/",    "meaning": "To make something bad better; improve.", "example": "Good design can ameliorate even the most chaotic workflow.", "french": "Améliorer"},
    {"word": "Subversive",    "phonetic": "/səbˈvɜːsɪv/",      "meaning": "Seeking to undermine an established system or institution.", "example": "The most subversive act in a bureaucracy is radical transparency.", "french": "Subversif"},
    {"word": "Perspicuity",   "phonetic": "/ˌpɜːspɪˈkjuːɪti/", "meaning": "Clearness of expression; the quality of being easily understood.", "example": "Perspicuity in communication is a skill that must be deliberately cultivated.", "french": "Clarté"},
    {"word": "Impecunious",   "phonetic": "/ˌɪmpɪˈkjuːnɪəs/",  "meaning": "Having little or no money; poor.", "example": "He started impecunious but became the wealthiest man in the room through discipline.", "french": "Démuni"},
    {"word": "Verisimilitude","phonetic": "/ˌvɛrɪsɪˈmɪlɪtjuːd/","meaning": "The appearance of being true or real.", "example": "The novel achieved its power through verisimilitude — every detail rang true.", "french": "Vraisemblance"},
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

import random

_QUOTES_STOIC = [q for q in QUOTES if q["category"] == "stoic"]
_QUOTES_MOTIV = [q for q in QUOTES if q["category"] == "motivational"]

def get_quote_of_day():
    return QUOTES[today_date().toordinal() % len(QUOTES)]

def get_stoic_of_day():
    return _QUOTES_STOIC[today_date().toordinal() % len(_QUOTES_STOIC)]

def get_motivational_of_day():
    return _QUOTES_MOTIV[today_date().toordinal() % len(_QUOTES_MOTIV)]

def get_word_of_day():
    return WORDS[today_date().toordinal() % len(WORDS)]

def get_random_word():
    return random.choice(WORDS)

def get_random_quote(category=None):
    if category == "stoic":
        return random.choice(_QUOTES_STOIC)
    if category == "motivational":
        return random.choice(_QUOTES_MOTIV)
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
    "abdominales":      {"label": "Abdominales",                     "cat": "Salud Física",     "pts": 2, "ec": 0, "tier": "micro"},
    "gymbook":          {"label": "GymBook",                         "cat": "Salud Física",     "pts": 2, "ec": 0, "tier": "micro"},

    # ── HEGEMONIKON — Salud Base ──────────────────────────────────────────────
    "colacion":         {"label": "Colación saludable",              "cat": "Salud Base",       "pts": 1, "ec": 0, "tier": "micro"},
    "jugo_verde":       {"label": "Jugo verde",                      "cat": "Salud Base",       "pts": 2, "ec": 0, "tier": "micro"},
    "comer_fruta":      {"label": "Comer fruta",                     "cat": "Salud Base",       "pts": 1, "ec": 0, "tier": "micro"},
    "dormir_8h":        {"label": "Dormir 8 horas",                  "cat": "Salud Base",       "pts": 2, "ec": 0, "tier": "micro"},
    "skincare_noche":   {"label": "Skin Care nocturno",              "cat": "Salud Base",       "pts": 2, "ec": 0, "tier": "micro"},

    # ── EURYTHMIA — Baile ─────────────────────────────────────────────────────
    # Estos dos keys son escritos automáticamente por modules/eurythmia (sesión
    # guiada real) — "hidden" los oculta del checklist manual de Acta Diurna
    # para evitar doble-entry; ver modules/eurythmia/routes.py.
    "eurythmia_session": {"label": "Sesión de práctica (EURYTHMIA)",  "cat": "Baile",            "pts": 20, "ec": 1, "tier": "alto",     "hidden": True},
    "eurythmia_grabado":  {"label": "Grabé mi práctica de baile",     "cat": "Baile",            "pts": 3,  "ec": 1, "tier": "progreso", "hidden": True},

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
    "llegar_puntual":   {"label": "Llegar Puntual",                  "cat": "Identidad",        "pts": 4, "ec": 1, "tier": "progreso"},

    # ── SÁBADO RESET — 7 bloques ──────────────────────────────────────────────
    "sat_bloque1":           {"label": "Bloque 1 — Mantenimiento & Recepción", "cat": "Sábado Reset", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sat"},
    "sat_gym_bloque":        {"label": "Gym — Fuerza & Hipertrofia",           "cat": "Sábado Reset", "pts": 4, "ec": 2, "tier": "alto",     "weekend": "sat"},
    "sat_textiles_bloque":   {"label": "Textiles & Cambio de Sábanas",         "cat": "Sábado Reset", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sat"},
    "sat_limpieza_bloque":   {"label": "Limpieza de Arriba a Abajo",           "cat": "Sábado Reset", "pts": 3, "ec": 1, "tier": "progreso", "weekend": "sat"},
    "sat_bano_bloque":       {"label": "Desinfección de Baño",                 "cat": "Sábado Reset", "pts": 2, "ec": 1, "tier": "progreso", "weekend": "sat"},
    "sat_barrido_bloque":    {"label": "Barrido y Trapeado General",           "cat": "Sábado Reset", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sat"},
    "sat_jugos_bloque":      {"label": "Jugos de la Semana",                   "cat": "Sábado Reset", "pts": 2, "ec": 1, "tier": "progreso", "weekend": "sat"},

    # ── DOMINGO STRATEGY — 10 bloques ────────────────────────────────────────
    "sun_cafe_bloque":        {"label": "Arranque del Día",              "cat": "Domingo Strategy", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sun"},
    "sun_gym_bloque":         {"label": "Gym — Gym Vacío de Domingo",    "cat": "Domingo Strategy", "pts": 4, "ec": 2, "tier": "alto",     "weekend": "sun"},
    "sun_nevera_bloque":      {"label": "Nevera & Despensa",             "cat": "Domingo Strategy", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sun"},
    "sun_comidas_bloque":     {"label": "Meal Prep Semanal",             "cat": "Domingo Strategy", "pts": 3, "ec": 1, "tier": "progreso", "weekend": "sun"},
    "sun_guardado_bloque":    {"label": "Guardado de Ropa",              "cat": "Domingo Strategy", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sun"},
    "sun_planchar_bloque":    {"label": "Planchado de Uniforme",         "cat": "Domingo Strategy", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sun"},
    "sun_planeacion_bloque":  {"label": "Planeación Semanal",            "cat": "Domingo Strategy", "pts": 4, "ec": 2, "tier": "alto",     "weekend": "sun"},
    "sun_prioridades_bloque": {"label": "3 Prioridades de la Semana",    "cat": "Domingo Strategy", "pts": 3, "ec": 1, "tier": "progreso", "weekend": "sun"},
    "sun_reset_bloque":       {"label": "Eudaimonia OS Reset",           "cat": "Domingo Strategy", "pts": 2, "ec": 1, "tier": "progreso", "weekend": "sun"},
    "sun_cierre_bloque":      {"label": "Cierre Semanal",                "cat": "Domingo Strategy", "pts": 0, "ec": 0, "tier": "micro",    "weekend": "sun"},
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
