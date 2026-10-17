/* EUDAIMONIA — Level-up (único uso de eu-celebrate.js, DS V2 · Motion).
   Scrim 360 ms → eyebrow → nombre con tracking que se cierra (.32em→.12em,
   1.2 s) → cita. Se descarta al tocar, con Esc o Enter. Estilos: bloque
   «MOTION» de components.css (.eu-lvlup). El resto de coreografías (XP,
   logro, confirm, toast) está en eu-motion.js.

   - euLevelUp({ level, level_name, level_subtitle })  muestra la ceremonia.
   - euCheckLevel(stats)  compara el nivel de /api/xp (o de gam.stats) con
     el último visto en este navegador y dispara euLevelUp si subió. La
     primera vez solo guarda el nivel: no se celebra un nivel ya existente. */
(function () {
  'use strict';
  var KEY = 'eu-level-seen';
  var open = false;

  function quoteOf(sub) {
    // LEVEL_SUBTITLES: «El autosuficiente — dueño de ti mismo» → «Dueño de ti mismo.»
    var s = String(sub || '').split('—').pop().trim();
    if (!s) return '';
    return '«' + s.charAt(0).toUpperCase() + s.slice(1) + '.»';
  }

  window.euLevelUp = function (o) {
    if (open) return;
    o = o || {};
    open = true;
    var opener = document.activeElement;
    var sc = document.createElement('div');
    sc.className = 'eu-lvlup';
    sc.setAttribute('role', 'dialog');
    sc.setAttribute('aria-modal', 'true');
    sc.setAttribute('aria-labelledby', 'eu-lvlup-name');
    sc.innerHTML =
      '<div class="eu-lvlup-in" tabindex="-1">' +
        '<div class="t-eyebrow">Subiste de nivel · Nivel ' + (Number(o.level) || '') + '</div>' +
        '<h2 class="eu-lvlup-name" id="eu-lvlup-name"></h2>' +
        '<p class="t-quote"></p>' +
        '<div class="t-meta eu-lvlup-hint">Toca para continuar</div>' +
      '</div>';
    sc.querySelector('.eu-lvlup-name').textContent = String(o.level_name || '');
    sc.querySelector('.t-quote').textContent = quoteOf(o.level_subtitle);
    document.body.appendChild(sc);
    var prevOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    var inner = sc.querySelector('.eu-lvlup-in');
    setTimeout(function () { inner.focus(); }, 30);

    var reduced = window.euMotion ? window.euMotion.reduced() : false;
    function close() {
      if (!open) return;
      open = false;
      document.removeEventListener('keydown', onKey, true);
      sc.classList.add('is-leaving');
      setTimeout(function () {
        sc.remove();
        document.documentElement.style.overflow = prevOverflow;
        if (opener && opener.focus && document.contains(opener)) opener.focus();
      }, reduced ? 0 : 220);
    }
    function onKey(e) {
      if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); close(); }
      else if (e.key === 'Tab') { e.preventDefault(); inner.focus(); }
    }
    sc.addEventListener('click', close);
    document.addEventListener('keydown', onKey, true);
  };

  window.euCheckLevel = function (s) {
    if (!s || !s.level) return;
    var lvl = Number(s.level), seen = null;
    try { seen = parseInt(localStorage.getItem(KEY), 10); } catch (e) { /* sin storage */ }
    try { localStorage.setItem(KEY, String(lvl)); } catch (e) { /* sin storage */ }
    if (seen && lvl > seen) window.euLevelUp(s);
  };
})();
