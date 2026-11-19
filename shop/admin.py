import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from . import bouquet
from .admin_site import awaiting_prepayment
from .models import (FAQ, Addon, BotOperation, Category, GiftCertificate, GiftCertificateLedger, Lead, LegalAcceptance, Order, OrderAddon,
                     OrderItem, Product, ProductImage, PromoCode, Review, Shop, SiteSettings, SpecialDay, Variant)
from .utils import rub

STATUS_COLORS = {
    Order.Status.NEW: '#d6336c', Order.Status.CONFIRMED: '#e08a00', Order.Status.READY: '#2f7fb0',
    Order.Status.DELIVERING: '#7a5cc7', Order.Status.DONE: '#3f8f46', Order.Status.CANCELED: '#8a8a8a',
}
PAY_COLORS = {
    Order.PayStatus.UNPAID: '#8a8a8a', Order.PayStatus.PENDING: '#e08a00',
    Order.PayStatus.PAID: '#3f8f46', Order.PayStatus.REFUNDED: '#d6336c',
}


def chip(text, color):
    return format_html('<span style="display:inline-block;padding:2px 10px;border-radius:99px;color:#fff;font-weight:600;'
                       'font-size:12px;background:{}">{}</span>', color, text)


def product_image_url(product, size=96):
    cover = product.cover
    if cover:
        from .thumbs import thumb_url
        return thumb_url(cover, size * 2)
    return product.art_url


# ───────────────────────────── каталог ─────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    fields = ('name', 'description', 'order', 'is_active')


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    verbose_name = 'Размер / вариант'
    verbose_name_plural = 'Размеры (если у букета бывает несколько размеров с разной ценой — иначе оставьте пусто)'


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    verbose_name_plural = 'Ещё фото (спереди, сбоку, в руке)'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'name', 'category', 'price', 'in_stock', 'is_active', 'popularity')
    list_display_links = ('thumb', 'name')
    list_editable = ('price', 'in_stock', 'is_active', 'popularity')
    list_filter = ('category', 'is_active', 'in_stock', 'is_ready')
    search_fields = ('name', 'tagline', 'description')
    inlines = [VariantInline, ProductImageInline]
    save_on_top = True
    actions = ['set_in_stock', 'set_out_of_stock', 'show', 'hide', 'duplicate']
    fieldsets = (
        (None, {'fields': ('name', 'category', 'price', 'old_price', 'tagline', 'description', 'occasion')}),
        ('Фото', {'fields': ('image', 'badge'), 'description': 'Загрузите фото букета. Пока фото нет — сайт нарисует букет сам.'}),
        ('Наличие и показ', {'fields': ('is_active', 'in_stock', 'is_ready', ('season_from', 'season_to'), 'popularity')}),
        ('Рисунок (пока нет фото)', {'classes': ('collapse',), 'fields': ('art_kind', 'art_count', 'color_a', 'color_b')}),
    )

    @admin.display(description='')
    def thumb(self, obj):
        return format_html('<img src="{}" alt="" style="width:48px;height:60px;object-fit:cover;border-radius:10px;background:#f3ece4">',
                           product_image_url(obj, 48))

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category').prefetch_related('photos')

    @admin.action(description='Есть сегодня (можно заказать)')
    def set_in_stock(self, request, queryset):
        self.message_user(request, f'Отмечено «есть»: {queryset.update(in_stock=True)}')

    @admin.action(description='Нет сегодня (временно нельзя заказать)')
    def set_out_of_stock(self, request, queryset):
        self.message_user(request, f'Отмечено «нет»: {queryset.update(in_stock=False)}')

    @admin.action(description='Показать на сайте')
    def show(self, request, queryset):
        self.message_user(request, f'Показано: {queryset.update(is_active=True)}')

    @admin.action(description='Скрыть с сайта')
    def hide(self, request, queryset):
        self.message_user(request, f'Скрыто: {queryset.update(is_active=False)}')

    @admin.action(description='Сделать копию (удобно для похожих букетов)')
    def duplicate(self, request, queryset):
        for product in queryset.prefetch_related('variants'):
            variants = list(product.variants.all())
            product.pk, product.slug, product.name, product.is_active = None, '', f'{product.name} (копия)', False
            product.save()
            for variant in variants:
                variant.pk, variant.product = None, product
                variant.save()
        self.message_user(request, 'Копии созданы и скрыты — откройте, поправьте и включите «Показывать на сайте».')


@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_music', 'is_active', 'order')
    list_editable = ('price', 'is_active', 'order')


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'value_display', 'valid_until', 'used_count', 'usage_limit', 'is_active', 'note')
    list_editable = ('is_active',)
    readonly_fields = ('used_count',)

    @admin.display(description='Скидка')
    def value_display(self, obj):
        return f'{obj.value}%' if obj.kind == PromoCode.Kind.PERCENT else rub(obj.value)


class CertificateLedgerInline(admin.TabularInline):
    model = GiftCertificateLedger
    extra = 0
    can_delete = False
    readonly_fields = ('order', 'delta', 'note', 'created')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GiftCertificate)
class GiftCertificateAdmin(admin.ModelAdmin):
    list_display = ('code', 'amount', 'balance', 'status', 'expires_at', 'buyer_telegram_id', 'purchase_order', 'created')
    list_filter = ('status', 'expires_at')
    search_fields = ('code', 'buyer_telegram_id', 'purchase_order__id')
    readonly_fields = ('code', 'created', 'updated')
    inlines = [CertificateLedgerInline]


@admin.register(BotOperation)
class BotOperationAdmin(admin.ModelAdmin):
    list_display = ('action', 'key', 'telegram_user_id', 'status_code', 'created')
    list_filter = ('action', 'status_code')
    readonly_fields = ('action', 'key', 'telegram_user_id', 'response', 'status_code', 'created')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SpecialDay)
class SpecialDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'is_closed', 'limit', 'note')
    list_filter = ('is_closed',)


# ───────────────────────────── точки, тексты, заявки ─────────────────────────────

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'is_pickup', 'is_active', 'order')
    list_editable = ('is_pickup', 'is_active', 'order')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_text', 'rating', 'source', 'permission_given', 'is_published', 'created')
    list_editable = ('is_published',)
    list_filter = ('source', 'permission_given', 'is_published')

    @admin.display(description='Отзыв')
    def short_text(self, obj):
        return obj.text[:80]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('created', 'kind', 'name', 'company', 'display_phone', 'status_chip', 'source')
    list_filter = ('status', 'kind')
    list_display_links = ('created', 'name')
    search_fields = ('name', 'company', 'phone', 'email', 'message')
    readonly_fields = ('kind', 'name', 'company', 'phone', 'email', 'message', 'source', 'created')
    fields = ('status', 'staff_note', 'kind', 'name', 'company', 'phone', 'email', 'message', 'source', 'created')
    actions = ['mark_work', 'mark_done']

    class Media:
        css = {'all': ('shop/css/builder.css',)}

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.layout:
            return (*self.readonly_fields, 'bouquet_preview')
        return self.readonly_fields

    def get_fields(self, request, obj=None):
        if obj and obj.layout:
            return (*self.fields, 'bouquet_preview')
        return self.fields

    @admin.display(description='Эскиз композиции')
    def bouquet_preview(self, obj):
        return mark_safe(render_to_string('shop/_bouquet_preview.html', {
            'builder_config': bouquet.builder_config(), 'layout': obj.layout,
        }))

    @admin.display(description='Телефон')
    def display_phone(self, obj):
        return format_html('<a class="mz-dial" href="tel:{}">{}</a>', obj.phone, obj.display_phone)

    @admin.display(description='Статус')
    def status_chip(self, obj):
        colors = {Lead.Status.NEW: '#d6336c', Lead.Status.WORK: '#e08a00', Lead.Status.DONE: '#3f8f46'}
        return chip(obj.get_status_display(), colors[obj.status])

    @admin.action(description='Взять в работу')
    def mark_work(self, request, queryset):
        self.message_user(request, f'В работе: {queryset.update(status=Lead.Status.WORK)}')

    @admin.action(description='Закрыть заявку')
    def mark_done(self, request, queryset):
        self.message_user(request, f'Закрыто: {queryset.update(status=Lead.Status.DONE)}')


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Контакты', {'fields': ('shop_name', 'phone', 'email', 'telegram', 'max_url', 'yandex_maps_url', ('yandex_rating', 'yandex_votes'))}),
        ('Часы работы', {'fields': (('open_time', 'close_time'), 'hours_text')}),
        ('Принимаем ли заказы', {'fields': ('orders_paused', 'pause_message', 'announcement')}),
        ('Доставка', {'fields': ('delivery_enabled', 'delivery_cost', 'free_delivery_from', 'min_order', 'delivery_area_text',
                                 'delivery_lead_minutes', 'delivery_window_hours')}),
        ('Самовывоз и даты', {'fields': ('pickup_lead_minutes', 'pickup_discount_percent', 'max_days_ahead', 'daily_order_limit')}),
        ('Оплата', {'fields': ('prepay_future_orders', 'allow_pay_on_receipt', 'payment_details')}),
        ('Реквизиты продавца', {'fields': ('legal_name', 'inn', 'ogrnip', 'registration_authority', 'legal_address')}),
        ('Статистика', {'fields': ('metrika_id',)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):  # настройки одни — сразу открываем форму
        return redirect(reverse('admin:shop_sitesettings_change', args=[SiteSettings.load().pk]))


# ───────────────────────────── заказы ─────────────────────────────

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('name', 'variant_name', 'price', 'qty')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class OrderAddonInline(OrderItemInline):
    model = OrderAddon
    fields = ('name', 'price', 'note')


class DayFilter(admin.SimpleListFilter):
    title = 'дата получения'
    parameter_name = 'day'

    def lookups(self, request, model_admin):
        return [('today', 'Сегодня'), ('tomorrow', 'Завтра'), ('week', 'Ближайшие 7 дней'), ('past', 'Прошедшие')]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        return {
            'today': queryset.filter(date=today),
            'tomorrow': queryset.filter(date=today + timedelta(days=1)),
            'week': queryset.filter(date__range=(today, today + timedelta(days=7))),
            'past': queryset.filter(date__lt=today),
        }.get(self.value(), queryset)


class PrepaymentFilter(admin.SimpleListFilter):
    title = 'Предоплата'
    parameter_name = 'prepay'

    def lookups(self, request, model_admin):
        return [('waiting', 'Ждут предоплату')]

    def queryset(self, request, queryset):
        if self.value() == 'waiting':
            return awaiting_prepayment(queryset)
        return queryset


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'when', 'customer', 'place', 'total_rub', 'status_chip', 'pay_chip', 'source', 'created')
    list_display_links = ('order_no', 'customer')
    list_filter = (DayFilter, 'status', 'receive_method', PrepaymentFilter, 'payment_status', 'source')
    search_fields = ('id', 'name', 'phone', 'email', 'address', 'recipient_name')
    inlines = [OrderItemInline, OrderAddonInline]
    save_on_top = True
    list_per_page = 40
    actions = ['mark_confirmed', 'mark_ready', 'mark_delivering', 'mark_done', 'mark_paid', 'mark_canceled', 'print_selected', 'export_csv']
    readonly_fields = ('print_links', 'kind', 'user', 'telegram_user_id', 'receive_method', 'shop', 'promo_code', 'subtotal', 'discount', 'addons_total',
                       'delivery_cost', 'total', 'certificate', 'certificate_amount', 'prepay_required', 'paid_at', 'source',
                       'marketing_consent', 'created', 'updated')
    fieldsets = (
        ('Заказ', {'fields': ('print_links', 'kind', 'status', ('payment_status', 'payment_method'), 'staff_note')}),
        ('Клиент', {'fields': ('name', 'phone', 'email', 'user', 'telegram_user_id', 'marketing_consent', 'source')}),
        ('Получение', {'fields': ('receive_method', 'shop', 'address', 'address_details', 'recipient_name', 'recipient_phone',
                                  'surprise', 'date', 'asap', ('time_from', 'time_to'))}),
        ('Открытка и пожелания', {'fields': ('card_text', 'comment')}),
        ('Фото перед выдачей или доставкой', {'fields': ('delivery_photo',),
            'description': 'Загрузите только что сделанное фото собранного букета. Оно появится на странице заказа; при указанной почте клиент получит ссылку.'}),
        ('Деньги', {'fields': ('subtotal', 'discount', 'addons_total', 'delivery_cost', 'certificate', 'certificate_amount',
                              'total', 'promo_code', 'prepay_required', 'paid_at')}),
        ('Служебное', {'classes': ('collapse',), 'fields': ('created', 'updated')}),
    )

    def save_model(self, request, obj, form, change):
        photo_added = 'delivery_photo' in form.changed_data
        super().save_model(request, obj, form, change)
        if photo_added and obj.delivery_photo:
            from . import notifications
            origin = request.build_absolute_uri('/').rstrip('/')
            transaction.on_commit(lambda: notifications.dispatch_order_photo(obj.pk, origin))
            self.message_user(request, 'Фото сохранено. Клиент видит его по ссылке на заказ.', messages.SUCCESS)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop').prefetch_related('items', 'addons')

    # --- колонки ---
    @admin.display(description='№', ordering='id')
    def order_no(self, obj):
        return f'№{obj.pk}'

    @admin.display(description='Когда', ordering='date')
    def when(self, obj):
        return obj.when_display

    @admin.display(description='Клиент')
    def customer(self, obj):
        return f'{obj.name}, {obj.display_phone}'

    @admin.display(description='Куда')
    def place(self, obj):
        return obj.place_display[:60]

    @admin.display(description='Сумма', ordering='total')
    def total_rub(self, obj):
        return rub(obj.total)

    @admin.display(description='Статус', ordering='status')
    def status_chip(self, obj):
        return chip(obj.get_status_display(), STATUS_COLORS[obj.status])

    @admin.display(description='Оплата', ordering='payment_status')
    def pay_chip(self, obj):
        return chip(obj.get_payment_status_display(), PAY_COLORS[obj.payment_status])

    @admin.display(description='Печать')
    def print_links(self, obj):
        if not obj.pk:
            return '—'
        return format_html('<a class="button" href="{}" target="_blank">Бланк заказа</a> &nbsp; <a class="button" href="{}" target="_blank">Открытка</a>',
                           reverse('admin:shop_order_print', args=[obj.pk]), reverse('admin:shop_order_card', args=[obj.pk]))

    # --- массовые действия ---
    def _set(self, request, queryset, status):
        n = 0
        for order in queryset:
            order.set_status(status)
            n += 1
        self.message_user(request, f'Готово: {n}', messages.SUCCESS)

    @admin.action(description='Статус → Подтверждён')
    def mark_confirmed(self, request, queryset):
        self._set(request, queryset, Order.Status.CONFIRMED)

    @admin.action(description='Статус → Собран')
    def mark_ready(self, request, queryset):
        self._set(request, queryset, Order.Status.READY)

    @admin.action(description='Статус → В пути')
    def mark_delivering(self, request, queryset):
        self._set(request, queryset, Order.Status.DELIVERING)

    @admin.action(description='Статус → Выдан / доставлен')
    def mark_done(self, request, queryset):
        self._set(request, queryset, Order.Status.DONE)

    @admin.action(description='Статус → Отменён')
    def mark_canceled(self, request, queryset):
        self._set(request, queryset, Order.Status.CANCELED)

    @admin.action(description='Отметить оплаченными')
    def mark_paid(self, request, queryset):
        n = 0
        for order in queryset:
            order.mark_paid()
            n += 1
        self.message_user(request, f'Отмечено оплаченными: {n}', messages.SUCCESS)

    @admin.action(description='Распечатать бланки выбранных заказов')
    def print_selected(self, request, queryset):
        ids = ','.join(str(pk) for pk in queryset.values_list('pk', flat=True))
        return redirect(f'{reverse("admin:shop_order_print_many")}?ids={ids}')

    @admin.action(description='Скачать таблицу (Excel)')
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="zakazy-muzflowers.csv"'
        out = csv.writer(response, delimiter=';')
        out.writerow(['№', 'Создан', 'Статус', 'Дата', 'Время', 'Способ', 'Куда', 'Клиент', 'Телефон', 'Получатель', 'Состав',
                      'Дополнения', 'Открытка', 'Пожелания', 'Букеты', 'Скидка', 'Доставка', 'Дополнения ₽', 'Итого', 'Оплата', 'Откуда'])
        for o in queryset.select_related('shop').prefetch_related('items', 'addons'):
            out.writerow([
                o.pk, timezone.localtime(o.created).strftime('%d.%m.%Y %H:%M'), o.get_status_display(), o.date.strftime('%d.%m.%Y'),
                o.time_display, o.get_receive_method_display(), o.place_display, o.name, o.display_phone,
                f'{o.recipient_name} {o.display_recipient_phone}'.strip(),
                '; '.join(f'{i.full_name} × {i.qty}' for i in o.items.all()),
                '; '.join(f'{a.name}{": " + a.note if a.note else ""}' for a in o.addons.all()),
                o.card_text, o.comment, o.subtotal, o.discount, o.delivery_cost, o.addons_total, o.total,
                o.get_payment_status_display(), o.source,
            ])
        return response


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = ('created', 'kind', 'action', 'version', 'reference', 'contact', 'user', 'ip_address')
    list_filter = ('kind', 'action', 'version')
    search_fields = ('reference', 'contact', 'user__email', 'ip_address')
    date_hierarchy = 'created'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
