/* Oikonomia Hub — Oikonomia v2.
   El botón .js-nw-toggle de la topbar oculta/muestra las cifras (toggleNetWorth del
   layout guarda la preferencia y sincroniza aria-pressed, ícono y texto). */
(function () {
  'use strict';
  document.querySelectorAll('.js-nw-toggle').forEach(function (b) {
    b.addEventListener('click', function () { toggleNetWorth(); });
  });
  setNetWorthHidden(document.body.classList.contains('nw-hidden'));

  // «Siguiente paso» → Marcar pagado (POST /finanzas/api/pago-ciclo). Al
  // resolverlo se recarga: el héroe propone el siguiente pendiente y la
  // tarjeta sale de los avisos y del total de mínimos.
  document.querySelectorAll('.js-pago').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (btn.disabled) return;
      btn.disabled = true; btn.setAttribute('aria-busy', 'true');
      fetch('/finanzas/api/pago-ciclo', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cuenta: btn.dataset.cuenta, monto: btn.dataset.monto || null }),
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok) throw new Error(j.error || '');
        btn.classList.add('is-done'); btn.removeAttribute('aria-busy');
        btn.querySelector('span').textContent = 'Pagado';
        toast('Pago marcado', 'ok');
        setTimeout(function () { location.reload(); }, 700);
      }).catch(function (e) {
        btn.disabled = false; btn.removeAttribute('aria-busy');
        toast(e.message || 'No se pudo marcar el pago', 'err');
      });
    });
  });
})();
