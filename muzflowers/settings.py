import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# --- читаем файл .env (если есть); настоящие переменные окружения важнее ---
_env = BASE_DIR / '.env'
if _env.exists():
    for _line in _env.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"\''))

DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or ('dev-only-insecure-key' if DEBUG else '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Задайте DJANGO_SECRET_KEY в файле .env (обязательно при DJANGO_DEBUG=0)')


def _list(name, default=''):
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]


ALLOWED_HOSTS = _list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
CSRF_TRUSTED_ORIGINS = _list('DJANGO_CSRF_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'shop',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
try:  # раздача статики на боевом сервере; если пакета нет — просто пропускаем
    import whitenoise  # noqa: F401
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

ROOT_URLCONF = 'muzflowers.urls'
WSGI_APPLICATION = 'muzflowers.wsgi.application'
ASGI_APPLICATION = 'muzflowers.asgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'shop.context_processors.site',
    ]},
}]

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru'
TIME_ZONE = os.environ.get('DJANGO_TIME_ZONE', 'Europe/Moscow')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
SERVE_MEDIA = os.environ.get('DJANGO_SERVE_MEDIA', '1' if DEBUG else '0') == '1'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:profile'
LOGOUT_REDIRECT_URL = 'shop:index'
ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'admin').strip('/') + '/'

# --- магазин ---
SHOP_PHONE = os.environ.get('SHOP_PHONE', '+7 (000) 000-00-00')
SHOP_EMAIL = os.environ.get('SHOP_EMAIL', 'hello@example.com')
SHOP_ADDRESS = os.environ.get('SHOP_ADDRESS', 'Ваш город, ул. Цветочная, 1')
SHOP_HOURS = os.environ.get('SHOP_HOURS', 'Ежедневно, 8:00–22:00')
SHOP_FREE_DELIVERY_FROM = int(os.environ.get('SHOP_FREE_DELIVERY_FROM', 3000))
SHOP_DELIVERY_COST = int(os.environ.get('SHOP_DELIVERY_COST', 300))
# Заголовок с реальным IP посетителя (например HTTP_X_REAL_IP) — только если его ставит ваш nginx
SHOP_CLIENT_IP_HEADER = os.environ.get('SHOP_CLIENT_IP_HEADER') or None

DATA_UPLOAD_MAX_MEMORY_SIZE = 100_000

if os.environ.get('REDIS_URL'):  # общий кэш для лимитов (нужен пакет redis)
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': os.environ['REDIS_URL']}}

if not DEBUG:  # боевой режим: защищённые cookie, HTTPS, HSTS
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SSL', '1') == '1'
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
    SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
    if os.environ.get('DJANGO_BEHIND_PROXY') == '1':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
