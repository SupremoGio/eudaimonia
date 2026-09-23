/* EUDAIMONIA — Motion V2 (Design System V2 · Fundamentos 05 · Motion).
   Coreografías de recompensa con los tokens --dur-* / --ease-* (estilos en
   components.css, bloque «MOTION»). El movimiento responde a una acción y
   se asienta sin rebotar: nada de confeti ni animaciones en reposo.

   - euXpGain(opts)      XP ganada: check 220 ms settle → «+N XP» sube 600 ms
                         → barra .eu-xpbar.is-gaining 1.2 s → contador tabular.
   - euCountTo(el, n)    contador que sube con tabular-nums.
   - euAchievement(opts) logro: sello .86→1 (settle 700 ms) + halo de 1 px.
   - euConfirm(msg,opts) confirmación con el markup de ui.modal (alertdialog).
   - toast(msg, type)    toast eu-toast con aria-live.
   El level-up vive aparte en eu-celebrate.js (único uso de ese archivo).

   Compatibilidad: euRewardSheet, euPerfectDay, euAnnounceAchievements,
   euCelebrate y euCelebrateBig siguen existiendo para los módulos que ya
   los llaman, pero ahora usan estas coreografías (sin partículas). */
(function () {
  'use strict';

  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  function reduced() { return !!(mq && mq.matches); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function icons(root) {
    if (!window.lucide) return;
    try { lucide.createIcons(root ? { root: root } : undefined); } catch (e) { try { lucide.createIcons(); } catch (e2) {} }
  }
  function restart(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  function toArr(x) {
    if (!x) return [];
    if (typeof x === 'string') return Array.prototype.slice.call(document.querySelectorAll(x));
    if (x.length != null && !x.nodeType) return Array.prototype.slice.call(x);
    return [x];
  }

  /* ── Contador tabular ──────────────────────────────────────────────── */
  function euCountTo(el, to, opts) {
    if (!el) return;
    opts = opts || {};
    to = Math.round(Number(to) || 0);
    var from = parseInt(String(el.textContent).replace(/[^\d-]/g, ''), 10);
    if (isNaN(from) || reduced() || from === to) { el.textContent = to.toLocaleString('es-MX'); return; }
    el.classList.add('eu-count');
    var dur = opts.duration || 1200, t0 = null, last = from;
    if (el._euCount) cancelAnimationFrame(el._euCount);
    function step(ts) {
      if (t0 == null) t0 = ts;
      var p = Math.min(1, (ts - t0) / dur);
      var e = 1 - Math.pow(1 - p, 3); // desacelera como --ease-emphasis
      var v = Math.round(from + (to - from) * e);
      if (v !== last) { el.textContent = v.toLocaleString('es-MX'); restart(el, 'is-ticking'); last = v; }
      if (p < 1) el._euCount = requestAnimationFrame(step);
    }
    el._euCount = requestAnimationFrame(step);
  }

  /* ── XP ganada ─────────────────────────────────────────────────────────
     opts: { el: botón/fila que se marcó, pop (false = ya hizo su check), xp, bars: .eu-xpbar (o su <i>),
             pct: nuevo % de la barra, counters: elementos del número, to } */
  function euXpGain(opts) {
    opts = opts || {};
    var el = opts.el;
    if (el && opts.pop !== false) {
      var chk = el.querySelector ? (el.querySelector('.eu-act-check') || null) : null;
      if (!reduced()) restart(chk || el, chk ? 'is-pop' : 'eu-pop');
    }
    var xp = Number(opts.xp) || 0;
    if (xp > 0 && el && !reduced()) {
      var r = el.getBoundingClientRect();
      var f = document.createElement('span');
      f.className = 'eu-xpfloat';
      f.setAttribute('aria-hidden', 'true');
      f.textContent = '+' + xp + ' XP';
      f.style.left = Math.max(8, Math.min(window.innerWidth - 80, r.right - 72)) + 'px';
      f.style.top = (r.top + r.height / 2 - 8) + 'px';
      document.body.appendChild(f);
      setTimeout(function () { f.remove(); }, 700);
    }
    var later = reduced() ? 0 : 300;
    setTimeout(function () {
      toArr(opts.bars).forEach(function (b) {
        var bar = b.classList.contains('eu-xpbar') ? b : b.closest('.eu-xpbar');
        var fill = bar ? bar.querySelector('i') : b;
        if (opts.pct != null && fill) fill.style.width = Math.max(0, Math.min(100, opts.pct)) + '%';
        if (bar) {
          if (opts.pct != null) bar.setAttribute('aria-valuenow', Math.round(opts.to != null ? opts.to : opts.pct));
          if (!reduced()) restart(bar, 'is-gaining');
        }
      });
      if (opts.to != null) toArr(opts.counters).forEach(function (c) { euCountTo(c, opts.to); });
    }, later);
  }

  /* ── Insignia de clasificación (mismo SVG que ui.rank) ─────────────── */
  var RANK_KEY = { iron: 'hierro', gold: 'oro', diamond: 'diamante' };
  var RANK_LABEL = { carbon: 'Carbón', hierro: 'Hierro', oro: 'Oro', diamante: 'Diamante' };
  function rankKey(r) { return RANK_KEY[r] || (RANK_LABEL[r] ? r : 'carbon'); }
  function euRank(rank, size, label) {
    var k = rankKey(rank), s = size || 48;
    return '<svg class="eu-rank" width="' + s + '" height="' + s + '" viewBox="0 0 120 120" data-rank="' + k + '"' +
      (label ? ' role="img" aria-label="' + esc(label) + '"' : ' aria-hidden="true"') + ' focusable="false"><use href="#eu-rank-' + k + '"/></svg>';
  }
  /** Cambia un <svg class="eu-rank"> existente a otro rango. */
  function euRankSet(svg, rank, label) {
    if (!svg) return;
    var k = rankKey(rank);
    svg.setAttribute('data-rank', k);
    var u = svg.querySelector('use'); if (u) u.setAttribute('href', '#eu-rank-' + k);
    if (label) svg.setAttribute('aria-label', label);
  }

  /** Actualiza una escalera ui.ranks() al rango dado (sin recargar). */
  var ORDER = ['carbon', 'hierro', 'oro', 'diamante'];
  function euRanksUpdate(ol, rank) {
    if (!ol) return;
    var ci = ORDER.indexOf(rankKey(rank));
    Array.prototype.forEach.call(ol.querySelectorAll('.eu-rank-step'), function (li, i) {
      li.classList.toggle('is-past', i < ci); li.classList.toggle('is-now', i === ci); li.classList.toggle('is-next', i > ci);
      if (i === ci) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
      var svg = li.querySelector('.eu-rank'); if (svg) svg.classList.toggle('is-locked', i > ci);
    });
    ol.setAttribute('aria-label', 'Clasificación del día: ' + RANK_LABEL[ORDER[ci]]);
  }

  /* ── Logro desbloqueado ────────────────────────────────────────────────
     opts: { icon | rank (carbon…diamante: medallón), rarity: bronce|plata|oro|especial, eyebrow, title, desc } */
  var achHost = null, achQueue = [], achBusy = false;
  function achHostEl() {
    if (achHost && document.body.contains(achHost)) return achHost;
    achHost = document.getElementById('eu-ach');
    if (!achHost) {
      achHost = document.createElement('div');
      achHost.id = 'eu-ach';
      achHost.className = 'eu-ach-toasts';
      achHost.setAttribute('aria-live', 'polite');
      document.body.appendChild(achHost);
    }
    return achHost;
  }
  function euAchievement(opts) {
    achQueue.push(opts || {});
    if (!achBusy) nextAch();
  }
  function nextAch() {
    var o = achQueue.shift();
    if (!o) { achBusy = false; return; }
    achBusy = true;
    var card = document.createElement('div');
    card.className = 'eu-ach eu-ach-toast is-earned';
    card.dataset.rarity = o.rarity || 'oro';
    card.innerHTML =
      (o.rank
        ? '<div class="eu-ach-seal eu-ach-seal--rank">' + euRank(o.rank, 56) + '<span class="eu-ach-halo" aria-hidden="true"></span></div>'
        : '<div class="eu-ach-seal"><i data-lucide="' + esc(o.icon || 'trophy') + '"></i><span class="eu-ach-halo" aria-hidden="true"></span></div>') +
      '<div class="eu-grow">' +
        '<div class="eu-ach-rar">' + esc(o.eyebrow || 'Logro desbloqueado') + '</div>' +
        '<div class="t-card">' + esc(o.title || '') + '</div>' +
        (o.desc ? '<div class="t-meta">' + esc(o.desc) + '</div>' : '') +
      '</div>' +
      '<button type="button" class="eu-iconbtn" aria-label="Cerrar aviso"><i data-lucide="x"></i></button>';
    achHostEl().appendChild(card);
    icons(card);
    var done = false;
    function close() {
      if (done) return; done = true;
      clearTimeout(timer);
      card.classList.add('is-leaving');
      setTimeout(function () { card.remove(); nextAch(); }, reduced() ? 0 : 220);
    }
    card.addEventListener('click', close);
    var timer = setTimeout(close, o.duration || 4500);
    // Pausa mientras el puntero o el foco están encima (WCAG 2.2.1).
    card.addEventListener('mouseenter', function () { clearTimeout(timer); });
    card.addEventListener('mouseleave', function () { if (!done) timer = setTimeout(close, 2000); });
  }

  /* ── Toast global con aria-live ──────────────────────────────────────── */
  var toastHost = null;
  function toastHostEl() {
    if (toastHost && document.body.contains(toastHost)) return toastHost;
    // El host vive en el layout desde la carga (región aria-live estable:
    // VoiceOver no siempre anuncia regiones que se insertan ya con texto).
    toastHost = document.getElementById('eu-toasts');
    if (!toastHost) {
      toastHost = document.createElement('div');
      toastHost.id = 'eu-toasts';
      toastHost.className = 'eu-toast-host';
      toastHost.setAttribute('aria-live', 'polite');
      document.body.appendChild(toastHost);
    }
    return toastHost;
  }
  var TOAST = {
    ok: { cls: 'eu-toast--success', icon: 'circle-check' },
    win: { cls: 'eu-toast--xp', icon: 'sparkles' },
    err: { cls: 'eu-toast--danger', icon: 'circle-alert' },
  };
  function euToast(msg, type) {
    var k = TOAST[type] || TOAST.ok;
    var host = toastHostEl();
    // Un solo toast a la vez: el nuevo reemplaza al anterior.
    Array.prototype.slice.call(host.children).forEach(function (c) { c.remove(); });
    var t = document.createElement('div');
    t.className = 'eu-toast ' + k.cls;
    // Errores interrumpen (role=alert); el resto lo anuncia el host (polite).
    if (type === 'err') t.setAttribute('role', 'alert');
    t.innerHTML = '<i data-lucide="' + k.icon + '" aria-hidden="true"></i><span class="grow"></span>';
    t.querySelector('.grow').textContent = msg;
    host.appendChild(t);
    icons(t);
    var ms = type === 'err' ? 5000 : 3000;
    setTimeout(function () {
      t.classList.add('is-leaving');
      setTimeout(function () { t.remove(); }, reduced() ? 0 : 220);
    }, ms);
  }

  /* ── Confirmación (alertdialog con el markup de ui.modal) ──────────── */
  var FOCUSABLE = 'button:not([disabled]),[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  function euConfirm(message, opts) {
    opts = opts || {};
    var danger = opts.danger !== false;
    return new Promise(function (resolve) {
      var opener = document.activeElement;
      var id = 'eu-cf-' + Date.now();
      var scrim = document.createElement('div');
      scrim.className = 'eu-scrim eu-confirm';
      scrim.innerHTML =
        '<div class="eu-modal" role="alertdialog" aria-modal="true" aria-describedby="' + id + '">' +
          '<div class="eu-modal-bd"><p class="eu-confirm-msg" id="' + id + '"></p></div>' +
          '<div class="eu-modal-ft">' +
            '<button type="button" class="eu-btn eu-btn--ghost" data-r="0"></button>' +
            '<button type="button" class="eu-btn ' + (danger ? 'eu-btn--danger' : 'eu-btn--primary') + '" data-r="1"></button>' +
          '</div>' +
        '</div>';
      scrim.querySelector('.eu-confirm-msg').textContent = message;
      var btns = scrim.querySelectorAll('[data-r]');
      btns[0].textContent = opts.cancelLabel || 'Cancelar';
      btns[1].textContent = opts.confirmLabel || (danger ? 'Eliminar' : 'Confirmar');
      scrim.querySelector('[role=alertdialog]').setAttribute('aria-label', opts.title || (danger ? 'Confirmar eliminación' : 'Confirmar'));
      document.body.appendChild(scrim);
      var prevOverflow = document.documentElement.style.overflow;
      document.documentElement.style.overflow = 'hidden';

      var settled = false;
      function close(v) {
        if (settled) return; settled = true;
        document.removeEventListener('keydown', onKey, true);
        scrim.remove();
        document.documentElement.style.overflow = prevOverflow;
        if (opener && opener.focus && document.contains(opener)) opener.focus();
        resolve(v);
      }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(false); return; }
        if (e.key === 'Tab') {
          var f = scrim.querySelectorAll(FOCUSABLE);
          var a = f[0], z = f[f.length - 1];
          if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
          else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
          else if (!scrim.contains(document.activeElement)) { e.preventDefault(); a.focus(); }
        }
      }
      scrim.addEventListener('mousedown', function (e) { if (e.target === scrim) close(false); });
      btns[0].addEventListener('click', function () { close(false); });
      btns[1].addEventListener('click', function () { close(true); });
      document.addEventListener('keydown', onKey, true);
      // Foco inicial en Cancelar: default seguro para acciones destructivas.
      (danger ? btns[0] : btns[1]).focus();
    });
  }


  /* ── XP del día / nivel / EC en topbar y sidebar ───────────────────── */
  var fmt = function (n) { return Number(n || 0).toLocaleString('es-MX'); };
  function euRefreshXp(opts) {
    opts = opts || {};
    if (!document.querySelector('.eu-ec-val')) return Promise.resolve(null);
    return fetch('/api/xp', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) return null;
      var anim = !opts.initial;
      document.querySelectorAll('.eu-ec-val').forEach(function (el) { anim ? euCountTo(el, d.total_coins) : (el.textContent = fmt(d.total_coins)); });
      document.querySelectorAll('.eu-xp-today').forEach(function (el) { anim ? euCountTo(el, d.xp_today) : (el.textContent = fmt(d.xp_today)); });
      var lv = document.getElementById('eu-sb-level');
      if (lv) lv.textContent = 'Nivel ' + d.level + ' · ' + (d.level_name || '').charAt(0) + (d.level_name || '').slice(1).toLowerCase();
      var pct = Math.max(0, Math.min(100, Math.round(d.level_pct || 0)));
      var pc = document.getElementById('eu-sb-pct'); if (pc) pc.textContent = pct + '%';
      var bar = document.getElementById('eu-sb-bar');
      if (bar) {
        bar.style.width = pct + '%';
        bar.parentNode.setAttribute('aria-valuenow', pct);
        bar.parentNode.setAttribute('aria-valuetext', pct + '% del nivel ' + d.level);
        if (anim && !reduced()) restart(bar.parentNode, 'is-gaining');
      }
      if (window.euCheckLevel) window.euCheckLevel(d);
      return d;
    }).catch(function () { return null; });
  }

  /* ── Respuesta de gamificación de cualquier módulo ─────────────────────
     gam: { xp, ec, achievements, badges, ... } — lo que devuelven los
     endpoints que dan XP. opts.el: el control que el usuario activó. */
  function euGam(gam, opts) {
    opts = opts || {};
    if (!gam) return;
    var xp = Number(gam.xp) || 0;
    if (opts.el && xp > 0) euXpGain({ el: opts.el, xp: xp, pop: opts.pop });
    euRefreshXp();
    window.euAnnounceAchievements(gam);
  }

  /* ── Vacío (mismo markup que ui.empty()) para listas que arma JS ─────── */
  function euEmpty(icon, title, text, compact, ctaHtml) {
    return '<div class="eu-empty' + (compact ? ' eu-empty--sm' : '') + '"><div class="eu-empty-ic"><i data-lucide="' + esc(icon) + '"></i></div>' +
      '<div class="t-card">' + esc(title) + '</div>' + (text ? '<p>' + esc(text) + '</p>' : '') + (ctaHtml || '') + '</div>';
  }

  /* ── Esqueleto de carga: filas .eu-skel en un envoltorio aria-busy que
     desaparece solo cuando el módulo reemplaza el contenido. ─────────── */
  function euSkelHTML(n, h) {
    var rows = '';
    for (var i = 0; i < (n || 3); i++) rows += '<div class="eu-skel" style="height:' + (h || 56) + 'px"></div>';
    return '<div class="eu-skel-wrap" aria-busy="true" role="status" aria-label="Cargando">' + rows + '</div>';
  }
  function euSkel(el, n, h) {
    if (typeof el === 'string') el = document.getElementById(el) || document.querySelector(el);
    if (el) el.innerHTML = euSkelHTML(n, h);
  }

  /* ── API pública + compatibilidad ────────────────────────────────────── */
  window.euMotion = { reduced: reduced };
  window.euCountTo = euCountTo;
  window.euEmpty = euEmpty;
  window.euRank = euRank;
  window.euRankSet = euRankSet;
  window.euRanksUpdate = euRanksUpdate;
  window.euRankLabel = function (r) { return RANK_LABEL[rankKey(r)]; };
  window.euSkel = euSkel;
  window.euSkelHTML = euSkelHTML;
  window.euXpGain = euXpGain;
  window.euRefreshXp = euRefreshXp;
  window.euGam = euGam;
  window.euAchievement = euAchievement;
  window.euConfirm = euConfirm;
  window.toast = euToast;

  // Antes: bottom sheet con partículas. Ahora: aviso de logro (sello + halo).
  window.euRewardSheet = function (o) {
    o = o || {};
    euAchievement({ icon: o.icon, rarity: o.rarity || 'oro', eyebrow: o.eyebrow, title: o.title, desc: o.desc });
  };
  window.euPerfectDay = function (o) {
    o = o || {};
    var parts = [];
    if (o.xp) parts.push('+' + o.xp + ' XP');
    if (o.ec) parts.push('+' + o.ec + ' EC');
    euAchievement({ icon: 'sparkles', rarity: 'especial', eyebrow: 'Día perfecto', title: 'Día Perfecto', desc: parts.join(' · ') });
  };
  var TIER = { bronze: 'bronce', silver: 'plata', gold: 'oro', diamond: 'especial' };
  window.euAnnounceAchievements = function (gam) {
    if (!gam) return;
    (gam.achievements || []).forEach(function (a) {
      var desc = [a.description, a.xp ? '+' + a.xp + ' XP' : '', a.coins ? '+' + a.coins + ' EC' : ''].filter(Boolean).join(' · ');
      euAchievement({ icon: a.icon_lucide || 'trophy', rarity: a.rarity || TIER[a.tier] || 'oro', eyebrow: 'Logro desbloqueado', title: a.name, desc: desc });
    });
    (gam.badges || []).forEach(function (b) {
      euAchievement({ icon: b.icon_lucide || 'award', rarity: TIER[b.tier] || b.rarity || 'bronce', eyebrow: 'Insignia', title: b.name, desc: b.description || '' });
    });
  };
  // Antes: ráfaga de partículas. Ahora: settle del propio elemento.
  window.euCelebrate = function (el) { if (el && !reduced()) restart(el, 'eu-pop'); };
  window.euCelebrateBig = window.euCelebrate;
})();
