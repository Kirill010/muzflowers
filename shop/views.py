import json
import re
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Order, OrderItem, Product, PromoCode

FREE_FROM = getattr(settings, 'SHOP_FREE_DELIVERY_FROM', 3000)
DELIVERY = getattr(settings, 'SHOP_DELIVERY_COST', 300)
SLOTS = ['9:00–12:00', '12:00–15:00', '15:00–18:00', '18:00–21:00']


def _client_ip(request):
    # Заголовок с реальным IP читаем, только если его явно указали в настройках
    # (его должен выставлять ваш nginx, затирая клиентское значение).
    header = getattr(settings, 'SHOP_CLIENT_IP_HEADER', None)
    return (request.META.get(header, '') if header else '') or request.META.get('REMOTE_ADDR', '')


def _throttled(request, scope, limit, window):
    """Не больше `limit` запросов за `window` секунд с одного IP. Нужен общий кэш (Redis)."""
    key = f'shop:{scope}:{_client_ip(request)}'
    cache.add(key, 0, window)
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.set(key, 1, window)
        return False


@ensure_csrf_cookie
def index(request):
    products = [
        {
            'id': p.id, 'n': p.name, 'd': p.description, 'p': p.price, 'c': p.category.name,
            'a': p.color_a, 'b': p.color_b, 'k': p.petals, 't': p.badge,
            'img': p.image.url if p.image else '',
        }
        for p in Product.objects.filter(is_active=True).select_related('category')
    ]
    config = {
        'free': FREE_FROM, 'delivery': DELIVERY,
        'promoUrl': reverse('shop:promo'), 'orderUrl': reverse('shop:order'),
    }
    return render(request, 'shop/index.html', {'products': products, 'config': config})


def _body(request):
    try:
        data = json.loads(request.body)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _find_promo(code):
    promo = PromoCode.objects.filter(code__iexact=str(code).strip()).first() if code else None
    return promo if promo and promo.is_valid() else None


def _error(msg, status=400):
    return JsonResponse({'ok': False, 'error': msg}, status=status)


@require_POST
def promo_check(request):
    if _throttled(request, 'promo', 15, 600):
        return _error('Слишком много попыток. Попробуйте через несколько минут', 429)
    promo = _find_promo(_body(request).get('code'))
    return JsonResponse({'ok': bool(promo), 'percent': promo.percent if promo else 0})


@require_POST
def order_create(request):
    if _throttled(request, 'order', 10, 3600):
        return _error('Слишком много заказов с одного адреса. Позвоните нам', 429)
    d = _body(request)
    name = str(d.get('name', '')).strip()[:100]
    phone = str(d.get('phone', '')).strip()[:30]
    address = str(d.get('address', '')).strip()[:255]
    note = str(d.get('note', '')).strip()[:500]
    slot = d.get('slot') if d.get('slot') in SLOTS else SLOTS[0]
    try:
        when = date.fromisoformat(str(d.get('date', '')))
    except ValueError:
        when = None

    if not name or not address or len(re.sub(r'\D', '', phone)) < 10:
        return _error('Проверьте имя, телефон и адрес')
    if d.get('consent') is not True:
        return _error('Нужно согласие на обработку персональных данных')
    today = timezone.localdate()
    if not when or not today <= when <= today + timedelta(days=90):
        return _error('Выберите дату доставки в ближайшие 90 дней')

    qty = {}
    items = d.get('items')
    for it in (items[:30] if isinstance(items, list) else []):
        try:
            pid, n = int(it['id']), int(it['qty'])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 < n <= 50:
            qty[pid] = qty.get(pid, 0) + n
    products = list(Product.objects.filter(is_active=True, id__in=qty))
    if not products:
        return _error('Корзина пуста или букеты больше недоступны')

    # Цены берутся только из БД — данным от клиента не доверяем.
    subtotal = sum(p.price * qty[p.id] for p in products)
    promo = _find_promo(d.get('promo'))
    discount = round(subtotal * promo.percent / 100) if promo else 0
    delivery = 0 if subtotal - discount >= FREE_FROM else DELIVERY

    with transaction.atomic():
        order = Order.objects.create(
            name=name, phone=phone, address=address, delivery_date=when, delivery_slot=slot,
            card_text=note, promo_code=promo.code if promo else '', subtotal=subtotal,
            discount=discount, delivery_cost=delivery, total=subtotal - discount + delivery,
        )
        OrderItem.objects.bulk_create(
            OrderItem(order=order, product=p, name=p.name, price=p.price, qty=qty[p.id]) for p in products
        )
    return JsonResponse({'ok': True, 'number': order.pk})
