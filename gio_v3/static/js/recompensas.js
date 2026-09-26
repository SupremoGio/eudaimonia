/* Recompensas (/recompensas/) — antes inline en recompensas/index.html.
   Endpoints (sin cambios):
     POST   /recompensas/api/rewards/<id>/redeem   canjear (puede traer bonus_ec)
     POST   /recompensas/api/rewards               crear
     PUT    /recompensas/api/rewards/<id>          editar
     DELETE /recompensas/api/rewards/<id>          eliminar
     POST   /recompensas/api/gasto  {ec, descripcion}  gasto libre de EC
     GET    /recompensas/api/gastos                historial */
(function () {
  'use strict';
  var root = document.getElementById('rw');
  if (!root) return;
  var RATE = parseInt(root.dataset.rate, 10) || 10;
  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return [].slice.call((el || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fmt(n) { return Number(n || 0).toLocaleString('es-MX'); }
  function json(url, method, body) {
    return fetch(url, { method: method || 'GET', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok && !d.error) d.error = 'Error ' + r.status; return d; }); });
  }
  function setBalance(ec) {
    root.dataset.ec = ec;
    $$('.js-ec').forEach(function (el) { el.textContent = ec; });
    $$('.js-ec-mxn').forEach(function (el) { el.textContent = fmt(ec * RATE); });
    $$('.eu-ec-val').forEach(function (el) { el.textContent = fmt(ec); });   // topbar / sidebar
  }

  // ── Filtros ────────────────────────────────────────────────────────────
  root.dataset.filter = 'all';
  var emptyF = $('.js-filter-empty');
  $$('.rw-filters [data-filter]').forEach(function (c) {
    c.addEventListener('click', function () {
      root.dataset.filter = c.dataset.filter;
      $$('.rw-filters [data-filter]').forEach(function (x) { x.setAttribute('aria-pressed', x === c ? 'true' : 'false'); });
      if (emptyF) emptyF.hidden = $$('.rw-card').some(function (k) { return k.offsetParent !== null; }) || !$('.rw-card');
    });
  });

  // ── Canjear ────────────────────────────────────────────────────────────
  root.addEventListener('click', function (e) {
    var card = e.target.closest('.rw-card'); if (!card) return;
    if (e.target.closest('.js-redeem')) return redeem(card, e.target.closest('.js-redeem'));
    if (e.target.closest('.js-edit')) return openForm(card);
    if (e.target.closest('.js-del')) return del(card);
  });

  function redeem(card, btn) {
    var name = card.dataset.name, cost = card.dataset.cost;
    euConfirm('¿Canjear «' + name + '» por ' + cost + ' EC?', { danger: false, confirmLabel: 'Canjear' }).then(function (ok) {
      if (!ok) return;
      btn.setAttribute('aria-busy', 'true');
      json('/recompensas/api/rewards/' + card.dataset.id + '/redeem', 'POST').then(function (d) {
        if (d.error) { toast(d.error, 'err'); btn.removeAttribute('aria-busy'); return; }
        setBalance(d.ec_remaining);
        if (d.bonus_ec > 0 && window.euRewardSheet) {
          euRewardSheet({ icon: 'sparkles', eyebrow: 'Racha de suerte', title: '+' + d.bonus_ec + ' EC de bono',
                          desc: name + ' canjeada — el azar te devolvió parte del costo.' });
          setTimeout(function () { location.reload(); }, 4200);
        } else {
          toast(name + ' canjeada · −' + cost + ' EC');
          setTimeout(function () { location.reload(); }, 1200);
        }
      }).catch(function () { toast('Error al canjear', 'err'); btn.removeAttribute('aria-busy'); });
    });
  }

  // ── Alta / edición en modal ────────────────────────────────────────────
  var editingId = null, form = $('.js-rw-form'), title = $('#rw-modal-t');
  function openForm(card) {
    editingId = card ? card.dataset.id : null;
    form.reset();
    $('#f-name').value = card ? card.dataset.name : '';
    $('#f-cost').value = card ? card.dataset.cost : 50;
    $('#f-lvl').value = card ? card.dataset.level : 1;
    $('#f-cool').value = card ? card.dataset.cool : 30;
    $('#f-cool').disabled = false;
    coolPrev = card && card.dataset.cool !== '0' ? card.dataset.cool : 30;
    $('#f-desc').value = card ? card.dataset.desc : '';
    $('#f-weekend').value = card ? (card.dataset.weekend || '0') : '0';
    $('#f-unica').checked = card ? card.dataset.unica === '1' : false;
    coolSync();
    if (title) title.textContent = card ? 'Editar recompensa' : 'Nueva recompensa';
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
    json(editingId ? '/recompensas/api/rewards/' + editingId : '/recompensas/api/rewards', editingId ? 'PUT' : 'POST', {
      name: name, ec_cost: parseInt($('#f-cost').value, 10) || 0, level_required: parseInt($('#f-lvl').value, 10) || 1,
      cooldown_days: parseInt($('#f-cool').value, 10) || 0, description: $('#f-desc').value.trim(), weekend_only: parseInt($('#f-weekend').value, 10) || 0,
      unica: $('#f-unica').checked,
    }).then(function (d) {
      if (d.error) { toast(d.error, 'err'); btn.removeAttribute('aria-busy'); return; }
      toast(editingId ? 'Recompensa actualizada' : 'Recompensa agregada');
      setTimeout(function () { location.reload(); }, 600);
    }).catch(function () { toast('Error al guardar', 'err'); btn.removeAttribute('aria-busy'); });
  }
  $('.js-rw-save').addEventListener('click', save);
  form.addEventListener('submit', function (e) { e.preventDefault(); save(); });

  function del(card) {
    euConfirm('¿Eliminar «' + card.dataset.name + '»?').then(function (ok) {
      if (!ok) return;
      fetch('/recompensas/api/rewards/' + card.dataset.id, { method: 'DELETE' }).then(function () {
        card.remove(); toast('Eliminada');
      }).catch(function () { toast('No se pudo eliminar', 'err'); });
    });
  }

  // ── Gasto libre: pesos ⇄ EC ────────────────────────────────────────────
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
      setBalance(r.ec_restante);
      spend.reset();
      toast('−' + n + ' EC · ' + d);
      loadHistory();
    }).catch(function () { toast('Error al registrar', 'err'); });
  });

  // ── Historial ──────────────────────────────────────────────────────────
  function loadHistory() {
    json('/recompensas/api/gastos').then(function (rows) {
      var list = $('.js-hist');
      list.innerHTML = rows.map(function (g) {
        return '<div class="eu-row"><div class="eu-row-main"><div class="eu-row-t">' + esc(g.description) + '</div>' +
               '<div class="eu-row-s">' + esc(g.date) + ' · $' + fmt(g.ec * RATE) + ' MXN</div></div>' +
               '<span class="eu-amt rw-minus">−' + g.ec + '</span></div>';
      }).join('');
      $('.js-hist-empty').hidden = rows.length > 0;
    }).catch(function () {});
  }
})();
