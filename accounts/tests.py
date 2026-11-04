import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from shop.models import Order, OrderItem, Variant
from shop.tests.helpers import TODAY, ShopTestCase

from .models import Profile

User = get_user_model()
PASSWORD = 'Flowers-2026!x'


class AccountTestCase(ShopTestCase):
    def register(self, **extra):
        data = {'name': 'Анна', 'email': 'Anna@Example.com', 'phone': '8 917 549-49-41', 'password1': PASSWORD, 'password2': PASSWORD, 'consent': 'on'}
        data.update(extra)
        return self.client.post(reverse('accounts:register'), data)

    def make_user(self, email='anna@example.com', phone='+79175494941'):
        user = User.objects.create_user(email, email, PASSWORD, first_name='Анна')
        Profile.objects.create(user=user, phone=phone)
        return user


class RegisterTests(AccountTestCase):
    def test_register_logs_in_and_stores_profile(self):
        r = self.register()
        self.assertRedirects(r, reverse('accounts:profile'))
        user = User.objects.get()
        self.assertEqual((user.username, user.email, user.first_name), ('anna@example.com', 'anna@example.com', 'Анна'))
        self.assertEqual(user.profile.phone, '+79175494941')
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 200)

    def test_duplicate_email_is_rejected_ignoring_case(self):
        self.make_user()
        r = self.register(email='ANNA@example.com', phone='')
        self.assertEqual(User.objects.count(), 1)
        self.assertIn('email', r.context['form'].errors)

    def test_duplicate_phone_is_rejected(self):
        self.make_user(email='other@example.com')
        self.assertIn('phone', self.register().context['form'].errors)

    def test_weak_password_and_mismatch(self):
        self.assertIn('password2', self.register(password1='12345678', password2='12345678').context['form'].errors)
        self.assertIn('password2', self.register(password2='different-2026!').context['form'].errors)
        self.assertFalse(User.objects.exists())

    def test_consent_and_honeypot(self):
        self.assertIn('consent', self.register(consent='').context['form'].errors)
        self.assertIn('website', self.register(website='http://spam').context['form'].errors)
        self.assertFalse(User.objects.exists())

    def test_register_is_throttled(self):
        for i in range(10):
            self.register(email=f'bad{i}', phone='')
        self.register()
        self.assertFalse(User.objects.exists())

    def test_order_made_before_registering_is_attached(self):
        self.add_to_cart()
        self.place_order()
        self.register()
        self.assertEqual(Order.objects.get().user, User.objects.get())

    def test_logged_in_user_is_redirected_from_register(self):
        self.register()
        self.assertRedirects(self.client.get(reverse('accounts:register')), reverse('accounts:profile'))


class LoginTests(AccountTestCase):
    def test_login_by_email_phone_and_username(self):
        self.make_user()
        User.objects.create_user('boss', 'boss@example.com', PASSWORD)
        for who in ('anna@example.com', 'ANNA@example.com', '8 (917) 549-49-41', '+79175494941', 'boss', 'boss@example.com'):
            with self.subTest(who=who):
                self.client.logout()
                r = self.client.post(reverse('accounts:login'), {'username': who, 'password': PASSWORD})
                self.assertRedirects(r, reverse('accounts:profile'), fetch_redirect_response=False)

    def test_wrong_password(self):
        self.make_user()
        r = self.client.post(reverse('accounts:login'), {'username': 'anna@example.com', 'password': 'nope'})
        self.assertContains(r, 'Неверная почта')

    def test_login_attempts_are_limited(self):
        self.make_user()
        for _ in range(10):
            self.client.post(reverse('accounts:login'), {'username': 'anna@example.com', 'password': 'nope'})
        r = self.client.post(reverse('accounts:login'), {'username': 'anna@example.com', 'password': PASSWORD})
        self.assertEqual(r.status_code, 429)

    def test_next_is_followed_only_inside_the_site(self):
        self.make_user()
        r = self.client.post(reverse('accounts:login'), {'username': 'anna@example.com', 'password': PASSWORD, 'next': '/catalog/'})
        self.assertRedirects(r, '/catalog/', fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse('accounts:login'), {'username': 'anna@example.com', 'password': PASSWORD, 'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('accounts:profile'), fetch_redirect_response=False)

    def test_logout_needs_post(self):
        self.client.force_login(self.make_user())
        self.client.post(reverse('accounts:logout'))
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 302)


class ProfileTests(AccountTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client.force_login(self.user)

    def test_profile_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(r, f'{reverse("accounts:login")}?next={reverse("accounts:profile")}', fetch_redirect_response=False)

    def test_update_profile(self):
        r = self.client.post(reverse('accounts:profile'), {'name': 'Анна П.', 'email': 'new@example.com', 'phone': '9001112233',
                                                           'address': 'Москва, ул. Пушкина, 1', 'marketing_consent': 'on'})
        self.assertRedirects(r, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email, self.user.username), ('Анна П.', 'new@example.com', 'new@example.com'))
        self.assertEqual((self.user.profile.phone, self.user.profile.marketing_consent), ('+79001112233', True))

    def test_cannot_take_another_users_email_or_phone(self):
        self.make_user('other@example.com', '+79000000000')
        r = self.client.post(reverse('accounts:profile'), {'name': 'А', 'email': 'other@example.com', 'phone': '9000000000'})
        self.assertEqual(set(r.context['form'].errors), {'email', 'phone'})

    def test_orders_are_listed_and_can_be_repeated(self):
        order = Order.objects.create(user=self.user, name='Анна', phone='+79175494941', date=TODAY, subtotal=1990, total=1990)
        OrderItem.objects.create(order=order, product=self.rose, name='Классика', price=1990, qty=2)
        self.assertContains(self.client.get(reverse('accounts:profile')), 'Заказ №')
        r = self.client.post(reverse('accounts:repeat', args=[order.pk]))
        self.assertRedirects(r, reverse('shop:cart'))
        self.assertEqual(self.client.session['mz_cart']['items'], {f'{self.rose.pk}:0': 2})

    def test_repeat_skips_hidden_products_and_keeps_size(self):
        small = Variant.objects.create(product=self.big, name='Малый', price=4000)
        order = Order.objects.create(user=self.user, name='А', phone='+79175494941', date=TODAY, subtotal=1, total=1)
        OrderItem.objects.create(order=order, product=self.rose, name='Классика', price=1990, qty=1)
        OrderItem.objects.create(order=order, product=self.big, variant=small, name='25 роз', price=4000, qty=1)
        self.rose.is_active = False
        self.rose.save()
        self.client.post(reverse('accounts:repeat', args=[order.pk]))
        self.assertEqual(list(self.client.session['mz_cart']['items']), [f'{self.big.pk}:{small.pk}'])

    def test_cannot_repeat_someone_elses_order(self):
        other = Order.objects.create(user=self.make_user('o@example.com', '+79000000000'), name='О', phone='+79000000000', date=TODAY, subtotal=1, total=1)
        self.assertEqual(self.client.post(reverse('accounts:repeat', args=[other.pk])).status_code, 404)

    def test_change_password(self):
        r = self.client.post(reverse('accounts:password_change'), {'old_password': PASSWORD, 'new_password1': 'Brand-new-2026!', 'new_password2': 'Brand-new-2026!'})
        self.assertRedirects(r, reverse('accounts:password_change_done'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brand-new-2026!'))


class PasswordResetTests(AccountTestCase):
    def test_full_reset_flow_by_email(self):
        user = self.make_user()
        r = self.client.post(reverse('accounts:password_reset'), {'email': 'anna@example.com'})
        self.assertRedirects(r, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r'http://testserver(\S+)', mail.outbox[0].body).group(1)
        self.assertIn('/accounts/password/reset/', link)
        r = self.client.get(link, follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {'new_password1': 'Reset-2026!ok', 'new_password2': 'Reset-2026!ok'})
        self.assertRedirects(r, reverse('accounts:password_reset_complete'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('Reset-2026!ok'))

    def test_unknown_email_gives_same_answer_and_no_mail(self):
        r = self.client.post(reverse('accounts:password_reset'), {'email': 'nobody@example.com'})
        self.assertRedirects(r, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_requests_are_limited(self):
        for _ in range(5):
            self.client.post(reverse('accounts:password_reset'), {'email': 'x@example.com'})
        self.assertEqual(self.client.post(reverse('accounts:password_reset'), {'email': 'x@example.com'}).status_code, 429)


class OwnerSetupTests(AccountTestCase):
    def data(self, **extra):
        return {'name': 'Ирина', 'email': 'Owner@Example.com', 'password1': PASSWORD, 'password2': PASSWORD, **extra}

    def test_first_run_creates_the_owner_and_logs_in(self):
        self.assertEqual(self.client.get(reverse('accounts:setup')).status_code, 200)
        r = self.client.post(reverse('accounts:setup'), self.data())
        self.assertRedirects(r, '/admin/', fetch_redirect_response=False)
        owner = User.objects.get()
        self.assertEqual((owner.username, owner.is_superuser, owner.is_staff), ('owner@example.com', True, True))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_setup_disappears_once_there_is_an_owner(self):
        User.objects.create_superuser('boss', 'boss@example.com', PASSWORD)
        self.assertEqual(self.client.get(reverse('accounts:setup')).status_code, 404)
        self.assertEqual(self.client.post(reverse('accounts:setup'), self.data()).status_code, 404)
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_refused(self):
        r = self.client.post(reverse('accounts:setup'), self.data(password1='12345', password2='12345'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.exists())

    @override_settings(BEHIND_PROXY=True)
    def test_behind_a_proxy_everyone_looks_local_so_a_token_is_required(self):
        self.assertEqual(self.client.get(reverse('accounts:setup')).status_code, 403)
        self.assertEqual(self.client.post(reverse('accounts:setup'), self.data()).status_code, 403)
        self.assertFalse(User.objects.exists())

    @override_settings(BEHIND_PROXY=True, SETUP_TOKEN='secret-code')
    def test_token_unlocks_setup_on_a_server(self):
        self.assertEqual(self.client.get(reverse('accounts:setup'), {'token': 'wrong'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:setup'), {'token': 'secret-code'}).status_code, 200)
        r = self.client.post(reverse('accounts:setup'), self.data(token='secret-code'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.get().is_superuser)

    def test_remote_address_is_not_trusted(self):
        r = self.client.get(reverse('accounts:setup'), REMOTE_ADDR='203.0.113.7')
        self.assertEqual(r.status_code, 403)
