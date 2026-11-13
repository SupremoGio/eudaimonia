/* eu-avisos.js — Avisos, un solo centro (handoff Avisos, Sprint 2).

   Campana de la topbar (#eu-avisos-btn) + panel #eu-avisos: popover de
   440px en escritorio, hoja inferior en móvil (components.css). Los avisos
   vienen de GET /api/avisos (modules/avisos.py), agrupados en Hoy, Esta
   semana y Logros. Cada fila trae su acción:
     · con `method`: fetch en línea, la fila se va y queda un toast con
       «Deshacer» (llama a accion.deshacer si el módulo tiene endpoint
       inverso; si no, no se ofrece);
     · sin `method`: navega a accion.url.
   ⏱ pospone (1 día en Hoy, 3 en la semana) y ✕ descarta un logro; ambos
   se deshacen con /restaurar. Al abrir se marcan vistos los logros.
   Diálogo accesible: foco al primer aviso, Tab atrapado, Esc cierra y el
   foco vuelve a la campana. */
(function () {
  'use strict';
  var root = window, doc = document;
  var NIVELES = [['hoy', 'Hoy'], ['semana', 'Esta semana'], ['logro', 'Logros']];
  var POSPONER = { hoy: 'Pospuesto hasta mañana', semana: 'Pospuesto 3 días', logro: 'Descartado' };
  var FOCUSABLE = 'a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])';
  var state = { data: null, tab: 'todo', opener: null, loading: null };

  function $(id) { return doc.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function icons() { try { root.lucide.createIcons(); } catch (e) {} }
  function json(url, method, body) {
    var opt = { method: method || 'GET', headers: { 'Accept': 'application/json' } };
    if (body !== undefined && method && method !== 'GET') {
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body || {});
    }
    return fetch(url, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok || d.ok === false || d.error) throw new Error(d.error || ('Error ' + r.status));
        return d;
      });
    });
  }
  function enc(clave) { return clave.split('/').map(encodeURIComponent).join('/'); }

  /* ── Campana ─────────────────────────────────────────────────────────── */
  function setCount(n) {
    var btn = $('eu-avisos-btn'); if (!btn) return;
    n = Math.max(0, n | 0);
    var prev = btn.getAttribute('aria-label');
    btn.setAttribute('aria-label', 'Avisos, ' + n + ' para hoy');
    var live = $('eu-avisos-live');
    if (live && prev && prev !== btn.getAttribute('aria-label')) live.textContent = n + ' aviso' + (n !== 1 ? 's' : '') + ' para hoy';
    var b = btn.querySelector('.eu-avisos-badge');
    if (n && !b) { b = doc.createElement('b'); b.className = 'eu-avisos-badge'; b.setAttribute('aria-hidden', 'true'); btn.appendChild(b); }
    if (b) { if (n) b.textContent = n; else b.remove(); }
  }

  /* ── Datos ───────────────────────────────────────────────────────────── */
  function load() {
    state.loading = json('/api/avisos').then(function (d) {
      state.data = d; state.loading = null; setCount(d.conteo_hoy); return d;
    }, function (e) { state.loading = null; throw e; });
    return state.loading;
  }
  function all() {
    var d = state.data || {}, out = [];
    NIVELES.forEach(function (n) { (d[n[0]] || []).forEach(function (a) { out.push(a); }); });
    return out;
  }
  function find(clave) { return all().filter(function (a) { return a.clave === clave; })[0]; }
  function remove(clave) {
    var d = state.data; if (!d) return null;
    var hit = null;
    NIVELES.forEach(function (n) {
      var l = d[n[0]] || [], i = l.findIndex(function (a) { return a.clave === clave; });
      if (i >= 0) { hit = { aviso: l[i], nivel: n[0], i: i }; l.splice(i, 1); }
    });
    if (hit) { d.conteo_hoy = (d.hoy || []).length; d.total = all().length; setCount(d.conteo_hoy); }
    return hit;
  }
  function restore(hit) {
    if (!hit || !state.data) return;
    var l = state.data[hit.nivel] = state.data[hit.nivel] || [];
    if (!l.some(function (a) { return a.clave === hit.aviso.clave; })) l.splice(Math.min(hit.i, l.length), 0, hit.aviso);
    state.data.conteo_hoy = (state.data.hoy || []).length;
    state.data.total = all().length;
    setCount(state.data.conteo_hoy);
    render();
  }

  /* ── Pintar ──────────────────────────────────────────────────────────── */
  function row(a) {
    var ac = a.accion || {};
    var act = ac.method
      ? '<button type="button" class="eu-avisos-act" data-av-act>' + esc(ac.label || 'Hecho') + '</button>'
      : (ac.url ? '<a class="eu-avisos-act" data-av-go href="' + esc(ac.url) + '">' + esc(ac.label || 'Ver') + '</a>' : '');
    var logro = a.nivel === 'logro';
    var snz = '<button type="button" class="eu-avisos-snz" data-av-snz aria-label="' +
      (logro ? 'Descartar' : (a.nivel === 'hoy' ? 'Posponer hasta mañana' : 'Posponer 3 días')) + ': ' + esc(a.titulo) + '" title="' +
      (logro ? 'Descartar' : (a.nivel === 'hoy' ? 'Hasta mañana' : '3 días')) + '"><i data-lucide="' + (logro ? 'x' : 'timer') + '"></i></button>';
    return '<li class="eu-avisos-row" data-clave="' + esc(a.clave) + '">' +
      '<span class="eu-avisos-ic" aria-hidden="true"><i data-lucide="' + esc(a.icono || 'bell') + '"></i></span>' +
      '<div class="eu-avisos-tx"><div class="eu-avisos-tt">' + esc(a.titulo) + '</div>' +
      '<div class="eu-avisos-st">' + esc(a.modulo) + (a.detalle ? ' · ' + esc(a.detalle) : '') + '</div></div>' +
      '<div class="eu-avisos-acts">' + act + snz + '</div></li>';
  }
  function render() {
    var bd = $('eu-avisos-bd'); if (!bd) return;
    var d = state.data || {};
    var html = '', vis = 0;
    NIVELES.forEach(function (n) {
      if (state.tab === 'pend' && n[0] === 'logro') return;
      var l = d[n[0]] || [];
      if (!l.length) return;
      vis += l.length;
      var hid = 'eu-av-g-' + n[0];
      html += '<section class="eu-avisos-g" data-nivel="' + n[0] + '" aria-labelledby="' + hid + '">' +
        '<h3 class="eu-avisos-gh" id="' + hid + '">' + n[1] + ' <span class="num">' + l.length + '</span></h3>' +
        '<ul class="eu-avisos-list">' + l.map(row).join('') + '</ul></section>';
    });
    bd.innerHTML = vis ? html :
      '<div class="eu-avisos-empty"><i data-lucide="check" aria-hidden="true"></i><b>Nada pendiente</b><span>Lo pospuesto vuelve solo cuando toca.</span></div>';
    var tot = $('eu-avisos-total'); if (tot) tot.textContent = d.total || 0;
    var n = d.conteo_hoy || 0, ft = $('eu-avisos-foot');
    if (ft) ft.textContent = (n ? n + ' para hoy' : 'Al día') + ' · lo pospuesto vuelve solo';
    [].forEach.call(doc.querySelectorAll('[data-avtab]'), function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-avtab') === state.tab ? 'true' : 'false');
    });
    icons();
  }

  /* ── Toast con «Deshacer» (mismo host aria-live que toast()) ────────── */
  function undoToast(msg, undo) {
    var host = $('eu-toasts');
    if (!host || !undo) { if (root.toast) root.toast(msg); return; }
    [].slice.call(host.children).forEach(function (c) { c.remove(); });
    var t = doc.createElement('div');
    t.className = 'eu-toast eu-toast--success';
    t.innerHTML = '<i data-lucide="circle-check" aria-hidden="true"></i><span class="grow"></span><button type="button" class="eu-quick-undo">Deshacer</button>';
    t.querySelector('.grow').textContent = msg;
    host.appendChild(t); icons();
    var gone = setTimeout(function () { t.remove(); }, 6000);
    t.querySelector('button').addEventListener('click', function () {
      clearTimeout(gone); t.remove();
      undo().then(function () { if (root.toast) root.toast('Deshecho'); })
        .catch(function (e) { if (root.toast) root.toast(e.message || 'No se pudo deshacer', 'err'); });
    });
  }

  /* ── Acciones ────────────────────────────────────────────────────────── */
  /* Quita la fila y deja el foco en la siguiente (o en el título). */
  function dropAndFocus(li, clave) {
    var sib = li && (li.nextElementSibling || li.previousElementSibling);
    var next = sib && sib.getAttribute('data-clave');
    var hit = remove(clave);
    render();
    var bd = $('eu-avisos-bd'), el = null;
    if (next) [].some.call(bd.querySelectorAll('.eu-avisos-row'), function (r) {
      if (r.getAttribute('data-clave') === next) { el = r.querySelector('a,button'); return true; }
    });
    (el || bd.querySelector('.eu-avisos-row a, .eu-avisos-row button') || $('eu-avisos-t')).focus();
    return hit;
  }
  function act(li, a, btn) {
    var ac = a.accion || {};
    btn.setAttribute('aria-busy', 'true');
    json(ac.url, ac.method, ac.body || {}).then(function (res) {
      var hit = dropAndFocus(li, a.clave);
      if (res && res.gam && root.euGam) root.euGam(res.gam, {});
      else if (root.euRefreshXp) root.euRefreshXp();
      var d = ac.deshacer;
      undoToast(ac.hecho || (ac.label + ' · listo'), d ? function () {
        return json(d.url, d.method, d.body || {}).then(function () { restore(hit); if (root.euRefreshXp) root.euRefreshXp(); });
      } : null);
      doc.dispatchEvent(new CustomEvent('eu:avisos-changed', { detail: { clave: a.clave } }));
    }).catch(function (e) {
      btn.removeAttribute('aria-busy');
      if (root.toast) root.toast(e.message || 'No se pudo', 'err');
    });
  }
  function snooze(li, a) {
    var logro = a.nivel === 'logro';
    var url = '/api/avisos/' + enc(a.clave) + (logro ? '/descartar' : '/posponer');
    json(url, 'POST', logro ? {} : { nivel: a.nivel }).then(function (res) {
      var hit = dropAndFocus(li, a.clave);
      doc.dispatchEvent(new CustomEvent('eu:avisos-changed', { detail: { clave: a.clave } }));
      undoToast(POSPONER[a.nivel] || 'Pospuesto', function () {
        return json('/api/avisos/' + enc(a.clave) + '/restaurar', 'POST', {}).then(function () { restore(hit); });
      });
    }).catch(function (e) { if (root.toast) root.toast(e.message || 'No se pudo posponer', 'err'); });
  }

  /* ── Abrir / cerrar (euDialog: foco atrapado, Esc y regreso del foco) ── */
  function isOpen() { var p = $('eu-avisos'); return p && root.euDialog && root.euDialog.isOpen(p); }
  function open() {
    var p = $('eu-avisos'), btn = $('eu-avisos-btn'); if (!p || isOpen()) return;
    var movil = root.matchMedia && root.matchMedia('(max-width:767px)').matches;
    root.euDialog.open(p, btn, { focus: false, scrimClose: true, lock: movil,
      onClose: function () { doc.documentElement.classList.remove('eu-avisos-open'); } });
    doc.documentElement.classList.add('eu-avisos-open');
    var bd = $('eu-avisos-bd');
    if (!state.data && bd) bd.innerHTML = root.euSkelHTML ? root.euSkelHTML(3, 52) : '';
    else render();
    $('eu-avisos-t').setAttribute('tabindex', '-1');
    $('eu-avisos-t').focus();
    load().then(function (d) {
      render();
      var first = $('eu-avisos-bd').querySelector('.eu-avisos-row a, .eu-avisos-row button');
      if (isOpen() && first && (doc.activeElement === $('eu-avisos-t') || !p.contains(doc.activeElement))) first.focus();
      var logros = (d.logro || []).map(function (a) { return a.clave; });
      if (logros.length) json('/api/avisos/logros/vistos', 'POST', { claves: logros }).catch(function () {});
    }).catch(function () {
      if (bd) bd.innerHTML = '<div class="eu-avisos-empty"><b>No se pudieron cargar</b><span>Intenta de nuevo en un momento.</span></div>';
    });
  }
  function close() { var p = $('eu-avisos'); if (p && isOpen()) root.euDialog.close(p); }

  function init() {
    var btn = $('eu-avisos-btn'), p = $('eu-avisos');
    if (!btn || !p) return;
    btn.addEventListener('click', function () { isOpen() ? close() : open(); });
    p.addEventListener('click', function (e) {
      var t = e.target.closest('[data-avtab]');
      if (t) { state.tab = t.getAttribute('data-avtab'); render(); return; }
      var li = e.target.closest('.eu-avisos-row'); if (!li) return;
      var a = find(li.getAttribute('data-clave')); if (!a) return;
      var b;
      if ((b = e.target.closest('[data-av-act]'))) act(li, a, b);
      else if (e.target.closest('[data-av-snz]')) snooze(li, a);
      else if (e.target.closest('[data-av-go]')) close();
    });
    // Lo que resuelve otro flujo (captura rápida, la página del módulo)
    // puede cambiar el conteo: se refresca al volver a la pestaña.
    doc.addEventListener('visibilitychange', function () { if (!doc.hidden && !isOpen()) load().catch(function () {}); });
  }

  root.euAvisos = { open: open, close: close, load: load, setCount: setCount };
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init); else init();
})();
