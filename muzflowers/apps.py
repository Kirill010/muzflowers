from django.contrib.admin.apps import AdminConfig


class MuzAdminConfig(AdminConfig):
    """Обычная админка Django, но с «панелью владельца» на главной (см. shop/admin_site.py)."""
    default_site = 'shop.admin_site.MuzAdminSite'
