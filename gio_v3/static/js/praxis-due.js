/* Praxis — fecha límite relativa (handoff Praxis v2, nota 6).
   relDue('2026-11-04', '2026-11-05') → {txt: 'Vencida 1 d', tone: 'danger'}
   · pasada → «Vencida N d» (danger) · hoy → «Hoy» (danger)
   · mañana → «Mañana» (warning) · < 7 días → «vie 13» (warning si faltan ≤ 3)
   · más adelante → «13 nov». Sin fecha → null.
   byDue: orden por fecha límite, primero las que tienen fecha.
   Se carga antes de praxis.js y también se prueba con Node (tests/). */
(function (root) {
  'use strict';
  var DAYS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
  var MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

  function parse(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function relDue(fecha, today) {
    var f = parse(fecha), t = parse(today);
    if (f == null || t == null) return null;
    var d = Math.round((f - t) / 86400000), x = new Date(f);
    if (d < 0) return { txt: 'Vencida ' + (-d) + ' d', tone: 'danger', days: d };
    if (d === 0) return { txt: 'Hoy', tone: 'danger', days: d };
    if (d === 1) return { txt: 'Mañana', tone: 'warning', days: d };
    if (d < 7) return { txt: DAYS[x.getUTCDay()] + ' ' + x.getUTCDate(), tone: d <= 3 ? 'warning' : '', days: d };
    return { txt: x.getUTCDate() + ' ' + MONTHS[x.getUTCMonth()], tone: '', days: d };
  }
  function byDue(a, b) {
    var fa = parse(a.fecha_limite), fb = parse(b.fecha_limite);
    if (fa == null && fb == null) return 0;
    if (fa == null) return 1;
    if (fb == null) return -1;
    return fa - fb;
  }
  var api = { relDue: relDue, byDue: byDue };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PxDue = api;
})(this);
