/* Cosmopolitismo v2 (/idiomas/) — un selector de idioma (id_lang) filtra toda la
   página: plan (tiempo contra hecho), «Repaso de hoy» de una pregunta a la vez
   (un solo POST al terminar, con XP y Acta), journal con «Revisar y guardar» y
   tendencia, y lateral con palabra del día, tests por destreza y Acta. */
(function () {
  'use strict';
  var root = document.getElementById('id');
  if (!root) return;
  var API = '/idiomas/api';
  var NOMBRE = { en: 'English', fr: 'Français' };
  function $(id) { return document.getElementById(id); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function getJ(u) { return fetch(u).then(function (r) { return r.json(); }); }
  function jpost(url, body) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); }); }
  function plural(n, s, p) { return n + ' ' + (n === 1 ? s : (p || s + 's')); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }

  /* ── Borrar (todas las vistas) ── */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.js-del-test, .js-del-j'); if (!b) return;
    e.preventDefault();
    var t = b.classList.contains('js-del-test');
    euConfirm(t ? '¿Eliminar este resultado?' : '¿Eliminar esta entrada?', { confirmLabel: 'Eliminar' }).then(function (ok) {
      if (!ok) return;
      fetch((t ? API + '/test/' : API + '/journal/') + b.dataset.id, { method: 'DELETE' }).then(function () {
        (b.closest('tr') || b.closest('.id-entry')).remove(); toast('Eliminado');
        if (!t && lang) cargar();
      });
    });
  });

  /* ── + Resultado (modal) ── */
  $$('.js-add-test').forEach(function (b) {
    b.addEventListener('click', function () {
      if (lang) $('tt-idioma').value = NOMBRE[lang];
      $('tt-score').value = ''; euModal.open('m-test'); setTimeout(function () { $('tt-score').focus(); }, 20);
    });
  });
  $('f-test').addEventListener('submit', function (e) {
    e.preventDefault();
    var score = $('tt-score').value.trim();
    if (!score) { toast('Ingresa el score', 'err'); $('tt-score').focus(); return; }
    jpost(API + '/test', { test_type: $('tt-type').value, idioma: $('tt-idioma').value, destreza: $('tt-destreza').value, score: score, test_date: $('tt-date').value }).then(function (d) {
      if (!d.ok) { toast('No se pudo guardar', 'err'); return; }
      euModal.close('m-test'); toast('Resultado guardado', 'ok');
      if (root.dataset.vista === 'tests') location.reload(); else cargar();
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Vista ?vista=plan: chips de checkpoints + reiniciar ── */
  if (root.dataset.vista === 'plan') {
    var cargarPlan = function () {
      getJ(API + '/plan').then(function (d) {
        $('plan-inicio').textContent = 'Inicio del plan: ' + d.inicio + ' · semana ' + d.semana_actual + ' de ' + d.total_semanas + ' · hecho ' + d.hecho_pct + '%';
        $('plan-cps').innerHTML = d.checkpoints.map(function (cp) {
          return '<button type="button" class="id-cp' + (cp.vencido && !cp.completado ? ' is-late' : '') + '" data-cp="' + cp.id + '" data-to="' + (cp.completado ? 0 : 1) + '" aria-pressed="' + !!cp.completado + '">' +
            '<span class="eu-between"><span class="t-eyebrow">' + (cp.completado ? 'Completada' : 'Fase ' + cp.fase) + '</span><span class="eu-act-check"><i data-lucide="check"></i></span></span>' +
            '<span class="t-ui">' + esc(cp.nombre) + '</span><span class="t-meta">Hasta semana ' + cp.semana_fin + ' · ' + esc(cp.fecha_objetivo) + '</span><span class="t-meta id-crit">' + esc(cp.criterio) + '</span></button>';
        }).join('');
        icons();
      });
    };
    $('plan-cps').addEventListener('click', function (e) {
      var b = e.target.closest('[data-cp]'); if (!b) return;
      jpost(API + '/plan/checkpoint/' + b.dataset.cp, { completado: b.dataset.to === '1' }).then(cargarPlan);
    });
    document.querySelector('.js-reiniciar').addEventListener('click', function () {
      euConfirm('¿Reiniciar el plan desde hoy? Los checkpoints vuelven a pendientes.', { confirmLabel: 'Reiniciar' }).then(function (ok) {
        if (ok) jpost(API + '/plan/reiniciar', {}).then(function () { toast('Plan reiniciado'); cargarPlan(); });
      });
    });
    cargarPlan();
    return;
  }
  if (root.dataset.vista) return;

  /* ══ Vista principal ══════════════════════════════════════════════════ */
  var lang = store('id_lang') === 'fr' ? 'fr' : 'en';
  var est = null, quiz = [], qi = 0, picked = null, answers = [], score = 0, roundId = null, libre = false;

  function setLang(l) {
    lang = l; store('id_lang', l);
    $$('#id-lang [data-lang]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.lang === l)); });
    $('j-text').placeholder = l === 'fr' ? 'Écrivez en français…' : 'Write in English…';
    $('j-res').hidden = true;
    cargar(true);
  }
  $$('#id-lang [data-lang]').forEach(function (b) { b.addEventListener('click', function () { if (b.dataset.lang !== lang) setLang(b.dataset.lang); }); });

  function cargar(conRepaso) {
    var l = lang;
    return getJ(API + '/estado?lang=' + l).then(function (d) {
      if (l !== lang) return;
      est = d;
      renderPlan(); renderPalabra(); renderTests(); renderJournal(); renderActa();
      if (conRepaso) iniciarRepaso();
    }).catch(function () { toast('No se pudo cargar Cosmopolitismo', 'err'); });
  }

  /* ── Plan ── */
  function renderPlan() {
    var p = est.plan, cp = p.siguiente_cp;
    $('plan-t').textContent = 'Plan C1 · semana ' + p.semana_actual + ' de ' + p.total_semanas + ' · Fase ' + p.fase_actual + (p.fase_nombre ? ' · ' + p.fase_nombre : '');
    $('plan-tiempo').style.setProperty('--p', p.progreso_pct + '%'); $('plan-tiempo-v').textContent = p.progreso_pct + '%';
    $('plan-hecho-l').textContent = 'Hecho · ' + p.hechos + '/' + p.checkpoints.length;
    $('plan-hecho').style.setProperty('--p', p.hecho_pct + '%'); $('plan-hecho-v').textContent = p.hecho_pct + '%';
    var a = $('plan-atraso');
    a.hidden = !(p.atraso_pts > 0);
    a.textContent = p.atraso_pts > 0 ? 'Vas ' + plural(p.atraso_pts, 'punto') + ' detrás del calendario' + (cp ? ': el checkpoint de la fase ' + cp.fase + ' vence en ' + plural(cp.semanas_restantes, 'semana') + '.' : '.') : '';
    $('cp-fase').textContent = cp ? 'Checkpoint · Fase ' + cp.fase : 'Plan completo';
    $('cp-t').textContent = cp ? cp.criterio : 'Todos los checkpoints cumplidos';
    $('cp-vence').textContent = cp ? 'vence sem ' + cp.semana_fin + ' · ' + (cp.semanas_restantes ? 'en ' + plural(cp.semanas_restantes, 'semana') : 'esta semana') : '';
  }

  /* ── Repaso de hoy ── */
  function dots() {
    $('rep-dots').innerHTML = quiz.map(function (_, k) {
      return '<i class="' + (k < qi || (k === qi && picked !== null) ? 'is-done' : k === qi ? 'is-cur' : '') + '"></i>';
    }).join('');
  }
  function iniciarRepaso(forzar) {
    quiz = []; qi = 0; picked = null; answers = []; score = 0; roundId = null;
    var v = est.vencidas;
    $('rep-dots').innerHTML = '';
    if (!v && !forzar) {
      $('rep-sub').textContent = 'Al día · próximo repaso mañana';
      $('rep-body').innerHTML = '<div class="id-rep-done"><i data-lucide="check-circle-2"></i><div class="eu-grow"><div class="id-rep-big">Al día</div><div class="t-meta">No tienes palabras vencidas en ' + NOMBRE[lang] + '.</div></div>' +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm js-libre">Ronda libre</button></div>';
      icons(); return;
    }
    libre = !v;
    $('rep-body').innerHTML = euSkelHTML(2, 48);
    getJ(API + '/quiz?lang=' + lang).then(function (d) {
      quiz = d.questions || []; roundId = 'r' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      $('rep-sub').textContent = (libre ? 'Ronda libre' : plural(d.vencidas, 'vencida')) + ' · ronda de ' + quiz.length + ' · ' + NOMBRE[lang];
      pregunta();
    }).catch(function () { $('rep-body').innerHTML = '<p class="t-meta">No se pudo cargar el repaso.</p>'; });
  }
  function pregunta() {
    var q = quiz[qi]; if (!q) return;
    var ans = picked !== null, ok = ans && picked === q.answer;
    var last = qi === quiz.length - 1;
    $('rep-body').innerHTML = '<div class="id-q"><div class="id-q-w">' + esc(q.word) + '</div><div class="t-meta">' + esc(q.tag || '') + '</div></div>' +
      '<div class="id-opts" role="group" aria-label="Opciones">' + q.options.map(function (o, k) {
        var c = ans && k === q.answer ? ' is-ok' : ans && k === picked ? ' is-bad' : '';
        return '<button type="button" class="id-opt' + c + '" data-opt="' + k + '"' + (ans ? ' disabled' : '') + '>' + esc(o) + '</button>';
      }).join('') + '</div>' +
      (ans ? '<div class="id-q-fb"><span class="' + (ok ? 'fg-success' : 'fg-danger') + '">' + (ok ? 'Correcto · vuelve en ' + plural(q.vuelve_ok || 2, 'día') : 'Era «' + esc(q.options[q.answer]) + '» · vuelve mañana') + '</span>' +
        '<button type="button" class="eu-btn eu-btn--primary js-next">' + (last ? 'Terminar' : 'Siguiente') + '</button></div>' : '');
    dots();
    var f = $('rep-body').querySelector(ans ? '.js-next' : '.id-opt'); if (f) f.focus();
  }
  $('rep-body').addEventListener('click', function (e) {
    var o = e.target.closest('[data-opt]'), n = e.target.closest('.js-next'), l = e.target.closest('.js-libre'), r = e.target.closest('.js-otra');
    if (o && picked === null) {
      picked = +o.dataset.opt; answers[qi] = { selected: picked };
      if (picked === quiz[qi].answer) score++;
      pregunta();
    } else if (n) {
      if (qi < quiz.length - 1) { qi++; picked = null; pregunta(); } else terminar(n);
    } else if (l) iniciarRepaso(true);
    else if (r) cargar(false).then(function () { iniciarRepaso(true); });
  });
  function terminar(btn) {
    btn.disabled = true;
    jpost(API + '/quiz/check', { questions: quiz, answers: answers, lang: lang, round_id: roundId }).then(function (d) {
      var px = d.proximos || { manana: 0, espaciadas: 0 };
      $('rep-sub').textContent = 'Listo por hoy';
      $('rep-body').innerHTML = '<div class="id-rep-done"><span class="id-rep-score num">' + d.score + '/' + d.total + '</span><div class="eu-grow">' +
        '<div class="id-rep-big">Repaso completo · +' + d.xp + ' XP</div><div class="t-meta">' + px.manana + ' vuelven mañana · ' + px.espaciadas + ' se espacian · Cosmopolitismo marcado en Acta Diurna</div></div>' +
        '<button type="button" class="eu-btn eu-btn--secondary eu-btn--sm js-otra">Otra ronda</button></div>';
      qi = quiz.length; dots();
      if (d.gam && window.euGam) euGam(d.gam, { el: $('id-rep') });
      est.vencidas = d.vencidas; est.acta = d.acta; renderActa();
    }).catch(function () { btn.disabled = false; toast('Sin conexión', 'err'); });
  }

  /* ── Journal ── */
  function contar() { var t = $('j-text').value.trim(); $('j-words').textContent = plural(t ? t.split(/\s+/).length : 0, 'palabra'); }
  $('j-text').addEventListener('input', contar);
  function corrHtml(cs) {
    return cs.length ? '<ul class="id-corr">' + cs.map(function (c) {
      return '<li><s>' + esc(c.issue) + '</s>' + (c.suggestion ? ' → <b>' + esc(c.suggestion) + '</b>' : '') + ' <span>· ' + esc(c.type) + '</span></li>';
    }).join('') + '</ul>' : '<p class="t-meta">Sin correcciones.</p>';
  }
  function entradaHtml(e) {
    return '<details class="id-entry" data-id="' + e.id + '"><summary class="id-entry-hd"><span class="id-mono12">' + esc(e.entry_date) + (e.fase ? ' · fase ' + e.fase : '') + ' · ' + esc(e.language) +
      (e.score != null ? ' · <b class="fg-brand">' + e.score + '</b>' : '') + '</span>' +
      '<button type="button" class="eu-iconbtn id-danger js-del-j" data-id="' + e.id + '" aria-label="Eliminar entrada"><i data-lucide="trash-2"></i></button>' +
      '<span class="id-entry-txt">' + esc(e.entry_text.slice(0, 200)) + (e.entry_text.length > 200 ? '…' : '') + '</span></summary>' +
      (e.score == null && !e.correcciones.length ? '<p class="t-meta">Sin revisión guardada.</p>' : corrHtml(e.correcciones)) + '</details>';
  }
  function renderJournal() {
    var j = est.journal, t = j.tendencia;
    $('j-spark').innerHTML = t.length ? t.map(function (v, k) {
      return '<i class="' + (k === t.length - 1 ? 'is-last' : '') + '" style="--h:' + Math.max(2, (v - 40) / 3) + 'px" title="' + v + '"></i>';
    }).join('') + '<span class="t-meta">últimas ' + t.length + '</span>' : '';
    $('j-prompt').innerHTML = 'Prompt de la fase ' + est.plan.fase_actual + ': <i>' + esc(est.prompt) + '</i>';
    $('j-list').innerHTML = j.entradas.length ? j.entradas.map(entradaHtml).join('') : euEmpty('notebook-pen', 'Sin entradas en ' + NOMBRE[lang], 'Escribe la primera arriba.', true);
    icons();
  }
  document.querySelector('.js-revisar').addEventListener('click', function () {
    var btn = this, text = $('j-text').value.trim();
    if (!text) { toast('Escribe algo primero', 'err'); $('j-text').focus(); return; }
    btn.disabled = true; btn.setAttribute('aria-busy', 'true');
    jpost(API + '/journal/revisar', { text: text, lang: lang }).then(function (d) {
      if (!d.ok) { toast(d.error || 'No se pudo guardar', 'err'); return; }
      var r = $('j-res'); r.hidden = false;
      r.innerHTML = d.lt_ok
        ? '<div class="id-fb-hd"><span class="id-fb-score num">' + d.score + '</span><span class="t-meta">≈ ' + d.grade + ' (estimado por errores) · ' + plural(d.total_issues, 'corrección', 'correcciones') + (d.xp ? ' · +' + d.xp + ' XP' : '') + '</span></div>' + corrHtml(d.corrections)
        : '<p class="id-fb-aviso">' + esc(d.aviso) + (d.xp ? ' · +' + d.xp + ' XP' : '') + '</p>';
      $('j-text').value = ''; contar();
      est.journal = d.journal; est.acta = d.acta; renderJournal(); renderActa();
      if (d.gam && d.gam.stats && window.euGam) euGam(d.gam, { el: btn });
      toast('Entrada guardada', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); }).finally(function () { btn.disabled = false; btn.removeAttribute('aria-busy'); });
  });

  /* ── Palabra del día (fija) ── */
  function renderPalabra() {
    var w = est.palabra;
    $('w-word').textContent = w.word; $('w-ph').textContent = w.phonetic || ''; $('w-ph').hidden = !w.phonetic;
    $('w-mean').textContent = w.meaning; $('w-ex').textContent = '«' + w.example + '»';
    var b = $('w-add');
    b.disabled = !!w.en_repaso; b.classList.toggle('is-on', !!w.en_repaso);
    b.innerHTML = w.en_repaso ? '<i data-lucide="check"></i>En tu repaso' : '<i data-lucide="plus"></i>Añadir a repaso';
    icons();
  }
  $('w-add').addEventListener('click', function () {
    jpost(API + '/word/srs', { lang: lang }).then(function (d) {
      if (!d.ok) return;
      est.palabra.en_repaso = true; renderPalabra(); toast('«' + d.word + '» entra a tu repaso mañana', 'ok');
    }).catch(function () { toast('Sin conexión', 'err'); });
  });

  /* ── Tests por destreza ── */
  function num(v) { return lang === 'fr' ? String(v) : (+v).toFixed(1); }
  function renderTests() {
    var t = est.tests;
    $('ts-t').textContent = t.titulo;
    var meta = t.meta / t.max * 100;
    $('ts-rows').innerHTML = t.skills.length ? t.skills.map(function (s) {
      return '<div class="id-skill' + (s.ok ? ' is-ok' : '') + '"><span class="id-skill-n">' + esc(s.nombre) + '</span>' +
        '<span class="id-skill-bar" style="--p:' + (s.valor / s.max * 100).toFixed(1) + '%;--m:' + meta.toFixed(1) + '%"><i></i><b aria-hidden="true"></b></span>' +
        '<span class="id-skill-v num">' + num(s.valor) + '</span></div>';
    }).join('') : '<p class="t-meta id-tests-empty">Sin resultados por destreza en ' + NOMBRE[lang] + '.</p>';
    $('ts-ft').textContent = t.skills.length ? 'Marca = C1 (' + num(t.meta) + (lang === 'fr' ? '/25' : '') + ')' + (t.brecha ? ' · ' + t.brecha + ' es la brecha' : '') : 'Todos los resultados →';
  }

  /* ── Acta ── */
  function renderActa() {
    var a = est.acta;
    $('acta-v').textContent = a.hechos + '/' + a.total + ' hoy';
    $('id-acta').classList.toggle('is-ok', a.total > 0 && a.hechos >= a.total);
  }

  setLang(lang);
})();
