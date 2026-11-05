// Runs before the page paints: marks JS as available and applies the saved theme (no flash).
document.documentElement.classList.add('js');
try { var t = localStorage.getItem('pt-theme'); if (t) document.documentElement.setAttribute('data-theme', t); } catch (e) {}

// Skeleton loader: when a click or form submit starts a page change that takes a moment, swap the page body for grey shimmering placeholders.
// (The pages are rendered on the server, so this is shown between "click" and "next page arrives". Nothing appears if the next page is quick.)
(function () {
  var timer, SKIP = /(^#|^javascript:|^mailto:|^tel:|\.(csv|xlsx?|zip|pdf|docx?|pptx?|png|jpe?g|gif|webp)(\?|$)|\/files?\/|\/file$|\/photo|data-export|template|\/receipts?\/|\/logout)/i;
  function bars(n, cls) { var h = ''; for (var i = 0; i < n; i++) h += '<i class="sk ' + cls + '"></i>'; return h; }
  function layout() {
    var c = document.body.className;
    if (/\badm\b/.test(c)) return '<i class="sk sk-h"></i><i class="sk sk-bar"></i><div class="sk-rows">' + bars(7, 'sk-row') + '</div>';
    if (/\bpt\b/.test(c)) return '<i class="sk sk-h"></i><div class="sk-tiles">' + bars(4, 'sk-tile') + '</div><div class="sk-rows">' + bars(4, 'sk-row') + '</div>';
    return '<div class="w"><i class="sk sk-hero"></i><i class="sk sk-h"></i><i class="sk sk-line"></i><i class="sk sk-line short"></i><div class="sk-cards">' + bars(3, 'sk-card') + '</div></div>';
  }
  function show() {
    var m = document.querySelector('main');
    if (!m || m.classList.contains('sk-busy')) return;
    var d = document.createElement('div');
    d.className = 'sk-page'; d.setAttribute('aria-hidden', 'true'); d.innerHTML = layout();
    m.appendChild(d); m.classList.add('sk-busy'); m.setAttribute('aria-busy', 'true');
    setTimeout(hide, 12000);                       // safety net, e.g. a link that turned out to be a download
  }
  function hide() {
    clearTimeout(timer);
    var m = document.querySelector('main.sk-busy');
    if (!m) return;
    var d = m.querySelector('.sk-page'); if (d) d.remove();
    m.classList.remove('sk-busy'); m.removeAttribute('aria-busy');
  }
  function later(e) {                              // wait a tick so other handlers (e.g. "Are you sure?") can cancel first
    setTimeout(function () { if (!e.defaultPrevented) { clearTimeout(timer); timer = setTimeout(show, 150); } }, 0);
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || a.target === '_blank' || a.hasAttribute('download') || a.hasAttribute('data-noskel')) return;
    var u = a.getAttribute('href');
    if (SKIP.test(u) || (a.origin && a.origin !== location.origin)) return;
    if (a.pathname === location.pathname && a.search === location.search) return;
    later(e);
  });
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (f.target === '_blank' || f.hasAttribute('data-noskel') || SKIP.test(f.getAttribute('action') || '')) return;
    later(e);
  });
  addEventListener('pageshow', hide);              // coming back with the Back button
})();
