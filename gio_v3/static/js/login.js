/* Login — Design System V2 · pantalla 01.
   Modo «login» (POST /login) o «setup» la primera vez (POST /login/setup).
   Remates · Login S1: mínimo de 8 con contador «N de 8», coincidencia
   validada en el segundo campo mientras se escribe, mostrar/ocultar
   (aria-pressed), busy en el botón y cuenta regresiva con el 429. */
(function () {
  'use strict';
  var form = document.getElementById('au-form');
  if (!form) return;
  var setup = form.dataset.mode === 'setup';
  var pw = document.getElementById('au-pw'), pw2 = document.getElementById('au-pw2');
  var err = document.getElementById('au-err'), btn = document.getElementById('au-submit');
  var lbl = btn.querySelector('.au-lbl'), lblTxt = lbl.textContent;
  var count = document.getElementById('au-pw-n'), err2 = document.getElementById('au-err2');
  var MIN = count ? parseInt(count.dataset.min, 10) || 8 : 0;
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  var bloqueo = null;

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
    if (pw) pw.removeAttribute('aria-invalid');
  }

  // ── Alta: contador y coincidencia en vivo ──
  function contar() {
    if (!count) return;
    var n = pw.value.length;
    count.textContent = Math.min(n, 64) + ' de ' + MIN;
    count.classList.toggle('is-ok', n >= MIN);
  }
  // El error aparece en el segundo campo en cuanto ya no puede coincidir
  // (lo escrito no es el inicio de la primera) o cuando sale del campo.
  function coincide(final) {
    if (!pw2 || !err2) return true;
    var a = pw.value, b = pw2.value;
    var mal = !!b && (final ? a !== b : a.indexOf(b) !== 0);
    err2.hidden = !mal;
    if (mal) pw2.setAttribute('aria-invalid', 'true'); else pw2.removeAttribute('aria-invalid');
    return !(b && a !== b) && (!final || a === b);
  }
  pw.addEventListener('input', function () { clearErr(); contar(); if (pw2 && pw2.value) coincide(false); });
  if (pw2) {
    pw2.addEventListener('input', function () { clearErr(); coincide(false); });
    pw2.addEventListener('blur', function () { if (pw2.value) coincide(true); });
  }
  contar();

  // ── Mostrar u ocultar ──
  form.querySelectorAll('[data-eye]').forEach(function (b) {
    b.addEventListener('click', function () {
      var input = document.getElementById(b.dataset.eye);
      var ver = input.type === 'password';
      input.type = ver ? 'text' : 'password';
      b.setAttribute('aria-pressed', ver ? 'true' : 'false');
      b.innerHTML = '<i data-lucide="' + (ver ? 'eye-off' : 'eye') + '"></i>';
      if (window.lucide) lucide.createIcons({ nodes: [b] });
      input.focus();
    });
  });

  // ── Bloqueo por intentos: «Espera N s» con el botón deshabilitado ──
  function bloquear(seg) {
    clearInterval(bloqueo);
    var fin = Date.now() + seg * 1000;
    btn.disabled = true;
    function tick() {
      var s = Math.ceil((fin - Date.now()) / 1000);
      if (s <= 0) {
        clearInterval(bloqueo); bloqueo = null;
        btn.disabled = false; lbl.textContent = lblTxt; err.hidden = true;
        pw.focus();
        return;
      }
      lbl.textContent = 'Espera ' + s + ' s';
      err.querySelector('span').textContent = 'Demasiados intentos. Espera ' + s + ' s.';
    }
    tick();
    bloqueo = setInterval(tick, 1000);
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (btn.getAttribute('aria-busy') === 'true' || btn.disabled) return;
    var p1 = pw.value;
    if (!p1) { showErr(setup ? 'Ingresa una contraseña' : 'Escribe tu contraseña'); return; }
    if (setup) {
      if (p1.length < MIN) { showErr('Mínimo ' + MIN + ' caracteres'); return; }
      if (!pw2.value) { showErr('Confirma la contraseña', pw2); return; }
      if (!coincide(true)) { pw2.focus(); return; }
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
      if (r.status === 429) {
        var seg = parseInt(d.retry_after || r.headers.get('Retry-After'), 10) || 60;
        btn.removeAttribute('aria-busy');
        showErr('Demasiados intentos. Espera ' + seg + ' s.');
        bloquear(seg);
        return;
      }
      showErr(d.error || 'No se pudo entrar');
    } catch (_) {
      showErr('Sin conexión. Inténtalo de nuevo.');
    }
    btn.removeAttribute('aria-busy');
  });
})();
