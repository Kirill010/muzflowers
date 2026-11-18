import json
import xml.etree.ElementTree as ET

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse

from shop.models import FAQ, Category, Lead, Product, Review

from .helpers import ShopTestCase


class PageTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        FAQ.objects.create(question='Как быстро?', answer='За 15 минут', order=1)

    def test_all_public_pages_open(self):
        names = ['home', 'catalog', 'bouquet_builder', 'balloons', 'souvenirs', 'music', 'offices', 'subscription', 'delivery', 'care', 'about', 'contacts', 'faq', 'privacy', 'offer',
                 'legal', 'consent', 'marketing_consent', 'cookies', 'cart', 'wishlist']
        for name in names:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'shop:{name}')).status_code, 200)

    def test_category_and_product_pages(self):
        self.assertContains(self.client.get(self.cat.get_absolute_url()), 'Классика')
        r = self.client.get(self.rose.get_absolute_url())
        self.assertContains(r, 'Классика')
        self.assertContains(r, 'В корзину')
        self.assertContains(r, 'Музыкальная открытка')

    def test_hidden_product_and_category_are_404(self):
        self.rose.is_active = False
        self.rose.save()
        self.assertEqual(self.client.get(self.rose.get_absolute_url()).status_code, 404)
        self.cat.is_active = False
        self.cat.save()
        self.assertEqual(self.client.get(self.cat.get_absolute_url()).status_code, 404)

    def test_unavailable_product_page_has_no_buy_button(self):
        self.rose.in_stock = False
        self.rose.save()
        r = self.client.get(self.rose.get_absolute_url())
        self.assertContains(r, 'нет в наличии')
        self.assertNotContains(r, 'pdp__add')

    def test_404_page_is_friendly(self):
        r = self.client.get('/net-takoy-stranitsy/')
        self.assertContains(r, 'Такой страницы', status_code=404)

    def test_home_has_structured_data_and_real_contacts(self):
        r = self.client.get(reverse('shop:home'))
        blocks = [json.loads(b) for b in r.context['jsonld']]
        self.assertEqual(blocks[0]['@type'], 'Florist')
        self.assertEqual(blocks[0]['telephone'], '+79951522131')
        self.assertEqual(blocks[0]['openingHoursSpecification'][0]['opens'], '09:00')
        self.assertContains(r, '+7 (995) 152-21-31')
        self.assertContains(r, 'ул. Вешняковская, 39Г')

    def test_quick_pick_and_artwork_labels(self):
        r = self.client.get(reverse('shop:home'))
        self.assertContains(r, 'Букет под повод и бюджет')
        self.assertContains(r, 'name="occasion"')
        self.assertContains(r, 'name="budget"')
        self.assertContains(r, 'Иллюстрация, не фото букета')
        self.assertContains(self.client.get(self.rose.get_absolute_url()), 'Иллюстрация, не фото готового букета')
        self.assertContains(self.client.get(reverse('shop:catalog')), 'Самовывоз — бесплатно')

    def test_presentation_links_and_brand_artwork(self):
        self.update_site(pickup_discount_percent=10)
        Category.objects.create(name='Сезонные', slug='season')
        self.cat.slug = 'roses'
        self.cat.save()
        r = self.client.get(reverse('shop:home'))
        for label in ('Букеты', 'Собери сам', 'Акции', 'Сезонные цветы', 'Композиции', 'Розы', 'Цветы', 'Шары', 'Сувениры'):
            self.assertContains(r, label)
        self.assertContains(r, 'logo-sage.png')
        self.assertContains(r, 'data-record-toggle')
        self.assertContains(r, 'Скидка 10% при самовывозе')
        self.assertNotContains(r, 'по наличию')
        self.assertContains(r, 'href="/balloons/"')
        self.assertContains(r, 'href="/souvenirs/"')
        self.assertNotContains(r, 'title="Уточнить наличие шаров по телефону"')
        self.assertContains(r, 'favicon-32.png')
        self.assertNotContains(r, 'rel="icon" href="/static/shop/img/favicon.svg"')

    def test_product_page_has_offer_and_breadcrumbs(self):
        r = self.client.get(self.rose.get_absolute_url())
        kinds = [json.loads(b)['@type'] for b in r.context['jsonld']]
        self.assertEqual(kinds, ['Product', 'BreadcrumbList'])
        offer = json.loads(r.context['jsonld'][0])['offers']
        self.assertEqual((offer['price'], offer['priceCurrency']), ('1990', 'RUB'))

    def test_old_presentation_address_opens_the_workshop_page(self):
        response = self.client.get(reverse('shop:presentation'))
        self.assertRedirects(response, reverse('shop:about'), status_code=301)
        about = self.client.get(reverse('shop:about'))
        self.assertContains(about, 'Как мы собираем букеты')
        for page in (about, self.client.get(reverse('shop:home'))):
            self.assertNotContains(page, 'Наталья Боброва')
            self.assertNotContains(page, 'Школа Бизнеса')
            self.assertNotContains(page, 'Великой Школе Бизнеса')

    def test_contacts_include_saved_messengers_without_fake_reviews(self):
        self.update_site(telegram='muzflowers', max_url='https://max.ru/muzflowers', yandex_rating='4.8', yandex_votes=24,
                         yandex_maps_url='https://yandex.ru/maps/')
        Review.objects.create(name='Покупатель', text='Текст сохранённого отзыва', rating=5)
        for name in ('home', 'about', 'contacts', 'care', 'faq', 'delivery'):
            with self.subTest(page=name):
                response = self.client.get(reverse(f'shop:{name}'))
                self.assertNotContains(response, 'Текст сохранённого отзыва')
                self.assertNotContains(response, 'Читать и оставить отзыв')
                self.assertNotContains(response, 'aggregateRating')
        contacts = self.client.get(reverse('shop:contacts'))
        self.assertContains(contacts, 'https://t.me/muzflowers')
        self.assertContains(contacts, 'https://max.ru/muzflowers')
        self.assertNotContains(contacts, '<b>MAX</b>')

    def test_only_checked_reviews_are_shown(self):
        Review.objects.create(name='Не опубликовано', text='Непроверенный текст', permission_given=False)
        verified = Review.objects.create(name='Анна', text='Проверенный отзыв покупателя', rating=5, permission_given=True,
                                         source_url='https://yandex.ru/maps/org/muzflowers/123/reviews/456/')
        response = self.client.get(reverse('shop:home'))
        self.assertContains(response, verified.text)
        self.assertContains(response, verified.source_url)
        self.assertContains(response, 'Оригинал')
        self.assertNotContains(response, 'Непроверенный текст')
        self.assertNotContains(response, 'aggregateRating')

    def test_review_requires_permission_and_verifiable_yandex_source(self):
        with self.assertRaises(ValidationError):
            Review(name='Анна', text='Отзыв', is_published=True, permission_given=False).full_clean()
        for url in ('', 'https://example.com/review/1', 'https://yandex.ru/maps/?text=shop',
                    'https://yandex.ru.evil.example/maps/org/shop/1/'):
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    Review(name='Анна', text='Отзыв', permission_given=True, source_url=url).full_clean()
        Review(name='Анна', text='Отзыв', permission_given=True,
               source_url='https://yandex.ru/maps/org/shop/1/reviews/2/').full_clean()

    def test_faq_page_has_faq_markup(self):
        r = self.client.get(reverse('shop:faq'))
        markup = json.loads(r.context['jsonld'][0])
        self.assertEqual(markup['@type'], 'FAQPage')
        self.assertEqual(len(r.context['items']), 6)
        self.assertContains(r, 'Почему нельзя повторить букет точь-в-точь?')
        self.assertIn('Как быстро?', {q['name'] for q in markup['mainEntity']})

    def test_announcement_and_pause_are_shown(self):
        self.update_site(announcement='Предзаказ на 8 Марта открыт')
        self.assertContains(self.client.get(reverse('shop:home')), 'Предзаказ на 8 Марта открыт')
        self.update_site(orders_paused=True, pause_message='Не принимаем заказы')
        self.assertContains(self.client.get(reverse('shop:home')), 'Не принимаем заказы')

    def test_legal_pages_show_requisites_when_filled(self):
        self.assertContains(self.client.get(reverse('shop:offer')), 'Перед публикацией заполните реквизиты продавца')
        self.update_site(legal_name='ИП Иванов И. И.', inn='7700000000')
        r = self.client.get(reverse('shop:offer'))
        self.assertContains(r, 'ИП Иванов И. И.')
        self.assertNotContains(r, 'Перед публикацией заполните реквизиты продавца')

    def test_legal_documents_are_muzflowers_specific(self):
        for name in ('offer', 'privacy', 'consent', 'marketing_consent', 'cookies', 'legal'):
            with self.subTest(page=name):
                r = self.client.get(reverse(f'shop:{name}'))
                expected = 'Редакция комплекта 1.0' if name == 'legal' else 'Редакция 1.0'
                self.assertContains(r, expected)
                self.assertNotContains(r, 'RestHelper')
                self.assertNotContains(r, 'iiko')
        self.assertContains(self.client.get(reverse('shop:privacy')), 'Трансграничная передача')
        self.assertContains(self.client.get(reverse('shop:privacy')), 'ИИ и обезличенная аналитика')


class WishlistTests(ShopTestCase):
    def toggle(self, product=None, **extra):
        return self.client.post(reverse('shop:wishlist_toggle'), {'product': (product or self.rose).pk, **extra},
                                headers={'X-Requested-With': 'fetch'})

    def test_toggle_persists_in_session_and_page(self):
        response = self.toggle()
        self.assertEqual(response.json(), {'ok': True, 'active': True, 'count': 1, 'product': self.rose.pk,
                                           'message': '«Классика» — в избранном'})
        self.assertEqual(self.client.session['mz_wishlist'], [self.rose.pk])
        page = self.client.get(reverse('shop:wishlist'))
        self.assertEqual([p.pk for p in page.context['products']], [self.rose.pk])
        self.assertContains(page, 'Классика')
        self.assertContains(page, 'noindex, nofollow')
        self.assertContains(page, 'aria-pressed="true"')
        self.assertFalse(self.toggle().json()['active'])
        self.assertEqual(self.client.session['mz_wishlist'], [])

    def test_header_count_and_catalog_button(self):
        self.toggle()
        page = self.client.get(reverse('shop:catalog'))
        self.assertContains(page, 'data-wishlist-count data-count="1"')
        self.assertContains(page, 'data-wishlist-form')

    def test_hidden_products_cannot_be_added_and_disappear_from_page(self):
        self.toggle()
        self.rose.is_active = False
        self.rose.save()
        self.assertEqual(self.toggle().status_code, 404)
        self.assertEqual(self.client.get(reverse('shop:wishlist')).context['products'], [])
        self.cat.is_active = False
        self.cat.save()
        self.rose.is_active = True
        self.rose.save()
        self.assertEqual(self.toggle().status_code, 404)

    def test_invalid_product_and_get_are_rejected(self):
        self.assertEqual(self.client.post(reverse('shop:wishlist_toggle'), {'product': 'bad'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('shop:wishlist_toggle')).status_code, 405)

    def test_redirect_cannot_leave_the_site(self):
        response = self.client.post(reverse('shop:wishlist_toggle'), {'product': self.rose.pk, 'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('shop:wishlist'))
        response = self.client.post(reverse('shop:wishlist_toggle'), {'product': self.rose.pk, 'next': self.rose.get_absolute_url()})
        self.assertRedirects(response, self.rose.get_absolute_url())


class CatalogTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.mono = Category.objects.create(name='Моно', slug='mono')
        self.chrys = Product.objects.create(category=self.mono, name='Хризантемы', price=2190, popularity=1)

    def names(self, **params):
        return [p.name for p in self.client.get(reverse('shop:catalog'), params).context['products']]

    def test_default_order_is_by_popularity(self):
        self.assertEqual(self.names(), ['Классика', '25 роз', 'Хризантемы'])

    def test_search_ignores_case_of_cyrillic(self):
        self.assertEqual(self.names(q='КЛАССИКА'), ['Классика'])
        self.assertEqual(self.names(q='хризантем'), ['Хризантемы'])
        self.assertEqual(self.names(q='роз'), ['Классика', '25 роз'])  # по названию и описанию

    def test_price_range_and_sort(self):
        self.assertEqual(self.names(min=2000, max=3000), ['Хризантемы'])
        self.assertEqual(self.names(sort='price_asc'), ['Классика', 'Хризантемы', '25 роз'])
        self.assertEqual(self.names(sort='price_desc'), ['25 роз', 'Хризантемы', 'Классика'])

    def test_occasion_filter(self):
        self.rose.occasion = 'birthday'
        self.rose.save()
        self.big.occasion = 'celebration'
        self.big.save()
        self.assertEqual(self.names(occasion='birthday'), ['Классика'])
        self.assertEqual(self.names(occasion='birthday', ready='1'), ['Классика'])
        self.assertEqual(self.names(occasion='love'), [])
        self.assertEqual(self.names(occasion='unknown'), ['Классика', '25 роз', 'Хризантемы'])

    def test_budget_shortcuts_use_server_side_ranges(self):
        self.assertEqual(self.names(budget='small'), ['Классика', 'Хризантемы'])
        self.assertEqual(self.names(budget='large'), ['25 роз'])
        self.assertEqual(self.names(budget='unknown'), ['Классика', '25 роз', 'Хризантемы'])
        r = self.client.get(reverse('shop:catalog'), {'budget': 'medium', 'sort': 'price_asc'})
        self.assertEqual((r.context['price_min'], r.context['price_max']), ('2500', '5000'))
        self.assertEqual(r.context['qs'], 'sort=price_asc&min=2500&max=5000')

    def test_bouquet_tiers_filter_at_exact_price_boundaries(self):
        for price in (3000, 6999, 7000, 14999, 15000):
            Product.objects.create(category=self.cat, name=f'Букет {price}', price=price)
        self.assertEqual(self.names(budget='economy', sort='price_asc'), ['Букет 3000', '25 роз', 'Букет 6999'])
        self.assertEqual(self.names(budget='standard', sort='price_asc'), ['Букет 7000', 'Букет 14999'])
        self.assertEqual(self.names(budget='premium'), ['Букет 15000'])

    def test_ready_only(self):
        self.assertEqual(self.names(ready='1'), ['Классика'])

    def test_sale_only_uses_current_catalog_prices(self):
        self.rose.old_price = self.rose.price + 500
        self.rose.save()
        self.chrys.old_price = self.chrys.price
        self.chrys.save()
        self.assertEqual(self.names(sale='1'), ['Классика'])
        self.assertEqual(self.names(sale='1', q='хризантемы'), [])

    def test_category_page_filters(self):
        r = self.client.get(self.mono.get_absolute_url())
        self.assertEqual([p.name for p in r.context['products']], ['Хризантемы'])

    def test_ajax_returns_only_results(self):
        r = self.client.get(reverse('shop:catalog'), {'q': 'хризантемы'}, headers={'X-Requested-With': 'fetch'})
        self.assertContains(r, 'Хризантемы')
        self.assertNotContains(r, '<html')

    def test_pagination(self):
        for i in range(30):
            Product.objects.create(category=self.cat, name=f'Букет {i}', price=1000 + i)
        r = self.client.get(reverse('shop:catalog'), {'page': 2})
        self.assertEqual((r.context['page'].number, len(r.context['products'])), (2, 9))
        self.assertContains(r, 'noindex')  # вторые страницы поисковикам не нужны

    def test_empty_search_has_message(self):
        response = self.client.get(reverse('shop:catalog'), {'q': 'нетакого'})
        self.assertContains(response, 'Ничего не нашли')
        self.assertContains(response, 'href="/bouquet/"')

    def test_suggest(self):
        data = self.client.get(reverse('shop:suggest'), {'q': 'клас'}).json()
        self.assertEqual([i['name'] for i in data['items']], ['Классика'])
        self.assertEqual(data['items'][0]['image'], self.rose.art_url)
        self.assertEqual(self.client.get(reverse('shop:suggest'), {'q': 'к'}).json(), {'items': []})


class SeoAndArtTests(ShopTestCase):
    def test_art_is_valid_svg(self):
        for kind in ('rose', 'chrysanthemum', 'alstroemeria', 'hydrangea', 'tulip', 'mixed'):
            with self.subTest(kind=kind):
                r = self.client.get(f'/art/{kind}/7/fca8c0/e0587c.svg')
                self.assertEqual(r['Content-Type'], 'image/svg+xml')
                self.assertEqual(ET.fromstring(r.content).tag, '{http://www.w3.org/2000/svg}svg')
                self.assertIn('immutable', r['Cache-Control'])

    def test_art_rejects_bad_parameters(self):
        for url in ('/art/cactus/7/fca8c0/e0587c.svg', '/art/rose/0/fca8c0/e0587c.svg', '/art/rose/99/fca8c0/e0587c.svg',
                    '/art/rose/7/zzzzzz/e0587c.svg', '/art/rose/7/fca8c0/e05.svg'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_art_is_deterministic(self):
        url = '/art/mixed/13/fca8c0/c2416c.svg'
        self.assertEqual(self.client.get(url).content, self.client.get(url).content)

    def test_sitemap(self):
        r = self.client.get('/sitemap.xml')
        self.assertContains(r, self.rose.get_absolute_url())
        self.assertContains(r, self.cat.get_absolute_url())
        self.assertNotContains(r, '/cart/')
        self.assertNotContains(r, '/presentation/')
        ET.fromstring(r.content)

    def test_robots(self):
        r = self.client.get('/robots.txt')
        self.assertContains(r, 'Disallow: /checkout/')
        self.assertContains(r, 'Disallow: /order/')
        self.assertContains(r, 'Sitemap: http://testserver/sitemap.xml')

    @override_settings(SITE_URL='https://muzflowers.example')
    def test_canonical_uses_configured_site_url(self):
        self.assertContains(self.client.get(reverse('shop:delivery')), 'href="https://muzflowers.example/delivery/"')

    def test_manifest_favicon_health(self):
        self.assertEqual(self.client.get(reverse('shop:manifest')).json()['short_name'], 'MuzFlowers')
        self.assertEqual(self.client.get('/favicon.ico').status_code, 302)
        self.assertEqual(self.client.get(reverse('shop:health')).json(), {'ok': True})

    def test_security_headers(self):
        r = self.client.get(reverse('shop:home'))
        self.assertIn("script-src 'self'", r['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", r['Content-Security-Policy'])
        self.assertIn('camera=()', r['Permissions-Policy'])
        self.assertEqual(r['X-Frame-Options'], 'DENY')

    def test_metrika_is_opt_in(self):
        r = self.client.get(reverse('shop:home'))
        self.assertNotContains(r, 'name="metrika-id"')
        self.assertNotContains(r, 'cookie_consent.js')
        self.update_site(metrika_id='12345678')
        r = self.client.get(reverse('shop:home'))
        self.assertContains(r, 'name="metrika-id" content="12345678"')
        self.assertContains(r, 'data-cookie-consent')
        self.assertContains(r, 'cookie_consent.js')
        self.assertNotContains(r, 'src="/static/shop/js/metrika.js"')
        self.assertContains(r, 'Только необходимые')
        self.assertContains(r, 'Разрешить аналитику')
        self.assertIn('mc.yandex.ru', r['Content-Security-Policy'])

    def test_pages_do_not_use_inline_scripts_or_styles(self):
        """Иначе защита CSP заблокирует их на боевом сайте."""
        self.add_to_cart()
        for url in (reverse('shop:home'), reverse('shop:catalog'), self.rose.get_absolute_url(), reverse('shop:checkout')):
            html = self.client.get(url).content.decode()
            with self.subTest(url=url):
                self.assertNotIn(' style="', html)
                self.assertNotIn('<style', html)
                self.assertNotRegex(html, r'<script(?![^>]*(src=|type="application/(ld\+)?json"))[^>]*>')
                self.assertNotRegex(html, r'\son(click|load|error|submit)=')


class LeadTests(ShopTestCase):
    def post(self, name, **extra):
        data = {'name': 'Ольга', 'phone': '8 900 111-22-33', 'consent': 'on', 'company': 'ООО Ромашка', 'message': 'Нужен букет на ресепшен'}
        data.update(extra)
        return self.client.post(reverse(f'shop:{name}'), data)

    def test_office_request_is_saved(self):
        r = self.post('offices')
        self.assertRedirects(r, reverse('shop:offices'))
        lead = Lead.objects.get()
        self.assertEqual((lead.kind, lead.phone, lead.company, lead.status), ('office', '+79001112233', 'ООО Ромашка', 'new'))

    def test_subscription_request_is_saved(self):
        self.post('subscription')
        self.assertEqual(Lead.objects.get().kind, 'subscription')

    def test_gift_pages_save_the_right_kind_of_request(self):
        for route, kind, text in (('balloons', Lead.Kind.BALLOONS, 'Нужны розовые шары'),
                                  ('souvenirs', Lead.Kind.SOUVENIRS, 'Нужен сувенир к букету')):
            with self.subTest(page=route):
                response = self.post(route, message=text)
                self.assertRedirects(response, reverse(f'shop:{route}'))
                lead = Lead.objects.get(kind=kind)
                self.assertEqual((lead.message, lead.status), (text, Lead.Status.NEW))
                self.assertContains(self.client.get(reverse(f'shop:{route}')), 'name="message"')

    def test_success_message_is_shown_after_redirect(self):
        r = self.client.post(reverse('shop:offices'), {'name': 'О', 'phone': '9001112233', 'consent': 'on'}, follow=True)
        self.assertContains(r, 'Спасибо! Мы получили заявку')

    def test_invalid_requests_are_not_saved(self):
        for extra in ({'phone': '1'}, {'consent': ''}, {'website': 'http://spam'}, {'name': ''}):
            with self.subTest(extra=extra):
                data = {'name': 'Ольга', 'phone': '9001112233', 'consent': 'on', **extra}
                r = self.client.post(reverse('shop:offices'), data)
                self.assertEqual(r.status_code, 200)
        self.assertFalse(Lead.objects.exists())

    def test_leads_are_throttled(self):
        for _ in range(5):
            self.post('offices')
        self.post('offices')
        self.assertEqual(Lead.objects.count(), 5)
