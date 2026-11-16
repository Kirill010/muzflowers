from datetime import datetime, timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from shop.models import Addon, Category, Product, PromoCode, Shop, SiteSettings, Variant

# «Сейчас» во всех тестах: среда, 4 ноября 2026, 12:00 по Москве
NOW = timezone.make_aware(datetime(2026, 11, 4, 12, 0))
TODAY = NOW.date()
TOMORROW = TODAY + timedelta(days=1)


def freeze(now=NOW):
    return mock.patch('django.utils.timezone.now', return_value=now)


@override_settings(CSP_MODE='enforce')
class ShopTestCase(TestCase):
    """Общая основа: заморозка времени, одна точка, два букета и музыкальная открытка."""

    def setUp(self):
        cache.clear()
        patcher = freeze()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.site = SiteSettings.load()
        self.shop = Shop.objects.create(name='Курская', address='Земляной Вал, 39/1', landmark='переход у вокзала', is_pickup=True)
        self.cat = Category.objects.create(name='Розы')
        self.rose = Product.objects.create(category=self.cat, name='Классика', price=1990, tagline='7 роз, зелень', is_ready=True, popularity=10)
        self.big = Product.objects.create(category=self.cat, name='25 роз', price=5990, popularity=5)
        self.music = Addon.objects.create(name='Музыкальная открытка', price=300, is_music=True,
                                          note_label='Какая песня?', note_required=True)

    # --- удобные помощники ---
    def update_site(self, **fields):
        SiteSettings.objects.filter(pk=1).update(**fields)
        cache.clear()
        self.site = SiteSettings.load()

    def add_to_cart(self, product=None, qty=1, **extra):
        product = product or self.rose
        return self.client.post(reverse('shop:cart_add'), {'product': product.pk, 'qty': qty, **extra},
                                headers={'X-Requested-With': 'fetch'})

    def order_data(self, **overrides):
        """Данные формы оформления: самовывоз сегодня «как можно скорее», оплата при получении."""
        data = {
            'name': 'Анна', 'phone': '+7 917 549-49-41', 'receive_method': 'pickup', 'shop': self.shop.pk,
            'date': TODAY.isoformat(), 'time_slot': 'asap', 'payment_method': 'on_receipt',
            'consent_pd': 'on', 'consent_offer': 'on',
        }
        data.update(overrides)
        return data

    def place_order(self, **overrides):
        return self.client.post(reverse('shop:checkout'), self.order_data(**overrides))
