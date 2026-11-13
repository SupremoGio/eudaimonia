/* Dashboard (/) — interacciones. Antes vivía inline en dashboard/index.html.
   Endpoints (sin cambios):
     POST /actividades/api/activity/log   {key}  → marcar la sugerencia (refresca el héroe)
     GET  /api/quote/refresh                     → nueva reflexión (pestaña Reflexión)
     GET  /api/word/refresh                      → otra palabra del día (pestaña Palabra)
     POST data-url de cada fila del radar        → cumplir tarea/riego/recordatorio */
(function () {
  'use strict';

  function spin(btn, on) { if (btn) btn.classList.toggle('is-spinning', on); }

  // ── Siguiente paso (dentro del héroe): registra la actividad, deja el
  //    botón en «Hecho» y refresca rango, criterios y XP sin recargar
  //    (mismo HTML del servidor: el héroe no se pinta dos veces).
  function refreshHero() {
    var hero = document.querySelector('.js-hero'); if (!hero) return Promise.resolve();
    var oldBar = hero.querySelector('.js-hero-xp .eu-xpbar > i'), oldW = oldBar ? oldBar.style.width : null;
    return fetch(location.pathname, { credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      ['.js-hero-rank', '.js-hero-crit', '.dash-hero-side'].forEach(function (sel) {
        var cur = hero.querySelector(sel), neu = doc.querySelector('.js-hero ' + sel);
        if (cur && neu) cur.replaceWith(neu);
        else if (cur) cur.remove();
        else if (neu) { var next = hero.querySelector('.dash-next'); if (next) next.before(neu); }
      });
      var bar = hero.querySelector('.js-hero-xp .eu-xpbar > i');
      if (bar && oldW) { var to = bar.style.width; bar.style.width = oldW; requestAnimationFrame(function () { requestAnimationFrame(function () { bar.style.width = to; }); }); }
      if (window.lucide) lucide.createIcons();
    });
  }
  document.querySelectorAll('.js-sugg').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (btn.classList.contains('is-done') || btn.getAttribute('aria-busy')) return;
      btn.setAttribute('aria-busy', 'true');
      fetch('/actividades/api/activity/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: btn.dataset.key }),
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j || j.action !== 'added') throw new Error();
        btn.removeAttribute('aria-busy');
        btn.classList.add('is-done');
        btn.setAttribute('aria-label', 'Hecho, +' + (j.xp || btn.dataset.pts) + ' XP');
        btn.querySelector('span').textContent = 'Hecho · +' + (j.xp || btn.dataset.pts) + ' XP';
        if (window.euGam && j.gam) euGam(j.gam, { el: btn });
        return refreshHero();
      }).catch(function () { btn.removeAttribute('aria-busy'); toast('No se pudo registrar', 'err'); });
    });
  });

  // ── Inspiración: pestañas Reflexión | Palabra (role=tablist; las flechas
  //    las maneja eu-a11y.js) y un solo ↻ que renueva la pestaña activa.
  var INSP_KEY = 'eu-dash-insp';
  var inspTabs = document.querySelectorAll('[data-insp]');
  var inspBtn = document.getElementById('insp-refresh');
  function inspShow(which, save) {
    inspTabs.forEach(function (t) {
      var on = t.dataset.insp === which;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      var panel = document.getElementById(t.getAttribute('aria-controls'));
      if (panel) panel.hidden = !on;
    });
    if (inspBtn) {
      var lbl = which === 'word' ? 'Otra palabra' : 'Otra reflexión';
      inspBtn.setAttribute('aria-label', lbl); inspBtn.title = lbl;
    }
    if (save) { try { localStorage.setItem(INSP_KEY, which); } catch (_) {} }
  }
  inspTabs.forEach(function (t) { t.addEventListener('click', function () { inspShow(t.dataset.insp, true); }); });
  if (inspTabs.length) {
    var saved = null; try { saved = localStorage.getItem(INSP_KEY); } catch (_) {}
    inspShow(saved === 'word' ? 'word' : 'quote', false);
  }
  function current() { var t = document.querySelector('[data-insp][aria-selected=true]'); return t ? t.dataset.insp : 'quote'; }
  if (inspBtn) inspBtn.addEventListener('click', function () {
    spin(inspBtn, true);
    if (current() === 'word') {
      fetch('/api/word/refresh').then(function (r) { return r.json(); }).then(function (w) {
        if (!document.querySelector('.js-w-word')) { location.reload(); return; }   // venía vacía
        document.querySelector('.js-w-word').textContent = w.word;
        document.querySelector('.js-w-phon').textContent = w.phonetic;
        document.querySelector('.js-w-meaning').textContent = w.meaning;
        document.querySelector('.js-w-example').textContent = '“' + w.example + '”';
        document.querySelector('.js-w-fr').textContent = 'FR · ' + w.french;
      }).catch(function () {}).then(function () { spin(inspBtn, false); });
    } else {
      fetch('/api/quote/refresh').then(function (r) { return r.json(); }).then(function (q) {
        var t = document.querySelector('.js-q-text'), a = document.querySelector('.js-q-author'),
            c = document.querySelector('.js-q-cat');
        if (t) t.textContent = '«' + q.text + '»';
        if (a) a.textContent = q.author;
        if (c) c.textContent = q.category === 'stoic' ? 'Estoica' : 'Motivacional';
      }).catch(function () {}).then(function () { spin(inspBtn, false); });
    }
  });

  // ── Pendiente: marcar como cumplido (o posponer riego). La fila sale con
  //    animación y se actualizan los contadores de ambos grupos.
  function syncRadar() {
    document.querySelectorAll('.js-dl-sec').forEach(function (sec) {
      var n = sec.querySelectorAll('.dash-radar-row').length;
      if (!n) { sec.remove(); return; }
      sec.querySelector('.js-dl-sec-ct').textContent = n;
      var more = sec.querySelector('.dash-radar-more');
      if (more) {
        var m = more.querySelectorAll('.dash-radar-row').length;
        if (!m) more.remove(); else more.querySelector('summary').textContent = 'Ver ' + m + ' más';
      }
    });
    document.querySelectorAll('.js-radar-box').forEach(function (box) {
      if (box.querySelector('.dash-radar-row')) return;
      var list = box.querySelector('.js-radar-list'); if (list) list.remove();
      var empty = box.querySelector('.js-radar-empty'); if (empty) empty.hidden = false;
    });
  }
  // Lo resuelto desde la campana sale también de «Pendiente» (misma fuente).
  document.addEventListener('eu:avisos-changed', function (e) {
    var k = e.detail && e.detail.clave; if (!k) return;
    document.querySelectorAll('.dash-radar-row').forEach(function (row) { if (row.dataset.clave === k) row.remove(); });
    syncRadar();
  });
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.js-dl-done');
    if (!btn || btn.disabled) return;
    var key = btn.closest('.dash-radar-row').dataset.key;
    var copies = document.querySelectorAll('.dash-radar-row[data-key="' + key + '"] .js-dl-done');
    copies.forEach(function (b) { b.disabled = true; });
    var opt = { method: btn.dataset.method || 'POST' };
    if (btn.dataset.body) { opt.headers = { 'Content-Type': 'application/json' }; opt.body = btn.dataset.body; }
    fetch(btn.dataset.url, opt).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) { copies.forEach(function (b) { b.disabled = false; }); toast('No se pudo marcar', 'err'); return; }
      if (j.gam && window.euXpGain) euXpGain({ el: btn, xp: j.gam.xp });
      document.querySelectorAll('.dash-radar-row[data-key="' + key + '"]').forEach(function (row) { row.classList.add('is-leaving'); });
      setTimeout(function () {
        document.querySelectorAll('.dash-radar-row[data-key="' + key + '"]').forEach(function (row) { row.remove(); });
        syncRadar();
      }, 220);
      if (window.euAvisos) euAvisos.load().catch(function () {});
      if (j.gam && j.gam.xp) toast('+' + j.gam.xp + ' XP' + (j.gam.ec ? ' · +' + j.gam.ec + ' EC' : ''), 'win');
      else toast(j.msg || 'Hecho', 'ok');
      if (j.gam && window.euGam) euGam(j.gam);
    }).catch(function () { copies.forEach(function (b) { b.disabled = false; }); toast('No se pudo marcar', 'err'); });
  });
})();
