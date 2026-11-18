from datetime import datetime, timedelta

from django.utils import timezone

from shop import slots
from shop.models import Order, SpecialDay

from .helpers import TODAY, TOMORROW, ShopTestCase


def at(hour, minute=0):
    return timezone.make_aware(datetime(2026, 11, 4, hour, minute))


class SlotTests(ShopTestCase):
    def make_order(self, day, status=Order.Status.NEW):
        return Order.objects.create(name='А', phone='+79175494941', date=day, subtotal=1, total=1, status=status)

    def test_pickup_today_offers_asap_and_half_hours(self):
        values = [o['value'] for o in slots.time_options(TODAY, 'pickup')]
        self.assertEqual(values[0], 'asap')
        self.assertEqual(values[1], '12:30')  # сейчас 12:00 + 20 минут на сборку
        self.assertEqual(values[-1], '20:30')  # закрываемся в 21:00

    def test_asap_not_offered_before_opening(self):
        values = [o['value'] for o in slots.time_options(TODAY, 'pickup', now=at(6))]
        self.assertNotIn('asap', values)
        self.assertEqual(values[0], '09:00')

    def test_nothing_left_late_in_the_evening(self):
        self.assertEqual(slots.time_options(TODAY, 'pickup', now=at(20, 50)), [])
        self.assertIn('не успеваем', slots.day_problem(TODAY, 'pickup', now=at(20, 50)))

    def test_future_day_has_full_grid(self):
        values = [o['value'] for o in slots.time_options(TOMORROW, 'pickup')]
        self.assertEqual((values[0], values[-1], len(values)), ('09:00', '20:30', 24))

    def test_delivery_windows(self):
        values = [o['value'] for o in slots.time_options(TOMORROW, 'delivery')]
        self.assertEqual(values, ['09:00-11:00', '11:00-13:00', '13:00-15:00', '15:00-17:00', '17:00-19:00', '19:00-21:00'])

    def test_delivery_today_respects_lead_time(self):
        values = [o['value'] for o in slots.time_options(TODAY, 'delivery')]
        self.assertEqual(values[0], '15:00-17:00')  # первое окно после 14:00

    def test_closed_special_day(self):
        SpecialDay.objects.create(date=TOMORROW, is_closed=True, note='Выходной')
        self.assertEqual(slots.day_problem(TOMORROW), 'Выходной')
        self.assertIn(TOMORROW.isoformat(), slots.unavailable_dates())

    def test_daily_limit(self):
        self.update_site(daily_order_limit=1)
        self.assertEqual(slots.day_problem(TOMORROW), '')
        self.make_order(TOMORROW)
        self.assertIn('разобраны', slots.day_problem(TOMORROW))
        self.assertIn(TOMORROW.isoformat(), slots.unavailable_dates())

    def test_canceled_orders_do_not_count(self):
        self.update_site(daily_order_limit=1)
        self.make_order(TOMORROW, Order.Status.CANCELED)
        self.assertEqual(slots.day_problem(TOMORROW), '')

    def test_special_day_limit_overrides_default(self):
        self.update_site(daily_order_limit=1)
        SpecialDay.objects.create(date=TOMORROW, limit=0, note='Без ограничений')
        self.make_order(TOMORROW)
        self.assertEqual(slots.day_problem(TOMORROW), '')

    def test_past_and_too_far(self):
        self.assertIn('прошла', slots.day_problem(TODAY - timedelta(days=1)))
        self.assertIn('вперёд', slots.day_problem(TODAY + timedelta(days=61)))
        self.assertEqual(slots.day_problem(TODAY + timedelta(days=60)), '')

    def test_pick_option(self):
        self.assertEqual(slots.pick_option(TOMORROW, 'pickup', '10:00')['time_from'].hour, 10)
        self.assertIsNone(slots.pick_option(TOMORROW, 'pickup', '03:00'))
        self.assertIsNone(slots.pick_option(TODAY, 'pickup', '09:00'))  # это время уже прошло
        self.assertTrue(slots.pick_option(TODAY, 'pickup', 'asap')['asap'])
