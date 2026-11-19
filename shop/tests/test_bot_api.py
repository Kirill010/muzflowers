import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from shop.models import BotOperation, GiftCertificate, GiftCertificateLedger, LegalAcceptance, Order
from shop.orders import create_order
from shop.pricing import build_quote

from .helpers import TODAY, ShopTestCase

SECRET = 'test-bot-secret-0123456789abcdef0123456789'
ADMIN = 1000000001
CUSTOMER = 2000000002
OTHER = 3000000003


@override_settings(BOT_API_SECRET=SECRET, BOT_ADMIN_IDS=[ADMIN])
class BotApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.telegram = CUSTOMER

    def call(self, name, data=None, *, key=None, signature=None, timestamp=None, nonce=None):
        path = reverse(f'shop:{name}')
        body = json.dumps(data or {}, ensure_ascii=False).encode()
        moment = timestamp or str(int(timezone.now().timestamp()))
        signed = moment.encode() + b'.' + path.encode() + b'.' + body
        headers = {
            'X-Muz-Timestamp': moment,
            'X-Muz-Nonce': nonce or uuid.uuid4().hex,
            'X-Muz-Signature': signature or hmac.new(SECRET.encode(), signed, hashlib.sha256).hexdigest(),
        }
        if key:
            headers['X-Idempotency-Key'] = key
        return self.client.post(path, body, content_type='application/json', headers=headers)

    def order_payload(self, **extra):
        data = {
            'telegram_user_id': self.telegram,
            'lines': [{'product': self.rose.pk, 'variant': 0, 'qty': 1}],
            'addons': [{'id': self.music.pk, 'note': 'Земфира — Хочешь?'}],
            'name': 'Анна', 'phone': '+7 917 549-49-41', 'receive_method': 'pickup', 'shop': self.shop.pk,
            'date': TODAY.isoformat(), 'time_slot': 'asap', 'payment_method': 'on_receipt',
            'consent_pd': True, 'consent_offer': True,
        }
        data.update(extra)
        return data

    def test_signature_expiry_replay_and_method(self):
        response = self.client.post(reverse('shop:bot_bootstrap'), '{}', content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.call('bot_bootstrap', signature='0' * 64).status_code, 403)
        old = str(int((timezone.now() - timedelta(minutes=10)).timestamp()))
        self.assertEqual(self.call('bot_bootstrap', timestamp=old).status_code, 401)
        nonce = uuid.uuid4().hex
        self.assertEqual(self.call('bot_bootstrap', nonce=nonce).status_code, 200)
        self.assertEqual(self.call('bot_bootstrap', nonce=nonce).status_code, 409)
        self.assertEqual(self.client.get(reverse('shop:bot_bootstrap')).status_code, 405)

    def test_bootstrap_has_catalog_and_vykhino_not_secrets(self):
        response = self.call('bot_bootstrap')
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['shop']['phone'], '+7 (995) 152-21-31')
        self.assertIn('Вешняковская', data['shop']['address'])
        self.assertTrue(any(item['id'] == self.rose.pk for item in data['products']))
        self.assertNotIn('secret', response.content.decode().lower())

    def test_quote_uses_server_rules_and_certificate(self):
        self.update_site(pickup_discount_percent=10)
        certificate = GiftCertificate.objects.create(code='AAAA-BBBB-CCCC', amount=3000, balance=3000,
                                                     expires_at=TODAY + timedelta(days=100))
        response = self.call('bot_quote', {
            'lines': [{'product': self.rose.pk, 'qty': 1}], 'receive_method': 'pickup',
            'certificate_code': 'aaaa bbbb cccc',
        })
        data = response.json()
        self.assertEqual((data['discount'], data['certificate_amount'], data['total']), (199, 1791, 0))
        self.assertEqual(data['payment_methods'][0]['value'], 'certificate')
        self.assertTrue(certificate.problem() == '')

    def test_order_create_is_idempotent_and_private(self):
        response = self.call('bot_order_create', self.order_payload(), key='order-one-unique')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['total'], 2290)
        order = Order.objects.get()
        self.assertEqual((order.telegram_user_id, order.source), (CUSTOMER, 'telegram'))
        self.assertEqual(order.addons.get().note, 'Земфира — Хочешь?')
        self.assertEqual(LegalAcceptance.objects.count(), 2)
        repeat = self.call('bot_order_create', self.order_payload(), key='order-one-unique')
        self.assertEqual(repeat.json()['id'], order.pk)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(BotOperation.objects.count(), 1)
        self.telegram = OTHER
        self.assertEqual(self.call('bot_order_detail', {'telegram_user_id': OTHER, 'order': order.pk}).status_code, 404)
        self.telegram = CUSTOMER
        self.assertEqual(self.call('bot_order_list', {'telegram_user_id': CUSTOMER}).json()['orders'][0]['id'], order.pk)

    def test_order_requires_consents_and_valid_data(self):
        response = self.call('bot_order_create', self.order_payload(consent_pd=False), key='missing-consent')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        response = self.call('bot_order_create', self.order_payload(lines=[{'product': 999999, 'qty': 1}]), key='bad-product')
        self.assertEqual(response.status_code, 400)

    def test_customer_can_cancel_only_new_unpaid_order(self):
        order = Order.objects.create(name='Анна', phone='+79175494941', telegram_user_id=CUSTOMER,
                                     date=TODAY, subtotal=100, total=100)
        response = self.call('bot_order_cancel', {'telegram_user_id': CUSTOMER, 'order': order.pk}, key='cancel-one')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELED)
        response = self.call('bot_order_cancel', {'telegram_user_id': CUSTOMER, 'order': order.pk}, key='cancel-two')
        self.assertEqual(response.status_code, 409)

    @override_settings(PAYMENT_PROVIDER='yookassa', PAYMENT_YOOKASSA_SHOP_ID='123', PAYMENT_YOOKASSA_SECRET='test_secret_01234567890123456789')
    def test_certificate_purchase_issue_and_duplicate_operation(self):
        def pay(order, return_url):
            order.pay_url = 'https://bank.example/pay'
            order.save(update_fields=['pay_url'])
            return order.pay_url
        with mock.patch('shop.bot_api.payments.start_payment', side_effect=pay):
            response = self.call('bot_certificate_purchase', {
                'telegram_user_id': CUSTOMER, 'amount': 3000, 'name': 'Анна', 'phone': '+79175494941',
                'consent_pd': True, 'consent_offer': True,
            }, key='certificate-purchase-one')
            self.assertEqual(response.status_code, 201, response.content)
            repeat = self.call('bot_certificate_purchase', {
                'telegram_user_id': CUSTOMER, 'amount': 3000, 'name': 'Анна', 'phone': '+79175494941',
                'consent_pd': True, 'consent_offer': True,
            }, key='certificate-purchase-one')
        order = Order.objects.get(kind=Order.Kind.CERTIFICATE)
        self.assertEqual(repeat.json()['order']['id'], order.pk)
        order.mark_paid()
        certificate = GiftCertificate.objects.get(purchase_order=order)
        self.assertEqual((certificate.amount, certificate.balance), (3000, 3000))
        self.assertEqual(certificate.ledger.get(note='Продажа сертификата').delta, 3000)

    def test_certificate_redemption_and_cancellation_restores_once(self):
        certificate = GiftCertificate.objects.create(code='AAAA-BBBB-CCCC', amount=3000, balance=3000,
                                                     expires_at=TODAY + timedelta(days=100))
        lines, _ = __import__('shop.bot_api', fromlist=['_lines'])._lines({'lines': [{'product': self.rose.pk, 'qty': 1}], 'addons': []})
        quote = build_quote(lines, [], method='pickup', certificate_code=certificate.code)
        data = {
            'name': 'Анна', 'phone': '+79175494941', 'receive_method': 'pickup', 'shop': self.shop,
            'date': TODAY, 'option': {'time_from': None, 'time_to': None, 'asap': True},
            'payment_method': 'certificate', 'telegram_user_id': CUSTOMER,
        }
        with self.captureOnCommitCallbacks(execute=True):
            order = create_order(quote=quote, data=data, source='telegram', request=mock.Mock(META={}))
        certificate.refresh_from_db()
        self.assertEqual((order.total, certificate.balance), (0, 1010))
        order.set_status(Order.Status.CANCELED)
        certificate.refresh_from_db()
        self.assertEqual(certificate.balance, 3000)
        order.set_status(Order.Status.CANCELED)
        certificate.refresh_from_db()
        self.assertEqual(certificate.balance, 3000)
        self.assertEqual(GiftCertificateLedger.objects.filter(note='Возврат при отмене заказа').count(), 1)

    def test_staff_permissions_and_stock(self):
        response = self.call('bot_staff_stock', {'telegram_user_id': CUSTOMER, 'product': self.rose.pk, 'in_stock': False}, key='stock-denied')
        self.assertEqual(response.status_code, 403)
        response = self.call('bot_staff_stock', {'telegram_user_id': ADMIN, 'product': self.rose.pk, 'in_stock': False}, key='stock-allowed')
        self.assertEqual(response.status_code, 200)
        self.rose.refresh_from_db()
        self.assertFalse(self.rose.in_stock)

    def test_old_api_responses_are_cleaned_up(self):
        from django.core.management import call_command
        old = BotOperation.objects.create(action='test', key='old-operation', telegram_user_id=CUSTOMER, response={'ok': True})
        BotOperation.objects.filter(pk=old.pk).update(created=timezone.now() - timedelta(days=91))
        recent = BotOperation.objects.create(action='test', key='recent-operation', telegram_user_id=CUSTOMER, response={'ok': True})
        call_command('cleanup_bot_operations', verbosity=0)
        self.assertFalse(BotOperation.objects.filter(pk=old.pk).exists())
        self.assertTrue(BotOperation.objects.filter(pk=recent.pk).exists())
