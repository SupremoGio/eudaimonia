/* Login — Design System V2 · pantalla 01.
   Modo «login» (POST /login) o «setup» la primera vez (POST /login/setup). */
(function () {
  'use strict';
  var form = document.getElementById('au-form');
  if (!form) return;
  var setup = form.dataset.mode === 'setup';
  var pw = document.getElementById('au-pw'), pw2 = document.getElementById('au-pw2');
  var err = document.getElementById('au-err'), btn = document.getElementById('au-submit');
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  function showErr(msg, input) {
    err.querySelector('span').textContent = msg;
    err.hidden = false;
    [pw, pw2].forEach(function (i) { if (i) i.removeAttribute('aria-invalid'); });
    (input || pw).setAttribute('aria-invalid', 'true');
    (input || pw).focus();
    form.classList.remove('is-shake'); void form.offsetWidth; form.classList.add('is-shake');
  }
  function clearErr() {
    err.hidden = true;
    [pw, pw2].forEach(function (i) { if (i) i.removeAttribute('aria-invalid'); });
  }
  [pw, pw2].forEach(function (i) { if (i) i.addEventListener('input', clearErr); });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (btn.getAttribute('aria-busy') === 'true') return;
    var p1 = pw.value;
    if (!p1) { showErr(setup ? 'Ingresa una contraseña' : 'Escribe tu contraseña'); return; }
    if (setup) {
      if (p1.length < 4) { showErr('Mínimo 4 caracteres'); return; }
      if (p1 !== pw2.value) { showErr('Las contraseñas no coinciden', pw2); return; }
    }
    btn.setAttribute('aria-busy', 'true');
    try {
      var r = await fetch(setup ? '/login/setup' : '/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ password: p1 })
      });
      var d = await r.json().catch(function () { return {}; });
      if (d.ok) { location.href = '/'; return; }
      if (!setup) pw.value = '';
      showErr(d.error || (r.status === 429 ? 'Demasiados intentos. Espera un momento.' : 'No se pudo entrar'));
    } catch (_) {
      showErr('Sin conexión. Inténtalo de nuevo.');
    }
    btn.removeAttribute('aria-busy');
  });
})();
