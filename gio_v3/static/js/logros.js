/* Logros (/logros) — pestañas por estado y orden de insignias. Sin endpoints:
   todo viene renderizado por el servidor. */
(function () {
  'use strict';
  var root = document.querySelector('.lg');
  if (!root) return;
  function $$(s, el) { return [].slice.call((el || document).querySelectorAll(s)); }

  // Pestañas: Todos / Ganados / Bloqueados
  var tabs = $$('.eu-tabs [data-status]', root), empty = root.querySelector('.js-coll-empty');
  function setStatus(st) {
    root.dataset.status = st;
    tabs.forEach(function (t) { t.setAttribute('aria-selected', t.dataset.status === st ? 'true' : 'false'); });
    var visible = $$('.eu-ach', root).some(function (a) { return a.offsetParent !== null; });
    if (empty) empty.hidden = visible;
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { setStatus(t.dataset.status); }); });
  // Flechas ←/→ entre pestañas (patrón tablist)
  root.querySelector('.eu-tabs').addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    var i = tabs.indexOf(document.activeElement); if (i < 0) return;
    var n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    n.focus(); n.click();
  });

  // Orden de insignias: rareza (orden del servidor) o más recientes primero
  var grid = root.querySelector('.js-badges');
  var seg = $$('[data-sort]', root);
  seg.forEach(function (b) {
    b.addEventListener('click', function () {
      seg.forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      var cards = $$('.eu-ach', grid);
      cards.sort(b.dataset.sort === 'recent'
        ? function (a, c) { return (c.dataset.date || '').localeCompare(a.dataset.date || '') || a.dataset.order - c.dataset.order; }
        : function (a, c) { return a.dataset.order - c.dataset.order; });
      cards.forEach(function (c) { grid.appendChild(c); });
    });
  });
})();
