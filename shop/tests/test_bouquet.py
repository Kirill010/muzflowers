import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from shop.bouquet import MAX_STEMS
from shop.models import Lead, LegalAcceptance


class BouquetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('shop:bouquet_builder')
        self.layout = {
            'vessel': 'basket',
            'stems': [{'kind': 'rose', 'x': 240, 'y': 120}, {'kind': 'peony', 'x': 300, 'y': 90}],
        }
        self.data = {'name': 'Анна', 'phone': '+7 900 123-45-67', 'consent': 'on',
                     'occasion': 'birthday', 'budget': 4500, 'layout': json.dumps(self.layout)}

    @patch('shop.views.notifications.dispatch_lead')
    def test_saves_composition_and_notifies_florist(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, self.data)

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        lead = Lead.objects.get(kind=Lead.Kind.BOUQUET)
        self.assertEqual(lead.layout, self.layout)
        self.assertIn('Корзина', lead.message)
        self.assertIn('Роза × 1, Пион × 1', lead.message)
        self.assertIn('4 500 ₽', lead.message)
        self.assertTrue(LegalAcceptance.objects.filter(reference=f'lead:{lead.pk}').exists())
        notify.assert_called_once_with(lead.pk)

        owner = get_user_model().objects.create_superuser(username='owner', password='test-password')
        self.client.force_login(owner)
        preview = self.client.get(reverse('admin:shop_lead_change', args=[lead.pk]))
        self.assertContains(preview, 'data-bouquet-preview')
        self.assertContains(preview, '"x": 240')

    def test_rejects_invalid_layout_and_missing_consent(self):
        for layout in (
            {'vessel': 'box', 'stems': self.layout['stems']},
            {'vessel': 'vase', 'stems': [{'kind': 'rose', 'x': -1, 'y': 32}]},
            {'vessel': 'vase', 'stems': [self.layout['stems'][0]] * (MAX_STEMS + 1)},
        ):
            with self.subTest(layout=layout):
                response = self.client.post(self.url, dict(self.data, layout=json.dumps(layout)))
                self.assertTrue(response.context['form'].errors['layout'])
        response = self.client.post(self.url, dict(self.data, consent=''))
        self.assertTrue(response.context['form'].errors['consent'])
        self.assertFalse(Lead.objects.exists())

    def test_accepts_a_description_without_javascript(self):
        response = self.client.post(self.url, dict(self.data, layout='', message='Розы в маленькой вазе'))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        lead = Lead.objects.get(kind=Lead.Kind.BOUQUET)
        self.assertEqual(lead.layout, {})
        self.assertIn('Розы в маленькой вазе', lead.message)
