/* Praxis (GTD) — Design System V2.
   Captura → Inbox → clasificación Eisenhower (importante × urgente) →
   cuadrantes Hoy / Esta semana / Delegar / Ideas → completar (+pts). */
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
  var open = { inbox: true, hoy: true, semana: true, delegar: true, ideas: true, done: false };

  var SECS = [
    { key: 'inbox', label: 'Inbox', sub: 'Sin clasificar', icon: 'inbox', tone: '' },
    { key: 'hoy', label: 'Hoy', sub: 'Urgente e importante', icon: 'flame', tone: 'danger' },
    { key: 'semana', label: 'Esta semana', sub: 'Importante · agéndalo', icon: 'calendar', tone: 'info' },
    { key: 'delegar', label: 'Delegar', sub: 'Urgente sin impacto', icon: 'users', tone: 'warning' },
    { key: 'ideas', label: 'Banco de ideas', sub: 'Ni urgente ni importante', icon: 'lightbulb', tone: 'brand' },
    { key: 'done', label: 'Completadas', sub: 'Últimas 40', icon: 'check-circle-2', tone: 'success' }
  ];
  var Q_LABEL = { hoy: 'Hoy', semana: 'Esta semana', delegar: 'Delegar', ideas: 'Ideas' };
  var TIPO = { tarea: ['Tarea', 'pin'], idea: ['Idea', 'lightbulb'], mantenimiento: ['Mantenimiento', 'wrench'] };

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  /* Fecha del servidor (zona de la app), no la del navegador */
  function today() { return root.dataset.today; }
  function jpost(url, body) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }).then(function (r) { return r.json(); }).catch(function () { return null; }); }

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
    var t = { id: r.id, title: texto, tipo: tipo, importante: idea ? false : null, urgente: idea ? false : null,
      cuadrante: idea ? 'ideas' : null, completado: false, fecha_completado: null, fecha_limite: null, notas: null };
    tasks.unshift(t);
    inp.value = '';
    open[idea ? 'ideas' : 'inbox'] = true;
    render();
    if (idea) toast('Guardada en Banco de ideas');
    else openReview([t], true);  /* se clasifica al momento en vez de quedar flotando */
  });

  /* ── Acciones ── */
  async function classify(id, imp, urg) {
    var t = tasks.find(function (x) { return x.id === id; }); if (!t) return;
    var r = await jpost('/gtd/api/task/' + id + '/classify', { importante: imp, urgente: urg });
    if (!r || !r.ok) { toast('No se pudo clasificar', 'err'); return null; }
    t.importante = imp; t.urgente = urg; t.cuadrante = r.cuadrante;
    if (r.cuadrante) open[r.cuadrante] = true;
    return r.cuadrante;
  }
  async function complete(id, btn) {
    var t = tasks.find(function (x) { return x.id === id; });
    if (!t || t.completado) return;
    btn.disabled = true; btn.setAttribute('aria-pressed', 'true');
    if (window.euCelebrate) euCelebrate(btn);
    var r = await jpost('/gtd/api/task/' + id + '/complete');
    if (!r || !r.ok) { btn.disabled = false; btn.setAttribute('aria-pressed', 'false'); toast('Error al completar', 'err'); return; }
    t.completado = true; t.fecha_completado = today();
    render();
    toast('+' + r.pts + ' pts' + (r.bonus ? ' · bonus +' + r.bonus : ''), 'win');
    if (window.euAnnounceAchievements) euAnnounceAchievements(r.gam);
  }
  async function del(id) {
    if (!(await euConfirm('¿Eliminar esta tarea?', { confirmLabel: 'Eliminar' }))) return;
    var res = await fetch('/gtd/api/task/' + id, { method: 'DELETE' }).catch(function () { return null; });
    if (!res || !res.ok) { toast('No se pudo eliminar', 'err'); return; }
    tasks = tasks.filter(function (t) { return t.id !== id; });
    render();
  }

  root.addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var id = b.dataset.id ? parseInt(b.dataset.id, 10) : null;
    if (b.dataset.sec) { open[b.dataset.sec] = !open[b.dataset.sec]; render(); }
    else if (b.classList.contains('js-done')) complete(id, b);
    else if (b.classList.contains('js-del')) del(id);
    else if (b.classList.contains('js-unclass')) {
      await classify(id, null, null); open.inbox = true; render(); toast('Movida a Inbox');
    } else if (b.classList.contains('js-rev')) {
      var q = tasks.filter(function (t) { return !t.completado && t.cuadrante == null; });
      if (!q.length) { toast('Inbox vacío'); return; }
      openReview(q, false);
    } else if (b.dataset.cls) {
      var t = tasks.find(function (x) { return x.id === id; });
      t[b.dataset.cls] = b.dataset.val === '1';
      if (t.importante != null && t.urgente != null) {
        var c = await classify(id, t.importante, t.urgente);
        if (c) toast('→ ' + (Q_LABEL[c] || c));
      }
      render();
    }
  });

  /* ── Render ── */
  function metaHTML(t) {
    var tp = TIPO[t.tipo] || TIPO.tarea;
    return '<div class="px-meta">' +
      (t.fecha_limite ? '<span class="eu-badge"><i data-lucide="calendar"></i>' + esc(t.fecha_limite) + '</span>' : '') +
      '<span class="eu-badge px-tipo px-tipo--' + esc(t.tipo || 'tarea') + '"><i data-lucide="' + tp[1] + '"></i>' + tp[0] + '</span></div>';
  }
  function segHTML(t, campo, label) {
    var v = t[campo];
    return '<div class="px-cls-q"><span class="t-meta">' + label + '</span><div class="eu-seg">' +
      '<button type="button" data-id="' + t.id + '" data-cls="' + campo + '" data-val="1" aria-pressed="' + (v === true) + '">Sí</button>' +
      '<button type="button" data-id="' + t.id + '" data-cls="' + campo + '" data-val="0" aria-pressed="' + (v === false) + '">No</button></div></div>';
  }
  function itemHTML(t, sec) {
    var main = '<div class="px-item-main"><div class="px-item-t' + (sec === 'done' ? ' is-done' : '') + '">' + esc(t.title) + '</div>' +
      (t.notas ? '<div class="t-meta px-notas">' + esc(t.notas) + '</div>' : '') +
      (sec === 'done' ? (t.fecha_completado ? '<div class="t-meta">Completada ' + esc(t.fecha_completado) + '</div>' : '') : metaHTML(t)) + '</div>';
    var delBtn = '<button type="button" class="eu-iconbtn px-danger js-del" data-id="' + t.id + '" aria-label="Eliminar «' + esc(t.title) + '»"><i data-lucide="trash-2"></i></button>';
    if (sec === 'inbox') {
      return '<li class="px-item px-item--inbox">' + main + '<div class="px-cls">' + segHTML(t, 'importante', '¿Importante?') + segHTML(t, 'urgente', '¿Urgente?') + '</div>' + delBtn + '</li>';
    }
    if (sec === 'done') {
      return '<li class="px-item"><span class="px-check is-on" aria-hidden="true"><span class="eu-act-check"><i data-lucide="check"></i></span></span>' + main + delBtn + '</li>';
    }
    return '<li class="px-item"><button type="button" class="px-check js-done" data-id="' + t.id + '" aria-pressed="false" aria-label="Completar «' + esc(t.title) + '»"><span class="eu-act-check"><i data-lucide="check"></i></span></button>' + main +
      '<button type="button" class="eu-iconbtn js-unclass" data-id="' + t.id + '" aria-label="Regresar a Inbox"><i data-lucide="undo-2"></i></button>' + delBtn + '</li>';
  }
  function render() {
    var groups = { inbox: [], hoy: [], semana: [], delegar: [], ideas: [], done: [] };
    tasks.forEach(function (t) {
      if (t.completado) groups.done.push(t);
      else if (t.cuadrante == null) groups.inbox.push(t);
      else if (groups[t.cuadrante]) groups[t.cuadrante].push(t);
    });
    groups.done = groups.done.slice(0, 40);
    root.innerHTML = SECS.map(function (s) {
      var items = groups[s.key], isOpen = open[s.key];
      return '<section class="eu-card eu-card--flush px-sec px-sec--' + s.key + '"' + (s.tone ? ' data-tone="' + s.tone + '"' : '') + '>' +
        '<div class="px-sec-hd">' +
          '<button type="button" class="px-sec-tg" data-sec="' + s.key + '" aria-expanded="' + isOpen + '">' +
            '<span class="eu-row-ic px-sec-ic"><i data-lucide="' + s.icon + '"></i></span>' +
            '<span class="px-sec-tt"><span class="t-card">' + s.label + '</span><span class="t-meta">' + s.sub + '</span></span>' +
            (items.length && s.key !== 'done' ? '<span class="eu-badge eu-badge--status px-count">' + items.length + '</span>' : '') +
            '<i data-lucide="chevron-down" class="px-chev"></i></button>' +
          (s.key === 'inbox' && items.length ? '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm js-rev"><i data-lucide="sparkles"></i>Revisión rápida</button>' : '') +
        '</div>' +
        (isOpen ? (items.length ? '<ul class="px-list">' + items.map(function (t) { return itemHTML(t, s.key); }).join('') + '</ul>'
          : '<p class="t-meta px-empty">' + (s.key === 'done' ? 'Aún sin completadas.' : s.key === 'inbox' ? 'Inbox en cero. Todo está decidido.' : 'Nada aquí.') + '</p>') : '') +
        '</section>';
    }).join('');
    document.getElementById('st-inbox').textContent = groups.inbox.length;
    document.getElementById('st-hoy').textContent = groups.hoy.length;
    var td = today();
    document.getElementById('st-done').textContent = tasks.filter(function (t) { return t.completado && t.fecha_completado === td; }).length;
    if (window.lucide) lucide.createIcons();
  }

  /* ── Revisión rápida (modal) ── */
  var rev = { q: [], i: 0, imp: null, urg: null, single: false };
  function openReview(q, single) {
    rev = { q: q, i: 0, imp: null, urg: null, single: single };
    showRev();
    euModal.open('px-rev');
  }
  function showRev() {
    if (rev.i >= rev.q.length) {
      euModal.close('px-rev');
      if (!rev.single) toast('Revisión completa');
      render(); return;
    }
    var t = rev.q[rev.i];
    document.getElementById('px-rev-t').textContent = rev.single ? '¿A dónde va?' : 'Revisión rápida';
    document.getElementById('rev-ctr').textContent = rev.single ? 'Clasifícala ahora o déjala en Inbox' : (rev.i + 1) + ' de ' + rev.q.length;
    document.getElementById('rev-txt').textContent = t.title;
    document.getElementById('rev-skip').textContent = rev.single ? 'Dejar en Inbox' : 'Saltar';
    rev.imp = rev.urg = null;
    document.querySelectorAll('[data-rev]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
  }
  document.querySelectorAll('[data-rev]').forEach(function (b) {
    b.addEventListener('click', async function () {
      var v = b.dataset.val === '1';
      if (b.dataset.rev === 'importante') rev.imp = v; else rev.urg = v;
      document.querySelectorAll('[data-rev="' + b.dataset.rev + '"]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      if (rev.imp != null && rev.urg != null) {
        var c = await classify(rev.q[rev.i].id, rev.imp, rev.urg);
        if (c && rev.single) toast('→ ' + (Q_LABEL[c] || c));
        await new Promise(function (r) { setTimeout(r, 180); });
        rev.i++; showRev(); render();
      }
    });
  });
  document.getElementById('rev-skip').addEventListener('click', function () { rev.i++; showRev(); });

  /* Estado inicial: Inbox colapsado si está vacío */
  if (!tasks.some(function (t) { return !t.completado && t.cuadrante == null; })) open.inbox = false;
  render();
  document.getElementById('qi').addEventListener('keydown', function (e) { if (e.key === 'Escape') e.target.blur(); });
})();
