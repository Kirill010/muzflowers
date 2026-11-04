"""Оформление заказа, страница заказа и оплата."""
import json
from datetime import date, timedelta

from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import payments, slots
from .cart import Cart
from .forms import CheckoutForm
from .models import Addon, Order, SiteSettings
from .orders import OrderError, create_order, is_prepay_required, payment_options
from .pricing import build_quote
from .throttle import throttled
from .views import origin_of


def _first_free_day(method, site):
    today = timezone.localdate()
    for offset in range(0, min(site.max_days_ahead, 60) + 1):
        day = today + timedelta(days=offset)
        if not slots.day_problem(day, method, site):
            return day
    return today


def _initial(request, site):
    initial = {'receive_method': Order.Method.PICKUP}
    user = request.user
    if user.is_authenticated:
        from accounts.models import profile_of
        profile = profile_of(user)
        initial.update(name=user.first_name or user.get_username(), phone=profile.phone, email=user.email,
                       address=profile.address, marketing_consent=profile.marketing_consent)
        last = user.orders.order_by('-created').first()
        if last:
            initial.update(name=last.name, phone=last.phone, email=last.email or user.email,
                           address=last.address or profile.address)
    return initial


def _chosen_method(raw):
    return raw if raw in (Order.Method.PICKUP, Order.Method.DELIVERY) else Order.Method.PICKUP


def _parse_day(raw, fallback):
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return fallback


def _summary_html(request, cart, method, site, addon_ids=None, promo=None):
    lines, rows = cart.resolve()
    if addon_ids is not None:
        chosen = {a.pk: a for a in Addon.objects.filter(pk__in=addon_ids, is_active=True)}
        notes = {str(k): v for k, v in cart.addons.items()}
        rows = [(chosen[i], notes.get(str(i), '')) for i in addon_ids if i in chosen]
    quote = build_quote(lines, rows, cart.promo if promo is None else promo, method=method, site=site)
    return quote, render_to_string('shop/_checkout_summary.html', {'quote': quote, 'site': site}, request=request)


@never_cache
def checkout(request):
    cart = Cart(request)
    site = SiteSettings.load()
    quote = cart.quote(Order.Method.PICKUP, site)
    if not quote.lines:
        messages.info(request, 'Корзина пуста — выберите букет.')
        return redirect('shop:catalog')

    if request.method == 'POST':
        form = CheckoutForm(request.POST, site=site, cart=cart)
        if throttled(request, 'order', 10, 3600):
            form.add_error(None, 'Слишком много заказов с одного адреса. Позвоните нам — оформим по телефону.')
        elif form.is_valid():
            data = form.cleaned_data
            lines, _ = cart.resolve()
            final = build_quote(lines, data['addons'], data.get('promo') or cart.promo, method=data['receive_method'], site=site)
            try:
                order = create_order(quote=final, data=data, source=request.session.get('mz_src', ''),
                                     user=request.user if request.user.is_authenticated else None, origin=origin_of(request))
            except OrderError as exc:
                form.add_error(None, str(exc))
            else:
                cart.clear()
                request.session['mz_last_order'] = order.token
                _remember_customer(request, order)
                if order.payment_method == Order.Pay.ONLINE and payments.is_configured():
                    return redirect('shop:order_pay', token=order.token)
                return redirect(order)
        method = _chosen_method(request.POST.get('receive_method'))
        day = _parse_day(request.POST.get('date'), _first_free_day(method, site))
        slot_value = request.POST.get('time_slot', '')
    else:
        form = CheckoutForm(site=site, cart=cart, initial=_initial(request, site))
        method = Order.Method.PICKUP if form.pickup_shops else Order.Method.DELIVERY
        day = _first_free_day(method, site)
        options = slots.time_options(day, method, site)
        slot_value = options[0]['value'] if options else ''
        form.initial.update(receive_method=method, date=day.isoformat(), time_slot=slot_value)

    prepay = is_prepay_required(day, site)
    summary_quote, _ = _summary_html(request, cart, method, site)
    context = {
        'form': form, 'site': site, 'quote': summary_quote, 'method': method, 'day': day,
        'slot_options': slots.time_options(day, method, site), 'slot_value': slot_value, 'day_problem': slots.day_problem(day, method, site),
        'min_day': timezone.localdate().isoformat(), 'max_day': (timezone.localdate() + timedelta(days=site.max_days_ahead)).isoformat(),
        'blocked_days': json.dumps(slots.unavailable_dates(site), ensure_ascii=False),
        'prepay': prepay, 'payments': payment_options(prepay, site), 'selected_payment': request.POST.get('payment_method', ''),
        'shop_count': len(form.pickup_shops),
    }
    return render(request, 'shop/checkout.html', context)


def _remember_customer(request, order):
    """Запоминаем телефон и адрес в профиле вошедшего покупателя — в следующий раз форма заполнится сама."""
    if not request.user.is_authenticated:
        return
    from accounts.models import profile_of
    profile = profile_of(request.user)
    changed = False
    if not profile.phone:
        profile.phone, changed = order.phone, True
    if order.address and not profile.address:
        profile.address, changed = order.address, True
    if order.marketing_consent and not profile.marketing_consent:
        profile.marketing_consent, changed = True, True
    if changed:
        profile.save()


@require_GET
def checkout_state(request):
    """Что менять на странице оформления, когда клиент выбрал способ получения или дату."""
    cart = Cart(request)
    site = SiteSettings.load()
    method = _chosen_method(request.GET.get('method'))
    day = _parse_day(request.GET.get('date'), _first_free_day(method, site))
    problem = slots.day_problem(day, method, site)
    options = [] if problem else slots.time_options(day, method, site)
    prepay = is_prepay_required(day, site) if not problem else False
    addon_ids = [int(x) for x in request.GET.get('addons', '').split(',') if x.isdigit()]
    quote, html = _summary_html(request, cart, method, site, addon_ids=addon_ids)
    return JsonResponse({
        'problem': problem, 'slots': [{'value': o['value'], 'label': o['label']} for o in options],
        'prepay': prepay, 'payments': payment_options(prepay, site), 'summary': html, 'total': quote.total,
    })


@never_cache
def order_status(request, token):
    order = get_object_or_404(Order.objects.select_related('shop').prefetch_related('items', 'addons'), token=token)
    site = SiteSettings.load()
    if order.payment_method == Order.Pay.ONLINE and order.payment_status == Order.PayStatus.PENDING and payments.refresh(order):
        from . import notifications
        notifications.dispatch_paid(order.pk)  # клиент вернулся с оплаты раньше, чем банк прислал уведомление
    response = render(request, 'shop/order_status.html', {
        'order': order, 'site': site, 'just_created': request.session.get('mz_last_order') == token,
        'steps': order.status_steps, 'can_pay': order.payment_status != Order.PayStatus.PAID and order.payment_method == Order.Pay.ONLINE
        and payments.is_configured() and order.status != Order.Status.CANCELED,
    })
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@never_cache
def order_pay(request, token):
    """Открывает страницу оплаты банка. Ссылка создаётся один раз и повторно используется."""
    order = get_object_or_404(Order, token=token)
    if order.is_paid or order.status == Order.Status.CANCELED or not payments.is_configured():
        return redirect(order)
    try:
        url = payments.start_payment(order, return_url=origin_of(request) + order.get_absolute_url())
    except payments.PaymentError as exc:
        messages.error(request, f'Не удалось открыть оплату: {exc} Позвоните нам — поможем оплатить.')
        return redirect(order)
    return redirect(url)


@csrf_exempt
@require_POST
def payment_webhook(request, provider):
    """Банк сообщает, что платёж прошёл. Данным из запроса не верим — статус перепроверяется у банка."""
    if provider != payments.provider():
        raise Http404
    try:
        order = payments.handle_webhook(request)
    except payments.PaymentError:
        return HttpResponse(status=400)
    if order is not None:
        from . import notifications
        notifications.dispatch_paid(order.pk)
    return HttpResponse('OK')
