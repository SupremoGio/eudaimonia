/* Viajes — Design System V2: lista agrupada (vigentes / próximos / pasados) y
   detalle con outfit por día (picker desde Guardarropa), maleta por categorías
   (generada desde outfits + extras, prendas o ítems sueltos) y checklist de regreso. */
(function () {
  'use strict';
  var root = document.getElementById('vj');
  if (!root) return;
  var API = '/viajes/api';
  var TODAY = root.dataset.today || new Date().toISOString().slice(0, 10);
  var CAT_ORDER = ['Documentos', 'Tops', 'Bottoms', 'Calzado', 'Ropa interior', 'Formal', 'Abrigo', 'Accesorios', 'Higiene', 'Tecnología', 'Salud', 'Ropa', 'Varios'];
  var ESTADO = { planificado: ['Planificado', 'eu-badge--info'], activo: ['En curso', 'eu-badge--success'], completado: ['Completado', ''], cancelado: ['Cancelado', 'eu-badge--danger'] };
  var CLIMA = { calor: 'Calor / Playa', frio: 'Frío / Nieve', templado: 'Templado', lluvia: 'Lluvioso' };
  var OCASION = { negocios: 'Negocios', casual: 'Casual / Turismo', playa: 'Playa / Resort', aventura: 'Aventura / Outdoor', formal: 'Evento formal' };

  var trips = [], curId = null, curTrip = null, dias = [], maleta = [], outfits = null, wardrobe = null;
  var editing = false, pickerDia = null, activeTab = 'outfits', aiMode = 'wardrobe';

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function fmtD(s) { return s ? s.slice(0, 10).split('-').reverse().join('/') : '—'; }
  function getJ(url) { return fetch(url).then(function (r) { return r.json(); }); }
  function send(url, method, body) {
    var o = { method: method };
    if (body !== undefined) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(url, o).then(function (r) { return r.json(); });
  }
  function plural(n, s, p) { return n + ' ' + (n === 1 ? s : (p || s + 's')); }
  function emptyHtml(ic, t, txt) {
    return '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p></div>';
  }
  function setErr(id, msg) { var e = $(id); e.hidden = !msg; e.querySelector('span').textContent = msg || ''; }
  function setProg(id, n, total) {
    var bar = $(id), pct = total ? Math.round(n / total * 100) : 0;
    bar.setAttribute('aria-valuenow', pct); bar.querySelector('i').style.width = pct + '%';
    return pct;
  }
  function swatch(hex, cls) { return '<span class="vj-sw ' + (cls || '') + '" style="--sw:' + esc(hex || '#444') + '"></span>'; }
  function photo(foto, cls) { return '<img class="' + cls + '" src="/guardarropa/photos/' + esc(foto) + '" alt="" loading="lazy">'; }

  /* ── Lista ──────────────────────────────────────────────────────────── */
  function loadTrips() { return getJ(API + '/trips').then(function (t) { trips = t || []; }); }

  function tripCard(t) {
    var est = ESTADO[t.estado] || [t.estado, ''];
    var d = t.total_dias || 0, p = t.items_packed || 0;
    return '<button type="button" class="eu-card eu-card--interactive vj-card" data-trip="' + t.id + '" aria-label="Ver detalle de ' + esc(t.nombre) + '">' +
      '<span class="eu-between vj-card-top"><span class="t-card vj-card-t">' + esc(t.nombre) + '</span><span class="eu-badge eu-badge--status ' + est[1] + '">' + esc(est[0]) + '</span></span>' +
      (t.destino ? '<span class="t-meta vj-card-dest"><i data-lucide="map-pin"></i>' + esc(t.destino) + '</span>' : '') +
      '<span class="t-data vj-card-dates">' + fmtD(t.fecha_inicio) + ' — ' + fmtD(t.fecha_fin) + '</span>' +
      '<span class="eu-between vj-card-ft"><span class="t-meta">' + plural(d, 'día') + ' · ' + plural(p, 'ítem') + ' empacado' + (p !== 1 ? 's' : '') + '</span><span class="t-meta fg-brand vj-card-go">Ver<i data-lucide="arrow-right"></i></span></span>' +
      '</button>';
  }

  function renderList() {
    setView('list');
    var box = $('trip-sections');
    var g = { vigente: [], proximo: [], pasado: [] };
    trips.forEach(function (t) {
      if (t.fecha_fin < TODAY) g.pasado.push(t);
      else if (t.fecha_inicio > TODAY) g.proximo.push(t);
      else g.vigente.push(t);
    });
    g.vigente.sort(function (a, b) { return a.fecha_inicio.localeCompare(b.fecha_inicio); });
    g.proximo.sort(function (a, b) { return a.fecha_inicio.localeCompare(b.fecha_inicio); });
    g.pasado.sort(function (a, b) { return b.fecha_inicio.localeCompare(a.fecha_inicio); });
    var sv = $$('#vj-stats .eu-stat-val');
    sv[0].textContent = g.vigente.length; sv[1].textContent = g.proximo.length; sv[2].textContent = g.pasado.length;

    if (!trips.length) {
      box.innerHTML = '<div class="eu-card">' + emptyHtml('plane', 'Aún no tienes viajes', 'Crea tu primer viaje para planear outfits por día y armar la maleta.') +
        '<div class="vj-empty-cta"><button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Crear primer viaje</button></div></div>';
      $$('.js-new', box).forEach(function (b) { b.addEventListener('click', function () { openTrip(false); }); });
      icons(); return;
    }
    box.innerHTML = [
      { k: 'vigente', l: 'Vigentes', ic: 'plane', t: g.vigente },
      { k: 'proximo', l: 'Próximos', ic: 'calendar-clock', t: g.proximo },
      { k: 'pasado', l: 'Pasados', ic: 'history', t: g.pasado },
    ].map(function (s) {
      return '<section class="vj-sec vj-sec--' + s.k + '" aria-label="' + s.l + '"><h2 class="t-eyebrow vj-sec-t"><i data-lucide="' + s.ic + '"></i>' + s.l + ' <span class="num">(' + s.t.length + ')</span></h2>' +
        (s.t.length ? '<div class="vj-grid">' + s.t.map(tripCard).join('') + '</div>' : euEmpty('calendar-x', 'Sin viajes ' + s.l.toLowerCase(), '', true)) + '</section>';
    }).join('');
    icons();
  }
  $('trip-sections').addEventListener('click', function (e) {
    var c = e.target.closest('[data-trip]'); if (c) showDetail(+c.dataset.trip);
  });

  function setView(v) {
    root.dataset.view = v;
    $('vw-list').hidden = v !== 'list';
    $('vw-detail').hidden = v !== 'detail';
    var nb = document.querySelector('.eu-topbar .js-new'); if (nb) nb.hidden = v !== 'list';
  }
  function showList() {
    curId = null; curTrip = null;
    history.replaceState(null, '', location.pathname);
    renderList(); window.scrollTo(0, 0);
  }

  /* ── Detalle ────────────────────────────────────────────────────────── */
  function showDetail(id) {
    curId = id;
    setView('detail');
    $('detail-title').textContent = 'Cargando…';
    history.replaceState(null, '', location.pathname + '?trip=' + id);
    return Promise.all([
      getJ(API + '/trips/' + id), getJ(API + '/trips/' + id + '/dias'), getJ(API + '/trips/' + id + '/maleta'),
      outfits ? Promise.resolve(outfits) : getJ(API + '/outfits'),
    ]).then(function (r) {
      curTrip = r[0]; dias = r[1] || []; maleta = r[2] || []; outfits = r[3] || [];
      renderHeader(); switchTab(activeTab); window.scrollTo(0, 0);
    }).catch(function () { toast('No se pudo cargar el viaje', 'err'); showList(); });
  }
  function renderHeader() {
    var t = curTrip, est = ESTADO[t.estado] || [t.estado, ''];
    $('detail-title').textContent = t.nombre;
    var b = $('detail-estado-badge'); b.className = 'eu-badge eu-badge--status ' + est[1]; b.textContent = est[0];
    $('detail-destino').textContent = t.destino || '—';
    $('detail-fechas').textContent = fmtD(t.fecha_inicio) + ' — ' + fmtD(t.fecha_fin);
    var noches = Math.round((new Date(t.fecha_fin) - new Date(t.fecha_inicio)) / 86400000);
    $('detail-duracion').textContent = plural(t.total_dias, 'día') + ' / ' + plural(noches, 'noche');
    // Mismo viaje, misma fila en `viajes`: el presupuesto vive en Estados de Cuenta (Oikonomia).
    $('detail-presupuesto-link').href = '/finanzas/estados/viajes/?trip=' + t.id;
    var extra = [CLIMA[t.tipo_clima] || t.tipo_clima, OCASION[t.ocasion] || t.ocasion].filter(Boolean);
    $('detail-clima').textContent = extra.length ? extra.join(' · ') : '—';
  }
  function switchTab(tab) {
    activeTab = tab;
    ['outfits', 'maleta', 'regreso'].forEach(function (t) {
      $('tab-' + t).setAttribute('aria-selected', String(t === tab));
      $('pane-' + t).hidden = t !== tab;
    });
    if (tab === 'outfits') renderOutfits();
    if (tab === 'maleta') renderMaleta();
    if (tab === 'regreso') renderRegreso();
  }
  $$('[data-pane]').forEach(function (b) { b.addEventListener('click', function () { switchTab(b.dataset.pane); }); });
  $$('.js-back').forEach(function (b) { b.addEventListener('click', showList); });

  /* ── Outfits por día ────────────────────────────────────────────────── */
  function mosaic(items) {
    var all = (items || []).filter(function (i) { return i.foto; }).concat((items || []).filter(function (i) { return !i.foto; })).slice(0, 4);
    if (!all.length) return '<span class="vj-mosaic vj-mosaic--empty"><i data-lucide="shirt"></i></span>';
    return '<span class="vj-mosaic vj-mosaic--' + all.length + '">' + all.map(function (i) {
      return i.foto ? photo(i.foto, 'vj-ms') : swatch(i.color_hex, 'vj-ms');
    }).join('') + '</span>';
  }
  function thumb(o) {
    var full = (outfits || []).filter(function (x) { return x.id === o.id; })[0];
    var items = full ? full.items || [] : [];
    var wp = items.filter(function (i) { return i.foto; })[0];
    if (wp) return photo(wp.foto, 'vj-thumb');
    if (items[0]) return swatch(items[0].color_hex, 'vj-thumb');
    return '<span class="vj-thumb vj-thumb--ic"><i data-lucide="shirt"></i></span>';
  }
  function renderOutfits() {
    var el = $('dias-list');
    if (!dias.length) {
      el.innerHTML = '<li>' + emptyHtml('calendar-x', 'Sin días cargados', 'Este viaje aún no tiene itinerario de días para planificar outfits.') + '</li>';
      $('outfits-progress-txt').textContent = ''; setProg('outfits-prog', 0, 0); icons(); return;
    }
    var con = dias.filter(function (d) { return d.outfits && d.outfits.length; }).length;
    $('outfits-progress-txt').textContent = con + ' de ' + dias.length + ' días con outfit';
    setProg('outfits-prog', con, dias.length);
    el.innerHTML = dias.map(function (d, i) {
      var o = d.outfits && d.outfits[0];
      var wd = new Date(d.fecha + 'T12:00:00').toLocaleDateString('es-MX', { weekday: 'short' });
      return '<li class="vj-day' + (o ? ' has-outfit' : '') + (d.fecha === TODAY ? ' is-today' : '') + '">' +
        '<span class="vj-day-n"><span class="t-meta">Día</span><span class="t-data">' + (i + 1) + '</span></span>' +
        '<span class="vj-day-bd"><span class="t-ui">' + esc(wd) + ' · <span class="num">' + fmtD(d.fecha) + '</span></span>' + (d.descripcion ? '<span class="t-meta">' + esc(d.descripcion) + '</span>' : '') + '</span>' +
        (o ? '<span class="vj-day-act"><button type="button" class="vj-ochip" data-pick="' + d.id + '" aria-label="Cambiar outfit: ' + esc(o.nombre) + '">' + thumb(o) + '<span class="vj-ochip-t">' + esc(o.nombre) + '</span></button>' +
          '<button type="button" class="eu-iconbtn" data-unpick="' + d.id + '" aria-label="Quitar outfit del día ' + (i + 1) + '"><i data-lucide="x"></i></button></span>'
          : '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm vj-day-add" data-pick="' + d.id + '"><i data-lucide="plus"></i>Elegir outfit</button>') +
        '</li>';
    }).join('');
    icons();
  }
  $('dias-list').addEventListener('click', function (e) {
    var p = e.target.closest('[data-pick]'), u = e.target.closest('[data-unpick]');
    if (p) openPicker(+p.dataset.pick);
    else if (u) unassign(+u.dataset.unpick);
  });

  function openPicker(diaId) {
    pickerDia = dias.filter(function (d) { return d.id === diaId; })[0]; if (!pickerDia) return;
    $('picker-day-label').textContent = fmtD(pickerDia.fecha) + (pickerDia.descripcion ? ' — ' + pickerDia.descripcion : '');
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
    send(API + '/trips/' + curId + '/dias/' + pickerDia.id + '/outfit', 'POST', { outfit_id: +c.dataset.outfit }).then(function (r) {
      if (!r.ok) { toast(r.error || 'Error', 'err'); return; }
      euModal.close('m-picker'); toast('Outfit asignado ✓', 'ok'); afterOutfitChange();
    }).catch(function () { toast('Sin conexión', 'err'); });
  });
  $('btn-quitar-outfit').addEventListener('click', function () {
    if (!pickerDia) return; var id = pickerDia.id; euModal.close('m-picker'); unassign(id);
  });
  function unassign(diaId) {
    send(API + '/trips/' + curId + '/dias/' + diaId + '/outfit', 'DELETE').then(function (r) {
      if (r.ok) { toast('Outfit quitado'); afterOutfitChange(); }
    }).catch(function () { toast('Sin conexión', 'err'); });
  }
  // Tras cambiar outfits se recalcula la maleta en silencio, para que las prendas
  // aparezcan en el checklist sin tener que pulsar «Generar».
  function afterOutfitChange() {
    return getJ(API + '/trips/' + curId + '/dias').then(function (d) { dias = d || []; renderOutfits(); })
      .then(function () { return send(API + '/trips/' + curId + '/maleta/generar', 'POST', {}); })
      .then(function (r) { if (r && r.ok) return reloadMaleta(); });
  }
  function reloadMaleta() {
    return getJ(API + '/trips/' + curId + '/maleta').then(function (m) {
      maleta = m || [];
      if (activeTab === 'maleta') renderMaleta();
      if (activeTab === 'regreso') renderRegreso();
    });
  }

  /* ── Maleta y regreso ───────────────────────────────────────────────── */
  function grouped() {
    var cats = {};
    maleta.forEach(function (m) { (cats[m.categoria] = cats[m.categoria] || []).push(m); });
    return CAT_ORDER.filter(function (c) { return cats[c]; }).concat(Object.keys(cats).filter(function (c) { return CAT_ORDER.indexOf(c) < 0; }))
      .map(function (c) { return { cat: c, items: cats[c] }; });
  }
  function itemThumb(m) {
    if (m.item_foto) return photo(m.item_foto, 'vj-ithumb');
    if (m.item_color) return swatch(m.item_color, 'vj-ithumb');
    return '';
  }
  function listHtml(field, withDel) {
    return grouped().map(function (g) {
      var done = g.items.filter(function (m) { return m[field]; }).length;
      return '<section class="vj-cat"><h3 class="eu-between t-eyebrow vj-cat-t"><span>' + esc(g.cat) + '</span><span class="num t-meta">' + done + '/' + g.items.length + '</span></h3><ul class="vj-items">' +
        g.items.map(function (m) {
          var on = !!m[field];
          return '<li class="vj-item' + (on ? ' is-done' : '') + '">' +
            '<button type="button" class="vj-chk" role="checkbox" aria-checked="' + on + '" data-chk="' + m.id + '" data-field="' + field + '">' +
            '<span class="vj-chk-box" aria-hidden="true"><i data-lucide="check"></i></span>' + itemThumb(m) +
            '<span class="vj-item-t">' + esc(m.nombre) + (m.cantidad > 1 ? ' <span class="t-meta num">×' + m.cantidad + '</span>' : '') + '</span></button>' +
            (withDel ? '<button type="button" class="eu-iconbtn vj-item-del" data-del="' + m.id + '" aria-label="Eliminar ' + esc(m.nombre) + '"><i data-lucide="x"></i></button>' : '') +
            '</li>';
        }).join('') + '</ul></section>';
    }).join('');
  }
  function progTxt(field, id, barId, suffix) {
    var n = maleta.filter(function (m) { return m[field]; }).length, t = maleta.length;
    var pct = setProg(barId, n, t);
    $(id).textContent = t ? n + ' de ' + t + ' ítems empacados' + suffix + ' (' + pct + '%)' : '';
    return { n: n, t: t };
  }
  function renderMaleta() {
    progTxt('packed_ida', 'maleta-progress-txt', 'maleta-prog', '');
    $('maleta-list').innerHTML = maleta.length ? listHtml('packed_ida', true)
      : emptyHtml('luggage', 'Tu maleta está vacía', 'Asigna outfits a tus días en «Outfits por día» y aquí irán apareciendo las prendas, o genera la lista con extras estándar.');
    icons();
  }
  function renderRegreso() {
    progTxt('packed_vuelta', 'regreso-progress-txt', 'regreso-prog', ' de regreso');
    $('regreso-list').innerHTML = maleta.length ? listHtml('packed_vuelta', false)
      : emptyHtml('package-check', 'Nada que revisar aún', 'Genera tu maleta primero, en la pestaña «Mi maleta», para ver aquí el checklist de regreso.');
    icons();
  }
  function onListClick(e) {
    var c = e.target.closest('[data-chk]'), d = e.target.closest('[data-del]');
    if (c) {
      var id = +c.dataset.chk, field = c.dataset.field, item = maleta.filter(function (m) { return m.id === id; })[0];
      if (!item) return;
      var now = !item[field];
      item[field] = now ? 1 : 0;
      c.setAttribute('aria-checked', String(now)); c.closest('.vj-item').classList.toggle('is-done', now);
      var st = field === 'packed_ida' ? progTxt(field, 'maleta-progress-txt', 'maleta-prog', '') : progTxt(field, 'regreso-progress-txt', 'regreso-prog', ' de regreso');
      var sec = c.closest('.vj-cat'); var cnt = sec.querySelector('.vj-cat-t .num');
      cnt.textContent = sec.querySelectorAll('[aria-checked=true]').length + '/' + sec.querySelectorAll('[data-chk]').length;
      send(API + '/trips/' + curId + '/maleta/' + id, 'PATCH', { field: field }).then(function () {
        if (field === 'packed_vuelta' && now && st.n === st.t) toast('¡Todo empacado! Viaje completo', 'win');
      }).catch(function () {
        item[field] = now ? 0 : 1; toast('Sin conexión', 'err');
        if (field === 'packed_ida') renderMaleta(); else renderRegreso();
      });
    } else if (d) {
      var did = +d.dataset.del;
      send(API + '/trips/' + curId + '/maleta/' + did, 'DELETE').then(function (r) {
        if (!r.ok) return;
        maleta = maleta.filter(function (m) { return m.id !== did; }); renderMaleta(); toast('Ítem eliminado');
      }).catch(function () { toast('Sin conexión', 'err'); });
    }
  }
  $('maleta-list').addEventListener('click', onListClick);
  $('regreso-list').addEventListener('click', onListClick);

  $('btn-generar').addEventListener('click', function () {
    var btn = this; btn.disabled = true; btn.setAttribute('aria-busy', 'true'); btn.querySelector('span').textContent = 'Generando…';
    send(API + '/trips/' + curId + '/maleta/generar', 'POST', {}).then(function (r) {
      if (!r.ok) { toast(r.error || 'Error al generar', 'err'); return; }
      toast('Maleta generada — ' + plural(r.outfit_items || 0, 'prenda') + ' de tus outfits + extras estándar', 'ok');
      return reloadMaleta();
    }).catch(function () { toast('Sin conexión', 'err'); })
      .finally(function () { btn.disabled = false; btn.removeAttribute('aria-busy'); btn.querySelector('span').textContent = 'Generar desde outfits'; });
  });

  /* ── Agregar ítem ───────────────────────────────────────────────────── */
  function setAi(mode) {
    aiMode = mode;
    $$('[data-ai]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.ai === mode)); });
    $('ai-panel-wardrobe').hidden = mode !== 'wardrobe';
    $('ai-panel-generic').hidden = mode !== 'generic';
    // En modo «prenda» agregar es un clic sobre la tarjeta: no hace falta botón de envío.
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

  /* ── Viaje: crear / editar / eliminar ───────────────────────────────── */
  var F = ['nombre', 'destino', 'estado', 'inicio', 'fin', 'clima', 'ocasion', 'notas'];
  function openTrip(isEdit) {
    editing = !!isEdit && !!curTrip;
    $('m-trip-t').textContent = editing ? 'Editar viaje' : 'Nuevo viaje';
    setErr('modal-err', '');
    var t = editing ? curTrip : {};
    var v = { nombre: t.nombre, destino: t.destino, estado: t.estado || 'planificado', inicio: t.fecha_inicio, fin: t.fecha_fin, clima: t.tipo_clima, ocasion: t.ocasion, notas: t.notas };
    F.forEach(function (k) { $('f-' + k).value = v[k] || ''; });
    euModal.open('m-trip');
    setTimeout(function () { $('f-nombre').focus(); }, 20);
  }
  $$('.js-new').forEach(function (b) { b.addEventListener('click', function () { openTrip(false); }); });
  $$('.js-edit').forEach(function (b) { b.addEventListener('click', function () { openTrip(true); }); });
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
    var btn = document.querySelector('[form="f-trip"]'); btn.disabled = true;
    send(editing ? API + '/trips/' + curId : API + '/trips', editing ? 'PATCH' : 'POST', payload).then(function (r) {
      if (!r.ok) { setErr('modal-err', r.error || 'Error al guardar'); return; }
      euModal.close('m-trip'); toast(editing ? 'Viaje actualizado ✓' : 'Viaje creado ✓', 'ok');
      var id = editing ? curId : r.id;
      return loadTrips().then(function () { return id ? showDetail(id) : renderList(); });
    }).catch(function () { setErr('modal-err', 'Sin conexión'); }).finally(function () { btn.disabled = false; });
  });
  $$('.js-del').forEach(function (b) {
    b.addEventListener('click', function () {
      var name = curTrip ? curTrip.nombre : 'este viaje';
      euConfirm('¿Eliminar «' + name + '»? Se borrarán los días, outfits y maleta de este viaje.', { confirmLabel: 'Eliminar' }).then(function (ok) {
        if (!ok) return;
        send(API + '/trips/' + curId, 'DELETE').then(function (r) {
          if (!r.ok) { toast('No se pudo eliminar', 'err'); return; }
          toast('Viaje eliminado'); return loadTrips().then(showList);
        }).catch(function () { toast('Sin conexión', 'err'); });
      });
    });
  });

  /* ── Boot ───────────────────────────────────────────────────────────── */
  loadTrips().then(function () {
    var tp = Number(new URLSearchParams(location.search).get('trip'));
    if (tp && trips.some(function (t) { return t.id === tp; })) showDetail(tp); else renderList();
  }).catch(function () { $('trip-sections').innerHTML = '<div class="eu-card">' + emptyHtml('wifi-off', 'Sin conexión', 'No se pudieron cargar tus viajes.') + '</div>'; icons(); });
})();
