/* Viajes v2 — un viaje, una página: lista con el próximo viaje destacado y
   detalle con cuenta regresiva, medidores de preparación, fases Antes | Regreso
   (outfits por día con sugerencias en la fila + maleta que se arma sola) y
   lateral con Dinero (solo fin_ok) y Otros viajes con su resultado del regreso. */
(function () {
  'use strict';
  var root = document.getElementById('vj');
  if (!root) return;
  var API = '/viajes/api', FIN = '/finanzas/estados/api';
  var TODAY = root.dataset.today || new Date().toISOString().slice(0, 10);
  var FIN_OK = root.dataset.fin === '1';
  var CAT_ORDER = ['Tops', 'Bottoms', 'Formal', 'Abrigo', 'Calzado', 'Ropa interior', 'Accesorios', 'Ropa', 'Documentos', 'Higiene', 'Tecnología', 'Salud', 'Varios'];
  var CLIMA = { calor: 'Calor', frio: 'Frío', templado: 'Templado', lluvia: 'Lluvioso' };
  var OCASION = { negocios: 'Negocios', casual: 'Casual', playa: 'Playa', aventura: 'Aventura', formal: 'Evento formal' };
  var MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  var DIA = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

  var trips = [], curId = null, curTrip = null, dias = [], maleta = [], outfits = null, wardrobe = null;
  var fase = 'antes', openDia = null, editing = false, pickerDia = null, aiMode = 'wardrobe', menuItem = null;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function getJ(url) { return fetch(url).then(function (r) { return r.json(); }); }
  function send(url, method, body) {
    var o = { method: method };
    if (body !== undefined) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(url, o).then(function (r) { return r.json(); });
  }
  function plural(n, s, p) { return n + ' ' + (n === 1 ? s : (p || s + 's')); }
  function money(n) { return '$' + Math.round(+n || 0).toLocaleString('es-MX'); }
  function d(s) { return new Date(s + 'T12:00:00'); }
  function diff(a, b) { return Math.round((d(b) - d(a)) / 86400000); }
  function corta(s) { var x = d(s); return x.getDate() + ' ' + MES[x.getMonth()]; }
  function rango(a, b) {
    var x = d(a), y = d(b);
    if (x.getFullYear() !== y.getFullYear()) return corta(a) + ' ' + x.getFullYear() + ' – ' + corta(b) + ' ' + y.getFullYear();
    if (x.getMonth() === y.getMonth()) return x.getDate() + '–' + y.getDate() + ' ' + MES[y.getMonth()];
    return corta(a) + ' – ' + corta(b);
  }
  function diaCorto(s) { var x = d(s); return DIA[x.getDay()] + ' ' + x.getDate(); }
  function emptyHtml(ic, t, txt) {
    return '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p></div>';
  }
  function setErr(id, msg) { var e = $(id); e.hidden = !msg; e.querySelector('span').textContent = msg || ''; }
  function swatch(hex, cls) { return '<span class="vj-sw ' + (cls || '') + '" style="--sw:' + esc(hex || '#444') + '"></span>'; }
  function photo(foto, cls) { return '<img class="' + cls + '" src="/guardarropa/photos/' + esc(foto) + '" alt="" loading="lazy">'; }
  function bar(pct, tone) { return '<span class="vj-bar' + (tone ? ' vj-bar--' + tone : '') + '" aria-hidden="true"><i style="--p:' + Math.max(0, Math.min(100, pct)) + '%"></i></span>'; }

  /* Cuenta regresiva del viaje: «en 18 días», «hoy», «último día», «completado»… */
  function cuenta(t) {
    if (t.estado === 'completado') return 'completado';
    var para = diff(TODAY, t.fecha_inicio), resta = diff(TODAY, t.fecha_fin);
    if (resta < 0) return 'terminó';
    if (resta === 0) return 'último día';
    if (para > 1) return para > 60 ? 'en ' + Math.round(para / 30) + ' meses' : 'en ' + para + ' días';
    if (para === 1) return 'mañana';
    if (para === 0) return 'hoy';
    return 'día ' + (1 - para) + ' de ' + (diff(t.fecha_inicio, t.fecha_fin) + 1);
  }
  /* Resultado del regreso de un viaje pasado («todo regresó» / «N olvidados»). */
  function regresoTxt(r) {
    if (!r) return null;
    return r.olvidados > 0 ? [plural(r.olvidados, 'olvidado'), 'warning'] : ['todo regresó', 'success'];
  }
  function grupo(t) { return t.fecha_fin < TODAY || t.estado === 'completado' ? 'pasado' : t.fecha_inicio > TODAY ? 'proximo' : 'vigente'; }

  /* ── Lista ──────────────────────────────────────────────────────────── */
  function loadTrips() { return getJ(API + '/trips').then(function (t) { trips = t || []; }); }

  function tripRow(t) {
    var g = grupo(t), r = g === 'pasado' ? regresoTxt(t.regreso) : null;
    var right = g === 'pasado' ? (r ? '<span class="vj-res vj-res--' + r[1] + '">' + r[0] + '</span>' : '')
      : '<span class="t-meta">' + (g === 'vigente' ? 'en curso' : cuenta(t)) + '</span>';
    var tipo = OCASION[t.ocasion] || (t.estado === 'completado' ? 'completado' : '');
    return '<button type="button" class="vj-trow" data-trip="' + t.id + '"><i data-lucide="plane"></i>' +
      '<span class="vj-trow-bd"><span class="t-ui vj-trow-t">' + esc(t.nombre) + '</span><span class="vj-trow-s">' + rango(t.fecha_inicio, t.fecha_fin) + (tipo ? ' · ' + esc(tipo.toLowerCase()) : '') + '</span></span>' + right + '</button>';
  }

  function renderList() {
    setView('list');
    var box = $('trip-sections');
    if (!trips.length) {
      box.innerHTML = '<div class="eu-card">' + emptyHtml('plane', 'Aún no tienes viajes', 'Crea tu primer viaje para planear outfits por día y armar la maleta.') +
        '<div class="vj-empty-cta"><button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Crear primer viaje</button></div></div>';
      icons(); return;
    }
    var vig = trips.filter(function (t) { return grupo(t) === 'vigente'; }).sort(function (a, b) { return a.fecha_inicio.localeCompare(b.fecha_inicio); });
    var prox = trips.filter(function (t) { return grupo(t) === 'proximo'; }).sort(function (a, b) { return a.fecha_inicio.localeCompare(b.fecha_inicio); });
    var pas = trips.filter(function (t) { return grupo(t) === 'pasado'; }).sort(function (a, b) { return b.fecha_inicio.localeCompare(a.fecha_inicio); });
    var dest = vig[0] || prox[0];
    var rest = vig.slice(dest === vig[0] ? 1 : 0).concat(prox.filter(function (t) { return t !== dest; }));
    var html = '';
    if (dest) {
      var meta = [dest.destino, rango(dest.fecha_inicio, dest.fecha_fin), plural(diff(dest.fecha_inicio, dest.fecha_fin), 'noche'), CLIMA[dest.tipo_clima], OCASION[dest.ocasion]].filter(Boolean).map(esc).join(' · ');
      html += '<button type="button" class="eu-card eu-card--interactive vj-feat" data-trip="' + dest.id + '" aria-label="Abrir ' + esc(dest.nombre) + '">' +
        '<span class="t-eyebrow vj-count">' + (grupo(dest) === 'vigente' ? 'En curso' : 'Próximo viaje') + ' · ' + cuenta(dest) + '</span>' +
        '<span class="t-section vj-feat-t">' + esc(dest.nombre) + '</span><span class="vj-dmeta">' + meta + '</span>' +
        '<span class="t-meta fg-brand vj-feat-go">Preparar<i data-lucide="arrow-right"></i></span></button>';
    }
    [['Próximos', rest], ['Pasados', pas]].forEach(function (s) {
      if (!s[1].length) return;
      html += '<section class="eu-card eu-card--inset vj-others" aria-label="' + s[0] + '"><h2 class="t-eyebrow vj-others-hd">' + s[0] + ' <span class="num">· ' + s[1].length + '</span></h2>' + s[1].map(tripRow).join('') + '</section>';
    });
    box.innerHTML = html; icons();
  }
  root.addEventListener('click', function (e) {
    var c = e.target.closest('[data-trip]'); if (c && root.contains(c)) showDetail(+c.dataset.trip);
  });

  function setView(v) {
    root.dataset.view = v;
    $('vw-list').hidden = v !== 'list';
    $('vw-detail').hidden = v !== 'detail';
    var nb = document.querySelector('.eu-topbar .js-new'); if (nb) nb.hidden = v !== 'list';
  }
  function showList() {
    curId = null; curTrip = null; closeMenu();
    history.replaceState(null, '', location.pathname);
    renderList(); window.scrollTo(0, 0);
  }

  /* ── Detalle ────────────────────────────────────────────────────────── */
  function showDetail(id) {
    curId = id; openDia = null;
    setView('detail');
    $('detail-title').textContent = 'Cargando…';
    history.replaceState(null, '', location.pathname + '?id=' + id);
    return Promise.all([getJ(API + '/trips/' + id), getJ(API + '/trips/' + id + '/dias'), getJ(API + '/trips/' + id + '/maleta')]).then(function (r) {
      if (r[0].error) throw new Error(r[0].error);
      curTrip = r[0]; dias = r[1] || []; maleta = r[2] || [];
      fase = curTrip.preparacion.fase === 'antes' ? 'antes' : 'regreso';
      renderDetail(); window.scrollTo(0, 0);
    }).catch(function () { toast('No se pudo cargar el viaje', 'err'); showList(); });
  }
  function reloadTrip() {
    return getJ(API + '/trips/' + curId).then(function (t) { if (!t.error) { curTrip = t; renderHeader(); renderPrep(); renderMoney(); } });
  }
  function renderDetail() { renderHeader(); renderPhase(); renderMoney(); renderOthers(); }

  function renderHeader() {
    var t = curTrip;
    var c = cuenta(t); $('detail-eyebrow').textContent = c.charAt(0).toUpperCase() + c.slice(1);
    $('detail-title').textContent = t.nombre;
    var noches = diff(t.fecha_inicio, t.fecha_fin);
    $('detail-meta').textContent = [t.destino, rango(t.fecha_inicio, t.fecha_fin), plural(noches, 'noche'), CLIMA[t.tipo_clima] || t.tipo_clima, OCASION[t.ocasion] || t.ocasion].filter(Boolean).join(' · ');
  }

  /* Medidores: Outfits · Maleta (ida o regreso según la fase) · Presupuesto (fin_ok) */
  function cuentaMaleta() {
    var pool = fase === 'antes' ? maleta : maleta.filter(function (m) { return !m.no_regresa; });
    var f = fase === 'antes' ? 'packed_ida' : 'packed_vuelta';
    return { n: pool.filter(function (m) { return m[f]; }).length, t: pool.length };
  }
  function renderPrep() {
    var con = dias.filter(function (x) { return x.outfits && x.outfits.length; }).length, tot = dias.length, m = cuentaMaleta();
    var cells = [
      { l: 'Outfits', ic: 'shirt', v: con + '/' + tot, p: tot ? con / tot * 100 : 0, ok: tot && con === tot,
        s: !tot ? 'sin días' : con === tot ? 'todos los días listos' : 'faltan ' + plural(tot - con, 'día') },
      { l: fase === 'antes' ? 'Maleta · ida' : 'Maleta · regreso', ic: 'luggage', v: m.n + '/' + m.t, p: m.t ? m.n / m.t * 100 : 0, ok: m.t && m.n === m.t,
        s: !m.t ? 'vacía' : m.n === m.t ? (fase === 'antes' ? 'todo empacado' : 'nada se queda') : 'faltan ' + (m.t - m.n) },
    ];
    var din = curTrip.dinero;
    if (FIN_OK && din) {
      cells.push(din.presupuesto > 0
        ? { l: 'Presupuesto', ic: 'wallet', v: din.pct + '%', p: din.pct, over: din.gastado > din.presupuesto, s: money(din.gastado) + ' de ' + money(din.presupuesto) }
        : { l: 'Presupuesto', ic: 'wallet', v: '—', p: 0, s: 'sin presupuesto · ' + money(din.gastado) });
    }
    var el = $('vj-prep');
    el.dataset.n = cells.length;
    el.innerHTML = cells.map(function (c) {
      var tone = c.over ? 'danger' : c.ok ? 'success' : c.l === 'Presupuesto' ? 'brand' : '';
      return '<div class="vj-prep-c' + (c.ok ? ' is-ok' : '') + (c.over ? ' is-over' : '') + '"><span class="vj-prep-l"><i data-lucide="' + c.ic + '"></i>' + c.l + '</span>' +
        '<span class="vj-mono22">' + c.v + '</span>' + bar(c.p, tone) + '<span class="t-meta">' + c.s + '</span></div>';
    }).join('');
    icons();
  }

  function renderPhase() {
    var cerrado = curTrip.preparacion.fase === 'cerrado';
    $$('#vj-phases [data-fase]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.fase === fase)); });
    $('phase-hint').textContent = fase === 'antes'
      ? (curTrip.preparacion.fase === 'antes' ? 'Regreso se abre solo el ' + corta(curTrip.fecha_fin) : 'Ya es el regreso: marca lo que va de vuelta')
      : 'Misma maleta, check de vuelta · sin consumibles';
    $('box-dias').hidden = fase !== 'antes';
    $('box-maleta').classList.toggle('is-regreso', fase !== 'antes');
    $('maleta-t').textContent = fase === 'antes' ? 'Maleta' : 'Regreso';
    $('maleta-hint').textContent = fase === 'antes' ? 'Se actualiza sola con tus outfits' : 'Marca lo que ya va de vuelta';
    renderCierre(cerrado);
    if (fase === 'antes') renderOutfits();
    renderMaleta(); renderPrep();
  }
  $$('#vj-phases [data-fase]').forEach(function (b) {
    b.addEventListener('click', function () { fase = b.dataset.fase; openDia = null; closeMenu(); renderPhase(); });
  });

  /* Viaje cerrado: «Todo regresó» o «N olvidados» con la lista */
  function renderCierre(cerrado) {
    var el = $('vj-cierre');
    el.hidden = !cerrado;
    if (!cerrado) return;
    var r = curTrip.regreso || { olvidados: 0 };
    var falt = maleta.filter(function (m) { return !m.no_regresa && !m.packed_vuelta; });
    el.className = 'vj-cierre vj-cierre--' + (r.olvidados > 0 ? 'warning' : 'success');
    el.innerHTML = r.olvidados > 0
      ? '<i data-lucide="alert-triangle"></i><div><b>' + plural(r.olvidados, 'olvidado') + '</b>' + (falt.length ? '<p class="t-meta">' + falt.map(function (m) { return esc(m.nombre); }).join(' · ') + '</p>' : '') + '</div>'
      : '<i data-lucide="check-circle-2"></i><div><b>Todo regresó</b><p class="t-meta">Nada se quedó en este viaje.</p></div>';
    icons();
  }

  /* ── Outfits por día ────────────────────────────────────────────────── */
  function renderOutfits() {
    var el = $('dias-list');
    var con = dias.filter(function (x) { return x.outfits && x.outfits.length; }).length;
    $('dias-n').textContent = con + '/' + dias.length;
    if (!dias.length) { el.innerHTML = '<li>' + emptyHtml('calendar-x', 'Sin días', 'Este viaje aún no tiene días para planear outfits.') + '</li>'; icons(); return; }
    el.innerHTML = dias.map(function (x, i) {
      var o = x.outfits && x.outfits[0], open = openDia === x.id;
      var desc = x.descripcion || 'Día ' + (i + 1);
      var sub = o ? [desc, o.prendas].filter(Boolean).join(' · ') : 'Sin outfit';
      return '<li class="vj-day' + (o ? ' has-outfit' : '') + (x.fecha === TODAY ? ' is-today' : '') + '">' +
        '<div class="vj-day-row"><span class="vj-day-f">' + diaCorto(x.fecha) + '</span>' +
        '<span class="vj-day-bd"><span class="vj-day-t">' + esc(o ? o.nombre : desc) + '</span><span class="vj-day-s">' + esc(sub) + '</span></span>' +
        '<button type="button" class="eu-btn eu-btn--sm vj-day-btn' + (o || open ? '' : ' is-pick') + '" data-open="' + x.id + '" aria-expanded="' + open + '">' + (open ? 'Cerrar' : o ? 'Cambiar' : 'Elegir') + '</button></div>' +
        (open ? '<div class="vj-sugs" id="sugs-' + x.id + '">' + euSkelHTML(1, 48) + '</div>' : '') + '</li>';
    }).join('');
    icons();
    if (openDia) loadSugs(openDia);
  }
  function loadSugs(diaId) {
    getJ(API + '/trips/' + curId + '/dias/' + diaId + '/sugerencias').then(function (r) {
      var box = $('sugs-' + diaId); if (!box) return;
      var s = r.data || [];
      box.innerHTML = s.map(function (o) {
        return '<button type="button" class="vj-sug" data-sug="' + o.id + '" data-dia="' + diaId + '"><span class="t-ui">' + esc(o.nombre) + '</span><span class="vj-sug-w">' + esc(o.razon) + '</span></button>';
      }).join('') + '<button type="button" class="vj-sug vj-sug--all" data-pick="' + diaId + '"><span class="t-ui">Ver todos…</span><span class="vj-sug-w">' + plural(r.total || 0, 'outfit') + '</span></button>';
      var f = box.querySelector('button'); if (f) f.focus();
    }).catch(function () { var box = $('sugs-' + diaId); if (box) box.innerHTML = '<p class="t-meta">No se pudieron cargar las sugerencias.</p>'; });
  }
  $('dias-list').addEventListener('click', function (e) {
    var o = e.target.closest('[data-open]'), s = e.target.closest('[data-sug]'), p = e.target.closest('[data-pick]');
    if (o) { openDia = openDia === +o.dataset.open ? null : +o.dataset.open; renderOutfits(); }
    else if (s) assign(+s.dataset.dia, +s.dataset.sug, s);
    else if (p) openPicker(+p.dataset.pick);
  });

  function assign(diaId, outfitId, btn) {
    if (btn) btn.disabled = true;
    return send(API + '/trips/' + curId + '/dias/' + diaId + '/outfit', 'POST', { outfit_id: outfitId }).then(function (r) {
      if (!r.ok) { toast(r.error || 'Error', 'err'); if (btn) btn.disabled = false; return; }
      toast('Outfit asignado · maleta actualizada', 'ok'); openDia = null; return afterOutfit(r);
    }).catch(function () { toast('Sin conexión', 'err'); if (btn) btn.disabled = false; });
  }
  function unassign(diaId) {
    return send(API + '/trips/' + curId + '/dias/' + diaId + '/outfit', 'DELETE').then(function (r) {
      if (r.ok) { toast('Outfit quitado'); openDia = null; return afterOutfit(r); }
    }).catch(function () { toast('Sin conexión', 'err'); });
  }
  // La respuesta trae la maleta ya regenerada: se repinta sin recargar.
  function afterOutfit(r) {
    maleta = r.maleta || maleta;
    if (r.preparacion) curTrip.preparacion = r.preparacion;
    return getJ(API + '/trips/' + curId + '/dias').then(function (x) { dias = x || []; renderOutfits(); renderMaleta(); renderPrep(); });
  }

  /* Picker completo («Ver todos…» / Cambiar), con «Quitar outfit» dentro */
  function mosaic(items) {
    var all = (items || []).filter(function (i) { return i.foto; }).concat((items || []).filter(function (i) { return !i.foto; })).slice(0, 4);
    if (!all.length) return '<span class="vj-mosaic vj-mosaic--empty"><i data-lucide="shirt"></i></span>';
    return '<span class="vj-mosaic vj-mosaic--' + all.length + '">' + all.map(function (i) {
      return i.foto ? photo(i.foto, 'vj-ms') : swatch(i.color_hex, 'vj-ms');
    }).join('') + '</span>';
  }
  function openPicker(diaId) {
    pickerDia = dias.filter(function (x) { return x.id === diaId; })[0]; if (!pickerDia) return;
    $('picker-day-label').textContent = diaCorto(pickerDia.fecha) + (pickerDia.descripcion ? ' — ' + pickerDia.descripcion : '');
    $('btn-quitar-outfit').hidden = !(pickerDia.outfits && pickerDia.outfits.length);
    var grid = $('picker-outfit-grid');
    grid.innerHTML = euSkelHTML(3, 72);
    euModal.open('m-picker');
    (outfits ? Promise.resolve(outfits) : getJ(API + '/outfits')).then(function (o) {
      outfits = o || [];
      $('picker-empty').hidden = !!outfits.length; grid.hidden = !outfits.length;
      var cur = pickerDia.outfits && pickerDia.outfits[0] ? pickerDia.outfits[0].id : null;
      grid.innerHTML = outfits.map(function (o) {
        var prendas = (o.items || []).slice(0, 3).map(function (i) { return esc(i.nombre); }).join(' · ');
        return '<button type="button" class="eu-card eu-card--interactive vj-ocard" data-outfit="' + o.id + '" aria-pressed="' + (o.id === cur) + '">' + mosaic(o.items) +
          '<span class="t-ui vj-ocard-t">' + esc(o.nombre) + '</span>' + (o.ocasion ? '<span class="eu-badge">' + esc(o.ocasion) + '</span>' : '') +
          (prendas ? '<span class="t-meta vj-ocard-p">' + prendas + '</span>' : '') + '</button>';
      }).join('');
      icons();
      var sel = grid.querySelector('[aria-pressed=true]') || grid.querySelector('[data-outfit]'); if (sel) sel.focus();
    }).catch(function () { grid.innerHTML = '<p class="t-meta">No se pudieron cargar los outfits.</p>'; });
  }
  $('picker-outfit-grid').addEventListener('click', function (e) {
    var c = e.target.closest('[data-outfit]'); if (!c || !pickerDia) return;
    euModal.close('m-picker'); assign(pickerDia.id, +c.dataset.outfit);
  });
  $('btn-quitar-outfit').addEventListener('click', function () {
    if (!pickerDia) return; var id = pickerDia.id; euModal.close('m-picker'); unassign(id);
  });

  /* ── Maleta / Regreso ───────────────────────────────────────────────── */
  function grouped(list) {
    var cats = {};
    list.forEach(function (m) { (cats[m.categoria] = cats[m.categoria] || []).push(m); });
    return CAT_ORDER.filter(function (c) { return cats[c]; }).concat(Object.keys(cats).filter(function (c) { return CAT_ORDER.indexOf(c) < 0; }))
      .map(function (c) { return { cat: c, items: cats[c] }; });
  }
  function qty(m) {
    if (m.no_regresa) return 'no regresa';
    if (m.dias_uso > 1) return m.dias_uso + ' días';
    if (m.cantidad > 1) return '× ' + m.cantidad;
    return '';
  }
  function renderMaleta() {
    var field = fase === 'antes' ? 'packed_ida' : 'packed_vuelta';
    var list = fase === 'antes' ? maleta : maleta.filter(function (m) { return !m.no_regresa; });
    var c = cuentaMaleta();
    $('maleta-n').textContent = c.n + '/' + c.t;
    $('maleta-list').innerHTML = list.length ? grouped(list).map(function (g) {
      return '<h3 class="vj-bag-cat">' + esc(g.cat) + '</h3><ul class="vj-bag-items">' + g.items.map(function (m) {
        var on = !!m[field];
        return '<li class="vj-item' + (on ? ' is-done' : '') + (m.no_regresa ? ' is-cons' : '') + '" data-item="' + m.id + '">' +
          '<button type="button" class="vj-chk" role="checkbox" aria-checked="' + on + '" data-chk="' + m.id + '" data-field="' + field + '">' +
          '<span class="vj-chk-box" aria-hidden="true"><i data-lucide="check"></i></span>' +
          '<span class="vj-item-t">' + esc(m.nombre) + '</span><span class="vj-item-q">' + qty(m) + '</span></button>' +
          '<button type="button" class="eu-iconbtn vj-item-menu" data-menu="' + m.id + '" aria-haspopup="menu" aria-label="Opciones de ' + esc(m.nombre) + '"><i data-lucide="more-horizontal"></i></button></li>';
      }).join('') + '</ul>';
    }).join('') : emptyHtml('luggage', fase === 'antes' ? 'Tu maleta está vacía' : 'Nada que revisar', fase === 'antes' ? 'Elige un outfit en cualquier día y sus prendas aparecen aquí.' : 'Cuando tu maleta tenga ítems, aquí marcas lo que va de vuelta.');
    icons();
  }
  function toggleChk(c) {
    var id = +c.dataset.chk, field = c.dataset.field, item = maleta.filter(function (m) { return m.id === id; })[0];
    if (!item) return;
    var now = !item[field];
    item[field] = now ? 1 : 0;
    c.setAttribute('aria-checked', String(now)); c.closest('.vj-item').classList.toggle('is-done', now);
    var st = cuentaMaleta(); $('maleta-n').textContent = st.n + '/' + st.t; renderPrep();
    send(API + '/trips/' + curId + '/maleta/' + id, 'PATCH', { field: field }).then(function () {
      if (now && st.n === st.t) toast(field === 'packed_vuelta' ? 'Nada se queda ✓' : 'Todo empacado ✓', 'win');
    }).catch(function () { item[field] = now ? 0 : 1; toast('Sin conexión', 'err'); renderMaleta(); renderPrep(); });
  }

  /* Menú del ítem (clic en ⋯ o clic largo): no regresa / quitar */
  var menu = document.createElement('div');
  menu.className = 'vj-menu'; menu.setAttribute('role', 'menu'); menu.hidden = true;
  document.body.appendChild(menu);
  function openMenu(id, anchor) {
    var m = maleta.filter(function (x) { return x.id === id; })[0]; if (!m) return;
    menuItem = m;
    menu.innerHTML = '<button type="button" role="menuitem" data-act="cons"><i data-lucide="' + (m.no_regresa ? 'rotate-ccw' : 'droplet') + '"></i>' + (m.no_regresa ? 'Sí regresa' : 'No regresa (consumible)') + '</button>' +
      '<button type="button" role="menuitem" data-act="del"><i data-lucide="x"></i>Quitar de la maleta</button>';
    menu.hidden = false; icons();
    var r = anchor.getBoundingClientRect(), w = menu.offsetWidth;
    menu.style.setProperty('--x', Math.max(8, Math.min(window.innerWidth - w - 8, r.right - w)) + 'px');
    var h = menu.offsetHeight, y = r.bottom + 4 + h > window.innerHeight ? r.top - h - 4 : r.bottom + 4;
    menu.style.setProperty('--y', Math.max(8, y) + 'px');
    menu.querySelector('button').focus();
  }
  function closeMenu() { menu.hidden = true; menuItem = null; }
  // composedPath: el ícono del botón puede re-pintarse (lucide) y quedar fuera del DOM.
  document.addEventListener('click', function (e) {
    if (menu.hidden) return;
    var dentro = e.composedPath().some(function (n) { return n === menu || (n.dataset && n.dataset.menu); });
    if (!dentro) closeMenu();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !menu.hidden) closeMenu(); });
  window.addEventListener('scroll', function () { if (!menu.hidden) closeMenu(); }, true);
  menu.addEventListener('click', function (e) {
    var b = e.target.closest('[data-act]'); if (!b || !menuItem) return;
    var m = menuItem; closeMenu();
    if (b.dataset.act === 'cons') {
      var val = m.no_regresa ? 0 : 1;
      send(API + '/trips/' + curId + '/maleta/' + m.id, 'PATCH', { no_regresa: val }).then(function (r) {
        if (!r.ok) return;
        m.no_regresa = val; renderMaleta(); renderPrep();
        toast(val ? m.nombre + ': no regresa' : m.nombre + ': sí regresa');
      }).catch(function () { toast('Sin conexión', 'err'); });
    } else {
      send(API + '/trips/' + curId + '/maleta/' + m.id, 'DELETE').then(function (r) {
        if (!r.ok) return;
        maleta = maleta.filter(function (x) { return x.id !== m.id; }); renderMaleta(); renderPrep(); toast('Ítem quitado');
      }).catch(function () { toast('Sin conexión', 'err'); });
    }
  });
  var press = null, longFired = false;
  $('maleta-list').addEventListener('pointerdown', function (e) {
    var c = e.target.closest('[data-chk]'); if (!c) return;
    longFired = false;
    press = setTimeout(function () { longFired = true; openMenu(+c.dataset.chk, c); }, 550);
  });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) { $('maleta-list').addEventListener(ev, function () { clearTimeout(press); }); });
  $('maleta-list').addEventListener('contextmenu', function (e) {
    var c = e.target.closest('[data-chk]'); if (!c) return;
    e.preventDefault(); if (!longFired) openMenu(+c.dataset.chk, c);
  });
  $('maleta-list').addEventListener('click', function (e) {
    var c = e.target.closest('[data-chk]'), mn = e.target.closest('[data-menu]');
    if (c) { if (longFired) { longFired = false; return; } toggleChk(c); }
    else if (mn) { if (menuItem && menuItem.id === +mn.dataset.menu && !menu.hidden) closeMenu(); else openMenu(+mn.dataset.menu, mn); }
  });
  function reloadMaleta() {
    return getJ(API + '/trips/' + curId + '/maleta').then(function (m) { maleta = m || []; renderMaleta(); renderPrep(); });
  }

  /* ── Lateral: Dinero (fin_ok) y Otros viajes ────────────────────────── */
  function renderMoney() {
    var box = $('vj-money'); if (!box) return;
    var din = curTrip.dinero;
    box.hidden = !din; if (!din) return;
    $('money-gastado').textContent = money(din.gastado);
    $('money-de').textContent = din.presupuesto > 0 ? 'de ' + money(din.presupuesto) : 'sin presupuesto';
    var b = $('money-bar'), pct = din.presupuesto > 0 ? Math.min(100, din.pct) : 0;
    b.hidden = !(din.presupuesto > 0); b.setAttribute('aria-valuenow', pct); b.querySelector('i').style.setProperty('--p', pct + '%');
    b.classList.toggle('is-over', din.gastado > din.presupuesto && din.presupuesto > 0);
    $('money-rest').textContent = din.presupuesto > 0 ? (din.restan >= 0 ? 'restan ' + money(din.restan) : 'excedido por ' + money(-din.restan)) : 'Define un presupuesto al editar el viaje.';
    var s = din.sugeridos;
    $('money-sug').hidden = !s.n;
    $('money-sug-t').textContent = plural(s.n, 'movimiento') + ' en estas fechas sin vincular · ' + money(s.total);
    $('money-go').href = '/finanzas/estados/viajes/?id=' + curTrip.id;
  }
  var ml = $('money-link');
  if (ml) ml.addEventListener('click', function () {
    var ids = (curTrip.dinero && curTrip.dinero.sugeridos.ids) || []; if (!ids.length) return;
    ml.disabled = true;
    send(FIN + '/trips/' + curId + '/tag', 'POST', { tx_ids: ids }).then(function (r) {
      if (!r.ok) { toast(r.error || 'No se pudo vincular', 'err'); return; }
      toast(plural(r.tagged, 'movimiento') + ' vinculado' + (r.tagged !== 1 ? 's' : ''), 'ok'); return reloadTrip();
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { ml.disabled = false; });
  });

  function renderOthers() {
    var otros = trips.filter(function (t) { return t.id !== curId; });
    var fut = otros.filter(function (t) { return grupo(t) !== 'pasado'; }).sort(function (a, b) { return a.fecha_inicio.localeCompare(b.fecha_inicio); });
    var pas = otros.filter(function (t) { return grupo(t) === 'pasado'; }).sort(function (a, b) { return b.fecha_inicio.localeCompare(a.fecha_inicio); });
    var list = fut.concat(pas).slice(0, 6);
    $('others-list').innerHTML = list.length ? list.map(tripRow).join('') : '<p class="t-meta vj-others-empty">No hay otros viajes.</p>';
    icons();
  }

  /* ── Agregar ítem ───────────────────────────────────────────────────── */
  function setAi(mode) {
    aiMode = mode;
    $$('[data-ai]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.ai === mode)); });
    $('ai-panel-wardrobe').hidden = mode !== 'wardrobe';
    $('ai-panel-generic').hidden = mode !== 'generic';
    $('ai-submit-btn').hidden = mode !== 'generic';
    setTimeout(function () { $(mode === 'generic' ? 'ai-nombre' : 'ai-wi-search').focus(); }, 20);
  }
  $$('[data-ai]').forEach(function (b) { b.addEventListener('click', function () { setAi(b.dataset.ai); }); });
  $$('.js-add-item').forEach(function (b) {
    b.addEventListener('click', function () {
      $('ai-nombre').value = ''; $('ai-cat').value = 'Varios'; $('ai-wi-search').value = ''; setErr('ai-err', '');
      euSkel('ai-wi-grid', 3, 64);
      euModal.open('m-item'); setAi('wardrobe');
      (wardrobe ? Promise.resolve(wardrobe) : getJ(API + '/wardrobe-items')).then(function (w) { wardrobe = w || []; renderWardrobe(); })
        .catch(function () { $('ai-wi-grid').innerHTML = '<p class="t-meta">No se pudieron cargar las prendas.</p>'; });
    });
  });
  function renderWardrobe() {
    var grid = $('ai-wi-grid'), q = $('ai-wi-search').value.toLowerCase().trim();
    $('ai-wi-empty').hidden = !!wardrobe.length; grid.hidden = !wardrobe.length;
    if (!wardrobe.length) return;
    var added = {}; maleta.forEach(function (m) { if (m.item_id) added[m.item_id] = true; });
    var list = q ? wardrobe.filter(function (w) { return w.nombre.toLowerCase().indexOf(q) >= 0; }) : wardrobe;
    grid.innerHTML = list.length ? list.map(function (w) {
      var on = !!added[w.id];
      return '<button type="button" class="vj-wcard" data-wi="' + w.id + '" aria-pressed="' + on + '" aria-label="' + (on ? 'Quitar de la maleta: ' : 'Agregar a la maleta: ') + esc(w.nombre) + '">' +
        (w.foto ? photo(w.foto, 'vj-wimg') : swatch(w.color_hex, 'vj-wimg')) +
        '<span class="vj-wcheck" aria-hidden="true"><i data-lucide="check"></i></span><span class="t-meta vj-wname">' + esc(w.nombre) + '</span></button>';
    }).join('') : '<div class="vj-span">' + euEmpty('search-x', 'Sin resultados', 'Nada coincide con «' + q + '».', true) + '</div>';
    icons();
  }
  $('ai-wi-search').addEventListener('input', renderWardrobe);
  $('ai-wi-grid').addEventListener('click', function (e) {
    var c = e.target.closest('[data-wi]'); if (!c) return;
    var wid = +c.dataset.wi, on = c.getAttribute('aria-pressed') === 'true';
    c.disabled = true;
    var p;
    if (on) {
      var row = maleta.filter(function (m) { return m.item_id === wid; })[0];
      p = row ? send(API + '/trips/' + curId + '/maleta/' + row.id, 'DELETE').then(function (r) { if (r.ok) toast('Quitada de la maleta'); }) : Promise.resolve();
    } else {
      p = send(API + '/trips/' + curId + '/maleta/item-from-wardrobe', 'POST', { item_id: wid }).then(function (r) {
        if (r.ok) toast('Prenda agregada ✓', 'ok'); else toast(r.error || 'Error', 'err');
      });
    }
    p.then(reloadMaleta).then(function () {
      renderWardrobe(); var nb = document.querySelector('[data-wi="' + wid + '"]'); if (nb) nb.focus();
    }).catch(function () { toast('Sin conexión', 'err'); c.disabled = false; });
  });
  $('ai-panel-generic').addEventListener('submit', function (e) {
    e.preventDefault();
    var nombre = $('ai-nombre').value.trim();
    if (!nombre) { setErr('ai-err', 'Escribe un nombre'); $('ai-nombre').focus(); return; }
    send(API + '/trips/' + curId + '/maleta/item', 'POST', { nombre: nombre, categoria: $('ai-cat').value }).then(function (r) {
      if (!r.ok) { setErr('ai-err', r.error || 'Error'); return; }
      euModal.close('m-item'); toast('Ítem agregado ✓', 'ok'); reloadMaleta();
    }).catch(function () { setErr('ai-err', 'Sin conexión'); });
  });

  /* ── Viaje: un solo alta y edición (presupuesto solo con fin_ok) ────── */
  var F = ['nombre', 'destino', 'estado', 'inicio', 'fin', 'clima', 'ocasion', 'notas'];
  function openTrip(isEdit) {
    editing = !!isEdit && !!curTrip;
    $('m-trip-t').textContent = editing ? 'Editar viaje' : 'Nuevo viaje';
    setErr('modal-err', '');
    var t = editing ? curTrip : {};
    var v = { nombre: t.nombre, destino: t.destino, estado: t.estado || 'planificado', inicio: t.fecha_inicio, fin: t.fecha_fin, clima: t.tipo_clima, ocasion: t.ocasion, notas: t.notas };
    F.forEach(function (k) { $('f-' + k).value = v[k] || ''; });
    if ($('f-presupuesto')) $('f-presupuesto').value = editing && t.dinero && t.dinero.presupuesto ? t.dinero.presupuesto : '';
    $$('#m-trip .js-del').forEach(function (b) { b.hidden = !editing; });
    euModal.open('m-trip');
    setTimeout(function () { $('f-nombre').focus(); }, 20);
  }
  document.addEventListener('click', function (e) {
    if (e.target.closest('.js-new')) openTrip(false);
    else if (e.target.closest('.js-edit')) openTrip(true);
  });
  $('f-trip').addEventListener('submit', function (e) {
    e.preventDefault();
    var nombre = $('f-nombre').value.trim(), inicio = $('f-inicio').value, fin = $('f-fin').value;
    if (!nombre) { setErr('modal-err', 'El nombre es obligatorio'); $('f-nombre').focus(); return; }
    if (!inicio) { setErr('modal-err', 'Ingresa la fecha de inicio'); $('f-inicio').focus(); return; }
    if (!fin) { setErr('modal-err', 'Ingresa la fecha de fin'); $('f-fin').focus(); return; }
    if (fin < inicio) { setErr('modal-err', 'La fecha fin debe ser posterior al inicio'); $('f-fin').focus(); return; }
    var payload = {
      nombre: nombre, destino: $('f-destino').value.trim(), fecha_inicio: inicio, fecha_fin: fin,
      estado: $('f-estado').value, tipo_clima: $('f-clima').value, ocasion: $('f-ocasion').value, notas: $('f-notas').value.trim(),
    };
    if ($('f-presupuesto')) payload.presupuesto = parseFloat($('f-presupuesto').value) || 0;
    var btn = document.querySelector('[form="f-trip"]'); btn.disabled = true;
    send(editing ? API + '/trips/' + curId : API + '/trips', editing ? 'PATCH' : 'POST', payload).then(function (r) {
      if (!r.ok) { setErr('modal-err', r.error || 'Error al guardar'); return; }
      euModal.close('m-trip'); toast(editing ? 'Viaje actualizado ✓' : 'Viaje creado ✓', 'ok');
      var id = editing ? curId : r.id;
      return loadTrips().then(function () { return id ? showDetail(id) : renderList(); });
    }).catch(function () { setErr('modal-err', 'Sin conexión'); }).finally(function () { btn.disabled = false; });
  });
  $$('#m-trip .js-del').forEach(function (b) {
    b.addEventListener('click', function () {
      var name = curTrip ? curTrip.nombre : 'este viaje';
      euConfirm('¿Eliminar «' + name + '»? Se borran sus días, outfits y maleta; los movimientos de Oikonomia solo se desvinculan.', { confirmLabel: 'Eliminar' }).then(function (ok) {
        if (!ok) return;
        send(API + '/trips/' + curId, 'DELETE').then(function (r) {
          if (!r.ok) { toast('No se pudo eliminar', 'err'); return; }
          euModal.close('m-trip'); toast('Viaje eliminado'); return loadTrips().then(showList);
        }).catch(function () { toast('Sin conexión', 'err'); });
      });
    });
  });
  $$('.js-back').forEach(function (b) { b.addEventListener('click', function () { loadTrips().then(showList); }); });

  /* ── Boot: ?id= (o ?trip=, enlaces viejos) abre el viaje; ?nuevo=1 el alta ── */
  loadTrips().then(function () {
    var q = new URLSearchParams(location.search), tp = Number(q.get('id') || q.get('trip'));
    if (tp && trips.some(function (t) { return t.id === tp; })) showDetail(tp); else renderList();
    if (q.get('nuevo') === '1') { history.replaceState(null, '', location.pathname); openTrip(false); }
  }).catch(function () { $('trip-sections').innerHTML = '<div class="eu-card">' + emptyHtml('wifi-off', 'Sin conexión', 'No se pudieron cargar tus viajes.') + '</div>'; icons(); });
})();
