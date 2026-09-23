/* Cosmopolitismo (Idiomas) — Design System V2: plan C1, palabra del día,
   tests, quiz con repetición espaciada y journal con LanguageTool. */
(function () {
  'use strict';
  if (!document.getElementById('id')) return;
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function icons() { if (window.lucide) lucide.createIcons(); }
  function jpost(url, body) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); }).catch(function () { return {}; }); }

  /* ── Plan C1 ── */
  async function plan() {
    var d = await fetch('/idiomas/api/plan').then(function (r) { return r.json(); }).catch(function () { return null; });
    if (!d) return;
    $('plan-week').textContent = d.semana_actual;
    $('plan-fase').textContent = 'Semana ' + d.semana_actual + ' de ' + d.total_semanas + ' · Fase ' + d.fase_actual;
    $('plan-fase').removeAttribute('aria-busy');
    $('plan-bar').setAttribute('aria-valuenow', Math.round(d.progreso_pct));
    $('plan-inicio').textContent = 'Inicio del plan: ' + d.inicio;
    $('plan-fill').style.width = d.progreso_pct + '%';
    $('plan-ring').style.strokeDashoffset = 263.9 - Math.min(100, d.progreso_pct) / 100 * 263.9;
    $('plan-cps').innerHTML = d.checkpoints.map(function (cp) {
      return '<button type="button" class="id-cp' + (cp.vencido && !cp.completado ? ' is-late' : '') + '" data-cp="' + cp.id + '" data-to="' + (cp.completado ? 0 : 1) + '" aria-pressed="' + !!cp.completado + '">' +
        '<span class="eu-between"><span class="t-eyebrow">' + (cp.completado ? 'Completada' : 'Fase ' + cp.fase) + '</span><span class="eu-act-check"><i data-lucide="check"></i></span></span>' +
        '<span class="t-ui">' + esc(cp.nombre) + '</span><span class="t-meta">Hasta semana ' + cp.semana_fin + ' · ' + esc(cp.fecha_objetivo) + '</span><span class="t-meta id-crit">' + esc(cp.criterio) + '</span></button>';
    }).join('');
    icons();
  }
  $('plan-cps').addEventListener('click', async function (e) {
    var b = e.target.closest('[data-cp]'); if (!b) return;
    await jpost('/idiomas/api/plan/checkpoint/' + b.dataset.cp, { completado: b.dataset.to === '1' });
    plan();
  });

  /* ── Palabra del día ── */
  document.querySelector('.js-word').addEventListener('click', async function () {
    var d = await fetch('/idiomas/api/word/refresh').then(function (r) { return r.json(); }).catch(function () { return null; });
    if (!d) return;
    $('wph').textContent = d.phonetic; $('ww').textContent = d.word; $('wm').textContent = d.meaning;
    $('we').textContent = '«' + d.example + '»'; $('wf').textContent = 'FR · ' + d.french;
  });

  /* ── Tests ── */
  $('f-test').addEventListener('submit', async function (e) {
    e.preventDefault();
    var score = $('tt-score').value.trim();
    if (!score) { toast('Ingresa el score', 'err'); $('tt-score').focus(); return; }
    var d = await jpost('/idiomas/api/test', { test_type: $('tt-type').value, idioma: $('tt-idioma').value, destreza: $('tt-destreza').value, score: score, test_date: $('tt-date').value });
    if (d.ok) { toast('Resultado guardado'); setTimeout(function () { location.reload(); }, 500); } else toast('No se pudo guardar', 'err');
  });

  /* ── Journal ── */
  document.querySelector('.js-fb').addEventListener('click', async function () {
    var btn = this, text = $('j-text').value.trim();
    if (!text) { toast('Escribe algo primero', 'err'); return; }
    btn.setAttribute('aria-busy', 'true');
    var d = await jpost('/idiomas/api/language/feedback', { text: text, language: $('j-lang').value });
    btn.removeAttribute('aria-busy');
    if (!d.ok) { toast(d.error || 'Error al conectar', 'err'); return; }
    $('fb-score').textContent = d.score + ' / 100';
    $('fb-grade').textContent = 'Nivel estimado: ' + d.grade + ' · ' + d.total_issues + ' ' + (d.total_issues === 1 ? 'error' : 'errores');
    $('fb-words').textContent = d.word_count + ' palabras · LanguageTool';
    $('fb-list').innerHTML = d.corrections.length ? d.corrections.map(function (c) {
      return '<li><span class="eu-badge eu-badge--warning">' + esc(c.type) + '</span><span><s class="fg-danger">' + esc(c.issue) + '</s>' + (c.suggestion ? ' → <b class="fg-success">' + esc(c.suggestion) + '</b>' : '') + '<span class="t-meta"> — ' + esc(c.message) + '</span></span></li>';
    }).join('') : '<li class="fg-success">Sin errores detectados. Excelente escritura.</li>';
    $('fb-box').hidden = false;
  });
  document.querySelector('.js-save-j').addEventListener('click', async function () {
    var text = $('j-text').value.trim();
    if (!text) { toast('Escribe algo primero', 'err'); return; }
    var d = await jpost('/idiomas/api/journal', { language: $('j-lang').value, entry_text: text, fase: $('j-fase').value || null, destreza: $('j-destreza').value });
    if (d.ok) { toast('Entrada guardada', 'win'); setTimeout(function () { location.reload(); }, 500); } else toast('No se pudo guardar', 'err');
  });

  /* ── Quiz ── */
  var lang = 'en', quiz = [];
  document.querySelectorAll('[data-lang]').forEach(function (b) {
    b.addEventListener('click', function () { lang = b.dataset.lang; document.querySelectorAll('[data-lang]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); });
  });
  async function start() {
    $('quiz-res').hidden = true;
    var d = await fetch('/idiomas/api/quiz?lang=' + lang).then(function (r) { return r.json(); }).catch(function () { return null; });
    if (!d) { toast('No se pudo cargar el quiz', 'err'); return; }
    quiz = d.questions;
    $('quiz-qs').innerHTML = quiz.map(function (q, i) {
      return '<fieldset class="id-q"><legend class="t-ui">' + esc(q.word) + '</legend><p class="t-meta">' + esc(q.question) + '</p><div class="id-opts">' +
        q.options.map(function (o, j) { return '<label class="id-opt"><input type="radio" name="q' + i + '" value="' + j + '"><span>' + esc(o) + '</span></label>'; }).join('') + '</div></fieldset>';
    }).join('');
    $('quiz-body').hidden = false;
    if (d.repasando > 0) toast('Repasando ' + d.repasando + ' palabra' + (d.repasando === 1 ? '' : 's') + ' de repetición espaciada');
  }
  document.querySelectorAll('.js-quiz').forEach(function (b) { b.addEventListener('click', start); });
  document.querySelector('.js-check').addEventListener('click', async function () {
    var answers = quiz.map(function (_, i) { var s = document.querySelector('input[name="q' + i + '"]:checked'); return { selected: s ? +s.value : -1 }; });
    if (answers.some(function (a) { return a.selected < 0; })) { toast('Responde todas las preguntas', 'err'); return; }
    var d = await jpost('/idiomas/api/quiz/check', { questions: quiz, answers: answers, lang: lang });
    $('quiz-body').hidden = true;
    $('quiz-score').textContent = d.score + ' / ' + d.total;
    $('quiz-items').innerHTML = d.results.map(function (r) {
      return '<div class="id-q"><div class="t-ui ' + (r.correct ? 'fg-success' : 'fg-danger') + '"><i data-lucide="' + (r.correct ? 'check' : 'x') + '"></i>' + esc(r.word) + '</div><div class="id-opts">' +
        r.options.map(function (o, j) { var c = j === r.answer ? ' is-ok' : (j === r.selected && !r.correct ? ' is-bad' : ''); return '<div class="id-opt' + c + '"><span>' + esc(o) + '</span></div>'; }).join('') + '</div>' +
        (r.example ? '<p class="t-meta id-ex-s">«' + esc(r.example) + '»</p>' : '') + '</div>';
    }).join('');
    $('quiz-res').hidden = false; icons();
  });

  /* ── Borrar ── */
  document.addEventListener('click', async function (e) {
    var b = e.target.closest('.js-del-test, .js-del-j'); if (!b) return;
    var t = b.classList.contains('js-del-test');
    if (!(await euConfirm(t ? '¿Eliminar este resultado?' : '¿Eliminar esta entrada?', { confirmLabel: 'Eliminar' }))) return;
    await fetch((t ? '/idiomas/api/test/' : '/idiomas/api/journal/') + b.dataset.id, { method: 'DELETE' });
    (b.closest('tr') || b.closest('.id-entry')).remove(); toast('Eliminado');
  });
  plan();
})();
