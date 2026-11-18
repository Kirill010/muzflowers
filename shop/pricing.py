"""Расчёт цен. Единственное место, где считаются скидка, доставка и итог:
корзина, оформление и заказ берут цифры отсюда — данным из браузера не доверяем."""
from dataclasses import dataclass, field

from .models import Order, PromoCode, SiteSettings


@dataclass
class Line:
    key: str
    product: object
    variant: object
    qty: int

    @property
    def unit_price(self):
        return self.variant.price if self.variant else self.product.price

    @property
    def total(self):
        return self.unit_price * self.qty

    @property
    def variant_name(self):
        return self.variant.name if self.variant else ''

    @property
    def problem(self):
        """Почему эту позицию сейчас нельзя заказать (пусто — можно)."""
        if self.variant is not None and not self.variant.is_active:
            return 'Этот размер сейчас недоступен'
        return self.product.unavailable_reason


@dataclass
class Quote:
    lines: list
    addon_rows: list  # [(Addon, заметка клиента)]
    subtotal: int = 0
    discount: int = 0
    addons_total: int = 0
    delivery: int = 0
    total: int = 0
    promo: object = None
    promo_error: str = ''
    free_from: int = 0
    free_left: int = 0
    pickup_discount: int = 0

    @property
    def total_discount(self):
        return self.discount + self.pickup_discount

    method: str = ''
    problems: list = field(default_factory=list)

    @property
    def count(self):
        return sum(line.qty for line in self.lines)

    @property
    def free_progress(self):
        """Сколько процентов пути до бесплатной доставки (0–100)."""
        if not self.free_from:
            return 0
        return min(100, int((self.subtotal - self.discount) * 100 / self.free_from))


def find_promo(code):
    code = (code or '').strip()
    return PromoCode.objects.filter(code__iexact=code).first() if code else None


def build_quote(lines, addon_rows, promo_code='', method='', site=None, today=None):
    site = site or SiteSettings.load()
    subtotal = sum(line.total for line in lines)

    promo, promo_error, discount = find_promo(promo_code), '', 0
    if promo_code and promo is None:
        promo_error = 'Такого промокода нет'
    elif promo is not None:
        promo_error = promo.problem(subtotal, today)
        if promo_error:
            promo = None
        else:
            discount = promo.discount_for(subtotal)

    addons_total = sum(addon.price for addon, _ in addon_rows)
    after_discount = subtotal - discount
    pickup_discount = ((after_discount * site.pickup_discount_percent + 50) // 100
                       if method == Order.Method.PICKUP else 0)
    free_from = site.free_delivery_from
    delivery = 0
    if method == Order.Method.DELIVERY:
        delivery = 0 if (free_from and after_discount >= free_from) else site.delivery_cost

    problems = [f'«{line.product.name}»: {line.problem}' for line in lines if line.problem]
    if lines and site.min_order and subtotal < site.min_order:
        problems.append(f'Минимальная сумма заказа — {site.min_order} ₽')
    if method == Order.Method.DELIVERY and not site.delivery_enabled:
        problems.append('Доставка сейчас не работает — выберите самовывоз')

    return Quote(
        lines=lines, addon_rows=addon_rows, subtotal=subtotal, discount=discount, addons_total=addons_total,
        delivery=delivery, total=after_discount - pickup_discount + addons_total + delivery,
        pickup_discount=pickup_discount, promo=promo, promo_error=promo_error,
        free_from=free_from, free_left=max(0, free_from - after_discount) if free_from else 0,
        method=method, problems=problems,
    )
