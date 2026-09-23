/* Salud (Hegemonikon) — Design System V2.
   Episodios (enfermedad/lesión/consulta) → recetas → medicamentos, más
   documentos (recetas o estudios). En móvil el detalle abre a pantalla completa. */
(function () {
  'use strict';
  var root = document.getElementById('sl');
  if (!root) return;
  var BASE = '/bienestar/salud';
  var EPS = JSON.parse(document.getElementById('sl-data').textContent || '[]');
  var TIPO = { enfermedad: ['Enfermedad', 'thermometer', 'danger'], lesion: ['Lesión', 'activity', 'warning'], consulta: ['Consulta', 'stethoscope', 'info'] };
  var active = null;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function today() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function days(a, b) { return Math.max(0, Math.round(((b ? new Date(b) : new Date()) - new Date(a)) / 864e5)); }
  function send(url, method, body) {
    return fetch(url, { method: method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().catch(function () { return { ok: r.ok }; }); }).catch(function () { return { ok: false, error: 'sin conexión' }; });
  }
  function reload(msg) { toast(msg); setTimeout(function () { location.reload(); }, 500); }

  /* ── Filtros ── */
  document.querySelectorAll('[data-filter]').forEach(function (b) {
    b.addEventListener('click', function () {
      var f = b.dataset.filter, n = 0;
      document.querySelectorAll('[data-filter]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      document.querySelectorAll('.js-ep').forEach(function (c) {
        var show = f === 'todos' || (f === 'activos' ? c.dataset.activo === '1' : c.dataset.tipo === f);
        c.hidden = !show; if (show) n++;
      });
      $('sl-none').hidden = n > 0 || !document.querySelectorAll('.js-ep').length;
    });
  });

  /* ── Selección y detalle ── */
  async function select(id, keep) {
    if (active === id && !keep) { close(); return; }
    active = id;
    document.querySelectorAll('.js-ep').forEach(function (c) { c.setAttribute('aria-pressed', String(+c.dataset.id === id)); });
    var ep = EPS.find(function (e) { return e.id === id; }); if (!ep) return;
    $('detail-empty').hidden = true; $('detail-content').hidden = false; euSkel('detail-content', 4, 56);
    $('sl-detail').dataset.open = 'true';
    var res = await Promise.all([fetch(BASE + '/api/episodios/' + id + '/detail').then(function (r) { return r.json(); }),
      fetch(BASE + '/api/episodios/' + id + '/documentos').then(function (r) { return r.json(); })]);
    render(ep, res[0], res[1]);
    $('sl-detail').dataset.open = 'true';
  }
  function close() {
    active = null;
    document.querySelectorAll('.js-ep').forEach(function (c) { c.setAttribute('aria-pressed', 'false'); });
    $('detail-content').hidden = true; $('detail-empty').hidden = false;
    delete $('sl-detail').dataset.open;
  }
  function medHTML(m) {
    var sub = [m.dosis, m.frecuencia, m.duracion_dias ? m.duracion_dias + ' d' : ''].filter(Boolean).join(' · ') || '—';
    return '<li class="sl-med' + (m.tomando ? '' : ' is-off') + '" id="med-' + m.id + '">' +
      '<span class="eu-row-ic sl-med-ic"><i data-lucide="pill"></i></span>' +
      '<span class="sl-med-t"><span class="t-ui">' + esc(m.nombre) + '</span><span class="t-meta">' + esc(sub) + '</span></span>' +
      '<button type="button" class="sl-switch js-med-toggle" role="switch" data-id="' + m.id + '" aria-checked="' + !!m.tomando + '" aria-label="Tomándolo: ' + esc(m.nombre) + '"><span></span></button>' +
      '<button type="button" class="eu-iconbtn sl-danger js-med-del" data-id="' + m.id + '" aria-label="Eliminar ' + esc(m.nombre) + '"><i data-lucide="x"></i></button></li>';
  }
  function render(ep, recetas, docs) {
    var tp = TIPO[ep.tipo] || TIPO.consulta, d = days(ep.fecha_inicio, ep.fecha_fin);
    var html =
      '<div class="sl-d-hd">' +
        '<button type="button" class="eu-iconbtn sl-d-back js-close" aria-label="Volver a la lista"><i data-lucide="chevron-left"></i></button>' +
        '<span class="eu-row-ic sl-ic sl-tone--' + tp[2] + '"><i data-lucide="' + tp[1] + '"></i></span>' +
        '<div class="eu-grow"><h2 class="t-section">' + esc(ep.titulo) + '</h2>' +
          '<div class="sl-badges"><span class="eu-badge eu-badge--status ' + (ep.activo ? 'eu-badge--warning">Activo' : 'eu-badge--success">Resuelto') + '</span><span class="eu-badge">' + tp[0] + '</span>' +
          (ep.zona_cuerpo ? '<span class="t-meta">' + esc(ep.zona_cuerpo) + '</span>' : '') + '</div></div></div>' +
      '<div class="eu-hstack sl-d-meta t-meta"><span>Inicio ' + esc(ep.fecha_inicio) + '</span>' + (ep.fecha_fin ? '<span>Fin ' + esc(ep.fecha_fin) + '</span>' : '') +
        '<span class="fg-brand num">' + d + ' día' + (d !== 1 ? 's' : '') + '</span></div>' +
      (ep.descripcion ? '<p class="t-body fg-2 sl-d-desc">' + esc(ep.descripcion) + '</p>' : '') +
      (ep.activo ? '<div class="eu-card eu-card--inset sl-resolve"><span class="t-ui">¿Ya te recuperaste?</span><button type="button" class="eu-btn eu-btn--secondary eu-btn--sm js-resolve" data-id="' + ep.id + '"><i data-lucide="check"></i>Marcar resuelto</button></div>' : '') +
      '<div class="eu-between sl-sec-hd"><h3 class="t-card">Recetas</h3><button type="button" class="eu-btn eu-btn--ghost eu-btn--sm js-add-rx" data-id="' + ep.id + '"><i data-lucide="plus"></i>Receta</button></div>' +
      (recetas.length ? '<ol class="sl-tl">' + recetas.map(function (r) {
        return '<li class="sl-tl-it"><div class="eu-between sl-tl-hd"><div><div class="t-ui num">' + esc(r.fecha) + '</div>' +
          '<div class="t-meta">' + [r.medico ? 'Dr(a). ' + esc(r.medico) : '', esc(r.especialidad || '')].filter(Boolean).join(' · ') + '</div>' +
          (r.notas ? '<p class="t-meta fg-2 sl-rx-notes">«' + esc(r.notas) + '»</p>' : '') + '</div>' +
          '<div class="eu-hstack sl-gap"><button type="button" class="eu-btn eu-btn--ghost eu-btn--sm js-add-med" data-id="' + r.id + '"><i data-lucide="plus"></i>Med.</button>' +
          '<button type="button" class="eu-iconbtn sl-danger js-del-rx" data-id="' + r.id + '" aria-label="Eliminar receta"><i data-lucide="trash-2"></i></button></div></div>' +
          (r.medicamentos.length ? '<ul class="sl-meds">' + r.medicamentos.map(medHTML).join('') + '</ul>' : '<p class="t-meta">Sin medicamentos.</p>') + '</li>';
      }).join('') + '</ol>' : euEmpty('pill', 'Sin recetas', 'Agrega la receta o el medicamento de este episodio.', true)) +
      '<div class="eu-between sl-sec-hd"><h3 class="t-card">Documentos</h3><button type="button" class="eu-btn eu-btn--ghost eu-btn--sm js-add-doc" data-id="' + ep.id + '"><i data-lucide="upload"></i>Documento</button></div>' +
      (docs && docs.length ? '<div class="eu-list sl-docs">' + docs.map(function (dc) {
        var pdf = dc.nombre_archivo.toLowerCase().slice(-4) === '.pdf', name = dc.nombre_original || dc.nombre_archivo;
        return '<div class="eu-row"><span class="eu-row-ic"><i data-lucide="' + (pdf ? 'file-text' : 'image') + '"></i></span>' +
          '<a class="eu-row-main sl-doc-link" href="' + BASE + '/documentos/' + encodeURIComponent(dc.nombre_archivo) + '" target="_blank" rel="noopener"><span class="eu-row-t">' + esc(name) + '</span><span class="eu-row-s">' + (dc.tipo === 'estudio' ? 'Estudio' : 'Receta') + ' · ' + esc(dc.fecha) + '</span></a>' +
          '<button type="button" class="eu-iconbtn sl-danger js-del-doc" data-id="' + dc.id + '" aria-label="Eliminar ' + esc(name) + '"><i data-lucide="trash-2"></i></button></div>';
      }).join('') + '</div>' : euEmpty('file-text', 'Sin documentos', 'Sube recetas, estudios o notas del episodio.', true)) +
      '<div class="sl-d-ft"><button type="button" class="eu-btn eu-btn--ghost eu-btn--sm sl-danger js-del-ep" data-id="' + ep.id + '"><i data-lucide="trash-2"></i>Eliminar episodio</button></div>';
    $('detail-content').innerHTML = html;
    $('detail-content').hidden = false; $('detail-empty').hidden = true;
    if (window.lucide) lucide.createIcons();
  }

  /* ── Formularios ── */
  function openForm(id, init) { init(); euModal.open(id); }
  function newEp() {
    openForm('m-ep', function () { ['ep-titulo', 'ep-zona', 'ep-desc'].forEach(function (k) { $(k).value = ''; }); $('ep-tipo').value = 'enfermedad'; $('ep-fecha').value = today(); });
  }
  document.querySelectorAll('.js-new-ep').forEach(function (b) { b.addEventListener('click', newEp); });
  var emptyCta = document.querySelector('#ep-list .eu-empty .eu-btn'); if (emptyCta) emptyCta.addEventListener('click', newEp);

  $('f-ep').addEventListener('submit', async function (e) {
    e.preventDefault();
    var titulo = $('ep-titulo').value.trim();
    if (!titulo) { toast('El nombre es requerido', 'err'); $('ep-titulo').focus(); return; }
    var r = await send(BASE + '/api/episodios', 'POST', { tipo: $('ep-tipo').value, titulo: titulo, descripcion: $('ep-desc').value.trim(), zona_cuerpo: $('ep-zona').value.trim(), fecha_inicio: $('ep-fecha').value || today() });
    if (r.ok) reload('Episodio registrado'); else toast('Error: ' + (r.error || 'no se pudo guardar'), 'err');
  });
  $('f-res').addEventListener('submit', async function (e) {
    e.preventDefault();
    var r = await send(BASE + '/api/episodios/' + $('res-ep-id').value, 'PATCH', { activo: 0, fecha_fin: $('res-fecha').value || today() });
    if (r.ok !== false) reload('Episodio resuelto'); else toast('Error', 'err');
  });
  $('f-rx').addEventListener('submit', async function (e) {
    e.preventDefault();
    var r = await send(BASE + '/api/recetas', 'POST', { episodio_id: +$('rx-ep-id').value, medico: $('rx-medico').value.trim(), especialidad: $('rx-esp').value.trim(), fecha: $('rx-fecha').value || today(), notas: $('rx-notas').value.trim() });
    if (!r.ok) { toast('Error', 'err'); return; }
    euModal.close('m-rx'); toast('Receta agregada'); select(active, true);
  });
  $('f-med').addEventListener('submit', async function (e) {
    e.preventDefault();
    var nombre = $('med-nombre').value.trim();
    if (!nombre) { toast('El nombre es requerido', 'err'); $('med-nombre').focus(); return; }
    var r = await send(BASE + '/api/medicamentos', 'POST', { receta_id: +$('med-rx-id').value, nombre: nombre, dosis: $('med-dosis').value.trim(), frecuencia: $('med-freq').value.trim(), duracion_dias: parseInt($('med-dias').value, 10) || null });
    if (!r.ok) { toast('Error', 'err'); return; }
    euModal.close('m-med'); toast('Medicamento agregado'); select(active, true);
  });
  $('f-doc').addEventListener('submit', async function (e) {
    e.preventDefault();
    var f = $('doc-file').files[0];
    if (!f) { toast('Selecciona un archivo', 'err'); return; }
    var fd = new FormData(); fd.append('file', f); fd.append('tipo', $('doc-tipo').value); fd.append('fecha', $('doc-fecha').value || today());
    var r = await fetch(BASE + '/api/episodios/' + $('doc-ep-id').value + '/documentos', { method: 'POST', body: fd }).then(function (x) { return x.json(); }).catch(function () { return {}; });
    if (!r.ok) { toast('Error: ' + (r.error || 'no se pudo subir'), 'err'); return; }
    euModal.close('m-doc'); toast('Documento subido'); select(active, true);
  });

  /* ── Delegación ── */
  root.addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var id = b.dataset.id ? parseInt(b.dataset.id, 10) : null;
    if (b.classList.contains('js-ep')) select(id);
    else if (b.classList.contains('js-close')) close();
    else if (b.classList.contains('js-resolve')) openForm('m-res', function () { $('res-ep-id').value = id; $('res-fecha').value = today(); });
    else if (b.classList.contains('js-add-rx')) openForm('m-rx', function () { $('rx-ep-id').value = id; $('rx-fecha').value = today(); ['rx-medico', 'rx-esp', 'rx-notas'].forEach(function (k) { $(k).value = ''; }); });
    else if (b.classList.contains('js-add-med')) openForm('m-med', function () { $('med-rx-id').value = id; ['med-nombre', 'med-dosis', 'med-freq', 'med-dias'].forEach(function (k) { $(k).value = ''; }); });
    else if (b.classList.contains('js-add-doc')) openForm('m-doc', function () { $('doc-ep-id').value = id; $('doc-tipo').value = 'receta'; $('doc-fecha').value = today(); $('doc-file').value = ''; });
    else if (b.classList.contains('js-del-ep')) {
      if (!(await euConfirm('¿Eliminar este episodio con sus recetas y documentos?', { confirmLabel: 'Eliminar' }))) return;
      await send(BASE + '/api/episodios/' + id, 'DELETE'); reload('Episodio eliminado');
    } else if (b.classList.contains('js-del-rx')) {
      if (!(await euConfirm('¿Eliminar esta receta y sus medicamentos?', { confirmLabel: 'Eliminar' }))) return;
      await send(BASE + '/api/recetas/' + id, 'DELETE'); toast('Receta eliminada'); select(active, true);
    } else if (b.classList.contains('js-del-doc')) {
      if (!(await euConfirm('¿Eliminar este documento?', { confirmLabel: 'Eliminar' }))) return;
      await send(BASE + '/api/documentos/' + id, 'DELETE'); toast('Documento eliminado'); select(active, true);
    } else if (b.classList.contains('js-med-del')) {
      await send(BASE + '/api/medicamentos/' + id, 'DELETE'); var li = $('med-' + id); if (li) li.remove(); toast('Medicamento eliminado');
    } else if (b.classList.contains('js-med-toggle')) {
      var on = b.getAttribute('aria-checked') !== 'true';
      b.setAttribute('aria-checked', String(on)); b.closest('.sl-med').classList.toggle('is-off', !on);
      var r = await send(BASE + '/api/medicamentos/' + id, 'PATCH', { tomando: on ? 1 : 0 });
      if (r.ok === false) { b.setAttribute('aria-checked', String(!on)); b.closest('.sl-med').classList.toggle('is-off', on); toast('Error', 'err'); return; }
      toast(on ? 'Lo estás tomando' : 'Marcado como terminado');
    }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && $('sl-detail').dataset.open && !document.querySelector('.eu-scrim:not([hidden])')) close(); });

  /* Abre solo el episodio activo si es el único */
  var act = EPS.filter(function (e) { return e.activo; });
  if (act.length === 1 && window.matchMedia('(min-width:1024px)').matches) select(act[0].id);
})();
