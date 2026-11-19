"""Настройки сайта MuzFlowers.

Всё, что нужно менять (пароли, адрес сайта, Telegram, почта), лежит в файле .env — см. .env.example.
Контакты, часы работы, цены доставки и тексты меняются в панели владельца (/admin/ → «Настройки сайта»).
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# --- читаем файл .env (если есть); настоящие переменные окружения важнее ---
def _load_env(path):
    if not path.exists():
        return
    # utf-8-sig: Блокнот Windows любит дописывать в начало файла невидимый знак BOM
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip().removeprefix('export ').strip()
        os.environ.setdefault(key, value.strip().strip('"\''))


_load_env(BASE_DIR / '.env')


def _flag(name, default=False):
    return os.environ.get(name, '1' if default else '0').strip().lower() in ('1', 'true', 'yes', 'on', 'да')


def _list(name, default=''):
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]


TESTING = 'test' in sys.argv
DEBUG = _flag('DJANGO_DEBUG', True)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or ('dev-only-insecure-key' if (DEBUG or TESTING) else '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Задайте DJANGO_SECRET_KEY в файле .env (обязательно при DJANGO_DEBUG=0)')

ALLOWED_HOSTS = _list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
CSRF_TRUSTED_ORIGINS = _list('DJANGO_CSRF_ORIGINS')
# Основной адрес сайта (для ссылок в письмах и поисковиках). Если не задан — берём из запроса.
SITE_URL = os.environ.get('SITE_URL', '').rstrip('/')

# Папка с данными (база и фото). По умолчанию — рядом с проектом; на хостинге/в Docker — отдельный том.
DATA_DIR = Path(os.environ.get('DJANGO_DATA_DIR') or BASE_DIR)
DATA_DIR.mkdir(parents=True, exist_ok=True)

INSTALLED_APPS = [
    'muzflowers.apps.MuzAdminConfig',  # обычная админка Django + «панель владельца» на главной
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
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
    'shop.middleware.TrafficSourceMiddleware',
    'shop.middleware.SecurityHeadersMiddleware',
]
try:  # раздача статики на боевом сервере (на своём компьютере её раздаёт сам runserver); если пакета нет — пропускаем
    import whitenoise  # noqa: F401
    _HAS_WHITENOISE = True
except ImportError:
    _HAS_WHITENOISE = False
if _HAS_WHITENOISE and not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

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


# --- база данных: по умолчанию файл db.sqlite3; для Postgres задайте DJANGO_DB_URL=postgres://user:pass@host:5432/name ---
def _database():
    url = os.environ.get('DJANGO_DB_URL', '').strip()
    if not url:
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DATA_DIR / 'db.sqlite3',
            # IMMEDIATE: две одновременные записи ждут друг друга, а не падают с «database is locked»
            'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'},
        }
    parsed = urlparse(url)
    if parsed.scheme in ('postgres', 'postgresql'):
        return {
            'ENGINE': 'django.db.backends.postgresql', 'NAME': parsed.path.lstrip('/'),
            'USER': unquote(parsed.username or ''), 'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or '', 'PORT': parsed.port or '', 'CONN_MAX_AGE': 60,
        }
    if parsed.scheme == 'sqlite':
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': unquote(parsed.path.lstrip('/')) or DATA_DIR / 'db.sqlite3'}
    raise ImproperlyConfigured('DJANGO_DB_URL: поддерживаются postgres://… и sqlite:///…')


DATABASES = {'default': _database()}

AUTH_USER_MODEL = 'auth.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrPhoneBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
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
MEDIA_ROOT = DATA_DIR / 'media'
SERVE_MEDIA = _flag('DJANGO_SERVE_MEDIA', DEBUG)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': (
        'whitenoise.storage.CompressedManifestStaticFilesStorage'
        if (_HAS_WHITENOISE and not DEBUG and not TESTING)
        else 'django.contrib.staticfiles.storage.StaticFilesStorage')},
}
WHITENOISE_MANIFEST_STRICT = False
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:profile'
LOGOUT_REDIRECT_URL = 'shop:home'
ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'admin').strip('/') + '/'

# --- почта: без настроек письма просто печатаются в окне запуска ---
EMAIL_BACKEND = os.environ.get('DJANGO_EMAIL_BACKEND') or (
    'django.core.mail.backends.smtp.EmailBackend' if os.environ.get('DJANGO_EMAIL_HOST')
    else 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('DJANGO_EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('DJANGO_EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_PASSWORD', '')
EMAIL_USE_TLS = _flag('DJANGO_EMAIL_TLS', True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_EMAIL_FROM') or EMAIL_HOST_USER or 'MuzFlowers <noreply@muzflowers.local>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- уведомления о заказах (необязательно) ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')  # можно несколько через запятую
ORDER_WEBHOOK_URL = os.environ.get('ORDER_WEBHOOK_URL', '')  # любой сервис, который принимает JSON
ORDER_NOTIFY_EMAILS = _list('ORDER_NOTIFY_EMAILS')  # почта владельца/сотрудников для писем о новых заказах

# Служебное API Telegram-бота. Секрет задаётся только на сервере, не в коде и не в Telegram.
BOT_API_SECRET = os.environ.get('BOT_API_SECRET', '')
BOT_ADMIN_IDS = [int(value) for value in _list('BOT_ADMIN_IDS') if value.isdigit()]

# --- онлайн-оплата (необязательно): none | tbank | yookassa ---
PAYMENT_PROVIDER = os.environ.get('PAYMENT_PROVIDER', 'none').strip().lower()
PAYMENT_TBANK_TERMINAL = os.environ.get('PAYMENT_TBANK_TERMINAL', '')
PAYMENT_TBANK_PASSWORD = os.environ.get('PAYMENT_TBANK_PASSWORD', '')
PAYMENT_YOOKASSA_SHOP_ID = os.environ.get('PAYMENT_YOOKASSA_SHOP_ID', '')
PAYMENT_YOOKASSA_SECRET = os.environ.get('PAYMENT_YOOKASSA_SECRET', '')
PAYMENT_RECEIPT = _flag('PAYMENT_RECEIPT', True)  # передавать банку данные для чека (нужно, если подключена онлайн-касса банка)
PAYMENT_TAXATION = os.environ.get('PAYMENT_TAXATION', 'usn_income')  # система налогообложения для чека
PAYMENT_VAT = os.environ.get('PAYMENT_VAT', 'none')  # НДС для чека

# Заголовок с реальным IP посетителя (например HTTP_X_REAL_IP) — только если его ставит ваш nginx
SHOP_CLIENT_IP_HEADER = os.environ.get('SHOP_CLIENT_IP_HEADER') or None

# enforce — браузер блокирует чужие скрипты; report — только пишет предупреждения в консоль (удобно при разработке); off — выключено
CSP_MODE = os.environ.get('DJANGO_CSP') or ('report' if DEBUG else 'enforce')
# Уведомления о заказах отправляются в фоне, чтобы клиент не ждал; в тестах — сразу
NOTIFY_ASYNC = not TESTING

DATA_UPLOAD_MAX_MEMORY_SIZE = 1_000_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 5_000_000
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
CSRF_COOKIE_HTTPONLY = True  # токен для JS берём из <meta name="csrf-token">, а не из cookie

# Общий кэш для лимитов между несколькими процессами сервера. Название нарочно длинное:
# в старых файлах .env бывает REDIS_URL от прошлых версий, его сайт не читает. Без DJANGO_REDIS_URL — кэш в памяти процесса.
_redis_url = os.environ.get('DJANGO_REDIS_URL', '').strip()
if _redis_url:
    try:
        import redis  # noqa: F401
        CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': _redis_url}}
    except ImportError:
        pass

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'plain': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {'shop': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}

if not DEBUG:  # боевой режим: защищённые cookie, HTTPS, HSTS
    SECURE_SSL_REDIRECT = _flag('DJANGO_SSL', True)
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
    SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
    if _flag('DJANGO_BEHIND_PROXY'):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # «HSTS preload» — внесение сайта в список браузеров: решение на годы и не для каждого магазина, поэтому не включаем
    SILENCED_SYSTEM_CHECKS = ['security.W021']
BEHIND_PROXY = _flag('DJANGO_BEHIND_PROXY')
# Одноразовый код для создания владельца на сайте в интернете (на своём компьютере не нужен)
SETUP_TOKEN = os.environ.get('DJANGO_SETUP_TOKEN', '')
