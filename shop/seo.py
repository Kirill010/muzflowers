"""Поисковая оптимизация: карта сайта, robots.txt, манифест и структурированные данные для Яндекса и Google."""
import json

from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_page

from .models import Category, Product, Shop, SiteSettings
from .thumbs import thumb_url

PUBLIC_PAGES = ['shop:home', 'shop:catalog', 'shop:bouquet_builder', 'shop:music', 'shop:delivery', 'shop:care', 'shop:offices',
                'shop:subscription', 'shop:about', 'shop:contacts', 'shop:faq', 'shop:privacy', 'shop:offer',
                'shop:legal', 'shop:consent', 'shop:marketing_consent', 'shop:cookies']


class PagesSitemap(Sitemap):
    changefreq, priority = 'weekly', 0.7

    def items(self):
        return PUBLIC_PAGES

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    changefreq, priority = 'weekly', 0.8

    def items(self):
        return Category.objects.filter(is_active=True)


class ProductSitemap(Sitemap):
    changefreq, priority = 'weekly', 0.9

    def items(self):
        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated


SITEMAPS = {'pages': PagesSitemap, 'categories': CategorySitemap, 'products': ProductSitemap}


def robots(request):
    from django.conf import settings
    origin = settings.SITE_URL or request.build_absolute_uri('/').rstrip('/')
    admin = '/' + settings.ADMIN_URL
    lines = ['User-agent: *', 'Disallow: /cart/', 'Disallow: /checkout/', 'Disallow: /order/', 'Disallow: /accounts/',
             f'Disallow: {admin}', 'Disallow: /search/', 'Allow: /', f'Sitemap: {origin}/sitemap.xml']
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')


@cache_page(3600)
def manifest(request):
    site = SiteSettings.load()
    return JsonResponse({
        'name': f'{site.shop_name} — цветочный магазин', 'short_name': site.shop_name, 'lang': 'ru', 'start_url': '/',
        'display': 'standalone', 'background_color': '#e4e9c9', 'theme_color': '#607344',
        'icons': [{'src': static('shop/img/icon-192.png'), 'sizes': '192x192', 'type': 'image/png'},
                  {'src': static('shop/img/icon-512.png'), 'sizes': '512x512', 'type': 'image/png'}],
    }, json_dumps_params={'ensure_ascii': False}, content_type='application/manifest+json')


# ───────────── структурированные данные (JSON-LD) ─────────────

def abs_url(origin, path):
    return path if path.startswith('http') else origin + path


def florist(origin):
    site = SiteSettings.load()
    shop = Shop.objects.filter(is_active=True).first()
    data = {
        '@context': 'https://schema.org', '@type': 'Florist', 'name': site.shop_name, 'url': origin + '/',
        'telephone': '+' + ''.join(c for c in site.phone if c.isdigit()),
        'image': origin + static('shop/img/logo-sage.png'), 'priceRange': '₽₽',
        'openingHoursSpecification': [{
            '@type': 'OpeningHoursSpecification',
            'dayOfWeek': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
            'opens': site.open_time.strftime('%H:%M'), 'closes': site.close_time.strftime('%H:%M')}],
    }
    if site.yandex_maps_url:
        data['sameAs'] = [site.yandex_maps_url]
    if shop and shop.address:
        data['address'] = {'@type': 'PostalAddress', 'streetAddress': shop.address, 'addressLocality': 'Москва', 'addressCountry': 'RU'}
    if site.email:
        data['email'] = site.email
    return data


def product_ld(product, origin):
    cover = product.cover
    image = abs_url(origin, thumb_url(cover, 1200)) if cover else origin + static('shop/img/og.jpg')
    return {
        '@context': 'https://schema.org', '@type': 'Product', 'name': product.name, 'sku': str(product.pk),
        'image': [image], 'description': product.tagline or product.description[:200] or product.name,
        'brand': {'@type': 'Brand', 'name': SiteSettings.load().shop_name},
        'offers': {'@type': 'Offer', 'url': origin + product.get_absolute_url(), 'priceCurrency': 'RUB', 'price': str(product.price_from),
                   'availability': 'https://schema.org/InStock' if product.is_orderable else 'https://schema.org/OutOfStock'},
    }


def breadcrumbs_ld(origin, crumbs):
    """crumbs: [(название, путь)]"""
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i, 'name': name, 'item': origin + path} for i, (name, path) in enumerate(crumbs, 1)]}


def faq_ld(items):
    return {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q.question, 'acceptedAnswer': {'@type': 'Answer', 'text': q.answer}} for q in items]}


def dump(*blocks):
    """Готовит JSON-LD для вставки в <script type="application/ld+json">: знак < экранируем, чтобы нельзя было закрыть тег."""
    return [json.dumps(b, ensure_ascii=False).replace('<', '\\u003c') for b in blocks if b]
