/* EUDAIMONIA — Accesibilidad compartida (DS V2 · Fase 5).
   - Tabs (role=tablist): patrón WAI-ARIA. Solo la pestaña activa entra en el
     orden de Tab (tabindex itinerante); ←/→ (o ↑/↓ si es vertical), Inicio y
     Fin mueven el foco y activan la pestaña. Funciona con cualquier tablist
     de la app, también los que pinta JS o React, porque se delega en document.
   - El enlace «Saltar al contenido» del layout enfoca <main>. */
(function () {
  'use strict';

  function tabsOf(list) {
    return Array.prototype.filter.call(list.querySelectorAll('[role=tab]'), function (t) {
      return t.closest('[role=tablist]') === list && !t.disabled && t.offsetParent !== null;
    });
  }

  function syncRoving(list) {
    var tabs = tabsOf(list);
    if (!tabs.length) return;
    var sel = tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0] || tabs[0];
    tabs.forEach(function (t) {
      var want = t === sel ? '0' : '-1';
      if (t.getAttribute('tabindex') !== want) t.setAttribute('tabindex', want);
    });
  }
  function syncAll(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll('[role=tablist]'), syncRoving);
  }

  document.addEventListener('keydown', function (e) {
    var tab = e.target.closest && e.target.closest('[role=tab]');
    if (!tab) return;
    var list = tab.closest('[role=tablist]');
    if (!list) return;
    var vertical = list.getAttribute('aria-orientation') === 'vertical';
    var prev = vertical ? 'ArrowUp' : 'ArrowLeft', next = vertical ? 'ArrowDown' : 'ArrowRight';
    if ([prev, next, 'Home', 'End'].indexOf(e.key) === -1) return;
    var tabs = tabsOf(list), i = tabs.indexOf(tab);
    if (i === -1) return;
    e.preventDefault();
    var j = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1
      : e.key === next ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
    tabs[j].focus();
    tabs[j].click(); // activación automática: cada tab ya cambia su panel al hacer clic
    setTimeout(function () { syncRoving(list); }, 0);
  });

  // Mantener el tabindex itinerante al día cuando cambia aria-selected o
  // aparecen tablists nuevos (vistas pintadas por JS/React).
  var pending = false;
  new MutationObserver(function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; syncAll(); });
  }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ['aria-selected'] });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { syncAll(); });
  else syncAll();

  // «Saltar al contenido»: mover el foco de verdad (no solo el scroll).
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('.eu-skip');
    if (!a) return;
    var main = document.getElementById('eu-main');
    if (!main) return;
    e.preventDefault();
    main.focus();
    main.scrollIntoView();
  });
})();
