/* Аналитика загружается только после отдельного разрешения. Выбор хранится локально, без серверного идентификатора. */
(function () {
  'use strict';
  var KEY = 'mz-cookie-choice-v1';
  var banner = document.querySelector('[data-cookie-consent]');
  if (!banner) return;
  var loaded = false;

  function read() {
    try {
      var value = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (!value || ['accepted', 'necessary'].indexOf(value.choice) < 0) return null;
      if (!Date.parse(value.at) || Date.now() - Date.parse(value.at) > 365 * 86400000) return null;
      return value;
    } catch (e) { return null; }
  }

  function removeAnalyticsCookies() {
    document.cookie.split(';').forEach(function (part) {
      var name = part.split('=')[0].trim();
      if (name.indexOf('_ym_') !== 0) return;
      document.cookie = name + '=; Max-Age=0; path=/; SameSite=Lax';
      document.cookie = name + '=; Max-Age=0; path=/; domain=' + location.hostname + '; SameSite=Lax';
      document.cookie = name + '=; Max-Age=0; path=/; domain=.' + location.hostname + '; SameSite=Lax';
    });
  }

  function loadMetrika() {
    if (loaded) return;
    loaded = true;
    var script = document.createElement('script');
    script.src = '/static/shop/js/metrika.js';
    script.async = true;
    script.dataset.metrikaLoader = '1';
    document.head.appendChild(script);
  }

  function choose(choice) {
    var wasAccepted = (read() || {}).choice === 'accepted';
    try { localStorage.setItem(KEY, JSON.stringify({ choice: choice, at: new Date().toISOString() })); } catch (e) { /* выбор работает до следующего перехода */ }
    banner.hidden = true;
    if (choice === 'accepted') loadMetrika();
    else {
      removeAnalyticsCookies();
      if (wasAccepted) window.location.reload();
    }
  }

  var current = read();
  if (current && current.choice === 'accepted') loadMetrika();
  else if (!current) banner.hidden = false;

  document.querySelectorAll('[data-cookie-choice]').forEach(function (button) {
    button.addEventListener('click', function () { choose(button.dataset.cookieChoice); });
  });
  document.querySelectorAll('[data-cookie-settings]').forEach(function (link) {
    link.addEventListener('click', function (event) {
      event.preventDefault();
      banner.hidden = false;
      var first = banner.querySelector('button');
      if (first) first.focus();
    });
  });
})();
