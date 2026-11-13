/* revision.js — Revisión de la semana en 4 pasos (handoff Revisión).

   · Pasos: Atrás / Siguiente y la columna de pasos cambian de panel sin
     recargar (?paso=N en la URL, para retomar). Cada cambio de paso guarda
     el paso y lo escrito (POST parcial a /ataraxia/api/revision).
   · Paso 1 y 2 se guardan solos al escribir (notas y métricas a mano).
   · Paso 3: cada botón ejecuta, en orden, las llamadas de su módulo
     (data-calls) y la fila queda resuelta ahí mismo.
   · Paso 4: estrellas con /ataraxia/api/prioridad-semana (máx. 3).
   · «Cerrar la semana» manda cerrar:true: el servidor paga una sola vez y
     marca «Planeación» del domingo. */
(function () {
  'use strict';
  var root = document.getElementById('rv');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var paso = +root.dataset.paso || 1;
  var cerrada = root.dataset.cerrada === 'true';
  var saved = $('rv-saved');
  var resueltos = 0;

  function icons() { try { window.lucide.createIcons(); } catch (e) {} }
  function call(c) {
    var opt = { method: c.method || 'POST', headers: { 'Accept': 'application/json' } };
    if (c.body !== undefined || opt.method !== 'DELETE') {
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(c.body || {});
    }
    return fetch(c.url, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok || d.ok === false || d.error) throw new Error(d.error || ('Error ' + r.status));
        return d;
      });
    });
  }

  /* ── Guardado parcial ─────────────────────────────────────────────── */
  var pend = {}, timer = null, enVuelo = Promise.resolve();
  function estado(t) { if (saved) saved.textContent = t; }
  function flush(extra) {
    clearTimeout(timer);
    var body = Object.assign({}, pend, extra || {});
    pend = {};
    if (!Object.keys(body).length) return enVuelo;
    estado('Guardando…');
    enVuelo = enVuelo.then(function () {
      return call({ url: '/ataraxia/api/revision', body: body });
    }).then(function (d) { estado('Guardado'); return d; }, function (e) {
      estado('No se guardó'); if (window.toast) toast(e.message || 'No se pudo guardar', 'err'); throw e;
    });
    return enVuelo;
  }
  function queue(key, val) { pend[key] = val; clearTimeout(timer); timer = setTimeout(flush, 700); }
  root.addEventListener('input', function (e) {
    var el = e.target.closest('[data-save]'); if (!el) return;
    queue(el.dataset.save, el.value);
  });
  window.addEventListener('pagehide', function () {
    if (!Object.keys(pend).length) return;
    try { fetch('/ataraxia/api/revision', { method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pend) }); } catch (e) {}
  });

  /* ── Pasos ────────────────────────────────────────────────────────── */
  function show(n, opts) {
    paso = n;
    [].forEach.call(root.querySelectorAll('[data-panel]'), function (p) { p.hidden = +p.dataset.panel !== n; });
    [].forEach.call(root.querySelectorAll('.rv-step'), function (a) {
      var k = +a.dataset.go;
      if (k === n) a.setAttribute('aria-current', 'step'); else a.removeAttribute('aria-current');
      if (k < n || cerrada) a.dataset.done = 'true'; else delete a.dataset.done;
    });
    $('rv-nav').hidden = n === 5;
    $('rv-prev').hidden = n <= 1;
    var next = $('rv-next');
    next.innerHTML = n === 4 ? (cerrada ? 'Guardar y ver el cierre' : 'Cerrar la semana') : 'Siguiente<i data-lucide="arrow-right"></i>';
    icons();
    try { history.replaceState(null, '', '?paso=' + n); } catch (e) {}
    var h = root.querySelector('[data-panel="' + n + '"] [tabindex="-1"]');
    if (h && !(opts && opts.sinFoco)) h.focus({ preventScroll: true });
    if (!(opts && opts.sinFoco)) window.scrollTo({ top: 0, behavior: 'smooth' });
    if (n <= 4 && !(opts && opts.sinFoco)) flush({ paso: n }).catch(function () {});
  }
  root.addEventListener('click', function (e) {
    var a = e.target.closest('[data-go]');
    if (a) { e.preventDefault(); show(+a.dataset.go); }
  });
  $('rv-prev').addEventListener('click', function () { show(Math.max(1, paso - 1)); });
  $('rv-next').addEventListener('click', function () {
    if (paso < 4) { show(paso + 1); return; }
    var btn = this;
    btn.setAttribute('aria-busy', 'true'); btn.disabled = true;
    flush({ paso: 4, cerrar: true }).then(function (d) {
      cerrada = true; root.dataset.cerrada = 'true';
      var n = $('rv-prio-list').querySelectorAll('[aria-pressed=true]').length;
      $('rv-done-sub').textContent = n + ' prioridad' + (n === 1 ? '' : 'es') + ' · ' + resueltos + ' cabo' + (resueltos === 1 ? '' : 's') + ' cerrado' + (resueltos === 1 ? '' : 's') +
        (d.planeacion ? ' · Planeación marcada en Ataraxia' : '');
      show(5);
      if (d.gam && window.euGam) euGam(d.gam, { el: $('rv-h5') });
      else if (window.euRefreshXp) euRefreshXp();
      if (!d.pagada && window.toast) toast('Semana cerrada · la recompensa ya se había pagado');
      if (window.euAvisos) euAvisos.load().catch(function () {});
    }).catch(function () {}).then(function () { btn.removeAttribute('aria-busy'); btn.disabled = false; });
  });

  /* ── Paso 3: cerrar cabos ─────────────────────────────────────────── */
  var pendEl = $('rv-pend');
  root.addEventListener('click', function (e) {
    var b = e.target.closest('[data-calls]'); if (!b || b.disabled) return;
    var li = b.closest('.rv-cabo');
    var calls = JSON.parse(b.dataset.calls || '[]');
    var btns = li.querySelectorAll('button');
    [].forEach.call(btns, function (x) { x.disabled = true; });
    b.setAttribute('aria-busy', 'true');
    calls.reduce(function (p, c) { return p.then(function () { return call(c); }); }, Promise.resolve())
      .then(function (d) {
        li.classList.add('is-done');
        if (b.dataset.tachar) li.classList.add('is-gone');
        li.querySelector('.rv-cabo-acts').hidden = true;
        var res = li.querySelector('.rv-cabo-res'); res.textContent = b.dataset.res || 'Listo'; res.hidden = false;
        resueltos++;
        if (pendEl) pendEl.textContent = Math.max(0, (+pendEl.textContent || 0) - 1);
        if (d && d.gam && window.euGam) euGam(d.gam, { el: res });
        if (window.euAvisos) euAvisos.load().catch(function () {});
      })
      .catch(function (err) {
        [].forEach.call(btns, function (x) { x.disabled = false; });
        if (window.toast) toast(err.message || 'No se pudo', 'err');
      })
      .then(function () { b.removeAttribute('aria-busy'); });
  });

  /* ── Paso 4: prioridades (máx. 3) ─────────────────────────────────── */
  var box = $('rv-prio'), list = $('rv-prio-list');
  function pintar(v) {
    if (!v || !v.opciones) return;
    list.innerHTML = v.opciones.map(function (o) {
      var t = document.createElement('span'); t.textContent = o.title;
      return '<li><button type="button" class="rv-prio-it" data-id="' + o.id + '" aria-pressed="' + (o.on ? 'true' : 'false') + '"><i data-lucide="star"></i><span>' + t.innerHTML + '</span></button></li>';
    }).join('');
    var full = v.n >= v.max;
    box.dataset.full = full ? 'true' : 'false';
    var n = $('rv-prio-n'); n.textContent = v.n + '/' + v.max; n.classList.toggle('is-full', full);
    $('rv-prio-add').hidden = full;
    $('rv-prio-empty').hidden = v.opciones.length > 0;
    icons();
  }
  list.addEventListener('click', function (e) {
    var b = e.target.closest('.rv-prio-it'); if (!b) return;
    if (box.dataset.full === 'true' && b.getAttribute('aria-pressed') !== 'true') {
      if (window.toast) toast('Ya elegiste 3. Quita una estrella primero.'); return;
    }
    call({ url: '/ataraxia/api/prioridad-semana/' + b.dataset.id, body: {} }).then(pintar)
      .catch(function (err) { if (window.toast) toast(err.message || 'No se pudo', 'err'); });
  });
  $('rv-prio-add').addEventListener('submit', function (e) {
    e.preventDefault();
    var inp = $('rv-prio-inp'), texto = inp.value.trim(); if (!texto) return;
    call({ url: '/ataraxia/api/prioridad-semana', body: { texto: texto } }).then(function (v) { inp.value = ''; pintar(v); })
      .catch(function (err) { if (window.toast) toast(err.message || 'No se pudo', 'err'); });
  });

  show(paso, { sinFoco: true });
})();
