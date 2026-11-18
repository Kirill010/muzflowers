"""Создание заказа: единственное место, где корзина превращается в Order."""
import logging

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from . import notifications, payments, slots
from .legal import record_acceptance
from .models import Order, OrderAddon, OrderItem, PromoCode, SiteSettings

log = logging.getLogger('shop')


class OrderError(Exception):
    """Понятная клиенту причина, по которой заказ не создан."""


def is_prepay_required(day, site=None):
    """Правило магазина: букет на определённую дату (не сегодня) — только с полной предоплатой."""
    site = site or SiteSettings.load()
    return bool(site.prepay_future_orders and day > timezone.localdate())


def payment_options(prepay_required, site=None):
    """Какие способы оплаты показываем клиенту. Всегда есть хотя бы один."""
    site = site or SiteSettings.load()
    has_details = bool(site.payment_details.strip())
    options = []
    if payments.is_configured():
        options.append({'value': Order.Pay.ONLINE, 'label': 'Картой или через СБП онлайн', 'hint': 'Откроется безопасная страница банка'})
    if has_details:
        options.append({'value': Order.Pay.TRANSFER, 'label': 'Переводом по реквизитам', 'hint': 'Реквизиты покажем после оформления'})
    elif prepay_required:
        options.append({'value': Order.Pay.TRANSFER, 'label': 'Предоплата — пришлём ссылку на оплату',
                        'hint': 'Мы свяжемся с вами и отправим ссылку, пока букет не оплачен — он не в работе'})
    if not prepay_required and site.allow_pay_on_receipt:
        options.append({'value': Order.Pay.ON_RECEIPT, 'label': 'При получении (картой или наличными)', 'hint': ''})
    if not options:
        options.append({'value': Order.Pay.TRANSFER, 'label': 'Предоплата — пришлём ссылку на оплату', 'hint': ''})
    options[0]['default'] = True
    return options


@transaction.atomic
def create_order(*, quote, data, user=None, source='', origin='', request=None):
    """Создаёт заказ из рассчитанной корзины (`quote`) и проверенных данных формы (`data`)."""
    site = SiteSettings.load()
    if site.orders_paused:
        raise OrderError(site.pause_message or 'Сейчас не принимаем заказы на сайте.')
    if not quote.lines:
        raise OrderError('Корзина пуста.')
    if quote.problems:
        raise OrderError(quote.problems[0])

    method, day = data['receive_method'], data['date']
    problem = slots.day_problem(day, method, site)  # ещё раз внутри транзакции: пока клиент заполнял форму, день мог заполниться
    if problem:
        raise OrderError(problem)

    promo = quote.promo
    if promo is not None:
        claimed = PromoCode.objects.filter(pk=promo.pk).filter(
            Q(usage_limit__isnull=True) | Q(used_count__lt=F('usage_limit'))).update(used_count=F('used_count') + 1)
        if not claimed:
            raise OrderError('Этот промокод уже использован.')

    option = data['option']
    prepay = is_prepay_required(day, site)
    pay_method = data['payment_method']
    order = Order.objects.create(
        user=user, name=data['name'], phone=data['phone'], email=data.get('email', ''),
        receive_method=method, shop=data.get('shop') if method == Order.Method.PICKUP else None,
        address=data.get('address', '') if method == Order.Method.DELIVERY else '',
        address_details=data.get('address_details', '') if method == Order.Method.DELIVERY else '',
        recipient_name=data.get('recipient_name', ''), recipient_phone=data.get('recipient_phone', ''),
        surprise=data.get('surprise', False),
        date=day, time_from=option['time_from'], time_to=option['time_to'], asap=option['asap'],
        card_text=data.get('card_text', ''), comment=data.get('comment', ''),
        promo_code=promo.code if promo else '',
        subtotal=quote.subtotal, discount=quote.total_discount, addons_total=quote.addons_total,
        delivery_cost=quote.delivery, total=quote.total,
        payment_method=pay_method, prepay_required=prepay,
        payment_status=Order.PayStatus.UNPAID if pay_method == Order.Pay.ON_RECEIPT else Order.PayStatus.PENDING,
        source=source[:40], marketing_consent=data.get('marketing_consent', False),
    )
    OrderItem.objects.bulk_create(
        OrderItem(order=order, product=line.product, variant=line.variant, name=line.product.name,
                  variant_name=line.variant_name, price=line.unit_price, qty=line.qty)
        for line in quote.lines)
    OrderAddon.objects.bulk_create(
        OrderAddon(order=order, addon=addon, name=addon.name, price=addon.price, note=note[:200])
        for addon, note in quote.addon_rows)
    if request is not None:
        contact = order.email or order.phone
        record_acceptance(request, 'offer', reference=f'order:{order.pk}', contact=contact, user=user)
        record_acceptance(request, 'personal', reference=f'order:{order.pk}', contact=contact, user=user)
        if order.marketing_consent:
            record_acceptance(request, 'marketing', reference=f'order:{order.pk}', contact=contact, user=user)

    transaction.on_commit(lambda: notifications.dispatch(order.pk, origin))
    log.info('Новый заказ №%s на %s рублей', order.pk, order.total)
    return order
