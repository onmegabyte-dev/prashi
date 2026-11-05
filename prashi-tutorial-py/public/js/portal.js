// Opens and closes the side menu on phones.
(function () {
  var btn = document.getElementById('pmenu'), side = document.getElementById('pside');
  if (!btn || !side) return;
  btn.addEventListener('click', function () { btn.setAttribute('aria-expanded', side.classList.toggle('open')); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { side.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); } });
  // Buttons/forms with data-confirm ask first.
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  }, true);
})();
