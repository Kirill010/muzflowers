/* Каталог: фильтры и поиск обновляют список на месте, без перезагрузки страницы. Без JavaScript работает обычной формой. */
(function () {
  'use strict';
  var form = document.querySelector('[data-filters]');
  var results = document.querySelector('[data-results]');
  if (!form || !results || !window.fetch || !window.URLSearchParams) return;

  var timer = 0, controller = null;

  function url() {
    var params = new URLSearchParams(new FormData(form));
    Array.from(params.keys()).forEach(function (k) { if (!params.get(k)) params.delete(k); });
    var qs = params.toString();
    return form.getAttribute('action') + (qs ? '?' + qs : '');
  }

  function load(target, push) {
    if (controller) controller.abort();
    controller = new AbortController();
    results.style.opacity = '.55';
    fetch(target, { headers: { 'X-Requested-With': 'fetch' }, signal: controller.signal, credentials: 'same-origin' })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        results.innerHTML = html;
        results.style.opacity = '';
        if (window.MZ) MZ.reveal(results);
        history[push ? 'pushState' : 'replaceState'](null, '', target);
      })
      .catch(function (err) { if (err.name !== 'AbortError') window.location.href = target; });
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); load(url(), true); });
  form.addEventListener('change', function () { clearTimeout(timer); load(url(), false); });
  form.addEventListener('input', function (e) {
    if (e.target.matches('[type="search"], [type="number"]')) {
      clearTimeout(timer);
      timer = setTimeout(function () { load(url(), false); }, 380);
    }
  });
  results.addEventListener('click', function (e) {
    var link = e.target.closest('.pager a');
    if (!link) return;
    e.preventDefault();
    load(link.href, true);
    window.scrollTo({ top: form.getBoundingClientRect().top + window.scrollY - 100, behavior: 'smooth' });
  });
  window.addEventListener('popstate', function () { window.location.reload(); });
})();
