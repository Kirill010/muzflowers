import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Category, Order, Product, Review


class PageTests(TestCase):
    def setUp(self):
        cache.clear()
        cat = Category.objects.create(name='Розы', slug='roses')
        self.product = Product.objects.create(category=cat, name='Нежность', price=1000)
        Review.objects.create(name='Анна', text='Отличный сервис!')

    def test_index_shows_products_and_reviews(self):
        r = self.client.get(reverse('shop:index'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['products'][0]['n'], 'Нежность')
        self.assertContains(r, 'Отличный сервис!')

    def test_privacy_page(self):
        self.assertEqual(self.client.get(reverse('shop:privacy')).status_code, 200)

    def test_order_is_linked_to_logged_in_user(self):
        user = get_user_model().objects.create_user('kirill', password='Strong-pass-123')
        self.client.force_login(user)
        data = {
            'consent': True, 'name': 'Кирилл', 'phone': '+7 900 000-00-00', 'address': 'ул. Цветочная, 1',
            'date': (date.today() + timedelta(days=1)).isoformat(),
            'items': [{'id': self.product.id, 'qty': 1}],
        }
        r = self.client.post(reverse('shop:order'), json.dumps(data), content_type='application/json')
        self.assertTrue(r.json()['ok'])
        self.assertEqual(Order.objects.get().user, user)
