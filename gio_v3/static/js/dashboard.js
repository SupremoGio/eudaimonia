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

  // ── Radar: marcar como cumplido
  var count = document.querySelector('.js-radar-count');
  document.querySelectorAll('.js-dl-done').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (btn.disabled) return;
      btn.disabled = true;
      fetch(btn.dataset.url, { method: 'POST' }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok) { btn.disabled = false; toast('No se pudo marcar', 'err'); return; }
        var row = btn.closest('.dash-radar-row');
        row.classList.add('is-leaving');
        setTimeout(function () {
          row.remove();
          var left = document.querySelectorAll('.dash-radar-row').length;
          if (count) count.textContent = left + ' próximos';
          if (!left) {
            var list = document.querySelector('.js-radar-list'); if (list) list.remove();
            var empty = document.querySelector('.js-radar-empty'); if (empty) empty.hidden = false;
          }
        }, 220);
        if (j.gam && j.gam.xp) toast('+' + j.gam.xp + ' XP' + (j.gam.ec ? ' · +' + j.gam.ec + ' EC' : ''));
      }).catch(function () { btn.disabled = false; toast('No se pudo marcar', 'err'); });
    });
  });
})();
