/* Plantas — handoff Plantas y Ajustes (S1–S2).
   «Hoy»: todos los cuidados vencidos o urgentes, con «Aún húmeda» en riego
   y «Regar las N» por entorno; filtro por entorno y cuadrícula compacta con
   el siguiente cuidado; panel de la planta con pestañas Cuidados · Fotos ·
   Historial · Doctor (380px en escritorio, hoja en móvil). «Editar datos»
   abre m-planta (corto; lo avanzado plegado). Endpoints de siempre. */
(function () {
  'use strict';
  var root = document.getElementById('pl');
  if (!root) return;
  var BASE = '/plantas';
  var PLANTAS = JSON.parse(document.getElementById('pl-data').textContent || '[]');
  var HOY = JSON.parse((document.getElementById('pl-hoy-data') || {}).textContent || '[]');
  var ST = {
    vencido: ['Vencido', 'eu-badge--danger', 'danger'], urgente: ['Urgente', 'eu-badge--warning', 'warning'],
    proximo: ['Próximo', 'eu-badge--brand', 'brand'], nominal: ['Al día', 'eu-badge--success', 'success'],
  };
  var IA = JSON.parse((document.getElementById('pl-ia') || {}).textContent || 'false');
  var TODAY = JSON.parse((document.getElementById('pl-today') || {}).textContent || 'null');
  var env = 'todas', sel = null, opener = null, fotoFile = null, sugTimer = null;
  var MOVIL = window.matchMedia ? window.matchMedia('(max-width:1023px)') : { matches: false };

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function jpost(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); });
  }
  function planta(id) { return PLANTAS.filter(function (x) { return x.id === +id; })[0]; }

  /* Cuándo toca, en palabras: «hoy», «mañana», «en 5 d», «hace 2 d». */
  function cuando(dias, tipo) {
    if (dias === 0) return 'hoy';
    if (dias === 1) return 'mañana';
    if (dias === -1) return 'ayer';
    if (dias < 0) return 'hace ' + (-dias) + ' d';
    if (tipo === 'trasplante' && dias > 45) return 'en ' + Math.round(dias / 30) + ' meses';
    return 'en ' + dias + ' d';
  }
  var EXTRA_IC = { fertilizar: 'flask-conical', rotar: 'rotate-cw', limpiar: 'sparkles', plagas: 'bug', tratamiento: 'spray-can' };
  var EXTRA_BTN = { fertilizar: 'Fertilicé', rotar: 'Roté', limpiar: 'Limpié', plagas: 'Revisé', tratamiento: 'Apliqué' };
  var BTN = { riego: 'Regué', trasplante: 'Trasplanté' };
  /* Normaliza riego / trasplante / cuidados extra a una misma forma. */
  function careItems(p) {
    var r = {
      tipo: 'riego', label: 'Riego', icon: 'droplet', btn: 'Regué', status: p.riego_status, pct: p.riego_pct, dias: p.riego_dias, prox: p.riego_proxima,
      regla: (p.riego_interval_efectivo !== p.dias_riego ? 'cada ' + p.riego_interval_efectivo + ' d (ajustado; base ' + p.dias_riego + ' d)' : 'cada ' + p.dias_riego + ' d') +
        (p.riego_pospuesta ? ' · pospuesto (aún húmeda)' : '')
    };
    var t = { tipo: 'trasplante', label: 'Trasplante', icon: 'sprout', btn: 'Trasplanté', status: p.trasplante_status, pct: p.trasplante_pct,
      dias: p.trasplante_dias, prox: p.trasplante_proxima, regla: 'cada ' + p.meses_trasplante + ' meses' };
    return [r, t].concat((p.cuidados || []).map(function (c) {
      return { tipo: c.tipo, label: c.label, icon: EXTRA_IC[c.tipo] || 'leaf', btn: EXTRA_BTN[c.tipo] || 'Hecho', status: c.status,
        pct: c.pct, dias: c.dias, prox: c.proxima, regla: 'cada ' + c.cada_dias + ' d' + (c.nota ? ' · ' + c.nota : ''), pausado: c.pausado, extra: true };
    }));
  }
  /* El siguiente cuidado de una planta (el más cercano; lo pausado no cuenta). */
  function siguiente(p) {
    var its = careItems(p).filter(function (it) { return !it.pausado; });
    its.sort(function (a, b) { return a.dias - b.dias || (a.tipo === 'riego' ? -1 : 1); });
    return its[0];
  }
  function thumb(p, cls) {
    if (p.foto) return '<img class="' + cls + '" src="' + BASE + '/foto/' + encodeURIComponent(p.foto) + '" alt="" loading="lazy">';
    if (p.ref_foto) return '<img class="' + cls + '" src="' + esc(p.ref_foto) + '" alt="" loading="lazy" referrerpolicy="no-referrer">';
    return '<span class="' + cls + ' pl-ph" aria-hidden="true"><i data-lucide="flower-2"></i></span>';
  }
  function entornoTxt(p) { return p.entorno === 'balcon' ? 'balcón' : 'interior'; }

  /* ── «Hoy» (nota 1) ─────────────────────────────────────────────────── */
  function renderHoy() {
    var ul = $('pl-hoy-list'), n = HOY.length;
    $('pl-hoy-n').textContent = n || '';
    $('pl-hoy').classList.toggle('is-late', HOY.some(function (h) { return h.status === 'vencido'; }));
    if (!n) {
      var nx = PLANTAS.map(function (p) { return { p: p, it: siguiente(p) }; }).filter(function (x) { return x.it; })
        .sort(function (a, b) { return a.it.dias - b.it.dias; })[0];
      ul.innerHTML = '<li class="pl-hoy-ok"><i data-lucide="circle-check"></i><span>Todas al día.' +
        (nx ? ' Siguiente: ' + esc(nx.p.nombre) + ', ' + esc(nx.it.label.toLowerCase()) + ' ' + cuando(nx.it.dias, nx.it.tipo) + '.' : '') + '</span></li>';
    } else {
      ul.innerHTML = HOY.map(function (h) {
        var p = planta(h.planta_id) || { nombre: h.nombre };
        var late = h.dias < 0, btn = BTN[h.tipo] || EXTRA_BTN[h.tipo] || 'Hecho';
        return '<li class="pl-hoy-row" data-tone="' + ST[h.status][2] + '">' +
          '<button type="button" class="pl-hoy-th" data-open="' + h.planta_id + '" aria-label="Abrir ' + esc(p.nombre) + '">' + thumb(p, 'pl-hoy-img') + '</button>' +
          '<div class="pl-hoy-tx"><div class="pl-hoy-n"><b>' + esc(p.nombre) + '</b> · <span class="pl-hoy-care">' + esc(h.label.toLowerCase()) + '</span></div>' +
          '<div class="t-meta">' + (late ? 'tocaba ' : 'toca ') + cuando(h.dias, h.tipo) + ' · ' + esc(h.regla) + '</div></div>' +
          '<div class="pl-hoy-acts">' +
          (h.tipo === 'riego' && h.pospuesto_ok ? '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm" data-posponer="' + h.planta_id + '" title="Revisé la tierra y aún está húmeda: posponer 2 días" aria-label="' + esc(p.nombre) + ': aún está húmeda, posponer 2 días">Aún húmeda</button>' : '') +
          '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-care="' + h.tipo + '" data-id="' + h.planta_id + '" aria-label="' + btn + ' ' + esc(p.nombre) + '"><i data-lucide="check"></i>' + btn + '</button>' +
          '</div></li>';
      }).join('');
    }
    groupBar();
  }
  /* «N del balcón / de interior piden agua · Regar las N» cuando hay 2 o más
     (mismo criterio que /api/riego-grupo: riego que no está al día). */
  function groupBar() {
    var box = $('pl-group'); if (!box) return;
    var html = ['balcon', 'interior'].map(function (e) {
      var n = PLANTAS.filter(function (p) { return p.entorno === e && p.riego_status !== 'nominal'; }).length;
      return n >= 2 ? '<div class="pl-group-row"><span class="eu-grow">' + n + (e === 'balcon' ? ' del balcón' : ' de interior') + ' piden agua</span>' +
        '<button type="button" class="eu-btn eu-btn--primary eu-btn--sm" data-grupo="' + e + '"><i data-lucide="droplets"></i>Regar las ' + n + '</button></div>' : '';
    }).join('');
    box.innerHTML = html; box.hidden = !html;
  }

  /* ── Cuadrícula compacta (nota 2) ───────────────────────────────────── */
  function renderGrid() {
    var list = PLANTAS.filter(function (p) { return env === 'todas' || p.entorno === env; }), box = $('pl-grid');
    if (!list.length) {
      box.innerHTML = PLANTAS.length
        ? window.euEmptyFilter('Ninguna planta en ' + (env === 'balcon' ? 'el balcón' : 'interior') + '.', 'Sin ese filtro hay ' + PLANTAS.length + '.',
            { key: 'todas', label: env === 'balcon' ? 'Balcón' : 'Interior' }, 'pl-span')
        : '<div class="eu-card pl-span">' + window.euEmpty('sprout', 'Aún no agregas ninguna planta', 'Agrega la primera con el botón de arriba.', false,
            '<button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Nueva planta</button>') + '</div>';
      icons(); return;
    }
    box.innerHTML = list.map(function (p) {
      var it = siguiente(p), tone = it ? ST[it.status][2] : 'success';
      var next = it ? esc(it.label.toLowerCase()) + ' ' + cuando(it.dias, it.tipo) : 'al día';
      return '<button type="button" class="pl-tile" data-open="' + p.id + '" data-tone="' + tone + '"' + (sel === p.id ? ' aria-current="true"' : '') + '>' +
        thumb(p, 'pl-tile-img') + '<span class="pl-tile-bd"><span class="pl-tile-n">' + esc(p.nombre) + '</span>' +
        '<span class="pl-tile-next">' + next + '</span></span></button>';
    }).join('');
    icons();
  }

  /* ── Panel de la planta (nota 3) ────────────────────────────────────── */
  var tab = 'care';
  function careHTML(p, it) {
    var pct = Math.min(1, it.pct || 0) * 100, f = it.prox ? fmtFecha(it.prox) : '';
    var acts = (it.tipo === 'riego' && it.status !== 'nominal'
        ? '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm" data-posponer="' + p.id + '" aria-label="' + esc(p.nombre) + ': aún está húmeda, posponer 2 días">Aún húmeda</button>' : '') +
      (it.pausado ? '' : '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-care="' + it.tipo + '" data-id="' + p.id + '" aria-label="' + it.btn + ' ' + esc(p.nombre) + '"><i data-lucide="check"></i>' + it.btn + '</button>');
    return '<div class="pl-pp-care" data-tone="' + ST[it.status][2] + '">' +
      '<div class="eu-between"><span class="t-ui"><i data-lucide="' + it.icon + '"></i>' + esc(it.label) + '</span>' +
      '<span class="pl-pp-when">' + (it.pausado ? 'en pausa (invierno)' : (it.dias < 0 ? 'tocaba ' : '') + cuando(it.dias, it.tipo)) + '</span></div>' +
      '<div class="eu-progress eu-progress--thin pl-prog" aria-hidden="true"><i style="width:' + pct.toFixed(1) + '%"></i></div>' +
      '<div class="pl-pp-row"><span class="t-meta">' + esc(it.regla) + (f && !it.pausado ? ' · próxima ' + f : '') + '</span><span class="pl-pp-acts">' + acts + '</span></div></div>';
  }
  function renderPanel() {
    var p = planta(sel), pan = $('pl-panel');
    if (!p) { root.classList.remove('has-panel'); return; }
    root.classList.add('has-panel');
    $('pp-cover').innerHTML = thumb(p, 'pl-pp-img');
    $('pp-name').textContent = p.nombre;
    $('pp-sub').innerHTML = [p.especie_cientifica && p.especie_cientifica !== p.especie ? esc(p.especie) + ' <i>' + esc(p.especie_cientifica) + '</i>' : esc(p.especie),
      esc(p.ubicacion), entornoTxt(p)].filter(Boolean).join(' · ');
    $('pp-care-list').innerHTML = careItems(p).map(function (it) { return careHTML(p, it); }).join('');
    var nt = $('pp-notas'); nt.textContent = p.notas || ''; nt.hidden = !p.notas;
    fillOtra(p);
    icons();
  }
  function setTab(t, foco) {
    if (t === 'doctor' && !$('pp-doctor')) t = 'care';
    tab = t;
    $$('[data-pp-tab]').forEach(function (b) {
      var on = b.dataset.ppTab === t;
      b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1;
      $(b.getAttribute('aria-controls')).hidden = !on;
      if (on && foco) b.focus();
    });
    if (t === 'fotos') loadFotos(sel);
    if (t === 'hist') loadHist(sel);
    if (t === 'doctor') prepDoctor(sel);
  }
  /* Panel con euDialog: en móvil es modal (hoja, foco atrapado); en
     escritorio, un panel lateral no modal. En ambos, Esc lo cierra y el
     foco vuelve a la tarjeta. */
  function openPanel(id, from) {
    var pan = $('pl-panel'), cambio = sel !== null;
    sel = +id;
    renderPanel(); renderGrid(); setTab('care');
    if (cambio && window.euDialog.isOpen(pan)) { if (from) $('pp-name').focus(); return; }
    window.euDialog.open(pan, from || null, {
      box: pan.querySelector('.pl-panel-in'), modal: MOVIL.matches, focus: from || MOVIL.matches ? $('pp-name') : false,
      onClose: function () {
        var back = sel; sel = null; renderPanel(); renderGrid();
        var t = from && document.contains(from) ? from
          : (document.querySelector('.pl-tile[data-open="' + back + '"]') || document.querySelector('[data-open="' + back + '"]'));
        if (t) t.focus();
      }
    });
  }
  function closePanel() { var pan = $('pl-panel'); if (window.euDialog.isOpen(pan)) window.euDialog.close(pan, { noFocus: true }); else { sel = null; renderPanel(); renderGrid(); } }
  $('pl-panel').addEventListener('click', function (e) {
    var t = e.target.closest('[data-pp-tab]'); if (t) { setTab(t.dataset.ppTab); return; }
    if (e.target.closest('.js-pp-close')) { closePanel(); return; }
    if (e.target.closest('.js-pp-edit')) { var p = planta(sel); if (p) fill(p); }
  });
  $('pl-panel').addEventListener('keydown', function (e) {
    var t = e.target.closest && e.target.closest('[data-pp-tab]');
    if (t && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
      var tabs = $$('[data-pp-tab]'), i = tabs.indexOf(t) + (e.key === 'ArrowRight' ? 1 : -1);
      setTab(tabs[(i + tabs.length) % tabs.length].dataset.ppTab, true); e.preventDefault();
    }
  });
  function apply(d) {
    PLANTAS = d.state.plantas; HOY = d.state.hoy || [];
    var n = HOY.length, eb = root.querySelector('.eu-page-eb');
    if (eb) eb.textContent = PLANTAS.length + ' planta' + (PLANTAS.length !== 1 ? 's' : '') + ' · ' + (n ? n + ' por atender hoy' : 'todas al día');
    renderHoy(); renderGrid(); if (sel !== null) { if (planta(sel)) renderPanel(); else closePanel(); }
  }

  $$('[data-env]').forEach(function (b) {
    b.addEventListener('click', function () {
      env = b.dataset.env;
      $$('[data-env]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      renderGrid();
    });
  });
  root.addEventListener('click', function (e) {
    if (e.target.closest('.js-new')) { openNew(); return; }
    if (e.target.closest('.js-empty-drop')) { var t = document.querySelector('[data-env="todas"]'); if (t) t.click(); return; }
    var op = e.target.closest('[data-open]'); if (op) { openPanel(op.dataset.open, op); return; }
    var pp = e.target.closest('[data-posponer]');
    if (pp) {
      pp.disabled = true;
      fetch(BASE + '/api/plantas/' + pp.dataset.posponer + '/posponer', { method: 'POST' }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast('Error al guardar', 'err'); pp.disabled = false; return; }
        apply(d); toast(d.msg || 'Riego pospuesto', 'ok');
      }).catch(function () { toast('Sin conexión', 'err'); pp.disabled = false; });
      return;
    }
    var g = e.target.closest('[data-grupo]');
    if (g) {
      g.disabled = true;
      jpost(BASE + '/api/riego-grupo', { entorno: g.dataset.grupo }).then(function (d) {
        if (!d.ok) { toast(d.error || 'Error al guardar', 'err'); g.disabled = false; return; }
        apply(d); toast(d.msg + (d.gam && d.gam.xp ? ' · +' + d.gam.xp + ' XP' : ''), d.gam ? 'win' : 'ok');
        if (d.gam && window.euGam) euGam(d.gam);
      }).catch(function () { toast('Sin conexión', 'err'); g.disabled = false; });
      return;
    }
    var c = e.target.closest('[data-care]'); if (!c) return;
    var tipo = c.dataset.care, id = c.dataset.id, enPanel = !!c.closest('#pl-panel'); c.disabled = true;
    fetch(BASE + '/api/plantas/' + id + '/cuidado/' + tipo, { method: 'POST' }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast('Error al guardar', 'err'); c.disabled = false; return; }
      apply(d);
      if (d.ya_registrado) { toast(d.msg || 'Ya estaba registrado hoy', 'ok'); return; }
      toast(d.gam && d.gam.xp ? '+' + d.gam.xp + ' XP · +' + d.gam.ec + ' EC' : 'Registrado', d.gam && d.gam.xp ? 'win' : 'ok');
      var nb = enPanel ? document.querySelector('#pl-panel [data-care="' + tipo + '"]') : $('pl-hoy-list').querySelector('button');
      if (nb) nb.focus();
      if (d.gam && window.euGam) euGam(d.gam, { el: nb });
    }).catch(function () { toast('Sin conexión', 'err'); c.disabled = false; });
  });
  var tb = document.querySelector('.eu-topbar .js-new'); if (tb) tb.addEventListener('click', openNew);

  /* ── Formulario ─────────────────────────────────────────────────────── */
  function setFoto(url) {
    var img = $('pl-photo-img');
    if (url) img.src = url; else img.removeAttribute('src');
    img.hidden = !url; $('pl-photo-empty').hidden = !!url;
    $('pl-photo-caption').textContent = url ? 'Foto lista' : 'Sin foto';
  }
  root.ownerDocument.querySelector('#m-planta .js-photo').addEventListener('click', function () { $('pl-photo-input').click(); });
  $('pl-photo-input').addEventListener('change', function () {
    var f = this.files && this.files[0]; if (!f) return;
    fotoFile = f;
    var rd = new FileReader(); rd.onload = function (e) { setFoto(e.target.result); }; rd.readAsDataURL(f);
  });
  function hideSug() { $('pl-sugerencia').hidden = true; }
  function fill(p) {
    p = p || {};
    $('pl-id').value = p.id || '';
    $('pl-nombre').value = p.nombre || ''; $('pl-especie').value = p.especie || ''; $('pl-ubicacion').value = p.ubicacion || '';
    $('pl-dias-riego').value = p.dias_riego || 7; $('pl-meses-trasplante').value = p.meses_trasplante || 12;
    $('pl-notas').value = p.notas || ''; $('pl-photo-input').value = '';
    $('pl-entorno').value = p.entorno || 'interior'; $('pl-luz').value = p.luz || '';
    setTaxon(p.especie_cientifica ? { cient: p.especie_cientifica, comun: p.especie, foto: p.ref_foto, cred: p.ref_foto_credito } : null);
    $('pl-taxa').hidden = true; $('pl-taxa').innerHTML = '';
    $('pl-last-wrap').hidden = !!p.id; $('pl-last-riego').value = TODAY || ''; if (TODAY) $('pl-last-riego').max = TODAY;
    fillExtras(p); if ($('pl-ficha')) $('pl-ficha').hidden = true;
    $('pl-avanzado').open = !p.id;               // «Avanzado» abierto solo en el alta
    $('pl-delete-btn').hidden = !p.id;
    $('m-planta-t').textContent = p.id ? 'Editar planta' : 'Nueva planta';
    fotoFile = null; setFoto(p.foto ? BASE + '/foto/' + encodeURIComponent(p.foto) : null); hideSug();
    icons(); euModal.open('m-planta'); setTimeout(function () { $('pl-nombre').focus(); }, 20);
  }
  function openNew() { fill(null); }

  /* ── Confirmar la especie con fotos (iNaturalist, desde el navegador) ── */
  // Se consulta directo desde el navegador: no depende de que el servidor
  // (Railway) tenga salida a iNaturalist. Si falla o no hay internet, no se
  // muestra nada y el formulario funciona igual.
  var INAT = 'https://api.inaturalist.org/v1/taxa/autocomplete', PLANTAE = 47126;
  var RANGOS = { species: 1, subspecies: 1, variety: 1, form: 1, hybrid: 1, genus: 1 };
  var taxaTimer = null, taxaCtl = null, taxaCache = {}, TAXA = [];
  function setTaxon(t) {
    $('pl-cient').value = t ? t.cient : ''; $('pl-ref-foto').value = t ? (t.foto || '') : ''; $('pl-ref-cred').value = t ? (t.cred || '') : '';
    var box = $('pl-taxa-sel'); box.dataset.comun = t ? (t.comun || '') : '';
    box.hidden = !t;
    if (!t) { box.innerHTML = ''; return; }
    box.innerHTML = (t.foto ? '<img src="' + esc(t.foto) + '" alt="" referrerpolicy="no-referrer">' : '') +
      '<span class="eu-grow"><span class="t-ui"><i data-lucide="badge-check"></i> ' + esc(t.comun || t.cient) + '</span><i class="sci">' + esc(t.cient) + '</i>' +
      (t.cred ? '<span class="t-meta">Foto: ' + esc(t.cred) + ' · iNaturalist</span>' : '') + '</span>' +
      '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm js-taxon-cambiar">Cambiar</button>';
    icons();
  }
  function buscarTaxa(q) {
    clearTimeout(taxaTimer);
    q = (q || '').trim();
    if (q.length < 3 || $('pl-cient').value) { if (!$('pl-cient').value) $('pl-taxa').hidden = true; return; }
    taxaTimer = setTimeout(function () {
      if (taxaCache[q]) { pintarTaxa(taxaCache[q], q); return; }
      if (taxaCtl) taxaCtl.abort();
      taxaCtl = window.AbortController ? new AbortController() : null;
      var url = INAT + '?q=' + encodeURIComponent(q) + '&taxon_id=' + PLANTAE + '&locale=es&preferred_place_id=6793&per_page=10&is_active=true';
      fetch(url, taxaCtl ? { signal: taxaCtl.signal } : {}).then(function (r) { return r.ok ? r.json() : { results: [] }; }).then(function (d) {
        var res = (d.results || []).filter(function (t) { return RANGOS[t.rank] && t.default_photo; }).slice(0, 4).map(function (t) {
          var ph = t.default_photo || {};
          return { cient: t.name, comun: t.preferred_common_name || '', rank: t.rank, foto: ph.medium_url || ph.square_url || '', cred: ph.attribution || '' };
        });
        taxaCache[q] = res; pintarTaxa(res, q);
      }).catch(function () { /* sin iNaturalist: no se muestra nada */ });
    }, 500);
  }
  function pintarTaxa(res, q) {
    var box = $('pl-taxa'); TAXA = res;
    if (!res.length || $('pl-especie').value.trim() !== q) { box.hidden = true; return; }
    box.innerHTML = '<span class="t-meta">¿Es alguna de estas? Toca la que se parezca a la tuya.</span><ul class="pl-taxa-list">' + res.map(function (t, i) {
      return '<li class="pl-taxon">' + (t.foto ? '<img src="' + esc(t.foto) + '" alt="' + esc(t.comun || t.cient) + '" loading="lazy" referrerpolicy="no-referrer">' : '<span class="pl-taxon-ph"><i data-lucide="flower-2"></i></span>') +
        '<span class="pl-taxon-bd"><span class="t-ui">' + esc(t.comun || t.cient) + '</span><i>' + esc(t.cient) + (t.rank === 'genus' ? ' (género)' : '') + '</i></span>' +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-taxon="' + i + '">Es esta</button></li>';
    }).join('') + '</ul>';
    box.hidden = false; icons();
  }
  $('pl-taxa').addEventListener('click', function (e) {
    var b = e.target.closest('[data-taxon]'); if (!b) return;
    var t = TAXA[+b.dataset.taxon]; if (!t) return;
    if (t.comun) $('pl-especie').value = t.comun.charAt(0).toUpperCase() + t.comun.slice(1);
    t.comun = $('pl-especie').value.trim() || t.comun;
    setTaxon(t); $('pl-taxa').hidden = true;
    // Con la especie confirmada, la sugerencia local de intervalos usa ambos nombres.
    $('pl-especie').dispatchEvent(new Event('input'));
  });
  $('pl-taxa-sel').addEventListener('click', function (e) {
    if (!e.target.closest('.js-taxon-cambiar')) return;
    setTaxon(null); buscarTaxa($('pl-especie').value); $('pl-especie').focus();
  });

  /* ── Otros cuidados (fertilizar, rotar, limpiar, plagas) ─────────────── */
  function fillExtras(p) {
    var activos = {}, notas = {};
    ((p && p.cuidados) || []).forEach(function (c) { activos[c.tipo] = c.cada_dias; notas[c.tipo] = c.nota || ''; });
    if ($('pl-exnota-tratamiento')) $('pl-exnota-tratamiento').value = notas.tratamiento || '';
    $$('[data-ex]').forEach(function (chk) {
      var k = chk.dataset.ex, inp = $('pl-ex-' + k);
      chk.checked = k in activos;
      inp.value = activos[k] || inp.defaultValue;
      chk.closest('.pl-extra-row').classList.toggle('is-off', !chk.checked);
    });
  }
  $$('[data-ex]').forEach(function (chk) {
    chk.addEventListener('change', function () { chk.closest('.pl-extra-row').classList.toggle('is-off', !chk.checked); });
  });

  /* ── Registrar en otra fecha («la regué ayer») ──────────────────────── */
  function fillOtra(p) {
    if (!p) return;
    var opts = [['riego', 'Riego'], ['trasplante', 'Trasplante']].concat((p.cuidados || []).map(function (c) { return [c.tipo, c.label]; }));
    $('pl-otra-tipo').innerHTML = opts.map(function (o) { return '<option value="' + o[0] + '">' + esc(o[1]) + '</option>'; }).join('');
    var f = $('pl-otra-fecha');
    if (TODAY) {
      var d = new Date(TODAY + 'T12:00:00'); d.setDate(d.getDate() - 1);
      var min = new Date(TODAY + 'T12:00:00'); min.setDate(min.getDate() - 60);
      f.value = d.toISOString().slice(0, 10); f.max = TODAY; f.min = min.toISOString().slice(0, 10);
    }
  }
  document.querySelector('#pl-panel .js-otra').addEventListener('click', function () {
    var id = sel, tipo = $('pl-otra-tipo').value, fecha = $('pl-otra-fecha').value, b = this;
    if (!id || !fecha) return;
    b.disabled = true;
    jpost(BASE + '/api/plantas/' + id + '/cuidado/' + tipo, { fecha: fecha }).then(function (d) {
      if (!d.ok) { toast(d.error || 'No se pudo registrar', 'err'); return; }
      apply(d); if (tab === 'hist') loadHist(id);
      toast(d.ya_registrado ? d.msg : 'Registrado el ' + fmtFecha(fecha) + (d.gam && d.gam.xp ? ' · +' + d.gam.xp + ' XP' : ''), d.gam ? 'win' : 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { b.disabled = false; });
  });

  /* ── Fotos de evolución ─────────────────────────────────────────────── */
  function loadFotos(id) {
    var ul = $('pl-fotos-strip');
    ul.innerHTML = ''; if (!id) return;
    fetch(BASE + '/api/plantas/' + id + '/fotos').then(function (r) { return r.json(); }).then(function (d) {
      var fotos = d.fotos || [];
      ul.innerHTML = fotos.length ? fotos.map(function (f) {
        var src = BASE + '/foto/' + encodeURIComponent(f.foto);
        return '<li class="' + (f.portada ? 'is-cover' : '') + '"><a href="' + src + '" target="_blank" rel="noopener" aria-label="Ver foto del ' + fmtFecha(f.fecha) + '"><img src="' + src + '" alt="" loading="lazy"></a>' +
          '<span class="t-meta num">' + fmtFecha(f.fecha) + (f.portada ? ' · portada' : '') + '</span>' +
          '<button type="button" class="eu-iconbtn" data-foto-del="' + f.id + '" aria-label="Borrar foto del ' + fmtFecha(f.fecha) + '"><i data-lucide="x"></i></button></li>';
      }).join('') : '<li class="t-meta">Aún sin fotos. Una al mes basta para ver cómo cambia.</li>';
      icons();
    }).catch(function () { ul.innerHTML = '<li class="t-meta">No se pudieron cargar las fotos.</li>'; });
  }
  document.querySelector('#pl-panel .js-foto-add').addEventListener('click', function () { $('pl-foto-add').click(); });
  $('pl-foto-add').addEventListener('change', function () {
    var f = this.files && this.files[0], id = sel; if (!f || !id) return;
    var fd = new FormData(); fd.append('foto', f); this.value = '';
    toast('Subiendo foto…', 'ok');
    fetch(BASE + '/api/plantas/' + id + '/fotos', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast(d.error || 'No se pudo subir', 'err'); return; }
      apply(d); loadFotos(id);
      toast('Foto agregada', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); });
  });
  $('pl-fotos-strip').addEventListener('click', function (e) {
    var b = e.target.closest('[data-foto-del]'); if (!b) return;
    euConfirm('¿Borrar esta foto?', { confirmLabel: 'Borrar' }).then(function (ok) {
      if (!ok) return;
      fetch(BASE + '/api/fotos/' + b.dataset.fotoDel, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast('No se pudo borrar', 'err'); return; }
        var id = sel; apply(d); loadFotos(id);
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  });

  /* ── Historial (bitácora) con deshacer del último registro ──────────── */
  var HIST = { riego: ['droplet', 'Regada'], trasplante: ['sprout', 'Trasplantada'], revision: ['clock', 'Revisada'],
    diagnostico: ['stethoscope', 'Diagnóstico'], fertilizar: ['flask-conical', 'Fertilizada'], rotar: ['rotate-cw', 'Rotada'], limpiar: ['sparkles', 'Hojas limpias'], plagas: ['bug', 'Plagas revisadas'] };
  function fmtFecha(f) { var d = f.split('-'); return d[2] + '/' + d[1] + '/' + d[0]; }
  function loadHist(id) {
    var ul = $('pl-hist-list');
    ul.innerHTML = ''; if (!id) return;
    ul.innerHTML = '<li class="t-meta">Cargando…</li>';
    fetch(BASE + '/api/plantas/' + id + '/bitacora').then(function (r) { return r.json(); }).then(function (d) {
      var rows = d.bitacora || [];
      ul.innerHTML = rows.length ? rows.map(function (b) {
        var h = HIST[b.tipo] || ['circle', b.tipo];
        return '<li><i data-lucide="' + h[0] + '"></i><span class="num">' + fmtFecha(b.fecha) + '</span><span class="eu-grow">' + h[1] + (b.notas ? ' · ' + esc(b.notas) : '') + '</span>' +
          (b.deshacer ? '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm" data-undo="' + b.id + '"><i data-lucide="undo-2"></i>Deshacer</button>' : '') + '</li>';
      }).join('') : '<li class="t-meta">Sin registros todavía.</li>';
      icons();
    }).catch(function () { ul.innerHTML = '<li class="t-meta">No se pudo cargar el historial.</li>'; });
  }
  $('pl-hist-list').addEventListener('click', function (e) {
    var b = e.target.closest('[data-undo]'); if (!b) return;
    b.disabled = true;
    fetch(BASE + '/api/bitacora/' + b.dataset.undo, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast(d.error || 'No se pudo deshacer', 'err'); b.disabled = false; return; }
      apply(d); loadHist(sel); toast('Registro deshecho', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); b.disabled = false; });
  });

  // Sugerencia de intervalos por especie: nunca sobreescribe sola, solo ofrece «Usar».
  $('pl-especie').addEventListener('input', function () {
    // Si cambia el texto, la especie confirmada ya no aplica.
    if ($('pl-cient').value && this.value.trim() !== ($('pl-taxa-sel').dataset.comun || '')) setTaxon(null);
    buscarTaxa(this.value);
  });
  ['pl-nombre', 'pl-especie'].forEach(function (id) {
    $(id).addEventListener('input', function () {
      clearTimeout(sugTimer);
      sugTimer = setTimeout(function () {
        var q = ($('pl-especie').value || $('pl-nombre').value).trim();
        if (q.length < 3) { hideSug(); return; }
        fetch(BASE + '/api/sugerir?q=' + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (s) {
          if (!s.match) { hideSug(); return; }
          var box = $('pl-sugerencia');
          box.innerHTML = '<i data-lucide="lightbulb"></i><span class="eu-grow">Sugerencia para «' + esc(s.match) + '»: <b>cada ' + s.dias_riego + ' d</b> riego · <b>cada ' + s.meses_trasplante + ' m</b> trasplante</span>' +
            '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-sug="' + s.dias_riego + ',' + s.meses_trasplante + '">Usar</button>';
          box.hidden = false; icons();
        }).catch(hideSug);
      }, 450);
    });
  });
  $('pl-sugerencia').addEventListener('click', function (e) {
    var b = e.target.closest('[data-sug]'); if (!b) return;
    var v = b.dataset.sug.split(',');
    $('pl-dias-riego').value = v[0]; $('pl-meses-trasplante').value = v[1];
    hideSug(); toast('Intervalos aplicados', 'ok'); $('pl-dias-riego').focus();
  });

  $('f-planta').addEventListener('submit', function (e) {
    e.preventDefault();
    var nombre = $('pl-nombre').value.trim();
    if (!nombre) { toast('El nombre es requerido', 'err'); $('pl-nombre').focus(); return; }
    var id = $('pl-id').value, fd = new FormData();
    fd.append('nombre', nombre); fd.append('especie', $('pl-especie').value.trim()); fd.append('ubicacion', $('pl-ubicacion').value.trim());
    fd.append('dias_riego', $('pl-dias-riego').value || 7); fd.append('meses_trasplante', $('pl-meses-trasplante').value || 12);
    fd.append('notas', $('pl-notas').value.trim());
    fd.append('entorno', $('pl-entorno').value); fd.append('luz', $('pl-luz').value);
    fd.append('especie_cientifica', $('pl-cient').value); fd.append('ref_foto', $('pl-ref-foto').value); fd.append('ref_foto_credito', $('pl-ref-cred').value);
    $$('[data-ex]').forEach(function (chk) {
      fd.append('cuidado_' + chk.dataset.ex, chk.checked ? ($('pl-ex-' + chk.dataset.ex).value || '') : '');
      if ($('pl-exnota-' + chk.dataset.ex)) fd.append('cuidado_' + chk.dataset.ex + '_nota', $('pl-exnota-' + chk.dataset.ex).value);
    });
    if (!id && $('pl-last-riego').value) fd.append('last_riego', $('pl-last-riego').value);
    if (fotoFile) fd.append('foto', fotoFile);
    var btn = document.querySelector('[form="f-planta"]'); btn.disabled = true;
    fetch(id ? BASE + '/api/plantas/' + id : BASE + '/api/plantas', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast('Error: ' + (d.error || 'no se pudo guardar'), 'err'); return; }
      euModal.close('m-planta'); apply(d); toast(id ? 'Planta actualizada ✓' : 'Planta agregada ✓', 'ok');
      if (!id && d.id) openPanel(d.id);
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { btn.disabled = false; });
  });
  $('pl-delete-btn').addEventListener('click', function () {
    var id = $('pl-id').value; if (!id) return;
    var p = PLANTAS.filter(function (x) { return String(x.id) === id; })[0];
    euConfirm('¿Eliminar «' + (p ? p.nombre : 'esta planta') + '»?', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      fetch(BASE + '/api/plantas/' + id, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast('Error al eliminar', 'err'); return; }
        euModal.close('m-planta'); sel = null; apply(d); closePanel(); toast('Planta eliminada');
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  });

  /* ── Doctor de plantas (IA) ─────────────────────────────────────────── */
  var dr = { id: null, foto: null };
  var URG = { alta: ['Urgencia alta', 'eu-badge--danger'], media: ['Urgencia media', 'eu-badge--warning'], baja: ['Urgencia baja', 'eu-badge--success'] };
  var LUZ_TXT = { baja: 'baja', media: 'media', brillante: 'brillante indirecta', sol_directo: 'sol directo' };
  function busy(btn, on, txt) {
    btn.disabled = on; btn.setAttribute('aria-busy', String(on));
    var sp = btn.querySelector('span'); if (sp) { if (!btn.dataset.lbl) btn.dataset.lbl = sp.textContent; sp.textContent = on ? txt : btn.dataset.lbl; }
  }
  function prepDoctor(id) {
    var p = planta(id); if (!p || !$('pp-doctor') || dr.id === id) return;
    dr.id = id; dr.foto = null;
    $$('[data-sint]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
    $('dr-texto').value = ''; $('dr-result').innerHTML = ''; $('cx-result').innerHTML = '';
    var img = $('dr-foto-img');
    if (p.foto) { img.src = BASE + '/foto/' + encodeURIComponent(p.foto); img.hidden = false; $('dr-foto-cap').textContent = 'Se usará la foto de portada; mejor toma una de cómo está hoy.'; }
    else { img.removeAttribute('src'); img.hidden = true; $('dr-foto-cap').textContent = 'Sin foto: agrega una para un diagnóstico más certero.'; }
    icons();
  }
  if ($('pp-doctor')) {
    $('pp-doctor').addEventListener('click', function (e) {
      var b = e.target.closest('[data-sint]'); if (b) b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true'));
    });
    document.querySelector('#pp-doctor .js-dr-foto').addEventListener('click', function () { $('dr-foto-input').click(); });
    $('dr-foto-input').addEventListener('change', function () {
      var f = this.files && this.files[0]; if (!f) return;
      dr.foto = f;
      var rd = new FileReader(); rd.onload = function (ev) { var img = $('dr-foto-img'); img.src = ev.target.result; img.hidden = false; }; rd.readAsDataURL(f);
      $('dr-foto-cap').textContent = 'Foto de hoy lista (se guarda en su línea de tiempo).';
    });
    document.querySelector('#pp-doctor .js-dr-go').addEventListener('click', function () {
      var btn = this, fd = new FormData();
      $$('[data-sint][aria-pressed="true"]').forEach(function (b) { fd.append('sintomas', b.dataset.sint); });
      fd.append('texto', $('dr-texto').value.trim());
      if (dr.foto) fd.append('foto', dr.foto);
      busy(btn, true, 'Revisando la planta…'); $('dr-result').innerHTML = '';
      fetch(BASE + '/api/plantas/' + dr.id + '/diagnostico', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast(d.error || 'No se pudo diagnosticar', 'err'); return; }
        $('dr-result').innerHTML = dxHTML(d.diagnostico); icons();
      }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { busy(btn, false); });
    });
    document.querySelector('#pp-doctor .js-cx-go').addEventListener('click', function () {
      var btn = this; busy(btn, true, 'Analizando…'); $('cx-result').innerHTML = '';
      fetch(BASE + '/api/plantas/' + dr.id + '/consejo').then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast(d.error || 'No se pudo analizar', 'err'); return; }
        $('cx-result').innerHTML = d.suficiente ? cxHTML(d.consejo, d.historial) : '<p class="t-meta">' + esc(d.msg) + '</p>'; icons();
      }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { busy(btn, false); });
    });
    $('pp-doctor').addEventListener('click', function (e) {
      var b = e.target.closest('[data-aplicar]'); if (!b) return;
      var fd = new FormData(); fd.append(b.dataset.aplicar, b.dataset.valor); b.disabled = true;
      fetch(BASE + '/api/plantas/' + dr.id, { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast(d.error || 'No se pudo aplicar', 'err'); b.disabled = false; return; }
        apply(d); b.innerHTML = '<i data-lucide="check"></i>Aplicado'; icons(); toast('Ajuste aplicado', 'ok');
      }).catch(function () { toast('Sin conexión', 'err'); b.disabled = false; });
    });
  }
  function ajusteBtns(aj) {
    var out = [];
    if (aj && aj.dias_riego) out.push('<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-aplicar="dias_riego" data-valor="' + aj.dias_riego + '"><i data-lucide="droplet"></i>Aplicar: regar cada ' + aj.dias_riego + ' d</button>');
    if (aj && aj.luz) out.push('<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-aplicar="luz" data-valor="' + aj.luz + '"><i data-lucide="sun"></i>Aplicar: luz ' + esc(LUZ_TXT[aj.luz] || aj.luz) + '</button>');
    return out.length ? '<div class="pl-dx-aj">' + out.join('') + '</div>' : '';
  }
  function dxHTML(d) {
    var u = URG[d.urgencia] || URG.media;
    var grupos = ['hoy', 'esta semana', 'este mes'].map(function (k) {
      var acc = d.acciones.filter(function (a) { return a.cuando === k; });
      return acc.length ? '<div><div class="t-eyebrow">' + k.charAt(0).toUpperCase() + k.slice(1) + '</div><ol>' + acc.map(function (a) { return '<li>' + esc(a.paso) + '</li>'; }).join('') + '</ol></div>' : '';
    }).join('');
    return '<div class="pl-dx"><h4>' + esc(d.resumen) + '</h4>' +
      '<div class="pl-dx-badges"><span class="eu-badge ' + u[1] + '">' + u[0] + '</span><span class="eu-badge">Confianza ' + esc(d.confianza) + '</span></div>' +
      (d.pedir_mejor_foto ? '<p class="pl-dx-warn"><i data-lucide="triangle-alert"></i>La foto no deja ver bien la planta: toma otra con luz de día, de cerca a las hojas afectadas.</p>' : '') +
      (d.en_la_foto ? '<p class="pl-dx-eye"><i data-lucide="scan-eye"></i><span>' + esc(d.en_la_foto) + '</span></p>' : '') +
      (d.causas.length ? '<div><div class="t-eyebrow">Causas probables</div><ul class="pl-causes">' + d.causas.map(function (c) {
        return '<li class="pl-cause"><span class="eu-between"><span>' + esc(c.causa) + '</span><span class="num">' + c.probabilidad + '%</span></span>' +
          '<span class="eu-progress eu-progress--thin" aria-hidden="true"><i style="width:' + c.probabilidad + '%"></i></span>' +
          (c.evidencia ? '<span class="t-meta">' + esc(c.evidencia) + '</span>' : '') + '</li>';
      }).join('') + '</ul></div>' : '') +
      grupos +
      (d.vigilar.length ? '<div><div class="t-eyebrow">Vigila</div><ul>' + d.vigilar.map(function (v) { return '<li>' + esc(v) + '</li>'; }).join('') + '</ul></div>' : '') +
      ajusteBtns(d.ajustes_sugeridos) +
      '<p class="t-meta">Guardado en su historial.</p></div>';
  }
  function cxHTML(c, h) {
    var datos = 'Riegos en 120 días: ' + h.n_riegos + (h.intervalo_real ? ' · cada ' + h.intervalo_real + ' d en promedio (configurado: ' + h.intervalo_configurado + ' d)' : '') +
      (h.revisiones_humeda ? ' · seguía húmeda ' + h.revisiones_humeda + ' vez/veces' : '');
    return '<div class="pl-dx"><p class="t-meta">' + esc(datos) + '</p>' +
      (c.observacion ? '<div><div class="t-eyebrow">Lo que muestran tus datos</div><p class="t-body">' + esc(c.observacion) + '</p></div>' : '') +
      (c.recomendacion ? '<div><div class="t-eyebrow">Qué hacer</div><p class="t-body">' + esc(c.recomendacion) + '</p></div>' : '') +
      (c.ajuste ? '<p class="t-meta">' + esc(c.ajuste.razon) + '</p>' + ajusteBtns({ dias_riego: c.ajuste.valor }) : '') + '</div>';
  }

  /* ── Ficha de cuidados con IA (formulario) ──────────────────────────── */
  var fichaBtn = document.querySelector('#m-planta .js-ficha'), fichaData = null;
  if (fichaBtn) fichaBtn.addEventListener('click', function () {
    var id = $('pl-id').value, especie = $('pl-especie').value.trim(), p = id ? planta(+id) : null;
    var fd = new FormData();
    fd.append('especie', $('pl-cient').value ? $('pl-cient').value + (especie ? ' (' + especie + ')' : '') : (especie || $('pl-nombre').value.trim()));
    fd.append('entorno', $('pl-entorno').value); fd.append('luz', $('pl-luz').value);
    fd.append('especie_cientifica', $('pl-cient').value); fd.append('ref_foto', $('pl-ref-foto').value); fd.append('ref_foto_credito', $('pl-ref-cred').value);
    // Sin especie escrita, se identifica por la foto (la recién elegida o la portada).
    if (!especie && !$('pl-cient').value && fotoFile) fd.append('foto', fotoFile);
    else if (!especie && p && p.foto) { fd.append('planta_id', id); fd.append('usar_foto', '1'); }
    var box = $('pl-ficha'); box.hidden = false; box.innerHTML = '<span class="t-meta">Consultando…</span>';
    fichaBtn.disabled = true;
    fetch(BASE + '/api/ficha', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { box.hidden = true; toast(d.error || 'No se pudo generar la ficha', 'err'); return; }
      var f = fichaData = d.ficha;
      box.innerHTML = '<div class="eu-between"><span class="t-ui">' + esc(f.nombre_comun || f.especie || 'Ficha') + (f.especie && f.nombre_comun ? ' <span class="t-meta">(' + esc(f.especie) + ')</span>' : '') + '</span>' +
        '<span class="eu-badge">Confianza ' + esc(f.confianza) + '</span></div>' +
        '<dl><dt>Riego</dt><dd>cada ' + f.dias_riego + ' d</dd><dt>Trasplante</dt><dd>cada ' + f.meses_trasplante + ' meses</dd>' +
        '<dt>Fertilizar</dt><dd>' + (f.fertilizar_cada_dias ? 'cada ' + f.fertilizar_cada_dias + ' d (pausa nov-feb)' : 'no hace falta') + '</dd>' +
        (f.luz_ideal ? '<dt>Luz ideal</dt><dd>' + esc(LUZ_TXT[f.luz_ideal] || f.luz_ideal) + '</dd>' : '') +
        (f.humedad ? '<dt>Humedad</dt><dd>' + esc(f.humedad) + '</dd>' : '') +
        (f.toxica_mascotas !== null ? '<dt>Mascotas</dt><dd>' + (f.toxica_mascotas ? 'tóxica' : 'no tóxica') + '</dd>' : '') + '</dl>' +
        (f.nota_entorno ? '<p class="t-meta">' + esc(f.nota_entorno) + '</p>' : '') +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm js-ficha-usar"><i data-lucide="check"></i>Usar estos valores</button>';
      icons();
    }).catch(function () { box.hidden = true; toast('Sin conexión', 'err'); }).finally(function () { fichaBtn.disabled = false; });
  });
  if ($('pl-ficha')) $('pl-ficha').addEventListener('click', function (e) {
    if (!e.target.closest('.js-ficha-usar') || !fichaData) return;
    var f = fichaData;
    $('pl-dias-riego').value = f.dias_riego; $('pl-meses-trasplante').value = f.meses_trasplante;
    if (!$('pl-especie').value.trim()) $('pl-especie').value = f.nombre_comun || f.especie || '';
    if (f.luz_ideal && !$('pl-luz').value) $('pl-luz').value = f.luz_ideal;
    var fert = $('pl-exon-fertilizar');
    if (fert) {
      fert.checked = !!f.fertilizar_cada_dias; if (f.fertilizar_cada_dias) $('pl-ex-fertilizar').value = f.fertilizar_cada_dias;
      fert.closest('.pl-extra-row').classList.toggle('is-off', !fert.checked);
    }
    $('pl-ficha').hidden = true; toast('Valores aplicados: revisa y guarda', 'ok');
  });

  renderHoy(); renderGrid();
  if (!MOVIL.matches && PLANTAS.length) openPanel((HOY[0] || PLANTAS[0]).planta_id || PLANTAS[0].id);
})();
