/* Patrimonio (salud financiera) — Design System V2: cuentas, bienes, deudas
   personales, abonos, registro diario del patrimonio y ocultar cifras. */
(function () {
  'use strict';
  var root = document.getElementById('pt');
  if (!root) return;
  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function send(u, m, b) { return fetch(u, { method: m, headers: { 'Content-Type': 'application/json' }, body: b === undefined ? undefined : JSON.stringify(b) }).then(function (r) { return r.json(); }); }
  function setErr(id, msg) { var e = $(id); e.hidden = !msg; e.querySelector('span').textContent = msg || ''; }
  function reload(ms) { setTimeout(function () { location.reload(); }, ms || 400); }
  function open(id, focus) { euModal.open(id); if (focus) setTimeout(function () { $(focus).focus(); }, 20); }
  function busy(form, on) { var b = document.querySelector('[form="' + form + '"]'); if (b) b.disabled = on; }

  document.querySelectorAll('.js-nw-toggle').forEach(function (b) { b.addEventListener('click', function () { toggleNetWorth(); }); });
  setNetWorthHidden(document.body.classList.contains('nw-hidden'));

  /* ── Cuentas ────────────────────────────────────────────────────────── */
  function fillCuenta(c) {
    c = c || {};
    $('mc-id').value = c.id || ''; $('m-cuenta-t').textContent = c.id ? 'Editar cuenta' : 'Agregar cuenta';
    $('mc-nombre').value = c.nombre || ''; $('mc-tipo').value = c.tipo || 'cuenta_banco'; $('mc-inst').value = c.institucion || '';
    $('mc-saldo').value = c.saldo == null ? '' : c.saldo; $('mc-moneda').value = c.moneda || 'MXN'; $('mc-notas').value = c.notas || '';
    setErr('mc-err', ''); open('m-cuenta', 'mc-nombre');
  }
  $('f-m-cuenta').addEventListener('submit', function (e) {
    e.preventDefault();
    var id = $('mc-id').value, nombre = $('mc-nombre').value.trim(), saldo = parseFloat($('mc-saldo').value);
    if (!nombre) { setErr('mc-err', 'Ingresa el nombre.'); $('mc-nombre').focus(); return; }
    if (isNaN(saldo)) { setErr('mc-err', 'Saldo inválido.'); $('mc-saldo').focus(); return; }
    busy('f-m-cuenta', true);
    send(id ? '/finanzas/salud/api/cuenta/' + id : '/finanzas/salud/api/cuenta', id ? 'PATCH' : 'POST', {
      nombre: nombre, tipo: $('mc-tipo').value, institucion: $('mc-inst').value.trim(), saldo: saldo, moneda: $('mc-moneda').value, notas: $('mc-notas').value.trim(),
    }).then(function (d) {
      if (!d.ok) { setErr('mc-err', d.error || 'Error al guardar.'); busy('f-m-cuenta', false); return; }
      euModal.close('m-cuenta'); toast(id ? 'Cuenta actualizada' : 'Cuenta agregada', 'ok'); reload();
    }).catch(function () { setErr('mc-err', 'Sin conexión.'); busy('f-m-cuenta', false); });
  });

  /* ── Bienes ─────────────────────────────────────────────────────────── */
  function fillBien(b) {
    b = b || {};
    $('mb-id').value = b.id || ''; $('m-bien-t').textContent = b.id ? 'Editar bien' : 'Agregar bien personal';
    $('mb-nombre').value = b.nombre || ''; $('mb-categoria').value = b.categoria || 'electrodomestico'; $('mb-descripcion').value = b.descripcion || '';
    $('mb-precio').value = b.id ? b.precio_compra : ''; $('mb-valor').value = b.id ? b.valor_actual : '';
    $('mb-fecha').value = b.fecha_compra || ''; $('mb-lugar').value = b.lugar_compra || ''; $('mb-garantia').value = b.garantia_hasta || ''; $('mb-notas').value = b.notas || '';
    setErr('mb-err', ''); open('m-bien', 'mb-nombre');
  }
  $('f-m-bien').addEventListener('submit', function (e) {
    e.preventDefault();
    var id = $('mb-id').value, nombre = $('mb-nombre').value.trim(), precio = parseFloat($('mb-precio').value) || 0, vr = $('mb-valor').value;
    if (!nombre) { setErr('mb-err', 'Ingresa el nombre.'); $('mb-nombre').focus(); return; }
    busy('f-m-bien', true);
    send(id ? '/finanzas/salud/api/bien/' + id : '/finanzas/salud/api/bien', id ? 'PATCH' : 'POST', {
      nombre: nombre, categoria: $('mb-categoria').value, descripcion: $('mb-descripcion').value.trim(), precio_compra: precio,
      valor_actual: vr !== '' ? parseFloat(vr) : precio, fecha_compra: $('mb-fecha').value, lugar_compra: $('mb-lugar').value.trim(),
      garantia_hasta: $('mb-garantia').value, notas: $('mb-notas').value.trim(),
    }).then(function (d) {
      if (!d.ok) { setErr('mb-err', d.error || 'Error al guardar.'); busy('f-m-bien', false); return; }
      euModal.close('m-bien'); toast(id ? 'Bien actualizado' : 'Bien agregado', 'ok'); reload();
    }).catch(function () { setErr('mb-err', 'Sin conexión.'); busy('f-m-bien', false); });
  });
  $$('[data-bf]').forEach(function (c) {
    c.addEventListener('click', function () {
      var f = c.dataset.bf;
      $$('[data-bf]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      $$('#bienes-grid .pt-bien').forEach(function (b) { b.hidden = !(f === 'todos' || b.dataset.bcat === f); });
    });
  });

  /* ── Deudas ─────────────────────────────────────────────────────────── */
  function setDtype(t) {
    $('md-type').value = t;
    $$('[data-dtype]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.dtype === t)); });
  }
  $$('[data-dtype]').forEach(function (b) { b.addEventListener('click', function () { setDtype(b.dataset.dtype); }); });
  $('f-m-debt').addEventListener('submit', function (e) {
    e.preventDefault();
    var person = $('md-person').value.trim(), amount = parseFloat($('md-amount').value);
    if (!person) { setErr('md-err', 'Ingresa el nombre.'); $('md-person').focus(); return; }
    if (!(amount > 0)) { setErr('md-err', 'Monto inválido.'); $('md-amount').focus(); return; }
    busy('f-m-debt', true);
    send('/finanzas/api/debt', 'POST', { type: $('md-type').value, person: person, concept: $('md-concept').value.trim(), amount: amount }).then(function (d) {
      if (!d.ok) { setErr('md-err', d.error || 'Error al guardar.'); busy('f-m-debt', false); return; }
      euModal.close('m-debt'); toast('Deuda registrada', 'ok'); reload();
    }).catch(function () { setErr('md-err', 'Sin conexión.'); busy('f-m-debt', false); });
  });
  $('f-m-abonar').addEventListener('submit', function (e) {
    e.preventDefault();
    var amount = parseFloat($('ma-amount').value);
    if (!(amount > 0)) { setErr('ma-err', 'Monto inválido.'); $('ma-amount').focus(); return; }
    busy('f-m-abonar', true);
    send('/finanzas/api/debt/' + $('ma-did').value + '/abonar', 'POST', { amount: amount, note: $('ma-note').value.trim() }).then(function (d) {
      if (!d.ok) { setErr('ma-err', d.error || 'Error.'); busy('f-m-abonar', false); return; }
      euModal.close('m-abonar'); toast('Abono registrado', 'ok'); reload();
    }).catch(function () { setErr('ma-err', 'Sin conexión.'); busy('f-m-abonar', false); });
  });

  /* ── Delegación de acciones ─────────────────────────────────────────── */
  function confirmDel(msg, url, okMsg, opts) {
    euConfirm(msg, opts || { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      send(url, (opts && opts.method) || 'DELETE').then(function (d) {
        if (d.ok) { toast(okMsg, 'ok'); reload(); } else toast(d.error || 'Error', 'err');
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  }
  root.addEventListener('click', function (e) {
    var t;
    if ((t = e.target.closest('[data-new-cuenta]'))) { fillCuenta({ tipo: t.dataset.newCuenta }); }
    else if ((t = e.target.closest('[data-edit-cuenta]'))) { fillCuenta(JSON.parse(t.dataset.editCuenta)); }
    else if ((t = e.target.closest('[data-del-cuenta]'))) { confirmDel('¿Eliminar esta cuenta? No se puede deshacer.', '/finanzas/salud/api/cuenta/' + t.dataset.delCuenta, 'Cuenta eliminada'); }
    else if (e.target.closest('.js-new-bien')) { fillBien(null); }
    else if ((t = e.target.closest('[data-edit-bien]'))) { fillBien(JSON.parse(t.dataset.editBien)); }
    else if ((t = e.target.closest('[data-del-bien]'))) { confirmDel('¿Eliminar este bien? No se puede deshacer.', '/finanzas/salud/api/bien/' + t.dataset.delBien, 'Bien eliminado'); }
    else if ((t = e.target.closest('[data-new-debt]'))) {
      setDtype(t.dataset.newDebt); $('md-person').value = ''; $('md-concept').value = ''; $('md-amount').value = ''; setErr('md-err', '');
      open('m-debt', 'md-person');
    }
    else if ((t = e.target.closest('[data-abonar]'))) {
      $('ma-did').value = t.dataset.abonar; $('ma-restante').textContent = '$' + Number(t.dataset.rest).toLocaleString('es-MX', { minimumFractionDigits: 2 });
      $('ma-amount').value = ''; $('ma-note').value = ''; setErr('ma-err', ''); open('m-abonar', 'ma-amount');
    }
    else if ((t = e.target.closest('[data-settle]'))) { confirmDel('¿Marcar como liquidada? Se moverá al historial.', '/finanzas/api/debt/' + t.dataset.settle + '/settle', 'Deuda liquidada', { danger: false, confirmLabel: 'Marcar liquidada', method: 'POST' }); }
    else if ((t = e.target.closest('[data-del-debt]'))) { confirmDel('¿Eliminar esta deuda? No se puede deshacer.', '/finanzas/api/debt/' + t.dataset.delDebt, 'Deuda eliminada'); }
    else if ((t = e.target.closest('.js-snap'))) {
      t.disabled = true;
      send('/finanzas/salud/api/snapshot', 'POST').then(function (d) {
        if (!d.ok) { toast(d.error || 'No se pudo guardar el registro.', 'err'); t.disabled = false; return; }
        toast((d.actualizado ? 'Registro de hoy actualizado' : 'Registro de hoy guardado') + ': $' + d.patrimonio_neto.toLocaleString('es-MX', { minimumFractionDigits: 2 }) + ' MXN', 'win');
        reload(900);
      }).catch(function () { toast('Sin conexión', 'err'); t.disabled = false; });
    }
  });
})();
