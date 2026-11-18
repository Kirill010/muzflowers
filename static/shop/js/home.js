/* Главная и страница «Музыкальная открытка»: «сейчас открыто» и короткая мелодия-пример. */
(function () {
  'use strict';

  var recordToggle = document.querySelector('[data-record-toggle]');
  if (recordToggle) {
    var motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    recordToggle.hidden = motion.matches;
    motion.addEventListener('change', function (event) { recordToggle.hidden = event.matches; });
    recordToggle.addEventListener('click', function () {
      var paused = recordToggle.getAttribute('aria-pressed') !== 'true';
      recordToggle.setAttribute('aria-pressed', String(paused));
      recordToggle.closest('.design-hero__record').classList.toggle('is-paused', paused);
    });
  }

  /* ───── открыто / закрыто (время по Москве) ───── */
  var status = document.querySelector('[data-open-now]');
  if (status) {
    var toMin = function (s) { var p = s.split(':'); return (+p[0]) * 60 + (+p[1]); };
    var clock = function (s) { return String(parseInt(s.split(':')[0], 10)) + ':' + s.split(':')[1]; };
    var parts = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
    var now = 0;
    parts.forEach(function (p) { if (p.type === 'hour') now += (+p.value % 24) * 60; if (p.type === 'minute') now += +p.value; });
    var open = toMin(status.dataset.open), close = toMin(status.dataset.close), text;
    if (now >= open && now < close) text = (close - now <= 60 ? 'Скоро закроемся — до ' : 'Открыто до ') + clock(status.dataset.close);
    else if (now < open) text = 'Откроемся сегодня в ' + clock(status.dataset.open);
    else text = 'Откроемся завтра в ' + clock(status.dataset.open);
    var label = status.querySelector('[data-open-now-text]');
    if (label) label.textContent = text;
    status.classList.toggle('is-closed', !(now >= open && now < close));
  }

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
