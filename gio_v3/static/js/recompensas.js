/* Recompensas (/recompensas/) — handoff Recompensas v2.
   Endpoints:
     POST   /recompensas/api/rewards/<id>/redeem   canjear (saldo_antes/despues, bonus_ec)
     POST   /recompensas/api/redeem/<id>/undo      deshacer (10 min)
     POST   /recompensas/api/rewards               crear
     PUT    /recompensas/api/rewards/<id>          editar
     DELETE /recompensas/api/rewards/<id>          eliminar (desde el modal)
     POST   /recompensas/api/gasto  {ec, descripcion}  gasto libre de EC
   Tras canjear, deshacer o gastar, el héroe, los grupos y el historial se
   vuelven a pedir al servidor (misma página) y se reemplazan sin recargar. */
(function () {
  'use strict';
  var root = document.getElementById('rw');
  if (!root) return;
  var RATE = parseInt(root.dataset.rate, 10) || 10;
  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return [].slice.call((el || document).querySelectorAll(s)); }
  function fmt(n) { return Number(n || 0).toLocaleString('es-MX'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function json(url, method, body) {
    return fetch(url, { method: method || 'GET', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok && !d.error) d.error = 'Error ' + r.status; return d; }); });
  }
  function setTopbar(ec) {
    root.dataset.ec = ec;
    $$('.eu-ec-val').forEach(function (el) { el.textContent = fmt(ec); });   // topbar / sidebar
  }

  /* Vuelve a pedir la página y reemplaza héroe, grupos, wishlists e historial */
  function refresh() {
    return fetch(location.pathname, { headers: { 'X-Requested-With': 'fetch' } }).then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      ['#rw-hero', '#rw-main', '#rw-hist'].forEach(function (sel) {
        var a = $(sel), b = $(sel, doc);
        if (a && b) a.replaceWith(b);
      });
      var w = $('.rw-wish'), w2 = $('.rw-wish', doc);
      if (w && w2) w.replaceWith(w2); else if (w && !w2) w.remove();
      var nr = $('#rw', doc); if (nr) setTopbar(nr.dataset.ec);
      icons();
    }).catch(function () { location.reload(); });
  }

  /* ── Canjear con confirmación (nota 4) ── */
  var undoBar = $('#rw-undo'), undoTimer = null, lastId = null;
  function closeAsk(card) {
    card.classList.remove('is-asking');
    $('.js-ask', card).hidden = false;
    $('.rw-confirm', card).hidden = true;
  }
  function showUndo(text, id) {
    lastId = id;
    $('.js-undo-t', undoBar).textContent = text;
    undoBar.hidden = false; icons();
    clearTimeout(undoTimer);
    undoTimer = setTimeout(function () { undoBar.hidden = true; lastId = null; }, 10 * 60 * 1000);
  }
  root.addEventListener('click', function (e) {
    var card = e.target.closest('.rw-av');
    if (card && e.target.closest('.js-ask')) {
      $$('.rw-av.is-asking').forEach(closeAsk);
      card.classList.add('is-asking');
      e.target.closest('.js-ask').hidden = true;
      $('.rw-confirm', card).hidden = false;
      $('.js-confirm', card).focus();
      return;
    }
    if (card && e.target.closest('.js-cancel')) { closeAsk(card); return; }
    if (card && e.target.closest('.js-confirm')) { redeem(card, e.target.closest('.js-confirm')); return; }
    var item = e.target.closest('[data-id]');
    if (item && e.target.closest('.js-edit')) openForm(item);
  });

  function redeem(card, btn) {
    var name = card.dataset.name, cost = card.dataset.cost, id = card.dataset.id;
    btn.setAttribute('aria-busy', 'true');
    json('/recompensas/api/rewards/' + id + '/redeem', 'POST').then(function (d) {
      if (d.error) { toast(d.error, 'err'); btn.removeAttribute('aria-busy'); return; }
      showUndo(name + ' canjeado · −' + cost + ' EC · saldo ' + d.saldo_despues + ' EC', id);
      if (d.bonus_ec > 0 && window.euRewardSheet) {
        euRewardSheet({ icon: 'sparkles', eyebrow: 'Racha de suerte', title: '+' + d.bonus_ec + ' EC de bono',
                        desc: name + ' canjeada — el azar te devolvió parte del costo.' });
      }
      refresh();
    }).catch(function () { toast('Error al canjear', 'err'); btn.removeAttribute('aria-busy'); });
  }
  $('.js-undo', undoBar).addEventListener('click', function () {
    if (!lastId) return;
    var b = this; b.setAttribute('aria-busy', 'true');
    json('/recompensas/api/redeem/' + lastId + '/undo', 'POST').then(function (d) {
      b.removeAttribute('aria-busy');
      undoBar.hidden = true; lastId = null;
      if (d.error) { toast(d.error, 'err'); return; }
      toast('Canje deshecho');
      refresh();
    }).catch(function () { b.removeAttribute('aria-busy'); toast('No se pudo deshacer', 'err'); });
  });

  /* ── Alta / edición / borrado en el modal (nota 8) ── */
  var editing = null, form = $('.js-rw-form'), title = $('#rw-modal-t'), delBtn = $('.js-del');
  function openForm(item) {
    editing = item ? { id: item.dataset.id, name: item.dataset.name } : null;
    form.reset();
    $('#f-name').value = item ? item.dataset.name : '';
    $('#f-cost').value = item ? item.dataset.cost : 50;
    $('#f-lvl').value = item ? item.dataset.level : 1;
    $('#f-cool').value = item ? item.dataset.cool : 30;
    $('#f-cool').disabled = false;
    coolPrev = item && item.dataset.cool !== '0' ? item.dataset.cool : 30;
    $('#f-desc').value = item ? item.dataset.desc : '';
    $('#f-weekend').value = item ? (item.dataset.weekend || '0') : '0';
    $('#f-max').value = item ? (item.dataset.max || '0') : '0';
    $('#f-unica').checked = item ? item.dataset.unica === '1' : false;
    coolSync();
    if (title) title.textContent = item ? 'Editar recompensa' : 'Nueva recompensa';
    if (delBtn) delBtn.hidden = !item;
    euModal.open('rw-modal');
  }
  /* Una recompensa única no tiene cooldown: se canjea una vez y queda como Conseguida */
  var coolPrev = 30;
  function coolSync() {
    var u = $('#f-unica').checked, f = $('#f-cool');
    if (u && !f.disabled) coolPrev = f.value || coolPrev;
    f.disabled = u;
    f.value = u ? 0 : (f.value === '0' && coolPrev ? coolPrev : f.value);
  }
  $('#f-unica').addEventListener('change', coolSync);
  $$('.js-new').forEach(function (b) { b.addEventListener('click', function () { openForm(null); }); });
  function save() {
    var name = $('#f-name').value.trim();
    if (!name) { $('#f-name').focus(); return; }
    var btn = $('.js-rw-save'); btn.setAttribute('aria-busy', 'true');
    json(editing ? '/recompensas/api/rewards/' + editing.id : '/recompensas/api/rewards', editing ? 'PUT' : 'POST', {
      name: name, ec_cost: parseInt($('#f-cost').value, 10) || 0, level_required: parseInt($('#f-lvl').value, 10) || 1,
      cooldown_days: parseInt($('#f-cool').value, 10) || 0, description: $('#f-desc').value.trim(), weekend_only: parseInt($('#f-weekend').value, 10) || 0,
      unica: $('#f-unica').checked, max_por_ventana: parseInt($('#f-max').value, 10) || 0,
    }).then(function (d) {
      btn.removeAttribute('aria-busy');
      if (d.error) { toast(d.error, 'err'); return; }
      euModal.close('rw-modal');
      toast(editing ? 'Recompensa actualizada' : 'Recompensa agregada');
      refresh();
    }).catch(function () { toast('Error al guardar', 'err'); btn.removeAttribute('aria-busy'); });
  }
  $('.js-rw-save').addEventListener('click', save);
  form.addEventListener('submit', function (e) { e.preventDefault(); save(); });
  if (delBtn) delBtn.addEventListener('click', function () {
    if (!editing) return;
    var ed = editing;
    euConfirm('¿Eliminar «' + ed.name + '»?').then(function (ok) {
      if (!ok) return;
      fetch('/recompensas/api/rewards/' + ed.id, { method: 'DELETE' }).then(function () {
        euModal.close('rw-modal'); toast('Eliminada'); refresh();
      }).catch(function () { toast('No se pudo eliminar', 'err'); });
    });
  });

  /* ── Gasto libre: pesos ⇄ EC ── */
  var pesos = $('#g-pesos'), ec = $('#g-ec'), desc = $('#g-desc');
  if (pesos) pesos.addEventListener('input', function () { var p = parseFloat(pesos.value) || 0; ec.value = p > 0 ? Math.round(p / RATE) : ''; });
  if (ec) ec.addEventListener('input', function () { var n = parseFloat(ec.value) || 0; pesos.value = n > 0 ? n * RATE : ''; });
  var spend = $('.js-spend');
  if (spend) spend.addEventListener('submit', function (e) {
    e.preventDefault();
    var n = parseInt(ec.value, 10) || 0, d = desc.value.trim();
    if (n <= 0) { toast('Ingresa los EC a gastar', 'err'); ec.focus(); return; }
    if (!d) { toast('Describe en qué lo gastaste', 'err'); desc.focus(); return; }
    json('/recompensas/api/gasto', 'POST', { ec: n, descripcion: d }).then(function (r) {
      if (r.error) { toast(r.error, 'err'); return; }
      spend.reset();
      toast('−' + n + ' EC · ' + d);
      refresh();
    }).catch(function () { toast('Error al registrar', 'err'); });
  });

  /* ── Canjes recientes: «Todo →» despliega el resto ── */
  root.addEventListener('click', function (e) {
    var b = e.target.closest('.js-hist-all'); if (!b) return;
    var open = b.getAttribute('aria-expanded') !== 'true';
    $$('#rw-hist .rw-hrow').forEach(function (r, i) { if (i >= 4) r.hidden = !open; });
    b.setAttribute('aria-expanded', String(open));
    b.textContent = open ? 'Menos' : 'Todo →';
  });
})();
