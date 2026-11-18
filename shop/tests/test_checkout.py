from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from shop import notifications
from shop.legal import DOCUMENT_VERSION
from shop.models import Lead, LegalAcceptance, Order, OrderAddon, PromoCode, SpecialDay, Variant

from .helpers import TODAY, TOMORROW, ShopTestCase


class CheckoutTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.add_to_cart()

    def assertNoOrder(self, response, field=None):
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        if field:
            self.assertIn(field, response.context['form'].errors)

    # ───────── удачные заказы ─────────
    def test_pickup_today_pay_on_receipt(self):
        r = self.place_order()
        order = Order.objects.get()
        self.assertRedirects(r, order.get_absolute_url())
        self.assertEqual((order.receive_method, order.shop, order.asap, order.prepay_required), ('pickup', self.shop, True, False))
        self.assertEqual((order.subtotal, order.delivery_cost, order.total), (1990, 0, 1990))
        self.assertEqual((order.phone, order.payment_status, order.status), ('+79175494941', 'unpaid', 'new'))
        self.assertEqual(order.items.get().name, 'Классика')
        self.assertEqual(self.client.session['mz_cart']['items'], {})  # корзина очищена

    def test_delivery_for_tomorrow_requires_prepayment_and_keeps_recipient(self):
        self.place_order(receive_method='delivery', address='Москва, ул. Пушкина, 1', address_details='подъезд 2',
                         date=TOMORROW.isoformat(), time_slot='11:00-13:00', payment_method='transfer',
                         other_recipient='on', recipient_name='Мама', recipient_phone='8 900 111-22-33', surprise='on')
        order = Order.objects.get()
        self.assertEqual((order.receive_method, order.shop, order.prepay_required), ('delivery', None, True))
        self.assertEqual((order.recipient_name, order.recipient_phone, order.surprise), ('Мама', '+79001112233', True))
        self.assertEqual((order.time_from.hour, order.time_to.hour, order.delivery_cost, order.total), (11, 13, 300, 2290))
        self.assertEqual(order.payment_status, 'pending')

    def test_free_delivery_over_threshold(self):
        self.add_to_cart(self.big)
        self.place_order(receive_method='delivery', address='Москва, ул. Пушкина, 1', date=TOMORROW.isoformat(),
                         time_slot='11:00-13:00', payment_method='transfer')
        self.assertEqual((Order.objects.get().delivery_cost, Order.objects.get().total), (0, 7980))

    def test_promo_is_applied_and_counted(self):
        promo = PromoCode.objects.create(code='MUZ10', value=10, usage_limit=1)
        self.client.post(reverse('shop:cart_promo'), {'code': 'muz10'}, headers={'X-Requested-With': 'fetch'})
        self.place_order(promo='MUZ10')
        order = Order.objects.get()
        self.assertEqual((order.promo_code, order.discount, order.total), ('MUZ10', 199, 1791))
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)

    def test_musical_card_is_saved_with_the_song(self):
        key = f'addon_{self.music.pk}'
        self.place_order(**{key: 'on', f'{key}_note': 'Земфира — Хочешь?'})
        order = Order.objects.get()
        self.assertEqual(order.addons_total, 300)
        self.assertEqual(order.total, 2290)
        self.assertEqual(OrderAddon.objects.get().note, 'Земфира — Хочешь?')

    def test_variant_price_and_name_are_stored(self):
        v = Variant.objects.create(product=self.big, name='Большой', price=7000)
        self.client.post(reverse('shop:cart_remove'), {'key': f'{self.rose.pk}:0'})
        self.client.post(reverse('shop:cart_add'), {'product': self.big.pk, 'variant': v.pk})
        self.place_order()
        item = Order.objects.get().items.get()
        self.assertEqual((item.variant_name, item.price), ('Большой', 7000))

    # ───────── отказы ─────────
    def test_future_date_cannot_be_paid_on_receipt(self):
        r = self.place_order(date=TOMORROW.isoformat(), time_slot='10:00', payment_method='on_receipt')
        self.assertNoOrder(r, 'payment_method')

    def test_past_date_is_rejected(self):
        r = self.place_order(date=(TODAY - timedelta(days=1)).isoformat())
        self.assertNoOrder(r, 'date')

    def test_time_must_come_from_the_list(self):
        self.assertNoOrder(self.place_order(time_slot='03:00'), 'time_slot')
        self.assertNoOrder(self.place_order(date=TOMORROW.isoformat(), time_slot='asap', payment_method='transfer'), 'time_slot')

    def test_both_consents_are_required(self):
        data = self.order_data()
        del data['consent_pd']
        self.assertNoOrder(self.client.post(reverse('shop:checkout'), data), 'consent_pd')
        data = self.order_data()
        del data['consent_offer']
        self.assertNoOrder(self.client.post(reverse('shop:checkout'), data), 'consent_offer')

    def test_phone_must_be_complete(self):
        self.assertNoOrder(self.place_order(phone='123'), 'phone')

    def test_delivery_needs_address_and_recipient(self):
        self.assertNoOrder(self.place_order(receive_method='delivery', address=''), 'address')
        r = self.place_order(receive_method='delivery', address='Москва, ул. Пушкина, 1', other_recipient='on',
                             time_slot='17:00-19:00')
        self.assertNoOrder(r, 'recipient_name')

    def test_delivery_can_be_switched_off(self):
        self.update_site(delivery_enabled=False)
        r = self.place_order(receive_method='delivery', address='Москва, ул. Пушкина, 1', time_slot='17:00-19:00')
        self.assertNoOrder(r, 'receive_method')

    def test_robots_are_caught_by_honeypot(self):
        self.assertNoOrder(self.place_order(website='http://spam.example'), 'website')

    def test_orders_can_be_paused(self):
        self.update_site(orders_paused=True, pause_message='Не успеваем')
        r = self.place_order()
        self.assertNoOrder(r)
        self.assertContains(r, 'Не успеваем')

    def test_unavailable_product_blocks_the_order(self):
        self.rose.in_stock = False
        self.rose.save()
        r = self.place_order()
        self.assertNoOrder(r)
        self.assertContains(r, 'нет в наличии')

    def test_minimum_order(self):
        self.update_site(min_order=5000)
        self.assertNoOrder(self.place_order())

    def test_musical_card_needs_a_song(self):
        key = f'addon_{self.music.pk}'
        self.assertNoOrder(self.place_order(**{key: 'on'}), f'{key}_note')

    def test_closed_day_and_daily_limit(self):
        SpecialDay.objects.create(date=TOMORROW, is_closed=True)
        self.assertNoOrder(self.place_order(date=TOMORROW.isoformat(), time_slot='10:00', payment_method='transfer'), 'date')
        SpecialDay.objects.all().delete()
        self.update_site(daily_order_limit=1)
        self.place_order(date=TOMORROW.isoformat(), time_slot='10:00', payment_method='transfer')
        self.assertEqual(Order.objects.count(), 1)
        self.add_to_cart()
        r = self.place_order(date=TOMORROW.isoformat(), time_slot='10:30', payment_method='transfer')
        self.assertEqual((r.status_code, Order.objects.count()), (200, 1))
        self.assertIn('date', r.context['form'].errors)

    def test_empty_cart_redirects_to_catalog(self):
        self.place_order()
        r = self.place_order()
        self.assertRedirects(r, reverse('shop:catalog'))
        self.assertEqual(Order.objects.count(), 1)

    def test_order_attempts_are_limited(self):
        for _ in range(10):
            self.place_order(phone='1')
        r = self.place_order()
        self.assertContains(r, 'Слишком много заказов')
        self.assertFalse(Order.objects.exists())

    # ───────── страницы и подсказки ─────────
    def test_checkout_page_opens_with_defaults(self):
        r = self.client.get(reverse('shop:checkout'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['method'], 'pickup')
        self.assertEqual(r.context['day'], TODAY)
        self.assertEqual(r.context['slot_options'][0]['value'], 'asap')
        self.assertContains(r, 'Выхино')

    def test_state_endpoint_for_future_delivery(self):
        r = self.client.get(reverse('shop:checkout_state'), {'method': 'delivery', 'date': TOMORROW.isoformat(), 'addons': self.music.pk})
        data = r.json()
        self.assertEqual(data['slots'][0], {'value': '09:00-11:00', 'label': '09:00–11:00'})
        self.assertTrue(data['prepay'])
        self.assertEqual([p['value'] for p in data['payments']], ['transfer'])
        self.assertEqual(data['total'], 1990 + 300 + 300)
        self.assertIn('Доставка', data['summary'])

    def test_state_endpoint_reports_closed_day(self):
        SpecialDay.objects.create(date=TOMORROW, is_closed=True, note='Выходной')
        data = self.client.get(reverse('shop:checkout_state'), {'method': 'pickup', 'date': TOMORROW.isoformat()}).json()
        self.assertEqual((data['problem'], data['slots']), ('Выходной', []))

    def test_logged_in_user_gets_prefilled_form_and_order_is_linked(self):
        user = get_user_model().objects.create_user('anna@example.com', 'anna@example.com', 'Strong-pass-123', first_name='Анна')
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('shop:checkout')), 'value="Анна"')
        self.place_order()
        self.assertEqual(Order.objects.get().user, user)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.phone, '+79175494941')

    def test_order_page_is_private(self):
        self.place_order()
        order = Order.objects.get()
        r = self.client.get(order.get_absolute_url())
        self.assertContains(r, 'Заказ №')
        self.assertEqual(r['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(self.client.get(reverse('shop:order_status', args=['no-such-token'])).status_code, 404)

    def test_traffic_source_is_remembered(self):
        self.client.get('/?utm_source=Telegram')
        self.place_order()
        self.assertEqual(Order.objects.get().source, 'telegram')

    # ───────── уведомления ─────────
    @override_settings(TELEGRAM_BOT_TOKEN='TOKEN', TELEGRAM_CHAT_ID='111, 222', ORDER_NOTIFY_EMAILS=['boss@example.com'])
    def test_notifications_are_sent_and_user_input_is_escaped(self):
        with mock.patch('shop.notifications._post_json') as post, self.captureOnCommitCallbacks(execute=True):
            self.place_order(name='<b>Хакер</b>', email='anna@example.com', card_text='Любимой & дорогой')
        self.assertEqual(post.call_count, 2)  # два чата
        url, payload = post.call_args_list[0].args
        self.assertIn('/botTOKEN/sendMessage', url)
        self.assertIn('Новый заказ №', payload['text'])
        self.assertIn('&lt;b&gt;Хакер&lt;/b&gt;', payload['text'])
        self.assertIn('Любимой &amp; дорогой', payload['text'])
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({m.to[0] for m in mail.outbox}, {'boss@example.com', 'anna@example.com'})

    @override_settings(TELEGRAM_BOT_TOKEN='TOKEN', TELEGRAM_CHAT_ID='111')
    def test_failed_notification_never_breaks_the_order(self):
        with mock.patch('shop.notifications._post_json', side_effect=OSError('нет сети')), self.captureOnCommitCallbacks(execute=True):
            r = self.place_order()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)

    @override_settings(ORDER_WEBHOOK_URL='https://hooks.example/order')
    def test_webhook_gets_order_json(self):
        with mock.patch('shop.notifications._post_json') as post, self.captureOnCommitCallbacks(execute=True):
            self.place_order()
        url, payload = post.call_args.args
        self.assertEqual((url, payload['event'], payload['total']), ('https://hooks.example/order', 'order.created', 1990))
        self.assertEqual(payload['items'][0]['name'], 'Классика')

    def test_staff_text_mentions_song_and_prepay(self):
        key = f'addon_{self.music.pk}'
        self.place_order(date=TOMORROW.isoformat(), time_slot='10:00', payment_method='transfer', **{key: 'on', f'{key}_note': 'Земфира'})
        text = notifications.staff_text(Order.objects.get())
        self.assertIn('🎵 Музыкальная открытка: Земфира', text)
        self.assertIn('нужна предоплата', text)


class LegalAcceptanceTests(ShopTestCase):
    def test_order_records_offer_and_personal_data_with_version(self):
        self.add_to_cart()
        self.place_order()
        order = Order.objects.get()
        events = LegalAcceptance.objects.all()
        self.assertEqual({e.kind for e in events}, {'offer', 'personal'})
        self.assertTrue(all(e.version == DOCUMENT_VERSION and e.reference == f'order:{order.pk}' for e in events))
        self.assertTrue(all(e.contact == order.phone and e.ip_address for e in events))

    def test_marketing_is_separate_and_optional(self):
        self.add_to_cart()
        self.place_order()
        self.assertFalse(LegalAcceptance.objects.filter(kind='marketing').exists())
        self.add_to_cart()
        self.place_order(marketing_consent='on')
        event = LegalAcceptance.objects.get(kind='marketing')
        order = Order.objects.order_by('-pk').first()
        self.assertEqual((event.action, event.reference), ('accepted', f'order:{order.pk}'))

    def test_lead_records_personal_data_acceptance(self):
        self.client.post(reverse('shop:offices'), {'name': 'Ольга', 'phone': '8 900 111-22-33', 'consent': 'on'})
        lead = Lead.objects.get()
        event = LegalAcceptance.objects.get(kind='personal')
        self.assertEqual((event.reference, event.contact), (f'lead:{lead.pk}', lead.phone))
