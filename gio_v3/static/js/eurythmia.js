/* Eurythmia — handoff Eurythmia v2. «Sesión de hoy» ya armada (duración
   habitual, bucle proporcional, 3 pasos sugeridos por espaciado), runner de
   la sesión guiada, cierre en la misma tarjeta con la recompensa en vivo,
   repertorio por espaciado y lateral (últimas sesiones, música, ciencia).
   Vistas completas: ?vista=bitacora | musica | progreso. */
(function () {
  'use strict';
  var root = document.getElementById('ey');
  if (!root) return;
  var D = JSON.parse(document.getElementById('ey-data').textContent || '{}');
  var PHASES = D.phases || [], FLOW = D.flow || [], DIMS = D.dims || [], GRAB = D.grabado || { xp: 3, ec: 1 };
  var STATE = D.state, MUSICA = D.musica;
  var VISTA = root.dataset.vista || '';
  var MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  var PH_BG = ['ph1', 'ph2', 'ph3'];
  var PH_CAT = { diso: 'eurythmia', paso: 'oikonomia', improv: 'harma' };

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function post(url, body) {
    var o = { method: 'POST' };
    if (body !== undefined) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(url, o).then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }
  function emptyHtml(ic, t, txt) {
    return '<div class="eu-card"><div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p></div></div>';
  }
  function splitMinutes(total) {
    var base = [10, 15, 5], sum = 30;
    var mins = base.map(function (b) { return Math.max(1, Math.round(b / sum * total)); });
    var diff = total - mins.reduce(function (a, b) { return a + b; }, 0);
    mins[1] = Math.max(1, mins[1] + diff);
    return mins;
  }
  function fmtTime(sec) { var m = Math.floor(sec / 60), s = sec % 60; return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0'); }
  function allSteps() { return STATE.repertoire.pareja.concat(STATE.repertoire.libres); }
  function stepBy(key) { return allSteps().filter(function (s) { return s.step_key === key; })[0]; }
  function hace(d) { return d == null ? 'sin práctica' : d === 0 ? 'hoy' : d === 1 ? 'ayer' : 'hace ' + d + ' d'; }
  function fecha(iso) {
    var p = iso.split('-').map(Number), hoy = new Date(), d = new Date(p[0], p[1] - 1, p[2]);
    var diff = Math.round((new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate()) - d) / 864e5);
    return diff === 0 ? 'hoy' : diff === 1 ? 'ayer' : diff < 7 ? ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'][d.getDay()] : p[2] + ' ' + MES[p[1] - 1];
  }

  /* Recompensa en vivo: las mismas fórmulas que /api/session y
     /api/preview-reward (xp = min + 4·fluidez; EC por fluidez y duración;
     el grabado +3 XP · +1 EC una vez al día). */
  function sessionEc(min, flow) { return (flow >= 5 ? 2 : flow >= 3 ? 1 : 0) + (min >= 45 ? 1 : 0); }
  function reward(min, flow, grabado) {
    var g = grabado && !STATE.grabado_today;
    return { xp: min + flow * 4 + (g ? GRAB.xp : 0), ec: sessionEc(min, flow) + (g ? GRAB.ec : 0) };
  }

  /* ── Lateral: últimas sesiones ── */
  function renderLast() {
    var box = $('ey-last'); if (!box) return;
    var log = (STATE.log || []).slice(0, 4);
    box.innerHTML = log.length ? log.map(function (l) {
      var dots = ''; for (var i = 1; i <= 5; i++) dots += '<i' + (i <= l.flow ? ' class="is-on"' : '') + '></i>';
      return '<div class="ey-last-row"><span class="ey-dots5" aria-label="Fluidez ' + l.flow + ' de 5">' + dots + '</span>' +
        '<div class="eu-grow ey-min"><div class="ey-last-t">' + esc(l.step || 'Sesión libre') + '</div><div class="num t-meta">' + fecha(l.date) + ' · ' + l.min + '′ · ' + esc(FLOW[l.flow] || '') + '</div></div>' +
        (l.grabado ? '<i data-lucide="video" class="ey-vid" aria-label="Grabada"></i>' : '') + '</div>';
    }).join('') : '<p class="t-meta ey-box-empty">Aún no hay sesiones.</p>';
  }

  /* ── Bitácora completa (?vista=bitacora) ── */
  function renderBitacora() {
    var box = $('ey-log-list'); if (!box) return;
    var log = STATE.log || [];
    if (!log.length) { box.innerHTML = emptyHtml('notebook-pen', 'Sin sesiones todavía', 'Empieza una sesión en «Sesión de hoy».'); icons(); return; }
    box.innerHTML = log.map(function (l) {
      var p = l.date.split('-').map(Number);
      return '<article class="eu-card ey-entry"><div class="eu-between"><div><span class="t-card">' + p[2] + ' ' + MES[p[1] - 1] + '</span> <span class="t-meta num">' + l.min + ' min</span></div>' +
        '<span class="eu-badge eu-badge--xp num">+' + l.xp + ' XP</span></div>' +
        '<div class="ey-splitbar" aria-label="Reparto ' + l.split.join(' / ') + ' min">' + l.split.map(function (mn, i) {
          return '<i class="' + PH_BG[i] + '" style="flex:' + Math.max(mn, 0.0001) + '"></i>';
        }).join('') + '</div>' +
        '<div class="ey-entry-tags">' + (l.step ? '<span class="eu-badge eu-badge--cat" data-cat="eurythmia"><i data-lucide="music"></i>' + esc(l.step) + '</span>' : '') +
        '<span class="eu-badge">' + esc(FLOW[l.flow] || '') + '</span>' +
        (l.grabado ? '<span class="eu-badge eu-badge--info"><i data-lucide="video"></i>grabado</span>' : '') + '</div>' +
        (l.improv ? '<p class="t-quote ey-quote">“' + esc(l.improv) + '”</p>' : '') + '</article>';
    }).join('');
    icons();
  }

  var sound = false, bpm = 180, metroTimer = null, audioCtx = null;
  var total = STATE.duracion_habitual || 30;
  var stepKey = (STATE.sugerencias[0] || allSteps()[0] || {}).step_key || '';
  var today = $('ey-today');

  if (today) {
    /* ── Sesión de hoy (nota 2) ── */
    var renderIdle = function () {
      $$('.ey-durs [data-min]').forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.min === total)); });
      var mins = splitMinutes(total);
      $('ey-loopbar').innerHTML = PHASES.map(function (p, i) {
        return '<div class="ey-seg ' + PH_BG[i] + '" style="flex:' + mins[i] + '"><span class="ey-seg-g" aria-hidden="true">' + esc(p.glyph) + '</span>' +
          '<span class="ey-seg-n">' + esc(p.id === 'paso' ? 'Paso' : p.short) + '</span><span class="ey-seg-m num">' + mins[i] + '′</span></div>';
      }).join('');
      $('ey-start-min').textContent = total;
      var sug = STATE.sugerencias.slice();
      if (stepKey && !sug.some(function (s) { return s.step_key === stepKey; })) {
        var st = stepBy(stepKey); if (st) sug = [{ step_key: st.step_key, nombre: st.name, mastery: st.mastery, dias: st.dias }].concat(sug.slice(0, 2));
      }
      $('ey-sugg').innerHTML = sug.length ? sug.map(function (s) {
        return '<button type="button" class="ey-sug" data-step="' + esc(s.step_key) + '" aria-pressed="' + (s.step_key === stepKey) + '">' +
          '<span class="ey-sug-n">' + esc(s.nombre) + '</span><span class="ey-bar"><i style="--p:' + s.mastery + '%"></i></span>' +
          '<span class="ey-sug-s' + (s.dias == null || s.dias > 10 ? ' ey-warn' : '') + '">' + s.mastery + '% · ' + hace(s.dias) + '</span></button>';
      }).join('') : '<p class="t-meta">Todo tu repertorio está automatizado. Elige un paso para mantenerlo.</p>';
      $('ey-other').innerHTML = allSteps().map(function (s) {
        return '<button type="button" class="eu-chip" data-step="' + esc(s.step_key) + '" aria-pressed="' + (s.step_key === stepKey) + '">' + esc(s.name) + '</button>';
      }).join('');
    };
    root.addEventListener('click', function (e) {
      var b = e.target.closest('.ey-durs [data-min]');
      if (b) { total = +b.dataset.min; renderIdle(); return; }
      var st = e.target.closest('#ey-sugg [data-step], #ey-other [data-step]');
      if (st) { stepKey = st.dataset.step; renderIdle(); return; }
      if (e.target.closest('.js-other')) {
        var o = $('ey-other'), btn = e.target.closest('.js-other'); o.hidden = !o.hidden; btn.setAttribute('aria-expanded', String(!o.hidden));
      }
    });
    $('ey-sound-toggle').addEventListener('click', function () { sound = !sound; this.setAttribute('aria-checked', String(sound)); });
    $('ey-bpm-range').addEventListener('input', function (e) { bpm = +e.target.value; $('ey-bpm-n').textContent = bpm; $('ey-bpm-lbl').textContent = bpm; if (metroTimer) startMetro(); });

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
    var st = stepBy(stepKey);
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


    /* ── Cierre en la misma tarjeta (nota 5) ── */
    var closeCtx = null, flow = 3, closeGrabado = false;
    var setMode = function (m) { today.dataset.mode = m; };
    var openClose = function (mins, split, stepName) {
      closeCtx = { min: mins, split: split, step: stepName, key: stepKey };
      flow = 3; closeGrabado = false;
      $('ey-close-t').textContent = mins + ' min' + (stepName ? ' · ' + stepName : '');
      $('ey-improv').value = '';
      $('ey-close-grabado').setAttribute('aria-pressed', 'false');
      renderFlow();
      setMode('closing');
      today.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    var renderFlow = function () {
      var h = '';
      for (var n = 1; n <= 5; n++) h += '<button type="button" class="ey-flow-b" role="radio" data-flow="' + n + '" aria-checked="' + (flow === n) + '">' + esc(FLOW[n]) + '</button>';
      $('ey-flow-row').innerHTML = h;
      var r = reward(closeCtx.min, flow, closeGrabado);
      $('ey-reward').textContent = '+' + r.xp + ' XP · +' + r.ec + ' EC';
    };
    $('ey-flow-row').addEventListener('click', function (e) {
      var b = e.target.closest('[data-flow]'); if (!b) return;
      flow = +b.dataset.flow; renderFlow();
      var nb = document.querySelector('[data-flow="' + flow + '"]'); if (nb) nb.focus();
    });
    $('ey-close-grabado').addEventListener('click', function () {
      closeGrabado = !closeGrabado; this.setAttribute('aria-pressed', String(closeGrabado)); renderFlow();
    });
    root.querySelector('.js-close-cancel').addEventListener('click', function () { closeCtx = null; setMode('idle'); });
    root.querySelector('.js-again').addEventListener('click', function () { setMode('idle'); renderIdle(); });
    $('f-close').addEventListener('submit', function (e) {
      e.preventDefault();
      if (!closeCtx) return;
      var btn = $('ey-save-btn'); btn.disabled = true; btn.setAttribute('aria-busy', 'true');
      var ctx = closeCtx;
      post('/eurythmia/api/session', {
        min: ctx.min, split: ctx.split, step: ctx.step, step_key: ctx.key,
        flow: flow, improv: $('ey-improv').value.trim(), grabado: closeGrabado,
      }).then(function (d) {
        if (d.error || !d._ok) { toast('No se pudo guardar la sesión', 'err'); return; }
        STATE = d.state; closeCtx = null;
        var xp = d.xp + (d.grabado_gam ? GRAB.xp : 0);
        $('ey-saved-sub').textContent = '+' + xp + ' XP · +' + d.ec_total + ' EC' +
          (d.step_mastery_nuevo != null ? ' · ' + ctx.step + ' sube a ' + d.step_mastery_nuevo + '%' : '') + ' · racha ' + STATE.streak + ' d';
        setMode('saved');
        if (window.euGam) euGam(d.gam || { xp: d.xp });
        refreshStrip(); renderRep(); renderLast(); icons();
      }).catch(function () { toast('Error de red', 'err'); })
        .finally(function () { btn.disabled = false; btn.removeAttribute('aria-busy'); });
    });
    $('ey-start-btn').addEventListener('click', startRunner);

    /* Franja: se vuelve a pedir la página y se reemplaza (sin recargar) */
    var refreshStrip = function () {
      fetch(location.pathname).then(function (r) { return r.text(); }).then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html'), a = $('ey-strip'), b = doc.getElementById('ey-strip');
        if (a && b) { a.replaceWith(b); icons(); }
      });
    };

    renderIdle();
    if (root.dataset.from === 'acta') setTimeout(function () { today.scrollIntoView({ block: 'start' }); }, 50);
  }

  /* ── Repertorio (nota 4) ── */
  var kind = 'pareja';
  function renderRep() {
    var box = $('ey-rep-list'); if (!box) return;
    var list = STATE.repertoire[kind] || [];
    box.innerHTML = list.length ? list.map(function (s) {
      var m = s.mastery || 0, est = m >= 80 ? 'auto' : m >= 50 ? 'cons' : 'apr';
      var old = s.dias != null && s.dias > 10 && m < 80;
      return '<div class="ey-rep-row" data-e="' + est + '"><span class="ey-rep-n">' + esc(s.name) + '</span>' +
        '<span class="ey-rep-m"><span class="ey-bar"><i style="--p:' + m + '%"></i></span><span class="num t-meta">' + m + '%</span></span>' +
        '<span class="ey-rep-e">' + esc(s.estado) + '</span>' +
        '<span class="num ey-rep-d' + (old ? ' ey-warn' : '') + '">' + hace(s.dias) + '</span></div>';
    }).join('') : '<p class="t-meta ey-box-empty">No hay figuras en esta categoría.</p>';
  }
  $$('[data-kind]').forEach(function (c) {
    c.addEventListener('click', function () {
      kind = c.dataset.kind;
      $$('[data-kind]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      renderRep();
    });
  });

  if (VISTA === 'musica') {
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
      if (d.gam && window.euGam) euGam(d.gam, { el: nb });
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

    renderMusica();
  }
  /* ── init ── */
  renderRep(); renderLast(); renderBitacora(); icons();
})();
