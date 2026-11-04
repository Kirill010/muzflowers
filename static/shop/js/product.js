/* Страница букета: галерея, выбор размера (цена меняется сразу), количество. */
(function () {
  'use strict';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  var gallery = $('[data-gallery]');
  if (gallery) {
    var slides = $$('[data-slide]', gallery), thumbs = $$('[data-thumb]', gallery);
    var show = function (i) {
      slides.forEach(function (s, n) { s.classList.toggle('is-active', n === i); });
      thumbs.forEach(function (t, n) { t.classList.toggle('is-active', n === i); });
    };
    thumbs.forEach(function (t) { t.addEventListener('click', function () { show(+t.dataset.thumb); }); });
    if (slides.length > 1) {
      var start = 0;
      var main = $('.gallery__main', gallery);
      main.addEventListener('touchstart', function (e) { start = e.changedTouches[0].clientX; }, { passive: true });
      main.addEventListener('touchend', function (e) {
        var dx = e.changedTouches[0].clientX - start;
        if (Math.abs(dx) < 40) return;
        var cur = slides.findIndex(function (s) { return s.classList.contains('is-active'); });
        show((cur + (dx < 0 ? 1 : -1) + slides.length) % slides.length);
      });
    }
  }

  var price = $('[data-pdp-price]');
  $$('input[name="variant"]').forEach(function (r) {
    r.addEventListener('change', function () {
      if (price && r.checked) price.textContent = Number(r.dataset.price).toLocaleString('ru-RU') + ' ₽';
    });
  });

  var qty = $('.qty__input');
  if (qty) {
    var step = function (d) { qty.value = Math.min(50, Math.max(1, (parseInt(qty.value, 10) || 1) + d)); };
    var minus = $('[data-qty-minus]'), plus = $('[data-qty-plus]');
    if (minus) minus.addEventListener('click', function () { step(-1); });
    if (plus) plus.addEventListener('click', function () { step(1); });
    qty.addEventListener('change', function () { step(0); });
  }
})();
