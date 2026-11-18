(function () {
  'use strict';
  const form = document.querySelector('[data-filters]');
  const results = document.querySelector('[data-results]');
  const cards = Array.from(results.querySelectorAll('[data-static-item]'));
  const count = results.querySelector('[data-results-count]');
  const empty = results.querySelector('[data-catalog-empty]');
  const budgets = JSON.parse(document.querySelector('#catalog-budget-ranges').textContent);
  const plural = new Intl.PluralRules('ru');
  if (matchMedia('(max-width:560px)').matches) document.querySelector('[data-filter-panel]').open = false;

  function restore() {
    const params = new URLSearchParams(location.search);
    for (const input of form.elements) {
      if (!input.name) continue;
      if (input.type === 'checkbox') input.checked = params.get(input.name) === input.value;
      else input.value = params.get(input.name) || (input.name === 'sort' ? 'pop' : '');
    }
    const budget = budgets[params.get('budget')];
    if (Array.isArray(budget)) [form.elements.min.value, form.elements.max.value] = budget;
    filter();
  }

  function filter() {
    const { q, min, max, occasion, sort, ready, sale } = form.elements;
    const needle = q.value.trim().toLocaleLowerCase('ru');
    const visible = cards.filter(({ dataset }) => {
      const price = Number(dataset.price);
      return (!needle || dataset.name.toLocaleLowerCase('ru').includes(needle)) &&
        (!occasion.value || dataset.occasion === occasion.value) &&
        (!min.value || price >= Number(min.value)) && (!max.value || price <= Number(max.value)) &&
        (!ready.checked || dataset.ready) && (!sale.checked || dataset.sale);
    });
    const orders = {
      price_asc: (a, b) => a.dataset.price - b.dataset.price,
      price_desc: (a, b) => b.dataset.price - a.dataset.price,
      new: (a, b) => b.dataset.new - a.dataset.new,
    };
    if (orders[sort.value]) visible.sort(orders[sort.value]);
    for (const card of cards) card.hidden = true;
    for (const card of visible) {
      card.hidden = false;
      card.parentNode.append(card);
    }
    empty.hidden = visible.length > 0;
    const label = { one: 'букет', few: 'букета', many: 'букетов' };
    count.textContent = visible.length + ' ' + label[plural.select(visible.length)];
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    filter();
    const params = new URLSearchParams([...new FormData(form)].filter(([, value]) => value));
    history.replaceState(null, '', location.pathname + (params.size ? '?' + params : '') + location.hash);
  });
  form.addEventListener('input', filter);
  window.addEventListener('popstate', restore);
  restore();
})();
