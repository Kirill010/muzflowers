from django.contrib import admin

from .models import Category, Order, OrderItem, Product, PromoCode


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'badge', 'popularity', 'is_active')
    list_editable = ('price', 'badge', 'popularity', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'percent', 'is_active', 'valid_until')
    list_editable = ('is_active',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'name', 'price', 'qty')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'delivery_date', 'delivery_slot', 'total', 'status', 'created')
    list_editable = ('status',)
    list_filter = ('status', 'delivery_date')
    search_fields = ('name', 'phone', 'address')
    date_hierarchy = 'created'
    inlines = [OrderItemInline]
    readonly_fields = ('subtotal', 'discount', 'delivery_cost', 'total', 'promo_code', 'created')
