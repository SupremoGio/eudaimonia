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

  // Bottom sheet de recompensa (logro desbloqueado, bono variable...) —
  // port vanilla del ComboBonusSheet de eu-components.jsx, mismo lenguaje
  // visual (barra de cuenta regresiva, icono, auto-dismiss a los 4s).
  // opts: { eyebrow, title, desc, icon }
  window.euRewardSheet = function (opts) {
    opts = opts || {};
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var backdrop = document.createElement('div');
    backdrop.setAttribute('role', 'status');
    backdrop.setAttribute('aria-live', 'polite');
    backdrop.style.cssText =
      'position:fixed;inset:0;z-index:997;display:flex;align-items:flex-end;' +
      'justify-content:center;background:color-mix(in srgb, var(--bg) 60%, transparent);' +
      (reduced ? '' : 'animation:euFadeIn .25s ease;');

    var sheet = document.createElement('div');
    sheet.style.cssText =
      'position:relative;background:linear-gradient(180deg, var(--surf), var(--bg));' +
      'border:1px solid var(--gold-border, rgba(201,168,76,.18));border-top-left-radius:20px;border-top-right-radius:20px;' +
      'padding:24px 22px;width:100%;max-width:420px;overflow:hidden;' +
      'box-shadow:0 -12px 40px color-mix(in srgb, var(--bg) 50%, black);' +
      (reduced ? '' : 'animation:euAchievementRise .4s ease-out;');
    sheet.addEventListener('click', function (e) { e.stopPropagation(); });

    var bar = document.createElement('div');
    bar.style.cssText =
      'position:absolute;top:0;left:0;right:0;height:2px;background:var(--gold);' +
      'border-radius:2px 2px 0 0;' + (reduced ? '' : 'animation:undoCountdown 4s linear forwards;');
    sheet.appendChild(bar);

    var row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:14px;';
    row.innerHTML =
      '<div style="font-size:36px;line-height:1;display:flex;filter:drop-shadow(0 0 12px var(--gold-glow, rgba(201,168,76,.45)));">' +
        (opts.icon ? '<i data-lucide="' + opts.icon + '" style="width:36px;height:36px;color:var(--gold);" stroke-width="1.5"></i>' : '') +
      '</div>' +
      '<div style="flex:1;min-width:0;">' +
        '<div style="font-size:10px;letter-spacing:.2em;color:var(--gold);opacity:.7;text-transform:uppercase;margin-bottom:3px;font-family:var(--sans,\'DM Sans\',sans-serif);">' + (opts.eyebrow || '') + '</div>' +
        '<div style="font-family:var(--serif,\'Cormorant Garamond\',serif);font-size:20px;font-weight:600;color:var(--text);letter-spacing:.03em;">' + (opts.title || '') + '</div>' +
        (opts.desc ? '<div style="font-size:12px;color:var(--mid);margin-top:3px;">' + opts.desc + '</div>' : '') +
      '</div>';
    sheet.appendChild(row);
    backdrop.appendChild(sheet);
    document.body.appendChild(backdrop);
    if (window.lucide) lucide.createIcons();

    // Momentos de mayor peso (logro/insignia desbloqueada) piden más chispa
    // que el resto de refuerzos (bono de racha, etc): el ícono hace pop y
    // dispara el mismo burst de partículas que ya usa HabitRow, esta vez
    // desde el ícono del sheet en vez de un checkbox.
    if (opts.burst && !reduced) {
      var iconWrap = row.firstElementChild;
      if (iconWrap) {
        iconWrap.style.animation = 'euIconPop 0.5s cubic-bezier(.2,1.4,.4,1)';
        window.euCelebrate(iconWrap);
      }
    }

    var close = function () { backdrop.remove(); };
    backdrop.addEventListener('click', close);
    setTimeout(close, 4000);
  };

  // Muchos endpoints (completar tarea GTD, bonos de prioridad/rutina...)
  // ya devuelven `gam.achievements` con los logros recién desbloqueados
  // (engine.check_and_unlock) pero hasta ahora ninguna pantalla lo leía
  // — el usuario nunca se enteraba de un logro nuevo salvo que visitara
  // /logros por su cuenta. Esto lo anuncia con el mismo lenguaje visual
  // que el resto de refuerzos.
  window.euAnnounceAchievements = function (gam) {
    if (!gam || !Array.isArray(gam.achievements) || !gam.achievements.length) return;
    var first = gam.achievements[0];
    var extra = gam.achievements.length - 1;
    window.euRewardSheet({
      icon: first.icon_lucide || 'trophy',
      eyebrow: 'Logro desbloqueado' + (extra > 0 ? ` · +${extra} más` : ''),
      title: first.name,
      desc: first.description + (first.xp ? ` · +${first.xp} XP` : '') + (first.coins ? ` · +${first.coins} EC` : ''),
      burst: true,
    });
  };
})();
