from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Order


def _send_order_email(order_id):
    """Синхронная отправка письма."""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return f"Заказ {order_id} не найден."

    subject = f'Muzflowers: Ваш заказ №{order.id} оформлен!'
    context = {
        'order': order,
        'items': order.items.all(),
        'total': order.get_total_cost(),
    }
    html_message = render_to_string('emails/order_confirmation.html', context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        html_message=html_message,
        fail_silently=False,
    )
    return f"Письмо для заказа {order.id} отправлено."


@shared_task
def send_order_confirmation_email(order_id):
    """Celery-задача для отправки письма."""
    return _send_order_email(order_id)


def send_order_email_safe(order_id):
    """
    Безопасная отправка: пробуем через Celery,
    при ошибке (Redis/Celery не запущен) — отправляем синхронно.
    """
    try:
        send_order_confirmation_email.delay(order_id)
    except Exception:
        # Celery/Redis недоступен — отправляем сразу
        _send_order_email(order_id)