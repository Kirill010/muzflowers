/* Мелодия-пример на странице музыкальной открытки. */
(function () {
  'use strict';

  /* ───── мелодия-пример: играет прямо в браузере, без файлов ───── */
  var section = document.querySelector('[data-music]');
  var button = section && section.querySelector('[data-music-play]');
  if (!button) return;
  var ctx = null, timer = 0;
  var NOTES = [523.25, 659.25, 783.99, 880.0, 783.99, 659.25, 587.33, 698.46, 880.0, 1046.5, 880.0, 783.99, 659.25, 523.25];
  button.addEventListener('click', function () {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (section.classList.contains('is-playing')) return;
    ctx = ctx || new AC();
    if (ctx.state === 'suspended') ctx.resume();
    var start = ctx.currentTime + 0.05, step = 0.3;
    NOTES.forEach(function (freq, i) {
      var osc = ctx.createOscillator(), gain = ctx.createGain(), t = start + i * step;
      osc.type = 'triangle'; osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.13, t + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + step * 1.8);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(t); osc.stop(t + step * 1.9);
    });
    section.classList.add('is-playing');
    button.setAttribute('aria-pressed', 'true');
    clearTimeout(timer);
    timer = setTimeout(function () {
      section.classList.remove('is-playing');
      button.setAttribute('aria-pressed', 'false');
    }, NOTES.length * step * 1000 + 700);
  });
})();
