import csv
import io
import shutil
import tempfile
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from shop.models import Order, OrderAddon, OrderItem, Product, ProductImage, SiteSettings, Variant
from shop.thumbs import process_upload, thumb_url

from .helpers import TODAY, TOMORROW, ShopTestCase

User = get_user_model()


class AdminTestCase(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_superuser('owner@example.com', 'owner@example.com', 'Strong-pass-123')
        self.client.force_login(self.owner)
        self.order = Order.objects.create(name='Анна', phone='+79175494941', date=TODAY, asap=True, subtotal=1990, total=2290, addons_total=300,
                                          receive_method='pickup', shop=self.shop, card_text='Люблю', comment='Позвоните')
        OrderItem.objects.create(order=self.order, product=self.rose, name='Классика', price=1990, qty=1)
        OrderAddon.objects.create(order=self.order, addon=self.music, name='Музыкальная открытка', price=300, note='Земфира — Хочешь?')


class DashboardTests(AdminTestCase):
    def test_dashboard_shows_today_and_buttons(self):
        r = self.client.get(reverse('admin:index'))
        self.assertContains(r, 'Что сегодня?')
        self.assertContains(r, 'Анна')
        self.assertContains(r, 'Подтвердить')
        self.assertContains(r, 'Земфира')
        self.assertEqual(len(r.context['board_today']), 1)

    def test_dashboard_lists_later_orders_and_new_orders_on_other_dates(self):
        later = Order.objects.create(name='Борис', phone='+79000000000', date=TODAY + timedelta(days=5), subtotal=1, total=1,
                                     status=Order.Status.CONFIRMED)
        fresh = Order.objects.create(name='Вера', phone='+79000000001', date=TODAY + timedelta(days=3), subtotal=1, total=1)
        r = self.client.get(reverse('admin:index'))
        self.assertEqual([row['order'] for row in r.context['board_later']], [later])
        self.assertEqual([row['order'] for row in r.context['new_rows']], [fresh])

    def test_checklist_reports_missing_things(self):
        titles = {item['title']: item['ok'] for item in self.client.get(reverse('admin:index')).context['checklist']}
        self.assertFalse(titles['Реквизиты продавца'])
        self.assertTrue(titles['Адрес точки самовывоза'])
        self.assertFalse(titles['Фото букетов'])
        self.update_site(legal_name='ИП Иванов', inn='770000000000', payment_details='СБП +7 900')
        titles = {item['title']: item['ok'] for item in self.client.get(reverse('admin:index')).context['checklist']}
        self.assertTrue(titles['Реквизиты продавца'])
        self.assertTrue(titles['Как принимать предоплату'])

    def test_login_page_offers_first_run_setup_when_there_is_no_owner(self):
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('admin:login')), 'Создать владельца')
        User.objects.all().delete()
        self.assertContains(self.client.get(reverse('admin:login')), 'Создать владельца')

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        for url in (reverse('admin:index'), reverse('admin:shop_order_print', args=[self.order.pk])):
            self.assertEqual(self.client.get(url).status_code, 302)


class QuickActionTests(AdminTestCase):
    def post_status(self, to, pk=None):
        return self.client.post(reverse('admin:shop_order_status', args=[pk or self.order.pk]), {'to': to, 'next': reverse('admin:index')})

    def test_status_buttons_walk_through_the_flow(self):
        for status in ('confirmed', 'ready', 'done'):
            r = self.post_status(status)
            self.assertRedirects(r, reverse('admin:index'), fetch_redirect_response=False)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, status)
        self.assertTrue(self.order.is_paid)  # оплата при получении засчитана при выдаче

    def test_unknown_status_and_get_are_rejected(self):
        self.assertEqual(self.post_status('weird').status_code, 404)
        self.assertEqual(self.client.get(reverse('admin:shop_order_status', args=[self.order.pk])).status_code, 405)

    def test_mark_paid(self):
        self.order.payment_method = 'transfer'
        self.order.save()
        self.client.post(reverse('admin:shop_order_paid', args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)

    def test_staff_without_permission_cannot_change_status(self):
        staff = User.objects.create_user('staff@example.com', 'staff@example.com', 'Strong-pass-123', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.post_status('confirmed').status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='change_order'))
        self.assertEqual(self.post_status('confirmed').status_code, 302)

    def test_redirect_target_is_validated(self):
        r = self.client.post(reverse('admin:shop_order_status', args=[self.order.pk]), {'to': 'ready', 'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('admin:index'), fetch_redirect_response=False)


class FloristGroupTests(AdminTestCase):
    def setUp(self):
        super().setUp()
        from django.core.management import call_command
        call_command('seed_shop', verbosity=0)
        self.florist = User.objects.create_user('flora@example.com', 'flora@example.com', 'Strong-pass-123', is_staff=True)
        self.florist.groups.add(__import__('django.contrib.auth.models', fromlist=['Group']).Group.objects.get(name='Флористы'))
        self.client.force_login(self.florist)

    def test_florist_sees_orders_and_can_move_them_along(self):
        self.assertContains(self.client.get(reverse('admin:index')), 'Анна')
        r = self.client.post(reverse('admin:shop_order_status', args=[self.order.pk]), {'to': 'confirmed'})
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'confirmed')

    def test_florist_can_mark_a_bouquet_as_out_of_stock(self):
        r = self.client.post(reverse('admin:shop_product_changelist'), {'action': 'set_out_of_stock', '_selected_action': [self.rose.pk]})
        self.assertEqual(r.status_code, 302)
        self.rose.refresh_from_db()
        self.assertFalse(self.rose.in_stock)

    def test_florist_cannot_touch_settings_promos_or_users(self):
        for name in ('shop_sitesettings_change', 'shop_promocode_add', 'auth_user_changelist', 'shop_addon_add', 'shop_specialday_add'):
            with self.subTest(page=name):
                args = [1] if name.endswith('change') else []
                self.assertEqual(self.client.get(reverse(f'admin:{name}', args=args)).status_code, 403)

    def test_seed_is_idempotent_and_keeps_the_owners_catalog(self):
        from django.core.management import call_command
        count = Product.objects.count()
        self.rose.name = 'Моя Классика'
        self.rose.save()
        call_command('seed_shop', verbosity=0)
        self.assertEqual(Product.objects.count(), count)
        self.assertTrue(Product.objects.filter(name='Моя Классика').exists())


class PrintTests(AdminTestCase):
    def test_slip(self):
        r = self.client.get(reverse('admin:shop_order_print', args=[self.order.pk]))
        for text in ('Заказ №', 'Классика', 'Земфира — Хочешь?', 'Люблю', 'как можно скорее'):
            self.assertContains(r, text)

    def test_slip_warns_about_missing_prepayment(self):
        self.order.prepay_required = True
        self.order.save()
        self.assertContains(self.client.get(reverse('admin:shop_order_print', args=[self.order.pk])), 'Предоплата ещё не получена')

    def test_many_by_date_and_by_ids(self):
        Order.objects.create(name='Борис', phone='+79000000000', date=TOMORROW, time_from=None, subtotal=1, total=1)
        r = self.client.get(reverse('admin:shop_order_print_many'), {'date': TOMORROW.isoformat()})
        self.assertContains(r, 'Борис')
        self.assertNotContains(r, 'Анна')
        r = self.client.get(reverse('admin:shop_order_print_many'), {'ids': f'{self.order.pk},999'})
        self.assertContains(r, 'Анна')

    def test_day_table(self):
        r = self.client.get(reverse('admin:shop_order_day'), {'date': TODAY.isoformat()})
        self.assertContains(r, 'Анна')
        self.assertContains(r, 'Итого')

    def test_card_has_text_and_song_link(self):
        r = self.client.get(reverse('admin:shop_order_card', args=[self.order.pk]))
        self.assertContains(r, 'Люблю')
        self.assertEqual(r.context['link'], 'https://music.yandex.ru/search?text=%D0%97%D0%B5%D0%BC%D1%84%D0%B8%D1%80%D0%B0%20%E2%80%94%20%D0%A5%D0%BE%D1%87%D0%B5%D1%88%D1%8C%3F')

    def test_card_uses_given_link_as_is(self):
        OrderAddon.objects.filter(order=self.order).update(note='https://example.com/track/1')
        self.assertEqual(self.client.get(reverse('admin:shop_order_card', args=[self.order.pk])).context['link'], 'https://example.com/track/1')


class ModelAdminTests(AdminTestCase):
    def test_every_registered_page_opens(self):
        for model, model_admin in admin.site._registry.items():
            opts = model._meta
            if opts.app_label not in ('shop', 'accounts', 'auth'):
                continue
            with self.subTest(model=opts.label):
                self.assertIn(self.client.get(reverse(f'admin:{opts.app_label}_{opts.model_name}_changelist')).status_code, (200, 302))
                self.assertIn(self.client.get(reverse(f'admin:{opts.app_label}_{opts.model_name}_add')).status_code, (200, 403))

    def test_change_pages(self):
        for url in (reverse('admin:shop_order_change', args=[self.order.pk]), reverse('admin:shop_product_change', args=[self.rose.pk]),
                    reverse('admin:shop_shop_change', args=[self.shop.pk]), reverse('admin:shop_addon_change', args=[self.music.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(reverse('admin:shop_order_change', args=[self.order.pk])), 'Бланк заказа')

    def test_site_settings_changelist_goes_straight_to_the_form(self):
        r = self.client.get(reverse('admin:shop_sitesettings_changelist'))
        self.assertRedirects(r, reverse('admin:shop_sitesettings_change', args=[1]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('admin:shop_sitesettings_add')).status_code, 403)

    def test_owner_can_edit_settings_and_site_reflects_it(self):
        form = {f: getattr(SiteSettings.load(), f) for f in ('shop_name', 'phone', 'email', 'telegram', 'yandex_maps_url', 'hours_text',
                                                              'pause_message', 'delivery_area_text', 'payment_details', 'announcement',
                                                              'legal_name', 'inn', 'ogrnip', 'legal_address', 'metrika_id')}
        form.update(phone='+7 (999) 111-22-33', delivery_cost=450, free_delivery_from=5000, min_order=0, pickup_lead_minutes=20,
                    delivery_lead_minutes=120, delivery_window_hours=2, max_days_ahead=60, daily_order_limit=0, open_time='09:00:00',
                    close_time='20:00:00', delivery_enabled='on', prepay_future_orders='on', allow_pay_on_receipt='on',
                    yandex_rating='4.6', yandex_votes='26')
        r = self.client.post(reverse('admin:shop_sitesettings_change', args=[1]), form)
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['adminform'].form.errors)
        page = self.client.get(reverse('shop:delivery'))
        self.assertContains(page, '450')
        self.assertContains(page, 'ежедневно, 09:00–20:00')

    def test_order_changelist_filters_and_search(self):
        url = reverse('admin:shop_order_changelist')
        self.assertContains(self.client.get(url, {'day': 'today'}), 'Анна')
        self.assertNotContains(self.client.get(url, {'day': 'tomorrow'}), 'Анна')
        self.assertContains(self.client.get(url, {'q': '+79175494941'}), 'Анна')
        self.assertNotContains(self.client.get(url, {'q': 'Несуществующий'}), 'Анна')

    def test_bulk_status_action(self):
        r = self.client.post(reverse('admin:shop_order_changelist'), {'action': 'mark_confirmed', '_selected_action': [self.order.pk]})
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'confirmed')

    def test_csv_export(self):
        r = self.client.post(reverse('admin:shop_order_changelist'), {'action': 'export_csv', '_selected_action': [self.order.pk]})
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8-sig')
        rows = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(rows[0][:3], ['№', 'Создан', 'Статус'])
        self.assertIn('Классика × 1', rows[1])
        self.assertIn('Музыкальная открытка: Земфира — Хочешь?', rows[1])

    def test_print_selected_action_redirects_to_slips(self):
        r = self.client.post(reverse('admin:shop_order_changelist'), {'action': 'print_selected', '_selected_action': [self.order.pk]})
        self.assertRedirects(r, f'{reverse("admin:shop_order_print_many")}?ids={self.order.pk}', fetch_redirect_response=False)

    def test_product_stock_actions_and_duplicate(self):
        url = reverse('admin:shop_product_changelist')
        Variant.objects.create(product=self.rose, name='Большой', price=3000)
        self.client.post(url, {'action': 'set_out_of_stock', '_selected_action': [self.rose.pk]})
        self.rose.refresh_from_db()
        self.assertFalse(self.rose.in_stock)
        self.client.post(url, {'action': 'duplicate', '_selected_action': [self.rose.pk]})
        copy = Product.objects.get(name='Классика (копия)')
        self.assertFalse(copy.is_active)
        self.assertEqual(copy.variants.count(), 1)
        self.assertNotEqual(copy.slug, self.rose.slug)


class PhotoTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        patch = override_settings(MEDIA_ROOT=self.media)
        patch.enable()
        self.addCleanup(patch.disable)

    def upload(self, size=(3000, 2000), orientation=None, name='photo.jpg'):
        buf = io.BytesIO()
        img = Image.new('RGB', size, (200, 80, 120))
        exif = Image.Exif()
        if orientation:
            exif[0x0112] = orientation
        img.save(buf, 'JPEG', exif=exif)
        return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')

    def test_big_photo_is_shrunk_on_upload(self):
        product = Product.objects.create(category=self.cat, name='С фото', price=1000, image=self.upload())
        with Image.open(product.image.path) as im:
            self.assertEqual(max(im.size), 2400)

    def test_phone_rotation_is_applied(self):
        product = Product.objects.create(category=self.cat, name='Повёрнутое', price=1000, image=self.upload((800, 400), orientation=6))
        with Image.open(product.image.path) as im:
            self.assertEqual(im.size, (400, 800))  # телефон снял боком — выправляем

    def test_thumbnail_is_created_once(self):
        product = Product.objects.create(category=self.cat, name='С фото', price=1000, image=self.upload((1200, 1500)))
        url = thumb_url(product.image, 480)
        self.assertTrue(url.startswith('/media/thumbs/') and url.endswith('-480.webp'))
        with Image.open(self.media + url.removeprefix('/media')) as im:
            self.assertEqual((im.format, im.width), ('WEBP', 480))
        self.assertEqual(thumb_url(product.image, 480), url)

    def test_cover_prefers_main_photo_then_gallery(self):
        product = Product.objects.create(category=self.cat, name='Галерея', price=1000)
        self.assertIsNone(product.cover)
        ProductImage.objects.create(product=product, image=self.upload((600, 800), name='a.jpg'))
        self.assertTrue(Product.objects.prefetch_related('photos').get(pk=product.pk).cover)

    def test_pages_use_photos_when_present(self):
        product = Product.objects.create(category=self.cat, name='С фото', price=1000, image=self.upload((1200, 1500)))
        html = self.client.get(product.get_absolute_url()).content.decode()
        self.assertIn('/media/thumbs/', html)
        self.assertIn('srcset=', html)

    def test_broken_upload_is_kept_as_is(self):
        self.assertEqual(process_upload(SimpleUploadedFile('bad.jpg', b'not an image')).read(), b'not an image')
