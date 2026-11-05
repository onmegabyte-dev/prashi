// Rich-text editor (Quill). Turns every <div class="rt"> into an editor tied to the textarea next to it.
(function () {
  if (typeof Quill === 'undefined') return;
  var token = document.querySelector('meta[name=csrf-token]').content;

  function pickImage(quill) {
    var inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'image/jpeg,image/png,image/gif,image/webp';
    inp.onchange = function () {
      var f = inp.files[0]; if (!f) return;
      var fd = new FormData(); fd.append('image', f);
      fetch('/admin/upload-image?_csrf=' + encodeURIComponent(token), { method: 'POST', body: fd, credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j.ok) return alert(j.message || 'Could not upload that image.');
          var at = (quill.getSelection(true) || { index: quill.getLength() }).index;
          quill.insertEmbed(at, 'image', j.url, 'user');
        })
        .catch(function () { alert('Could not upload that image. Check your connection.'); });
    };
    inp.click();
  }

  document.querySelectorAll('.rt').forEach(function (box) {
    var ta = document.getElementById(box.dataset.for);
    var quill = new Quill(box, {
      theme: 'snow', placeholder: 'Type here…',
      modules: { toolbar: { container: [[{ header: [2, 3, false] }], ['bold', 'italic', 'underline'], [{ list: 'ordered' }, { list: 'bullet' }], ['link', 'image'], ['clean']], handlers: { image: function () { pickImage(quill); } } } },
    });
    if (ta.value) quill.setContents(quill.clipboard.convert({ html: ta.value }), 'silent');
    var form = ta.form;
    // getSemanticHTML() writes proper <ul>/<ol> lists (the raw editor HTML marks bullets with an attribute our safety filter removes).
    form.addEventListener('submit', function () { ta.value = (quill.getText().trim() === '' && !quill.root.querySelector('img')) ? '' : quill.getSemanticHTML(); });
  });
})();
