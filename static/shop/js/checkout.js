/* Оформление заказа: способ получения, дата и время, оплата и итог обновляются сразу, как клиент что-то выбрал.
   Все цифры считает сервер (/checkout/state/) — здесь только показываем. */
(function () {
  'use strict';
  var form = document.querySelector('[data-checkout]');
  if (!form) return;
  var $ = function (s, c) { return (c || form).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || form).querySelectorAll(s)); };

  var stateUrl = form.dataset.stateUrl, blocked = {};
  try { blocked = JSON.parse(form.dataset.blocked || '{}'); } catch (e) { blocked = {}; }
  var dateInput = $('[data-date]'), slotSelect = $('[data-slot]'), problemBox = $('[data-day-problem]'),
    prepayNote = $('[data-prepay-note]'), summary = $('[data-summary]'), totalBtn = $('[data-total-btn]'),
    submit = $('[data-submit]'), seq = 0, sent = false;

  var method = function () { var r = $('input[name="receive_method"]:checked'); return r ? r.value : 'pickup'; };
  var addonIds = function () { return $$('input[data-addon-id]:checked').map(function (i) { return i.dataset.addonId; }).join(','); };

  function syncMethod() {
    var m = method();
    $$('[data-when]').forEach(function (b) { b.hidden = b.dataset.when !== m; });
  }

  function renderSlots(slots) {
    var current = slotSelect.value;
    slotSelect.innerHTML = '';
    if (!slots.length) {
      var none = new Option('Нет свободного времени', ''); none.disabled = true; slotSelect.add(none); slotSelect.value = '';
      return;
    }
    slots.forEach(function (s) { slotSelect.add(new Option(s.label, s.value)); });
    slotSelect.value = slots.some(function (s) { return s.value === current; }) ? current : slots[0].value;
  }

  function renderPayments(list) {
    var wrap = $('[data-payments]');
    var chosen = wrap.querySelector('input:checked');
    var selected = chosen ? chosen.value : '';
    var pick = list.some(function (o) { return o.value === selected; }) ? selected : (list.filter(function (o) { return o['default']; })[0] || list[0]).value;
    wrap.innerHTML = '';
    list.forEach(function (o) {
      var label = MZ.el('label', 'choice'), input = MZ.el('input'), span = MZ.el('span');
      input.type = 'radio'; input.name = 'payment_method'; input.value = o.value; input.checked = o.value === pick;
      span.appendChild(MZ.el('b', '', o.label));
      if (o.hint) span.appendChild(MZ.el('small', '', o.hint));
      label.appendChild(input); label.appendChild(span); wrap.appendChild(label);
    });
  }

  function apply(state) {
    var message = state.problem || blocked[dateInput.value] || '';
    problemBox.hidden = !message;
    if (message) problemBox.querySelector('span').textContent = message;
    renderSlots(state.slots);
    prepayNote.hidden = !state.prepay;
    renderPayments(state.payments);
    summary.innerHTML = state.summary;
    totalBtn.textContent = MZ.rub(state.total);
  }

  function refresh() {
    var mine = ++seq;
    var params = new URLSearchParams({ method: method(), date: dateInput.value, addons: addonIds() });
    fetch(stateUrl + '?' + params.toString(), { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json(); })
      .then(function (state) { if (mine === seq) apply(state); })
      .catch(function () { /* оставляем как есть: сервер проверит всё при отправке */ });
  }

  /* способ получения */
  $$('input[name="receive_method"]').forEach(function (r) {
    r.addEventListener('change', function () { syncMethod(); refresh(); });
  });
  dateInput.addEventListener('change', refresh);

  /* «Получатель — другой человек» и другие переключатели */
  $$('[data-toggle]').forEach(function (box) {
    var target = $('[data-target="' + box.dataset.toggle + '"]');
    var apply2 = function () { if (target) target.hidden = !box.checked; };
    box.addEventListener('change', apply2); apply2();
  });

  /* дополнения: музыкальная открытка и т. п. */
  $$('input[data-addon-id]').forEach(function (box) {
    box.addEventListener('change', function () {
      var wrap = box.closest('[data-addon]'), note = wrap && $('[data-addon-note]', wrap);
      if (wrap) wrap.classList.toggle('is-on', box.checked);
      if (note) {
        note.hidden = !box.checked;
        var field = $('input', note);
        if (box.checked && field) field.focus();
      }
      refresh();
    });
  });

  /* телефон: +7 (900) 000-00-00 */
  function maskPhone(input) {
    var d = input.value.replace(/\D/g, '');
    if (!d) { input.value = ''; return; }
    if (d[0] === '8') d = '7' + d.slice(1);
    if (d[0] === '9') d = '7' + d;
    if (d[0] !== '7') return;  // не российский номер — не трогаем
    d = d.slice(0, 11);
    var out = '+7';
    if (d.length > 1) out += ' (' + d.slice(1, 4);
    if (d.length >= 4) out += ')';
    if (d.length > 4) out += ' ' + d.slice(4, 7);
    if (d.length > 7) out += '-' + d.slice(7, 9);
    if (d.length > 9) out += '-' + d.slice(9, 11);
    input.value = out;
  }
  $$('input[type="tel"], input[inputmode="tel"]').forEach(function (i) {
    i.addEventListener('input', function (e) { if (!(e.inputType && e.inputType.indexOf('delete') === 0)) maskPhone(i); });
    i.addEventListener('blur', function () { maskPhone(i); });
  });

  /* защита от двойного нажатия */
  form.addEventListener('submit', function () {
    if (sent) return;
    sent = true;
    MZ.goal('checkout_submit');
    if (submit) { submit.classList.add('is-disabled'); submit.setAttribute('aria-busy', 'true'); }
  });
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) { sent = false; if (submit) { submit.classList.remove('is-disabled'); submit.removeAttribute('aria-busy'); } syncMethod(); }
  });

  /* если сервер вернул ошибки — сразу показываем, где они */
  var summaryError = $('[data-error-summary]');
  var firstError = $('.has-error input, .has-error select, .has-error textarea');
  if (summaryError) summaryError.focus();
  if (firstError) { firstError.scrollIntoView({ block: 'center' }); firstError.focus({ preventScroll: true }); }

  syncMethod();
})();
