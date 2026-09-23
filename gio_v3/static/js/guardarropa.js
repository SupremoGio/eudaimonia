/* Guardarropa — Design System V2 · pantalla 09
   Prendas (grid/lista, departamentos, búsqueda, orden, detalle con foto e IA),
   Outfits (cifras, filtros, vista flat-lay, generador IA), Análisis (score
   cápsula, colores, categorías, IA) y panel lateral (outfit de hoy +XP,
   rotación de 90 días). Toda la lógica venía inline en index.html. */
(function () {
  'use strict';
  var root = document.getElementById('gr');
  if (!root) return;

  var DATA = JSON.parse(document.getElementById('gr-data').textContent || '{}');
  var ALL_ITEMS = DATA.items || [];
  var ALL_OUTFITS = DATA.outfits || [];
  var CATEGORIA_ORDER = DATA.categorias || [];
  var TODAY = DATA.today;
  var XP = DATA.outfit_xp || {};
  var IDLE_DAYS = 90;
  var CUTOFF = (function () { var d = new Date(TODAY + 'T12:00:00'); d.setDate(d.getDate() - IDLE_DAYS); return d.toISOString().slice(0, 10); })();

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function money(n) { return '$' + Math.round(n || 0).toLocaleString('es-MX'); }
  function plural(n, s, p) { return n + ' ' + (n === 1 ? s : (p || s + 's')); }
  function jpost(url, body, method) {
    return fetch(url, { method: method || 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  }
  function setErr(id, msg) {
    var el = $(id);
    el.querySelector('span').textContent = msg || '';
    el.hidden = !msg;
  }
  function photoSrc(r) { return r.foto ? '/guardarropa/photos/' + encodeURIComponent(r.foto) : (r.url || ''); }
  function swatchHTML(r, cls) {
    return '<span class="gr-sw ' + (cls || '') + '" style="--sw:' + esc(r.color_hex || '#444') + '"><span>' + esc((r.nombre || '?')[0].toUpperCase()) + '</span></span>';
  }
  /* Foto con respaldo: si no carga, se reemplaza por el swatch de color (ver listener de error) */
  function visualHTML(r, cls) {
    var src = photoSrc(r);
    return src ? '<img class="gr-img ' + (cls || '') + '" src="' + esc(src) + '" alt="" loading="lazy" data-hex="' + esc(r.color_hex || '#444') + '" data-ini="' + esc((r.nombre || '?')[0].toUpperCase()) + '">'
      : swatchHTML(r, cls);
  }
  document.addEventListener('error', function (e) {
    var img = e.target;
    if (!img.classList || !img.classList.contains('gr-img')) return;
    var sw = document.createElement('span');
    sw.className = 'gr-sw ' + img.className.replace('gr-img', '');
    sw.style.setProperty('--sw', img.dataset.hex);
    sw.innerHTML = '<span>' + esc(img.dataset.ini) + '</span>';
    img.replaceWith(sw);
  }, true);

  /* Una prenda está «sin uso en 90 días» si su último uso es anterior al corte,
     o si nunca se ha usado y lleva más de 90 días en el armario. Las prendas
     usadas antes de existir ultimo_uso (sin fecha) no cuentan como inactivas. */
  function isIdle(r) {
    if (r.ultimo_uso) return r.ultimo_uso < CUTOFF;
    return !(r.veces_usado > 0) && (r.created_at || '').slice(0, 10) < CUTOFF;
  }

  /* ── Psicología del color ─────────────────────────────────── */
  var COLOR_PSYCH = {
    negro: { name: 'Negro', hex: '#1a1a1a', psych: 'Autoridad · Elegancia · Poder', rec: 'Reuniones clave, entrevistas, eventos formales' },
    blanco: { name: 'Blanco', hex: '#f0ede4', psych: 'Claridad · Frescura · Accesibilidad', rec: 'Networking casual, verano, looks limpios' },
    navy: { name: 'Navy', hex: '#1B2A4A', psych: 'Profesionalismo · Confianza · Liderazgo', rec: 'Business formal, presentaciones importantes' },
    gris: { name: 'Gris', hex: '#6b7280', psych: 'Neutralidad · Sofisticación · Balance', rec: 'Office, negocios, complemento versátil' },
    azul: { name: 'Azul', hex: '#2563eb', psych: 'Calma · Inteligencia · Accesibilidad', rec: 'Trabajo colaborativo, casual smart' },
    cafe: { name: 'Café', hex: '#92400e', psych: 'Calidez · Fiabilidad · Tierra', rec: 'Casual, otoño, eventos informales' },
    beige: { name: 'Beige', hex: '#d4b896', psych: 'Sofisticación sutil · Calma', rec: 'Business casual, verano, look europeo' },
    caqui: { name: 'Caqui', hex: '#8a8360', psych: 'Practicidad · Look outdoor sofisticado', rec: 'Casual, fin de semana, looks utilitarios' },
    camel: { name: 'Camel', hex: '#C19A6B', psych: 'Lujo accesible · Calidez intelectual', rec: 'Outerwear premium, look business casual' },
    mostaza: { name: 'Mostaza', hex: '#c9962c', psych: 'Calidez vibrante · Personalidad', rec: 'Acentos, suéteres, accesorios de temporada' },
    borgona: { name: 'Borgoña', hex: '#7C2D41', psych: 'Madurez · Lujo · Confianza sutil', rec: 'Cenas selectas, eventos sociales nocturnos' },
    verde: { name: 'Verde', hex: '#16a34a', psych: 'Vitalidad · Crecimiento · Armonía', rec: 'Casual, actividades al aire libre, creatividad' },
    rojo: { name: 'Rojo', hex: '#dc2626', psych: 'Energía · Poder · Atención inmediata', rec: 'Presentaciones, eventos sociales, impacto visual' },
    blanco_roto: { name: 'Blanco roto', hex: '#ede8dc', psych: 'Elegancia cálida · Sofisticación', rec: 'Business casual, look intelectual' },
    amarillo: { name: 'Amarillo', hex: '#eab308', psych: 'Optimismo · Energía creativa · Calidez', rec: 'Acentos veraniegos, looks casuales llamativos' },
    turquesa: { name: 'Turquesa', hex: '#0d9488', psych: 'Frescura · Originalidad · Calma vibrante', rec: 'Casual creativo, verano, acentos statement' },
    morado: { name: 'Morado', hex: '#7c3aed', psych: 'Creatividad · Distinción · Lujo moderno', rec: 'Eventos nocturnos, acentos statement' },
    rosa: { name: 'Rosa', hex: '#db2777', psych: 'Confianza · Calidez · Personalidad', rec: 'Casual smart, looks statement de temporada' }
  };
  function matchColor(hex) {
    if (!hex) return null;
    var h = hex.toLowerCase();
    for (var k in COLOR_PSYCH) if (COLOR_PSYCH[k].hex.toLowerCase() === h) return COLOR_PSYCH[k];
    var r = parseInt(h.slice(1, 3), 16), g = parseInt(h.slice(3, 5), 16), b = parseInt(h.slice(5, 7), 16);
    var lum = (r * 299 + g * 587 + b * 114) / 1000;
    var max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    /* Sin tinte perceptible: manda la luminosidad */
    if (d < 20) return lum < 40 ? COLOR_PSYCH.negro : lum > 210 ? COLOR_PSYCH.blanco : COLOR_PSYCH.gris;
    /* Con tinte: manda el matiz aunque el color sea muy oscuro o muy claro */
    var hue = max === r ? ((g - b) / d + 6) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    hue *= 60;
    if (hue >= 200 && hue <= 260) return lum < 60 ? COLOR_PSYCH.navy : COLOR_PSYCH.azul;
    if (hue >= 10 && hue <= 45) return lum < 70 ? COLOR_PSYCH.cafe : lum > 200 ? COLOR_PSYCH.blanco_roto : COLOR_PSYCH.beige;
    if (hue >= 340 || hue <= 10) return lum < 90 ? COLOR_PSYCH.borgona : COLOR_PSYCH.rojo;
    if (hue >= 80 && hue <= 160) return COLOR_PSYCH.verde;
    if (hue > 45 && hue < 80) return lum < 140 ? COLOR_PSYCH.mostaza : COLOR_PSYCH.amarillo;
    if (hue > 160 && hue < 200) return COLOR_PSYCH.turquesa;
    if (hue > 260 && hue < 340) return hue < 300 ? COLOR_PSYCH.morado : COLOR_PSYCH.rosa;
    return { name: 'Color personalizado', psych: 'Expresa tu personalidad única', rec: 'Accesorios y prendas statement' };
  }

  /* ── Pestañas y vista ─────────────────────────────────────── */
  var tab = 'prendas';
  function setTab(t) {
    tab = t;
    root.dataset.tab = t;
    $$('[data-tab-set]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tabSet === t)); });
    $$('[data-panel]').forEach(function (p) { p.hidden = p.dataset.panel !== t; });
    $$('.gr-hd [data-for]').forEach(function (b) { b.hidden = b.dataset.for !== t; });
    $('gr-analisis').hidden = t !== 'analisis';
    if (t === 'outfits') renderOutfits();
    if (t === 'analisis') renderAnalysis();
    try { history.replaceState(null, '', t === 'prendas' ? location.pathname : '#' + t); } catch (_) {}
  }
  $$('[data-tab-set]').forEach(function (b) { b.addEventListener('click', function () { setTab(b.dataset.tabSet); }); });

  var view = 'grid';
  try { view = localStorage.getItem('gr-view') === 'list' ? 'list' : 'grid'; } catch (_) {}
  function setView(v) {
    view = v; root.dataset.view = v;
    $$('[data-view-set]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.viewSet === v)); });
    try { localStorage.setItem('gr-view', v); } catch (_) {}
    renderGrid();
  }
  $$('[data-view-set]').forEach(function (b) { b.addEventListener('click', function () { setView(b.dataset.viewSet); }); });

  /* ── Departamentos y filtros ──────────────────────────────── */
  var DEPARTMENTS = [
    { key: '', label: 'Todo', cats: null },
    { key: 'superior', label: 'Superior', cats: ['Camisa', 'Camiseta', 'Polo', 'Sudadera', 'Suéter'] },
    { key: 'inferior', label: 'Inferior', cats: ['Pantalón', 'Jeans', 'Pants', 'Short'] },
    { key: 'exterior', label: 'Sacos y trajes', cats: ['Blazer / Saco', 'Chamarra / Abrigo', 'Traje / Conjunto'] },
    { key: 'calzado', label: 'Calzado', cats: ['Zapatos formales', 'Zapatos casuales', 'Sneakers', 'Botas', 'Sandalias'] },
    { key: 'accesorios', label: 'Accesorios', cats: ['Calcetas', 'Accesorio'] }
  ];
  var st = { dept: '', cat: '', color: '', catF: null, idle: false };
  var items = ALL_ITEMS.slice();
  var sortEl = $('gr-sort');
  try { var s0 = localStorage.getItem('gr-sort'); if (s0 && sortEl.querySelector('option[value="' + s0 + '"]')) sortEl.value = s0; } catch (_) {}

  function renderDepts() {
    $('gr-depts').innerHTML = DEPARTMENTS.map(function (d) {
      var n = d.cats ? ALL_ITEMS.filter(function (i) { return d.cats.indexOf(i.categoria) >= 0; }).length : ALL_ITEMS.length;
      if (d.cats && !n) return '';
      return '<button type="button" class="eu-chip" data-dept="' + d.key + '" aria-pressed="' + (st.dept === d.key) + '">' + esc(d.label) + ' <span class="ct">' + n + '</span></button>';
    }).join('');
    var dept = DEPARTMENTS.find(function (d) { return d.key === st.dept; });
    var bar = $('gr-subcats');
    if (!dept.cats) { bar.hidden = true; bar.innerHTML = ''; return; }
    var cats = CATEGORIA_ORDER.filter(function (c) { return dept.cats.indexOf(c) >= 0 && ALL_ITEMS.some(function (i) { return i.categoria === c; }); });
    bar.hidden = cats.length < 2;
    bar.innerHTML = '<button type="button" class="eu-chip" data-subcat="" aria-pressed="' + !st.cat + '">Todas</button>' +
      cats.map(function (c) {
        var n = ALL_ITEMS.filter(function (i) { return i.categoria === c; }).length;
        return '<button type="button" class="eu-chip" data-subcat="' + esc(c) + '" aria-pressed="' + (st.cat === c) + '">' + esc(c) + ' <span class="ct">' + n + '</span></button>';
      }).join('');
  }
  $('gr-depts').addEventListener('click', function (e) {
    var b = e.target.closest('[data-dept]'); if (!b) return;
    st.dept = b.dataset.dept; st.cat = ''; renderDepts(); filterItems();
  });
  $('gr-subcats').addEventListener('click', function (e) {
    var b = e.target.closest('[data-subcat]'); if (!b) return;
    st.cat = b.dataset.subcat; renderDepts(); filterItems();
  });

  var SORTERS = {
    menos_usadas: function (a, b) {
      var ia = isIdle(a) ? 0 : 1, ib = isIdle(b) ? 0 : 1;
      return ia - ib || (a.veces_usado || 0) - (b.veces_usado || 0) || (a.ultimo_uso || '').localeCompare(b.ultimo_uso || '');
    },
    recientes: function (a, b) { return (b.created_at || '').localeCompare(a.created_at || ''); },
    precio_desc: function (a, b) { return (b.precio || 0) - (a.precio || 0); },
    precio_asc: function (a, b) { return (a.precio || 0) - (b.precio || 0); },
    usos_desc: function (a, b) { return (b.veces_usado || 0) - (a.veces_usado || 0); },
    nombre: function (a, b) { return a.nombre.localeCompare(b.nombre); }
  };

  function filterItems() {
    var q = $('gr-q').value.trim().toLowerCase();
    var dept = DEPARTMENTS.find(function (d) { return d.key === st.dept; });
    items = ALL_ITEMS.filter(function (r) {
      return (!dept.cats || dept.cats.indexOf(r.categoria) >= 0) &&
        (!st.cat || r.categoria === st.cat) &&
        (!q || r.nombre.toLowerCase().indexOf(q) >= 0 || (r.marca || '').toLowerCase().indexOf(q) >= 0 || (r.color_name || '').toLowerCase().indexOf(q) >= 0) &&
        (!st.color || ((matchColor(r.color_hex) || {}).name || 'Otro') === st.color) &&
        (st.catF === null || r.categoria === st.catF) &&
        (!st.idle || isIdle(r));
    });
    items.sort(SORTERS[sortEl.value] || SORTERS.recientes);
    $('gr-count').textContent = plural(items.length, 'prenda');
    var cc = document.querySelector('.js-clear-color');
    cc.hidden = !st.color && !st.idle;
    cc.innerHTML = esc(st.idle ? 'Sin uso · ' + IDLE_DAYS + ' d' : st.color) + ' <i data-lucide="x"></i>';
    var ck = document.querySelector('.js-clear-cat');
    ck.hidden = st.catF === null;
    ck.innerHTML = esc(st.catF || 'Sin categoría') + ' <i data-lucide="x"></i>';
    renderGrid();
  }
  $('gr-q').addEventListener('input', filterItems);
  sortEl.addEventListener('change', function () { try { localStorage.setItem('gr-sort', sortEl.value); } catch (_) {} filterItems(); });
  document.querySelector('.js-clear-color').addEventListener('click', function () { st.color = ''; st.idle = false; filterItems(); });
  document.querySelector('.js-clear-cat').addEventListener('click', function () { st.catF = null; filterItems(); });

  function jumpFilter(patch) {
    st.color = ''; st.catF = null; st.idle = false; st.dept = ''; st.cat = '';
    Object.assign(st, patch);
    $('gr-q').value = '';
    renderDepts();
    setTab('prendas');
    filterItems();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ── Grid / lista ─────────────────────────────────────────── */
  function usoMeta(r) {
    if (isIdle(r)) return '<span class="gr-idle">' + (r.veces_usado ? 'Sin uso' : '0 usos') + ' · ' + IDLE_DAYS + ' d</span>';
    return plural(r.veces_usado || 0, 'uso');
  }
  function renderGrid() {
    var grid = $('gr-grid');
    grid.className = view === 'list' ? 'eu-card eu-card--flush gr-list' : 'gr-grid';
    if (!ALL_ITEMS.length) {
      grid.className = 'gr-grid';
      grid.innerHTML = '<div class="eu-empty gr-span"><div class="eu-empty-ic"><i data-lucide="shirt"></i></div><div class="t-card">Tu armario está vacío</div>' +
        '<p>Añade tu primera prenda para empezar a construir tu catálogo.</p><button type="button" class="eu-btn eu-btn--primary js-new-item"><i data-lucide="plus"></i>Nueva prenda</button></div>';
      icons(); return;
    }
    if (!items.length) {
      grid.className = 'gr-grid';
      grid.innerHTML = '<div class="eu-empty gr-span"><div class="eu-empty-ic"><i data-lucide="search-x"></i></div><div class="t-card">Sin resultados</div><p>Ninguna prenda coincide con este filtro.</p></div>';
      icons(); return;
    }
    if (view === 'list') {
      grid.innerHTML = '<div class="eu-list">' + items.map(function (r) {
        return '<button type="button" class="eu-row eu-row--interactive gr-lrow js-open" data-id="' + r.id + '">' +
          '<span class="gr-lthumb">' + visualHTML(r) + '</span>' +
          '<span class="eu-row-main"><span class="eu-row-t">' + esc(r.nombre) + '</span>' +
          '<span class="eu-row-s">' + esc(r.categoria) + (r.marca ? ' · ' + esc(r.marca) : '') + ' · ' + usoMeta(r) + '</span></span>' +
          (r.precio ? '<span class="t-meta num">' + money(r.precio) + '</span>' : '') + '</button>';
      }).join('') + '</div>';
    } else {
      grid.innerHTML = items.map(function (r) {
        return '<article class="gr-card' + (isIdle(r) ? ' is-idle' : '') + '">' +
          '<button type="button" class="gr-card-open js-open" data-id="' + r.id + '" aria-label="Ver ' + esc(r.nombre) + '">' +
          '<span class="gr-ph">' + visualHTML(r) + '</span>' +
          '<span class="gr-card-t">' + esc(r.nombre) + '</span>' +
          '<span class="t-meta gr-card-m">' + esc(r.categoria) + ' · ' + usoMeta(r) + '</span></button>' +
          '<button type="button" class="eu-iconbtn gr-card-edit js-edit-item" data-id="' + r.id + '" aria-label="Editar ' + esc(r.nombre) + '"><i data-lucide="pencil"></i></button>' +
          '</article>';
      }).join('');
    }
    icons();
  }

  /* ── Detalle de prenda ────────────────────────────────────── */
  var detailId = null;
  function openDetail(id) {
    var r = ALL_ITEMS.find(function (x) { return x.id === id; });
    if (!r) return;
    detailId = id;
    var idx = items.findIndex(function (x) { return x.id === id; });
    $('gr-d-pos').textContent = idx >= 0 ? (idx + 1) + ' / ' + items.length : '';
    document.querySelector('.js-d-prev').disabled = !(idx > 0);
    document.querySelector('.js-d-next').disabled = !(idx >= 0 && idx < items.length - 1);
    var psych = matchColor(r.color_hex);
    var cpu = r.precio && r.veces_usado > 0 ? money(r.precio / r.veces_usado) : '—';
    var occs = (r.ocasion || '').split(',').map(function (o) { return o.trim(); }).filter(Boolean);
    var estadoTone = { nuevo: 'success', bueno: '', regular: 'warning', donar: 'danger' }[r.estado] || '';
    $('gr-d-bd').innerHTML =
      '<div class="gr-d-photo" id="gr-drop">' + visualHTML(r, 'gr-d-img') +
        '<div class="gr-drop-hint" aria-hidden="true"><i data-lucide="upload"></i>Suelta la imagen aquí</div>' +
        '<label class="eu-btn eu-btn--secondary eu-btn--sm gr-d-up"><input type="file" class="js-photo" accept=".jpg,.jpeg,.png,.webp,.heic"><i data-lucide="camera"></i>Foto</label>' +
      '</div>' +
      '<div class="eu-vstack gr-d-info">' +
        '<div class="eu-hstack gr-wrapchips">' +
          '<span class="eu-badge' + (estadoTone ? ' eu-badge--' + estadoTone : '') + '">' + esc(r.estado) + '</span>' +
          (r.temporada && r.temporada !== 'todo' ? '<span class="eu-badge">' + esc(r.temporada) + '</span>' : '') +
          occs.map(function (o) { return '<span class="eu-badge eu-badge--brand">' + esc(o) + '</span>'; }).join('') +
          (isIdle(r) ? '<span class="eu-badge eu-badge--warning">Sin uso · ' + IDLE_DAYS + ' d</span>' : '') +
        '</div>' +
        '<div><h2 class="t-section" id="gr-detail-t">' + esc(r.nombre) + '</h2>' +
        '<div class="t-meta">' + esc(r.categoria) + (r.marca ? ' · ' + esc(r.marca) : '') + (r.subcategoria ? ' · ' + esc(r.subcategoria) : '') + '</div></div>' +
        '<div class="eu-card eu-card--inset eu-vstack gr-psych">' +
          '<div class="eu-hstack"><span class="gr-psych-sw" style="--sw:' + esc(r.color_hex || '#444') + '"></span>' +
          '<div class="eu-grow"><div class="t-ui" id="gr-psych-name">' + esc(psych ? psych.name : '—') + '</div><div class="t-meta">Psicología del color</div></div>' +
          '<span class="eu-badge eu-badge--brand" id="gr-psych-ai" hidden>IA</span></div>' +
          '<p class="t-meta fg-2" id="gr-psych-msg">' + esc(psych ? psych.psych : '') + '</p>' +
          '<p class="t-meta eu-hstack gr-psych-rec"><i data-lucide="lightbulb"></i><span id="gr-psych-rec">' + esc(psych ? psych.rec : '') + '</span></p>' +
          '<span class="eu-badge eu-badge--success" id="gr-sport" hidden></span>' +
        '</div>' +
        '<div class="eu-grid-3 gr-d-stats">' +
          '<div class="eu-stat"><div class="eu-stat-lbl">Usos</div><div class="eu-stat-val">' + (r.veces_usado || 0) + '</div></div>' +
          '<div class="eu-stat"><div class="eu-stat-lbl">Precio</div><div class="eu-stat-val">' + (r.precio ? money(r.precio) : '—') + '</div></div>' +
          '<div class="eu-stat"><div class="eu-stat-lbl">Costo / uso</div><div class="eu-stat-val">' + cpu + '</div></div>' +
        '</div>' +
        (r.ultimo_uso ? '<div class="t-meta">Último uso: ' + esc(r.ultimo_uso) + '</div>' : '') +
        (r.notas ? '<p class="t-body fg-2 gr-d-notes">' + esc(r.notas) + '</p>' : '') +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--block js-uso" data-id="' + r.id + '"><i data-lucide="plus"></i>Registrar uso</button>' +
        '<div class="eu-hstack gr-d-act">' +
          '<button type="button" class="eu-btn eu-btn--ghost eu-grow js-edit-item" data-id="' + r.id + '"><i data-lucide="pencil"></i>Editar</button>' +
          '<button type="button" class="eu-btn eu-btn--danger js-del-item" data-id="' + r.id + '"><i data-lucide="trash-2"></i>Eliminar</button>' +
        '</div>' +
      '</div>';
    icons();
    setupDrop(r.id);
    if ($('gr-detail').hidden) euModal.open('gr-detail');  /* si ya está abierto, solo se re-renderiza */
    fetchAnalysis(r.id);
  }
  document.querySelector('.js-d-prev').addEventListener('click', function () {
    var i = items.findIndex(function (x) { return x.id === detailId; }); if (i > 0) openDetailInPlace(items[i - 1].id);
  });
  document.querySelector('.js-d-next').addEventListener('click', function () {
    var i = items.findIndex(function (x) { return x.id === detailId; }); if (i >= 0 && i < items.length - 1) openDetailInPlace(items[i + 1].id);
  });
  /* Re-render con el modal ya abierto (anterior/siguiente, foto nueva, uso) */
  var openDetailInPlace = openDetail;

  async function fetchAnalysis(id) {
    try {
      var res = await fetch('/guardarropa/api/item/' + id + '/analyze', { method: 'POST' });
      if (!res.ok) return;
      var d = await res.json();
      if (!d.ok || detailId !== id || !$('gr-psych-name')) return;
      $('gr-psych-name').textContent = d.color_name || $('gr-psych-name').textContent;
      if (d.psych) $('gr-psych-msg').textContent = d.psych;
      if (d.rec) $('gr-psych-rec').textContent = d.rec;
      $('gr-psych-ai').hidden = false;
      if (d.is_sportswear) { $('gr-sport').textContent = d.sport_note || 'Prenda deportiva'; $('gr-sport').hidden = false; }
    } catch (_) { /* queda el análisis local */ }
  }

  function setPhoto(id, filename) {
    var it = ALL_ITEMS.find(function (x) { return x.id === id; });
    if (it) it.foto = filename;
    ALL_OUTFITS.forEach(function (o) { (o.items || []).forEach(function (i) { if (i.id === id) i.foto = filename; }); });
    renderGrid();
    if (detailId === id && !$('gr-detail').hidden) openDetailInPlace(id);
    renderToday();
  }
  async function uploadFile(id, file) {
    var fd = new FormData(); fd.append('file', file);
    var d = await (await fetch('/guardarropa/api/upload/' + id, { method: 'POST', body: fd })).json().catch(function () { return {}; });
    if (d.ok) { setPhoto(id, d.filename); toast('Foto guardada'); } else toast('Error: ' + (d.error || 'no se pudo subir'), 'err');
  }
  async function photoFromUrl(id, url) {
    var d = await (await jpost('/guardarropa/api/item/' + id + '/fetch-url-photo', { url: url })).json().catch(function () { return {}; });
    if (d.ok) { setPhoto(id, d.filename); return true; }
    return d.error || 'No se pudo descargar';
  }
  /* Arrastrar una imagen desde otra pestaña (URL) o desde el escritorio (archivo) */
  function setupDrop(id) {
    var dv = $('gr-drop');
    dv.addEventListener('dragover', function (e) { e.preventDefault(); dv.classList.add('is-over'); });
    dv.addEventListener('dragleave', function (e) { if (!dv.contains(e.relatedTarget)) dv.classList.remove('is-over'); });
    dv.addEventListener('drop', async function (e) {
      e.preventDefault(); dv.classList.remove('is-over');
      var dt = e.dataTransfer;
      var url = (dt.getData('text/uri-list') || '').split('\n').map(function (s) { return s.trim(); }).find(function (s) { return s.indexOf('http') === 0; });
      if (!url) { var m = (dt.getData('text/html') || '').match(/src=["'](https?:[^"']+)["']/i); if (m) url = m[1]; }
      if (url) {
        toast('Descargando imagen…');
        var ok = await photoFromUrl(id, url);
        if (ok === true) toast('Foto guardada'); else toast('Error: ' + ok, 'err');
        return;
      }
      var file = Array.prototype.find.call(dt.files || [], function (f) { return f.type.indexOf('image/') === 0; });
      if (file) { uploadFile(id, file); return; }
      toast('No se detectó imagen', 'err');
    });
  }

  $('gr-d-bd').addEventListener('change', function (e) {
    if (e.target.classList.contains('js-photo') && e.target.files[0]) uploadFile(detailId, e.target.files[0]);
  });

  async function registerUso(id) {
    var d = await (await fetch('/guardarropa/api/item/' + id + '/uso', { method: 'POST' })).json().catch(function () { return {}; });
    if (d.veces_usado == null) { toast('No se pudo registrar', 'err'); return; }
    var it = ALL_ITEMS.find(function (x) { return x.id === id; });
    if (it) { it.veces_usado = d.veces_usado; it.ultimo_uso = d.ultimo_uso || TODAY; }
    filterItems(); renderRotation();
    openDetailInPlace(id);
    toast('Uso registrado');
  }
  async function deleteItem(id) {
    var r = ALL_ITEMS.find(function (x) { return x.id === id; });
    if (!(await euConfirm('¿Eliminar «' + (r ? r.nombre : '') + '»?', { confirmLabel: 'Eliminar' }))) return;
    var res = await fetch('/guardarropa/api/item/' + id, { method: 'DELETE' });
    if (!res.ok) { toast('No se pudo eliminar', 'err'); return; }
    ALL_ITEMS.splice(ALL_ITEMS.findIndex(function (x) { return x.id === id; }), 1);
    euModal.close('gr-detail'); detailId = null;
    renderDepts(); filterItems(); renderRotation();
    toast('Prenda eliminada');
  }

  /* ── Formulario de prenda ─────────────────────────────────── */
  var occs = [];
  var pendingFotoUrl = '';
  function renderSwatches() {
    $('im-swatches').innerHTML = Object.keys(COLOR_PSYCH).map(function (k) {
      var v = COLOR_PSYCH[k];
      return '<button type="button" class="gr-swatch" style="--sw:' + v.hex + '" data-hex="' + v.hex + '" data-name="' + esc(v.name) + '" aria-label="' + esc(v.name) + '" title="' + esc(v.name) + '"></button>';
    }).join('');
  }
  function markSwatch(hex) {
    var h = String(hex || '').toLowerCase();
    $$('#im-swatches .gr-swatch').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.hex.toLowerCase() === h)); });
  }
  $('im-swatches').addEventListener('click', function (e) {
    var b = e.target.closest('.gr-swatch'); if (!b) return;
    $('im-color-hex').value = b.dataset.hex; $('im-color-name').value = b.dataset.name; markSwatch(b.dataset.hex);
  });
  $('im-color-hex').addEventListener('input', function () {
    var p = matchColor(this.value);
    if (p && !$('im-color-name').value) $('im-color-name').placeholder = p.name;
    markSwatch('');
  });
  var eyedrop = document.querySelector('.js-eyedrop');
  if (window.EyeDropper) eyedrop.hidden = false;
  eyedrop.addEventListener('click', async function () {
    try { var r = await new EyeDropper().open(); $('im-color-hex').value = r.sRGBHex; $('im-color-hex').dispatchEvent(new Event('input')); } catch (_) { /* cancelado */ }
  });
  $('im-occ').addEventListener('click', function (e) {
    var b = e.target.closest('[data-oc]'); if (!b) return;
    var on = b.getAttribute('aria-pressed') !== 'true';
    b.setAttribute('aria-pressed', String(on));
    occs = on ? occs.concat(b.dataset.oc) : occs.filter(function (x) { return x !== b.dataset.oc; });
  });
  function syncOccs() { $$('#im-occ [data-oc]').forEach(function (p) { p.setAttribute('aria-pressed', String(occs.indexOf(p.dataset.oc) >= 0)); }); }
  function urlButtons() {
    var v = $('im-url').value.trim();
    document.querySelector('.js-autofill').hidden = !v;
    document.querySelector('.js-url-photo').hidden = !(v && $('im-id').value);
  }
  $('im-url').addEventListener('input', urlButtons);

  function openItemForm(id) {
    var r = id ? ALL_ITEMS.find(function (x) { return x.id === id; }) : null;
    if (!$('gr-detail').hidden) euModal.close('gr-detail');
    $('gr-item-t').textContent = r ? 'Editar prenda' : 'Nueva prenda';
    $('im-id').value = r ? r.id : '';
    $('im-nombre').value = r ? r.nombre : '';
    $('im-categoria').value = (r && r.categoria) || 'Camisa';
    $('im-marca').value = (r && r.marca) || '';
    $('im-sub').value = (r && r.subcategoria) || '';
    $('im-color-hex').value = (r && r.color_hex) || '#C9A84C';
    $('im-color-name').value = (r && r.color_name) || '';
    markSwatch(r && r.color_hex);
    $('im-precio').value = (r && r.precio) || '';
    $('im-temp').value = (r && r.temporada) || 'todo';
    $('im-estado').value = (r && r.estado) || 'bueno';
    $('im-notas').value = (r && r.notas) || '';
    $('im-url').value = (r && r.url) || '';
    occs = ((r && r.ocasion) || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
    syncOccs(); urlButtons(); setErr('im-err', '');
    pendingFotoUrl = '';
    euModal.open('gr-item');
    setTimeout(function () { $('im-nombre').focus(); }, 30);
  }

  document.querySelector('.js-autofill').addEventListener('click', async function () {
    var btn = this, url = $('im-url').value.trim(); if (!url) return;
    btn.setAttribute('aria-busy', 'true'); setErr('im-err', '');
    try {
      var d = await (await jpost('/guardarropa/api/parse-url', { url: url })).json();
      if (!d.ok) { setErr('im-err', d.error || 'No se pudo leer la página'); return; }
      var map = { nombre: 'im-nombre', categoria: 'im-categoria', subcategoria: 'im-sub', marca: 'im-marca', color_name: 'im-color-name', color_hex: 'im-color-hex', precio: 'im-precio', temporada: 'im-temp', notas: 'im-notas' };
      Object.keys(map).forEach(function (k) { if (d[k]) $(map[k]).value = d[k]; });
      if (d.color_hex) markSwatch(d.color_hex);
      if (Array.isArray(d.ocasion) && d.ocasion.length) { occs = d.ocasion.slice(); syncOccs(); }
      pendingFotoUrl = d.foto_url || '';
      toast(d.suficiente_info === false ? 'La página no dio mucha información — completa lo que falte' : 'Información completada — revisa y guarda');
    } catch (_) { setErr('im-err', 'Error de conexión'); }
    finally { btn.removeAttribute('aria-busy'); }
  });
  document.querySelector('.js-url-photo').addEventListener('click', async function () {
    var btn = this, id = parseInt($('im-id').value, 10), url = $('im-url').value.trim();
    if (!id || !url) return;
    btn.setAttribute('aria-busy', 'true');
    var ok = await photoFromUrl(id, url);
    btn.removeAttribute('aria-busy');
    if (ok === true) toast('Foto obtenida'); else setErr('im-err', ok);
  });

  $('gr-item-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var nombre = $('im-nombre').value.trim();
    if (!nombre) { setErr('im-err', 'El nombre es obligatorio'); $('im-nombre').focus(); return; }
    var payload = {
      nombre: nombre, categoria: $('im-categoria').value, subcategoria: $('im-sub').value.trim(),
      color_hex: $('im-color-hex').value, color_name: $('im-color-name').value.trim(), marca: $('im-marca').value.trim(),
      ocasion: occs.join(','), temporada: $('im-temp').value, estado: $('im-estado').value,
      precio: parseFloat($('im-precio').value) || 0, notas: $('im-notas').value.trim(), url: $('im-url').value.trim()
    };
    var id = $('im-id').value;
    var res = await jpost(id ? '/guardarropa/api/item/' + id : '/guardarropa/api/item', payload, id ? 'PUT' : 'POST');
    if (!res.ok) { setErr('im-err', 'Error al guardar'); return; }
    var saved = await res.json();
    if (id) { var i = ALL_ITEMS.findIndex(function (x) { return x.id === saved.id; }); if (i >= 0) ALL_ITEMS[i] = saved; }
    else ALL_ITEMS.unshift(saved);
    if (pendingFotoUrl && !saved.foto) await photoFromUrl(saved.id, pendingFotoUrl);  /* la foto es opcional */
    pendingFotoUrl = '';
    euModal.close('gr-item');
    renderDepts(); filterItems(); renderRotation();
    toast('«' + saved.nombre + '» guardada');
    setTimeout(function () { openDetail(saved.id); }, 80);
  });

  /* ── Delegación de clics de la página ─────────────────────── */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('button, a');
    if (!b) return;
    var id = b.dataset.id ? parseInt(b.dataset.id, 10) : null;
    if (b.classList.contains('js-open')) openDetail(id);
    else if (b.classList.contains('js-edit-item')) openItemForm(id);
    else if (b.classList.contains('js-new-item')) openItemForm(null);
    else if (b.classList.contains('js-new-outfit')) openOutfitForm(null);
    else if (b.classList.contains('js-uso')) registerUso(id);
    else if (b.classList.contains('js-del-item')) deleteItem(id);
    else if (b.classList.contains('js-fab')) { if (tab === 'outfits') openOutfitForm(null); else openItemForm(null); }
    else if (b.classList.contains('js-idle-filter')) jumpFilter({ idle: true });
  });

  /* ── Outfits ──────────────────────────────────────────────── */
  var otFilter = '';
  function stars(n) { var s = ''; for (var i = 1; i <= 5; i++) s += i <= n ? '★' : '☆'; return s; }
  function mosaic(list) {
    var all = (list || []).slice().sort(function (a, b) { return (b.foto ? 1 : 0) - (a.foto ? 1 : 0); }).slice(0, 4);
    if (!all.length) return '<span class="gr-mosaic gr-mosaic--0"><i data-lucide="shirt"></i></span>';
    return '<span class="gr-mosaic gr-mosaic--' + all.length + '">' + all.map(function (i) { return '<span class="gr-ms">' + visualHTML(i) + '</span>'; }).join('') + '</span>';
  }
  function renderOutfits() {
    var weekAgo = (function () { var d = new Date(TODAY + 'T12:00:00'); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10); })();
    $('ot-total').textContent = ALL_OUTFITS.length;
    $('ot-week').textContent = ALL_OUTFITS.filter(function (o) { return o.ultimo_uso && o.ultimo_uso >= weekAgo; }).length;
    var occMap = {};
    ALL_OUTFITS.forEach(function (o) { if (o.ocasion) occMap[o.ocasion] = (occMap[o.ocasion] || 0) + 1; });
    var top = Object.keys(occMap).sort(function (a, b) { return occMap[b] - occMap[a]; })[0];
    $('ot-fav').textContent = top || '—';
    var list = otFilter ? ALL_OUTFITS.filter(function (o) { return (o.ocasion || '').toLowerCase() === otFilter.toLowerCase(); }) : ALL_OUTFITS;
    var grid = $('ot-grid');
    if (!list.length) {
      grid.innerHTML = '<div class="eu-empty gr-span"><div class="eu-empty-ic"><i data-lucide="' + (otFilter ? 'search-x' : 'layers') + '"></i></div>' +
        '<div class="t-card">' + (otFilter ? 'Sin resultados' : 'Sin outfits guardados') + '</div><p>' +
        (otFilter ? 'No hay outfits guardados para esta ocasión.' : 'Crea tu primer look o pídele uno al coach de imagen.') + '</p>' +
        (otFilter ? '' : '<button type="button" class="eu-btn eu-btn--primary js-new-outfit"><i data-lucide="plus"></i>Nuevo outfit</button>') + '</div>';
      icons(); return;
    }
    grid.innerHTML = list.map(function (o) {
      var used = o.ultimo_uso === TODAY;
      return '<article class="eu-card eu-card--flush gr-ocard">' +
        '<button type="button" class="gr-ocard-open js-oview" data-id="' + o.id + '" aria-label="Ver outfit ' + esc(o.nombre) + '">' + mosaic(o.items) +
          (o.ocasion ? '<span class="eu-badge gr-ocard-occ">' + esc(o.ocasion) + '</span>' : '') + '</button>' +
        '<div class="gr-ocard-bd">' +
          '<div class="t-ui gr-ocard-t">' + esc(o.nombre) + '</div>' +
          '<div class="eu-between t-meta"><span class="gr-stars-ro" aria-label="' + (o.rating || 0) + ' de 5">' + stars(o.rating || 0) + '</span>' +
          '<span title="' + (o.ultimo_uso ? 'Último: ' + esc(o.ultimo_uso) : '') + '">' + (o.veces_usado ? o.veces_usado + '× usado' : 'Nunca usado') + '</span></div>' +
          '<div class="eu-hstack gr-ocard-act">' +
            '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm eu-grow js-ouse" data-id="' + o.id + '"' + (used ? ' disabled' : '') + '>' + (used ? 'Usado hoy' : 'Usar hoy') + '</button>' +
            '<button type="button" class="eu-iconbtn js-oedit" data-id="' + o.id + '" aria-label="Editar ' + esc(o.nombre) + '"><i data-lucide="pencil"></i></button>' +
            '<button type="button" class="eu-iconbtn gr-danger js-odel" data-id="' + o.id + '" aria-label="Eliminar ' + esc(o.nombre) + '"><i data-lucide="trash-2"></i></button>' +
          '</div></div></article>';
    }).join('');
    icons();
  }
  $('ot-filters').addEventListener('click', function (e) {
    var b = e.target.closest('[data-occ]'); if (!b) return;
    otFilter = b.dataset.occ;
    $$('#ot-filters [data-occ]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
    renderOutfits();
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var id = b.dataset.id ? parseInt(b.dataset.id, 10) : null;
    if (b.classList.contains('js-oview')) openOutfitView(id);
    else if (b.classList.contains('js-oedit')) openOutfitForm(id);
    else if (b.classList.contains('js-odel')) deleteOutfit(id);
    else if (b.classList.contains('js-ouse')) useOutfit(id, b);
  });

  /* Usar un outfit: suma uso al outfit y a cada prenda. Si es el de hoy y la
     actividad «outfit» del Acta sigue sin marcar, también la marca (+XP). */
  async function useOutfit(id, btn, withXP) {
    if (btn) btn.setAttribute('aria-busy', 'true');
    try {
      var d = await (await fetch('/guardarropa/api/outfit/' + id + '/usar', { method: 'POST' })).json();
      if (!d.ok) throw new Error();
      var o = ALL_OUTFITS.find(function (x) { return x.id === id; });
      if (o) { o.veces_usado = d.veces_usado; o.ultimo_uso = d.ultimo_uso; }
      (d.item_ids || []).forEach(function (iid) {
        var it = ALL_ITEMS.find(function (x) { return x.id === iid; });
        if (it) { it.veces_usado = (it.veces_usado || 0) + 1; it.ultimo_uso = d.ultimo_uso; }
      });
      var msg = 'Outfit registrado';
      if (withXP !== false && XP.key && !XP.done) {
        var j = await (await jpost('/actividades/api/activity/log', { key: XP.key })).json().catch(function () { return {}; });
        if (j.action === 'removed') j = await (await jpost('/actividades/api/activity/log', { key: XP.key })).json().catch(function () { return {}; });
        if (j.action === 'added') {
          XP.done = true; msg += ' · +' + (j.xp != null ? j.xp : XP.pts) + ' XP';
          if (window.euGam) euGam(j.gam || { xp: j.xp });
        }
      }
      toast(msg, 'win');
      todayOffset = 0;  /* el de hoy pasa a ser el que se acaba de usar */
      renderOutfits(); renderToday(); filterItems(); renderRotation();
      return true;
    } catch (_) { toast('No se pudo registrar', 'err'); return false; }
    finally { if (btn) btn.removeAttribute('aria-busy'); }
  }
  async function deleteOutfit(id) {
    var o = ALL_OUTFITS.find(function (x) { return x.id === id; });
    if (!(await euConfirm('¿Eliminar el outfit «' + (o ? o.nombre : '') + '»? Si está asignado a un día de viaje, también se quita de ahí.', { confirmLabel: 'Eliminar' }))) return false;
    var res = await fetch('/guardarropa/api/outfit/' + id, { method: 'DELETE' });
    if (!res.ok) { toast('No se pudo eliminar', 'err'); return false; }
    ALL_OUTFITS.splice(ALL_OUTFITS.findIndex(function (x) { return x.id === id; }), 1);
    renderOutfits(); renderToday();
    toast('Outfit eliminado');
    return true;
  }

  /* Vista flat-lay */
  var ovId = null;
  function openOutfitView(id) {
    var o = ALL_OUTFITS.find(function (x) { return x.id === id; }); if (!o) return;
    ovId = id;
    $('gr-oview-t').textContent = o.nombre;
    $('ov-sub').innerHTML = (o.ocasion ? esc(o.ocasion) + ' · ' : '') + '<span class="gr-stars-ro">' + stars(o.rating || 0) + '</span> · ' +
      (o.veces_usado ? o.veces_usado + '× usado' : 'Nunca usado') + (o.ultimo_uso ? ' · Último: ' + esc(o.ultimo_uso) : '');
    var its = o.items || [];
    $('ov-flat').innerHTML = its.length ? its.map(function (i) {
      return '<div class="gr-piece"><span class="gr-ph">' + visualHTML(i) + '</span><span class="t-meta">' + esc(i.categoria || '') + '</span><span class="t-ui gr-piece-t">' + esc(i.nombre) + '</span></div>';
    }).join('') : '<p class="t-meta">Este outfit no tiene prendas asignadas todavía.</p>';
    $('ov-notes').hidden = !o.notas; $('ov-notes').textContent = o.notas || '';
    var use = document.querySelector('.js-ov-use');
    var used = o.ultimo_uso === TODAY;
    use.disabled = used;
    use.textContent = used ? 'Usado hoy' : 'Usar hoy' + (XP.key && !XP.done ? ' · +' + XP.pts + ' XP' : '');
    icons();
    euModal.open('gr-oview');
  }
  document.querySelector('.js-ov-use').addEventListener('click', async function () {
    if (ovId == null) return;
    if (await useOutfit(ovId, this)) euModal.close('gr-oview');
  });
  document.querySelector('.js-ov-edit').addEventListener('click', function () { var id = ovId; euModal.close('gr-oview'); openOutfitForm(id); });
  document.querySelector('.js-ov-del').addEventListener('click', async function () {
    if (ovId == null) return;
    if (await deleteOutfit(ovId)) euModal.close('gr-oview');
  });

  /* Formulario de outfit */
  var picked = new Set(), pickerCat = '', rating = 0;
  function renderStarsInput() {
    $$('#om-stars [data-val]').forEach(function (b) {
      var v = parseInt(b.dataset.val, 10);
      b.classList.toggle('is-on', v <= rating);
      b.setAttribute('aria-checked', String(v === rating));
    });
  }
  $('om-stars').addEventListener('click', function (e) {
    var b = e.target.closest('[data-val]'); if (!b) return;
    var v = parseInt(b.dataset.val, 10); rating = rating === v ? 0 : v; renderStarsInput();
  });
  function renderPickerCats() {
    var present = {}; ALL_ITEMS.forEach(function (r) { present[r.categoria] = 1; });
    $('om-cats').innerHTML = '<button type="button" class="eu-chip" data-pcat="" aria-pressed="' + !pickerCat + '">Todas</button>' +
      CATEGORIA_ORDER.filter(function (c) { return present[c]; }).map(function (c) {
        return '<button type="button" class="eu-chip" data-pcat="' + esc(c) + '" aria-pressed="' + (pickerCat === c) + '">' + esc(c) + '</button>';
      }).join('');
  }
  $('om-cats').addEventListener('click', function (e) {
    var b = e.target.closest('[data-pcat]'); if (!b) return;
    pickerCat = b.dataset.pcat; renderPickerCats(); renderPicker();
  });
  function renderPicker() {
    var q = $('om-q').value.trim().toLowerCase();
    var list = ALL_ITEMS.filter(function (r) { return (!q || r.nombre.toLowerCase().indexOf(q) >= 0 || r.categoria.toLowerCase().indexOf(q) >= 0) && (!pickerCat || r.categoria === pickerCat); });
    var groups = {};
    list.forEach(function (r) { (groups[r.categoria] = groups[r.categoria] || []).push(r); });
    var cats = CATEGORIA_ORDER.filter(function (c) { return groups[c]; }).concat(Object.keys(groups).filter(function (c) { return CATEGORIA_ORDER.indexOf(c) < 0; }));
    $('om-picker').innerHTML = cats.map(function (c) {
      return '<div class="gr-pgroup"><div class="t-eyebrow gr-pgroup-t">' + esc(c) + ' <span class="num">' + groups[c].length + '</span></div>' +
        groups[c].map(function (r) {
          var on = picked.has(r.id);
          return '<button type="button" class="gr-prow" data-pid="' + r.id + '" aria-pressed="' + on + '">' +
            '<span class="gr-pthumb">' + visualHTML(r) + '</span><span class="gr-prow-t">' + esc(r.nombre) + '</span>' +
            '<span class="eu-act-check"><i data-lucide="check"></i></span></button>';
        }).join('') + '</div>';
    }).join('') || euEmpty('shirt', 'Sin prendas', 'No hay prendas que coincidan.', true);
    icons(); renderPicked();
  }
  $('om-q').addEventListener('input', renderPicker);
  $('om-picker').addEventListener('click', function (e) {
    var b = e.target.closest('[data-pid]'); if (!b) return;
    var id = parseInt(b.dataset.pid, 10);
    if (picked.has(id)) picked.delete(id); else picked.add(id);
    b.setAttribute('aria-pressed', String(picked.has(id)));
    renderPicked();
  });
  function renderPicked() {
    var bar = $('om-picked');
    var sel = ALL_ITEMS.filter(function (r) { return picked.has(r.id); });
    bar.hidden = !sel.length;
    bar.innerHTML = '<span class="t-meta">Elegidas (' + sel.length + ')</span>' + sel.map(function (r) {
      return '<button type="button" class="eu-chip" aria-pressed="true" data-unpick="' + r.id + '" aria-label="Quitar ' + esc(r.nombre) + '">' + esc(r.nombre) + ' <i data-lucide="x"></i></button>';
    }).join('');
    icons();
  }
  $('om-picked').addEventListener('click', function (e) {
    var b = e.target.closest('[data-unpick]'); if (!b) return;
    var id = parseInt(b.dataset.unpick, 10); picked.delete(id);
    var row = document.querySelector('#om-picker [data-pid="' + id + '"]'); if (row) row.setAttribute('aria-pressed', 'false');
    renderPicked();
  });
  function openOutfitForm(id) {
    var o = id ? ALL_OUTFITS.find(function (x) { return x.id === id; }) : null;
    $('gr-outfit-t').textContent = o ? 'Editar outfit' : 'Nuevo outfit';
    $('om-id').value = o ? o.id : '';
    $('om-nombre').value = o ? o.nombre : '';
    $('om-ocasion').value = (o && o.ocasion) || '';
    $('om-notas').value = (o && o.notas) || '';
    $('om-q').value = '';
    setErr('om-err', '');
    rating = (o && o.rating) || 0; renderStarsInput();
    picked = new Set(((o && o.items) || []).map(function (i) { return i.id; }));
    pickerCat = ''; renderPickerCats(); renderPicker();
    euModal.open('gr-outfit');
    setTimeout(function () { $('om-nombre').focus(); }, 30);
  }
  $('gr-outfit-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var nombre = $('om-nombre').value.trim();
    if (!nombre) { setErr('om-err', 'El nombre es obligatorio'); $('om-nombre').focus(); return; }
    var id = $('om-id').value;
    var res = await jpost(id ? '/guardarropa/api/outfit/' + id : '/guardarropa/api/outfit',
      { nombre: nombre, ocasion: $('om-ocasion').value, rating: rating, notas: $('om-notas').value.trim(), item_ids: Array.from(picked) }, id ? 'PUT' : 'POST');
    if (!res.ok) { setErr('om-err', 'Error al guardar'); return; }
    var saved = await res.json();
    if (id) { var i = ALL_OUTFITS.findIndex(function (x) { return x.id === saved.id; }); if (i >= 0) ALL_OUTFITS[i] = Object.assign(ALL_OUTFITS[i], saved); }
    else ALL_OUTFITS.unshift(saved);
    euModal.close('gr-outfit');
    renderOutfits(); renderToday();
    toast('Outfit «' + saved.nombre + '» guardado');
  });

  /* ── Coach de imagen · IA ─────────────────────────────────── */
  var ai = { mode: 'ocasion', occ: 'Casual', anchor: null, last: null };
  function aiLabel() { return ai.mode === 'item' ? 'Combinar con IA' : 'Generar look'; }
  $$('[data-ai-mode]').forEach(function (b) {
    b.addEventListener('click', function () {
      ai.mode = b.dataset.aiMode;
      $$('[data-ai-mode]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      $('ai-anchor-wrap').hidden = ai.mode !== 'item';
      $('ai-go').querySelector('span').textContent = aiLabel();
      $('ai-result').hidden = true;
      if (ai.mode === 'item' && !$('ai-anchor').dataset.filled) {
        var byCat = {};
        ALL_ITEMS.forEach(function (i) { (byCat[i.categoria] = byCat[i.categoria] || []).push(i); });
        $('ai-anchor').innerHTML = '<option value="">— elegir prenda —</option>' + Object.keys(byCat).sort().map(function (c) {
          return '<optgroup label="' + esc(c) + '">' + byCat[c].map(function (i) { return '<option value="' + i.id + '">' + esc(i.nombre) + '</option>'; }).join('') + '</optgroup>';
        }).join('');
        $('ai-anchor').dataset.filled = '1';
      }
    });
  });
  $('ai-anchor').addEventListener('change', function () { ai.anchor = this.value ? parseInt(this.value, 10) : null; });
  $('ai-occs').addEventListener('click', function (e) {
    var b = e.target.closest('[data-ai-occ]'); if (!b) return;
    ai.occ = b.dataset.aiOcc;
    $$('#ai-occs [data-ai-occ]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
  });
  async function generateAI() {
    if (ai.mode === 'item' && !ai.anchor) { toast('Elige una prenda para combinar', 'err'); return; }
    var btn = $('ai-go');
    btn.setAttribute('aria-busy', 'true'); btn.disabled = true;
    $('ai-result').hidden = true;
    try {
      var d = await (await jpost(ai.mode === 'item' ? '/guardarropa/api/ai-outfit-from-item' : '/guardarropa/api/ai-outfit',
        ai.mode === 'item' ? { item_id: ai.anchor, ocasion: ai.occ } : { ocasion: ai.occ })).json();
      if (!d.ok) { toast('Error IA: ' + (d.error || 'desconocido'), 'err'); return; }
      renderAI(d);
    } catch (_) { toast('Error al conectar con IA', 'err'); }
    finally { btn.removeAttribute('aria-busy'); btn.disabled = false; }
  }
  $('ai-go').addEventListener('click', generateAI);
  function renderAI(d) {
    ai.last = d;
    var chosen = (d.item_ids || []).map(function (id) { return ALL_ITEMS.find(function (x) { return x.id === id; }); }).filter(Boolean);
    var box = $('ai-result');
    box.innerHTML = '<div class="eu-card eu-card--inset eu-vstack gr-ai-res">' +
      '<div class="eu-between"><div><div class="t-card">' + esc(d.nombre || 'Look ' + ai.occ) + '</div><div class="t-meta">' + esc(d.harmony || '') + '</div></div>' +
      '<span class="gr-stars-ro">' + stars(d.rating || 5) + '</span></div>' +
      (d.why_works ? '<p class="t-body fg-2">' + esc(d.why_works) + '</p>' : '') +
      ((d.tips || []).length ? '<ul class="gr-tips">' + d.tips.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>' : '') +
      '<div class="gr-ai-items">' + chosen.map(function (i) {
        return '<span class="gr-ai-item"><span class="gr-pthumb">' + visualHTML(i) + '</span><span><span class="t-ui">' + esc(i.nombre) + '</span><span class="t-meta">' + esc(i.categoria) + '</span></span></span>';
      }).join('') + '</div>' +
      '<div class="eu-hstack"><button type="button" class="eu-btn eu-btn--primary eu-grow js-ai-save">Guardar outfit</button>' +
      '<button type="button" class="eu-btn eu-btn--ghost js-ai-again"><i data-lucide="refresh-cw"></i>Regenerar</button></div></div>';
    box.hidden = false;
    icons();
  }
  $('ai-result').addEventListener('click', async function (e) {
    if (e.target.closest('.js-ai-again')) { generateAI(); return; }
    if (!e.target.closest('.js-ai-save') || !ai.last) return;
    var d = ai.last;
    var saved = await (await jpost('/guardarropa/api/outfit', { nombre: d.nombre, ocasion: d.ocasion || ai.occ, rating: d.rating || 5, notas: d.why_works, item_ids: d.item_ids || [] })).json().catch(function () { return {}; });
    if (saved.id) { ALL_OUTFITS.unshift(saved); renderOutfits(); renderToday(); $('ai-result').hidden = true; toast('Outfit guardado'); }
    else toast('No se pudo guardar', 'err');
  });

  /* ── Panel lateral: outfit de hoy y rotación ──────────────── */
  var todayOffset = 0;
  function todayPick() {
    var list = ALL_OUTFITS.filter(function (o) { return (o.items || []).length; });
    if (!list.length) return null;
    var worn = list.find(function (o) { return o.ultimo_uso === TODAY; });
    if (worn && !todayOffset) return worn;
    /* Sugerencia: el que lleva más tiempo sin usarse; a igualdad, el de mejor rating */
    list.sort(function (a, b) { return (a.ultimo_uso || '').localeCompare(b.ultimo_uso || '') || (b.rating || 0) - (a.rating || 0); });
    return list[todayOffset % list.length];
  }
  function renderToday() {
    var o = todayPick();
    var card = document.querySelector('.gr-today'), empty = document.querySelector('.gr-today-empty'), mini = document.querySelector('.gr-today-mini');
    card.hidden = !o; empty.hidden = !!o; mini.hidden = !o;
    if (!o) return;
    var used = o.ultimo_uso === TODAY;
    var its = (o.items || []).slice().sort(function (a, b) { return (b.foto ? 1 : 0) - (a.foto ? 1 : 0); }).slice(0, 2);
    card.querySelector('.gr-today-pieces').innerHTML = its.map(function (i) { return '<span class="gr-ph">' + visualHTML(i) + '</span>'; }).join('');
    card.querySelector('.gr-today-pieces').dataset.id = o.id;
    $$('.gr-today-name').forEach(function (el) { el.textContent = o.nombre; });
    card.querySelector('.gr-today-sub').textContent = [o.ocasion, plural((o.items || []).length, 'prenda'), used ? 'usado hoy' : (o.ultimo_uso ? 'último: ' + o.ultimo_uso : 'nunca usado')].filter(Boolean).join(' · ');
    var use = card.querySelector('.js-today-use');
    use.dataset.id = o.id;
    use.disabled = used;
    use.innerHTML = used ? '<i data-lucide="check"></i>Usado hoy' : 'Usar hoy' + (XP.key && !XP.done ? ' · +' + XP.pts + ' XP' : '');
    card.querySelector('.js-today-next').hidden = ALL_OUTFITS.filter(function (x) { return (x.items || []).length; }).length < 2;
    mini.dataset.id = o.id;
    mini.querySelector('.gr-today-mini-ph').innerHTML = its[0] ? visualHTML(its[0]) : '';
    var badge = mini.querySelector('.gr-today-xp');
    badge.textContent = used ? 'Usado ✓' : (XP.key && !XP.done ? '+' + XP.pts + ' XP' : 'Ver');
    icons();
  }
  document.querySelector('.js-today-use').addEventListener('click', function () { useOutfit(parseInt(this.dataset.id, 10), this); });
  document.querySelector('.js-today-next').addEventListener('click', function () { todayOffset++; renderToday(); });
  $$('.js-today-view').forEach(function (b) {
    b.addEventListener('click', function () {
      var id = parseInt(b.dataset.id || document.querySelector('.gr-today-pieces').dataset.id, 10);
      if (id) openOutfitView(id);
    });
  });

  function renderRotation() {
    var total = ALL_ITEMS.length;
    var idle = ALL_ITEMS.filter(isIdle).length;
    var pct = total ? Math.round((total - idle) / total * 100) : 0;
    $('gr-rot-pct').textContent = total ? pct + '%' : '—';
    var bar = $('gr-rot-bar');
    bar.querySelector('i').style.width = pct + '%';
    bar.setAttribute('aria-valuenow', pct);
    var b = $('gr-rot-idle');
    b.textContent = !total ? 'Aún no hay prendas' : idle ? plural(idle, 'prenda') + ' sin usar · candidata' + (idle === 1 ? '' : 's') + ' a donar' : 'Todas las prendas se usaron en los últimos 90 días';
    b.disabled = !idle;
  }

  /* ── Análisis (armario cápsula) ───────────────────────────── */
  var CAPSULE_RULES = [
    { section: 'anclas', label: 'Camisa blanca · la prenda de mayor versatilidad cromática', check: function (it) { return it.some(function (i) { return i.categoria === 'Camisa' && /(blanc|white)/i.test((i.color_name || '') + i.color_hex); }); } },
    { section: 'anclas', label: 'Blazer versátil navy/gris · sube el dress code instantáneamente', check: function (it) { return it.some(function (i) { return i.categoria === 'Blazer / Saco'; }); } },
    { section: 'anclas', label: 'Oxford negro · calzado más versátil del armario masculino', check: function (it) { return it.some(function (i) { return i.categoria === 'Zapatos formales' && /(negr|black|#0|#1|#2)/i.test((i.color_name || '') + i.color_hex); }); } },
    { section: 'anclas', label: 'Pantalón gris · ancla neutra que combina con todo', check: function (it) { return it.some(function (i) { return i.categoria === 'Pantalón' && /(gris|gray|grey)/i.test(i.color_name || ''); }); } },
    { section: 'paleta', label: 'Base neutra ≥3: blanco + gris + navy en superiores', check: function (it) { return it.filter(function (i) { return ['Camisa', 'Camiseta', 'Polo', 'Suéter'].indexOf(i.categoria) >= 0; }).length >= 3; } },
    { section: 'paleta', label: 'Denim de calidad · puente smart-casual indispensable', check: function (it) { return it.some(function (i) { return i.categoria === 'Jeans'; }); } },
    { section: 'paleta', label: '2+ pantalones en neutros (gris, beige, navy, khaki)', check: function (it) { return it.filter(function (i) { return i.categoria === 'Pantalón'; }).length >= 2; } },
    { section: 'dresscode', label: 'Calzado café/camel · para look diurno y casual sofisticado', check: function (it) { return it.some(function (i) { return ['Zapatos formales', 'Zapatos casuales', 'Botas'].indexOf(i.categoria) >= 0 && /(caf|cam[ae]|marr|brow|tan)/i.test(i.color_name || ''); }); } },
    { section: 'dresscode', label: 'Sneakers minimalistas · pieza clave del smart-casual moderno', check: function (it) { return it.some(function (i) { return i.categoria === 'Sneakers'; }); } },
    { section: 'dresscode', label: 'Capa exterior de calidad (chamarra/abrigo)', check: function (it) { return it.some(function (i) { return i.categoria === 'Chamarra / Abrigo'; }); } },
    { section: 'amplificadores', label: 'Accesorio de calidad · 20% del outfit, 80% del impacto visual', check: function (it) { return it.some(function (i) { return i.categoria === 'Accesorio'; }); } },
    { section: 'amplificadores', label: 'Suéter o polo · transiciones de temperatura y capas interiores', check: function (it) { return it.some(function (i) { return ['Suéter', 'Polo'].indexOf(i.categoria) >= 0; }); } },
    { section: 'volumen', label: 'Volumen mínimo: 20+ prendas activas para versatilidad real', check: function (it) { return it.length >= 20; } },
    { section: 'volumen', label: 'Cobertura multiocasión: formal + casual + business', check: function (it) {
      var has = function (cats) { return it.some(function (i) { return cats.indexOf(i.categoria) >= 0; }); };
      return [has(['Blazer / Saco', 'Zapatos formales', 'Traje / Conjunto']), has(['Camiseta', 'Jeans', 'Sneakers']), has(['Camisa', 'Pantalón'])].filter(Boolean).length >= 2;
    } }
  ];
  var CAPSULE_SECTIONS = [
    { key: 'anclas', title: 'Prendas ancla', icon: 'anchor', desc: 'Las piezas de mayor retorno de inversión: combinan con casi todo lo demás, así que son las primeras que deberían estar cubiertas.' },
    { key: 'paleta', title: 'Paleta 70/20/10', icon: 'palette', desc: 'La regla de Faber Birren: ~70% de neutros como base, 20% de color secundario y 10% de acento — así casi cualquier par de prendas funciona junto.' },
    { key: 'dresscode', title: 'Cobertura de dress code', icon: 'shirt', desc: 'Piezas que cubran del extremo casual al formal, para no quedarte sin qué ponerte cuando cambia el contexto del día.' },
    { key: 'amplificadores', title: 'Amplificadores de look', icon: 'sparkle', desc: 'No son la base pero elevan cualquier outfit — el 20% del esfuerzo que se nota en el 80% del impacto visual.' },
    { key: 'volumen', title: 'Métricas de volumen', icon: 'layout-grid', desc: 'Un armario cápsula real necesita suficientes piezas y cobertura de ocasión para sostenerse sin comprar algo nuevo cada semana.' }
  ];
  function renderAnalysis() {
    var box = $('gr-analisis');
    var act = ALL_ITEMS.filter(function (i) { return i.activo !== 0; });
    if (!act.length) {
      box.innerHTML = '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="sparkles"></i></div><div class="t-card">Aún no hay nada que analizar</div>' +
        '<p>Añade algunas prendas y aquí verás qué tan cerca estás de un armario cápsula completo, con cada principio explicado.</p></div>';
      icons(); return;
    }
    var colorMap = {};
    act.forEach(function (i) { var p = matchColor(i.color_hex); var n = (p && p.name) || 'Otro'; colorMap[n] = colorMap[n] || { count: 0, hex: (p && p.hex) || i.color_hex }; colorMap[n].count++; });
    var colors = Object.keys(colorMap).sort(function (a, b) { return colorMap[b].count - colorMap[a].count; });
    var maxC = colors.length ? colorMap[colors[0]].count : 1;
    var catMap = {};
    act.forEach(function (i) { catMap[i.categoria] = (catMap[i.categoria] || 0) + 1; });
    var cats = Object.keys(catMap).sort(function (a, b) { return catMap[b] - catMap[a]; });
    var maxK = cats.length ? catMap[cats[0]] : 1;
    var okAll = CAPSULE_RULES.filter(function (r) { return r.check(act); }).length;
    var score = Math.round(okAll / CAPSULE_RULES.length * 100);
    var tone = score >= 86 ? 'success' : score >= 71 ? 'brand' : score >= 50 ? 'warning' : 'danger';
    var lvl = score >= 96 ? 'Maestro' : score >= 86 ? 'Élite' : score >= 71 ? 'Avanzado' : score >= 51 ? 'Sólido' : score >= 31 ? 'Competente' : 'Iniciado';
    var totalVal = act.reduce(function (s, i) { return s + (i.precio || 0); }, 0);
    var withUso = act.filter(function (i) { return i.precio && i.veces_usado > 0; });
    var avgCpu = withUso.length ? withUso.reduce(function (s, i) { return s + i.precio / i.veces_usado; }, 0) / withUso.length : 0;
    var R = 52, C = 2 * Math.PI * R;
    box.innerHTML =
      '<div class="eu-card gr-score">' +
        '<div class="gr-ring gr-ring--' + tone + '"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="' + R + '" class="gr-ring-bg"/>' +
          '<circle cx="60" cy="60" r="' + R + '" class="gr-ring-fg" stroke-dasharray="' + C.toFixed(1) + '" stroke-dashoffset="' + (C * (1 - score / 100)).toFixed(1) + '"/></svg>' +
          '<div class="gr-ring-lbl"><span class="t-data">' + score + '%</span><span class="t-eyebrow">' + lvl + '</span></div></div>' +
        '<div class="eu-vstack gr-score-info"><div><div class="t-eyebrow">Score de armario cápsula</div>' +
          '<p class="t-meta fg-2">Qué tan preparado está tu clóset para vestir bien todos los días sin comprar de más, según principios de moda masculina (Susie Faux · Faber Birren · Permanent Style).</p></div>' +
          '<div class="eu-grid-3 gr-score-stats">' +
            '<div class="eu-stat"><div class="eu-stat-lbl">Prendas</div><div class="eu-stat-val">' + act.length + '</div></div>' +
            '<div class="eu-stat"><div class="eu-stat-lbl">Valor total</div><div class="eu-stat-val">' + money(totalVal) + '</div></div>' +
            '<div class="eu-stat"><div class="eu-stat-lbl">Costo / uso prom.</div><div class="eu-stat-val">' + (avgCpu ? money(avgCpu) : '—') + '</div></div>' +
          '</div></div></div>' +
      '<div class="gr-an-grid">' +
        '<div class="eu-card eu-vstack"><h2 class="t-card">Distribución de colores</h2><div class="gr-bars">' + colors.map(function (n) {
          var c = colorMap[n];
          return '<button type="button" class="gr-bar" data-color="' + esc(n) + '" style="--sw:' + esc(c.hex) + '" aria-label="Ver ' + plural(c.count, 'prenda') + ' ' + esc(n) + '">' +
            '<span class="gr-bar-dot"></span><span class="gr-bar-l">' + esc(n) + '</span><span class="gr-bar-t"><i style="width:' + Math.round(c.count / maxC * 100) + '%"></i></span><span class="num t-meta">' + c.count + '</span></button>';
        }).join('') + '</div></div>' +
        '<div class="eu-card eu-vstack"><h2 class="t-card">Prendas por categoría</h2><div class="gr-bars">' + cats.map(function (k) {
          return '<button type="button" class="gr-bar gr-bar--cat" data-catf="' + esc(k) + '" aria-label="Ver ' + plural(catMap[k], 'prenda') + ' en ' + esc(k || 'Sin categoría') + '">' +
            '<span class="gr-bar-l">' + esc(k || 'Sin categoría') + '</span><span class="gr-bar-t"><i style="width:' + Math.round(catMap[k] / maxK * 100) + '%"></i></span><span class="num t-meta">' + catMap[k] + '</span></button>';
        }).join('') + '</div></div>' +
      '</div>' +
      '<div class="eu-card eu-vstack gr-check"><h2 class="t-card">Checklist · armario cápsula</h2>' + CAPSULE_SECTIONS.map(function (sec) {
        var rules = CAPSULE_RULES.filter(function (r) { return r.section === sec.key; });
        var ok = rules.filter(function (r) { return r.check(act); }).length;
        return '<section class="gr-check-sec"><div class="eu-hstack"><span class="eu-row-ic fg-brand"><i data-lucide="' + sec.icon + '"></i></span>' +
          '<span class="t-ui eu-grow">' + esc(sec.title) + '</span><span class="eu-badge' + (ok === rules.length ? ' eu-badge--success' : '') + ' num">' + ok + '/' + rules.length + '</span></div>' +
          '<p class="t-meta">' + esc(sec.desc) + '</p>' + rules.map(function (r) {
            var y = r.check(act);
            return '<div class="gr-rule' + (y ? ' is-ok' : '') + '"><i data-lucide="' + (y ? 'check-circle-2' : 'circle-alert') + '"></i><span class="eu-grow">' + esc(r.label) + '</span><span class="t-meta">' + (y ? 'OK' : 'Falta') + '</span></div>';
          }).join('') + '</section>';
      }).join('') +
      '<div class="eu-between gr-check-ft"><a class="t-meta gr-link" href="/guardarropa/wishlist/">Ver wishlist <i data-lucide="arrow-right"></i></a>' +
      '<button type="button" class="eu-btn eu-btn--secondary js-cap-ai"><i data-lucide="sparkles"></i><span>Análisis IA profundo</span></button></div></div>' +
      '<div id="cap-ai" hidden></div>';
    icons();
  }
  $('gr-analisis').addEventListener('click', function (e) {
    var c = e.target.closest('[data-color]'); if (c) { jumpFilter({ color: c.dataset.color }); return; }
    var k = e.target.closest('[data-catf]'); if (k) { jumpFilter({ catF: k.dataset.catf }); return; }
    if (e.target.closest('.js-cap-ai')) capsuleAI(e.target.closest('.js-cap-ai'));
  });
  async function capsuleAI(btn) {
    var out = $('cap-ai');
    btn.setAttribute('aria-busy', 'true'); btn.disabled = true; out.hidden = true;
    try {
      var d = await (await fetch('/guardarropa/api/capsule/analyze', { method: 'POST' })).json();
      if (!d.ok) { toast('Error IA: ' + (d.error || 'desconocido'), 'err'); return; }
      var tone = (d.score || 0) >= 86 ? 'success' : (d.score || 0) >= 71 ? 'brand' : 'danger';
      out.innerHTML = '<div class="eu-card eu-vstack gr-capai">' +
        '<div class="eu-between"><div><div class="t-eyebrow">Coach de imagen · análisis IA</div><div class="t-section">Diagnóstico profesional</div></div>' +
        '<div class="gr-capai-score gr-tone--' + tone + '"><span class="t-data">' + (d.score || 0) + '</span><span class="t-eyebrow">' + esc(d.score_label || '') + '</span></div></div>' +
        (d.elite_verdict ? '<blockquote class="t-quote gr-verdict">«' + esc(d.elite_verdict) + '»</blockquote>' : '') +
        (d.color_harmony ? '<div><div class="t-eyebrow">Armonía cromática</div><p class="t-meta fg-2">' + esc(d.color_harmony) + '</p></div>' : '') +
        '<div class="gr-capai-grid"><div><div class="t-eyebrow">Fortalezas</div>' + ((d.strengths || []).map(function (s) {
          return '<div class="gr-rule is-ok"><i data-lucide="check-circle-2"></i><span>' + esc(s) + '</span></div>';
        }).join('') || '<p class="t-meta">—</p>') + '</div>' +
        '<div class="eu-grid-2"><div class="eu-card eu-card--inset eu-stat"><div class="eu-stat-lbl">Índice de versatilidad</div><div class="eu-stat-val">' + (d.versatility_index || 0) + '</div></div>' +
        '<div class="eu-card eu-card--inset eu-stat"><div class="eu-stat-lbl">Outfits posibles</div><div class="eu-stat-val">~' + (d.outfit_combinations_est || 0) + '</div></div></div></div>' +
        ((d.gaps || []).length ? '<div class="eu-vstack"><div class="t-eyebrow">Prendas prioritarias a adquirir</div>' + d.gaps.map(function (g) {
          return '<div class="eu-row gr-gap"><span class="eu-badge eu-badge--' + (g.priority === 'alta' ? 'danger' : 'warning') + '">' + esc(g.priority) + '</span>' +
            '<div class="eu-row-main"><div class="eu-row-t">' + esc(g.item) + '</div><div class="eu-row-s">' + esc(g.reason) + '</div></div>' +
            (g.versatility_multiplier ? '<span class="t-meta num fg-brand">×' + esc(g.versatility_multiplier) + '</span>' : '') + '</div>';
        }).join('') + '</div>' : '') + '</div>';
      out.hidden = false; icons();
      out.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (_) { toast('Error al conectar con IA', 'err'); }
    finally { btn.removeAttribute('aria-busy'); btn.disabled = false; }
  }

  /* ── Arranque ─────────────────────────────────────────────── */
  renderSwatches();
  renderDepts();
  setView(view);
  filterItems();
  renderToday();
  renderRotation();
  function fromHash() { var h = location.hash.slice(1); if (h === 'outfits' || h === 'analisis') setTab(h); }
  window.addEventListener('hashchange', fromHash);
  fromHash();
  if (new URLSearchParams(location.search).get('nueva')) {
    try { history.replaceState(null, '', location.pathname); } catch (_) {}
    openItemForm(null);
  }
})();
