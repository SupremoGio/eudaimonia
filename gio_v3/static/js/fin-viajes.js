/* Oikonomia · Gastos de viaje — Design System V2: lista de viajes con avance
   del presupuesto y detalle (desglose por concepto, sugerencias para vincular
   movimientos de los estados de cuenta y transacciones vinculadas). */
(function () {
  'use strict';
  var root = document.getElementById('gv');
  if (!root) return;
  var API = '/finanzas/estados/api';
  var ICON = { Vuelos: 'plane', Hotel: 'building', Transporte: 'car', Comida: 'utensils', Experiencias: 'drama', Otros: 'package' };
  var CAT = { Vuelos: 'cosmopolitismo', Hotel: 'paideia', Transporte: 'hegemonikon', Comida: 'harma', Experiencias: 'eurythmia', Otros: 'identidad' };
  var ESTADO = { planificado: ['Planificado', 'eu-badge--info'], activo: ['En curso', 'eu-badge--success'], completado: ['Completado', ''], cancelado: ['Cancelado', 'eu-badge--danger'] };
  var trips = [], curId = null, summary = null, tagged = [], suggested = [], editing = false;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function fmt(n) { return (+n || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function fmtD(s) { return s ? s.slice(0, 10).split('-').reverse().join('/') : '—'; }
  function getJ(u) { return fetch(u).then(function (r) { return r.json(); }); }
  function send(u, m, b) { return fetch(u, { method: m, headers: { 'Content-Type': 'application/json' }, body: b === undefined ? undefined : JSON.stringify(b) }).then(function (r) { return r.json(); }); }
  function empty(ic, t, txt) { return '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p></div>'; }
  function tone(pct, over) { return over ? 'danger' : pct > 80 ? 'warning' : 'brand'; }
  function setErr(msg) { var e = $('modal-err'); e.hidden = !msg; e.querySelector('span').textContent = msg || ''; }

  function setView(v) {
    root.dataset.view = v; $('vw-list').hidden = v !== 'list'; $('vw-detail').hidden = v !== 'detail';
    var tb = document.querySelector('.eu-topbar .js-new'); if (tb) tb.hidden = v !== 'list';
  }

  /* ── Lista ──────────────────────────────────────────────────────────── */
  function loadTrips() { return getJ(API + '/trips').then(function (t) { trips = t || []; }); }
  function renderList() {
    setView('list');
    var grid = $('trip-grid');
    if (!trips.length) {
      grid.innerHTML = '<div class="eu-card gv-span">' + empty('plane', 'Aún no tienes viajes', 'Crea un viaje con su presupuesto y vincula los movimientos de tus estados de cuenta.') +
        '<div class="gv-cta"><button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Crear primer viaje</button></div></div>';
      icons(); return;
    }
    grid.innerHTML = trips.map(function (t) {
      var pct = t.presupuesto > 0 ? Math.min(t.total_gastado / t.presupuesto * 100, 100) : 0, over = t.presupuesto > 0 && t.total_gastado > t.presupuesto;
      var est = ESTADO[t.estado] || [t.estado, ''];
      return '<button type="button" class="eu-card eu-card--interactive gv-card" data-trip="' + t.id + '" data-tone="' + tone(pct, over) + '" aria-label="Ver detalle de ' + esc(t.nombre) + '">' +
        '<span class="eu-between gv-card-top"><span class="t-card gv-card-t">' + esc(t.nombre) + '</span><span class="eu-badge eu-badge--status ' + est[1] + '">' + esc(est[0]) + '</span></span>' +
        (t.destino ? '<span class="t-meta gv-dest"><i data-lucide="map-pin"></i>' + esc(t.destino) + '</span>' : '') +
        '<span class="t-data gv-dates">' + fmtD(t.fecha_inicio) + ' — ' + fmtD(t.fecha_fin) + '</span>' +
        (t.presupuesto > 0
          ? '<span class="eu-progress eu-progress--thin gv-prog" aria-hidden="true"><i style="width:' + pct.toFixed(1) + '%"></i></span><span class="eu-between t-meta num"><span>$' + fmt(t.total_gastado) + '</span><span>' + pct.toFixed(0) + '% de $' + fmt(t.presupuesto) + '</span></span>'
          : '<span class="t-meta">Sin presupuesto · $' + fmt(t.total_gastado) + ' gastado</span>') +
        '<span class="eu-between gv-card-ft t-meta"><span>' + t.tx_count + ' transaccion' + (t.tx_count !== 1 ? 'es' : '') + '</span><span class="fg-brand gv-go">Ver<i data-lucide="arrow-right"></i></span></span></button>';
    }).join('');
    icons();
  }
  $('trip-grid').addEventListener('click', function (e) { var c = e.target.closest('[data-trip]'); if (c) showDetail(+c.dataset.trip); });
  function showList() { curId = null; history.replaceState(null, '', location.pathname); renderList(); window.scrollTo(0, 0); }
  $$('.js-back').forEach(function (b) { b.addEventListener('click', showList); });

  /* ── Detalle ────────────────────────────────────────────────────────── */
  function showDetail(id) {
    curId = id; setView('detail');
    history.replaceState(null, '', location.pathname + '?trip=' + id);
    return Promise.all([getJ(API + '/trips/' + id + '/summary'), getJ(API + '/trips/' + id + '/transactions')]).then(function (r) {
      summary = r[0]; tagged = r[1].data || [];
      renderDetail(); window.scrollTo(0, 0);
      return loadSuggestions();
    }).catch(function () { toast('No se pudo cargar el viaje', 'err'); showList(); });
  }
  function renderDetail() {
    var t = summary.trip, gastado = summary.total_gastado, pres = t.presupuesto || 0, rest = pres - gastado;
    var pct = pres > 0 ? Math.min(gastado / pres * 100, 100) : 0, over = pres > 0 && gastado > pres;
    $('detail-title').textContent = t.nombre;
    $('detail-meta-dest').textContent = (t.destino || 'Sin destino') + ' · ' + fmtD(t.fecha_inicio) + ' — ' + fmtD(t.fecha_fin);
    // Misma fila en `viajes`: la maleta y outfits viven en el módulo Viajes.
    $('detail-maleta-link').href = '/viajes/?trip=' + t.id;
    $('detail-gastado').textContent = '$' + fmt(gastado);
    $('detail-presupuesto').textContent = pres > 0 ? '$' + fmt(pres) : '—';
    var r = $('detail-restante');
    r.textContent = pres > 0 ? (rest >= 0 ? '$' + fmt(rest) : '−$' + fmt(-rest)) : '—';
    r.dataset.tone = pres > 0 ? (rest >= 0 ? 'success' : 'danger') : '';
    $('gv-budget').dataset.tone = tone(pct, over);
    var bar = $('detail-bar'); bar.querySelector('i').style.width = pct.toFixed(1) + '%'; bar.setAttribute('aria-valuenow', Math.round(pct)); bar.hidden = !pres;
    $('detail-pct-txt').textContent = pres > 0 ? pct.toFixed(0) + '% del presupuesto' + (over ? ' — excedido' : '') : 'Define un presupuesto al editar el viaje para ver el avance.';

    var bd = summary.breakdown || [], max = bd.length ? bd[0].total : 1;
    $('breakdown-list').innerHTML = bd.length ? bd.map(function (b) {
      return '<li class="gv-concept" data-cat="' + (CAT[b.concepto] || 'identidad') + '"><span class="eu-row-ic gv-c-ic"><i data-lucide="' + (ICON[b.concepto] || 'package') + '"></i></span>' +
        '<span class="gv-c-bd"><span class="eu-between"><span class="t-ui">' + esc(b.concepto) + ' <span class="t-meta num">· ' + b.n + '</span></span><span class="t-data">$' + fmt(b.total) + '</span></span>' +
        '<span class="eu-progress eu-progress--thin eu-progress--cat" aria-hidden="true"><i style="width:' + (max > 0 ? (b.total / max * 100).toFixed(1) : 0) + '%"></i></span></span></li>';
    }).join('') : '<li>' + empty('pie-chart', 'Sin gastos vinculados', 'Vincula movimientos desde Sugerencias para ver el desglose.') + '</li>';

    $('tx-count-badge').textContent = '(' + tagged.length + ')';
    $('tx-list-wrap').innerHTML = tagged.length ? '<div class="gv-table-wrap"><table class="eu-table gv-table"><thead><tr><th scope="col">Fecha</th><th scope="col">Descripción</th><th scope="col">Categoría</th><th scope="col" class="num">Monto</th><th scope="col"><span class="gv-sr">Acciones</span></th></tr></thead><tbody>' +
      tagged.map(function (tx) {
        return '<tr><td class="num gv-nowrap">' + fmtD(tx.fecha) + '</td><td><span class="gv-desc" title="' + esc(tx.descripcion) + '">' + esc(tx.descripcion) + '</span></td>' +
          '<td class="t-meta">' + esc(tx.categoria) + (tx.subcategoria ? ' · ' + esc(tx.subcategoria) : '') + '</td><td class="num">$' + fmt(tx.mi_parte == null ? tx.monto : tx.mi_parte) + '</td>' +
          '<td><button type="button" class="eu-iconbtn" data-untag="' + tx.id + '" aria-label="Desvincular ' + esc(tx.descripcion) + '" title="Desvincular"><i data-lucide="unlink"></i></button></td></tr>';
      }).join('') + '</tbody></table></div>' : empty('link-2', 'Sin transacciones vinculadas', 'Usa las sugerencias para vincular los gastos de este viaje.');
    icons();
  }
  function loadSuggestions() {
    if (!curId) return Promise.resolve();
    $('suggest-list').innerHTML = '<p class="t-meta">Buscando transacciones…</p>'; $('suggest-footer').hidden = true;
    return getJ(API + '/trips/' + curId + '/suggest').then(function (r) {
      suggested = r.data || [];
      $('suggest-footer').hidden = !suggested.length;
      $('suggest-list').innerHTML = suggested.length ? suggested.map(function (tx) {
        return '<label class="gv-sug"><input type="checkbox" class="gv-chk" value="' + tx.id + '"><span class="eu-grow gv-sug-bd"><span class="t-ui gv-desc">' + esc(tx.descripcion) + '</span>' +
          '<span class="t-meta">' + fmtD(tx.fecha) + ' · ' + esc(tx.banco) + ' · ' + esc(tx.categoria) + '</span></span><span class="t-data">$' + fmt(tx.mi_parte == null ? tx.monto : tx.mi_parte) + '</span></label>';
      }).join('') : '<p class="t-meta">No hay sugerencias para el rango de fechas del viaje.</p>';
    }).catch(function () { $('suggest-list').innerHTML = '<p class="t-meta">No se pudieron cargar las sugerencias.</p>'; });
  }
  root.querySelector('.js-reload').addEventListener('click', loadSuggestions);
  root.querySelector('.js-all').addEventListener('click', function () {
    var cs = $$('.gv-chk'), all = cs.every(function (c) { return c.checked; });
    cs.forEach(function (c) { c.checked = !all; });
    this.textContent = all ? 'Seleccionar todas' : 'Quitar selección';
  });
  root.querySelector('.js-link').addEventListener('click', function () {
    var ids = $$('.gv-chk:checked').map(function (c) { return +c.value; });
    if (!ids.length) { toast('Selecciona al menos una transacción', 'err'); return; }
    var btn = this; btn.disabled = true;
    send(API + '/trips/' + curId + '/tag', 'POST', { tx_ids: ids }).then(function (r) {
      if (!r.ok) { toast(r.error || 'Error', 'err'); return; }
      toast(r.tagged + ' transaccion' + (r.tagged !== 1 ? 'es vinculadas' : ' vinculada'), 'ok');
      return showDetail(curId);
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { btn.disabled = false; });
  });
  $('tx-list-wrap').addEventListener('click', function (e) {
    var b = e.target.closest('[data-untag]'); if (!b) return;
    send(API + '/trips/' + curId + '/untag', 'POST', { tx_ids: [+b.dataset.untag] }).then(function (r) {
      if (r.ok) { toast('Transacción desvinculada'); return showDetail(curId); }
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Crear / editar / eliminar ──────────────────────────────────────── */
  function openTrip(isEdit) {
    editing = !!isEdit && !!summary && !!curId;
    $('m-trip-t').textContent = editing ? 'Editar viaje' : 'Nuevo viaje'; setErr('');
    var t = editing ? summary.trip : {};
    $('f-nombre').value = t.nombre || ''; $('f-destino').value = t.destino || ''; $('f-estado').value = t.estado || 'planificado';
    $('f-inicio').value = t.fecha_inicio || ''; $('f-fin').value = t.fecha_fin || ''; $('f-presupuesto').value = t.presupuesto || ''; $('f-notas').value = t.notas || '';
    euModal.open('m-trip'); setTimeout(function () { $('f-nombre').focus(); }, 20);
  }
  document.addEventListener('click', function (e) {
    if (e.target.closest('.js-new')) openTrip(false);
    else if (e.target.closest('#gv .js-edit')) openTrip(true);
  });
  $('f-trip').addEventListener('submit', function (e) {
    e.preventDefault();
    var nombre = $('f-nombre').value.trim(), inicio = $('f-inicio').value, fin = $('f-fin').value;
    if (!nombre) { setErr('El nombre es obligatorio'); $('f-nombre').focus(); return; }
    if (!inicio) { setErr('Ingresa la fecha de inicio'); $('f-inicio').focus(); return; }
    if (!fin) { setErr('Ingresa la fecha de fin'); $('f-fin').focus(); return; }
    if (fin < inicio) { setErr('La fecha fin debe ser posterior al inicio'); $('f-fin').focus(); return; }
    var payload = { nombre: nombre, destino: $('f-destino').value.trim(), fecha_inicio: inicio, fecha_fin: fin,
      presupuesto: parseFloat($('f-presupuesto').value) || 0, estado: $('f-estado').value, notas: $('f-notas').value.trim() };
    var btn = document.querySelector('[form="f-trip"]'); btn.disabled = true;
    send(editing ? API + '/trips/' + curId : API + '/trips', editing ? 'PATCH' : 'POST', payload).then(function (r) {
      if (!r.ok) { setErr(r.error || 'Error al guardar'); return; }
      euModal.close('m-trip'); toast(editing ? 'Viaje actualizado ✓' : 'Viaje creado ✓', 'ok');
      var id = editing ? curId : r.id;
      return loadTrips().then(function () { return id ? showDetail(id) : renderList(); });
    }).catch(function () { setErr('Sin conexión'); }).finally(function () { btn.disabled = false; });
  });
  root.querySelector('.js-del').addEventListener('click', function () {
    var name = summary && summary.trip ? summary.trip.nombre : 'este viaje';
    euConfirm('¿Eliminar «' + name + '»? Las transacciones se desvincularán (no se eliminan).', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      send(API + '/trips/' + curId, 'DELETE').then(function (r) {
        if (!r.ok) { toast('No se pudo eliminar', 'err'); return; }
        toast('Viaje eliminado'); return loadTrips().then(showList);
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  });

  loadTrips().then(function () {
    var tp = Number(new URLSearchParams(location.search).get('trip'));
    if (tp && trips.some(function (t) { return t.id === tp; })) showDetail(tp); else renderList();
  }).catch(function () { $('trip-grid').innerHTML = '<div class="eu-card">' + empty('wifi-off', 'Sin conexión', 'No se pudieron cargar los viajes.') + '</div>'; icons(); });
})();
