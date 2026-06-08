function copyBibtex() {
  var text = document.getElementById('bibtex-block').innerText;
  var label = document.getElementById('copy-label');
  var done = function () {
    label.textContent = 'Copied!';
    setTimeout(function () { label.textContent = 'Copy'; }, 1800);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(fallbackCopy.bind(null, text, done));
  } else {
    fallbackCopy(text, done);
  }
}

function fallbackCopy(text, done) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); done(); } catch (e) { /* no-op */ }
  document.body.removeChild(ta);
}
