/* Prioridades (wishlist de Oikonomia) — Design System V2. Remates · Wishlist
   S1: grupos por mes_objetivo, franja viva (pendiente, este mes contra «libre
   para deseos», comprado en el año), «Comprado» con el precio en línea,
   «Mover de mes», «o N EC» y menú ⋯; alta de artículos a través del
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

  /* ── Remates · Wishlist S1: grupos por mes, franja viva y acciones en la fila ── */
  var MES = root.dataset.mes, ANIO = root.dataset.anio;
  var MESES = JSON.parse(($('pr-meses') || {}).textContent || '[]');
  var LIBRE = root.dataset.libre != null ? +root.dataset.libre : null;
  var balance = +root.dataset.ecBalance || 0;
  function money(n) { return '$' + Math.round(n || 0).toLocaleString('en-US'); }
  function mesMas(m, n) { var y = +m.slice(0, 4), k = +m.slice(5, 7) + n; y += Math.floor((k - 1) / 12); k = (k - 1) % 12 + 1; return y + '-' + (k < 10 ? '0' : '') + k; }
  function grupoDe(m) { if (!m || m.length !== 7) return 'sin'; if (m <= MES) return 'este'; return m === mesMas(MES, 1) ? 'prox' : 'despues'; }
  function rows(sel) { return $$('.pr-row' + (sel || '')); }
  function insertar(list, row) {
    var k = row.dataset.orden, sig = $$('.pr-row', list).filter(function (r) { return r !== row && r.dataset.orden > k; })[0];
    list.insertBefore(row, sig || null);
  }

  /* Recalcula la franja, el antetítulo y los conteos desde las filas */
  function recalc() {
    var pend = rows('[data-estado="Pendiente"]'), por = { Alta: 0, Media: 0, Baja: 0 }, total = 0, este = 0;
    pend.forEach(function (r) { var v = +r.dataset.precio; total += v; if (por[r.dataset.prioridad] != null) por[r.dataset.prioridad] += v; if (grupoDe(r.dataset.mes) === 'este') este += v; });
    var eb = document.querySelector('.pr-hd .t-eyebrow');
    if (eb) eb.textContent = pend.length + ' pendiente' + (pend.length !== 1 ? 's' : '') + ' · ' + money(total);
    $('pr-pend').textContent = money(total);
    Object.keys(por).forEach(function (k) {
      var seg = document.querySelector('#pr-stack [data-p="' + k + '"]'); if (seg) seg.style.flexGrow = por[k];
      var lg = document.querySelector('[data-leg="' + k + '"]'); if (lg) lg.textContent = money(por[k]);
    });
    $('pr-stack').setAttribute('aria-label', 'Alta ' + money(por.Alta) + ', Media ' + money(por.Media) + ', Baja ' + money(por.Baja));
    if ($('pr-este')) {
      $('pr-este').textContent = money(este);
      var pct = LIBRE > 0 ? este / LIBRE * 100 : (este ? 100 : 0), bar = $('pr-este-bar');
      bar.className = 'eu-progress eu-progress--' + (pct > 100 ? 'danger' : pct > 85 ? 'warning' : 'success') + ' pr-este-bar';
      bar.setAttribute('aria-valuenow', Math.round(Math.min(pct, 100)));
      bar.querySelector('i').style.width = Math.min(pct, 100) + '%';
    }
    var compr = rows('[data-estado="Comprado"]').filter(function (r) { return r.dataset.comprado === ANIO; });
    $('pr-anio').textContent = money(compr.reduce(function (s, r) { return s + +r.dataset.real; }, 0));
    $('pr-anio-n').textContent = compr.length;
    $$('.pr-group').forEach(function (g) {
      var rs = $$('.pr-row', g);
      g.hidden = !rs.length;
      g.querySelector('[data-gn]').textContent = rs.length;
      g.querySelector('[data-gt]').textContent = money(rs.reduce(function (s, r) { return s + +r.dataset.precio; }, 0));
    });
    $$('.pr-done').forEach(function (d) { var n = $$('.pr-row', d).length; d.hidden = !n; d.querySelector('[data-dn]').textContent = n; });
  }

  /* Menús (Mover de mes y ⋯): uno abierto a la vez, flechas, Esc y foco de vuelta */
  var abierto = null;
  function cerrarMenu(foco) {
    if (!abierto) return;
    abierto.menu.hidden = true; abierto.btn.setAttribute('aria-expanded', 'false');
    if (foco) abierto.btn.focus();
    abierto = null;
  }
  function abrirMenu(btn) {
    var menu = btn.parentNode.querySelector('.pr-menu');
    if (abierto && abierto.btn === btn) { cerrarMenu(true); return; }
    cerrarMenu(false);
    if (menu.dataset.kind === 'mover') {
      var actual = btn.closest('.pr-row').dataset.mes;
      menu.innerHTML = MESES.filter(function (m) { return m.mes !== actual; }).map(function (m, i) {
        return '<button type="button" role="menuitem" class="js-mover" data-mes="' + m.mes + '"><i data-lucide="calendar"></i>' + (i === 0 && m.mes === MES ? 'Este mes · ' : '') + esc(m.label) + '</button>';
      }).join('');
      icons();
    }
    menu.hidden = false; btn.setAttribute('aria-expanded', 'true');
    abierto = { btn: btn, menu: menu };
    var first = menu.querySelector('[role=menuitem]'); if (first) first.focus();
  }
  document.addEventListener('click', function (e) { if (abierto && !abierto.menu.contains(e.target) && e.target.closest('.js-menu') !== abierto.btn) cerrarMenu(false); });
  root.addEventListener('keydown', function (e) {
    if (!abierto || !abierto.menu.contains(document.activeElement)) return;
    var its = $$('[role=menuitem]', abierto.menu), i = its.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); its[(i + 1) % its.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); its[(i - 1 + its.length) % its.length].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); its[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); its[its.length - 1].focus(); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrarMenu(true); }
    else if (e.key === 'Tab') cerrarMenu(false);
  });

  /* Pasa una fila pendiente a Comprado (precio real o EC) sin recargar */
  function aComprado(row, real, ec) {
    row.dataset.estado = 'Comprado'; row.dataset.real = real; row.dataset.comprado = ANIO; row.classList.add('is-done');
    ['.pr-buy', '.js-comprar', '.js-ec', '.js-descartar'].forEach(function (s) { var n = row.querySelector(s); if (n) n.remove(); });
    var mv = row.querySelector('.pr-menu[data-kind="mover"]'); if (mv) mv.parentNode.remove();
    row.querySelector('.pr-price').textContent = money(ec ? +row.dataset.precio : real);
    if (ec) row.querySelector('.pr-row-t').insertAdjacentHTML('beforeend', '<span class="eu-badge eu-badge--ec"><i data-lucide="coins"></i>' + ec + ' EC</span>');
    var list = document.querySelector('[data-list="Comprado"]'); list.insertBefore(row, list.firstChild);
    icons(); recalc();
  }
  function afterEC() {   // con menos EC, algunas filas ya no se pueden pagar
    root.dataset.ecBalance = balance;
    $$('.js-ec').forEach(function (b) { if (+b.dataset.ec > balance) b.remove(); });
  }

  root.addEventListener('click', function (e) {
    var t = e.target.closest('button'); if (!t || !root.contains(t)) return;
    var row = t.closest('.pr-row'), id = row && row.dataset.id;
    if (t.classList.contains('js-menu')) { abrirMenu(t); return; }
    if (t.classList.contains('js-comprar')) {
      var form = row.querySelector('.pr-buy'), open = form.hidden;
      form.hidden = !open; t.setAttribute('aria-expanded', String(open));
      if (open) { var inp = form.querySelector('input'); inp.focus(); inp.select(); }
      return;
    }
    if (t.classList.contains('js-buy-x')) { row.querySelector('.pr-buy').hidden = true; var c = row.querySelector('.js-comprar'); c.setAttribute('aria-expanded', 'false'); c.focus(); return; }
    if (t.classList.contains('js-ec')) {
      var ec = +t.dataset.ec, nombre = row.dataset.nombre;
      euConfirm('¿Pagar ' + ec + ' EC por «' + nombre + '»? Se descontarán de tu balance y quedará como comprado.', { confirmLabel: 'Pagar ' + ec + ' EC' }).then(function (ok) {
        if (!ok) return;
        post(BASE + '/api/comprar-ec/' + id).then(function (d) {
          if (!d.ok) { toast(d.error || 'No se pudo pagar', 'err'); return; }
          balance = d.balance; afterEC(); aComprado(row, 0, d.ec); toast('Comprado con ' + d.ec + ' EC', 'win');
        }).catch(function () { toast('Sin conexión', 'err'); });
      });
      return;
    }
    if (t.classList.contains('js-mover')) {
      var mes = t.dataset.mes, label = t.textContent, trig = abierto && abierto.btn;
      cerrarMenu(false);
      fetch(BASE + '/api/get/' + id).then(function (r) { return r.json(); }).then(function (d) {
        d.mes_objetivo = mes;
        return post(BASE + '/api/update/' + id, d);
      }).then(function () {
        row.dataset.mes = mes;
        $$('.pr-row-t .eu-badge', row).forEach(function (b) { if (/^Desde /.test(b.textContent)) b.remove(); });
        insertar(document.querySelector('[data-list="' + grupoDe(mes) + '"]'), row);
        recalc();
        if (trig) trig.focus();
        toast('Movido a ' + label.replace('Este mes · ', ''), 'ok');
      }).catch(function () { toast('Sin conexión', 'err'); });
      return;
    }
    if (t.classList.contains('js-edit')) {
      cerrarMenu(false);
      fetch(BASE + '/api/get/' + id).then(function (r) { return r.json(); }).then(function (d) {
        $('editId').value = id;
        $('fNombre').value = d.nombre || ''; $('fCategoria').value = d.categoria || ''; $('fPrioridad').value = d.prioridad || 'Media';
        $('fPrecio').value = d.precio_estimado || ''; $('fMes').value = d.mes_objetivo || ''; $('fTienda').value = d.tienda || '';
        $('fUrl').value = d.url || ''; $('fNotas').value = d.notas || ''; $('fEstado').value = d.estado || 'Pendiente';
        euModal.open('m-edit'); setTimeout(function () { $('fNombre').focus(); }, 20);
      }).catch(function () { toast('Sin conexión', 'err'); });
      return;
    }
    if (t.classList.contains('js-descartar')) {
      cerrarMenu(false);
      euConfirm('¿Descartar «' + row.dataset.nombre + '»?', { danger: false, confirmLabel: 'Descartar' }).then(function (ok) {
        if (ok) post(BASE + '/api/descartar/' + id).then(function () { toast('Descartado'); reload(); });
      });
      return;
    }
    if (t.classList.contains('js-del')) {
      cerrarMenu(false);
      euConfirm('¿Eliminar definitivamente «' + row.dataset.nombre + '»?', { confirmLabel: 'Eliminar' }).then(function (ok) {
        if (ok) post(BASE + '/api/delete/' + id).then(function () { row.remove(); recalc(); toast('Eliminado'); });
      });
    }
  });
  root.addEventListener('submit', function (e) {
    var form = e.target.closest('.pr-buy'); if (!form) return;
    e.preventDefault();
    var row = form.closest('.pr-row'), real = parseFloat(form.querySelector('input').value);
    if (!(real >= 0)) { toast('Escribe el precio que pagaste', 'err'); form.querySelector('input').focus(); return; }
    post(BASE + '/api/comprar/' + row.dataset.id, { precio_real: real }).then(function () { aComprado(row, real, 0); toast('¡Comprado!', 'win'); })
      .catch(function () { toast('Sin conexión', 'err'); });
  });
  root.addEventListener('keydown', function (e) {
    var form = e.target.closest && e.target.closest('.pr-buy');
    if (form && e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); form.querySelector('.js-buy-x').click(); }
  });

  $('f-edit').addEventListener('submit', function (e) {
    e.preventDefault();
    var body = readFields('f');
    if (!body.nombre) { toast('El nombre es requerido', 'err'); $('fNombre').focus(); return; }
    body.estado = $('fEstado').value;
    post(BASE + '/api/update/' + $('editId').value, body).then(function () { euModal.close('m-edit'); toast('Guardado', 'ok'); reload(); })
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
    /* Aviso de duplicado: no bloquea, solo pregunta */
    fetch(BASE + '/api/existe?nombre=' + encodeURIComponent(item.nombre)).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.existe) return show(1);
      euConfirm('Ya tienes «' + d.existe.nombre + '» en tu lista (' + (d.existe.estado || 'sin estado') + '). ¿Agregarlo otra vez?',
        { danger: false, confirmLabel: 'Agregar de todos modos' }).then(function (ok) { if (ok) show(1); });
    }).catch(function () { show(1); });
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
