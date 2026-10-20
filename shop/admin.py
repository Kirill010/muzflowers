from django.contrib import admin
from django.core.cache import cache
from django.utils.html import format_html
from .models import Category, Product, Order, OrderItem, ConsultationRequest


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'image_preview']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="60" />', obj.image.url)
        return '—'
    image_preview.short_description = 'Превью'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete('all_categories')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        cache.delete('all_categories')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'price', 'old_price', 'available', 'stock',
                    'rating', 'occasion', 'created', 'image_preview']
    list_filter = ['available', 'created', 'updated', 'category', 'occasion']
    list_editable = ['price', 'old_price', 'available', 'stock']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['image_preview', 'rating']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80" />', obj.image.url)
        return '—'
    image_preview.short_description = 'Превью'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete('products_all')
        cache.delete(f'products_category_{obj.category.id}')

    def delete_model(self, request, obj):
        cat_id = obj.category.id
        super().delete_model(request, obj)
        cache.delete('products_all')
        cache.delete(f'products_category_{cat_id}')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'email', 'phone',
                    'status', 'paid', 'discount_amount', 'created']
    list_filter = ['status', 'paid', 'created', 'updated']
    list_editable = ['status', 'paid']
    inlines = [OrderItemInline]
    actions = ['mark_processing', 'mark_delivered']

    def mark_processing(self, request, queryset):
        queryset.update(status='processing')
    mark_processing.short_description = '→ В обработку'

    def mark_delivered(self, request, queryset):
        queryset.update(status='delivered')
    mark_delivered.short_description = '→ Доставлен'


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'occasion', 'budget_min', 'budget_max',
                    'processed', 'created']
    list_filter = ['processed', 'occasion']
    list_editable = ['processed']