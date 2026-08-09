// EUDAIMONIA — Refuerzo positivo compartido (vanilla JS)
// Port del burst de partículas de HabitRow (eu-components.jsx) para las
// pantallas Jinja2 que no corren React: GTD, Recompensas, Logros...
// Reutiliza las @keyframes euBurst / euIconPop ya definidas en app.css.
(function () {
  var DIRS = [[28,-28],[38,0],[28,28],[0,38],[-28,28],[-38,0],[-28,-28],[0,-38]];

  // Burst de 8 partículas ancladas a `el` (para completar tarea, canjear
  // recompensa, etc). No requiere que el contenedor tenga position:relative:
  // las partículas se posicionan en position:fixed sobre el viewport.
  window.euCelebrate = function (el, opts) {
    if (!el || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
    opts = opts || {};
    var rect = el.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var layer = document.createElement('div');
    layer.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:9999;pointer-events:none;';
    DIRS.forEach(function (d, i) {
      var p = document.createElement('div');
      p.style.cssText =
        'position:fixed;left:' + cx + 'px;top:' + cy + 'px;' +
        'width:5px;height:5px;border-radius:50%;' +
        'background:' + (opts.color || ('oklch(75% 0.18 ' + (45 + i * 20) + ')')) + ';' +
        'opacity:0;pointer-events:none;' +
        '--dx:' + d[0] + 'px;--dy:' + (d[1] - 10) + 'px;' +
        'animation:euBurst 0.65s ease-out forwards;' +
        'animation-delay:' + (i * 0.02) + 's;';
      layer.appendChild(p);
    });
    document.body.appendChild(layer);
    setTimeout(function () { layer.remove(); }, 750);
  };

  // Pop más grande para momentos de mayor peso (logro desbloqueado,
  // meta cumplida) — un solo elemento con euIconPop, sin partículas.
  window.euCelebrateBig = function (el) {
    if (!el || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
    el.style.animation = 'none';
    // Forzar reflow para poder re-disparar la animación en clics sucesivos
    void el.offsetWidth;
    el.style.animation = 'euIconPop 0.5s cubic-bezier(.2,1.4,.4,1)';
  };
})();
