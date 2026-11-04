/* Яндекс Метрика. Подключается только если номер счётчика указан в настройках сайта. */
(function () {
  var meta = document.querySelector('meta[name="metrika-id"]');
  var id = meta ? parseInt(meta.content, 10) : 0;
  if (!id) return;
  (function (m, e, t, r, i, k, a) {
    m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
    m[i].l = 1 * new Date();
    k = e.createElement(t); a = e.getElementsByTagName(t)[0]; k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
  })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym');
  window.ym(id, 'init', { clickmap: true, trackLinks: true, accurateTrackBounce: true });
})();
