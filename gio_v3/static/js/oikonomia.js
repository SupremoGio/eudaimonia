/* Oikonomia Hub — Design System V2 · pantalla 06.
   Los botones .js-nw-toggle ocultan/muestran las cifras (toggleNetWorth del
   layout guarda la preferencia y sincroniza aria-pressed, ícono y texto). */
(function () {
  'use strict';
  document.querySelectorAll('.js-nw-toggle').forEach(function (b) {
    b.addEventListener('click', function () { toggleNetWorth(); });
  });
  setNetWorthHidden(document.body.classList.contains('nw-hidden'));
})();
