// EUDAIMONIA — Data & Constants

// Reads a CSS custom property from :root (reactive to class changes on <html>)
function _euCssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Getter-based color object — each access reads the current CSS var so theme
// toggle is instant without location.reload()
var _euColors = {
  get gold() {
    return _euCssVar('--gold');
  },
  get goldLight() {
    return _euCssVar('--gold-l');
  },
  get goldBg() {
    return _euCssVar('--gold-bg');
  },
  get goldBorder() {
    return _euCssVar('--gold-border');
  },
  get goldGlow() {
    return _euCssVar('--gold-glow');
  },
  get bg() {
    return _euCssVar('--bg');
  },
  get deep() {
    return _euCssVar('--bg');
  },
  get card() {
    return _euCssVar('--card');
  },
  get card2() {
    return _euCssVar('--card2');
  },
  get surface() {
    return _euCssVar('--surf');
  },
  get text() {
    return _euCssVar('--text');
  },
  get textSub() {
    return _euCssVar('--mid');
  },
  get textMuted() {
    return _euCssVar('--dim');
  },
  get emerald() {
    return _euCssVar('--emerald');
  },
  get amber() {
    return _euCssVar('--amber');
  },
  get coral() {
    return _euCssVar('--coral');
  },
  get violet() {
    return _euCssVar('--violet');
  },
  get cyan() {
    return _euCssVar('--cyan');
  }
};
window.EU = {
  colors: _euColors,
  getColors: function () {
    return _euColors;
  },
  rgba: function (key, alpha) {
    var val = _euColors[key] || key;
    if (val && val[0] === '#') {
      var r = parseInt(val.slice(1, 3), 16);
      var g = parseInt(val.slice(3, 5), 16);
      var b = parseInt(val.slice(5, 7), 16);
      return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }
    return val;
  },
  // Theme-aware oklch tints for per-hue module cards
  catTint: function (hue, kind) {
    var light = document.documentElement.classList.contains('light');
    var p = {
      dark: {
        bg: 'oklch(18% 0.04 ' + hue + ')',
        border: 'oklch(35% 0.09 ' + hue + ')',
        text: 'oklch(65% 0.15 ' + hue + ')'
      },
      light: {
        bg: 'oklch(93% 0.04 ' + hue + ')',
        border: 'oklch(70% 0.10 ' + hue + ')',
        text: 'oklch(40% 0.18 ' + hue + ')'
      }
    };
    return p[light ? 'light' : 'dark'][kind];
  },
  // Must match LEVEL_THRESHOLDS in engine.py exactly
  levelThresholds: [0, 300, 900, 1800, 3000, 4200, 5000, 5600, 6000, 6500],
  levels: [{
    n: 1,
    name: 'PROKOPTON',
    sub: 'El que avanza — iniciaste el camino',
    xpNext: 300
  }, {
    n: 2,
    name: 'EFEBO',
    sub: 'El joven — forjando disciplina',
    xpNext: 600
  }, {
    n: 3,
    name: 'ASQUETÉS',
    sub: 'El asceta — probando el esfuerzo',
    xpNext: 900
  }, {
    n: 4,
    name: 'ESTRATEGOS',
    sub: 'El estratega — ejecutando con intención',
    xpNext: 1200
  }, {
    n: 5,
    name: 'AUTARKÉS',
    sub: 'El autosuficiente — dueño de ti mismo',
    xpNext: 1200
  }, {
    n: 6,
    name: 'POLÍMATA',
    sub: 'El polímata — crecimiento en todas virtudes',
    xpNext: 800
  }, {
    n: 7,
    name: 'ARETÉ',
    sub: 'La excelencia — viviendo con areté',
    xpNext: 600
  }, {
    n: 8,
    name: 'HEGEMÓN',
    sub: 'El rector — guiando desde dentro',
    xpNext: 400
  }, {
    n: 9,
    name: 'SOPHOS',
    sub: 'El sabio — equilibrio y maestría',
    xpNext: 500
  }, {
    n: 10,
    name: 'EUDAIMÓN',
    sub: 'La eudaimonía — vida floreciente plena',
    xpNext: null
  }],
  // Default modules — streak/done are overridden by server data at runtime
  modules: [{
    id: 'hegemonikon',
    name: 'HEGEMONIKON',
    concept: 'Bienestar',
    desc: 'Salud · Nutrición · Perfil',
    hue: 45,
    streak: 0,
    done: false
  }, {
    id: 'oikonomia',
    name: 'OIKONOMIA',
    concept: 'Finanzas',
    desc: 'Finanzas · Gastos · Deudas',
    hue: 80,
    route: '/finanzas',
    streak: 0,
    done: false
  }, {
    id: 'ataraxia',
    name: 'ATARAXIA',
    concept: 'Productividad',
    desc: 'Automatización · Checklist',
    hue: 155,
    streak: 0,
    done: false
  }, {
    id: 'paideia',
    name: 'PAIDEIA',
    concept: 'Conocimiento',
    desc: 'Aprendizaje · Libros',
    hue: 265,
    streak: 0,
    done: false
  }, {
    id: 'cosmopolitismo',
    name: 'COSMOPOLITISMO',
    concept: 'Idiomas',
    desc: 'Idiomas · Culturas',
    hue: 215,
    streak: 0,
    done: false
  }, {
    id: 'logoi',
    name: 'LOGOI',
    concept: 'Programación',
    desc: 'Programación · Lógica',
    hue: 120,
    streak: 0,
    done: false
  }, {
    id: 'eurythmia',
    name: 'EURYTHMIA',
    concept: 'Baile',
    desc: 'Baile · Ritmo · Cuerpo',
    hue: 330,
    streak: 0,
    done: false
  }],
  quotes: [{
    text: 'Busca dentro. Dentro está la fuente del bien, y siempre brotará, si siempre cavas.',
    author: 'Marco Aurelio · Meditaciones VII'
  }, {
    text: 'No turbará tu mente lo que te acontece desde fuera; pues depende solo de tus juicios.',
    author: 'Marco Aurelio · Meditaciones IV'
  }, {
    text: 'La felicidad de tu vida depende de la calidad de tus pensamientos.',
    author: 'Marco Aurelio · Meditaciones V'
  }, {
    text: 'Soporta y abstente: ese es el doble mandato de la filosofía estoica.',
    author: 'Epicteto · Enquiridión'
  }, {
    text: 'Pierde el tiempo el que mide el tiempo; aprovéchalo el que lo vive.',
    author: 'Séneca · Cartas a Lucilio'
  }, {
    text: 'Vive conforme a la naturaleza; en eso reside la virtud y la felicidad.',
    author: 'Zenón de Citio'
  }, {
    text: 'Haz cada acto de tu vida como si fuera el último.',
    author: 'Marco Aurelio · Meditaciones II'
  }],
  moduleHabits: {
    hegemonikon: [{
      label: 'Registrar comidas del día',
      xp: 10,
      done: true
    }, {
      label: 'Pesar en ayunas',
      xp: 5,
      done: true
    }, {
      label: '8,000 pasos mínimo',
      xp: 15,
      done: false
    }, {
      label: 'Dormir antes de las 11pm',
      xp: 20,
      done: false
    }],
    oikonomia: [{
      label: 'Registrar todos los gastos',
      xp: 10,
      done: false
    }, {
      label: 'Revisar balance de cuentas',
      xp: 5,
      done: false
    }, {
      label: 'Cero gastos impulsivos hoy',
      xp: 25,
      done: false
    }],
    ataraxia: [{
      label: 'Completar checklist de mañana',
      xp: 20,
      done: true
    }, {
      label: 'Inbox GTD a cero',
      xp: 15,
      done: false
    }, {
      label: 'Revisión semanal realizada',
      xp: 30,
      done: false
    }],
    paideia: [{
      label: 'Leer 30 minutos',
      xp: 20,
      done: false
    }, {
      label: 'Tomar notas de lo leído',
      xp: 10,
      done: false
    }, {
      label: 'Aplicar concepto aprendido',
      xp: 25,
      done: false
    }],
    cosmopolitismo: [{
      label: 'Lección de idioma (app)',
      xp: 15,
      done: true
    }, {
      label: 'Podcast en el idioma meta',
      xp: 10,
      done: false
    }, {
      label: 'Escribir 5 oraciones nuevas',
      xp: 20,
      done: true
    }],
    logoi: [{
      label: 'Resolver ejercicio de código',
      xp: 20,
      done: false
    }, {
      label: 'Avanzar en proyecto personal',
      xp: 25,
      done: false
    }, {
      label: 'Leer artículo técnico',
      xp: 10,
      done: false
    }],
    eurythmia: [{
      label: 'Práctica de baile 30 min',
      xp: 25,
      done: false
    }, {
      label: 'Aprender nuevo paso/figura',
      xp: 20,
      done: false
    }, {
      label: 'Analizar música nueva',
      xp: 10,
      done: false
    }]
  },
  gtd: {
    inbox: [{
      id: 1,
      text: 'Revisar balances de inversiones Q1',
      context: '@finanzas'
    }, {
      id: 2,
      text: 'Practicar 30 min vocabulario alemán',
      context: '@idiomas'
    }, {
      id: 3,
      text: 'Leer capítulo 5 de Meditaciones',
      context: '@lectura'
    }, {
      id: 4,
      text: 'Configurar automatización de presupuesto',
      context: '@logoi'
    }, {
      id: 5,
      text: 'Revisar deuda con tarjeta de crédito',
      context: '@finanzas'
    }],
    projects: [{
      id: 'p1',
      name: 'Autarquía Financiera 2026',
      actions: 12,
      done: 3
    }, {
      id: 'p2',
      name: 'Alemán B2 — Mayo',
      actions: 8,
      done: 5
    }, {
      id: 'p3',
      name: 'Sistema de Automatización Personal',
      actions: 15,
      done: 7
    }, {
      id: 'p4',
      name: 'Repertorio de Baile Q2',
      actions: 6,
      done: 1
    }, {
      id: 'p5',
      name: 'Lectura Filosofía Estoica',
      actions: 10,
      done: 6
    }],
    contexts: ['@finanzas', '@idiomas', '@lectura', '@logoi', '@cuerpo', '@reflexión', '@sistema', '@energía'],
    review: [{
      label: 'Vaciar inbox completamente',
      done: true
    }, {
      label: 'Revisar lista "Siguiente acción"',
      done: true
    }, {
      label: 'Revisar proyectos activos',
      done: false
    }, {
      label: 'Revisar contextos',
      done: false
    }, {
      label: 'Revisar "Algún día / quizás"',
      done: false
    }, {
      label: 'Revisar compromisos del calendario',
      done: false
    }, {
      label: 'Procesar papel y notas físicas',
      done: false
    }]
  }
};

// useTheme hook — re-renders React component when <html> class toggles
function useTheme() {
  var _useState = React.useState(function () {
    return document.documentElement.classList.contains('light');
  });
  var isLight = _useState[0];
  var setIsLight = _useState[1];
  React.useEffect(function () {
    var observer = new MutationObserver(function () {
      setIsLight(document.documentElement.classList.contains('light'));
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    });
    return function () {
      observer.disconnect();
    };
  }, []);
  return {
    isLight: isLight,
    isDark: !isLight
  };
}
Object.assign(window, {
  useTheme: useTheme
});

// Override with server-injected data when Flask serves this
;
(function () {
  var d = window.__EUDAIMONIA_DATA__;
  if (!d) return;

  // Módulos con streak y done reales
  if (Array.isArray(d.modules)) window.EU.modules = d.modules;

  // GTD inbox real
  if (Array.isArray(d.gtd_inbox)) window.EU.gtd.inbox = d.gtd_inbox;

  // Hábitos done reales (basados en activity_logs de hoy)
  if (d.habits_done) {
    Object.keys(d.habits_done).forEach(function (modId) {
      var doneList = d.habits_done[modId];
      if (window.EU.moduleHabits[modId]) {
        window.EU.moduleHabits[modId] = window.EU.moduleHabits[modId].map(function (h, i) {
          return Object.assign({}, h, {
            done: doneList[i] !== undefined ? doneList[i] : h.done
          });
        });
      }
    });
  }

  // Datos reales disponibles globalmente para los screens
  window.EU._server = {
    financial: d.financial || {},
    body: d.body || {},
    langStats: d.lang_stats || [],
    xpToday: d.xp_today || 0,
    activities: d.activities || [],
    actCats: d.act_cats || [],
    pts: {
      today: d.pts_today || 0,
      week: d.pts_week || 0,
      month: d.pts_month || 0
    },
    streak: d.streak || 0,
    word: d.word_of_day || null,
    reflexion: d.reflexion || null,
    reminders: d.reminders || [],
    ecBalance: d.ec_balance || 0,
    deadlines: d.deadlines || [],
    classification: d.classification || null,
    suggestion: d.suggestion || null
  };
  window.EU.catHues = d.category_hues || {};
})();
// EUDAIMONIA — UI Primitives
const {
  useState,
  useEffect,
  useMemo,
  useRef,
  useReducer,
  useCallback
} = React;
const C = window.EU.getColors();

// ─── Greek Column XP Visualizer ────────────────────────────
function GreekColumn({
  level = 3,
  xpPct = 0.65,
  size = 110
}) {
  const totalDrums = 10;
  const h = size * 1.4;
  const cx = size / 2;
  const baseShaftW = size * 0.26;
  const shaftTop = h * 0.07;
  const shaftBot = h * 0.80;
  const shaftH = shaftBot - shaftTop;
  const drumH = shaftH / totalDrums;
  const capW = size * 0.42;
  const baseW = size * 0.50;
  const uid = `col${size}${level}`;
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: h,
    viewBox: `0 0 ${size} ${h}`,
    style: {
      overflow: 'visible'
    }
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: `gg${uid}`,
    x1: "0",
    y1: "1",
    x2: "0",
    y2: "0"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    style: {
      stopColor: 'color-mix(in srgb, var(--gold) 60%, #000)'
    }
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "50%",
    style: {
      stopColor: 'var(--gold)'
    }
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "100%",
    style: {
      stopColor: 'var(--gold-l)'
    }
  })), /*#__PURE__*/React.createElement("linearGradient", {
    id: `gd${uid}`,
    x1: "0",
    y1: "0",
    x2: "0",
    y2: "1"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    style: {
      stopColor: 'var(--surf)'
    }
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "100%",
    style: {
      stopColor: 'var(--bg)'
    }
  })), /*#__PURE__*/React.createElement("filter", {
    id: `glow${uid}`,
    x: "-60%",
    y: "-60%",
    width: "220%",
    height: "220%"
  }, /*#__PURE__*/React.createElement("feGaussianBlur", {
    stdDeviation: "5",
    result: "b"
  }), /*#__PURE__*/React.createElement("feMerge", null, /*#__PURE__*/React.createElement("feMergeNode", {
    in: "b"
  }), /*#__PURE__*/React.createElement("feMergeNode", {
    in: "SourceGraphic"
  }))), /*#__PURE__*/React.createElement("filter", {
    id: `sglow${uid}`,
    x: "-30%",
    y: "-30%",
    width: "160%",
    height: "160%"
  }, /*#__PURE__*/React.createElement("feGaussianBlur", {
    stdDeviation: "2.5",
    result: "b"
  }), /*#__PURE__*/React.createElement("feMerge", null, /*#__PURE__*/React.createElement("feMergeNode", {
    in: "b"
  }), /*#__PURE__*/React.createElement("feMergeNode", {
    in: "SourceGraphic"
  })))), Array.from({
    length: totalDrums
  }).map((_, i) => {
    const fromBottom = totalDrums - 1 - i;
    const filled = fromBottom < level;
    const isCurrent = fromBottom === level - 1;
    // Entasis (slight column bulge)
    const entasis = 1 + Math.sin(Math.PI * ((fromBottom + 0.5) / totalDrums)) * 0.14;
    const w = baseShaftW * entasis;
    const y = shaftTop + i * drumH;
    return /*#__PURE__*/React.createElement("g", {
      key: i
    }, /*#__PURE__*/React.createElement("rect", {
      x: cx - w / 2,
      y: y + 0.5,
      width: w,
      height: drumH - 1,
      rx: 0.8,
      fill: filled ? `url(#gg${uid})` : `url(#gd${uid})`,
      stroke: filled ? 'var(--gold-glow)' : 'color-mix(in srgb, var(--gold) 6%, transparent)',
      strokeWidth: 0.5,
      filter: isCurrent ? `url(#sglow${uid})` : undefined
    }), [0.28, 0.5, 0.72].map((fx, fi) => /*#__PURE__*/React.createElement("line", {
      key: fi,
      x1: cx - w / 2 + w * fx,
      y1: y + 1.5,
      x2: cx - w / 2 + w * fx,
      y2: y + drumH - 1.5,
      stroke: filled ? 'rgba(255,210,80,0.1)' : 'rgba(255,255,255,0.025)',
      strokeWidth: 0.5
    })), isCurrent && xpPct > 0 && /*#__PURE__*/React.createElement("rect", {
      x: cx - w / 2 + 0.5,
      y: y + 0.5,
      width: (w - 1) * xpPct,
      height: drumH - 1,
      rx: 0.8,
      fill: "rgba(240,216,128,0.5)"
    }));
  }), /*#__PURE__*/React.createElement("ellipse", {
    cx: cx,
    cy: shaftTop + 1.5,
    rx: baseShaftW * 0.75,
    ry: 3,
    fill: `url(#gg${uid})`,
    opacity: 0.45
  }), /*#__PURE__*/React.createElement("rect", {
    x: cx - capW / 2,
    y: shaftTop - h * 0.045,
    width: capW,
    height: h * 0.045,
    rx: 1,
    fill: level >= 10 ? `url(#gg${uid})` : '#1C1829',
    stroke: "color-mix(in srgb, var(--gold) 25%, transparent)",
    strokeWidth: 0.5
  }), /*#__PURE__*/React.createElement("rect", {
    x: cx - capW * 0.56,
    y: shaftTop - h * 0.06,
    width: capW * 1.12,
    height: h * 0.014,
    rx: 0.5,
    fill: "#191525",
    stroke: "var(--b)",
    strokeWidth: 0.5
  }), /*#__PURE__*/React.createElement("rect", {
    x: cx - baseShaftW * 0.65,
    y: shaftBot,
    width: baseShaftW * 1.3,
    height: h * 0.03,
    rx: 1,
    fill: "#1E1B2A",
    stroke: "var(--b)",
    strokeWidth: 0.5
  }), /*#__PURE__*/React.createElement("rect", {
    x: cx - baseW * 0.5,
    y: shaftBot + h * 0.031,
    width: baseW,
    height: h * 0.038,
    rx: 1,
    fill: "#1A1726",
    stroke: "var(--gold-bg)",
    strokeWidth: 0.5
  }), /*#__PURE__*/React.createElement("rect", {
    x: cx - baseW * 0.62,
    y: shaftBot + h * 0.069,
    width: baseW * 1.24,
    height: h * 0.038,
    rx: 1,
    fill: "#181524",
    stroke: "var(--gold-bg)",
    strokeWidth: 0.5
  }));
}

// ─── Progress Ring ──────────────────────────────────────────
function ProgressRing({
  pct = 0,
  size = 44,
  stroke = 3,
  color = C.gold
}) {
  const r = (size - stroke * 2) / 2;
  const circ = 2 * Math.PI * r;
  const cx = size / 2;
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    style: {
      display: 'block'
    }
  }, /*#__PURE__*/React.createElement("circle", {
    cx: cx,
    cy: cx,
    r: r,
    fill: "none",
    stroke: "color-mix(in srgb, var(--gold) 7%, transparent)",
    strokeWidth: stroke
  }), /*#__PURE__*/React.createElement("circle", {
    cx: cx,
    cy: cx,
    r: r,
    fill: "none",
    stroke: color,
    strokeWidth: stroke,
    strokeDasharray: `${circ * Math.min(1, pct)} ${circ}`,
    strokeLinecap: "round",
    transform: `rotate(-90 ${cx} ${cx})`,
    style: {
      transition: 'stroke-dasharray 0.8s ease'
    }
  }));
}

// ─── Module Card ───────────────────────────────────────────
function ModuleCard({
  mod,
  onClick,
  small = false
}) {
  const {
    isLight
  } = useTheme();
  const [hov, setHov] = useState(false);
  const acc = EU.catTint(mod.hue, 'text');
  const accBg = EU.catTint(mod.hue, 'bg');
  const accBorder = EU.catTint(mod.hue, 'border');
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHov(true),
    onMouseLeave: () => setHov(false),
    style: {
      background: hov ? C.cardHover : C.card,
      border: `1px solid ${hov ? accBorder : C.goldBorder}`,
      borderRadius: 14,
      padding: small ? '12px 14px' : '16px 15px',
      cursor: 'pointer',
      position: 'relative',
      overflow: 'hidden',
      transition: 'all 0.25s ease',
      boxShadow: hov ? `0 8px 32px rgba(0,0,0,0.45), 0 0 24px ${accBg}` : '0 2px 14px rgba(0,0,0,0.32)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      right: 0,
      width: 70,
      height: 70,
      background: `radial-gradient(circle at top right, ${accBg}, transparent 70%)`,
      pointerEvents: 'none'
    }
  }), mod.done && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 11,
      left: 12,
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: C.success,
      boxShadow: `0 0 7px ${C.success}`
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 10,
      right: 12,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: acc,
      opacity: 0.75,
      letterSpacing: '0.05em'
    }
  }, mod.streak, "d ◆"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: small ? 13 : 15,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.08em',
      marginTop: small ? 0 : 2
    }
  }, mod.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: acc,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 3,
      lineHeight: 1.3
    }
  }, mod.concept), !small && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      color: C.textMuted,
      marginTop: 6
    }
  }, mod.desc));
}

// ─── Habit Row ────────────────────────────────────────────
function HabitRow({
  label,
  done,
  onToggle,
  xp = 10,
  accent = C.gold
}) {
  const [burst, setBurst] = useState(false);
  const handle = () => {
    if (!done) {
      setBurst(true);
      setTimeout(() => setBurst(false), 700);
    }
    onToggle();
  };
  const dirs = [[28, -28], [38, 0], [28, 28], [0, 38], [-28, 28], [-38, 0], [-28, -28], [0, -38]];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '11px 0',
      borderBottom: '1px solid color-mix(in srgb, var(--gold) 6%, transparent)',
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: handle,
    style: {
      width: 22,
      height: 22,
      borderRadius: 6,
      flexShrink: 0,
      cursor: 'pointer',
      border: `1.5px solid ${done ? accent : 'color-mix(in srgb, var(--gold) 22%, transparent)'}`,
      background: done ? accent : 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.2s',
      boxShadow: done ? `0 0 10px ${accent}55` : 'none'
    }
  }, done && /*#__PURE__*/React.createElement("svg", {
    width: 11,
    height: 11,
    viewBox: "0 0 11 11"
  }, /*#__PURE__*/React.createElement("polyline", {
    points: "2,5.5 4.5,8.5 9,2.5",
    stroke: "#09070F",
    strokeWidth: 1.8,
    fill: "none",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }))), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: done ? C.textMuted : C.text,
      textDecoration: done ? 'line-through' : 'none',
      transition: 'all 0.3s'
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted
    }
  }, "+", xp, " XP"), burst && dirs.map(([dx, dy], i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      position: 'absolute',
      left: 11,
      top: '50%',
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: `oklch(75% 0.18 ${45 + i * 20})`,
      transform: `translate(${dx}px,${dy - 10}px)`,
      opacity: 0,
      animation: `euBurst 0.65s ease-out forwards`,
      animationDelay: `${i * 0.02}s`,
      pointerEvents: 'none'
    }
  })));
}

// ─── Quote Display ────────────────────────────────────────
function QuoteDisplay({
  quote
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '18px 18px 16px',
      background: 'color-mix(in srgb, var(--gold) 4%, transparent)',
      border: '1px solid var(--gold-bg)',
      borderLeft: '3px solid var(--gold-glow)',
      borderRadius: '0 10px 10px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 16,
      lineHeight: 1.6,
      color: C.text,
      marginBottom: 10,
      textWrap: 'pretty'
    }
  }, "\"", quote.text, "\""), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.12em',
      color: C.gold,
      textTransform: 'uppercase',
      opacity: 0.75
    }
  }, "— ", quote.author));
}

// ─── Bottom Nav ───────────────────────────────────────────
function BottomNav({
  active,
  onChange
}) {
  const tabs = [{
    id: 'home',
    label: 'Ἀρχή',
    sub: 'Inicio'
  }, {
    id: 'modules',
    label: 'Κόσμος',
    sub: 'Módulos'
  }, {
    id: 'acta',
    label: 'Acta',
    sub: 'Diurna'
  }, {
    id: 'profile',
    label: 'Αὐτός',
    sub: 'Perfil'
  }];
  const isLight = document.documentElement.classList.contains('light');
  const SunIcon = () => /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "4"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41 M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
  }));
  const MoonIcon = () => /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
  }));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: 0,
      left: '50%',
      transform: 'translateX(-50%)',
      width: '100%',
      maxWidth: 430,
      background: EU.rgba('deep', 0.97),
      backdropFilter: 'blur(24px)',
      borderTop: '1px solid color-mix(in srgb, var(--gold) 12%, transparent)',
      display: 'flex',
      paddingBottom: 'env(safe-area-inset-bottom,8px)',
      zIndex: 200
    }
  }, tabs.map(t => /*#__PURE__*/React.createElement("div", {
    key: t.id,
    onClick: () => onChange(t.id),
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '10px 4px 6px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 18,
      color: active === t.id ? C.gold : C.textMuted,
      transition: 'all 0.25s',
      lineHeight: 1
    }
  }, t.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 3,
      color: active === t.id ? C.gold : C.textMuted,
      opacity: active === t.id ? 1 : 0.45,
      transition: 'all 0.25s'
    }
  }, t.sub), active === t.id && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 20,
      height: 2,
      borderRadius: 1,
      background: C.gold,
      marginTop: 4,
      boxShadow: `0 0 6px ${C.gold}`
    }
  }))), /*#__PURE__*/React.createElement("div", {
    onClick: () => window.euToggleTheme(),
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '10px 4px 6px',
      cursor: 'pointer',
      color: C.textMuted,
      transition: 'color 0.25s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: C.textMuted,
      lineHeight: 1,
      transition: 'all 0.25s'
    }
  }, isLight ? /*#__PURE__*/React.createElement(SunIcon, null) : /*#__PURE__*/React.createElement(MoonIcon, null)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 3,
      color: C.textMuted,
      opacity: 0.45
    }
  }, isLight ? 'Día' : 'Noche')));
}

// ─── Level Up Modal ───────────────────────────────────────
function LevelUpModal({
  level,
  onClose,
  rewards = []
}) {
  const lv = EU.levels[level - 1];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 999,
      background: EU.rgba('deep', 0.95),
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      animation: 'euFadeIn 0.5s ease'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      background: `radial-gradient(ellipse at center, var(--gold-border) 0%, transparent 60%)`,
      animation: 'euGoldPulse 2.4s ease-in-out infinite',
      pointerEvents: 'none'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      letterSpacing: '0.25em',
      color: C.gold,
      textTransform: 'uppercase',
      marginBottom: 16,
      opacity: 0.7
    }
  }, "¡SUBISTE DE NIVEL!"), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euLevelUpRise 1.2s ease-out',
      filter: 'drop-shadow(0 0 24px var(--gold-glow))'
    }
  }, /*#__PURE__*/React.createElement(GreekColumn, {
    level: level,
    xpPct: 1,
    size: 140
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      letterSpacing: '0.2em',
      color: C.gold,
      marginTop: 20,
      marginBottom: 6,
      opacity: 0.65
    }
  }, "NIVEL ", level), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 44,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.08em',
      textAlign: 'center',
      animation: 'euScaleIn 0.6s ease 0.3s both'
    }
  }, lv?.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 18,
      color: C.textSub,
      marginTop: 6,
      marginBottom: rewards.length ? 18 : 32
    }
  }, lv?.sub), rewards.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      flexWrap: 'wrap',
      justifyContent: 'center',
      marginBottom: 28,
      maxWidth: 380
    }
  }, rewards.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      padding: '6px 14px',
      background: 'var(--gold-bg)',
      border: `1px solid ${C.goldBorder}`,
      borderRadius: 100,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.gold,
      letterSpacing: '0.06em',
      animation: `euScaleIn 0.5s ease ${0.5 + i * 0.15}s both`
    }
  }, r.icon, " ", r.label))), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    style: {
      background: 'transparent',
      border: `1.5px solid var(--gold-glow)`,
      borderRadius: 10,
      padding: '12px 32px',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      letterSpacing: '0.15em',
      color: C.gold,
      cursor: 'pointer',
      textTransform: 'uppercase',
      transition: 'all 0.2s'
    }
  }, "CONTINUAR"));
}

// ─── Streak Heatmap ──────────────────────────────────────────
function StreakHeatmap({
  days = 21,
  compact = false
}) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(`/api/streak/heatmap?days=${days}`).then(r => r.json()).then(setData).catch(() => {});
  }, [days]);
  if (!data) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        height: compact ? 60 : 100,
        borderRadius: 10,
        background: 'linear-gradient(90deg,color-mix(in srgb, var(--gold) 3%, transparent) 0%,var(--gold-bg) 50%,color-mix(in srgb, var(--gold) 3%, transparent) 100%)',
        backgroundSize: '200% 100%',
        animation: 'euShimmer 1.4s ease-in-out infinite'
      }
    });
  }
  const maxXp = Math.max(...data.days.map(d => d.xp), 1);
  const cellSize = compact ? 14 : 18;
  const gap = compact ? 3 : 4;
  const cols = Math.ceil(days / 7);
  const todayStr = data.days[data.days.length - 1].date;
  const cell = xp => {
    if (xp === 0) return {
      bg: 'color-mix(in srgb, var(--gold) 4%, transparent)',
      border: C.goldBorder
    };
    const t = xp / maxXp;
    return {
      bg: `oklch(${50 + t * 25}% ${0.06 + t * 0.1} 80)`,
      border: `oklch(${55 + t * 25}% ${0.08 + t * 0.1} 80)`
    };
  };
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      letterSpacing: '0.18em',
      color: C.textMuted,
      textTransform: 'uppercase'
    }
  }, "Últimos ", days, " días"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: C.gold,
      opacity: 0.7
    }
  }, data.days.filter(d => d.xp > 0).length, " días activos")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, ${cellSize}px)`,
      gap,
      justifyContent: 'start'
    }
  }, data.days.map(d => {
    const s = cell(d.xp);
    const isToday = d.date === todayStr;
    return /*#__PURE__*/React.createElement("div", {
      key: d.date,
      title: `${d.date}: ${d.xp} XP`,
      style: {
        width: cellSize,
        height: cellSize,
        borderRadius: 4,
        background: s.bg,
        border: `1px solid ${s.border}`,
        boxShadow: isToday ? `0 0 8px ${C.gold}66` : 'none',
        transition: 'all 0.2s'
      }
    });
  })));
}

// ─── Achievement Sheet ────────────────────────────────────
function AchievementSheet({
  achievement,
  onClose
}) {
  useEffect(() => {
    const t = setTimeout(onClose, 6000);
    return () => clearTimeout(t);
  }, [onClose]);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 998,
      background: EU.rgba('deep', 0.7),
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
      animation: 'euFadeIn 0.3s ease'
    },
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      background: 'linear-gradient(180deg, #1C1830 0%, #110F20 100%)',
      border: `1px solid ${C.goldBorder}`,
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      padding: '32px 28px 40px',
      width: '100%',
      maxWidth: 460,
      animation: 'euAchievementRise 0.5s ease-out',
      boxShadow: '0 -20px 60px rgba(0,0,0,0.6)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      left: 0,
      height: 3,
      borderRadius: '24px 24px 0 0',
      background: `linear-gradient(90deg,${C.gold},${C.goldLight})`,
      animation: 'undoCountdown 6s linear forwards',
      width: '100%'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 64,
      lineHeight: 1,
      marginBottom: 14,
      filter: 'drop-shadow(0 0 16px var(--gold-glow))'
    }
  }, achievement.icon || '🏆'), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      letterSpacing: '0.22em',
      color: C.gold,
      opacity: 0.65,
      textTransform: 'uppercase',
      marginBottom: 6
    }
  }, "Logro desbloqueado"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 28,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.04em',
      marginBottom: 6
    }
  }, achievement.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 14,
      color: C.textSub,
      marginBottom: 18,
      lineHeight: 1.5
    }
  }, achievement.description), achievement.xp > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-block',
      padding: '6px 16px',
      background: 'var(--gold-bg)',
      border: `1px solid ${C.goldBorder}`,
      borderRadius: 100,
      fontSize: 13,
      color: C.gold,
      letterSpacing: '0.08em',
      marginBottom: 22
    }
  }, "+", achievement.xp, " XP"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    style: {
      background: 'transparent',
      border: `1.5px solid ${C.goldBorder}`,
      borderRadius: 10,
      padding: '10px 36px',
      fontSize: 12,
      letterSpacing: '0.15em',
      textTransform: 'uppercase',
      color: C.gold,
      cursor: 'pointer',
      transition: 'all 0.2s'
    }
  }, "Continuar")))));
}

// ─── Skeleton ──────────────────────────────────────────────
function Skeleton({
  kind = 'card',
  width,
  height,
  style
}) {
  const presets = {
    card: {
      height: 80,
      width: '100%',
      borderRadius: 12
    },
    line: {
      height: 14,
      width: '70%',
      borderRadius: 6
    },
    circle: {
      width: 44,
      height: 44,
      borderRadius: '50%'
    },
    title: {
      height: 28,
      width: '50%',
      borderRadius: 6
    }
  };
  const base = presets[kind] || presets.card;
  const s = {
    ...base,
    width: width || base.width,
    height: height || base.height,
    background: 'linear-gradient(90deg,color-mix(in srgb, var(--gold) 3%, transparent) 0%,var(--gold-bg) 50%,color-mix(in srgb, var(--gold) 3%, transparent) 100%)',
    backgroundSize: '200% 100%',
    animation: 'euShimmer 1.4s ease-in-out infinite',
    ...style
  };
  return /*#__PURE__*/React.createElement("div", {
    style: s
  });
}

// ─── EmptyState ────────────────────────────────────────────
function EmptyState({
  icon = 'inbox',
  title,
  desc,
  cta,
  kbd,
  onAction
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      padding: '48px 24px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 56,
      height: 56,
      borderRadius: 14,
      border: `1px solid ${C.goldBorder}`,
      background: C.card,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("i", {
    "data-lucide": icon,
    style: {
      width: 22,
      height: 22,
      color: C.textMuted,
      opacity: 0.6
    }
  })), title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 22,
      color: C.text,
      letterSpacing: '0.02em'
    }
  }, title), desc && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: C.textMuted,
      maxWidth: 320,
      lineHeight: 1.5
    }
  }, desc), cta && /*#__PURE__*/React.createElement("button", {
    onClick: onAction,
    style: {
      marginTop: 10,
      background: 'var(--gold-bg)',
      border: `1px solid ${C.goldBorder}`,
      borderRadius: 8,
      padding: '9px 16px',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: C.gold,
      letterSpacing: '0.06em',
      cursor: 'pointer',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8
    }
  }, cta, kbd && /*#__PURE__*/React.createElement("kbd", {
    style: {
      fontFamily: 'monospace',
      fontSize: 10,
      background: C.card2 || C.card,
      border: `1px solid ${C.goldBorder}`,
      borderRadius: 4,
      padding: '1px 6px',
      color: C.textMuted
    }
  }, kbd)));
}

// ─── PerfectDayModal ───────────────────────────────────────
function PerfectDayModal({
  details,
  onClose
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 999,
      background: 'color-mix(in srgb, var(--bg) 90%, transparent)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      animation: 'euFadeIn 0.6s ease'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      background: 'radial-gradient(ellipse at center, var(--gold-glow) 0%, transparent 65%)',
      opacity: 0.25,
      animation: 'euGoldPulse 2.4s ease-in-out infinite',
      pointerEvents: 'none'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      letterSpacing: '0.25em',
      color: 'var(--gold)',
      textTransform: 'uppercase',
      marginBottom: 18,
      opacity: 0.75
    }
  }, "✦ Día Perfecto ✦"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 54,
      fontWeight: 600,
      color: 'var(--text)',
      letterSpacing: '0.06em',
      textAlign: 'center',
      animation: 'euLevelUpRise 1.2s ease-out'
    }
  }, "Todas las virtudes"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 18,
      color: 'var(--mid)',
      marginTop: 12,
      marginBottom: 28,
      textAlign: 'center',
      maxWidth: 380,
      lineHeight: 1.5
    }
  }, "Cumpliste con cada categoría hoy."), (details.bonusXp > 0 || details.bonusEc > 0) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      marginBottom: 32
    }
  }, details.bonusXp > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 18px',
      background: 'var(--gold-bg)',
      border: '1px solid var(--gold-border)',
      borderRadius: 100,
      fontSize: 13,
      color: 'var(--gold)',
      letterSpacing: '0.08em'
    }
  }, "+", details.bonusXp, " XP bonus"), details.bonusEc > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 18px',
      background: 'var(--gold-bg)',
      border: '1px solid var(--gold-border)',
      borderRadius: 100,
      fontSize: 13,
      color: 'var(--gold)',
      letterSpacing: '0.08em'
    }
  }, "+", details.bonusEc, " EC bonus")), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    style: {
      background: 'transparent',
      border: '1.5px solid var(--gold-border)',
      borderRadius: 10,
      padding: '12px 32px',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      letterSpacing: '0.18em',
      color: 'var(--gold)',
      cursor: 'pointer',
      textTransform: 'uppercase'
    }
  }, "Continuar"));
}

// ─── ComboBonusSheet ───────────────────────────────────────
function ComboBonusSheet({
  combo,
  onClose
}) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 997,
      background: 'color-mix(in srgb, var(--bg) 60%, transparent)',
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
      animation: 'euFadeIn 0.25s ease'
    },
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      background: 'linear-gradient(180deg, var(--surf), var(--bg))',
      border: '1px solid var(--gold-border)',
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      padding: '24px 22px',
      width: '100%',
      maxWidth: 420,
      animation: 'euAchievementRise 0.4s ease-out',
      boxShadow: '0 -12px 40px color-mix(in srgb, var(--bg) 50%, black)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      height: 2,
      background: 'var(--gold)',
      borderRadius: '2px 2px 0 0',
      animation: 'undoCountdown 4s linear forwards'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 36,
      lineHeight: 1,
      filter: 'drop-shadow(0 0 12px var(--gold-glow))'
    }
  }, combo.icon || '⚡'), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      letterSpacing: '0.2em',
      color: 'var(--gold)',
      opacity: 0.7,
      textTransform: 'uppercase',
      marginBottom: 3
    }
  }, "Combo desbloqueado"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 20,
      fontWeight: 600,
      color: 'var(--text)',
      letterSpacing: '0.03em'
    }
  }, combo.name), combo.description && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: 'var(--mid)',
      marginTop: 2,
      lineHeight: 1.4
    }
  }, combo.description)), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right',
      flexShrink: 0
    }
  }, combo.xp > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      color: 'var(--gold)',
      fontWeight: 600
    }
  }, "+", combo.xp, " XP"), combo.ec > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--dim)',
      marginTop: 2
    }
  }, "+", combo.ec, " EC")))));
}
Object.assign(window, {
  GreekColumn,
  ProgressRing,
  ModuleCard,
  HabitRow,
  QuoteDisplay,
  BottomNav,
  LevelUpModal,
  StreakHeatmap,
  AchievementSheet,
  EmptyState,
  Skeleton,
  PerfectDayModal,
  ComboBonusSheet
});
// EUDAIMONIA — App State & Root
// hooks and C declared in eu-components.jsx (bundled before this file)

function _xpStateFromTotal(totalXP) {
  const thr = EU.levelThresholds; // [0,200,500,1000,1800,2700,3600,4400,5000,5500]
  let level = 1;
  for (let i = 0; i < thr.length; i++) {
    if (totalXP >= thr[i]) level = i + 1;else break;
  }
  level = Math.max(1, Math.min(10, level));
  const cur = thr[level - 1] || 0;
  const next = level < 10 ? thr[level] || 5500 : 5500;
  return {
    level,
    xp: totalXP - cur,
    xpNext: level < 10 ? next - cur : null
  };
}
function initFromServer() {
  const d = window.__EUDAIMONIA_DATA__ || {};
  const totalXP = d.total_xp || 0;
  const {
    level,
    xp,
    xpNext
  } = _xpStateFromTotal(totalXP);
  // Merge server modules (dynamic streak/done) with static route info
  const serverMods = Array.isArray(d.modules) && d.modules.length > 0 ? d.modules : null;
  const modules = serverMods ? EU.modules.map(m => {
    const s = serverMods.find(sm => sm.id === m.id);
    return s ? {
      ...m,
      streak: s.streak,
      done: s.done
    } : m;
  }) : EU.modules;
  return {
    level,
    xp,
    xpNext,
    totalXP,
    modules,
    openModuleId: null,
    leveledUp: false
  };
}
function reducer(state, action) {
  switch (action.type) {
    case 'ADD_XP':
      {
        const totalXP = state.totalXP + action.amount;
        const next = _xpStateFromTotal(totalXP);
        const leveledUp = next.level > state.level;
        return {
          ...state,
          ...next,
          totalXP,
          leveledUp
        };
      }
    case 'CLEAR_LEVELUP':
      return {
        ...state,
        leveledUp: false
      };
    case 'OPEN_MODULE':
      return {
        ...state,
        openModuleId: action.id
      };
    case 'CLOSE_MODULE':
      return {
        ...state,
        openModuleId: null
      };
    case 'SET_TAB':
      return {
        ...state,
        _tab: action.tab
      };
    default:
      return state;
  }
}

// ── Responsive hook ───────────────────────────────────────
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 768);
  useEffect(() => {
    const handler = () => setIsDesktop(window.innerWidth >= 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isDesktop;
}

// ── Desktop Sidebar Nav helpers ───────────────────────────
function NavGroup({
  title,
  children
}) {
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      letterSpacing: '0.2em',
      color: C.textMuted,
      padding: '14px 22px 6px',
      textTransform: 'uppercase',
      opacity: 0.55
    }
  }, title), children);
}
function NavItem({
  active,
  label,
  sub,
  accent,
  dot,
  onClick
}) {
  const isMod = dot !== undefined;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    style: {
      padding: '10px 22px',
      cursor: 'pointer',
      borderLeft: `2.5px solid ${active ? C.gold : 'transparent'}`,
      background: active ? 'color-mix(in srgb, var(--gold) 5%, transparent)' : 'transparent',
      transition: 'all 0.2s',
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, isMod && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      flexShrink: 0,
      background: dot ? accent || C.gold : 'var(--b)',
      boxShadow: dot ? `0 0 6px ${accent || C.gold}` : 'none'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: isMod ? 'DM Sans,sans-serif' : 'Cormorant Garamond,serif',
      fontSize: isMod ? 13 : 20,
      color: active ? C.gold : isMod ? C.text : C.textMuted,
      fontWeight: isMod ? 500 : 600,
      letterSpacing: isMod ? '0.04em' : 'inherit',
      lineHeight: 1.1,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      transition: 'color 0.2s'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 2,
      color: active ? C.gold : C.textMuted,
      opacity: active ? 0.75 : 0.45,
      transition: 'all 0.2s'
    }
  }, sub)));
}
function NavItemLink({
  href,
  label,
  sub
}) {
  return /*#__PURE__*/React.createElement("a", {
    href: href,
    style: {
      padding: '10px 22px',
      display: 'block',
      textDecoration: 'none',
      borderLeft: '2.5px solid transparent',
      transition: 'all 0.2s'
    },
    onMouseEnter: e => e.currentTarget.style.background = 'color-mix(in srgb, var(--gold) 4%, transparent)',
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 20,
      color: C.textMuted,
      lineHeight: 1.1
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 2,
      color: C.textMuted,
      opacity: 0.45
    }
  }, sub));
}

// ── Desktop Sidebar Nav ───────────────────────────────────
function SideNav({
  active,
  onChange,
  modules,
  dispatch
}) {
  const todayTabs = [{
    id: 'home',
    label: 'Ἀρχή',
    sub: 'Inicio'
  }, {
    id: 'acta',
    label: 'Acta',
    sub: 'Diurna'
  }];
  const systemItems = [{
    kind: 'link',
    href: '/gtd',
    label: 'Πρᾶξις',
    sub: 'Praxis · GTD'
  }, {
    kind: 'link',
    href: '/logros',
    label: '🏆',
    sub: 'Logros'
  }, {
    kind: 'link',
    href: '/recompensas',
    label: '🪙',
    sub: 'Recompensas'
  }, {
    kind: 'tab',
    id: 'profile',
    label: 'Αὐτός',
    sub: 'Perfil'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 210,
      flexShrink: 0,
      background: EU.rgba('deep', 0.99),
      borderRight: '1px solid var(--gold-bg)',
      position: 'fixed',
      top: 0,
      left: 0,
      bottom: 0,
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '28px 22px 24px',
      borderBottom: '1px solid var(--gold-bg)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      letterSpacing: '0.28em',
      color: C.gold,
      opacity: 0.55,
      textTransform: 'uppercase',
      marginBottom: 5
    }
  }, "SISTEMA PERSONAL"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 20,
      color: C.text,
      letterSpacing: '0.14em',
      fontWeight: 600
    }
  }, "EUDAIMONIA")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      paddingTop: 8,
      overflowY: 'auto'
    }
  }, /*#__PURE__*/React.createElement(NavGroup, {
    title: "HOY"
  }, todayTabs.map(t => /*#__PURE__*/React.createElement(NavItem, {
    key: t.id,
    active: active === t.id,
    label: t.label,
    sub: t.sub,
    onClick: () => onChange(t.id)
  }))), /*#__PURE__*/React.createElement(NavGroup, {
    title: "MÓDULOS"
  }, (modules || []).map(mod => {
    const acc = EU.catTint(mod.hue, 'text');
    return /*#__PURE__*/React.createElement(NavItem, {
      key: mod.id,
      active: false,
      label: mod.name,
      sub: mod.concept,
      accent: acc,
      dot: mod.done,
      onClick: () => mod.route ? window.location.href = mod.route : dispatch({
        type: 'OPEN_MODULE',
        id: mod.id
      })
    });
  })), /*#__PURE__*/React.createElement(NavGroup, {
    title: "SISTEMA"
  }, systemItems.map(item => item.kind === 'link' ? /*#__PURE__*/React.createElement(NavItemLink, {
    key: item.href,
    href: item.href,
    label: item.label,
    sub: item.sub
  }) : /*#__PURE__*/React.createElement(NavItem, {
    key: item.id,
    active: active === item.id,
    label: item.label,
    sub: item.sub,
    onClick: () => onChange(item.id)
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 22px 16px',
      borderTop: '1px solid color-mix(in srgb, var(--gold) 7%, transparent)'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => window.euToggleTheme(),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      background: 'transparent',
      border: `1px solid ${C.goldBorder}`,
      borderRadius: 8,
      padding: '7px 12px',
      cursor: 'pointer',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      color: C.textMuted,
      letterSpacing: '0.08em',
      width: '100%'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      lineHeight: 1
    }
  }, document.documentElement.classList.contains('light') ? '☀' : '☽'), /*#__PURE__*/React.createElement("span", null, document.documentElement.classList.contains('light') ? 'Modo día' : 'Modo noche'))));
}

// ── App ───────────────────────────────────────────────────
function App() {
  const [state, dispatch] = useReducer(reducer, null, initFromServer);
  const [tab, setTab] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    const t = p.get('tab');
    return ['home', 'modules', 'acta', 'profile'].includes(t) ? t : 'home';
  });
  const isDesktop = useIsDesktop();
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const open = p.get('open');
    if (open && state.modules.find(m => m.id === open)) {
      dispatch({
        type: 'OPEN_MODULE',
        id: open
      });
    }
  }, []);
  const appDispatch = action => {
    if (action.type === 'SET_TAB') setTab(action.tab);
    dispatch(action);
  };

  // Closing a module must happen whenever the user switches tabs
  const handleTabChange = id => {
    dispatch({
      type: 'CLOSE_MODULE'
    });
    setTab(id);
    window.scrollTo(0, 0);
  };
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const [activeAchievement, setActiveAchievement] = useState(null);
  const [perfectDay, setPerfectDay] = useState(null);
  const [comboQueue, setComboQueue] = useState([]);

  // Achievement sheet listener
  useEffect(() => {
    const onAch = e => setActiveAchievement(e.detail);
    window.addEventListener('eu:achievement-unlocked', onAch);
    return () => window.removeEventListener('eu:achievement-unlocked', onAch);
  }, []);

  // Perfect day + combo bonus listeners
  useEffect(() => {
    const onPerfect = e => setPerfectDay(e.detail);
    const onCombo = e => setComboQueue(q => [...q, e.detail]);
    window.addEventListener('eu:perfect-day', onPerfect);
    window.addEventListener('eu:combo-bonus', onCombo);
    return () => {
      window.removeEventListener('eu:perfect-day', onPerfect);
      window.removeEventListener('eu:combo-bonus', onCombo);
    };
  }, []);

  // ⌘K global shortcut + custom event from HomeScreen header button
  useEffect(() => {
    const onKey = e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdkOpen(o => !o);
      }
    };
    const onEv = () => setCmdkOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('eu:open-cmdk', onEv);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('eu:open-cmdk', onEv);
    };
  }, []);
  const logActivityFromApp = key => {
    const updated = (window.EU._server.activities || []).map(a => a.key === key ? {
      ...a,
      done: !a.done
    } : a);
    window.EU._server.activities = updated;
    fetch('/actividades/api/activity/log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        key
      })
    }).then(r => r.json()).then(data => {
      if (data.gam && (data.gam.xp_delta || data.gam.xp)) dispatch({
        type: 'ADD_XP',
        amount: data.gam.xp_delta || data.gam.xp
      });
    }).catch(() => {});
  };
  const cmdkItems = useMemo(() => {
    const pendingActs = (window.EU._server?.activities || []).filter(a => !a.done).slice(0, 20);
    return [{
      i: '⌂',
      label: 'Ir a Inicio',
      sub: 'Dashboard',
      section: 'nav',
      run: () => handleTabChange('home')
    }, {
      i: '✦',
      label: 'Ir a Acta Diurna',
      sub: 'Actividades',
      section: 'nav',
      run: () => handleTabChange('acta')
    }, {
      i: '◆',
      label: 'Ir a Módulos',
      sub: 'Command Center',
      section: 'nav',
      run: () => handleTabChange('modules')
    }, {
      i: '◎',
      label: 'Ir a Perfil',
      sub: 'Sistema',
      section: 'nav',
      run: () => handleTabChange('profile')
    }, {
      i: '◐',
      label: 'Cambiar tema',
      sub: 'Día / Noche',
      section: 'sys',
      keys: ['⇧', 'T'],
      run: () => window.euToggleTheme()
    }, {
      i: '🏆',
      label: 'Ver Logros',
      sub: 'Sistema',
      section: 'sys',
      run: () => {
        location.href = '/logros';
      }
    }, {
      i: '🪙',
      label: 'Ver Recompensas',
      sub: 'Sistema',
      section: 'sys',
      run: () => {
        location.href = '/recompensas';
      }
    }, ...pendingActs.map(a => ({
      i: '✓',
      label: `Registrar: ${a.label} (+${a.pts} XP)`,
      sub: `Acta · ${a.cat}`,
      section: 'act',
      run: () => logActivityFromApp(a.key)
    }))];
  }, [state.totalXP]);
  const props = {
    appState: state,
    dispatch: appDispatch,
    isDesktop
  };
  const openMod = state.openModuleId ? state.modules.find(m => m.id === state.openModuleId) : null;
  const screen = openMod ? /*#__PURE__*/React.createElement(ModuleDetailScreen, {
    mod: openMod,
    ...props
  }) : tab === 'home' ? /*#__PURE__*/React.createElement(HomeScreen, props) : tab === 'modules' ? /*#__PURE__*/React.createElement(CommandCenterScreen, props) : tab === 'acta' ? /*#__PURE__*/React.createElement(ActaDiurnaScreen, props) : /*#__PURE__*/React.createElement(ProfileScreen, props);
  if (isDesktop) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        minHeight: '100vh',
        background: C.deep
      }
    }, /*#__PURE__*/React.createElement(SideNav, {
      active: tab,
      onChange: handleTabChange,
      modules: state.modules,
      dispatch: appDispatch
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        marginLeft: 210,
        flex: 1,
        minHeight: '100vh',
        overflow: 'hidden'
      }
    }, screen), state.leveledUp && /*#__PURE__*/React.createElement(LevelUpModal, {
      level: state.level,
      onClose: () => dispatch({
        type: 'CLEAR_LEVELUP'
      })
    }), activeAchievement && /*#__PURE__*/React.createElement(AchievementSheet, {
      achievement: activeAchievement,
      onClose: () => setActiveAchievement(null)
    }), perfectDay && /*#__PURE__*/React.createElement(PerfectDayModal, {
      details: perfectDay,
      onClose: () => setPerfectDay(null)
    }), comboQueue[0] && /*#__PURE__*/React.createElement(ComboBonusSheet, {
      combo: comboQueue[0],
      onClose: () => setComboQueue(q => q.slice(1))
    }), /*#__PURE__*/React.createElement(CommandPalette, {
      open: cmdkOpen,
      onClose: () => setCmdkOpen(false),
      items: cmdkItems
    }));
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 430,
      margin: '0 auto',
      minHeight: '100vh',
      background: C.deep,
      position: 'relative',
      fontFamily: 'DM Sans, sans-serif'
    }
  }, screen, state.leveledUp && /*#__PURE__*/React.createElement(LevelUpModal, {
    level: state.level,
    onClose: () => dispatch({
      type: 'CLEAR_LEVELUP'
    })
  }), activeAchievement && /*#__PURE__*/React.createElement(AchievementSheet, {
    achievement: activeAchievement,
    onClose: () => setActiveAchievement(null)
  }), perfectDay && /*#__PURE__*/React.createElement(PerfectDayModal, {
    details: perfectDay,
    onClose: () => setPerfectDay(null)
  }), comboQueue[0] && /*#__PURE__*/React.createElement(ComboBonusSheet, {
    combo: comboQueue[0],
    onClose: () => setComboQueue(q => q.slice(1))
  }), !openMod && /*#__PURE__*/React.createElement(BottomNav, {
    active: tab,
    onChange: handleTabChange
  }), /*#__PURE__*/React.createElement(CommandPalette, {
    open: cmdkOpen,
    onClose: () => setCmdkOpen(false),
    items: cmdkItems
  }));
}

// ── Achievement dispatch helper (used by screens) ─────────
// xp >= 30 → sheet; lower → toast only
window.euFireAchievements = function (achievements) {
  if (!achievements || !achievements.length) return;
  const high = achievements.filter(a => (a.xp || 0) >= 30);
  const low = achievements.filter(a => (a.xp || 0) < 30);
  if (high.length) {
    window.dispatchEvent(new CustomEvent('eu:achievement-unlocked', {
      detail: high[0]
    }));
    // remaining high-tier after first: toast
    high.slice(1).forEach(a => {
      if (typeof toast === 'function') toast(`🏆 ${a.name}`, 'win');
    });
  }
  low.forEach(a => {
    if (typeof toast === 'function') toast(`🏆 ${a.name}`, 'win');
  });
};

// ── Tweaks ────────────────────────────────────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentHue": 45,
  "levelDemo": 3,
  "showStreak": true
} /*EDITMODE-END*/;
function TweaksPanel({
  tweaks,
  onChange,
  visible
}) {
  if (!visible) return null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: 90,
      right: 16,
      zIndex: 9000,
      background: C.card,
      border: '1px solid color-mix(in srgb, var(--gold) 25%, transparent)',
      borderRadius: 14,
      padding: '16px',
      width: 220,
      boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
      fontFamily: 'DM Sans, sans-serif'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      letterSpacing: '0.15em',
      color: C.gold,
      textTransform: 'uppercase',
      marginBottom: 14
    }
  }, "Tweaks"), /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'block',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: C.textMuted,
      marginBottom: 5
    }
  }, "Demo Nivel: ", tweaks.levelDemo), /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: 1,
    max: 10,
    value: tweaks.levelDemo,
    onChange: e => onChange('levelDemo', +e.target.value),
    style: {
      width: '100%',
      accentColor: C.gold
    }
  })), /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'block',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: C.textMuted,
      marginBottom: 5
    }
  }, "Color acento (hue): ", tweaks.accentHue, "°"), /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: 0,
    max: 360,
    value: tweaks.accentHue,
    onChange: e => onChange('accentHue', +e.target.value),
    style: {
      width: '100%',
      accentColor: C.gold
    }
  })), /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: tweaks.showStreak,
    onChange: e => onChange('showStreak', e.target.checked),
    style: {
      accentColor: C.gold
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: C.textSub
    }
  }, "Mostrar rachas")));
}
function Root() {
  const [tweaks, setTweaks] = useState(TWEAK_DEFAULTS);
  const [tweakVisible, setTweakVisible] = useState(false);
  useEffect(() => {
    window.addEventListener('message', e => {
      if (e.data?.type === '__activate_edit_mode') setTweakVisible(true);
      if (e.data?.type === '__deactivate_edit_mode') setTweakVisible(false);
    });
    window.parent.postMessage({
      type: '__edit_mode_available'
    }, '*');
  }, []);
  const handleTweak = (key, val) => {
    const next = {
      ...tweaks,
      [key]: val
    };
    setTweaks(next);
    window.parent.postMessage({
      type: '__edit_mode_set_keys',
      edits: next
    }, '*');
  };
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(App, {
    tweaks: tweaks
  }), /*#__PURE__*/React.createElement(TweaksPanel, {
    tweaks: tweaks,
    onChange: handleTweak,
    visible: tweakVisible
  }));
}
ReactDOM.createRoot(document.getElementById('root')).render(/*#__PURE__*/React.createElement(Root, null));
// EUDAIMONIA — All Screens
// hooks and C declared in eu-components.jsx (bundled before this file)

// ═══════════════════════════════════════════════════════════
// ICONS — hand-authored line icons (Lucide-style), self-contained
// so the dashboard has no external icon CDN dependency to fail on.
// ═══════════════════════════════════════════════════════════
function EuIcon({
  children,
  size = 16,
  viewBox = '0 0 24 24',
  fill = 'none',
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("svg", Object.assign({
    width: size,
    height: size,
    viewBox: viewBox,
    fill: fill,
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      display: 'block',
      flexShrink: 0,
      ...style
    }
  }, rest), children);
}
const IconCommand = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("rect", {
  x: "4",
  y: "4",
  width: "16",
  height: "16",
  rx: "4"
}), /*#__PURE__*/React.createElement("circle", {
  cx: "9",
  cy: "9",
  r: "1.4",
  fill: "currentColor",
  stroke: "none"
}), /*#__PURE__*/React.createElement("circle", {
  cx: "15",
  cy: "9",
  r: "1.4",
  fill: "currentColor",
  stroke: "none"
}), /*#__PURE__*/React.createElement("circle", {
  cx: "9",
  cy: "15",
  r: "1.4",
  fill: "currentColor",
  stroke: "none"
}), /*#__PURE__*/React.createElement("circle", {
  cx: "15",
  cy: "15",
  r: "1.4",
  fill: "currentColor",
  stroke: "none"
}));
const IconTrophy = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M8 4h8v5a4 4 0 0 1-8 0V4z"
}), /*#__PURE__*/React.createElement("path", {
  d: "M8 5H5a2 2 0 0 0 0 4h2"
}), /*#__PURE__*/React.createElement("path", {
  d: "M16 5h3a2 2 0 0 1 0 4h-2"
}), /*#__PURE__*/React.createElement("line", {
  x1: "12",
  y1: "13",
  x2: "12",
  y2: "17"
}), /*#__PURE__*/React.createElement("line", {
  x1: "9",
  y1: "20",
  x2: "15",
  y2: "20"
}), /*#__PURE__*/React.createElement("line", {
  x1: "12",
  y1: "17",
  x2: "12",
  y2: "20"
}));
const IconMountain = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M3 20 9 8 13 15 17 9 21 20z"
}));
const IconSwords = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("line", {
  x1: "5",
  y1: "19",
  x2: "19",
  y2: "5"
}), /*#__PURE__*/React.createElement("line", {
  x1: "19",
  y1: "19",
  x2: "5",
  y2: "5"
}), /*#__PURE__*/React.createElement("line", {
  x1: "15",
  y1: "9",
  x2: "17",
  y2: "7"
}), /*#__PURE__*/React.createElement("line", {
  x1: "9",
  y1: "9",
  x2: "7",
  y2: "7"
}));
const IconMedal = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("circle", {
  cx: "12",
  cy: "15",
  r: "5"
}), /*#__PURE__*/React.createElement("path", {
  d: "M9 11 6 3M15 11 18 3"
}), /*#__PURE__*/React.createElement("path", {
  d: "M9.5 15.5l1.3 1.5 2.2-3"
}));
const IconGem = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M6 3h12l4 6-10 12L2 9z"
}), /*#__PURE__*/React.createElement("path", {
  d: "M2 9h20M9 3l3 6-3 12M15 3l-3 6 3 12"
}));
const IconZap = p => /*#__PURE__*/React.createElement(EuIcon, Object.assign({}, p, {
  fill: "currentColor"
}), /*#__PURE__*/React.createElement("polygon", {
  points: "13,2 3,14 11,14 9,22 21,10 13,10",
  stroke: "none"
}));
const IconRefreshCw = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M21 12a9 9 0 0 1-15.5 6.5L3 16"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "3 21 3 16 8 16"
}), /*#__PURE__*/React.createElement("path", {
  d: "M3 12a9 9 0 0 1 15.5-6.5L21 8"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "21 3 21 8 16 8"
}));
const IconBell = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M12 3a5 5 0 0 0-5 5v3.5c0 1-.4 2-1.2 2.8L4 16h16l-1.8-1.7c-.8-.8-1.2-1.8-1.2-2.8V8a5 5 0 0 0-5-5z"
}), /*#__PURE__*/React.createElement("path", {
  d: "M9.5 19a2.5 2.5 0 0 0 5 0"
}));
const IconCheckSquare = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("rect", {
  x: "3",
  y: "3",
  width: "18",
  height: "18",
  rx: "3"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "7 12 10.5 15.5 17 8.5"
}));
const IconShoppingBag = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M6 8h12l-1 12H7z"
}), /*#__PURE__*/React.createElement("path", {
  d: "M9 8V6a3 3 0 0 1 6 0v2"
}));
const IconCheck = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("polyline", {
  points: "4 12 9.5 17.5 20 6"
}));
const IconGlobe = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("circle", {
  cx: "12",
  cy: "12",
  r: "9"
}), /*#__PURE__*/React.createElement("path", {
  d: "M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"
}));
const IconTerminal = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("rect", {
  x: "2",
  y: "4",
  width: "20",
  height: "16",
  rx: "2"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "6 9 10 12 6 15"
}), /*#__PURE__*/React.createElement("line", {
  x1: "12",
  y1: "15",
  x2: "17",
  y2: "15"
}));
const IconMusic = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("circle", {
  cx: "6",
  cy: "18",
  r: "2.5"
}), /*#__PURE__*/React.createElement("circle", {
  cx: "17",
  cy: "16",
  r: "2.5"
}), /*#__PURE__*/React.createElement("path", {
  d: "M8.5 18V6l11-2v12"
}));
const IconShieldCheck = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6z"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "9 12 11 14 15 9.5"
}));
const IconWallet = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
}), /*#__PURE__*/React.createElement("path", {
  d: "M16 12h3v3h-3a1.5 1.5 0 0 1 0-3z"
}));
const IconClipboardCheck = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("rect", {
  x: "5",
  y: "4",
  width: "14",
  height: "17",
  rx: "2"
}), /*#__PURE__*/React.createElement("rect", {
  x: "9",
  y: "2",
  width: "6",
  height: "4",
  rx: "1"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "9 13 11 15 15 10.5"
}));
const IconBookOpen = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("path", {
  d: "M12 6c-2-1.5-4.5-2-7-2v13c2.5 0 5 .5 7 2 2-1.5 4.5-2 7-2V4c-2.5 0-5 .5-7 2z"
}), /*#__PURE__*/React.createElement("line", {
  x1: "12",
  y1: "6",
  x2: "12",
  y2: "19"
}));
const IconFutbol = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("circle", {
  cx: "12",
  cy: "12",
  r: "9"
}), /*#__PURE__*/React.createElement("path", {
  d: "M12 7.5l3 2.2-1.1 3.6h-3.8L9 9.7z"
}), /*#__PURE__*/React.createElement("path", {
  d: "M12 3v4.5M12 20.5V16M4.2 9l3.5 1.2M16.3 10.2L19.8 9M5.8 17l2.9-3.1M15.3 13.9l2.9 3.1"
}));
const IconArrowRight = p => /*#__PURE__*/React.createElement(EuIcon, p, /*#__PURE__*/React.createElement("line", {
  x1: "4",
  y1: "12",
  x2: "18",
  y2: "12"
}), /*#__PURE__*/React.createElement("polyline", {
  points: "12 6 18 12 12 18"
}));
const MODULE_ICONS = {
  hegemonikon: IconShieldCheck,
  oikonomia: IconWallet,
  ataraxia: IconClipboardCheck,
  paideia: IconBookOpen,
  cosmopolitismo: IconGlobe,
  logoi: IconTerminal,
  eurythmia: IconMusic
};
const DEADLINE_TYPE_ICON = {
  reminder: IconBell,
  task: IconCheckSquare,
  wishlist: IconShoppingBag,
  partido: IconFutbol
};
const DEADLINE_TYPE_LABEL = {
  reminder: 'recordatorio',
  task: 'tarea gtd',
  wishlist: 'wishlist',
  partido: 'partido'
};
const DEADLINE_PAL = {
  red: {
    text: '#f87171',
    bg: 'rgba(239,68,68,0.09)',
    border: '#ef4444',
    pill: 'rgba(239,68,68,0.20)'
  },
  amber: {
    text: '#fbbf24',
    bg: 'rgba(245,158,11,0.09)',
    border: '#f59e0b',
    pill: 'rgba(245,158,11,0.20)'
  },
  yellow: {
    text: '#fde047',
    bg: 'rgba(234,179,8,0.07)',
    border: '#eab308',
    pill: 'rgba(234,179,8,0.18)'
  },
  green: {
    text: '#34d399',
    bg: 'rgba(16,185,129,0.07)',
    border: '#10b981',
    pill: 'rgba(16,185,129,0.18)'
  }
};

// ─── Shared deadlines/reminders state — one source of truth for the ─────────
// sidebar Deadline Radar and the topbar notification bell.
function useDeadlines() {
  const initial = (window.EU._server || {}).deadlines || [];
  const [deadlines, setDeadlines] = useState(initial);
  const [checking, setChecking] = useState({});
  async function handleCheck(dl) {
    if (checking[dl.id]) return;
    // Solo reminders/tareas GTD se "marcan cumplidas" con un click — otros
    // tipos (ej. partidos) tienen su propio flujo, ver DeadlineItemCard.
    if (dl.type !== 'task' && dl.type !== 'reminder') return;
    setChecking(prev => ({
      ...prev,
      [dl.id]: true
    }));
    const url = dl.type === 'task' ? `/gtd/api/task/${dl.id}/complete` : `/perfil/api/reminder/${dl.id}/done`;
    try {
      const res = await fetch(url, {
        method: 'POST'
      });
      const j = await res.json();
      if (j.ok) {
        setDeadlines(prev => prev.filter(d => !(d.id === dl.id && d.type === dl.type)));
      }
    } catch (e) {}
    setChecking(prev => ({
      ...prev,
      [dl.id]: false
    }));
  }
  return {
    deadlines,
    checking,
    handleCheck
  };
}

// ─── One deadline/reminder card — reused by the sidebar radar and the ──────
// topbar notification dropdown.
function DeadlineItemCard({
  dl,
  isChecking,
  onCheck
}) {
  const p = DEADLINE_PAL[dl.level] || DEADLINE_PAL.green;
  const urgent = dl.level === 'red';
  const sublabel = dl.days > 0 ? 'DÍAS' : dl.days === 0 ? 'DEADLINE' : 'EXPIRADO';
  const TypeIcon = DEADLINE_TYPE_ICON[dl.type] || IconBell;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'stretch',
      borderRadius: 14,
      overflow: 'hidden',
      border: '1px solid rgba(255,255,255,0.05)',
      background: p.bg,
      boxShadow: '0 2px 14px rgba(0,0,0,0.32)',
      opacity: isChecking ? 0.5 : 1,
      transition: 'opacity 0.2s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 3,
      flexShrink: 0,
      background: p.border,
      boxShadow: urgent ? `0 0 9px ${p.border}` : 'none'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      padding: '11px 12px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      color: p.text,
      opacity: 0.75
    }
  }, /*#__PURE__*/React.createElement(TypeIcon, {
    size: 10,
    style: urgent ? {
      animation: 'euIconWiggle 1.8s ease-in-out infinite'
    } : undefined
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      letterSpacing: '0.12em',
      textTransform: 'uppercase'
    }
  }, DEADLINE_TYPE_LABEL[dl.type] || dl.type)), dl.type === 'partido' ? /*#__PURE__*/React.createElement("a", {
    href: `/bienestar/futbol?resultado=${dl.id}`,
    title: "Ir a F\xFAtbol \u2014 registrar resultado",
    style: {
      flexShrink: 0,
      width: 20,
      height: 20,
      borderRadius: '50%',
      border: `1.5px solid ${p.border}`,
      background: 'transparent',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'background 0.15s'
    },
    onMouseEnter: e => e.currentTarget.style.background = p.pill,
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, /*#__PURE__*/React.createElement(IconHoverFx, {
    Icon: IconArrowRight,
    fx: "pop",
    size: 10,
    color: p.border
  })) : /*#__PURE__*/React.createElement("button", {
    onClick: () => onCheck(dl),
    title: "Marcar como cumplido",
    style: {
      flexShrink: 0,
      width: 20,
      height: 20,
      borderRadius: '50%',
      border: `1.5px solid ${p.border}`,
      background: 'transparent',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'background 0.15s',
      opacity: isChecking ? 0.4 : 1
    },
    onMouseEnter: e => e.currentTarget.style.background = p.pill,
    onMouseLeave: e => e.currentTarget.style.background = 'transparent'
  }, /*#__PURE__*/React.createElement(IconHoverFx, {
    Icon: IconCheck,
    fx: "pop",
    size: 10,
    color: p.border
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      fontWeight: 500,
      color: C.text,
      lineHeight: 1.3,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    },
    title: dl.label
  }, dl.label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      marginTop: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: p.pill,
      borderRadius: 8,
      padding: '4px 9px',
      display: 'inline-flex',
      alignItems: 'baseline',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontWeight: 900,
      lineHeight: 1,
      fontSize: ['HOY', 'VENCIDO'].includes(dl.badge) ? 12 : 17,
      color: p.text
    }
  }, dl.badge), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 7,
      letterSpacing: '0.14em',
      color: p.text,
      opacity: 0.6
    }
  }, sublabel)), urgent && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 7,
      height: 7,
      borderRadius: '50%',
      flexShrink: 0,
      marginBottom: 2,
      background: p.border,
      boxShadow: `0 0 6px ${p.border}`,
      animation: 'blink 1.4s ease-in-out infinite'
    }
  }))));
}

// ─── Topbar notification bell — badge + dropdown, shares state with the ───
// sidebar Deadline Radar so checking an item off stays in sync everywhere.
function NotificationBell({
  deadlines,
  checking,
  onCheck
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const hasUrgent = deadlines.some(d => d.level === 'red');
  useEffect(() => {
    if (!open) return;
    function onDocClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setOpen(o => !o),
    title: "Notificaciones",
    style: {
      position: 'relative',
      background: 'var(--gold-bg)',
      border: '1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
      borderRadius: 6,
      width: 26,
      height: 26,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(IconHoverFx, {
    Icon: IconBell,
    fx: "wiggle",
    size: 13,
    color: "var(--gold)"
  }), deadlines.length > 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: -4,
      right: -4,
      minWidth: 14,
      height: 14,
      borderRadius: 7,
      background: hasUrgent ? '#ef4444' : 'var(--gold)',
      color: hasUrgent ? '#fff' : '#09070F',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      fontWeight: 700,
      lineHeight: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '0 3px',
      boxShadow: hasUrgent ? '0 0 6px #ef4444' : '0 0 6px var(--gold-glow)',
      animation: hasUrgent ? 'blink 1.4s ease-in-out infinite' : 'none'
    }
  }, deadlines.length)), open && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 'calc(100% + 10px)',
      right: 0,
      zIndex: 60,
      width: 320,
      maxHeight: 420,
      overflowY: 'auto',
      background: 'var(--surf)',
      border: '1px solid var(--gold-border)',
      borderRadius: 14,
      padding: 14,
      boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
      animation: 'euIconPop 0.18s ease'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase'
    }
  }, "Notificaciones"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted,
      opacity: 0.45
    }
  }, deadlines.length, " pr\xF3ximos")), deadlines.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px 4px',
      textAlign: 'center',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: C.textMuted
    }
  }, "Sin pendientes por ahora \u2726") : /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, deadlines.map((dl, i) => /*#__PURE__*/React.createElement(DeadlineItemCard, {
    key: `${dl.type}-${dl.id ?? i}`,
    dl: dl,
    isChecking: checking[dl.id],
    onCheck: onCheck
  })))));
}

// ─── Small hover-triggered icon button (wiggle/pop/spin on hover) ─────────
function IconHoverFx({
  Icon,
  size = 14,
  fx = 'wiggle',
  color,
  style,
  iconStyle
}) {
  const [hov, setHov] = useState(false);
  const FX = {
    wiggle: 'euIconWiggle 0.5s ease',
    pop: 'euIconPop 0.4s ease',
    spin: 'euIconSpinSlow 0.6s linear'
  };
  return /*#__PURE__*/React.createElement("span", {
    onMouseEnter: () => setHov(true),
    onMouseLeave: () => setHov(false),
    style: {
      display: 'inline-flex',
      color,
      ...style
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    size: size,
    style: {
      animation: hov ? FX[fx] : 'none',
      ...iconStyle
    }
  }));
}
function todayQuote() {
  const dayIndex = Math.floor(Date.now() / 86400000);
  return EU.quotes[dayIndex % EU.quotes.length];
}

// ═══════════════════════════════════════════════════════════
// REFLEXION DEL DÍA
// ═══════════════════════════════════════════════════════════
function ReflexionDelDia() {
  const initial = (window.EU._server || {}).reflexion || null;
  const [quote, setQuote] = useState(initial || todayQuote());
  const [spinning, setSpinning] = useState(false);
  const CATEGORY_LABEL = {
    stoic: 'Estoica',
    motivational: 'Motivacional'
  };
  const CATEGORY_COLOR = {
    stoic: {
      text: '#a78bfa',
      bg: 'rgba(167,139,250,0.08)',
      border: 'rgba(167,139,250,0.18)'
    },
    motivational: {
      text: '#34d399',
      bg: 'rgba(52,211,153,0.08)',
      border: 'rgba(52,211,153,0.18)'
    }
  };
  const cat = CATEGORY_COLOR[quote.category] || CATEGORY_COLOR.stoic;
  async function refresh() {
    setSpinning(true);
    try {
      const r = await fetch('/api/quote/refresh');
      setQuote(await r.json());
    } catch (e) {}
    setSpinning(false);
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase'
    }
  }, "Reflexi\xF3n del D\xEDa"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, quote.category && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      color: cat.text,
      background: cat.bg,
      border: `1px solid ${cat.border}`,
      padding: '2px 8px',
      borderRadius: 100,
      letterSpacing: '0.06em'
    }
  }, CATEGORY_LABEL[quote.category] || quote.category), /*#__PURE__*/React.createElement("button", {
    onClick: refresh,
    style: {
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
      color: C.textMuted,
      padding: 0,
      lineHeight: 1,
      display: 'inline-flex',
      alignItems: 'center',
      transform: spinning ? 'rotate(180deg)' : 'rotate(0deg)',
      transition: 'transform 0.4s ease'
    }
  }, /*#__PURE__*/React.createElement(IconHoverFx, {
    Icon: IconRefreshCw,
    fx: "spin",
    size: 14
  })))), /*#__PURE__*/React.createElement(QuoteDisplay, {
    quote: quote
  }));
}
function fmtDate() {
  const d = new Date();
  const days = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
  const mos = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  return `${days[d.getDay()]} ${d.getDate()} de ${mos[d.getMonth()]}`;
}

// ═══════════════════════════════════════════════════════════
// WORD OF THE DAY
// ═══════════════════════════════════════════════════════════
function WordOfDay() {
  const [word, setWord] = useState((window.EU._server || {}).word || null);
  const [spinning, setSpinning] = useState(false);
  if (!word) return null;
  async function refresh() {
    setSpinning(true);
    try {
      const r = await fetch('/api/word/refresh');
      setWord(await r.json());
    } catch (e) {}
    setSpinning(false);
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'color-mix(in srgb, var(--gold) 4%, transparent)',
      border: '1px solid var(--gold-bg)',
      borderRadius: 12,
      padding: '16px 18px',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase'
    }
  }, "Word of the Day"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      color: '#60a5fa',
      background: 'rgba(96,165,250,0.08)',
      border: '1px solid rgba(96,165,250,0.18)',
      padding: '2px 8px',
      borderRadius: 100,
      letterSpacing: '0.06em',
      whiteSpace: 'nowrap'
    }
  }, "EN \u2192 FR"), /*#__PURE__*/React.createElement("button", {
    onClick: refresh,
    style: {
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
      color: C.textMuted,
      padding: 0,
      lineHeight: 1,
      display: 'inline-flex',
      alignItems: 'center',
      transform: spinning ? 'rotate(180deg)' : 'rotate(0deg)',
      transition: 'transform 0.4s ease'
    }
  }, /*#__PURE__*/React.createElement(IconHoverFx, {
    Icon: IconRefreshCw,
    fx: "spin",
    size: 14
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted,
      marginBottom: 2,
      letterSpacing: '0.04em'
    }
  }, word.phonetic), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 26,
      fontWeight: 300,
      color: C.text,
      lineHeight: 1,
      marginBottom: 10
    }
  }, word.word), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 1,
      background: 'linear-gradient(90deg,var(--gold-glow),transparent)',
      marginBottom: 10
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: C.textMuted,
      lineHeight: 1.55,
      marginBottom: 8
    }
  }, word.meaning), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 12,
      color: C.textMuted,
      borderLeft: '2px solid var(--b2)',
      paddingLeft: 10,
      marginBottom: 10,
      lineHeight: 1.55,
      opacity: 0.75
    }
  }, "\"", word.example, "\""), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      background: 'color-mix(in srgb, var(--gold) 6%, transparent)',
      border: '1px solid var(--gold-border)',
      color: C.gold,
      padding: '3px 9px',
      borderRadius: 100,
      display: 'inline-block'
    }
  }, "\uD83C\uDDEB\uD83C\uDDF7 ", word.french));
}

// ═══════════════════════════════════════════════════════════
// REMINDERS WIDGET
// ═══════════════════════════════════════════════════════════
function RemindersWidget() {
  const initial = (window.EU._server || {}).reminders || [];
  const [items, setItems] = useState(initial);
  if (!items.length) return null;
  const FREQ_LABELS = {
    dias: 'días',
    semanas: 'semanas',
    meses: 'meses'
  };
  async function handleDone(id, type) {
    setItems(prev => prev.map(r => r.id === id ? {
      ...r,
      _loading: true
    } : r));
    try {
      const res = await fetch(`/perfil/api/reminder/${id}/done`, {
        method: 'POST'
      });
      const j = await res.json();
      if (j.ok) {
        if (type === 'unico') {
          setItems(prev => prev.filter(r => r.id !== id));
        } else {
          const res2 = await fetch('/perfil/api/reminders');
          const all = await res2.json();
          const today7 = new Date();
          today7.setDate(today7.getDate() + 7);
          const iso7 = today7.toISOString().slice(0, 10);
          setItems(all.filter(r => {
            const d = r.next_date || r.target_date || '9999-12-31';
            return d <= iso7;
          }).slice(0, 5));
        }
      }
    } catch (e) {
      setItems(prev => prev.map(r => r.id === id ? {
        ...r,
        _loading: false
      } : r));
    }
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 10
    }
  }, "Recordatorios"), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'color-mix(in srgb, var(--gold) 3%, transparent)',
      border: '1px solid var(--gold-bg)',
      borderRadius: 12,
      overflow: 'hidden'
    }
  }, items.map((r, i) => {
    const dateStr = r.next_date || r.target_date || '';
    const isPeriodic = r.type === 'periodico';
    return /*#__PURE__*/React.createElement("div", {
      key: r.id,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 16px',
        borderBottom: i < items.length - 1 ? '1px solid color-mix(in srgb, var(--gold) 6%, transparent)' : 'none',
        opacity: r._loading ? 0.4 : 1,
        transition: 'opacity 0.2s'
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: () => !r._loading && handleDone(r.id, r.type),
      style: {
        flexShrink: 0,
        background: 'none',
        border: '1.5px solid color-mix(in srgb, var(--gold) 25%, transparent)',
        width: 18,
        height: 18,
        borderRadius: '50%',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'border-color 0.15s, background 0.15s'
      },
      onMouseEnter: e => {
        e.currentTarget.style.borderColor = 'var(--gold)';
        e.currentTarget.style.background = 'var(--gold-bg)';
      },
      onMouseLeave: e => {
        e.currentTarget.style.borderColor = 'color-mix(in srgb, var(--gold) 25%, transparent)';
        e.currentTarget.style.background = 'none';
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, r.description), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6,
        alignItems: 'center',
        marginTop: 3
      }
    }, isPeriodic ? /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 8,
        background: 'rgba(167,139,250,0.1)',
        border: '1px solid rgba(167,139,250,0.2)',
        color: '#a78bfa',
        padding: '1px 7px',
        borderRadius: 100,
        letterSpacing: '0.06em'
      }
    }, "cada ", r.freq_value, " ", FREQ_LABELS[r.freq_unit] || r.freq_unit) : /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 8,
        background: 'rgba(96,165,250,0.08)',
        border: '1px solid rgba(96,165,250,0.15)',
        color: '#60a5fa',
        padding: '1px 7px',
        borderRadius: 100,
        letterSpacing: '0.06em'
      }
    }, "\xFAnico"), dateStr && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        color: C.textMuted
      }
    }, dateStr))));
  })));
}

// ═══════════════════════════════════════════════════════════
// DEADLINE RADAR
// ═══════════════════════════════════════════════════════════
function DeadlineRadar({
  deadlines,
  checking,
  onCheck
}) {
  if (!deadlines.length) return null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: '#ef4444',
      boxShadow: '0 0 7px #ef4444',
      animation: 'blink 1.4s ease-in-out infinite',
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase',
      flex: 1
    }
  }, "Deadline Radar"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted,
      opacity: 0.45
    }
  }, deadlines.length, " pr\xF3ximos")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, deadlines.map((dl, i) => /*#__PURE__*/React.createElement(DeadlineItemCard, {
    key: `${dl.type}-${dl.id ?? i}`,
    dl: dl,
    isChecking: checking[dl.id],
    onCheck: onCheck
  }))));
}

// ═══════════════════════════════════════════════════════════
// DAILY SCORE CARD
// ═══════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════
// HOME SCREEN
// ═══════════════════════════════════════════════════════════
const TIERS = [{
  rank: 'carbon',
  Icon: IconMountain,
  label: 'Carbón',
  color: '#94a3b8',
  threshold: 0
}, {
  rank: 'iron',
  Icon: IconSwords,
  label: 'Hierro',
  color: '#eab308',
  threshold: 8
}, {
  rank: 'gold',
  Icon: IconMedal,
  label: 'Oro',
  color: '#fbbf24',
  threshold: 16
}, {
  rank: 'diamond',
  Icon: IconGem,
  label: 'Diamante',
  color: '#7dd3fc',
  threshold: 20
}];
function titleCase(s) {
  return s.charAt(0) + s.slice(1).toLowerCase();
}
function SuggestionCard({
  suggestion,
  onClick,
  tint
}) {
  const [hov, setHov] = useState(false);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHov(true),
    onMouseLeave: () => setHov(false),
    style: {
      background: tint.bg,
      border: `1px solid ${tint.border}`,
      borderRadius: 12,
      padding: '14px 16px',
      marginBottom: 14,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      transform: hov ? 'translateY(-2px)' : 'translateY(0)',
      boxShadow: hov ? '0 10px 24px rgba(0,0,0,0.3)' : 'none',
      transition: 'transform 0.18s, box-shadow 0.18s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 34,
      height: 34,
      borderRadius: 9,
      background: 'rgba(0,0,0,0.15)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement(IconZap, {
    size: 16,
    style: {
      color: tint.text,
      animation: 'euIconWiggle 2.4s ease-in-out infinite'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      letterSpacing: '0.16em',
      textTransform: 'uppercase',
      color: tint.text,
      marginBottom: 4
    }
  }, "Un click cierra ", suggestion.cat), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      color: C.text
    }
  }, suggestion.label)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      color: C.gold,
      fontWeight: 600,
      flexShrink: 0
    }
  }, "+", suggestion.pts, " XP"));
}
function ModuleStripCard({
  mod,
  onClick
}) {
  const [hov, setHov] = useState(false);
  const acc = EU.catTint(mod.hue, 'text');
  const Icon = MODULE_ICONS[mod.id] || IconTerminal;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHov(true),
    onMouseLeave: () => setHov(false),
    style: {
      background: C.card,
      border: `1px solid ${mod.done ? acc : C.goldBorder}`,
      borderRadius: 13,
      padding: 14,
      cursor: 'pointer',
      boxShadow: mod.done ? `0 0 16px color-mix(in srgb, ${acc} 30%, transparent)` : 'none',
      transform: hov ? 'translateY(-3px)' : 'translateY(0)',
      transition: 'transform 0.18s, box-shadow 0.18s, border-color 0.18s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 36,
      height: 36,
      borderRadius: 10,
      marginBottom: 10,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: `color-mix(in srgb, ${acc} 14%, transparent)`,
      border: `1px solid color-mix(in srgb, ${acc} 35%, transparent)`
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    size: 17,
    style: {
      color: acc,
      animation: mod.done ? 'euIconFloat 2.6s ease-in-out infinite' : hov ? 'euIconPulseScale 0.5s ease' : 'none'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 15,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.02em'
    }
  }, titleCase(mod.name)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9.5,
      color: C.textMuted,
      marginTop: 2,
      lineHeight: 1.35
    }
  }, mod.desc), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      marginTop: 10,
      fontSize: 9.5
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: mod.done ? acc : C.textMuted,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: mod.done ? acc : C.textMuted
    }
  }, mod.done ? `${mod.streak} días` : 'pendiente hoy')));
}
function HomeScreen({
  appState,
  dispatch,
  isDesktop
}) {
  const {
    isLight
  } = useTheme();
  const {
    level,
    xp,
    xpNext,
    modules
  } = appState;
  const lv = EU.levels[level - 1];
  const xpPct = xpNext ? xp / xpNext : 1;
  const srv = window.EU._server || {};
  const xpToday = srv.xpToday || 0;
  const streak = srv.streak || 0;
  const clf = srv.classification || {};
  const XP_GOAL = 15;
  const xpDayPct = Math.min(1, xpToday / XP_GOAL);
  const [suggestion, setSuggestion] = React.useState(srv.suggestion || null);
  const {
    deadlines,
    checking,
    handleCheck
  } = useDeadlines();
  const logActivityFromHome = key => {
    if (suggestion?.key === key) setSuggestion(null);
    const updated = (window.EU._server.activities || []).map(a => a.key === key ? {
      ...a,
      done: !a.done
    } : a);
    window.EU._server.activities = updated;
    fetch('/actividades/api/activity/log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        key
      })
    }).then(r => r.json()).then(data => {
      if (data.gam && (data.gam.xp_delta || data.gam.xp)) dispatch({
        type: 'ADD_XP',
        amount: data.gam.xp_delta || data.gam.xp
      });
      if (data.gam?.achievements?.length) window.euFireAchievements(data.gam.achievements);
      if (data.gam?.perfect_day) {
        window.dispatchEvent(new CustomEvent('eu:perfect-day', {
          detail: {
            bonusXp: data.gam.perfect_day.xp || 5,
            bonusEc: data.gam.perfect_day.ec || 10
          }
        }));
      } else if (data.gam?.combo_bonuses?.length) {
        data.gam.combo_bonuses.forEach(c => window.dispatchEvent(new CustomEvent('eu:combo-bonus', {
          detail: c
        })));
      }
      if (data.stats) {
        window.EU._server.xpToday = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
        window.EU._server.streak = data.stats.streak ?? streak;
      }
    }).catch(() => {});
  };

  // ── Shared blocks ──────────────────────────────────────────
  const heroXp = /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'linear-gradient(140deg, var(--surf), var(--bg))',
      border: '1px solid var(--gold-border)',
      borderRadius: 16,
      padding: '20px',
      marginBottom: 14,
      position: 'relative',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      letterSpacing: '0.18em',
      color: C.gold,
      opacity: 0.6,
      textTransform: 'uppercase',
      marginBottom: 6
    }
  }, "XP hoy"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 48,
      lineHeight: 1,
      color: C.goldLight,
      fontWeight: 600
    }
  }, xpToday), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: C.textMuted
    }
  }, "/ ", XP_GOAL, " meta")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 5,
      background: 'var(--gold-bg)',
      borderRadius: 3,
      overflow: 'hidden',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 3,
      background: 'linear-gradient(90deg, color-mix(in srgb, var(--gold) 60%, transparent), var(--gold), var(--gold-l))',
      width: `${xpDayPct * 100}%`,
      boxShadow: '0 0 8px var(--gold-glow)',
      transition: 'width 0.8s ease'
    }
  })), (() => {
    const ci = Math.max(0, TIERS.findIndex(t => t.rank === clf.rank));
    const nt = TIERS[ci + 1] || null;
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'stretch',
        gap: 6,
        marginBottom: 10
      }
    }, TIERS.map((t, i) => {
      const active = i === ci;
      const TIcon = t.Icon;
      return /*#__PURE__*/React.createElement("div", {
        key: t.rank,
        style: {
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 6,
          padding: '10px 4px',
          borderRadius: 10,
          border: `1px solid ${active ? t.color : 'transparent'}`,
          background: active ? `color-mix(in srgb, ${t.color} 8%, transparent)` : 'transparent',
          boxShadow: active ? `0 0 16px color-mix(in srgb, ${t.color} 25%, transparent)` : 'none',
          transition: 'all 0.25s'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: 26,
          height: 26,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: active ? t.color : 'rgba(255,255,255,0.04)',
          boxShadow: active ? `0 0 10px ${t.color}` : 'none',
          transition: 'all 0.25s'
        }
      }, /*#__PURE__*/React.createElement(TIcon, {
        size: 13,
        style: {
          color: active ? '#09070F' : C.textMuted,
          animation: active ? 'euIconPop 0.5s ease 0.1s both, euIconPulseScale 2.2s ease-in-out 1s infinite' : 'none'
        }
      })), /*#__PURE__*/React.createElement("div", {
        style: {
          fontFamily: 'DM Sans,sans-serif',
          fontSize: 9,
          letterSpacing: '0.06em',
          color: active ? t.color : C.textMuted,
          fontWeight: active ? 600 : 400,
          opacity: active ? 1 : 0.6,
          textAlign: 'center'
        }
      }, t.label));
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.textMuted
      }
    }, "Clasificaci\xF3n de hoy"), /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.gold,
        opacity: 0.8
      }
    }, nt ? `${nt.threshold - xpToday} XP → ${nt.label}` : '✦ Diamante alcanzado')));
  })());
  const levelCard = /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'linear-gradient(140deg, var(--card), var(--surf) 55%, var(--bg))',
      border: '1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
      borderRadius: 16,
      padding: '18px 16px',
      marginBottom: 14,
      position: 'relative',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      background: 'radial-gradient(ellipse at 15% 85%,color-mix(in srgb, var(--gold) 5%, transparent) 0%,transparent 55%),' + 'radial-gradient(ellipse at 85% 15%,color-mix(in srgb, var(--gold) 3%, transparent) 0%,transparent 45%)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flexShrink: 0,
      cursor: 'pointer',
      transition: 'opacity 0.15s'
    },
    onClick: () => window.location.reload(),
    onMouseDown: e => e.currentTarget.style.opacity = '0.5',
    onMouseUp: e => e.currentTarget.style.opacity = '1'
  }, /*#__PURE__*/React.createElement(GreekColumn, {
    level: level,
    xpPct: xpPct,
    size: 72
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      paddingBottom: 3
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.18em',
      color: C.gold,
      opacity: 0.6,
      textTransform: 'uppercase',
      marginBottom: 2
    }
  }, "NIVEL ", level), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 28,
      fontWeight: 600,
      color: C.text,
      lineHeight: 1,
      letterSpacing: '0.05em'
    }
  }, lv?.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 12,
      color: C.textSub,
      marginTop: 3,
      marginBottom: 10
    }
  }, lv?.sub), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      background: 'var(--gold-bg)',
      borderRadius: 2,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 2,
      background: 'linear-gradient(90deg, color-mix(in srgb, var(--gold) 60%, transparent), var(--gold), var(--gold-l))',
      width: `${xpPct * 100}%`,
      boxShadow: '0 0 8px var(--gold-glow)',
      transition: 'width 1.2s ease'
    }
  })))));
  const modulesStrip = /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase'
    }
  }, "M\xF3dulos"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: C.textMuted
    }
  }, modules.filter(m => m.done).length, " de ", modules.length)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 3,
      marginBottom: 14,
      height: 3,
      borderRadius: 2,
      overflow: 'hidden',
      background: 'color-mix(in srgb, var(--gold) 6%, transparent)'
    }
  }, modules.map(mod => /*#__PURE__*/React.createElement("div", {
    key: mod.id,
    style: {
      flex: 1,
      height: '100%',
      background: mod.done ? EU.catTint(mod.hue, 'text') : 'transparent',
      transition: 'background 0.4s'
    }
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(150px,1fr))',
      gap: 10
    }
  }, modules.map(mod => /*#__PURE__*/React.createElement(ModuleStripCard, {
    key: mod.id,
    mod: mod,
    onClick: () => mod.route ? window.location.href = mod.route : dispatch({
      type: 'OPEN_MODULE',
      id: mod.id
    })
  }))));
  const heatmapCard = /*#__PURE__*/React.createElement("div", {
    style: {
      background: C.card,
      border: `1px solid ${C.goldBorder}`,
      borderRadius: 12,
      padding: '14px 16px',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      letterSpacing: '0.18em',
      color: C.gold,
      opacity: 0.7,
      textTransform: 'uppercase'
    }
  }, "Racha \xB7 ", streak, " d\xEDas"), /*#__PURE__*/React.createElement("a", {
    href: "/logros",
    style: {
      fontSize: 10,
      color: C.gold,
      opacity: 0.6,
      textDecoration: 'none'
    }
  }, "Ver historial \u2192")), /*#__PURE__*/React.createElement(StreakHeatmap, {
    days: 21,
    compact: true
  }));
  const suggestionCard = suggestion && /*#__PURE__*/React.createElement(SuggestionCard, {
    suggestion: suggestion,
    onClick: () => logActivityFromHome(suggestion.key),
    tint: {
      bg: EU.catTint((EU.catHues || {})[suggestion.cat] || 45, 'bg'),
      border: EU.catTint((EU.catHues || {})[suggestion.cat] || 45, 'border'),
      text: EU.catTint((EU.catHues || {})[suggestion.cat] || 45, 'text')
    }
  });

  // ── Desktop 2-column layout ─────────────────────────────────
  if (isDesktop) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        minHeight: '100vh'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'sticky',
        top: 0,
        zIndex: 50,
        padding: '14px 40px',
        background: 'var(--surf-top)',
        borderBottom: '1px solid color-mix(in srgb, var(--gold) 7%, transparent)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        letterSpacing: '0.22em',
        color: C.gold,
        opacity: 0.65,
        textTransform: 'uppercase'
      }
    }, fmtDate()), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'Cormorant Garamond,serif',
        fontSize: 22,
        color: C.text,
        fontWeight: 500,
        letterSpacing: '0.14em',
        marginTop: 1
      }
    }, "\u0395 \u03A5 \u0394 \u0391 \u0399 \u039C \u039F \u039D \u0399 \u0391")), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: () => window.dispatchEvent(new CustomEvent('eu:open-cmdk')),
      style: {
        background: 'var(--gold-bg)',
        border: '1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
        borderRadius: 6,
        padding: '5px 10px',
        color: C.gold,
        fontSize: 11,
        cursor: 'pointer',
        fontFamily: 'DM Sans,sans-serif',
        letterSpacing: '0.05em',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5
      }
    }, /*#__PURE__*/React.createElement(IconHoverFx, {
      Icon: IconCommand,
      fx: "wiggle",
      size: 11
    }), " K"), /*#__PURE__*/React.createElement(NotificationBell, {
      deadlines: deadlines,
      checking: checking,
      onCheck: handleCheck
    }), /*#__PURE__*/React.createElement("a", {
      href: "/logros",
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        color: C.gold,
        opacity: 0.65,
        textDecoration: 'none',
        letterSpacing: '0.08em'
      }
    }, /*#__PURE__*/React.createElement(IconHoverFx, {
      Icon: IconTrophy,
      fx: "pop",
      size: 11
    }), " Logros"))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 380px',
        gap: '0 32px',
        padding: '32px 40px 60px',
        alignItems: 'start'
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 20,
        animation: 'euRise 0.5s ease 0.02s both'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'Cormorant Garamond,serif',
        fontSize: 26,
        color: C.text
      }
    }, "Buenos d\xEDas, Gio."), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: C.textMuted,
        marginTop: 3
      }
    }, fmtDate(), " \xB7 d\xEDa ", streak, " de tu racha")), /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.06s both'
      }
    }, heroXp), suggestionCard && /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.10s both'
      }
    }, suggestionCard), /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.14s both'
      }
    }, levelCard), /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.18s both'
      }
    }, modulesStrip), /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.24s both'
      }
    }, /*#__PURE__*/React.createElement(ReflexionDelDia, null))), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'sticky',
        top: 80
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.08s both'
      }
    }, heatmapCard), /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.14s both'
      }
    }, /*#__PURE__*/React.createElement(WordOfDay, null)), /*#__PURE__*/React.createElement("div", {
      style: {
        animation: 'euRise 0.5s ease 0.20s both'
      }
    }, /*#__PURE__*/React.createElement(DeadlineRadar, {
      deadlines: deadlines,
      checking: checking,
      onCheck: handleCheck
    })))));
  }

  // ── Mobile layout ───────────────────────────────────────────
  return /*#__PURE__*/React.createElement("div", {
    style: {
      paddingBottom: 100,
      minHeight: '100vh'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: 'env(safe-area-inset-top,16px) 20px 12px',
      paddingTop: 'max(env(safe-area-inset-top,16px),16px)',
      background: EU.rgba('deep', 0.97),
      borderBottom: '1px solid color-mix(in srgb, var(--gold) 7%, transparent)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.22em',
      color: C.gold,
      opacity: 0.65,
      textTransform: 'uppercase'
    }
  }, fmtDate()), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 20,
      color: C.text,
      fontWeight: 500,
      letterSpacing: '0.18em',
      marginTop: 1
    }
  }, "\u0395\u03A5\u0394\u0391\u0399\u039C\u039F\u039D\u0399\u0391")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      paddingTop: 2
    }
  }, /*#__PURE__*/React.createElement(NotificationBell, {
    deadlines: deadlines,
    checking: checking,
    onCheck: handleCheck
  }), /*#__PURE__*/React.createElement("a", {
    href: "/logros",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.gold,
      opacity: 0.65,
      textDecoration: 'none',
      letterSpacing: '0.08em'
    }
  }, /*#__PURE__*/React.createElement(IconHoverFx, {
    Icon: IconTrophy,
    fx: "pop",
    size: 11
  }), " Logros")))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 16px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px 0 12px',
      animation: 'euRise 0.5s ease 0.02s both'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 22,
      color: C.text
    }
  }, "Buenos d\xEDas, Gio."), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: C.textMuted,
      marginTop: 2
    }
  }, fmtDate(), " \xB7 d\xEDa ", streak, " de tu racha")), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.06s both'
    }
  }, heroXp), suggestionCard && /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.10s both'
    }
  }, suggestionCard), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.14s both'
    }
  }, levelCard), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.18s both'
    }
  }, modulesStrip), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.22s both'
    }
  }, heatmapCard), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.26s both'
    }
  }, /*#__PURE__*/React.createElement(ReflexionDelDia, null)), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.30s both'
    }
  }, /*#__PURE__*/React.createElement(WordOfDay, null)), /*#__PURE__*/React.createElement("div", {
    style: {
      animation: 'euRise 0.5s ease 0.34s both'
    }
  }, /*#__PURE__*/React.createElement(DeadlineRadar, {
    deadlines: deadlines,
    checking: checking,
    onCheck: handleCheck
  }))));
}

// ═══════════════════════════════════════════════════════════
// COMMAND CENTER
// ═══════════════════════════════════════════════════════════
function CommandCenterScreen({
  appState,
  dispatch,
  isDesktop
}) {
  const {
    modules
  } = appState;
  const doneCount = modules.filter(m => m.done).length;
  const cols = isDesktop ? '1fr 1fr 1fr' : '1fr 1fr';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      paddingBottom: isDesktop ? 48 : 100,
      minHeight: '100vh'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '28px 24px 20px' : '16px 20px 20px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.2em',
      color: C.gold,
      textTransform: 'uppercase',
      opacity: 0.6,
      marginBottom: 4
    }
  }, "COMMAND CENTER"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 30,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.05em'
    }
  }, "M\xF3dulos"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      marginTop: 4
    }
  }, doneCount, " de ", modules.length, " completados hoy"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 4,
      marginTop: 14,
      height: 3,
      borderRadius: 2,
      overflow: 'hidden',
      background: 'color-mix(in srgb, var(--gold) 6%, transparent)'
    }
  }, modules.map(mod => /*#__PURE__*/React.createElement("div", {
    key: mod.id,
    style: {
      flex: 1,
      height: '100%',
      background: mod.done ? EU.catTint(mod.hue, 'text') : 'transparent',
      transition: 'background 0.4s'
    }
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '0 24px' : '0 16px',
      display: 'grid',
      gridTemplateColumns: cols,
      gap: 10
    }
  }, modules.map(mod => /*#__PURE__*/React.createElement(ModuleStripCard, {
    key: mod.id,
    mod: mod,
    onClick: () => mod.route ? window.location.href = mod.route : dispatch({
      type: 'OPEN_MODULE',
      id: mod.id
    })
  })), /*#__PURE__*/React.createElement("a", {
    href: "/gtd",
    style: {
      gridColumn: '1/-1',
      background: C.card,
      border: '1px solid var(--b)',
      borderRadius: 14,
      padding: '14px 15px',
      cursor: 'pointer',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      transition: 'all 0.25s',
      textDecoration: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 15,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.08em'
    }
  }, "PRAXIS"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.gold,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 3
    }
  }, "Ejecuci\xF3n de la voluntad \xB7 GTD")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 22,
      color: C.gold,
      opacity: 0.5
    }
  }, "\u2192")), /*#__PURE__*/React.createElement("a", {
    href: "/logros",
    style: {
      gridColumn: '1/-1',
      background: 'color-mix(in srgb, var(--gold) 4%, transparent)',
      border: '1px solid var(--b)',
      borderRadius: 14,
      padding: '14px 15px',
      cursor: 'pointer',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      transition: 'all 0.25s',
      textDecoration: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 15,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.08em'
    }
  }, "\uD83C\uDFC6 LOGROS"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.gold,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 3
    }
  }, "Trofeos \xB7 Clasificaci\xF3n \xB7 Historial XP")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 22,
      color: C.gold,
      opacity: 0.5
    }
  }, "\u2192"))));
}

// ═══════════════════════════════════════════════════════════
// MODULE DETAIL
// ═══════════════════════════════════════════════════════════
function ModuleDetailScreen({
  mod,
  appState,
  dispatch,
  isDesktop
}) {
  const acc = EU.catTint(mod.hue, 'text');
  const accMid = EU.catTint(mod.hue, 'border');
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: '100vh',
      paddingBottom: isDesktop ? 48 : 100
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '28px 24px 28px' : '16px 20px 24px',
      background: `linear-gradient(170deg,${EU.catTint(mod.hue, 'bg')} 0%,transparent 100%)`,
      borderBottom: `1px solid ${accMid}`
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => dispatch({
      type: 'CLOSE_MODULE'
    }),
    style: {
      background: 'none',
      border: 'none',
      color: C.textMuted,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      cursor: 'pointer',
      padding: 0,
      display: 'flex',
      alignItems: 'center',
      gap: 6
    }
  }, "\u2190 M\xF3dulos")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: acc,
      textTransform: 'uppercase',
      opacity: 0.85,
      marginBottom: 3
    }
  }, mod.concept), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 32,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.06em'
    }
  }, mod.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      marginTop: 3
    }
  }, mod.desc)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '24px 24px 0' : '20px 16px 0'
    }
  }, /*#__PURE__*/React.createElement(ModuleExtra, {
    id: mod.id,
    acc: acc,
    isDesktop: isDesktop
  })));
}
function OikonomiaExtra() {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    fetch('/finanzas/api/oikonomia-summary').then(r => r.json()).then(d => {
      setData(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);
  const fmt = v => v != null && v !== '' ? `$${Number(v).toLocaleString('es-MX', {
    maximumFractionDigits: 0
  })}` : '—';
  const GOLD = '#E8C96D';
  const CARD_BG = 'linear-gradient(150deg,#1a1510 0%,#241d14 55%,#16110b 100%)';
  const CARD_BR = '1px solid rgba(201,168,76,0.28)';
  if (loading) return /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      padding: '24px 0',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      letterSpacing: '0.1em'
    }
  }, "cargando\u2026");
  if (!data || data.locked) return /*#__PURE__*/React.createElement("div", {
    style: {
      background: C.card,
      border: '1px solid var(--b)',
      borderRadius: 16,
      padding: '28px 20px',
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 26,
      color: GOLD,
      marginBottom: 8
    }
  }, "Oikonomia \uD83D\uDD12"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      marginBottom: 18
    }
  }, "Activa tu m\xF3dulo financiero para ver tu patrimonio neto."), /*#__PURE__*/React.createElement("a", {
    href: "/finanzas/",
    style: {
      display: 'inline-block',
      background: GOLD,
      color: '#1a1510',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      fontWeight: 600,
      padding: '10px 24px',
      borderRadius: 10,
      textDecoration: 'none'
    }
  }, "Desbloquear Oikonomia \uD83D\uDD12"));
  const trendPos = data.trend_pct >= 0;
  const trendSymbol = trendPos ? '▲' : '▼';
  const trendColor = trendPos ? '#7BC49A' : '#E59B92';

  // Bar-chart sparkline (matches mockup design)
  const spark = (data.spark || []).filter(v => v != null && v !== '');
  let sparkBars = null;
  if (spark.length >= 2) {
    const min = Math.min(...spark);
    const max = Math.max(...spark);
    const range = max - min || 1;
    sparkBars = /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'flex-end',
        gap: 3,
        height: 36,
        marginTop: 14,
        marginBottom: 2
      }
    }, spark.map((v, i) => {
      const pct = Math.max(8, (v - min) / range * 92 + 8);
      const isLast = i === spark.length - 1;
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          flex: 1,
          height: `${pct}%`,
          background: isLast ? 'linear-gradient(180deg,#E8C96D,rgba(201,168,76,0.3))' : 'linear-gradient(180deg,rgba(201,168,76,0.55),rgba(201,168,76,0.12))',
          borderRadius: '2px 2px 0 0',
          boxShadow: isLast ? '0 0 10px rgba(201,168,76,0.5)' : 'none'
        }
      });
    }));
  }
  const pillars = [{
    icon: '🏛️',
    label: 'Patrimonio',
    sub: 'Cuentas · deudas · bienes',
    href: '/finanzas/',
    iconBg: 'rgba(58,95,138,0.12)',
    statV: String(data.n_cuentas),
    statL: 'cuentas'
  }, {
    icon: '📊',
    label: 'Presupuesto',
    sub: '50 · 30 · 20',
    href: '/finanzas/budget',
    iconBg: 'rgba(26,122,82,0.12)',
    statV: null,
    statL: null
  }, {
    icon: '📈',
    label: 'Inversiones',
    sub: 'Portafolio · rendimientos',
    href: '/finanzas/inversiones',
    iconBg: 'rgba(34,197,94,0.10)',
    statV: null,
    statL: null
  }, {
    icon: '💳',
    label: 'Estados',
    sub: 'Movimientos · análisis',
    href: '/finanzas/estados',
    iconBg: 'rgba(139,105,20,0.12)',
    statV: String(data.n_bancos),
    statL: 'bancos'
  }];
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      overflow: 'hidden',
      background: CARD_BG,
      borderRadius: 18,
      padding: '22px 22px 20px',
      marginBottom: 14,
      border: CARD_BR,
      boxShadow: '0 16px 40px -16px rgba(40,28,8,0.55)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      background: 'radial-gradient(ellipse at 88% 10%,rgba(201,168,76,0.12),transparent 55%)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      letterSpacing: '0.22em',
      textTransform: 'uppercase',
      color: 'rgba(232,201,109,0.7)',
      marginBottom: 8
    }
  }, "Patrimonio Neto"), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'baseline',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 46,
      fontWeight: 600,
      color: GOLD,
      lineHeight: 0.95,
      letterSpacing: '0.01em'
    }
  }, fmt(data.patrimonio_neto)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 14,
      color: 'rgba(232,201,109,0.55)'
    }
  }, "MXN")), data.trend_pct !== 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      marginTop: 8,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: trendColor
    }
  }, trendSymbol, " ", Math.abs(data.trend_pct), "%", data.trend_delta !== 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'rgba(242,237,224,0.4)',
      fontSize: 11
    }
  }, "\xB7 ", data.trend_delta > 0 ? '+' : '', fmt(data.trend_delta), " este mes")), sparkBars, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      justifyContent: 'space-between',
      marginTop: 14,
      paddingTop: 13,
      borderTop: '1px solid rgba(201,168,76,0.14)'
    }
  }, [{
    label: 'Activos',
    val: fmt(data.activos),
    color: '#7BC49A'
  }, {
    label: 'Pasivos',
    val: fmt(data.pasivos),
    color: '#E59B92'
  }, {
    label: 'Líquido',
    val: fmt(data.liquido),
    color: GOLD
  }].map((it, i) => /*#__PURE__*/React.createElement("div", {
    key: i
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      color: 'rgba(242,237,224,0.4)',
      marginBottom: 3
    }
  }, it.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 17,
      color: it.color
    }
  }, it.val))))), data.pay_alerts && data.pay_alerts.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 11,
      background: 'rgba(139,105,20,0.07)',
      border: '1px solid rgba(201,168,76,0.3)',
      borderLeft: '3px solid rgba(201,168,76,0.9)',
      borderRadius: '0 11px 11px 0',
      padding: '12px 15px',
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 30,
      height: 30,
      borderRadius: 8,
      background: 'rgba(201,168,76,0.12)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      fontSize: 14
    }
  }, "\uD83D\uDD14"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: C.text
    }
  }, "Hoy \xB7 pagar", ' ', data.pay_alerts.map(a => /*#__PURE__*/React.createElement("span", {
    key: a.label,
    style: {
      color: a.color,
      fontWeight: 600,
      marginRight: 4
    }
  }, a.label))), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      color: 'rgba(201,168,76,0.6)'
    }
  }, "\u2192")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      letterSpacing: '0.18em',
      color: C.textMuted,
      textTransform: 'uppercase',
      margin: '0 0 10px 2px'
    }
  }, "N\xFAcleo"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 9,
      marginBottom: 20
    }
  }, pillars.map((p, i) => /*#__PURE__*/React.createElement("a", {
    key: i,
    href: p.href,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      background: C.card,
      border: '1px solid var(--b)',
      borderRadius: 14,
      padding: '15px 16px',
      textDecoration: 'none',
      color: 'inherit',
      transition: 'all 0.2s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 42,
      height: 42,
      borderRadius: 11,
      flexShrink: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 19,
      background: p.iconBg
    }
  }, p.icon), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 19,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.02em',
      lineHeight: 1.1
    }
  }, p.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      marginTop: 2
    }
  }, p.sub)), p.statV && /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 18,
      color: C.text,
      lineHeight: 1
    }
  }, p.statV), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: C.textMuted,
      marginTop: 3
    }
  }, p.statL))))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      letterSpacing: '0.18em',
      color: C.textMuted,
      textTransform: 'uppercase',
      margin: '0 0 10px 2px'
    }
  }, "Accesos"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, [{
    icon: '🛒',
    label: 'Consumo',
    href: '/finanzas/consumo'
  }, {
    icon: '⭐',
    label: 'Wishlist',
    href: '/finanzas/prioridades'
  }, {
    icon: '✈️',
    label: 'Viajes',
    href: '/finanzas/estados/viajes'
  }].map((chip, i) => /*#__PURE__*/React.createElement("a", {
    key: i,
    href: chip.href,
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 6,
      background: C.card2,
      border: '1px solid var(--b)',
      borderRadius: 12,
      padding: '13px 8px',
      textDecoration: 'none',
      color: 'inherit',
      transition: 'border-color 0.2s'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 18
    }
  }, chip.icon), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      letterSpacing: '0.04em'
    }
  }, chip.label)))));
}
function HegemonikonExtra({
  acc,
  isDesktop
}) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    fetch('/bienestar/api/hegemonikon-summary').then(r => r.json()).then(d => {
      setData(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);
  if (loading) return /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      padding: '24px 0',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      letterSpacing: '0.1em'
    }
  }, "cargando\u2026");
  const b = data && data.body || {};
  const nut = data && data.nutricion || {
    comidas_done: 0,
    comidas_total: 0,
    streak: 0,
    xp_today: 0
  };
  const salud = data && data.salud || {
    episodios_activos: 0,
    meds_activos: 0
  };
  const guard = data && data.guardarropa || {
    items: 0,
    outfits: 0
  };
  const rec = data && data.recetas || {
    total: 0,
    favoritas: 0
  };
  const futbol = data && data.futbol || {
    partidos: 0,
    rating: null
  };
  const bodyRows = [{
    label: 'Peso',
    val: b.peso || '—',
    sub: b.estatura ? `Estatura: ${b.estatura}` : ''
  }, {
    label: 'Pecho',
    val: b.pecho || '—',
    sub: b.cintura ? `Cintura: ${b.cintura}` : ''
  }, {
    label: 'Hombros',
    val: b.hombros || '—',
    sub: b.manga ? `Manga: ${b.manga}` : ''
  }, {
    label: 'T. Camisa',
    val: b.t_camisa || '—',
    sub: b.t_pantalon ? `Pantalón: ${b.t_pantalon}` : ''
  }];
  const subs = [{
    href: '/bienestar/salud',
    icon: '🩺',
    label: 'Salud',
    hue: 350,
    sub: salud.episodios_activos > 0 ? `${salud.episodios_activos} episodio${salud.episodios_activos !== 1 ? 's' : ''} activo${salud.episodios_activos !== 1 ? 's' : ''}` : 'Al día',
    alert: salud.episodios_activos > 0
  }, {
    href: '/nutricion/',
    icon: '🥗',
    label: 'Nutrición',
    hue: 140,
    sub: `${nut.comidas_done}/${nut.comidas_total} comidas hoy · racha ${nut.streak}d`
  }, {
    href: '/guardarropa/',
    icon: '👔',
    label: 'Guardarropa',
    hue: 280,
    sub: `${guard.items} prendas · ${guard.outfits} outfits`
  }, {
    href: '/recetas/',
    icon: '🍳',
    label: 'Recetas',
    hue: 40,
    sub: `${rec.total} recetas · ${rec.favoritas} favoritas`
  }, {
    href: '/perfil/',
    icon: '👤',
    label: 'Perfil',
    hue: 220,
    sub: 'Datos personales · documentos'
  }, {
    href: '/bienestar/futbol',
    icon: '⚽',
    label: 'Fútbol',
    hue: 170,
    sub: futbol.partidos > 0 ? `${futbol.partidos} partido${futbol.partidos !== 1 ? 's' : ''}${futbol.rating ? ` · rating ${futbol.rating}` : ''}` : 'Registra tu primer partido'
  }];

  // ── Sparkline de peso (últimos registros, más viejo→reciente) ──────────
  const sparkPts = data && data.peso_spark || [];
  const pesoSpark = sparkPts.length >= 2 && (() => {
    const w = 84,
      h = 28,
      pad = 3;
    const min = Math.min(...sparkPts),
      max = Math.max(...sparkPts);
    const range = max - min || 1;
    const step = (w - pad * 2) / (sparkPts.length - 1);
    const pts = sparkPts.map((v, i) => [pad + i * step, pad + (h - pad * 2) * (1 - (v - min) / range)]);
    const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
    const last = pts[pts.length - 1];
    return /*#__PURE__*/React.createElement("svg", {
      width: w,
      height: h,
      style: {
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement("path", {
      d: path,
      fill: "none",
      stroke: acc,
      strokeWidth: "1.6",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      opacity: "0.85"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: last[0],
      cy: last[1],
      r: "2.4",
      fill: acc
    }));
  })();
  const alertBanner = (salud.episodios_activos > 0 || salud.meds_activos > 0) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 11,
      background: 'rgba(244,63,94,0.06)',
      border: '1px solid rgba(244,63,94,0.25)',
      borderLeft: '3px solid rgba(244,63,94,0.8)',
      borderRadius: '0 11px 11px 0',
      padding: '12px 15px',
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 30,
      height: 30,
      borderRadius: 8,
      background: 'rgba(244,63,94,0.12)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      fontSize: 14
    }
  }, "\uD83E\uDE7A"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: C.text
    }
  }, salud.episodios_activos, " episodio", salud.episodios_activos !== 1 ? 's' : '', " activo", salud.episodios_activos !== 1 ? 's' : '', salud.meds_activos > 0 && ` · ${salud.meds_activos} medicamento${salud.meds_activos !== 1 ? 's' : ''} en curso`), /*#__PURE__*/React.createElement("a", {
    href: "/bienestar/salud",
    style: {
      fontSize: 14,
      color: 'rgba(244,63,94,0.8)',
      textDecoration: 'none'
    }
  }, "\u2192"));
  const bodySection = /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 10
    }
  }, "M\xE9tricas Corporales"), bodyRows.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '11px 0',
      borderBottom: '1px solid color-mix(in srgb, var(--gold) 6%, transparent)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: C.textSub
    }
  }, r.label), r.label === 'Peso' && pesoSpark, /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 19,
      color: acc,
      display: 'flex',
      alignItems: 'baseline',
      gap: 6,
      justifyContent: 'flex-end'
    }
  }, r.val, r.label === 'Peso' && data && data.peso_trend != null && data.peso_trend !== 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      color: data.peso_trend < 0 ? '#7BC49A' : '#E59B92'
    }
  }, data.peso_trend < 0 ? '▼' : '▲', " ", Math.abs(data.peso_trend))), r.sub && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted
    }
  }, r.sub)))));
  const subsSection = /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 10
    }
  }, "Subm\xF3dulos"), subs.map((s, i) => {
    const tintBg = EU.catTint(s.hue, 'bg');
    const tintBorder = EU.catTint(s.hue, 'border');
    const tintText = EU.catTint(s.hue, 'text');
    return /*#__PURE__*/React.createElement("a", {
      key: i,
      href: s.href,
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: C.card,
        border: `1px solid ${s.alert ? 'rgba(244,63,94,0.4)' : 'var(--gold-border)'}`,
        borderRadius: 12,
        padding: '12px 14px',
        marginBottom: 8,
        textDecoration: 'none',
        transform: 'scale(1)',
        transition: 'border-color 0.18s, transform 0.18s, box-shadow 0.18s',
        animation: `eu-fade-in 0.3s ease ${i * 0.04}s both`
      },
      onMouseEnter: e => {
        e.currentTarget.style.borderColor = s.alert ? 'rgba(244,63,94,0.4)' : tintBorder;
        e.currentTarget.style.transform = 'scale(1.015)';
        e.currentTarget.style.boxShadow = `0 4px 16px ${tintBg}`;
      },
      onMouseLeave: e => {
        e.currentTarget.style.borderColor = s.alert ? 'rgba(244,63,94,0.4)' : 'var(--gold-border)';
        e.currentTarget.style.transform = 'scale(1)';
        e.currentTarget.style.boxShadow = 'none';
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 11
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: 34,
        height: 34,
        borderRadius: 10,
        flexShrink: 0,
        background: tintBg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 16
      }
    }, s.icon), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text
      }
    }, s.label), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: s.alert ? '#E59B92' : C.textMuted,
        marginTop: 1
      }
    }, s.sub))), /*#__PURE__*/React.createElement("span", {
      style: {
        color: tintText,
        fontSize: 15,
        opacity: 0.7
      }
    }, "\u203A"));
  }));
  const fadeKeyframes = /*#__PURE__*/React.createElement("style", null, `@keyframes eu-fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }`);
  if (isDesktop) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 340px',
        gap: '0 28px',
        alignItems: 'start'
      }
    }, fadeKeyframes, /*#__PURE__*/React.createElement("div", null, alertBanner, bodySection), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'sticky',
        top: 24
      }
    }, subsSection));
  }
  return /*#__PURE__*/React.createElement("div", null, fadeKeyframes, alertBanner, subsSection, bodySection);
}
function PaideiaExtra({
  acc
}) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [tip, setTip] = React.useState(null);
  const [tipSpin, setTipSpin] = React.useState(false);
  React.useEffect(() => {
    fetch('/paideia/api/summary').then(r => r.json()).then(d => {
      setData(d);
      setTip(d.tip);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);
  const refreshTip = e => {
    e.preventDefault();
    setTipSpin(true);
    fetch('/paideia/api/tip/refresh').then(r => r.json()).then(t => {
      setTip(t);
      setTipSpin(false);
    }).catch(() => setTipSpin(false));
  };
  if (loading) return /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      padding: '24px 0',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      letterSpacing: '0.1em'
    }
  }, "cargando\u2026");
  const stats = data && data.stats || {
    meta_anual: 12,
    leidos_este_anio: 0,
    total_leidos: 0,
    leyendo: 0,
    por_leer: 0,
    rating_prom: null
  };
  const leyendo = data && data.leyendo;
  const pct = stats.meta_anual > 0 ? Math.min(100, stats.leidos_este_anio / stats.meta_anual * 100) : 0;
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("style", null, `@keyframes eu-fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }`), /*#__PURE__*/React.createElement("a", {
    href: "/paideia/",
    style: {
      display: 'block',
      textDecoration: 'none',
      background: `linear-gradient(135deg, ${acc}, color-mix(in srgb, ${acc} 60%, white))`,
      borderRadius: 16,
      padding: '16px 18px',
      marginBottom: 16,
      animation: 'eu-fade-in 0.3s ease both'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      fontWeight: 600,
      color: 'rgba(9,7,15,0.65)',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      marginBottom: 6
    }
  }, "Meta de lectura"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 26,
      fontWeight: 700,
      color: '#09070F',
      marginBottom: 10
    }
  }, stats.leidos_este_anio, " / ", stats.meta_anual, " libros"), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 6,
      borderRadius: 3,
      background: 'rgba(9,7,15,0.15)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 3,
      background: '#09070F',
      width: `${pct}%`,
      transition: 'width 0.6s ease'
    }
  }))), leyendo && /*#__PURE__*/React.createElement("a", {
    href: "/paideia/",
    style: {
      display: 'block',
      textDecoration: 'none',
      background: C.card,
      border: '1px solid var(--gold-border)',
      borderRadius: 14,
      padding: '14px 16px',
      marginBottom: 16,
      animation: 'eu-fade-in 0.3s ease 0.05s both'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.12em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 8
    }
  }, "Leyendo ahora"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 14,
      fontWeight: 600,
      color: C.text
    }
  }, leyendo.titulo), leyendo.autor && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.textMuted,
      marginTop: 1
    }
  }, leyendo.autor), leyendo.paginas_totales > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      height: 4,
      borderRadius: 2,
      background: 'var(--gold-bg, rgba(201,168,76,0.15))',
      overflow: 'hidden',
      marginTop: 9
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 2,
      background: acc,
      width: `${Math.min(100, leyendo.paginas_actuales / leyendo.paginas_totales * 100)}%`
    }
  }))), tip && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      background: C.card,
      border: '1px solid var(--gold-border)',
      borderRadius: 14,
      padding: '14px 16px',
      marginBottom: 16,
      animation: 'eu-fade-in 0.3s ease 0.1s both'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 18,
      flexShrink: 0
    }
  }, tip.icon), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: C.text,
      lineHeight: 1.5
    }
  }, tip.text), /*#__PURE__*/React.createElement("button", {
    onClick: refreshTip,
    title: "Otro tip",
    style: {
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      color: C.textMuted,
      fontSize: 14,
      flexShrink: 0,
      transform: tipSpin ? 'rotate(180deg)' : 'none',
      transition: 'transform 0.3s'
    }
  }, "\u21BB")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 10
    }
  }, "Subm\xF3dulos"), /*#__PURE__*/React.createElement("a", {
    href: "/paideia/",
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      background: C.card,
      border: '1px solid var(--gold-border)',
      borderRadius: 12,
      padding: '12px 14px',
      textDecoration: 'none',
      transition: 'border-color 0.18s, transform 0.18s',
      animation: 'eu-fade-in 0.3s ease 0.15s both'
    },
    onMouseEnter: e => {
      e.currentTarget.style.borderColor = acc;
      e.currentTarget.style.transform = 'scale(1.01)';
    },
    onMouseLeave: e => {
      e.currentTarget.style.borderColor = 'var(--gold-border)';
      e.currentTarget.style.transform = 'scale(1)';
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 11
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 34,
      height: 34,
      borderRadius: 10,
      flexShrink: 0,
      background: EU.catTint(265, 'bg'),
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 16
    }
  }, "\uD83D\uDCDA"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: C.text
    }
  }, "Libros"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      color: C.textMuted,
      marginTop: 1
    }
  }, stats.total_leidos, " le\xEDdos \xB7 ", stats.leyendo, " leyendo \xB7 ", stats.por_leer, " por leer"))), /*#__PURE__*/React.createElement("span", {
    style: {
      color: EU.catTint(265, 'text'),
      fontSize: 15,
      opacity: 0.7
    }
  }, "\u203A")));
}
function ModuleExtra({
  id,
  acc,
  isDesktop
}) {
  const srv = window.EU._server || {};
  if (id === 'oikonomia') return /*#__PURE__*/React.createElement(OikonomiaExtra, null);
  if (id === 'cosmopolitismo') {
    const langs = srv.langStats && srv.langStats.length ? srv.langStats : [{
      lang: 'Alemán',
      lvl: 'B1+',
      entries: 0,
      pct: 0.72
    }, {
      lang: 'Inglés',
      lvl: 'C1',
      entries: 0,
      pct: 0.91
    }, {
      lang: 'Francés',
      lvl: 'A2',
      entries: 0,
      pct: 0.25
    }];
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("a", {
      href: "/idiomas/",
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: C.card,
        border: '1px solid var(--gold-border)',
        borderRadius: 12,
        padding: '11px 14px',
        marginBottom: 18,
        textDecoration: 'none',
        transition: 'border-color 0.18s'
      },
      onMouseEnter: e => e.currentTarget.style.borderColor = acc,
      onMouseLeave: e => e.currentTarget.style.borderColor = 'var(--gold-border)'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 18
      }
    }, "\uD83C\uDF0D"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text
      }
    }, "Cosmopolitismo"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: C.textMuted,
        marginTop: 1
      }
    }, "Lecciones \xB7 Vocabulario \xB7 Pr\xE1ctica"))), /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.textMuted,
        fontSize: 14
      }
    }, "\u203A")), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        letterSpacing: '0.15em',
        color: C.textMuted,
        textTransform: 'uppercase',
        marginBottom: 14
      }
    }, "Idiomas en Progreso"), langs.map((l, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        marginBottom: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'Cormorant Garamond,serif',
        fontSize: 17,
        color: C.text
      }
    }, l.lang), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: acc
      }
    }, l.lvl, l.entries ? ` · ${l.entries} entradas` : '')), /*#__PURE__*/React.createElement("div", {
      style: {
        height: 3,
        background: 'var(--gold-bg)',
        borderRadius: 2
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: '100%',
        borderRadius: 2,
        background: acc,
        width: `${(l.pct || 0) * 100}%`,
        boxShadow: `0 0 6px ${acc}66`
      }
    })))));
  }
  if (id === 'hegemonikon') return /*#__PURE__*/React.createElement(HegemonikonExtra, {
    acc: acc,
    isDesktop: isDesktop
  });
  if (id === 'paideia') return /*#__PURE__*/React.createElement(PaideiaExtra, {
    acc: acc,
    isDesktop: isDesktop
  });
  if (id === 'ataraxia') {
    const mkLink = (href, icon, label, sub) => /*#__PURE__*/React.createElement("a", {
      href: href,
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: C.card,
        border: '1px solid var(--gold-border)',
        borderRadius: 12,
        padding: '11px 14px',
        marginBottom: 8,
        textDecoration: 'none',
        transition: 'border-color 0.18s'
      },
      onMouseEnter: e => e.currentTarget.style.borderColor = acc,
      onMouseLeave: e => e.currentTarget.style.borderColor = 'var(--gold-border)'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 18
      }
    }, icon), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text
      }
    }, label), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: C.textMuted,
        marginTop: 1
      }
    }, sub))), /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.textMuted,
        fontSize: 14
      }
    }, "\u203A"));
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        letterSpacing: '0.15em',
        color: C.textMuted,
        textTransform: 'uppercase',
        marginBottom: 10
      }
    }, "Subm\xF3dulos"), mkLink('/ataraxia/', '⚓', 'Ataraxia', 'Checklist semanal · Orden'), mkLink('/sabado/', '🧹', 'Sábado Reset', 'Ritual matutino de limpieza'), mkLink('/gtd/', '🎯', 'Praxis GTD', 'Inbox · Next Actions · Proyectos'));
  }
  if (id === 'logoi') {
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        letterSpacing: '0.15em',
        color: C.textMuted,
        textTransform: 'uppercase',
        marginBottom: 10
      }
    }, "Subm\xF3dulos"), /*#__PURE__*/React.createElement("a", {
      href: "/actividades",
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: C.card,
        border: '1px solid var(--gold-border)',
        borderRadius: 12,
        padding: '11px 14px',
        marginBottom: 8,
        textDecoration: 'none',
        transition: 'border-color 0.18s'
      },
      onMouseEnter: e => e.currentTarget.style.borderColor = acc,
      onMouseLeave: e => e.currentTarget.style.borderColor = 'var(--gold-border)'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 18
      }
    }, "\uD83D\uDCBB"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text
      }
    }, "Acta Diurna"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: C.textMuted,
        marginTop: 1
      }
    }, "Programaci\xF3n \xB7 L\xF3gica \xB7 Proyectos"))), /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.textMuted,
        fontSize: 14
      }
    }, "\u203A")));
  }
  if (id === 'eurythmia') {
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 9,
        letterSpacing: '0.15em',
        color: C.textMuted,
        textTransform: 'uppercase',
        marginBottom: 10
      }
    }, "Subm\xF3dulos"), /*#__PURE__*/React.createElement("a", {
      href: "/actividades",
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: C.card,
        border: '1px solid var(--gold-border)',
        borderRadius: 12,
        padding: '11px 14px',
        marginBottom: 8,
        textDecoration: 'none',
        transition: 'border-color 0.18s'
      },
      onMouseEnter: e => e.currentTarget.style.borderColor = acc,
      onMouseLeave: e => e.currentTarget.style.borderColor = 'var(--gold-border)'
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 18
      }
    }, "\uD83D\uDD7A"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text
      }
    }, "Acta Diurna"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: C.textMuted,
        marginTop: 1
      }
    }, "Baile \xB7 Ritmo \xB7 Pr\xE1ctica"))), /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.textMuted,
        fontSize: 14
      }
    }, "\u203A")));
  }
  return null;
}

// ═══════════════════════════════════════════════════════════
// PRAXIS INBOX — GTD tabs (extracted, not yet wired to Acta)
// ═══════════════════════════════════════════════════════════
function PraxisInbox({
  isDesktop
}) {
  const [gtdTab, setGtdTab] = useState('inbox');
  const [inbox, setInbox] = useState(EU.gtd.inbox);
  const [newItem, setNewItem] = useState('');
  const [inputFocus, setInputFocus] = useState(false);
  const addItem = () => {
    if (!newItem.trim()) return;
    setInbox(p => [...p, {
      id: Date.now(),
      text: newItem.trim(),
      context: '@inbox'
    }]);
    setNewItem('');
  };
  const GTD_TABS = [{
    id: 'inbox',
    label: 'Inbox',
    count: inbox.length
  }, {
    id: 'projects',
    label: 'Proyectos',
    count: EU.gtd.projects.length
  }, {
    id: 'contexts',
    label: 'Contextos'
  }, {
    id: 'review',
    label: 'Revisión'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--gold-bg)',
      marginTop: 4
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      borderBottom: '1px solid var(--gold-bg)',
      padding: isDesktop ? '0 24px' : '0 20px'
    }
  }, GTD_TABS.map(t => /*#__PURE__*/React.createElement("div", {
    key: t.id,
    onClick: () => setGtdTab(t.id),
    style: {
      flex: 1,
      padding: '11px 2px',
      textAlign: 'center',
      cursor: 'pointer',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      fontWeight: gtdTab === t.id ? 700 : 400,
      color: gtdTab === t.id ? C.gold : C.textMuted,
      borderBottom: gtdTab === t.id ? `2px solid ${C.gold}` : '2px solid transparent',
      transition: 'all 0.2s'
    }
  }, t.label, t.count != null && /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 5,
      fontSize: 9,
      borderRadius: 9,
      padding: '1px 6px',
      background: gtdTab === t.id ? C.gold : 'rgba(201,168,76,0.14)',
      color: gtdTab === t.id ? C.deep : C.textSub
    }
  }, t.count)))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '16px 24px 0' : '16px 20px 0'
    }
  }, gtdTab === 'inbox' && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginBottom: 14,
      background: C.card,
      border: `1.5px solid ${inputFocus ? C.gold : 'var(--b)'}`,
      borderRadius: 10,
      padding: '4px 4px 4px 14px',
      alignItems: 'center',
      boxShadow: inputFocus ? '0 0 0 3px rgba(201,168,76,0.12)' : 'none',
      transition: 'all 0.15s'
    }
  }, /*#__PURE__*/React.createElement("input", {
    value: newItem,
    onChange: e => setNewItem(e.target.value),
    onKeyDown: e => e.key === 'Enter' && addItem(),
    onFocus: () => setInputFocus(true),
    onBlur: () => setInputFocus(false),
    placeholder: "Capturar pensamiento...",
    style: {
      flex: 1,
      background: 'none',
      border: 'none',
      outline: 'none',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: C.text
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: addItem,
    style: {
      background: C.gold,
      border: 'none',
      borderRadius: 7,
      width: 34,
      height: 34,
      cursor: 'pointer',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 20,
      color: C.deep,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      lineHeight: 1
    }
  }, "+")), inbox.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      padding: '40px 0',
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 17,
      color: C.textMuted
    }
  }, "Inbox limpio. Mente clara.") : inbox.map(item => /*#__PURE__*/React.createElement("div", {
    key: item.id,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '11px 0',
      borderBottom: '1px solid color-mix(in srgb, var(--gold) 6%, transparent)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: 'color-mix(in srgb, var(--gold) 28%, transparent)',
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: C.text
    }
  }, item.text), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted
    }
  }, item.context), /*#__PURE__*/React.createElement("button", {
    onClick: () => setInbox(p => p.filter(i => i.id !== item.id)),
    style: {
      background: 'none',
      border: 'none',
      color: C.textMuted,
      cursor: 'pointer',
      fontSize: 18,
      padding: '0 2px',
      lineHeight: 1
    }
  }, "\xD7"))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted,
      textAlign: 'center',
      marginTop: 10
    }
  }, inbox.length, " elemento", inbox.length !== 1 ? 's' : '')), gtdTab === 'projects' && EU.gtd.projects.map(p => {
    const pct = p.done / p.actions;
    return /*#__PURE__*/React.createElement("div", {
      key: p.id,
      style: {
        background: C.card,
        border: '1px solid var(--gold-bg)',
        borderRadius: 12,
        padding: '14px 16px',
        marginBottom: 9
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 13,
        color: C.text,
        marginBottom: 9
      }
    }, p.name), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        height: 3,
        background: 'var(--gold-bg)',
        borderRadius: 2
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: '100%',
        borderRadius: 2,
        background: C.gold,
        width: `${pct * 100}%`,
        boxShadow: '0 0 6px var(--gold-glow)'
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: C.textMuted,
        whiteSpace: 'nowrap'
      }
    }, p.done, "/", p.actions)));
  }), gtdTab === 'contexts' && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 8,
      paddingTop: 4
    }
  }, EU.gtd.contexts.map(ctx => /*#__PURE__*/React.createElement("div", {
    key: ctx,
    style: {
      padding: '8px 14px',
      background: C.card,
      border: '1px solid color-mix(in srgb, var(--gold) 12%, transparent)',
      borderRadius: 20,
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: C.textSub
    }
  }, ctx))), gtdTab === 'review' && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 15,
      color: C.textSub,
      lineHeight: 1.65,
      marginBottom: 18,
      textWrap: 'pretty'
    }
  }, "\"La revisi\xF3n semanal es el mantenimiento del sistema. Sin ella, el GTD colapsa.\""), EU.gtd.review.map((item, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '10px 0',
      borderBottom: '1px solid color-mix(in srgb, var(--gold) 6%, transparent)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 20,
      height: 20,
      borderRadius: 6,
      flexShrink: 0,
      border: `1.5px solid ${item.done ? C.gold : 'color-mix(in srgb, var(--gold) 20%, transparent)'}`,
      background: item.done ? C.gold : 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, item.done && /*#__PURE__*/React.createElement("svg", {
    width: 10,
    height: 10,
    viewBox: "0 0 10 10"
  }, /*#__PURE__*/React.createElement("polyline", {
    points: "2,5 4.5,8 8,2",
    stroke: C.deep,
    strokeWidth: 1.5,
    fill: "none",
    strokeLinecap: "round"
  }))), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 13,
      color: item.done ? C.textMuted : C.text,
      textDecoration: item.done ? 'line-through' : 'none'
    }
  }, item.label))))));
}

// ═══════════════════════════════════════════════════════════
// UNDO TOAST
// ═══════════════════════════════════════════════════════════
function useUndoToast() {
  const [toast, setToast] = useState(null); // {key, logId, label, pts, id}
  const timer = useRef(null);
  const show = (key, logId, label, pts) => {
    if (timer.current) clearTimeout(timer.current);
    setToast({
      key,
      logId,
      label,
      pts,
      id: Date.now()
    });
    timer.current = setTimeout(() => setToast(null), 5000);
  };
  const dismiss = () => {
    if (timer.current) clearTimeout(timer.current);
    setToast(null);
  };
  return {
    toast,
    show,
    dismiss
  };
}
function UndoToast({
  toast,
  onUndo,
  onDismiss,
  isDesktop
}) {
  if (!toast) return null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: isDesktop ? 24 : 88,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 9999,
      background: C.card,
      border: '1px solid color-mix(in srgb, var(--gold) 25%, transparent)',
      borderRadius: 12,
      padding: '12px 16px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.55)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      minWidth: 240,
      maxWidth: 'calc(100vw - 32px)',
      animation: 'euScaleIn 0.2s ease'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 12,
      color: C.text,
      lineHeight: 1.3
    }
  }, toast.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.gold,
      marginTop: 2
    }
  }, "+", toast.pts, " XP registrado")), /*#__PURE__*/React.createElement("button", {
    onClick: onUndo,
    style: {
      background: 'transparent',
      border: '1px solid var(--b2)',
      borderRadius: 6,
      padding: '5px 12px',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: C.gold,
      cursor: 'pointer',
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      flexShrink: 0,
      transition: 'all 0.15s'
    }
  }, "Deshacer"), /*#__PURE__*/React.createElement("button", {
    onClick: onDismiss,
    style: {
      background: 'none',
      border: 'none',
      color: C.textMuted,
      cursor: 'pointer',
      fontSize: 16,
      padding: '0 2px',
      lineHeight: 1
    }
  }, "\xD7"), /*#__PURE__*/React.createElement("div", {
    key: toast.id,
    style: {
      position: 'absolute',
      bottom: 0,
      left: 0,
      height: 3,
      borderRadius: '0 0 12px 12px',
      background: `linear-gradient(90deg,${C.gold},${C.goldLight})`,
      animation: 'undoCountdown 5s linear forwards',
      width: '100%'
    }
  }));
}

// ═══════════════════════════════════════════════════════════
// ACTIVITY BUTTON
// ═══════════════════════════════════════════════════════════
function ActivityButton({
  act,
  catHue,
  onLog
}) {
  const {
    isLight
  } = useTheme();
  const [burst, setBurst] = useState(false);
  const isAlto = act.tier === 'alto';
  const handle = () => {
    if (!act.done) {
      setBurst(true);
      setTimeout(() => setBurst(false), 700);
    }
    onLog(act.key);
  };
  const dirs = [[26, -26], [36, 0], [26, 26], [0, 34], [-26, 26], [-36, 0], [-26, -26], [0, -34]];
  const burstColor = isAlto ? '#fbbf24' : EU.catTint(catHue, 'text');
  return /*#__PURE__*/React.createElement("div", {
    onClick: handle,
    style: {
      display: 'flex',
      flexDirection: 'column',
      padding: '10px 12px',
      borderRadius: 10,
      cursor: 'pointer',
      background: act.done ? isAlto ? 'rgba(245,158,11,0.07)' : 'rgba(99,102,241,0.07)' : C.card,
      border: act.done ? isAlto ? '1px solid rgba(245,158,11,0.3)' : '1px solid rgba(99,102,241,0.25)' : `1px solid ${EU.catTint(catHue, 'border')}`,
      minHeight: 52,
      gap: 5,
      transition: 'all 0.18s',
      position: 'relative',
      overflow: 'hidden'
    }
  }, isAlto && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      right: 0,
      background: act.done ? 'rgba(245,158,11,0.35)' : 'rgba(245,158,11,0.14)',
      color: '#fbbf24',
      fontSize: 7,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      padding: '2px 7px',
      borderRadius: '0 10px 0 6px',
      transition: 'background 0.2s'
    }
  }, "ALTO"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 16,
      height: 16,
      borderRadius: 5,
      flexShrink: 0,
      border: `1.5px solid ${act.done ? isAlto ? '#fbbf24' : 'rgba(99,102,241,0.7)' : EU.catTint(catHue, 'border')}`,
      background: act.done ? isAlto ? '#fbbf24' : 'rgba(99,102,241,0.8)' : 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.2s',
      boxShadow: act.done ? isAlto ? '0 0 8px rgba(245,158,11,0.4)' : '0 0 8px rgba(99,102,241,0.35)' : 'none'
    }
  }, act.done && /*#__PURE__*/React.createElement("svg", {
    width: 9,
    height: 9,
    viewBox: "0 0 9 9"
  }, /*#__PURE__*/React.createElement("polyline", {
    points: "1.5,4.5 3.7,7 7.5,1.5",
    stroke: isAlto ? '#1a1210' : '#fff',
    strokeWidth: 1.6,
    fill: "none",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }))), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 11,
      color: act.done ? C.textMuted : C.textSub,
      fontWeight: act.done ? 500 : 400,
      lineHeight: 1.3,
      flex: 1,
      textDecoration: act.done ? 'none' : 'none'
    }
  }, act.label)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'flex-end',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      padding: '1px 6px',
      borderRadius: 100,
      background: act.done ? isAlto ? 'linear-gradient(135deg,rgba(245,158,11,0.5),rgba(234,179,8,0.5))' : 'linear-gradient(135deg,rgba(99,102,241,0.7),rgba(139,92,246,0.7))' : EU.catTint(catHue, 'bg'),
      color: act.done ? '#fff' : EU.catTint(catHue, 'text'),
      border: act.done ? 'none' : `1px solid ${EU.catTint(catHue, 'border')}`
    }
  }, "+", act.pts, " XP", act.ec > 0 ? ` · ${act.ec}🪙` : '')), burst && dirs.map(([dx, dy], i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      position: 'absolute',
      left: '50%',
      top: '50%',
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: burstColor,
      transform: `translate(${dx}px,${dy}px)`,
      opacity: 0,
      animation: 'euBurst 0.65s ease-out forwards',
      animationDelay: `${i * 0.025}s`,
      pointerEvents: 'none'
    }
  })));
}

// ═══════════════════════════════════════════════════════════
// ACTA DIURNA SCREEN
// ═══════════════════════════════════════════════════════════
function ActaDiurnaScreen({
  appState,
  dispatch,
  isDesktop
}) {
  const srv = window.EU._server || {};
  const [acts, setActs] = useState(srv.activities || []);
  const [pts, setPts] = useState(srv.pts || {
    today: 0,
    week: 0,
    month: 0
  });
  const [streak, setStreak] = useState(srv.streak || 0);
  const actCats = srv.actCats || [];
  const {
    level,
    xp,
    xpNext
  } = appState;
  const [xpToday, setXpToday] = useState(srv.xpToday || 0);
  const [clf, setClf] = useState(srv.classification || {});
  const [loaded, setLoaded] = useState(!!(srv.activities && srv.activities.length > 0));
  const XP_GOAL = 15;
  const xpDayPct = Math.min(1, xpToday / XP_GOAL);
  useEffect(() => {
    fetch('/actividades/api/today').then(r => r.json()).then(data => {
      if (data.activities) {
        setActs(data.activities);
        window.EU._server.activities = data.activities;
      }
      // /api/today devuelve data.xp (no data.pts)
      if (data.xp) {
        const newPts = {
          today: data.xp.today,
          week: data.xp.week,
          month: data.xp.month
        };
        setPts(newPts);
        window.EU._server.pts = newPts;
        setXpToday(data.xp.today);
        window.EU._server.xpToday = data.xp.today;
      }
      if (data.streak !== undefined) {
        setStreak(data.streak);
        window.EU._server.streak = data.streak;
      }
      if (data.classification) {
        setClf(data.classification);
        window.EU._server.classification = data.classification;
      }
      setLoaded(true);
    }).catch(() => {
      setLoaded(true);
    });
  }, []);
  const logActivity = key => {
    const source = window.EU._server.activities || acts;
    const act = source.find(a => a.key === key);
    const updated = source.map(a => a.key === key ? {
      ...a,
      done: !a.done
    } : a);
    window.EU._server.activities = updated;
    setActs(updated);
    fetch('/actividades/api/activity/log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        key
      })
    }).then(r => r.json()).then(data => {
      if (data.stats) {
        const newXp = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
        setXpToday(newXp);
        window.EU._server.xpToday = newXp;
        const newPts = {
          today: data.stats.pts_today,
          week: data.stats.pts_week,
          month: data.stats.pts_month
        };
        setPts(newPts);
        window.EU._server.pts = newPts;
        if (data.stats.streak !== undefined) {
          setStreak(data.stats.streak);
          window.EU._server.streak = data.stats.streak;
        }
      }
      if (data.gam && (data.gam.xp_delta || data.gam.xp)) dispatch({
        type: 'ADD_XP',
        amount: data.gam.xp_delta || data.gam.xp
      });
      if (data.gam?.achievements?.length) window.euFireAchievements(data.gam.achievements);
      if (data.gam?.perfect_day) {
        window.dispatchEvent(new CustomEvent('eu:perfect-day', {
          detail: {
            bonusXp: data.gam.perfect_day.xp || 5,
            bonusEc: data.gam.perfect_day.ec || 10
          }
        }));
      } else if (data.gam?.combo_bonuses?.length) {
        data.gam.combo_bonuses.forEach(c => window.dispatchEvent(new CustomEvent('eu:combo-bonus', {
          detail: c
        })));
      }
      if (data.action === 'added' && data.log_id && act) {
        undoToast.show(key, data.log_id, act.label, act.pts);
      } else {
        undoToast.dismiss();
      }
    }).catch(() => {});
  };
  const undoToast = useUndoToast();
  const handleUndo = () => {
    const t = undoToast.toast;
    if (!t) return;
    const source = window.EU._server.activities || acts;
    const restored = source.map(a => a.key === t.key ? {
      ...a,
      done: false
    } : a);
    window.EU._server.activities = restored;
    setActs(restored);
    fetch(`/actividades/api/activity/undo/${t.logId}`, {
      method: 'POST'
    }).then(r => r.json()).then(data => {
      if (data.stats) {
        const newXp = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
        setXpToday(newXp);
        window.EU._server.xpToday = newXp;
        const newPts = {
          today: data.stats.pts_today,
          week: data.stats.pts_week,
          month: data.stats.pts_month
        };
        setPts(newPts);
        window.EU._server.pts = newPts;
      }
      if (data.gam && data.gam.xp_delta) dispatch({
        type: 'ADD_XP',
        amount: data.gam.xp_delta
      });
    }).catch(() => {});
    undoToast.dismiss();
  };
  if (!loaded) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        padding: isDesktop ? '28px 24px' : '16px 20px'
      }
    }, /*#__PURE__*/React.createElement(Skeleton, {
      kind: "card",
      height: 180
    }), /*#__PURE__*/React.createElement(Skeleton, {
      kind: "card",
      height: 60,
      style: {
        marginTop: 12
      }
    }), [1, 2, 3].map(i => /*#__PURE__*/React.createElement(Skeleton, {
      key: i,
      kind: "card",
      height: 200,
      style: {
        marginTop: 12
      }
    })));
  }
  const byCategory = {};
  actCats.forEach(cat => {
    byCategory[cat] = [];
  });
  acts.forEach(a => {
    if (byCategory[a.cat]) byCategory[a.cat].push(a);else {
      byCategory[a.cat] = [a];
    }
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: '100vh',
      paddingBottom: isDesktop ? 48 : 100
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '28px 24px 20px' : '16px 20px 16px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'linear-gradient(140deg, var(--surf), var(--bg))',
      border: '1px solid var(--gold-border)',
      borderRadius: 16,
      padding: '20px',
      marginBottom: 14,
      position: 'relative',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      letterSpacing: '0.18em',
      color: C.gold,
      opacity: 0.6,
      textTransform: 'uppercase'
    }
  }, "Acta Diurna \xB7 XP hoy"), clf.rank && (() => {
    const curTier = TIERS.find(t => t.rank === clf.rank) || TIERS[0];
    const CurIcon = curTier.Icon;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        background: 'rgba(255,255,255,0.05)',
        borderRadius: 20,
        padding: '3px 10px'
      }
    }, /*#__PURE__*/React.createElement(CurIcon, {
      size: 12,
      style: {
        color: curTier.color
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        color: C.textMuted,
        letterSpacing: '0.08em',
        textTransform: 'uppercase'
      }
    }, curTier.label));
  })()), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 64,
      lineHeight: 1,
      color: C.goldLight,
      fontWeight: 600
    }
  }, xpToday), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: C.textMuted
    }
  }, "/ ", XP_GOAL, " meta")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 5,
      background: 'var(--gold-bg)',
      borderRadius: 3,
      overflow: 'hidden',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      borderRadius: 3,
      background: 'linear-gradient(90deg, color-mix(in srgb, var(--gold) 60%, #000), var(--gold), var(--gold-l))',
      width: `${xpDayPct * 100}%`,
      boxShadow: '0 0 8px var(--gold-glow)',
      transition: 'width 0.8s ease'
    }
  })), (() => {
    const curIdx = TIERS.findIndex(t => t.rank === clf.rank);
    const ci = curIdx >= 0 ? curIdx : 0;
    const nt = TIERS[ci + 1] || null;
    const col = TIERS[ci].color;
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'flex-start',
        marginBottom: 8
      }
    }, TIERS.map((t, i) => {
      const active = i === ci;
      const past = i < ci;
      const TIcon = t.Icon;
      return /*#__PURE__*/React.createElement(React.Fragment, {
        key: t.rank
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 4,
          flex: 1
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: active ? 9 : 5,
          height: active ? 9 : 5,
          borderRadius: '50%',
          background: active ? col : past ? `${col}55` : 'rgba(255,255,255,0.08)',
          boxShadow: active ? `0 0 9px ${col}` : 'none',
          transition: 'all 0.3s'
        }
      }), /*#__PURE__*/React.createElement(TIcon, {
        size: 9,
        style: {
          color: active ? col : C.textMuted,
          opacity: active ? 1 : past ? 0.55 : 0.28
        }
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          fontFamily: 'DM Sans,sans-serif',
          fontSize: 7,
          color: active ? col : C.textMuted,
          opacity: active ? 1 : past ? 0.55 : 0.28,
          textAlign: 'center',
          lineHeight: 1.3
        }
      }, t.label)), i < TIERS.length - 1 && /*#__PURE__*/React.createElement("div", {
        style: {
          height: 1,
          flex: 1,
          marginTop: 4,
          background: i < ci ? `${col}35` : 'rgba(255,255,255,0.06)'
        }
      }));
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.textMuted
      }
    }, nt ? `${Math.max(0, nt.threshold - xpToday)} XP → ${nt.label}` : '✦ Diamante alcanzado'), /*#__PURE__*/React.createElement("span", {
      style: {
        color: C.gold,
        opacity: 0.7
      }
    }, xpNext ? `${xpNext - xp} XP → ${EU.levels[level]?.name || ''}` : '')));
  })()), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr',
      gap: 8,
      marginBottom: 16
    }
  }, [{
    label: 'SEMANA',
    val: pts.week,
    sub: 'meta 50+'
  }, {
    label: 'MES',
    val: pts.month,
    sub: 'meta 300+'
  }, {
    label: 'RACHA',
    val: streak > 0 ? `${streak}d` : '—',
    sub: 'días'
  }].map(s => /*#__PURE__*/React.createElement("div", {
    key: s.label,
    style: {
      background: C.card,
      border: '1px solid var(--gold-bg)',
      borderRadius: 10,
      padding: '10px 8px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 7,
      letterSpacing: '0.1em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 2
    }
  }, s.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 20,
      color: C.gold,
      lineHeight: 1
    }
  }, s.val), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 8,
      color: C.textMuted,
      marginTop: 2
    }
  }, s.sub)))), (actCats.length > 0 ? actCats : Object.keys(byCategory)).map(cat => {
    const catActs = byCategory[cat] || [];
    if (!catActs.length) return null;
    const catHue = (EU.catHues || {})[cat] || 45;
    const doneCnt = catActs.filter(a => a.done).length;
    const total = catActs.length;
    const pct = total > 0 ? doneCnt / total : 0;
    const complete = doneCnt === total && total > 0;
    return /*#__PURE__*/React.createElement("div", {
      key: cat,
      "data-cat": cat,
      style: {
        background: EU.catTint(catHue, 'bg'),
        border: `1px solid ${complete ? EU.catTint(catHue, 'border') : 'var(--b)'}`,
        borderRadius: 14,
        padding: '14px',
        marginBottom: 14,
        transition: 'border-color 0.3s'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 8
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: 7,
        height: 7,
        borderRadius: '50%',
        flexShrink: 0,
        background: doneCnt > 0 ? EU.catTint(catHue, 'text') : 'var(--b2)',
        boxShadow: doneCnt > 0 ? `0 0 6px ${EU.catTint(catHue, 'text')}` : 'none',
        transition: 'all 0.3s'
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        flex: 1,
        color: EU.catTint(catHue, 'text')
      }
    }, cat), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'DM Sans,sans-serif',
        fontSize: 10,
        color: complete ? EU.catTint(catHue, 'text') : C.textMuted
      }
    }, doneCnt, "/", total)), /*#__PURE__*/React.createElement("div", {
      style: {
        height: 3,
        background: 'var(--b)',
        borderRadius: 2,
        overflow: 'hidden',
        marginBottom: 10
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: '100%',
        borderRadius: 2,
        background: EU.catTint(catHue, 'text'),
        width: `${pct * 100}%`,
        boxShadow: pct > 0 ? `0 0 5px ${EU.catTint(catHue, 'text')}` : 'none',
        transition: 'width 0.5s ease'
      }
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 6
      }
    }, catActs.map(act => /*#__PURE__*/React.createElement(ActivityButton, {
      key: act.key,
      act: act,
      catHue: catHue,
      onLog: logActivity
    }))));
  }), acts.length === 0 && /*#__PURE__*/React.createElement(EmptyState, {
    icon: "check-square",
    title: "El d\xEDa est\xE1 en blanco",
    desc: "Marc\xE1 tu primera virtud para abrir la cuenta de hoy.",
    cta: "Empezar",
    kbd: "\u2193",
    onAction: () => {
      const first = document.querySelector('[data-cat]');
      if (first) {
        const top = first.getBoundingClientRect().top + window.scrollY - 80;
        window.scrollTo({
          top,
          behavior: 'smooth'
        });
      }
    }
  })), /*#__PURE__*/React.createElement(UndoToast, {
    toast: undoToast.toast,
    onUndo: handleUndo,
    onDismiss: undoToast.dismiss,
    isDesktop: isDesktop
  }));
}

// ═══════════════════════════════════════════════════════════
// PROFILE SCREEN
// ═══════════════════════════════════════════════════════════
function ProfileScreen({
  appState,
  isDesktop
}) {
  const {
    level,
    xp,
    xpNext,
    totalXP,
    modules
  } = appState;
  const d = window.__EUDAIMONIA_DATA__ || {};
  const maxStreak = d.max_streak ?? 0;
  const weeksActive = d.weeks_active ?? 0;
  const ecBalance = (window.EU._server || {}).ecBalance ?? 0;
  const lv = EU.levels[level - 1];
  const xpPct = xpNext ? xp / xpNext : 1;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: '100vh',
      paddingBottom: isDesktop ? 48 : 100
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '28px 24px 0' : '16px 20px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.2em',
      color: C.gold,
      textTransform: 'uppercase',
      opacity: 0.6,
      marginBottom: 4
    }
  }, "\u0391\u03A5\u03A4\u039F\u03A3"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 28,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.05em',
      marginBottom: 14
    }
  }, "Perfil"), /*#__PURE__*/React.createElement("a", {
    href: "/perfil",
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      background: C.card,
      border: '1px solid var(--gold-border)',
      borderRadius: 12,
      padding: '13px 16px',
      marginBottom: 20,
      textDecoration: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 15,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.08em'
    }
  }, "Ver Perfil Completo"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.gold,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginTop: 3,
      opacity: 0.75
    }
  }, "Medidas \xB7 Datos personales")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 22,
      color: C.gold,
      opacity: 0.5
    }
  }, "\u2192"))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 16px 20px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: `linear-gradient(135deg,${C.card},${C.surface})`,
      border: '1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
      borderRadius: 20,
      padding: '24px',
      textAlign: 'center',
      boxShadow: '0 8px 40px rgba(0,0,0,0.5)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'center',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement(GreekColumn, {
    level: level,
    xpPct: xpPct,
    size: 80
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.18em',
      color: C.gold,
      opacity: 0.6
    }
  }, "NIVEL ", level), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 30,
      fontWeight: 600,
      color: C.text,
      letterSpacing: '0.08em',
      marginTop: 3
    }
  }, lv?.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontStyle: 'italic',
      fontSize: 14,
      color: C.textSub,
      marginTop: 2
    }
  }, lv?.sub))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '0 24px' : '0 16px',
      display: 'grid',
      gridTemplateColumns: isDesktop ? 'repeat(5,1fr)' : '1fr 1fr',
      gap: 8,
      marginBottom: 20
    }
  }, [{
    label: 'XP Total',
    val: totalXP.toLocaleString()
  }, {
    label: 'Racha Mayor',
    val: `${maxStreak} días`
  }, {
    label: 'Hoy',
    val: `${modules.filter(m => m.done).length}/${modules.length} mods`
  }, {
    label: 'Semanas activo',
    val: String(weeksActive)
  }, {
    label: 'EC Disponibles',
    val: `${ecBalance} 🪙`,
    accent: true,
    href: '/recompensas'
  }].map(s => /*#__PURE__*/React.createElement("div", {
    key: s.label,
    onClick: s.href ? () => window.location.href = s.href : undefined,
    style: {
      background: s.accent ? 'color-mix(in srgb, var(--gold) 6%, transparent)' : C.card,
      border: s.accent ? '1px solid color-mix(in srgb, var(--gold) 25%, transparent)' : '1px solid var(--gold-bg)',
      borderRadius: 12,
      padding: '14px',
      cursor: s.href ? 'pointer' : 'default'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginBottom: 4
    }
  }, s.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 24,
      color: C.gold
    }
  }, s.val)))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: isDesktop ? '0 24px' : '0 16px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      letterSpacing: '0.15em',
      color: C.textMuted,
      textTransform: 'uppercase',
      marginBottom: 12
    }
  }, "Camino al Eudaim\xF3n"), EU.levels.map(lv => /*#__PURE__*/React.createElement("div", {
    key: lv.n,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '9px 0',
      borderBottom: '1px solid color-mix(in srgb, var(--gold) 5%, transparent)',
      opacity: lv.n > level ? 0.35 : 1,
      transition: 'opacity 0.3s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 28,
      height: 28,
      borderRadius: 8,
      flexShrink: 0,
      background: lv.n < level ? C.gold : lv.n === level ? 'var(--b)' : C.card,
      border: `1.5px solid ${lv.n <= level ? C.gold : 'var(--gold-bg)'}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 10,
      color: lv.n < level ? C.deep : C.gold
    }
  }, lv.n < level ? '✓' : lv.n), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'Cormorant Garamond,serif',
      fontSize: 15,
      letterSpacing: '0.05em',
      color: lv.n <= level ? C.text : C.textMuted
    }
  }, lv.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.textMuted
    }
  }, lv.sub)), lv.n === level && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 9,
      color: C.gold,
      opacity: 0.7,
      letterSpacing: '0.08em'
    }
  }, "ACTUAL")))));
}
Object.assign(window, {
  HomeScreen,
  CommandCenterScreen,
  ModuleDetailScreen,
  ActaDiurnaScreen,
  PraxisInbox,
  ProfileScreen
});
// ── Command Palette ⌘K ───────────────────────────────────────────────────────
const {
  useState: _cpUseState,
  useMemo: _cpUseMemo,
  useEffect: _cpUseEffect
} = React;
function CommandPalette({
  open,
  onClose,
  items
}) {
  const [q, setQ] = _cpUseState('');
  const [idx, setIdx] = _cpUseState(0);
  const filtered = _cpUseMemo(() => {
    if (!q.trim()) return items;
    const t = q.toLowerCase();
    return items.filter(it => (it.label + ' ' + (it.sub || '')).toLowerCase().includes(t));
  }, [items, q]);
  _cpUseEffect(() => {
    setIdx(0);
  }, [q]);
  _cpUseEffect(() => {
    if (!open) {
      setQ('');
      setIdx(0);
      return;
    }
    const onKey = e => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setIdx(i => Math.min(filtered.length - 1, i + 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setIdx(i => Math.max(0, i - 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const sel = filtered[idx];
        if (sel) {
          sel.run();
          onClose();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, filtered, idx, onClose]);
  if (!open) return null;
  const C2 = window.EU.getColors();

  // Group items into sections
  const navItems = filtered.filter(i => i.section === 'nav');
  const sysItems = filtered.filter(i => i.section === 'sys');
  const actItems = filtered.filter(i => i.section === 'act');
  let globalIdx = 0;
  const renderItem = item => {
    const myIdx = globalIdx++;
    const isActive = myIdx === idx;
    return /*#__PURE__*/React.createElement("div", {
      key: item.label + myIdx,
      onMouseEnter: () => setIdx(myIdx),
      onClick: () => {
        item.run();
        onClose();
      },
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 16px',
        cursor: 'pointer',
        borderLeft: isActive ? `2px solid ${C2.gold}` : '2px solid transparent',
        background: isActive ? 'color-mix(in srgb, var(--gold) 7%, transparent)' : 'transparent',
        transition: 'background 0.12s'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 28,
        height: 28,
        borderRadius: 7,
        flexShrink: 0,
        background: 'color-mix(in srgb, var(--gold) 7%, transparent)',
        border: '1px solid color-mix(in srgb, var(--gold) 12%, transparent)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 13,
        color: C2.gold
      }
    }, item.i), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        color: C2.text,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, item.label), item.sub && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: C2.textMuted,
        marginTop: 1
      }
    }, item.sub)), item.keys && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 3,
        flexShrink: 0
      }
    }, item.keys.map(k => /*#__PURE__*/React.createElement("kbd", {
      key: k,
      style: {
        background: 'var(--gold-bg)',
        border: '1px solid var(--gold-border)',
        borderRadius: 4,
        padding: '1px 5px',
        fontSize: 10,
        color: C2.gold,
        fontFamily: 'DM Sans,sans-serif'
      }
    }, k))));
  };
  const SectionHeader = ({
    title
  }) => /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      letterSpacing: '0.2em',
      textTransform: 'uppercase',
      color: C2.textMuted,
      padding: '10px 16px 4px',
      opacity: 0.55
    }
  }, title);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 900,
      background: 'color-mix(in srgb, var(--bg) 75%, transparent)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'center',
      padding: '15vh 16px 0'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: '100%',
      maxWidth: 580,
      background: 'var(--card)',
      border: `1px solid ${C2.goldBorder}`,
      borderRadius: 12,
      boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '12px 16px',
      borderBottom: '1px solid var(--gold-bg)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: C2.gold,
      fontSize: 16,
      flexShrink: 0
    }
  }, "⌘"), /*#__PURE__*/React.createElement("input", {
    autoFocus: true,
    value: q,
    onChange: e => setQ(e.target.value),
    placeholder: "Buscar acciones...",
    style: {
      flex: 1,
      background: 'transparent',
      border: 'none',
      outline: 'none',
      fontFamily: 'DM Sans,sans-serif',
      fontSize: 15,
      color: C2.text
    }
  }), /*#__PURE__*/React.createElement("kbd", {
    onClick: onClose,
    style: {
      background: 'color-mix(in srgb, var(--gold) 7%, transparent)',
      border: '1px solid var(--gold-border)',
      borderRadius: 5,
      padding: '2px 6px',
      fontSize: 10,
      color: C2.textMuted,
      cursor: 'pointer',
      fontFamily: 'DM Sans,sans-serif'
    }
  }, "ESC")), /*#__PURE__*/React.createElement("div", {
    style: {
      maxHeight: 360,
      overflowY: 'auto'
    }
  }, filtered.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '24px 16px',
      textAlign: 'center',
      fontSize: 13,
      color: C2.textMuted
    }
  }, "Sin resultados"), (() => {
    globalIdx = 0;
    return null;
  })(), navItems.length > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SectionHeader, {
    title: "Ir a..."
  }), navItems.map(renderItem)), sysItems.length > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SectionHeader, {
    title: "Sistema"
  }), sysItems.map(renderItem)), actItems.length > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SectionHeader, {
    title: "Actividades pendientes"
  }), actItems.map(renderItem))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      padding: '8px 16px',
      borderTop: '1px solid color-mix(in srgb, var(--gold) 7%, transparent)',
      fontSize: 10,
      color: C2.textMuted,
      opacity: 0.6
    }
  }, /*#__PURE__*/React.createElement("span", null, "↑↓ navegar"), /*#__PURE__*/React.createElement("span", null, "⏎ seleccionar"), /*#__PURE__*/React.createElement("span", null, "ESC cerrar"))));
}
window.CommandPalette = CommandPalette;
