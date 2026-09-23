/* Recetas — Design System V2: grid filtrable + detalle (en móvil a pantalla
   completa), favoritas, pasos marcables y formulario con filas dinámicas. */
(function () {
  'use strict';
  var root = document.getElementById('rc');
  if (!root) return;
  var ALL = JSON.parse(document.getElementById('rc-data').textContent || '[]');
  var list = ALL.slice(), cat = '', active = null;
  var CAT = { 'Desayuno': 'oikonomia', 'Almuerzo': 'hegemonikon', 'Cena': 'paideia', 'Snack': 'eurythmia', 'Meal Prep': 'cosmopolitismo', 'Post-Entrenamiento': 'harma' };
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function mins(r) { return (r.tiempo_prep || 0) + (r.tiempo_coccion || 0); }

  function stats() {
    $('st-total').textContent = ALL.length;
    $('st-fav').textContent = ALL.filter(function (r) { return r.favorita; }).length;
    $('st-cats').textContent = new Set(ALL.map(function (r) { return r.categoria; })).size;
  }
  function filter() {
    var q = $('rc-q').value.trim().toLowerCase();
    list = ALL.filter(function (r) {
      return (!cat || r.categoria === cat) && (!q || r.nombre.toLowerCase().indexOf(q) >= 0 || (r.tags || '').toLowerCase().indexOf(q) >= 0 ||
        (r.ingredientes || []).some(function (i) { return String(i.item || i).toLowerCase().indexOf(q) >= 0; }));
    });
    render();
  }
  function macroChips(r) {
    return [r.calorias ? '<span class="eu-badge num">' + r.calorias + ' kcal</span>' : '', r.proteina ? '<span class="eu-badge eu-badge--success num">' + Math.round(r.proteina) + 'g P</span>' : '',
      r.carbos ? '<span class="eu-badge eu-badge--info num">' + Math.round(r.carbos) + 'g C</span>' : '', r.grasa ? '<span class="eu-badge eu-badge--warning num">' + Math.round(r.grasa) + 'g G</span>' : ''].join('');
  }
  function render() {
    var g = $('rc-grid');
    if (!list.length) {
      g.innerHTML = '<div class="eu-card rc-span">' + (ALL.length
        ? '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="search-x"></i></div><div class="t-card">Sin resultados</div><p>Ninguna receta coincide con este filtro.</p></div>'
        : '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="cooking-pot"></i></div><div class="t-card">Aún no tienes recetas</div><p>Agrega la primera para empezar tu recetario.</p><button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Nueva receta</button></div>') + '</div>';
      icons(); return;
    }
    g.innerHTML = list.map(function (r) {
      var m = mins(r);
      return '<article class="eu-card rc-card" data-cat="' + (CAT[r.categoria] || 'hegemonikon') + '">' +
        '<button type="button" class="rc-card-open js-open" data-id="' + r.id + '" aria-pressed="' + (active === r.id) + '">' +
          '<span class="t-eyebrow rc-card-cat">' + esc(r.categoria) + '</span><span class="t-ui rc-card-t">' + esc(r.nombre) + '</span>' +
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
    var maxM = Math.max(r.proteina || 0, r.carbos || 0, r.grasa || 0, 1), video = '';
    if (r.video_url) {
      var yt = r.video_url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]{11})/);
      video = yt ? '<div class="rc-video"><iframe src="https://www.youtube.com/embed/' + yt[1] + '" title="Video de la receta" allowfullscreen loading="lazy"></iframe></div>'
        : '<a class="eu-btn eu-btn--secondary eu-btn--sm rc-vlink" href="' + esc(r.video_url) + '" target="_blank" rel="noopener"><i data-lucide="play-circle"></i>Ver video</a>';
    }
    function bar(lbl, v, cls, u) { return v ? '<div class="rc-mbar"><span class="t-meta">' + lbl + '</span><span class="rc-mbar-t ' + cls + '"><i style="width:' + Math.round(v / maxM * 100) + '%"></i></span><span class="t-meta num">' + v + u + '</span></div>' : ''; }
    var ings = (r.ingredientes || []).map(function (i) {
      return typeof i === 'string' ? '<li><span>' + esc(i) + '</span></li>' : '<li><span>' + esc(i.item || '') + '</span><span class="t-meta num">' + esc(i.cantidad || '') + (i.unidad ? ' ' + esc(i.unidad) : '') + '</span></li>';
    }).join('');
    var steps = (r.instrucciones || []).map(function (s, i) {
      return '<li><button type="button" class="rc-step js-step" aria-pressed="false"><span class="rc-step-n num">' + (i + 1) + '</span><span>' + esc(s) + '</span></button></li>';
    }).join('');
    var m = mins(r);
    $('rc-content').innerHTML =
      '<div class="rc-d-hd" data-cat="' + (CAT[r.categoria] || 'hegemonikon') + '"><button type="button" class="eu-iconbtn rc-back js-close" aria-label="Volver"><i data-lucide="chevron-left"></i></button>' +
        '<div class="eu-grow"><span class="eu-badge eu-badge--cat">' + esc(r.categoria) + '</span><h2 class="t-section">' + esc(r.nombre) + '</h2>' +
        (r.descripcion ? '<p class="t-meta fg-2">' + esc(r.descripcion) + '</p>' : '') +
        '<div class="rc-card-m t-meta">' + (r.tiempo_prep ? '<span><i data-lucide="clock"></i>Prep ' + r.tiempo_prep + ' min</span>' : '') + (r.tiempo_coccion ? '<span><i data-lucide="flame"></i>Cocción ' + r.tiempo_coccion + ' min</span>' : '') +
        (r.porciones ? '<span><i data-lucide="utensils"></i>' + r.porciones + ' porción' + (r.porciones > 1 ? 'es' : '') + '</span>' : '') + '</div></div></div>' +
      ((r.proteina || r.carbos || r.grasa || r.calorias) ? '<div class="eu-vstack rc-sec"><div class="t-eyebrow">Macros por porción' + (r.calorias ? ' · <span class="num">' + r.calorias + ' kcal</span>' : '') + '</div>' +
        bar('Proteína', r.proteina, 'is-p', 'g') + bar('Carbos', r.carbos, 'is-c', 'g') + bar('Grasa', r.grasa, 'is-g', 'g') + '</div>' : '') +
      video +
      (ings ? '<div class="eu-vstack rc-sec"><div class="t-eyebrow">Ingredientes</div><ul class="rc-ings">' + ings + '</ul></div>' : '') +
      (steps ? '<div class="eu-vstack rc-sec"><div class="t-eyebrow">Instrucciones · toca para marcar</div><ol class="rc-steps">' + steps + '</ol></div>' : '') +
      '<div class="eu-hstack rc-d-act"><button type="button" class="eu-btn eu-btn--secondary eu-grow js-edit" data-id="' + r.id + '"><i data-lucide="pencil"></i>Editar</button>' +
        '<button type="button" class="eu-btn eu-btn--danger js-del" data-id="' + r.id + '"><i data-lucide="trash-2"></i>Eliminar</button></div>';
    $('rc-content').hidden = false; $('rc-empty').hidden = true; $('rc-detail').dataset.open = 'true';
    icons();
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
    $('rm-err').hidden = true;
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
      video_url: $('rm-video').value.trim(), favorita: $('rm-fav').checked,
      ingredientes: Array.prototype.map.call(document.querySelectorAll('#ing-list .rc-row'), function (row) { var i = row.querySelectorAll('input'); return { item: i[0].value.trim(), cantidad: i[1].value.trim(), unidad: i[2].value.trim() }; }).filter(function (i) { return i.item; }),
      instrucciones: Array.prototype.map.call(document.querySelectorAll('#step-list textarea'), function (t) { return t.value.trim(); }).filter(Boolean) };
    var id = $('rm-id').value;
    var res = await fetch(id ? '/recetas/api/recipe/' + id : '/recetas/api/recipe', { method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) { $('rm-err').querySelector('span').textContent = 'Error al guardar'; $('rm-err').hidden = false; return; }
    var saved = await res.json();
    if (id) { var k = ALL.findIndex(function (r) { return r.id === saved.id; }); if (k >= 0) ALL[k] = saved; } else ALL.unshift(saved);
    euModal.close('m-rc'); filter(); stats(); toast('Receta «' + saved.nombre + '» guardada');
    setTimeout(function () { open(saved.id); }, 60);
  });

  /* ── Delegación ── */
  document.addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var id = b.dataset.id ? +b.dataset.id : null;
    if (b.classList.contains('js-new')) form(null);
    else if (!root.contains(b)) return;
    else if (b.classList.contains('js-open')) open(id);
    else if (b.classList.contains('js-close')) close();
    else if (b.classList.contains('js-step')) b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true'));
    else if (b.classList.contains('js-edit')) form(ALL.find(function (r) { return r.id === id; }));
    else if (b.classList.contains('js-fav')) {
      var d = await fetch('/recetas/api/recipe/' + id + '/favorita', { method: 'POST' }).then(function (r) { return r.json(); }).catch(function () { return null; });
      if (!d) { toast('Error', 'err'); return; }
      var r = ALL.find(function (x) { return x.id === id; }); if (r) r.favorita = d.favorita ? 1 : 0;
      b.setAttribute('aria-pressed', String(!!d.favorita)); stats();
    } else if (b.classList.contains('js-del')) {
      var rr = ALL.find(function (x) { return x.id === id; });
      if (!(await euConfirm('¿Eliminar «' + (rr ? rr.nombre : '') + '»?', { confirmLabel: 'Eliminar' }))) return;
      await fetch('/recetas/api/recipe/' + id, { method: 'DELETE' });
      ALL.splice(ALL.findIndex(function (x) { return x.id === id; }), 1);
      close(); filter(); stats(); toast('Receta eliminada');
    }
  });
  $('rc-q').addEventListener('input', filter);
  document.querySelectorAll('[data-fcat]').forEach(function (b) {
    b.addEventListener('click', function () { cat = b.dataset.fcat; document.querySelectorAll('[data-fcat]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); filter(); });
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && $('rc-detail').dataset.open && !document.querySelector('.eu-scrim:not([hidden])')) close(); });
  render();
})();
