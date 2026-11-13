/* Captura rápida (handoff Captura) — la hoja «+» del móvil y ⌘K que registra.
   Una sola fuente: nav.QUICK (llega en #eu-quick-data, ya filtrado por
   permisos y ordenado por uso). Cada registro postea al endpoint que ya usa su
   módulo; aquí no hay reglas de negocio, solo:
     · el formulario (chips, nunca <select>; money/number en mono),
     · el POST (+ pasos «then»), el contador de uso y el aviso con Deshacer,
     · los contadores de la barra (Acta · anclas que faltan, Praxis · vencidas),
     · el parser de frases para ⌘K («gasto 180 tacos», «peso 78.2»…), sin red.
   API global: window.euQuick = {data, parse, describe, options, save, openSheet,
   renderForm, refreshBadges}. El parser también se exporta para Node (tests). */
(function (root) {
  'use strict';

  /* ── Parser (sin red; probado con tests/quick_parse_cases.json) ──────── */
  function norm(t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function num(t) {
    var s = String(t || '').replace(/^\$/, '').trim();
    if (!/^\d[\d.,]*$/.test(s)) return null;
    // «84,500» y «1,250.50» → miles con coma; «78,2» → decimal con coma
    if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, '');
    else s = s.replace(',', '.');
    var n = parseFloat(s);
    return isNaN(n) ? null : n;
  }
  var COMIDA_SLOTS = { desayuno: 'desayuno', comida: 'comida', cena: 'cena', colacion: 'colación', snack: 'colación' };

  /* parse(texto, QUICK) → {id, values, missing, ready} o null si el primer
     token no es un sinónimo de ningún registro (⌘K sigue como siempre). */
  function parse(text, quick) {
    var toks = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!toks.length) return null;
    var first = norm(toks[0]);
    var q = (quick || []).filter(function (r) { return (r.keywords || []).some(function (k) { return norm(k) === first; }); })[0];
    if (!q) return null;
    var rest = toks.slice(1), values = {}, words = [];
    var f = q.fields || [];
    var numField = f.filter(function (x) { return x.kind === 'money' || x.kind === 'number'; })[0];
    var txtField = f.filter(function (x) { return x.kind === 'text'; })[0];
    if (q.id === 'comida' && COMIDA_SLOTS[first]) values.meal_slot = COMIDA_SLOTS[first];
    rest.forEach(function (t) {
      var n = num(t), nt = norm(t);
      if (numField && n !== null && values[numField.name] === undefined) { values[numField.name] = n; return; }
      if (q.id === 'baile' && n !== null && values.min === undefined) { values.min = n; return; }
      if (q.id === 'tarea' && (nt === 'hoy' || nt === 'manana')) { values.cuando = nt; return; }
      if (q.id === 'comida' && COMIDA_SLOTS[nt] && !values.meal_slot) { values.meal_slot = COMIDA_SLOTS[nt]; return; }
      if (q.id === 'comida' && (nt === 'desliz' || nt === 'mal')) { values.como = 'desliz'; return; }
      words.push(t);
    });
    if (words.length) {
      if (txtField) values[txtField.name] = words.join(' ');
      else if (q.id === 'actividad') values.key_text = words.join(' ');
    }
    var missing = f.filter(function (x) {
      if (x.kind === 'chips') return false;                   // los chips traen default
      if (x.fallback) return false;
      return values[x.name] === undefined || values[x.name] === '';
    }).map(function (x) { return x.name; });
    if (q.id === 'actividad' && !values.key_text) missing.push('key');
    return { id: q.id, values: values, missing: missing, ready: !!q.post && !missing.length };
  }

  if (typeof module !== 'undefined' && module.exports) { module.exports = { parse: parse, num: num, norm: norm }; return; }

  /* ── Navegador ──────────────────────────────────────────────────────── */
  var doc = root.document;
  var QUICK = [];
  try { QUICK = JSON.parse(doc.getElementById('eu-quick-data').textContent || '[]'); } catch (e) { QUICK = []; }
  var BY = {}; QUICK.forEach(function (q) { BY[q.id] = q; });
  var optCache = {};

  function $(id) { return doc.getElementById(id); }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function icons() { try { root.lucide.createIcons(); } catch (e) {} }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function ymd(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }

  function options(id) {
    if (optCache[id]) return Promise.resolve(optCache[id]);
    return fetch('/api/quick/options?id=' + encodeURIComponent(id)).then(function (r) { return r.json(); })
      .then(function (d) { optCache[id] = d.fields || {}; return optCache[id]; });
  }

  /* Valores finales: lo que puso la persona + defaults de /options; los
     textos del parser (comida «cena», actividad «gym») se resuelven contra
     las opciones del día. */
  function resolveValues(q, vals, opts) {
    var v = {};
    (q.fields || []).forEach(function (f) {
      var o = opts[f.name] || {};
      var x = vals[f.name];
      if (x === undefined || x === '') x = o.default != null ? o.default : f.default;
      v[f.name] = x;
    });
    if (vals.meal_slot && opts.meal) {
      var m = (opts.meal.options || []).filter(function (op) { return norm(op.label).indexOf(norm(vals.meal_slot)) === 0; })[0];
      if (m) v.meal = m.value;
    }
    if (vals.key_text && opts.key) {
      var w = norm(vals.key_text);
      var a = (opts.key.options || []).filter(function (op) { return norm(op.label).indexOf(w) >= 0; })[0];
      if (a) v.key = a.value;
    }
    if (vals.como) v.como = vals.como;
    if (vals.cuando) v.cuando = vals.cuando;
    return v;
  }

  function fill(tpl, ctx) {
    if (typeof tpl === 'string') {
      var whole = tpl.match(/^\{(\w+)\}$/);
      if (whole) return ctx[whole[1]];
      return tpl.replace(/\{(\w+)\}/g, function (_, k) { return ctx[k] == null ? '' : ctx[k]; });
    }
    if (Array.isArray(tpl)) return tpl.map(function (x) { return fill(x, ctx); });
    if (tpl && typeof tpl === 'object') { var o = {}; Object.keys(tpl).forEach(function (k) { o[k] = fill(tpl[k], ctx); }); return o; }
    return tpl;
  }
  function ctxOf(q, v, extra) {
    var now = new Date(), man = new Date(now.getTime() + 864e5);
    var c = { today: ymd(now), tomorrow: ymd(man), hora: pad(now.getHours()) + ':' + pad(now.getMinutes()) };
    (q.fields || []).forEach(function (f) {
      var x = v[f.name];
      if ((f.kind === 'money' || f.kind === 'number') && x !== '' && x != null) x = num(x);
      if ((x === '' || x == null) && f.fallback) x = fill(f.fallback, c);
      c[f.name] = x;
    });
    return Object.assign(c, extra || {});
  }
  function call(step, ctx) {
    var o = { method: step.method, headers: { 'Content-Type': 'application/json' } };
    if (step.body) o.body = JSON.stringify(fill(step.body, ctx));
    return fetch(fill(step.url, ctx), o).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok || j.ok === false || (j.error && !j.id && !j.log_id)) throw new Error(j.error || 'No se pudo guardar');
        return j;
      });
    });
  }

  /* save(id, valores) → {res, msg, undo()} — el mismo POST para la hoja y ⌘K. */
  function save(id, vals) {
    var q = BY[id];
    if (!q || !q.post) return Promise.reject(new Error('Este registro se hace en su pantalla'));
    return options(id).then(function (opts) {
      var v = resolveValues(q, vals || {}, opts);
      var ctx = ctxOf(q, v);
      return call(q.post, ctx).then(function (res) {
        if (q.id_from && res[q.id_from] != null) ctx.id = res[q.id_from];
        var pasos = (q.then || []).filter(function (s) { return Object.keys(s.if || {}).every(function (k) { return String(v[k]) === String(s.if[k]); }); });
        return pasos.reduce(function (p, s) { return p.then(function () { return call(s, ctx); }); }, Promise.resolve()).then(function () {
          fetch('/api/quick/uso', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id, values: v }) }).catch(function () {});
          delete optCache[id];
          var gam = res.gam || {};
          var xp = gam.xp || res.xp || res.xp_earned || 0;
          return { res: res, xp: xp, gam: gam, msg: q.label + ' guardado' + (xp > 0 ? ' · +' + xp + ' XP' : ''),
                   undo: q.undo ? function () { return call(q.undo, ctx); } : null };
        });
      });
    });
  }

  /* Aviso con «Deshacer» (mismo host aria-live que toast()). */
  function quickToast(msg, undo) {
    var host = $('eu-toasts');
    if (!host || !undo) { if (root.toast) root.toast(msg, 'win'); return; }
    Array.prototype.slice.call(host.children).forEach(function (c) { c.remove(); });
    var t = doc.createElement('div');
    t.className = 'eu-toast eu-toast--xp eu-quick-toast';
    t.innerHTML = '<i data-lucide="circle-check" aria-hidden="true"></i><span class="grow"></span><button type="button" class="eu-quick-undo">Deshacer</button>';
    t.querySelector('.grow').textContent = msg;
    host.appendChild(t); icons();
    var gone = setTimeout(function () { t.remove(); }, 6000);
    t.querySelector('.eu-quick-undo').addEventListener('click', function () {
      clearTimeout(gone); t.remove();
      undo().then(function () { if (root.toast) root.toast('Deshecho'); after(); })
        .catch(function (e) { if (root.toast) root.toast(e.message || 'No se pudo deshacer', 'err'); });
    });
  }
  function after() {
    if (root.euRefreshXp) root.euRefreshXp();
    refreshBadges();
    try { doc.dispatchEvent(new CustomEvent('eu:quick-saved')); } catch (e) {}
  }
  function done(r) {
    quickToast(r.msg, r.undo);
    if (r.gam && r.gam.stats && root.euGam) root.euGam(r.gam, {});
    after();
  }

  /* ── Formulario (hoja móvil y panel de ⌘K) ─────────────────────────── */
  function renderForm(box, id, vals, hooks) {
    var q = BY[id]; if (!q) return;
    hooks = hooks || {};
    box.innerHTML = '<div class="eu-quick-fhd"><button type="button" class="eu-iconbtn js-qback" aria-label="Volver"><i data-lucide="chevron-left"></i></button>' +
      '<span class="t-section">' + esc(q.label) + '</span>' + (q.reward ? '<span class="eu-quick-rw num">' + esc(q.reward) + '</span>' : '') + '</div>' +
      '<div class="eu-quick-fields">' + (root.euSkelHTML ? root.euSkelHTML(2, 44) : '') + '</div>' +
      '<div class="eu-err eu-quick-err" role="alert" hidden><i data-lucide="alert-circle"></i><span></span></div>' +
      '<button type="submit" class="eu-btn eu-btn--primary eu-btn--block eu-quick-save">Guardar</button>';
    icons();
    var state = Object.assign({}, vals || {});
    box.querySelector('.js-qback').onclick = function () { if (hooks.back) hooks.back(); };
    options(id).then(function (opts) {
      var v = resolveValues(q, state, opts);
      var html = (q.fields || []).map(function (f, i) {
        var o = opts[f.name] || {}, fid = 'eu-qf-' + id + '-' + f.name;
        if (f.kind === 'chips') {
          var ops = o.options || f.options || [];
          if (!ops.length) return '<div class="eu-field"><span class="eu-label">' + esc(f.label) + '</span><p class="t-meta">Nada pendiente por ahora.</p></div>';
          return '<div class="eu-field"><span class="eu-label" id="' + fid + '">' + esc(f.label) + '</span><div class="eu-quick-chips" role="radiogroup" aria-labelledby="' + fid + '">' +
            ops.map(function (op) {
              var on = String(v[f.name]) === String(op.value);
              return '<button type="button" role="radio" class="eu-chip eu-quick-chip" data-f="' + esc(f.name) + '" data-v="' + esc(op.value) + '" aria-checked="' + on + '"' + (op.hint ? ' title="' + esc(op.hint) + '"' : '') + '>' + esc(op.label) + '</button>';
            }).join('') + '</div></div>';
        }
        var mono = f.kind === 'money' || f.kind === 'number';
        var hint = o.actual != null ? '<span class="t-meta">Ahora: <span class="num">' + esc(o.actual) + '</span>' + (o.vehiculo ? ' · ' + esc(o.vehiculo) : '') + '</span>' : '';
        return '<div class="eu-field"><label class="eu-label" for="' + fid + '">' + esc(f.label) + '</label>' +
          '<input class="eu-input' + (mono ? ' eu-input--money' : '') + '" id="' + fid + '" data-f="' + esc(f.name) + '" ' +
          (mono ? 'inputmode="' + (f.kind === 'money' || f.step === 'any' ? 'decimal' : 'numeric') + '"' : 'type="text"') +
          ' placeholder="' + esc(f.placeholder || '') + '" value="' + esc(state[f.name] != null ? state[f.name] : '') + '">' + hint + '</div>';
      }).join('');
      box.querySelector('.eu-quick-fields').innerHTML = html || '<p class="t-meta">Este registro se hace en su pantalla.</p>';
      Object.keys(v).forEach(function (k) { if (state[k] === undefined && v[k] != null && (q.fields || []).some(function (f) { return f.name === k && f.kind === 'chips'; })) state[k] = v[k]; });
      icons();
      var first = box.querySelector('.eu-quick-fields input, .eu-quick-fields [aria-checked=true], .eu-quick-fields button');
      if (first) setTimeout(function () { first.focus(); }, 30);
    }).catch(function () { box.querySelector('.eu-quick-fields').innerHTML = '<p class="t-meta">No se pudieron cargar las opciones.</p>'; });

    box.onclick = function (e) {
      var c = e.target.closest('[data-v]'); if (!c) return;
      state[c.dataset.f] = c.dataset.v;
      box.querySelectorAll('[data-f="' + c.dataset.f + '"][data-v]').forEach(function (b) { b.setAttribute('aria-checked', String(b === c)); });
    };
    box.oninput = function (e) { var i = e.target.closest('input[data-f]'); if (i) state[i.dataset.f] = i.value; };
    box.onsubmit = function (e) {
      e.preventDefault();
      var err = box.querySelector('.eu-quick-err'), btn = box.querySelector('.eu-quick-save');
      var falta = (q.fields || []).filter(function (f) { return f.kind !== 'chips' && !f.fallback && (state[f.name] == null || String(state[f.name]).trim() === ''); })[0];
      if (falta) { err.hidden = false; err.querySelector('span').textContent = 'Falta ' + falta.label.toLowerCase(); var inp = box.querySelector('[data-f="' + falta.name + '"]'); if (inp) inp.focus(); return; }
      btn.disabled = true; err.hidden = true;
      save(id, state).then(function (r) { if (hooks.saved) hooks.saved(r); done(r); })
        .catch(function (x) { err.hidden = false; err.querySelector('span').textContent = x.message || 'No se pudo guardar'; })
        .finally(function () { btn.disabled = false; });
    };
  }

  /* ── Hoja «+» (móvil) ──────────────────────────────────────────────── */
  var sheet = $('eu-quick'), btn = $('eu-quick-btn'), pick = $('eu-quick-pick'), form = $('eu-quick-form');
  var opener = null;
  function step(id, vals) {
    if (!id) { form.hidden = true; form.innerHTML = ''; pick.hidden = false; var f = pick.querySelector('[data-quick]'); if (f) f.focus(); return; }
    var q = BY[id];
    if (q && !q.post) { root.location.href = q.url; return; }
    pick.hidden = true; form.hidden = false;
    renderForm(form, id, vals, { back: function () { step(null); }, saved: function () { openSheet(false); } });
  }
  /* Diálogo con euDialog (handoff A11y, S2): foco atrapado, Esc (vuelve del
     formulario a la lista; en la lista, cierra) y regreso del foco. */
  function marcar(open) { if (btn) { btn.setAttribute('aria-expanded', open ? 'true' : 'false'); btn.classList.toggle('is-open', !!open); } }
  function openSheet(open, id, vals) {
    if (!sheet || !root.euDialog) return;
    if (open) {
      opener = doc.activeElement;
      root.euDialog.open(sheet, opener, {
        focus: false,
        onEscape: function () { if (!form.hidden) { step(null); return true; } },
        onClose: function () { form.innerHTML = ''; marcar(false); },
      });
      marcar(true); step(id || null, vals);
    } else root.euDialog.close(sheet);
  }
  if (btn) btn.addEventListener('click', function () { openSheet(sheet.hidden); });
  if (sheet) {
    sheet.addEventListener('click', function (e) {
      if (e.target === sheet) { openSheet(false); return; }
      var c = e.target.closest('[data-quick]'); if (c) step(c.dataset.quick);
    });
  }

  /* ── Contadores de la barra ─────────────────────────────────────────── */
  function refreshBadges() {
    var links = doc.querySelectorAll('[data-badge-for]');
    if (!links.length || (root.matchMedia && !root.matchMedia('(max-width: 1023px)').matches)) return;
    fetch('/api/quick/badges').then(function (r) { return r.json(); }).then(function (d) {
      links.forEach(function (a) {
        var n = d[a.dataset.badgeFor] || 0, b = a.querySelector('.eu-bnav-badge');
        b.hidden = !n; b.textContent = n > 9 ? '9+' : n;
        a.setAttribute('aria-label', a.dataset.label + (n ? ', ' + n + ' pendiente' + (n === 1 ? '' : 's') : ''));
      });
    }).catch(function () {});
  }
  refreshBadges();

  /* Descripción de una frase reconocida para ⌘K: «Gasto · $180», detalle con defaults. */
  function describe(p) {
    var q = BY[p.id]; if (!q) return Promise.resolve(null);
    return options(p.id).then(function (opts) {
      var v = resolveValues(q, p.values, opts), det = [], title = q.label;
      function lab(f) { var o = (opts[f] || {}).options || ((q.fields || []).filter(function (x) { return x.name === f; })[0] || {}).options || []; var m = o.filter(function (x) { return String(x.value) === String(v[f]); })[0]; return m ? m.label : ''; }
      if (p.id === 'gasto') { title += v.monto != null ? ' · $' + Number(v.monto).toLocaleString('es-MX') : ''; det = [v.concepto || 'sin concepto', lab('categoria'), lab('cuenta')]; }
      else if (p.id === 'peso') { title += v.kg != null ? ' · ' + v.kg + ' kg' : ''; det = [(opts.kg || {}).actual ? 'antes ' + opts.kg.actual + ' kg' : '']; }
      else if (p.id === 'km') { title = 'Odómetro' + (v.km != null ? ' · ' + Number(v.km).toLocaleString('es-MX') + ' km' : ''); det = [(opts.km || {}).vehiculo || '', (opts.km || {}).actual != null ? 'ahora ' + Number(opts.km.actual).toLocaleString('es-MX') + ' km' : '']; }
      else if (p.id === 'tarea' || p.id === 'nota') { title += v.texto ? ' · ' + v.texto : ''; det = [p.id === 'nota' ? 'Ideas de Praxis' : lab('cuando')]; }
      else if (p.id === 'baile') { title += ' · ' + v.min + ' min'; det = ['flow ' + lab('flow')]; }
      else if (p.id === 'comida') { title = lab('meal') || 'Comida'; det = [v.como === 'desliz' ? 'con desliz' : 'limpia', 'Díaita · hoy']; if (!v.meal) p.missing = ['meal']; }
      else if (p.id === 'actividad') { title = lab('key') || 'Actividad'; if (!v.key) p.missing = ['key']; }
      return { title: title, detail: det.filter(Boolean).join(' · '), reward: q.reward || '', icon: q.icon, ready: !!q.post && !(p.missing || []).length, values: v };
    });
  }

  root.euQuick = { data: QUICK, byId: BY, parse: function (t) { return parse(t, QUICK); }, describe: describe, options: options,
                   save: save, done: done, openSheet: openSheet, renderForm: renderForm, refreshBadges: refreshBadges };
})(typeof window !== 'undefined' ? window : this);
