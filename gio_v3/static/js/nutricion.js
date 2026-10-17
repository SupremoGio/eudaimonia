/* Nutrición (Díaita) — Design System V2.
   Plan del día (vista Ritmo o Protocolo), banco de recetas, diario de
   síntomas + Bristol, planificador semanal y deslices. Toda la lógica venía
   inline en el template con estilos en línea; ahora usa clases y tokens. */
(function () {
  'use strict';
  var root = document.getElementById('dt');
  if (!root) return;
  var S = JSON.parse(document.getElementById('dt-data').textContent || '{}');
  S.variant = 'ritmo'; S.semDay = S.today; S.tab = 'hoy';

  /* ── Datos estáticos ── */
  var TAGS = { safe: ['Seguro', 'success'], caution: ['Porción', 'warning'], trigger: ['Disparador', 'danger'] };
  var FEELINGS = [{ id: 'bien', label: 'Bien', icon: 'smile', tone: 'success' }, { id: 'regular', label: 'Regular', icon: 'meh', tone: 'warning' }, { id: 'mal', label: 'Mal', icon: 'frown', tone: 'danger' }];
  var SYMPTOM_TAGS = ['Hinchazón', 'Dolor', 'Gases', 'Urgencia', 'Reflujo', 'Náusea'];
  var BRISTOL = [{ n: 1, d: 'Bolitas duras' }, { n: 2, d: 'Grumosa' }, { n: 3, d: 'Con grietas' }, { n: 4, d: 'Lisa y blanda' }, { n: 5, d: 'Blanda, bordes' }, { n: 6, d: 'Pastosa' }, { n: 7, d: 'Líquida' }];
  var TEMPTATIONS = [
    { id: 'cafe', label: 'Café de más', glyph: 'coffee', pen: 5 }, { id: 'pan', label: 'Pan / harina', glyph: 'wheat', pen: 12 },
    { id: 'galleta', label: 'Galleta / dulce', glyph: 'cookie', pen: 12 }, { id: 'lacteo', label: 'Lácteo', glyph: 'milk', pen: 10 },
    { id: 'frijol', label: 'Frijol / legumbre', glyph: 'bean', pen: 8 }, { id: 'alcohol', label: 'Alcohol', glyph: 'wine', pen: 12 },
    { id: 'otro', label: 'Otro disparador', glyph: 'flag', pen: 8 }];
  var TRIGGERS_LIST = ['Café en exceso', 'Lácteos', 'Frijol', 'Harinas refinadas', 'Galletas'];
  var RECIPES = [
    { id: 'r1', slot: 'Desayuno', name: 'Omelette de espinaca y papa', kcal: 390, protein: 26, tag: 'safe', time: '12 min' },
    { id: 'r2', slot: 'Desayuno', name: 'Avena sin gluten con fresas', kcal: 340, protein: 12, tag: 'caution', time: '8 min', note: 'Avena en porción ≤ ½ taza' },
    { id: 'r3', slot: 'Comida', name: 'Res magra con arroz y zanahoria', kcal: 600, protein: 45, tag: 'safe', time: '25 min' },
    { id: 'r4', slot: 'Comida', name: 'Pescado blanco + quinoa + calabaza', kcal: 520, protein: 38, tag: 'safe', time: '20 min' },
    { id: 'r5', slot: 'Cena', name: 'Pavo molido con calabacita', kcal: 440, protein: 40, tag: 'safe', time: '18 min' },
    { id: 'r6', slot: 'Cena', name: 'Tortilla de maíz con pollo y limón', kcal: 410, protein: 34, tag: 'safe', time: '15 min' },
    { id: 'r7', slot: 'Colación', name: 'Kiwi + puñado de almendras', kcal: 200, protein: 7, tag: 'safe', time: '2 min' },
    { id: 'r8', slot: 'Colación', name: 'Arroz inflado + mantequilla de maní', kcal: 240, protein: 9, tag: 'safe', time: '3 min' },
    { id: 'r9', slot: 'Colación', name: 'Yogur SIN lactosa + semillas chía', kcal: 210, protein: 14, tag: 'caution', time: '2 min', note: 'Solo versión sin lactosa' }];
  var RULES = [
    ['check', 'Comida/colación cumplida a tiempo', '+8–14 XP', false], ['notebook-pen', 'Registrar cómo cayó (síntoma)', '+5 XP', false],
    ['sun', 'Día 100% adherido (protocolo limpio)', '+30 XP bonus', false], ['gem', 'Cerrar el día completo', '+8 EC', false],
    ['flame', 'Racha de días limpios sin disparador', 'multiplica XP', false], ['x-circle', 'Caer en tentación (registrado)', '−5 a −12 XP · rompe racha', true]];
  var DAYS = [{ k: 'L', l: 'Lun', full: 'Lunes' }, { k: 'M', l: 'Mar', full: 'Martes' }, { k: 'X', l: 'Mié', full: 'Miércoles' }, { k: 'J', l: 'Jue', full: 'Jueves' },
    { k: 'V', l: 'Vie', full: 'Viernes' }, { k: 'S', l: 'Sáb', full: 'Sábado' }, { k: 'D', l: 'Dom', full: 'Domingo' }];
  var SLOT_TIME = { 'Desayuno': '07:00', 'Colación AM': '10:30', 'Comida': '14:00', 'Colación PM': '17:30', 'Cena': '20:30' };
  var SLOTS = Object.keys(SLOT_TIME);

  /* ── Helpers ── */
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function toMin(t) { var p = (t || '00:00').split(':').map(Number); return p[0] * 60 + p[1]; }
  function nowMin() { var n = new Date(); return n.getHours() * 60 + n.getMinutes(); }
  function dayOf(k) { return DAYS.find(function (d) { return d.k === k; }) || {}; }
  function plan(k) { return S.week[k || S.today] || []; }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function api(url, data) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {}) }).then(function (r) { return r.json(); }).catch(function () { return {}; }); }
  function tagDot(tag) { return '<span class="dt-dot dt-t--' + (TAGS[tag] || TAGS.safe)[1] + '" aria-hidden="true"></span>'; }
  function tagChip(tag) { var t = TAGS[tag] || TAGS.safe; return '<span class="eu-badge eu-badge--' + t[1] + '">' + t[0] + '</span>'; }
  function feel(id) { return FEELINGS.find(function (f) { return f.id === id; }); }
  function feelBadge(id) { var f = feel(id); return f ? '<span class="dt-feel dt-t--' + f.tone + '"><i data-lucide="' + f.icon + '"></i>' + f.label + '</span>' : ''; }
  function macros(m) { return '<span class="dt-macros t-meta"><b>' + esc(m.kcal) + '</b> kcal · <b>' + esc(m.protein) + 'g</b> prot</span>'; }
  function ring(pct, size, inner) {
    var st = size > 100 ? 8 : 6, r = (size - st) / 2, c = 2 * Math.PI * r;
    return '<div class="dt-ring" style="--sz:' + size + 'px"><svg viewBox="0 0 ' + size + ' ' + size + '" aria-hidden="true"><circle class="dt-ring-bg" cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" stroke-width="' + st + '"/>' +
      '<circle class="dt-ring-fg" cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" stroke-width="' + st + '" stroke-dasharray="' + c.toFixed(1) + '" stroke-dashoffset="' + (c * (1 - pct)).toFixed(1) + '"/></svg><div class="dt-ring-c">' + inner + '</div></div>';
  }

  /* ── KPIs ── */
  function kpis() {
    var xp = S.xp_today;
    $('k-xp').textContent = (xp < 0 ? '' : '+') + xp + ' XP';
    $('k-xp').classList.toggle('eu-badge--danger', xp < 0);
    $('k-ec').textContent = '+' + S.ec_today + ' EC';
    $('k-streak').lastChild.textContent = S.streak + ' d limpios';
    if (S.tab === 'hoy') renderRail();
  }

  /* ── Pestañas ── */
  function setTab(t) {
    S.tab = t; root.dataset.tab = t;
    document.querySelectorAll('[data-tab-set]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tabSet === t)); });
    document.querySelectorAll('[data-panel]').forEach(function (p) { p.hidden = p.dataset.panel !== t; });
    ({ hoy: renderHoy, recetas: renderRecetas, sintomas: renderSintomas, semana: renderSemana })[t]();
  }
  document.querySelectorAll('[data-tab-set]').forEach(function (b) { b.addEventListener('click', function () { setTab(b.dataset.tabSet); }); });

  /* ── HOY ── */
  document.querySelectorAll('[data-variant]').forEach(function (b) {
    b.addEventListener('click', function () {
      S.variant = b.dataset.variant;
      document.querySelectorAll('[data-variant]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      renderView();
    });
  });
  function renderHoy() {
    var p = plan(), done = p.filter(function (m) { return m.done; }).length;
    $('hoy-day').innerHTML = esc(dayOf(S.today).full || '') + ' <span class="eu-badge eu-badge--brand">hoy</span>';
    $('hoy-progress').textContent = done + '/' + p.length + ' cumplidas';
    renderView(); renderRail();
  }
  function emptyPlan() {
    return '<div class="eu-card"><div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="utensils"></i></div><div class="t-card">Día sin plan</div>' +
      '<p>Aún no agregaste comidas para hoy. Elige una del banco de recetas o crea una personalizada.</p>' +
      '<button type="button" class="eu-btn eu-btn--primary js-add"><i data-lucide="plus"></i>Añadir comida</button></div></div>';
  }
  function renderView() {
    var p = plan(), nm = nowMin(), el = $('hoy-view');
    if (!p.length) { el.innerHTML = emptyPlan(); icons(); return; }
    if (S.variant === 'ritmo') {
      el.innerHTML = '<ol class="dt-timeline">' + p.map(function (m) {
        var past = toMin(m.time) <= nm;
        return '<li class="dt-tl' + (m.done ? ' is-done' : past ? ' is-past' : '') + '"><span class="dt-tl-time num">' + esc(m.time) + '</span>' +
          '<span class="dt-tl-node">' + (m.done ? '<i data-lucide="check"></i>' : '') + '</span>' +
          '<button type="button" class="eu-card dt-meal js-meal" data-id="' + m.id + '">' +
            '<span class="eu-between"><span class="eu-hstack dt-slot">' + tagDot(m.tag) + '<span class="t-eyebrow">' + esc(m.slot) + '</span></span>' +
            '<span class="dt-xp">' + (m.done ? '<i data-lucide="check"></i>' : '+' + m.xp + ' XP') + '</span></span>' +
            '<span class="t-ui dt-meal-t">' + esc(m.name) + '</span>' +
            '<span class="eu-hstack dt-meal-m">' + macros(m) + (m.symptom ? feelBadge(m.symptom) : '') + '</span></button></li>';
      }).join('') + '</ol>';
    } else {
      el.innerHTML = '<div class="eu-vstack dt-proto">' + p.map(function (m) {
        return '<button type="button" class="eu-card dt-meal dt-meal--proto js-meal' + (m.done ? ' is-done' : '') + '" data-id="' + m.id + '" data-tag="' + esc(m.tag) + '">' +
          '<span class="dt-proto-main"><span class="eu-between"><span class="t-eyebrow">' + esc(m.slot) + ' · ' + esc(m.time) + '</span>' + (m.symptom ? feelBadge(m.symptom) : '') + '</span>' +
          '<span class="t-ui dt-meal-t">' + esc(m.name) + '</span>' + macros(m) + '</span>' +
          '<span class="dt-proto-chk">' + (m.done ? '<i data-lucide="check"></i>' : '<span class="num">+' + m.xp + '</span>') + '</span></button>';
      }).join('') + '</div>';
    }
    icons();
  }
  function renderRail() {
    var p = plan(), done = p.filter(function (m) { return m.done; }).length, pct = p.length ? done / p.length : 0;
    var clean = p.filter(function (m) { return m.done && m.symptom !== 'mal'; }).length, xp = S.xp_today;
    $('hoy-ring').innerHTML = ring(pct, 116, '<span class="t-data num">' + done + '<span class="fg-3">/' + p.length + '</span></span><span class="t-eyebrow">cumplidas</span>') +
      '<div class="dt-ring-stats"><div><div class="t-data num' + (xp < 0 ? ' fg-danger' : ' fg-brand') + '">' + (xp < 0 ? '' : '+') + xp + '</div><div class="t-meta">XP</div></div>' +
      '<div><div class="t-data num dt-ec">+' + S.ec_today + '</div><div class="t-meta">EC</div></div>' +
      '<div><div class="t-data num fg-success">' + clean + '</div><div class="t-meta">sin síntoma</div></div></div>';
    var st = $('hoy-status');
    if (S.slips.length) st.innerHTML = '<div class="eu-card dt-status is-danger"><i data-lucide="x-circle"></i><div><div class="t-ui">Racha reiniciada</div><div class="t-meta">' + S.slips.length + ' desliz' + (S.slips.length > 1 ? 'es' : '') + ' hoy · sin bonus de día limpio. Recomienza.</div></div></div>';
    else if (p.length && done === p.length) st.innerHTML = '<div class="eu-card dt-status is-success"><i data-lucide="sparkles"></i><div><div class="t-ui">Día cerrado · limpio</div><div class="t-meta">Protocolo íntegro: +30 XP bonus · +8 EC · racha +1</div></div></div>';
    else st.innerHTML = p.length ? '<p class="t-meta dt-foot">' + (p.length - done) + ' por cumplir para cerrar el día limpio.</p>' : '';
    icons();
  }

  /* ── RECETAS ── */
  var recFilter = 'Todas';
  function renderRecetas() {
    $('rec-filter').innerHTML = ['Todas', 'Desayuno', 'Comida', 'Cena', 'Colación'].map(function (c) {
      return '<button type="button" class="eu-chip" data-rf="' + c + '" aria-pressed="' + (recFilter === c) + '">' + c + '</button>';
    }).join('');
    $('rec-list').innerHTML = RECIPES.filter(function (r) { return recFilter === 'Todas' || r.slot === recFilter; }).map(function (r) {
      return '<div class="eu-row dt-rec"><span class="eu-row-ic dt-rec-ic">' + tagDot(r.tag) + '</span>' +
        '<div class="eu-row-main"><div class="t-eyebrow">' + esc(r.slot) + ' · ' + esc(r.time) + '</div><div class="eu-row-t">' + esc(r.name) + '</div>' +
        '<div class="eu-row-s">' + macros(r) + (r.note ? '<span class="dt-note">' + esc(r.note) + '</span>' : '') + '</div></div>' +
        '<button type="button" class="eu-iconbtn js-add" data-recipe="' + r.id + '" aria-label="Añadir «' + esc(r.name) + '» al plan de hoy"><i data-lucide="plus"></i></button></div>';
    }).join('');
    icons();
  }
  $('rec-filter').addEventListener('click', function (e) { var b = e.target.closest('[data-rf]'); if (b) { recFilter = b.dataset.rf; renderRecetas(); } });

  /* ── SÍNTOMAS ── */
  function renderSintomas() {
    $('sint-triggers').innerHTML = TRIGGERS_LIST.map(function (t) { return '<span class="eu-badge eu-badge--danger"><i data-lucide="flag"></i>' + esc(t) + '</span>'; }).join('');
    if (S.slips.length) {
      var tot = S.slips.reduce(function (a, b) { return a + (b.pen || 0); }, 0);
      $('sint-slips').innerHTML = '<div class="eu-card eu-card--flush"><div class="eu-between dt-card-hd"><span class="t-card">Deslices de hoy</span><span class="t-data num fg-danger">−' + tot + ' XP</span></div><div class="eu-list">' +
        S.slips.map(function (s) {
          return '<div class="eu-row"><span class="eu-row-ic dt-slip-ic"><i data-lucide="' + esc(s.glyph || 'flag') + '"></i></span><div class="eu-row-main"><div class="eu-row-t">' + esc(s.label) +
            (s.over ? ' <span class="fg-danger">· me pasé</span>' : '') + '</div>' + (s.note ? '<div class="eu-row-s">' + esc(s.note) + '</div>' : '') + '</div><span class="t-data num fg-danger">−' + s.pen + '</span></div>';
        }).join('') + '</div></div>';
    } else $('sint-slips').innerHTML = '';
    var logged = plan().filter(function (m) { return m.symptom; });
    $('sint-meals').innerHTML = logged.length ? logged.map(function (m) {
      var f = feel(m.symptom) || FEELINGS[0];
      return '<div class="eu-row"><span class="eu-row-ic dt-t--' + f.tone + ' dt-feel-ic"><i data-lucide="' + f.icon + '"></i></span><div class="eu-row-main"><div class="eu-row-t">' + esc(m.slot) + ' · ' + esc(m.time) + '</div>' +
        (m.sym_tags && m.sym_tags.length ? '<div class="eu-row-s">' + m.sym_tags.map(esc).join(' · ') + '</div>' : '') + '</div><span class="dt-feel dt-t--' + f.tone + '">' + f.label + '</span></div>';
    }).join('') : '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="notebook-pen"></i></div><div class="t-card">Aún sin registros</div><p>Marca cómo te cayó cada comida desde el plan del día para llevar tu diario.</p></div>';
    renderBristol(); icons();
  }
  function renderBristol() {
    var cur = S.bristol;
    $('bristol-btns').innerHTML = BRISTOL.map(function (b) {
      return '<button type="button" role="radio" class="dt-bristol-b' + (b.n === 4 ? ' is-ideal' : '') + '" data-bristol="' + b.n + '" aria-checked="' + (cur === b.n) + '" aria-label="Tipo ' + b.n + ': ' + b.d + '" title="' + b.d + '">' + b.n + '</button>';
    }).join('');
    var b = BRISTOL.find(function (x) { return x.n === cur; });
    $('bristol-desc').innerHTML = b ? '<span class="' + (cur === 4 ? 'fg-success' : '') + '">Tipo ' + cur + ': ' + esc(b.d) + (cur === 4 ? ' · ideal' : '') + '</span>' : 'Sin registro hoy.';
  }
  $('bristol-btns').addEventListener('click', function (e) {
    var b = e.target.closest('[data-bristol]'); if (!b) return;
    S.bristol = +b.dataset.bristol; renderBristol(); api('/nutricion/api/bristol', { valor: S.bristol });
  });

  /* ── SEMANA ── */
  function renderSemana() {
    $('sem-planned').textContent = DAYS.filter(function (d) { return (S.week[d.k] || []).length; }).length + '/7';
    $('sem-total').textContent = DAYS.reduce(function (a, d) { return a + (S.week[d.k] || []).length; }, 0);
    $('sem-days').innerHTML = DAYS.map(function (d) {
      var n = (S.week[d.k] || []).length;
      return '<button type="button" role="tab" class="dt-day' + (d.k === S.today ? ' is-today' : '') + '" data-sd="' + d.k + '" aria-selected="' + (S.semDay === d.k) + '">' +
        '<span class="t-meta">' + d.l + '</span><span class="dt-bars" aria-hidden="true">' + [0, 1, 2, 3, 4].map(function (i) { return '<i class="' + (i < n ? 'on' : '') + '"></i>'; }).join('') + '</span></button>';
    }).join('');
    var k = S.semDay, di = dayOf(k), meals = sorted(k);
    $('sem-day').innerHTML = '<div class="eu-card eu-vstack dt-semday"><div class="eu-between"><span class="t-section">' + esc(di.full || '') + (k === S.today ? ' <span class="eu-badge eu-badge--brand">hoy</span>' : '') + '</span><span class="t-meta num">' + meals.length + '/5</span></div>' +
      (meals.length ? '<div class="eu-list">' + meals.map(function (m) { return mealRow(m, k); }).join('') + '</div>' : '<p class="t-meta dt-free">Día libre. Añade tus comidas.</p>') +
      '<button type="button" class="eu-btn eu-btn--secondary eu-btn--block js-add" data-day="' + k + '"><i data-lucide="plus"></i>Agregar a ' + esc(di.full || '') + '</button>' +
      (meals.length ? '<button type="button" class="eu-btn eu-btn--ghost eu-btn--block js-repeat" data-day="' + k + '"><i data-lucide="repeat"></i>Repetir este plan de lunes a viernes</button>' : '') + '</div>';
    $('sem-grid').innerHTML = DAYS.map(function (d) {
      var ms = sorted(d.k);
      return '<div class="eu-card dt-col' + (d.k === S.today ? ' is-today' : '') + '"><div class="eu-between"><span class="t-eyebrow">' + d.l + '</span><span class="t-meta num">' + ms.length + '/5</span></div>' +
        (ms.length ? ms.map(function (m) {
          return '<div class="dt-mini" data-tag="' + esc(m.tag) + '"><div class="eu-between"><span class="eu-hstack dt-slot">' + tagDot(m.tag) + '<span class="t-meta num">' + esc(m.time) + '</span></span>' +
            '<button type="button" class="dt-x js-rm" data-id="' + m.id + '" data-day="' + d.k + '" aria-label="Quitar ' + esc(m.name) + '"><i data-lucide="x"></i></button></div>' +
            '<button type="button" class="dt-mini-t js-meal" data-id="' + m.id + '">' + esc(m.name) + '</button></div>';
        }).join('') : '<p class="t-meta dt-free">Libre</p>') +
        '<button type="button" class="dt-col-add js-add" data-day="' + d.k + '"><i data-lucide="plus"></i>Añadir</button>' +
        (ms.length ? '<button type="button" class="dt-col-rep js-repeat" data-day="' + d.k + '"><i data-lucide="repeat"></i>Repetir L–V</button>' : '') + '</div>';
    }).join('');
    $('sem-rules').innerHTML = RULES.map(function (r) {
      return '<div class="eu-row"><span class="eu-row-ic' + (r[3] ? ' dt-slip-ic' : ' dt-rule-ic') + '"><i data-lucide="' + r[0] + '"></i></span><div class="eu-row-main"><div class="eu-row-t dt-wrap-t">' + r[1] + '</div></div><span class="t-meta num ' + (r[3] ? 'fg-danger' : 'fg-brand') + '">' + r[2] + '</span></div>';
    }).join('');
    icons();
  }
  function sorted(k) { return (S.week[k] || []).slice().sort(function (a, b) { return toMin(a.time) - toMin(b.time); }); }
  function mealRow(m, k) {
    return '<div class="eu-row dt-mrow">' + tagDot(m.tag) + '<button type="button" class="eu-row-main dt-mrow-b js-meal" data-id="' + m.id + '"><span class="t-eyebrow">' + esc(m.slot) + ' · ' + esc(m.time) + '</span><span class="eu-row-t">' + esc(m.name) + '</span></button>' +
      '<button type="button" class="eu-iconbtn js-rm" data-id="' + m.id + '" data-day="' + k + '" aria-label="Quitar ' + esc(m.name) + '"><i data-lucide="x"></i></button></div>';
  }
  $('sem-days').addEventListener('click', function (e) { var b = e.target.closest('[data-sd]'); if (b) { S.semDay = b.dataset.sd; renderSemana(); } });

  /* ── Detalle de comida ── */
  var cur = null, mFeel = null, mTags = [];
  function findMeal(id) { for (var k in S.week) { var m = S.week[k].find(function (x) { return x.id === id; }); if (m) return m; } return null; }
  function openMeal(id) { cur = findMeal(id); if (!cur) return; mFeel = cur.symptom || null; mTags = (cur.sym_tags || []).slice(); renderMeal(); euModal.open('m-meal'); }
  function renderMeal() {
    var m = cur;
    $('m-meal-t').textContent = m.name;
    var h = '<div class="eu-between"><span class="t-eyebrow">' + esc(m.slot) + ' · ' + esc(m.time) + '</span>' + tagChip(m.tag) + '</div>' +
      (m.note ? '<p class="t-meta fg-2">' + esc(m.note) + '</p>' : '') +
      '<div class="eu-grid-2 dt-meal-stats"><div class="eu-stat"><div class="eu-stat-lbl">kcal</div><div class="eu-stat-val">' + esc(m.kcal) + '</div></div>' +
      '<div class="eu-stat"><div class="eu-stat-lbl">proteína</div><div class="eu-stat-val">' + esc(m.protein) + 'g</div></div></div>';
    if ((m.items || []).length) h += '<div class="eu-vstack dt-comp"><div class="t-eyebrow">Composición</div>' + m.items.map(function (it) {
      return '<div class="dt-comp-it">' + tagDot(it.tag || 'safe') + '<div><div>' + esc(it.t) + '</div>' + (it.why ? '<div class="t-meta fg-danger">' + esc(it.why) + '</div>' : '') + '</div></div>';
    }).join('') + '</div>';
    if (m.swap) h += '<div class="eu-card eu-card--inset dt-swap"><i data-lucide="repeat"></i><p class="t-meta">' + esc(m.swap) + '</p></div>';
    if (m.done) {
      h += '<div class="eu-vstack dt-feel-box"><div class="t-eyebrow">¿Cómo te cayó? <span class="fg-brand">+5 XP</span></div><div class="dt-feels" role="radiogroup" aria-label="Cómo te cayó">' +
        FEELINGS.map(function (f) { return '<button type="button" role="radio" class="dt-feel-b dt-t--' + f.tone + '" data-feel="' + f.id + '" aria-checked="' + (mFeel === f.id) + '"><i data-lucide="' + f.icon + '"></i>' + f.label + '</button>'; }).join('') +
        '</div><div class="eu-chips dt-wrap">' + SYMPTOM_TAGS.map(function (t) { return '<button type="button" class="eu-chip" data-sym="' + esc(t) + '" aria-pressed="' + (mTags.indexOf(t) >= 0) + '">' + esc(t) + '</button>'; }).join('') +
        '</div><button type="button" class="eu-btn eu-btn--secondary eu-btn--block js-save-sym"' + (mFeel ? '' : ' disabled') + '>Guardar registro</button></div>';
    } else h += '<button type="button" class="eu-btn eu-btn--primary eu-btn--lg eu-btn--block js-cumplir" data-id="' + m.id + '"><i data-lucide="check"></i>Cumplir al pie de la letra · +' + m.xp + ' XP</button>';
    if (m.custom) h += '<button type="button" class="eu-btn eu-btn--ghost eu-btn--block dt-danger js-rm" data-id="' + m.id + '">Quitar del plan</button>';
    $('meal-content').innerHTML = h; icons();
  }
  $('meal-content').addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.feel) { mFeel = b.dataset.feel; renderMeal(); }
    else if (b.dataset.sym) { var t = b.dataset.sym; mTags = mTags.indexOf(t) >= 0 ? mTags.filter(function (x) { return x !== t; }) : mTags.concat(t); renderMeal(); }
    else if (b.classList.contains('js-cumplir')) {
      b.setAttribute('aria-busy', 'true');
      var res = await api('/nutricion/api/cumplir', { meal_id: cur.id });
      if (res.error) { b.removeAttribute('aria-busy'); toast('No se pudo registrar', 'err'); return; }
      if (window.euGam) euGam({ xp: (res.xp_earned || 0) + (res.bonus_xp || 0) }, { el: b });
      cur.done = true; S.xp_today = res.total_xp; S.ec_today = res.total_ec; S.streak = res.streak; kpis();
      toast(res.bonus_xp > 0 ? 'Día cerrado · +' + res.bonus_xp + ' XP bonus · +' + res.bonus_ec + ' EC' : '+' + res.xp_earned + ' XP · cumplida', 'win');
      mFeel = null; mTags = []; renderMeal(); if (S.tab === 'hoy') renderHoy();
    } else if (b.classList.contains('js-save-sym')) {
      var r = await api('/nutricion/api/sintoma', { meal_id: cur.id, feeling: mFeel, tags: mTags });
      cur.symptom = mFeel; cur.sym_tags = mTags; if (r.total_xp != null) S.xp_today = r.total_xp; kpis();
      toast('+5 XP · registro guardado', 'win'); euModal.close('m-meal');
      if (window.euRefreshXp) euRefreshXp();
      if (S.tab === 'hoy') renderView(); if (S.tab === 'sintomas') renderSintomas();
    }
  });

  async function removeMeal(id, day) {
    var m = findMeal(id); if (!m) return;
    var dk = day || Object.keys(S.week).find(function (k) { return S.week[k].some(function (x) { return x.id === id; }); });
    await fetch('/nutricion/api/comida/' + id, { method: 'DELETE' });
    if (dk) S.week[dk] = S.week[dk].filter(function (x) { return x.id !== id; });
    toast(m.slot + ' eliminada');
    if (!$('m-meal').hidden) euModal.close('m-meal');
    if (S.tab === 'hoy') renderHoy(); if (S.tab === 'semana') renderSemana();
  }

  /* ── Deslices ── */
  var slip = { t: null, over: false };
  function openSlip() {
    slip = { t: null, over: false }; $('slip-note').value = '';
    document.querySelectorAll('[data-over]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.over === '0')); });
    renderSlip(); euModal.open('m-slip');
  }
  function renderSlip() {
    $('slip-trigs').innerHTML = TEMPTATIONS.map(function (t) {
      return '<button type="button" role="radio" class="dt-slip-b" data-trig="' + t.id + '" aria-checked="' + (slip.t && slip.t.id === t.id) + '"><i data-lucide="' + t.glyph + '"></i><span><span class="t-ui">' + t.label + '</span><span class="t-meta">−' + t.pen + ' XP</span></span></button>';
    }).join('');
    var pen = slip.t ? Math.round(slip.t.pen * (slip.over ? 1.5 : 1)) : 0;
    $('slip-pen').textContent = slip.t ? '−' + pen + ' XP' : '—';
    $('slip-pen').classList.toggle('fg-danger', !!slip.t);
    $('slip-submit').disabled = !slip.t; icons();
  }
  $('slip-trigs').addEventListener('click', function (e) { var b = e.target.closest('[data-trig]'); if (b) { slip.t = TEMPTATIONS.find(function (t) { return t.id === b.dataset.trig; }); renderSlip(); } });
  document.querySelectorAll('[data-over]').forEach(function (b) {
    b.addEventListener('click', function () { slip.over = b.dataset.over === '1'; document.querySelectorAll('[data-over]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); renderSlip(); });
  });
  $('slip-submit').addEventListener('click', async function () {
    if (!slip.t) return;
    var pen = Math.round(slip.t.pen * (slip.over ? 1.5 : 1)), note = $('slip-note').value;
    var res = await api('/nutricion/api/desliz', { trig_id: slip.t.id, over: slip.over, note: note });
    S.slips.push(res.slip || { id: Date.now(), label: slip.t.label, glyph: slip.t.glyph, pen: pen, over: slip.over, note: note });
    if (res.total_xp != null) S.xp_today = res.total_xp; S.streak = 0; kpis();
    toast('−' + pen + ' XP' + (res.msg ? ' · ' + res.msg : ''), 'err'); euModal.close('m-slip');
    if (S.tab === 'hoy') renderHoy(); if (S.tab === 'sintomas') renderSintomas();
  });

  /* ── Añadir comida ── */
  var add = { day: null, mode: 'banco', slot: 'Comida', picked: null, ctag: 'safe' };
  function openAdd(day, preset) {
    add = { day: day || S.today, mode: 'banco', slot: preset ? (preset.slot === 'Colación' ? 'Colación AM' : preset.slot) : 'Comida', picked: preset || null, ctag: 'safe' };
    $('m-add-t').textContent = 'Añadir a ' + (dayOf(add.day).full || 'tu plan');
    $('add-time').value = SLOT_TIME[add.slot] || '12:00';
    ['add-name', 'add-kcal', 'add-prot', 'add-ing'].forEach(function (k) { $(k).value = ''; });
    setMode('banco'); setCtag('safe'); renderAdd(); euModal.open('m-add');
  }
  function setMode(m) {
    add.mode = m;
    document.querySelectorAll('[data-mode]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.mode === m)); });
    $('add-banco').hidden = m !== 'banco'; $('add-custom').hidden = m !== 'custom'; canAdd();
  }
  function setCtag(t) { add.ctag = t; document.querySelectorAll('[data-ctag]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.ctag === t)); }); }
  function renderAdd() {
    $('add-xp').textContent = '+' + (add.slot.indexOf('Colación') >= 0 ? 8 : 12) + ' XP';
    $('add-slots').innerHTML = SLOTS.map(function (s) { return '<button type="button" class="eu-chip" data-slot="' + s + '" aria-pressed="' + (add.slot === s) + '">' + s + '</button>'; }).join('');
    $('add-list').innerHTML = RECIPES.map(function (r) {
      return '<button type="button" role="radio" class="dt-pick-b" data-pick="' + r.id + '" aria-checked="' + (!!add.picked && add.picked.id === r.id) + '">' + tagDot(r.tag) +
        '<span class="dt-pick-t"><span class="t-ui">' + esc(r.name) + '</span><span class="t-meta">' + esc(r.slot) + ' · ' + r.kcal + ' kcal · ' + r.protein + 'g prot</span></span><i data-lucide="check" class="dt-pick-ok"></i></button>';
    }).join('');
    canAdd(); icons();
  }
  function canAdd() { $('add-submit').disabled = add.mode === 'banco' ? !add.picked : !$('add-name').value.trim(); }
  document.querySelectorAll('[data-mode]').forEach(function (b) { b.addEventListener('click', function () { setMode(b.dataset.mode); }); });
  document.querySelectorAll('[data-ctag]').forEach(function (b) { b.addEventListener('click', function () { setCtag(b.dataset.ctag); }); });
  $('add-name').addEventListener('input', canAdd);
  $('add-slots').addEventListener('click', function (e) { var b = e.target.closest('[data-slot]'); if (b) { add.slot = b.dataset.slot; $('add-time').value = SLOT_TIME[add.slot]; renderAdd(); } });
  $('add-list').addEventListener('click', function (e) { var b = e.target.closest('[data-pick]'); if (b) { add.picked = RECIPES.find(function (r) { return r.id === b.dataset.pick; }); renderAdd(); } });
  $('add-submit').addEventListener('click', async function () {
    var payload = { day: add.day, slot: add.slot, time: $('add-time').value || SLOT_TIME[add.slot] || '12:00' }, p = add.picked;
    if (add.mode === 'banco' && p) Object.assign(payload, { name: p.name, kcal: p.kcal, protein: p.protein, tag: p.tag, note: p.note || 'Del banco de recetas seguras.', items: [{ t: p.name, tag: p.tag }], swap: null });
    else {
      var name = $('add-name').value.trim(); if (!name) return;
      var ing = $('add-ing').value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      Object.assign(payload, { name: name, kcal: +$('add-kcal').value || 0, protein: +$('add-prot').value || 0, tag: add.ctag, note: 'Comida personalizada.',
        items: ing.length ? ing.map(function (t) { return { t: t, tag: add.ctag }; }) : [{ t: name, tag: add.ctag }] });
    }
    var res = await api('/nutricion/api/comida', payload);
    if (!res.meal) { toast('No se pudo añadir', 'err'); return; }
    (S.week[add.day] = S.week[add.day] || []).push(res.meal);
    S.week[add.day].sort(function (a, b) { return toMin(a.time) - toMin(b.time); });
    toast('Añadida: ' + (dayOf(add.day).full || '') + ' · ' + add.slot); euModal.close('m-add');
    if (S.tab === 'hoy') renderHoy(); if (S.tab === 'semana') renderSemana();
  });

  /* ── Delegación general ── */
  root.addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.classList.contains('js-meal')) openMeal(+b.dataset.id);
    else if (b.classList.contains('js-add')) openAdd(b.dataset.day || S.today, b.dataset.recipe ? RECIPES.find(function (r) { return r.id === b.dataset.recipe; }) : null);
    else if (b.classList.contains('js-slip')) openSlip();
    else if (b.classList.contains('js-rm')) removeMeal(+b.dataset.id, b.dataset.day);
    else if (b.classList.contains('js-repeat')) {
      var res = await api('/nutricion/api/repetir', { src_day: b.dataset.day });
      if (res.week) S.week = res.week;
      toast('Plantilla aplicada de lunes a viernes', 'win'); renderSemana();
    }
  });
  $('meal-content').addEventListener('click', function (e) { var b = e.target.closest('.js-rm'); if (b) removeMeal(+b.dataset.id); });

  kpis();
  setTab('hoy');
})();
