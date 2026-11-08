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

  /* ── Bloques: uno abierto, el «Ahora» (nota 3); clic en el encabezado
     abre o cierra cualquiera ── */
  function setOpen(bid, open) {
    var body = $('blbody-' + bid), h = document.querySelector('[data-bl-toggle="' + bid + '"]');
    if (!body || !h) return;
    body.hidden = !open;
    h.setAttribute('aria-expanded', String(open));
  }
  root.addEventListener('click', function (e) {
    var h = e.target.closest('[data-bl-toggle]'); if (!h) return;
    setOpen(h.dataset.blToggle, $('blbody-' + h.dataset.blToggle).hidden);
  });
  /* «Ahora» = primer bloque del día con requeridas pendientes */
  function markNow(dia) {
    var cards = [].slice.call(document.querySelectorAll('[data-dia-panel="' + dia + '"] .at-bl'));
    var now = cards.find(function (c) { return c.dataset.done !== 'true' && parseInt(c.dataset.req, 10) > 0; });
    cards.forEach(function (c) { c.classList.toggle('is-now', c === now); });
    return now;
  }

  /* ── Temporizadores ── */
  var TIMERS = {};
  function fmt(s) { return [Math.floor(s / 3600), Math.floor(s % 3600 / 60), s % 60].map(function (n) { return String(n).padStart(2, '0'); }).join(':'); }
  function timerEl(bid) { return document.querySelector('[data-timer="' + bid + '"]'); }
  function paint(bid) {
    var t = TIMERS[bid], el = timerEl(bid); if (!el) return;
    $('timer-' + bid).textContent = fmt(t.secs);
    var pct = t.ref ? t.secs / t.ref : 0;
    el.dataset.state = pct >= 1 ? 'over' : pct >= .85 ? 'near' : '';
    var btn = el.querySelector('.js-timer'), ic = t.running ? 'pause' : 'play';
    btn.setAttribute('aria-pressed', String(t.running));
    btn.querySelector('span').textContent = t.running ? 'Pausar' : (t.secs ? 'Seguir' : 'Iniciar');
    if (btn.dataset.ic !== ic) {
      btn.dataset.ic = ic;
      var i = document.createElement('i'); i.setAttribute('data-lucide', ic);
      btn.replaceChild(i, btn.firstElementChild); lucide.createIcons({ nodes: [i] });
    }
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
  /* Fila de recompensa: circle-dashed → circle-check verde al cumplirse */
  function setReward(id, ok) {
    var row = $('rw-' + id); if (!row || row.classList.contains('is-ok') === ok) return;
    row.classList.toggle('is-ok', ok);
    icon(row.querySelector('.at-rw-ic'), ok ? 'circle-check' : row.dataset.ic);
  }
  function updateDay(dia, r) {
    document.querySelectorAll('.js-day-cnt[data-dia="' + dia + '"]').forEach(function (el) { el.textContent = r.complete ? '✓' : r.done + '/' + r.total; });
    document.querySelectorAll('.js-rw-cnt[data-dia="' + dia + '"]').forEach(function (el) { el.textContent = r.done + '/' + r.total; });
    $('tab-' + dia).dataset.complete = String(!!r.complete);
    setReward(dia, !!r.complete);
    setReward('finde', $('tab-sabado').dataset.complete === 'true' && $('tab-domingo').dataset.complete === 'true');
    var justDone = null;
    (r.bloques || []).forEach(function (bl) {
      var p = $('blprog-' + bl.bloque_id); if (p) p.textContent = bl.bloque_done ? 'Listo' : bl.done_count + '/' + bl.required_count;
      var bar = $('blbar-' + bl.bloque_id); if (bar) bar.style.width = (bl.required_count ? Math.round(bl.done_count / bl.required_count * 100) : (bl.bloque_done ? 100 : 0)) + '%';
      var pb = $('blpb-' + bl.bloque_id); if (pb) pb.setAttribute('aria-valuenow', bl.done_count);
      var card = $('blcard-' + bl.bloque_id);
      if (card) {
        if (bl.bloque_done && card.dataset.done !== 'true' && bl.required_count > 0) justDone = bl.bloque_id;
        card.dataset.done = String(!!bl.bloque_done);
      }
      if (bl.bloque_done) stop(bl.bloque_id);
    });
    var now = markNow(dia);
    // Al terminar un bloque se cierra y se abre el siguiente pendiente
    if (justDone) {
      setTimeout(function () {
        setOpen(justDone, false);
        if (now) { setOpen(now.dataset.bl, true); now.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
      }, 450);
    }
  }

  /* ── Marcar tareas ── */
  var pending = {};
  async function toggleTask(btn) {
    var id = btn.dataset.task, bid = btn.dataset.bl, dia = btn.dataset.dia;
    if (pending[id]) return;
    if (root.dataset.preview) { toast('Vista previa: se marca el sábado y el domingo'); return; }
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
        (g.combo_bonuses || []).forEach(function (c) { setTimeout(function () { toast((c.name || c.label || 'Combo') + ' +' + c.xp + ' XP', 'win'); }, 300); });
        if (window.euGam) euGam(g, { el: btn });
      }
    } catch (_) { toast('Sin conexión', 'err'); }
    finally { delete pending[id]; }
  }
  root.addEventListener('click', function (e) { var b = e.target.closest('.js-task'); if (b) toggleTask(b); });

  /* ── Prioridades de la semana desde Praxis (nota 6) ── */
  var ps = $('prio-semana');
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function renderPS(d) {
    ps.querySelector('.js-ps-list').innerHTML = (d.opciones || []).map(function (o) {
      return '<button type="button" class="at-prio-it js-ps" data-id="' + o.id + '" aria-pressed="' + o.on + '"><i data-lucide="star"></i><span>' + esc(o.title) + '</span></button>';
    }).join('');
    ps.querySelector('.js-ps-n').textContent = d.n;
    ps.querySelector('.js-ps-empty').hidden = (d.opciones || []).length > 0;
    var f = ps.querySelector('.js-ps-form'); if (f) f.hidden = d.n >= d.max;
    lucide.createIcons();
    // Elegir 3 completa la tarea del bloque
    var row = $('trow-sun_prioridades');
    if (d.n >= d.max && row && row.getAttribute('aria-pressed') !== 'true') toggleTask(row);
  }
  if (ps) {
    ps.addEventListener('click', async function (e) {
      var b = e.target.closest('.js-ps'); if (!b) return;
      if (root.dataset.preview) { toast('Vista previa: las prioridades se eligen el fin de semana'); return; }
      b.disabled = true;
      try {
        var d = await jpost('/ataraxia/api/prioridad-semana/' + b.dataset.id);
        if (!d._ok || !d.ok) { toast(d.error || 'No se pudo guardar', 'err'); b.disabled = false; return; }
        renderPS(d);
        toast(d.prioridad ? 'Prioridad de la semana · ' + d.n + '/3' : 'Quitada de la semana');
      } catch (_) { toast('Sin conexión', 'err'); b.disabled = false; }
    });
    var psf = ps.querySelector('.js-ps-form');
    if (psf) psf.addEventListener('submit', async function (e) {
      e.preventDefault();
      var inp = $('ps-inp'), texto = inp.value.trim(); if (!texto) return;
      try {
        var d = await jpost('/ataraxia/api/prioridad-semana', { texto: texto });
        if (!d._ok || !d.ok) { toast(d.error || 'No se pudo guardar', 'err'); return; }
        inp.value = ''; renderPS(d); toast('Agregada a Esta semana · ' + d.n + '/3', 'win');
      } catch (_) { toast('Sin conexión', 'err'); }
    });
  }

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
        if (window.euGam) euGam(d.gam);
      } else toast('Revisión guardada');
      setTimeout(function () { location.reload(); }, 900);
    } catch (_) { toast('Sin conexión', 'err'); }
  });

  /* ── Menú ⋯ (nota 4): el Reset vive aquí y siempre pide confirmación ── */
  var more = $('more-trigger'), menu = $('at-menu');
  function setMenu(open) { menu.hidden = !open; more.setAttribute('aria-expanded', String(open)); if (open) menu.querySelector('[role=menuitem]').focus(); }
  more.addEventListener('click', function (e) { e.stopPropagation(); setMenu(menu.hidden); });
  document.addEventListener('click', function (e) { if (!menu.hidden && !menu.contains(e.target)) setMenu(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !menu.hidden) { setMenu(false); more.focus(); } });

  /* ── Reset de la semana ── */
  $('reset-trigger').addEventListener('click', function () { setMenu(false); euModal.open('at-reset'); });
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
