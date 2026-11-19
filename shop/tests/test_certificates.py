from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from shop.models import GiftCertificate, LegalAcceptance, Order

from .helpers import TODAY, ShopTestCase


@override_settings(PAYMENT_PROVIDER='yookassa', PAYMENT_YOOKASSA_SHOP_ID='123', PAYMENT_YOOKASSA_SECRET='test_secret_01234567890123456789')
class CertificatePageTests(ShopTestCase):
    def payload(self, operation_id, **extra):
        data = {'amount': '1000', 'custom_amount': '', 'name': 'Анна', 'phone': '+7 917 549-49-41',
                'email': 'anna@example.com', 'consent_pd': 'on', 'consent_offer': 'on', 'operation_id': operation_id}
        data.update(extra)
        return data

    def test_purchase_page_creates_one_order_and_code_after_payment(self):
        response = self.client.get(reverse('shop:certificates'))
        self.assertContains(response, 'Подарочный')
        operation_id = self.client.session['certificate_operation']
        with mock.patch('shop.payments._yookassa_start', return_value=('pay-1', 'https://bank.example/pay')):
            response = self.client.post(reverse('shop:certificates'), self.payload(operation_id))
            order = Order.objects.get(kind=Order.Kind.CERTIFICATE)
            self.assertRedirects(response, reverse('shop:order_pay', args=[order.token]), fetch_redirect_response=False)
            response = self.client.post(reverse('shop:certificates'), self.payload(operation_id))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.phone, '+79175494941')
        self.assertEqual(LegalAcceptance.objects.count(), 2)
        order.mark_paid()
        certificate = GiftCertificate.objects.get(purchase_order=order)
        page = self.client.get(order.get_absolute_url())
        self.assertContains(page, certificate.code)
        self.assertContains(page, 'Telegram-боте')

    def test_web_checkout_can_be_fully_paid_by_certificate(self):
        certificate = GiftCertificate.objects.create(code='AAAA-BBBB-CCCC', amount=3000, balance=3000,
                                                     expires_at=TODAY + timedelta(days=100))
        self.add_to_cart()
        response = self.place_order(certificate_code=certificate.code, payment_method='certificate')
        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual((order.total, order.payment_method, order.payment_status), (0, 'certificate', 'paid'))
        certificate.refresh_from_db()
        self.assertEqual(certificate.balance, 1010)
