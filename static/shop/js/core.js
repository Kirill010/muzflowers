/* MuzFlowers — общий код: тема, меню, поиск, корзина, всплывающие сообщения. Без библиотек. */
(function () {
  'use strict';

  var $ = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };
  var MZ = window.MZ = { $: $, $$: $$ };

  MZ.csrf = function () { var m = $('meta[name="csrf-token"]'); return m ? m.content : ''; };
  MZ.rub = function (n) { return Number(n).toLocaleString('ru-RU') + ' ₽'; };
  MZ.el = function (tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };
  MZ.goal = function (name) {  // цель для Яндекс Метрики (если она подключена)
    var m = $('meta[name="metrika-id"]');
    if (m && window.ym) { try { window.ym(+m.content, 'reachGoal', name); } catch (e) { /* не страшно */ } }
  };

  /* ───── запросы ───── */
  MZ.post = function (url, formData) {
    return fetch(url, {
      method: 'POST', body: formData, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': MZ.csrf() }
    }).then(function (r) { return r.json().then(function (data) { data.status = r.status; return data; }); });
  };

  /* ───── всплывающие сообщения ───── */
  MZ.toast = function (text, opts) {
    opts = opts || {};
    var box = $('#toasts');
    if (!box) return;
    var t = MZ.el('div', 'toast' + (opts.error ? ' toast--error' : ''));
    t.appendChild(MZ.el('span', '', text));
    if (opts.action) {
      var b = MZ.el('button', 'link-btn', opts.action.label);
      b.type = 'button';
      b.style.color = 'inherit';
      b.addEventListener('click', function () { opts.action.run(); t.remove(); });
      t.appendChild(b);
    }
    box.appendChild(t);
    while (box.children.length > 3) box.removeChild(box.firstChild);
    setTimeout(function () {
      t.classList.add('is-leaving');
      setTimeout(function () { t.remove(); }, 350);
    }, opts.error ? 5200 : 3400);
  };

  /* ───── окна (меню, поиск, корзина): фокус не уходит за пределы окна, Esc закрывает ───── */
  function modal(el, opts) {
    opts = opts || {};
    var opened = false, previous = null;
    function focusable() {
      return $$('a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])', el)
        .filter(function (n) { return n.offsetParent !== null; });
    }
    function onKey(e) {
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      var f = focusable();
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
    function open() {
      if (opened) return;
      opened = true; previous = document.activeElement;
      el.hidden = false;
      document.body.classList.add('is-locked');
      requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add('is-open'); }); });
      document.addEventListener('keydown', onKey);
      setTimeout(function () { var t = opts.focus ? $(opts.focus, el) : focusable()[0]; if (t) t.focus(); }, 80);
      if (opts.onOpen) opts.onOpen();
    }
    function close() {
      if (!opened) return;
      opened = false;
      el.classList.remove('is-open');
      document.removeEventListener('keydown', onKey);
      setTimeout(function () { if (!opened) { el.hidden = true; document.body.classList.remove('is-locked'); } }, opts.animated ? 420 : 0);
      if (previous && previous.focus) previous.focus();
      if (opts.onClose) opts.onClose();
    }
    return { open: open, close: close, isOpen: function () { return opened; } };
  }

  /* ───── тема ───── */
  $$('[data-theme-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var root = document.documentElement;
      var current = root.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      var next = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('mz-theme', next); } catch (e) { /* ничего */ }
    });
  });

  /* ───── шапка ───── */
  var header = $('[data-header]');
  if (header) {
    var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
    onScroll();
    addEventListener('scroll', onScroll, { passive: true });
  }

  /* ───── мобильное меню ───── */
  var navEl = $('[data-mobile-nav]');
  if (navEl) {
    var nav = modal(navEl, {
      onOpen: function () { $$('[data-menu-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'true'); }); },
      onClose: function () { $$('[data-menu-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); }); }
    });
    $$('[data-menu-open]').forEach(function (b) { b.addEventListener('click', nav.open); });
    $$('[data-menu-close]').forEach(function (b) { b.addEventListener('click', nav.close); });
  }

  /* ───── поиск с подсказками ───── */
  var searchEl = $('[data-search]');
  if (searchEl) {
    var search = modal(searchEl, { focus: '[data-search-input]' });
    var input = $('[data-search-input]', searchEl), list = $('[data-search-results]', searchEl), timer = 0, seq = 0;
    $$('[data-search-open]').forEach(function (b) { b.addEventListener('click', search.open); });
    $$('[data-search-close]').forEach(function (b) { b.addEventListener('click', search.close); });
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || '') && !e.ctrlKey && !e.metaKey) {
        e.preventDefault(); search.open();
      }
    });
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { list.innerHTML = ''; return; }
      var mine = ++seq;
      timer = setTimeout(function () {
        fetch(searchEl.dataset.url + '?q=' + encodeURIComponent(q), { credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (mine !== seq) return;
            list.innerHTML = '';
            data.items.forEach(function (it) {
              var li = MZ.el('li'), a = MZ.el('a'), img = new Image(), text = MZ.el('span');
              a.href = it.url; img.src = it.image; img.alt = ''; img.width = 52; img.height = 64;
              text.appendChild(MZ.el('b', '', it.name));
              if (it.tagline) text.appendChild(MZ.el('small', '', it.tagline));
              a.appendChild(img); a.appendChild(text); a.appendChild(MZ.el('span', 'search__price', MZ.rub(it.price)));
              li.appendChild(a); list.appendChild(li);
            });
            if (!data.items.length) list.appendChild(MZ.el('li', 'search__hint', 'Ничего не нашли — попробуйте другое слово.'));
          })
          .catch(function () { /* без подсказок тоже можно: Enter откроет каталог */ });
      }, 180);
    });
  }

  /* ───── корзина ───── */
  var drawerEl = $('[data-drawer]');
  var drawer = drawerEl ? modal(drawerEl, { animated: true, focus: '[data-cart-close].icon-btn' }) : null;

  function applyCart(data) {
    if (data.html != null) {
      var active = document.activeElement, memo = null;
      if (active && active.closest && active.closest('[data-cart-body]')) {
        var f = active.closest('form');
        var key = f && (f.querySelector('[name="key"]') || f.querySelector('[name="addon"]'));
        memo = { label: active.getAttribute('aria-label'), name: active.getAttribute('name'), key: key && key.value };
      }
      $$('[data-cart-body]').forEach(function (el) { el.innerHTML = data.html; });
      if (memo && memo.key) {  // возвращаем фокус на то же место, чтобы работа с клавиатуры не прерывалась
        var again = $$('[data-cart-body] form').filter(function (f2) {
          var k = f2.querySelector('[name="key"]') || f2.querySelector('[name="addon"]');
          return k && k.value === memo.key;
        });
        for (var i = 0; i < again.length; i++) {
          var cand = memo.label ? $('[aria-label="' + memo.label + '"]', again[i]) : $('button, input', again[i]);
          if (cand) { cand.focus(); break; }
        }
      }
    }
    if (typeof data.count === 'number') {
      $$('[data-cart-count]').forEach(function (el) {
        el.textContent = data.count; el.setAttribute('data-count', data.count);
        el.classList.remove('is-bump'); void el.offsetWidth; el.classList.add('is-bump');
      });
    }
  }
  MZ.applyCart = applyCart;

  function openCart() {
    if (!drawer) return false;
    drawer.open();
    fetch(drawerEl.dataset.fragmentUrl, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json(); }).then(function (d) { applyCart({ html: d.html }); }).catch(function () { /* оставляем то, что есть */ });
    return true;
  }
  $$('[data-cart-open]').forEach(function (a) {
    a.addEventListener('click', function (e) { if (drawer) { e.preventDefault(); openCart(); } });
  });
  $$('[data-cart-close]').forEach(function (b) { b.addEventListener('click', function () { if (drawer) drawer.close(); }); });

  // любая форма корзины отправляется «молча» и обновляет корзину на месте; без JavaScript — обычный переход
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.matches || !form.matches('[data-cart-form]')) return;
    e.preventDefault();
    if (form.classList.contains('is-busy')) return;
    form.classList.add('is-busy');
    MZ.post(form.action, new FormData(form)).then(function (data) {
      applyCart(data);
      if (data.message) {
        var opts = { error: !data.ok };
        if (data.ok && form.hasAttribute('data-add') && drawer && !form.hasAttribute('data-pdp')) opts.action = { label: 'Открыть', run: openCart };
        MZ.toast(data.message, opts);
      }
      if (data.ok && form.hasAttribute('data-add')) {
        MZ.goal('add_to_cart');
        if (form.hasAttribute('data-pdp')) openCart();
      }
    }).catch(function () {
      MZ.toast('Нет связи. Попробуйте ещё раз.', { error: true });
    }).then(function () { form.classList.remove('is-busy'); });
  });
  document.addEventListener('change', function (e) {
    var form = e.target.closest && e.target.closest('[data-autosubmit]');
    if (form && form.requestSubmit) form.requestSubmit();
  });

  /* ───── избранное ───── */
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.matches || !form.matches('[data-wishlist-form]')) return;
    e.preventDefault();
    if (form.classList.contains('is-busy')) return;
    form.classList.add('is-busy');
    MZ.post(form.action, new FormData(form)).then(function (data) {
      if (!data || typeof data.count !== 'number') throw new Error('bad response');
      $$('[data-wishlist-count]').forEach(function (el) {
        el.textContent = data.count; el.setAttribute('data-count', data.count);
      });
      $$('[data-wishlist-product="' + data.product + '"]').forEach(function (button) {
        button.setAttribute('aria-pressed', data.active ? 'true' : 'false');
        button.setAttribute('aria-label', button.getAttribute('aria-label').replace(/^[^:]+/, data.active ? 'Убрать из избранного' : 'Добавить в избранное'));
      });
      if (data.ok && !data.active && $('[data-wishlist-page]')) {
        var card = form.closest('.card');
        if (card) card.remove();
        if ($('[data-wishlist-grid]') && !$('[data-wishlist-grid] .card')) window.location.reload();
      }
      if (data.message) MZ.toast(data.message, { error: !data.ok });
      if (data.ok) MZ.goal(data.active ? 'wishlist_add' : 'wishlist_remove');
    }).catch(function () {
      MZ.toast('Не удалось изменить избранное. Попробуйте ещё раз.', { error: true });
    }).then(function () { form.classList.remove('is-busy'); });
  });

  /* ───── появление блоков при прокрутке ───── */
  MZ.reveal = function (root) {
    var items = $$('[data-reveal]:not(.is-visible)', root);
    if (!('IntersectionObserver' in window)) { items.forEach(function (n) { n.classList.add('is-visible'); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('is-visible'); io.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    items.forEach(function (n, i) { n.style.transitionDelay = (i % 4) * 70 + 'ms'; io.observe(n); });
  };
  MZ.reveal(document);
})();
