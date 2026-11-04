"""Корзина живёт в сессии (cookie с номером сессии), а не в браузере: работает без JavaScript,
цены всегда свежие, и на сервере нечего подделывать."""
from .models import Addon, Product, Variant
from .pricing import Line, build_quote

MAX_LINES = 30
MAX_QTY = 50


class Cart:
    SESSION_KEY = 'mz_cart'

    def __init__(self, request):
        self.session = request.session
        data = self.session.get(self.SESSION_KEY) or {}
        self.items = {str(k): int(v) for k, v in (data.get('items') or {}).items()}
        self.addons = {str(k): str(v) for k, v in (data.get('addons') or {}).items()}
        self.promo = str(data.get('promo') or '')

    def _save(self):
        self.session[self.SESSION_KEY] = {'items': self.items, 'addons': self.addons, 'promo': self.promo}
        self.session.modified = True

    @staticmethod
    def key(product_id, variant_id=0):
        return f'{int(product_id)}:{int(variant_id or 0)}'

    @property
    def count(self):
        return sum(self.items.values())

    def __bool__(self):
        return bool(self.items)

    # --- изменения ---
    def add(self, product_id, variant_id=0, qty=1):
        key = self.key(product_id, variant_id)
        if key not in self.items and len(self.items) >= MAX_LINES:
            return
        self.items[key] = min(MAX_QTY, self.items.get(key, 0) + max(1, int(qty)))
        self._save()

    def set_qty(self, key, qty):
        if key in self.items:
            if int(qty) <= 0:
                del self.items[key]
            else:
                self.items[key] = min(MAX_QTY, int(qty))
            self._save()

    def remove(self, key):
        self.set_qty(key, 0)

    def set_addon(self, addon_id, on, note=''):
        addon_id = str(int(addon_id))
        if on:
            self.addons[addon_id] = str(note)[:200]
        else:
            self.addons.pop(addon_id, None)
        self._save()

    def set_promo(self, code):
        self.promo = str(code or '').strip().upper()[:30]
        self._save()

    def clear(self):
        self.items, self.addons, self.promo = {}, {}, ''
        self._save()

    # --- превращаем содержимое сессии в настоящие букеты ---
    def resolve(self):
        """Возвращает (позиции, дополнения). Удалённые из каталога букеты тихо выбрасываем."""
        parsed = {}
        for key, qty in self.items.items():
            try:
                pid, vid = (int(x) for x in key.split(':'))
            except ValueError:
                continue
            parsed[key] = (pid, vid, qty)

        products = Product.objects.filter(id__in={p for p, _, _ in parsed.values()}, is_active=True) \
            .prefetch_related('variants', 'photos')
        by_id = {p.id: p for p in products}
        lines = []
        for key, (pid, vid, qty) in parsed.items():
            product = by_id.get(pid)
            if product is None:
                continue
            variant = None
            if vid:
                variant = next((v for v in product.variants.all() if v.id == vid), None)
                if variant is None:
                    continue
            elif product.active_variants:  # у букета появились размеры — берём первый
                variant = product.default_variant
            lines.append(Line(key=key, product=product, variant=variant, qty=qty))

        addon_rows = []
        if self.addons:
            found = {str(a.id): a for a in Addon.objects.filter(id__in=[int(i) for i in self.addons], is_active=True)}
            addon_rows = [(found[i], note) for i, note in self.addons.items() if i in found]
        return lines, addon_rows

    def quote(self, method='', site=None):
        lines, addon_rows = self.resolve()
        return build_quote(lines, addon_rows, self.promo, method=method, site=site)

    def addon_states(self, quote=None):
        """Все дополнения магазина и отметка, какие из них клиент уже выбрал: [{'addon', 'on', 'note'}]."""
        chosen = {str(addon.pk): note for addon, note in (quote or self.quote()).addon_rows}
        return [{'addon': a, 'on': str(a.pk) in chosen, 'note': chosen.get(str(a.pk), '')}
                for a in Addon.objects.filter(is_active=True)]

    def prune(self):
        """Убирает из сессии то, чего уже нет в каталоге (чтобы счётчик на значке не врал)."""
        lines, addon_rows = self.resolve()
        keep = {line.key for line in lines}
        if keep != set(self.items):
            self.items = {k: v for k, v in self.items.items() if k in keep}
            self._save()
