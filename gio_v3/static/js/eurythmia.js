/* Eurythmia — Design System V2: baile (sesión guiada con metrónomo, runner y
   cierre en bitácora; repertorio con drills; escalera de niveles) y música
   (100 mejores álbumes con ranking personal por dimensiones). */
(function () {
  'use strict';
  var root = document.getElementById('ey');
  if (!root) return;
  var D = JSON.parse(document.getElementById('ey-data').textContent || '{}');
  var PHASES = D.phases || [], LEVELS = D.levels || [], FLOW = D.flow || [], DIMS = D.dims || [];
  var STATE = D.state, MUSICA = D.musica;
  var PH_CAT = { diso: 'eurythmia', paso: 'oikonomia', improv: 'harma' };
  var MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function post(url, body) {
    var o = { method: 'POST' };
    if (body !== undefined) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(url, o).then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }
  function mini(items) {
    return items.map(function (it) {
      return '<div class="eu-card eu-stat"><div class="eu-stat-lbl">' + it[1] + '</div><div class="eu-stat-val' + (it[2] ? ' fg-brand' : '') + '">' + it[0] + '</div></div>';
    }).join('');
  }
  function emptyHtml(ic, t, txt) {
    return '<div class="eu-card"><div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p></div></div>';
  }

  /* ── Submódulos y sub-pestañas ──────────────────────────────────────── */
  function setMod(m) {
    root.dataset.mod = m;
    $$('[data-mod-set]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.modSet === m)); });
    $('mod-baile').hidden = m !== 'baile';
    $('mod-musica').hidden = m !== 'musica';
    if (m === 'musica') renderMusica();
  }
  $$('[data-mod-set]').forEach(function (b) { b.addEventListener('click', function () { setMod(b.dataset.modSet); }); });
  function setTab(t) {
    $$('[data-tab]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tab === t)); });
    $$('.ey-panel').forEach(function (p) { p.hidden = p.id !== 'panel-' + t; });
  }
  $$('[data-tab]').forEach(function (b) { b.addEventListener('click', function () { setTab(b.dataset.tab); }); });

  /* ── Sesión: duración, fases, paso y metrónomo ──────────────────────── */
  function splitMinutes(total) {
    var base = [10, 15, 5], sum = 30;
    var mins = base.map(function (b) { return Math.max(1, Math.round(b / sum * total)); });
    var diff = total - mins.reduce(function (a, b) { return a + b; }, 0);
    mins[1] = Math.max(1, mins[1] + diff);
    return mins;
  }
  function allSteps() { return STATE.repertoire.libres.concat(STATE.repertoire.pareja); }
  function fmtTime(sec) { var m = Math.floor(sec / 60), s = sec % 60; return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0'); }

  var total = 30, stepKey = allSteps()[0] ? allSteps()[0].step_key : '';
  var sound = false, bpm = 180, metroTimer = null, audioCtx = null;

  function renderSession() {
    $$('#ey-presets [data-min]').forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.min === total)); });
    $('ey-total-range').value = total;
    $('ey-total-n').textContent = total;
    var mins = splitMinutes(total);
    $('ey-phases').innerHTML = PHASES.map(function (p, i) {
      return '<li class="ey-phase" data-cat="' + (PH_CAT[p.id] || 'eurythmia') + '">' +
        '<span class="ey-phase-bd"><span class="eu-between"><span class="t-ui"><span class="ey-glyph-sm" aria-hidden="true">' + esc(p.glyph) + '</span> ' + esc(p.short) + '</span>' +
        '<span class="t-data ey-phase-min">' + mins[i] + '<span class="t-meta"> min</span></span></span>' +
        '<span class="t-meta">' + esc(p.principle) + ' — ' + esc(p.desc) + '</span></span></li>';
    }).join('');
    $('ey-split-lbl').textContent = total + ' min repartidos';
    $('ey-start-min').textContent = total;
  }
  function renderSteps() {
    $('ey-step-chips').innerHTML = allSteps().map(function (s) {
      return '<button type="button" class="eu-chip" data-step="' + esc(s.step_key) + '" aria-pressed="' + (s.step_key === stepKey) + '">' + esc(s.name) + '</button>';
    }).join('');
  }
  $('ey-step-chips').addEventListener('click', function (e) {
    var b = e.target.closest('[data-step]'); if (!b) return;
    stepKey = b.dataset.step; renderSteps();
    var nb = document.querySelector('#ey-step-chips [data-step="' + CSS.escape(stepKey) + '"]'); if (nb) nb.focus();
  });
  $$('#ey-presets [data-min]').forEach(function (b) { b.addEventListener('click', function () { total = +b.dataset.min; renderSession(); }); });
  $('ey-total-range').addEventListener('input', function (e) { total = +e.target.value; renderSession(); });
  $('ey-bpm-range').addEventListener('input', function (e) { bpm = +e.target.value; $('ey-bpm-n').textContent = bpm; if (metroTimer) startMetro(); });
  $('ey-sound-toggle').addEventListener('click', function () {
    sound = !sound; this.setAttribute('aria-checked', String(sound));
  });

  function metroTick() {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
      osc.frequency.value = 1200; gain.gain.value = 0.15;
      osc.connect(gain); gain.connect(audioCtx.destination);
      osc.start(); osc.stop(audioCtx.currentTime + 0.04);
    } catch (e) { /* sin audio */ }
  }
  function startMetro() { stopMetro(); metroTimer = setInterval(function () { if (sound) metroTick(); }, 60000 / bpm); }
  function stopMetro() { if (metroTimer) { clearInterval(metroTimer); metroTimer = null; } }

  /* ── Runner de la sesión guiada ─────────────────────────────────────── */
  var runner = null, runnerInterval = null, finishing = false;
  function startRunner() {
    var mins = splitMinutes(total);
    var st = allSteps().filter(function (s) { return s.step_key === stepKey; })[0];
    runner = { phaseIdx: 0, mins: mins, secondsLeft: mins[0] * 60, paused: false, stepName: st ? st.name : '' };
    setPause(false);
    renderRunner();
    euModal.open('m-run');
    startMetro();
    clearInterval(runnerInterval);
    runnerInterval = setInterval(function () {
      if (!runner || runner.paused) return;
      runner.secondsLeft--;
      if (runner.secondsLeft < 0) { advancePhase(); return; }
      $('ey-r-time').textContent = fmtTime(runner.secondsLeft);
    }, 1000);
  }
  function renderRunner() {
    var p = PHASES[runner.phaseIdx];
    $('ey-r-phase').textContent = 'Fase ' + (runner.phaseIdx + 1) + ' / 3';
    $('ey-r-name').textContent = p.short + (p.id === 'paso' && runner.stepName ? ' · ' + runner.stepName : '');
    $('ey-r-desc').textContent = p.desc;
    $('ey-r-time').textContent = fmtTime(runner.secondsLeft);
    document.querySelector('.ey-runner').dataset.cat = PH_CAT[p.id] || 'eurythmia';
    $$('#ey-r-dots i').forEach(function (d, i) { d.className = i < runner.phaseIdx ? 'is-done' : (i === runner.phaseIdx ? 'is-on' : ''); });
  }
  function advancePhase() {
    if (!runner) return;
    if (runner.phaseIdx >= 2) { finishRunner(); return; }
    runner.phaseIdx++;
    runner.secondsLeft = runner.mins[runner.phaseIdx] * 60;
    renderRunner();
  }
  function stopRunner() { clearInterval(runnerInterval); runnerInterval = null; stopMetro(); }
  function finishRunner() {
    var r = runner; stopRunner(); runner = null;
    finishing = true; euModal.close('m-run'); finishing = false;
    openClose(total, r.mins, r.stepName);
  }
  function setPause(p) {
    if (runner) runner.paused = p;
    var b = $('ey-r-pause');
    b.querySelector('span').textContent = p ? 'Reanudar' : 'Pausar';
    b.querySelector('i,svg').outerHTML = '<i data-lucide="' + (p ? 'play' : 'pause') + '"></i>';
    icons();
  }
  $('ey-r-pause').addEventListener('click', function () { if (runner) setPause(!runner.paused); });
  $('ey-r-skip').addEventListener('click', advancePhase);
  $('ey-r-cancel').addEventListener('click', function () { euModal.close('m-run'); });
  // Cerrar el runner por cualquier vía (Esc, clic fuera, Cancelar) cancela la sesión.
  new MutationObserver(function () {
    if ($('m-run').hidden && runner && !finishing) { stopRunner(); runner = null; toast('Sesión cancelada'); }
  }).observe($('m-run'), { attributes: true, attributeFilter: ['hidden'] });
  $('ey-start-btn').addEventListener('click', startRunner);

  /* ── Hoja de cierre ─────────────────────────────────────────────────── */
  var closeCtx = null, flow = 3, closeGrabado = false;
  function openClose(mins, split, stepName) {
    closeCtx = { min: mins, split: split, step: stepName };
    flow = 3; closeGrabado = false;
    $('ey-close-min').textContent = mins;
    $('ey-close-sub').textContent = split.join(' · ') + ' min' + (stepName ? ' · técnica en ' + stepName : '');
    $('ey-improv').value = '';
    $('ey-close-grabado').setAttribute('aria-pressed', 'false');
    renderFlow();
    euModal.open('m-close');
  }
  function renderFlow() {
    var h = '';
    for (var n = 1; n <= 5; n++) {
      h += '<button type="button" class="ey-flow-btn' + (flow >= n ? ' is-on' : '') + '" role="radio" data-flow="' + n + '" aria-checked="' + (flow === n) + '" aria-label="' + esc(FLOW[n]) + '"><i data-lucide="music"></i></button>';
    }
    $('ey-flow-row').innerHTML = h;
    $('ey-flow-lbl').textContent = FLOW[flow];
    $('ey-close-xp').textContent = closeCtx ? closeCtx.min + flow * 4 : 0;
    icons();
  }
  $('ey-flow-row').addEventListener('click', function (e) {
    var b = e.target.closest('[data-flow]'); if (!b) return;
    flow = +b.dataset.flow; renderFlow();
    var nb = document.querySelector('[data-flow="' + flow + '"]'); if (nb) nb.focus();
  });
  $('ey-close-grabado').addEventListener('click', function () {
    closeGrabado = !closeGrabado; this.setAttribute('aria-pressed', String(closeGrabado));
  });
  $('f-close').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!closeCtx) return;
    var btn = $('ey-save-btn'); btn.disabled = true; btn.setAttribute('aria-busy', 'true');
    post('/eurythmia/api/session', {
      min: closeCtx.min, split: closeCtx.split, step: closeCtx.step,
      flow: flow, improv: $('ey-improv').value.trim(), grabado: closeGrabado,
    }).then(function (d) {
      if (d.error || !d._ok) { toast('No se pudo guardar la sesión', 'err'); return; }
      STATE = d.state; closeCtx = null;
      euModal.close('m-close');
      toast('+' + d.xp + ' XP · Sesión guardada', 'win');
      setTab('bitacora');
      renderRepertorio(); renderProgreso(); renderBitacora(); renderSteps();
    }).catch(function () { toast('Error de red', 'err'); })
      .finally(function () { btn.disabled = false; btn.removeAttribute('aria-busy'); });
  });

  /* ── Repertorio ─────────────────────────────────────────────────────── */
  var kind = 'libres';
  function mastery(m) {
    if (m >= 75) return { label: 'Automatizado', cls: 'eu-badge--success', bar: 'is-auto' };
    if (m >= 34) return { label: 'Drillando', cls: 'eu-badge--warning', bar: 'is-drill' };
    return { label: 'Aprendiendo', cls: '', bar: '' };
  }
  function renderRepertorio() {
    var list = STATE.repertoire[kind] || [];
    var auto = list.filter(function (s) { return s.mastery >= 75; }).length;
    var reps = list.reduce(function (a, s) { return a + s.reps; }, 0);
    $('ey-rep-stats').innerHTML = mini([[list.length, 'Figuras'], [auto, 'Automatizadas', true], [reps, 'Reps totales']]);
    $('ey-rep-list').innerHTML = list.length ? list.map(function (s) {
      var st = mastery(s.mastery);
      return '<article class="eu-card ey-fig"><div class="eu-between"><span class="t-card">' + esc(s.name) + '</span><span class="eu-badge ' + st.cls + '">' + st.label + '</span></div>' +
        '<div class="t-meta">' + esc(s.note) + ' · <span class="num">' + s.reps + '</span> reps</div>' +
        '<div class="ey-fig-row"><div class="eu-progress eu-progress--thin ey-mbar ' + st.bar + '" role="progressbar" aria-label="Dominio de ' + esc(s.name) + '" aria-valuenow="' + s.mastery + '" aria-valuemax="100"><i style="width:' + s.mastery + '%"></i></div>' +
        '<span class="t-data ey-mpct">' + s.mastery + '%</span>' +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-drill="' + esc(s.step_key) + '" aria-label="Registrar 10 repeticiones de ' + esc(s.name) + '"><i data-lucide="plus"></i>10 reps</button></div></article>';
    }).join('') : emptyHtml('footprints', 'Sin figuras', 'No hay figuras en esta categoría.');
    icons();
  }
  $$('[data-kind]').forEach(function (c) {
    c.addEventListener('click', function () {
      kind = c.dataset.kind;
      $$('[data-kind]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      renderRepertorio();
    });
  });
  $('ey-rep-list').addEventListener('click', function (e) {
    var b = e.target.closest('[data-drill]'); if (!b) return;
    var key = b.dataset.drill; b.disabled = true;
    post('/eurythmia/api/drill', { step_key: key }).then(function (d) {
      if (d.error) { toast('No se pudo registrar', 'err'); return; }
      ['libres', 'pareja'].forEach(function (k) {
        STATE.repertoire[k] = STATE.repertoire[k].map(function (s) {
          return s.step_key === d.step_key ? Object.assign({}, s, { mastery: d.mastery, reps: d.reps }) : s;
        });
      });
      toast('+10 reps · dominio +3', 'ok');
      renderRepertorio(); renderSteps();
      var nb = document.querySelector('[data-drill="' + CSS.escape(key) + '"]'); if (nb) nb.focus();
    }).catch(function () { toast('Error de red', 'err'); }).finally(function () { b.disabled = false; });
  });

  /* ── Progreso ───────────────────────────────────────────────────────── */
  function levelFromMinutes(totalMin) {
    var hours = totalMin / 60, cur = LEVELS[LEVELS.length - 1];
    for (var i = 0; i < LEVELS.length; i++) { if (hours < LEVELS[i].h) { cur = LEVELS[i]; break; } }
    var idx = LEVELS.indexOf(cur), prevH = idx > 0 ? LEVELS[idx - 1].h : 0;
    var pct = cur.h > prevH ? (hours - prevH) / (cur.h - prevH) : 1;
    return { level: cur, idx: idx, pct: Math.min(1, Math.max(0, pct)), hoursToNext: Math.max(0, cur.h - hours) };
  }
  function renderProgreso() {
    var sv = $$('.ey-stats .eu-stat-val');
    if (sv.length >= 3) { sv[0].textContent = STATE.streak + ' d'; sv[1].textContent = (STATE.total_min / 60).toFixed(1); sv[2].textContent = STATE.sessions; }
    var lv = levelFromMinutes(STATE.total_min), circ = 2 * Math.PI * 56, ring = $('ey-ring-fg');
    ring.setAttribute('stroke-dasharray', circ);
    ring.setAttribute('stroke-dashoffset', circ * (1 - lv.pct));
    var next = LEVELS[Math.min(lv.idx + 1, LEVELS.length - 1)], isMax = lv.idx === LEVELS.length - 1;
    var weeks = STATE.avg_daily > 0 ? Math.ceil(lv.hoursToNext * 60 / STATE.avg_daily / 7) : 0;
    $('ey-forecast').innerHTML = isMax ? 'Nivel máximo — ahora se trata de refinar.'
      : (STATE.avg_daily > 0
        ? 'A tu ritmo de <b>' + STATE.avg_daily + ' min/día</b> alcanzas <b class="fg-brand">' + esc(next.name) + '</b> en <b class="fg-brand">~' + weeks + ' semana' + (weeks !== 1 ? 's' : '') + '</b>.'
        : 'Registra tu primera sesión para estimar cuándo alcanzas <b class="fg-brand">' + esc(next.name) + '</b>.');
    $('ey-ladder').innerHTML = LEVELS.map(function (L, i) {
      var done = i < lv.idx, cur = i === lv.idx;
      return '<li class="eu-row ey-rung' + (cur ? ' is-cur' : done ? ' is-done' : ' is-next') + '"' + (cur ? ' aria-current="step"' : '') + '>' +
        '<span class="ey-rung-n t-data">' + (done ? '<i data-lucide="check"></i>' : L.n) + '</span>' +
        '<span class="eu-grow ey-rung-bd"><span class="t-card">' + esc(L.name) + '</span><span class="t-meta">' + esc(L.sub) + '</span></span>' +
        '<span class="t-data t-meta">' + L.h + ' h</span></li>';
    }).join('');
    icons();
  }

  /* ── Bitácora ───────────────────────────────────────────────────────── */
  function renderBitacora() {
    var log = STATE.log || [];
    var totalMin = log.reduce(function (a, l) { return a + l.min; }, 0);
    var xp = log.reduce(function (a, l) { return a + l.xp; }, 0);
    $('ey-log-stats').innerHTML = mini([[log.length, 'Sesiones', true], [Math.floor(totalMin / 60) + 'h', 'Registradas'], [xp, 'XP en bitácora']]);
    $('ey-grabado-chip').setAttribute('aria-pressed', String(!!STATE.grabado_today));
    if (!log.length) { $('ey-log-list').innerHTML = emptyHtml('notebook-pen', 'Sin sesiones todavía', 'Empieza una sesión guiada en la pestaña Sesión.'); icons(); return; }
    $('ey-log-list').innerHTML = log.map(function (l) {
      var p = l.date.split('-').map(Number);
      return '<article class="eu-card ey-entry"><div class="eu-between"><div><span class="t-card">' + p[2] + ' ' + MES[p[1] - 1] + '</span> <span class="t-meta num">' + l.min + ' min</span></div>' +
        '<span class="eu-badge eu-badge--xp num">+' + l.xp + ' XP</span></div>' +
        '<div class="ey-splitbar" aria-label="Reparto ' + l.split.join(' / ') + ' min">' + l.split.map(function (mn, i) {
          return '<i data-cat="' + (PH_CAT[(PHASES[i] || {}).id] || 'eurythmia') + '" style="flex:' + Math.max(mn, 0.0001) + '"></i>';
        }).join('') + '</div>' +
        '<div class="ey-entry-tags">' + (l.step ? '<span class="eu-badge eu-badge--cat" data-cat="eurythmia"><i data-lucide="music"></i>' + esc(l.step) + '</span>' : '') +
        '<span class="eu-badge">' + esc(FLOW[l.flow] || '') + '</span>' +
        (l.grabado ? '<span class="eu-badge eu-badge--info"><i data-lucide="video"></i>grabado</span>' : '') + '</div>' +
        (l.improv ? '<p class="t-quote ey-quote">“' + esc(l.improv) + '”</p>' : '') + '</article>';
    }).join('');
    icons();
  }
  $('ey-grabado-chip').addEventListener('click', function () {
    post('/eurythmia/api/grabado/toggle').then(function (d) {
      if (!d.state) { toast('Error al guardar', 'err'); return; }
      STATE = d.state; renderBitacora();
      toast(d.action === 'added' ? 'Marcado como grabado' : 'Desmarcado', 'ok');
    }).catch(function () { toast('Error de red', 'err'); });
  });

  /* ── Música ─────────────────────────────────────────────────────────── */
  var muFilter = 'todos', openRate = null;
  function score(v) { return v != null ? Number(v).toFixed(1) : '—'; }
  function muItems() {
    if (muFilter === 'pendientes') return MUSICA.albumes.filter(function (a) { return !a.escuchado; });
    if (muFilter === 'escuchados') return MUSICA.albumes.filter(function (a) { return a.escuchado; });
    if (muFilter === 'ranking') return MUSICA.ranking;
    return MUSICA.albumes;
  }
  function ratePanel(a) {
    return DIMS.map(function (d) {
      var val = a['rating_' + d.key], dots = '';
      for (var i = 1; i <= 10; i++) {
        dots += '<button type="button" class="ey-dot' + (val != null && i <= val ? ' is-on' : '') + '" data-dim="' + d.key + '" data-val="' + i + '" aria-label="' + esc(d.label) + ': ' + i + '" aria-pressed="' + (val === i) + '"></button>';
      }
      return '<div class="ey-dim"><div class="eu-between"><span class="t-meta">' + esc(d.label) + '</span><span class="t-data fg-brand">' + (val == null ? '—' : val) + '</span></div><div class="ey-dots" role="group" aria-label="' + esc(d.label) + '">' + dots + '</div></div>';
    }).join('') + '<div class="t-meta ey-overall">Tu rating · <b class="t-data fg-brand">' + score(a.mi_rating) + '</b>/10</div>';
  }
  function renderMusica() {
    var box = $('mu-list'), items = muItems();
    if (muFilter === 'ranking') {
      box.innerHTML = items.length ? '<ol class="eu-card eu-card--flush eu-list mu-list">' + items.map(function (a, i) {
        return '<li class="eu-row"><span class="mu-pos t-data' + (i < 3 ? ' is-top' : '') + '">' + (i + 1) + '</span>' +
          '<span class="eu-grow mu-info"><span class="t-ui">' + esc(a.album) + '</span><span class="t-meta">' + esc(a.artista) + ' · #' + a.rank + ' Apple Music</span></span>' +
          '<span class="t-data fg-brand">' + score(a.mi_rating) + '<span class="t-meta">/10</span></span></li>';
      }).join('') + '</ol>' : emptyHtml('trophy', 'Tu ranking está vacío', 'Aún no calificaste ningún álbum escuchado.');
      icons(); return;
    }
    if (!items.length) { box.innerHTML = emptyHtml('disc-3', 'Nada en este filtro', 'No hay álbumes en esta vista.'); icons(); return; }
    box.innerHTML = '<ol class="eu-card eu-card--flush eu-list mu-list">' + items.map(function (a) {
      var open = openRate === a.id && a.escuchado;
      return '<li class="mu-item' + (a.escuchado ? ' is-done' : '') + '" id="mu-row-' + a.id + '"><div class="eu-row mu-row">' +
        '<span class="mu-rank t-data">' + a.rank + '</span>' +
        '<button type="button" class="mu-check" data-act="toggle" data-id="' + a.id + '" aria-pressed="' + !!a.escuchado + '" aria-label="' + (a.escuchado ? 'Marcar como pendiente' : 'Marcar como escuchado') + ': ' + esc(a.album) + '"><i data-lucide="check"></i></button>' +
        '<span class="eu-grow mu-info"><span class="t-ui">' + esc(a.album) + '</span><span class="t-meta">' + esc(a.artista) + (a.anio ? ' · ' + a.anio : '') + '</span></span>' +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm mu-rate' + (a.mi_rating != null ? ' is-rated' : '') + '" data-act="rate" data-id="' + a.id + '" aria-expanded="' + open + '" aria-controls="mu-panel-' + a.id + '" aria-label="Calificar ' + esc(a.album) + '"' + (a.escuchado ? '' : ' disabled') + '><i data-lucide="star"></i><span class="num" id="mu-score-' + a.id + '">' + score(a.mi_rating) + '</span></button>' +
        '</div><div class="ey-rate" id="mu-panel-' + a.id + '"' + (open ? '' : ' hidden') + '>' + ratePanel(a) + '</div></li>';
    }).join('') + '</ol>';
    icons();
  }
  function syncMusica() {
    $('mu-count-n').textContent = MUSICA.escuchados_n + '/' + MUSICA.total;
    var bar = $('mu-bar'); bar.setAttribute('aria-valuenow', MUSICA.escuchados_n);
    bar.querySelector('i').style.width = (MUSICA.total ? MUSICA.escuchados_n / MUSICA.total * 100 : 0) + '%';
    $('mu-f-todos').querySelector('.ct').textContent = MUSICA.total;
    $('mu-f-pendientes').querySelector('.ct').textContent = MUSICA.total - MUSICA.escuchados_n;
    $('mu-f-escuchados').querySelector('.ct').textContent = MUSICA.escuchados_n;
  }
  function muToggle(id) {
    var a = MUSICA.albumes.filter(function (x) { return x.id === id; })[0]; if (!a) return;
    var now = !a.escuchado;
    post('/eurythmia/api/album/' + id, { escuchado: now }).then(function (d) {
      if (!d._ok || !d.ok) { toast('Error al guardar', 'err'); return; }
      MUSICA = d.musica;
      if (d.gam && d.gam.xp) toast('+' + d.gam.xp + ' XP', 'win');
      openRate = now ? id : (openRate === id ? null : openRate);
      syncMusica(); renderMusica();
      var nb = document.querySelector('[data-act="toggle"][data-id="' + id + '"]'); if (nb) nb.focus();
    }).catch(function () { toast('Sin conexión', 'err'); });
  }
  function muRateToggle(id) {
    openRate = openRate === id ? null : id;
    $$('#mu-list .ey-rate').forEach(function (el) { el.hidden = el.id !== 'mu-panel-' + openRate; });
    $$('#mu-list [data-act="rate"]').forEach(function (b) { b.setAttribute('aria-expanded', String(+b.dataset.id === openRate)); });
  }
  function muRate(id, dim, val) {
    var body = {}; body['rating_' + dim] = val;
    post('/eurythmia/api/album/' + id, body).then(function (d) {
      if (!d._ok || !d.ok) { toast('Error al guardar', 'err'); return; }
      MUSICA = d.musica;
      var a = MUSICA.albumes.filter(function (x) { return x.id === id; })[0]; if (!a) return;
      $('mu-panel-' + id).innerHTML = ratePanel(a);
      $('mu-score-' + id).textContent = score(a.mi_rating);
      document.querySelector('[data-act="rate"][data-id="' + id + '"]').classList.toggle('is-rated', a.mi_rating != null);
      var dot = document.querySelector('#mu-panel-' + id + ' [data-dim="' + dim + '"][data-val="' + val + '"]'); if (dot) dot.focus();
    }).catch(function () { toast('Sin conexión', 'err'); });
  }
  $('mu-list').addEventListener('click', function (e) {
    var dot = e.target.closest('.ey-dot');
    if (dot) { muRate(+dot.closest('.mu-item').id.replace('mu-row-', ''), dot.dataset.dim, +dot.dataset.val); return; }
    var b = e.target.closest('[data-act]'); if (!b) return;
    if (b.dataset.act === 'toggle') muToggle(+b.dataset.id); else muRateToggle(+b.dataset.id);
  });
  $$('[data-mf]').forEach(function (c) {
    c.addEventListener('click', function () {
      muFilter = c.dataset.mf;
      $$('[data-mf]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      renderMusica();
    });
  });

  /* ── init ───────────────────────────────────────────────────────────── */
  renderSession(); renderSteps(); renderRepertorio(); renderProgreso(); renderBitacora();
  if (location.hash === '#musica') setMod('musica');
})();
