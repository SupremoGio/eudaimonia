/* Consumo inteligente — Design System V2: lista con filtros por categoría,
   registrar compra / nuevo producto en modales, y detalle con registro,
   desactivar y borrado de compras. */
(function () {
  'use strict';
  var API = '/finanzas/consumo/api';
  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json(); });
  }
  function reload(ms) { setTimeout(function () { location.reload(); }, ms || 600); }
  function price(id) {
    var v = parseFloat($(id).value);
    if (!v || v <= 0) { toast('Ingresa un precio válido', 'err'); $(id).focus(); return null; }
    return v;
  }

  /* ── Lista ──────────────────────────────────────────────────────────── */
  var list = $('ci');
  if (list) {
    var today = list.dataset.today || new Date().toISOString().slice(0, 10);
    $$('[data-f]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var f = chip.dataset.f, shown = 0;
        $$('[data-f]').forEach(function (c) { c.setAttribute('aria-pressed', String(c === chip)); });
        $$('.ci-card').forEach(function (card) {
          var ok = f === 'all' || (f === '__atrasados' ? card.dataset.status === 'atrasado' : card.dataset.catName === f);
          card.hidden = !ok; if (ok) shown++;
        });
        $('ci-nomatch').hidden = shown > 0 || !$$('.ci-card').length;
      });
    });
    $$('.js-nuevo').forEach(function (b) {
      b.addEventListener('click', function () {
        $('nuevo-nombre').value = ''; $('nuevo-cat').value = '';
        euModal.open('m-nuevo'); setTimeout(function () { $('nuevo-nombre').focus(); }, 20);
      });
    });
    list.addEventListener('click', function (e) {
      var b = e.target.closest('[data-reg]'); if (!b) return;
      $('reg-pid').value = b.dataset.reg; $('reg-nombre').textContent = b.dataset.nombre;
      $('reg-fecha').value = today; $('reg-precio').value = ''; $('reg-cantidad').value = '1';
      euModal.open('m-reg'); setTimeout(function () { $('reg-precio').focus(); }, 20);
    });
    $('f-reg').addEventListener('submit', function (e) {
      e.preventDefault();
      var p = price('reg-precio'); if (p === null) return;
      post(API + '/compra', { producto_id: +$('reg-pid').value, fecha: $('reg-fecha').value, precio_total: p, cantidad: parseFloat($('reg-cantidad').value) || 1 })
        .then(function (d) {
          if (d.error) { toast(d.error, 'err'); return; }
          euModal.close('m-reg'); toast('Compra registrada', 'win'); reload(700);
        }).catch(function () { toast('Sin conexión', 'err'); });
    });
    $('f-nuevo').addEventListener('submit', function (e) {
      e.preventDefault();
      var nombre = $('nuevo-nombre').value.trim();
      if (!nombre) { toast('Nombre requerido', 'err'); $('nuevo-nombre').focus(); return; }
      post(API + '/producto', { nombre: nombre, categoria: $('nuevo-cat').value.trim() }).then(function (d) {
        if (d.error) { toast(d.error, 'err'); return; }
        euModal.close('m-nuevo'); toast('«' + nombre + '» agregado', 'win'); reload(700);
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  }

  /* ── Detalle ────────────────────────────────────────────────────────── */
  var det = $('ci-det');
  if (det) {
    var pid = +det.dataset.pid;
    $('f-det').addEventListener('submit', function (e) {
      e.preventDefault();
      var p = price('d-precio'); if (p === null) return;
      var btn = this.querySelector('[type=submit]'); btn.disabled = true;
      post(API + '/compra', { producto_id: pid, fecha: $('d-fecha').value, precio_total: p, cantidad: parseFloat($('d-cant').value) || 1 })
        .then(function (d) {
          if (d.error) { toast(d.error, 'err'); btn.disabled = false; return; }
          toast('Compra guardada', 'win'); reload(800);
        }).catch(function () { toast('Sin conexión', 'err'); btn.disabled = false; });
    });
    det.querySelector('.js-desactivar').addEventListener('click', function () {
      euConfirm('¿Desactivar este producto? Puedes reactivarlo desde la base de datos.', { confirmLabel: 'Desactivar' }).then(function (ok) {
        if (!ok) return;
        fetch(API + '/producto/' + pid, { method: 'DELETE' }).then(function () { location.href = '/finanzas/consumo/'; })
          .catch(function () { toast('Sin conexión', 'err'); });
      });
    });
    det.addEventListener('click', function (e) {
      var b = e.target.closest('[data-del]'); if (!b) return;
      euConfirm('¿Eliminar este registro de compra?', { confirmLabel: 'Eliminar' }).then(function (ok) {
        if (!ok) return;
        fetch(API + '/compra/' + b.dataset.del, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
          if (d.error) { toast(d.error, 'err'); return; }
          var row = $('row-' + b.dataset.del); if (row) row.remove();
          toast('Compra eliminada', 'ok'); reload(900);
        }).catch(function () { toast('Sin conexión', 'err'); });
      });
    });
  }
})();
