from urllib.parse import urlparse

from django.conf import settings

from .models import SiteSettings

SOURCE_PARAMS = ('utm_source', 'from', 'ref', 'src')
# «Откуда пришёл клиент»: по ссылке с меткой (?utm_source=telegram) или по сайту, с которого перешли
REFERRER_NAMES = {
    'yandex.ru': 'yandex', 'ya.ru': 'yandex', 'google.com': 'google', 't.me': 'telegram', 'telegram.org': 'telegram',
    'vk.com': 'vk', 'instagram.com': 'instagram', 'avito.ru': 'avito', 'flowwow.com': 'flowwow', '2gis.ru': '2gis',
}


class TrafficSourceMiddleware:
    """Запоминает в сессии, откуда пришёл клиент, — чтобы в заказе было видно «Яндекс», «Telegram», «QR у кассы»."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET' and 'mz_src' not in request.session and not request.path.startswith(('/static/', '/media/')):
            source = next((request.GET[p] for p in SOURCE_PARAMS if request.GET.get(p)), '')
            if not source:
                host = (urlparse(request.META.get('HTTP_REFERER', '')).hostname or '').removeprefix('www.')
                if host and host != request.get_host().split(':')[0]:
                    source = next((name for domain, name in REFERRER_NAMES.items() if host == domain or host.endswith('.' + domain)), '')
            if source:
                request.session['mz_src'] = source.strip().lower()[:40]
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Content-Security-Policy для сайта (админку не трогаем: ей нужны свои скрипты) и запрет лишних возможностей браузера."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.mode = settings.CSP_MODE

    def policy(self):
        metrika = bool(SiteSettings.load().metrika_id)
        parts = {
            'default-src': ["'self'"],
            'script-src': ["'self'"] + (['https://mc.yandex.ru', 'https://yastatic.net'] if metrika else []),
            'style-src': ["'self'", 'https://fonts.googleapis.com'],
            'font-src': ["'self'", 'https://fonts.gstatic.com', 'data:'],
            'img-src': ["'self'", 'data:', 'blob:'] + (['https://mc.yandex.ru'] if metrika else []),
            'connect-src': ["'self'"] + (['https://mc.yandex.ru', 'wss://mc.yandex.ru'] if metrika else []),
            'frame-src': ['https://mc.yandex.ru'] if metrika else ["'none'"],
            'object-src': ["'none'"],
            'base-uri': ["'self'"],
            'form-action': ["'self'"],
            'frame-ancestors': ["'none'"],
        }
        return '; '.join(f'{k} {" ".join(v)}' for k, v in parts.items())

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()')
        is_admin = request.path.startswith('/' + settings.ADMIN_URL)
        if self.mode != 'off' and not is_admin and response.headers.get('Content-Type', '').startswith('text/html'):
            name = 'Content-Security-Policy' if self.mode == 'enforce' else 'Content-Security-Policy-Report-Only'
            response.headers.setdefault(name, self.policy())
        return response
