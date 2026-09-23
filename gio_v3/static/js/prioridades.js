/* Prioridades (wishlist de Oikonomia) — Design System V2: lista filtrable,
   editar / comprado / descartar / eliminar, y alta de artículos a través del
   protocolo de compra (pasos compartidos con la wishlist de Guardarropa; aquí
   el score se calcula en el cliente y el pago con EC se registra al agregar). */
(function () {
  'use strict';
  var root = document.getElementById('pr');
  if (!root) return;
  var BASE = '/finanzas/prioridades';
  var LOGIC = ['util', 'dry', 'cpu', 'mant', 'cap'];
  var REC = {
    compra_optima: { t: 'success', ic: 'circle-check', title: 'Adquisición estratégica óptima', desc: 'El artículo supera todos los filtros. La compra está justificada.' },
    compra_limitada: { t: 'warning', ic: 'wrench', title: 'Compra limitada — CapEx justificado', desc: 'Estado inestable pero es inversión productiva. Procede con máxima austeridad.' },
    reevaluar: { t: 'warning', ic: 'triangle-alert', title: 'Re-evaluar o rechazar', desc: 'El artículo tiene mérito pero el mantenimiento es alto. Busca una alternativa más simple.' },
    no_compres: { t: 'danger', ic: 'x', title: 'No compres', desc: 'No superó los filtros del algoritmo lógico. Guarda este análisis y revísalo en 30 días.' },
    bloqueo_supervivencia: { t: 'danger', ic: 'ban', title: 'Bloqueo por supervivencia', desc: 'Estado inestable + ocio. Esta compra compromete tu estabilidad financiera.' },
    glitch_emocional: { t: 'danger', ic: 'zap', title: 'Glitch emocional detectado', desc: 'El deseo desaparece en calma. No es una necesidad real — libera el deseo.' },
  };
  var FIELDS = ['Nombre', 'Categoria', 'Prioridad', 'Precio', 'Mes', 'Tienda', 'Url', 'Notas'];
  var item = {}, ans = {}, result = null;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function post(u, b) { return fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then(function (r) { return r.json(); }); }
  function reload(ms) { setTimeout(function () { location.reload(); }, ms || 300); }
  function tone(s) { return s >= 70 ? 'success' : s >= 45 ? 'warning' : 'danger'; }
  function readFields(p) {
    return { nombre: $(p + 'Nombre').value.trim(), categoria: $(p + 'Categoria').value, prioridad: $(p + 'Prioridad').value,
      precio_estimado: parseFloat($(p + 'Precio').value) || 0, mes_objetivo: $(p + 'Mes').value, tienda: $(p + 'Tienda').value.trim(),
      url: $(p + 'Url').value.trim(), notas: $(p + 'Notas').value.trim() };
  }

  /* ── Filtros (se recuerdan por dispositivo) ─────────────────────────── */
  function filter(f) {
    var shown = 0;
    $$('[data-f]').forEach(function (c) { c.setAttribute('aria-pressed', String(c.dataset.f === f)); });
    $$('.pr-card').forEach(function (c) {
      var ok = f === 'todos' || c.dataset.estado === f || c.dataset.prioridad === f;
      c.hidden = !ok; if (ok) shown++;
    });
    $('pr-nomatch').hidden = shown > 0 || !$$('.pr-card').length;
    try { localStorage.setItem('wl_filter', f); } catch (e) { /* sin storage */ }
  }
  $$('[data-f]').forEach(function (c) { c.addEventListener('click', function () { filter(c.dataset.f); }); });
  try { var saved = localStorage.getItem('wl_filter'); if (saved && document.querySelector('[data-f="' + saved + '"]')) filter(saved); } catch (e) { /* sin storage */ }

  /* ── Acciones de la lista ───────────────────────────────────────────── */
  root.addEventListener('click', function (e) {
    var t;
    if ((t = e.target.closest('[data-edit]'))) {
      fetch(BASE + '/api/get/' + t.dataset.edit).then(function (r) { return r.json(); }).then(function (d) {
        $('editId').value = t.dataset.edit;
        $('fNombre').value = d.nombre || ''; $('fCategoria').value = d.categoria || ''; $('fPrioridad').value = d.prioridad || 'Media';
        $('fPrecio').value = d.precio_estimado || ''; $('fMes').value = d.mes_objetivo || ''; $('fTienda').value = d.tienda || '';
        $('fUrl').value = d.url || ''; $('fNotas').value = d.notas || ''; $('fEstado').value = d.estado || 'Pendiente';
        euModal.open('m-edit'); setTimeout(function () { $('fNombre').focus(); }, 20);
      }).catch(function () { toast('Sin conexión', 'err'); });
    } else if ((t = e.target.closest('[data-comprar]'))) {
      $('comprarId').value = t.dataset.comprar; $('comprarNombre').textContent = t.dataset.nombre;
      $('cPrecioReal').value = +t.dataset.precio || '';
      euModal.open('m-comprar'); setTimeout(function () { $('cPrecioReal').focus(); }, 20);
    } else if ((t = e.target.closest('[data-descartar]'))) {
      var id = t.dataset.descartar;
      euConfirm('¿Descartar este artículo?', { danger: false, confirmLabel: 'Descartar' }).then(function (ok) {
        if (ok) post(BASE + '/api/descartar/' + id).then(function () { toast('Descartado'); reload(); });
      });
    } else if ((t = e.target.closest('[data-del]'))) {
      var did = t.dataset.del;
      euConfirm('¿Eliminar definitivamente este artículo?', { confirmLabel: 'Eliminar' }).then(function (ok) {
        if (ok) post(BASE + '/api/delete/' + did).then(function () { toast('Eliminado'); reload(); });
      });
    }
  });
  $('f-edit').addEventListener('submit', function (e) {
    e.preventDefault();
    var body = readFields('f');
    if (!body.nombre) { toast('El nombre es requerido', 'err'); $('fNombre').focus(); return; }
    body.estado = $('fEstado').value;
    post(BASE + '/api/update/' + $('editId').value, body).then(function () { euModal.close('m-edit'); toast('Guardado', 'ok'); reload(); })
      .catch(function () { toast('Sin conexión', 'err'); });
  });
  $('f-comprar').addEventListener('submit', function (e) {
    e.preventDefault();
    post(BASE + '/api/comprar/' + $('comprarId').value, { precio_real: $('cPrecioReal').value }).then(function () { euModal.close('m-comprar'); toast('¡Comprado!', 'win'); reload(500); })
      .catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Protocolo de compra ────────────────────────────────────────────── */
  function show(s) {
    $$('#pr-proto .wl-step').forEach(function (el) { el.hidden = +el.dataset.step !== s; });
    var bar = $('wl-prog'); bar.querySelector('i').style.width = (s / 4 * 100) + '%'; bar.setAttribute('aria-valuenow', s * 25);
    $$('#wl-phases li').forEach(function (li) {
      var i = +li.dataset.ph; li.classList.toggle('is-done', i < s); li.classList.toggle('is-on', i === s);
      if (i === s) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
    if (s === 3) calcCPU();
    if (s === 4) renderResult();
    var body = $('pr-proto'); body.scrollTop = 0; if (body.parentNode) body.parentNode.scrollTop = 0;
    var h = document.querySelector('#pr-proto .wl-step[data-step="' + s + '"] .t-section, #pr-proto .wl-step[data-step="' + s + '"] legend');
    if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
  }
  function visibility() {
    var vis = {
      'q-cls': ans.sol === 'inestable', 'q-dry': ans.util === 'yes', 'q-cpu': ans.util === 'yes' && ans.dry === 'no',
      'q-mant': ans.util === 'yes' && ans.dry === 'no' && ans.cpu === 'yes',
      'q-cap': ans.util === 'yes' && ans.dry === 'no' && ans.cpu === 'yes' && ans.mant === 'yes',
    };
    Object.keys(vis).forEach(function (id) {
      $(id).hidden = !vis[id];
      if (!vis[id]) { var q = id.slice(2); delete ans[q]; $$('.wl-choice[data-q="' + q + '"]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); }); }
    });
  }
  function calcCPU() {
    var usos = parseInt($('usos-input').value, 10) || 1, cpu = (item.precio_estimado || 0) / usos;
    $('cpu-val').textContent = '$' + cpu.toFixed(2) + ' MXN';
    var note = usos + ' uso(s)/mes · ~' + usos * 12 + ' usos/año. ';
    note += cpu < 20 ? 'Excelente ratio — alta frecuencia.' : cpu < 100 ? 'Ratio aceptable.' : cpu < 500 ? 'Ratio elevado — evalúa la calidad del valor.' : 'Ratio muy alto — considera el uso real esperado.';
    $('cpu-note').textContent = note;
    $('cpu-val').closest('.wl-cpu-out').dataset.tone = cpu < 100 ? 'success' : cpu < 500 ? 'warning' : 'danger';
  }
  $('usos-input').addEventListener('input', calcCPU);
  function resetProto() {
    item = {}; ans = {}; result = null;
    $('f-item').reset(); $('usos-input').value = 1; $('wl-result').innerHTML = '';
    $$('#pr-proto .wl-choice').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
    visibility(); show(0);
  }
  $$('.js-add').forEach(function (b) {
    b.addEventListener('click', function () { resetProto(); euModal.open('m-proto'); setTimeout(function () { $('p0Nombre').focus(); }, 20); });
  });
  $('f-item').addEventListener('submit', function (e) {
    e.preventDefault();
    item = readFields('p0');
    if (!item.nombre) { toast('El nombre es requerido', 'err'); $('p0Nombre').focus(); return; }
    show(1);
  });
  function need(q, msg) { if (ans[q] == null) { toast(msg, 'err'); var b = document.querySelector('#pr-proto .wl-choice[data-q="' + q + '"]'); if (b) b.focus(); return true; } return false; }
  $('pr-proto').addEventListener('click', function (e) {
    var t;
    if ((t = e.target.closest('[data-go]'))) { show(+t.dataset.go); return; }
    if ((t = e.target.closest('.wl-choice'))) {
      ans[t.dataset.q] = t.dataset.v;
      $$('#pr-proto .wl-choice[data-q="' + t.dataset.q + '"]').forEach(function (b) { b.setAttribute('aria-pressed', String(b === t)); });
      visibility(); return;
    }
    if ((t = e.target.closest('[data-next]'))) {
      var from = +t.dataset.next;
      if (from === 1) { if (need('days', 'Selecciona cuántos días llevas deseando el artículo') || need('calm', 'Responde si el deseo persiste en calma')) return; show(2); }
      else if (from === 2) { if (need('sol', 'Indica tu estado financiero')) return; if (ans.sol === 'inestable' && need('cls', 'Clasifica el artículo (CapEx u OpEx)')) return; show(3); }
      else if (from === 3) {
        var msgs = { util: 'Responde si el artículo es útil', dry: 'Responde el filtro DRY', cpu: 'Responde el cálculo de CPU', mant: 'Responde la pregunta de mantenimiento', cap: 'Responde el filtro de costo de oportunidad' };
        for (var i = 0; i < LOGIC.length; i++) { if (!$('q-' + LOGIC[i]).hidden && need(LOGIC[i], msgs[LOGIC[i]])) return; }
        result = compute(); show(4);
      }
      return;
    }
    if ((t = e.target.closest('[data-add]'))) add(t.dataset.add === 'ec' ? +t.dataset.ec : 0, t);
    else if (e.target.closest('.js-skip')) euModal.close('m-proto');
  });

  function compute() {
    var score = 0, reasons = [], dias = +ans.days, usos = parseInt($('usos-input').value, 10) || 1;
    if (dias >= 7) { score += 15; reasons.push('Deseo verificado por ' + dias + ' días — supera el filtro de 72h con solidez'); }
    else if (dias >= 3) { score += 10; reasons.push('Deseo de ' + dias + ' días — supera el umbral mínimo de 72h'); }
    else if (dias >= 1) { score += 5; reasons.push('Deseo de ' + dias + ' día(s) — todavía en zona de riesgo dopamínico'); }
    else reasons.push('Deseo del mismo día — alta probabilidad de compra impulsiva');
    if (ans.calm !== 'yes') { reasons.push('El deseo desaparece en calma — patrón de glitch emocional detectado'); return { score: score, rec: 'glitch_emocional', reasons: reasons }; }
    score += 5; reasons.push('El deseo persiste sin estímulos — señal de necesidad real');
    if (ans.sol === 'estable') { score += 30; reasons.push('Estado financiero estable — capital disponible'); }
    else if (ans.cls === 'capex') { score += 15; reasons.push('Estado inestable, pero es inversión productiva (CapEx)'); return { score: score, rec: 'compra_limitada', reasons: reasons }; }
    else { reasons.push('Estado inestable + gasto de ocio — bloqueo por supervivencia financiera'); return { score: score, rec: 'bloqueo_supervivencia', reasons: reasons }; }
    if (ans.util !== 'yes') { reasons.push('Sin utilidad directa para vida o trabajo — rechazado por utilidad'); return { score: score, rec: 'no_compres', reasons: reasons }; }
    score += 15; reasons.push('Útil para trabajo/vida — pasa el filtro de utilidad directa');
    if (ans.dry === 'yes') { reasons.push('Ya tienes algo que cumple el 80% de la función — redundancia evitada (DRY)'); return { score: score, rec: 'no_compres', reasons: reasons }; }
    score += 10; reasons.push('No tienes una alternativa equivalente — no es redundante');
    if (ans.cpu !== 'yes') { reasons.push('Costo por uso elevado — retorno de inversión insuficiente'); return { score: score, rec: 'no_compres', reasons: reasons }; }
    score += 15; reasons.push('Costo por uso favorable (' + usos + ' usos/mes) — buena relación valor/precio');
    if (ans.mant !== 'yes') { reasons.push('Mantenimiento alto (>10 min/semana) — el costo de tiempo real es significativo'); return { score: score, rec: 'reevaluar', reasons: reasons }; }
    score += 5; reasons.push('Bajo mantenimiento — no drena tu tiempo de forma relevante');
    if (ans.cap === 'yes') { reasons.push('El capital rendiría más invertido — costo de oportunidad supera el valor'); return { score: score, rec: 'no_compres', reasons: reasons }; }
    score += 5; reasons.push('El valor del artículo supera el rendimiento compuesto del capital — adquisición justificada');
    return { score: score, rec: 'compra_optima', reasons: reasons };
  }
  var PASS = /^(Deseo verificado|El deseo persiste|Estado financiero|Útil|No tienes|Costo por uso favorable|Bajo|El valor del artículo|Estado inestable, pero)/, WARN = /^(Deseo de |Estado inestable)/;
  function renderResult() {
    var r = result, m = REC[r.rec] || REC.no_compres, sc = Math.max(0, Math.min(100, r.score)), circ = 2 * Math.PI * 52;
    var positive = r.rec === 'compra_optima' || r.rec === 'compra_limitada';
    $('wl-result').innerHTML = '<div class="wl-res" data-tone="' + tone(sc) + '"><div class="wl-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="wl-ring-bg" cx="60" cy="60" r="52"/><circle class="wl-ring-fg" id="pr-ring" cx="60" cy="60" r="52" stroke-dasharray="' + circ + '" stroke-dashoffset="' + circ + '"/></svg>' +
      '<div class="wl-ring-c"><span class="t-data wl-score">' + sc + '</span><span class="t-eyebrow">Score</span></div></div>' +
      '<div class="wl-rec" data-tone="' + m.t + '"><i data-lucide="' + m.ic + '"></i><span>' + m.title + '</span></div><p class="t-body wl-rec-desc">' + m.desc + '</p></div>' +
      '<ul class="wl-reasons">' + r.reasons.map(function (rs) {
        var t = PASS.test(rs) ? 'success' : WARN.test(rs) ? 'warning' : 'danger';
        return '<li class="wl-reason" data-tone="' + t + '"><i data-lucide="' + (t === 'success' ? 'check' : t === 'warning' ? 'triangle-alert' : 'x') + '"></i><span>' + esc(rs) + '</span></li>';
      }).join('') + '</ul><div id="pr-ec"></div>' +
      '<div class="wl-res-actions">' + (positive
        ? '<button type="button" class="eu-btn eu-btn--primary" data-add="plain"><i data-lucide="plus"></i>Agregar a la lista</button>'
        : '<button type="button" class="eu-btn eu-btn--secondary" data-add="plain"><i data-lucide="plus"></i>Agregar de todas formas</button><button type="button" class="eu-btn eu-btn--danger js-skip"><i data-lucide="x"></i>Descartar</button>') + '</div>';
    icons();
    requestAnimationFrame(function () { requestAnimationFrame(function () { var f = $('pr-ring'); if (f) f.style.strokeDashoffset = circ - sc / 100 * circ; }); });
    loadEC();
  }
  function loadEC() {
    var precio = item.precio_estimado || 0; if (!precio) return;
    fetch(BASE + '/api/ec-status?precio=' + precio).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ec_sugerido || !$('pr-ec')) return;
      var pct = Math.min(d.pct_balance || 0, 100), pctTxt = d.pct_balance !== null ? d.pct_balance + '%' : '—', pt = pct <= 30 ? 'success' : pct <= 60 ? 'warning' : 'danger';
      var at, ai, txt;
      if (d.puede_pagar && d.pct_balance <= 30) { at = 'success'; ai = 'circle-check'; txt = 'Puedes pagar con EC y solo usas el <b>' + pctTxt + '</b> de tu balance — decisión prudente.'; }
      else if (d.puede_pagar && d.pct_balance <= 60) { at = 'warning'; ai = 'triangle-alert'; txt = 'Puedes pagar, pero usarías el <b>' + pctTxt + '</b> de tu balance EC. Evalúa si lo vale.'; }
      else if (d.puede_pagar) { at = 'warning'; ai = 'triangle-alert'; txt = 'La compra consumiría <b>' + pctTxt + '</b> de tu balance EC — más de la mitad de tu esfuerzo acumulado.'; }
      else { at = 'danger'; ai = 'circle-x'; txt = 'Te faltan <b>' + (d.ec_sugerido - d.balance) + ' EC</b>. Sigue acumulando — con actividad diaria lo alcanzas en poco tiempo.'; }
      $('pr-ec').innerHTML = '<section class="eu-card eu-card--inset wl-ec" aria-labelledby="pr-ec-t"><div class="eu-hstack wl-ec-hd"><span class="eu-row-ic wl-ec-ic"><i data-lucide="coins"></i></span><div><div class="t-card" id="pr-ec-t">¿Comprar con Euda-Credits (EC)?</div><div class="t-meta">Gamificación · 1 EC = $' + d.ec_rate + ' MXN</div></div></div>' +
        '<div class="eu-grid-3 wl-ec-stats"><div><div class="t-data wl-ec-v">' + d.balance + '</div><div class="t-meta">Tu balance</div></div><div><div class="t-data wl-ec-v ' + (d.puede_pagar ? 'fg-ec' : 'fg-danger') + '">' + d.ec_sugerido + '</div><div class="t-meta">EC sugerido</div></div>' +
        '<div data-tone="' + pt + '"><div class="t-data wl-ec-v wl-tone-fg">' + pctTxt + '</div><div class="t-meta">Del balance</div></div></div>' +
        '<div class="eu-progress wl-ec-bar" data-tone="' + pt + '" role="progressbar" aria-label="Porcentaje del balance" aria-valuenow="' + Math.round(pct) + '" aria-valuemax="100"><i style="width:' + pct + '%"></i></div>' +
        '<p class="wl-alert" data-tone="' + at + '"><i data-lucide="' + ai + '"></i><span>' + txt + '</span></p>' +
        '<button type="button" class="eu-btn eu-btn--primary eu-btn--block" data-add="ec" data-ec="' + d.ec_sugerido + '"' + (d.puede_pagar ? '' : ' disabled') + '><i data-lucide="coins"></i>' + (d.puede_pagar ? 'Agregar + pagar ' + d.ec_sugerido + ' EC' : 'EC insuficientes (necesitas ' + (d.ec_sugerido - d.balance) + ' más)') + '</button></section>';
      icons();
    }).catch(function () { /* la tarjeta EC es opcional */ });
  }
  function add(ec, btn) {
    var go = function () {
      btn.disabled = true;
      post(BASE + '/api/add', Object.assign({}, item, { protocolo_score: result.score, protocolo_rec: result.rec, comprar_con_ec: ec ? 1 : 0, ec_pagado: ec }))
        .then(function () { euModal.close('m-proto'); toast(ec ? 'Agregado · ' + ec + ' EC descontados' : 'Agregado a la lista', 'ok'); reload(500); })
        .catch(function () { toast('Sin conexión', 'err'); btn.disabled = false; });
    };
    if (!ec) { go(); return; }
    euConfirm('¿Pagar ' + ec + ' EC por «' + item.nombre + '»? Se descontarán de tu balance.', { confirmLabel: 'Pagar ' + ec + ' EC' }).then(function (ok) { if (ok) go(); });
  }
})();
