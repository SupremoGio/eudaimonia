/* Logros (/logros) — handoff Logros v2. Todo viene renderizado por el
   servidor; aquí solo los filtros sin recargar:
   · Colección: Todos / Ganados / Bloqueados.
   · Historial: chips de fuente (?fuente= en la URL) y «Cargar más» por días. */
(function () {
  'use strict';
  var root = document.querySelector('.lg');
  if (!root) return;
  function $$(s, el) { return [].slice.call((el || document).querySelectorAll(s)); }
  function press(btns, on) { btns.forEach(function (b) { b.setAttribute('aria-pressed', String(b === on)); }); }

  /* ── Colección: estado ── */
  var chips = $$('[data-status]', root), collEmpty = root.querySelector('.js-coll-empty');
  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      root.dataset.status = c.dataset.status;
      press(chips, c);
      if (collEmpty) collEmpty.hidden = $$('.lg-item', root).some(function (a) { return a.offsetParent !== null; });
      if (collEmpty && !collEmpty.hidden && window.euSetDrop) {
        var todos = chips.filter(function (x) { return !x.dataset.status || x.dataset.status === 'todos' || x.dataset.status === 'all'; })[0];
        euSetDrop(collEmpty, euChipLabel(c), $$('.lg-item', root).length, function () { if (todos) todos.click(); });
      }
    });
  });

  /* ── Historial: fuente + «Cargar más» (10 días por página) ── */
  var log = root.querySelector('.lg-log');
  if (!log) return;
  var PAGE = 10, shown = PAGE;
  var src = log.dataset.fuente || '';
  var days = $$('.lg-day-g', log), more = log.querySelector('.js-more'), logEmpty = log.querySelector('.js-log-empty');
  var srcChips = $$('[data-src]', log).filter(function (b) { return b.tagName === 'BUTTON'; });

  function render() {
    var visibles = [];
    days.forEach(function (g) {
      var sum = 0, n = 0;
      $$('.lg-log-row', g).forEach(function (r) {
        var ok = !src || r.dataset.src === src;
        r.hidden = !ok;
        if (ok) { sum += +r.dataset.amt; n++; }
      });
      g.querySelector('.js-day-sum').textContent = (sum > 0 ? '+' : '') + sum + ' XP';
      g.hidden = true;
      if (n) visibles.push(g);
    });
    visibles.slice(0, shown).forEach(function (g) { g.hidden = false; });
    if (more) more.hidden = visibles.length <= shown;
    if (logEmpty) logEmpty.hidden = visibles.length > 0;
    if (logEmpty && !visibles.length && src && window.euSetDrop) {
      var on = srcChips.filter(function (b) { return b.dataset.src === src; })[0];
      euSetDrop(logEmpty, euChipLabel(on, src), days.length, function () {
        var all = srcChips.filter(function (b) { return !b.dataset.src; })[0]; if (all) all.click();
      });
    }
  }
  srcChips.forEach(function (b) {
    b.addEventListener('click', function () {
      src = b.dataset.src; shown = PAGE; press(srcChips, b);
      try {
        var u = new URL(location.href);
        if (src) u.searchParams.set('fuente', src); else u.searchParams.delete('fuente');
        history.replaceState(null, '', u.pathname + u.search);
      } catch (_) {}
      render();
    });
  });
  if (more) more.addEventListener('click', function () { shown += PAGE; render(); });
  render();
})();
