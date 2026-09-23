/* Wishlist — Design System V2: protocolo de compra en 5 pasos (artículo,
   firewall de dopamina, solvencia, algoritmo lógico, resultado con score y
   pago opcional con EC) y lista filtrable de artículos evaluados. */
(function () {
  'use strict';
  var root = document.getElementById('wl');
  if (!root) return;
  var API = '/guardarropa/wishlist/api';
  var step = 0, itemId = null, item = {}, ans = {}, result = null, listFilter = 'activos';
  var REC = {
    compra_optima: { t: 'success', ic: 'circle-check', title: 'Adquisición estratégica óptima', desc: 'El artículo supera todos los filtros del protocolo. La compra está justificada por utilidad, eficiencia económica y diseño de vida.', action: 'Comprar', short: 'Óptima' },
    compra_limitada: { t: 'warning', ic: 'wrench', title: 'Compra limitada — inversión estratégica', desc: 'Estado financiero inestable, pero el artículo es CapEx productivo. Procede con máxima austeridad: precio mínimo, financiamiento 0% o ahorro previo obligatorio.', action: 'Comprar con austeridad', short: 'Limitada' },
    reevaluar: { t: 'warning', ic: 'triangle-alert', title: 'Re-evaluar o rechazar', desc: 'El artículo tiene mérito pero el costo en tiempo de mantenimiento es significativo. Busca una alternativa de menor complejidad o espera a tener más claridad.', action: 'Pendiente — re-evaluar', short: 'Re-evaluar' },
    no_compres: { t: 'danger', ic: 'x', title: 'No compres', desc: 'El artículo no superó los filtros del algoritmo lógico. Comprar sería una pérdida de capital real. Guarda este análisis y revisítalo en 30 días si el deseo persiste.', action: 'Descartar', short: 'No comprar' },
    bloqueo_supervivencia: { t: 'danger', ic: 'ban', title: 'Bloqueo por supervivencia', desc: 'Estado financiero inestable + gasto de ocio. Esta compra comprometería tu estabilidad financiera. Prioridad absoluta: liquidar pasivos y construir reserva de emergencia primero.', action: 'Descartar', short: 'Bloqueo' },
    glitch_emocional: { t: 'danger', ic: 'zap', title: 'Glitch emocional detectado', desc: 'El deseo desaparece en ausencia de estímulos externos. No es una necesidad real — es una respuesta dopamínica a marketing o entorno de consumo. Libera el deseo.', action: 'Descartar', short: 'Glitch' },
  };
  var ESTADO = { evaluando: ['Evaluando', 'eu-badge--info'], pendiente: ['Pendiente', 'eu-badge--warning'], comprado: ['Comprado', 'eu-badge--success'], descartado: ['Descartado', ''] };
  // Una respuesta «mala» por pregunta (para colorear la selección).
  var LOGIC = ['util', 'dry', 'cpu', 'mant', 'cap'];

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function money(n) { return '$' + Number(n || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 }); }
  function post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); });
  }
  function tone(score) { return score == null ? '' : score >= 70 ? 'success' : score >= 45 ? 'warning' : 'danger'; }

  /* ── Pestañas ───────────────────────────────────────────────────────── */
  function setTab(t) {
    $$('[data-tab]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tab === t)); });
    $('pane-quiz').hidden = t !== 'quiz'; $('pane-list').hidden = t !== 'list';
    if (t === 'list') loadList();
  }
  $$('[data-tab]').forEach(function (b) { b.addEventListener('click', function () { setTab(b.dataset.tab); }); });

  /* ── Pasos ──────────────────────────────────────────────────────────── */
  function show(s, quiet) {
    step = s;
    $$('.wl-step').forEach(function (el) { el.hidden = +el.dataset.step !== s; });
    var bar = $('wl-prog'), pct = s / 4 * 100;
    bar.querySelector('i').style.width = pct + '%'; bar.setAttribute('aria-valuenow', Math.round(pct));
    $$('#wl-phases li').forEach(function (li) {
      var i = +li.dataset.ph;
      li.classList.toggle('is-done', i < s); li.classList.toggle('is-on', i === s);
      if (i === s) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
    if (s === 3) calcCPU();
    if (s === 4) renderResult();
    if (quiet) return;
    var h = document.querySelector('.wl-step[data-step="' + s + '"] .t-section, .wl-step[data-step="' + s + '"] legend');
    root.querySelector('.wl-quiz').scrollIntoView({ block: 'start', behavior: 'smooth' });
    if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
  }
  root.addEventListener('click', function (e) {
    var g = e.target.closest('[data-go]'); if (g) { show(+g.dataset.go); return; }
    var n = e.target.closest('[data-next]'); if (n) { next(+n.dataset.next); return; }
    var c = e.target.closest('.wl-choice'); if (c) pick(c.dataset.q, c.dataset.v);
  });
  function pick(q, v) {
    ans[q] = v;
    $$('.wl-choice[data-q="' + q + '"]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.v === v)); });
    visibility();
  }
  // Muestra las preguntas condicionales y limpia las respuestas que quedan ocultas.
  function visibility() {
    var vis = {
      'q-cls': ans.sol === 'inestable',
      'q-dry': ans.util === 'yes',
      'q-cpu': ans.util === 'yes' && ans.dry === 'no',
      'q-mant': ans.util === 'yes' && ans.dry === 'no' && ans.cpu === 'yes',
      'q-cap': ans.util === 'yes' && ans.dry === 'no' && ans.cpu === 'yes' && ans.mant === 'yes',
    };
    Object.keys(vis).forEach(function (id) {
      $(id).hidden = !vis[id];
      if (!vis[id]) {
        var q = id.slice(2); delete ans[q];
        $$('.wl-choice[data-q="' + q + '"]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
      }
    });
  }
  function calcCPU() {
    var usos = parseInt($('usos-input').value, 10) || 1, precio = item.precio_estimado || 0, cpu = precio / usos;
    $('cpu-val').textContent = '$' + cpu.toFixed(2) + ' MXN';
    var note = 'Con ' + usos + ' uso(s)/mes serían ~' + usos * 12 + ' usos al año. ';
    if (cpu < 20) note += 'Excelente ratio — artículo de alta frecuencia.';
    else if (cpu < 100) note += 'Ratio aceptable — evalúa la calidad del valor por uso.';
    else if (cpu < 500) note += 'Ratio elevado — asegúrate de que el valor justifique el precio.';
    else note += 'Ratio muy alto — considera si el uso real es suficiente.';
    $('cpu-note').textContent = note;
    $('cpu-val').closest('.wl-cpu-out').dataset.tone = cpu < 100 ? 'success' : cpu < 500 ? 'warning' : 'danger';
  }
  $('usos-input').addEventListener('input', calcCPU);

  $('f-item').addEventListener('submit', function (e) {
    e.preventDefault();
    var nombre = $('f-nombre').value.trim();
    if (!nombre) { toast('Ingresa el nombre del artículo', 'err'); $('f-nombre').focus(); return; }
    item = {
      nombre: nombre, categoria: $('f-cat').value, precio_estimado: parseFloat($('f-precio').value) || 0,
      marca: $('f-marca').value, url: $('f-url').value, descripcion: $('f-desc').value,
    };
    if (itemId) { show(1); return; }
    var btn = this.querySelector('[type=submit]'); btn.disabled = true;
    post(API + '/item', item).then(function (r) {
      if (!r.ok) { toast('Error al guardar', 'err'); return; }
      itemId = r.id; show(1);
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { btn.disabled = false; });
  });
  function need(q, msg) { if (ans[q] == null) { toast(msg, 'err'); var b = document.querySelector('.wl-choice[data-q="' + q + '"]'); if (b) b.focus(); return true; } return false; }
  function next(from) {
    if (from === 1) {
      if (need('days', 'Selecciona cuántos días llevas deseando el artículo') || need('calm', 'Responde si el deseo persiste en calma')) return;
      show(2);
    } else if (from === 2) {
      if (need('sol', 'Indica tu estado financiero')) return;
      if (ans.sol === 'inestable' && need('cls', 'Clasifica el artículo (CapEx u OpEx)')) return;
      show(3);
    } else if (from === 3) {
      var msgs = { util: 'Responde si el artículo es útil', dry: 'Responde el filtro DRY', cpu: 'Responde el cálculo de CPU', mant: 'Responde la pregunta de mantenimiento', cap: 'Responde el filtro de costo de oportunidad' };
      for (var i = 0; i < LOGIC.length; i++) { var q = LOGIC[i]; if (!$('q-' + q).hidden && need(q, msgs[q])) return; }
      submitQuiz();
    }
  }
  function yes(q) { return ans[q] === 'yes'; }
  function submitQuiz() {
    var body = Object.assign({}, item, {
      dias_deseo: +ans.days, q1_persiste: yes('calm'), q2_estado_financiero: ans.sol, q2_clasificacion: ans.cls || null,
      q3_es_util: yes('util'), q3_tiene_alternativa: ans.dry == null ? null : yes('dry'), q3_usos_mes: parseInt($('usos-input').value, 10) || 1,
      q3_cpu_ok: ans.cpu == null ? null : yes('cpu'), q3_mantenimiento_ok: ans.mant == null ? null : yes('mant'), q3_costo_oportunidad_ok: ans.cap == null ? null : yes('cap'),
    });
    post(API + '/item/' + itemId + '/quiz', body).then(function (r) {
      if (!r.ok) { toast('Error al calcular protocolo', 'err'); return; }
      result = r; show(4);
    }).catch(function () { toast('Sin conexión', 'err'); });
  }

  /* ── Resultado ──────────────────────────────────────────────────────── */
  var PASS = /^(✓|El valor|No tienes|Útil|Bajo|El deseo persiste|Deseo verificado|Costo por uso favorable|Estado financiero)/;
  var WARN = /^(△|Deseo de|Estado inestable)/;
  function renderResult() {
    var r = result, m = REC[r.recomendacion] || REC.no_compres, positive = r.recomendacion === 'compra_optima' || r.recomendacion === 'compra_limitada';
    var circ = 2 * Math.PI * 52;
    var reasons = r.razones.map(function (rs) {
      var t = PASS.test(rs) ? 'success' : WARN.test(rs) ? 'warning' : 'danger';
      var ic = t === 'success' ? 'check' : t === 'warning' ? 'triangle-alert' : 'x';
      return '<li class="wl-reason" data-tone="' + t + '"><i data-lucide="' + ic + '"></i><span>' + esc(rs.replace(/^[✓△✗]\s*/, '')) + '</span></li>';
    }).join('');
    $('wl-result').innerHTML =
      '<div class="wl-res" data-tone="' + tone(r.score) + '">' +
      '<div class="wl-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="wl-ring-bg" cx="60" cy="60" r="52"/><circle class="wl-ring-fg" id="ring-fill" cx="60" cy="60" r="52" stroke-dasharray="' + circ + '" stroke-dashoffset="' + circ + '"/></svg>' +
      '<div class="wl-ring-c"><span class="t-data wl-score">' + r.score + '</span><span class="t-eyebrow">Score</span></div></div>' +
      '<div class="wl-rec" data-tone="' + m.t + '"><i data-lucide="' + m.ic + '"></i><span>' + m.title + '</span></div>' +
      '<p class="t-body wl-rec-desc">' + m.desc + '</p></div>' +
      '<ul class="wl-reasons">' + reasons + '</ul>' +
      '<div class="wl-res-actions">' +
      (positive ? '<button type="button" class="eu-btn eu-btn--primary" data-decide="comprado" data-label="' + m.action + '"><i data-lucide="shopping-bag"></i>' + m.action + '</button>'
        : '<button type="button" class="eu-btn eu-btn--danger" data-decide="descartado" data-label="' + m.action + '"><i data-lucide="x"></i>' + m.action + '</button>') +
      (positive ? '<button type="button" class="eu-btn eu-btn--secondary" data-decide="pendiente" data-label="Guardar pendiente"><i data-lucide="clock"></i>Guardar pendiente</button>'
        : '<button type="button" class="eu-btn eu-btn--secondary" data-decide="pendiente" data-override="1" data-label="Agregar de todas formas"><i data-lucide="plus"></i>Agregar de todas formas</button>') +
      '</div><div id="ec-card-wrap"></div>';
    icons();
    requestAnimationFrame(function () { requestAnimationFrame(function () { var f = $('ring-fill'); if (f) f.style.strokeDashoffset = circ - (r.score / 100) * circ; }); });
    loadEC();
  }
  function loadEC() {
    var precio = item.precio_estimado || 0;
    if (!precio) return;
    fetch(API + '/ec-status?precio=' + precio).then(function (r) { return r.json(); }).then(function (d) {
      var wrap = $('ec-card-wrap'); if (!wrap) return;
      var pct = Math.min(d.pct_balance || 0, 100), pctTxt = d.pct_balance !== null ? d.pct_balance + '%' : '—';
      var pt = pct <= 30 ? 'success' : pct <= 60 ? 'warning' : 'danger';
      var alertT, alertIc, alertTxt;
      if (d.ec_sugerido === 0) { alertT = 'warning'; alertIc = 'info'; alertTxt = 'El artículo no tiene precio registrado. Edita el precio para calcular el EC necesario.'; }
      else if (d.puede_pagar && d.pct_balance <= 30) { alertT = 'success'; alertIc = 'circle-check'; alertTxt = 'Tienes EC suficientes y la compra usa solo el <b>' + pctTxt + '</b> de tu balance — decisión prudente dentro del sistema.'; }
      else if (d.puede_pagar && d.pct_balance <= 60) { alertT = 'warning'; alertIc = 'triangle-alert'; alertTxt = 'Puedes pagar, pero usarías el <b>' + pctTxt + '</b> de tu balance EC. Considera si merece ese porcentaje de tu esfuerzo acumulado.'; }
      else if (d.puede_pagar) { alertT = 'warning'; alertIc = 'triangle-alert'; alertTxt = 'La compra consumiría <b>' + pctTxt + '</b> de tu balance EC — más de la mitad de tu esfuerzo acumulado. Evalúa si el artículo lo justifica.'; }
      else { alertT = 'danger'; alertIc = 'circle-x'; alertTxt = 'Te faltan <b>' + (d.ec_sugerido - d.balance) + ' EC</b> para completar esta compra. Sigue acumulando — con actividad diaria lo alcanzas en días.'; }
      wrap.innerHTML = '<section class="eu-card eu-card--inset wl-ec" aria-labelledby="wl-ec-t">' +
        '<div class="eu-hstack wl-ec-hd"><span class="eu-row-ic wl-ec-ic"><i data-lucide="coins"></i></span><div><div class="t-card" id="wl-ec-t">¿Comprar con Euda-Credits (EC)?</div><div class="t-meta">Gamificación · tasa: 1 EC = $' + d.ec_rate + ' MXN</div></div></div>' +
        '<div class="eu-grid-3 wl-ec-stats">' +
        '<div><div class="t-data wl-ec-v">' + d.balance.toLocaleString('es-MX') + '</div><div class="t-meta">Tu balance EC</div></div>' +
        '<div><div class="t-data wl-ec-v' + (d.puede_pagar ? ' fg-ec' : ' fg-danger') + '">' + d.ec_sugerido.toLocaleString('es-MX') + '</div><div class="t-meta">EC sugerido</div></div>' +
        '<div data-tone="' + pt + '"><div class="t-data wl-ec-v wl-tone-fg">' + pctTxt + '</div><div class="t-meta">Del balance</div></div></div>' +
        (d.pct_balance !== null ? '<div class="eu-progress wl-ec-bar" data-tone="' + pt + '" role="progressbar" aria-label="Porcentaje del balance" aria-valuenow="' + Math.round(pct) + '" aria-valuemax="100"><i style="width:' + pct + '%"></i></div>' : '') +
        '<p class="wl-alert" data-tone="' + alertT + '"><i data-lucide="' + alertIc + '"></i><span>' + alertTxt + '</span></p>' +
        '<p class="t-meta wl-ec-note">' + money(precio) + ' MXN ÷ $' + d.ec_rate + '/EC = <b class="fg-ec">' + d.ec_sugerido + ' EC sugeridos</b></p>' +
        '<button type="button" class="eu-btn eu-btn--primary eu-btn--block" data-ec="' + d.ec_sugerido + '"' + (d.puede_pagar ? '' : ' disabled') + '><i data-lucide="coins"></i>' +
        (d.puede_pagar ? 'Comprar con ' + d.ec_sugerido + ' EC' : 'EC insuficientes (necesitas ' + (d.ec_sugerido - d.balance) + ' más)') + '</button></section>';
      icons();
    }).catch(function () { /* la tarjeta EC es opcional */ });
  }
  $('wl-result').addEventListener('click', function (e) {
    var d = e.target.closest('[data-decide]'), ec = e.target.closest('[data-ec]');
    if (d) {
      d.disabled = true;
      post(API + '/item/' + itemId + '/decide', { decision: d.dataset.decide, override: !!d.dataset.override }).then(function () {
        toast(d.dataset.label + ' — guardado en tu wishlist', 'ok'); resetQuiz(); setTab('list');
      }).catch(function () { toast('Sin conexión', 'err'); d.disabled = false; });
    } else if (ec) {
      var n = +ec.dataset.ec;
      euConfirm('¿Pagar ' + n + ' EC por «' + item.nombre + '»? Se descontarán de tu balance.', { confirmLabel: 'Pagar ' + n + ' EC' }).then(function (ok) {
        if (!ok) return;
        ec.disabled = true;
        post(API + '/item/' + itemId + '/comprar-ec', { ec_cantidad: n }).then(function (r) {
          if (!r.ok) { toast(r.error || 'Error al procesar EC', 'err'); ec.disabled = false; return; }
          toast(r.ec_gastado + ' EC deducidos — nuevo balance: ' + r.nuevo_balance + ' EC', 'ok'); resetQuiz(); setTab('list');
        }).catch(function () { toast('Sin conexión', 'err'); ec.disabled = false; });
      });
    }
  });
  function resetQuiz() {
    itemId = null; item = {}; ans = {}; result = null;
    $('f-item').reset(); $('usos-input').value = 1;
    $$('.wl-choice').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
    visibility(); $('wl-result').innerHTML = '';
    show(0);
  }

  /* ── Lista ──────────────────────────────────────────────────────────── */
  $$('[data-f]').forEach(function (c) {
    c.addEventListener('click', function () {
      listFilter = c.dataset.f;
      $$('[data-f]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      loadList();
    });
  });
  function loadList() {
    var url = API + '/items' + (listFilter === 'activos' ? '?view=activos' : listFilter ? '?estado=' + listFilter : '');
    return fetch(url).then(function (r) { return r.json(); }).then(function (items) { renderList(items || []); updateStats(); })
      .catch(function () { toast('Sin conexión', 'err'); });
  }
  function renderList(items) {
    var box = $('wl-list');
    if (!items.length) {
      box.innerHTML = '<div class="eu-card wl-span"><div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="package"></i></div><div class="t-card">Nada por aquí</div><p>Los artículos que evalúes con el protocolo aparecerán aquí para decidir si conviene comprarlos.</p></div></div>';
      icons(); return;
    }
    var circ = 2 * Math.PI * 16;
    box.innerHTML = items.map(function (it) {
      var has = it.score !== null && it.score !== undefined, est = ESTADO[it.estado] || [it.estado, ''], rec = REC[it.recomendacion];
      var off = has ? circ - (it.score / 100) * circ : circ;
      return '<article class="eu-card wl-item" data-tone="' + tone(has ? it.score : null) + '">' +
        '<div class="wl-mini" aria-label="' + (has ? 'Score ' + it.score : 'Sin evaluar') + '"><svg viewBox="0 0 44 44" aria-hidden="true"><circle class="wl-ring-bg" cx="22" cy="22" r="16"/><circle class="wl-ring-fg" cx="22" cy="22" r="16" stroke-dasharray="' + circ + '" stroke-dashoffset="' + off + '"/></svg><span class="t-data">' + (has ? it.score : '—') + '</span></div>' +
        '<div class="wl-item-bd"><div class="eu-between wl-item-top"><span class="t-ui wl-item-t">' + esc(it.nombre) + '</span><span class="t-data wl-price">' + (it.precio_estimado ? money(it.precio_estimado) : '—') + '</span></div>' +
        '<div class="t-meta">' + esc(it.categoria || '—') + (it.marca ? ' · ' + esc(it.marca) : '') + '</div>' +
        '<div class="wl-badges"><span class="eu-badge eu-badge--status ' + est[1] + '">' + est[0] + '</span>' +
        (rec ? '<span class="eu-badge" data-tone="' + rec.t + '">' + rec.short + '</span>' : '') +
        (it.decision_override ? '<span class="eu-badge eu-badge--warning">override</span>' : '') +
        (it.comprar_con_ec ? '<span class="eu-badge eu-badge--ec"><i data-lucide="coins"></i>' + it.ec_pagado + ' EC</span>' : '') + '</div></div>' +
        '<div class="wl-item-actions">' +
        (it.estado !== 'comprado' ? '<button type="button" class="eu-iconbtn" data-mark="comprado" data-id="' + it.id + '" aria-label="Marcar como comprado: ' + esc(it.nombre) + '" title="Marcar como comprado"><i data-lucide="check"></i></button>'
          : '<button type="button" class="eu-iconbtn" data-mark="pendiente" data-id="' + it.id + '" aria-label="Regresar a la wishlist: ' + esc(it.nombre) + '" title="Regresar a la wishlist"><i data-lucide="undo-2"></i></button>') +
        (it.estado !== 'descartado' ? '<button type="button" class="eu-iconbtn" data-mark="descartado" data-id="' + it.id + '" aria-label="Descartar: ' + esc(it.nombre) + '" title="Descartar"><i data-lucide="x"></i></button>' : '') +
        '<button type="button" class="eu-iconbtn wl-del" data-del="' + it.id + '" aria-label="Eliminar: ' + esc(it.nombre) + '" title="Eliminar"><i data-lucide="trash-2"></i></button></div></article>';
    }).join('');
    icons();
  }
  $('wl-list').addEventListener('click', function (e) {
    var m = e.target.closest('[data-mark]'), d = e.target.closest('[data-del]');
    if (m) {
      m.disabled = true;
      post(API + '/item/' + m.dataset.id + '/decide', { decision: m.dataset.mark }).then(function (r) {
        if (!r || !r.ok) throw new Error();
        toast(m.dataset.mark === 'comprado' ? 'Marcado como comprado' : m.dataset.mark === 'pendiente' ? 'Devuelto a la wishlist' : 'Descartado', 'ok');
        loadList();
      }).catch(function () { toast('Error al actualizar. Intenta de nuevo.', 'err'); m.disabled = false; });
    } else if (d) {
      euConfirm('¿Eliminar este artículo de tu wishlist?', { confirmLabel: 'Eliminar' }).then(function (ok) {
        if (!ok) return;
        fetch(API + '/item/' + d.dataset.del, { method: 'DELETE' }).then(function () { toast('Artículo eliminado'); loadList(); })
          .catch(function () { toast('Sin conexión', 'err'); });
      });
    }
  });
  function updateStats() {
    fetch(API + '/items').then(function (r) { return r.json(); }).then(function (all) {
      var comp = all.filter(function (i) { return i.estado === 'comprado'; }).length;
      var rej = all.filter(function (i) { return i.estado === 'descartado'; });
      var saved = rej.reduce(function (s, i) { return s + (i.precio_estimado || 0); }, 0);
      var v = $$('.wl-stats .eu-stat-val');
      v[0].textContent = all.length; v[1].textContent = comp; v[2].textContent = rej.length; v[3].textContent = saved ? money(saved) : '—';
    }).catch(function () {});
  }

  show(0, true);
  updateStats();
})();
