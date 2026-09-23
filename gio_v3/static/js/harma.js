/* Harma — Design System V2: vehículo + odómetro, plan de mantenimiento por
   categoría (progreso doble km/tiempo), bitácora de servicios y papeles
   (documentos, póliza y siniestros con archivos adjuntos). */
(function () {
  'use strict';
  var root = document.getElementById('hm');
  if (!root) return;
  var D = JSON.parse(document.getElementById('hm-data').textContent || '{}');
  var CAT_DEFS = D.cat_defs || [], TIPOS_SERVICIO = D.tipos_servicio || [], TIPOS_DOCUMENTO = D.tipos_documento || [];
  var TIPOS_SINIESTRO = D.tipos_siniestro || [], ESTADOS_SINIESTRO = D.estados_siniestro || [];
  var STATE = D.state;
  var TODAY = root.dataset.today || new Date().toISOString().slice(0, 10);
  var CAT_ICON = { motor: 'cog', frenos: 'disc', suspension: 'move-vertical', trans: 'settings-2', rodaje: 'circle-dot', fluidos: 'droplet' };
  var ST = {
    nominal: { l: 'Al día', b: 'eu-badge--success', t: 'success' }, proximo: { l: 'Próximo', b: 'eu-badge--brand', t: 'brand' },
    urgente: { l: 'Urgente', b: 'eu-badge--warning', t: 'warning' }, vencido: { l: 'Vencido', b: 'eu-badge--danger', t: 'danger' },
  };
  var POL = { vigente: ['Vigente', 'eu-badge--success'], proximo: ['Por vencer', 'eu-badge--warning'], vencida: ['Vencida', 'eu-badge--danger'], sin_fecha: ['Sin fecha', ''] };
  var MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  var filter = 'all', detail = null;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function money(n) { return '$' + Number(n || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 }); }
  function km(n) { return Number(n || 0).toLocaleString('es-MX') + ' km'; }
  function date(iso) { if (!iso) return ''; var p = iso.slice(0, 10).split('-'); return +p[2] + ' ' + MES[+p[1] - 1] + ' ' + p[0]; }
  function lbl(id, list) { return (list.filter(function (t) { return t.id === id; })[0] || {}).label || id; }
  function tipoIcon(id, list) { return (list.filter(function (t) { return t.id === id; })[0] || {}).icon || 'wrench'; }
  function num(id) { var v = $(id).value; return v === '' ? null : +v; }
  function emptyHtml(ic, t, txt, act, actLbl) {
    return '<div class="eu-card"><div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p>' +
      (act ? '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm ' + act + '"><i data-lucide="plus"></i>' + actLbl + '</button>' : '') + '</div></div>';
  }
  function busy(form, on) { var b = document.querySelector('[form="' + form + '"]'); if (b) { b.disabled = on; b.setAttribute('aria-busy', String(on)); } }
  // Todas las APIs devuelven {state}; se re-renderiza todo con el estado nuevo.
  function call(url, opts, okMsg, modal, form) {
    if (form) busy(form, true);
    return fetch(url, opts).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error || d.ok === false || !d.state) { toast(d.error || 'Error al guardar', 'err'); return null; }
      STATE = d.state;
      if (modal) euModal.close(modal);
      renderAll();
      var g = d.gam;
      var won = g && g.xp > 0;
      toast(won ? '+' + g.xp + ' XP · +' + (g.ec || 0) + ' EC' : okMsg, won ? 'win' : 'ok');
      if (g && window.euGam) euGam(g);
      return d;
    }).catch(function () { toast('Error de red', 'err'); }).finally(function () { if (form) busy(form, false); });
  }
  function json(method, body) { return { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }; }
  function onSubmit(id, fn) { $(id).addEventListener('submit', function (e) { e.preventDefault(); fn(); }); }
  function openM(id, focus) { euModal.open(id); if (focus) setTimeout(function () { $(focus).focus(); }, 20); }

  /* ── Pestañas ───────────────────────────────────────────────────────── */
  $$('[data-tab]').forEach(function (b) {
    b.addEventListener('click', function () {
      $$('[data-tab]').forEach(function (x) { x.setAttribute('aria-selected', String(x === b)); });
      $$('.hm-pane').forEach(function (p) { p.hidden = p.id !== 'pane-' + b.dataset.tab; });
    });
  });
  // Botones «nuevo» (incluidos los que aparecen dentro de estados vacíos).
  root.addEventListener('click', function (e) {
    var b = e.target.closest('.js-veh,.js-plan-new,.js-serv-new,.js-doc-new,.js-pol-new,.js-sin-new'); if (!b) return;
    if (b.classList.contains('js-veh')) openVeh();
    else if (b.classList.contains('js-plan-new')) openPlan();
    else if (b.classList.contains('js-serv-new')) openServ();
    else if (b.classList.contains('js-doc-new')) openDoc();
    else if (b.classList.contains('js-pol-new')) openPol();
    else openSin();
  });

  /* ── Vehículo ───────────────────────────────────────────────────────── */
  function renderVeh() {
    var v = STATE.vehiculo || {};
    $('hm-veh-name').textContent = v.nombre || 'Mi carro';
    $('hm-veh-sub').textContent = [v.marca, v.modelo, v.anio, v.motor, v.color].filter(Boolean).join(' · ') || '—';
    $('hm-veh-plate').hidden = !v.placas; $('hm-veh-plate').textContent = v.placas || '';
    $('hm-veh-km').textContent = Number(v.km_actual || 0).toLocaleString('es-MX');
  }
  function openVeh() {
    var v = STATE.vehiculo || {};
    ['nombre', 'placas', 'marca', 'modelo', 'anio', 'motor', 'color'].forEach(function (k) { $('v-' + k).value = v[k] || ''; });
    $('v-km').value = v.km_actual || 0;
    openM('m-veh', 'v-km');
  }
  onSubmit('f-m-veh', function () {
    call('/harma/api/vehiculo', json('POST', {
      nombre: $('v-nombre').value.trim() || 'Mi carro', placas: $('v-placas').value.trim(), marca: $('v-marca').value.trim(),
      modelo: $('v-modelo').value.trim(), anio: num('v-anio'), motor: $('v-motor').value.trim(), color: $('v-color').value.trim(),
      km_actual: +($('v-km').value || 0),
    }), 'Vehículo actualizado', 'm-veh', 'f-m-veh');
  });

  /* ── Estado y plan ──────────────────────────────────────────────────── */
  function renderStatus() {
    var c = STATE.plan_counts;
    [['vencidos', c.vencido], ['urgentes', c.urgente], ['nominal', c.nominal]].forEach(function (x) {
      $('hm-st-' + x[0]).textContent = x[1];
      $('hm-stbox-' + x[0]).classList.toggle('is-on', x[1] > 0);
    });
  }
  function renderFilters() {
    var c = STATE.plan_counts;
    $('hm-filters').innerHTML = [['all', 'Todos', STATE.plan.length], ['vencido', 'Vencidos', c.vencido], ['urgente', 'Urgentes', c.urgente], ['proximo', 'Próximos', c.proximo]]
      .map(function (f) { return '<button type="button" class="eu-chip" data-f="' + f[0] + '" aria-pressed="' + (filter === f[0]) + '">' + f[1] + ' <span class="ct">' + f[2] + '</span></button>'; }).join('');
  }
  $('hm-filters').addEventListener('click', function (e) {
    var b = e.target.closest('[data-f]'); if (!b) return;
    filter = b.dataset.f; renderPlan();
    var nb = document.querySelector('#hm-filters [data-f="' + filter + '"]'); if (nb) nb.focus();
  });
  function renderPlan() {
    renderFilters();
    var vis = filter === 'all' ? STATE.plan : STATE.plan.filter(function (it) { return it.status === filter; });
    var by = {}; vis.forEach(function (it) { (by[it.cat] = by[it.cat] || []).push(it); });
    var h = CAT_DEFS.filter(function (c) { return by[c.id] && by[c.id].length; }).map(function (c) {
      return '<section class="hm-cat" aria-label="' + esc(c.label) + '"><h3 class="t-eyebrow hm-cat-t"><i data-lucide="' + (CAT_ICON[c.id] || 'wrench') + '"></i>' + esc(c.label) + '<span class="hm-cat-rule"></span></h3><div class="hm-rows">' +
        by[c.id].sort(function (a, b) { return b.pct - a.pct; }).map(rowHtml).join('') + '</div></section>';
    }).join('');
    $('hm-plan-cats').innerHTML = h || emptyHtml('search-x', 'Nada en este filtro', 'Prueba con otro filtro o agrega un servicio al plan de mantenimiento.', 'js-plan-new', 'Servicio al plan');
    icons();
  }
  function rowHtml(it) {
    var s = ST[it.status], pct = Math.min(1, it.pct) * 100;
    return '<button type="button" class="eu-card eu-card--interactive hm-row" data-tone="' + s.t + '" data-item="' + esc(it.id) + '" aria-label="' + esc(it.name) + ': ' + s.l + '">' +
      '<span class="eu-between hm-row-top"><span class="t-ui hm-row-t">' + esc(it.name) + '</span><span class="hm-row-badges">' +
      (it.critical ? '<span class="eu-badge eu-badge--danger">Crítico</span>' : '') + '<span class="eu-badge eu-badge--status ' + s.b + '">' + s.l + '</span></span></span>' +
      '<span class="eu-progress eu-progress--thin hm-prog" aria-hidden="true"><i style="width:' + pct.toFixed(1) + '%"></i></span>' +
      '<span class="eu-between hm-row-ft t-meta"><span>Último: <span class="num">' + km(it.last_km) + '</span> · ' + date(it.last_date) + '</span>' +
      '<span class="num' + (it.km_left < 0 ? ' hm-over' : '') + '">' + (it.km_left < 0 ? 'Vencido hace ' + km(-it.km_left) : 'Faltan ' + km(it.km_left)) + '</span></span></button>';
  }
  $('hm-plan-cats').addEventListener('click', function (e) {
    var r = e.target.closest('[data-item]'); if (!r) return;
    var it = STATE.plan.filter(function (x) { return String(x.id) === r.dataset.item; })[0]; if (it) openDetail(it);
  });

  function openDetail(it) {
    detail = it;
    var s = ST[it.status];
    $('m-detail-t').textContent = it.name;
    document.querySelector('#m-detail .t-eyebrow').textContent = it.cat_label;
    $('hm-detail').dataset.tone = s.t;
    $('hm-detail-desc').textContent = it.desc || ''; $('hm-detail-desc').hidden = !it.desc;
    $('hm-detail-stats').innerHTML = [
      ['Intervalo km', it.km_interval < 999999 ? km(it.km_interval) : '—'],
      ['Intervalo tiempo', it.meses_interval < 999 ? it.meses_interval + ' meses' : '—'],
      ['Último servicio', km(it.last_km), date(it.last_date)],
      ['Próximo', km(it.next_km), 'en ' + km(Math.max(0, it.km_left))],
    ].map(function (r) {
      return '<div class="eu-card eu-card--inset hm-dstat"><div class="t-eyebrow">' + r[0] + '</div><div class="t-data hm-dstat-v">' + r[1] + '</div>' + (r[2] ? '<div class="t-meta">' + r[2] + '</div>' : '') + '</div>';
    }).join('');
    $('hm-detail-bars').innerHTML = [['Progreso por kilómetros', it.km_pct], ['Progreso por tiempo', it.time_pct]].map(function (b) {
      var over = b[1] >= 1;
      return '<div class="hm-dbar' + (over ? ' is-over' : '') + '"><div class="eu-between t-meta"><span>' + b[0] + '</span><span class="num hm-dbar-v">' + Math.round(b[1] * 100) + '%</span></div>' +
        '<div class="eu-progress hm-prog" role="progressbar" aria-label="' + b[0] + '" aria-valuenow="' + Math.round(b[1] * 100) + '" aria-valuemax="100"><i style="width:' + (Math.min(1, b[1]) * 100).toFixed(1) + '%"></i></div></div>';
    }).join('');
    openM('m-detail');
  }
  $('hm-detail-mark').addEventListener('click', function () {
    euModal.close('m-detail');
    $('m-marcar-t').textContent = 'Registrar: ' + detail.name;
    $('mk-km').value = (STATE.vehiculo || {}).km_actual || '';
    ['mk-costo', 'mk-taller', 'mk-desc'].forEach(function (k) { $(k).value = ''; });
    openM('m-marcar', 'mk-km');
  });
  $('hm-detail-edit').addEventListener('click', function () {
    euModal.close('m-detail');
    $('pe-km').value = detail.last_km; $('pe-fecha').value = detail.last_date || '';
    openM('m-plan-edit', 'pe-km');
  });
  $('hm-detail-del').addEventListener('click', function () {
    var it = detail;
    euConfirm('¿Quitar «' + it.name + '» del plan?', { confirmLabel: 'Quitar' }).then(function (ok) {
      if (ok) call('/harma/api/plan/' + encodeURIComponent(it.id), { method: 'DELETE' }, 'Servicio quitado del plan', 'm-detail');
    });
  });
  onSubmit('f-m-marcar', function () {
    call('/harma/api/plan/' + encodeURIComponent(detail.id) + '/marcar', json('POST', {
      km: num('mk-km'), costo: num('mk-costo') || 0, taller: $('mk-taller').value.trim(), descripcion: $('mk-desc').value.trim(),
    }), 'Servicio registrado', 'm-marcar', 'f-m-marcar');
  });
  onSubmit('f-m-plan-edit', function () {
    call('/harma/api/plan/' + encodeURIComponent(detail.id), json('PATCH', { last_km: num('pe-km'), last_date: $('pe-fecha').value || null }), 'Actualizado', 'm-plan-edit', 'f-m-plan-edit');
  });
  function openPlan() {
    $('pl-cat').value = 'motor'; ['pl-name', 'pl-km', 'pl-meses', 'pl-desc'].forEach(function (k) { $(k).value = ''; }); $('pl-critical').checked = false;
    openM('m-plan', 'pl-name');
  }
  onSubmit('f-m-plan', function () {
    var name = $('pl-name').value.trim();
    if (!name) { toast('Falta el nombre', 'err'); $('pl-name').focus(); return; }
    call('/harma/api/plan', json('POST', {
      cat: $('pl-cat').value, name: name, km_interval: num('pl-km'), meses_interval: num('pl-meses'),
      desc: $('pl-desc').value.trim(), critical: $('pl-critical').checked,
    }), 'Agregado al plan', 'm-plan', 'f-m-plan');
  });

  /* ── Historial y bitácora ───────────────────────────────────────────── */
  function renderHist() {
    var rec = STATE.servicios.slice(0, 5);
    $('hm-historial').innerHTML = rec.length ? rec.map(function (s) {
      var ic = s.plan_item_id ? 'check' : tipoIcon(s.tipo, TIPOS_SERVICIO);
      return '<li class="eu-row"><span class="eu-row-ic hm-hist-ic"><i data-lucide="' + ic + '"></i></span><span class="eu-grow hm-hist-bd"><span class="t-ui">' + esc(s.titulo) + '</span>' +
        '<span class="t-meta">' + (s.km ? '<span class="num">' + km(s.km) + '</span> · ' : '') + date(s.fecha) + '</span></span><span class="t-data fg-brand">' + money(s.costo) + '</span></li>';
    }).join('') : '<li>' + emptyHtml('history', 'Aún no hay historial', 'Registra tu primer servicio y aquí quedará el rastro completo.', 'js-serv-new', 'Registrar servicio') + '</li>';
    $('hm-historial').classList.toggle('is-empty', !rec.length);
  }
  function actions(links, delAttr, lblDel) {
    return '<div class="hm-actions">' + links + '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm hm-del" ' + delAttr + '><i data-lucide="trash-2"></i>' + (lblDel || 'Eliminar') + '</button></div>';
  }
  function fileLink(name, label) {
    return name ? '<a class="eu-btn eu-btn--secondary eu-btn--sm" href="/harma/documentos/' + encodeURIComponent(name) + '" target="_blank" rel="noopener"><i data-lucide="external-link"></i>' + label + '</a>' : '';
  }
  function renderServ() {
    $('hm-cost-total').textContent = money(STATE.total_costo);
    $('hm-serv-list').innerHTML = STATE.servicios.length ? STATE.servicios.map(function (s) {
      return '<article class="eu-card hm-card"><div class="eu-between"><span class="eu-hstack hm-card-t"><i data-lucide="' + tipoIcon(s.tipo, TIPOS_SERVICIO) + '"></i><span class="t-ui">' + esc(s.titulo) + '</span></span><span class="t-data fg-brand">' + money(s.costo) + '</span></div>' +
        '<div class="t-meta">' + date(s.fecha) + (s.km ? ' · <span class="num">' + km(s.km) + '</span>' : '') + (s.taller ? ' · ' + esc(s.taller) : '') + '</div>' +
        (s.descripcion ? '<p class="t-meta hm-note">' + esc(s.descripcion) + '</p>' : '') + actions('', 'data-del-serv="' + s.id + '"') + '</article>';
    }).join('') : emptyHtml('wrench', 'Bitácora vacía', 'Cada servicio que registres construye el historial completo del vehículo.', 'js-serv-new', 'Servicio ad hoc');
  }
  function openServ() {
    $('s-tipo').value = 'otro'; $('s-fecha').value = TODAY;
    ['s-titulo', 's-costo', 's-taller', 's-desc'].forEach(function (k) { $(k).value = ''; });
    $('s-km').value = (STATE.vehiculo || {}).km_actual || '';
    openM('m-serv', 's-titulo');
  }
  onSubmit('f-m-serv', function () {
    var titulo = $('s-titulo').value.trim();
    if (!titulo) { toast('Falta el título', 'err'); $('s-titulo').focus(); return; }
    call('/harma/api/servicio', json('POST', {
      tipo: $('s-tipo').value, titulo: titulo, fecha: $('s-fecha').value, km: num('s-km'), costo: num('s-costo') || 0,
      taller: $('s-taller').value.trim(), descripcion: $('s-desc').value.trim(),
    }), 'Servicio guardado', 'm-serv', 'f-m-serv');
  });

  /* ── Papeles ────────────────────────────────────────────────────────── */
  function renderDocs() {
    $('hm-doc-list').innerHTML = STATE.documentos.length ? STATE.documentos.map(function (d) {
      var pdf = /\.pdf$/i.test(d.nombre_archivo || '');
      return '<article class="eu-card hm-card"><div class="eu-hstack hm-doc"><span class="eu-row-ic"><i data-lucide="' + (pdf ? 'file-text' : 'image') + '"></i></span>' +
        '<div class="eu-grow"><div class="t-ui">' + esc(d.titulo) + '</div><div class="t-meta">' + esc(lbl(d.tipo, TIPOS_DOCUMENTO)) + (d.fecha_vencimiento ? ' · vence ' + date(d.fecha_vencimiento) : '') + '</div></div></div>' +
        actions(fileLink(d.nombre_archivo, 'Ver'), 'data-del-doc="' + d.id + '"') + '</article>';
    }).join('') : emptyHtml('file-text', 'Sin documentos', 'Sube tarjeta de circulación, factura o cualquier papel importante del vehículo.', 'js-doc-new', 'Subir');
  }
  function renderPols() {
    $('hm-poliza-list').innerHTML = STATE.polizas.length ? STATE.polizas.map(function (p) {
      var bits = [], st = POL[p.status] || [p.status, ''];
      if (p.numero_poliza) bits.push('póliza ' + esc(p.numero_poliza));
      if (p.vigencia_fin) bits.push('vence ' + date(p.vigencia_fin));
      if (p.deducible) bits.push('deducible ' + money(p.deducible));
      if (p.telefono_asistencia) bits.push('asistencia: <a href="tel:' + esc(p.telefono_asistencia) + '">' + esc(p.telefono_asistencia) + '</a>');
      return '<article class="eu-card hm-card hm-pol" data-status="' + esc(p.status) + '"><div class="eu-between"><span class="eu-hstack hm-card-t"><i data-lucide="shield"></i><span class="t-ui">' + esc(p.aseguradora) + '</span></span>' +
        '<span class="eu-badge eu-badge--status ' + st[1] + '">' + st[0] + '</span></div><div class="t-meta">' + bits.join(' · ') + '</div>' +
        actions(fileLink(p.nombre_archivo, 'Ver PDF'), 'data-del-pol="' + p.id + '"') + '</article>';
    }).join('') : emptyHtml('shield', 'Sin póliza registrada', 'Agrega los datos de tu seguro para tenerlos a la mano cuando los necesites.', 'js-pol-new', 'Agregar');
  }
  function renderSins() {
    $('hm-siniestro-list').innerHTML = STATE.siniestros.length ? STATE.siniestros.map(function (s) {
      var bits = [date(s.fecha)];
      if (s.costo_estimado) bits.push('estimado ' + money(s.costo_estimado));
      if (s.costo_cubierto) bits.push('cubierto ' + money(s.costo_cubierto));
      if (s.taller) bits.push(esc(s.taller));
      var opts = ESTADOS_SINIESTRO.map(function (e) { return '<option value="' + e.id + '"' + (e.id === s.estado ? ' selected' : '') + '>' + e.label + '</option>'; }).join('');
      return '<article class="eu-card hm-card"><div class="eu-between hm-sin-top"><span class="eu-hstack hm-card-t"><i data-lucide="' + tipoIcon(s.tipo, TIPOS_SINIESTRO) + '"></i><span class="t-ui">' + esc(lbl(s.tipo, TIPOS_SINIESTRO)) + '</span></span>' +
        '<select class="eu-select hm-estado" data-estado="' + s.id + '" aria-label="Estado del siniestro">' + opts + '</select></div>' +
        '<div class="t-meta">' + bits.join(' · ') + '</div>' + (s.descripcion ? '<p class="t-meta hm-note">' + esc(s.descripcion) + '</p>' : '') +
        actions(fileLink(s.nombre_archivo, 'Ver documento'), 'data-del-sin="' + s.id + '"') + '</article>';
    }).join('') : emptyHtml('shield-alert', 'Sin siniestros', 'Ojalá se mantenga así. Aquí quedará registrado cualquier accidente o incidente.', 'js-sin-new', 'Registrar');
  }
  // Eliminaciones y cambio de estado (delegados, con confirmación).
  var DEL = {
    'del-serv': ['/harma/api/servicio/', '¿Eliminar este servicio de la bitácora?', 'Servicio eliminado'],
    'del-doc': ['/harma/api/documentos/', '¿Eliminar este documento?', 'Documento eliminado'],
    'del-pol': ['/harma/api/poliza/', '¿Eliminar esta póliza?', 'Póliza eliminada'],
    'del-sin': ['/harma/api/siniestro/', '¿Eliminar este siniestro?', 'Siniestro eliminado'],
  };
  root.addEventListener('click', function (e) {
    var b = e.target.closest('.hm-del'); if (!b) return;
    Object.keys(DEL).forEach(function (k) {
      var id = b.getAttribute('data-' + k); if (!id) return;
      euConfirm(DEL[k][1], { confirmLabel: 'Eliminar' }).then(function (ok) { if (ok) call(DEL[k][0] + id, { method: 'DELETE' }, DEL[k][2]); });
    });
  });
  root.addEventListener('change', function (e) {
    var s = e.target.closest('[data-estado]'); if (!s) return;
    call('/harma/api/siniestro/' + s.dataset.estado, json('PATCH', { estado: s.value }), 'Estado actualizado');
  });

  function openDoc() {
    $('d-tipo').value = 'tarjeta_circulacion'; $('d-venc').value = ''; $('d-titulo').value = ''; $('d-file').value = '';
    openM('m-doc', 'd-titulo');
  }
  onSubmit('f-m-doc', function () {
    var titulo = $('d-titulo').value.trim(), file = $('d-file').files[0];
    if (!titulo) { toast('Falta el título', 'err'); $('d-titulo').focus(); return; }
    if (!file) { toast('Selecciona un archivo', 'err'); $('d-file').focus(); return; }
    var fd = new FormData();
    fd.append('file', file); fd.append('titulo', titulo); fd.append('tipo', $('d-tipo').value); fd.append('fecha_vencimiento', $('d-venc').value);
    call('/harma/api/documentos', { method: 'POST', body: fd }, 'Documento subido', 'm-doc', 'f-m-doc');
  });
  function openPol() {
    ['p-aseguradora', 'p-numero', 'p-vig-ini', 'p-vig-fin', 'p-prima', 'p-deducible', 'p-tel', 'p-notas', 'p-file'].forEach(function (k) { $(k).value = ''; });
    openM('m-poliza', 'p-aseguradora');
  }
  onSubmit('f-m-poliza', function () {
    var a = $('p-aseguradora').value.trim();
    if (!a) { toast('Falta la aseguradora', 'err'); $('p-aseguradora').focus(); return; }
    var fd = new FormData();
    fd.append('aseguradora', a); fd.append('numero_poliza', $('p-numero').value.trim());
    fd.append('vigencia_inicio', $('p-vig-ini').value); fd.append('vigencia_fin', $('p-vig-fin').value);
    fd.append('prima', $('p-prima').value || 0); fd.append('deducible', $('p-deducible').value || 0);
    fd.append('telefono_asistencia', $('p-tel').value.trim()); fd.append('notas', $('p-notas').value.trim());
    if ($('p-file').files[0]) fd.append('file', $('p-file').files[0]);
    call('/harma/api/poliza', { method: 'POST', body: fd }, 'Póliza guardada', 'm-poliza', 'f-m-poliza');
  });
  function openSin() {
    $('sn-tipo').value = 'choque'; $('sn-fecha').value = TODAY;
    ['sn-desc', 'sn-costo-est', 'sn-costo-cub', 'sn-deducible', 'sn-taller', 'sn-file'].forEach(function (k) { $(k).value = ''; });
    $('sn-poliza').innerHTML = '<option value="">— ninguna —</option>' + STATE.polizas.map(function (p) {
      return '<option value="' + p.id + '">' + esc(p.aseguradora) + (p.numero_poliza ? ' · ' + esc(p.numero_poliza) : '') + '</option>';
    }).join('');
    openM('m-siniestro', 'sn-desc');
  }
  onSubmit('f-m-siniestro', function () {
    var fd = new FormData();
    fd.append('tipo', $('sn-tipo').value); fd.append('fecha', $('sn-fecha').value); fd.append('descripcion', $('sn-desc').value.trim());
    fd.append('costo_estimado', $('sn-costo-est').value || 0); fd.append('costo_cubierto', $('sn-costo-cub').value || 0);
    fd.append('deducible_pagado', $('sn-deducible').value || 0); fd.append('taller', $('sn-taller').value.trim()); fd.append('poliza_id', $('sn-poliza').value);
    if ($('sn-file').files[0]) fd.append('file', $('sn-file').files[0]);
    call('/harma/api/siniestro', { method: 'POST', body: fd }, 'Siniestro registrado', 'm-siniestro', 'f-m-siniestro');
  });

  function renderAll() {
    renderVeh(); renderStatus(); renderPlan(); renderHist(); renderServ(); renderDocs(); renderPols(); renderSins(); icons();
  }
  renderAll();
})();
