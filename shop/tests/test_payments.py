import json
from unittest import mock

from django.test import Client, override_settings
from django.urls import reverse

from shop import payments
from shop.models import Order, OrderAddon, OrderItem

from .helpers import TODAY, TOMORROW, ShopTestCase

TBANK = dict(PAYMENT_PROVIDER='tbank', PAYMENT_TBANK_TERMINAL='TERM', PAYMENT_TBANK_PASSWORD='SECRET', SITE_URL='https://muz.example')
YOO = dict(PAYMENT_PROVIDER='yookassa', PAYMENT_YOOKASSA_SHOP_ID='123', PAYMENT_YOOKASSA_SECRET='key', SITE_URL='https://muz.example')


class PaymentTestCase(ShopTestCase):
    def make_order(self, **extra):
        # 3 × 1990 + 5990 = 11960 за букеты, −500 скидка, +300 открытка, +300 доставка = 12060
        data = dict(name='Анна', phone='+79175494941', date=TOMORROW, time_from=None, subtotal=11960, discount=500, addons_total=300,
                    delivery_cost=300, total=12060, payment_method=Order.Pay.ONLINE, payment_status=Order.PayStatus.PENDING,
                    prepay_required=True, receive_method=Order.Method.DELIVERY, email='anna@example.com')
        data.update(extra)
        order = Order.objects.create(**data)
        OrderItem.objects.create(order=order, product=self.rose, name='Классика', price=1990, qty=3)
        OrderItem.objects.create(order=order, product=self.big, name='25 роз', price=5990, qty=1)
        OrderAddon.objects.create(order=order, name='Музыкальная открытка', price=300, note='Песня')
        return order


class TBankTests(PaymentTestCase):
    @override_settings(PAYMENT_TBANK_PASSWORD='11111111111111')
    def test_token_matches_the_official_example(self):
        params = {'TerminalKey': 'MerchantTerminalKey', 'Amount': 19200, 'OrderId': '00000', 'Description': 'Подарочная карта на 1000 рублей',
                  'Receipt': {'Items': [{'Name': 'x'}]}, 'DATA': {'a': 'b'}}
        self.assertEqual(payments._tbank_token(params), '72dd466f8ace0a37a1f740ce5fb78101712bc0665d91a8108c7c8a0ccd426db2')

    def test_receipt_adds_up_exactly_to_the_total(self):
        order = self.make_order()
        lines = payments.receipt_lines(order)
        self.assertEqual(sum(amount for *_, amount in lines), order.total * 100)
        for name, qty, price, amount in lines:
            self.assertEqual(price * qty, amount)

    @override_settings(**TBANK)
    def test_start_payment_sends_signed_init_and_is_idempotent(self):
        order = self.make_order()
        reply = {'Success': True, 'PaymentId': '777', 'PaymentURL': 'https://pay.example/777'}
        with mock.patch('shop.payments._http', return_value=reply) as http:
            url = payments.start_payment(order, 'https://muz.example/order/x/')
            again = payments.start_payment(order, 'https://muz.example/order/x/')
        self.assertEqual((url, again), ('https://pay.example/777', 'https://pay.example/777'))
        self.assertEqual(http.call_count, 1)
        endpoint, body = http.call_args.args
        self.assertEqual(endpoint, 'https://securepay.tinkoff.ru/v2/Init')
        self.assertEqual((body['Amount'], body['TerminalKey']), (12060 * 100, 'TERM'))
        self.assertEqual(body['Token'], payments._tbank_token(body))
        self.assertEqual(sum(i['Amount'] for i in body['Receipt']['Items']), body['Amount'])
        self.assertEqual(body['Receipt']['Email'], 'anna@example.com')
        self.assertEqual(body['NotificationURL'], 'https://muz.example/payments/webhook/tbank/')
        order.refresh_from_db()
        self.assertEqual((order.pay_external_id, order.pay_provider), ('777', 'tbank'))

    @override_settings(**TBANK, PAYMENT_RECEIPT=False)
    def test_receipt_can_be_switched_off(self):
        order = self.make_order()
        with mock.patch('shop.payments._http', return_value={'Success': True, 'PaymentId': '1', 'PaymentURL': 'https://p/1'}) as http:
            payments.start_payment(order, 'https://muz.example/')
        self.assertNotIn('Receipt', http.call_args.args[1])

    @override_settings(**TBANK)
    def test_bank_refusal_becomes_a_payment_error(self):
        with mock.patch('shop.payments._http', return_value={'Success': False, 'ErrorCode': '8'}):
            with self.assertRaises(payments.PaymentError):
                payments.start_payment(self.make_order(), 'https://muz.example/')

    def notify(self, order, **override):
        body = {'TerminalKey': 'TERM', 'OrderId': f'{order.pk}-abc123', 'Success': True, 'Status': 'CONFIRMED', 'PaymentId': 777,
                'ErrorCode': '0', 'Amount': order.total * 100}
        body.update(override)
        body['Token'] = payments._tbank_token(body)
        return Client(enforce_csrf_checks=True).post(reverse('shop:payment_webhook', args=['tbank']), json.dumps(body), content_type='application/json')

    @override_settings(**TBANK)
    def test_webhook_marks_order_paid(self):
        order = self.make_order()
        r = self.notify(order)
        self.assertEqual((r.status_code, r.content), (200, b'OK'))
        order.refresh_from_db()
        self.assertTrue(order.is_paid)

    @override_settings(**TBANK)
    def test_webhook_with_wrong_signature_is_rejected(self):
        order = self.make_order()
        body = {'TerminalKey': 'TERM', 'OrderId': f'{order.pk}-x', 'Success': True, 'Status': 'CONFIRMED', 'Amount': order.total * 100, 'Token': 'bad'}
        r = Client().post(reverse('shop:payment_webhook', args=['tbank']), json.dumps(body), content_type='application/json')
        self.assertEqual(r.status_code, 400)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    @override_settings(**TBANK)
    def test_webhook_with_wrong_amount_does_not_pay(self):
        order = self.make_order()
        self.assertEqual(self.notify(order, Amount=100).status_code, 200)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    @override_settings(**TBANK)
    def test_unfinished_statuses_do_not_pay(self):
        order = self.make_order()
        self.notify(order, Status='REJECTED', Success=False)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    @override_settings(**TBANK)
    def test_webhook_for_another_provider_is_404(self):
        r = Client().post(reverse('shop:payment_webhook', args=['yookassa']), '{}', content_type='application/json')
        self.assertEqual(r.status_code, 404)

    @override_settings(**TBANK)
    def test_return_from_bank_checks_status(self):
        order = self.make_order(pay_provider='tbank', pay_external_id='777', pay_url='https://pay.example/777')
        with mock.patch('shop.payments._http', return_value={'Success': True, 'Status': 'CONFIRMED'}):
            r = self.client.get(order.get_absolute_url())
        self.assertContains(r, 'Оплачено')
        order.refresh_from_db()
        self.assertTrue(order.is_paid)

    @override_settings(**TBANK)
    def test_pay_view_redirects_to_bank(self):
        order = self.make_order()
        with mock.patch('shop.payments._http', return_value={'Success': True, 'PaymentId': '9', 'PaymentURL': 'https://pay.example/9'}):
            r = self.client.get(reverse('shop:order_pay', args=[order.token]))
        self.assertRedirects(r, 'https://pay.example/9', fetch_redirect_response=False)

    @override_settings(**TBANK)
    def test_pay_view_shows_error_when_bank_is_down(self):
        order = self.make_order()
        with mock.patch('shop.payments._http', side_effect=payments.PaymentError('банк сейчас не отвечает.')):
            r = self.client.get(reverse('shop:order_pay', args=[order.token]), follow=True)
        self.assertContains(r, 'Не удалось открыть оплату')

    @override_settings(**TBANK)
    def test_online_option_appears_when_configured(self):
        self.add_to_cart()
        r = self.client.get(reverse('shop:checkout'))
        self.assertContains(r, 'Картой или через СБП онлайн')

    @override_settings(**TBANK)
    def test_checkout_with_online_payment_goes_to_bank(self):
        self.add_to_cart()
        with mock.patch('shop.payments._http', return_value={'Success': True, 'PaymentId': '5', 'PaymentURL': 'https://pay.example/5'}):
            r = self.place_order(date=TOMORROW.isoformat(), time_slot='10:00', payment_method='online', email='a@example.com')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].endswith('/pay/'))

    def test_online_option_is_hidden_without_keys(self):
        self.add_to_cart()
        self.assertNotContains(self.client.get(reverse('shop:checkout')), 'Картой или через СБП онлайн')


class YooKassaTests(PaymentTestCase):
    @override_settings(**YOO)
    def test_start_payment(self):
        order = self.make_order()
        reply = {'id': 'pay-1', 'status': 'pending', 'confirmation': {'confirmation_url': 'https://yoo.example/pay-1'}}
        with mock.patch('shop.payments._http', return_value=reply) as http:
            url = payments.start_payment(order, 'https://muz.example/order/x/')
        self.assertEqual(url, 'https://yoo.example/pay-1')
        endpoint, body = http.call_args.args
        self.assertEqual(endpoint, 'https://api.yookassa.ru/v3/payments')
        self.assertEqual(body['amount'], {'value': '12060.00', 'currency': 'RUB'})
        self.assertEqual(body['confirmation'], {'type': 'redirect', 'return_url': 'https://muz.example/order/x/'})
        self.assertEqual(body['receipt']['customer'], {'email': 'anna@example.com'})
        self.assertEqual(sum(float(i['amount']['value']) * float(i['quantity']) for i in body['receipt']['items']), 12060.0)
        self.assertEqual(len(http.call_args.kwargs['headers']['Idempotence-Key']), 32)
        self.assertEqual(http.call_args.kwargs['auth'], ('123', 'key'))

    @override_settings(**YOO)
    def test_webhook_is_verified_with_the_bank(self):
        order = self.make_order(pay_provider='yookassa', pay_external_id='pay-1', pay_url='https://yoo.example/pay-1')
        status = {'id': 'pay-1', 'status': 'succeeded', 'paid': True, 'amount': {'value': '12060.00', 'currency': 'RUB'},
                  'metadata': {'order_id': str(order.pk)}}
        body = json.dumps({'type': 'notification', 'event': 'payment.succeeded', 'object': {'id': 'pay-1'}})
        with mock.patch('shop.payments._http', return_value=status) as http:
            r = Client(enforce_csrf_checks=True).post(reverse('shop:payment_webhook', args=['yookassa']), body, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(http.call_args.args[0], 'https://api.yookassa.ru/v3/payments/pay-1')
        order.refresh_from_db()
        self.assertTrue(order.is_paid)

    @override_settings(**YOO)
    def test_forged_webhook_does_not_pay(self):
        order = self.make_order(pay_provider='yookassa', pay_external_id='pay-1')
        body = json.dumps({'type': 'notification', 'event': 'payment.succeeded', 'object': {'id': 'pay-1'}})
        pending = {'id': 'pay-1', 'status': 'pending', 'paid': False, 'amount': {'value': '12060.00'}, 'metadata': {'order_id': str(order.pk)}}
        with mock.patch('shop.payments._http', return_value=pending):
            Client().post(reverse('shop:payment_webhook', args=['yookassa']), body, content_type='application/json')
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    @override_settings(**YOO)
    def test_amount_mismatch_does_not_pay(self):
        order = self.make_order(pay_provider='yookassa', pay_external_id='pay-1')
        cheap = {'id': 'pay-1', 'status': 'succeeded', 'paid': True, 'amount': {'value': '1.00'}, 'metadata': {'order_id': str(order.pk)}}
        body = json.dumps({'type': 'notification', 'event': 'payment.succeeded', 'object': {'id': 'pay-1'}})
        with mock.patch('shop.payments._http', return_value=cheap):
            Client().post(reverse('shop:payment_webhook', args=['yookassa']), body, content_type='application/json')
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    @override_settings(**YOO)
    def test_phone_is_used_when_no_email(self):
        order = self.make_order(email='')
        with mock.patch('shop.payments._http', return_value={'id': 'p', 'confirmation': {'confirmation_url': 'https://y/p'}}) as http:
            payments.start_payment(order, 'https://muz.example/')
        self.assertEqual(http.call_args.args[1]['receipt']['customer'], {'phone': '79175494941'})


class NoProviderTests(PaymentTestCase):
    def test_nothing_is_configured_by_default(self):
        self.assertFalse(payments.is_configured())
        with self.assertRaises(payments.PaymentError):
            payments.start_payment(self.make_order(), 'https://muz.example/')

    def test_incomplete_keys_mean_not_configured(self):
        with override_settings(PAYMENT_PROVIDER='tbank', PAYMENT_TBANK_TERMINAL='x', PAYMENT_TBANK_PASSWORD=''):
            self.assertFalse(payments.is_configured())
