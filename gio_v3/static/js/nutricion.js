/* Nutrición v2 (Díaita) — Design System V2. Hoy es la página: comidas por
   hora con «Ahora» y «Cumplí · +XP», sub-fila «¿Cómo cayó?», banda de día
   limpio y lateral (el día, Bristol, disparadores, recetario). Semana y
   Síntomas viven en ?vista=semana / ?vista=sintomas. Todo el XP lo otorga el
   backend vía el motor; cada respuesta trae el `estado` completo. */
(function () {
  'use strict';
  var root = document.getElementById('dt');
  if (!root) return;
  var S = JSON.parse(document.getElementById('dt-data').textContent || '{}');
  var VISTA = root.dataset.vista || '';
  S.semDay = S.today;

  /* ── Datos estáticos ── */
  var TAGS = { safe: ['Seguro', 'success'], caution: ['Porción', 'warning'], trigger: ['Disparador', 'danger'] };
  var FEELS = [{ id: 'bien', label: 'Bien', tone: 'success' }, { id: 'regular', label: 'Pesado', tone: 'warning' }, { id: 'mal', label: 'Molestia', tone: 'danger' }];
  var SYMPTOM_TAGS = ['Hinchazón', 'Dolor', 'Gases', 'Urgencia', 'Reflujo', 'Náusea'];
  var BRISTOL = ['Muy duro', 'Duro', 'Algo duro', 'Ideal', 'Blando', 'Pastoso', 'Líquido'];
  var TEMPTATIONS = [
    { id: 'cafe', label: 'Café de más', glyph: 'coffee', pen: 5 }, { id: 'pan', label: 'Pan / harina', glyph: 'wheat', pen: 12 },
    { id: 'galleta', label: 'Galleta / dulce', glyph: 'cookie', pen: 12 }, { id: 'lacteo', label: 'Lácteo', glyph: 'milk', pen: 10 },
    { id: 'frijol', label: 'Frijol / legumbre', glyph: 'bean', pen: 8 }, { id: 'alcohol', label: 'Alcohol', glyph: 'wine', pen: 12 },
    { id: 'otro', label: 'Otro disparador', glyph: 'flag', pen: 8 }];
  var RULES = [
    ['check', 'Comida/colación cumplida', '+8–14 XP', false], ['notebook-pen', 'Decir cómo cayó (una vez por comida)', '+5 XP', false],
    ['sun', 'Día limpio: todas cumplidas y sin desliz', '+30 XP · +8 EC', false],
    ['flame', 'Racha: días limpios seguidos', 'multiplica XP', false], ['x-circle', 'Desliz registrado', '−5 a −18 XP · rompe racha', true]];
  var DAYS = [{ k: 'L', l: 'Lun', full: 'Lunes' }, { k: 'M', l: 'Mar', full: 'Martes' }, { k: 'X', l: 'Mié', full: 'Miércoles' }, { k: 'J', l: 'Jue', full: 'Jueves' },
    { k: 'V', l: 'Vie', full: 'Viernes' }, { k: 'S', l: 'Sáb', full: 'Sábado' }, { k: 'D', l: 'Dom', full: 'Domingo' }];
  var SLOT_TIME = { 'Desayuno': '07:00', 'Colación AM': '10:30', 'Comida': '14:00', 'Colación PM': '17:30', 'Pre-gym': '18:00', 'Cena': '20:30' };
  var SLOTS = Object.keys(SLOT_TIME);

  /* ── Helpers ── */
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function toMin(t) { var p = (t || '00:00').split(':').map(Number); return p[0] * 60 + (p[1] || 0); }
  function nowMin() { var n = new Date(); return n.getHours() * 60 + n.getMinutes(); }
  function dayOf(k) { return DAYS.find(function (d) { return d.k === k; }) || {}; }
  function sorted(k) { return (S.week[k] || []).slice().sort(function (a, b) { return toMin(a.time) - toMin(b.time); }); }
  function hoy() { return sorted(S.today); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function api(url, data) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {}) }).then(function (r) { return r.json(); }); }
  function tagDot(tag) { return '<span class="dt-dot dt-t--' + (TAGS[tag] || TAGS.safe)[1] + '" aria-hidden="true"></span>'; }
  function tagChip(tag) { var t = TAGS[tag] || TAGS.safe; return '<span class="eu-badge eu-badge--' + t[1] + '">' + t[0] + '</span>'; }
  function feel(id) { return FEELS.find(function (f) { return f.id === id; }); }
  function plural(n, s, p) { return n + ' ' + (n === 1 ? s : (p || s + 's')); }
  function setEstado(e) { if (e) { var sd = S.semDay; S = e; S.semDay = sd || e.today; } }
  function gam(g, el) { if (g && g.stats && window.euGam) euGam(g, { el: el }); else if (window.euRefreshXp) euRefreshXp(); }

  /* «Ahora»: la última comida sin marcar cuya hora ≤ ahora + 60 min y que no
     quedó atrás de una ya cumplida; si no hay, la siguiente por venir. Las
     anteriores sin marcar quedan vencidas (warning). */
  function ahoraId(list) {
    var n = nowMin(), lim = n + 60, pend = list.filter(function (m) { return !m.done; });
    var lastDone = list.filter(function (m) { return m.done; }).reduce(function (a, m) { return Math.max(a, toMin(m.time)); }, -1);
    var due = pend.filter(function (m) { var t = toMin(m.time); return t <= lim && t >= lastDone; });
    if (due.length) return due[due.length - 1].id;
    var next = pend.filter(function (m) { return toMin(m.time) > n; });
    return next.length ? next[0].id : null;
  }

  /* ══ Hoy ═══════════════════════════════════════════════════════════════ */
  var askId = null;
  function renderHoy() {
    if (VISTA) return;
    var list = hoy(), now = ahoraId(list), done = list.filter(function (m) { return m.done; }).length;
    var nowT = now ? toMin((list.find(function (m) { return m.id === now; }) || {}).time) : 9999;
    $('hoy-n').textContent = done + ' de ' + list.length;
    $('hoy-list').innerHTML = list.length ? list.map(function (m) {
      var isNow = m.id === now, late = !m.done && !isNow && toMin(m.time) < Math.min(nowT, nowMin()), f = feel(m.symptom);
      var act = m.done
        ? '<button type="button" class="dt-done js-meal" data-id="' + m.id + '" aria-label="Detalle de ' + esc(m.name) + '"><i data-lucide="check"></i>' + (f ? '<span class="dt-f--' + f.id + '">' + f.label + '</span>' : 'hecho') + '</button>'
        : '<button type="button" class="eu-btn eu-btn--sm ' + (isNow ? 'eu-btn--primary' : 'eu-btn--ghost dt-btn-line') + ' js-cumplir" data-id="' + m.id + '">Cumplí · +' + m.xp + '</button>';
      return '<li class="dt-row' + (isNow ? ' is-now' : '') + (late ? ' is-late' : '') + (m.done ? ' is-done' : '') + '">' +
        '<div class="dt-row-g"><span class="dt-row-t"><span class="num">' + esc(m.time) + '</span>' + (isNow ? '<span class="dt-ahora">Ahora</span>' : '') + '</span>' +
        '<button type="button" class="dt-row-n js-meal" data-id="' + m.id + '"><span class="dt-row-s">' + esc(m.slot) + '</span><span class="dt-row-name">' + esc(m.name) + '</span></button>' +
        '<span class="dt-row-k num">' + (m.kcal || m.protein ? (m.kcal || 0) + ' kcal · ' + (m.protein || 0) + ' g' : '—') + '</span>' + act + '</div>' +
        (askId === m.id ? '<div class="dt-ask"><span class="t-meta">¿Cómo cayó? · +5 XP</span>' +
          FEELS.map(function (x) { return '<button type="button" class="dt-feel-b dt-f--' + x.id + '" data-feel="' + x.id + '" data-meal="' + m.id + '">' + x.label + '</button>'; }).join('') +
          '<button type="button" class="dt-luego js-luego">Luego</button></div>' : '') + '</li>';
    }).join('') : '<li class="dt-pad">' + euEmpty('utensils', 'Día sin plan', 'Agrega comidas del recetario para hoy.', true) + '</li>';
    var cerr = $('hoy-cerrado');
    cerr.hidden = !S.dia_cerrado;
    cerr.innerHTML = '<i data-lucide="sparkles"></i>Día limpio · +30 XP · +8 EC · racha ' + plural(S.streak, 'día') ;
    renderSide(); icons();
  }

  /* ── Lateral ── */
  function renderSide() {
    var list = hoy(), done = list.filter(function (m) { return m.done; }).length;
    $('dia-streak').innerHTML = '<i data-lucide="flame"></i>' + S.streak + ' d limpios';
    var mk = S.macros || { kcal: 0, prot: 0 }, mt = S.metas || { kcal: 1850, prot: 130 };
    $('m-kcal-v').textContent = mk.kcal.toLocaleString('es-MX') + ' / ' + mt.kcal.toLocaleString('es-MX');
    $('m-prot-v').textContent = mk.prot + ' / ' + mt.prot + ' g';
    $('m-kcal').style.setProperty('--p', Math.min(100, mk.kcal / mt.kcal * 100) + '%');
    $('m-prot').style.setProperty('--p', Math.min(100, mk.prot / mt.prot * 100) + '%');
    $('dia-xp').textContent = (S.xp_today < 0 ? '' : '+') + S.xp_today + ' XP';
    $('dia-xp').classList.toggle('is-neg', S.xp_today < 0);
    $('dia-ec').textContent = '+' + S.ec_today + ' EC';
    $('dia-acta').textContent = 'en Acta: ' + (S.dia_cerrado ? 'día cerrado' : done + '/' + list.length);
    renderBristol();
    var tr = S.disparadores || [];
    $('trig-list').innerHTML = tr.length ? tr.map(function (t) {
      return '<div class="dt-trig-r"><span class="eu-grow">' + esc(t.label) + '</span><span class="dt-trig-bars" aria-hidden="true">' +
        new Array(Math.min(t.n, 10) + 1).join('<i></i>') + '</span><span class="num">' + t.n + '</span></div>';
    }).join('') : '<p class="t-meta">Sin deslices en 30 días.</p>';
  }
  function renderBristol() {
    var cur = S.bristol;
    $('bristol-btns').innerHTML = BRISTOL.map(function (d, i) {
      var n = i + 1, on = cur === n;
      return '<button type="button" role="radio" class="dt-br' + (on ? (n === 3 || n === 4 ? ' is-ok' : ' is-warn') : '') + '" data-bristol="' + n + '" aria-checked="' + on + '" aria-label="Tipo ' + n + ': ' + d + '" title="' + d + '">' + n + '</button>';
    }).join('');
    $('bristol-desc').textContent = cur ? cur + ' · ' + BRISTOL[cur - 1] : 'Sin registro hoy · 3–4 es lo ideal';
  }

  if (!VISTA) {
    $('bristol-btns').addEventListener('click', function (e) {
      var b = e.target.closest('[data-bristol]'); if (!b) return;
      S.bristol = +b.dataset.bristol; renderBristol(); api('/nutricion/api/bristol', { valor: S.bristol });
    });
    $('hoy-list').addEventListener('click', function (e) {
      var c = e.target.closest('.js-cumplir'), f = e.target.closest('[data-feel]'), l = e.target.closest('.js-luego');
      if (c) cumplir(+c.dataset.id, c);
      else if (f) sintoma(+f.dataset.meal, f.dataset.feel, [], f);
      else if (l) { askId = null; renderHoy(); toast('Queda pendiente en Síntomas'); }
    });
  }

  function cumplir(id, btn) {
    if (btn) btn.disabled = true;
    return api('/nutricion/api/cumplir', { meal_id: id }).then(function (r) {
      if (r.error) { toast('No se pudo registrar', 'err'); if (btn) btn.disabled = false; return; }
      setEstado(r.estado); askId = id;
      gam(r.gam, btn);
      toast(r.bonus_xp > 0 ? 'Día limpio · +' + r.bonus_xp + ' XP · +' + r.bonus_ec + ' EC' : '+' + r.xp_earned + ' XP · cumplida', 'win');
      renderHoy(); if (!$('m-meal').hidden) renderMeal();
    }).catch(function () { toast('Sin conexión', 'err'); if (btn) btn.disabled = false; });
  }
  function sintoma(id, f, tags, btn) {
    return api('/nutricion/api/sintoma', { meal_id: id, feeling: f, tags: tags || [] }).then(function (r) {
      var m = findMeal(id); if (m) { m.symptom = r.feeling || f; m.sym_tags = tags || []; }
      if (r.total_xp != null) S.xp_today = r.total_xp;
      askId = null; gam(r.gam, btn);
      toast(r.xp_earned ? '+' + r.xp_earned + ' XP · registrado' : 'Registro actualizado', 'win');
      if (VISTA === 'sintomas') { var row = document.querySelector('.dt-hist-row[data-meal="' + id + '"] .dt-feels-row'); if (row) { var x = feel(r.feeling || f); row.outerHTML = '<span class="dt-feel dt-f--' + x.id + '">' + x.label + '</span>'; } }
      else renderHoy();
    }).catch(function () { toast('Sin conexión', 'err'); });
  }

  /* ══ Detalle de comida (m-meal) ═══════════════════════════════════════ */
  var cur = null, mFeel = null, mTags = [];
  function findMeal(id) { for (var k in S.week) { var m = (S.week[k] || []).find(function (x) { return x.id === id; }); if (m) return m; } return null; }
  function openMeal(id) { cur = findMeal(id); if (!cur) return; mFeel = cur.symptom || null; mTags = (cur.sym_tags || []).slice(); renderMeal(); euModal.open('m-meal'); }
  function renderMeal() {
    var m = cur = findMeal(cur.id) || cur;
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
      h += '<div class="eu-vstack dt-feel-box"><div class="t-eyebrow">¿Cómo cayó? <span class="fg-brand">+5 XP</span></div><div class="dt-feels" role="radiogroup" aria-label="Cómo cayó">' +
        FEELS.map(function (f) { return '<button type="button" role="radio" class="dt-feel-b dt-f--' + f.id + '" data-mfeel="' + f.id + '" aria-checked="' + (mFeel === f.id) + '">' + f.label + '</button>'; }).join('') +
        '</div><div class="eu-chips dt-wrap">' + SYMPTOM_TAGS.map(function (t) { return '<button type="button" class="eu-chip" data-sym="' + esc(t) + '" aria-pressed="' + (mTags.indexOf(t) >= 0) + '">' + esc(t) + '</button>'; }).join('') +
        '</div><button type="button" class="eu-btn eu-btn--secondary eu-btn--block js-save-sym"' + (mFeel ? '' : ' disabled') + '>Guardar registro</button></div>' +
        '<button type="button" class="eu-btn eu-btn--ghost eu-btn--block js-undo" data-id="' + m.id + '"><i data-lucide="undo-2"></i>Deshacer «Cumplí»</button>';
    } else h += '<button type="button" class="eu-btn eu-btn--primary eu-btn--lg eu-btn--block js-cumplir-m" data-id="' + m.id + '"><i data-lucide="check"></i>Cumplí · +' + m.xp + ' XP</button>';
    if (m.custom) h += '<button type="button" class="eu-btn eu-btn--ghost eu-btn--block dt-danger js-rm" data-id="' + m.id + '">Quitar del plan</button>';
    $('meal-content').innerHTML = h; icons();
  }
  $('meal-content').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.mfeel) { mFeel = b.dataset.mfeel; renderMeal(); }
    else if (b.dataset.sym) { var t = b.dataset.sym; mTags = mTags.indexOf(t) >= 0 ? mTags.filter(function (x) { return x !== t; }) : mTags.concat(t); renderMeal(); }
    else if (b.classList.contains('js-cumplir-m')) cumplir(cur.id, b);
    else if (b.classList.contains('js-save-sym')) sintoma(cur.id, mFeel, mTags, b).then(function () { euModal.close('m-meal'); });
    else if (b.classList.contains('js-undo')) {
      b.disabled = true;
      api('/nutricion/api/descumplir', { meal_id: cur.id }).then(function (r) {
        if (!r.ok) { toast('No se pudo deshacer', 'err'); b.disabled = false; return; }
        setEstado(r.estado); if (window.euRefreshXp) euRefreshXp();
        toast(r.bono_revertido ? 'Deshecho · se revirtió el bono del día' : 'Deshecho');
        euModal.close('m-meal'); renderAll();
      });
    } else if (b.classList.contains('js-rm')) removeMeal(+b.dataset.id);
  });

  function removeMeal(id, day) {
    var m = findMeal(id); if (!m) return;
    var dk = day || Object.keys(S.week).find(function (k) { return (S.week[k] || []).some(function (x) { return x.id === id; }); });
    fetch('/nutricion/api/comida/' + id, { method: 'DELETE' }).then(function () {
      if (dk) S.week[dk] = S.week[dk].filter(function (x) { return x.id !== id; });
      toast(m.slot + ' eliminada');
      if (!$('m-meal').hidden) euModal.close('m-meal');
      renderAll();
    });
  }

  /* ══ Desliz (m-slip) ══════════════════════════════════════════════════ */
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
  $('slip-submit').addEventListener('click', function () {
    if (!slip.t) return;
    var btn = this; btn.disabled = true;
    api('/nutricion/api/desliz', { trig_id: slip.t.id, over: slip.over, note: $('slip-note').value }).then(function (r) {
      setEstado(r.estado); if (window.euRefreshXp) euRefreshXp();
      toast('−' + r.pen + ' XP' + (r.msg ? ' · ' + r.msg : ''), 'err'); euModal.close('m-slip'); renderAll();
    }).catch(function () { toast('Sin conexión', 'err'); btn.disabled = false; });
  });

  /* ══ Agregar comida (m-add) — «Del recetario» lee la tabla recetas ═════ */
  var add = { day: null, mode: 'banco', slot: 'Comida', picked: null, ctag: 'safe', banco: [] };
  function slotSugerido() {
    var n = nowMin(), best = 'Comida';
    SLOTS.forEach(function (s) { if (toMin(SLOT_TIME[s]) <= n + 60) best = s; });
    return best;
  }
  function openAdd(day) {
    add = { day: day || S.today, mode: 'banco', slot: day && day !== S.today ? 'Comida' : slotSugerido(), picked: null, ctag: 'safe', banco: [] };
    $('m-add-t').textContent = 'Añadir a ' + (dayOf(add.day).full || 'tu plan');
    $('add-time').value = SLOT_TIME[add.slot] || '12:00';
    ['add-name', 'add-kcal', 'add-prot', 'add-ing'].forEach(function (k) { $(k).value = ''; });
    setMode('banco'); setCtag('safe'); renderAdd(); loadBanco(); euModal.open('m-add');
  }
  function loadBanco() {
    $('add-list').innerHTML = euSkelHTML(3, 48);
    fetch('/nutricion/api/banco?slot=' + encodeURIComponent(add.slot)).then(function (r) { return r.json(); }).then(function (b) { add.banco = b || []; add.picked = null; renderAdd(); });
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
    $('add-list').innerHTML = add.banco.length ? add.banco.map(function (r) {
      return '<button type="button" role="radio" class="dt-pick-b" data-pick="' + r.id + '" aria-checked="' + (!!add.picked && add.picked.id === r.id) + '">' + tagDot(r.tag) +
        '<span class="dt-pick-t"><span class="t-ui">' + esc(r.nombre) + '</span><span class="t-meta">' + (r.fodmap === 'seguro' ? 'Apta FODMAP' : r.fodmap === 'porcion' ? 'Porción' : 'Sin etiqueta') + ' · ' + r.kcal + ' kcal · ' + r.protein + 'g prot' + (r.nota ? ' · ' + esc(r.nota) : '') + '</span></span><i data-lucide="check" class="dt-pick-ok"></i></button>';
    }).join('') + '<a class="t-meta dt-pick-more" href="/recetas/?fodmap=seguro">Ver el recetario →</a>' : '<p class="t-meta">No hay recetas para este momento. <a href="/recetas/">Agrega una al recetario</a>.</p>';
    canAdd(); icons();
  }
  function canAdd() { $('add-submit').disabled = add.mode === 'banco' ? !add.picked : !$('add-name').value.trim(); }
  document.querySelectorAll('[data-mode]').forEach(function (b) { b.addEventListener('click', function () { setMode(b.dataset.mode); }); });
  document.querySelectorAll('[data-ctag]').forEach(function (b) { b.addEventListener('click', function () { setCtag(b.dataset.ctag); }); });
  $('add-name').addEventListener('input', canAdd);
  $('add-slots').addEventListener('click', function (e) { var b = e.target.closest('[data-slot]'); if (b) { add.slot = b.dataset.slot; $('add-time').value = SLOT_TIME[add.slot]; renderAdd(); loadBanco(); } });
  $('add-list').addEventListener('click', function (e) { var b = e.target.closest('[data-pick]'); if (b) { add.picked = add.banco.find(function (r) { return r.id === +b.dataset.pick; }); renderAdd(); } });
  $('add-submit').addEventListener('click', function () {
    var payload = { day: add.day, slot: add.slot, time: $('add-time').value || SLOT_TIME[add.slot] || '12:00' };
    if (add.mode === 'banco' && add.picked) payload.receta_id = add.picked.id;
    else {
      var name = $('add-name').value.trim(); if (!name) return;
      var ing = $('add-ing').value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      Object.assign(payload, { name: name, kcal: +$('add-kcal').value || 0, protein: +$('add-prot').value || 0, tag: add.ctag, note: 'Comida personalizada.',
        items: ing.length ? ing.map(function (t) { return { t: t, tag: add.ctag }; }) : [{ t: name, tag: add.ctag }] });
    }
    api('/nutricion/api/comida', payload).then(function (res) {
      if (!res.meal) { toast('No se pudo añadir', 'err'); return; }
      (S.week[add.day] = S.week[add.day] || []).push(res.meal);
      toast('Añadida: ' + (dayOf(add.day).full || '') + ' · ' + add.slot); euModal.close('m-add'); renderAll();
    });
  });

  /* ══ Semana (?vista=semana) ═══════════════════════════════════════════ */
  function renderSemana() {
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
  function mealRow(m, k) {
    return '<div class="eu-row dt-mrow">' + tagDot(m.tag) + '<button type="button" class="eu-row-main dt-mrow-b js-meal" data-id="' + m.id + '"><span class="t-eyebrow">' + esc(m.slot) + ' · ' + esc(m.time) + '</span><span class="eu-row-t">' + esc(m.name) + '</span></button>' +
      '<button type="button" class="eu-iconbtn js-rm" data-id="' + m.id + '" data-day="' + k + '" aria-label="Quitar ' + esc(m.name) + '"><i data-lucide="x"></i></button></div>';
  }
  if (VISTA === 'semana') $('sem-days').addEventListener('click', function (e) { var b = e.target.closest('[data-sd]'); if (b) { S.semDay = b.dataset.sd; renderSemana(); } });

  /* ── Síntomas (?vista=sintomas): responder pendientes en la fila ── */
  if (VISTA === 'sintomas') $('hist-list').addEventListener('click', function (e) {
    var f = e.target.closest('[data-feel]'); if (f) sintoma(+f.dataset.meal, f.dataset.feel, [], f);
  });

  /* ── Delegación general ── */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b || !root.contains(b)) return;
    if (b.classList.contains('js-meal')) openMeal(+b.dataset.id);
    else if (b.classList.contains('js-add')) openAdd(b.dataset.day || S.today);
    else if (b.classList.contains('js-slip')) openSlip();
    else if (b.classList.contains('js-rm')) removeMeal(+b.dataset.id, b.dataset.day);
    else if (b.classList.contains('js-repeat')) {
      api('/nutricion/api/repetir', { src_day: b.dataset.day }).then(function (res) {
        if (res.week) S.week = res.week;
        toast('Plantilla aplicada de lunes a viernes', 'win'); renderSemana();
      });
    }
  });

  function renderAll() { if (VISTA === 'semana') renderSemana(); else if (!VISTA) renderHoy(); }
  renderAll(); icons();
  // La comida «Ahora» cambia con la hora: repinta cada 5 min.
  if (!VISTA) setInterval(function () { if (!document.hidden && askId === null) renderHoy(); }, 300000);
})();
