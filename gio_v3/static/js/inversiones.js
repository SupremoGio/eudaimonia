/* Inversiones — Design System V2: registrar / eliminar movimientos y ocultar cifras. */
(function () {
  'use strict';
  var root = document.getElementById('iv');
  if (!root) return;
  function $(id) { return document.getElementById(id); }
  document.querySelectorAll('.js-nw-toggle').forEach(function (b) { b.addEventListener('click', function () { toggleNetWorth(); }); });
  setNetWorthHidden(document.body.classList.contains('nw-hidden'));

  document.querySelectorAll('.js-new').forEach(function (b) {
    b.addEventListener('click', function () {
      $('inv-monto').value = ''; $('inv-desc').value = '';
      euModal.open('m-inv'); setTimeout(function () { $('inv-monto').focus(); }, 20);
    });
  });
  $('f-inv').addEventListener('submit', function (e) {
    e.preventDefault();
    var monto = parseFloat($('inv-monto').value);
    if (!monto || monto <= 0) { toast('Ingresa un monto válido', 'err'); $('inv-monto').focus(); return; }
    var btn = document.querySelector('[form="f-inv"]'); btn.disabled = true;
    fetch('/finanzas/inversiones/api/mov', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fecha: $('inv-fecha').value, plataforma: $('inv-plat').value, direccion: $('inv-dir').value, monto: monto, descripcion: $('inv-desc').value }),
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast(d.error || 'Error', 'err'); btn.disabled = false; return; }
      euModal.close('m-inv'); toast('Movimiento guardado', 'ok');
      setTimeout(function () { location.reload(); }, 700);
    }).catch(function () { toast('Sin conexión', 'err'); btn.disabled = false; });
  });
  $('f-adj').addEventListener('submit', function (e) {
    e.preventDefault();
    var v = parseFloat($('adj-saldo').value);
    if (isNaN(v) || v < 0) { toast('Ingresa un saldo válido', 'err'); $('adj-saldo').focus(); return; }
    fetch('/finanzas/inversiones/api/saldo', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plataforma: $('adj-plat').value, saldo: v }),
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast(d.error || 'Error', 'err'); return; }
      euModal.close('m-adj'); toast('Saldo ajustado', 'ok');
      setTimeout(function () { location.reload(); }, 600);
    }).catch(function () { toast('Sin conexión', 'err'); });
  });
  root.addEventListener('click', function (e) {
    var a = e.target.closest('[data-adj]');
    if (a) {
      $('adj-plat').value = a.dataset.adj;
      $('adj-l').textContent = 'Saldo real de ' + a.dataset.label + ' hoy (MXN)';
      $('adj-saldo').value = (+a.dataset.saldo).toFixed(2);
      euModal.open('m-adj'); setTimeout(function () { $('adj-saldo').select(); }, 20);
      return;
    }
    var b = e.target.closest('[data-del]'); if (!b) return;
    euConfirm('¿Eliminar este movimiento?', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      fetch('/finanzas/inversiones/api/mov/' + b.dataset.del, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast(d.error || 'Error', 'err'); return; }
        toast('Eliminado', 'ok');
        // Los totales dependen del movimiento: se recarga para recalcularlos.
        setTimeout(function () { location.reload(); }, 500);
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  });
})();
