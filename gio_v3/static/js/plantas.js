/* Plantas — Design System V2: tarjetas con dos calendarios (riego ajustado por
   temporada y trasplante), filtros, alta/edición con foto y sugerencia de
   intervalos por especie (tabla local). */
(function () {
  'use strict';
  var root = document.getElementById('pl');
  if (!root) return;
  var BASE = '/plantas';
  var PLANTAS = JSON.parse(document.getElementById('pl-data').textContent || '[]');
  var ST = {
    vencido: ['Vencido', 'eu-badge--danger', 'danger'], urgente: ['Urgente', 'eu-badge--warning', 'warning'],
    proximo: ['Próximo', 'eu-badge--brand', 'brand'], nominal: ['Al día', 'eu-badge--success', 'success'],
  };
  var TODAY = JSON.parse((document.getElementById('pl-today') || {}).textContent || 'null');
  var filter = 'todas', fotoFile = null, sugTimer = null;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function jpost(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); });
  }

  function items() {
    if (filter === 'pendientes') return PLANTAS.filter(function (p) { return p.status !== 'nominal'; });
    if (filter === 'al_dia') return PLANTAS.filter(function (p) { return p.status === 'nominal'; });
    return PLANTAS;
  }
  /* Cuándo toca, en palabras: «hoy», «mañana», «en 5 d», «hace 2 d». */
  function cuando(dias, tipo) {
    if (dias === 0) return 'hoy';
    if (dias === 1) return 'mañana';
    if (dias === -1) return 'ayer';
    if (dias < 0) return 'hace ' + (-dias) + ' d';
    if (tipo === 'trasplante' && dias > 45) return 'en ' + Math.round(dias / 30) + ' meses';
    return 'en ' + dias + ' d';
  }
  var EXTRA_IC = { fertilizar: 'flask-conical', rotar: 'rotate-cw', limpiar: 'sparkles', plagas: 'bug' };
  var EXTRA_BTN = { fertilizar: 'Fertilicé', rotar: 'Roté', limpiar: 'Limpié', plagas: 'Revisé' };
  /* Normaliza riego / trasplante / cuidados extra a una misma forma. */
  function careItems(p) {
    var r = {
      tipo: 'riego', label: 'Riego', icon: 'droplet', btn: 'Regué', status: p.riego_status, pct: p.riego_pct, dias: p.riego_dias,
      regla: (p.riego_interval_efectivo !== p.dias_riego ? 'cada ' + p.riego_interval_efectivo + ' d (ajustado; base ' + p.dias_riego + ' d)' : 'cada ' + p.dias_riego + ' d') +
        (p.riego_pospuesta ? ' · pospuesto (aún húmeda)' : '')
    };
    var t = { tipo: 'trasplante', label: 'Trasplante', icon: 'sprout', btn: 'Trasplanté', status: p.trasplante_status, pct: p.trasplante_pct,
      dias: p.trasplante_dias, regla: 'cada ' + p.meses_trasplante + ' meses' };
    return [r, t].concat((p.cuidados || []).map(function (c) {
      return { tipo: c.tipo, label: c.label, icon: EXTRA_IC[c.tipo] || 'leaf', btn: EXTRA_BTN[c.tipo] || 'Hecho', status: c.status,
        pct: c.pct, dias: c.dias, regla: 'cada ' + c.cada_dias + ' d', pausado: c.pausado, extra: true };
    }));
  }
  function badge(it) {
    var s = ST[it.status], lbl = s[0];
    if (it.status === 'urgente') lbl = it.tipo === 'trasplante' ? 'Esta semana' : 'Hoy';
    return '<span class="eu-badge eu-badge--status ' + s[1] + '">' + lbl + '</span>';
  }
  function care(p, it) {
    var pct = Math.min(1, it.pct || 0) * 100;
    var extra = (it.dias < 0 ? 'Tocaba ' : 'Toca ') + cuando(it.dias, it.tipo) + ' · ' + it.regla;
    var acts = (it.tipo === 'riego' && it.status !== 'nominal'
        ? '<button type="button" class="eu-btn eu-btn--ghost eu-btn--sm" data-posponer="' + p.id + '" aria-label="' + esc(p.nombre) + ': aún está húmeda, posponer 2 días" title="Revisé la tierra y aún está húmeda: posponer 2 días"><i data-lucide="clock"></i>Aún húmeda</button>' : '') +
      '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-care="' + it.tipo + '" data-id="' + p.id + '" aria-label="' + it.btn + ' ' + esc(p.nombre) + '">' +
      '<i data-lucide="check"></i>' + it.btn + '</button>';
    return '<div class="pl-care" data-tone="' + ST[it.status][2] + '"><span class="pl-care-ic"><i data-lucide="' + it.icon + '"></i></span>' +
      '<div class="pl-care-bd"><div class="eu-between"><span class="t-ui">' + it.label + '</span>' + badge(it) + '</div>' +
      '<div class="eu-progress eu-progress--thin pl-prog" aria-hidden="true"><i style="width:' + pct.toFixed(1) + '%"></i></div><span class="t-meta">' + extra + '</span></div>' +
      '<div class="pl-care-act">' + acts + '</div></div>';
  }
  /* Cuidados extra al día: una sola línea en lugar de una fila cada uno. */
  function moreLine(rest) {
    if (!rest.length) return '';
    return '<p class="t-meta pl-more">' + rest.map(function (it) {
      return '<span><i data-lucide="' + it.icon + '"></i>' + esc(it.label) + ' · ' + (it.pausado ? 'en pausa (invierno)' : cuando(it.dias, it.tipo)) + '</span>';
    }).join('') + '</p>';
  }
  /* «Regar las N pendientes del balcón / de interior» cuando hay 2 o más. */
  function groupBar() {
    var box = $('pl-group'); if (!box) return;
    var html = ['balcon', 'interior'].map(function (env) {
      var n = PLANTAS.filter(function (p) { return p.entorno === env && p.riego_status !== 'nominal'; }).length;
      return n >= 2 ? '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-grupo="' + env + '"><i data-lucide="droplets"></i>Regar las ' + n + ' pendientes ' + (env === 'balcon' ? 'del balcón' : 'de interior') + '</button>' : '';
    }).join('');
    box.innerHTML = html; box.hidden = !html;
  }
  function render() {
    var list = items(), box = $('pl-grid');
    if (!list.length) {
      box.innerHTML = '<div class="eu-card pl-span"><div class="eu-empty"><div class="eu-empty-ic"><i data-lucide="sprout"></i></div><div class="t-card">' +
        (PLANTAS.length ? 'Nada por aquí' : 'Aún no agregas ninguna planta') + '</div><p>' + (PLANTAS.length ? 'Cambia el filtro para ver el resto.' : 'Agrega la primera con el botón de arriba.') + '</p>' +
        (PLANTAS.length ? '' : '<button type="button" class="eu-btn eu-btn--primary js-new"><i data-lucide="plus"></i>Nueva planta</button>') + '</div></div>';
      icons(); return;
    }
    box.innerHTML = list.map(function (p) {
      var env = '<span class="pl-env"><i data-lucide="' + (p.entorno === 'balcon' ? 'sun' : 'house') + '"></i>' + (p.entorno === 'balcon' ? 'Balcón' : 'Interior') + '</span>';
      var sub = [env].concat([p.especie, p.ubicacion].filter(Boolean).map(esc)).join(' · ');
      return '<article class="eu-card eu-card--flush pl-card" data-tone="' + ST[p.status][2] + '">' +
        (p.foto ? '<img class="pl-cover" src="' + BASE + '/foto/' + encodeURIComponent(p.foto) + '" alt="" loading="lazy">' : '<span class="pl-cover pl-cover--empty" aria-hidden="true"><i data-lucide="flower-2"></i></span>') +
        '<div class="pl-card-bd"><div class="eu-between pl-card-hd"><div class="eu-grow"><h2 class="t-card pl-card-t">' + esc(p.nombre) + '</h2><p class="t-meta">' + sub + '</p></div>' +
        '<button type="button" class="eu-iconbtn" data-edit="' + p.id + '" aria-label="Editar ' + esc(p.nombre) + '"><i data-lucide="pencil"></i></button></div>' +
        (function () {
          var its = careItems(p), main = its.filter(function (it) { return !it.extra || it.status !== 'nominal'; });
          return main.map(function (it) { return care(p, it); }).join('') + moreLine(its.filter(function (it) { return it.extra && it.status === 'nominal'; }));
        })() +
        (p.notas ? '<p class="t-meta pl-notes">' + esc(p.notas) + '</p>' : '') + '</div></article>';
    }).join('');
    icons();
  }
  function sync() {
    var c = { vencido: 0, urgente: 0, proximo: 0, nominal: 0 };
    PLANTAS.forEach(function (p) { c[p.status]++; });
    Object.keys(c).forEach(function (k) {
      var b = $('pl-st-' + k); b.querySelector('.eu-stat-val').textContent = c[k]; b.classList.toggle('is-on', c[k] > 0);
    });
    $('pl-f-todas').querySelector('.ct').textContent = PLANTAS.length;
    $('pl-f-pendientes').querySelector('.ct').textContent = c.vencido + c.urgente + c.proximo;
    $('pl-f-al_dia').querySelector('.ct').textContent = c.nominal;
  }
  function apply(d) { PLANTAS = d.state.plantas; sync(); render(); groupBar(); }

  $$('[data-f]').forEach(function (b) {
    b.addEventListener('click', function () {
      filter = b.dataset.f;
      $$('[data-f]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      render();
    });
  });
  root.addEventListener('click', function (e) {
    if (e.target.closest('.js-new')) { openNew(); return; }
    var ed = e.target.closest('[data-edit]'); if (ed) { openEdit(+ed.dataset.edit); return; }
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
    var tipo = c.dataset.care, id = c.dataset.id; c.disabled = true;
    fetch(BASE + '/api/plantas/' + id + '/cuidado/' + tipo, { method: 'POST' }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast('Error al guardar', 'err'); c.disabled = false; return; }
      apply(d);
      if (d.ya_registrado) { toast(d.msg || 'Ya estaba registrado hoy', 'ok'); return; }
      toast(d.gam && d.gam.xp ? '+' + d.gam.xp + ' XP · +' + d.gam.ec + ' EC' : 'Registrado', d.gam && d.gam.xp ? 'win' : 'ok');
      var nb = document.querySelector('[data-care="' + tipo + '"][data-id="' + id + '"]'); if (nb) nb.focus();
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
    $('pl-last-wrap').hidden = !!p.id; $('pl-last-riego').value = TODAY || ''; if (TODAY) $('pl-last-riego').max = TODAY;
    loadHist(p.id); loadFotos(p.id); fillExtras(p); fillOtra(p);
    $('pl-delete-btn').hidden = !p.id;
    $('m-planta-t').textContent = p.id ? 'Editar planta' : 'Nueva planta';
    fotoFile = null; setFoto(p.foto ? BASE + '/foto/' + encodeURIComponent(p.foto) : null); hideSug();
    icons(); euModal.open('m-planta'); setTimeout(function () { $('pl-nombre').focus(); }, 20);
  }
  function openNew() { fill(null); }

  /* ── Otros cuidados (fertilizar, rotar, limpiar, plagas) ─────────────── */
  function fillExtras(p) {
    var activos = {};
    ((p && p.cuidados) || []).forEach(function (c) { activos[c.tipo] = c.cada_dias; });
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
    var box = $('pl-otra'); box.hidden = !(p && p.id); if (box.hidden) return;
    var opts = [['riego', 'Riego'], ['trasplante', 'Trasplante']].concat((p.cuidados || []).map(function (c) { return [c.tipo, c.label]; }));
    $('pl-otra-tipo').innerHTML = opts.map(function (o) { return '<option value="' + o[0] + '">' + esc(o[1]) + '</option>'; }).join('');
    var f = $('pl-otra-fecha');
    if (TODAY) {
      var d = new Date(TODAY + 'T12:00:00'); d.setDate(d.getDate() - 1);
      var min = new Date(TODAY + 'T12:00:00'); min.setDate(min.getDate() - 60);
      f.value = d.toISOString().slice(0, 10); f.max = TODAY; f.min = min.toISOString().slice(0, 10);
    }
  }
  document.querySelector('#m-planta .js-otra').addEventListener('click', function () {
    var id = $('pl-id').value, tipo = $('pl-otra-tipo').value, fecha = $('pl-otra-fecha').value, b = this;
    if (!id || !fecha) return;
    b.disabled = true;
    jpost(BASE + '/api/plantas/' + id + '/cuidado/' + tipo, { fecha: fecha }).then(function (d) {
      if (!d.ok) { toast(d.error || 'No se pudo registrar', 'err'); return; }
      apply(d); loadHist(id);
      toast(d.ya_registrado ? d.msg : 'Registrado el ' + fmtFecha(fecha) + (d.gam && d.gam.xp ? ' · +' + d.gam.xp + ' XP' : ''), d.gam ? 'win' : 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { b.disabled = false; });
  });

  /* ── Fotos de evolución ─────────────────────────────────────────────── */
  function loadFotos(id) {
    var box = $('pl-fotos'), ul = $('pl-fotos-strip');
    box.hidden = !id; ul.innerHTML = ''; if (!id) return;
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
  document.querySelector('#m-planta .js-foto-add').addEventListener('click', function () { $('pl-foto-add').click(); });
  $('pl-foto-add').addEventListener('change', function () {
    var f = this.files && this.files[0], id = $('pl-id').value; if (!f || !id) return;
    var fd = new FormData(); fd.append('foto', f); this.value = '';
    toast('Subiendo foto…', 'ok');
    fetch(BASE + '/api/plantas/' + id + '/fotos', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast(d.error || 'No se pudo subir', 'err'); return; }
      apply(d); loadFotos(id);
      var p = PLANTAS.filter(function (x) { return String(x.id) === id; })[0];
      setFoto(p && p.foto ? BASE + '/foto/' + encodeURIComponent(p.foto) : null);
      toast('Foto agregada', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); });
  });
  $('pl-fotos-strip').addEventListener('click', function (e) {
    var b = e.target.closest('[data-foto-del]'); if (!b) return;
    euConfirm('¿Borrar esta foto?', { confirmLabel: 'Borrar' }).then(function (ok) {
      if (!ok) return;
      fetch(BASE + '/api/fotos/' + b.dataset.fotoDel, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast('No se pudo borrar', 'err'); return; }
        var id = $('pl-id').value; apply(d); loadFotos(id);
        var p = PLANTAS.filter(function (x) { return String(x.id) === id; })[0];
        setFoto(p && p.foto ? BASE + '/foto/' + encodeURIComponent(p.foto) : null);
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  });

  /* ── Historial (bitácora) con deshacer del último registro ──────────── */
  var HIST = { riego: ['droplet', 'Regada'], trasplante: ['sprout', 'Trasplantada'], revision: ['clock', 'Revisada'],
    fertilizar: ['flask-conical', 'Fertilizada'], rotar: ['rotate-cw', 'Rotada'], limpiar: ['sparkles', 'Hojas limpias'], plagas: ['bug', 'Plagas revisadas'] };
  function fmtFecha(f) { var d = f.split('-'); return d[2] + '/' + d[1] + '/' + d[0]; }
  function loadHist(id) {
    var box = $('pl-hist'), ul = $('pl-hist-list');
    box.hidden = !id; ul.innerHTML = ''; if (!id) return;
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
      apply(d); loadHist($('pl-id').value); toast('Registro deshecho', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); b.disabled = false; });
  });
  function openEdit(id) { var p = PLANTAS.filter(function (x) { return x.id === id; })[0]; if (p) fill(p); }

  // Sugerencia de intervalos por especie: nunca sobreescribe sola, solo ofrece «Usar».
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
    $$('[data-ex]').forEach(function (chk) {
      fd.append('cuidado_' + chk.dataset.ex, chk.checked ? ($('pl-ex-' + chk.dataset.ex).value || '') : '');
    });
    if (!id && $('pl-last-riego').value) fd.append('last_riego', $('pl-last-riego').value);
    if (fotoFile) fd.append('foto', fotoFile);
    var btn = document.querySelector('[form="f-planta"]'); btn.disabled = true;
    fetch(id ? BASE + '/api/plantas/' + id : BASE + '/api/plantas', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast('Error: ' + (d.error || 'no se pudo guardar'), 'err'); return; }
      euModal.close('m-planta'); apply(d); toast(id ? 'Planta actualizada ✓' : 'Planta agregada ✓', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { btn.disabled = false; });
  });
  $('pl-delete-btn').addEventListener('click', function () {
    var id = $('pl-id').value; if (!id) return;
    var p = PLANTAS.filter(function (x) { return String(x.id) === id; })[0];
    euConfirm('¿Eliminar «' + (p ? p.nombre : 'esta planta') + '»?', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      fetch(BASE + '/api/plantas/' + id, { method: 'DELETE' }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) { toast('Error al eliminar', 'err'); return; }
        euModal.close('m-planta'); apply(d); toast('Planta eliminada');
      }).catch(function () { toast('Sin conexión', 'err'); });
    });
  });

  render(); groupBar();
})();
