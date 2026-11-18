from html.parser import HTMLParser
from pathlib import Path
from shutil import copy2, copytree
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings
from django.urls import reverse

from shop.bouquet import FLOWERS
from shop.models import Category, Product
from shop.seo import PUBLIC_PAGES


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if not value:
                continue
            if key in ('href', 'src') or (tag == 'meta' and key == 'content'):
                self.urls.add(value)
            elif key == 'srcset':
                self.urls.update(candidate.split()[0] for candidate in value.split(',') if candidate.strip())


class Command(BaseCommand):
    help = 'Экспортирует публичную витрину для статического хостинга Sites.'

    def add_arguments(self, parser):
        parser.add_argument('output', type=Path)
        parser.add_argument('--origin', required=True)

    def handle(self, output, origin, **options):
        url = urlsplit(origin)
        if url.scheme not in ('http', 'https') or not url.netloc or url.path.rstrip('/') or url.query or url.fragment:
            raise CommandError('Укажите адрес сайта без пути, например https://muzflowers.example.')
        if output.exists() and any(output.iterdir()):
            raise CommandError('Для экспорта нужна пустая папка.')
        output.mkdir(parents=True, exist_ok=True)

        products = Product.objects.filter(is_active=True, category__is_active=True)
        pages = [reverse(name) for name in PUBLIC_PAGES]
        pages += [category.get_absolute_url() for category in Category.objects.filter(is_active=True)]
        pages += [product.get_absolute_url() for product in products]
        art_paths = {reverse('shop:stem_art', args=[kind]) for kind in FLOWERS}
        assets = PageAssets()
        with override_settings(
            SITES_STOREFRONT=True, SITE_URL=origin.rstrip('/'), ALLOWED_HOSTS=[url.hostname],
            SECURE_SSL_REDIRECT=False, STORAGES={
                **settings.STORAGES,
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
            },
        ):
            client = Client(SERVER_NAME=url.hostname)
            for route in pages:
                response = client.get(route, secure=url.scheme == 'https')
                self.save(output / route.lstrip('/') / 'index.html', response)
                assets.feed(response.content.decode(response.charset))

            for address in assets.urls:
                path = urlsplit(address).path
                if path.startswith('/art/'):
                    art_paths.add(path)
                elif path.startswith(settings.MEDIA_URL):
                    relative = unquote(path.removeprefix(settings.MEDIA_URL))
                    root = Path(settings.MEDIA_ROOT).resolve()
                    source = (root / relative).resolve()
                    if source.is_relative_to(root) and source.is_file():
                        target = output / settings.MEDIA_URL.lstrip('/') / source.relative_to(root)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        copy2(source, target)
            for path in sorted(art_paths):
                self.save(output / path.lstrip('/'), client.get(path))
            self.save(output / 'manifest.webmanifest', client.get(reverse('shop:manifest')))

        copytree(settings.BASE_DIR / 'static' / 'shop', output / 'static' / 'shop')
        (output / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
        (output / '_headers').write_text(
            '/art/*\n  Content-Type: image/svg+xml\n  Cache-Control: public, max-age=86400\n', encoding='utf-8',
        )
        self.stdout.write(f'Экспортировано страниц: {len(pages)}')

    def save(self, path, response):
        if response.status_code != 200:
            raise CommandError(f'Не удалось экспортировать {path}: HTTP {response.status_code}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
