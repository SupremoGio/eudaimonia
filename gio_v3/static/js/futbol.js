/* Fútbol (Hegemonikon) — Design System V2.
   Paso 1: programar (fecha/hora/cancha/rival). Paso 2: registrar resultado
   (marcador, goles, asistencias, minutos, rating) → liquida XP en el backend. */
(function () {
  'use strict';
  var BASE = '/bienestar/futbol';
  function $(id) { return document.getElementById(id); }
  function today() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  var F = ['pt-id', 'pt-cancha', 'pt-rival', 'pt-gf', 'pt-gc', 'pt-goles', 'pt-asist', 'pt-min', 'pt-rating', 'pt-hora'];

  function openForm(title, save, withResult) {
    $('m-pt-t').textContent = title; $('pt-save').textContent = save;
    $('pt-result').hidden = !withResult;
    euModal.open('m-pt');
  }
  function fill(p) {
    var map = { 'pt-id': p.id, 'pt-fecha': p.fecha, 'pt-hora': p.hora, 'pt-cancha': p.cancha, 'pt-rival': p.rival, 'pt-gf': p.goles_favor,
      'pt-gc': p.goles_contra, 'pt-goles': p.goles_propios, 'pt-asist': p.asistencias, 'pt-min': p.minutos_jugados, 'pt-rating': p.rendimiento };
    Object.keys(map).forEach(function (k) { $(k).value = map[k] == null ? '' : map[k]; });
  }
  async function get(id) {
    var d = await fetch(BASE + '/api/partidos').then(function (r) { return r.json(); });
    return (d.partidos || []).find(function (x) { return x.id === id; });
  }
  function nuevo() {
    F.forEach(function (k) { $(k).value = ''; }); $('pt-fecha').value = today(); $('pt-estado').value = 'programado';
    openForm('Programar partido', 'Programar partido', false);
  }
  async function editar(id) {
    var p = await get(id); if (!p) return;
    fill(p); var jugado = (p.estado || 'jugado') === 'jugado'; $('pt-estado').value = p.estado || 'jugado';
    openForm(jugado ? 'Editar partido' : 'Editar partido programado', 'Guardar', jugado);
  }
  async function resultado(id) {
    var p = await get(id); if (!p) return;
    fill(p); $('pt-estado').value = 'jugado';
    openForm('Resultado vs ' + (p.rival || 'rival'), 'Guardar resultado', true);
    setTimeout(function () { $('pt-gf').focus(); }, 30);
  }

  document.querySelectorAll('.js-new').forEach(function (b) { b.addEventListener('click', nuevo); });
  var cta = document.querySelector('.fb .eu-empty .eu-btn'); if (cta) cta.addEventListener('click', nuevo);
  $('fb').addEventListener('click', async function (e) {
    var b = e.target.closest('button'); if (!b || !b.dataset.id) return;
    var id = parseInt(b.dataset.id, 10);
    if (b.classList.contains('js-edit')) editar(id);
    else if (b.classList.contains('js-result')) resultado(id);
    else if (b.classList.contains('js-del')) {
      if (!(await euConfirm('¿Eliminar este partido?', { confirmLabel: 'Eliminar' }))) return;
      await fetch(BASE + '/api/partidos/' + id, { method: 'DELETE' });
      toast('Eliminado'); setTimeout(function () { location.reload(); }, 400);
    }
  });
  $('f-pt').addEventListener('submit', async function (e) {
    e.preventDefault();
    var id = $('pt-id').value;
    var body = { fecha: $('pt-fecha').value || today(), hora: $('pt-hora').value, cancha: $('pt-cancha').value.trim(), rival: $('pt-rival').value.trim(),
      estado: $('pt-estado').value, goles_favor: $('pt-gf').value || 0, goles_contra: $('pt-gc').value || 0, goles_propios: $('pt-goles').value || 0,
      asistencias: $('pt-asist').value || 0, minutos_jugados: $('pt-min').value || null, rendimiento: $('pt-rating').value || null };
    var r = await fetch(id ? BASE + '/api/partidos/' + id : BASE + '/api/partidos', { method: id ? 'PATCH' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (x) { return x.json(); }).catch(function () { return {}; });
    if (!r.ok) { toast('Error: ' + (r.error || 'no se pudo guardar'), 'err'); return; }
    euModal.close('m-pt'); toast(id ? 'Guardado' : 'Partido programado');
    setTimeout(function () { location.reload(); }, 500);
  });
  /* Deep link del radar del dashboard: ?resultado=<id> */
  var q = new URLSearchParams(location.search).get('resultado');
  if (q) { history.replaceState(null, '', location.pathname); resultado(parseInt(q, 10)); }
})();
