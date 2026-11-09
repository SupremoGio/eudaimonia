/* Paideia — Design System V2 · handoff Paideia v2. Libros: héroe (meta con
   ritmo, leyendo ahora con «Página» → /progreso y «Terminar +10 XP»),
   biblioteca de portadas con filtros y «Empezar», modal con búsqueda
   OpenLibrary + portada. Películas: ranking personal con calificación por
   dimensiones y búsqueda OMDb. */
(function () {
  'use strict';
  var root = document.getElementById('pd');
  if (!root) return;
  var BASE = '/paideia';
  var DATA = JSON.parse(document.getElementById('pd-data').textContent || '{}');
  var PELIS = DATA.peliculas || { peliculas: [], ranking: [], vistas_n: 0, total: 0 };
  var DIMS = DATA.dims || [];
  var mod = 'libros', peFilter = 'todos', openRate = null;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function json(url, method, body) {
    var o = { method: method || 'GET' };
    if (body !== undefined) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    return fetch(url, o).then(function (r) { return r.json().then(function (d) { if (!r.ok && d.ok === undefined) d.ok = false; return d; }); });
  }
  function reload(ms) { setTimeout(function () { location.reload(); }, ms || 450); }
  function busy(btn, on) { if (btn) { btn.disabled = on; btn.setAttribute('aria-busy', String(on)); } }

  /* ── Submódulos ─────────────────────────────────────────────────────── */
  function setMod(m) {
    mod = m; root.dataset.mod = m;
    document.querySelectorAll('[data-mod-set]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.modSet === m)); });
    $('mod-libros').hidden = m !== 'libros';
    $('mod-peliculas').hidden = m !== 'peliculas';
    document.querySelectorAll('.js-new-lbl').forEach(function (s) { s.textContent = m === 'libros' ? 'Libro' : 'Película'; });
    document.querySelectorAll('.eu-topbar .js-new').forEach(function (b) { b.setAttribute('aria-label', m === 'libros' ? 'Nuevo libro' : 'Nueva película'); });
    if (m === 'peliculas') renderPelis();
  }
  document.querySelectorAll('[data-mod-set]').forEach(function (b) { b.addEventListener('click', function () { setMod(b.dataset.modSet); }); });
  document.querySelectorAll('.js-new').forEach(function (b) { b.addEventListener('click', function () { if (mod === 'libros') abrirNuevo(); else abrirPeli(); }); });

  /* ── Filtros de la biblioteca (nota 8): Por leer · Leídos · Todos ─────── */
  var bookFilter = 'por_leer';
  function pdApplyFilter() {
    var shown = 0, any = false;
    document.querySelectorAll('[data-f]').forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.f === bookFilter)); });
    document.querySelectorAll('.pd-book').forEach(function (b) {
      any = true;
      var ok = bookFilter === 'todos' || b.dataset.estado === bookFilter;
      b.hidden = !ok; if (ok) shown++;
    });
    var g = $('pd-grid'); if (g) g.dataset.filter = bookFilter;
    var nm = $('pd-nomatch'); if (nm) nm.hidden = shown > 0;
  }
  window.pdApplyFilter = pdApplyFilter;
  pdApplyFilter();

  /* ── Héroe: Página / Registrar %, Terminar (handoff Paideia v2, notas 5–6).
     Delegado en #mod-libros: refreshLibros() reemplaza su contenido. ── */
  var libs = $('mod-libros');
  function refreshLibros() {
    return fetch(BASE + '/').then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var fresh = doc.getElementById('mod-libros');
      if (fresh) { libs.innerHTML = fresh.innerHTML; icons(); if (window.pdApplyFilter) pdApplyFilter(); }
    });
  }
  function setAnchor(label, ok) {
    var a = libs.querySelector('.js-anchor'); if (!a || !ok) return;
    a.classList.add('is-ok');
    a.innerHTML = '<i data-lucide="circle-check"></i><span>«' + esc(label || a.dataset.label) + '» marcada hoy en Acta Diurna</span>';
    icons();
  }
  libs.addEventListener('click', function (e) {
    var chip = e.target.closest('[data-f]');
    if (chip) { bookFilter = chip.dataset.f; pdApplyFilter(); return; }
    var b = e.target.closest('.js-prog, .js-finish, .js-edit, .js-meta, .js-start, .js-rate');
    if (!b) return;
    if (b.classList.contains('js-edit')) { abrirEditar(+b.dataset.id); return; }
    if (b.classList.contains('js-rate')) {
      abrirEditar(+b.dataset.id).then(function () {
        var r = $('lb-rating-row'); if (r) { r.scrollIntoView({ block: 'center' }); var st = r.querySelector('.pd-star'); if (st) st.focus(); }
      });
      return;
    }
    if (b.classList.contains('js-start')) {
      busy(b, true);
      json(BASE + '/api/libros/' + b.dataset.id, 'PATCH', { estado: 'leyendo' }).then(function (r) {
        if (!r.ok) throw new Error(r.error);
        toast('Empezado · ya está en «Leyendo ahora»', 'win');
        return refreshLibros().then(function () { var h = $('pd-hero'); if (h) h.scrollIntoView({ block: 'start', behavior: 'smooth' }); });
      }).catch(function () { busy(b, false); toast('No se pudo empezar', 'err'); });
      return;
    }
    if (b.classList.contains('js-meta')) { euModal.open('m-meta'); setTimeout(function () { $('meta-input').focus(); }, 30); return; }
    var art = b.closest('.pd-rd');
    if (b.classList.contains('js-prog')) {
      var f = art.querySelector('.js-prog-form');
      f.hidden = !f.hidden;
      art.querySelectorAll('.js-prog, .js-finish').forEach(function (x) { x.hidden = !f.hidden; });
      if (!f.hidden) { var inp = f.querySelector('input'); inp.focus(); inp.select(); }
      return;
    }
    if (b.classList.contains('js-finish')) {
      busy(b, true);
      json(BASE + '/api/libros/' + b.dataset.id, 'PATCH', { estado: 'leido' }).then(function (r) {
        if (!r.ok) throw new Error(r.error);
        var st = r.stats || {};
        var msg = '«' + art.dataset.titulo + '» terminado · +10 XP · +5 EC · meta ' + st.leidos_este_anio + '/' + st.meta_anual;
        if (window.euGam && r.gam) euGam(r.gam, { el: b });
        (window.euToast || toast)(msg, 'win');
        return refreshLibros();
      }).catch(function () { busy(b, false); toast('No se pudo terminar', 'err'); });
    }
  });
  libs.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var f = e.target.closest('.js-prog-form'); if (!f) return;
    f.hidden = true; f.closest('.pd-rd').querySelectorAll('.js-prog, .js-finish').forEach(function (x) { x.hidden = false; });
  });
  libs.addEventListener('submit', function (e) {
    var f = e.target.closest('.js-prog-form'); if (!f) return;
    e.preventDefault();
    var v = f.querySelector('input').value, body = f.dataset.mode === 'pagina' ? { pagina: v } : { pct: v };
    var btn = f.querySelector('button[type=submit]'); busy(btn, true);
    json(BASE + '/api/libros/' + f.dataset.id + '/progreso', 'POST', body).then(function (r) {
      if (!r.ok) throw new Error(r.error);
      if (r.nueva) {
        toast('Avance guardado · «' + r.actividad + '» marcada en Acta', 'win');
        if (window.euGam && r.gam) euGam(r.gam, { el: btn });
      } else toast('Avance guardado');
      setAnchor(r.actividad, r.ancla_marcada);
      return refreshLibros().then(function () { setAnchor(r.actividad, r.ancla_marcada); });
    }).catch(function () { busy(btn, false); toast('No se pudo guardar el avance', 'err'); });
  });

  /* ── Vista previa de portada / póster ───────────────────────────────── */
  var CAPT = {
    lb: ['Portada encontrada', 'Sin portada — búscalo por título para autocompletarla'],
    pe: ['Póster encontrado', 'Sin póster — búscala por título para autocompletarlo'],
  };
  function setCover(pfx, url) {
    $(pfx + '-portada').value = url || '';
    $(pfx + '-cover-row').hidden = false;
    var img = $(pfx + '-cover-img');
    if (url) img.src = url; else img.removeAttribute('src');
    img.hidden = !url;
    $(pfx + '-cover-empty').hidden = !!url;
    $(pfx + '-cover-caption').textContent = CAPT[pfx][url ? 0 : 1];
    $(pfx + '-cover-clear').hidden = !url;
  }
  ['lb', 'pe'].forEach(function (pfx) { $(pfx + '-cover-clear').addEventListener('click', function () { setCover(pfx, null); }); });

  /* ── Combobox de búsqueda (libros y películas) ──────────────────────── */
  function combobox(input, drop, fetchFn, itemHtml, onPick) {
    var timer = null, res = [], active = -1;
    function hide() { drop.hidden = true; drop.innerHTML = ''; active = -1; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); }
    function move(d) {
      var items = drop.querySelectorAll('.pd-opt');
      if (!items.length) return;
      active = (active + d + items.length) % items.length;
      items.forEach(function (el, i) { el.setAttribute('aria-selected', String(i === active)); });
      input.setAttribute('aria-activedescendant', items[active].id);
      items[active].scrollIntoView({ block: 'nearest' });
    }
    function pick(i) { var r = res[i]; if (!r) return; hide(); onPick(r); }
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 3) { hide(); return; }
      timer = setTimeout(function () {
        fetchFn(q).then(function (list) {
          if (input.value.trim() !== q) return;
          if (!list.length) { hide(); return; }
          res = list; active = -1;
          drop.innerHTML = list.map(function (r, i) {
            return '<div class="pd-opt" id="' + drop.id + '-' + i + '" data-i="' + i + '" role="option" aria-selected="false">' + itemHtml(r) + '</div>';
          }).join('');
          drop.hidden = false; input.setAttribute('aria-expanded', 'true');
        }).catch(hide);
      }, 450);
    });
    input.addEventListener('keydown', function (e) {
      if (drop.hidden) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); pick(active); }
      else if (e.key === 'Escape') { e.stopPropagation(); hide(); }
    });
    drop.addEventListener('mousedown', function (e) { e.preventDefault(); });
    drop.addEventListener('click', function (e) { var o = e.target.closest('.pd-opt'); if (o) pick(+o.dataset.i); });
    document.addEventListener('click', function (e) { if (!e.target.closest('.pd-search') || !input.parentNode.contains(e.target)) hide(); });
    return { hide: hide };
  }
  function optHtml(img, title, meta) {
    return (img ? '<img src="' + esc(img) + '" alt="">' : '<span class="pd-opt-noimg"></span>') +
      '<span class="pd-opt-bd"><span class="t-ui">' + esc(title) + '</span><span class="t-meta">' + esc(meta) + '</span></span>';
  }

  /* ── Modal libro ────────────────────────────────────────────────────── */
  var lbSearch = combobox($('lb-titulo'), $('lb-drop'),
    function (q) { return json(BASE + '/api/buscar?q=' + encodeURIComponent(q)).then(function (d) { return d.resultados || []; }); },
    function (b) { return optHtml(b.portada, b.titulo, (b.autor || 'Autor desconocido') + (b.paginas ? ' · ' + b.paginas + ' pág.' : '') + (b.anio ? ' · ' + b.anio : '')); },
    function (b) {
      $('lb-titulo').value = b.titulo;
      if (b.autor) $('lb-autor').value = b.autor;
      if (b.paginas) $('lb-pag-tot').value = b.paginas;
      setCover('lb', b.portada || null);
    });

  function toggleEstado() {
    var est = $('lb-estado').value, modo = $('lb-modo').value;
    $('lb-rating-row').hidden = est !== 'leido';
    $('lb-pag-act-row').hidden = est === 'por_leer';
    $('lb-pct-field').hidden = est === 'por_leer' || modo !== 'pct';
  }
  function setModo(m) {
    $('lb-modo').value = m;
    document.querySelectorAll('[data-modo]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.modo === m)); });
    $('lb-pag-fields').hidden = m !== 'paginas';
    toggleEstado();
  }
  function setRating(v) {
    $('lb-rating').value = v || '';
    document.querySelectorAll('#lb-rating-picker .pd-star').forEach(function (b) {
      var on = !!v && +b.dataset.val <= v;
      b.classList.toggle('is-on', on);
      b.setAttribute('aria-checked', String(!!v && +b.dataset.val === v));
    });
    $('lb-rating-clear').hidden = !v;
  }
  $('lb-estado').addEventListener('change', toggleEstado);
  document.querySelectorAll('[data-modo]').forEach(function (b) { b.addEventListener('click', function () { setModo(b.dataset.modo); }); });
  document.querySelectorAll('#lb-rating-picker .pd-star').forEach(function (b) { b.addEventListener('click', function () { setRating(+b.dataset.val); }); });
  $('lb-rating-clear').addEventListener('click', function () { setRating(null); });

  function fillLibro(l) {
    l = l || {};
    $('lb-id').value = l.id || '';
    $('lb-titulo').value = l.titulo || '';
    $('lb-autor').value = l.autor || '';
    $('lb-categoria').value = l.categoria || 'Otro';
    $('lb-estado').value = l.estado || 'por_leer';
    $('lb-pag-tot').value = l.paginas_totales || '';
    $('lb-pag-act').value = l.paginas_actuales || '';
    $('lb-pct').value = l.progreso_pct == null ? '' : l.progreso_pct;
    $('lb-notas').value = l.notas || '';
    $('lb-delete').hidden = !l.id;
    $('m-libro-t').textContent = l.id ? 'Editar libro' : 'Nuevo libro';
    setRating(l.rating || null);
    setCover('lb', l.portada || null);
    lbSearch.hide();
    setModo(l.progreso_pct != null ? 'pct' : 'paginas');
  }
  function abrirNuevo() {
    fillLibro(null); icons(); euModal.open('m-libro');
    setTimeout(function () { $('lb-titulo').focus(); }, 30);
  }
  function abrirEditar(id) {
    return json(BASE + '/api/libros').then(function (d) {
      var l = (d.libros || []).filter(function (x) { return x.id === id; })[0];
      if (!l) { toast('No se encontró el libro', 'err'); return; }
      fillLibro(l); icons(); euModal.open('m-libro');
    }).catch(function () { toast('Sin conexión', 'err'); });
  }

  $('f-libro').addEventListener('submit', function (e) {
    e.preventDefault();
    var titulo = $('lb-titulo').value.trim();
    if (!titulo) { toast('El título es requerido', 'err'); $('lb-titulo').focus(); return; }
    var id = $('lb-id').value, modo = $('lb-modo').value;
    var body = {
      titulo: titulo,
      autor: $('lb-autor').value.trim(),
      categoria: $('lb-categoria').value,
      estado: $('lb-estado').value,
      paginas_totales: modo === 'pct' ? null : ($('lb-pag-tot').value || null),
      paginas_actuales: modo === 'pct' ? 0 : ($('lb-pag-act').value || 0),
      progreso_pct: modo === 'pct' ? ($('lb-pct').value || 0) : null,
      rating: $('lb-rating').value || null,
      notas: $('lb-notas').value.trim(),
      portada: $('lb-portada').value || null,
    };
    var sub = document.querySelector('[form="f-libro"]'); busy(sub, true);
    json(id ? BASE + '/api/libros/' + id : BASE + '/api/libros', id ? 'PATCH' : 'POST', body).then(function (r) {
      if (r.ok) { toast(id ? 'Libro actualizado ✓' : 'Libro agregado ✓', 'ok'); reload(500); }
      else { toast('Error: ' + (r.error || 'no se pudo guardar'), 'err'); busy(sub, false); }
    }).catch(function () { toast('Sin conexión', 'err'); busy(sub, false); });
  });

  $('lb-delete').addEventListener('click', function () {
    var id = $('lb-id').value;
    if (!id) return;
    euConfirm('¿Eliminar este libro?', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      json(BASE + '/api/libros/' + id, 'DELETE').then(function () { toast('Eliminado'); reload(400); })
        .catch(function () { toast('Sin conexión', 'err'); });
    });
  });

  /* ── Meta anual ─────────────────────────────────────────────────────── */
  $('f-meta').addEventListener('submit', function (e) {
    e.preventDefault();
    json(BASE + '/api/meta', 'POST', { meta: $('meta-input').value || 12 }).then(function (r) {
      if (r.ok) { toast('Meta actualizada ✓', 'ok'); reload(500); } else toast('Error al guardar', 'err');
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Películas ──────────────────────────────────────────────────────── */
  function peFiltered() {
    if (peFilter === 'pendientes') return PELIS.peliculas.filter(function (p) { return !p.vista; });
    if (peFilter === 'vistas') return PELIS.peliculas.filter(function (p) { return p.vista; });
    if (peFilter === 'ranking') return PELIS.ranking;
    return PELIS.peliculas;
  }
  function sub(p) { return esc(p.director || '') + (p.anio ? (p.director ? ' · ' : '') + p.anio : ''); }
  function score(v) { return v != null ? Number(v).toFixed(1) : '—'; }
  /* Una escala (handoff Paideia v2, Sprint 4): en lista y ranking las películas
     se ven en ★ 1–5 como los libros (mi_rating 1–10 ÷ 2). El detalle por
     dimensión sigue en 1–10 dentro de su panel. Sin cambios en la base. */
  function stars5(v) { return v == null ? null : Math.max(1, Math.min(5, Math.round(Number(v) / 2))); }
  function starsHtml(v) {
    var n = stars5(v); if (n == null) return '';
    var h = '';
    for (var i = 1; i <= 5; i++) h += '<i data-lucide="star" class="' + (i <= n ? 'is-on' : '') + '"></i>';
    return '<span class="pd-stars" role="img" aria-label="' + n + ' de 5 estrellas (' + score(v) + '/10)" title="' + score(v) + '/10">' + h + '</span>';
  }
  function rateLbl(v) { return v != null ? stars5(v) + '/5' : 'Calificar'; }

  function ratePanel(p) {
    return DIMS.map(function (d) {
      var val = p['rating_' + d.key], dots = '';
      for (var i = 1; i <= 10; i++) {
        dots += '<button type="button" class="pe-dot' + (val != null && i <= val ? ' is-on' : '') + '" data-dim="' + d.key + '" data-val="' + i + '" aria-label="' + esc(d.label) + ': ' + i + '" aria-pressed="' + (val === i) + '"></button>';
      }
      return '<div class="pe-dim"><div class="eu-between"><span class="t-meta">' + esc(d.label) + '</span><span class="t-data pe-dim-v">' + (val == null ? '—' : val) + '</span></div><div class="pe-dots" role="group" aria-label="' + esc(d.label) + '">' + dots + '</div></div>';
    }).join('') + '<div class="pe-overall t-meta">Tu rating · <b class="t-data">' + score(p.mi_rating) + '</b>/10</div>';
  }

  function renderPelis() {
    var box = $('pe-list'), items = peFiltered();
    box.classList.toggle('pe-grid', peFilter !== 'ranking');
    box.classList.toggle('pe-rank', peFilter === 'ranking');
    if (peFilter === 'ranking') {
      box.innerHTML = items.length ? '<ol class="eu-card eu-card--flush eu-list pe-rank-list">' + items.map(function (p, i) {
        return '<li class="eu-row pe-rank-row"><span class="pe-pos t-data' + (i < 3 ? ' is-top' : '') + '">' + (i + 1) + '</span>' +
          '<span class="eu-grow pe-rank-info"><span class="t-ui">' + esc(p.titulo) + '</span><span class="t-meta">' + sub(p) + '</span></span>' +
          starsHtml(p.mi_rating) + '</li>';
      }).join('') + '</ol>'
        : '<div class="eu-card">' + emptyHtml('trophy', 'Tu ranking está vacío', 'Aún no calificaste ninguna película vista.') + '</div>';
      icons(); return;
    }
    if (!items.length) {
      box.innerHTML = '<div class="pd-span eu-card">' + (PELIS.total
        ? emptyHtml('filter', 'Nada en este filtro', 'No hay películas en esta vista.')
        : emptyHtml('clapperboard', 'Aún no agregas ninguna película', 'Agrega la primera con el botón de arriba.')) + '</div>';
      icons(); return;
    }
    box.innerHTML = items.map(function (p) {
      return '<article class="eu-card pe-card' + (p.vista ? ' is-done' : '') + '" id="pe-row-' + p.id + '">' +
        '<div class="pe-card-main">' +
        (p.portada ? '<img class="pd-cover pe-cover" src="' + esc(p.portada) + '" alt="" loading="lazy">'
          : '<span class="pd-cover pe-cover pd-cover--empty" aria-hidden="true">' + esc((p.titulo[0] || '?').toUpperCase()) + '</span>') +
        '<div class="pd-card-bd">' +
        '<span class="pd-badges"><span class="eu-badge' + (p.vista ? ' eu-badge--success' : '') + '">' + (p.vista ? 'Vista' : 'Pendiente') + '</span>' +
        (p.genero ? '<span class="eu-badge">' + esc(p.genero) + '</span>' : '') + '</span>' +
        '<span class="t-card pd-card-t">' + esc(p.titulo) + '</span><span class="t-meta">' + sub(p) + '</span>' +
        '<span class="pe-stars" id="pe-stars-' + p.id + '">' + starsHtml(p.mi_rating) + '</span>' +
        '<div class="pe-actions">' +
        '<button type="button" class="eu-act-check pe-check" data-act="vista" data-id="' + p.id + '" aria-pressed="' + !!p.vista + '" aria-label="' + (p.vista ? 'Marcar como pendiente' : 'Marcar como vista') + ': ' + esc(p.titulo) + '"><i data-lucide="check"></i></button>' +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm pe-rate' + (p.mi_rating != null ? ' is-rated' : '') + '" data-act="rate" data-id="' + p.id + '" aria-expanded="' + (openRate === p.id) + '" aria-controls="pe-panel-' + p.id + '"' + (p.vista ? '' : ' disabled') + '><i data-lucide="star"></i><span class="num" id="pe-score-' + p.id + '">' + rateLbl(p.mi_rating) + '</span></button>' +
        '<span class="eu-grow"></span>' +
        '<button type="button" class="eu-iconbtn" data-act="del" data-id="' + p.id + '" aria-label="Eliminar ' + esc(p.titulo) + '"><i data-lucide="trash-2"></i></button>' +
        '</div></div></div>' +
        '<div class="pe-panel" id="pe-panel-' + p.id + '"' + (openRate === p.id && p.vista ? '' : ' hidden') + '>' + ratePanel(p) + '</div>' +
        '</article>';
    }).join('');
    icons();
  }
  function emptyHtml(ic, t, txt) {
    return '<div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="' + ic + '"></i></div><div class="t-card">' + t + '</div><p>' + txt + '</p></div>';
  }

  function syncCounters() {
    $('pe-count-n').textContent = PELIS.vistas_n + '/' + PELIS.total;
    var bar = $('pe-bar'); bar.setAttribute('aria-valuenow', PELIS.vistas_n); bar.setAttribute('aria-valuemax', PELIS.total);
    bar.querySelector('i').style.width = (PELIS.total ? PELIS.vistas_n / PELIS.total * 100 : 0) + '%';
    $('pe-f-todos').querySelector('.ct').textContent = PELIS.total;
    $('pe-f-pendientes').querySelector('.ct').textContent = PELIS.total - PELIS.vistas_n;
    $('pe-f-vistas').querySelector('.ct').textContent = PELIS.vistas_n;
  }

  function toggleVista(id) {
    var p = PELIS.peliculas.filter(function (x) { return x.id === id; })[0];
    if (!p) return;
    var now = !p.vista;
    json(BASE + '/api/peliculas/' + id, 'POST', { vista: now }).then(function (d) {
      if (!d.ok) { toast('Error al guardar', 'err'); return; }
      PELIS = d.peliculas;
      if (d.gam && d.gam.xp) toast('+' + d.gam.xp + ' XP · +' + d.gam.ec + ' EC', 'win');
      if (d.gam && window.euGam) euGam(d.gam);
      openRate = now ? id : (openRate === id ? null : openRate);
      syncCounters(); renderPelis();
    }).catch(function () { toast('Sin conexión', 'err'); });
  }
  function toggleRate(id) {
    openRate = openRate === id ? null : id;
    document.querySelectorAll('.pe-panel').forEach(function (el) { el.hidden = el.id !== 'pe-panel-' + openRate; });
    document.querySelectorAll('[data-act="rate"]').forEach(function (b) { b.setAttribute('aria-expanded', String(+b.dataset.id === openRate)); });
  }
  function setPeliRating(id, dim, val) {
    var body = {}; body['rating_' + dim] = val;
    json(BASE + '/api/peliculas/' + id, 'POST', body).then(function (d) {
      if (!d.ok) { toast('Error al guardar', 'err'); return; }
      PELIS = d.peliculas;
      var p = PELIS.peliculas.filter(function (x) { return x.id === id; })[0];
      if (!p) return;
      $('pe-panel-' + id).innerHTML = ratePanel(p);
      $('pe-score-' + id).textContent = rateLbl(p.mi_rating);
      $('pe-stars-' + id).innerHTML = starsHtml(p.mi_rating); icons();
      document.querySelector('[data-act="rate"][data-id="' + id + '"]').classList.toggle('is-rated', p.mi_rating != null);
      var dot = document.querySelector('#pe-panel-' + id + ' [data-dim="' + dim + '"][data-val="' + val + '"]');
      if (dot) dot.focus();
    }).catch(function () { toast('Sin conexión', 'err'); });
  }
  function delPeli(id) {
    var p = PELIS.peliculas.filter(function (x) { return x.id === id; })[0];
    if (!p) return;
    euConfirm('¿Eliminar "' + p.titulo + '"?', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      json(BASE + '/api/peliculas/' + id, 'DELETE').then(function (d) {
        if (!d.ok) { toast('Error al eliminar', 'err'); return; }
        PELIS = d.peliculas; if (openRate === id) openRate = null;
        syncCounters(); renderPelis(); toast('Película eliminada');
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  }
  $('pe-list').addEventListener('click', function (e) {
    var dot = e.target.closest('.pe-dot');
    if (dot) { setPeliRating(+dot.closest('.pe-card').id.replace('pe-row-', ''), dot.dataset.dim, +dot.dataset.val); return; }
    var b = e.target.closest('[data-act]');
    if (!b) return;
    var id = +b.dataset.id;
    if (b.dataset.act === 'vista') toggleVista(id);
    else if (b.dataset.act === 'rate') toggleRate(id);
    else if (b.dataset.act === 'del') delPeli(id);
  });
  document.querySelectorAll('[data-pf]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      peFilter = chip.dataset.pf;
      document.querySelectorAll('[data-pf]').forEach(function (c) { c.setAttribute('aria-pressed', String(c === chip)); });
      renderPelis();
    });
  });

  /* ── Modal película ─────────────────────────────────────────────────── */
  var peSearch = combobox($('pe-titulo'), $('pe-drop'),
    function (q) { return json(BASE + '/api/buscar_pelicula?q=' + encodeURIComponent(q)).then(function (d) { return d.resultados || []; }); },
    function (m) { return optHtml(m.portada, m.titulo, m.anio || ''); },
    function (m) {
      $('pe-titulo').value = m.titulo;
      if (m.anio) $('pe-anio').value = m.anio;
      setCover('pe', m.portada || null);
      // La búsqueda de OMDb no trae director/género: se pide el detalle solo de la elegida.
      if (!m.imdb_id) return;
      json(BASE + '/api/pelicula_detalle?id=' + encodeURIComponent(m.imdb_id)).then(function (det) {
        if (det.director) $('pe-director').value = det.director;
        if (det.genero) $('pe-genero').value = det.genero;
        if (det.portada) setCover('pe', det.portada);
      }).catch(function () {});
    });
  function abrirPeli() {
    ['pe-titulo', 'pe-director', 'pe-anio', 'pe-genero'].forEach(function (k) { $(k).value = ''; });
    setCover('pe', null); peSearch.hide(); icons();
    euModal.open('m-peli'); setTimeout(function () { $('pe-titulo').focus(); }, 30);
  }
  root.querySelector('.js-new-peli').addEventListener('click', abrirPeli);
  $('f-peli').addEventListener('submit', function (e) {
    e.preventDefault();
    var titulo = $('pe-titulo').value.trim();
    if (!titulo) { toast('El título es requerido', 'err'); $('pe-titulo').focus(); return; }
    var btn = document.querySelector('[form="f-peli"]'); busy(btn, true);
    json(BASE + '/api/peliculas', 'POST', {
      titulo: titulo, director: $('pe-director').value.trim(), anio: $('pe-anio').value || null,
      genero: $('pe-genero').value.trim(), portada: $('pe-portada').value || null,
    }).then(function (d) {
      if (!d.ok) { toast('Error: ' + (d.error || 'no se pudo guardar'), 'err'); return; }
      PELIS = d.peliculas; euModal.close('m-peli'); syncCounters(); renderPelis(); toast('Película agregada ✓', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { busy(btn, false); });
  });

  if (location.hash === '#peliculas') setMod('peliculas');
})();
