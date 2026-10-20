import json
from datetime import date, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Category, Order, Product, PromoCode


class OrderTests(TestCase):
    def setUp(self):
        cache.clear()
        cat = Category.objects.create(name='Розы', slug='roses')
        self.product = Product.objects.create(category=cat, name='Тест', price=1000)
        PromoCode.objects.create(code='muz10', percent=10)

    def send(self, qty=2, **extra):
        data = {
            'consent': True, 'name': 'Анна', 'phone': '+7 900 000-00-00', 'address': 'ул. Цветочная, 1',
            'date': (date.today() + timedelta(days=1)).isoformat(),
            'items': [{'id': self.product.id, 'qty': qty, 'price': 1}],  # цена от клиента игнорируется
        }
        data.update(extra)
        return self.client.post(reverse('shop:order'), json.dumps(data), content_type='application/json')

    def test_small_order_pays_delivery(self):
        self.assertTrue(self.send().json()['ok'])
        o = Order.objects.get()
        self.assertEqual((o.subtotal, o.delivery_cost, o.total), (2000, 300, 2300))

    def test_promo_and_free_delivery(self):
        self.send(qty=4, promo='MUZ10')
        o = Order.objects.get()
        self.assertEqual((o.discount, o.delivery_cost, o.total), (400, 0, 3600))

    def test_past_date_rejected(self):
        r = self.send(date=(date.today() - timedelta(days=1)).isoformat())
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_consent_required(self):
        self.assertEqual(self.send(consent=False).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_far_future_date_rejected(self):
        far = (date.today() + timedelta(days=400)).isoformat()
        self.assertEqual(self.send(date=far).status_code, 400)

    def test_order_rate_limit(self):
        codes = [self.send().status_code for _ in range(11)]
        self.assertEqual(codes[-1], 429)
        self.assertEqual(Order.objects.count(), 10)
