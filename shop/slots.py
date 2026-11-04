"""Когда можно получить заказ: часы работы, запас времени на сборку, праздники и лимит заказов на день."""
from datetime import datetime, timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Order, SiteSettings, SpecialDay

PICKUP_STEP = timedelta(minutes=30)
ASAP = 'asap'


def now_local():
    return timezone.localtime()


def _aware(naive):
    return timezone.make_aware(naive)


def orders_count(day):
    return Order.objects.filter(date=day).exclude(status=Order.Status.CANCELED).count()


def day_limit(day, site, special=None):
    """Сколько заказов принимаем на этот день (0 — без ограничения)."""
    if special is None:
        special = SpecialDay.objects.filter(date=day).first()
    if special is not None and special.limit is not None:
        return special.limit
    return site.daily_order_limit


def time_options(day, method, site=None, now=None):
    """Варианты времени на выбранный день: [{'value', 'label', 'time_from', 'time_to', 'asap'}]."""
    site = site or SiteSettings.load()
    now = now or now_local()
    today = now.date()
    open_dt = datetime.combine(day, site.open_time)
    close_dt = datetime.combine(day, site.close_time)
    options = []

    if method == Order.Method.DELIVERY:
        earliest = now + timedelta(minutes=site.delivery_lead_minutes) if day == today else None
        window = timedelta(hours=site.delivery_window_hours)
        start = open_dt
        while start < close_dt:
            end = min(start + window, close_dt)
            if end - start >= timedelta(hours=1) and (earliest is None or _aware(start) >= earliest):
                options.append({
                    'value': f'{start:%H:%M}-{end:%H:%M}', 'label': f'{start:%H:%M}–{end:%H:%M}',
                    'time_from': start.time(), 'time_to': end.time(), 'asap': False,
                })
            start += window
        return options

    earliest = now + timedelta(minutes=site.pickup_lead_minutes) if day == today else None
    if day == today and site.open_time <= now.time() and earliest.time() <= site.close_time and earliest.date() == today:
        options.append({'value': ASAP, 'label': f'Как можно скорее (≈ через {site.pickup_lead_minutes} мин)',
                        'time_from': None, 'time_to': None, 'asap': True})
    t = open_dt
    while t <= close_dt - PICKUP_STEP:
        if earliest is None or _aware(t) >= earliest:
            options.append({'value': f'{t:%H:%M}', 'label': f'К {t:%H:%M}', 'time_from': t.time(), 'time_to': None, 'asap': False})
        t += PICKUP_STEP
    return options


def day_problem(day, method=Order.Method.PICKUP, site=None, now=None):
    """Текст, почему на эту дату заказать нельзя. Пустая строка — можно."""
    site = site or SiteSettings.load()
    now = now or now_local()
    today = now.date()
    if day < today:
        return 'Эта дата уже прошла'
    if day > today + timedelta(days=site.max_days_ahead):
        return f'Заказать можно не дальше чем на {site.max_days_ahead} дн. вперёд'
    special = SpecialDay.objects.filter(date=day).first()
    if special is not None and special.is_closed:
        return special.note or 'На эту дату заказы не принимаем'
    limit = day_limit(day, site, special)
    if limit and orders_count(day) >= limit:
        return 'На эту дату все заказы уже разобраны — выберите другой день'
    if not time_options(day, method, site, now):
        return 'На сегодня уже не успеваем — выберите другой день' if day == today else 'На эту дату нет свободного времени'
    return ''


def pick_option(day, method, value, site=None, now=None):
    """Находит вариант времени по значению из формы. None — такого варианта нет (или время уже прошло)."""
    return next((o for o in time_options(day, method, site, now) if o['value'] == value), None)


def unavailable_dates(site=None, now=None):
    """{'2026-11-08': 'причина'} — закрытые и полностью занятые дни на ближайшие месяцы (для календаря на странице)."""
    site = site or SiteSettings.load()
    now = now or now_local()
    today = now.date()
    last = today + timedelta(days=site.max_days_ahead)
    specials = {s.date: s for s in SpecialDay.objects.filter(date__range=(today, last))}
    counts = {row['date']: row['n'] for row in
              Order.objects.filter(date__range=(today, last)).exclude(status=Order.Status.CANCELED)
              .values('date').annotate(n=Count('id'))}
    result = {}
    day = today
    while day <= last:
        special = specials.get(day)
        if special is not None and special.is_closed:
            result[day.isoformat()] = special.note or 'Заказы на эту дату не принимаем'
        else:
            limit = day_limit(day, site, special)
            if limit and counts.get(day, 0) >= limit:
                result[day.isoformat()] = 'Все заказы на эту дату разобраны'
        day += timedelta(days=1)
    return result
