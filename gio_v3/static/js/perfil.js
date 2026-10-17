/* Perfil «Tú» — Design System V2 · pantalla 10
   Navegación por hash entre secciones, edición en línea de datos y medidas,
   documentos, recordatorios, contraseñas, tallas, plicómetro y ajustes. */
(function () {
  'use strict';
  var root = document.getElementById('pf');
  if (!root) return;

  var data = JSON.parse(document.getElementById('pf-data').textContent || '{}');
  var PH = '— editar —';
  var rv = data.rv || {}, priv = data.priv || {}, mv = data.mv || {};
  var vaultCache = {};
  var MAX_MB = 10;  /* MAX_CONTENT_LENGTH de app.py */
  var desk = window.matchMedia('(min-width:1024px)');

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons(el) { if (window.lucide) lucide.createIcons(el ? { nodes: [el] } : undefined); }
  function setIcon(btn, name) {
    var old = btn.querySelector('svg,i');
    var i = document.createElement('i');
    i.setAttribute('data-lucide', name);
    if (old) old.replaceWith(i); else btn.prepend(i);
    icons(i);
  }
  function copy(text) {
    if (!text) { toast('Nada que copiar', 'err'); return; }
    navigator.clipboard.writeText(text).then(function () { toast('Copiado'); },
      function () { toast('No se pudo copiar', 'err'); });
  }
  async function post(url, body) {
    var opts = { method: 'POST' };
    if (body instanceof FormData) opts.body = body;
    else if (body !== undefined) { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
    var r = await fetch(url, opts);
    if (r.status === 401 || r.status === 403) {
      toast('Sesión expirada — recargando…', 'err');
      setTimeout(function () { location.reload(); }, 1200);
      return { ok: false, expired: true };
    }
    return r.json().catch(function () { return { ok: false }; });
  }
  function fail(j, msg) { if (!j.expired) toast((msg || 'Error') + (j.error ? ': ' + j.error : ''), 'err'); }

  /* ── Navegación por secciones ─────────────────────────────── */
  var SECS = Array.prototype.map.call(document.querySelectorAll('[data-sec-panel]'), function (s) { return s.dataset.secPanel; });
  function show(sec) {
    if (SECS.indexOf(sec) < 0) sec = desk.matches ? 'datos' : '';
    root.dataset.sec = sec;
    document.querySelectorAll('[data-sec-panel]').forEach(function (p) { p.hidden = p.dataset.secPanel !== sec; });
    document.querySelectorAll('.pf-subnav [data-sec-link]').forEach(function (a) {
      if (a.dataset.secLink === sec) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
  }
  var navigated = false;  /* ¿se abrió la sección desde esta misma página? */
  function route() { show(location.hash.slice(1)); }
  window.addEventListener('hashchange', function () { navigated = true; route(); window.scrollTo(0, 0); });
  desk.addEventListener('change', route);
  route();

  /* Móvil: con una sección abierta, el «volver» de la topbar regresa al hub */
  var tbBack = document.querySelector('.eu-tb-back');
  if (tbBack) tbBack.addEventListener('click', function (e) {
    if (desk.matches || !root.dataset.sec) return;
    e.preventDefault();
    if (navigated) history.back();
    else { history.replaceState(null, '', location.pathname); route(); window.scrollTo(0, 0); }
  });

  /* ── Tema ─────────────────────────────────────────────────── */
  function syncTheme() {
    var t = localStorage.getItem('eu-theme') || 'dark';
    document.querySelectorAll('[data-theme-set]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.themeSet === t));
    });
  }
  document.querySelectorAll('[data-theme-set]').forEach(function (b) {
    b.addEventListener('click', function () {
      try { localStorage.setItem('eu-theme', b.dataset.themeSet); } catch (_) {}
      _applyTheme(b.dataset.themeSet);
      syncTheme();
    });
  });
  syncTheme();

  /* ── Datos personales ─────────────────────────────────────── */
  function renderVal(k, reveal) {
    var el = $('val-' + k), v = rv[k], empty = !v || v === PH;
    el.classList.toggle('is-empty', empty);
    el.classList.toggle('is-priv', !!priv[k] && !reveal && !empty);
    el.textContent = empty ? 'Sin capturar' : (priv[k] && !reveal ? '••••••••' : v);
    el.dataset.showing = reveal ? '1' : '0';
  }
  function editOpen(k) {
    $('vrow-' + k).hidden = true;
    $('erow-' + k).hidden = false;
    $('einp-' + k).focus();
  }
  function editClose(k) {
    $('vrow-' + k).hidden = false;
    $('erow-' + k).hidden = true;
  }

  /* Panel de documentos por campo: solo uno abierto a la vez */
  var openPanel = null;
  function togglePanel(k) {
    var p = $('fdp-' + k);
    if (!p) return;
    if (openPanel && openPanel !== k) {
      $('fdp-' + openPanel).hidden = true;
      $('attachbtn-' + openPanel).setAttribute('aria-expanded', 'false');
    }
    p.hidden = !p.hidden;
    $('attachbtn-' + k).setAttribute('aria-expanded', String(!p.hidden));
    openPanel = p.hidden ? null : k;
  }
  function attachCount(k, delta) {
    var btn = $('attachbtn-' + k);
    if (!btn) return;
    var badge = $('badge-' + k);
    var n = (badge ? parseInt(badge.textContent, 10) || 0 : 0) + delta;
    if (n > 0) {
      if (!badge) { badge = document.createElement('span'); badge.className = 'pf-attach-n'; badge.id = 'badge-' + k; btn.appendChild(badge); }
      badge.textContent = n;
    } else if (badge) badge.remove();
    btn.classList.toggle('has-docs', n > 0);
    var emptyEl = $('fdp-empty-' + k);
    if (emptyEl) emptyEl.hidden = n > 0;
  }

  root.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b) return;
    var k = b.dataset.key;
    if (b.classList.contains('js-vis')) {
      var showing = $('val-' + k).dataset.showing === '1';
      renderVal(k, !showing);
      setIcon(b, showing ? 'eye' : 'eye-off');
    } else if (b.classList.contains('js-copy')) copy(rv[k] === PH ? '' : rv[k]);
    else if (b.classList.contains('js-edit')) editOpen(k);
    else if (b.classList.contains('js-cancel')) editClose(k);
    else if (b.classList.contains('js-attach')) togglePanel(k);
    else if (b.classList.contains('js-mcopy')) copy(mv[k] === PH ? '' : mv[k]);
    else if (b.classList.contains('js-medit')) mOpen(k);
    else if (b.classList.contains('js-mcancel')) mClose(k);
  });

  document.querySelectorAll('.js-edit-form').forEach(function (f) {
    var k = f.dataset.key;
    f.addEventListener('keydown', function (e) { if (e.key === 'Escape') editClose(k); });
    f.addEventListener('submit', async function (e) {
      e.preventDefault();
      var val = $('einp-' + k).value.trim();
      if (!val) { toast('Escribe un valor', 'err'); return; }
      var j = await post('/perfil/api/update', { key: k, value: val });
      if (!j.ok) { fail(j, 'Error al guardar'); return; }
      rv[k] = val;
      renderVal(k, false);
      var eye = $('eyebtn-' + k);
      if (eye) setIcon(eye, 'eye');
      editClose(k);
      toast('Guardado');
    });
  });

  /* ── Medidas ──────────────────────────────────────────────── */
  function mOpen(k) { $('mvrow-' + k).hidden = true; $('merow-' + k).hidden = false; $('meinp-' + k).focus(); }
  function mClose(k) { $('mvrow-' + k).hidden = false; $('merow-' + k).hidden = true; }
  function diff(a, b) {
    var x = parseFloat(a), y = parseFloat(b);
    if (isNaN(x) || isNaN(y) || !x || !y) return null;
    return Math.round((x - y) * 10) / 10;
  }
  function deltaHtml(d) {
    if (d === null) return '<span class="t-meta">—</span>';
    return '<span class="eu-badge pf-delta' + (d > 0 ? ' is-up' : d < 0 ? ' is-down' : '') + '">' + (d > 0 ? '+' + d : d < 0 ? d : '=') + '</span>';
  }

  document.querySelectorAll('.js-medit-form').forEach(function (f) {
    var k = f.dataset.key;
    f.addEventListener('keydown', function (e) { if (e.key === 'Escape') mClose(k); });
    f.addEventListener('submit', async function (e) {
      e.preventDefault();
      var val = $('meinp-' + k).value.trim();
      if (!val) { toast('Escribe un valor', 'err'); return; }
      var prev = mv[k];
      var j = await post('/perfil/api/update_measurement', { key: k, value: val });
      if (!j.ok) { fail(j, 'Error al guardar'); return; }
      mv[k] = val;
      var valEl = $('mval-' + k);
      valEl.textContent = val;
      valEl.parentElement.classList.remove('is-empty');
      var d = diff(val, prev), badge = $('mdelta-' + k);
      if (badge) {
        badge.hidden = d === null;
        if (d !== null) {
          badge.classList.toggle('is-up', d > 0);
          badge.classList.toggle('is-down', d < 0);
          badge.textContent = d > 0 ? '+' + d : d < 0 ? d : '=';
        }
      }
      var h = j.history || [];
      if (h.length) {
        $('mhist-' + k).innerHTML = h.map(function (en, i) {
          var nx = h[i + 1];
          return '<div class="eu-between pf-hist-row"><span class="t-meta">' + esc(en.date) + '</span><span class="num">' +
            esc(en.value) + '</span>' + deltaHtml(nx ? diff(en.value, nx.value) : null) + '</div>';
        }).join('');
        $('mhistbtn-' + k).textContent = 'Historial (' + h.length + ')';
        $('mhistwrap-' + k).hidden = false;
      }
      mClose(k);
      toast('Guardado');
    });
  });

  /* ── Documentos ───────────────────────────────────────────── */
  function docRow(doc, field) {
    var ext = (doc.original.split('.').pop() || '').toLowerCase();
    var url = '/perfil/docs/' + encodeURIComponent(doc.filename);
    var ic = ['jpg', 'jpeg', 'png', 'webp'].indexOf(ext) >= 0
      ? '<img class="pf-thumb" src="' + url + '" alt="" loading="lazy">'
      : '<div class="eu-row-ic' + (ext === 'pdf' ? ' pf-ic-pdf' : '') + '"><i data-lucide="' +
        (ext === 'pdf' ? 'file-text' : ['xls', 'xlsx'].indexOf(ext) >= 0 ? 'table' : ext === 'zip' ? 'archive' : 'file') + '"></i></div>';
    var el = document.createElement('div');
    el.className = 'eu-row pf-doc';
    el.id = (field ? 'fdprow-' : 'docrow-') + doc.id;
    el.innerHTML = ic +
      '<div class="eu-row-main"><a class="eu-row-t pf-doc-name" href="' + url + '" target="_blank" rel="noopener">' + esc(doc.original) + '</a>' +
      '<div class="eu-row-s">' + esc((doc.uploaded_at || '').slice(0, 10)) + '</div></div>' +
      '<a class="eu-iconbtn" href="' + url + '" target="_blank" rel="noopener" aria-label="Abrir ' + esc(doc.original) + '"><i data-lucide="external-link"></i></a>' +
      '<button type="button" class="eu-iconbtn pf-danger js-doc-del" data-id="' + doc.id + '"' + (field ? ' data-field="' + esc(field) + '"' : '') +
      ' aria-label="Eliminar ' + esc(doc.original) + '"><i data-lucide="trash-2"></i></button>';
    return el;
  }
  function docsEmpty() {
    var e = document.querySelector('.js-docs-empty');
    if (e) e.hidden = !!$('docsList').children.length;
  }

  document.querySelectorAll('.js-upload').forEach(function (inp) {
    inp.addEventListener('change', async function () {
      var field = inp.dataset.field || '';
      var files = Array.prototype.slice.call(inp.files);
      for (var i = 0; i < files.length; i++) {
        var f = files[i];
        if (f.size > MAX_MB * 1024 * 1024) { toast(f.name + ' supera ' + MAX_MB + ' MB', 'err'); continue; }
        var fd = new FormData();
        fd.append('file', f);
        if (field) fd.append('field_key', field);
        var j = await post('/perfil/api/upload_doc', fd);
        if (!j.ok) { fail(j, 'No se pudo subir ' + f.name); continue; }
        var row = docRow(j, field);
        if (field) { $('fdp-list-' + field).appendChild(row); attachCount(field, 1); }
        else { $('docsList').prepend(row); docsEmpty(); }
        icons(row);
        toast(field ? 'Adjuntado' : 'Subido');
      }
      inp.value = '';
    });
  });

  /* ── Delegación: borrar y acciones de listas ─────────────── */
  root.addEventListener('click', async function (e) {
    var b = e.target.closest('button');
    if (!b) return;
    var row = b.closest('[data-id]');
    var id = b.dataset.id || (row && row.dataset.id);
    var j;

    if (b.classList.contains('js-doc-del')) {
      if (!(await euConfirm('¿Eliminar este documento?', { danger: true, confirmLabel: 'Eliminar' }))) return;
      j = await post('/perfil/api/delete_doc', { id: parseInt(id, 10) });
      if (!j.ok) { fail(j, 'No se pudo eliminar'); return; }
      var f = b.dataset.field;
      var el = $((f ? 'fdprow-' : 'docrow-') + id);
      if (el) el.remove();
      if (f) attachCount(f, -1); else docsEmpty();
      toast('Eliminado');
    }

    /* Recordatorios */
    else if (b.classList.contains('js-rem-new')) remForm(null);
    else if (b.classList.contains('js-rem-edit')) remForm(row);
    else if (b.classList.contains('js-rem-done')) {
      row.classList.add('is-busy');
      j = await post('/perfil/api/reminder/' + id + '/done');
      if (!j.ok) { row.classList.remove('is-busy'); fail(j, 'Error al actualizar'); return; }
      if (row.dataset.type === 'unico') {
        remRemove(row);
        toast('Hecho');
      } else location.reload();
    } else if (b.classList.contains('js-rem-del')) {
      /* Borrar vive dentro del formulario de edición, no en cada fila */
      var rid = $('remEditId').value, rrow = $('remrow-' + rid);
      if (!rid || !(await euConfirm('¿Eliminar «' + (rrow ? rrow.dataset.desc : 'este recordatorio') + '»?', { danger: true, confirmLabel: 'Eliminar' }))) return;
      j = await post('/perfil/api/reminder/' + rid + '/delete');
      if (!j.ok) { fail(j, 'No se pudo eliminar'); return; }
      $('remForm').hidden = true;
      if (rrow) remRemove(rrow);
      toast('Eliminado');
    } else if (b.classList.contains('js-rem-tema')) {
      remFiltro(b.dataset.tema);
    } else if (b.classList.contains('js-rem-snooze')) {
      snoozeOpen(row, b);
    } else if (b.classList.contains('js-snooze-opt')) {
      snoozeTo({ dias: parseInt(b.dataset.dias, 10) });
    }

    /* Contraseñas */
    else if (b.classList.contains('js-vault-new')) vaultForm(null);
    else if (b.classList.contains('js-vault-edit')) vaultForm(row);
    else if (b.classList.contains('js-vault-reveal')) {
      var span = $('vaultpass-' + id);
      if (span.dataset.showing === '1') {
        span.textContent = '••••••••'; span.dataset.showing = '0'; setIcon(b, 'eye'); return;
      }
      var pw = await reveal(id);
      if (pw == null) return;
      span.textContent = pw; span.dataset.showing = '1'; setIcon(b, 'eye-off');
    } else if (b.classList.contains('js-vault-copy')) {
      var p2 = await reveal(id);
      if (p2 != null) copy(p2);
    } else if (b.classList.contains('js-vault-del')) {
      if (!(await euConfirm('¿Eliminar la contraseña de «' + row.dataset.servicio + '»?', { danger: true, confirmLabel: 'Eliminar' }))) return;
      j = await post('/perfil/api/vault/' + id + '/delete');
      if (!j.ok) { fail(j, 'No se pudo eliminar'); return; }
      row.remove();
      delete vaultCache[id];
      listEmpty('vaultList', '.js-vault-empty');
      toast('Eliminada');
    }

    /* Tallas y plicómetro */
    else if (b.classList.contains('js-talla-new')) openForm('tallaForm', 'tallaMarca');
    else if (b.classList.contains('js-talla-del')) {
      if (!(await euConfirm('¿Eliminar esta talla?', { danger: true, confirmLabel: 'Eliminar' }))) return;
      j = await post('/perfil/api/talla/' + id + '/delete');
      if (j.ok) location.reload(); else fail(j, 'No se pudo eliminar');
    } else if (b.classList.contains('js-plg-new')) {
      var fr = $('plgForm');
      if (fr.hidden) { fr.reset(); $('plgFecha').value = new Date().toISOString().slice(0, 10); }
      openForm('plgForm', 'plgMm');
    } else if (b.classList.contains('js-plg-del')) {
      if (!(await euConfirm('¿Eliminar esta lectura?', { danger: true, confirmLabel: 'Eliminar' }))) return;
      j = await post('/perfil/api/pliegue/' + id + '/delete');
      if (!j.ok) { fail(j, 'No se pudo eliminar'); return; }
      var pr = $('plgrow-' + id);
      if (pr) pr.remove();
      listEmpty('plgList', '.js-plg-empty');
      toast('Eliminada');
    }

    else if (b.classList.contains('js-form-close')) b.closest('form').hidden = true;
  });

  function listEmpty(listId, emptySel) {
    var e = document.querySelector(emptySel);
    if (e) e.hidden = !!$(listId).children.length;
  }
  function openForm(id, focusId) {
    var f = $(id);
    f.hidden = false;
    f.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    $(focusId).focus();
  }
  document.querySelectorAll('.pf-form').forEach(function (f) {
    f.addEventListener('keydown', function (e) { if (e.key === 'Escape') f.hidden = true; });
  });

  /* Recordatorios */
  /* Quita una fila y actualiza el contador de su grupo (o el grupo entero) */
  function remRemove(row) {
    var g = row.closest('details');
    row.remove();
    if (g && !g.querySelector('.pf-rem')) g.remove();
    listEmpty('remindersList', '.js-rem-empty');
    remFiltro(remTema);
  }

  /* Chips de tema: ocultan filas de otros temas y los grupos que quedan
     vacíos; los contadores de grupo cuentan solo lo visible. */
  var remTema = '';
  try { remTema = localStorage.getItem('eu.rem.tema') || ''; } catch (e) {}
  function remFiltro(tema) {
    var chips = document.querySelectorAll('.js-rem-tema');
    if (!chips.length) tema = '';
    else if (tema && !document.querySelector('.js-rem-tema[data-tema="' + tema + '"]')) tema = '';
    remTema = tema;
    try { localStorage.setItem('eu.rem.tema', tema); } catch (e) {}
    chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.tema === tema)); });
    var visibles = 0;
    document.querySelectorAll('#remindersList details').forEach(function (g) {
      var n = 0;
      g.querySelectorAll('.pf-rem').forEach(function (r) {
        var ok = !tema || r.dataset.tema === tema;
        r.hidden = !ok; if (ok) n++;
      });
      g.hidden = !n; visibles += n;
      var ct = g.querySelector('.js-remg-ct'); if (ct) ct.textContent = n;
    });
    var list = $('remindersList'); if (list) list.classList.toggle('is-filtered', !!tema);
    var none = document.querySelector('.js-rem-none');
    if (none) none.hidden = !(tema && !visibles);
    if (snoozeRow && snoozeRow.hidden) snoozeClose();
  }
  remFiltro(remTema);

  /* Posponer: menú bajo la fila con Mañana / 3 días / +1 semana / fecha */
  var snoozeRow = null, snoozeBtn = null;
  function snoozeClose() {
    $('remSnooze').hidden = true;
    if (snoozeBtn) snoozeBtn.setAttribute('aria-expanded', 'false');
    snoozeRow = snoozeBtn = null;
  }
  function snoozeOpen(row, btn) {
    var m = $('remSnooze');
    if (snoozeRow === row) { snoozeClose(); return; }
    snoozeClose();
    snoozeRow = row; snoozeBtn = btn;
    row.after(m);
    m.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    m.querySelector('button').focus();
  }
  async function snoozeTo(body) {
    if (!snoozeRow) return;
    var j = await post('/perfil/api/reminder/' + snoozeRow.dataset.id + '/snooze', body);
    if (!j.ok) { fail(j, 'No se pudo posponer'); return; }
    location.hash = 'recordatorios'; location.reload();
  }
  document.querySelector('.js-snooze-date').addEventListener('change', function () {
    if (this.value) snoozeTo({ fecha: this.value });
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && snoozeRow) { var b = snoozeBtn; snoozeClose(); b.focus(); } });

  function remTypeSync() { $('remFreqRow').hidden = $('remType').value !== 'periodico'; }
  $('remType').addEventListener('change', remTypeSync);
  function remForm(row) {
    var d = row ? row.dataset : {};
    $('remEditId').value = row ? d.id : '';
    $('remFormLabel').textContent = row ? 'Editar recordatorio' : 'Nuevo recordatorio';
    $('remSaveBtn').textContent = row ? 'Actualizar' : 'Guardar';
    $('remDelBtn').hidden = !row;
    $('remDesc').value = d.desc || '';
    $('remType').value = d.type || 'unico';
    $('remDate').value = d.date || '';
    $('remFreqVal').value = d.freqval || 1;
    $('remFreqUnit').value = d.frequnit || 'dias';
    $('remTema').value = d.tema || '';
    remTypeSync();
    openForm('remForm', 'remDesc');
  }
  $('remForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var desc = $('remDesc').value.trim();
    if (!desc) { toast('Escribe una descripción', 'err'); return; }
    var type = $('remType').value, date = $('remDate').value, editId = $('remEditId').value;
    var payload = { description: desc, type: type, target_date: date || null, tema: $('remTema').value };
    if (type === 'periodico') {
      payload.freq_value = parseInt($('remFreqVal').value, 10) || 1;
      payload.freq_unit = $('remFreqUnit').value;
      payload.next_date = date || null;
    }
    var j = await post(editId ? '/perfil/api/reminder/' + editId + '/edit' : '/perfil/api/reminder/add', payload);
    if (j.ok) { location.hash = 'recordatorios'; location.reload(); } else fail(j, 'Error');
  });

  /* Contraseñas */
  async function reveal(id) {
    if (vaultCache[id] != null) return vaultCache[id];
    var j = await post('/perfil/api/vault/' + id + '/reveal');
    if (!j.ok) { fail(j, 'No se pudo descifrar'); return null; }
    vaultCache[id] = j.password;
    return j.password;
  }
  function vaultForm(row) {
    var d = row ? row.dataset : {};
    $('vaultEditId').value = row ? d.id : '';
    $('vaultFormLabel').textContent = row ? 'Editar contraseña' : 'Nueva contraseña';
    $('vaultSaveBtn').textContent = row ? 'Actualizar' : 'Guardar';
    $('vaultServicio').value = d.servicio || '';
    $('vaultUsuario').value = d.usuario || '';
    $('vaultUrl').value = d.url || '';
    $('vaultNotas').value = d.notas || '';
    $('vaultPassword').value = '';
    $('vaultPassword').placeholder = row ? 'Déjala vacía para no cambiarla' : '';
    openForm('vaultForm', 'vaultServicio');
  }
  $('vaultForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var servicio = $('vaultServicio').value.trim();
    if (!servicio) { toast('Escribe el nombre del servicio', 'err'); return; }
    var editId = $('vaultEditId').value, password = $('vaultPassword').value;
    if (!editId && !password) { toast('Escribe una contraseña', 'err'); return; }
    var payload = { servicio: servicio, usuario: $('vaultUsuario').value.trim(), url: $('vaultUrl').value.trim(), notas: $('vaultNotas').value.trim() };
    if (password) payload.password = password;
    var j = await post(editId ? '/perfil/api/vault/' + editId + '/edit' : '/perfil/api/vault/add', payload);
    if (j.ok) location.reload(); else fail(j, 'Error');
  });

  /* Tallas */
  $('tallaForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var marca = $('tallaMarca').value.trim(), talla = $('tallaTalla').value.trim();
    if (!marca || !talla) { toast('Escribe la marca y la talla', 'err'); return; }
    var j = await post('/perfil/api/talla/add', { prenda: $('tallaPrenda').value, marca: marca, talla: talla, notas: $('tallaNotas').value.trim() });
    if (j.ok) location.reload(); else fail(j, 'Error');
  });

  /* Plicómetro */
  $('plgForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var mm = $('plgMm').value, pct = $('plgPct').value;
    if (!mm || !pct) { toast('Escribe la lectura en mm y el % de grasa', 'err'); return; }
    var j = await post('/perfil/api/pliegue/add', {
      fecha: $('plgFecha').value, mm: parseFloat(mm), porcentaje: parseFloat(pct),
      categoria: $('plgCategoria').value.trim(), notas: $('plgNotas').value.trim()
    });
    if (j.ok) location.reload(); else fail(j, 'Error');
  });

  /* ── Reset de gamificación ────────────────────────────────── */
  var rInp = $('reset-confirm'), rBtn = $('reset-confirm-btn');
  $('reset-trigger').addEventListener('click', function () {
    rInp.value = ''; rBtn.disabled = true; rBtn.textContent = 'Borrar todo';
    euModal.open('reset-modal');
    setTimeout(function () { rInp.focus(); }, 50);
  });
  rInp.addEventListener('input', function () { rBtn.disabled = rInp.value.trim() !== 'RESET'; });
  rBtn.addEventListener('click', async function () {
    rBtn.disabled = true; rBtn.textContent = 'Borrando…';
    try {
      var r = await fetch('/api/gamification/reset', { method: 'POST' });
      if (!r.ok) throw new Error();
      euModal.close('reset-modal');
      toast('Reset completo — empiezas desde cero', 'win');
      setTimeout(function () { location.href = '/'; }, 800);
    } catch (_) {
      toast('Error al resetear', 'err');
      rBtn.disabled = false; rBtn.textContent = 'Borrar todo';
    }
  });
})();
