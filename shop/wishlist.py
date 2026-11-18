class Wishlist:
    SESSION_KEY = 'mz_wishlist'
    MAX_ITEMS = 50

    def __init__(self, request):
        self.session = request.session
        raw = self.session.get(self.SESSION_KEY) or []
        self.ids = []
        for value in raw if isinstance(raw, list) else []:
            try:
                product_id = int(value)
            except (TypeError, ValueError):
                continue
            if product_id > 0 and product_id not in self.ids and len(self.ids) < self.MAX_ITEMS:
                self.ids.append(product_id)

    @property
    def count(self):
        return len(self.ids)

    def toggle(self, product_id):
        if product_id in self.ids:
            self.ids.remove(product_id)
            active, changed = False, True
        elif len(self.ids) >= self.MAX_ITEMS:
            return False, False
        else:
            self.ids.append(product_id)
            active, changed = True, True
        self.session[self.SESSION_KEY] = self.ids
        self.session.modified = True
        return active, changed

    def products(self):
        from .views import catalog_qs

        found = {p.pk: p for p in catalog_qs().filter(pk__in=self.ids)}
        return [found[product_id] for product_id in self.ids if product_id in found]
