/* Hegemonikon (/bienestar/) — handoff Hegemonikon v2.
   Sin recargar: «Marcar resuelto» (PATCH activo=0, con Deshacer 10 s),
   «Terminé» / Deshacer de medicamentos (PATCH tomando), ocultar la alerta
   de recurrencia 30 días y «+ Episodio» con el modal m-ep de Salud. Tras
   cada acción se vuelven a pedir «Hoy en tu cuerpo» y «En tratamiento». */
(function () {
  'use strict';
  var root = document.getElementById('hg');
  if (!root) return;
  var SALUD = '/bienestar/salud';
  function $(id) { return document.getElementById(id); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function today() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function send(url, method, body) {
    return fetch(url, { method: method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok && d.ok === undefined) d.ok = false; return d; }); })
      .catch(function () { return { ok: false, error: 'sin conexión' }; });
  }

  /* Vuelve a pedir la página y reemplaza las secciones con estado */
  function refresh(keep) {
    return fetch(location.pathname).then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      ['hg-hoy', 'hg-body', 'hg-match'].concat(keep ? [] : ['hg-trat']).forEach(function (id) {
        var a = $(id), b = doc.getElementById(id);
        if (a && b) a.replaceWith(b);
      });
      icons();
    });
  }

  /* ── Marcar resuelto (con Deshacer 10 s) ── */
  var undoTimer = null, resolvedId = null;
  root.addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var trat = $('hg-trat');

    if (b.classList.contains('js-resolve')) {
      var id = trat.dataset.id;
      b.setAttribute('aria-busy', 'true');
      var r = await send(SALUD + '/api/episodios/' + id, 'PATCH', { activo: 0, fecha_fin: today() });
      b.removeAttribute('aria-busy');
      if (r.ok === false) { toast('No se pudo resolver', 'err'); return; }
      resolvedId = id;
      var titulo = trat.querySelector('.hg-ep-t').firstChild.textContent.trim();
      var msg = titulo + ' resuelto' + (r.dias != null ? ' en ' + r.dias + ' día' + (r.dias === 1 ? '' : 's') : '');
      if (r.vs_promedio != null && r.vs_promedio !== 0) {
        var n = Math.abs(Math.round(r.vs_promedio));
        msg += ', ' + n + (r.vs_promedio < 0 ? ' menos' : ' más') + ' que tu promedio';
      }
      trat.querySelectorAll('.hg-ep,.hg-med,.hg-trat-ft').forEach(function (el) { el.hidden = true; });
      trat.classList.remove('is-open'); trat.classList.add('is-clear');
      var cl = trat.querySelector('.js-clear');
      cl.hidden = false; cl.querySelector('.js-clear-t').textContent = 'Nada en tratamiento. ' + msg + '.';
      cl.querySelector('.js-reopen').hidden = false;
      clearTimeout(undoTimer);
      undoTimer = setTimeout(function () { cl.querySelector('.js-reopen').hidden = true; resolvedId = null; refresh(); }, 10000);
      refresh(true);
      return;
    }
    if (b.classList.contains('js-reopen')) {
      if (!resolvedId) return;
      clearTimeout(undoTimer);
      await send(SALUD + '/api/episodios/' + resolvedId, 'PATCH', { activo: 1, fecha_fin: null });
      resolvedId = null;
      toast('Episodio reabierto');
      refresh();
      return;
    }

    /* ── Terminé / Deshacer de un medicamento ── */
    var med = b.closest('[data-med]');
    if (med && (b.classList.contains('js-med-stop') || b.classList.contains('js-med-undo'))) {
      var on = b.classList.contains('js-med-undo');
      b.setAttribute('aria-busy', 'true');
      var rr = await send(SALUD + '/api/medicamentos/' + med.dataset.med, 'PATCH', { tomando: on ? 1 : 0 });
      b.removeAttribute('aria-busy');
      if (rr.ok === false) { toast('Error', 'err'); return; }
      toast(on ? 'Lo sigues tomando' : 'Medicamento terminado');
      refresh();
      return;
    }

    /* ── Ocultar la alerta de recurrencia 30 días ── */
    if (b.classList.contains('js-alert-hide')) {
      var al = $('hg-alert');
      var ra = await send('/bienestar/api/alerta/ocultar', 'POST', { titulo: al.dataset.titulo });
      if (ra.ok === false) { toast('No se pudo ocultar', 'err'); return; }
      al.hidden = true;
      toast('Alerta oculta 30 días');
    }
  });

  /* ── + Episodio (modal m-ep de Salud) ── */
  document.querySelectorAll('.js-new-ep').forEach(function (b) {
    b.addEventListener('click', function () {
      ['ep-titulo', 'ep-zona', 'ep-desc'].forEach(function (k) { $(k).value = ''; });
      $('ep-tipo').value = 'enfermedad'; $('ep-fecha').value = today();
      euModal.open('m-ep');
    });
  });
  var fep = $('f-ep');
  if (fep) fep.addEventListener('submit', async function (e) {
    e.preventDefault();
    var titulo = $('ep-titulo').value.trim();
    if (!titulo) { toast('El nombre es requerido', 'err'); $('ep-titulo').focus(); return; }
    var r = await send(SALUD + '/api/episodios', 'POST', { tipo: $('ep-tipo').value, titulo: titulo, descripcion: $('ep-desc').value.trim(), zona_cuerpo: $('ep-zona').value.trim(), fecha_inicio: $('ep-fecha').value || today() });
    if (!r.ok) { toast('Error: ' + (r.error || 'no se pudo guardar'), 'err'); return; }
    euModal.close('m-ep');
    toast('Episodio registrado');
    refresh();
  });
})();
