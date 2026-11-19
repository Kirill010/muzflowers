import hashlib
import hmac
import json
import re
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import notifications, payments, slots
from .certificates import normalize_certificate_code
from .forms import CheckoutForm, clean_phone_value
from .legal import record_acceptance
from .models import Addon, BotOperation, GiftCertificate, Lead, Order, Product, Review, Shop, SiteSettings
from .orders import OrderError, create_order, is_prepay_required, payment_options
from .pricing import Line, build_quote
from .throttle import throttled
from .thumbs import thumb_url
from .views import catalog_qs, origin_of

MAX_BODY = 65536
IDEMPOTENCY_RE = re.compile(r'^[A-Za-z0-9_.:-]{8,100}$')


def _error(message, status=400, **extra):
    return JsonResponse({'ok': False, 'error': message, **extra}, status=status)


def _secret():
    return getattr(settings, 'BOT_API_SECRET', '')


def bot_view(view):
    @csrf_exempt
    def wrapped(request, *args, **kwargs):
        if request.method != 'POST':
            return _error('Метод не поддерживается', 405)
        if len(request.body) > MAX_BODY:
            return _error('Слишком большой запрос', 413)
        if throttled(request, 'bot-api', 240, 60):
            return _error('Слишком много запросов', 429)
        secret = _secret()
        if len(secret) < 32:
            return _error('API бота не настроено', 503)
        timestamp = request.headers.get('X-Muz-Timestamp', '')
        nonce = request.headers.get('X-Muz-Nonce', '')
        signature = request.headers.get('X-Muz-Signature', '')
        if not timestamp.isdigit() or abs(int(timezone.now().timestamp()) - int(timestamp)) > 300:
            return _error('Запрос устарел', 401)
        if not re.fullmatch(r'[A-Za-z0-9_-]{12,64}', nonce):
            return _error('Некорректный номер запроса', 401)
        signed = timestamp.encode() + b'.' + request.path.encode() + b'.' + request.body
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return _error('Доступ запрещён', 403)
        if not cache.add(f'bot-nonce:{nonce}', 1, 600):
            return _error('Повторный запрос', 409)
        try:
            request.bot_data = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return _error('Нужен корректный JSON')
        if not isinstance(request.bot_data, dict):
            return _error('Нужен JSON-объект')
        return view(request, *args, **kwargs)
    return wrapped


def idempotent(action):
    def decorator(view):
        def wrapped(request, *args, **kwargs):
            key = request.headers.get('X-Idempotency-Key', '')
            telegram_id = _int(request.bot_data.get('telegram_user_id'), 0)
            if not IDEMPOTENCY_RE.fullmatch(key) or telegram_id <= 0:
                return _error('Нужны идентификатор операции и Telegram-пользователя')
            try:
                with transaction.atomic():
                    operation = BotOperation.objects.create(action=action, key=key, telegram_user_id=telegram_id)
                    response = view(request, *args, **kwargs)
                    operation.response = json.loads(response.content.decode('utf-8'))
                    operation.status_code = response.status_code
                    operation.save(update_fields=['response', 'status_code'])
                    return response
            except IntegrityError:
                operation = BotOperation.objects.filter(action=action, key=key, telegram_user_id=telegram_id).first()
                if operation and operation.response:
                    return JsonResponse(operation.response, status=operation.status_code)
                return _error('Такая операция уже выполняется', 409)
        return wrapped
    return decorator


def _int(value, default=0):
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(data, key, maximum):
    value = data.get(key, '')
    return str(value).strip()[:maximum] if isinstance(value, str) else ''


def _telegram_id(request, admin=False):
    telegram_id = _int(request.bot_data.get('telegram_user_id'))
    allowed = set(getattr(settings, 'BOT_ADMIN_IDS', [])) if admin else set()
    return telegram_id if telegram_id > 0 and (not admin or telegram_id in allowed) else None


def _absolute(request, path):
    return origin_of(request) + path if path.startswith('/') else path


def _product_data(request, product):
    cover = product.cover
    image = thumb_url(cover, 960) if cover else product.art_url
    return {
        'id': product.pk, 'slug': product.slug, 'name': product.name, 'tagline': product.tagline,
        'description': product.description, 'category': product.category.name, 'price': product.price_from,
        'available': product.is_orderable, 'in_stock': product.in_stock, 'unavailable_reason': product.unavailable_reason,
        'badge': product.badge, 'illustration': not bool(cover), 'image': _absolute(request, image),
        'url': _absolute(request, product.get_absolute_url()),
        'variants': [{'id': v.pk, 'name': v.name, 'price': v.price} for v in product.active_variants],
    }


def _order_data(request, order):
    certificate = GiftCertificate.objects.filter(purchase_order=order).first()
    return {
        'id': order.pk, 'kind': order.kind, 'token': order.token, 'url': _absolute(request, order.get_absolute_url()),
        'created': order.created.isoformat(),
        'status': order.status, 'payment_method': order.payment_method, 'payment_status': order.payment_status,
        'name': order.name, 'phone': order.phone, 'date': order.date.isoformat(), 'time': order.time_display,
        'method': order.receive_method, 'address': order.place_display, 'subtotal': order.subtotal,
        'discount': order.discount, 'addons_total': order.addons_total, 'delivery': order.delivery_cost,
        'certificate_amount': order.certificate_amount, 'total': order.total, 'pay_url': order.pay_url,
        'items': [{'name': item.full_name, 'price': item.price, 'qty': item.qty, 'product_id': item.product_id,
                   'variant_id': item.variant_id} for item in order.items.all()],
        'addons': [{'name': addon.name, 'price': addon.price, 'note': addon.note} for addon in order.addons.all()],
        'delivery_photo': _absolute(request, order.delivery_photo.url) if order.delivery_photo else '',
        'certificate': _certificate_data(certificate) if certificate else None,
    }


def _certificate_data(certificate):
    if certificate is None:
        return None
    return {'code': certificate.code, 'amount': certificate.amount, 'balance': certificate.balance,
            'status': certificate.status, 'expires_at': certificate.expires_at.isoformat()}


def _quote_data(quote, site, day=None):
    if quote.total == 0 and quote.certificate_amount:
        methods = [{'value': Order.Pay.CERTIFICATE, 'label': 'Оформить с оплатой сертификатом', 'default': True}]
    else:
        methods = payment_options(is_prepay_required(day or timezone.localdate(), site), site)
    return {
        'ok': not quote.problems and not quote.certificate_error,
        'subtotal': quote.subtotal, 'discount': quote.total_discount, 'addons_total': quote.addons_total,
        'delivery': quote.delivery, 'certificate_amount': quote.certificate_amount, 'total': quote.total,
        'problems': quote.problems, 'promo_error': quote.promo_error, 'certificate_error': quote.certificate_error,
        'free_left': quote.free_left, 'payment_methods': methods,
    }


def _lines(data):
    raw_lines = data.get('lines', [])
    if not isinstance(raw_lines, list) or len(raw_lines) > 30:
        raise ValueError('Некорректная корзина')
    products = {p.pk: p for p in catalog_qs()}
    lines = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise ValueError('Некорректная позиция корзины')
        product = products.get(_int(raw.get('product')))
        qty = _int(raw.get('qty'))
        if product is None or not 1 <= qty <= 50:
            raise ValueError('Товар недоступен или количество неверно')
        variant_id = _int(raw.get('variant'))
        variants = {v.pk: v for v in product.active_variants}
        if variants:
            variant = variants.get(variant_id) or product.default_variant
        else:
            variant = None
        lines.append(Line(key=f'{product.pk}:{variant.pk if variant else 0}', product=product, variant=variant, qty=qty))
    addon_rows = []
    raw_addons = data.get('addons', [])
    if not isinstance(raw_addons, list) or len(raw_addons) > 10:
        raise ValueError('Некорректные дополнения')
    addons = {a.pk: a for a in Addon.objects.filter(is_active=True)}
    for raw in raw_addons:
        if not isinstance(raw, dict) or _int(raw.get('id')) not in addons:
            raise ValueError('Дополнение недоступно')
        addon = addons[_int(raw.get('id'))]
        note = _text(raw, 'note', 200)
        addon_rows.append((addon, note))
    return lines, addon_rows


def _quote(data, site):
    lines, addon_rows = _lines(data)
    return build_quote(lines, addon_rows, _text(data, 'promo', 30), method=_text(data, 'receive_method', 10),
                       site=site, certificate_code=_text(data, 'certificate_code', 20))


@bot_view
def bootstrap(request):
    site = SiteSettings.load()
    shops = list(Shop.objects.filter(is_active=True, is_pickup=True))
    return JsonResponse({
        'ok': True, 'shop': {
            'name': site.shop_name, 'phone': site.phone, 'email': site.email, 'hours': site.hours_display,
            'address': shops[0].full_address if shops else '', 'shop_id': shops[0].pk if shops else None,
            'map_url': site.yandex_maps_url, 'reviews_url': site.yandex_reviews_url,
            'telegram': site.telegram_url, 'max_url': site.max_url,
            'delivery_enabled': site.delivery_enabled, 'delivery_cost': site.delivery_cost,
            'free_delivery_from': site.free_delivery_from, 'pickup_discount_percent': site.pickup_discount_percent,
            'delivery_lead_minutes': site.delivery_lead_minutes, 'pickup_lead_minutes': site.pickup_lead_minutes,
            'max_days_ahead': site.max_days_ahead, 'online_payment': payments.is_configured(),
            'consent_url': _absolute(request, reverse('shop:consent')), 'offer_url': _absolute(request, reverse('shop:offer')),
            'certificate_amounts': [1000, 3000, 5000], 'certificate_min': 500, 'certificate_max': 30000,
        },
        'products': [_product_data(request, p) for p in catalog_qs()],
        'addons': [{'id': a.pk, 'name': a.name, 'description': a.description, 'price': a.price,
                    'note_label': a.note_label, 'note_required': a.note_required, 'is_music': a.is_music}
                   for a in Addon.objects.filter(is_active=True)],
    })


def _requested_day(data):
    try:
        return date.fromisoformat(_text(data, 'date', 10))
    except ValueError:
        return timezone.localdate()


@bot_view
def quote(request):
    site = SiteSettings.load()
    try:
        result = _quote(request.bot_data, site)
    except ValueError as exc:
        return _error(str(exc))
    return JsonResponse(_quote_data(result, site, _requested_day(request.bot_data)))


@bot_view
def availability(request):
    site = SiteSettings.load()
    day = _requested_day(request.bot_data)
    method = _text(request.bot_data, 'receive_method', 10)
    if method not in Order.Method.values:
        return _error('Выберите доставку или самовывоз')
    problem = slots.day_problem(day, method, site)
    options = slots.time_options(day, method, site)
    return JsonResponse({'ok': not problem, 'problem': problem, 'date': day.isoformat(), 'prepay': is_prepay_required(day, site),
                         'options': [{'value': option['value'], 'label': option['label'],
                                      'time_from': option['time_from'].isoformat() if option['time_from'] else None,
                                      'time_to': option['time_to'].isoformat() if option['time_to'] else None,
                                      'asap': option['asap']} for option in options]})


@bot_view
@idempotent('order.create')
def order_create(request):
    data = request.bot_data
    telegram_id = _telegram_id(request)
    if telegram_id is None:
        return _error('Некорректный Telegram-пользователь')
    site = SiteSettings.load()
    try:
        lines, addon_rows = _lines(data)
    except ValueError as exc:
        return _error(str(exc))
    form_data = {
        'name': _text(data, 'name', 100), 'phone': _text(data, 'phone', 30), 'email': _text(data, 'email', 254),
        'receive_method': _text(data, 'receive_method', 10), 'shop': _int(data.get('shop')),
        'address': _text(data, 'address', 255), 'address_details': _text(data, 'address_details', 120),
        'other_recipient': bool(data.get('other_recipient')), 'recipient_name': _text(data, 'recipient_name', 100),
        'recipient_phone': _text(data, 'recipient_phone', 30), 'surprise': bool(data.get('surprise')),
        'date': _text(data, 'date', 10), 'time_slot': _text(data, 'time_slot', 20),
        'card_text': _text(data, 'card_text', 500), 'comment': _text(data, 'comment', 500),
        'promo': _text(data, 'promo', 30), 'certificate_code': _text(data, 'certificate_code', 20),
        'payment_method': _text(data, 'payment_method', 12), 'consent_pd': data.get('consent_pd') is True,
        'consent_offer': data.get('consent_offer') is True, 'marketing_consent': data.get('marketing_consent') is True,
        'website': '',
    }
    for addon, note in addon_rows:
        form_data[f'addon_{addon.pk}'] = True
        form_data[f'addon_{addon.pk}_note'] = note
    form = CheckoutForm(form_data, site=site)
    if not form.is_valid():
        first = next((errors[0] for errors in form.errors.values()), 'Проверьте данные заказа')
        return _error(first, 400, fields=form.errors)
    cleaned = form.cleaned_data
    final = build_quote(lines, cleaned['addons'], cleaned.get('promo'), method=cleaned['receive_method'], site=site,
                        certificate_code=cleaned.get('certificate_code', ''))
    if _int(data.get('expected_total'), -1) not in (-1, final.total):
        return _error('Цена изменилась. Покажем новый расчёт.', 409, quote=_quote_data(final, site, cleaned['date']))
    cleaned['telegram_user_id'] = telegram_id
    try:
        order = create_order(quote=final, data=cleaned, source='telegram', origin=origin_of(request), request=request)
    except OrderError as exc:
        return _error(str(exc), 409)
    payment_error = ''
    if order.payment_method == Order.Pay.ONLINE and payments.is_configured():
        try:
            payments.start_payment(order, _absolute(request, order.get_absolute_url()))
        except payments.PaymentError:
            payment_error = 'Заказ сохранён. Ссылку на оплату пришлёт менеджер.'
    result = _order_data(request, order)
    result.update(ok=True, payment_error=payment_error)
    return JsonResponse(result, status=201)


@bot_view
def order_list(request):
    telegram_id = _telegram_id(request)
    if telegram_id is None:
        return _error('Некорректный Telegram-пользователь')
    orders = Order.objects.filter(telegram_user_id=telegram_id).prefetch_related('items', 'addons')[:20]
    return JsonResponse({'ok': True, 'orders': [_order_data(request, order) for order in orders]})


@bot_view
def order_detail(request):
    telegram_id = _telegram_id(request)
    order = Order.objects.filter(pk=_int(request.bot_data.get('order')), telegram_user_id=telegram_id) \
        .prefetch_related('items', 'addons').first()
    if order is None:
        return _error('Заказ не найден', 404)
    if order.payment_method == Order.Pay.ONLINE and order.payment_status == Order.PayStatus.PENDING:
        if payments.refresh(order):
            notifications.dispatch_paid(order.pk)
    return JsonResponse({'ok': True, 'order': _order_data(request, order)})


@bot_view
@idempotent('order.cancel')
def order_cancel(request):
    order = Order.objects.filter(pk=_int(request.bot_data.get('order')), telegram_user_id=_telegram_id(request)).first()
    if order is None:
        return _error('Заказ не найден', 404)
    if order.status != Order.Status.NEW or order.is_paid or order.kind != Order.Kind.PRODUCTS:
        return _error('Этот заказ уже нельзя отменить в боте. Напишите менеджеру.', 409)
    order.set_status(Order.Status.CANCELED)
    return JsonResponse({'ok': True, 'order': _order_data(request, order)})


@bot_view
def payment_link(request):
    order = Order.objects.filter(pk=_int(request.bot_data.get('order')), telegram_user_id=_telegram_id(request)).first()
    if order is None:
        return _error('Заказ не найден', 404)
    if order.is_paid:
        return JsonResponse({'ok': True, 'order': _order_data(request, order)})
    if order.payment_method != Order.Pay.ONLINE or order.status == Order.Status.CANCELED:
        return _error('Для этого заказа онлайн-оплата недоступна', 409)
    try:
        if not payments.refresh(order):
            payments.start_payment(order, _absolute(request, order.get_absolute_url()))
        else:
            notifications.dispatch_paid(order.pk)
    except payments.PaymentError as exc:
        return _error(str(exc), 503)
    return JsonResponse({'ok': True, 'order': _order_data(request, order)})


@bot_view
@idempotent('certificate.purchase')
def certificate_purchase(request):
    if not payments.is_configured():
        return _error('Онлайн-покупка сертификата пока не подключена', 503)
    amount = _int(request.bot_data.get('amount'))
    if not 500 <= amount <= 30000:
        return _error('Сумма сертификата должна быть от 500 до 30 000 ₽')
    name, phone = _text(request.bot_data, 'name', 100), _text(request.bot_data, 'phone', 30)
    try:
        phone = clean_phone_value(phone)
    except ValidationError:
        return _error('Проверьте телефон')
    if not name or not phone or request.bot_data.get('consent_pd') is not True or request.bot_data.get('consent_offer') is not True:
        return _error('Укажите имя, телефон и подтвердите документы')
    order = Order.objects.create(
        kind=Order.Kind.CERTIFICATE, telegram_user_id=_telegram_id(request), name=name, phone=phone,
        email=_text(request.bot_data, 'email', 254), date=timezone.localdate(), asap=True,
        subtotal=amount, total=amount, payment_method=Order.Pay.ONLINE, payment_status=Order.PayStatus.PENDING,
        source='telegram-certificate',
    )
    record_acceptance(request, 'offer', reference=f'order:{order.pk}', contact=order.email or order.phone)
    record_acceptance(request, 'personal', reference=f'order:{order.pk}', contact=order.email or order.phone)
    transaction.on_commit(lambda: notifications.dispatch(order.pk, origin_of(request)))
    try:
        payments.start_payment(order, _absolute(request, order.get_absolute_url()))
    except payments.PaymentError:
        return _error('Заказ на сертификат сохранён, но ссылку на оплату не удалось создать. Менеджер поможет.', 503,
                      order=_order_data(request, order))
    return JsonResponse({'ok': True, 'order': _order_data(request, order)}, status=201)


@bot_view
def certificate_check(request):
    telegram_id = _telegram_id(request)
    if telegram_id is None:
        return _error('Некорректный Telegram-пользователь')
    throttle_key = f'certificate-check:{telegram_id}'
    cache.add(throttle_key, 0, 1800)
    try:
        attempts = cache.incr(throttle_key)
    except ValueError:
        cache.set(throttle_key, 1, 1800)
        attempts = 1
    if attempts > 5:
        return _error('Слишком много попыток. Повторите через 30 минут.', 429)
    code = normalize_certificate_code(request.bot_data.get('code'))
    certificate = GiftCertificate.objects.filter(code=code).first() if code else None
    if certificate is None:
        return _error('Сертификат с таким кодом не найден', 404)
    problem = certificate.problem()
    if problem:
        return _error(problem, 409)
    cache.delete(throttle_key)
    return JsonResponse({'ok': True, 'certificate': _certificate_data(certificate)})


@bot_view
def certificate_list(request):
    telegram_id = _telegram_id(request)
    certificates = GiftCertificate.objects.filter(buyer_telegram_id=telegram_id)[:20]
    return JsonResponse({'ok': True, 'certificates': [_certificate_data(certificate) for certificate in certificates]})


@bot_view
def lead_create(request):
    telegram_id = _telegram_id(request)
    name, phone = _text(request.bot_data, 'name', 100), _text(request.bot_data, 'phone', 30)
    try:
        phone = clean_phone_value(phone)
    except ValidationError:
        return _error('Проверьте телефон')
    message = _text(request.bot_data, 'message', 1000)
    if telegram_id is None or not name or not phone or not message or request.bot_data.get('consent_pd') is not True:
        return _error('Для обращения нужны имя, телефон, сообщение и согласие')
    lead = Lead.objects.create(kind=Lead.Kind.QUESTION, name=name, phone=phone, message=message, source='telegram')
    record_acceptance(request, 'personal', reference=f'lead:{lead.pk}', contact=lead.phone)
    transaction.on_commit(lambda: notifications.dispatch_lead(lead.pk))
    return JsonResponse({'ok': True, 'lead': lead.pk}, status=201)


@bot_view
def review_create(request):
    telegram_id = _telegram_id(request)
    name, text = _text(request.bot_data, 'name', 60), _text(request.bot_data, 'text', 600)
    rating = _int(request.bot_data.get('rating'))
    order_id = _int(request.bot_data.get('order'))
    if order_id and not Order.objects.filter(pk=order_id, telegram_user_id=telegram_id, status=Order.Status.DONE).exists():
        return _error('Отзыв можно оставить только после выполненного заказа', 409)
    if telegram_id is None or not name or not text or not 1 <= rating <= 5:
        return _error('Проверьте имя, текст и оценку')
    Review.objects.create(name=name, text=text, rating=rating, source=Review.Source.SITE,
                          permission_given=False, is_published=False)
    return JsonResponse({'ok': True, 'message': 'Спасибо! Отзыв появится после проверки.'}, status=201)


@bot_view
def review_list(request):
    reviews = Review.objects.filter(is_published=True, permission_given=True).exclude(source=Review.Source.YANDEX, source_url='')[:20]
    return JsonResponse({'ok': True, 'reviews': [
        {'name': review.name, 'text': review.text, 'rating': review.rating,
         'source': review.get_source_display(), 'url': review.source_url} for review in reviews]})


@bot_view
def staff_orders(request):
    if _telegram_id(request, admin=True) is None:
        return _error('Недостаточно прав', 403)
    date_value = _text(request.bot_data, 'date', 10)
    orders = Order.objects.filter(kind=Order.Kind.PRODUCTS).select_related('shop').prefetch_related('items', 'addons')
    if date_value:
        orders = orders.filter(date=date_value)
    else:
        orders = orders.exclude(status__in=[Order.Status.DONE, Order.Status.CANCELED])
    return JsonResponse({'ok': True, 'orders': [_order_data(request, order) for order in orders[:50]]})


@bot_view
@idempotent('staff.status')
def staff_status(request):
    if _telegram_id(request, admin=True) is None:
        return _error('Недостаточно прав', 403)
    order = Order.objects.filter(pk=_int(request.bot_data.get('order'))).first()
    status = _text(request.bot_data, 'status', 12)
    if order is None or status not in Order.Status.values:
        return _error('Заказ или статус не найден', 404)
    order.set_status(status)
    return JsonResponse({'ok': True, 'order': _order_data(request, order)})


@bot_view
@idempotent('staff.paid')
def staff_paid(request):
    if _telegram_id(request, admin=True) is None:
        return _error('Недостаточно прав', 403)
    order = Order.objects.filter(pk=_int(request.bot_data.get('order'))).first()
    if order is None:
        return _error('Заказ не найден', 404)
    order.mark_paid()
    return JsonResponse({'ok': True, 'order': _order_data(request, order)})


@bot_view
@idempotent('staff.stock')
def staff_stock(request):
    if _telegram_id(request, admin=True) is None:
        return _error('Недостаточно прав', 403)
    product = Product.objects.filter(pk=_int(request.bot_data.get('product'))).first()
    if product is None:
        return _error('Букет не найден', 404)
    product.in_stock = bool(request.bot_data.get('in_stock'))
    product.save(update_fields=['in_stock', 'updated'])
    return JsonResponse({'ok': True, 'product': _product_data(request, product)})
