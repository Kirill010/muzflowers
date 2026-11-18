"""Панель владельца: главная страница админки с заказами на сегодня и завтра, кнопками статусов,
списком «что осталось заполнить» и печатью бланков."""
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Sum
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe

from . import payments, qr
from .models import Lead, Order, Product, Shop, SiteSettings


def next_step(order):
    """Следующий шаг заказа: (статус, подпись на кнопке) или None, если заказ закрыт."""
    S, M = Order.Status, Order.Method
    if order.status == S.NEW:
        return S.CONFIRMED, 'Подтвердить'
    if order.status == S.CONFIRMED:
        return S.READY, 'Собран'
    if order.status == S.READY:
        return (S.DELIVERING, 'Передан курьеру') if order.receive_method == M.DELIVERY else (S.DONE, 'Выдан')
    if order.status == S.DELIVERING:
        return S.DONE, 'Доставлен'
    return None


def _orders_qs():
    return Order.objects.select_related('shop').prefetch_related('items', 'addons')


def _sorted(qs):
    return qs.order_by(F('time_from').asc(nulls_first=True), 'id')  # «как можно скорее» — первыми


def awaiting_prepayment(orders):
    return orders.filter(prepay_required=True, payment_status__in=[Order.PayStatus.UNPAID, Order.PayStatus.PENDING]) \
        .exclude(status=Order.Status.CANCELED)


class OwnerLoginForm(AdminAuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Почта или логин'


class MuzAdminSite(AdminSite):
    site_header = 'MuzFlowers — рабочая панель'
    site_title = 'MuzFlowers'
    index_title = 'Что сегодня?'
    index_template = 'admin/dashboard.html'
    login_template = 'admin/muz_login.html'
    login_form = OwnerLoginForm

    # ───────────── адреса ─────────────
    def get_urls(self):
        mine = [
            path('shop/order/<int:pk>/print/', self.admin_view(self.print_order), name='shop_order_print'),
            path('shop/order/<int:pk>/card/', self.admin_view(self.print_card), name='shop_order_card'),
            path('shop/order/print/', self.admin_view(self.print_many), name='shop_order_print_many'),
            path('shop/order/day/', self.admin_view(self.print_day), name='shop_order_day'),
            path('shop/order/<int:pk>/status/', self.admin_view(self.quick_status), name='shop_order_status'),
            path('shop/order/<int:pk>/paid/', self.admin_view(self.quick_paid), name='shop_order_paid'),
        ]
        return mine + super().get_urls()

    def login(self, request, extra_context=None):
        no_owner = not get_user_model().objects.filter(is_superuser=True).exists()
        return super().login(request, {**(extra_context or {}), 'no_owner': no_owner})

    # ───────────── главная ─────────────
    def index(self, request, extra_context=None):
        return super().index(request, {**(extra_context or {}), **self.dashboard(request)})

    def dashboard(self, request):
        site = SiteSettings.load()
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        can_change_orders = request.user.has_perm('shop.change_order')
        can_view_orders = can_change_orders or request.user.has_perm('shop.view_order')
        can_view_leads = request.user.has_perm('shop.view_lead') or request.user.has_perm('shop.change_lead')
        can_view_products = request.user.has_perm('shop.view_product') or request.user.has_perm('shop.change_product')
        can_manage_shop = request.user.has_perm('shop.change_sitesettings')
        orders = _orders_qs() if can_view_orders else Order.objects.none()
        live = orders.exclude(status=Order.Status.CANCELED)

        def board(day):
            rows = _sorted(live.filter(date=day))
            return [{'order': o, 'step': next_step(o)} for o in rows]

        month_start = today.replace(day=1)
        month = live.filter(created__date__gte=month_start).aggregate(n=Count('id'), total=Sum('total'))
        week = live.filter(created__date__gte=today - timedelta(days=6)).aggregate(n=Count('id'), total=Sum('total'))
        sources = list(live.filter(created__date__gte=month_start).values('source').annotate(n=Count('id'), total=Sum('total')).order_by('-n')[:6])
        for row in sources:
            row['label'] = row['source'] or 'Сайт напрямую'

        checklist = self.checklist(request, site) if can_manage_shop else []
        new_queue = orders.filter(status=Order.Status.NEW)
        new_orders = list(new_queue.order_by('created')[:50])
        new_elsewhere = [o for o in new_orders if o.date not in (today, tomorrow)]  # на сегодня и завтра они уже видны в карточках выше
        later = live.filter(date__gt=tomorrow, date__lte=today + timedelta(days=14)) \
            .exclude(status=Order.Status.NEW).order_by('date', F('time_from').asc(nulls_first=True), 'id')
        waiting_pay = awaiting_prepayment(orders).count()
        leads = Lead.objects.filter(status=Lead.Status.NEW) if can_view_leads else Lead.objects.none()
        return {
            'today': today, 'tomorrow': tomorrow, 'board_today': board(today), 'board_tomorrow': board(tomorrow),
            'new_orders': new_queue.count(), 'new_rows': [{'order': o, 'step': next_step(o)} for o in new_elsewhere], 'waiting_pay': waiting_pay,
            'board_later': [{'order': o, 'step': next_step(o)} for o in later],
            'new_leads': leads.count(), 'recent_leads': list(leads.order_by('created')[:4]),
            'month': month, 'week': week, 'sources': sources, 'month_name': month_start,
            'checklist': checklist, 'todo_count': sum(1 for item in checklist if not item['ok']),
            'off_products': Product.objects.filter(is_active=True, in_stock=False).count() if can_view_products else 0,
            'can_view_orders': can_view_orders, 'can_change_orders': can_change_orders,
            'can_view_leads': can_view_leads, 'can_view_products': can_view_products, 'can_manage_shop': can_manage_shop,
            'dash_site': site,
        }

    def checklist(self, request, site):
        items = []

        def add(ok, title, hint, url=''):
            items.append({'ok': bool(ok), 'title': title, 'hint': hint, 'url': url})

        settings_url = reverse('admin:shop_sitesettings_changelist')
        add(site.has_requisites, 'Реквизиты продавца', 'Имя ИП и ИНН нужны по закону: они показываются в оферте и внизу сайта.', settings_url)
        add(Shop.objects.filter(is_active=True, is_pickup=True).exclude(address='').exists(), 'Адрес точки самовывоза',
            'Впишите адрес хотя бы одной точки и включите её.', reverse('admin:shop_shop_changelist'))
        products = list(Product.objects.filter(is_active=True).prefetch_related('photos'))
        without_photo = [p for p in products if not p.cover]
        add(not without_photo, 'Фото букетов', f'У {len(without_photo)} из {len(products)} букетов нет фото — сайт рисует их сам. Загрузите настоящие фото.',
            reverse('admin:shop_product_changelist'))
        add(payments.is_configured() or site.payment_details.strip(), 'Как принимать предоплату',
            'Впишите реквизиты для перевода в настройках или подключите онлайн-оплату (файл .env). Без этого предоплату согласуют по телефону.', settings_url)
        add(settings.ORDER_NOTIFY_EMAILS or (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID), 'Уведомления о новых заказах',
            'Подключите Telegram или почту в файле .env — тогда новые заказы будут приходить сами.')
        add(site.email, 'Почта магазина', 'Нужна для писем клиентам и для связи.', settings_url)
        if settings.DEBUG and request.get_host().split(':')[0] not in ('localhost', '127.0.0.1', '[::1]'):
            add(False, 'Режим разработки включён', 'На сайте в интернете выключите его: DJANGO_DEBUG=0 в файле .env.')
        return items

    # ───────────── кнопки на главной ─────────────
    def _back(self, request):
        target = request.POST.get('next', '')
        return target if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}) else reverse('admin:index')

    def quick_status(self, request, pk):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not request.user.has_perm('shop.change_order'):
            raise PermissionDenied
        order = get_object_or_404(Order, pk=pk)
        status = request.POST.get('to')
        if status not in Order.Status.values:
            raise Http404
        order.set_status(status)
        messages.success(request, f'Заказ №{order.pk}: {order.get_status_display().lower()}')
        return redirect(self._back(request))

    def quick_paid(self, request, pk):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not request.user.has_perm('shop.change_order'):
            raise PermissionDenied
        order = get_object_or_404(Order, pk=pk)
        order.mark_paid()
        messages.success(request, f'Заказ №{order.pk}: оплата отмечена')
        return redirect(self._back(request))

    # ───────────── печать ─────────────
    def _can_print(self, request):
        if not (request.user.has_perm('shop.view_order') or request.user.has_perm('shop.change_order')):
            raise PermissionDenied

    def print_order(self, request, pk):
        self._can_print(request)
        return render(request, 'admin/print/order_slip.html', {'orders': [get_object_or_404(_orders_qs(), pk=pk)], 'site': SiteSettings.load()})

    def print_many(self, request):
        """Бланки выбранных заказов (?ids=1,2,3) или всех заказов на день (?date=2026-11-05; по умолчанию — завтра)."""
        self._can_print(request)
        ids = [int(x) for x in request.GET.get('ids', '').split(',') if x.isdigit()]
        if ids:
            orders = list(_sorted(_orders_qs().filter(pk__in=ids)))
        else:
            day = self._day(request)
            orders = list(_sorted(_orders_qs().filter(date=day).exclude(status=Order.Status.CANCELED)))
        return render(request, 'admin/print/order_slip.html', {'orders': orders, 'site': SiteSettings.load()})

    def print_day(self, request):
        """Список заказов на день одной таблицей — как страница в тетради предзаказов."""
        self._can_print(request)
        day = self._day(request)
        orders = list(_sorted(_orders_qs().filter(date=day).exclude(status=Order.Status.CANCELED)))
        return render(request, 'admin/print/day.html', {'orders': orders, 'day': day, 'site': SiteSettings.load(),
                                                        'total': sum(o.total for o in orders)})

    def print_card(self, request, pk):
        """Открытка к букету: текст клиента и QR-код песни."""
        self._can_print(request)
        order = get_object_or_404(_orders_qs(), pk=pk)
        song = next((a for a in order.addons.all() if (a.addon and a.addon.is_music) or 'музык' in a.name.lower()), None)
        link = qr.song_link(song.note) if song else ''
        svg = qr.qr_svg(link)
        return render(request, 'admin/print/card.html', {
            'order': order, 'song': song, 'link': link, 'qr': mark_safe(svg) if svg else '', 'site': SiteSettings.load()})

    @staticmethod
    def _day(request):
        try:
            return date.fromisoformat(request.GET.get('date', ''))
        except ValueError:
            return timezone.localdate() + timedelta(days=1)
