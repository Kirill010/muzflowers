from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_register_creates_user_and_logs_in(self):
        r = self.client.post(reverse('accounts:register'), {
            'username': 'anna', 'first_name': 'Анна',
            'password1': 'Flowers-2026!x', 'password2': 'Flowers-2026!x',
        })
        self.assertRedirects(r, reverse('shop:index'))
        self.assertTrue(get_user_model().objects.filter(username='anna').exists())

    def test_profile_requires_login(self):
        r = self.client.get(reverse('accounts:profile'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('accounts:login'), r['Location'])

    def test_login_page_opens(self):
        self.assertEqual(self.client.get(reverse('accounts:login')).status_code, 200)
