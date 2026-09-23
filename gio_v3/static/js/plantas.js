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
  var filter = 'todas', fotoFile = null, sugTimer = null;

  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }

  function items() {
    if (filter === 'pendientes') return PLANTAS.filter(function (p) { return p.status !== 'nominal'; });
    if (filter === 'al_dia') return PLANTAS.filter(function (p) { return p.status === 'nominal'; });
    return PLANTAS;
  }
  function care(p, tipo, icon, label, key, extra, pctKey) {
    var s = ST[p[key]], pct = Math.min(1, p[pctKey] || 0) * 100;
    return '<div class="pl-care" data-tone="' + s[2] + '"><span class="pl-care-ic"><i data-lucide="' + icon + '"></i></span>' +
      '<div class="pl-care-bd"><div class="eu-between"><span class="t-ui">' + label + '</span><span class="eu-badge eu-badge--status ' + s[1] + '">' + s[0] + '</span></div>' +
      '<div class="eu-progress eu-progress--thin pl-prog" aria-hidden="true"><i style="width:' + pct.toFixed(1) + '%"></i></div><span class="t-meta">' + extra + '</span></div>' +
      '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm" data-care="' + tipo + '" data-id="' + p.id + '" aria-label="' + (tipo === 'riego' ? 'Regué' : 'Trasplanté') + ' ' + esc(p.nombre) + '">' +
      '<i data-lucide="check"></i>' + (tipo === 'riego' ? 'Regué' : 'Trasplanté') + '</button></div>';
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
      var riegoTxt = p.riego_interval_efectivo !== p.dias_riego ? 'cada ' + p.riego_interval_efectivo + ' d (ajustado; base ' + p.dias_riego + ' d)' : 'cada ' + p.dias_riego + ' d';
      var sub = [p.especie, p.ubicacion].filter(Boolean).map(esc).join(' · ');
      return '<article class="eu-card eu-card--flush pl-card" data-tone="' + ST[p.status][2] + '">' +
        (p.foto ? '<img class="pl-cover" src="' + BASE + '/foto/' + encodeURIComponent(p.foto) + '" alt="" loading="lazy">' : '<span class="pl-cover pl-cover--empty" aria-hidden="true"><i data-lucide="flower-2"></i></span>') +
        '<div class="pl-card-bd"><div class="eu-between pl-card-hd"><div class="eu-grow"><h2 class="t-card pl-card-t">' + esc(p.nombre) + '</h2>' + (sub ? '<p class="t-meta">' + sub + '</p>' : '') + '</div>' +
        '<button type="button" class="eu-iconbtn" data-edit="' + p.id + '" aria-label="Editar ' + esc(p.nombre) + '"><i data-lucide="pencil"></i></button></div>' +
        care(p, 'riego', 'droplet', 'Riego', 'riego_status', riegoTxt, 'riego_pct') +
        care(p, 'trasplante', 'sprout', 'Trasplante', 'trasplante_status', 'cada ' + p.meses_trasplante + ' meses', 'trasplante_pct') +
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
  function apply(d) { PLANTAS = d.state.plantas; sync(); render(); }

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
    var c = e.target.closest('[data-care]'); if (!c) return;
    var tipo = c.dataset.care, id = c.dataset.id; c.disabled = true;
    fetch(BASE + '/api/plantas/' + id + '/' + tipo, { method: 'POST' }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) { toast('Error al guardar', 'err'); c.disabled = false; return; }
      apply(d);
      toast(d.gam && d.gam.xp ? '+' + d.gam.xp + ' XP · +' + d.gam.ec + ' EC' : (tipo === 'riego' ? 'Riego registrado' : 'Trasplante registrado'), d.gam && d.gam.xp ? 'win' : 'ok');
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
    $('pl-delete-btn').hidden = !p.id;
    $('m-planta-t').textContent = p.id ? 'Editar planta' : 'Nueva planta';
    fotoFile = null; setFoto(p.foto ? BASE + '/foto/' + encodeURIComponent(p.foto) : null); hideSug();
    icons(); euModal.open('m-planta'); setTimeout(function () { $('pl-nombre').focus(); }, 20);
  }
  function openNew() { fill(null); }
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

  render();
})();
