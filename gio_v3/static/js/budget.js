/* Presupuesto 50-30-20 — Design System V2: ingreso manual, editor de límite
   por categoría y drill-down de movimientos con edición inline. */
(function () {
  'use strict';
  var root = document.getElementById('bg');
  if (!root) return;
  var MES = root.dataset.mes;
  var CATS = ['ALIMENTACION', 'CAFE/PAN', 'VIVIENDA', 'TRANSPORTE', 'SALUD', 'CUIDADO_PERSONAL', 'ROPA', 'DIGITAL', 'DEPORTE', 'OCIO', 'SALSA', 'VIAJES',
    'FAMILIA_REGALOS', 'PROYECTOS', 'COSTOS_FINANCIEROS', 'APRENDIZAJE', 'OTROS', 'EXPENSE', 'INVERSION', 'PAGO_TDC', 'TRANSFERENCIA', 'SPEI_ENVIADO', 'RETIRO'];
  var ddCat = null, changed = false;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function fmt(n) { return Number(n || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 }); }
  function post(u, b, m) { return fetch(u, { method: m || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); }

  /* ── Ingreso manual ─────────────────────────────────────────────────── */
  var fi = $('f-ingreso');
  if (fi) fi.addEventListener('submit', function (e) {
    e.preventDefault();
    var v = parseFloat($('ingreso-manual-input').value);
    if (!v || v <= 0) { toast('Ingresa un monto válido', 'err'); $('ingreso-manual-input').focus(); return; }
    post('/finanzas/budget/api/ingreso', { mes: MES, ingreso_total: v }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok) { toast('Ingreso guardado', 'win'); setTimeout(function () { location.reload(); }, 600); } else toast('Error al guardar', 'err');
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Límite por categoría ───────────────────────────────────────────── */
  root.addEventListener('click', function (e) {
    var l = e.target.closest('[data-lim]');
    if (l) {
      $('lim-cat').value = l.dataset.lim; $('lim-nombre').value = l.dataset.nombre;
      $('lim-cat-label').textContent = 'Presupuesto mensual de ' + l.dataset.nombre;
      $('lim-valor').value = +l.dataset.val > 0 ? l.dataset.val : '';
      euModal.open('m-limite'); setTimeout(function () { $('lim-valor').focus(); }, 20);
      return;
    }
    var d = e.target.closest('[data-dd]'); if (d) openDD(d);
  });
  $('f-limite').addEventListener('submit', function (e) {
    e.preventDefault();
    var v = parseFloat($('lim-valor').value);
    if (!v || v <= 0) { toast('Ingresa un monto válido', 'err'); $('lim-valor').focus(); return; }
    post('/finanzas/estados/api/budgets', { categoria: $('lim-cat').value, nombre: $('lim-nombre').value, limite: v }).then(function (r) {
      if (!r.ok) { toast('Error al guardar', 'err'); return; }
      euModal.close('m-limite'); toast('Límite guardado', 'win'); setTimeout(function () { location.reload(); }, 600);
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Drill-down ─────────────────────────────────────────────────────── */
  function openDD(btn) {
    ddCat = btn.dataset.dd; changed = false;
    $('m-dd-t').textContent = btn.dataset.nombre;
    $('dd-body').innerHTML = '<p class="t-meta">Cargando movimientos…</p>';
    $('dd-footer-n').textContent = ''; $('dd-footer-total').textContent = '';
    euModal.open('m-dd');
    fetch('/finanzas/budget/api/cat-movs/' + MES + '/' + encodeURIComponent(ddCat)).then(function (r) { return r.json(); })
      .then(function (d) { render(d.movimientos || []); })
      .catch(function () { $('dd-body').innerHTML = '<p class="t-meta fg-danger">Error al cargar</p>'; });
  }
  function render(movs) {
    if (!movs.length) {
      $('dd-body').innerHTML = '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="receipt"></i></div><div class="t-card">Sin movimientos</div><p>Esta categoría no tiene movimientos registrados en ' + esc(MES) + '.</p></div>';
      icons(); footer(); return;
    }
    $('dd-body').innerHTML = '<ul class="bg-movs">' + movs.map(function (m) {
      return '<li class="bg-mov" id="mov-row-' + m.id + '" data-monto="' + m.mi_monto + '">' +
        '<button type="button" class="bg-mov-sum" data-toggle="' + m.id + '" aria-expanded="false" aria-controls="mov-edit-' + m.id + '">' +
        '<span class="t-meta num bg-mov-f">' + esc(m.fecha.slice(5)) + '</span><span class="eu-grow bg-mov-d" title="' + esc(m.descripcion) + '">' + esc(m.descripcion) + '</span>' +
        '<span class="eu-badge bg-mov-c">' + esc(m.categoria) + '</span><span class="t-data bg-mov-m">$' + fmt(m.mi_monto) + '</span><i data-lucide="chevron-down" class="bg-mov-chev"></i></button>' +
        '<form class="bg-mov-edit" id="mov-edit-' + m.id + '" data-save="' + m.id + '" hidden novalidate><div class="eu-grid-2 bg-me-grid">' +
        '<div class="eu-field"><label class="eu-label" for="me-cat-' + m.id + '">Categoría</label><select class="eu-select" id="me-cat-' + m.id + '">' +
        CATS.map(function (c) { return '<option value="' + c + '"' + (c === m.categoria ? ' selected' : '') + '>' + c + '</option>'; }).join('') + '</select></div>' +
        '<div class="eu-field"><label class="eu-label" for="me-desc-' + m.id + '">Descripción</label><input class="eu-input" id="me-desc-' + m.id + '" value="' + esc(m.descripcion) + '" maxlength="200"></div></div>' +
        '<div class="bg-me-act"><button type="button" class="eu-btn eu-btn--ghost eu-btn--sm" data-toggle="' + m.id + '">Cancelar</button><button type="submit" class="eu-btn eu-btn--primary eu-btn--sm">Guardar</button></div></form></li>';
    }).join('') + '</ul>';
    icons(); footer();
  }
  function footer() {
    var rows = $$('#dd-body .bg-mov'), total = rows.reduce(function (s, r) { return s + (+r.dataset.monto || 0); }, 0);
    $('dd-footer-n').textContent = rows.length ? rows.length + ' movimiento' + (rows.length !== 1 ? 's' : '') : '';
    $('dd-footer-total').textContent = rows.length ? '$' + fmt(total) : '';
  }
  $('dd-body').addEventListener('click', function (e) {
    var t = e.target.closest('[data-toggle]'); if (!t) return;
    var id = t.dataset.toggle, f = $('mov-edit-' + id), sum = document.querySelector('.bg-mov-sum[data-toggle="' + id + '"]');
    f.hidden = !f.hidden; sum.setAttribute('aria-expanded', String(!f.hidden));
    $('mov-row-' + id).classList.toggle('is-open', !f.hidden);
    if (!f.hidden) $('me-cat-' + id).focus(); else sum.focus();
  });
  $('dd-body').addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target.closest('[data-save]'); if (!f) return;
    var id = f.dataset.save, cat = $('me-cat-' + id).value, desc = $('me-desc-' + id).value.trim(), btn = f.querySelector('[type=submit]');
    btn.disabled = true;
    post('/finanzas/budget/api/mov/' + id, { categoria: cat, descripcion: desc }, 'PATCH').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast(d.error || 'Error', 'err'); return; }
      toast('Guardado', 'win'); changed = true;
      var row = $('mov-row-' + id);
      if (cat !== ddCat) { row.remove(); footer(); var chip = document.querySelector('#cat-' + CSS.escape(ddCat) + ' .bg-cat-n'); if (chip) chip.textContent = $$('#dd-body .bg-mov').length + ' mov'; }
      else {
        row.querySelector('.bg-mov-c').textContent = cat; row.querySelector('.bg-mov-d').textContent = desc;
        f.hidden = true; row.classList.remove('is-open'); row.querySelector('.bg-mov-sum').setAttribute('aria-expanded', 'false');
      }
    }).catch(function () { toast('Error de red', 'err'); }).finally(function () { btn.disabled = false; });
  });
  // Si se reclasificó algo, los totales de los buckets cambian: recargar al cerrar.
  new MutationObserver(function () {
    if ($('m-dd').hidden && changed) { changed = false; location.reload(); }
  }).observe($('m-dd'), { attributes: true, attributeFilter: ['hidden'] });
})();
