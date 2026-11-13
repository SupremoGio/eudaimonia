/* eu-dialog.js — Un solo manejo de diálogos (handoff A11y + catálogo, S2).

   euDialog.open(el, trigger, opts) / euDialog.close(el) / euDialog.top()

   Lo que garantiza para todo modal y toda hoja (ui.modal vía euModal, hoja
   de Módulos, ⌘K, captura rápida, panel de avisos, panel de plantas):
     · role="dialog" (o el alertdialog que ya tenga), aria-modal y
       aria-labelledby apuntando a su título (si falta, usa el primer
       h1–h3 / .t-section y le pone id);
     · foco inicial (opts.focus, o el primer campo, o el primer control);
     · foco atrapado con Tab / Shift+Tab;
     · Esc cierra el de arriba (opts.onEscape puede manejarlo antes: si
       devuelve true, no se cierra);
     · clic en el fondo cierra si opts.scrimClose (el `el` es el fondo);
     · al cerrar, el foco regresa al disparador y su aria-expanded vuelve a false.

   opts: {box, focus (elemento, selector o false), scrimClose, modal (default true), lock (default =modal),
          onEscape(), onClose()} */
(function () {
  'use strict';
  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  var stack = [], uid = 0;

  function visibles(el) {
    return [].slice.call(el.querySelectorAll(FOCUSABLE)).filter(function (n) {
      return n.offsetParent !== null || n === document.activeElement;
    });
  }
  function caja(el, opts) {
    if (opts.box) return opts.box;
    if (el.matches && el.matches('[role=dialog],[role=alertdialog]')) return el;
    return el.querySelector('[role=dialog],[role=alertdialog]') || el;
  }
  function nombrar(box, modal) {
    if (!box.getAttribute('role')) box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', modal ? 'true' : 'false');
    if (box.hasAttribute('aria-labelledby') || box.hasAttribute('aria-label')) return;
    var t = box.querySelector('h1,h2,h3,.t-section,.eu-modal-t');
    if (t) { if (!t.id) t.id = 'eu-dlg-t-' + (++uid); box.setAttribute('aria-labelledby', t.id); }
  }
  function entrada(el) { for (var i = stack.length - 1; i >= 0; i--) if (stack[i].el === el) return i; return -1; }
  function bloqueo() {
    document.documentElement.style.overflow = stack.some(function (s) { return s.lock; }) ? 'hidden' : '';
  }

  function open(el, trigger, opts) {
    if (!el || entrada(el) >= 0) return;
    opts = opts || {};
    var modal = opts.modal !== false;
    var box = caja(el, opts);
    nombrar(box, modal);
    var s = { el: el, box: box, trigger: trigger || document.activeElement, opts: opts, modal: modal,
              lock: opts.lock !== undefined ? opts.lock : modal };
    stack.push(s);
    el.hidden = false;
    if (s.trigger && s.trigger.hasAttribute && s.trigger.hasAttribute('aria-expanded')) s.trigger.setAttribute('aria-expanded', 'true');
    bloqueo();
    if (opts.scrimClose && !el._euDlgScrim) {
      el._euDlgScrim = true;
      el.addEventListener('mousedown', function (e) { if (e.target === el && entrada(el) >= 0) close(el); });
    }
    if (opts.focus !== false) setTimeout(function () {       // focus:false → el módulo pone el foco
      if (entrada(el) < 0) return;
      var f = opts.focus;
      if (typeof f === 'string') f = box.querySelector(f);
      if (!f) { var v = visibles(box); f = v.filter(function (n) { return /INPUT|SELECT|TEXTAREA/.test(n.tagName); })[0] || v[0]; }
      if (f && f.focus) f.focus();
    }, 10);
  }

  function close(el, o) {
    var i = entrada(el); if (i < 0) return;
    var s = stack.splice(i, 1)[0];
    el.hidden = true;
    if (s.trigger && s.trigger.hasAttribute && s.trigger.hasAttribute('aria-expanded')) s.trigger.setAttribute('aria-expanded', 'false');
    bloqueo();
    if (s.opts.onClose) s.opts.onClose();
    if (!(o && o.noFocus) && s.trigger && s.trigger.focus && document.contains(s.trigger)) s.trigger.focus();
  }

  document.addEventListener('keydown', function (e) {
    var s = stack[stack.length - 1]; if (!s) return;
    if (e.key === 'Escape') {
      if (e.defaultPrevented) return;                 // ya lo manejó un control interno
      if (s.opts.onEscape && s.opts.onEscape(e) === true) { e.preventDefault(); return; }
      e.preventDefault(); close(s.el); return;
    }
    if (e.key !== 'Tab' || !s.modal) return;
    var f = visibles(s.box); if (!f.length) return;
    var a = f[0], z = f[f.length - 1], act = document.activeElement;
    if (!s.box.contains(act)) { e.preventDefault(); (e.shiftKey ? z : a).focus(); return; }
    if (e.shiftKey && act === a) { e.preventDefault(); z.focus(); }
    else if (!e.shiftKey && act === z) { e.preventDefault(); a.focus(); }
  });

  window.euDialog = { open: open, close: close, top: function () { var s = stack[stack.length - 1]; return s ? s.el : null; },
                      isOpen: function (el) { return entrada(el) >= 0; } };
})();
