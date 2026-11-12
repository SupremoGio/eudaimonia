/* Praxis (GTD) — Design System V2 · handoff Praxis v2.
   Captura → Inbox (4 destinos de un clic) → Hoy / Esta semana (columna
   principal) · Delegar / Ideas / Completadas hoy (columna derecha).
   Endpoints: POST /gtd/api/task · /api/task/<id>/classify · /complete ·
   DELETE /api/task/<id>. Fechas relativas en praxis-due.js. */
(function () {
  'use strict';
  var root = document.getElementById('px-root');
  if (!root) return;
  var tasks = JSON.parse(document.getElementById('px-data').textContent || '[]');
  tasks.forEach(function (t) {
    t.importante = t.importante == null ? null : !!t.importante;
    t.urgente = t.urgente == null ? null : !!t.urgente;
    t.completado = !!t.completado;
  });
  var tipo = 'tarea';
  var doneOpen = false;
  /* Tareas completadas hoy según el servidor: alimenta el bono de 3 */
  var doneToday = parseInt(root.dataset.doneToday, 10) || 0;
  /* Semanas cuyas prioridades (estrella de Ataraxia) siguen vigentes */
  var semPrio = (root.dataset.semanasPrio || '').split(',').filter(Boolean);

  var Q_LABEL = { hoy: 'Hoy', semana: 'Esta semana', delegar: 'Delegar', ideas: 'Ideas' };
  var TIPO = { tarea: ['Tarea', 'pin'], idea: ['Idea', 'lightbulb'], mantenimiento: ['Mantenimiento', 'wrench'] };
  /* Inbox de un clic (nota 3): cada destino manda su par importante/urgente */
  var DEST = [
    { q: 'hoy', label: 'Hoy', icon: 'flame', imp: 1, urg: 1, tip: 'Urgente e importante' },
    { q: 'semana', label: 'Semana', icon: 'calendar', imp: 1, urg: 0, tip: 'Importante' },
    { q: 'delegar', label: 'Delegar', icon: 'users', imp: 0, urg: 1, tip: 'Urgente' },
    { q: 'ideas', label: 'Idea', icon: 'lightbulb', imp: 0, urg: 0, tip: 'Ninguno' }
  ];
  var Due = window.PxDue || { relDue: function () { return null; }, byDue: function () { return 0; } };

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  /* Fecha del servidor (zona de la app), no la del navegador */
  function today() { return root.dataset.today; }
  function jpost(url, body) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }).then(function (r) { return r.json(); }).catch(function () { return null; }); }
  function find(id) { return tasks.find(function (x) { return x.id === id; }); }

  /* ── Captura ── */
  document.querySelectorAll('[data-tipo]').forEach(function (b) {
    b.addEventListener('click', function () {
      tipo = b.dataset.tipo;
      document.querySelectorAll('[data-tipo]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      document.getElementById('qi').focus();
    });
  });
  document.getElementById('px-capture').addEventListener('submit', async function (e) {
    e.preventDefault();
    var inp = document.getElementById('qi'), texto = inp.value.trim();
    if (!texto) return;
    inp.disabled = true;
    var r = await jpost('/gtd/api/task', { texto: texto, tipo: tipo });
    inp.disabled = false; inp.focus();
    if (!r || !r.ok) { toast('Error al guardar', 'err'); return; }
    var idea = tipo === 'idea';
    tasks.unshift({ id: r.id, title: texto, tipo: tipo, importante: idea ? false : null, urgente: idea ? false : null,
      cuadrante: idea ? 'ideas' : null, completado: false, fecha_completado: null, fecha_limite: null, notas: null });
    inp.value = '';
    render();
    toast(idea ? 'Guardada en Ideas' : 'Al Inbox');
  });

  /* ── Acciones ── */
  async function classify(id, imp, urg) {
    var t = find(id); if (!t) return null;
    var r = await jpost('/gtd/api/task/' + id + '/classify', { importante: imp, urgente: urg });
    if (!r || !r.ok) { toast('No se pudo clasificar', 'err'); return null; }
    t.importante = imp; t.urgente = urg; t.cuadrante = r.cuadrante;
    return r.cuadrante;
  }
  async function complete(id, btn) {
    var t = find(id);
    if (!t || t.completado) return;
    btn.disabled = true; btn.setAttribute('aria-pressed', 'true');
    if (window.euCelebrate) euCelebrate(btn);
    var r = await jpost('/gtd/api/task/' + id + '/complete');
    if (!r || !r.ok) { btn.disabled = false; btn.setAttribute('aria-pressed', 'false'); toast('Error al completar', 'err'); return; }
    t.completado = true; t.fecha_completado = today();
    doneToday = r.stats && r.stats.done_today != null ? r.stats.done_today : doneToday + 1;
    // Una sola moneda (D1): XP. «+N XP» sube desde el botón antes de re-renderizar.
    var xp = (r.xp || 0) + (r.bonus_xp || 0);
    if (window.euGam) euGam(Object.assign({}, r.gam || {}, { xp: xp }), { el: btn, pop: false });
    render();
    toast('+' + (r.xp || 0) + ' XP' + (r.bonus_xp ? ' · bono de 3 tareas +' + r.bonus_xp + ' XP' : ''), 'win');
  }
  /* Estrella = prioridad del día (D3): máx. 3; Acta las muestra y premia */
  async function star(id, btn) {
    var t = find(id); if (!t) return;
    btn.disabled = true;
    var r = await jpost('/gtd/api/task/' + id + '/prioridad');
    btn.disabled = false;
    if (!r || !r.ok) { toast((r && r.error) || 'No se pudo marcar', 'err'); return; }
    t.prioridad_dia = r.prioridad ? today() : null;
    render();
    toast(r.prioridad ? 'Prioridad del día · ' + r.n + '/3' : 'Quitada de prioridades');
  }
  async function del(id) {
    if (!(await euConfirm('¿Eliminar esta tarea?', { confirmLabel: 'Eliminar' }))) return;
    var res = await fetch('/gtd/api/task/' + id, { method: 'DELETE' }).catch(function () { return null; });
    if (!res || !res.ok) { toast('No se pudo eliminar', 'err'); return; }
    tasks = tasks.filter(function (t) { return t.id !== id; });
    render();
  }

  document.getElementById('px').addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b || !root.contains(b)) return;
    var id = b.dataset.id ? parseInt(b.dataset.id, 10) : null;
    if (b.classList.contains('js-done-tg')) { doneOpen = !doneOpen; render(); }
    else if (b.classList.contains('js-done')) complete(id, b);
    else if (b.classList.contains('js-del')) del(id);
    else if (b.classList.contains('js-unclass')) {
      await classify(id, null, null); render(); toast('Movida a Inbox');
    } else if (b.classList.contains('js-star')) {
      star(id, b);
    } else if (b.classList.contains('js-promote')) {
      b.disabled = true;
      if (await classify(id, true, true)) toast('→ Hoy');
      render();
    } else if (b.classList.contains('js-rev')) {
      var q = tasks.filter(function (t) { return !t.completado && t.cuadrante == null; });
      if (!q.length) { toast('Inbox vacío'); return; }
      openReview(q);
    } else if (b.classList.contains('js-dest')) {
      b.disabled = true;
      var c = await classify(id, b.dataset.imp === '1', b.dataset.urg === '1');
      if (c) toast('→ ' + (Q_LABEL[c] || c));
      render();
    }
  });

  /* ── Render ── */
  function ic(name, cls) { return '<i data-lucide="' + name + '"' + (cls ? ' class="' + cls + '"' : '') + '></i>'; }
  /* Fecha límite relativa con tono (praxis-due.js); nunca ISO */
  function dueHTML(t) {
    var d = t.completado ? null : Due.relDue(t.fecha_limite, today());
    return d ? '<span class="eu-badge px-due' + (d.tone ? ' px-due--' + d.tone : '') + '" title="' + esc(t.fecha_limite) + '">' + esc(d.txt) + '</span>' : '';
  }
  function semHTML(t) {
    return t.prioridad_semana && semPrio.indexOf(t.prioridad_semana) >= 0 && !t.completado
      ? '<span class="eu-badge px-sem" title="Prioridad de la semana (elegida en Ataraxia)">' + ic('star') + 'Semana</span>' : '';
  }
  function tipoHTML(t) {
    if (!t.tipo || t.tipo === 'tarea' || (t.tipo === 'idea' && t.cuadrante === 'ideas')) return '';
    var tp = TIPO[t.tipo] || TIPO.tarea;
    return '<span class="eu-badge px-tipo px-tipo--' + esc(t.tipo) + '">' + ic(tp[1]) + tp[0] + '</span>';
  }
  function checkHTML(t) {
    if (t.completado) return '<span class="px-check is-on" aria-hidden="true"><span class="eu-act-check">' + ic('check') + '</span></span>';
    return '<button type="button" class="px-check js-done" data-id="' + t.id + '" aria-pressed="false" aria-label="Completar «' + esc(t.title) + '»"><span class="eu-act-check">' + ic('check') + '</span></button>';
  }
  function delHTML(t) { return '<button type="button" class="eu-iconbtn px-danger js-del" data-id="' + t.id + '" aria-label="Eliminar «' + esc(t.title) + '»">' + ic('trash-2') + '</button>'; }
  function titleHTML(t) {
    return '<div class="px-item-main"><div class="px-item-t' + (t.completado ? ' is-done' : '') + '">' + esc(t.title) + '</div>' +
      (t.notas ? '<div class="t-meta px-notas">' + esc(t.notas) + '</div>' : '') + '</div>';
  }
  function destHTML(t) {
    return '<div class="px-dest" role="group" aria-label="Mandar «' + esc(t.title) + '» a">' + DEST.map(function (d) {
      return '<button type="button" class="px-dest-b js-dest" data-q="' + d.q + '" data-id="' + t.id + '" data-imp="' + d.imp + '" data-urg="' + d.urg + '" title="' + d.tip + '">' +
        ic(d.icon) + d.label + '</button>';
    }).join('') + '</div>';
  }
  /* sec: inbox | hoy | semana | side (Delegar / Ideas) */
  function rowHTML(t, sec) {
    if (sec === 'inbox') return '<li class="px-item px-item--inbox">' + titleHTML(t) + tipoHTML(t) + destHTML(t) + delHTML(t) + '</li>';
    var extra = '';
    if (sec === 'hoy') {
      var on = t.prioridad_dia === today();
      extra = t.completado ? (on ? '<span class="px-star is-on" aria-label="Prioridad del día">' + ic('star') + '</span>' : '') :
        '<button type="button" class="eu-iconbtn px-star js-star' + (on ? ' is-on' : '') + '" data-id="' + t.id + '" aria-pressed="' + on + '" ' +
        'aria-label="' + (on ? 'Quitar «' + esc(t.title) + '» de prioridades' : 'Marcar «' + esc(t.title) + '» como prioridad del día') + '" title="' +
        (on ? 'Quitar de prioridades' : 'Prioridad del día') + '">' + ic('star') + '</button>';
    }
    if (!t.completado) {
      if (sec === 'semana') extra = '<button type="button" class="px-promote js-promote" data-id="' + t.id + '" aria-label="Mover «' + esc(t.title) + '» a Hoy">→ Hoy</button>';
      extra += '<button type="button" class="eu-iconbtn px-ghost js-unclass" data-id="' + t.id + '" aria-label="Regresar «' + esc(t.title) + '» a Inbox" title="Regresar a Inbox">' + ic('undo-2') + '</button>' + delHTML(t);
    }
    return '<li class="px-item' + (sec === 'side' ? ' px-item--sm' : '') + (t.completado ? ' is-done' : '') + '">' + checkHTML(t) + titleHTML(t) + semHTML(t) + tipoHTML(t) + dueHTML(t) + extra + '</li>';
  }
  function empty(icon, title, text) { return window.euEmpty ? euEmpty(icon, title, text || '', true) : '<p class="t-meta px-empty">' + title + '</p>'; }

  function bonusHTML() {
    var n = Math.min(3, doneToday), won = doneToday >= 3, pips = '';
    for (var i = 0; i < 3; i++) pips += '<i' + (i < n ? ' class="is-on"' : '') + '></i>';
    return '<div class="px-bonus' + (won ? ' is-won' : '') + '">' +
      '<div class="px-bonus-t num"><span>' + n + '/3 hechas</span><span>' + (won ? '+5 XP ganados' : 'bono +5 XP') + '</span></div>' +
      '<div class="px-bonus-pips" role="progressbar" aria-label="Bono diario: tareas hechas" aria-valuemin="0" aria-valuemax="3" aria-valuenow="' + n + '">' + pips + '</div></div>';
  }

  function render() {
    var g = { inbox: [], hoy: [], semana: [], delegar: [], ideas: [], done: [] }, td = today();
    tasks.forEach(function (t) {
      if (t.completado) { if (t.fecha_completado === td) g.done.push(t); }
      else if (t.cuadrante == null) g.inbox.push(t);
      else if (g[t.cuadrante]) g[t.cuadrante].push(t);
    });
    ['inbox', 'hoy', 'semana', 'delegar', 'ideas'].forEach(function (k) { g[k].sort(Due.byDue); });
    // Hoy muestra también lo que ya se cerró hoy desde Hoy, tachado al final
    var hoyDone = g.done.filter(function (t) { return t.cuadrante === 'hoy'; });
    var nPrio = tasks.filter(function (t) { return t.prioridad_dia === td; }).length;

    var main = '';
    if (g.inbox.length) {
      main += '<section class="eu-card eu-card--flush px-sec px-sec--inbox" aria-labelledby="px-t-inbox">' +
        '<div class="px-sec-hd">' + ic('inbox', 'px-sec-ic') + '<h2 class="px-sec-n" id="px-t-inbox">Inbox</h2>' +
        '<span class="t-meta px-sec-sub">' + g.inbox.length + ' por decidir · un clic las manda a su lugar</span>' +
        '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm js-rev">' + ic('sparkles') + '<span>Revisión rápida</span></button></div>' +
        '<ul class="px-list">' + g.inbox.map(function (t) { return rowHTML(t, 'inbox'); }).join('') + '</ul>' +
        '<p class="t-meta px-rule">Hoy = urgente e importante · Semana = importante · Delegar = urgente · Idea = ninguno</p></section>';
    }
    main += '<section class="eu-card eu-card--flush px-sec px-sec--hoy" data-tone="danger" aria-labelledby="px-t-hoy">' +
      '<div class="px-hoy-hd"><div class="eu-grow"><h2 class="px-hoy-t" id="px-t-hoy">' + ic('flame') + 'Hoy</h2>' +
      '<div class="t-meta">Urgente e importante · ordenadas por fecha límite</div></div>' + bonusHTML() + '</div>' +
      (g.hoy.length || hoyDone.length ? '<ul class="px-list">' + g.hoy.concat(hoyDone).map(function (t) { return rowHTML(t, 'hoy'); }).join('') + '</ul>'
        : empty('flame', 'Nada urgente', 'Manda aquí desde el Inbox lo urgente e importante.')) +
      '<p class="t-meta px-prio-ft">' + ic('star') + '<span><b>' + nPrio + '/3 prioridades</b> · se muestran en Acta Diurna y dan su bono al completarse</span></p></section>';
    main += '<section class="eu-card eu-card--flush px-sec px-sec--semana" data-tone="info" aria-labelledby="px-t-semana">' +
      '<div class="px-sec-hd">' + ic('calendar', 'px-sec-ic') + '<h2 class="px-sec-n" id="px-t-semana">Esta semana</h2>' +
      '<span class="t-meta px-sec-sub">Importante · agéndalo</span><span class="px-sec-ct num">' + g.semana.length + '</span></div>' +
      (g.semana.length ? '<ul class="px-list">' + g.semana.map(function (t) { return rowHTML(t, 'semana'); }).join('') + '</ul>'
        : empty('calendar', 'Semana despejada')) + '</section>';

    function side(k, label, icon) {
      return '<section class="px-side-sec px-sec" data-tone="' + (k === 'delegar' ? 'warning' : 'brand') + '" aria-labelledby="px-t-' + k + '">' +
        '<div class="px-sec-hd">' + ic(icon, 'px-sec-ic') + '<h2 class="px-sec-n" id="px-t-' + k + '">' + label + '</h2><span class="px-sec-ct num">' + g[k].length + '</span></div>' +
        (g[k].length ? '<ul class="px-list">' + g[k].map(function (t) { return rowHTML(t, 'side'); }).join('') + '</ul>'
          : '<p class="t-meta px-side-empty">' + (k === 'delegar' ? 'Nada que delegar.' : 'Sin ideas guardadas.') + '</p>') +
        (k === 'ideas' ? '<p class="t-meta px-side-note">Un solo banco: el Pipeline de Acta Diurna guarda aquí.</p>' : '') + '</section>';
    }
    var aside = side('delegar', 'Delegar', 'users') + side('ideas', 'Ideas', 'lightbulb') +
      '<section class="px-side-sec px-done" data-tone="success">' +
        '<button type="button" class="px-done-tg js-done-tg" aria-expanded="' + doneOpen + '">' + ic('circle-check', 'px-sec-ic') +
          '<span>Completadas hoy</span><span class="px-sec-ct num">' + g.done.length + '</span>' + ic('chevron-down', 'px-chev') + '</button>' +
        (doneOpen ? (g.done.length ? '<ul class="px-list">' + g.done.map(function (t) { return rowHTML(t, 'side'); }).join('') + '</ul>'
          : '<p class="t-meta px-side-empty">Aún nada hoy.</p>') : '') +
        '<a class="t-meta px-done-link" href="/logros?tab=historial&fuente=Praxis">Historial completo en Logros →</a></section>';

    root.innerHTML = '<div class="px-main">' + main + '</div><aside class="px-side" aria-label="Delegar, ideas y completadas">' + aside + '</aside>';
    document.querySelectorAll('.js-mt-inbox').forEach(function (el) { el.textContent = g.inbox.length; });
    if (window.lucide) lucide.createIcons();
  }

  /* ── Revisión rápida (modal): vaciar el Inbox en lote ── */
  var rev = { q: [], i: 0, imp: null, urg: null };
  function openReview(q) {
    rev = { q: q, i: 0, imp: null, urg: null };
    showRev();
    euModal.open('px-rev');
  }
  function showRev() {
    if (rev.i >= rev.q.length) {
      euModal.close('px-rev');
      toast('Revisión completa');
      render(); return;
    }
    var t = rev.q[rev.i];
    document.getElementById('rev-ctr').textContent = (rev.i + 1) + ' de ' + rev.q.length;
    document.getElementById('rev-txt').textContent = t.title;
    rev.imp = rev.urg = null;
    document.querySelectorAll('[data-rev]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
  }
  document.querySelectorAll('[data-rev]').forEach(function (b) {
    b.addEventListener('click', async function () {
      var v = b.dataset.val === '1';
      if (b.dataset.rev === 'importante') rev.imp = v; else rev.urg = v;
      document.querySelectorAll('[data-rev="' + b.dataset.rev + '"]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      if (rev.imp != null && rev.urg != null) {
        await classify(rev.q[rev.i].id, rev.imp, rev.urg);
        await new Promise(function (r) { setTimeout(r, 180); });
        rev.i++; showRev(); render();
      }
    });
  });
  document.getElementById('rev-skip').addEventListener('click', function () { rev.i++; showRev(); });

  render();
  document.getElementById('qi').addEventListener('keydown', function (e) { if (e.key === 'Escape') e.target.blur(); });
})();
