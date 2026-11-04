/* Запускается до отрисовки страницы: включает тему (светлая/тёмная) и помечает, что JavaScript работает. */
(function () {
  var root = document.documentElement;
  root.classList.add('js');
  try {
    var saved = localStorage.getItem('mz-theme');
    if (saved === 'dark' || saved === 'light') root.setAttribute('data-theme', saved);
  } catch (e) { /* хранилище недоступно — берём тему системы */ }
})();
