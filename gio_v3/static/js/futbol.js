/* Fútbol (Hegemonikon) — Design System V2.
   Paso 1: programar (liga/fecha/hora/rival/cancha). Paso 2: registrar resultado
   (marcador, goles, asistencias, minutos, rating) → liquida XP en el backend.
   Pestañas por liga (SoccerGDL mié · Terranova jue · SoccerPark dom): filtran
   cifras, próximos e historial sin recargar; la pestaña va en el hash (#terranova). */
(function () {
  'use strict';
  var BASE = '/bienestar/futbol';
  var DIAS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];   // Date.getDay()
  function $(id) { return document.getElementById(id); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function today() { return iso(new Date()); }
  var F = ['pt-id', 'pt-cancha', 'pt-rival', 'pt-gf', 'pt-gc', 'pt-goles', 'pt-asist', 'pt-min', 'pt-rating', 'pt-hora'];
  var root = $('fb');

  /* ── Pestañas por liga ─────────────────────────────────────────────── */
  var tabs = $$('.fb-tabs [role=tab]');
  var actual = 'todas';

  function filtrar(liga) {
    actual = liga;
    tabs.forEach(function (t) {
      var on = t.dataset.liga === liga;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      if (on) { $('fb-panel').setAttribute('aria-labelledby', t.id); t.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    });
    $$('[data-panel]', root).forEach(function (el) { el.hidden = el.dataset.panel !== liga; });
    var ver = function (el) { return liga === 'todas' || el.dataset.liga === liga; };
    var prox = $$('.fb-card--prox', root);
    prox.forEach(function (el) { el.hidden = !ver(el); });
    var proxSec = root.querySelector('.js-prox-sec');
    proxSec.hidden = !prox.some(function (el) { return !el.hidden; });
    var hist = $$('.fb-card[data-res]', root);
    hist.forEach(function (el) { el.hidden = !ver(el); });
    var visibles = hist.filter(function (el) { return !el.hidden; });
    // Separadores de mes: solo los que tienen algún partido visible.
    $$('.js-mes', root).forEach(function (h) {
      h.hidden = !visibles.some(function (el) { return el.dataset.mes === h.dataset.mes; });
    });
    // Forma: los últimos 8 de lo que se ve.
    var dots = root.querySelector('.js-forma-dots');
    dots.innerHTML = '';
    visibles.slice(0, 8).forEach(function (el) {
      var s = document.createElement('span');
      s.className = 'fb-dot is-' + el.dataset.res; s.title = el.dataset.tip;
      dots.appendChild(s);
    });
    root.querySelector('.js-forma').hidden = !visibles.length;
    root.querySelector('.js-hist-empty').hidden = visibles.length > 0;
    var h = liga === 'todas' ? '' : '#' + liga;
    if (location.hash !== h) history.replaceState(null, '', location.pathname + location.search + h);
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { filtrar(t.dataset.liga); }); });
  $$('.js-liga', root).forEach(function (b) {
    b.addEventListener('click', function () {
      filtrar(b.dataset.liga);
      var tab = $('fb-tab-' + b.dataset.liga); if (tab) tab.focus();
    });
  });
  var inicial = location.hash.slice(1);
  filtrar(tabs.some(function (t) { return t.dataset.liga === inicial; }) ? inicial : 'todas');

  /* ── Selector de liga del formulario ───────────────────────────────── */
  var picks = $$('.fb-liga-pick [role=radio]');
  var ligaManual = false;
  function setLiga(liga) {
    $('pt-liga').value = liga;
    picks.forEach(function (b) { b.setAttribute('aria-checked', b.dataset.liga === liga ? 'true' : 'false'); });
  }
  function ligaPorFecha(f) {
    if (!f) return 'otra';
    var d = new Date(f + 'T12:00:00'), dia = DIAS[d.getDay()];
    var b = picks.filter(function (x) { return x.dataset.dia === dia; })[0];
    return b ? b.dataset.liga : 'otra';
  }
  /** Próxima fecha (hoy incluido) del día de la semana de esa liga. */
  function proximaFecha(liga) {
    var b = picks.filter(function (x) { return x.dataset.liga === liga; })[0];
    if (!b || !b.dataset.dia) return today();
    var d = new Date(), meta = DIAS.indexOf(b.dataset.dia);
    d.setDate(d.getDate() + ((meta - d.getDay() + 7) % 7));
    return iso(d);
  }
  picks.forEach(function (b) {
    b.addEventListener('click', function () {
      ligaManual = true; setLiga(b.dataset.liga);
      // Programando uno nuevo: la fecha salta al próximo día de esa liga.
      if (!$('pt-id').value && b.dataset.dia && ligaPorFecha($('pt-fecha').value) !== b.dataset.liga) {
        $('pt-fecha').value = proximaFecha(b.dataset.liga);
      }
    });
  });
  $('pt-fecha').addEventListener('change', function () { if (!ligaManual) setLiga(ligaPorFecha(this.value)); });

  /* ── Formulario ────────────────────────────────────────────────────── */
  function openForm(title, save, withResult) {
    $('m-pt-t').textContent = title; $('pt-save').textContent = save;
    $('pt-result').hidden = !withResult;
    euModal.open('m-pt');
  }
  function fill(p) {
    var map = { 'pt-id': p.id, 'pt-fecha': p.fecha, 'pt-hora': p.hora, 'pt-cancha': p.cancha, 'pt-rival': p.rival, 'pt-gf': p.goles_favor,
      'pt-gc': p.goles_contra, 'pt-goles': p.goles_propios, 'pt-asist': p.asistencias, 'pt-min': p.minutos_jugados, 'pt-rating': p.rendimiento };
    Object.keys(map).forEach(function (k) { $(k).value = map[k] == null ? '' : map[k]; });
    ligaManual = true; setLiga(p.liga || ligaPorFecha(p.fecha));
  }
  async function get(id) {
    var d = await fetch(BASE + '/api/partidos').then(function (r) { return r.json(); });
    return (d.partidos || []).find(function (x) { return x.id === id; });
  }
  function nuevo(liga) {
    F.forEach(function (k) { $(k).value = ''; }); $('pt-estado').value = 'programado';
    // Desde una liga (pestaña o tarjeta): esa liga y su próximo día de juego.
    liga = liga || (actual !== 'todas' ? actual : '');
    if (liga) { ligaManual = true; setLiga(liga); $('pt-fecha').value = proximaFecha(liga); }
    else { ligaManual = false; $('pt-fecha').value = today(); setLiga(ligaPorFecha(today())); }
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

  $$('.js-new').forEach(function (b) { b.addEventListener('click', function () { nuevo(b.dataset.liga); }); });
  var cta = document.querySelector('.fb .eu-empty .eu-btn'); if (cta) cta.addEventListener('click', function () { nuevo(); });
  root.addEventListener('click', async function (e) {
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
      liga: $('pt-liga').value || ligaPorFecha($('pt-fecha').value),
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
  if (q) { history.replaceState(null, '', location.pathname + location.hash); resultado(parseInt(q, 10)); }
})();
