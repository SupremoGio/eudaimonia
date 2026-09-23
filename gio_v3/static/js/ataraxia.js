/* Ataraxia — Design System V2.
   Rutina de fin de semana (sábado reset · domingo estrategia) por bloques con
   temporizador, prioridades de la semana, revisión semanal y reset. */
(function () {
  'use strict';
  var root = document.getElementById('at');
  if (!root) return;
  function $(id) { return document.getElementById(id); }
  function jpost(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }
  function icon(el, name) { var i = document.createElement('i'); i.setAttribute('data-lucide', name); el.innerHTML = ''; el.appendChild(i); lucide.createIcons({ nodes: [i] }); }

  /* ── Pestañas de día ── */
  function showDia(dia) {
    root.dataset.dia = dia;
    document.querySelectorAll('[data-dia-set]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.diaSet === dia)); });
    document.querySelectorAll('[data-dia-panel]').forEach(function (p) { p.hidden = p.dataset.diaPanel !== dia; });
    try { history.replaceState(null, '', '?dia=' + dia); } catch (_) {}
  }
  document.querySelectorAll('[data-dia-set]').forEach(function (b) { b.addEventListener('click', function () { showDia(b.dataset.diaSet); }); });

  /* ── Bloques plegables ── */
  root.addEventListener('click', function (e) {
    var h = e.target.closest('[data-bl-toggle]'); if (!h) return;
    var body = $('blbody-' + h.dataset.blToggle);
    body.hidden = !body.hidden;
    h.setAttribute('aria-expanded', String(!body.hidden));
  });

  /* ── Temporizadores ── */
  var TIMERS = {};
  function fmt(s) { return [Math.floor(s / 3600), Math.floor(s % 3600 / 60), s % 60].map(function (n) { return String(n).padStart(2, '0'); }).join(':'); }
  function timerEl(bid) { return document.querySelector('[data-timer="' + bid + '"]'); }
  function paint(bid) {
    var t = TIMERS[bid], el = timerEl(bid); if (!el) return;
    $('timer-' + bid).textContent = fmt(t.secs);
    var pct = t.ref ? t.secs / t.ref : 0;
    el.dataset.state = pct >= 1 ? 'over' : pct >= .85 ? 'near' : '';
    var btn = el.querySelector('.js-timer');
    btn.setAttribute('aria-label', t.running ? 'Pausar temporizador' : 'Iniciar temporizador');
    btn.setAttribute('aria-pressed', String(t.running));
    if (btn.dataset.ic !== (t.running ? 'pause' : 'play')) { btn.dataset.ic = t.running ? 'pause' : 'play'; icon(btn, btn.dataset.ic); }
  }
  function stop(bid) { var t = TIMERS[bid]; if (t && t.running) { clearInterval(t.iv); t.running = false; paint(bid); } }
  root.addEventListener('click', function (e) {
    var b = e.target.closest('.js-timer, .js-timer-reset'); if (!b) return;
    var el = b.closest('[data-timer]'), bid = el.dataset.timer;
    var t = TIMERS[bid] = TIMERS[bid] || { secs: 0, running: false, iv: null, ref: parseInt(el.dataset.ref, 10) || 0 };
    if (b.classList.contains('js-timer-reset')) { clearInterval(t.iv); t.running = false; t.secs = 0; }
    else if (t.running) { clearInterval(t.iv); t.running = false; }
    else { t.running = true; t.iv = setInterval(function () { t.secs++; paint(bid); }, 1000); }
    paint(bid);
  });

  /* ── Progreso ── */
  function updateDay(dia, r) {
    var pct = r.total ? Math.round(r.done / r.total * 100) : 0;
    document.querySelectorAll('.js-day-cnt[data-dia="' + dia + '"]').forEach(function (el) { el.textContent = r.done + ' / ' + r.total; });
    document.querySelectorAll('.js-day-bar[data-dia="' + dia + '"]').forEach(function (el) { el.style.width = pct + '%'; });
    $('tab-' + dia).dataset.complete = String(!!r.complete);
    $((dia === 'sabado' ? 'sat' : 'sun') + '-day-complete').hidden = !r.complete;
    (r.bloques || []).forEach(function (bl) {
      var p = $('blprog-' + bl.bloque_id); if (p) p.textContent = bl.done_count + '/' + bl.required_count;
      var bar = $('blbar-' + bl.bloque_id); if (bar) bar.style.width = (bl.required_count ? Math.round(bl.done_count / bl.required_count * 100) : 0) + '%';
      var card = $('blcard-' + bl.bloque_id); if (card) card.dataset.done = String(!!bl.bloque_done);
      if (bl.bloque_done) stop(bl.bloque_id);
    });
  }

  /* ── Marcar tareas ── */
  var pending = {};
  async function toggleTask(btn) {
    var id = btn.dataset.task, bid = btn.dataset.bl, dia = btn.dataset.dia;
    if (pending[id]) return;
    pending[id] = true;
    var done = btn.getAttribute('aria-pressed') === 'true';
    var secs = TIMERS[bid] ? TIMERS[bid].secs : 0;
    try {
      var d = await jpost(done ? '/ataraxia/api/rutina/uncheck' : '/ataraxia/api/rutina/check', done ? { bloque_id: id } : { bloque_id: id, tiempo_seg: secs });
      if (!d._ok) { toast('Error al guardar', 'err'); return; }
      btn.setAttribute('aria-pressed', String(!done));
      updateDay(dia, d.rutina);
      var g = d.gam;
      if (g && !done) {
        if (g.xp > 0 || g.ec > 0) toast('+' + g.xp + ' XP' + (g.ec > 0 ? ' · +' + g.ec + ' EC' : ''), 'win');
        (g.combo_bonuses || []).forEach(function (c) { setTimeout(function () { toast(c.label + ' +' + c.xp + ' XP', 'win'); }, 300); });
        if (g.achievements && g.achievements.length && window.euAnnounceAchievements) euAnnounceAchievements(g);
      }
      if (!done) fetch('/ataraxia/api/rutina/finde/status').then(function (r) { return r.json(); })
        .then(function (s) { if (s.finde_perfecto) $('finde-banner').hidden = false; }).catch(function () {});
    } catch (_) { toast('Sin conexión', 'err'); }
    finally { delete pending[id]; }
  }
  root.addEventListener('click', function (e) { var b = e.target.closest('.js-task'); if (b) toggleTask(b); });

  /* ── Prioridades de la semana ── */
  var prio = $('prio-form');
  if (prio) prio.addEventListener('submit', async function (e) {
    e.preventDefault();
    var p = [1, 2, 3].map(function (n) { return $('prio-' + n).value.trim(); });
    if (!p[0] && !p[1] && !p[2]) { toast('Escribe al menos una prioridad', 'err'); return; }
    try {
      var d = await jpost('/ataraxia/api/prioridades-semana', { p1: p[0], p2: p[1], p3: p[2] });
      if (!d._ok || !d.ok) { toast('Error al guardar', 'err'); return; }
      toast('Guardadas — aparecen en el Acta Diurna toda la semana', 'win');
      var row = $('trow-sun_prioridades');
      if (row && row.getAttribute('aria-pressed') !== 'true') toggleTask(row);
    } catch (_) { toast('Sin conexión', 'err'); }
  });

  /* ── Revisión semanal ── */
  var rev = $('rev-form');
  if (rev) rev.addEventListener('submit', async function (e) {
    e.preventDefault();
    var body = { notas: $('rs-notas').value || '' };
    document.querySelectorAll('[data-metric]').forEach(function (i) { body[i.dataset.metric] = i.value; });
    try {
      var d = await jpost('/ataraxia/api/revision', body);
      if (!d._ok || !d.ok) { toast('Error al guardar', 'err'); return; }
      if (d.first_save && d.gam) {
        toast('Revisión guardada · +' + d.gam.xp + ' XP · +' + d.gam.ec + ' EC', 'win');
        if (d.gam.achievements && d.gam.achievements.length && window.euAnnounceAchievements) euAnnounceAchievements(d.gam);
      } else toast('Revisión guardada');
      setTimeout(function () { location.reload(); }, 900);
    } catch (_) { toast('Sin conexión', 'err'); }
  });

  /* ── Reset de la semana ── */
  $('reset-trigger').addEventListener('click', function () { euModal.open('at-reset'); });
  $('reset-confirm').addEventListener('click', async function () {
    euModal.close('at-reset');
    try {
      var d = await jpost('/ataraxia/api/rutina/reset', { token: 'ataraxia-reset-2026' });
      if (!d._ok || d.error) { toast('Error al resetear', 'err'); return; }
      toast('Semana reseteada');
      setTimeout(function () { location.reload(); }, 900);
    } catch (_) { toast('Sin conexión', 'err'); }
  });
})();
