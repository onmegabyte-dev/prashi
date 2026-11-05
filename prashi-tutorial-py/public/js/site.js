(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hover = matchMedia('(hover: hover) and (pointer: fine)').matches;

  // "Show password" tick-box on sign-in
  $$('[data-show]').forEach(function (c) { c.addEventListener('change', function () { $('#' + c.dataset.show).type = c.checked ? 'text' : 'password'; }); });

  // Menu, scroll state, theme
  var bg = $('#bg'), lk = $('#lk');
  bg.addEventListener('click', function () { bg.setAttribute('aria-expanded', lk.classList.toggle('open')); });
  addEventListener('keydown', function (e) { if (e.key === 'Escape') { lk.classList.remove('open'); bg.setAttribute('aria-expanded', 'false'); } });
  addEventListener('scroll', function () { $('#nav').classList.toggle('s', scrollY > 30); }, { passive: true });
  $('#theme').addEventListener('click', function () {
    var root = document.documentElement;
    var dark = root.getAttribute('data-theme') ? root.getAttribute('data-theme') === 'dark' : !matchMedia('(prefers-color-scheme: light)').matches;
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('pt-theme', next); } catch (e) {}
  });

  // Reveal on scroll, count-up numbers, progress bars
  function countUp(n) {
    var to = +n.dataset.n, start = performance.now();
    if (reduce) return;
    (function step(now) {
      var p = Math.min((now - start) / 1400, 1);
      n.textContent = Math.round(to * p).toLocaleString('en-IN');
      if (p < 1) requestAnimationFrame(step);
    })(start);
  }
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      var t = e.target;
      t.classList.add('in');
      $$('[data-n]', t).forEach(countUp);
      $$('[data-w]', t).forEach(function (b) { b.style.width = b.dataset.w + '%'; });
      if (t.matches('[data-w]')) t.style.width = t.dataset.w + '%';
      io.unobserve(t);
    });
  }, { threshold: 0.15 });
  $$('.rv, .bar i').forEach(function (e) { io.observe(e); });

  // 3D hero: paused while off-screen; pointer parallax and card tilt only on mouse devices
  var stage = $('#stage');
  if (stage) {
    new IntersectionObserver(function (es) { stage.classList.toggle('paused', !es[0].isIntersecting); }).observe(stage);
    if (hover && !reduce) addEventListener('pointermove', function (e) {
      stage.style.transform = 'rotateY(' + ((e.clientX / innerWidth - 0.5) * 12) + 'deg) rotateX(' + (-(e.clientY / innerHeight - 0.5) * 8) + 'deg)';
    }, { passive: true });
  }
  if (hover && !reduce) $$('.tilt').forEach(function (el) {
    el.addEventListener('pointermove', function (ev) {
      var r = el.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width - 0.5, y = (ev.clientY - r.top) / r.height - 0.5;
      el.style.transform = 'perspective(700px) rotateY(' + x * 8 + 'deg) rotateX(' + -y * 8 + 'deg) translateY(-4px)';
    });
    el.addEventListener('pointerleave', function () { el.style.transform = ''; });
  });

  // Testimonial carousel
  var trk = $('#trk');
  if (trk) {
    var n = trk.children.length, i = 0, timer;
    var go = function (d) { i = (i + d + n) % n; trk.style.transform = 'translateX(-' + i * 100 + '%)'; };
    $('#nx').onclick = function () { go(1); }; $('#pv').onclick = function () { go(-1); };
    if (!reduce && n > 1) { timer = setInterval(function () { go(1); }, 6000); $('#car').addEventListener('focusin', function () { clearInterval(timer); }); }
  }

  // FAQ accordion
  $$('.fq button').forEach(function (b) {
    b.addEventListener('click', function () {
      var f = b.parentNode, o = f.classList.toggle('o');
      b.setAttribute('aria-expanded', o);
      b.lastElementChild.textContent = o ? '−' : '+';
    });
  });

  // Course filters
  if ($('#filters')) {
    var run = function () {
      var q = $('#q').value.toLowerCase(), v = function (id) { return $('#' + id).value; }, shown = 0;
      $$('#cl > article').forEach(function (c) {
        var ok = (!q || c.dataset.q.indexOf(q) > -1) && (!v('fl') || c.dataset.lv === v('fl')) && (!v('fs') || c.dataset.sub.split(',').indexOf(v('fs')) > -1) &&
          (!v('fe') || c.dataset.ex === v('fe')) && (!v('ft') || c.dataset.ty === v('ft')) && (!v('fd') || c.dataset.du === v('fd'));
        c.hidden = !ok; shown += ok;
      });
      $('#none').hidden = !!shown;
    };
    $$('#filters input, #filters select').forEach(function (e) { e.addEventListener('input', run); });
  }
  if ($('#rfilters')) {
    var runR = function () {
      var q = $('#rq').value.toLowerCase(), k = $('#rc').value, shown = 0;
      $$('#rl > article').forEach(function (a) {
        var ok = (!k || a.dataset.cat === k) && (!q || a.dataset.q.indexOf(q) > -1);
        a.hidden = !ok; shown += ok;
      });
      $('#none').hidden = !!shown;
    };
    $$('#rfilters input, #rfilters select').forEach(function (e) { e.addEventListener('input', runR); });
  }

  // Forms: validated again on the server; this just shows clear success/error states.
  var token = ($('meta[name=csrf-token]') || {}).content;
  $$('form[data-f]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var ok = $('.ok', f), bad = $('.bad', f), btn = $('button.btn', f);
      ok.hidden = bad.hidden = true;
      $$('.err', f).forEach(function (x) { x.textContent = ''; });
      var body = {};
      $$('input, select, textarea', f).forEach(function (el) { if (el.name) body[el.name] = el.type === 'checkbox' ? el.checked : el.value; });
      btn.disabled = true;
      fetch(f.action, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-csrf-token': token }, body: JSON.stringify(body), credentials: 'same-origin' })
        .then(function (r) { return r.json().then(function (j) { return { s: r.status, j: j }; }); })
        .then(function (r) {
          if (r.j.ok) { ok.textContent = r.j.message; ok.hidden = false; f.reset(); ok.scrollIntoView({ block: 'nearest' }); return; }
          bad.textContent = r.j.message || 'Something went wrong. Please try again.'; bad.hidden = false;
          Object.keys(r.j.errors || {}).forEach(function (k) { var d = $('.err[data-for="' + k + '"]', f); if (d) d.textContent = r.j.errors[k]; });
          var first = $('.err:not(:empty)', f); if (first) { var inp = first.previousElementSibling; if (inp && inp.focus) inp.focus(); }
        })
        .catch(function () { bad.textContent = 'Could not reach the server. Check your internet and try again, or call us.'; bad.hidden = false; })
        .then(function () { btn.disabled = false; });
    });
  });
})();
