(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // Mobile menu
  var menu = $('#menu'), side = $('#side');
  if (menu) menu.addEventListener('click', function () { menu.setAttribute('aria-expanded', side.classList.toggle('open')); });

  // Every destructive action asks first. Put data-confirm="Question?" on a form or button.
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute('data-confirm') || (e.submitter && e.submitter.getAttribute('data-confirm'));
    if (msg && !window.confirm(msg)) e.preventDefault();
  }, true);

  // Filters submit by themselves when changed
  $$('.tools select').forEach(function (s) { s.addEventListener('change', function () { s.form.submit(); }); });

  // "Select all" tick-boxes
  $$('[data-all]').forEach(function (a) {
    a.addEventListener('change', function () { $$('input[name="' + a.dataset.all + '"]').forEach(function (c) { c.checked = a.checked; }); });
  });

  // "Who is it for?" – show the student picker or the batch picker, not both
  var target = $('select[name="target"]');
  if (target) {
    var run = function () { $$('[data-when]').forEach(function (el) { el.hidden = el.dataset.when.split('|').indexOf(target.value) < 0; }); };
    target.addEventListener('change', run); run();
  }

  // Drop-downs with a "Custom…" choice: show the text box only when Custom is picked
  $$('select[data-custom-select]').forEach(function (sel) {
    var box = $('input[data-custom-for="' + sel.dataset.customSelect + '"]');
    var sync = function () { box.hidden = sel.value !== '__custom'; box.required = !box.hidden; };
    sel.addEventListener('change', sync); sync();
  });

  // Record form: show the result-sheet instructions only for "Result", and point the template link at the chosen batch
  var rType = $('select[name="type"]'), rBatch = $('select[name="batch_id"]');
  if (rType) {
    var rt = $('#rt-link'), runR = function () {
      $$('[data-when-type]').forEach(function (el) { el.hidden = el.dataset.whenType !== rType.value; });
      if (rt && rBatch) rt.href = rt.dataset.base + rBatch.value;
    };
    rType.addEventListener('change', runR); if (rBatch) rBatch.addEventListener('change', runR); runR();
  }

  // Batch form: fill Timing from the chosen course's schedule, unless the admin has typed their own
  var bCourse = $('form select[name="course_id"]'), bTiming = $('form input[name="timing"]');
  if (bCourse && bTiming) {
    var auto = !bTiming.value;
    bTiming.addEventListener('input', function () { auto = false; });
    var fill = function () {
      var o = bCourse.options[bCourse.selectedIndex];
      if (auto && o && o.dataset.schedule !== undefined) bTiming.value = o.dataset.schedule;
    };
    bCourse.addEventListener('change', function () { auto = auto || !bTiming.value; fill(); });
    fill();
  }

  // "Download as CSV" for a table on the page (used for the imported-students login list; built in the browser, nothing is stored)
  $$('[data-download-table]').forEach(function (b) {
    b.addEventListener('click', function () {
      var cell = function (v) { v = String(v).trim(); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
      var rows = $$('tr', document.getElementById(b.dataset.downloadTable)).map(function (tr) { return $$('th,td', tr).map(function (c) { return cell(c.textContent); }).join(','); });
      var url = URL.createObjectURL(new Blob(['\uFEFF' + rows.join('\r\n')], { type: 'text/csv;charset=utf-8' }));
      var a = document.createElement('a'); a.href = url; a.download = b.dataset.filename || 'download.csv'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    });
  });

  // Print button
  $$('[data-print]').forEach(function (b) { b.addEventListener('click', function () { window.print(); }); });
})();
