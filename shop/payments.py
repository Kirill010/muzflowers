"""Онлайн-оплата: Т-Касса (Т-Банк) и ЮKassa. Пока ключи не вписаны в .env (PAYMENT_PROVIDER=none),
сайт принимает предоплату переводом или оплату при получении — см. «Настройки сайта» в панели.

Форматы запросов сверены с официальной документацией:
  Т-Касса:  https://developer.tbank.ru/eacq/  (Init, GetState, подпись Token, уведомления — ответ «OK»)
  ЮKassa:   https://yookassa.ru/developers/  (POST /v3/payments, Idempotence-Key, уведомления — ответ 200)
Перед запуском проверьте оплату тестовым платежом из личного кабинета банка."""
import hashlib
import json
import logging
import urllib.error
import urllib.request
import uuid

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Order

log = logging.getLogger('shop')

TBANK_URL = 'https://securepay.tinkoff.ru/v2/'
YOOKASSA_URL = 'https://api.yookassa.ru/v3/'
YOOKASSA_TAX_SYSTEM = {'osn': 1, 'usn_income': 2, 'usn_income_outcome': 3, 'esn': 5, 'patent': 6}
YOOKASSA_VAT = {'none': 1, 'vat0': 2, 'vat10': 3, 'vat20': 4}


class PaymentError(Exception):
    """Понятная причина, почему оплату не удалось открыть."""


def provider():
    return settings.PAYMENT_PROVIDER if settings.PAYMENT_PROVIDER in ('tbank', 'yookassa') else 'none'


def is_configured():
    p = provider()
    if p == 'tbank':
        return bool(settings.PAYMENT_TBANK_TERMINAL and settings.PAYMENT_TBANK_PASSWORD)
    if p == 'yookassa':
        return bool(settings.PAYMENT_YOOKASSA_SHOP_ID and settings.PAYMENT_YOOKASSA_SECRET)
    return False


def _http(url, payload=None, headers=None, auth=None, timeout=15):
    """Один запрос к банку. Возвращает разобранный JSON; любая беда превращается в PaymentError."""
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    request = urllib.request.Request(url, data=data, method='POST' if payload is not None else 'GET')
    request.add_header('Content-Type', 'application/json')
    request.add_header('User-Agent', 'MuzFlowers-site/1.0')
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if auth:
        import base64
        request.add_header('Authorization', 'Basic ' + base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — адреса банков зашиты выше
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')[:500]
        log.error('Банк ответил ошибкой %s: %s', exc.code, body)
        raise PaymentError('банк не принял запрос.') from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log.error('Банк недоступен: %s', exc)
        raise PaymentError('банк сейчас не отвечает.') from exc


# ───────────── чек (54-ФЗ): цены в чеке должны складываться ровно в сумму платежа ─────────────

def receipt_lines(order):
    """[(название, количество, цена за штуку в копейках, сумма в копейках)]. Скидка раскладывается по букетам."""
    if order.kind == Order.Kind.CERTIFICATE:
        return [('Подарочный сертификат', 1, order.total * 100, order.total * 100)]
    items = list(order.items.all())
    gross = sum(i.line_total for i in items) or 1
    amounts, left = [], order.discount
    for index, item in enumerate(items):
        share = left if index == len(items) - 1 else round(order.discount * item.line_total / gross)
        share = min(share, left, item.line_total)
        left -= share
        amounts.append((item.line_total - share) * 100)
    lines = []
    for item, amount in zip(items, amounts):
        if item.qty > 0 and amount % item.qty == 0:
            lines.append((item.full_name[:128], item.qty, amount // item.qty, amount))
        else:  # не делится поровну — показываем одной строкой
            lines.append((f'{item.full_name} × {item.qty}'[:128], 1, amount, amount))
    for addon in order.addons.all():
        if addon.price:
            lines.append((addon.name[:128], 1, addon.price * 100, addon.price * 100))
    if order.delivery_cost:
        lines.append(('Доставка', 1, order.delivery_cost * 100, order.delivery_cost * 100))
    return lines


# ───────────── Т-Касса ─────────────

def _tbank_token(params):
    flat = {k: v for k, v in params.items() if k != 'Token' and not isinstance(v, (dict, list))}
    flat['Password'] = settings.PAYMENT_TBANK_PASSWORD
    joined = ''.join(('true' if v is True else 'false' if v is False else str(v)) for _, v in sorted(flat.items()))
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()


def _tbank_call(method, params):
    params = {'TerminalKey': settings.PAYMENT_TBANK_TERMINAL, **params}
    params['Token'] = _tbank_token(params)
    return _http(TBANK_URL + method, params)


def _tbank_start(order, return_url):
    attempt = f'{order.pk}-{uuid.uuid4().hex[:8]}'  # номер операции в банке должен быть уникальным при каждой попытке
    params = {
        'Amount': order.total * 100, 'OrderId': attempt, 'Description': f'Заказ №{order.pk}'[:140],
        'SuccessURL': return_url, 'FailURL': return_url, 'Language': 'ru',
        'NotificationURL': settings.SITE_URL + reverse('shop:payment_webhook', args=['tbank']) if settings.SITE_URL else '',
    }
    params = {k: v for k, v in params.items() if v != ''}
    body = dict(params)
    if _receipt_enabled():
        contact = {'Email': order.email} if order.email else {'Phone': order.phone}
        body['Receipt'] = {**contact, 'Taxation': settings.PAYMENT_TAXATION, 'Items': [
            {'Name': name, 'Price': price, 'Quantity': qty, 'Amount': amount, 'Tax': settings.PAYMENT_VAT,
             'PaymentMethod': 'advance' if order.kind == Order.Kind.CERTIFICATE else 'full_prepayment',
             'PaymentObject': 'commodity'}
            for name, qty, price, amount in receipt_lines(order)]}
    result = _tbank_call('Init', body)
    if not result.get('Success') or not result.get('PaymentURL'):
        log.error('Т-Касса отказала в оплате заказа №%s: %s', order.pk, result)
        raise PaymentError('банк отказал в создании платежа.')
    return str(result['PaymentId']), result['PaymentURL']


def _tbank_state(order):
    result = _tbank_call('GetState', {'PaymentId': order.pay_external_id})
    return result.get('Status') in ('CONFIRMED',)


def _tbank_webhook(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except ValueError as exc:
        raise PaymentError('не json') from exc
    expected = _tbank_token({k: v for k, v in payload.items() if k not in ('Data', 'Receipt')})
    if payload.get('Token') != expected:
        raise PaymentError('подпись не совпала')
    if payload.get('Status') != 'CONFIRMED' or not payload.get('Success'):
        return None
    order = Order.objects.filter(pk=str(payload.get('OrderId', '')).split('-')[0] or 0).first()
    if order is None or int(payload.get('Amount', -1)) != order.total * 100:
        log.error('Т-Касса: платёж не совпал с заказом: %s', payload.get('OrderId'))
        return None
    return order


# ───────────── ЮKassa ─────────────

def _yookassa_auth():
    return settings.PAYMENT_YOOKASSA_SHOP_ID, settings.PAYMENT_YOOKASSA_SECRET


def _rub(kopecks):
    return f'{kopecks / 100:.2f}'


def _yookassa_start(order, return_url):
    body = {
        'amount': {'value': _rub(order.total * 100), 'currency': 'RUB'}, 'capture': True,
        'confirmation': {'type': 'redirect', 'return_url': return_url},
        'description': f'Заказ №{order.pk}'[:128], 'metadata': {'order_id': str(order.pk)},
    }
    if _receipt_enabled():
        vat = YOOKASSA_VAT.get(settings.PAYMENT_VAT)
        system = YOOKASSA_TAX_SYSTEM.get(settings.PAYMENT_TAXATION)
        if vat is None or system is None:
            raise PaymentError('в настройках чека указан неподдерживаемый налог.')
        contact = {'email': order.email} if order.email else {'phone': order.phone.lstrip('+')}
        body['receipt'] = {'customer': contact, 'tax_system_code': system, 'items': [
            {'description': name, 'quantity': f'{qty:.2f}', 'amount': {'value': _rub(price), 'currency': 'RUB'},
             'vat_code': vat, 'payment_mode': 'advance' if order.kind == Order.Kind.CERTIFICATE else 'full_prepayment',
             'payment_subject': 'payment' if order.kind == Order.Kind.CERTIFICATE else 'commodity'}
            for name, qty, price, amount in receipt_lines(order)]}
    result = _http(YOOKASSA_URL + 'payments', body, headers={'Idempotence-Key': uuid.uuid4().hex}, auth=_yookassa_auth())
    url = (result.get('confirmation') or {}).get('confirmation_url')
    if not result.get('id') or not url:
        log.error('ЮKassa не создала платёж для заказа №%s: %s', order.pk, result)
        raise PaymentError('банк отказал в создании платежа.')
    return result['id'], url


def _yookassa_paid(payment_id, order=None):
    """Спрашиваем у ЮKassa, оплачен ли платёж (данным из уведомления не доверяем)."""
    result = _http(YOOKASSA_URL + f'payments/{payment_id}', auth=_yookassa_auth())
    if result.get('status') != 'succeeded' or not result.get('paid'):
        return None
    if order is None:
        order = Order.objects.filter(pk=(result.get('metadata') or {}).get('order_id') or 0).first()
    if order is None or order.pay_external_id != result.get('id') or round(float(result['amount']['value']) * 100) != order.total * 100:
        log.error('ЮKassa: платёж %s не совпал с заказом', payment_id)
        return None
    return order


def _yookassa_webhook(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        payment_id = payload['object']['id']
    except (ValueError, KeyError, TypeError) as exc:
        raise PaymentError('неверный формат') from exc
    if payload.get('event') != 'payment.succeeded':
        return None
    return _yookassa_paid(payment_id)


# ───────────── общее ─────────────

def _receipt_enabled():
    return settings.PAYMENT_RECEIPT


def start_payment(order, return_url):
    """Возвращает ссылку на оплату. Если ссылка уже создана и платёж ещё ждёт — отдаёт её же (двойной клик не создаст два платежа)."""
    if not is_configured():
        raise PaymentError('онлайн-оплата не подключена.')
    if order.pay_url and order.pay_provider == provider() and order.payment_status == Order.PayStatus.PENDING:
        return order.pay_url
    external_id, url = (_tbank_start if provider() == 'tbank' else _yookassa_start)(order, return_url)
    order.pay_provider, order.pay_external_id, order.pay_url = provider(), external_id, url
    order.payment_status = Order.PayStatus.PENDING
    order.save(update_fields=['pay_provider', 'pay_external_id', 'pay_url', 'payment_status', 'updated'])
    return url


def handle_webhook(request):
    """Разбирает уведомление банка. Возвращает заказ, если он только что оплачен, иначе None."""
    order = (_tbank_webhook if provider() == 'tbank' else _yookassa_webhook)(request)
    if order is not None and not order.is_paid:
        order.mark_paid()
        return order
    return None


def refresh(order):
    """Спрашивает у банка, оплачен ли заказ (вызывается, когда клиент вернулся на страницу заказа). True — только что оплачен."""
    if not is_configured() or order.is_paid or order.payment_status != Order.PayStatus.PENDING or not order.pay_external_id \
            or order.pay_provider != provider():
        return False
    try:
        paid = _tbank_state(order) if provider() == 'tbank' else bool(_yookassa_paid(order.pay_external_id, order))
    except PaymentError:
        return False
    if paid:
        order.mark_paid()
    return paid
