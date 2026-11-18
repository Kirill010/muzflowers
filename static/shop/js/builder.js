(function () {
  'use strict';

  const configNode = document.querySelector('#bouquet-config');
  if (!configNode) return;

  const { flowers, maxStems, bounds } = JSON.parse(configNode.textContent);
  const [minX, maxX, minY, maxY] = bounds;
  const editor = document.querySelector('[data-bouquet-editor]');
  const preview = document.querySelector('[data-bouquet-preview]');
  const root = editor || preview;
  const svg = root.querySelector('[data-bouquet-stage]');
  const stems = svg.querySelector('[data-bouquet-stems]');
  const heads = svg.querySelector('[data-bouquet-heads]');
  const vesselLayers = svg.querySelectorAll('[data-vessel]');
  const basketHandle = svg.querySelector('[data-basket-handle]');
  const field = editor && editor.querySelector('[data-bouquet-value]');

  function readLayout(raw) {
    let value;
    try { value = JSON.parse(raw); } catch { value = null; }
    const vessel = value?.vessel === 'basket' ? 'basket' : 'vase';
    const stems = Array.isArray(value?.stems) ? value.stems.slice(0, maxStems).filter(stem =>
      stem && typeof stem.kind === 'string' && Object.hasOwn(flowers, stem.kind) &&
      Number.isInteger(stem.x) && Number.isInteger(stem.y) &&
      stem.x >= minX && stem.x <= maxX && stem.y >= minY && stem.y <= maxY
    ) : [];
    return { vessel, stems };
  }

  const layout = readLayout(field ? field.value : root.querySelector('#bouquet-layout').textContent);

  function svgElement(tag, attributes) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
    return node;
  }

  function drawVessel() {
    vesselLayers.forEach(layer => layer.toggleAttribute('hidden', layer.dataset.vessel !== layout.vessel));
    basketHandle.toggleAttribute('hidden', layout.vessel !== 'basket');
  }

  function updateStem(index) {
    const { x, y } = layout.stems[index];
    const basket = layout.vessel === 'basket';
    const baseX = Math.round(320 + (x - 320) * (basket ? .32 : .12));
    const baseY = basket ? 317 : 296;
    const bendX = Math.round((x + baseX) / 2 + (baseX - x) * .15);
    const bendY = Math.round((y + baseY) / 2);
    stems.children[index].setAttribute('d', 'M' + baseX + ' ' + baseY + ' Q' + bendX + ' ' + bendY + ' ' + x + ' ' + y);
    heads.children[index].setAttribute('transform', 'translate(' + x + ' ' + y + ')');
  }

  function drawStems() {
    stems.replaceChildren();
    heads.replaceChildren();
    layout.stems.forEach(({ kind }, index) => {
      const flower = flowers[kind];
      stems.append(svgElement('path', { class: 'bouquet-stem' }));
      const head = svgElement('g', { class: 'bouquet-head' });
      if (editor) {
        head.setAttribute('data-stem-index', index);
        head.setAttribute('tabindex', '0');
        head.setAttribute('role', 'button');
        head.setAttribute('aria-label', flower.name + ', цветок ' + (index + 1));
        head.append(svgElement('circle', { r: 41, class: 'bouquet-head__outline' }));
      }
      head.append(svgElement('image', { x: -38, y: -38, width: 76, height: 76, href: flower.url }));
      heads.append(head);
      updateStem(index);
    });
  }

  drawVessel();
  drawStems();
  if (!editor) return;

  const workbench = editor.querySelector('[data-bouquet-workbench]');
  const paletteButtons = workbench.querySelectorAll('[data-add-stem]');
  const vessels = editor.querySelectorAll('[data-vessel-choice]');
  const count = editor.querySelector('[data-bouquet-count]');
  const announce = editor.querySelector('[data-bouquet-announcement]');
  const remove = editor.querySelector('[data-remove-stem]');
  const clear = editor.querySelector('[data-clear-stems]');
  const heading = editor.querySelector('.bouquet-vessels');
  let selected = -1;
  let move = null;
  let paletteDrag = null;
  let suppressClick = false;

  function sync() {
    field.value = JSON.stringify(layout);
    const total = layout.stems.length;
    count.textContent = total + ' / ' + maxStems + ' шт.';
    paletteButtons.forEach(button => button.setAttribute('aria-disabled', String(total >= maxStems)));
    vessels.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.vesselChoice === layout.vessel)));
    remove.disabled = selected < 0;
    clear.disabled = !total;
    Array.from(heads.children).forEach((head, index) => head.setAttribute('aria-pressed', String(index === selected)));
  }

  function select(index) {
    selected = index;
    sync();
  }

  function point(event) {
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
  }

  function position(x, y) {
    return {
      x: Math.max(minX, Math.min(maxX, Math.round(x))),
      y: Math.max(minY, Math.min(maxY, Math.round(y))),
    };
  }

  function relocate(index, x, y) {
    Object.assign(layout.stems[index], position(x, y));
    updateStem(index);
  }

  function add(kind, drop) {
    if (layout.stems.length >= maxStems) {
      announce.textContent = 'Достигнут предел цветов в композиции.';
      return;
    }
    // Find the nearest unoccupied spot when a flower is added using a button.
    if (!drop) {
      const spots = [320, 238, 402, 156, 484, 74, 566].flatMap((x) =>
        [136, 208, 64, 276].map(y => ({ x, y })));
      drop = spots.find(({ x, y }) => layout.stems.every(stem => Math.hypot(stem.x - x, stem.y - y) >= 62))
        || spots[layout.stems.length];
    }
    layout.stems.push({ kind, ...position(drop.x, drop.y) });
    drawStems();
    select(layout.stems.length - 1);
    announce.textContent = flowers[kind].name + ' — добавлен цветок ' + layout.stems.length + '.';
  }

  function removeSelected() {
    if (selected < 0) return;
    const [removed] = layout.stems.splice(selected, 1);
    const next = Math.min(selected, layout.stems.length - 1);
    drawStems();
    select(next);
    (heads.children[next] || paletteButtons[0]).focus({ preventScroll: true });
    announce.textContent = 'Удалено: ' + flowers[removed.kind].name + '.';
  }

  heading.addEventListener('click', event => {
    const choice = event.target.closest('[data-vessel-choice]');
    if (!choice) return;
    layout.vessel = choice.dataset.vesselChoice;
    drawVessel();
    layout.stems.forEach((_, index) => updateStem(index));
    sync();
  });

  remove.addEventListener('click', removeSelected);
  clear.addEventListener('click', () => {
    layout.stems = [];
    drawStems();
    select(-1);
    paletteButtons[0].focus({ preventScroll: true });
    announce.textContent = 'Композиция очищена.';
  });

  workbench.addEventListener('click', event => {
    const button = event.target.closest('[data-add-stem]');
    if (button && (!suppressClick || event.detail === 0)) add(button.dataset.addStem);
    suppressClick = false;
  });

  workbench.addEventListener('pointerdown', event => {
    const button = event.target.closest('[data-add-stem]');
    if (!button || !event.isPrimary || event.button !== 0 || layout.stems.length >= maxStems) return;
    suppressClick = false;
    paletteDrag = { id: event.pointerId, button, x: event.clientX, y: event.clientY, ghost: null };
    button.setPointerCapture(event.pointerId);
  });

  workbench.addEventListener('pointermove', event => {
    if (paletteDrag?.id !== event.pointerId) return;
    if (!paletteDrag.ghost && Math.hypot(event.clientX - paletteDrag.x, event.clientY - paletteDrag.y) > 9) {
      const ghost = paletteDrag.button.querySelector('img').cloneNode();
      ghost.classList.add('bouquet-ghost');
      document.body.append(ghost);
      paletteDrag.ghost = ghost;
    }
    if (paletteDrag.ghost) {
      paletteDrag.ghost.style.left = event.clientX + 'px';
      paletteDrag.ghost.style.top = event.clientY + 'px';
    }
  });

  function finishPaletteDrag(event) {
    if (paletteDrag?.id !== event.pointerId) return;
    const { ghost, button } = paletteDrag;
    if (event.type === 'lostpointercapture' && event.target !== button) return;
    paletteDrag = null;
    if (!ghost) return;
    ghost.remove();
    suppressClick = true;
    if (event.type !== 'pointerup') return;
    const drop = point(event);
    if (drop.x >= 0 && drop.x <= 640 && drop.y >= 0 && drop.y <= 440) add(button.dataset.addStem, drop);
  }

  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => workbench.addEventListener(type, finishPaletteDrag));

  heads.addEventListener('focusin', event => {
    if (event.target.hasAttribute('data-stem-index')) select(Number(event.target.dataset.stemIndex));
  });

  heads.addEventListener('pointerdown', event => {
    const head = event.target.closest('[data-stem-index]');
    if (!head || !event.isPrimary || event.button !== 0) return;
    const index = Number(head.dataset.stemIndex);
    const { x, y } = layout.stems[index];
    const start = point(event);
    head.focus({ preventScroll: true });
    select(index);
    svg.setPointerCapture(event.pointerId);
    move = { id: event.pointerId, index, x, y, dx: start.x - x, dy: start.y - y };
  });

  svg.addEventListener('pointermove', event => {
    if (move?.id !== event.pointerId) return;
    const p = point(event);
    relocate(move.index, p.x - move.dx, p.y - move.dy);
  });

  function finishMove(event) {
    if (move?.id !== event.pointerId) return;
    if (event.type === 'lostpointercapture' && event.target !== svg) return;
    if (event.type !== 'pointerup') relocate(move.index, move.x, move.y);
    move = null;
    sync();
  }

  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => svg.addEventListener(type, finishMove));

  const directions = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  heads.addEventListener('keydown', event => {
    if (selected < 0) return;
    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      removeSelected();
      return;
    }
    const direction = directions[event.key];
    if (!direction) return;
    event.preventDefault();
    const { x, y } = layout.stems[selected];
    const step = event.shiftKey ? 20 : 7;
    relocate(selected, x + direction[0] * step, y + direction[1] * step);
    sync();
  });

  window.addEventListener('pageshow', () => {
    // Some browsers restore the form field when returning from another page.
    const restored = readLayout(field.value);
    Object.assign(layout, restored);
    drawVessel();
    drawStems();
    select(-1);
  });

  sync();
  workbench.hidden = false;

  const copyDraft = editor.querySelector('[data-copy-draft]');
  if (copyDraft) {
    const status = editor.querySelector('[data-draft-status]');
    const output = editor.querySelector('[data-draft-output]');
    editor.addEventListener('submit', event => event.preventDefault());
    copyDraft.hidden = false;
    copyDraft.addEventListener('click', async () => {
      const counts = new Map();
      for (const { kind } of layout.stems) counts.set(kind, (counts.get(kind) || 0) + 1);
      const composition = Array.from(counts, ([kind, quantity]) => flowers[kind].name + ' × ' + quantity).join(', ');
      const elements = editor.elements;
      const note = elements.message.value.trim();
      if (!composition && !note) {
        status.textContent = 'Добавьте цветы или напишите, какой букет хотите.';
        return;
      }
      const occasion = elements.occasion;
      const fields = [
        'Основа: ' + (layout.vessel === 'basket' ? 'Корзина' : 'Ваза'),
        composition && 'Состав: ' + composition,
        elements.recipient.value.trim() && 'Кому: ' + elements.recipient.value.trim(),
        occasion.value && 'Повод: ' + occasion.selectedOptions[0].textContent,
        elements.date.value && 'Дата: ' + elements.date.value,
        elements.budget.value && 'Бюджет: до ' + elements.budget.value + ' ₽',
        note && 'Пожелания: ' + note,
      ].filter(Boolean);
      output.value = fields.join('\n');
      output.hidden = false;
      try {
        await navigator.clipboard.writeText(output.value);
        status.textContent = 'Состав скопирован.';
      } catch {
        output.select();
        status.textContent = 'Состав выделен. Его можно скопировать вручную.';
      }
    });
  }
})();
