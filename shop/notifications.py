"""Уведомления: Telegram, письмо сотрудникам, письмо клиенту, webhook.
Всё необязательно и «тихое»: если что-то не отправилось, заказ от этого не страдает — ошибка попадает в журнал."""
import json
import logging
import threading
import urllib.request
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import connection
from django.template.loader import render_to_string

from .models import Lead, Order, SiteSettings
from .utils import rub

log = logging.getLogger('shop')


def _background(name, func, *args):
    """На сайте отправляем в фоне, чтобы клиент не ждал; в тестах — сразу."""
    def target():
        try:
            func(*args)
        except Exception:
            log.exception('Уведомление «%s» не отправлено', name)
        finally:
            if settings.NOTIFY_ASYNC:
                connection.close()
    if settings.NOTIFY_ASYNC:
        threading.Thread(target=target, daemon=True, name=name).start()
    else:
        target()


def _each(label, *steps):
    """Каждый способ отправки — отдельно: если Telegram недоступен, письмо всё равно уйдёт."""
    for step in steps:
        try:
            step()
        except Exception:
            log.exception('Не удалось отправить уведомление (%s)', label)


# ───────────── точки входа ─────────────

def dispatch(order_id, origin=''):
    _background(f'order-{order_id}', _order_created, order_id, origin)


def dispatch_lead(lead_id):
    _background(f'lead-{lead_id}', _lead_created, lead_id)


def dispatch_paid(order_id):
    _background(f'paid-{order_id}', _order_paid, order_id)


def _order_created(order_id, origin):
    order = Order.objects.select_related('shop').prefetch_related('items', 'addons').get(pk=order_id)
    text = staff_text(order, origin)
    _each(f'заказ №{order_id}', lambda: send_telegram(text), lambda: send_webhook(order, origin),
          lambda: _staff_mail(f'Новый заказ №{order.pk} · {order.when_display}', text),
          lambda: send_customer_email(order, origin))


def _lead_created(lead_id):
    lead = Lead.objects.get(pk=lead_id)
    e = escape
    lines = [f'📨 <b>Заявка: {e(lead.get_kind_display())}</b>',
             f'👤 {e(lead.name)}{" · " + e(lead.company) if lead.company else ""}', f'📞 {e(lead.display_phone)}']
    if lead.email:
        lines.append(f'✉️ {e(lead.email)}')
    if lead.message:
        lines.append(f'💬 {e(lead.message)}')
    if lead.source:
        lines.append(f'🔗 Откуда: {e(lead.source)}')
    text = '\n'.join(lines)
    _each(f'заявка №{lead_id}', lambda: send_telegram(text), lambda: _staff_mail(f'Заявка: {lead.get_kind_display()}', text))


def _order_paid(order_id):
    order = Order.objects.get(pk=order_id)
    text = f'💳 <b>Заказ №{order.pk} оплачен</b> · {rub(order.total)} · {escape(order.when_display)}'
    _each(f'оплата №{order_id}', lambda: send_telegram(text), lambda: _staff_mail(f'Заказ №{order.pk} оплачен', text))


# ───────────── тексты ─────────────

def order_url(order, origin=''):
    base = (settings.SITE_URL or origin or '').rstrip('/')
    return f'{base}{order.get_absolute_url()}' if base else ''


def staff_text(order, origin=''):
    """Текст для сотрудников (Telegram, HTML-разметка; всё, что ввёл клиент, экранируется)."""
    e = escape
    lines = [f'🌸 <b>Новый заказ №{order.pk}</b> · {e(order.get_receive_method_display())}',
             f'🕒 {e(order.when_display)}', f'👤 {e(order.name)}, {e(order.display_phone)}', f'📍 {e(order.place_display)}']
    if order.receive_method == Order.Method.DELIVERY:
        if order.recipient_name:
            lines.append(f'🎁 Получит: {e(order.recipient_name)}, {e(order.display_recipient_phone)}')
        if order.surprise:
            lines.append('🤫 Сюрприз: получателю не звонить, не говорить, от кого')
    lines += ['', '💐 Состав:']
    lines += [f'• {e(i.full_name)} × {i.qty} — {rub(i.line_total)}' for i in order.items.all()]
    for addon in order.addons.all():
        note = f': {e(addon.note)}' if addon.note else ''
        lines.append(f'{"🎵" if "музык" in addon.name.lower() else "➕"} {e(addon.name)}{note}')
    if order.card_text:
        lines.append(f'💌 Открытка: «{e(order.card_text)}»')
    if order.comment:
        lines.append(f'💬 {e(order.comment)}')
    prepay = ' · <b>нужна предоплата</b>' if order.prepay_required else ''
    lines += ['', f'💳 Итого {rub(order.total)} · {e(order.get_payment_method_display())}{prepay}']
    if order.source:
        lines.append(f'🔗 Откуда: {e(order.source)}')
    if url := order_url(order, origin):
        lines.append(url)
    return '\n'.join(lines)[:4000]


# ───────────── отправка ─────────────

def _post_json(url, payload, timeout=8):
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'MuzFlowers-site/1.0'})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — адрес задаёт владелец в .env
        return response.status


def send_telegram(text):
    token = settings.TELEGRAM_BOT_TOKEN
    chats = [c.strip() for c in settings.TELEGRAM_CHAT_ID.split(',') if c.strip()]
    if not token or not chats:
        return
    for chat in chats:
        _post_json(f'https://api.telegram.org/bot{token}/sendMessage',
                   {'chat_id': chat, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})


def send_webhook(order, origin=''):
    if not settings.ORDER_WEBHOOK_URL:
        return
    _post_json(settings.ORDER_WEBHOOK_URL, {
        'event': 'order.created', 'id': order.pk, 'status': order.status, 'total': order.total,
        'name': order.name, 'phone': order.phone, 'email': order.email, 'method': order.receive_method,
        'date': order.date.isoformat(), 'time': order.time_display, 'place': order.place_display,
        'items': [{'name': i.full_name, 'qty': i.qty, 'price': i.price} for i in order.items.all()],
        'addons': [{'name': a.name, 'note': a.note, 'price': a.price} for a in order.addons.all()],
        'card_text': order.card_text, 'comment': order.comment, 'source': order.source,
        'payment': order.payment_method, 'prepay_required': order.prepay_required, 'url': order_url(order, origin),
    })


def _staff_mail(subject, html_text):
    if settings.ORDER_NOTIFY_EMAILS:
        plain = html_text.replace('<b>', '').replace('</b>', '')
        EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, settings.ORDER_NOTIFY_EMAILS).send()


def send_customer_email(order, origin=''):
    if not order.email:
        return
    site = SiteSettings.load()
    context = {'order': order, 'site': site, 'url': order_url(order, origin), 'items': order.items.all(), 'addons': order.addons.all()}
    mail = EmailMultiAlternatives(f'{site.shop_name}: заказ №{order.pk} принят', render_to_string('emails/order_customer.txt', context),
                                  settings.DEFAULT_FROM_EMAIL, [order.email])
    mail.attach_alternative(render_to_string('emails/order_customer.html', context), 'text/html')
    mail.send()
