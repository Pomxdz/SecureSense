(() => {
  const target = document.getElementById('typingText');
  if (!target) return;
  const phrase = 'Build the confidence to spot phishing.';
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let timer;
  function typePhrase() {
    clearTimeout(timer);
    if (motion.matches) { target.textContent = phrase; return; }
    target.textContent = '';
    let index = 0;
    function nextCharacter() {
      target.textContent = phrase.slice(0, ++index);
      timer = setTimeout(index < phrase.length ? nextCharacter : typePhrase,
        index < phrase.length ? 65 : 5000);
    }
    nextCharacter();
  }
  motion.addEventListener('change', typePhrase);
  typePhrase();
})();
