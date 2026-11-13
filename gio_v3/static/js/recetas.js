/* Recetas — Design System V2: grid filtrable + detalle (en móvil a pantalla
   completa), favoritas, pasos marcables y formulario con filas dinámicas.
   Remates · Recetas S1: «Para hoy» (Usar → POST /nutricion/api/comida),
   categorías en eu-seg, franja de macros, porciones que recalculan las
   cantidades, pasos con casilla y modo «Cocinar» (← → Esc, wakeLock). */
(function () {
  'use strict';
  var root = document.getElementById('rc');
  if (!root) return;
  var ALL = JSON.parse(document.getElementById('rc-data').textContent || '[]');
  var list = ALL.slice(), cat = '', active = null, dropF = null, porc = 1;
  var fodmapOnly = $id('rc-fodmap') && $id('rc-fodmap').getAttribute('aria-pressed') === 'true';
  function $id(i) { return document.getElementById(i); }
  var FOD = { seguro: ['Apta FODMAP', 'success'], porcion: ['FODMAP · porción', 'warning'], evitar: ['FODMAP · evitar', 'danger'] };
  var SLOTS = ['Desayuno', 'Colación AM', 'Comida', 'Colación PM', 'Pre-gym', 'Cena'];
  var MOM_SLOT = { desayuno: 'Desayuno', colacion: 'Colación AM', comida: 'Comida', pregym: 'Pre-gym', cena: 'Cena' };
  function fodBadge(r) { var f = FOD[r.fodmap]; return f ? '<span class="eu-badge eu-badge--' + f[1] + ' rc-fod">' + f[0] + '</span>' : ''; }
  var CAT = { 'Desayuno': 'oikonomia', 'Almuerzo': 'hegemonikon', 'Cena': 'paideia', 'Snack': 'eurythmia', 'Meal Prep': 'cosmopolitismo', 'Post-Entrenamiento': 'harma' };
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function mins(r) { return (r.tiempo_prep || 0) + (r.tiempo_coccion || 0); }

  /* Antetítulo vivo: «N recetas · M aptas FODMAP» (ya no hay stats) */
  function eyebrow() {
    var e = document.querySelector('.rc-hd .t-eyebrow'); if (!e) return;
    var n = ALL.length, a = ALL.filter(function (r) { return r.fodmap === 'seguro'; }).length;
    e.textContent = n + ' receta' + (n !== 1 ? 's' : '') + (a ? ' · ' + a + ' aptas FODMAP' : '');
  }

  /* ── Porciones: recalcula en cliente la cantidad numérica inicial
     («200», «1.5», «1,5», «1/2», «1 1/2»); lo demás («al gusto») queda igual ── */
  function parseQty(s) {
    var m = String(s == null ? '' : s).trim().match(/^(\d+)\s+(\d+)\/(\d+)|^(\d+)\/(\d+)|^(\d+(?:[.,]\d+)?)/);
    if (!m) return null;
    var n = m[1] ? +m[1] + m[2] / m[3] : m[4] ? m[4] / m[5] : parseFloat(m[6].replace(',', '.'));
    return { n: n, rest: String(s).trim().slice(m[0].length) };
  }
  function fmtQty(n) { return (Math.round(n * 100) / 100).toLocaleString('es-MX', { maximumFractionDigits: 2 }); }
  function escalar(s, factor) {
    var q = parseQty(s);
    return q && factor !== 1 ? fmtQty(q.n * factor) + q.rest : String(s == null ? '' : s);
  }
  function filter() {
    var q = $('rc-q').value.trim().toLowerCase();
    function match(r, skip) {
      return (skip === 'cat' || !cat || r.categoria === cat) && (skip === 'fodmap' || !fodmapOnly || r.fodmap === 'seguro') &&
        (skip === 'q' || !q || r.nombre.toLowerCase().indexOf(q) >= 0 || (r.tags || '').toLowerCase().indexOf(q) >= 0 ||
        (r.ingredientes || []).some(function (i) { return String(i.item || i).toLowerCase().indexOf(q) >= 0; }));
    }
    list = ALL.filter(function (r) { return match(r); });
    var act = [];
    if (cat) act.push({ key: 'cat', label: cat });
    if (fodmapOnly) act.push({ key: 'fodmap', label: 'FODMAP seguro' });
    if (q) act.push({ key: 'q', label: $('rc-q').value.trim() });
    dropF = list.length ? null : window.euDropFilter(act, function (k) { return ALL.filter(function (r) { return match(r, k); }).length; });
    render();
  }
  function macroChips(r) {
    return [r.calorias ? '<span class="eu-badge num">' + r.calorias + ' kcal</span>' : '', r.proteina ? '<span class="eu-badge eu-badge--success num">' + Math.round(r.proteina) + 'g P</span>' : '',
      r.carbos ? '<span class="eu-badge eu-badge--info num">' + Math.round(r.carbos) + 'g C</span>' : '', r.grasa ? '<span class="eu-badge eu-badge--warning num">' + Math.round(r.grasa) + 'g G</span>' : ''].join('');
  }
  function render() {
    var g = $('rc-grid');
    if (!list.length) {
      g.innerHTML = ALL.length
        ? window.euEmptyFilter('Ninguna receta coincide con estos filtros.', dropF ? 'Sin «' + dropF.label + '» hay ' + dropF.count + '.' : 'Prueba con otro filtro.', dropF, 'rc-span')
        : '<div class="eu-card rc-span">' + window.euEmpty('cooking-pot', 'Aún no tienes recetas', 'Agrega la primera para empezar tu recetario.', false,
            '<button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Nueva receta</button>') + '</div>';
      icons(); return;
    }
    g.innerHTML = list.map(function (r) {
      var m = mins(r);
      return '<article class="eu-card rc-card" data-cat="' + (CAT[r.categoria] || 'hegemonikon') + '">' +
        '<button type="button" class="rc-card-open js-open" data-id="' + r.id + '" aria-pressed="' + (active === r.id) + '">' +
          '<span class="t-eyebrow rc-card-cat">' + esc(r.categoria) + '</span><span class="t-ui rc-card-t">' + esc(r.nombre) + '</span>' + fodBadge(r) +
          (macroChips(r) ? '<span class="rc-chips">' + macroChips(r) + '</span>' : '') +
          '<span class="t-meta rc-card-m">' + (m ? '<span><i data-lucide="clock"></i>' + m + ' min</span>' : '') + (r.porciones ? '<span><i data-lucide="utensils"></i>' + r.porciones + ' porc.</span>' : '') + '</span></button>' +
        '<button type="button" class="eu-iconbtn rc-fav js-fav" data-id="' + r.id + '" aria-pressed="' + !!r.favorita + '" aria-label="Favorita: ' + esc(r.nombre) + '"><i data-lucide="star"></i></button></article>';
    }).join('');
    icons();
  }

  function open(id) {
    var r = ALL.find(function (x) { return x.id === id; }); if (!r) return;
    active = id;
    document.querySelectorAll('.js-open').forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.id === id)); });
    var video = '';
    if (r.video_url) {
      var yt = r.video_url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]{11})/);
      video = yt ? '<div class="rc-video"><iframe src="https://www.youtube.com/embed/' + yt[1] + '" title="Video de la receta" allowfullscreen loading="lazy"></iframe></div>'
        : '<a class="eu-btn eu-btn--secondary eu-btn--sm rc-vlink" href="' + esc(r.video_url) + '" target="_blank" rel="noopener"><i data-lucide="play-circle"></i>Ver video</a>';
    }
    porc = r.porciones || 1;
    function cell(lbl, v, u, cls) { return '<div class="rc-mcell ' + cls + '"><span class="t-meta">' + lbl + '</span><span class="rc-mcell-v num">' + (v ? Math.round(v) + u : '—') + '</span></div>'; }
    var ings = (r.ingredientes || []).length ? '<ul class="rc-ings" id="rc-ings">' + ingsHtml(r, 1) + '</ul>' : '';
    var steps = (r.instrucciones || []).map(function (s, i) {
      return '<li><button type="button" class="rc-step js-step" aria-pressed="false"><span class="rc-step-box" aria-hidden="true"><i data-lucide="check"></i></span><span class="rc-step-n num">' + (i + 1) + '</span><span>' + esc(s) + '</span></button></li>';
    }).join('');
    var m = mins(r);
    $('rc-content').innerHTML =
      '<div class="rc-d-hd" data-cat="' + (CAT[r.categoria] || 'hegemonikon') + '"><button type="button" class="eu-iconbtn rc-back js-close" aria-label="Volver"><i data-lucide="chevron-left"></i></button>' +
        '<div class="eu-grow"><span class="eu-hstack rc-d-badges"><span class="eu-badge eu-badge--cat">' + esc(r.categoria) + '</span>' + fodBadge(r) + '</span><h2 class="t-section">' + esc(r.nombre) + '</h2>' +
        (r.descripcion ? '<p class="t-meta fg-2">' + esc(r.descripcion) + '</p>' : '') +
        '<div class="rc-card-m t-meta">' + (r.tiempo_prep ? '<span><i data-lucide="clock"></i>Prep ' + r.tiempo_prep + ' min</span>' : '') + (r.tiempo_coccion ? '<span><i data-lucide="flame"></i>Cocción ' + r.tiempo_coccion + ' min</span>' : '') +
        (r.porciones ? '<span><i data-lucide="utensils"></i>' + r.porciones + ' porción' + (r.porciones > 1 ? 'es' : '') + '</span>' : '') + '</div></div></div>' +
      '<div class="rc-hoy"><label class="t-meta" for="rc-hoy-slot">Agregar a hoy</label><select class="eu-select rc-hoy-sel" id="rc-hoy-slot">' +
        SLOTS.map(function (s) { var def = MOM_SLOT[(r.momento || '').split(',')[0]] || 'Comida'; return '<option' + (s === def ? ' selected' : '') + '>' + s + '</option>'; }).join('') +
        '</select><button type="button" class="eu-btn eu-btn--secondary eu-btn--sm js-hoy" data-id="' + r.id + '"><i data-lucide="calendar-plus"></i>Agregar a hoy</button></div>' +
      ((r.proteina || r.carbos || r.grasa || r.calorias) ? '<div class="eu-vstack rc-sec"><div class="t-eyebrow">Macros por porción</div><div class="rc-mstrip">' +
        cell('Kcal', r.calorias, '', 'is-k') + cell('Proteína', r.proteina, ' g', 'is-p') + cell('Carbos', r.carbos, ' g', 'is-c') + cell('Grasa', r.grasa, ' g', 'is-g') + '</div></div>' : '') +
      video +
      (ings ? '<div class="eu-vstack rc-sec"><div class="rc-sec-hd"><div class="t-eyebrow">Ingredientes</div>' +
        '<div class="rc-porc" role="group" aria-label="Porciones"><button type="button" class="eu-iconbtn js-porc" data-d="-1" aria-label="Menos porciones"><i data-lucide="minus"></i></button>' +
        '<span class="t-meta"><output class="num" id="rc-porc-n" aria-live="polite">' + porc + '</output> porc.</span>' +
        '<button type="button" class="eu-iconbtn js-porc" data-d="1" aria-label="Más porciones"><i data-lucide="plus"></i></button></div></div>' + ings + '</div>' : '') +
      (steps ? '<div class="eu-vstack rc-sec"><div class="rc-sec-hd"><div class="t-eyebrow">Pasos · toca para marcar</div>' +
        '<button type="button" class="eu-btn eu-btn--primary eu-btn--sm js-cook" data-id="' + r.id + '"><i data-lucide="chef-hat"></i>Cocinar</button></div><ol class="rc-steps">' + steps + '</ol></div>' : '') +
      '<div class="eu-hstack rc-d-act"><button type="button" class="eu-btn eu-btn--secondary eu-grow js-edit" data-id="' + r.id + '"><i data-lucide="pencil"></i>Editar</button>' +
        '<button type="button" class="eu-btn eu-btn--danger js-del" data-id="' + r.id + '"><i data-lucide="trash-2"></i>Eliminar</button></div>';
    $('rc-content').hidden = false; $('rc-empty').hidden = true; $('rc-detail').dataset.open = 'true';
    icons();
  }
  function ingsHtml(r, factor) {
    return (r.ingredientes || []).map(function (i) {
      if (typeof i === 'string') return '<li><span>' + esc(i) + '</span></li>';
      var c = escalar(i.cantidad || '', factor);
      return '<li><span>' + esc(i.item || '') + '</span><span class="t-meta num">' + esc(c) + (i.unidad ? ' ' + esc(i.unidad) : '') + '</span></li>';
    }).join('');
  }
  function setPorc(n) {
    var r = ALL.find(function (x) { return x.id === active; }); if (!r) return;
    porc = Math.max(1, Math.min(50, n));
    $('rc-porc-n').textContent = porc;
    $('rc-ings').innerHTML = ingsHtml(r, porc / (r.porciones || 1));
  }

  /* ── Cocinar: un paso a la vez, 24px, wakeLock si existe ── */
  var cook = { r: null, i: 0, lock: null };
  function cookPaint() {
    var pasos = cook.r.instrucciones || [];
    $('rc-cook-n').textContent = 'Paso ' + (cook.i + 1) + ' de ' + pasos.length;
    $('rc-cook-step').textContent = pasos[cook.i];
    document.querySelector('.js-cook-prev').disabled = cook.i === 0;
    var nx = document.querySelector('.js-cook-next');
    nx.innerHTML = cook.i === pasos.length - 1 ? 'Terminar<i data-lucide="check"></i>' : 'Siguiente<i data-lucide="arrow-right"></i>';
    icons();
  }
  function cookGo(d) {
    var n = (cook.r.instrucciones || []).length;
    if (d > 0 && cook.i === n - 1) { window.euDialog.close($('rc-cook')); toast('¡Buen provecho!'); return; }
    cook.i = Math.max(0, Math.min(n - 1, cook.i + d)); cookPaint();
  }
  async function wake(on) {
    try {
      if (on && 'wakeLock' in navigator) cook.lock = await navigator.wakeLock.request('screen');
      else if (!on && cook.lock) { await cook.lock.release(); cook.lock = null; }
    } catch (_) { cook.lock = null; }   // sin permiso o sin soporte: la pantalla puede apagarse
  }
  function cookOpen(r, from) {
    if (!(r.instrucciones || []).length) return;
    cook.r = r; cook.i = 0;
    $('rc-cook-t').textContent = r.nombre;
    cookPaint();
    window.euDialog.open($('rc-cook'), from, { box: $('rc-cook').querySelector('.rc-cook-in'), focus: '.js-cook-next',
      onClose: function () { wake(false); } });
    wake(true);
  }
  document.addEventListener('visibilitychange', function () {   // el navegador suelta el lock al ocultar la pestaña
    if (document.visibilityState === 'visible' && window.euDialog.isOpen($('rc-cook')) && !cook.lock) wake(true);
  });
  $('rc-cook').addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { e.preventDefault(); cookGo(1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); cookGo(-1); }
  });
  document.querySelector('.js-cook-prev').addEventListener('click', function () { cookGo(-1); });
  document.querySelector('.js-cook-next').addEventListener('click', function () { cookGo(1); });
  document.querySelector('.js-cook-x').addEventListener('click', function () { window.euDialog.close($('rc-cook')); });

  /* ── «Para hoy»: Usar asigna la receta al momento con el endpoint de Nutrición ── */
  function usar(b) {
    var id = +b.dataset.id, slot = b.dataset.slot, r = ALL.find(function (x) { return x.id === id; });
    b.setAttribute('aria-busy', 'true');
    fetch('/nutricion/api/comida', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ receta_id: id, slot: slot }) })
      .then(function (res) { return res.json(); }).then(function (d) {
        b.removeAttribute('aria-busy');
        if (!d.meal) { toast('No se pudo asignar', 'err'); return; }
        var row = b.closest('.rc-today-row'), list = row.parentNode;
        row.remove();
        if (!list.children.length) $('rc-today').remove();
        else (list.querySelector('.js-usar') || document.body).focus();
        toast('«' + (r ? r.nombre : d.meal.name) + '» en ' + slot + ' · hoy', 'ok');
      }).catch(function () { b.removeAttribute('aria-busy'); toast('Sin conexión', 'err'); });
  }

  function close() {
    active = null; $('rc-content').hidden = true; $('rc-empty').hidden = false; delete $('rc-detail').dataset.open;
    document.querySelectorAll('.js-open').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
  }

  /* ── Formulario ── */
  function ingRow(i) {
    var d = document.createElement('div'); d.className = 'rc-row rc-row--ing';
    d.innerHTML = '<input class="eu-input" placeholder="Ingrediente" aria-label="Ingrediente" value="' + esc(i && i.item || (typeof i === 'string' ? i : '')) + '">' +
      '<input class="eu-input" placeholder="Cant." aria-label="Cantidad" value="' + esc(i && i.cantidad || '') + '"><input class="eu-input" placeholder="Unid." aria-label="Unidad" value="' + esc(i && i.unidad || '') + '">' +
      '<button type="button" class="eu-iconbtn js-rm-row" aria-label="Quitar"><i data-lucide="x"></i></button>';
    $('ing-list').appendChild(d);
  }
  function stepRow(s) {
    var d = document.createElement('div'); d.className = 'rc-row rc-row--step';
    d.innerHTML = '<span class="rc-step-n num"></span><textarea class="eu-textarea" rows="2" placeholder="Describe el paso…" aria-label="Paso">' + esc(typeof s === 'string' ? s : '') + '</textarea>' +
      '<button type="button" class="eu-iconbtn js-rm-row" aria-label="Quitar"><i data-lucide="x"></i></button>';
    $('step-list').appendChild(d); renumber();
  }
  function renumber() { document.querySelectorAll('#step-list .rc-step-n').forEach(function (n, i) { n.textContent = i + 1; }); }
  function form(r) {
    $('m-rc-t').textContent = r ? 'Editar receta' : 'Nueva receta';
    var v = { 'rm-id': r ? r.id : '', 'rm-nombre': r ? r.nombre : '', 'rm-categoria': r ? r.categoria : 'Almuerzo', 'rm-descripcion': r ? r.descripcion : '', 'rm-porciones': r ? r.porciones : 1,
      'rm-prep': r ? r.tiempo_prep : 0, 'rm-coccion': r ? r.tiempo_coccion : 0, 'rm-cal': r ? r.calorias : '', 'rm-pro': r ? r.proteina : '', 'rm-carb': r ? r.carbos : '', 'rm-fat': r ? r.grasa : '', 'rm-video': r ? r.video_url : '' };
    Object.keys(v).forEach(function (k) { $(k).value = v[k] == null ? '' : v[k]; });
    $('rm-fav').checked = !!(r && r.favorita);
    $('rm-fodmap').value = (r && r.fodmap) || '';
    var moms = ((r && r.momento) || '').split(',');
    document.querySelectorAll('#rm-momento [data-mom]').forEach(function (b) { b.setAttribute('aria-pressed', String(moms.indexOf(b.dataset.mom) >= 0)); });
    $('rm-err').hidden = true;
    $('rc-avanzado').open = !!(r && (r.calorias || r.proteina || r.carbos || r.grasa || r.tiempo_prep || r.tiempo_coccion || r.video_url || r.descripcion));
    $('ing-list').innerHTML = ''; $('step-list').innerHTML = '';
    ((r && r.ingredientes && r.ingredientes.length) ? r.ingredientes : [null]).forEach(ingRow);
    ((r && r.instrucciones && r.instrucciones.length) ? r.instrucciones : ['']).forEach(stepRow);
    icons(); euModal.open('m-rc'); setTimeout(function () { $('rm-nombre').focus(); }, 30);
  }
  document.querySelector('.js-add-ing').addEventListener('click', function () { ingRow(null); icons(); });
  document.querySelector('.js-add-step').addEventListener('click', function () { stepRow(''); icons(); });
  $('f-rc').addEventListener('click', function (e) { var b = e.target.closest('.js-rm-row'); if (b) { b.parentNode.remove(); renumber(); } });
  $('f-rc').addEventListener('submit', async function (e) {
    e.preventDefault();
    var nombre = $('rm-nombre').value.trim();
    if (!nombre) { $('rm-err').querySelector('span').textContent = 'El nombre es obligatorio'; $('rm-err').hidden = false; $('rm-nombre').focus(); return; }
    var payload = { nombre: nombre, categoria: $('rm-categoria').value, descripcion: $('rm-descripcion').value.trim(), porciones: parseInt($('rm-porciones').value, 10) || 1,
      tiempo_prep: parseInt($('rm-prep').value, 10) || 0, tiempo_coccion: parseInt($('rm-coccion').value, 10) || 0, calorias: parseFloat($('rm-cal').value) || 0,
      proteina: parseFloat($('rm-pro').value) || 0, carbos: parseFloat($('rm-carb').value) || 0, grasa: parseFloat($('rm-fat').value) || 0,
      video_url: $('rm-video').value.trim(), favorita: $('rm-fav').checked, fodmap: $('rm-fodmap').value,
      momento: Array.prototype.filter.call(document.querySelectorAll('#rm-momento [data-mom]'), function (b) { return b.getAttribute('aria-pressed') === 'true'; }).map(function (b) { return b.dataset.mom; }),
      ingredientes: Array.prototype.map.call(document.querySelectorAll('#ing-list .rc-row'), function (row) { var i = row.querySelectorAll('input'); return { item: i[0].value.trim(), cantidad: i[1].value.trim(), unidad: i[2].value.trim() }; }).filter(function (i) { return i.item; }),
      instrucciones: Array.prototype.map.call(document.querySelectorAll('#step-list textarea'), function (t) { return t.value.trim(); }).filter(Boolean) };
    var id = $('rm-id').value;
    var res = await fetch(id ? '/recetas/api/recipe/' + id : '/recetas/api/recipe', { method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) { $('rm-err').querySelector('span').textContent = 'Error al guardar'; $('rm-err').hidden = false; return; }
    var saved = await res.json();
    if (id) { var k = ALL.findIndex(function (r) { return r.id === saved.id; }); if (k >= 0) ALL[k] = saved; } else ALL.unshift(saved);
    euModal.close('m-rc'); filter(); eyebrow(); toast('Receta «' + saved.nombre + '» guardada');
    setTimeout(function () { open(saved.id); }, 60);
  });

  /* ── Delegación ── */
  document.addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var id = b.dataset.id ? +b.dataset.id : null;
    if (b.classList.contains('js-new')) form(null);
    else if (!root.contains(b)) return;
    else if (b.classList.contains('js-open') || b.classList.contains('js-ver')) open(id);
    else if (b.classList.contains('js-usar')) usar(b);
    else if (b.classList.contains('js-porc')) setPorc(porc + +b.dataset.d);
    else if (b.classList.contains('js-cook')) cookOpen(ALL.find(function (r) { return r.id === id; }), b);
    else if (b.classList.contains('js-close')) close();
    else if (b.classList.contains('js-hoy')) {
      b.disabled = true;
      fetch('/nutricion/api/comida', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ receta_id: id, slot: $('rc-hoy-slot').value }) })
        .then(function (r) { return r.json(); }).then(function (d) {
          b.disabled = false;
          if (d.meal) toast('Agregada a hoy · ' + d.meal.slot + ' ' + d.meal.time, 'ok'); else toast('No se pudo agregar', 'err');
        }).catch(function () { b.disabled = false; toast('Sin conexión', 'err'); });
    }
    else if (b.classList.contains('js-step')) b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true'));
    else if (b.classList.contains('js-edit')) form(ALL.find(function (r) { return r.id === id; }));
    else if (b.classList.contains('js-fav')) {
      var d = await fetch('/recetas/api/recipe/' + id + '/favorita', { method: 'POST' }).then(function (r) { return r.json(); }).catch(function () { return null; });
      if (!d) { toast('Error', 'err'); return; }
      var r = ALL.find(function (x) { return x.id === id; }); if (r) r.favorita = d.favorita ? 1 : 0;
      b.setAttribute('aria-pressed', String(!!d.favorita));
    } else if (b.classList.contains('js-del')) {
      var rr = ALL.find(function (x) { return x.id === id; });
      if (!(await euConfirm('¿Eliminar «' + (rr ? rr.nombre : '') + '»?', { confirmLabel: 'Eliminar' }))) return;
      await fetch('/recetas/api/recipe/' + id, { method: 'DELETE' });
      ALL.splice(ALL.findIndex(function (x) { return x.id === id; }), 1);
      close(); filter(); eyebrow(); toast('Receta eliminada');
    }
  });
  $('rc-q').addEventListener('input', filter);
  // «Quitar «X»» del vacío de filtro (kind=filter)
  $('rc-grid').addEventListener('click', function (e) {
    var b = e.target.closest('.js-empty-drop'); if (!b) return;
    if (b.dataset.drop === 'cat') { var all = document.querySelector('[data-fcat=""]'); if (all) { all.click(); return; } cat = ''; }
    else if (b.dataset.drop === 'fodmap') { $('rc-fodmap').click(); return; }
    else if (b.dataset.drop === 'q') $('rc-q').value = '';
    filter();
  });
  $('rc-fodmap').addEventListener('click', function () { fodmapOnly = !fodmapOnly; this.setAttribute('aria-pressed', String(fodmapOnly)); filter(); });
  $('rm-momento').addEventListener('click', function (e) { var b = e.target.closest('[data-mom]'); if (b) b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true')); });
  document.querySelectorAll('[data-fcat]').forEach(function (b) {
    b.addEventListener('click', function () { cat = b.dataset.fcat; document.querySelectorAll('[data-fcat]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); filter(); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !e.defaultPrevented && $('rc-detail').dataset.open && !document.querySelector('.eu-scrim:not([hidden])') && !window.euDialog.top()) close();
  });
  if (fodmapOnly) filter(); else render();
})();
