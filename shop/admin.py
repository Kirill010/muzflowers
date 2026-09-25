from django.contrib import admin
from django.core.cache import cache
from .models import Category, Product, Order, OrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete('all_categories')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        cache.delete('all_categories')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'price', 'available', 'created', 'updated']
    list_filter = ['available', 'created', 'updated', 'category']
    list_editable = ['price', 'available']
    prepopulated_fields = {'slug': ('name',)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete('products_all')
        cache.delete(f'products_category_{obj.category.id}')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        cache.delete('products_all')
        cache.delete(f'products_category_{obj.category.id}')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'email', 'phone',
                    'address', 'paid', 'created']
    list_filter = ['paid', 'created', 'updated']
    inlines = [OrderItemInline]