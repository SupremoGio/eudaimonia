/* Acta Diurna (/actividades/) — interacciones. Antes vivía inline en
   actividades/index.html. Endpoints (sin cambios):
     POST   /actividades/api/activity/log        {key}         marcar / desmarcar
     POST   /actividades/api/reflexion           {key, texto}  reflexión (auto-marca)
     POST   /actividades/api/activity/create     {...}         nueva actividad
     DELETE /actividades/api/activity/<key>                    quitar del checklist
     POST   /actividades/api/pillar-focus        {pillar, focus_key}
     POST   /actividades/api/priority            {text}   ·  POST /api/priority/<id>/toggle
     POST   /actividades/api/pipeline            {text}   ·  DELETE /api/pipeline/<id>
     GET    /actividades/api/quote/refresh?cat=stoic|motivational */
(function () {
  'use strict';
  var root = document.getElementById('acta');
  if (!root) return;

  var GOAL = parseInt(root.dataset.goal, 10) || 15;
  var PILLARS_TOTAL = parseInt(root.dataset.pillarsTotal, 10) || 8;
  var RANKS = ['carbon', 'iron', 'gold', 'diamond'];
  var TIER_T = { carbon: 'carbon', iron: 'hierro', gold: 'oro', diamond: 'diamante' };
  var clfRank = root.dataset.rank;
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return [].slice.call((el || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function icons() { try { lucide.createIcons(); } catch (e) {} }
  function post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
  }
  var channel = ('BroadcastChannel' in window) ? new BroadcastChannel('eudaimonia') : null;
  function notifyDashboard() { if (channel) channel.postMessage({ type: 'data_changed' }); }

  // ── Estado hecho/pendiente: todas las copias de un key (varias sesiones y
  //    las dos vistas) se mantienen sincronizadas ─────────────────────────────
  function isDone(key) {
    var el = $('.acta-item[data-key="' + key + '"]');
    return !!el && el.dataset.done === '1';
  }
  function setDone(key, done) {
    $$('.acta-item[data-key="' + key + '"]').forEach(function (it) {
      it.dataset.done = done ? '1' : '0';
      var b = $('.js-act', it); if (b) b.setAttribute('aria-pressed', done ? 'true' : 'false');
    });
    recount();
  }
  $$('.acta-item').forEach(function (it) {
    var b = $('.eu-act', it);
    it.dataset.done = (b && (b.getAttribute('aria-pressed') === 'true' || b.classList.contains('is-done'))) ? '1' : '0';
  });

  function recount() {
    var seen = {}, all = 0, done = 0, ancla = 0;
    $$('.acta-virtues .acta-item, .acta-weekend .acta-item').forEach(function (it) {
      if (seen[it.dataset.key]) return;
      seen[it.dataset.key] = 1; all++;
      if (it.dataset.done === '1') done++;
      if (it.classList.contains('is-ancla')) ancla++;
    });
    var set = function (sel, v) { $$(sel).forEach(function (el) { el.textContent = v; }); };
    set('.js-ct-all', all); set('.js-ct-done', done); set('.js-ct-pending', all - done); set('.js-ct-ancla', ancla);
    set('.js-done-n', done);
    $$('.acta-pillar').forEach(function (p) {
      var items = $$('.acta-item', p), d = items.filter(function (i) { return i.dataset.done === '1'; });
      var xp = d.reduce(function (s, i) { return s + (parseInt(i.dataset.pts, 10) || 0); }, 0);
      var c = $('.js-pcount', p); if (c) c.textContent = d.length + '/' + items.length;
      var x = $('.js-pxp', p); if (x) x.textContent = '+' + xp + ' XP';
    });
    $$('.acta-session').forEach(function (s) {
      var items = $$('.acta-item', s), d = items.filter(function (i) { return i.dataset.done === '1'; });
      var c = $('summary .num', s); if (c) c.textContent = d.length + '/' + items.length;
    });
    updWeekend();
  }

  function updWeekend() {
    var wk = $('.acta-weekend'); if (!wk) return;
    var req = $$('.acta-item', wk).filter(function (i) { return !i.dataset.optional; });
    var d = req.filter(function (i) { return i.dataset.done === '1'; }).length;
    var c = $('.js-wk-count', wk); if (c) c.textContent = d + ' / ' + req.length;
    var bar = $('.js-wk-bar', wk); if (bar) bar.style.width = (req.length ? Math.round(d / req.length * 100) : 0) + '%';
    var badge = $('.js-wk-done', wk); if (badge) badge.hidden = !(req.length && d === req.length);
  }

  // ── Stats del servidor ────────────────────────────────────────────────────
  function updS(s) {
    if (!s) return;
    var xp = s.xp_today != null ? s.xp_today : (s.pts_today || 0);
    $$('.js-xp-today').forEach(function (el) { if (window.euCountTo) euCountTo(el, xp); else el.textContent = xp; });
    $$('.js-xp-bar').forEach(function (el) {
      el.style.width = Math.min(100, xp / GOAL * 100) + '%';
      var bar = el.parentNode; bar.setAttribute('aria-valuenow', xp);
      if (!reduced) { bar.classList.remove('is-gaining'); void bar.offsetWidth; bar.classList.add('is-gaining'); }
    });
    var t = function (sel, v) { var el = $(sel); if (el && v != null) el.textContent = v; };
    t('.js-xp-week', s.xp_week != null ? s.xp_week : s.pts_week);
    t('.js-xp-month', s.xp_month != null ? s.xp_month : s.pts_month);
    t('.js-ec-total', Math.max(0, s.ec_total || 0));
    var st = s.streak || 0;
    t('.js-streak', st + ' d');
    t('.js-streak-sub', st >= 30 ? 'Racha · +10% XP' : st >= 7 ? 'Racha · +5% XP' : st >= 5 ? (7 - st) + ' d para bono' : (5 - st) + ' d para racha');
  }

  function updGam(g) {
    if (!g) return;
    var clf = g.classification;
    if (clf) {
      var badge = $('.js-clf-badge'); if (badge) badge.dataset.t = TIER_T[clf.rank] || 'carbon';
      var t = function (sel, v) { var el = $(sel); if (el) el.textContent = v || ''; };
      t('.js-clf-label', clf.label); t('.js-clf-desc', clf.desc); t('.js-clf-hint', clf.next_hint);
      var parts = [];
      if (clf.anchors_total > 0) parts.push('Anclas ' + clf.anchors_done + '/' + clf.anchors_total);
      if (clf.touches_total > 0) parts.push('Touches ' + clf.touches_done + '/' + clf.touches_total);
      t('.js-clf-meta', parts.join(' · '));
      var track = $('.js-clf-track'); if (track) track.hidden = clf.rank === 'diamond';
      var bar = $('.js-clf-bar'); if (bar) bar.style.width = (clf.next_pct || 0) + '%';
      // Subir de clasificación es el logro central del día: festejo propio
      if (clfRank && clf.rank !== clfRank && RANKS.indexOf(clf.rank) > RANKS.indexOf(clfRank) && window.euRewardSheet) {
        euRewardSheet({ icon: clf.icon_lucide || 'trophy', eyebrow: 'Subiste de clasificación', title: clf.label, desc: clf.desc || '', burst: false });
      }
      clfRank = clf.rank;
      if (clf.pillars) {
        var on = {}; clf.pillars.forEach(function (p) { on[p] = 1; });
        $$('.acta-cover-it').forEach(function (it) { it.classList.toggle('is-on', !!on[it.dataset.pillar]); });
        $$('.js-pillars-n').forEach(function (el) { el.textContent = clf.pillars.length; });
        $$('.js-pillars-count').forEach(function (el) { el.textContent = clf.pillars.length + ' / ' + PILLARS_TOTAL; });
      }
    }
    if (g.coins_today != null) $$('.js-ec-today').forEach(function (el) { el.textContent = g.coins_today; });
    var lb = $('.js-lvl-bar'); if (lb && g.level_pct != null) lb.style.width = g.level_pct + '%';
    var ln = $('.js-lvl-name'); if (ln && g.level_name) ln.textContent = g.level_name.charAt(0) + g.level_name.slice(1).toLowerCase();
    var nx = $('.js-lvl-next'); if (nx) nx.textContent = g.max_level ? 'nivel máximo' : (g.xp_to_next || 0) + ' XP para subir';
    if (window.euCheckLevel) euCheckLevel(g);
  }

  function afterGam(d) {
    var gam = d.gam || {};
    updS(d.stats); updGam(gam.stats);
    if (gam.combo_bonuses && gam.combo_bonuses.length) {
      toast(gam.combo_bonuses.map(function (c) { return 'Combo ' + c.label + ' +' + c.xp + ' XP'; }).join(' · '), 'win');
    }
    if (gam.perfect_day && window.euPerfectDay) euPerfectDay(gam.perfect_day);
    // Logros e insignias: sello + halo (eu-motion.js), uno tras otro.
    if (window.euAnnounceAchievements) euAnnounceAchievements(gam);
    icons(); notifyDashboard();
    if (window.euRefreshXp) euRefreshXp();
  }

  // ── Coreografía de «marcar» (eu-motion.js): check con settle 220 ms +
  //    «+N XP» que sube 600 ms; la barra y el contador los anima updS().
  function celebrate(btn, xp) {
    if (btn && window.euXpGain) euXpGain({ el: btn, xp: parseInt(xp, 10) || 0 });
  }

  // ── Toast con Deshacer (5 s) ─────────────────────────────────────────────
  var tEl = $('.js-toast'), tMsg = $('.js-toast-msg'), undoKey = null, tTimer = null;
  function showUndo(html, key) {
    if (!tEl) return;
    undoKey = key;
    tMsg.innerHTML = html;
    tEl.hidden = false;
    tEl.classList.remove('is-running'); void tEl.offsetWidth; tEl.classList.add('is-running');
    icons();
    clearTimeout(tTimer);
    tTimer = setTimeout(hideUndo, 5000);
  }
  function hideUndo() { if (tEl) { tEl.hidden = true; tEl.classList.remove('is-running'); } undoKey = null; }
  function undo() {
    if (!undoKey) return;
    var key = undoKey; hideUndo();
    logAct(key, null, true);
  }
  var undoBtn = $('.js-undo'); if (undoBtn) undoBtn.addEventListener('click', undo);

  // ── Marcar / desmarcar ───────────────────────────────────────────────────
  var pending = {};
  function labelOf(key) { var l = $('.acta-item[data-key="' + key + '"] .acta-lbl'); return l ? l.textContent.trim() : ''; }

  function logAct(key, btn, isUndo) {
    if (pending[key]) return Promise.resolve();
    var wasDone = isDone(key);
    var item = $('.acta-item[data-key="' + key + '"]');
    // Si hay una reflexión guardándose (blur de ese mismo click), se espera:
    // puede haber auto-marcado ya la actividad y no hay que deshacerlo.
    var ta = item && $('.js-reflect', item);
    var wait = ta && ta._pendingSave ? ta._pendingSave.catch(function () {}) : Promise.resolve();
    return wait.then(function () {
      if (ta && ta._wasAutoChecked && !wasDone && isDone(key)) { ta._wasAutoChecked = false; return; }
      wasDone = isDone(key);
      pending[key] = true;
      setDone(key, !wasDone);
      $$('.acta-item[data-key="' + key + '"] .js-act').forEach(function (b) { b.setAttribute('aria-busy', 'true'); });
      if (!wasDone) celebrate(btn || $('.acta-item[data-key="' + key + '"] .js-act'), item ? item.dataset.pts : 0);
      return post('/actividades/api/activity/log', { key: key }).then(function (d) {
        if (d.action === 'added') {
          showUndo(esc(labelOf(key)) + ' · <span class="fg-xp num">+' + (d.xp != null ? d.xp : d.pts) + ' XP</span>' +
                   (d.ec > 0 ? ' <span class="fg-ec num">+' + d.ec + ' EC</span>' : ''), key);
        } else if (!isUndo) {
          hideUndo(); toast('Removido');
        } else {
          toast('Deshecho');
        }
        afterGam(d);
        if (d.one_time) setTimeout(function () { $$('.acta-item[data-key="' + key + '"]').forEach(function (i) { i.remove(); }); recount(); }, 700);
      }).catch(function () {
        setDone(key, wasDone);
        toast('No se pudo registrar', 'err');
      }).then(function () {
        delete pending[key];
        $$('.acta-item[data-key="' + key + '"] .js-act').forEach(function (b) { b.removeAttribute('aria-busy'); });
      });
    });
  }

  root.addEventListener('click', function (e) {
    var b = e.target.closest('.js-act');
    if (b && root.contains(b)) { logAct(b.dataset.key, b); return; }
    var rm = e.target.closest('.js-rm');
    if (rm) { removeActivity(rm.dataset.key); return; }
    var add = e.target.closest('.js-add');
    if (add) { openAdd(add.dataset.session); return; }
  });

  // ── Reflexiones (MIT, gratitud…) ─────────────────────────────────────────
  $$('.js-reflect').forEach(function (ta) {
    ta.addEventListener('blur', function () {
      var p = post('/actividades/api/reflexion', { key: ta.dataset.key, texto: ta.value }).then(function (d) {
        if (d.auto_checked) {
          ta._wasAutoChecked = true;
          setDone(ta.dataset.key, true);
          celebrate($('.js-act', ta.closest('.acta-item')), 0);
          toast('+' + ((d.gam && d.gam.xp) || '') + ' XP registrado desde tu reflexión', 'win');
          afterGam({ stats: d.stats, gam: d.gam });
        } else {
          updS(d.stats); if (d.gam && d.gam.stats) updGam(d.gam.stats);
        }
      }).catch(function () { toast('No se pudo guardar la reflexión', 'err'); });
      ta._pendingSave = p;
      p.then(function () { if (ta._pendingSave === p) delete ta._pendingSave; });
    });
  });

  // ── Modo edición: quitar y agregar ───────────────────────────────────────
  var editBtn = $('.js-edit'), editBar = $('.acta-editbar');
  if (editBtn) editBtn.addEventListener('click', function () {
    var on = root.classList.toggle('is-editing');
    editBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    $('span', editBtn).textContent = on ? 'Listo' : 'Editar';
    if (editBar) editBar.hidden = !on;
  });

  function removeActivity(key) {
    if (!confirm('¿Quitar «' + labelOf(key) + '» de tu checklist?')) return;
    fetch('/actividades/api/activity/' + encodeURIComponent(key), { method: 'DELETE' }).then(function (r) {
      if (!r.ok) throw new Error();
      $$('.acta-item[data-key="' + key + '"]').forEach(function (i) { i.remove(); });
      recount(); toast('Actividad quitada');
    }).catch(function () { toast('No se pudo quitar', 'err'); });
  }

  var addForm = $('.js-add-form');
  function openAdd(session) {
    if (!addForm) return;
    addForm.reset();
    if (session) $('#f-session').value = session;
    $('.js-days').hidden = true;
    euModal.open('acta-add');
  }
  if (addForm) {
    $('#f-freq').addEventListener('change', function (e) { $('.js-days').hidden = e.target.value !== 'days'; });
    addForm.addEventListener('submit', function (e) { e.preventDefault(); saveAdd(); });
    $('.js-add-save').addEventListener('click', saveAdd);
  }
  function saveAdd() {
    var label = $('#f-label').value.trim();
    if (!label) { $('#f-label').focus(); return; }
    var freq = $('#f-freq').value, days = null;
    if (freq === 'days') {
      days = $$('.js-day:checked').map(function (c) { return c.value; });
      if (!days.length) { toast('Elige al menos un día', 'err'); return; }
    }
    var save = $('.js-add-save'); save.setAttribute('aria-busy', 'true');
    post('/actividades/api/activity/create', {
      label: label, pillar: $('#f-pillar').value, type: $('#f-type').value, session: $('#f-session').value,
      pts: parseInt($('#f-pts').value, 10) || 1, ec: parseInt($('#f-ec').value, 10) || 0,
      one_time: freq === 'once', days_of_week: days,
    }).then(function (d) {
      if (d.error) { toast(d.error, 'err'); save.removeAttribute('aria-busy'); return; }
      location.reload();
    }).catch(function () { toast('No se pudo crear', 'err'); save.removeAttribute('aria-busy'); });
  }

  // ── Foco del mes ─────────────────────────────────────────────────────────
  $$('.js-foco').forEach(function (sel) {
    sel.addEventListener('change', function () {
      post('/actividades/api/pillar-focus', { pillar: sel.dataset.pillar, focus_key: sel.value || null })
        .then(function () { location.reload(); })
        .catch(function () { toast('No se pudo cambiar el foco', 'err'); });
    });
  });

  // ── Vista (por virtud / por sesión) y filtros ────────────────────────────
  function setView(v) {
    $$('.eu-seg [data-view]').forEach(function (b) { b.setAttribute('aria-selected', b.dataset.view === v ? 'true' : 'false'); });
    $$('[data-view-panel]').forEach(function (p) { p.hidden = p.dataset.viewPanel !== v; });
    try { localStorage.setItem('acta-view', v); } catch (e) {}
  }
  $$('.eu-seg [data-view]').forEach(function (b) { b.addEventListener('click', function () { setView(b.dataset.view); }); });
  var savedView = null; try { savedView = localStorage.getItem('acta-view'); } catch (e) {}
  if (savedView === 'session') setView('session');

  root.dataset.filter = 'all';
  $$('[data-filter]').forEach(function (c) {
    if (c === root) return;
    c.addEventListener('click', function () {
      root.dataset.filter = c.dataset.filter;
      $$('.acta-filters [data-filter]').forEach(function (x) { x.setAttribute('aria-pressed', x === c ? 'true' : 'false'); });
    });
  });

  // ── Prioridades ──────────────────────────────────────────────────────────
  var pList = $('.js-prio-list');
  function renderP(ps) {
    pList.innerHTML = ps.map(function (p) {
      return '<button type="button" class="eu-act acta-prio-it js-prio" aria-pressed="' + (!!p.done) + '" data-id="' + p.id + '">' +
             '<span class="eu-act-check"><i data-lucide="check"></i></span><span class="eu-act-t">' + esc(p.text) + '</span></button>';
    }).join('');
    $('.js-prio-empty').hidden = ps.length > 0;
    $('.js-prio-bonus').hidden = !(ps.length === 3 && ps.every(function (p) { return p.done; }));
    icons();
  }
  var pForm = $('.js-prio-form');
  if (pForm) pForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var inp = $('#p-inp'), text = inp.value.trim(); if (!text) return;
    post('/actividades/api/priority', { text: text }).then(function (d) {
      if (d.error) { toast(d.error, 'err'); return; }
      renderP(d.priorities); inp.value = '';
    }).catch(function () { toast('Sin conexión', 'err'); });
  });
  if (pList) pList.addEventListener('click', function (e) {
    var b = e.target.closest('.js-prio'); if (!b) return;
    post('/actividades/api/priority/' + b.dataset.id + '/toggle').then(function (d) {
      renderP(d.priorities);
      if (d.all3) toast('Bono +5 XP · +5 EC', 'win');
      updS(d.stats); updGam(d.gam && d.gam.stats); notifyDashboard();
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  // ── Pipeline ─────────────────────────────────────────────────────────────
  var chips = $('.js-pipe-list');
  function renderChips(items) {
    chips.innerHTML = items.map(function (i) {
      return '<span class="eu-chip acta-pipe-chip" data-id="' + i.id + '">' + esc(i.text) +
             '<button type="button" class="acta-chip-x js-pipe-del" data-id="' + i.id + '" aria-label="Quitar «' + esc(i.text) + '» del pipeline"><i data-lucide="x"></i></button></span>';
    }).join('');
    $('.js-pipe-empty').hidden = items.length > 0;
    icons();
  }
  var pipeForm = $('.js-pipe-form');
  if (pipeForm) pipeForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var inp = $('#pipe-inp'), text = inp.value.trim(); if (!text) return;
    post('/actividades/api/pipeline', { text: text }).then(function (d) { renderChips(d.items || []); inp.value = ''; })
      .catch(function () { toast('Sin conexión', 'err'); });
  });
  if (chips) chips.addEventListener('click', function (e) {
    var b = e.target.closest('.js-pipe-del'); if (!b) return;
    b.closest('.acta-pipe-chip').remove();
    $('.js-pipe-empty').hidden = !!$('.acta-pipe-chip', chips);
    fetch('/actividades/api/pipeline/' + b.dataset.id, { method: 'DELETE' }).catch(function () {});
  });

  // ── Citas ────────────────────────────────────────────────────────────────
  $$('.js-quote').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var card = btn.closest('.acta-quote');
      btn.classList.add('is-spinning'); card.classList.add('is-swapping');
      fetch('/actividades/api/quote/refresh?cat=' + btn.dataset.kind).then(function (r) { return r.json(); }).then(function (q) {
        setTimeout(function () {
          $('.js-q-text', card).textContent = '«' + q.text + '»';
          $('.js-q-author', card).textContent = q.author;
          card.classList.remove('is-swapping');
        }, reduced ? 0 : 200);
      }).catch(function () { card.classList.remove('is-swapping'); })
        .then(function () { btn.classList.remove('is-spinning'); });
    });
  });

  // ── Atajos: 1–9 marca la n-ésima actividad visible · Ctrl/⌘+Z deshace ──
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (t && (/INPUT|TEXTAREA|SELECT/.test(t.tagName) || t.isContentEditable)) return;
    if (document.querySelector('.eu-scrim:not([hidden]), .eu-cmdk-scrim:not([hidden])')) return;
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key.toLowerCase() === 'z') {
      if (undoKey) { e.preventDefault(); undo(); }
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (/^[1-9]$/.test(e.key)) {
      var panel = $('[data-view-panel]:not([hidden])');
      var btns = $$('.js-act', panel).filter(function (b) { return b.offsetParent !== null; });
      var b = btns[parseInt(e.key, 10) - 1];
      if (b) { e.preventDefault(); b.focus(); logAct(b.dataset.key, b); }
    }
  });

  // ── Entrada: el XP de hoy cuenta hacia arriba (una vez) ──────────────────
  var cu = $('.js-countup');
  if (cu && !reduced) {
    var target = parseInt(cu.textContent, 10) || 0;
    if (target > 0) {
      var t0 = performance.now(), dur = 600;
      cu.textContent = '0';
      requestAnimationFrame(function step(t) {
        var p = Math.min(1, (t - t0) / dur);
        cu.textContent = Math.round((1 - Math.pow(1 - p, 3)) * target);
        if (p < 1) requestAnimationFrame(step);
      });
    }
  }

  // Cambio de día: recarga exacta en la siguiente medianoche local
  (function () {
    var now = new Date();
    var midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    setTimeout(function () { location.reload(); }, midnight - now + 500);
  })();

  recount();
})();
