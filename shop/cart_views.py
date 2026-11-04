"""Корзина. Каждое действие работает и без JavaScript (обычная форма → переход на страницу корзины),
а с JavaScript (заголовок X-Requested-With: fetch) отвечает готовым кусочком страницы, и корзина обновляется без перезагрузки."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .cart import Cart
from .models import Addon, Product
from .throttle import throttled


def wants_json(request):
    return request.headers.get('X-Requested-With') == 'fetch'


def cart_context(request, cart=None):
    """Всё, что нужно для отрисовки корзины (страница и боковая панель используют один шаблон)."""
    cart = cart or Cart(request)
    quote = cart.quote()
    return {'cart_quote': quote, 'cart_count': quote.count, 'cart_addons': cart.addon_states(quote), 'cart_promo': cart.promo}


def cart_page(request):
    return render(request, 'shop/cart.html', cart_context(request))


def _respond(request, cart, message='', ok=True, status=200):
    if wants_json(request):
        context = cart_context(request, cart)
        return JsonResponse({
            'ok': ok, 'count': context['cart_count'], 'message': message, 'total': context['cart_quote'].total,
            'html': render_to_string('includes/_cart_body.html', context, request=request),
        }, status=status)
    if message:
        (messages.success if ok else messages.error)(request, message)
    target = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = reverse('shop:cart')
    return redirect(target)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@require_POST
def cart_add(request):
    cart = Cart(request)
    if throttled(request, 'cart', 120, 600):
        return _respond(request, cart, 'Слишком много действий, подождите минуту.', ok=False, status=429)
    product = Product.objects.filter(pk=_int(request.POST.get('product')), is_active=True).prefetch_related('variants').first()
    if product is None:
        return _respond(request, cart, 'Такого букета нет.', ok=False, status=404)
    if product.unavailable_reason:
        return _respond(request, cart, f'«{product.name}»: {product.unavailable_reason.lower()}.', ok=False, status=409)
    variant_id = _int(request.POST.get('variant'))
    variants = {v.pk: v for v in product.active_variants}
    if variants:
        variant_id = variant_id if variant_id in variants else product.default_variant.pk
    else:
        variant_id = 0
    cart.add(product.pk, variant_id, max(1, _int(request.POST.get('qty'), 1)))
    for addon_id in request.POST.getlist('addon'):
        if Addon.objects.filter(pk=_int(addon_id), is_active=True).exists() and str(_int(addon_id)) not in cart.addons:
            cart.set_addon(_int(addon_id), True)
    return _respond(request, cart, f'«{product.name}» — в корзине')


@require_POST
def cart_update(request):
    cart = Cart(request)
    cart.set_qty(request.POST.get('key', ''), _int(request.POST.get('qty')))
    return _respond(request, cart)


@require_POST
def cart_remove(request):
    cart = Cart(request)
    cart.remove(request.POST.get('key', ''))
    return _respond(request, cart, 'Убрали из корзины')


@require_POST
def cart_addon(request):
    cart = Cart(request)
    addon = Addon.objects.filter(pk=_int(request.POST.get('addon')), is_active=True).first()
    if addon is None:
        return _respond(request, cart, 'Такого дополнения нет.', ok=False, status=404)
    cart.set_addon(addon.pk, request.POST.get('on') == '1', request.POST.get('note', ''))
    return _respond(request, cart)


@require_POST
def cart_promo(request):
    cart = Cart(request)
    code = request.POST.get('code', '').strip()
    if not code:
        cart.set_promo('')
        return _respond(request, cart, 'Промокод убран')
    if throttled(request, 'promo', 15, 600):
        return _respond(request, cart, 'Слишком много попыток. Попробуйте через несколько минут.', ok=False, status=429)
    from .pricing import build_quote
    lines, addon_rows = cart.resolve()
    quote = build_quote(lines, addon_rows, code)
    if quote.promo is None:
        return _respond(request, cart, quote.promo_error or 'Такого промокода нет', ok=False, status=400)
    cart.set_promo(quote.promo.code)
    return _respond(request, cart, f'Промокод {quote.promo.code} применён')


def cart_fragment(request):
    """Свежее содержимое корзины для боковой панели (вызывается при её открытии)."""
    return JsonResponse({'html': render_to_string('includes/_cart_body.html', cart_context(request), request=request)})
