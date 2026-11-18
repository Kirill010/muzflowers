from datetime import date, timedelta

from django.test import SimpleTestCase
from django.urls import reverse

from shop import utils
from shop.models import Addon, Category, Order, Product, PromoCode, SiteSettings, Variant
from shop.pricing import Line, build_quote

from .helpers import TODAY, ShopTestCase, freeze


class UtilsTests(SimpleTestCase):
    def test_phone_is_normalized(self):
        for raw in ('+7 917 549-49-41', '8 (917) 549-49-41', '9175494941', '7-917-549-49-41'):
            self.assertEqual(utils.normalize_phone(raw), '+79175494941')

    def test_bad_phone_is_rejected(self):
        for raw in ('', '12345', 'abc', '+7 917'):
            self.assertEqual(utils.normalize_phone(raw), '')

    def test_phone_is_formatted(self):
        self.assertEqual(utils.format_phone('+79175494941'), '+7 (917) 549-49-41')

    def test_plural(self):
        self.assertEqual([utils.plural_ru(n, 'букет', 'букета', 'букетов') for n in (1, 2, 5, 11, 21, 24, 111)],
                         ['букет', 'букета', 'букетов', 'букетов', 'букет', 'букета', 'букетов'])

    def test_slug_is_latin(self):
        self.assertEqual(utils.slugify_ru('Облако гортензий'), 'oblako-gortenziy')

    def test_rub_uses_non_breaking_spaces(self):
        self.assertEqual(utils.rub(11990), '11 990 ₽')


class CatalogModelTests(ShopTestCase):
    def test_slug_is_generated_and_unique(self):
        a = Product.objects.create(category=self.cat, name='Нежность', price=1000)
        b = Product.objects.create(category=self.cat, name='Нежность', price=1100)
        self.assertEqual(a.slug, 'nezhnost')
        self.assertEqual(b.slug, 'nezhnost-2')

    def test_season_range(self):
        tulips = Product.objects.create(category=self.cat, name='Тюльпаны', price=3990, season_from=2, season_to=5)
        self.assertFalse(tulips.in_season(date(2026, 11, 4)))
        self.assertTrue(tulips.in_season(date(2026, 3, 8)))
        self.assertIn('Сезон', tulips.unavailable_reason)

    def test_season_across_new_year(self):
        winter = Product.objects.create(category=self.cat, name='Зимний', price=100, season_from=11, season_to=2)
        self.assertTrue(winter.in_season(date(2026, 12, 31)))
        self.assertTrue(winter.in_season(date(2027, 1, 15)))
        self.assertFalse(winter.in_season(date(2026, 6, 1)))

    def test_out_of_stock_blocks_ordering(self):
        self.rose.in_stock = False
        self.rose.save()
        self.assertFalse(self.rose.is_orderable)

    def test_price_from_uses_cheapest_active_variant(self):
        Variant.objects.create(product=self.big, name='Большой', price=7000)
        Variant.objects.create(product=self.big, name='Малый', price=4000)
        Variant.objects.create(product=self.big, name='Скрытый', price=1000, is_active=False)
        product = Product.objects.prefetch_related('variants').get(pk=self.big.pk)
        self.assertEqual(product.price_from, 4000)
        self.assertTrue(product.has_choice)

    def test_discount_percent(self):
        self.rose.old_price = 2490
        self.assertEqual(self.rose.discount_percent, 20)

    def test_art_url_contains_all_parameters(self):
        self.assertEqual(self.rose.art_url, '/art/rose/7/fca8c0/e0587c.svg')

    def test_site_settings_is_single_and_cached(self):
        self.assertEqual(SiteSettings.objects.count(), 1)
        SiteSettings(pk=5, phone='+7 000').save()
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.load().phone, '+7 000')
        self.assertEqual(SiteSettings().hours_display, 'Ежедневно, 09:00–21:00')

    def test_order_set_status_marks_cash_order_paid_on_done(self):
        order = Order.objects.create(name='А', phone='+79175494941', date=TODAY, subtotal=100, total=100, status=Order.Status.READY)
        order.set_status(Order.Status.DONE)
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertIsNotNone(order.paid_at)

    def test_order_set_status_does_not_pay_prepaid_order(self):
        order = Order.objects.create(name='А', phone='+79175494941', date=TODAY, subtotal=100, total=100,
                                     payment_method=Order.Pay.TRANSFER, payment_status=Order.PayStatus.PENDING)
        order.set_status(Order.Status.DONE)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    def test_when_display(self):
        order = Order(name='А', date=TODAY, asap=True)
        self.assertEqual(order.when_display, 'сегодня, как можно скорее')


class PromoCodeTests(ShopTestCase):
    def test_code_is_uppercased_and_percent_capped(self):
        promo = PromoCode.objects.create(code=' muz10 ', value=95)
        self.assertEqual((promo.code, promo.value), ('MUZ10', 90))

    def test_percent_discount(self):
        self.assertEqual(PromoCode(kind='percent', value=10).discount_for(1990), 199)

    def test_fixed_discount_never_exceeds_subtotal(self):
        self.assertEqual(PromoCode(kind='fixed', value=500).discount_for(300), 300)

    def test_rules(self):
        promo = PromoCode.objects.create(code='A', value=10, min_order=1000, valid_until=TODAY, usage_limit=1)
        self.assertEqual(promo.problem(1500), '')
        self.assertIn('от 1000', promo.problem(500))
        self.assertIn('закончился', promo.problem(1500, TODAY + timedelta(days=1)))
        promo.used_count = 1
        self.assertIn('использован', promo.problem(1500))
        promo.is_active, promo.used_count = False, 0
        self.assertIn('не действует', promo.problem(1500))

    def test_not_yet_valid(self):
        promo = PromoCode(code='B', value=5, valid_from=TODAY + timedelta(days=3))
        self.assertIn('заработает', promo.problem(1000))


class PricingTests(ShopTestCase):
    def lines(self, *pairs):
        return [Line(key=str(p.pk), product=p, variant=None, qty=q) for p, q in pairs]

    def test_pickup_has_no_delivery_cost(self):
        q = build_quote(self.lines((self.rose, 1)), [], method='pickup')
        self.assertEqual((q.subtotal, q.delivery, q.total), (1990, 0, 1990))

    def test_small_delivery_order_pays_delivery(self):
        q = build_quote(self.lines((self.rose, 1)), [], method='delivery')
        self.assertEqual((q.delivery, q.total), (300, 2290))

    def test_delivery_is_free_from_threshold(self):
        q = build_quote(self.lines((self.rose, 2)), [], method='delivery')  # 3980 >= 3000
        self.assertEqual((q.delivery, q.total, q.free_left), (0, 3980, 0))

    def test_discount_applies_before_threshold(self):
        PromoCode.objects.create(code='HALF', value=50)
        q = build_quote(self.lines((self.rose, 2)), [], 'half', method='delivery')  # 3980 - 1990 = 1990 < 3000
        self.assertEqual((q.discount, q.delivery, q.total), (1990, 300, 2290))

    def test_addons_are_added_once(self):
        q = build_quote(self.lines((self.rose, 1)), [(self.music, 'Песня')], method='pickup')
        self.assertEqual((q.addons_total, q.total), (300, 2290))

    def test_unknown_promo_reports_error(self):
        q = build_quote(self.lines((self.rose, 1)), [], 'NOPE', method='pickup')
        self.assertEqual((q.discount, q.promo), (0, None))
        self.assertIn('нет', q.promo_error)

    def test_free_delivery_progress(self):
        q = build_quote(self.lines((self.rose, 1)), [], method='pickup')
        self.assertEqual((q.free_left, q.free_progress), (1010, 66))

    def test_problems_for_unavailable_product_and_min_order(self):
        self.update_site(min_order=3000)
        self.rose.in_stock = False
        q = build_quote(self.lines((self.rose, 1)), [], method='pickup')
        self.assertEqual(len(q.problems), 2)

    def test_delivery_disabled_is_a_problem(self):
        self.update_site(delivery_enabled=False)
        q = build_quote(self.lines((self.rose, 1)), [], method='delivery')
        self.assertTrue(any('Доставка' in p for p in q.problems))


class CartTests(ShopTestCase):
    def test_add_twice_increases_quantity(self):
        self.add_to_cart()
        r = self.add_to_cart()
        self.assertTrue(r.json()['ok'])
        self.assertEqual(r.json()['count'], 2)
        self.assertIn('Классика', r.json()['html'])

    def test_quantity_is_capped(self):
        self.add_to_cart(qty=500)
        self.assertEqual(self.client.get(reverse('shop:cart_fragment')).status_code, 200)
        self.assertEqual(self.client.session['mz_cart']['items'], {f'{self.rose.pk}:0': 50})

    def test_unknown_product(self):
        r = self.client.post(reverse('shop:cart_add'), {'product': 999}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.status_code, 404)

    def test_out_of_stock_product_cannot_be_added(self):
        self.rose.in_stock = False
        self.rose.save()
        r = self.add_to_cart()
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()['ok'])
        self.assertEqual(r.json()['count'], 0)

    def test_variant_is_required_when_product_has_variants(self):
        small = Variant.objects.create(product=self.big, name='Малый', price=4000, order=1)
        Variant.objects.create(product=self.big, name='Большой', price=7000, order=2)
        self.add_to_cart(self.big, variant=999)  # чужой номер → берём первый размер
        self.assertEqual(list(self.client.session['mz_cart']['items']), [f'{self.big.pk}:{small.pk}'])
        self.assertEqual(self.client.get(reverse('shop:cart')).context['cart_quote'].subtotal, 4000)

    def test_update_and_remove(self):
        self.add_to_cart(qty=3)
        key = f'{self.rose.pk}:0'
        r = self.client.post(reverse('shop:cart_update'), {'key': key, 'qty': 1}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.json()['count'], 1)
        r = self.client.post(reverse('shop:cart_remove'), {'key': key}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.json()['count'], 0)
        self.assertIn('пусто', r.json()['html'])

    def test_addon_toggle_and_note(self):
        self.add_to_cart()
        r = self.client.post(reverse('shop:cart_addon'), {'addon': self.music.pk, 'on': '1', 'note': 'Земфира'}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.json()['total'], 2290)
        self.assertEqual(self.client.session['mz_cart']['addons'], {str(self.music.pk): 'Земфира'})
        r = self.client.post(reverse('shop:cart_addon'), {'addon': self.music.pk, 'on': '0'}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.json()['total'], 1990)

    def test_add_with_addon_from_product_page(self):
        self.add_to_cart(addon=self.music.pk)
        self.assertIn(str(self.music.pk), self.client.session['mz_cart']['addons'])

    def test_promo_apply_and_clear(self):
        PromoCode.objects.create(code='MUZ10', value=10)
        self.add_to_cart()
        r = self.client.post(reverse('shop:cart_promo'), {'code': 'muz10'}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual((r.json()['ok'], r.json()['total']), (True, 1791))
        r = self.client.post(reverse('shop:cart_promo'), {'code': ''}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.json()['total'], 1990)

    def test_wrong_promo_is_not_stored(self):
        self.add_to_cart()
        r = self.client.post(reverse('shop:cart_promo'), {'code': 'NOPE'}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.session['mz_cart']['promo'], '')

    def test_promo_attempts_are_limited(self):
        for _ in range(15):
            self.client.post(reverse('shop:cart_promo'), {'code': 'X'}, headers={'X-Requested-With': 'fetch'})
        r = self.client.post(reverse('shop:cart_promo'), {'code': 'X'}, headers={'X-Requested-With': 'fetch'})
        self.assertEqual(r.status_code, 429)

    def test_without_javascript_redirects_back_safely(self):
        r = self.client.post(reverse('shop:cart_add'), {'product': self.rose.pk, 'next': '/catalog/'})
        self.assertRedirects(r, '/catalog/', fetch_redirect_response=False)
        r = self.client.post(reverse('shop:cart_add'), {'product': self.rose.pk, 'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('shop:cart'), fetch_redirect_response=False)

    def test_deleted_product_disappears_from_cart(self):
        self.add_to_cart()
        self.rose.is_active = False
        self.rose.save()
        self.assertEqual(self.client.get(reverse('shop:cart')).context['cart_quote'].count, 0)

    def test_cart_page_and_fragment(self):
        self.add_to_cart()
        self.assertContains(self.client.get(reverse('shop:cart')), 'Оформить заказ')
        self.assertIn('Классика', self.client.get(reverse('shop:cart_fragment')).json()['html'])

    def test_get_is_not_allowed_for_mutations(self):
        self.assertEqual(self.client.get(reverse('shop:cart_add')).status_code, 405)
