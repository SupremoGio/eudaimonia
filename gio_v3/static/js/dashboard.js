/* Dashboard (/) — interacciones. Antes vivía inline en dashboard/index.html.
   Endpoints (sin cambios):
     POST /actividades/api/activity/log   {key}  → marcar la sugerencia
     GET  /api/quote/refresh                     → nueva reflexión
     GET  /api/word/refresh                      → otra palabra del día
     POST data-url de cada fila del radar        → cumplir tarea/riego/recordatorio */
(function () {
  'use strict';

  function spin(btn, on) { if (btn) btn.classList.toggle('is-spinning', on); }

  // ── Siguiente paso: registra la actividad y recarga (XP, tiers y radar cambian)
  document.querySelectorAll('.js-sugg').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.setAttribute('aria-busy', 'true');
      fetch('/actividades/api/activity/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: btn.dataset.key }),
      }).then(function () { location.reload(); })
        .catch(function () { btn.removeAttribute('aria-busy'); toast('No se pudo registrar', 'err'); });
    });
  });

  // ── Reflexión del día
  var qBtn = document.getElementById('quote-refresh');
  if (qBtn) qBtn.addEventListener('click', function () {
    spin(qBtn, true);
    fetch('/api/quote/refresh').then(function (r) { return r.json(); }).then(function (q) {
      var t = document.querySelector('.js-q-text'), a = document.querySelector('.js-q-author'),
          c = document.querySelector('.js-q-cat');
      if (t) t.textContent = '«' + q.text + '»';
      if (a) a.textContent = q.author;
      if (c) { c.dataset.kind = q.category; c.textContent = q.category === 'stoic' ? 'Estoica' : 'Motivacional'; }
    }).catch(function () {}).then(function () { spin(qBtn, false); });
  });

  // ── Palabra del día
  var wBtn = document.getElementById('word-refresh');
  if (wBtn) wBtn.addEventListener('click', function () {
    spin(wBtn, true);
    fetch('/api/word/refresh').then(function (r) { return r.json(); }).then(function (w) {
      if (!document.querySelector('.js-w-word')) { location.reload(); return; }   // venía vacía
      document.querySelector('.js-w-word').textContent = w.word;
      document.querySelector('.js-w-phon').textContent = w.phonetic;
      document.querySelector('.js-w-meaning').textContent = w.meaning;
      document.querySelector('.js-w-example').textContent = '“' + w.example + '”';
      document.querySelector('.js-w-fr').textContent = 'FR · ' + w.french;
    }).catch(function () {}).then(function () { spin(wBtn, false); });
  });

  // ── Radar y campanita: marcar como cumplido. La misma fila vive en la
  //    tarjeta «Pendiente» y en el panel de la campanita (data-key).
  function syncRadar() {
    var left = document.querySelectorAll('.dash-radar .dash-radar-row').length;
    var count = document.querySelector('.js-radar-count'); if (count) count.textContent = left + ' próximos';
    document.querySelectorAll('.js-radar-box').forEach(function (box) {
      if (box.querySelector('.dash-radar-row')) return;
      var list = box.querySelector('.js-radar-list'); if (list) list.remove();
      var empty = box.querySelector('.js-radar-empty'); if (empty) empty.hidden = false;
    });
    document.querySelectorAll('.js-dl-sec').forEach(function (sec) {
      var n = sec.querySelectorAll('.dash-radar-row').length;
      if (!n) sec.remove(); else sec.querySelector('.js-dl-sec-ct').textContent = n;
    });
    var ct = document.querySelector('.js-bell-ct'), bell = document.querySelector('.dash-bell');
    var urgent = document.querySelectorAll('.dash-radar .dash-radar-row[data-level=red]').length;
    if (ct) { ct.textContent = left; ct.hidden = !left; ct.classList.toggle('is-urgent', urgent > 0); }
    if (bell) bell.setAttribute('aria-label', 'Recordatorios: ' + left + ' pendiente' + (left === 1 ? '' : 's') + (urgent ? ', ' + urgent + ' para hoy o vencido' + (urgent === 1 ? '' : 's') : ''));
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.js-dl-done');
    if (!btn || btn.disabled) return;
    var key = btn.closest('.dash-radar-row').dataset.key;
    var copies = document.querySelectorAll('.dash-radar-row[data-key="' + key + '"] .js-dl-done');
    copies.forEach(function (b) { b.disabled = true; });
    fetch(btn.dataset.url, { method: 'POST' }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) { copies.forEach(function (b) { b.disabled = false; }); toast('No se pudo marcar', 'err'); return; }
      if (j.gam && window.euXpGain) euXpGain({ el: btn, xp: j.gam.xp });
      document.querySelectorAll('.dash-radar-row[data-key="' + key + '"]').forEach(function (row) { row.classList.add('is-leaving'); });
      setTimeout(function () {
        document.querySelectorAll('.dash-radar-row[data-key="' + key + '"]').forEach(function (row) { row.remove(); });
        syncRadar();
      }, 220);
      if (j.gam && j.gam.xp) toast('+' + j.gam.xp + ' XP' + (j.gam.ec ? ' · +' + j.gam.ec + ' EC' : ''), 'win');
      else toast('Hecho', 'ok');
      if (j.gam && window.euGam) euGam(j.gam);
    }).catch(function () { copies.forEach(function (b) { b.disabled = false; }); toast('No se pudo marcar', 'err'); });
  });
})();
