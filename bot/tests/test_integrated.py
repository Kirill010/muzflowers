from __future__ import annotations

import unittest
from datetime import date, timedelta

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from flowerbot.integrated_handlers import IntegratedContext, router
from flowerbot.integrated_store import IntegratedStore
from flowerbot.middlewares import Throttle, UserMiddleware
from flowerbot.util import rub

from .harness import Harness
from .helpers import ADMIN, CUSTOMER, OTHER


class FakeShopAPI:
    def __init__(self):
        self.calls = []
        self.orders = []
        self.stock = True

    async def post(self, endpoint, data, *, idempotency_key=''):
        self.calls.append((endpoint, data, idempotency_key))
        if endpoint == 'bootstrap':
            return {'ok': True, 'shop': {
                'name': 'MuzFlowers', 'phone': '+7 (995) 152-21-31', 'email': 'muzflowers@ya.ru', 'hours': '09:00–21:00',
                'address': 'Вешняковская, 39Г', 'shop_id': 1, 'map_url': 'https://yandex.ru/maps/org/test/',
                'reviews_url': '', 'telegram': 'https://t.me/muzflowers', 'max_url': 'https://web.max.ru/test',
                'delivery_enabled': True, 'delivery_cost': 300, 'free_delivery_from': 3000,
                'pickup_discount_percent': 10, 'delivery_lead_minutes': 60, 'pickup_lead_minutes': 20,
                'max_days_ahead': 60, 'online_payment': True, 'consent_url': 'https://shop.example/consent/',
                'offer_url': 'https://shop.example/offer/', 'certificate_amounts': [1000, 3000, 5000],
                'certificate_min': 500, 'certificate_max': 30000,
            }, 'products': [
                {'id': 1, 'name': 'Мини', 'tagline': '3 розы', 'description': '', 'price': 3000, 'variants': [],
                 'available': True, 'in_stock': self.stock, 'unavailable_reason': '', 'illustration': True, 'image': '/art.svg'},
                {'id': 2, 'name': 'Классика', 'tagline': '7 роз', 'description': '', 'price': 5000,
                 'variants': [{'id': 10, 'name': 'Стандарт', 'price': 5000}, {'id': 11, 'name': 'Большой', 'price': 7000}],
                 'available': True, 'in_stock': True, 'unavailable_reason': '', 'illustration': True, 'image': '/art.svg'},
            ], 'addons': [{'id': 5, 'name': 'Музыкальная открытка', 'description': '', 'price': 300,
                           'note_label': 'Какая песня?', 'note_required': True, 'is_music': True}]}
        if endpoint == 'quote':
            subtotal = 0
            for line in data.get('lines', []):
                price = 3000 if line['product'] == 1 else 5000 if line['variant'] == 10 else 7000
                subtotal += price * line['qty']
            addons = sum(300 for _ in data.get('addons', []))
            discount = subtotal // 10 if data.get('receive_method') == 'pickup' else 0
            delivery = 300 if data.get('receive_method') == 'delivery' and subtotal - discount < 3000 else 0
            certificate = min(1000, subtotal - discount + addons + delivery) if data.get('certificate_code') else 0
            total = subtotal - discount + addons + delivery - certificate
            return {'ok': True, 'subtotal': subtotal, 'discount': discount, 'addons_total': addons,
                    'delivery': delivery, 'certificate_amount': certificate, 'total': total,
                    'problems': [], 'promo_error': '', 'certificate_error': '', 'free_left': 0,
                    'payment_methods': [{'value': 'on_receipt', 'label': 'При получении'}] if total else
                    [{'value': 'certificate', 'label': 'Сертификатом'}]}
        if endpoint == 'availability':
            return {'ok': True, 'problem': '', 'date': data['date'], 'prepay': False,
                    'options': [{'value': 'asap', 'label': 'Как можно скорее'}]}
        if endpoint == 'orders':
            order = self.make_order(data, len(self.orders) + 1)
            self.orders.append(order)
            return {**order, 'ok': True, 'payment_error': ''}
        if endpoint == 'orders/list':
            return {'ok': True, 'orders': self.orders}
        if endpoint in ('orders/detail', 'orders/cancel'):
            order = next(item for item in self.orders if item['id'] == data['order'])
            if endpoint == 'orders/cancel':
                order['status'] = 'canceled'
            return {'ok': True, 'order': order}
        if endpoint == 'orders/payment':
            order = next(item for item in self.orders if item['id'] == data['order'])
            return {'ok': True, 'order': order}
        if endpoint == 'certificates/purchase':
            order = self.make_order({'receive_method': 'pickup', 'date': date.today().isoformat(), 'time_slot': 'asap',
                                     'lines': [], 'payment_method': 'online', 'name': data['name'], 'phone': data['phone']},
                                    len(self.orders) + 1, total=data['amount'], kind='certificate')
            self.orders.append(order)
            return {'ok': True, 'order': order}
        if endpoint == 'certificates/check':
            return {'ok': True, 'certificate': {'code': 'AAAA-BBBB-CCCC', 'amount': 1000, 'balance': 1000,
                                                'status': 'active', 'expires_at': '2027-01-01'}}
        if endpoint == 'certificates/list':
            return {'ok': True, 'certificates': []}
        if endpoint == 'leads':
            return {'ok': True, 'lead': 1}
        if endpoint == 'reviews/list':
            return {'ok': True, 'reviews': []}
        if endpoint == 'reviews':
            return {'ok': True, 'message': 'Спасибо! Отзыв на проверке.'}
        if endpoint == 'staff/orders':
            return {'ok': True, 'orders': self.orders}
        if endpoint == 'staff/stock':
            self.stock = data['in_stock']
            return {'ok': True}
        if endpoint in ('staff/status', 'staff/paid'):
            return {'ok': True}
        raise AssertionError(endpoint)

    @staticmethod
    def make_order(data, order_id, total=None, kind='products'):
        total = 0 if total is None else total
        return {'id': order_id, 'kind': kind, 'status': 'new', 'payment_method': data['payment_method'],
                'payment_status': 'unpaid' if data['payment_method'] == 'on_receipt' else 'pending',
                'name': data.get('name', ''), 'phone': data.get('phone', ''), 'date': data['date'], 'time': data.get('time_slot', ''),
                'method': data['receive_method'], 'address': 'Вешняковская, 39Г', 'subtotal': total,
                'discount': 0, 'addons_total': 0, 'delivery': 0, 'certificate_amount': 0, 'total': total,
                'pay_url': 'https://bank.example/pay' if data['payment_method'] == 'online' else '',
                'items': [{'name': 'Букет', 'qty': line['qty'], 'price': 3000, 'product_id': line['product'],
                           'variant_id': line['variant']} for line in data.get('lines', [])],
                'addons': [], 'delivery_photo': '', 'certificate': None, 'token': 'secret', 'url': 'https://shop.example/order/1'}


class IntegratedHarness(Harness):
    def __init__(self):
        super().__init__()
        self.api = FakeShopAPI()
        self.store = IntegratedStore(self.db)
        self.ictx = IntegratedContext(settings=self.ctx.settings, db=self.db, client=self.api, store=self.store)
        router._parent_router = None
        self.dp = Dispatcher(storage=MemoryStorage())
        self.dp['ctx'] = self.ictx
        for observer in (self.dp.message, self.dp.callback_query):
            observer.outer_middleware(Throttle(limit=10 ** 6))
            observer.outer_middleware(UserMiddleware())
        self.dp.include_router(router)

    def last_text(self, calls=None):
        return super().last_text(self.session.calls if calls is None else calls)


class IntegratedTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.h = IntegratedHarness()
        self.addCleanup(self.h.close)

    async def add_mini(self):
        await self.h.say(CUSTOMER, '🌸 Каталог')
        await self.h.press(CUSTOMER, 'Мини', prefix=True)
        await self.h.press(CUSTOMER, '🛒 Добавить в корзину')


class StartCatalogTests(IntegratedTestCase):
    async def test_start_is_vykhino(self):
        text = self.h.last_text(await self.h.say(CUSTOMER, '/start'))
        self.assertIn('Выхино', text)
        self.assertIn('те же цены', text)

    async def test_variant_and_cart_stay_with_customer_not_callback_bot(self):
        await self.h.say(CUSTOMER, '🌸 Каталог')
        await self.h.press(CUSTOMER, 'Классика', prefix=True)
        await self.h.press(CUSTOMER, 'Большой')
        await self.h.press(CUSTOMER, '🛒 Добавить в корзину')
        self.assertEqual(self.h.store.cart(CUSTOMER)['lines'][0]['variant'], 11)
        self.assertEqual(self.h.store.cart(999)['lines'], [])
        self.assertIn(rub(7000), self.h.last_text())

    async def test_addon_note_and_certificate_are_shared_payload(self):
        await self.add_mini()
        await self.h.press(CUSTOMER, '🎵 Дополнения')
        await self.h.press(CUSTOMER, '➕ Музыкальная открытка')
        await self.h.say(CUSTOMER, 'Земфира — Хочешь?')
        await self.h.press(CUSTOMER, '🏷 Промокод / сертификат')
        await self.h.say(CUSTOMER, 'AAAA-BBBB-CCCC')
        cart = self.h.store.cart(CUSTOMER)
        self.assertEqual(cart['addons'][0]['note'], 'Земфира — Хочешь?')
        self.assertEqual(cart['certificate_code'], 'AAAA-BBBB-CCCC')
        self.assertIn('Сертификат', self.h.last_text())


class CheckoutTests(IntegratedTestCase):
    async def finish_checkout(self):
        await self.add_mini()
        await self.h.press(CUSTOMER, '✅ Оформить заказ')
        await self.h.contact(CUSTOMER, '+79175494941', first_name='Анна')
        await self.h.press(CUSTOMER, '🛍 Самовывоз')
        await self.h.press(CUSTOMER, 'Сегодня')
        await self.h.press(CUSTOMER, 'Как можно скорее')
        await self.h.press(CUSTOMER, '✅ Прочитал(а) и принимаю')
        await self.h.press(CUSTOMER, 'При получении')

    async def test_complete_order_uses_user_consents_and_idempotency(self):
        await self.finish_checkout()
        created = [call for call in self.h.api.calls if call[0] == 'orders']
        self.assertEqual(len(created), 1)
        _, payload, key = created[0]
        self.assertEqual(payload['telegram_user_id'], CUSTOMER)
        self.assertTrue(payload['consent_pd'] and payload['consent_offer'])
        self.assertEqual(payload['shop'], 1)
        self.assertTrue(key)
        self.assertEqual(self.h.store.cart(CUSTOMER)['lines'], [])
        self.assertIn('Заказ №1 принят', self.h.last_text())

    async def test_second_pay_click_does_not_duplicate(self):
        await self.finish_checkout()
        before = len([call for call in self.h.api.calls if call[0] == 'orders'])
        await self.h.tap(CUSTOMER, 'pay:on_receipt')
        after = len([call for call in self.h.api.calls if call[0] == 'orders'])
        self.assertEqual((before, after), (1, 1))

    async def test_orders_are_listed_and_can_repeat(self):
        await self.finish_checkout()
        await self.h.say(CUSTOMER, '🧾 Мои заказы')
        self.assertIn('Ваши заказы', self.h.last_text())
        await self.h.press(CUSTOMER, '№1', prefix=True)
        self.assertIn('Заказ №1', self.h.last_text())
        await self.h.press(CUSTOMER, '🔁 Повторить')
        self.assertEqual(len(self.h.store.cart(CUSTOMER)['lines']), 1)


class CertificatesAndStaffTests(IntegratedTestCase):
    async def test_certificate_purchase_uses_same_order_api(self):
        self.h.store.save_contact(CUSTOMER, 'Анна', '+79175494941')
        await self.h.say(CUSTOMER, '🎁 Сертификат')
        await self.h.press(CUSTOMER, rub(3000))
        await self.h.press(CUSTOMER, '✅ Принимаю', prefix=True)
        purchase = [call for call in self.h.api.calls if call[0] == 'certificates/purchase']
        self.assertEqual(len(purchase), 1)
        self.assertEqual(purchase[0][1]['amount'], 3000)
        self.assertTrue(purchase[0][1]['consent_pd'])

    async def test_certificate_can_be_bought_without_previous_contact(self):
        await self.h.say(CUSTOMER, '🎁 Сертификат')
        await self.h.press(CUSTOMER, rub(3000))
        await self.h.press(CUSTOMER, '✅ Принимаю', prefix=True)
        await self.h.contact(CUSTOMER, '+79175494941', first_name='Анна')
        purchase = [call for call in self.h.api.calls if call[0] == 'certificates/purchase']
        self.assertEqual(len(purchase), 1)
        self.assertEqual(purchase[0][1]['phone'], '+79175494941')

    async def test_customer_cannot_use_staff_panel_but_admin_can_change_stock(self):
        await self.h.say(OTHER, '👑 Панель')
        self.assertIn('только сотрудникам', self.h.last_text())
        await self.h.say(ADMIN, '👑 Панель')
        await self.h.press(ADMIN, '📦 Наличие')
        await self.h.press(ADMIN, '✅ Мини')
        self.assertFalse(self.h.api.stock)

    async def test_manager_creates_lead(self):
        self.h.store.save_contact(CUSTOMER, 'Анна', '+79175494941')
        await self.h.say(CUSTOMER, '💬 Менеджер')
        await self.h.say(CUSTOMER, 'Есть ли белые розы?')
        leads = [call for call in self.h.api.calls if call[0] == 'leads']
        self.assertEqual(leads[0][1]['message'], 'Есть ли белые розы?')
        self.assertIn('передано менеджеру', self.h.last_text())
