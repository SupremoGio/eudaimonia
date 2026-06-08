// EUDAIMONIA — Data & Constants

// Reads a CSS custom property from :root (reactive to class changes on <html>)
function _euCssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Getter-based color object — each access reads the current CSS var so theme
// toggle is instant without location.reload()
var _euColors = {
  get gold()       { return _euCssVar('--gold'); },
  get goldLight()  { return _euCssVar('--gold-l'); },
  get goldBg()     { return _euCssVar('--gold-bg'); },
  get goldBorder() { return _euCssVar('--gold-border'); },
  get goldGlow()   { return _euCssVar('--gold-glow'); },
  get bg()         { return _euCssVar('--bg'); },
  get deep()       { return _euCssVar('--bg'); },
  get card()       { return _euCssVar('--card'); },
  get card2()      { return _euCssVar('--card2'); },
  get surface()    { return _euCssVar('--surf'); },
  get text()       { return _euCssVar('--text'); },
  get textSub()    { return _euCssVar('--mid'); },
  get textMuted()  { return _euCssVar('--dim'); },
  get emerald()    { return _euCssVar('--emerald'); },
  get amber()      { return _euCssVar('--amber'); },
  get coral()      { return _euCssVar('--coral'); },
  get violet()     { return _euCssVar('--violet'); },
  get cyan()       { return _euCssVar('--cyan'); },
};

window.EU = {
  colors: _euColors,

  getColors: function() { return _euColors; },

  rgba: function(key, alpha) {
    var val = _euColors[key] || key;
    if (val && val[0] === '#') {
      var r = parseInt(val.slice(1,3),16);
      var g = parseInt(val.slice(3,5),16);
      var b = parseInt(val.slice(5,7),16);
      return 'rgba('+r+','+g+','+b+','+alpha+')';
    }
    return val;
  },

  // Theme-aware oklch tints for per-hue module cards
  catTint: function(hue, kind) {
    var light = document.documentElement.classList.contains('light');
    var p = {
      dark:  { bg:'oklch(18% 0.04 '+hue+')', border:'oklch(35% 0.09 '+hue+')', text:'oklch(65% 0.15 '+hue+')' },
      light: { bg:'oklch(93% 0.04 '+hue+')', border:'oklch(70% 0.10 '+hue+')', text:'oklch(40% 0.18 '+hue+')' },
    };
    return p[light ? 'light' : 'dark'][kind];
  },

  // Must match LEVEL_THRESHOLDS in engine.py exactly
  levelThresholds: [0, 300, 900, 1800, 3000, 4200, 5000, 5600, 6000, 6500],

  levels: [
    { n:1,  name:'PROKOPTON',  sub:'El que avanza — iniciaste el camino',          xpNext:300  },
    { n:2,  name:'EFEBO',      sub:'El joven — forjando disciplina',               xpNext:600  },
    { n:3,  name:'ASQUETÉS',   sub:'El asceta — probando el esfuerzo',             xpNext:900  },
    { n:4,  name:'ESTRATEGOS', sub:'El estratega — ejecutando con intención',      xpNext:1200 },
    { n:5,  name:'AUTARKÉS',   sub:'El autosuficiente — dueño de ti mismo',        xpNext:1200 },
    { n:6,  name:'POLÍMATA',   sub:'El polímata — crecimiento en todas virtudes',  xpNext:800  },
    { n:7,  name:'ARETÉ',      sub:'La excelencia — viviendo con areté',           xpNext:600  },
    { n:8,  name:'HEGEMÓN',    sub:'El rector — guiando desde dentro',             xpNext:400  },
    { n:9,  name:'SOPHOS',     sub:'El sabio — equilibrio y maestría',             xpNext:500  },
    { n:10, name:'EUDAIMÓN',   sub:'La eudaimonía — vida floreciente plena',       xpNext:null },
  ],

  // Default modules — streak/done are overridden by server data at runtime
  modules: [
    { id:'hegemonikon',    name:'HEGEMONIKON',    concept:'Bienestar',      desc:'Salud · Nutrición · Perfil',  hue:45,  route:'/actividades', streak:0, done:false },
    { id:'oikonomia',      name:'OIKONOMIA',      concept:'Finanzas',       desc:'Finanzas · Gastos · Deudas',  hue:80,  route:'/finanzas',    streak:0, done:false },
    { id:'ataraxia',       name:'ATARAXIA',       concept:'Productividad',  desc:'Automatización · Checklist',  hue:155, route:'/ataraxia',    streak:0, done:false },
    { id:'paideia',        name:'PAIDEIA',        concept:'Conocimiento',   desc:'Aprendizaje · Libros',        hue:265, route:'/actividades', streak:0, done:false },
    { id:'cosmopolitismo', name:'COSMOPOLITISMO', concept:'Idiomas',        desc:'Idiomas · Culturas',          hue:215, route:'/idiomas',     streak:0, done:false },
    { id:'logoi',          name:'LOGOI',          concept:'Programación',   desc:'Programación · Lógica',       hue:120, route:'/actividades', streak:0, done:false },
    { id:'eurythmia',      name:'EURYTHMIA',      concept:'Baile',          desc:'Baile · Ritmo · Cuerpo',      hue:330, route:'/actividades', streak:0, done:false },
  ],

  quotes: [
    { text:'Busca dentro. Dentro está la fuente del bien, y siempre brotará, si siempre cavas.', author:'Marco Aurelio · Meditaciones VII' },
    { text:'No turbará tu mente lo que te acontece desde fuera; pues depende solo de tus juicios.', author:'Marco Aurelio · Meditaciones IV' },
    { text:'La felicidad de tu vida depende de la calidad de tus pensamientos.', author:'Marco Aurelio · Meditaciones V' },
    { text:'Soporta y abstente: ese es el doble mandato de la filosofía estoica.', author:'Epicteto · Enquiridión' },
    { text:'Pierde el tiempo el que mide el tiempo; aprovéchalo el que lo vive.', author:'Séneca · Cartas a Lucilio' },
    { text:'Vive conforme a la naturaleza; en eso reside la virtud y la felicidad.', author:'Zenón de Citio' },
    { text:'Haz cada acto de tu vida como si fuera el último.', author:'Marco Aurelio · Meditaciones II' },
  ],

  moduleHabits: {
    hegemonikon:    [
      { label:'Registrar comidas del día',     xp:10, done:true  },
      { label:'Pesar en ayunas',               xp:5,  done:true  },
      { label:'8,000 pasos mínimo',            xp:15, done:false },
      { label:'Dormir antes de las 11pm',      xp:20, done:false },
    ],
    oikonomia:     [
      { label:'Registrar todos los gastos',    xp:10, done:false },
      { label:'Revisar balance de cuentas',    xp:5,  done:false },
      { label:'Cero gastos impulsivos hoy',    xp:25, done:false },
    ],
    ataraxia:      [
      { label:'Completar checklist de mañana', xp:20, done:true  },
      { label:'Inbox GTD a cero',              xp:15, done:false },
      { label:'Revisión semanal realizada',    xp:30, done:false },
    ],
    paideia:       [
      { label:'Leer 30 minutos',               xp:20, done:false },
      { label:'Tomar notas de lo leído',       xp:10, done:false },
      { label:'Aplicar concepto aprendido',    xp:25, done:false },
    ],
    cosmopolitismo:[
      { label:'Lección de idioma (app)',       xp:15, done:true  },
      { label:'Podcast en el idioma meta',     xp:10, done:false },
      { label:'Escribir 5 oraciones nuevas',   xp:20, done:true  },
    ],
    logoi:         [
      { label:'Resolver ejercicio de código',  xp:20, done:false },
      { label:'Avanzar en proyecto personal',  xp:25, done:false },
      { label:'Leer artículo técnico',         xp:10, done:false },
    ],
    eurythmia:     [
      { label:'Práctica de baile 30 min',      xp:25, done:false },
      { label:'Aprender nuevo paso/figura',    xp:20, done:false },
      { label:'Analizar música nueva',         xp:10, done:false },
    ],
  },

  gtd: {
    inbox: [
      { id:1, text:'Revisar balances de inversiones Q1',        context:'@finanzas' },
      { id:2, text:'Practicar 30 min vocabulario alemán',        context:'@idiomas'  },
      { id:3, text:'Leer capítulo 5 de Meditaciones',           context:'@lectura'  },
      { id:4, text:'Configurar automatización de presupuesto',   context:'@logoi'    },
      { id:5, text:'Revisar deuda con tarjeta de crédito',      context:'@finanzas' },
    ],
    projects: [
      { id:'p1', name:'Autarquía Financiera 2026',         actions:12, done:3  },
      { id:'p2', name:'Alemán B2 — Mayo',                  actions:8,  done:5  },
      { id:'p3', name:'Sistema de Automatización Personal', actions:15, done:7  },
      { id:'p4', name:'Repertorio de Baile Q2',            actions:6,  done:1  },
      { id:'p5', name:'Lectura Filosofía Estoica',         actions:10, done:6  },
    ],
    contexts: ['@finanzas','@idiomas','@lectura','@logoi','@cuerpo','@reflexión','@sistema','@energía'],
    review: [
      { label:'Vaciar inbox completamente',               done:true  },
      { label:'Revisar lista "Siguiente acción"',         done:true  },
      { label:'Revisar proyectos activos',                done:false },
      { label:'Revisar contextos',                        done:false },
      { label:'Revisar "Algún día / quizás"',             done:false },
      { label:'Revisar compromisos del calendario',       done:false },
      { label:'Procesar papel y notas físicas',           done:false },
    ],
  },
};

// useTheme hook — re-renders React component when <html> class toggles
function useTheme() {
  var _useState = React.useState(function() {
    return document.documentElement.classList.contains('light');
  });
  var isLight = _useState[0];
  var setIsLight = _useState[1];
  React.useEffect(function() {
    var observer = new MutationObserver(function() {
      setIsLight(document.documentElement.classList.contains('light'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return function() { observer.disconnect(); };
  }, []);
  return { isLight: isLight, isDark: !isLight };
}
Object.assign(window, { useTheme: useTheme });

// Override with server-injected data when Flask serves this
;(function () {
  var d = window.__EUDAIMONIA_DATA__;
  if (!d) return;

  // Módulos con streak y done reales
  if (Array.isArray(d.modules))   window.EU.modules   = d.modules;

  // GTD inbox real
  if (Array.isArray(d.gtd_inbox)) window.EU.gtd.inbox = d.gtd_inbox;

  // Hábitos done reales (basados en activity_logs de hoy)
  if (d.habits_done) {
    Object.keys(d.habits_done).forEach(function(modId) {
      var doneList = d.habits_done[modId];
      if (window.EU.moduleHabits[modId]) {
        window.EU.moduleHabits[modId] = window.EU.moduleHabits[modId].map(function(h, i) {
          return Object.assign({}, h, { done: doneList[i] !== undefined ? doneList[i] : h.done });
        });
      }
    });
  }

  // Datos reales disponibles globalmente para los screens
  window.EU._server = {
    financial:  d.financial   || {},
    body:       d.body        || {},
    langStats:  d.lang_stats  || [],
    xpToday:    d.xp_today    || 0,
    activities: d.activities  || [],
    actCats:    d.act_cats    || [],
    pts: {
      today: d.pts_today || 0,
      week:  d.pts_week  || 0,
      month: d.pts_month || 0,
    },
    streak:    d.streak    || 0,
    word:      d.word_of_day || null,
    reflexion: d.reflexion   || null,
    reminders:  d.reminders   || [],
    ecBalance:      d.ec_balance      || 0,
    deadlines:      d.deadlines       || [],
    classification: d.classification  || null,
    suggestion:     d.suggestion      || null,
  };
  window.EU.catHues = d.category_hues || {};
})();
